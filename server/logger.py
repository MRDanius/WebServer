import logging


class OwnFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        return message.replace('\r\n', ' | ').replace('\n', ' | ').replace('\r', ' | ')


def configure_logger():
    handler = logging.FileHandler('server.log', encoding='utf-8')
    handler.setFormatter(OwnFormatter(
        '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler],
    )
