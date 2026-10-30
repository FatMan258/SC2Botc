from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from botc_config import SCRIPT_PATH, require_file


@dataclass
class ScanResult:
    paren_depth: int = 0
    brace_depth: int = 0
    bracket_depth: int = 0
    min_paren: int = 0
    min_brace: int = 0
    min_bracket: int = 0
    in_string: bool = False
    in_block_comment: bool = False


def scan_galaxy(text: str) -> ScanResult:
    result = ScanResult()
    in_line_comment = False
    escaped = False
    i = 0

    while i < len(text):
        char = text[i]
        following = text[i + 1] if i + 1 < len(text) else "\0"

        if in_line_comment:
            if char in "\r\n":
                in_line_comment = False
            i += 1
            continue

        if result.in_block_comment:
            if char == "*" and following == "/":
                result.in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if result.in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                result.in_string = False
            i += 1
            continue

        if char == "/" and following == "/":
            in_line_comment = True
            i += 2
            continue
        if char == "/" and following == "*":
            result.in_block_comment = True
            i += 2
            continue
        if char == '"':
            result.in_string = True
            i += 1
            continue

        if char == "(":
            result.paren_depth += 1
        elif char == ")":
            result.paren_depth -= 1
            result.min_paren = min(result.min_paren, result.paren_depth)
        elif char == "{":
            result.brace_depth += 1
        elif char == "}":
            result.brace_depth -= 1
            result.min_brace = min(result.min_brace, result.brace_depth)
        elif char == "[":
            result.bracket_depth += 1
        elif char == "]":
            result.bracket_depth -= 1
            result.min_bracket = min(result.min_bracket, result.bracket_depth)
        i += 1

    return result


RETURN_TYPES = (
    "void",
    "bool",
    "int",
    "fixed",
    "string",
    "text",
    "unit",
    "trigger",
    "point",
    "playergroup",
    "unitgroup",
    "region",
    "timer",
    "order",
    "soundlink",
    "actormsgtype",
)
FUNCTION_DEF = re.compile(
    rf"^(?:{'|'.join(RETURN_TYPES)})\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\([^;{}]*\)\s*\{",
    re.MULTILINE,
)


def check_script(path: Path) -> tuple[list[str], list[str]]:
    path = require_file(Path(path), "Galaxy 脚本")
    raw = path.read_bytes()
    errors: list[str] = []
    warnings: list[str] = []

    if not raw.startswith(b"\xef\xbb\xbf"):
        warnings.append("正式粘贴脚本没有 UTF-8 BOM")
    if b"\x00" in raw:
        errors.append("文件中存在 NUL 字节")

    lf = raw.count(b"\n")
    crlf = raw.count(b"\r\n")
    lone_cr = raw.count(b"\r") - crlf
    if lf != crlf:
        errors.append(f"存在 {lf - crlf} 个单独的 LF，正式脚本必须使用 CRLF")
    if lone_cr:
        errors.append(f"存在 {lone_cr} 个单独的 CR")

    text = raw.decode("utf-8-sig")
    result = scan_galaxy(text)
    if result.in_string:
        errors.append("字符串没有闭合")
    if result.in_block_comment:
        errors.append("块注释没有闭合")
    if result.paren_depth or result.min_paren < 0:
        errors.append(f"圆括号不配平：结束深度 {result.paren_depth}")
    if result.brace_depth or result.min_brace < 0:
        errors.append(f"花括号不配平：结束深度 {result.brace_depth}")
    if result.bracket_depth or result.min_bracket < 0:
        errors.append(f"方括号不配平：结束深度 {result.bracket_depth}")

    names = FUNCTION_DEF.findall(text)
    duplicates = sorted({name for name in names if names.count(name) > 1})
    for name in duplicates:
        errors.append(f"函数定义重复：{name}")

    if "void BOTC_Init (" not in text and "void BOTC_Init()" not in text:
        errors.append("找不到 BOTC_Init()")
    if "for (i = 0; i <= 147; i += 1)" not in text:
        warnings.append("没有发现当前角色上限 147 的扫描循环，确认是否已扩展")

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 BOTC Galaxy 源脚本")
    parser.add_argument("script", nargs="?", type=Path, default=SCRIPT_PATH)
    args = parser.parse_args(argv)

    errors, warnings = check_script(args.script)
    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")

    if errors:
        return 1
    print(f"OK    {args.script}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
