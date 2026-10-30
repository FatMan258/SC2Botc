from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from botc_config import MAP_PATH, ROLE_SPEC_DIR, SCRIPT_PATH, require_file
from stormlib_mpq import MPQArchive


TEAM_CODES = {
    "townsfolk": 0,
    "outsider": 1,
    "minion": 2,
    "demon": 3,
    "legend": 4,
    "journey": 5,
}
ALIGN_CODES = {"good": 0, "evil": 1}
ACTION_CODES = {
    "passive": 0,
    "every_night": 1,
    "second_night_plus": 2,
    "public_trigger": 3,
    "triggered": 4,
    "first_night": 5,
    "conditional": 6,
}


def default_spec(index: int, name: str, team: str, alignment: str) -> dict:
    return {
        "schema_version": 1,
        "index": index,
        "name": name,
        "team": team,
        "alignment": alignment,
        "ability": "",
        "ability_fragments": [],
        "action": "passive",
        "target_count": 0,
        "first_night_order": None,
        "other_night_order": None,
        "role_tag": 0,
        "role_keywords": "",
        "boards": [7],
        "tokens": [],
        "death_token_slot": None,
        "resources": {
            "role_icon": f"botc_role{index}.dds",
            "night_icon": f"botc_night{index}.dds",
            "token_icons": [],
        },
        "implementation": {
            "required_functions": [],
            "required_symbols": [],
            "state_fields": [],
            "reset_points": [],
        },
        "acceptance": [
            "中毒和醉酒时面板可打开，按规则决定是否生效",
            "换座位后目标选择和确认仍然有效",
            "换说书人只读取新的真值行",
            "第二局不会残留状态和 token",
            "取消、拒绝发动和无效目标不会误结算",
        ],
    }


def create_spec(
    output: Path,
    index: int,
    name: str,
    team: str,
    alignment: str,
    force: bool,
    script_path: Path,
) -> Path:
    if team not in TEAM_CODES:
        raise ValueError(f"未知阵营：{team}")
    if alignment not in ALIGN_CODES:
        raise ValueError(f"未知阵营倾向：{alignment}")
    if index < 0:
        raise ValueError("角色索引不能小于 0")
    if output.exists() and not force:
        raise FileExistsError(f"规格已存在：{output}")
    script = require_file(Path(script_path), "Galaxy 脚本").read_text(
        encoding="utf-8-sig"
    )
    if _assignment(script, "g_roleName", index) is not None and not force:
        raise ValueError(f"角色索引 {index} 已在脚本中使用；确认要复用时加 --force")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            default_spec(index, name, team, alignment),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def list_roles(script_path: Path) -> int:
    script = require_file(Path(script_path), "Galaxy 脚本").read_text(
        encoding="utf-8-sig"
    )
    pattern = re.compile(r"g_roleName\s*\[\s*(\d+)\s*\]\s*=\s*\"((?:[^\"\\]|\\.)*)\"")
    roles = sorted((int(index), name) for index, name in pattern.findall(script))
    for index, name in roles:
        print(f"{index:3d}  {name}")
    used = {index for index, _ in roles}
    next_index = 0
    while next_index in used:
        next_index += 1
    print(f"NEXT      : {next_index}")
    print(f"MAX       : {max(used, default=-1)}")
    return 0


def _assignment(script: str, field: str, index: int) -> str | None:
    pattern = rf"\b{re.escape(field)}\s*\[\s*{index}\s*\]\s*=\s*([^;]+);"
    match = re.search(pattern, script)
    return match.group(1).strip() if match else None


def _resource_names(map_path: Path | None) -> set[str]:
    if not map_path:
        return set()
    with MPQArchive(map_path, writable=False) as archive:
        return {name.replace("/", "\\").lower() for name in archive.listfile()}


