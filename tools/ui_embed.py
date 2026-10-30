from __future__ import annotations

import os
import re
import struct
import tempfile
from pathlib import Path

from stormlib_mpq import MPQArchive


UI_DEPENDENCY_MARKER = b"UIHIDE"
UI_LAYOUT = r"Base.SC2Data\UI\Layout\BotcChatHide.SC2Layout"
UI_DESC_INDEX = r"Base.SC2Data\UI\Layout\DescIndex.SC2Layout"


def strip_ui_dependency_document_info(data: bytes) -> bytes:
    text = data.decode("utf-8-sig")
    pattern = re.compile(
        r"^[ \t]*<Value>[^<]*UIHIDE[^<]*</Value>\r?\n?",
        flags=re.MULTILINE | re.IGNORECASE,
    )
    updated, count = pattern.subn("", text)
    if count > 1:
        raise ValueError(f"DocumentInfo 中发现 {count} 条 UIHIDE 依赖")
    if "UIHIDE" in updated:
        raise ValueError("DocumentInfo 仍残留 UIHIDE 引用")
    return updated.encode("utf-8")


def strip_ui_dependency_header(data: bytes) -> bytes:
    if not data.startswith(b"H2CS"):
        raise ValueError("DocumentHeader 不是 H2CS 格式")

    first_start = data.find(b"bnet:")
    if first_start < 4:
        if UI_DEPENDENCY_MARKER not in data.upper():
            return data
        raise ValueError("找不到 DocumentHeader 依赖表")

    count_offset = first_start - 4
    dependency_count = struct.unpack_from("<I", data, count_offset)[0]
    if dependency_count < 1 or dependency_count > 64:
        raise ValueError(f"DocumentHeader 依赖数量异常：{dependency_count}")

    dependencies: list[bytes] = []
    position = first_start
    for _ in range(dependency_count):
        end = data.find(b"\0", position)
        if end < 0:
            raise ValueError("DocumentHeader 依赖字符串没有结束符")
        dependencies.append(data[position:end])
        position = end + 1

    filtered = [
        dependency
        for dependency in dependencies
        if UI_DEPENDENCY_MARKER not in dependency.upper()
    ]
    if len(filtered) == len(dependencies):
        return data
    if len(dependencies) - len(filtered) > 1:
        raise ValueError("DocumentHeader 中存在多条 UIHIDE 依赖")

    rebuilt = (
        data[:count_offset]
        + struct.pack("<I", len(filtered))
        + b"\0".join(filtered)
        + b"\0"
        + data[position:]
    )
    if UI_DEPENDENCY_MARKER in rebuilt[: position + 64].upper():
        raise ValueError("DocumentHeader 仍残留 UIHIDE 依赖")
    return rebuilt


def should_embed_member(name: str) -> bool:
    lower = name.lower()
    if lower in {
        "componentlist.sc2components",
        "documentinfo",
        "documentheader",
        "documentinfo.version",
        "gamedata.version",
        "gametext.version",
        "zhcn.sc2data\\localizeddata\\gamestrings.txt",
        "streamlined-md5.lst",
        "preloadassetdb.txt",
    }:
        return False
    if lower.startswith("base.sc2data\\ui\\"):
        return True
    if lower == "base.sc2data\\gamedata\\assets.txt":
        return True
    return lower.startswith(
        (
            "flag_",
            "icon_1v1_",
            "player_race_",
            "ui_custom_",
            "ui_observer_",
        )
    )


def _write_bytes(archive: MPQArchive, name: str, payload: bytes) -> None:
    fd, temp_name = tempfile.mkstemp(prefix="botc-ui-", suffix=".bin")
    os.close(fd)
    path = Path(temp_name)
    try:
        path.write_bytes(payload)
        archive.put_file(name, path, replace=True, compact=False)
    finally:
        path.unlink(missing_ok=True)


def embed_ui(archive_path: Path, mod_path: Path) -> int:
    archive_path = Path(archive_path).resolve()
    mod_path = Path(mod_path).resolve()
    if not mod_path.is_file():
        raise FileNotFoundError(f"UI 依赖不存在：{mod_path}")

    with MPQArchive(mod_path, writable=False) as mod:
        mod_names = mod.listfile()
        if UI_LAYOUT not in mod_names:
            raise ValueError(f"UI 依赖缺少 {UI_LAYOUT}")
        members = [name for name in mod_names if should_embed_member(name)]
        payloads = {name: mod.read_bytes(name) for name in members}

    with MPQArchive(archive_path, writable=True) as archive:
        for name, payload in payloads.items():
            _write_bytes(archive, name, payload)

        document_info = strip_ui_dependency_document_info(
            archive.read_bytes("DocumentInfo")
        )
        document_header = strip_ui_dependency_header(
            archive.read_bytes("DocumentHeader")
        )
        _write_bytes(archive, "DocumentInfo", document_info)
        _write_bytes(archive, "DocumentHeader", document_header)
        archive.compact()
    return len(payloads)


def verify_embedded_ui(archive_path: Path) -> list[str]:
    errors: list[str] = []
    with MPQArchive(archive_path, writable=False) as archive:
        names = set(archive.listfile())
        for required in (UI_LAYOUT, UI_DESC_INDEX):
            if required not in names:
                errors.append(f"缺少内嵌 UI 文件：{required}")
        document_info = archive.read_text("DocumentInfo")
        if "UIHIDE" in document_info:
            errors.append("DocumentInfo 仍包含 UIHIDE 依赖")
        header = archive.read_bytes("DocumentHeader")
        if UI_DEPENDENCY_MARKER in header.upper():
            errors.append("DocumentHeader 仍包含 UIHIDE 依赖")
    return errors
