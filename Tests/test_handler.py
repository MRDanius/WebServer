import unittest

from server.core.handler import Handler


class FakeFileService:
    def __init__(self, error=None):
        self.error = error

    def get_file(self, path):
        if self.error:
            raise self.error

        return iter([b"<h1>Hello</h1>"]), 14, "text/html"


class HandlerTests(unittest.TestCase):
    def test_handle_get_success(self):
        handler = Handler(FakeFileService())

        headers, content_generator = handler.handle_request("GET", "/index.html")
        result = headers + b"".join(content_generator)

        expected = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"<h1>Hello</h1>"
        )

        self.assertEqual(result, expected)

    def test_handle_head_success(self):
        handler = Handler(FakeFileService())

        headers, content_generator = handler.handle_request("HEAD", "/index.html")

        expected = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Length: 14\r\n"
            b"Content-Type: text/html\r\n"
            b"Connection: close\r\n"
            b"\r\n"
        )

        self.assertEqual(headers, expected)
        self.assertIsNone(content_generator)

    def test_handle_bad_method(self):
        handler = Handler(FakeFileService())

        result, content_generator = handler.handle_request("POST", "/index.html")

        self.assertIn(b"HTTP/1.1 400 Bad Request\r\n", result)
        self.assertIn(b"<h1>400 Bad Request</h1>", result)
        self.assertIsNone(content_generator)

    def test_handle_file_not_found(self):
        handler = Handler(FakeFileService(FileNotFoundError()))

        result, content_generator = handler.handle_request("GET", "/missing.html")

        self.assertIn(b"HTTP/1.1 404 Not Found\r\n", result)
        self.assertIn(b"<h1>404 Not Found</h1>", result)
        self.assertIsNone(content_generator)

    def test_handle_forbidden_file(self):
        handler = Handler(FakeFileService(PermissionError()))

        result, content_generator = handler.handle_request("GET", "/.env")

        self.assertIn(b"HTTP/1.1 403 Forbidden\r\n", result)
        self.assertIn(b"<h1>403 Forbidden</h1>", result)
        self.assertIsNone(content_generator)

    def test_handle_unexpected_error(self):
        handler = Handler(FakeFileService(RuntimeError()))

        result, content_generator = handler.handle_request("GET", "/index.html")

        self.assertIn(b"HTTP/1.1 500 Internal Server Error\r\n", result)
        self.assertIn(b"<h1>500 Internal Server Error</h1>", result)
        self.assertIsNone(content_generator)

    def test_handle_bad_request(self):
        handler = Handler(FakeFileService())

        result, content_generator = handler.handle_bad_request(error_text="Invalid request")

        self.assertIn(b"HTTP/1.1 400 Bad Request\r\n", result)
        self.assertIn(b"<h1>400 Bad Request</h1>", result)
        self.assertIsNone(content_generator)


if __name__ == "__main__":
    unittest.main()
