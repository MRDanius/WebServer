import logging
import json


log = logging.getLogger(__name__)

class Config:
    def __init__(self, file_path='config.json'):
        # добавлю значения по умолчанию вдруг с файлом конфига что то пойдёт не так, чтобы мы по итогу всё равно смогли
        # запустить наш сервер
        self.host = "127.0.0.1"
        self.port = 8080
        self.default_root = "./static"
        self.servers = {}
        self.log_file = "webserver.log"
        self.ssl_cert = ""
        self.ssl_key = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as config:
                data = json.load(config)

            self.host = data.get('host_ip', self.host)
            self.port = data.get('port', self.port)

            self.default_root = data.get('default_root', data.get('root_dir', self.default_root))
            self.servers = data.get('servers', {})

            self.log_file = data.get('log_file', self.log_file)
            self.ssl_cert = data.get('ssl_cert', self.ssl_cert)
            self.ssl_key = data.get('ssl_key', self.ssl_key)

            log.info("Конфиг успешно загружен из файла")
        except FileNotFoundError:
            log.warning("Файл конфигурации не найден, будут использованы значения по умолчанию")
        except json.JSONDecodeError:
            log.error("Ошибка в файле конфигурации, проверьте синтаксис JSON. Будут использованы значения по умолчанию")
        except Exception as e:
            log.error(f"Непредвиденная ошибка при загрузке конфига: {e}", exc_info=True)

#теперь формат конфига такой вот будет:
#{
#  "host_ip": "127.0.0.1",
#  "port": 8080,
#  "default_root": "./static",
#  "servers": {
#    "localhost": "./static",
#    "site2.com": "./site2"
#  }
#}