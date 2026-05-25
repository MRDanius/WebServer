import os
import shutil
import tempfile
import unittest
from collections.abc import Generator
from server.utils.file_manager import FileManager
from unittest.mock import patch


class FileManagerTests(unittest.TestCase):
    """
    Тесты сервиса управления файлами и кэширования
    """

    def setUp(self) -> None:
        """
        Подготовка временной директории и файлов перед каждым тестом
        """
        self.test_dir: str = tempfile.mkdtemp()

        self.index_path: str = os.path.join(self.test_dir, "index.html")
        with open(self.index_path, "wb") as f:
            f.write(b"<h1>Test Index</h1>")

        self.hidden_path: str = os.path.join(self.test_dir, ".env")
        with open(self.hidden_path, "wb") as f:
            f.write(b"SECRET=123")

        self.empty_dir: str = os.path.join(self.test_dir, "empty_folder")
        os.makedirs(self.empty_dir, exist_ok=True)

        self.fm: FileManager = FileManager(cache_limit_mb=1, max_open_fds=2)

    def tearDown(self) -> None:
        """
        Очистка файлов после завершения теста
        """

        for path_key in list(self.fm.fd_cache.keys()):
            try:
                os.close(self.fm.fd_cache[path_key]["fd"])
            except OSError:
                pass

        self.fm.fd_cache.clear()

        shutil.rmtree(self.test_dir)

    def test_get_file_success(self) -> None:
        """
        Проверка успешного чтения файла и типов возвращаемых значений
        """
        gen: Generator[bytes, None, None]
        size: int
        mime: str
        gen, size, mime = self.fm.get_file("/index.html", self.test_dir)

        self.assertIsInstance(gen, Generator)
        content: bytes = b"".join(gen)
        self.assertEqual(content, b"<h1>Test Index</h1>")
        self.assertEqual(mime, "text/html")
        self.assertEqual(size, len(b"<h1>Test Index</h1>"))

    def test_root_to_index(self) -> None:
        """
        Проверка подмены запроса директории на index.html
        """
        gen: Generator[bytes, None, None]
        size: int
        mime: str
        gen, size, mime = self.fm.get_file("/", self.test_dir)
        content: bytes = b"".join(gen)

        self.assertEqual(content, b"<h1>Test Index</h1>")

    def test_path_traversal_protection(self) -> None:
        """
        Проверка защиты от выхода за пределы директории
        """
        with self.assertRaises(PermissionError):
            self.fm.get_file("../passwords.txt", self.test_dir)

    def test_hidden_file_protection(self) -> None:
        """
        Проверка защиты от чтения скрытых файлов
        """
        with self.assertRaises(PermissionError):
            self.fm.get_file("/.env", self.test_dir)

    def test_autoindex_generation(self) -> None:
        """
        Проверка автоматической генерации листинга для пустой папки
        """
        gen: Generator[bytes, None, None]
        size: int
        mime: str
        gen, size, mime = self.fm.get_file("/empty_folder", self.test_dir)
        content: bytes = b"".join(gen)

        self.assertIn(b"Index of /empty_folder", content)
        self.assertEqual(mime, "text/html")

    def test_file_not_found(self) -> None:
        """
        Проверка реакции на запрос несуществующего файла
        """
        with self.assertRaises(FileNotFoundError):
            self.fm.get_file("/not_exists.txt", self.test_dir)

    def test_streaming_large_file(self) -> None:
        """
        Проверка работы потокового итератора для файлов, превышающих лимит кэша
        """

        large_path: str = os.path.join(self.test_dir, "large.bin")
        large_content: bytes = b"A" * (2 * 1024 * 1024)

        with open(large_path, "wb") as f:
            f.write(large_content)

        def fake_pread(fd: int, chunk_size: int, offset: int) -> bytes:
            with open(large_path, "rb") as file:
                file.seek(offset)
                return file.read(chunk_size)

        with patch("os.pread", side_effect=fake_pread, create=True):
            gen: Generator[bytes, None, None]
            size: int
            mime: str

            gen, size, mime = self.fm.get_file("/large.bin", self.test_dir)

            content: bytes = b"".join(gen)

            self.assertEqual(content, large_content)
            self.assertEqual(size, len(large_content))


if __name__ == "__main__":
    unittest.main()
