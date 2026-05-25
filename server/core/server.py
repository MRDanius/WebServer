import logging
import socket
import ssl
import threading
from collections.abc import Generator
from typing import Any

from server.core.config import Config
from server.core.handler import Handler
from server.protocol.parser import Parser
from server.utils.file_manager import FileManager
from server.utils.rate_limiter import RateLimiter

log: logging.Logger = logging.getLogger(__name__)


class Server:
    """
    Многопоточный веб-сервер.

    Обеспечивает жизненный цикл системных сокетов, сетевой обмен данными,
    распределение клиентских подключений по потокам, а также применение
    политик QoS (ограничение скорости и сетевые таймауты).
    """

    def __init__(self, config: Config) -> None:
        """
        Инициализирует основные компоненты сетевого слоя сервера

        Args:
            config (Config): объект конфигурации сервера
        """
        self.config: Config = config
        self.run_flag: bool = False
        self.socket_listener: socket.socket | None = None

        # Инициализация дочерних сервисов с указанием типов
        self.file_manager: FileManager = FileManager()
        self.handler: Handler = Handler(self.file_manager, self.config)
        self.parser: Parser = Parser()

    def start(self) -> None:
        """
        Запускает слушающий сокет сервера, настраивает SSL (HTTPS)
        при наличии ключей и переходит в режим ожидания клиентов
        """
        self.run_flag = True
        self.socket_listener = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM
        )
        self.socket_listener.setsockopt(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )
        self.socket_listener.settimeout(1.0)
        self.socket_listener.bind((self.config.host, self.config.port))
        self.socket_listener.listen(100)

        if getattr(self.config, "ssl_cert", None) and getattr(
            self.config, "ssl_key", None
        ):
            context: ssl.SSLContext = ssl.create_default_context(
                ssl.Purpose.CLIENT_AUTH
            )
            context.load_cert_chain(
                certfile=self.config.ssl_cert,
                keyfile=self.config.ssl_key,
            )
            self.socket_listener = context.wrap_socket(
                self.socket_listener, server_side=True
            )
            log.warning(
                f"Сервер запущен (HTTPS) на "
                f"{self.config.host}:{self.config.port}"
            )
        else:
            log.warning(
                f"Сервер запущен (HTTP) на "
                f"{self.config.host}:{self.config.port}"
            )

        self.accept_client()

    def accept_client(self) -> None:
        """
        Бесконечно принимает входящие TCP-соединения в цикле и распределяет
        каждого клиента в отдельный изолированный поток выполнения.
        """
        log.warning("Ожидание клиентов ...")
        threads: list[threading.Thread] = []

        while self.run_flag:
            try:
                client_socket: socket.socket
                address: tuple[str, int]
                client_socket, address = self.socket_listener.accept()
                client_ip: str = address[0]
                log.warning(f'Подключение: {client_ip} ')

                client_thread: threading.Thread = threading.Thread(
                    target=self._process_client,
                    args=(client_socket, client_ip)
                )
                client_thread.start()
                threads.append(client_thread)
            except socket.timeout:
                continue
            except Exception as e:
                if self.run_flag:
                    log.error(
                        f"Произошла ошибка при установке соединения: {e}"
                    )

        for t in threads:
            t.join()

    def _process_client(
        self, client_socket: socket.socket, client_ip: str
    ) -> None:
        """
        Управляет жизненным циклом соединения с клиентом.
        Читает запрос с лимитом upload, маршрутизирует
        и отправляет ответ с лимитом download.

        Args:
            client_socket (socket.socket): сокет клиентского соединения
            client_ip (str): IP-адрес клиента
        """
        try:
            while True:
                # Настройка таймаута на чтение запроса
                client_socket.settimeout(self.config.read_timeout)

                # Создание лимитера входящей скорости
                upload_limiter: RateLimiter = RateLimiter(
                    getattr(self.config, "upload_limit", 0)
                )
                raw_request: bytes = b""

                while b"\r\n\r\n" not in raw_request:
                    try:
                        chunk: bytes = client_socket.recv(4096)
                    except socket.timeout:
                        log.warning(f"Таймаут клиента {client_ip}")
                        return
                    if not chunk:
                        return
                    upload_limiter.wait(len(chunk))
                    raw_request += chunk

                if not raw_request:
                    return

                try:
                    params: dict[str, Any] = self.parser.parse_request(
                        raw_request
                    )

                    headers: bytes
                    content_generator: Generator[bytes, None, None] | None
                    keep_alive: bool

                    headers, content_generator, keep_alive = (
                        self.handler.handle_request(
                            method=params.get("operation"),
                            path=params.get("path"),
                            headers=params.get("headers"),
                            version=params.get("version", "HTTP/1.1"),
                            client_ip=client_ip,
                        )
                    )
                except ValueError as e:
                    log.warning(f"Некорректный запрос от {client_ip}: {e}")
                    headers, content_generator, keep_alive = (
                        self.handler.handle_bad_request(
                            client_ip=client_ip,
                            error_text=str(e),
                            keep_alive=False,
                        )
                    )

                client_socket.settimeout(self.config.write_timeout)

                # Создание лимитера исходящей скорости
                download_limiter: RateLimiter = RateLimiter(
                    getattr(self.config, "download_limit", 0)
                )

                try:
                    download_limiter.wait(len(headers))
                    client_socket.sendall(headers)

                    if content_generator is not None:
                        for chunk in content_generator:
                            download_limiter.wait(len(chunk))
                            client_socket.sendall(chunk)
                except socket.timeout:
                    log.warning(
                        f"Таймаут записи (Write Timeout) "
                        f"для клиента {client_ip}"
                    )
                    return

                if not keep_alive:
                    break

        except Exception as e:
            log.error(f"Сбой потока при обработке {client_ip}: {e}")
        finally:
            client_socket.close()

    def stop(self) -> None:
        """
        Останавливает главный цикл сервера и закрывает слушающий сокет.
        """
        log.warning("Остановка сервера...")
        self.run_flag = False
        if self.socket_listener:
            self.socket_listener.close()
