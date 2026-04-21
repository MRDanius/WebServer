import mimetypes
import os.path
import logging


logger = logging.getLogger(__name__)

class FileManager:
    def __init__(self, root_dir):
        self.root_dir = os.path.abspath(root_dir)

    def get_file(self, address):
        if address == '/':
            address = 'index.html'

        clean_address = address.lstrip('/')
        full_path = os.path.abspath(os.path.join(self.root_dir, clean_address))

        if not full_path.startswith(self.root_dir):
            logger.warning(f"Попытка Path Traversal! Запрошенный address: {address}")
            raise PermissionError("Access outside the root directory is prohibited!")

        if os.path.basename(full_path).startswith('.'):
            logger.warning(f"Блокировка доступа к скрытому файлу:{full_path}")
            raise PermissionError("Access to hidden files is prohibited!")

        file_size = os.path.getsize(full_path)

        result = mimetypes.guess_type(full_path)
        mime_type = result[0]
        if mime_type is None:
            mime_type = 'application/octet-stream'

        def file_iterator(path, chunk_s = 65536):
            with open(path, 'rb') as file:
                while True:
                    chunk = file.read(chunk_s)
                    if not chunk:
                        break
                    yield chunk

        logger.info(f"Начата потоковая отдача файла: {full_path} ({file_size} байт)")
        return file_iterator(full_path), file_size, mime_type

