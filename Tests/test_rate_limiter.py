import unittest
from unittest.mock import patch

from server.utils.rate_limiter import RateLimiter


class RateLimiterTests(unittest.TestCase):
    """
    Тесты ограничителя скорости передачи данных
    """

    limiter: RateLimiter

    def setUp(self) -> None:
        """
        Создаёт экземпляр ограничителя перед каждым тестом
        """
        self.limiter = RateLimiter()

    def test_init_with_default_limit(self) -> None:
        """
        Проверяет корректную инициализацию лимитера
        по умолчанию
        """
        self.assertEqual(self.limiter.bytes_per_second, 0)
        self.assertEqual(self.limiter.bytes_passed, 0)

    def test_init_with_custom_limit(self) -> None:
        """
        Проверяет корректную установку пользовательского лимита
        """
        limiter: RateLimiter = RateLimiter(bytes_per_second=1024)

        self.assertEqual(limiter.bytes_per_second, 1024)

    @patch("time.sleep")
    def test_wait_without_limit(self, mock_sleep) -> None:
        """
        Проверяет отсутствие задержки при отключённом лимите
        """
        self.limiter.wait(1024)

        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_wait_with_zero_chunk(self, mock_sleep) -> None:
        """
        Проверяет отсутствие задержки при нулевом размере чанка
        """
        limiter: RateLimiter = RateLimiter(bytes_per_second=1024)

        limiter.wait(0)

        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_wait_adds_delay(self, mock_sleep) -> None:
        """
        Проверяет добавление задержки при превышении скорости
        """
        limiter: RateLimiter = RateLimiter(bytes_per_second=1024)

        with patch(
            "time.monotonic",
            side_effect=[0.0, 0.1]
        ):
            limiter.started_at = 0.0

            limiter.wait(1024)

        mock_sleep.assert_called_once()

    @patch("time.sleep")
    def test_wait_without_required_delay(self, mock_sleep) -> None:
        """
        Проверяет отсутствие задержки,
        если ожидание не требуется
        """
        limiter: RateLimiter = RateLimiter(bytes_per_second=1024)

        limiter.started_at -= 10.0

        limiter.wait(512)

        mock_sleep.assert_not_called()

    def test_bytes_passed_updated(self) -> None:
        """
        Проверяет корректное обновление счётчика
        переданных байт
        """
        limiter: RateLimiter = RateLimiter(bytes_per_second=1024)

        with patch("time.sleep"):
            limiter.wait(256)
            limiter.wait(512)

        self.assertEqual(limiter.bytes_passed, 768)


if __name__ == "__main__":
    unittest.main()
