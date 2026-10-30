from __future__ import annotations

import argparse
import json
from pathlib import Path

from botc_config import MAP_PATH, SCRIPT_PATH, require_file
from role_workflow import ACTION_CODES, ALIGN_CODES, TEAM_CODES
from stormlib_mpq import MPQArchive


TIMINGS = {
    "setup",
    "passive",
    "first_night",
    "every_night",
    "other_nights",
    "day",
    "on_death",
    "on_execution",
    "on_nomination",
    "on_vote",
    "on_role_change",
}
FREQUENCIES = {
    "always",
    "once_per_game",
    "once_per_day",
    "first_time",
    "conditional",
}
TARGET_KINDS = {
    "none",
    "players",
    "role",
    "player_and_role",
    "alignment",
    "team",
}
EFFECT_KINDS = {
    "send_information",
    "set_token",
    "remove_token",
    "kill",
    "protect",
    "change_role",
    "modify_registration",
    "modify_vote",
    "win_condition",
    "custom",
}
DURATIONS = {
    "instant",
    "until_dawn",
    "until_dusk",
    "current_night",
    "game",
    "permanent",
}
NIGHT_SECTIONS = {
    "rules",         # 卡扎力、科学怪人等规则 / 设置系
    "role_change",   # 麻脸巫婆、哲学家、舞蛇人等身份 / 能力改变系
    "interference",  # 投毒、保护、限制、强制选择等状态干预系
    "kill",          # 恶魔及直接造成死亡的刀人位
    "information",   # 占卜师、共情者、守鸦人等主要信息位
    "utility",       # 不属于以上类别的剩余功能位
}
NIGHT_RELATIONS = {"before", "after", "near"}
TOKEN_VISIBILITIES = {"storyteller", "owner", "public", "hidden"}


def _issue(errors: list[str], warnings: list[str], message: str, severe: bool = True) -> None:
    (errors if severe else warnings).append(message)


