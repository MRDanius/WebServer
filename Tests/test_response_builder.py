import unittest

from server.protocol.response_builder import ResponseBuilder


class ResponseBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = ResponseBuilder()

    def test_build_get_response(self):
        content = b"<h1>Hello</h1>"

        result = self.builder.build_response(200, content, "text/html", "GET")

        expected = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"<h1>Hello</h1>"
        )

        self.assertEqual(result, expected)

    def test_build_head_response(self):
        content = b"<h1>Hello</h1>"

        result = self.builder.build_response(200, content, "text/html", "HEAD")

        expected = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )

        self.assertEqual(result, expected)

    def test_build_headers(self):
        result = self.builder.build_headers(200, 14, "text/html", "GET")

        expected = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )

        self.assertEqual(result, expected)

    def test_unknown_status_code(self):
        with self.assertRaises(ValueError) as error:
            self.builder.build_response(999, b"Hello", "text/plain", "GET")

        self.assertEqual(str(error.exception), "Unknown status code: 999")

    def test_content_length(self):
        content = b"HELLo"

        result = self.builder.build_response(200, content, "text/plain", "GET")

        self.assertIn(b"Content-Length: 5\r\n", result)


if __name__ == "__main__":
    unittest.main()
