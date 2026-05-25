import logging
import mimetypes
import os
from collections import OrderedDict
from collections.abc import Generator
from typing import Any

logger: logging.Logger = logging.getLogger(__name__)


class FileManager:
    """
    Сервис управления файлами и двухуровневого кэширования.
    Обеспечивает безопасное чтение статики, защиту от Path Traversal,
    генерацию листинга директорий (Autoindex), кэширование мелких файлов
    в RAM и кэширование дескрипторов (FD-Cache) для тяжелых файлов.
    """

    def __init__(self, cache_limit_mb: int = 50, max_open_fds: int = 100) -> None:
        """
        Инициализирует менеджер файлов и структуры данных кэша

        Args:
            cache_limit_mb (int): максимальный размер файла для кэширования в RAM (в МБ)
            max_open_fds (int): максимальное количество одновременно открытых дескрипторов файлов
        """
        # Явное указание типов для структур кэширования
        self.cache: dict[str, dict[str, Any]] = {}
        self.cache_limit: int = cache_limit_mb * 1024 * 1024
        self.fd_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self.max_open_fds: int = max_open_fds

    def get_file(self, address: str, root_dir: str) -> tuple[Generator[bytes, None, None], int, str]:
        """
        Производит валидацию пути и возвращает генератор контента, размер и MIME-тип объекта

        Args:
            address (str): относительный путь запроса (URL)
            root_dir (str): корневая папка текущего виртуального хоста

        Returns:
            tuple[Generator[bytes, None, None], int, str]: генератор байт, размер файла и MIME-тип

        Raises:
            PermissionError: при попытке Path Traversal или доступе к скрытым файлам
        """
        clean_address: str = address.lstrip('/')
        current_root: str = os.path.abspath(root_dir)
        full_path: str = os.path.abspath(os.path.join(current_root, clean_address))

        # Защита от выхода за пределы корня сайта
        if not full_path.startswith(current_root):
            logger.warning(f"Попытка Path Traversal! Запрошенный address: {address}")
            raise PermissionError("Access outside the root directory is prohibited!")

        # Блокировка скрытых файлов типа .env
        if os.path.basename(full_path).startswith('.'):
            logger.warning(f"Блокировка доступа к скрытому файлу: {full_path}")
            raise PermissionError("Access to hidden files is prohibited!")

        # Обработка директорий (ищем index.html или генерируем autoindex)
        if os.path.isdir(full_path):
            index_path: str = os.path.join(full_path, "index.html")
            if os.path.exists(index_path):
                return self._process_file(index_path)
            else:
                return self._generate_autoindex(full_path, address)

        return self._process_file(full_path)

    def _process_file(self, path: str) -> tuple[Generator[bytes, None, None], int, str]:
        """
        Определяет стратегию отдачи файла на основе его размера и актуальности кэша

        Args:
            path (str): абсолютный путь к файлу в файловой системе

        Returns:
            tuple[Generator[bytes, None, None], int, str]: генератор байт, размер файла и MIME-тип
        """
        stat: os.stat_result = os.stat(path)
        mtime: float = stat.st_mtime
        file_size: int = stat.st_size

        # 1. Проверка кэша (In-Memory RAM Cache)
        if path in self.cache:
            if self.cache[path]['mtime'] == mtime:
                logger.info(f"Файл взят из кэша: {path}")
                cached_data: bytes = self.cache[path]['content']
                return self._make_generator(cached_data), file_size, self.cache[path]['type']
            else:
                del self.cache[path]

        # 2. Инвалидация устаревшего дескриптора в FD-кэше при изменении файла
        if path in self.fd_cache:
            if self.fd_cache[path]['mtime'] != mtime:
                try:
                    os.close(self.fd_cache[path]['fd'])
                except OSError:
                    pass
                del self.fd_cache[path]

        mime_type: str = mimetypes.guess_type(path)[0] or 'application/octet-stream'

        # 3. Выбор стратегии: сохранение мелкого файла в RAM или стриминг тяжелого файла
        if file_size <= self.cache_limit:
            with open(path, 'rb') as f:
                content: bytes = f.read()

            self.cache[path] = {
                'content': content,
                'mtime': mtime,
                'type': mime_type
            }
            logger.info(f"Файл добавлен в кэш: {path}")
            return self._make_generator(content), file_size, mime_type

        logger.info(f"Файл слишком большой для кэша, читаем потоком: {path}")
        return self._file_iterator(path, file_size, mtime), file_size, mime_type

    def _get_fd(self, path: str, mtime: float) -> int:
        """
        Возвращает активный дескриптор файла из LRU-кэша или открывает новый

        Args:
            path (str): абсолютный путь к файлу
            mtime (float): время последней модификации файла

        Returns:
            int: файловый дескриптор Linux
        """
        if path in self.fd_cache:
            self.fd_cache.move_to_end(path)
            return self.fd_cache[path]['fd']

        # Вытеснение старых дескрипторов по алгоритму LRU, если превышен лимит
        if len(self.fd_cache) >= self.max_open_fds:
            oldest_path: str
            old_data: dict[str, Any]
            oldest_path, old_data = self.fd_cache.popitem(last=False)
            try:
                os.close(old_data['fd'])
                logger.debug(f"Закрыт старый дескриптор для {oldest_path}")
            except OSError:
                pass

        fd: int = os.open(path, os.O_RDONLY)
        self.fd_cache[path] = {'fd': fd, 'mtime': mtime}
        return fd

    def _make_generator(self, data: bytes) -> Generator[bytes, None, None]:
        """
        Оборачивает сырые байты в генератор для стандартизации интерфейса отдачи

        Args:
            data (bytes): данные для отправки

        Yields:
            bytes: монолитный кусок данных
        """
        yield data

    def _file_iterator(
            self,
            path: str,
            file_size: int,
            mtime: float,
            chunk_size: int = 65536
    ) -> Generator[bytes, None, None]:
        """
        Потоково читает тяжелый файл с диска порциями с помощью атомарного os.pread

        Args:
            path (str): абсолютный путь к файлу
            file_size (int): общий размер файла в байтах
            mtime (float): метка времени изменения файла для проверки FD
            chunk_size (int): размер одного считываемого чанка (дефолт 64 КБ)

        Yields:
            bytes: чанки файла для отправки в сеть
        """
        fd: int = self._get_fd(path, mtime)
        offset: int = 0

        while offset < file_size:
            try:
                chunk: bytes = os.pread(fd, chunk_size, offset)
            except OSError:
                break

            if not chunk:
                break

            yield chunk
            offset += len(chunk)

    def _generate_autoindex(self, full_path: str, rel_path: str) -> tuple[Generator[bytes, None, None], int, str]:
        """
        Формирует HTML-страницу со списком содержимого папки на лету (Autoindex)

        Args:
            full_path (str): абсолютный путь к папке в системе
            rel_path (str): относительный URL-путь папки

        Returns:
            tuple[Generator[bytes, None, None], int, str]: генератор HTML-кода, его размер и MIME-тип text/html

        Raises:
            PermissionError: при отсутствии прав на чтение директории
        """
        try:
            items: list[str] = os.listdir(full_path)
        except PermissionError:
            raise PermissionError("Нет прав на просмотр содержимого папки")

        html: str = f"<html><head><meta charset='utf-8'><title>Index of {rel_path}</title></head>"
        html += f"<body><h1>Содержимое папки: {rel_path}</h1><hr><ul>"

        if rel_path != "/":
            parent_dir: str = os.path.dirname(rel_path.rstrip('/'))
            if not parent_dir:
                parent_dir = "/"
            html += f'<li><a href="{parent_dir}">[.. Назад]</a></li>'

        for item in sorted(items):
            item_full_path: str = os.path.join(full_path, item)
            suffix: str = "/" if os.path.isdir(item_full_path) else ""
            html += f'<li><a href="{item}{suffix}">{item}{suffix}</a></li>'

        html += "</ul><hr><footer><i>Web Server 2026</i></footer></body></html>"

        data: bytes = html.encode('utf-8')
        return self._make_generator(data), len(data), "text/html"