def audit_spec(spec_path: Path, script_path: Path, map_path: Path | None) -> tuple[list[str], list[str]]:
    spec_path = require_file(Path(spec_path), "角色规格")
    script_path = require_file(Path(script_path), "Galaxy 脚本")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    script = script_path.read_text(encoding="utf-8-sig")

    index = int(spec["index"])
    name = str(spec["name"])
    team = str(spec["team"])
    alignment = str(spec["alignment"])
    action = str(spec["action"])
    target_count = int(spec.get("target_count", 0))
    errors: list[str] = []
    warnings: list[str] = []

    role_name = _assignment(script, "g_roleName", index)
    if role_name != json.dumps(name, ensure_ascii=False):
        errors.append(f"g_roleName[{index}] 应为 \"{name}\"，实际为 {role_name}")

    expected_team = str(TEAM_CODES.get(team, -999))
    if _assignment(script, "g_roleTeam", index) != expected_team:
        errors.append(f"g_roleTeam[{index}] 应为 {expected_team}")
    expected_align = str(ALIGN_CODES.get(alignment, -999))
    if _assignment(script, "g_roleAlign", index) != expected_align:
        errors.append(f"g_roleAlign[{index}] 应为 {expected_align}")

    expected_targets = str(target_count)
    actual_targets = _assignment(script, "g_roleTargets", index)
    if actual_targets not in (None, expected_targets):
        errors.append(f"g_roleTargets[{index}] 应为 {expected_targets}，实际为 {actual_targets}")
    elif actual_targets is None and expected_targets != "0":
        errors.append(f"缺少 g_roleTargets[{index}] = {expected_targets}")

    expected_act = str(ACTION_CODES.get(action, -999))
    actual_act = _assignment(script, "g_roleAct", index)
    if actual_act not in (None, expected_act):
        errors.append(f"g_roleAct[{index}] 应为 {expected_act}，实际为 {actual_act}")
    elif actual_act is None and expected_act != "0":
        errors.append(f"缺少 g_roleAct[{index}] = {expected_act}")

    role_tag = int(spec.get("role_tag", 0))
    if role_tag:
        if _assignment(script, "g_roleTag", index) != str(role_tag):
            errors.append(f"g_roleTag[{index}] 应为 {role_tag}")

    keywords = str(spec.get("role_keywords", ""))
    if keywords and _assignment(script, "g_roleKey", index) != json.dumps(
        keywords, ensure_ascii=False
    ):
        errors.append(f"g_roleKey[{index}] 应为 \"{keywords}\"")

    first_order = spec.get("first_night_order")
    other_order = spec.get("other_night_order")
    if first_order is not None:
        if _assignment(script, "g_noAllFirst", index) != str(first_order):
            errors.append(f"g_noAllFirst[{index}] 应为 {first_order}")
    if other_order is not None:
        if _assignment(script, "g_noAllOther", index) != str(other_order):
            errors.append(f"g_noAllOther[{index}] 应为 {other_order}")

    if f"g_tipAbility[{index}]" not in script:
        errors.append(f"缺少 g_tipAbility[{index}]")
    if f"g_tipRoleAt[{index}]" not in script:
        errors.append(f"缺少 g_tipRoleAt[{index}]")
    if f"g_tipRoleN[{index}]" not in script:
        errors.append(f"缺少 g_tipRoleN[{index}]")
    for fragment in spec.get("ability_fragments", []):
        if fragment not in script:
            errors.append(f"能力文本片段未找到：{fragment}")

    for token in spec.get("tokens", []):
        slot = int(token["slot"])
        for key, field in (
            ("name", "g_tokName"),
            ("short", "g_tokShort"),
            ("icon", "g_tokIcon"),
        ):
            value = token.get(key)
            if value is not None and _assignment(script, field, slot) != json.dumps(
                str(value), ensure_ascii=False
            ):
                errors.append(f"{field}[{slot}] 应为 \"{value}\"")
        if _assignment(script, "g_tokName", slot) is None:
            errors.append(f"缺少 token 名称 g_tokName[{slot}]")
        if _assignment(script, "g_tokRole", slot) != str(index):
            errors.append(f"g_tokRole[{slot}] 应绑定角色 {index}")

    death_slot = spec.get("death_token_slot")
    if death_slot is not None:
        if _assignment(script, "g_roleDeathTok", index) != str(death_slot):
            errors.append(f"g_roleDeathTok[{index}] 应为 {death_slot}")

    for board in spec.get("boards", []):
        board = int(board)
        pattern = rf"g_boardRole\s*\[\s*\(?\s*{board}\s*\*\s*256\s*\)?\s*\+\s*[^\]]+\]\s*=\s*{index}\s*;"
        if not re.search(pattern, script):
            warnings.append(f"未在板子 {board} 的 g_boardRole 中找到角色 {index}")

    impl = spec.get("implementation", {})
    for symbol in impl.get("required_functions", []):
        pattern = rf"\b(?:void|bool|int|fixed|string|text)\s+{re.escape(symbol)}\s*\("
        if not re.search(pattern, script):
            errors.append(f"缺少函数：{symbol}")
    for symbol in impl.get("required_symbols", []):
        if symbol not in script:
            errors.append(f"缺少实现符号：{symbol}")

    resources = _resource_names(map_path)
    if resources:
        for key, value in spec.get("resources", {}).items():
            values = value if isinstance(value, list) else [value]
            for resource in values:
                if not resource:
                    continue
                if resource.replace("/", "\\").lower() not in resources:
                    warnings.append(f"地图内未找到资源：{resource}")

    if index >= 148:
        if f"int[{index + 1}]" not in script and f"string[{index + 1}]" not in script:
            errors.append(f"角色索引 {index} 已超过当前数组容量，需要同步扩展角色数组和扫描上限")

    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="botc.py role", description="BOTC 角色规格工具"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    new_parser = sub.add_parser("new", help="创建角色规格")
    new_parser.add_argument("--index", type=int, required=True)
    new_parser.add_argument("--name", required=True)
    new_parser.add_argument(
        "--team", choices=sorted(TEAM_CODES), default="townsfolk"
    )
    new_parser.add_argument(
        "--alignment", choices=sorted(ALIGN_CODES), default="good"
    )
    new_parser.add_argument("--out", type=Path)
    new_parser.add_argument("--script", type=Path, default=SCRIPT_PATH)
    new_parser.add_argument("--force", action="store_true")

    audit_parser = sub.add_parser("audit", help="对照源码审计角色规格")
    audit_parser.add_argument("spec", type=Path)
    audit_parser.add_argument("--script", type=Path, default=SCRIPT_PATH)
    audit_parser.add_argument("--map", type=Path, default=MAP_PATH)

    list_parser = sub.add_parser("list", help="列出脚本中已使用的角色索引")
    list_parser.add_argument("--script", type=Path, default=SCRIPT_PATH)

    args = parser.parse_args(argv)
    if args.command == "new":
        output = args.out or (ROLE_SPEC_DIR / f"role_{args.index:03d}.json")
        result = create_spec(
            output,
            args.index,
            args.name,
            args.team,
            args.alignment,
            args.force,
            args.script,
        )
        print(f"OK       : {result}")
        return 0

    if args.command == "list":
        return list_roles(args.script)

    errors, warnings = audit_spec(args.spec, args.script, args.map)
    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")
    if errors:
        return 1
    print(f"OK    {args.spec}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
