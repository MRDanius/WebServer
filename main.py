import logging
from server.logger import configure_logger
from server.config import Config


log = logging.getLogger(__name__)

def test_config():
    print("--------Пошёл запуск теста моего конфига-------")
    cfg = Config()
    print(f"Host {cfg.host}")
    print(f"Port {cfg.port}")
    print(f"Root DIr {cfg.root_dir}")
    print(f"Log file {cfg.log_file}")

def main():
    configure_logger()
    test_config()

if __name__ == "__main__":
    main()
