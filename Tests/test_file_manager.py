import unittest
import os
import tempfile
import shutil
from WebServer.server.utils.file_manager import FileManager


class TestFileManager(unittest.TestCase):
    def setUp(self):
        """Подготовка временной директории и файлов перед каждым тестом"""
        self.test_dir = tempfile.mkdtemp()
        self.index_path = os.path.join(self.test_dir, 'index.html')
        with open(self.index_path, 'wb') as f:
            f.write(b"<h1>Test Index</h1>")

        self.hidden_path = os.path.join(self.test_dir, '.env')
        with open(self.hidden_path, 'wb') as f:
            f.write(b"SECRET=123")

        self.fm = FileManager(self.test_dir)

    def tearDown(self):
        """Очистка файлов после завершения теста"""
        shutil.rmtree(self.test_dir)

    def test_get_file_success(self):
        """Проверка успешного чтения обычного файла"""
        result = self.fm.get_file('/index.html')
        self.assertEqual(result[0], b"<h1>Test Index</h1>")
        self.assertEqual(result[1], 'text/html')

    def test_root_to_index(self):
        """Проверка подмены корневого запроса на index.html"""
        result = self.fm.get_file('/')
        self.assertEqual(result[0], b"<h1>Test Index</h1>")

    def test_path_traversal_protection(self):
        """Проверка защиты от выхода за пределы директории"""
        with self.assertRaises(PermissionError):
            self.fm.get_file('../passwords.txt')

    def test_hidden_file_protection(self):
        """Проверка защиты от чтения скрытых файлов"""
        with self.assertRaises(PermissionError):
            self.fm.get_file('/.env')

    def test_file_not_found(self):
        """Проверка реакции на запрос несуществующего файла"""
        with self.assertRaises(FileNotFoundError):
            self.fm.get_file('/not_exists.txt')


if __name__ == '__main__':
    unittest.main()