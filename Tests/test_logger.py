import logging
import os
import tempfile
import unittest

from server.utils.logger import OwnFormatter
from server.utils.logger import configure_logger


class LoggerTests(unittest.TestCase):
    """
    Тесты логгера и форматтера
    """

    def test_formatter_replaces_newlines(self) -> None:
        """
        Проверяет замену переносов строк в сообщении лога
        """
        formatter: OwnFormatter = OwnFormatter("%(message)s")

        record: logging.LogRecord = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="line1\nline2\r\nline3\rline4",
            args=(),
            exc_info=None,
        )

        result: str = formatter.format(record)

        self.assertEqual(
            result,
            "line1 | line2 | line3 | line4",
        )

    def test_configure_logger_adds_handlers(self) -> None:
        """
        Проверяет настройку обработчиков логгера
        """
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            log_path: str = temp_file.name

        try:
            configure_logger(log_path)

            logger: logging.Logger = logging.getLogger()

            self.assertEqual(logger.level, logging.DEBUG)
            self.assertEqual(len(logger.handlers), 2)

        finally:

            logger: logging.Logger = logging.getLogger()

            for handler in logger.handlers:
                handler.close()

            logger.handlers.clear()

            if os.path.exists(log_path):
                os.remove(log_path)


if __name__ == "__main__":
    unittest.main()
