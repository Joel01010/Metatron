from __future__ import annotations

import base64
import ctypes
import os
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Protocol


class SecretStore(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str) -> None: ...
    def delete(self, key: str) -> None: ...


class MemorySecretStore:
    """Portable fake used by tests and non-Windows development."""

    def __init__(self) -> None:
        self._items: dict[str, str] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._items.get(str(key))

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._items[str(key)] = str(value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._items.pop(str(key), None)


class DPAPISecretStore:
    """Current-user DPAPI store.

    The encrypted blobs are persisted as files, but only the same Windows user
    on the same machine can decrypt them under normal DPAPI semantics.
    """

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def __init__(self, root: Path) -> None:
        if os.name != "nt":
            raise RuntimeError("DPAPI secret store requires Windows")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @classmethod
    def _blob(cls, data: bytes) -> tuple["DPAPISecretStore.DATA_BLOB", ctypes.Array]:
        buf = ctypes.create_string_buffer(data)
        blob = cls.DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
        return blob, buf

    @classmethod
    def _protect(cls, data: bytes) -> bytes:
        src, keep = cls._blob(data)
        out = cls.DATA_BLOB()
        if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(src), "Metatron", None, None, None,
            cls.CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out),
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)

    @classmethod
    def _unprotect(cls, data: bytes) -> bytes:
        src, keep = cls._blob(data)
        out = cls.DATA_BLOB()
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(src), None, None, None, None,
            cls.CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out),
        ):
            raise ctypes.WinError()
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)

    def _path(self, key: str) -> Path:
        safe = base64.urlsafe_b64encode(str(key).encode("utf-8")).decode("ascii").rstrip("=")
        return self.root / f"{safe}.secret"

    def get(self, key: str) -> str | None:
        path = self._path(key)
        if not path.exists():
            return None
        return self._unprotect(path.read_bytes()).decode("utf-8")

    def set(self, key: str, value: str) -> None:
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(self._protect(str(value).encode("utf-8")))
        os.replace(tmp, path)

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            pass
