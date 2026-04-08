import logging
from server.logger import configure_logger


log = logging.getLogger(__name__)
def main():
    configure_logger()

if __name__ == "__main__":
    main()