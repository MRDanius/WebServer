import logging
import socket

from server.protocol.response_builder import ResponseBuilder


log = logging.getLogger(__name__)


class Handler:
    METHODS = {"GET", "HEAD"}
    ERROR_CONTENT_TYPE = "text/html"

    def __init__(self, file_service, config):
        self.file_service = file_service
        self.config = config
        self.response_builder = ResponseBuilder()


    def resolve_keep_alive(self, headers, version):
        headers = headers or {}
        connection = headers.get("connection", "").lower()
        if version == "HTTP/1.0":
            return connection == "keep-alive"
        return connection != "close"

    def handle_request(self, method, path, headers=None, version="HTTP/1.1", client_ip="-"):
        headers = headers or {}
        keep_alive = self.resolve_keep_alive(headers, version)

        raw_host = headers.get("host", "default")
        clean_host = raw_host.split(':')[0]
        root_dir = self.config.servers.get(clean_host, self.config.default_root)
        if path.startswith("/api"):
            return self.handle_proxy(method, path, headers, version, client_ip, keep_alive)

        if method == "GET":
            headers_bytes, gen = self.handle_get(path, root_dir,client_ip, keep_alive)
            return headers_bytes, gen, keep_alive

        if method == "HEAD":
            headers_bytes, gen = self.handle_head(path, root_dir,client_ip, keep_alive)
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

    def handle_proxy(self, method, path, headers, version, client_ip, keep_alive):
        if method not in self.METHODS:
            return self.build_error_response(
                status=400,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Unsupported method for proxy",
                keep_alive=keep_alive
            )

        try:
            upstream_host = "httpbin.org"
            upstream_port = 80

            upstream_path = path[len("/api"):] or "/"

            request_lines = [
                f"{method} {upstream_path} {version}",
                f"Host: {upstream_host}",
                "Connection: close",
            ]

            for k,v in (headers or {}).items():
                if k.lower() not in ("host", "connection"):
                    request_lines.append(f"{k}: {v}")

            request_data = "\r\n".join(request_lines) + "\r\n\r\n"

            with socket.create_connection((upstream_host, upstream_port), timeout=5) as sock:
                sock.sendall(request_data.encode())

                chunks = []
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)

                raw_response = b"".join(chunks)

            if not raw_response:
                raise ValueError("Empty upstream response")

            if b"\r\n\r\n" not in raw_response:
                raise ValueError("Invalid upstream response")

            header_part, body = raw_response.split(b"\r\n\r\n", 1)
            header_lines = header_part.decode("utf-8", errors="ignore").split("\r\n")

            status_line = header_lines[0].split()
            if len(status_line) < 2:
                raise ValueError("Invalid status line")

            status_code = int(status_line[1])

            response_headers = {}
            for line in header_lines[1:]:
                if ":" in line:
                    k, v = line.split(":", 1)
                    response_headers[k.strip().lower()] = v.strip()

            content_type = response_headers.get("content-type", "application/octet-stream")

            response_bytes = self.response_builder.build_response(
                status=status_code,
                content=body,
                content_type=content_type,
                method=method,
                keep_alive=keep_alive
            )

            if method == "HEAD":
                return response_bytes, None, keep_alive

            log.info("PROXY %s %s -> %s%s %s", client_ip, path, upstream_host, upstream_path, status_code)

            return response_bytes, None, keep_alive

        except Exception:
            log.exception("Proxy error")

            return self.build_error_response(
                status=500,
                method=method,
                path=path,
                client_ip=client_ip,
                error_text="Proxy error",
                keep_alive=keep_alive
            )


    def handle_get(self, path,root_dir ,client_ip="-" , keep_alive=False):
        return self.handle_file_request(
            method="GET",
            path=path,
            root_dir = root_dir,
            client_ip=client_ip,
            keep_alive=keep_alive
        )

    def handle_head(self, path,root_dir, client_ip="-", keep_alive=False):
        return self.handle_file_request(
            method="HEAD",
            path=path,
            root_dir = root_dir,
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

    def handle_file_request(self, method, path, root_dir, client_ip, keep_alive=False):
        try:
            content_generator, file_size, content_type = self.file_service.get_file(path, root_dir)

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
