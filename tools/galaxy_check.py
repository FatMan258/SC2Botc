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
FUNCTION_DECL = re.compile(
    rf"^(?:{'|'.join(RETURN_TYPES)})\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\([^;{}]*\)\s*;",
    re.MULTILINE,
)
FUNCTION_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
ARRAY_DECL = re.compile(
    rf"^[ \t]*(?:{'|'.join(RETURN_TYPES)})\s*"
    r"\[\s*(\d+)\s*\]\s+([A-Za-z_][A-Za-z0-9_]*)\s*;",
    re.MULTILINE,
)
ARRAY_CAPACITY_GROUPS = (
    ("g_jinxA", "g_jinxB", "g_jinxText", "g_jinxText2", "g_jinxText3"),
)
ARRAY_COUNT_CAPACITY = (("g_jinxCount", "g_jinxA"),)
# 数组维度必须写在类型后：`int[14] g_vote;`。
#   反过来写成 `int g_vote[14];` 编辑器会报「数组的定义需要在类型后添加维度」，
#   整份脚本编译失败（地图里所有按钮都不会出现），所以单独查一遍。
REVERSED_ARRAY_DECL = re.compile(
    r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\[\s*(\d+)\s*\]\s*;",
    re.MULTILINE,
)
# 这些关键字后面跟 `名字[数字];` 是普通语句（例如 `return g_x[3];`），不是声明。
REVERSED_ARRAY_SKIP_WORDS = {
    "return",
    "if",
    "else",
    "while",
    "for",
    "do",
    "switch",
    "case",
    "break",
    "continue",
    "true",
    "false",
    "null",
    "and",
    "or",
    "not",
}


def mask_galaxy_comments_and_strings(text: str) -> str:
    chars = list(text)
    in_line_comment = False
    in_block_comment = False
    in_string = False
    escaped = False
    i = 0
    while i < len(text):
        char = text[i]
        following = text[i + 1] if i + 1 < len(text) else "\0"
        if in_line_comment:
            if char in "\r\n":
                in_line_comment = False
            else:
                chars[i] = " "
            i += 1
            continue
        if in_block_comment:
            if char == "*" and following == "/":
                chars[i] = " "
                chars[i + 1] = " "
                in_block_comment = False
                i += 2
            else:
                if char not in "\r\n":
                    chars[i] = " "
                i += 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            if char not in "\r\n":
                chars[i] = " "
            i += 1
            continue
        if char == "/" and following == "/":
            chars[i] = " "
            chars[i + 1] = " "
            in_line_comment = True
            i += 2
            continue
        if char == "/" and following == "*":
            chars[i] = " "
            chars[i + 1] = " "
            in_block_comment = True
            i += 2
            continue
        if char == '"':
            chars[i] = " "
            in_string = True
        i += 1
    return "".join(chars)


def matching_brace(text: str, opening: int) -> int:
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def find_forward_call_errors(text: str) -> list[str]:
    clean = mask_galaxy_comments_and_strings(text)
    definitions: dict[str, list[tuple[int, int, int]]] = {}
    declarations: dict[str, list[int]] = {}
    for match in FUNCTION_DEF.finditer(clean):
        name = match.group(1)
        opening = match.end() - 1
        closing = matching_brace(clean, opening)
        if closing >= 0:
            definitions.setdefault(name, []).append(
                (match.start(), opening, closing)
            )
    for match in FUNCTION_DECL.finditer(clean):
        declarations.setdefault(match.group(1), []).append(match.start())

    errors: list[str] = []
    reported: set[tuple[str, str]] = set()
    for caller, bodies in definitions.items():
        for _, opening, closing in bodies:
            for call in FUNCTION_CALL.finditer(clean, opening + 1, closing):
                callee = call.group(1)
                if callee not in definitions:
                    continue
                if not any(start > call.start() for start, _, _ in definitions[callee]):
                    continue
                if any(pos < call.start() for pos in declarations.get(callee, [])):
                    continue
                key = (caller, callee)
                if key in reported:
                    continue
                reported.add(key)
                line = text.count("\n", 0, call.start()) + 1
                errors.append(
                    f"{caller}() 在第 {line} 行调用了后定义函数 {callee}()，"
                    "但调用前没有前置声明"
                )
    return errors


