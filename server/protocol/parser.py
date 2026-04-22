METHODS = {"GET", "HEAD"}
VERSIONS = {"HTTP/1.0", "HTTP/1.1"}


class Parser:
    def parse_request(self, request):
        if not request:
            raise ValueError("Request is empty")

        if b"\r\n\r\n" not in request:
            raise ValueError("Request is incomplete")

        params = {}
        data = request.decode("utf-8")

        lines = data.split("\r\n")
        request_line = lines[0].split()

        if len(request_line) != 3:
            raise ValueError("Invalid request line")

        if request_line[0] not in METHODS:
            raise ValueError("Invalid request method")

        if not request_line[1].startswith("/"):
            raise ValueError("Path is empty")

        if request_line[2] not in VERSIONS:
            raise ValueError("Invalid request version")

        params["operation"] = request_line[0]
        params["path"] = request_line[1]
        params["version"] = request_line[2]
        params["headers"] = {}

        for line in lines[1:]:
            if line.strip() == "":
                break

            if ":" not in line:
                raise ValueError("Invalid header line")

            key, value = line.split(":", 1)
            params["headers"][key.strip().lower()] = value.strip()

        return params
