import time


class RateLimiter:
    def __init__(self, bytes_per_second=0):
        self.bytes_per_second = bytes_per_second or 0
        self.started_at = time.monotonic()
        self.bytes_passed = 0

    def wait(self, chunk_size):
        if self.bytes_per_second <= 0 or chunk_size <= 0:
            return

        self.bytes_passed += chunk_size
        expected_time = self.bytes_passed / self.bytes_per_second
        real_time = time.monotonic() - self.started_at
        delay = expected_time - real_time

        if delay > 0:
            time.sleep(delay)
