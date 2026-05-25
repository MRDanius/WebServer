import unittest

from server.protocol.parser import Parser


class ParseRequestTests(unittest.TestCase):
    """
    Тесты парсера HTTP-запросов
    """

    parser: Parser

    def setUp(self) -> None:
        """
        Создаёт экземпляр парсера перед каждым тестом
        """
        self.parser = Parser()

    def test_parse_valid_get_request(self) -> None:
        """
        Проверяет разбор корректного GET-запроса
        """
        request: bytes = (
            b"GET /index.html HTTP/1.1\r\n"
            b"Host: localhost:8080\r\n"
            b"User-Agent: Mozilla/5.0\r\n"
            b"\r\n"
        )

        result: dict[str, str | dict[str, str]] = (
            self.parser.parse_request(request)
        )

        self.assertEqual(result["operation"], "GET")
        self.assertEqual(result["path"], "/index.html")
        self.assertEqual(result["version"], "HTTP/1.1")
        self.assertEqual(result["headers"]["host"], "localhost:8080")
        self.assertEqual(result["headers"]["user-agent"], "Mozilla/5.0")

    def test_parse_valid_head_request(self) -> None:
        """
        Проверяет разбор корректного HEAD-запроса
        """
        request: bytes = (
            b"HEAD / HTTP/1.0\r\n"
            b"Host: localhost\r\n"
            b"\r\n"
        )

        result: dict[str, str | dict[str, str]] = (
            self.parser.parse_request(request)
        )

        self.assertEqual(result["operation"], "HEAD")
        self.assertEqual(result["path"], "/")
        self.assertEqual(result["version"], "HTTP/1.0")
        self.assertEqual(result["headers"]["host"], "localhost")

    def test_empty_request(self) -> None:
        """
        Проверяет ошибку при пустом запросе
        """
        with self.assertRaises(ValueError) as error:
            self.parser.parse_request(b"")

        self.assertEqual(str(error.exception), "Request is empty")

    def test_incomplete_request(self) -> None:
        """
        Проверяет ошибку при неполном запросе
        """
        request: bytes = b"GET / HTTP/1.1\r\nHost: localhost:8080\r\n"

        with self.assertRaises(ValueError) as error:
            self.parser.parse_request(request)

        self.assertEqual(str(error.exception), "Request is incomplete")

    def test_invalid_request(self) -> None:
        """
        Проверяет ошибку при некорректной строке запроса
        """
        request: bytes = b"GET /index.html\r\nHost: localhost:8080\r\n\r\n"

        with self.assertRaises(ValueError) as error:
            self.parser.parse_request(request)

        self.assertEqual(str(error.exception), "Invalid request line")

    def test_invalid_method(self) -> None:
        """
        Проверяет ошибку при недопустимом методе
        """
        request: bytes = (
            b"POST /index.html HTTP/1.1\r\n"
            b"Host: localhost:8080\r\n\r\n"
        )

        with self.assertRaises(ValueError) as error:
            self.parser.parse_request(request)

        self.assertEqual(str(error.exception), "Invalid request method")

    def test_invalid_path(self) -> None:
        """
        Проверяет ошибку при некорректном пути
        """
        request: bytes = (
            b"GET index.html HTTP/1.1\r\n"
            b"Host: localhost:8080\r\n\r\n"
        )

        with self.assertRaises(ValueError) as error:
            self.parser.parse_request(request)

        self.assertEqual(str(error.exception), "Path is empty")

    def test_invalid_version(self) -> None:
        """
        Проверяет ошибку при недопустимой версии HTTP
        """
        request: bytes = (
            b"GET /index.html HTTP/2.0\r\n"
            b"Host: localhost:8080\r\n\r\n"
        )

        with self.assertRaises(ValueError) as error:
            self.parser.parse_request(request)

        self.assertEqual(str(error.exception), "Invalid request version")

    def test_invalid_header(self) -> None:
        """
        Проверяет ошибку при некорректной строке заголовка
        """
        request: bytes = (
            b"GET / HTTP/1.1\r\n"
            b"BrokenHeader\r\n"
            b"\r\n"
        )

        with self.assertRaises(ValueError) as error:
            self.parser.parse_request(request)

        self.assertEqual(str(error.exception), "Invalid header line")


if __name__ == "__main__":
    unittest.main()
