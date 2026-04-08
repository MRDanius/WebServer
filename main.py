from server.config import Config

def test_config():
    print("--------Пошёл запуск теста моего конфига-------")
    cfg = Config()
    print(f"Host {cfg.host}")
    print(f"Port {cfg.port}")
    print(f"Root DIr {cfg.root_dir}")
    print(f"Log file {cfg.log_file}")
if __name__ == "__main__":
    test_config()