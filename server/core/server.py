import logging
import socket
import ssl
import threading

from server.core.handler import Handler
from server.protocol.parser import Parser
from server.utils.file_manager import FileManager
from server.utils.rate_limiter import RateLimiter


log = logging.getLogger(__name__)

class Server:
    def __init__(self, config):
        self.config = config
        self.run_flag = False
        self.socket_listener = None

        self.file_manager = FileManager()
        self.handler = Handler(self.file_manager, self.config)
        self.parser = Parser()

    def start(self):
        self.run_flag = True
        self.socket_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket_listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket_listener.settimeout(1.0)
        self.socket_listener.bind((self.config.host, self.config.port))
        self.socket_listener.listen(100)

        if getattr(self.config, "ssl_cert", None) and getattr(self.config, "ssl_key", None):
            context =ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
            context.load_cert_chain(certfile=self.config.ssl_cert, keyfile=self.config.ssl_key)
            self.socket_listener = context.wrap_socket(self.socket_listener, server_side=True)
            log.warning(f"Сервер запущен (HTTPS) на {self.config.host}:{self.config.port}")
        else:
            log.warning(f"Сервер запущен (HTTP) на {self.config.host}:{self.config.port}")

        self.accept_client()

    def accept_client(self):
        log.warning("Ожидание клиентов ...")
        threads = []
        while self.run_flag:
            try:
                client_socket, address = self.socket_listener.accept()
                client_ip = address[0]
                log.warning(f'Подключение: {client_ip} ')

                client_thread = threading.Thread(
                    target=self._process_client,
                    args=(client_socket, client_ip)
                )
                client_thread.start()
                threads.append(client_thread)
            except socket.timeout:
                continue
            except Exception as e:
                if self.run_flag:
                    log.error(f"Произошла ошибка при установке соединения: {e}")
        for t in threads:
            t.join()

    def _process_client(self, client_socket, client_ip):
        try:
            while True:
                client_socket.settimeout(self.config.read_timeout)

                upload_limiter = RateLimiter(getattr(self.config, "upload_limit", 0))
                raw_request = b""
                while b"\r\n\r\n" not in raw_request:
                    try:
                        chunk = client_socket.recv(4096)
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
                    params = self.parser.parse_request(raw_request)
                    headers, content_generator, keep_alive = self.handler.handle_request(
                        method=params.get("operation"),
                        path=params.get("path"),
                        headers=params.get("headers"),
                        version=params.get("version", "HTTP/1.1"),
                        client_ip=client_ip
                    )
                except ValueError as e:
                    log.warning(f"Некорректный запрос от {client_ip}: {e}")
                    headers, content_generator, keep_alive = self.handler.handle_bad_request(
                        client_ip=client_ip,
                        error_text=str(e),
                        keep_alive=False
                    )
                client_socket.settimeout(self.config.write_timeout)
                download_limiter = RateLimiter(getattr(self.config, "download_limit", 0))
                try:
                    download_limiter.wait(len(headers))
                    client_socket.sendall(headers)

                    if content_generator is not None:
                        for chunk in content_generator:
                            download_limiter.wait(len(chunk))
                            client_socket.sendall(chunk)
                except socket.timeout:
                    log.warning(f"Таймаут записи (Write Timeout) для клиента {client_ip}")
                    return

                if not keep_alive:
                    break

        except Exception as e:
            log.error(f"Сбой потока при обработке {client_ip}: {e}")
        finally:
            client_socket.close()

    def stop(self):
        log.warning("Остановка сервера...")
        self.run_flag = False
        if self.socket_listener:
            self.socket_listener.close()