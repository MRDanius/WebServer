import logging


log = logging.getLogger(__name__)

class ResponseBuilder:
    CODES = {
        200: "OK",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        500: "Internal Server Error",
    }

    def build_response(self, status, content, content_type, method):

        answer_line = f"HTTP/1.1 {status} {self.get_status(status)}\r\n"

        headers = [
            f"Content-Length: {len(content)}",
            f"Content-Type: {content_type}",
            "Connection: close",
        ]

        header_part = "\r\n".join(headers) + "\r\n\r\n"
        response = answer_line + header_part
        response_bytes = response.encode("utf-8")

        if method == "HEAD":
            return response_bytes

        return response_bytes + content

    def get_status(self, status):
        if status not in self.CODES:
            raise ValueError(f"Unknown status code: {status}")
        return self.CODES[status]