def validate_spec(spec: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    required = (
        "schema_version",
        "index",
        "name",
        "team",
        "alignment",
        "text",
        "lore",
        "timing",
        "effects",
        "artwork",
        "night_order",
        "tokens",
        "jinxes",
    )
    for key in required:
        if key not in spec:
            errors.append(f"缺少字段：{key}")
    if errors:
        return errors, warnings

    if spec["schema_version"] != 2:
        errors.append("schema_version 必须为 2")
    if not isinstance(spec["index"], int) or spec["index"] < 0:
        errors.append("index 必须是非负整数")
    if not spec["name"]:
        errors.append("name 不能为空")
    if spec["team"] not in TEAM_CODES:
        errors.append(f"未知阵营：{spec['team']}")
    if spec["alignment"] not in ALIGN_CODES:
        errors.append(f"未知阵营倾向：{spec['alignment']}")
    expected_alignment = (
        "evil" if spec["team"] in {"minion", "demon"} else "good"
    )
    if spec["alignment"] != expected_alignment:
        errors.append(
            f"{spec['team']} 应为 {expected_alignment}，实际为 {spec['alignment']}"
        )
    if spec["timing"] not in TIMINGS:
        errors.append(f"未知时机：{spec['timing']}")
    if spec.get("frequency", "always") not in FREQUENCIES:
        errors.append(f"未知频率：{spec.get('frequency')}")
    if not str(spec["text"]).strip():
        errors.append("text 不能为空")
    if not str(spec["lore"]).strip():
        errors.append("lore 不能为空")
    if "可能" in spec["text"]:
        warnings.append("角色文本包含“可能”，需要写清触发条件和说书人判断边界")
    if "随机" in spec["text"] and not spec.get("randomness", {}).get("declared"):
        warnings.append("角色文本包含“随机”，但 randomness.declared 未声明")

    target = spec.get("target", {"kind": "none"})
    if target.get("kind", "none") not in TARGET_KINDS:
        errors.append(f"未知目标类型：{target.get('kind')}")
    count = target.get("count", 0)
    if not isinstance(count, int) or count < 0 or count > 3:
        errors.append("target.count 必须在 0..3")
    if target.get("kind") in {"players", "player_and_role"} and count < 1:
        errors.append("玩家目标必须至少有 1 个目标")
    if target.get("kind") == "role" and count < 1:
        warnings.append("角色目标建议明确 count")
    if target.get("living") and target.get("kind") not in {"players", "player_and_role"}:
        warnings.append("living 只对玩家目标有直接意义")

    effects = spec["effects"]
    if not isinstance(effects, list) or not effects:
        errors.append("effects 必须是非空数组")
        effects = []
    for position, effect in enumerate(effects, start=1):
        kind = effect.get("kind")
        if kind not in EFFECT_KINDS:
            errors.append(f"effects[{position}] 未知效果：{kind}")
            continue
        if kind == "send_information" and not effect.get("text"):
            errors.append(f"effects[{position}] send_information 缺少 text")
        if kind in {"set_token", "remove_token"}:
            if not effect.get("token"):
                errors.append(f"effects[{position}] {kind} 缺少 token")
            if kind == "set_token" and effect.get("duration") not in DURATIONS:
                errors.append(f"effects[{position}] set_token 缺少合法 duration")
        if kind == "change_role" and not effect.get("role"):
            errors.append(f"effects[{position}] change_role 缺少 role")
        if kind in {"kill", "protect", "modify_vote", "modify_registration", "win_condition"}:
            if not effect.get("mode"):
                errors.append(f"effects[{position}] {kind} 缺少 mode")
        if kind == "custom" and not effect.get("id"):
            errors.append(f"effects[{position}] custom 缺少 id")

    if any(effect.get("kind") == "win_condition" for effect in effects):
        warnings.append("胜利条件效果必须经过人工审核，并补相克与加时规则")
    if any(effect.get("kind") == "custom" for effect in effects):
        warnings.append("存在 custom 效果，不能自动视为完成")

    artwork = spec.get("artwork", {})
    for key in ("role_icon", "night_icon"):
        if not artwork.get(key):
            errors.append(f"artwork.{key} 不能为空")
    if not artwork.get("source") and not artwork.get("prompt"):
        errors.append("artwork 必须提供 source 或 prompt")

    tokens = spec.get("tokens", [])
    if not isinstance(tokens, list):
        errors.append("tokens 必须是数组")
        tokens = []
    token_ids = set()
    for position, token in enumerate(tokens, start=1):
        token_id = str(token.get("id", "")).strip()
        if not token_id:
            errors.append(f"tokens[{position}] 缺少 id")
            continue
        if token_id in token_ids:
            errors.append(f"token id 重复：{token_id}")
        token_ids.add(token_id)
        for key in ("name", "short", "effect", "place", "remove", "icon"):
            if not str(token.get(key, "")).strip():
                errors.append(f"token {token_id} 缺少 {key}")
        if token.get("visibility") not in TOKEN_VISIBILITIES:
            errors.append(
                f"token {token_id} visibility 必须是 {sorted(TOKEN_VISIBILITIES)}"
            )
    for position, effect in enumerate(effects, start=1):
        if effect.get("kind") in {"set_token", "remove_token"}:
            token_id = effect.get("token")
            if token_id and token_id not in token_ids:
                errors.append(
                    f"effects[{position}] 引用了未登记的 token：{token_id}"
                )

    jinxes = spec.get("jinxes", [])
    if not isinstance(jinxes, list):
        errors.append("jinxes 必须是数组")
        jinxes = []
    for position, jinx in enumerate(jinxes, start=1):
        if not jinx.get("role"):
            errors.append(f"jinxes[{position}] 缺少 role")
        if not str(jinx.get("text", "")).strip():
            errors.append(f"jinxes[{position}] 缺少 text")

    night_order = spec.get("night_order", {})
    section = night_order.get("section")
    if section not in NIGHT_SECTIONS:
        errors.append(
            f"night_order.section 必须是 {sorted(NIGHT_SECTIONS)}"
        )
    anchor_role = night_order.get("anchor_role")
    relation = night_order.get("relation")
    if bool(anchor_role) != bool(relation):
        errors.append("night_order.anchor_role 与 relation 必须同时填写")
    if relation is not None and relation not in NIGHT_RELATIONS:
        errors.append(
            f"night_order.relation 必须是 {sorted(NIGHT_RELATIONS)}"
        )
    for key in ("first", "other"):
        value = night_order.get(key)
        if value is not None and (not isinstance(value, int) or value <= 0):
            errors.append(f"night_order.{key} 必须是正整数或 null")
    acts_at_night = spec["timing"] in {
        "first_night",
        "every_night",
        "other_nights",
    }
    if (
        acts_at_night
        and night_order.get("first") is None
        and night_order.get("other") is None
        and not anchor_role
    ):
        warnings.append(
            "主动夜间角色没有夜序行号或 anchor_role；"
            "需按夜间顺序表补充插入位置"
        )

    test_cases = spec.get("tests", [])
    if len(test_cases) < 3:
        warnings.append("建议至少提供正常、失效、边界三类规则测试")
    return errors, warnings


def _target_summary(target: dict) -> str:
    kind = target.get("kind", "none")
    count = int(target.get("count", 0))
    if kind == "none":
        return "无目标"
    if kind == "players":
        result = f"{count} 名玩家"
        if target.get("living"):
            result = f"{count} 名存活玩家"
        if not target.get("allow_self", False):
            result += "，不能选择自己"
        if not target.get("allow_repeat", True):
            result += "，不能连续重复"
        return result
    if kind == "role":
        return f"{count} 个角色"
    if kind == "player_and_role":
        return f"{count} 名玩家和 1 个角色"
    if kind == "alignment":
        return "一个阵营"
    if kind == "team":
        return "一个角色类型"
    return kind


def _effect_summary(effect: dict) -> str:
    kind = effect["kind"]
    if kind == "send_information":
        return "发送信息：" + str(effect.get("text", ""))
    if kind == "set_token":
        return f"放置 token {effect.get('token')}，持续 {effect.get('duration')}"
    if kind == "remove_token":
        return f"移除 token {effect.get('token')}"
    if kind == "kill":
        return f"造成死亡（{effect.get('mode')}）"
    if kind == "protect":
        return f"施加保护（{effect.get('mode')}）"
    if kind == "change_role":
        return f"转变为角色 {effect.get('role')}"
    if kind == "modify_registration":
        return f"登记修改（{effect.get('mode')}）"
    if kind == "modify_vote":
        return f"投票修改（{effect.get('mode')}）"
    if kind == "win_condition":
        return f"新增胜利条件（{effect.get('mode')}）"
    if kind == "custom":
        return f"自定义效果 {effect.get('id')}：{effect.get('notes', '')}"
    return kind


def compile_plan(spec: dict) -> str:
    errors, warnings = validate_spec(spec)
    if errors:
        raise ValueError("角色 DSL 校验失败：\n" + "\n".join(errors))

    index = spec["index"]
    target = spec.get("target", {"kind": "none"})
    action = spec.get("action", "passive")
    night_order = spec.get("night_order", {})
    role_act = ACTION_CODES.get(action)
    lines = [
        f"# 角色设计计划：{spec['name']}",
        "",
        f"- 索引：{index}",
        f"- 阵营：{spec['team']} / {spec['alignment']}",
        f"- 时机：{spec['timing']}",
        f"- 频率：{spec.get('frequency', 'always')}",
        f"- 目标：{_target_summary(target)}",
        f"- 夜序分类：{night_order.get('section', '未填写')}",
        f"- 规则文本：{spec['text']}",
        f"- 角色介绍：{spec['lore']}",
        "",
        "## 效果",
    ]
    lines.extend(f"- {_effect_summary(effect)}" for effect in spec["effects"])
    lines.extend(["", "## Token"])
    if spec["tokens"]:
        for token in spec["tokens"]:
            lines.append(
                f"- {token['name']}（{token['short']} / {token['id']}）："
                f"{token['effect']}；图标：{token['icon']}；"
                f"放置：{token['place']}；移除：{token['remove']}；"
                f"可见性：{token['visibility']}"
            )
    else:
        lines.append("- 无 token")
    lines.extend(["", "## 相克规则"])
    if spec["jinxes"]:
        lines.extend(
            f"- {jinx['role']}：{jinx['text']}" for jinx in spec["jinxes"]
        )
    else:
        lines.append("- 当前未声明特殊相克；相克梳理仍需逐角色人工复核")
    lines.extend(["", "## 建议角色数据"])
    lines.append(
        f'g_roleName[{index}] = "{spec["name"]}"; '
        f"g_roleTeam[{index}] = {TEAM_CODES[spec['team']]}; "
        f"g_roleAlign[{index}] = {ALIGN_CODES[spec['alignment']]};"
    )
    if role_act is not None:
        lines.append(f"g_roleAct[{index}] = {role_act};")
    lines.append(f"g_roleTargets[{index}] = {int(target.get('count', 0))};")
    if night_order.get("first") is not None:
        lines.append(f"g_noAllFirst[{index}] = {night_order['first']};")
    if night_order.get("other") is not None:
        lines.append(f"g_noAllOther[{index}] = {night_order['other']};")
    if night_order.get("anchor_role"):
        lines.append(
            f"// TODO: 按官方夜间顺序表，将角色插入 "
            f"{night_order['anchor_role']} 的 {night_order['relation']} 位置"
        )

    lines.extend(["", "## 必须接入的位置"])
    checks = ["BOTC_HasAbility", "BOTC_AbilityWorks", "BOTC_AbilitySeat"]
    if target.get("kind") in {"players", "player_and_role"}:
        checks.extend(["BOTC_SkillOpen", "BOTC_SkillConfirm", "BOTC_SkillPickSeat"])
    if target.get("kind") in {"role", "player_and_role"}:
        checks.extend(["BOTC_PickChoose", "g_pickSlotRole"])
    if target.get("living"):
        checks.extend(["BOTC_TargetIsLiving", "目标死亡时拒绝确认"])
    if spec["timing"] in {"first_night", "every_night", "other_nights"}:
        checks.extend(["BOTC_CanWakeAt", "BOTC_NightOrder"])
    if spec["timing"] in {"on_death", "on_execution", "on_nomination", "on_vote"}:
        checks.extend(["对应事件入口", "同一次事件只触发一次"])
    if spec.get("frequency") in {"once_per_game", "once_per_day"}:
        checks.extend(["状态字段随换位迁移", "新局重置次数"])
    if any(effect["kind"] == "set_token" for effect in spec["effects"]):
        checks.extend(["token 放置", "token 移除", "来源离场清理", "第二局清理"])
    if any(effect["kind"] == "change_role" for effect in spec["effects"]):
        checks.extend(["BOTC_SetSeatRole", "BOTC_ChangeRoleMsg", "身份转变后的能力重算"])
    if any(effect["kind"] == "kill" for effect in spec["effects"]):
        checks.extend(["统一死亡通道", "死亡原因 token", "保护与免死拦截"])
    if any(effect["kind"] == "win_condition" for effect in spec["effects"]):
        checks.extend(["BOTC_CheckWin", "平局与优先胜利顺序", "换说书人后真值"])
    checks.extend(["角色能力文本", "详情页文本", "身份图", "夜序图", "token 图"])
    lines.extend(f"- [ ] {item}" for item in dict.fromkeys(checks))

    lines.extend(["", "## 规则测试"])
    tests = spec.get("tests", [])
    if tests:
        for case in tests:
            lines.append(f"- [ ] {case}")
    else:
        lines.extend(
            [
                "- [ ] 健康来源的正常路径",
                "- [ ] 中毒 / 醉酒时面板和结算路径",
                "- [ ] 取消、无效目标和死亡目标",
                "- [ ] 换座位、换说书人和第二局",
            ]
        )
    if warnings:
        lines.extend(["", "## 警告"])
        lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines) + "\n"


