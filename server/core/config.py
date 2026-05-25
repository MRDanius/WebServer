import logging
import json

log: logging.Logger = logging.getLogger(__name__)


class Config:
    """
    Конфигурация веб-сервера.

    Загружает, хранит и валидирует параметры работы сетевого слоя,
    виртуальных хостов, лимитов трафика и безопасности.
    """

    def __init__(self, file_path: str = "config.json") -> None:
        """
        Инициализирует дефолтные значения и загружает конфигурацию из файла

        Args:
            file_path (str): путь к JSON-файлу конфигурации
        """
        # Явно указываем типы всех полей класса при инициализации
        self.host: str = "127.0.0.1"
        self.port: int = 8080
        self.default_root: str = "./static"
        self.servers: dict[str, str] = {}
        self.log_file: str = "webserver.log"
        self.ssl_cert: str = ""
        self.ssl_key: str = ""

        self.read_timeout: int = 5
        self.write_timeout: int = 5
        self.upload_limit: int = 0  # 0 => "без ограничений"
        self.download_limit: int = 0

        try:
            with open(file_path, "r", encoding="utf-8") as config:
                data: dict[str, any] = json.load(config)

            self.host = data.get("host_ip", self.host)
            self.port = data.get("port", self.port)

            self.default_root = data.get(
                "default_root", data.get("root_dir", self.default_root)
            )
            self.servers = data.get("servers", {})

            self.log_file = data.get("log_file", self.log_file)
            self.ssl_cert = data.get("ssl_cert", self.ssl_cert)
            self.ssl_key = data.get("ssl_key", self.ssl_key)

            self.read_timeout = data.get("read_timeout", self.read_timeout)
            self.write_timeout = data.get("write_timeout", self.write_timeout)

            self.upload_limit = data.get(
                "upload_limit_bps", self.upload_limit
            )
            self.download_limit = data.get(
                "download_limit_bps", self.download_limit
            )

            log.info("Конфиг успешно загружен из файла")
        except FileNotFoundError:
            log.warning(
                "Файл конфигурации не найден, "
                "будут использованы значения по умолчанию"
            )
        except json.JSONDecodeError:
            log.error(
                "Ошибка в файле конфигурации, проверьте синтаксис JSON. "
                "Будут использованы значения по умолчанию"
            )
        except Exception as e:
            log.error(
                f"Непредвиденная ошибка при загрузке конфига: {e}",
                exc_info=True,
            )
