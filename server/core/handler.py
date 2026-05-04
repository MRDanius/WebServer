import logging

from server.protocol.response_builder import ResponseBuilder


log = logging.getLogger(__name__)


class Handler:
    METHODS = {"GET", "HEAD"}
    ERROR_CONTENT_TYPE = "text/html"

    def __init__(self, file_service):
        self.file_service = file_service
        self.response_builder = ResponseBuilder()


    def resolve_keep_alive(self, headers, version):
        headers = headers or {}
        connection = headers.get("connection", "").lower()
        if version == "HTTP/1.0":
            return connection == "keep-alive"
        return connection != "close"

    def handle_request(self, method, path, headers=None, version="HTTP/1.1", client_ip="-"):
        keep_alive = self.resolve_keep_alive(headers, version)

        if method == "GET":
            headers_bytes, gen = self.handle_get(path, client_ip, keep_alive)
            return headers_bytes, gen, keep_alive

        if method == "HEAD":
            headers_bytes, gen = self.handle_head(path, client_ip, keep_alive)
            return headers_bytes, gen, keep_alive

        headers_bytes, gen = self.build_error_response(
            status=400,
            method=method,
            path=path,
            client_ip=client_ip,
            error_text="Bad request method",
            keep_alive=keep_alive
        )
        return headers_bytes, gen, keep_alive

    def handle_get(self, path, client_ip="-", keep_alive=False):
        return self.handle_file_request(
            method="GET",
            path=path,
            client_ip=client_ip,
            keep_alive=keep_alive
        )

    def handle_head(self, path, client_ip="-", keep_alive=False):
        return self.handle_file_request(
            method="HEAD",
            path=path,
            client_ip=client_ip,
            keep_alive=keep_alive
        )

    def handle_bad_request(self, client_ip="-", error_text="Bad request", keep_alive=True):
        headers_bytes, gen = self.build_error_response(
            status=400,
            method="GET",
            path="-",
            client_ip=client_ip,
            error_text=error_text,
            keep_alive=keep_alive
        )
        return headers_bytes, gen, keep_alive

    def handle_file_request(self, method, path, client_ip, keep_alive=False):
        try:
            content_generator, file_size, content_type = self.file_service.get_file(path)

            headers = self.response_builder.build_headers(
                status=200,
                file_size=file_size,
                content_type=content_type,
                method=method,
                keep_alive=keep_alive
            )

            log.info("ACCESS %s %s %s %s", client_ip, method, path, 200)
            if method == "HEAD":
                return headers, None

            return headers, content_generator

        except FileNotFoundError:
            return self.build_error_response(
                status=404,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="File not found",
                keep_alive=keep_alive
            )

        except PermissionError:
            return self.build_error_response(
                status=403,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Access forbidden",
                keep_alive=keep_alive
            )

        except Exception:
            log.exception("Unexpected error while handling request")

            return self.build_error_response(
                status=500,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Internal server error",
                keep_alive=keep_alive
            )

    def build_error_response(self, status, method, path, client_ip, error_text, keep_alive=False):
        status_text = self.response_builder.get_status(status)
        content = f"<h1>{status} {status_text}</h1>".encode("utf-8")

        response_bytes = self.response_builder.build_response(
            status=status,
            content=content,
            content_type=self.ERROR_CONTENT_TYPE,
            method=method,
            keep_alive=keep_alive
        )

        log.error("ERROR %s %s %s %s %s", client_ip, method, path, status, error_text)
        return response_bytes, None