def build_ai_prompt(sentence: str) -> str:
    example = {
        "schema_version": 2,
        "index": 148,
        "name": "角色名",
        "team": "townsfolk",
        "alignment": "good",
        "text": "每个夜晚，你要选择一名存活玩家：你得知一条信息。",
        "lore": "角色背景与玩法定位。",
        "timing": "every_night",
        "frequency": "always",
        "action": "every_night",
        "target": {
            "kind": "players",
            "count": 1,
            "living": True,
            "allow_self": False,
            "allow_repeat": True,
        },
        "artwork": {
            "source": "原图路径或 AI 参考图路径",
            "role_icon": "botc_role148.dds",
            "night_icon": "botc_night148.dds",
            "token_icons": [],
        },
        "night_order": {
            "section": "information",
            "anchor_role": "共情者",
            "relation": "near",
            "first": None,
            "other": None,
        },
        "tokens": [],
        "jinxes": [],
        "effects": [
            {
                "kind": "send_information",
                "text": "你得知一条信息。",
            }
        ],
    }
    return (
        "你是《血染钟楼》角色规则设计器。只输出一个 JSON 对象，不要输出 Markdown。\n"
        "你必须严格遵守以下约束：\n"
        "1. 不能改变玩家原句中的胜负、时机、目标数量、目标存活条件、持续时间和触发条件。\n"
        "2. 原句没有明确的内容必须保留为待确认，不得自行补充有利效果。\n"
        "3. 只使用给定枚举。无法表达的效果使用 kind=custom 并写清 notes。\n"
        "4. 不生成 Galaxy 代码，只生成结构化角色规格。\n"
        "5. 输出必须包含 schema_version=2、index、name、team、alignment、text、lore、"
        "timing、effects、artwork、night_order、tokens、jinxes。\n"
        "6. team 可选 townsfolk/outsider/minion/demon/legend/journey；"
        "timing 可选 setup/passive/first_night/every_night/other_nights/day/"
        "on_death/on_execution/on_nomination/on_vote/on_role_change。\n"
        "7. effect.kind 可选 send_information/set_token/remove_token/kill/protect/"
        "change_role/modify_registration/modify_vote/win_condition/custom。\n\n"
        "8. night_order.section 只可选 rules/role_change/interference/kill/"
        "information/utility。粗粒度阶段为 rules → role_change/interference → "
        "kill → information/utility；interference 包含投毒、保护、限制、"
        "强制选择等状态干预。官方表内 role_change 与 interference 会交错，"
        "不能为了分类整齐而重排现有角色。按实际效果分类，不按阵营分类；"
        "爪牙只有直接造成死亡时才归入 kill。\n"
        "9. 用户没有指定具体夜序行号时，first/other 保持 null，并用 "
        "anchor_role 与 relation 表示靠近哪个现有角色插入；relation 只可选 "
        "before/after/near。用户明确给出顺序时才填写具体正整数行号。\n"
        "10. 每个 token 必须包含 id/name/short/effect/place/remove/icon/visibility；"
        "visibility 可选 storyteller/owner/public/hidden。\n"
        "11. 每条相克必须包含 role 和 text；没有相克时输出空数组。\n\n"
        f"玩家的一句话描述：{sentence}\n\n"
        "输出结构示例：\n"
        + json.dumps(example, ensure_ascii=False, indent=2)
        + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="botc.py design", description="角色 DSL 设计工具"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="校验角色 DSL")
    validate_parser.add_argument("spec", type=Path)

    compile_parser = sub.add_parser("compile", help="生成角色接入计划")
    compile_parser.add_argument("spec", type=Path)
    compile_parser.add_argument("--out", type=Path)

    prompt_parser = sub.add_parser("prompt", help="生成一句话转 DSL 的 AI 提示词")
    prompt_parser.add_argument("sentence")

    args = parser.parse_args(argv)
    if args.command == "prompt":
        print(build_ai_prompt(args.sentence))
        return 0

    spec_path = require_file(args.spec, "角色 DSL")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    errors, warnings = validate_spec(spec)
    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"ERROR {error}")
    if errors:
        return 1
    if args.command == "validate":
        print(f"OK    {spec_path}")
        return 0

    plan = compile_plan(spec)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(plan, encoding="utf-8")
        print(f"OK    {args.out}")
    else:
        print(plan, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
