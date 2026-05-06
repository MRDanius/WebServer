import mimetypes
import os.path
import logging
from collections import OrderedDict

logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self, cache_limit_mb=50, max_open_fds=100):
        self.cache = {}
        self.cache_limit = cache_limit_mb * 1024 * 1024
        self.fd_cache = OrderedDict()
        self.max_open_fds = max_open_fds

    def get_file(self, address, root_dir):
        clean_address = address.lstrip('/')
        current_root = os.path.abspath(root_dir)
        full_path = os.path.abspath(os.path.join(current_root, clean_address))

        if not full_path.startswith(current_root):
            logger.warning(f"Попытка Path Traversal! Запрошенный address: {address}")
            raise PermissionError("Access outside the root directory is prohibited!")

        if os.path.basename(full_path).startswith('.'):
            logger.warning(f"Блокировка доступа к скрытому файлу:{full_path}")
            raise PermissionError("Access to hidden files is prohibited!")

        if os.path.isdir(full_path):
            index_path = os.path.join(full_path, "index.html")
            if os.path.exists(index_path):
                return self._process_file(index_path)
            else:
                return self._generate_autoindex(full_path, address)
        return self._process_file(full_path)

    def _process_file(self, path):
        stat = os.stat(path)
        mtime = stat.st_mtime
        file_size = stat.st_size

        if path in self.cache:
            if self.cache[path]['mtime'] == mtime:
                logger.info(f"Файл взят из кэша: {path}")
                cached_data = self.cache[path]['content']
                return self._make_generator(cached_data), file_size, self.cache[path]['type']
            else:
                del self.cache[path]

        if path in self.fd_cache:
            if self.fd_cache[path]['mtime'] != mtime:
                try:
                    os.close(self.fd_cache[path]['fd'])
                except OSError:
                    pass
                del self.fd_cache[path]

        mime_type = mimetypes.guess_type(path)[0] or 'application/octet-stream'

        if file_size <= self.cache_limit:
            with open(path, 'rb') as f:
                content = f.read()

            self.cache[path] = {
                'content': content,
                'mtime': mtime,
                'type': mime_type
            }
            logger.info(f"Файл добавлен в кэш: {path}")
            return self._make_generator(content), file_size, mime_type

        logger.info(f"Файл слишком большой для кэша, читаем потоком: {path}")
        return self._file_iterator(path, file_size, mtime), file_size, mime_type

    def _get_fd(self, path, mtime):
        if path in self.fd_cache:
            self.fd_cache.move_to_end(path)
            return self.fd_cache[path]['fd']

        if len(self.fd_cache) >= self.max_open_fds:
            oldest_path, old_data = self.fd_cache.popitem(last=False)
            try:
                os.close(old_data['fd'])
                logger.debug(f"Закрыт старый дескриптор для {oldest_path}")
            except OSError:
                pass

        fd = os.open(path, os.O_RDONLY)
        self.fd_cache[path] = {'fd': fd, 'mtime': mtime}
        return fd

    def _make_generator(self, data):
        yield data

    def _file_iterator(self, path, file_size, mtime, chunk_size=65536):
        fd = self._get_fd(path, mtime)
        offset = 0

        while offset < file_size:
            try:
                chunk = os.pread(fd, chunk_size, offset)
            except OSError as e:
                break

            if not chunk:
                break

            yield chunk
            offset += len(chunk)

    def _generate_autoindex(self, full_path, rel_path):
        try:
            items = os.listdir(full_path)
        except PermissionError:
            raise PermissionError("Нет прав на просмотр содержимого папки")
        html = f"<html><head><meta charset='utf-8'><title>Index of {rel_path}</title></head>"
        html += f"<body><h1>Содержимое папки: {rel_path}</h1><hr><ul>"
        if rel_path != "/":
            parent_dir = os.path.dirname(rel_path.rstrip('/'))
            if not parent_dir: parent_dir = "/"
            html += f'<li><a href="{parent_dir}">[.. Назад]</a></li>'

        for item in sorted(items):
            item_full_path = os.path.join(full_path, item)
            suffix = "/" if os.path.isdir(item_full_path) else ""
            html += f'<li><a href="{item}{suffix}">{item}{suffix}</a></li>'

        html += "</ul><hr><footer><i>Web Server 2026</i></footer></body></html>"

        data = html.encode('utf-8')

        return self._make_generator(data), len(data), "text/html"