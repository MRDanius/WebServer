import logging

from server.response_builder import ResponseBuilder


log = logging.getLogger(__name__)


class Handler:
    METHODS = {"GET", "HEAD"}
    ERROR_CONTENT_TYPE = "text/html"

    def __init__(self, file_service):
        self.file_service = file_service
        self.response_builder = ResponseBuilder()

    def handle_request(self, method, path, headers=None, client_ip="-"):
        if method == "GET":
            return self.handle_get(path, client_ip)

        if method == "HEAD":
            return self.handle_head(path, client_ip)

        return self.build_error_response(
            status=400,
            method=method,
            path=path,
            client_ip=client_ip,
            error_text="Bad request method",
        )

    def handle_get(self, path, client_ip="-"):
        return self.handle_file_request(
            method="GET",
            path=path,
            client_ip=client_ip,
        )

    def handle_head(self, path, client_ip="-"):
        return self.handle_file_request(
            method="HEAD",
            path=path,
            client_ip=client_ip,
        )

    def handle_bad_request(self, client_ip="-", error_text="Bad request"):
        return self.build_error_response(
            status=400,
            method="GET",
            path="-",
            client_ip=client_ip,
            error_text=error_text,
        )

    def handle_file_request(self, method, path, client_ip):
        try:
            content, content_type = self.file_service.get_file(path)

            response = self.response_builder.build_response(
                status=200,
                content=content,
                content_type=content_type,
                method=method,
            )

            log.info("ACCESS %s %s %s %s", client_ip, method, path, 200)
            return response

        except FileNotFoundError:
            return self.build_error_response(
                status=404,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="File not found",
            )

        except PermissionError:
            return self.build_error_response(
                status=403,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Access forbidden",
            )

        except Exception:
            log.exception("Unexpected error while handling request")

            return self.build_error_response(
                status=500,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Internal server error",
            )

    def build_error_response(self, status, method, path, client_ip, error_text):
        status_text = self.response_builder.get_status(status)
        content = f"<h1>{status} {status_text}</h1>".encode("utf-8")

        response = self.response_builder.build_response(
            status=status,
            content=content,
            content_type=self.ERROR_CONTENT_TYPE,
            method=method,
        )

        log.error("ERROR %s %s %s %s %s", client_ip, method, path, status, error_text)
        return response
