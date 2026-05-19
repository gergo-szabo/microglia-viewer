import os
import threading

from .nd2_loader import FileRecord, Nd2Loader


class FileRegistry:

    def __init__(self):
        self._records: dict[str, FileRecord] = {}
        self._lock = threading.Lock()
        self._loader = Nd2Loader()

    def open_and_register(self, path: str) -> FileRecord:
        record = self._loader.open(path)
        with self._lock:
            self._records[record.id] = record
        return record

    def register(self, record: FileRecord) -> None:
        with self._lock:
            self._records[record.id] = record

    def get(self, file_id: str) -> FileRecord | None:
        with self._lock:
            return self._records.get(file_id)

    def list_all(self) -> list[FileRecord]:
        with self._lock:
            return list(self._records.values())

    def delete(self, file_id: str) -> None:
        with self._lock:
            record = self._records.pop(file_id, None)
        if record:
            try:
                record.nd2_handle.close()
            except Exception:
                pass
            try:
                os.remove(record.path)
            except Exception:
                pass

    def close_all(self) -> None:
        with self._lock:
            records = list(self._records.values())
            self._records.clear()
        for record in records:
            try:
                record.nd2_handle.close()
            except Exception:
                pass
