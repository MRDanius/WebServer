import unittest

from server.protocol.response_builder import ResponseBuilder


class ResponseBuilderTests(unittest.TestCase):
    """
    Тесты сборщика HTTP-ответов
    """

    builder: ResponseBuilder

    def setUp(self) -> None:
        """
        Создаёт экземпляр сборщика перед каждым тестом
        """
        self.builder = ResponseBuilder()

    def test_build_get_response(self) -> None:
        """
        Проверяет полный ответ для метода GET
        """
        content: bytes = b"<h1>Hello</h1>"

        result: bytes = self.builder.build_response(200, content, "text/html", "GET")

        expected: bytes = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"<h1>Hello</h1>"
        )

        self.assertEqual(result, expected)

    def test_build_head_response(self) -> None:
        """
        Проверяет ответ без тела для метода HEAD
        """
        content: bytes = b"<h1>Hello</h1>"

        result: bytes = self.builder.build_response(200, content, "text/html", "HEAD")

        expected: bytes = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )

        self.assertEqual(result, expected)

    def test_build_headers(self) -> None:
        """
        Проверяет формирование только заголовков ответа
        """
        result: bytes = self.builder.build_headers(200, 14, "text/html", "GET")

        expected: bytes = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )

        self.assertEqual(result, expected)

    def test_unknown_status_code(self) -> None:
        """
        Проверяет ошибку при неизвестном коде состояния
        """
        with self.assertRaises(ValueError) as error:
            self.builder.build_response(999, b"Hello", "text/plain", "GET")

        self.assertEqual(str(error.exception), "Unknown status code: 999")

    def test_content_length(self) -> None:
        """
        Проверяет заголовок Content-Length в ответе
        """
        content: bytes = b"HELLo"

        result: bytes = self.builder.build_response(200, content, "text/plain", "GET")

        self.assertIn(b"Content-Length: 5\r\n", result)

    def test_head_contains_content_length(self) -> None:
        """
        Проверяет Content-Length в HEAD-ответе без тела
        """
        result: bytes = self.builder.build_response(
            200,
            b"hello",
            "text/plain",
            "HEAD"
        )

        self.assertIn(b"Content-Length: 5\r\n", result)
        self.assertNotIn(b"hello", result)

    def test_keep_alive_header(self) -> None:
        """
        Проверяет заголовок Connection: keep-alive
        """
        result: bytes = self.builder.build_response(
            200,
            b"hello",
            "text/plain",
            "GET",
            keep_alive=True
        )

        self.assertIn(b"Connection: keep-alive\r\n", result)


if __name__ == "__main__":
    unittest.main()
