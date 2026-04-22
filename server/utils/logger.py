import logging


class OwnFormatter(logging.Formatter):
    def format(self, record):
        message = super().format(record)
        return message.replace('\r\n', ' | ').replace('\n', ' | ').replace('\r', ' | ')


def configure_logger(log_file):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    file_formatter = OwnFormatter(
        '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    handler_formatter = OwnFormatter(
        '%(asctime)s - %(name)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(handler_formatter)

    logger.handlers.clear()

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)