import socket
import unittest
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
        Проверяет корректное изменение флагов и закрытия сокета при остановке
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

        mock_sock.setsockopt.assert_called_once_with(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        mock_sock.bind.assert_called_with(("127.0.0.1", 8080))
        mock_sock.listen.assert_called_once_with(100)

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


if __name__ == "__main__":
    unittest.main()