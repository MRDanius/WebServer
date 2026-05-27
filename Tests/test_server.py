import socket
import ssl
import unittest
from collections.abc import Generator
from unittest.mock import MagicMock, patch

from server.core.config import Config
from server.core.server import Server


class ServerTests(unittest.TestCase):
    """
    Тесты сетевого слоя веб-сервера
    """

    def setUp(self) -> None:
        """
        Подготовка окружения перед каждым тестом
        """
        self.mock_config: MagicMock = MagicMock(spec=Config)
        self.mock_config.host = "127.0.0.1"
        self.mock_config.port = 8080
        self.mock_config.read_timeout = 5
        self.mock_config.write_timeout = 5
        self.mock_config.upload_limit = 0
        self.mock_config.download_limit = 0

        self.server: Server = Server(self.mock_config)

    def test_init(self) -> None:
        """
        Проверяет корректную инициализацию компонентов сервера
        """
        self.assertFalse(self.server.run_flag)
        self.assertEqual(self.server.config, self.mock_config)
        self.assertIsNotNone(self.server.file_manager)
        self.assertIsNotNone(self.server.handler)
        self.assertIsNotNone(self.server.parser)

    def test_stop(self) -> None:
        """
        Проверяет корректное изменение флагов и закрытие сокета
        """
        self.server.run_flag = True
        self.server.socket_listener = MagicMock()

        self.server.stop()

        self.assertFalse(self.server.run_flag)
        self.server.socket_listener.close.assert_called_once()

    @patch("server.core.server.socket.socket")
    def test_start_http_success(self, mock_socket_class: MagicMock) -> None:
        """
        Проверяет инициализацию и привязку сокета в режиме HTTP
        """
        self.mock_config.ssl_cert = ""
        self.mock_config.ssl_key = ""
        mock_sock: MagicMock = MagicMock()
        mock_socket_class.return_value = mock_sock

        with patch.object(self.server, "accept_client") as mock_accept:
            self.server.start()
            mock_accept.assert_called_once()

        mock_sock.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET, socket.SO_REUSEADDR, 1
        )
        mock_sock.bind.assert_called_with(("127.0.0.1", 8080))
        mock_sock.listen.assert_called_once_with(100)

    @patch("server.core.server.ssl.create_default_context")
    @patch("server.core.server.socket.socket")
    def test_start_https_success(
        self, mock_socket_class: MagicMock, mock_ssl_context: MagicMock
    ) -> None:
        """
        Проверяет инициализацию и настройку контекста HTTPS
        """
        self.mock_config.ssl_cert = "cert.pem"
        self.mock_config.ssl_key = "key.pem"

        mock_sock: MagicMock = MagicMock()
        mock_socket_class.return_value = mock_sock

        mock_context_instance: MagicMock = MagicMock()
        mock_ssl_context.return_value = mock_context_instance

        with patch.object(self.server, "accept_client") as mock_accept:
            self.server.start()
            mock_accept.assert_called_once()

        mock_ssl_context.assert_called_once_with(ssl.Purpose.CLIENT_AUTH)
        mock_context_instance.load_cert_chain.assert_called_once_with(
            certfile="cert.pem", keyfile="key.pem"
        )
        mock_context_instance.wrap_socket.assert_called_once_with(
            mock_sock, server_side=True
        )

    def test_process_client_disconnect_on_recv(self) -> None:
        """
        Проверяет закрытие соединения, если клиент отключился сразу
        """
        mock_client_socket: MagicMock = MagicMock()
        mock_client_socket.recv.return_value = b""

        self.server._process_client(mock_client_socket, "127.0.0.1")

        mock_client_socket.close.assert_called_once()

    def test_process_client_read_timeout(self) -> None:
        """
        Проверяет обработку исключения таймаута при чтении запроса
        """
        mock_client_socket: MagicMock = MagicMock()
        mock_client_socket.recv.side_effect = socket.timeout

        self.server._process_client(mock_client_socket, "127.0.0.1")

        mock_client_socket.close.assert_called_once()

    def test_process_client_value_error_handling(self) -> None:
        """
        Проверяет перехват ValueError от парсера и отправку 400
        """
        mock_client_socket: MagicMock = MagicMock()
        mock_client_socket.recv.side_effect = [
            b"INVALID REQUEST\r\n\r\n", b""
        ]

        self.server.parser.parse_request = MagicMock(
            side_effect=ValueError("Invalid HTTP format")
        )
        self.server.handler.handle_bad_request = MagicMock(
            return_value=(b"HTTP/1.1 400 Bad Request\r\n\r\n", None, False)
        )

        self.server._process_client(mock_client_socket, "127.0.0.1")

        self.server.handler.handle_bad_request.assert_called_once_with(
            client_ip="127.0.0.1",
            error_text="Invalid HTTP format",
            keep_alive=False,
        )
        mock_client_socket.sendall.assert_called_once_with(
            b"HTTP/1.1 400 Bad Request\r\n\r\n"
        )
        mock_client_socket.close.assert_called_once()

    def test_process_client_streaming_response(self) -> None:
        """
        Проверяет цикл отправки и итерации по генератору тела ответа
        """
        mock_client_socket: MagicMock = MagicMock()
        mock_client_socket.recv.side_effect = [
            b"GET /index.html HTTP/1.1\r\n\r\n", b""
        ]

        def sample_generator() -> Generator[bytes, None, None]:
            yield b"chunk1"
            yield b"chunk2"

        gen: Generator[bytes, None, None] = sample_generator()

        self.server.parser.parse_request = MagicMock(
            return_value={
                "operation": "GET",
                "path": "/index.html",
                "version": "HTTP/1.1",
            }
        )
        self.server.handler.handle_request = MagicMock(
            return_value=(b"HTTP/1.1 200 OK\r\n\r\n", gen, False)
        )

        self.server._process_client(mock_client_socket, "127.0.0.1")

        mock_client_socket.sendall.assert_any_call(b"HTTP/1.1 200 OK\r\n\r\n")
        mock_client_socket.sendall.assert_any_call(b"chunk1")
        mock_client_socket.sendall.assert_any_call(b"chunk2")
        mock_client_socket.close.assert_called_once()

    def test_process_client_write_timeout(self) -> None:
        """
        Проверяет безопасный выход из метода при таймауте записи
        """
        mock_client_socket: MagicMock = MagicMock()
        mock_client_socket.recv.side_effect = [
            b"GET / HTTP/1.1\r\n\r\n", b""
        ]
        mock_client_socket.sendall.side_effect = socket.timeout

        self.server.parser.parse_request = MagicMock(
            return_value={
                "operation": "GET",
                "path": "/",
                "version": "HTTP/1.1",
            }
        )
        self.server.handler.handle_request = MagicMock(
            return_value=(b"HTTP/1.1 200 OK\r\n\r\n", None, False)
        )

        self.server._process_client(mock_client_socket, "127.0.0.1")

        mock_client_socket.close.assert_called_once()

    def test_process_client_critical_exception_safety(self) -> None:
        """
        Проверяет закрытие сокета при критическом исключении
        """
        mock_client_socket: MagicMock = MagicMock()
        mock_client_socket.recv.side_effect = RuntimeError(
            "Critical hardware failure"
        )

        self.server._process_client(mock_client_socket, "127.0.0.1")

        mock_client_socket.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
