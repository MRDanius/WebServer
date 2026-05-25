import json
import os
import shutil
import tempfile
import unittest
from typing import Any
from server.core.config import Config


class ConfigTests(unittest.TestCase):
    """
    Тесты конфигурации веб-сервера
    """

    def setUp(self) -> None:
        """
        Подготовка временной директории перед каждым тестом
        """
        self.test_dir: str = tempfile.mkdtemp()
        self.config_path: str = os.path.join(self.test_dir, "config.json")

    def tearDown(self) -> None:
        """
        Очистка файлов после завершения теста
        """
        shutil.rmtree(self.test_dir)

    def test_default_values(self) -> None:
        """
        Проверяет использование дефолтных значений при отсутствии файла
        """
        config: Config = Config("not_found_config.json")

        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8080)
        self.assertEqual(config.default_root, "./static")
        self.assertEqual(config.read_timeout, 5)
        self.assertEqual(config.upload_limit, 0)

    def test_load_success(self) -> None:
        """
        Проверяет успешную загрузку параметров из корректного файла
        """
        valid_data: dict[str, Any] = {
            "host_ip": "0.0.0.0",
            "port": 9090,
            "root_dir": "./custom_static",
            "read_timeout": 10,
            "upload_limit_bps": 5000,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(valid_data, f)

        config: Config = Config(self.config_path)

        self.assertEqual(config.host, "0.0.0.0")
        self.assertEqual(config.port, 9090)
        self.assertEqual(config.default_root, "./custom_static")
        self.assertEqual(config.read_timeout, 10)
        self.assertEqual(config.upload_limit, 5000)

    def test_invalid_json_fallback(self) -> None:
        """
        Проверяет откат на дефолтные значения при битом JSON
        """
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{invalid json: 123}")

        config: Config = Config(self.config_path)

        self.assertEqual(config.host, "127.0.0.1")
        self.assertEqual(config.port, 8080)
        self.assertEqual(config.read_timeout, 5)


if __name__ == "__main__":
    unittest.main()
