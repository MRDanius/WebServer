import logging
from http import HTTPStatus


log = logging.getLogger(__name__)


class ResponseBuilder:
    CODES = {
        200: "OK",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        500: "Internal Server Error",
    }

    def build_headers(
        self,
        status,
        file_size,
        content_type,
        method,
        keep_alive=False,
        extra_headers=None,
    ):
        answer_line = f"HTTP/1.1 {status} {self.get_status(status)}\r\n"
        connection = "keep-alive" if keep_alive else "close"

        headers = [
            f"Content-Type: {content_type}",
        ]

        if file_size is not None:
            headers.insert(0, f"Content-Length: {file_size}")

        if extra_headers:
            for key, value in extra_headers:
                headers.append(f"{key}: {value}")

        headers.append(f"Connection: {connection}")

        header_part = "\r\n".join(headers) + "\r\n\r\n"
        return (answer_line + header_part).encode("utf-8")

    def build_response(
        self,
        status,
        content,
        content_type,
        method,
        keep_alive=False,
        extra_headers=None,
    ):
        response_bytes = self.build_headers(
            status=status,
            file_size=len(content),
            content_type=content_type,
            method=method,
            keep_alive=keep_alive,
            extra_headers=extra_headers,
        )

        if method == "HEAD":
            return response_bytes

        return response_bytes + content

    def get_status(self, status):
        if status in self.CODES:
            return self.CODES[status]

        try:
            return HTTPStatus(status).phrase
        except ValueError:
            raise ValueError(f"Unknown status code: {status}") from None
