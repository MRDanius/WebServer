import logging
import socket
from collections.abc import Generator
from server.core.config import Config
from server.protocol.response_builder import ResponseBuilder
from server.utils.file_manager import FileManager

log: logging.Logger = logging.getLogger(__name__)


class Handler:
    """
    Обработчик HTTP-запросов
    """

    METHODS: set[str] = {"GET", "HEAD"}
    ERROR_CONTENT_TYPE: str = "text/html"
    PROXY_SKIP_HEADERS: set[str] = {
        "connection",
        "content-length",
        "content-type",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }

    def __init__(self, file_service: FileManager, config: Config) -> None:
        """
        Инициализирует обработчик

        Args:
            file_service (FileManager): сервис работы с файлами
            config (Config): конфигурация сервера
        """
        self.file_service = file_service
        self.config = config
        self.response_builder: ResponseBuilder = ResponseBuilder()

    def resolve_keep_alive(self, headers: dict[str, str] | None, version: str) -> bool:
        """
        Определяет, нужно ли держать соединение открытым

        Args:
            headers (dict[str, str] | None): заголовки запроса
            version (str): версия HTTP

        Returns:
            bool: True, если соединение остаётся открытым
        """
        headers = headers or {}
        connection: str = headers.get("connection", "").lower()
        if version == "HTTP/1.0":
            return connection == "keep-alive"
        return connection != "close"

    def handle_request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        version: str = "HTTP/1.1",
        client_ip: str = "-",
    ) -> tuple[bytes, Generator[bytes, None, None] | None, bool]:
        """
        Маршрутизирует запрос к обработчику файлов, proxy или ошибки

        Args:
            method (str): метод HTTP
            path (str): путь запроса
            headers (dict[str, str] | None): заголовки запроса
            version (str): версия HTTP
            client_ip (str): IP клиента

        Returns:
            tuple[bytes, Generator[bytes, None, None] | None, bool]: заголовки, тело и флаг keep-alive
        """
        headers = headers or {}
        keep_alive: bool = self.resolve_keep_alive(headers, version)

        raw_host: str = headers.get("host", "default")
        clean_host: str = raw_host.split(":")[0]
        root_dir: str = self.config.servers.get(clean_host, self.config.default_root)
        if path == "/api" or path.startswith("/api/"):
            return self.handle_proxy(method, path, headers, version, client_ip, keep_alive)

        if method == "GET":
            headers_bytes, gen = self.handle_get(path, root_dir, client_ip, keep_alive)
            return headers_bytes, gen, keep_alive

        if method == "HEAD":
            headers_bytes, gen = self.handle_head(path, root_dir, client_ip, keep_alive)
            return headers_bytes, gen, keep_alive

        headers_bytes, gen = self.build_error_response(
            status=400,
            method=method,
            path=path,
            client_ip=client_ip,
            error_text="Bad request method",
            keep_alive=keep_alive
        )
        return headers_bytes, gen, keep_alive

    def handle_proxy(
        self,
        method: str,
        path: str,
        headers: dict[str, str],
        version: str,
        client_ip: str,
        keep_alive: bool,
    ) -> tuple[bytes, Generator[bytes, None, None] | None, bool]:
        """
        Проксирует запрос к внешнему серверу

        Args:
            method (str): метод HTTP
            path (str): путь запроса
            headers (dict[str, str]): заголовки запроса
            version (str): версия HTTP
            client_ip (str): IP клиента
            keep_alive (bool): флаг постоянного соединения

        Returns:
            tuple[bytes, Generator[bytes, None, None] | None, bool]: заголовки, тело и флаг keep-alive
        """
        if method not in self.METHODS:
            headers_bytes, gen = self.build_error_response(
                status=400,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Unsupported method for proxy",
                keep_alive=keep_alive
            )
            return headers_bytes, gen, keep_alive

        sock: socket.socket | None = None

        try:
            upstream_host: str = "httpbin.org"
            upstream_port: int = 80

            upstream_path: str = path[len("/api"):] or "/"

            request_lines: list[str] = [
                f"{method} {upstream_path} {version}",
                f"Host: {upstream_host}",
                "Connection: close",
            ]

            for k, v in (headers or {}).items():
                if k.lower() not in ("host", "connection"):
                    request_lines.append(f"{k}: {v}")

            request_data: str = "\r\n".join(request_lines) + "\r\n\r\n"

            sock = socket.create_connection(
                (upstream_host, upstream_port),
                timeout=5,
            )
            sock.sendall(request_data.encode("utf-8"))

            raw_headers: bytes = b""
            while b"\r\n\r\n" not in raw_headers:
                chunk: bytes = sock.recv(4096)
                if not chunk:
                    raise ValueError("Empty upstream response")
                raw_headers += chunk

            header_part: bytes
            first_body_chunk: bytes
            header_part, first_body_chunk = raw_headers.split(b"\r\n\r\n", 1)
            header_lines: list[str] = header_part.decode("utf-8").split("\r\n")

            status_line: list[str] = header_lines[0].split()
            if len(status_line) < 3:
                raise ValueError("Invalid status line")

            status_code: int = int(status_line[1])

            response_headers: dict[str, str] = {}
            extra_headers: list[tuple[str, str]] = []
            for line in header_lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    key: str = k.strip()
                    value: str = v.strip()
                    lower_key: str = key.lower()
                    response_headers[lower_key] = value

                    if lower_key not in self.PROXY_SKIP_HEADERS:
                        extra_headers.append((key, value))

            content_type: str = response_headers.get("content-type", "application/octet-stream")
            content_length: str | None = response_headers.get("content-length")
            transfer_encoding: str | None = response_headers.get("transfer-encoding")
            file_size: int | None = int(content_length) if content_length is not None else None

            if transfer_encoding and content_length is None:
                extra_headers.append(("Transfer-Encoding", transfer_encoding))

            if content_length is None and not transfer_encoding:
                keep_alive = False

            response_headers_bytes: bytes = self.response_builder.build_headers(
                status=status_code,
                file_size=file_size,
                content_type=content_type,
                method=method,
                keep_alive=keep_alive,
                extra_headers=extra_headers,
            )

            if method == "HEAD":
                sock.close()
                sock = None
                return response_headers_bytes, None, keep_alive

            log.info(
                "PROXY %s %s -> %s%s %s",
                client_ip,
                path,
                upstream_host,
                upstream_path,
                status_code,
            )

            content_generator: Generator[bytes, None, None] = self.stream_proxy_body(sock, first_body_chunk)
            sock = None
            return response_headers_bytes, content_generator, keep_alive

        except Exception:
            if sock is not None:
                sock.close()

            log.exception("Proxy error")

            headers_bytes, gen = self.build_error_response(
                status=500,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Proxy error",
                keep_alive=keep_alive
            )
            return headers_bytes, gen, keep_alive

    def stream_proxy_body(
        self,
        sock: socket.socket,
        first_chunk: bytes,
    ) -> Generator[bytes, None, None]:
        """
        Потоково читает тело ответа от upstream-сервера

        Args:
            sock (socket.socket): сокет соединения
            first_chunk (bytes): уже прочитанный фрагмент тела

        Yields:
            bytes: фрагменты тела ответа
        """
        try:
            if first_chunk:
                yield first_chunk

            while True:
                chunk: bytes = sock.recv(4096)
                if not chunk:
                    break
                yield chunk
        finally:
            sock.close()

    def handle_get(
        self,
        path: str,
        root_dir: str,
        client_ip: str = "-",
        keep_alive: bool = False,
    ) -> tuple[bytes, Generator[bytes, None, None] | None]:
        """
        Обрабатывает GET-запрос к файлу

        Args:
            path (str): путь запроса
            root_dir (str): корневая директория сайта
            client_ip (str): IP клиента
            keep_alive (bool): флаг постоянного соединения

        Returns:
            tuple[bytes, Generator[bytes, None, None] | None]: заголовки и генератор тела
        """
        return self.handle_file_request(
            method="GET",
            path=path,
            root_dir=root_dir,
            client_ip=client_ip,
            keep_alive=keep_alive
        )

    def handle_head(
        self,
        path: str,
        root_dir: str,
        client_ip: str = "-",
        keep_alive: bool = False,
    ) -> tuple[bytes, Generator[bytes, None, None] | None]:
        """
        Обрабатывает HEAD-запрос к файлу

        Args:
            path (str): путь запроса
            root_dir (str): корневая директория сайта
            client_ip (str): IP клиента
            keep_alive (bool): флаг постоянного соединения

        Returns:
            tuple[bytes, Generator[bytes, None, None] | None]: заголовки и генератор тела
        """
        return self.handle_file_request(
            method="HEAD",
            path=path,
            root_dir=root_dir,
            client_ip=client_ip,
            keep_alive=keep_alive
        )

    def handle_bad_request(
        self,
        client_ip: str = "-",
        error_text: str = "Bad request",
        keep_alive: bool = False,
    ) -> tuple[bytes, None, bool]:
        """
        Формирует ответ на некорректный запрос

        Args:
            client_ip (str): IP клиента
            error_text (str): текст ошибки для лога
            keep_alive (bool): флаг постоянного соединения

        Returns:
            tuple[bytes, None, bool]: заголовки ответа, None вместо тела и флаг keep-alive
        """
        headers_bytes, gen = self.build_error_response(
            status=400,
            method="GET",
            path="-",
            client_ip=client_ip,
            error_text=error_text,
            keep_alive=keep_alive
        )
        return headers_bytes, gen, keep_alive

    def handle_file_request(
        self,
        method: str,
        path: str,
        root_dir: str,
        client_ip: str,
        keep_alive: bool = False,
    ) -> tuple[bytes, Generator[bytes, None, None] | None]:
        """
        Отдаёт файл или страницу ошибки

        Args:
            method (str): метод HTTP
            path (str): путь запроса
            root_dir (str): корневая директория сайта
            client_ip (str): IP клиента
            keep_alive (bool): флаг постоянного соединения

        Returns:
            tuple[bytes, Generator[bytes, None, None] | None]: заголовки и генератор тела
        """
        try:
            content_generator: Generator[bytes, None, None]
            file_size: int
            content_type: str
            content_generator, file_size, content_type = self.file_service.get_file(path, root_dir)

            headers: bytes = self.response_builder.build_headers(
                status=200,
                file_size=file_size,
                content_type=content_type,
                method=method,
                keep_alive=keep_alive
            )

            log.info("ACCESS %s %s %s %s", client_ip, method, path, 200)
            if method == "HEAD":
                return headers, None

            return headers, content_generator

        except FileNotFoundError:
            return self.build_error_response(
                status=404,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="File not found",
                keep_alive=keep_alive
            )

        except PermissionError:
            return self.build_error_response(
                status=403,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Access forbidden",
                keep_alive=keep_alive
            )

        except Exception:
            log.exception("Unexpected error while handling request")

            return self.build_error_response(
                status=500,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Internal server error",
                keep_alive=keep_alive
            )

    def build_error_response(
        self,
        status: int,
        method: str,
        path: str,
        client_ip: str,
        error_text: str,
        keep_alive: bool = False,
    ) -> tuple[bytes, None]:
        """
        Формирует HTML-ответ с ошибкой

        Args:
            status (int): код состояния HTTP
            method (str): метод HTTP
            path (str): путь запроса
            client_ip (str): IP клиента
            error_text (str): текст ошибки для лога
            keep_alive (bool): флаг постоянного соединения

        Returns:
             tuple[bytes, None]: полный HTTP-ответ и None вместо тела
        """
        status_text: str = self.response_builder.get_status(status)
        content: bytes = f"<h1>{status} {status_text}</h1>".encode("utf-8")

        response_bytes: bytes = self.response_builder.build_response(
            status=status,
            content=content,
            content_type=self.ERROR_CONTENT_TYPE,
            method=method,
            keep_alive=keep_alive
        )

        log.error("ERROR %s %s %s %s %s", client_ip, method, path, status, error_text)
        return response_bytes, None
