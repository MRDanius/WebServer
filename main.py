import json
import logging

from WebServer.server.core.config import Config
from WebServer.server.core.server import Server
from WebServer.server.utils.logger import configure_logger


def get_log_filename(file_path='config.json', default_name='webserver.log'):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('log_file', default_name)
    except Exception:
        return default_name

def main():
    actual_log_file = get_log_filename()
    configure_logger(actual_log_file)

    logger = logging.getLogger(__name__)
    logger.info(" !!!! Запуск WebServer !!!!")
    config = Config('config.json')
    web_server = Server(config)
    try:
        web_server.start()
    except KeyboardInterrupt:
        print("\n")
        logger.info("Получен сигнал прерывания (Ctrl+C). Сервер начинает остановку")
    finally:
        web_server.stop()
        logger.info("Сервер успешно остановлен ")

if __name__ == '__main__':
    main()
