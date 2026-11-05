from __future__ import annotations

import json
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
sys.path.insert(0, str(TOOL_ROOT))

from build_map import (
    collect_local_assets,
    merge_asset_payloads,
    replace_custom_script,
    set_private_dependency,
    split_custom_script,
    split_trigger_custom_scripts,
    verify_packed_script,
    verify_split_map_script,
    verify_split_triggers,
)
from galaxy_check import (
    find_array_capacity_errors,
    find_forward_call_errors,
    find_literal_array_index_errors,
    scan_galaxy,
)
from private_dependency import render_impl
from role_design import validate_spec
from role_workflow import default_spec


class BuildMapTests(unittest.TestCase):
    def test_collects_local_assets_with_relative_paths(self) -> None:
        root = Path(__file__).resolve().parent / "fixtures" / "local-assets"
        assets = collect_local_assets(root)
        self.assertEqual(
            [name for name, _ in assets],
            ["example.bin", "nested/data.dat"],
        )

    def test_merge_rejects_duplicate_asset_members(self) -> None:
        with tempfile.TemporaryDirectory() as first:
            with tempfile.TemporaryDirectory() as second:
                Path(first, "same.bin").write_bytes(b"first")
                Path(second, "same.bin").write_bytes(b"second")
                with self.assertRaisesRegex(ValueError, "素材路径冲突"):
                    merge_asset_payloads(Path(first), Path(second))

    def test_replaces_only_custom_region(self) -> None:
        generated = "\r\n".join(
            [
                "// generated head",
                "// Custom Script: BOTC_Init()",
                "//--------------------------------------------------------------------------------------------------",
                "// old source",
                "//--------------------------------------------------------------------------------------------------",
                "// Custom Script Initialization",
                "//--------------------------------------------------------------------------------------------------",
                "void InitCustomScript () {",
                "}",
                "void InitMap () {",
                "}",
                "",
            ]
        )
        source = "// new source\r\nvoid BOTC_Init () {\r\n}\r\n"
        packed = replace_custom_script(generated, source)
        self.assertIn("// generated head", packed)
        self.assertIn("// new source", packed)
        self.assertNotIn("// old source", packed)
        self.assertIn("void InitCustomScript", packed)
        self.assertEqual(verify_packed_script(packed, source), [])

    def test_rejects_duplicate_markers(self) -> None:
        generated = "\n".join(
            [
                "// Custom Script: BOTC_Init()",
                "//---",
                "// custom",
                "//---",
                "// Custom Script Initialization",
                "// Custom Script Initialization",
            ]
        )
        with self.assertRaises(ValueError):
            replace_custom_script(generated, "void BOTC_Init () {}")

    def test_split_script_keeps_only_include_in_map_script(self) -> None:
        generated = "\r\n".join(
            [
                'include "TriggerLibs/NativeLib"',
                "// Custom Script: BOTC_Init()",
                "//--------------------------------------------------------------------------------------------------",
                "// old source",
                "//--------------------------------------------------------------------------------------------------",
                "// Custom Script Initialization",
                "//--------------------------------------------------------------------------------------------------",
                "void InitCustomScript () {",
                "}",
                "void InitMap () {",
                "}",
                "",
            ]
        )
        split = split_custom_script(generated)
        self.assertIn('include "BOTC_CustomLogic"', split)
        self.assertNotIn("// old source", split)
        self.assertEqual(verify_split_map_script(split), [])

    def test_split_script_replaces_trigger_custom_source(self) -> None:
        triggers = "\r\n".join(
            [
                '<?xml version="1.0" encoding="utf-8"?>',
                "<TriggerData>",
                '    <Element Type="CustomScript" Id="12345678">',
                "        <ScriptCode>",
                "            // old source",
                "            void BOTC_Init () {",
                "            }",
                "        </ScriptCode>",
                "    </Element>",
                "</TriggerData>",
                "",
            ]
        )
        split = split_trigger_custom_scripts(triggers)
        self.assertIn('include &quot;BOTC_CustomLogic&quot;', split)
        self.assertNotIn("// old source", split)
        self.assertEqual(verify_split_triggers(split), [])

    def test_private_dependency_replaces_old_private_values(self) -> None:
        original = (
            '<?xml version="1.0" encoding="utf-8"?>\r\n'
            "<DocInfo><Dependencies>"
            "<Value>bnet:Void</Value>"
            "<Value>file:Mods\\BOTC_Private_Core.SC2Mod</Value>"
            "</Dependencies></DocInfo>\r\n"
        )
        updated = set_private_dependency(
            original, "bnet:BOTC_Private_Core/1.0/123456789"
        )
        self.assertIn("bnet:Void", updated)
        self.assertNotIn("file:Mods\\BOTC_Private_Core.SC2Mod", updated)
        self.assertIn(
            "bnet:BOTC_Private_Core/1.0/123456789", updated
        )

    def test_private_dependency_renders_library_blacklist(self) -> None:
        source = render_impl(["Player#1234"])
        self.assertIn('include "LibBOTC_Private_h"', source)
        self.assertIn(
            'libBOTC_Private_gv_banHandle[0] = "Player#1234";',
            source,
        )
        self.assertIn("libBOTC_Private_gv_banHandleN = 1;", source)


