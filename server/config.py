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

            self.host = data['host_ip']
            self.port = data['port']
            self.root_dir = data['root_dir']
            self.log_file = data['log_file']
            self.ssl_cert = data['ssl_cert']
            self.ssl_key = data['ssl_key']

            print("OK! Конфиг успешно загружен из файла")
        except FileNotFoundError:
            print(f"[ERROR]: Файл не конфигурации не найден, будут использованы значения по умолчанию ")
        except json.JSONDecodeError:
            print(f"[ERROR]: Ошибка в файле конфигурации, проверьте JSON, будут использованы значения по умолчанию")
        except Exception as e:
            print(f"[ERROR]: Непредвиденная ошибка! {e}")
