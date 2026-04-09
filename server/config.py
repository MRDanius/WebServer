import logging
import json


log = logging.getLogger(__name__)

class Config:
    def __init__(self, file_path='config.json'):
        # добавлю значения по умолчанию вдруг с файлом конфига что то пойдёт не так, чтобы мы по итогу всё равно смогли
        # запустить наш сервер
        self.host = "127.0.0.1"
        self.port = 8080
        self.root_dir = "./static"
        self.log_file = "webserver.log"
        self.ssl_cert = ""
        self.ssl_key = ""
        try:
            with open(file_path, 'r', encoding='utf-8') as config:
                data = json.load(config)

            self.host = data.get('host_ip', self.host)
            self.port = data.get('port', self.port)
            self.root_dir = data.get('root_dir', self.root_dir)
            self.log_file = data.get('log_file', self.log_file)
            self.ssl_cert = data.get('ssl_cert', self.ssl_cert)
            self.ssl_key = data.get('ssl_key', self.ssl_key)

            print("OK! Конфиг успешно загружен из файла")
        except FileNotFoundError:
            print(f"[ERROR]: Файл не конфигурации не найден, будут использованы значения по умолчанию ")
        except json.JSONDecodeError:
            print(f"[ERROR]: Ошибка в файле конфигурации, проверьте JSON, будут использованы значения по умолчанию")
        except Exception as e:
            print(f"[ERROR]: Непредвиденная ошибка! {e}")