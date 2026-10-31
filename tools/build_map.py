from __future__ import annotations

import argparse
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from botc_config import (
    BUILD_DIR,
    LOCAL_ASSETS_DIR,
    MAP_PATH,
    SCRIPT_PATH,
    TRACKED_ASSETS_DIR,
    ensure_build_dir,
    require_file,
)
from galaxy_check import check_script
from stormlib_mpq import MPQArchive


CUSTOM_TITLE = "// Custom Script: BOTC_Init()"
CUSTOM_END = "// Custom Script Initialization"
MAP_SCRIPT = "MapScript.galaxy"
TRIGGERS_MEMBER = "Triggers"
CUSTOM_SCRIPT_NAME = "BOTC_CustomLogic"
CUSTOM_SCRIPT_MEMBER = f"{CUSTOM_SCRIPT_NAME}.galaxy"
CUSTOM_SCRIPT_INCLUDE = f'include "{CUSTOM_SCRIPT_NAME}"'
CUSTOM_TRIGGER_INCLUDE = f"include &quot;{CUSTOM_SCRIPT_NAME}&quot;"
CUSTOM_TRIGGER_PATTERN = re.compile(
    r'(<Element\s+Type="CustomScript"\s+Id="[^"]+">\s*<ScriptCode>)'
    r"(.*?)"
    r"(</ScriptCode>)",
    re.DOTALL,
)
RESERVED_MEMBERS = {
    MAP_SCRIPT,
    TRIGGERS_MEMBER,
    CUSTOM_SCRIPT_MEMBER,
}