def find_literal_array_index_errors(text: str) -> list[str]:
    clean = mask_galaxy_comments_and_strings(text)
    arrays: dict[str, int] = {
        match.group(2): int(match.group(1))
        for match in ARRAY_DECL.finditer(clean)
    }
    errors: list[str] = []
    for name, capacity in arrays.items():
        access = re.compile(
            rf"\b{re.escape(name)}\s*\[\s*(-?\d+)\s*\]"
        )
        for match in access.finditer(clean):
            index = int(match.group(1))
            if 0 <= index < capacity:
                continue
            line = text.count("\n", 0, match.start()) + 1
            errors.append(
                f"{name}[{index}] 超出数组容量 {capacity}（第 {line} 行）"
            )
        # 【板子下标】name[(N * 256) + M] / name[N * 256 + M]：2026-11-22 加第 16 张板子时漏扩数组
        access_expr = re.compile(
            rf"\b{re.escape(name)}\s*\[\s*\(?\s*(\d+)\s*\*\s*256\s*\)?\s*\+\s*(\d+)\s*\]"
        )
        for match in access_expr.finditer(clean):
            index = int(match.group(1)) * 256 + int(match.group(2))
            if 0 <= index < capacity:
                continue
            line = text.count("\n", 0, match.start()) + 1
            errors.append(
                f"{name}[({match.group(1)} * 256) + {match.group(2)}] = {index} 超出数组容量 {capacity}（第 {line} 行）"
            )
    return errors



def find_non_ascii_in_code_errors(text: str) -> list[str]:
    """Galaxy 代码区（去掉字符串与 // 注释后）出现中文 = 漏写 // 的注释，编译器必报错。"""
    errors: list[str] = []
    for idx, line in enumerate(text.splitlines(), start=1):
        s = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
        pos = s.find("//")
        if pos >= 0:
            s = s[:pos]
        if re.search(r"[^\x00-\x7f]", s):
            errors.append(f"第 {idx} 行：代码里出现中文（注释少了 //？）：{line.strip()[:80]}")
    return errors


def find_padding_corruption_errors(text: str) -> list[str]:
    """连续 20 行以上的「只有空格且很长」的行 = 文件曾被截断后用空格补齐，必须还原。"""
    errors: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].strip() == "" and len(lines[i]) >= 20:
            start = i
            while i < len(lines) and lines[i].strip() == "" and len(lines[i]) >= 20:
                i += 1
            if i - start >= 20:
                errors.append(f"第 {start + 1}~{i} 行整段被空格填充（{i - start} 行），疑似文件被截断")
        else:
            i += 1
    return errors


def find_called_undefined_errors(text: str) -> list[str]:
    """前置声明了、但整份脚本里找不到定义、而且还被调用 → 编译期「函数已声明但尚未定义」。"""
    clean = mask_galaxy_comments_and_strings(text)
    pattern = re.compile(
        r"(?m)^[ \t]*(?:void|bool|int|fixed|string|text|color|unit|sound|point|region|"
        r"timer|dialog|playergroup|bank|trigger)\s+([A-Za-z_]\w*)\s*\([^;{)]*\)"
    )
    decls = {m.group(1): m.start() for m in pattern.finditer(clean)}
    defs = {m.group(1) for m in re.finditer(
        r"(?m)^[ \t]*(?:void|bool|int|fixed|string|text|color|unit|sound|point|region|"
        r"timer|dialog|playergroup|bank|trigger)\s+([A-Za-z_]\w*)\s*\([^;{)]*\)\s*\{", clean)}
    errors: list[str] = []
    for name in sorted(set(decls) - defs):
        calls = len(re.findall(r"\b" + re.escape(name) + r"\s*\(", clean))
        if calls > 1:
            line = clean.count("\n", 0, decls[name]) + 1
            errors.append(f"{name} 只声明（第 {line} 行）没有定义，但有调用；编译器会报「函数已声明但尚未定义」")
    return errors

