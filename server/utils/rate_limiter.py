import time


class RateLimiter:
    """
    Ограничитель скорости передачи данных
    """

    def __init__(self, bytes_per_second: int = 0) -> None:
        """
        Инициализирует ограничитель

        Args:
            bytes_per_second (int): лимит байт в секунду, 0 - без ограничения
        """
        self.bytes_per_second: int = bytes_per_second or 0
        self.started_at: float = time.monotonic()
        self.bytes_passed: int = 0

    def wait(self, chunk_size: int) -> None:
        """
        При необходимости задерживает передачу очередной порции данных

        Args:
            chunk_size (int): размер переданного фрагмента в байтах
        """
        if self.bytes_per_second <= 0 or chunk_size <= 0:
            return

        self.bytes_passed += chunk_size
        expected_time: float = self.bytes_passed / self.bytes_per_second
        real_time: float = time.monotonic() - self.started_at
        delay: float = expected_time - real_time

        if delay > 0:
            time.sleep(delay)