class GalaxyCheckTests(unittest.TestCase):
    def test_balanced_scan(self) -> None:
        result = scan_galaxy('void A () { string s = "}"; } // {')
        self.assertEqual(result.brace_depth, 0)
        self.assertFalse(result.in_string)

    def test_unclosed_scan(self) -> None:
        result = scan_galaxy('void A () { string s = "unterminated')
        self.assertEqual(result.brace_depth, 1)
        self.assertTrue(result.in_string)

    def test_custom_role_visible_is_declared_before_sync_call(self) -> None:
        prototype = "bool   BOTC_CustomRoleVisible (int r);"
        definition = "bool BOTC_CustomRoleVisible (int r) {"
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        sync_start = source.index("void BOTC_CustomSyncBoardRoles () {")
        sync_end = source.index("void BOTC_GrantRoleOpen () {")
        sync_body = source[sync_start:sync_end]
        self.assertIn("BOTC_CustomRoleVisible(r)", sync_body)
        self.assertLess(source.index(prototype), sync_start)
        self.assertLess(sync_start, source.index(definition))

    def test_rejects_forward_call_without_prototype(self) -> None:
        source = "void First () {\n    Second();\n}\nvoid Second () {\n}\n"
        errors = find_forward_call_errors(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("Second", errors[0])

    def test_accepts_forward_call_with_prototype(self) -> None:
        source = (
            "void Second ();\n"
            "void First () {\n    Second();\n}\n"
            "void Second () {\n}\n"
        )
        self.assertEqual(find_forward_call_errors(source), [])

    def test_rejects_literal_array_index_past_capacity(self) -> None:
        source = (
            "int[2] g_values;\n"
            "void Test () {\n"
            "    g_values[2] = 1;\n"
            "}\n"
        )
        errors = find_literal_array_index_errors(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("g_values[2]", errors[0])
        self.assertIn("容量 2", errors[0])

    def test_ignores_array_indexes_in_comments_and_strings(self) -> None:
        source = (
            "int[2] g_values;\n"
            "// g_values[9]\n"
            'string g_text = "g_values[9]";\n'
            "void Test () {\n"
            "    g_values[1] = 1;\n"
            "}\n"
        )
        self.assertEqual(find_literal_array_index_errors(source), [])

    def test_rejects_mismatched_paired_array_capacities(self) -> None:
        source = (
            "int[3] g_jinxA;\n"
            "int[2] g_jinxB;\n"
            "string[3] g_jinxText;\n"
            "string[3] g_jinxText2;\n"
            "string[3] g_jinxText3;\n"
        )
        errors = find_array_capacity_errors(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("g_jinxA[3]", errors[0])
        self.assertIn("g_jinxB[2]", errors[0])

    def test_rejects_count_larger_than_array_capacity(self) -> None:
        source = (
            "int g_jinxCount;\n"
            "int[2] g_jinxA;\n"
            "void Test () {\n"
            "    g_jinxCount = 3;\n"
            "}\n"
        )
        errors = find_array_capacity_errors(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("g_jinxCount = 3", errors[0])
        self.assertIn("容量 2", errors[0])


class RoleSpecTests(unittest.TestCase):
    def test_default_spec_has_release_checks(self) -> None:
        spec = default_spec(148, "测试", "townsfolk", "good")
        self.assertEqual(spec["index"], 148)
        self.assertGreaterEqual(len(spec["acceptance"]), 5)
        self.assertIn("state_fields", spec["implementation"])

    def test_taotie_spec_and_runtime_entrypoints_match(self) -> None:
        spec = json.loads(
            (PROJECT_ROOT / "roles" / "role_154_taotie.json").read_text(
                encoding="utf-8"
            )
        )
        errors, _ = validate_spec(spec)
        self.assertEqual(errors, [])

        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            'g_roleName[154] = "饕餮"',
            "BOTC_BuildTaotie ();",
            "BOTC_TaotieSubmit (",
            "if (seen[team])",
            "BOTC_DemonStrike(p, 154, chosen[i], false);",
            'g_tokName[175] = "死亡（饕餮）"',
            "g_roleDeathTok[154] = 175",
            "BOTC_GoonTouch(p, chosen[i]);",
            "BOTC_WudTryTrigger(chosen[i], p)",
            "BOTC_TaotieToggle(g_who[p], q);",
            "if (demonPick == 154)",
            "if (g_rsPick[154])",
            "g_noAllOther[154] = 63;",
        ):
            self.assertIn(marker, source)

    def test_recent_role_dds_use_uncompressed_rgba_format(self) -> None:
        for index in range(148, 164):
            for prefix, size in (("role", 128), ("night", 85), ("tk", 48)):
                path = (
                    PROJECT_ROOT
                    / "assets"
                    / "game"
                    / f"botc_{prefix}{index}.dds"
                )
                raw = path.read_bytes()
                self.assertEqual(raw[:4], b"DDS ")
                self.assertEqual(struct.unpack_from("<I", raw, 84)[0], 0)
                self.assertEqual(struct.unpack_from("<I", raw, 88)[0], 32)
                self.assertEqual(len(raw), size * size * 4 + 128)

    def test_heshang_runtime_entrypoints_match_spec(self) -> None:
        spec = json.loads(
            (PROJECT_ROOT / "roles" / "role_161_heshang.json").read_text(
                encoding="utf-8"
            )
        )
        errors, _ = validate_spec(spec)
        self.assertEqual(errors, [])

        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "bool[14]    g_heshangSeatUsed;",
            "int[14]     g_heshangSeatNight;",
            "BOTC_HeshangTryBlockSelection(p, r)",
            "BOTC_HeshangTryBlockSeat(src, srcRole, q)",
            "BOTC_HeshangTryBlockSeat(d, 70, g_nodA)",
            "BOTC_HeshangDawnClear();",
            "BOTC_NoDashiiSync();",
            "BOTC_HeshangAdjacentAlive(i, q)",
            "g_heshangSeatUsed[h] = true;",
            "if (!BOTC_AbilityWorks(src, role)) {",
            "return false;                      // 刺客的刺杀明确不能被保护。",
            "g_tokRole[197] = 161;",
        ):
            self.assertIn(marker, source)

    def test_gudiao_runtime_entrypoints_match_spec(self) -> None:
        spec = json.loads(
            (PROJECT_ROOT / "roles" / "role_162_gudiao.json").read_text(
                encoding="utf-8"
            )
        )
        errors, _ = validate_spec(spec)
        self.assertEqual(errors, [])

        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "int[14]     g_gdPrev;",
            "int[14]     g_gdBy;",
            "g_roleName[162]",
            "g_tokName[198]",
            "g_tokName[199]",
            "g_tokName[200]",
            "int[14]     g_gdFlightBy;",
            "g_noAllFirst[162] = 26;",
            "g_noAllOther[162] = 1;",
            "BOTC_GudiaoNextTownsfolk(p, from, dir)",
            "from = BOTC_GudiaoFlightSeat(p);",
            "g_gdFlightBy[target] = p;",
            "盘璇已移动，但蛊毒被和尚阻止",
            "if (BOTC_SeatTeam(q) != 0) {",
            "if (BOTC_SeatTrueRole(q) == 136) {",
            "BOTC_HeshangTryBlockSeat(p, 162, target)",
            "BOTC_GudiaoApply(p, change);",
            "BOTC_GudiaoDuskClear();",
            "BOTC_GudiaoSourceGone(q);",
            "if (r == 162) {",
            "if (g_miRole == 813)",
            "RandomInt(1, 100) <= g_regDisguiseChance",
        ):
            self.assertIn(marker, source)

    def test_warden_runtime_entrypoints_match_spec(self) -> None:
        spec = json.loads(
            (PROJECT_ROOT / "roles" / "role_163_warden.json").read_text(
                encoding="utf-8"
            )
        )
        errors, _ = validate_spec(spec)
        self.assertEqual(errors, [])

        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "int[64]     g_wardenPick;",
            "int[14]     g_wardenBy;",
            "g_roleName[163]",
            "g_roleTargets[163] = 3;",
            "g_noAllFirst[163] = 26;",
            "g_noAllOther[163] = 124;",
            "g_tokName[201]",
            "g_tokName[202]",
            "if (r == 163) {",
            "BOTC_WardenResolve(p, w1, w2, w3)",
            "BOTC_WardenOpenChoice(p)",
            "BOTC_WardenKillChoice(n + 1)",
            "BOTC_WardenExecDeath(q)",
            "BOTC_WardenClear(q, true)",
            'return "选择至多三名玩家";',
        ):
            self.assertIn(marker, source)
        self.assertNotIn("典狱长至少要选择一名玩家", source)
        self.assertNotIn("if (!g_wardenAskBy", source)

    def test_mastermind_overtime_win_is_not_overridden(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn(
            "g_lastDeadSeat = 0;       // 这次恶魔死亡已经转化为主谋加时",
            source,
        )
        self.assertIn(
            "if (!g_manualWin && !g_mmExtra && side != 0",
            source,
        )

    def test_half_immortal_redirect_uses_dedicated_prompt(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("g_miRole = 815;", source)
        self.assertIn(
            "BOTC_HalfImmortalApply(seat, g_halfSlot, n + 1)",
            source,
        )
        half_start = source.index("bool BOTC_HalfImmortalMaybePrompt (int p) {")
        half_end = source.index("void BOTC_HalfImmortalApply (", half_start)
        half_prompt = source[half_start:half_end]
        self.assertNotIn("BOTC_SkillRender(1);", half_prompt)
        self.assertNotIn("g_skillPicking[1] = true;", half_prompt)
        self.assertNotIn("if (g_halfPick && p == 1)", source)

    def test_summoner_only_offers_demons_from_current_script(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        can_use_start = source.index("bool BOTC_SummonerCanUseRole (int role) {")
        can_use_end = source.index(
            "void BOTC_SummonerGridCatalog (int p) {", can_use_start
        )
        can_use = source[can_use_start:can_use_end]
        self.assertIn("if (!BOTC_BoardHasRole(role)) {", can_use)

        catalog_start = can_use_end
        catalog_end = source.index("int BOTC_SummonerSeat () {", catalog_start)
        catalog = source[catalog_start:catalog_end]
        self.assertIn("!BOTC_BoardHasRole(r)", catalog)

    def test_limited_ability_prompts_include_selection_type(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "string BOTC_LimitedAskText (int p, int r) {",
            'if (r == 29) { pick = "选择一个角色"; }',
            'if (r == 30) { pick = "选择一名已死亡玩家"; }',
            'if (r == 55) { pick = "选择除你以外的两名玩家"; }',
            'if (r == 56) { pick = "选择一个善良角色"; }',
            'if (r == 77) { pick = "选择一名存活玩家"; }',
            'if (r == 78) { pick = "选择恶魔或爪牙角色"; }',
            'if (r == 124) { pick = "选择一个镇民角色"; }',
            'return "是否发动能力（" + pick + "）";',
            "BOTC_LimitedAskText(p, r)",
            "BOTC_LimitedAskText(p, 46)",
            "是否发动能力（选择自己是否醉酒）",
        ):
            self.assertIn(marker, source)

    def test_wudao_triggers_for_selection_and_passive_effects(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "bool BOTC_WudTryTrigger (int target, int source) {",
            "void BOTC_WudCheckSelection (int source) {",
            "BOTC_WudCheckSelection(p);",
            "BOTC_WudTryTrigger(q, src);",
            "BOTC_WudTryTrigger(t, p);",
            "BOTC_WudTryTrigger(g_nodA, d);",
            "BOTC_WudTryTrigger(g_nodB, d);",
            "BOTC_WudTryTrigger(q, d);",
            "BOTC_WudTryTrigger(who, m);",
            "BOTC_WudTryTrigger(i, demon);",
            "BOTC_WudTryTrigger(i, q);",
            "BOTC_WudTryTrigger(q, p);",
            "BOTC_WudTryTrigger(n1, k);",
            "BOTC_WudTryTrigger(pick, who);",
            "原效果仍会继续结算",
        ):
            self.assertIn(marker, source)

    def test_painted_skin_revives_visible_death_and_restores_zombuul_life(self) -> None:
        spec = json.loads(
            (PROJECT_ROOT / "roles" / "role_155_paintedskin.json").read_text(
                encoding="utf-8"
            )
        )
        errors, _ = validate_spec(spec)
        self.assertEqual(errors, [])
        self.assertEqual(spec["other_night_order"], 24)

        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "wasZombuulFake = g_zombFake[q];",
            "!BOTC_PublicDead(q) && !BOTC_SeatDead(q)",
            "带有选择标记且广场显示为死亡",
            "BOTC_LivingCorpseRevive(q);",
            "wasLivingCorpse = g_liveCorpse[q];",
            "wasVisibleDead = (BOTC_PublicDead(q) || g_zombFake[q]);",
            "g_noAllOther[155] = 24;",
            "if (wasLivingCorpse || wasVisibleDead) {",
            "首次死亡能力与画皮攻击互相抵消",
        ):
            self.assertIn(marker, source)
        hook_start = source.index("int BOTC_SkinDeathHook (int q) {")
        hook_end = source.index("void BOTC_SkinChoose (int p, int q) {", hook_start)
        hook = source[hook_start:hook_end]
        self.assertIn("BOTC_LivingCorpseRevive(q);", hook)
        self.assertIn("BOTC_RestoreOneShot(q);", hook)

    def test_recent_minion_and_demon_names_are_colored_in_chat(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            'BOTC_PutWord(t, "饕餮", Color(255, 0, 0))',
            'BOTC_PutWord(t, "蛊雕", Color(255, 69, 0))',
            'BOTC_PutWord(t, "典狱长", Color(255, 0, 0))',
        ):
            self.assertIn(marker, source)


class BoardPaginationTests(unittest.TestCase):
    def test_cheng_shuang_cheng_dui_board_and_page_two(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("if (g_boardPage == 2)", source)
        self.assertIn("g_boardPage = 1;", source)
        self.assertIn("g_boardTabOfficial = BOTC_NewButton", source)
        self.assertIn("g_boardTabMore = BOTC_NewButton", source)
        self.assertIn('return "成双成对";', source)
        self.assertIn('return "botc_board_cscd.dds";', source)
        self.assertIn("g_boardRoleN[14] = 25;", source)

        roles = {
            int(slot): int(role)
            for slot, role in re.findall(
                r"g_boardRole\[\(14 \* 256\) \+ (\d+)\]\s*=\s*(\d+);",
                source,
            )
        }
        self.assertEqual(
            [roles[index] for index in range(25)],
            [
                76, 22, 115, 72, 151, 24, 73, 25, 7, 28, 54, 30, 77,
                38, 152, 61, 82,
                65, 153, 19, 93,
                154, 45, 134, 70,
            ],
        )

        cover = PROJECT_ROOT / "assets" / "game" / "botc_board_cscd.dds"
        raw = cover.read_bytes()
        self.assertEqual(raw[:4], b"DDS ")
        self.assertEqual(struct.unpack_from("<I", raw, 84)[0], 0)
        self.assertEqual(struct.unpack_from("<I", raw, 88)[0], 32)
        self.assertEqual(len(raw), 256 * 256 * 4 + 128)


class LogViewerTests(unittest.TestCase):
    def test_player_picker_rebuilds_for_current_seats(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )

        start = source.index("void BOTC_LogPickStart (int p) {")
        end = source.index("void BOTC_LogPickRender (int p) {", start)
        picker_start = source[start:end]

        self.assertIn("BOTC_LogPickRender(p);", picker_start)
        self.assertIn(
            "DialogControlSelectItem(g_logPickList, PlayerGroupSingle(p), 0);",
            picker_start,
        )
        self.assertNotIn("g_logPickFilled", source)


class SkillPanelRoutingTests(unittest.TestCase):
    def test_skill_clicks_use_control_and_current_player_mapping(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("int BOTC_SkillControlOwner (int c)", source)
        self.assertIn("int BOTC_SkillPickerForPlayer (int p)", source)
        self.assertIn("if (BOTC_SkillClickControl(p, c))", source)
        self.assertIn("q = BOTC_SkillPickerForPlayer(p);", source)
        self.assertIn("!g_skillPicking[p] && !g_limitedAsk[p]", source)


class LegionRecognitionTests(unittest.TestCase):
    def test_legion_receives_all_good_seats(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        start = source.index("bool BOTC_LegionRecognize () {")
        end = source.index("\n}\n", start) + 3
        function = source[start:end]

        self.assertIn("BOTC_SeatAlign(q) != 0", function)
        self.assertIn("BOTC_PmInfo(g_who[q], msg);", function)
        self.assertIn("BOTC_SeatTrueRole(q) != 94", function)
        self.assertIn(", 19);", function)
        self.assertIn("g_lgPend = true;", function)
        self.assertIn("BOTC_LegionRecognize();", source)
        self.assertNotIn("BOTC_LegionMarkFor", function)


class HadiRevivalTests(unittest.TestCase):
    def test_hadi_revival_waits_for_dawn(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        start = source.index("void BOTC_HdResolve () {")
        end = source.index("void BOTC_HdKill (int t) {", start)
        resolve = source[start:end]

        self.assertNotIn("BOTC_DeathToggle(t, 0, 0)", resolve)
        self.assertIn("保留复活标记，天亮统一公布", resolve)
        self.assertIn(
            "+ 113]) {\n            continue;\n        }\n        if (!BOTC_PublicDead(q))",
            source,
        )
        self.assertIn(
            "g_tokOn[(((g_teller * 14) + q) * 256) + 113] = false;",
            source,
        )


class PendingReviveTests(unittest.TestCase):
    def test_pending_revive_is_alive_at_night_but_waits_for_dawn(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        start = source.index("bool BOTC_PendingRevive (int q) {")
        end = source.index("bool BOTC_SeatDead (int q) {", start)
        pending = source[start:end]

        for token in ("+ 42]", "+ 43]", "+ 113]"):
            self.assertIn(token, pending)
        self.assertIn("if (BOTC_PendingRevive(q))", source)
        self.assertIn("if (g_zombFake[q] || BOTC_SeatDead(q))", source)
        self.assertIn("if (!BOTC_PublicDead(q))", source)
        self.assertIn(
            "新的死亡覆盖这次复活",
            source,
        )


class GameStartLogTests(unittest.TestCase):
    def test_logs_clear_after_countdown_and_on_cancel(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )

        start = source.index("void BOTC_GameStartGo () {")
        end = source.index("void BOTC_ClearAllLogs () {", start)
        game_start = source[start:end]
        self.assertLess(
            game_start.index("BOTC_ClearAllLogs();"),
            game_start.index('BOTC_PeriodRecord("---- 第1夜（游戏正式开始）----");'),
        )

        cancel_start = source.index("void BOTC_GameStartCancel () {")
        cancel_end = source.index("\n}\n", cancel_start)
        cancel = source[cancel_start:cancel_end]
        self.assertEqual(cancel.count("BOTC_ClearAllLogs();"), 2)


class BluffPanelRegressionTests(unittest.TestCase):
    def test_manual_bottom_right_bluff_panels_are_restored(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )

        self.assertGreaterEqual(
            source.count(
                "DialogControlSetVisible(g_bluffSeat[i], PlayerGroupSingle(g_teller), true);"
            ),
            2,
        )
        self.assertGreaterEqual(
            source.count(
                "DialogControlSetVisible(g_lbluffSeat[i], PlayerGroupSingle(g_teller), true);"
            ),
            2,
        )
        self.assertIn(
            "DialogControlSetVisible(g_specBtn, PlayerGroupSingle(g_teller), g_started || g_isNight);",
            source,
        )
        self.assertNotIn("g_specBluffBtn = BOTC_NewButton", source)
        self.assertNotIn("if (c == g_specBluffBtn)", source)
        self.assertNotIn("BOTC_BluffAskStart();", source)
        self.assertIn(
            "DialogSetVisible(g_bluffDlg, PlayerGroupSingle(g_teller), true);",
            source,
        )


if __name__ == "__main__":
    unittest.main()
