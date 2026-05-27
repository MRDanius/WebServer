import os
import shutil
import tempfile
import unittest
from collections.abc import Generator
from unittest.mock import patch
from server.utils.file_manager import FileManager


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

        self.fm: FileManager = FileManager(
            cache_limit_mb=1, max_open_fds=2
        )

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
        Проверка работы потокового итератора для больших файлов
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

    def test_ram_cache_hit_and_invalidation(self) -> None:
        """
        Проверка попадания в RAM-кэш и его инвалидацию при изменении mtime
        """
        gen1: Generator[bytes, None, None]
        size1: int
        mime1: str
        gen1, size1, mime1 = self.fm.get_file("/index.html", self.test_dir)
        b"".join(gen1)

        gen2: Generator[bytes, None, None]
        size2: int
        mime2: str
        gen2, size2, mime2 = self.fm.get_file("/index.html", self.test_dir)
        content: bytes = b"".join(gen2)
        self.assertEqual(content, b"<h1>Test Index</h1>")

        atime: float = os.path.getatime(self.index_path)
        mtime: float = os.path.getmtime(self.index_path) + 10.0
        os.utime(self.index_path, (atime, mtime))

        gen3: Generator[bytes, None, None]
        size3: int
        mime3: str
        gen3, size3, mime3 = self.fm.get_file("/index.html", self.test_dir)
        content3: bytes = b"".join(gen3)
        self.assertEqual(content3, b"<h1>Test Index</h1>")

    def test_fd_cache_lru_eviction(self) -> None:
        """
        Проверяет вытеснение старых дескрипторов по алгоритму LRU
        """
        large_content: bytes = b"B" * (2 * 1024 * 1024)
        for i in range(3):
            path: str = os.path.join(
                self.test_dir, f"large_{i}.bin"
            )
            with open(path, "wb") as f:
                f.write(large_content)

        patch_open = patch("os.open", side_effect=[10, 11, 12])
        patch_close = patch("os.close")
        patch_pread = patch("os.pread", return_value=b"")

        with patch_open, patch_close as mock_close, patch_pread:
            gen0: Generator[bytes, None, None]
            gen0, _, _ = self.fm.get_file(
                "/large_0.bin", self.test_dir
            )
            next(gen0, None)

            gen1: Generator[bytes, None, None]
            gen1, _, _ = self.fm.get_file(
                "/large_1.bin", self.test_dir
            )
            next(gen1, None)

            gen2: Generator[bytes, None, None]
            gen2, _, _ = self.fm.get_file(
                "/large_2.bin", self.test_dir
            )
            next(gen2, None)

            mock_close.assert_called_once_with(10)

    def test_fd_cache_invalidation_on_mtime_change(self) -> None:
        """
        Проверяет закрытие дескриптора при изменении файла
        """
        large_path: str = os.path.join(
            self.test_dir, "large_mtime.bin"
        )
        large_content: bytes = b"C" * (2 * 1024 * 1024)
        with open(large_path, "wb") as f:
            f.write(large_content)

        patch_open = patch("os.open", return_value=20)
        patch_close = patch("os.close")
        patch_pread = patch("os.pread", return_value=b"")

        with patch_open, patch_close as mock_close, patch_pread:
            gen1: Generator[bytes, None, None]
            gen1, _, _ = self.fm.get_file(
                "/large_mtime.bin", self.test_dir
            )
            next(gen1, None)

            atime: float = os.path.getatime(large_path)
            mtime: float = os.path.getmtime(large_path) + 10.0
            os.utime(large_path, (atime, mtime))

            gen2: Generator[bytes, None, None]
            gen2, _, _ = self.fm.get_file(
                "/large_mtime.bin", self.test_dir
            )
            next(gen2, None)

            mock_close.assert_called_once_with(20)

    def test_autoindex_permission_error(self) -> None:
        """
        Проверяет генерацию PermissionError для Autoindex
        """
        patch_listdir = patch(
            "os.listdir", side_effect=PermissionError("No permission")
        )
        with patch_listdir:
            with self.assertRaises(PermissionError):
                self.fm.get_file("/empty_folder", self.test_dir)


if __name__ == "__main__":
    unittest.main()
