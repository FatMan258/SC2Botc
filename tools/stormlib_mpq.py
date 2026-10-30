from __future__ import annotations

import ctypes
import os
import tempfile
from ctypes import wintypes
from pathlib import Path

from botc_config import STORM_DLL, require_file


HANDLE = ctypes.c_void_p
MPQ_OPEN_READ_ONLY = 0x00000100
MPQ_FILE_COMPRESS = 0x00000200
MPQ_FILE_REPLACEEXISTING = 0x80000000
MPQ_COMPRESSION_ZLIB = 0x00000002
MPQ_COMPRESSION_NEXT_SAME = 0xFFFFFFFF


class StormError(RuntimeError):
    pass


class StormLib:
    _dll = None

    @classmethod
    def load(cls):
        if cls._dll is not None:
            return cls._dll

        dll_path = require_file(STORM_DLL, "StormLib DLL")
        dll = ctypes.WinDLL(str(dll_path), use_last_error=True)

        dll.SFileOpenArchive.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(HANDLE),
        ]
        dll.SFileOpenArchive.restype = wintypes.BOOL
        dll.SFileCloseArchive.argtypes = [HANDLE]
        dll.SFileCloseArchive.restype = wintypes.BOOL
        dll.SFileExtractFile.argtypes = [
            HANDLE,
            ctypes.c_char_p,
            wintypes.LPCWSTR,
            wintypes.DWORD,
        ]
        dll.SFileExtractFile.restype = wintypes.BOOL
        dll.SFileAddFileEx.argtypes = [
            HANDLE,
            wintypes.LPCWSTR,
            ctypes.c_char_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        dll.SFileAddFileEx.restype = wintypes.BOOL
        dll.SFileFlushArchive.argtypes = [HANDLE]
        dll.SFileFlushArchive.restype = wintypes.BOOL
        dll.SFileCompactArchive.argtypes = [
            HANDLE,
            wintypes.LPCWSTR,
            wintypes.BOOL,
        ]
        dll.SFileCompactArchive.restype = wintypes.BOOL

        cls._dll = dll
        return dll


def _fail(operation: str, archive: Path) -> None:
    error = ctypes.get_last_error()
    raise StormError(f"{operation} 失败：{archive}（Win32={error}）")


class MPQArchive:
    def __init__(self, path: Path, writable: bool = False):
        self.path = Path(path).resolve()
        require_file(self.path, "MPQ 地图")
        self.writable = writable
        self.dll = StormLib.load()
        self.handle = HANDLE()
        flags = 0 if writable else MPQ_OPEN_READ_ONLY
        if not self.dll.SFileOpenArchive(
            str(self.path), 0, flags, ctypes.byref(self.handle)
        ):
            _fail("打开地图", self.path)

    def close(self) -> None:
        if self.handle:
            if not self.dll.SFileCloseArchive(self.handle):
                _fail("关闭地图", self.path)
            self.handle = HANDLE()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def extract_file(self, archived_name: str, output: Path) -> Path:
        output = Path(output).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        if not self.dll.SFileExtractFile(
            self.handle,
            archived_name.encode("ascii"),
            str(output),
            0,
        ):
            _fail(f"提取 {archived_name}", self.path)
        return output

    def read_bytes(self, archived_name: str) -> bytes:
        fd, temp_name = tempfile.mkstemp(prefix="botc-mpq-", suffix=".bin")
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            self.extract_file(archived_name, temp_path)
            return temp_path.read_bytes()
        finally:
            temp_path.unlink(missing_ok=True)

    def read_text(self, archived_name: str) -> str:
        return self.read_bytes(archived_name).decode("utf-8-sig")

    def put_file(
        self,
        archived_name: str,
        local_path: Path,
        replace: bool = True,
        compact: bool = True,
    ) -> None:
        if not self.writable:
            raise StormError("地图不是以可写方式打开的")
        local_path = Path(local_path).resolve()
        require_file(local_path, "本地写入文件")
        flags = MPQ_FILE_COMPRESS
        if replace:
            flags |= MPQ_FILE_REPLACEEXISTING
        if not self.dll.SFileAddFileEx(
            self.handle,
            str(local_path),
            archived_name.encode("ascii"),
            flags,
            MPQ_COMPRESSION_ZLIB,
            MPQ_COMPRESSION_NEXT_SAME,
        ):
            _fail(f"写入 {archived_name}", self.path)
        if not self.dll.SFileFlushArchive(self.handle):
            _fail("刷新地图", self.path)
        if compact and not self.dll.SFileCompactArchive(
            self.handle, None, False
        ):
            _fail("压缩地图", self.path)

    def compact(self) -> None:
        if not self.dll.SFileFlushArchive(self.handle):
            _fail("刷新地图", self.path)
        if not self.dll.SFileCompactArchive(self.handle, None, False):
            _fail("压缩地图", self.path)

    def listfile(self) -> list[str]:
        raw = self.read_bytes("(listfile)")
        return [
            line.strip()
            for line in raw.decode("utf-8", "replace").splitlines()
            if line.strip()
        ]