def find_reversed_array_declaration_errors(text: str) -> list[str]:
    clean = mask_galaxy_comments_and_strings(text)
    errors: list[str] = []
    for match in REVERSED_ARRAY_DECL.finditer(clean):
        type_name = match.group(1)
        var_name = match.group(2)
        capacity = match.group(3)
        if type_name in REVERSED_ARRAY_SKIP_WORDS:
            continue
        line = text.count("\n", 0, match.start()) + 1
        errors.append(
            f"第 {line} 行数组声明把维度写在变量名后：{type_name} {var_name}[{capacity}];，"
            f"应写成 {type_name}[{capacity}] {var_name};"
        )
    return errors


def find_array_capacity_errors(text: str) -> list[str]:
    clean = mask_galaxy_comments_and_strings(text)
    arrays: dict[str, int] = {
        match.group(2): int(match.group(1))
        for match in ARRAY_DECL.finditer(clean)
    }
    errors: list[str] = []
    for names in ARRAY_CAPACITY_GROUPS:
        present = [(name, arrays[name]) for name in names if name in arrays]
        capacities = {capacity for _, capacity in present}
        if len(capacities) > 1:
            detail = ", ".join(f"{name}[{capacity}]" for name, capacity in present)
            errors.append(f"配套数组容量不一致：{detail}")

    for count_name, array_name in ARRAY_COUNT_CAPACITY:
        if count_name not in clean or array_name not in arrays:
            continue
        assignment = re.search(
            rf"\b{re.escape(count_name)}\s*=\s*(\d+)\s*;",
            clean,
        )
        if assignment is None:
            continue
        count = int(assignment.group(1))
        capacity = arrays[array_name]
        if count > capacity:
            line = text.count("\n", 0, assignment.start()) + 1
            errors.append(
                f"{count_name} = {count} 超出 {array_name} "
                f"容量 {capacity}（第 {line} 行）"
            )
    return errors


def find_trigger_callback_errors(text: str) -> list[str]:
    """TriggerCreate uses a string, so normal call checks cannot verify its ABI."""
    clean = mask_galaxy_comments_and_strings(text)
    signatures = {
        match.group(2): (match.group(1), match.group(3).strip())
        for match in re.finditer(
            r"^(\w+)\s+(\w+)\s*\(([^;{}]*)\)\s*\{", clean, re.MULTILINE
        )
    }
    errors = []
    for call in re.finditer(r"\bTriggerCreate\s*\(\s*", clean):
        # Strings are masked in clean; take the literal from the original text.
        literal = re.match(r'\bTriggerCreate\s*\(\s*"(\w+)"\s*\)', text[call.start():])
        if literal is None:
            continue
        name = literal.group(1)
        if name not in signatures:
            # Included libraries may define callbacks outside this source file.
            if name.startswith("BOTC_"):
                errors.append(f"TriggerCreate 注册了未定义的回调 {name}")
            continue
        result, params = signatures[name]
        types = [param.strip().split()[0] for param in params.split(",") if param.strip()]
        if result != "bool" or types != ["bool", "bool"]:
            line = text.count("\n", 0, call.start()) + 1
            errors.append(
                f"第 {line} 行 TriggerCreate 回调 {name} 的签名为 {result} ({params})，"
                "必须为 bool (bool testConds, bool runActions)"
            )
    return errors


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
    errors.extend(find_forward_call_errors(text))
    errors.extend(find_reversed_array_declaration_errors(text))
    errors.extend(find_literal_array_index_errors(text))
    errors.extend(find_non_ascii_in_code_errors(text))
    errors.extend(find_padding_corruption_errors(text))
    errors.extend(find_called_undefined_errors(text))
    errors.extend(find_array_capacity_errors(text))
    errors.extend(find_trigger_callback_errors(text))

    if "void BOTC_Init (" not in text and "void BOTC_Init()" not in text:
        errors.append("找不到 BOTC_Init()")
    if ("for (i = 0; i <= 163; i += 1)" not in text
            and "for (i = 0; i <= 164; i += 1)" not in text
            and "for (i = 0; i <= 165; i += 1)" not in text
            and "for (i = 0; i <= 166; i += 1)" not in text):
        warnings.append("没有发现角色上限 163～166 的扫描循环，确认是否已扩展")

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