def collect_local_assets(root: Path | None) -> list[tuple[str, Path]]:
    if root is None:
        return []
    root = Path(root)
    if not root.is_dir():
        return []
    assets: list[tuple[str, Path]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        member = path.relative_to(root).as_posix()
        if member in RESERVED_MEMBERS:
            raise ValueError(f"本地素材不能覆盖保留成员：{member}")
        try:
            member.encode("ascii")
        except UnicodeEncodeError as error:
            raise ValueError(
                f"地图内素材路径必须为 ASCII：{member}"
            ) from error
        assets.append((member, path))
    return assets


def merge_asset_payloads(
    *roots: Path | None,
) -> list[tuple[str, Path]]:
    merged: list[tuple[str, Path]] = []
    seen: dict[str, Path] = {}
    for root in roots:
        for member, path in collect_local_assets(root):
            previous = seen.get(member)
            if previous is not None:
                raise ValueError(
                    f"素材路径冲突：{member}（{previous} / {path}）"
                )
            seen[member] = path
            merged.append((member, path))
    return merged


def replace_custom_script(map_script: str, source: str) -> str:
    lines = map_script.replace("\r\n", "\n").splitlines()
    title_indexes = [
        index for index, line in enumerate(lines) if CUSTOM_TITLE in line
    ]
    end_indexes = [
        index
        for index, line in enumerate(lines)
        if line.strip() == CUSTOM_END
    ]
    if len(title_indexes) != 1:
        raise ValueError(f"自定义脚本起始标记数量异常：{len(title_indexes)}")
    if len(end_indexes) != 1:
        raise ValueError(f"自定义脚本结束标记数量异常：{len(end_indexes)}")

    title_index = title_indexes[0]
    end_marker = end_indexes[0]
    start = title_index + 2
    end = end_marker - 1
    if start >= len(lines) or end <= start:
        raise ValueError("自定义脚本区段为空或标记顺序异常")
    if not lines[title_index + 1].lstrip().startswith("//---"):
        raise ValueError("自定义脚本标题后的分隔线缺失")
    if not lines[end].lstrip().startswith("//---"):
        raise ValueError("Custom Script Initialization 前的分隔线缺失")

    clean_source = source.lstrip("\ufeff").replace("\r\n", "\n").rstrip("\n")
    if CUSTOM_TITLE in clean_source or CUSTOM_END in clean_source:
        raise ValueError("源脚本不应包含地图生成器标记")

    result_lines = [
        *lines[:start],
        *clean_source.splitlines(),
        *lines[end:],
    ]
    return "\r\n".join(result_lines) + "\r\n"


def split_custom_script(map_script: str) -> str:
    return replace_custom_script(map_script, CUSTOM_SCRIPT_INCLUDE)


def split_trigger_custom_scripts(triggers: str) -> str:
    matches = list(CUSTOM_TRIGGER_PATTERN.finditer(triggers))
    if len(matches) != 1:
        raise ValueError(
            f"Triggers 中自定义脚本节点数量异常：{len(matches)}"
        )

    def replace(match: re.Match[str]) -> str:
        return (
            match.group(1)
            + "\r\n            "
            + CUSTOM_TRIGGER_INCLUDE
            + "\r\n        "
            + match.group(3)
        )

    return CUSTOM_TRIGGER_PATTERN.sub(replace, triggers, count=1)


def verify_packed_script(map_script: str, source: str) -> list[str]:
    errors: list[str] = []
    if CUSTOM_END not in map_script:
        errors.append("缺少 Custom Script Initialization 标记")
    if "void InitCustomScript" not in map_script:
        errors.append("缺少 InitCustomScript")
    if "void InitMap" not in map_script:
        errors.append("缺少 InitMap")
    if map_script.count(CUSTOM_END) != 1:
        errors.append("Custom Script Initialization 标记重复")

    clean_source = source.lstrip("\ufeff").replace("\r\n", "\n").rstrip("\n")
    first = clean_source.splitlines()[0]
    last = clean_source.splitlines()[-1]
    custom = map_script.replace("\r\n", "\n")
    if first not in custom or last not in custom:
        errors.append("打包后的自定义脚本首尾行未找到")
    if map_script.encode("utf-8").startswith(b"\xef\xbb\xbf"):
        errors.append("MapScript.galaxy 含有 BOM")
    return errors


def verify_split_map_script(map_script: str) -> list[str]:
    errors: list[str] = []
    if map_script.count(CUSTOM_SCRIPT_INCLUDE) != 1:
        errors.append(f"{CUSTOM_SCRIPT_INCLUDE} 必须恰好出现一次")
    if CUSTOM_END not in map_script:
        errors.append("缺少 Custom Script Initialization 标记")
    if "void InitCustomScript" not in map_script:
        errors.append("缺少 InitCustomScript")
    if "void InitMap" not in map_script:
        errors.append("缺少 InitMap")
    if map_script.count(CUSTOM_END) != 1:
        errors.append("Custom Script Initialization 标记重复")
    if map_script.encode("utf-8").startswith(b"\xef\xbb\xbf"):
        errors.append("MapScript.galaxy 含有 BOM")
    return errors


def verify_split_triggers(triggers: str) -> list[str]:
    errors: list[str] = []
    matches = list(CUSTOM_TRIGGER_PATTERN.finditer(triggers))
    if len(matches) != 1:
        return [f"Triggers 中自定义脚本节点数量异常：{len(matches)}"]
    if matches[0].group(2).strip() != CUSTOM_TRIGGER_INCLUDE:
        errors.append("Triggers 自定义脚本节点仍包含完整源码")
    return errors


def build_map(
    map_path: Path,
    script_path: Path,
    output: Path,
    compact: bool = True,
    skip_check: bool = False,
    split_script: bool = False,
    tracked_assets: Path | None = None,
    local_assets: Path | None = None,
) -> Path:
    map_path = require_file(Path(map_path), "基础地图")
    script_path = require_file(Path(script_path), "Galaxy 脚本")

    if not skip_check:
        errors, warnings = check_script(script_path)
        for warning in warnings:
            print(f"WARN  {warning}")
        if errors:
            raise ValueError("Galaxy 静态检查失败：\n" + "\n".join(errors))

    source = script_path.read_text(encoding="utf-8-sig")
    with MPQArchive(map_path, writable=False) as archive:
        map_script = archive.read_text(MAP_SCRIPT)
        triggers = (
            archive.read_text(TRIGGERS_MEMBER) if split_script else None
        )

    clean_source = source.lstrip("\ufeff").replace("\r\n", "\n").rstrip("\n")
    external_payload = (clean_source + "\r\n").encode("utf-8")
    if split_script:
        packed_script = split_custom_script(map_script)
        assert triggers is not None
        packed_triggers = split_trigger_custom_scripts(triggers)
        verification = verify_split_map_script(packed_script)
        verification.extend(verify_split_triggers(packed_triggers))
    else:
        packed_script = replace_custom_script(map_script, source)
        verification = verify_packed_script(packed_script, source)
    if verification:
        raise ValueError("\n".join(verification))
    asset_payloads = merge_asset_payloads(tracked_assets, local_assets)

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if map_path.resolve() != output:
        shutil.copy2(map_path, output)

    fd, temp_map_name = tempfile.mkstemp(
        prefix="botc-mapscript-", suffix=".galaxy"
    )
    os.close(fd)
    temp_map_path = Path(temp_map_name)
    temp_external_path: Path | None = None
    temp_triggers_path: Path | None = None
    try:
        temp_map_path.write_bytes(packed_script.encode("utf-8"))
        payloads = [(MAP_SCRIPT, temp_map_path)]
        if split_script:
            fd, temp_external_name = tempfile.mkstemp(
                prefix="botc-customlogic-", suffix=".galaxy"
            )
            os.close(fd)
            temp_external_path = Path(temp_external_name)
            temp_external_path.write_bytes(external_payload)
            payloads.append((CUSTOM_SCRIPT_MEMBER, temp_external_path))
            fd, temp_triggers_name = tempfile.mkstemp(
                prefix="botc-triggers-", suffix=".xml"
            )
            os.close(fd)
            temp_triggers_path = Path(temp_triggers_name)
            temp_triggers_path.write_bytes(packed_triggers.encode("utf-8"))
            payloads.append((TRIGGERS_MEMBER, temp_triggers_path))
        payloads.extend(asset_payloads)
        with MPQArchive(output, writable=True) as archive:
            for member_name, local_path in payloads:
                archive.put_file(
                    member_name,
                    local_path,
                    replace=True,
                    compact=False,
                )
            if compact:
                archive.compact()
    finally:
        temp_map_path.unlink(missing_ok=True)
        if temp_external_path is not None:
            temp_external_path.unlink(missing_ok=True)
        if temp_triggers_path is not None:
            temp_triggers_path.unlink(missing_ok=True)

    with MPQArchive(output, writable=False) as archive:
        check_back = archive.read_text(MAP_SCRIPT)
        check_custom = (
            archive.read_bytes(CUSTOM_SCRIPT_MEMBER)
            if split_script
            else None
        )
        check_triggers = (
            archive.read_text(TRIGGERS_MEMBER) if split_script else None
        )
        asset_results = [
            (member, archive.read_bytes(member) == path.read_bytes())
            for member, path in asset_payloads
        ]
    if split_script:
        errors = verify_split_map_script(check_back)
        if check_custom != external_payload:
            errors.append(f"{CUSTOM_SCRIPT_MEMBER} 回读内容与源脚本不一致")
        if check_triggers != packed_triggers:
            errors.append(f"{TRIGGERS_MEMBER} 回读内容与预期不一致")
        errors.extend(verify_split_triggers(check_triggers))
    else:
        errors = verify_packed_script(check_back, source)
    for member, matches in asset_results:
        if not matches:
            errors.append(f"本地素材回读不一致：{member}")
    if errors:
        raise ValueError("回读校验失败：\n" + "\n".join(errors))
    if asset_payloads:
        print(f"assets   : 已注入 {len(asset_payloads)} 个素材（仓库 + 本地）")

    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 BOTC 自定义脚本直接写入 SC2Map"
    )
    parser.add_argument("--map", type=Path, default=MAP_PATH)
    parser.add_argument("--script", type=Path, default=SCRIPT_PATH)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--no-compact", action="store_true")
    parser.add_argument("--skip-check", action="store_true")
    parser.add_argument(
        "--split-script",
        action="store_true",
        help=f"把主逻辑写入 {CUSTOM_SCRIPT_MEMBER}，MapScript 只保留 include",
    )
    parser.add_argument("--local-assets", type=Path, default=LOCAL_ASSETS_DIR)
    parser.add_argument("--no-local-assets", action="store_true")
    args = parser.parse_args(argv)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = args.name or f"血染钟楼_build_{stamp}"
    output = args.out or (ensure_build_dir(BUILD_DIR) / f"{name}.SC2Map")

    print(f"map      : {args.map}")
    print(f"script   : {args.script}")
    print(f"output   : {output}")
    local_assets = None if args.no_local_assets else args.local_assets
    if local_assets is not None and not local_assets.is_dir():
        if local_assets == LOCAL_ASSETS_DIR:
            print(f"assets   : 未找到 {local_assets}，不注入本地素材")
            local_assets = None
        else:
            raise FileNotFoundError(f"本地素材目录不存在：{local_assets}")
    tracked_assets = TRACKED_ASSETS_DIR if TRACKED_ASSETS_DIR.is_dir() else None
    built = build_map(
        args.map,
        args.script,
        output,
        compact=not args.no_compact,
        skip_check=args.skip_check,
        split_script=args.split_script,
        tracked_assets=tracked_assets,
        local_assets=local_assets,
    )
    print(f"OK       : {built} ({built.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
