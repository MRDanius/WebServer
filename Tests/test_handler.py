import unittest
from collections.abc import Generator, Iterator
from unittest.mock import MagicMock, patch

from server.core.handler import Handler


class FakeConfig:
    """
    Заглушка конфигурации для тестов
    """

    def __init__(self) -> None:
        self.default_root: str = "./static"
        self.servers: dict[str, str] = {}


class FakeFileService:
    """
    Заглушка файлового сервиса для тестов
    """

    def __init__(self, error: Exception | None = None) -> None:
        self.error: Exception | None = error

    def get_file(
        self, path: str, root_dir: str
    ) -> tuple[Iterator[bytes], int, str]:
        if self.error:
            raise self.error

        return iter([b"<h1>Hello</h1>"]), 14, "text/html"


class HandlerTests(unittest.TestCase):
    """
    Тесты обработчика HTTP-запросов
    """

    def test_handle_get_success(self) -> None:
        """
        Проверяет успешную обработку GET-запроса
        """
        handler = Handler(FakeFileService(), FakeConfig())

        headers: bytes
        content_generator: Generator[bytes, None, None] | None
        keep_alive: bool
        headers, content_generator, keep_alive = handler.handle_request(
            "GET", "/index.html"
        )
        result: bytes = headers + b"".join(content_generator)

        expected: bytes = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: keep-alive\r\n"
            b"\r\n"
            b"<h1>Hello</h1>"
        )

        self.assertEqual(result, expected)
        self.assertTrue(keep_alive)

    def test_handle_head_success(self) -> None:
        """
        Проверяет успешную обработку HEAD-запроса
        """
        handler = Handler(FakeFileService(), FakeConfig())

        headers: bytes
        content_generator: Generator[bytes, None, None] | None
        keep_alive: bool
        headers, content_generator, keep_alive = handler.handle_request(
            "HEAD", "/index.html"
        )

        expected: bytes = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: keep-alive\r\n"
            b"\r\n"
        )

        self.assertEqual(headers, expected)
        self.assertIsNone(content_generator)
        self.assertTrue(keep_alive)

    def test_handle_bad_method(self) -> None:
        """
        Проверяет ответ при недопустимом методе
        """
        handler = Handler(FakeFileService(), FakeConfig())

        result: bytes
        content_generator: Generator[bytes, None, None] | None
        keep_alive: bool
        result, content_generator, keep_alive = handler.handle_request(
            "POST", "/index.html"
        )

        self.assertIn(b"HTTP/1.1 400 Bad Request\r\n", result)
        self.assertIn(b"<h1>400 Bad Request</h1>", result)
        self.assertIsNone(content_generator)
        self.assertTrue(keep_alive)

    def test_handle_file_not_found(self) -> None:
        """
        Проверяет ответ при отсутствии файла
        """
        handler = Handler(FakeFileService(FileNotFoundError()), FakeConfig())

        result: bytes
        content_generator: Generator[bytes, None, None] | None
        keep_alive: bool
        result, content_generator, keep_alive = handler.handle_request(
            "GET", "/missing.html"
        )

        self.assertIn(b"HTTP/1.1 404 Not Found\r\n", result)
        self.assertIn(b"<h1>404 Not Found</h1>", result)
        self.assertIsNone(content_generator)
        self.assertTrue(keep_alive)

    def test_handle_forbidden_file(self) -> None:
        """
        Проверяет ответ при запрете доступа к файлу
        """
        handler = Handler(FakeFileService(PermissionError()), FakeConfig())

        result: bytes
        content_generator: Generator[bytes, None, None] | None
        keep_alive: bool
        result, content_generator, keep_alive = handler.handle_request(
            "GET", "/.env"
        )

        self.assertIn(b"HTTP/1.1 403 Forbidden\r\n", result)
        self.assertIn(b"<h1>403 Forbidden</h1>", result)
        self.assertIsNone(content_generator)
        self.assertTrue(keep_alive)

    def test_handle_unexpected_error(self) -> None:
        """
        Проверяет ответ при непредвиденной ошибке
        """
        handler = Handler(FakeFileService(RuntimeError()), FakeConfig())

        result: bytes
        content_generator: Generator[bytes, None, None] | None
        keep_alive: bool
        result, content_generator, keep_alive = handler.handle_request(
            "GET", "/index.html"
        )

        self.assertIn(b"HTTP/1.1 500 Internal Server Error\r\n", result)
        self.assertIn(b"<h1>500 Internal Server Error</h1>", result)
        self.assertIsNone(content_generator)
        self.assertTrue(keep_alive)

    def test_handle_bad_request(self) -> None:
        """
        Проверяет ответ на некорректный запрос
        """
        handler = Handler(FakeFileService(), FakeConfig())

        result: bytes
        content_generator: Generator[bytes, None, None] | None
        keep_alive: bool
        result, content_generator, keep_alive = handler.handle_bad_request(
            error_text="Invalid request"
        )

        self.assertIn(b"HTTP/1.1 400 Bad Request\r\n", result)
        self.assertIn(b"<h1>400 Bad Request</h1>", result)
        self.assertIsNone(content_generator)
        self.assertFalse(keep_alive)

    def test_connection_close_header(self) -> None:
        """
        Проверяет закрытие соединения по заголовку Connection: close
        """
        handler = Handler(FakeFileService(), FakeConfig())

        headers: bytes
        content_generator: Generator[bytes, None, None] | None
        keep_alive: bool
        headers, content_generator, keep_alive = handler.handle_request(
            "GET",
            "/index.html",
            headers={"connection": "close"},
        )

        self.assertIn(b"Connection: close\r\n", headers)
        self.assertFalse(keep_alive)

    def test_resolve_keep_alive_http11_default(self) -> None:
        """
        Проверяет keep-alive по умолчанию для HTTP/1.1
        """
        handler = Handler(FakeFileService(), FakeConfig())

        self.assertTrue(handler.resolve_keep_alive({}, "HTTP/1.1"))

    def test_resolve_keep_alive_with_close(self) -> None:
        """
        Проверяет отключение keep-alive при Connection: close
        """
        handler = Handler(FakeFileService(), FakeConfig())

        self.assertFalse(
            handler.resolve_keep_alive({"connection": "close"}, "HTTP/1.1")
        )

    def test_handle_proxy_route(self) -> None:
        """
        Проверяет перенаправление запросов /api в proxy
        """
        handler = Handler(FakeFileService(), FakeConfig())

        with patch.object(
                handler,
                "handle_proxy",
                return_value=(b"proxy-response", None, True),
        ) as mock_proxy:
            result: tuple[bytes, None, bool]
            result = handler.handle_request(
                "GET",
                "/api/get",
                headers={"host": "localhost:8080"},
                version="HTTP/1.1",
                client_ip="127.0.0.1",
            )

        self.assertEqual(result, (b"proxy-response", None, True))

        mock_proxy.assert_called_once_with(
            "GET",
            "/api/get",
            {"host": "localhost:8080"},
            "HTTP/1.1",
            "127.0.0.1",
            True,
        )

    def test_handle_proxy_success(self) -> None:
        """
        Проверяет успешную обработку proxy-запроса
        """
        handler = Handler(FakeFileService(), FakeConfig())

        raw_response: bytes = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 5\r\n"
            b"\r\n"
            b"hello"
        )

        mock_socket = MagicMock()
        mock_socket.recv.side_effect = [
            raw_response,
            b"",
        ]

        with patch(
                "server.core.handler.socket.create_connection",
                return_value=mock_socket,
        ):
            headers: bytes
            content_generator: Generator[bytes, None, None] | None
            keep_alive: bool

            headers, content_generator, keep_alive = handler.handle_proxy(
                "GET",
                "/api/get",
                {"host": "localhost:8080"},
                "HTTP/1.1",
                "127.0.0.1",
                True,
            )

        result: bytes = headers + b"".join(content_generator)

        expected: bytes = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 5\r\n"
            b"Content-Type: text/plain\r\n"
            b"Connection: keep-alive\r\n"
            b"\r\n"
            b"hello"
        )

        self.assertEqual(result, expected)
        self.assertTrue(keep_alive)


if __name__ == "__main__":
    unittest.main()
