import logging
from server.logger import configure_logger
from server.config import Config


log = logging.getLogger(__name__)

def test_config(cfg):
    print("--------Пошёл запуск теста моего конфига-------")
    print(f"Host {cfg.host}")
    print(f"Port {cfg.port}")
    print(f"Root DIr {cfg.root_dir}")
    print(f"Log file {cfg.log_file}")

def main():
    cfg = Config()
    configure_logger(cfg.log_file)
    test_config(cfg)
    log.info("Start server")
    log.error("Error test")

if __name__ == "__main__":
    main()
