import logging
from http import HTTPStatus


log: logging.Logger = logging.getLogger(__name__)


class ResponseBuilder:
    """
    Сборщик HTTP-ответов
    """

    CODES: dict[int, str] = {
        200: "OK",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
        500: "Internal Server Error",
    }

    def build_headers(
        self,
        status: int,
        file_size: int | None,
        content_type: str,
        method: str,
        keep_alive: bool = False,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> bytes:
        """
        Формирует байты заголовков HTTP-ответа

        Args:
            status (int): код состояния HTTP
            file_size (int | None): размер тела ответа или None
            content_type (str): тип содержимого
            method (str): метод запроса
            keep_alive (bool): использовать ли постоянное соединение
            extra_headers (list[tuple[str, str]] | None): дополнительные заголовки

        Returns:
            bytes: заголовки ответа в байтах
        """
        answer_line: str = f"HTTP/1.1 {status} {self.get_status(status)}\r\n"
        connection: str = "keep-alive" if keep_alive else "close"

        headers: list[str] = [
            f"Content-Type: {content_type}",
        ]

        if file_size is not None:
            headers.insert(0, f"Content-Length: {file_size}")

        if extra_headers:
            for key, value in extra_headers:
                headers.append(f"{key}: {value}")

        headers.append(f"Connection: {connection}")

        header_part: str = "\r\n".join(headers) + "\r\n\r\n"
        return (answer_line + header_part).encode("utf-8")

    def build_response(
        self,
        status: int,
        content: bytes,
        content_type: str,
        method: str,
        keep_alive: bool = False,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> bytes:
        """
        Формирует полный HTTP-ответ с заголовками и телом

        Args:
            status (int): код состояния HTTP
            content (bytes): тело ответа
            content_type (str): тип содержимого
            method (str): метод запроса
            keep_alive (bool): использовать ли постоянное соединение
            extra_headers (list[tuple[str, str]] | None): дополнительные заголовки

        Returns:
            bytes:  HTTP-ответ в байтах
        """
        response_bytes: bytes = self.build_headers(
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

    def get_status(self, status: int) -> str:
        """
        Возвращает текстовое описание кода состояния HTTP

        Args:
            status (int): код состояния HTTP

        Returns:
            str: фраза статуса

        Raises:
            ValueError: при неизвестном коде состояния
        """
        try:
            return HTTPStatus(status).phrase
        except ValueError:
            raise ValueError(f"Unknown status code: {status}") from None
