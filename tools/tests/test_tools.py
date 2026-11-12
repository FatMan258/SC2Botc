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
    find_reversed_array_declaration_errors,
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

    def test_rejects_array_dimension_after_name(self) -> None:
        source = (
            "bool[14] g_ok;\n"
            "void Test () {\n"
            "    int[2] g_local;\n"
            "}\n"
            "bool g_bad[14];\n"
        )
        errors = find_reversed_array_declaration_errors(source)
        self.assertEqual(len(errors), 1)
        self.assertIn("g_bad", errors[0])
        self.assertIn("bool[14] g_bad;", errors[0])

    def test_ignores_array_index_statements(self) -> None:
        source = (
            "int[2] g_values;\n"
            "int Test () {\n"
            "    // int g_bad[2];\n"
            '    string s = "int g_bad[2];";\n'
            "    g_values[1] = 1;\n"
            "    return g_values[1];\n"
            "}\n"
        )
        self.assertEqual(find_reversed_array_declaration_errors(source), [])

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
            'g_tokName[175] = "死亡"',
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
            "g_noAllFirst[163] = 48;",
            "g_noAllOther[163] = 69;",
            "g_tokName[201]",
            "g_tokName[202]",
            "g_tokName[204]",
            "g_deathN = 24;",
            "g_deathTok[22] = 204;",
            "g_roleDeathTok[163] = 204;",
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
        choice_start = source.index("void BOTC_WardenKillChoice (int q) {")
        choice_end = source.index("\nvoid ", choice_start + 1)
        choice = source[choice_start:choice_end]
        self.assertNotIn("g_wardenPick", choice)
        self.assertIn("BOTC_WardenKillChoice(q);", source)
        self.assertIn(
            "BOTC_MiSeatFieldsReset();\n    g_miSeat = p;\n    g_miRole = 814;",
            source,
        )

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

    def test_po_decline_bypasses_demon_target_lock(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        start = source.index("bool BOTC_DemonTargetLocked (int p) {")
        end = source.index("\nvoid ", start)
        body = source[start:end]
        guard = body.index("if (g_poAsk[p] || g_limitedAsk[p]) {")
        role = body.index("r = BOTC_ActRoleOf(p);")
        self.assertLess(guard, role)

        cancel_start = source.index("void BOTC_SkillCancel (int p) {")
        cancel_end = source.index("\nvoid ", cancel_start)
        cancel = source[cancel_start:cancel_end]
        self.assertIn("BOTC_PoAskAnswer(p, false);", cancel)
        self.assertIn("BOTC_GudiaoAnswer(p, false);", source)

    def test_lil_monsta_and_legion_use_target_pickers(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "BOTC_LmDetectNoDemon();\n    if (g_lmOn) {\n        BOTC_LmGroupChat();",
            "if (g_lmOn && q == g_lmSeat) {\n        r = 112;",
            "showRole[112] = true;",
            "if (g_noAllFirst[112] <= 0) {\n            g_noAllFirst[112] = 26;",
            "if (g_noAllOther[112] <= 0) {\n            g_noAllOther[112] = 59;",
            "g_lmOn = true;\n        g_lmSeat = seat;",
            "void BOTC_ManualDeathOpen (int src, int role) {",
            "g_miRole = 816;",
            "BOTC_ManualDeathOpen(best, bestRole);",
            "BOTC_ManualDeathPick(q);",
            "BOTC_MarkDeathQuietSrc(q, 1, 1, g_mdRole);",
            "g_roleDeathTok[112] = 132;",
            "g_roleDeathTok[94] = 115;",
        ):
            self.assertIn(marker, source)

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

    def test_yihua_board_roster_and_cover(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("return 14;  // 【板子张数】", source)
        self.assertIn('return "移花接木";', source)
        self.assertIn('return "botc_board_yhjm.dds";', source)
        self.assertIn("if (slot == 11) {\n            return 15;", source)
        self.assertIn("g_boardRoleN[15] = 25;", source)

        roles = {
            int(slot): int(role)
            for slot, role in re.findall(
                r"g_boardRole\[\(15 \* 256\) \+ (\d+)\]\s*=\s*(\d+);",
                source,
            )
        }
        self.assertEqual(
            [roles[index] for index in range(25)],
            [
                50, 5, 116, 159, 24, 156, 161, 128, 105, 27, 28, 158, 74,
                160, 37, 38, 157,
                93, 155, 162, 39,
                44, 154, 121, 163,
            ],
        )

        for path, size in (
            (PROJECT_ROOT / "assets" / "source" / "board_15_yihua.png", (550, 248)),
            (PROJECT_ROOT / "assets" / "game" / "botc_board_yhjm.dds", (256, 256)),
        ):
            self.assertTrue(path.is_file())
            self.assertGreater(path.stat().st_size, 0)
        raw = (PROJECT_ROOT / "assets" / "game" / "botc_board_yhjm.dds").read_bytes()
        self.assertEqual(raw[:4], b"DDS ")
        self.assertEqual(struct.unpack_from("<I", raw, 12)[0], size[0])
        self.assertEqual(struct.unpack_from("<I", raw, 16)[0], size[1])
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


class IntroNameFlowTests(unittest.TestCase):
    def test_board_selection_starts_name_phase_before_seat_assignment(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )

        board_finish = source[source.index("void BOTC_BoardFinish (int b) {"):]
        board_finish = board_finish[: board_finish.index("\n}\n") + 3]
        self.assertIn("BOTC_IntroBegin();", board_finish)

        intro_finish = source[source.index("void BOTC_IntroFinish () {"):]
        intro_finish = intro_finish[: intro_finish.index("\n}\n") + 3]
        self.assertLess(
            intro_finish.index("BOTC_ShuffleSeats();"),
            intro_finish.index("BOTC_AssignRandomNames();"),
        )
        self.assertLess(
            intro_finish.index("BOTC_AssignRandomNames();"),
            intro_finish.index("BOTC_ClearAllLogs();"),
        )

        self.assertEqual(source.count("BOTC_ShuffleSeats();"), 1)
        self.assertEqual(source.count("BOTC_AssignRandomNames();"), 1)
        board_open = source[source.index("void BOTC_BoardOpen () {"):]
        board_open = board_open[: board_open.index("\n}\n") + 3]
        self.assertIn("if (BOTC_P1IsComputer()) {", board_open)
        self.assertLess(
            board_open.index("BOTC_BoardSelect(1);"),
            board_open.index("BOTC_BoardStart();"),
        )
        self.assertIn("BOTC_BoardSelect(b);", source)
        self.assertIn("g_boardStartBtn = BOTC_NewButton(g_boardDlg, 280, 50, 1600, 930", source)
        self.assertIn("DialogSetPosition(g_tmShowDlg, c_anchorTopLeft, 1600, 990);", source)
        self.assertIn("DialogSetPosition(g_tmShowDlg, c_anchorCenter, 0, 40);", source)
        self.assertIn("BOTC_FixedCountdownStop();", source)
        self.assertIn("if (!g_boardOpen || g_boardFade < 4 || g_cOpen)", source)
        self.assertIn("g_seatInfoLbl = BOTC_NewLabel(g_boardDlg, 900, 36, 980, 956", source)
        self.assertIn('StringToText("取消")', source)
        self.assertIn("BOTC_BoardStartCancel();", source)
        self.assertIn("TimerStart(g_tIntro, 20.0, false, c_timeGame);", source)
        self.assertIn("TimerStart(g_tStartCd, 1.0, true, c_timeGame);", source)
        self.assertIn("g_startCdSec = g_startCdSec - 1;", source)
        count_render = source[source.index("void BOTC_BoardStartCdRender () {"):]
        count_render = count_render[: count_render.index("\n}\n") + 3]
        self.assertNotIn("DialogSetVisible", count_render)
        self.assertIn("输入 -名字 以取名", source)
        self.assertIn("例如：-好人", source)
        self.assertIn('g_namePool[4]  = "泰凯斯"', source)
        self.assertIn("BOTC_TextWidth(name) > 20", source)
        self.assertIn("bool BOTC_ValidColorName (string s) {", source)
        self.assertIn("BOTC_ValidColorName(name)", source)
        self.assertIn("BOTC_IsHexChar(StringSub(code, j, j + 1))", source)
        self.assertIn("bool BOTC_NameUsesOfficialName (string s)", source)
        self.assertIn("if (s == g_namePool[i])", source)
        self.assertIn("visible == g_namePool[i]", source)
        self.assertIn("return BOTC_ChatNoColor(s);", source)
        self.assertIn("g_introName[q] == name", source)
        self.assertIn("positions[m] = i;", source)
        self.assertIn("g_who[positions[i]] = people[i];", source)
        self.assertIn('if (p == g_teller) {\n        BOTC_Notice(p, "说书人保持战网名', source)
        self.assertIn(
            "DialogSetVisible(g_chatDlg[p], PlayerGroupSingle(p), true);",
            source,
        )
        self.assertIn("BOTC_IntroTryMsg(p, msg);", source)
        self.assertIn("StringSub(msg, at + 1, n)", source)
        self.assertIn('StringFind(msg, "\uff0d", false)', source)
        self.assertIn("if (!g_introHinted[p])", source)
        self.assertIn(
            "if (pid == g_teller && !g_introChosen[pid])",
            source,
        )
        self.assertIn(
            'StringToText("说书人 [") + TextWithColor(BOTC_SeatNameText(1),',
            source,
        )
        intro_begin = source[source.index("void BOTC_IntroBegin () {"):]
        intro_begin = intro_begin[: intro_begin.index("\n}\n") + 3]
        self.assertIn("BOTC_ClearAllLogs();", intro_begin)
        self.assertLess(
            intro_begin.index("BOTC_ClearAllLogs();"),
            intro_begin.index("TimerStart(g_tIntro, 20.0, false, c_timeGame);"),
        )
        custom_show = source[source.index("void BOTC_CustomShowEditor () {"):]
        custom_show = custom_show[: custom_show.index("\n}\n") + 3]
        self.assertIn(
            "DialogSetVisible(g_boardStartBtn, PlayerGroupAll(), false);",
            custom_show,
        )
        self.assertIn("g_dispName[p] = name;", source)
        self.assertGreaterEqual(source.count("BOTC_ResetPlayerNames();"), 3)


class AmnesiaViewTests(unittest.TestCase):
    def test_player_identity_stays_masked_until_correct_guess(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        role_view = source[source.index("int BOTC_PlayerRoleView (int seat, int roleIdx) {"):]
        role_view = role_view[: role_view.index("\n}\n") + 3]
        self.assertIn("!g_guessRoleDone[g_who[seat]]", role_view)
        self.assertNotIn("g_nightNum == 0", role_view)

        sync = source[source.index("void BOTC_AmnesiaSyncSeat (int seat, int roleIdx) {"):]
        sync = sync[: sync.index("\n}\n") + 3]
        self.assertIn("BOTC_PlayerRoleView(seat, roleIdx)", sync)


class LogIdentityTests(unittest.TestCase):
    def test_only_storyteller_logs_append_real_battle_ids(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        player_name = source[source.index("text BOTC_LogPlayerNameText (int p) {"):]
        player_name = player_name[: player_name.index("\n}\n") + 3]
        self.assertIn("g_who[p] == g_teller", player_name)
        self.assertIn("shown == battle", player_name)
        self.assertIn('StringToText("（")', player_name)
        self.assertIn('StringToText("）")', player_name)

        line_text = source[source.index("text BOTC_LogLineText (int viewer, string line, int who) {"):]
        line_text = line_text[: line_text.index("\n}\n") + 3]
        self.assertIn("viewer == g_teller", line_text)
        self.assertIn("BOTC_LogNameSubstText(t)", line_text)
        self.assertIn("BOTC_NameSubstText(t)", line_text)

        self.assertGreaterEqual(source.count("BOTC_LogLineText(p,"), 20)
        self.assertIn("g_pubLog[i], g_pubWho[i]", source)
        self.assertIn("g_pmLog[(p * 600) + i]", source)


class BluffPanelRegressionTests(unittest.TestCase):
    def test_manual_bottom_right_bluff_panels_are_restored(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )

        teller_ui_start = source.index("void BOTC_BluffTellerUI () {")
        teller_ui_end = source.index("\n}\n", teller_ui_start)
        teller_ui = source[teller_ui_start:teller_ui_end]
        self.assertIn(
            "DialogSetVisible(g_bluffDlg, PlayerGroupSingle(g_teller), true);",
            teller_ui,
        )

        deal_start = source.index("void BOTC_Deal () {")
        deal_end = source.index("\nvoid ", deal_start + 1)
        deal = source[deal_start:deal_end]
        self.assertIn(
            "DialogSetVisible(g_bluffDlg, PlayerGroupSingle(g_teller), true);",
            deal,
        )

        self.assertGreaterEqual(
            source.count(
                "DialogControlSetVisible(g_bluffSeat[i], PlayerGroupSingle(g_teller), true);"
            ),
            2,
        )
        self.assertNotIn("g_lbluff", source)
        self.assertIn(
            "DialogControlSetVisible(g_specBtn, PlayerGroupSingle(g_teller), g_started || g_isNight);",
            source,
        )
        self.assertNotIn("g_specBluffBtn = BOTC_NewButton", source)
        self.assertNotIn("if (c == g_specBluffBtn)", source)


class MergeRegressionTests(unittest.TestCase):
    @staticmethod
    def _function_text(source: str, signature: str) -> str:
        start = source.index(signature)
        end = source.find("\nvoid ", start + len(signature))
        return source[start:] if end < 0 else source[start:end]

    def test_living_corpse_skill_keeps_impaired_target_flow(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        skill_works = self._function_text(source, "bool BOTC_SkillWorks (int q) {")
        skill_confirm = self._function_text(
            source, "void BOTC_SkillConfirmCore (int p) {"
        )

        self.assertIn("if (g_liveCorpse[q])", skill_works)
        self.assertNotIn("g_liveCorpse[p]", skill_confirm)
        self.assertIn("BOTC_TellSkillChoice(p, -1);", skill_confirm)
        self.assertIn("BOTC_PmStore(g_teller, s);", skill_confirm)
        self.assertIn("BOTC_ManInfoOpen(", skill_confirm)

    def test_handles_command_is_public_colored_and_replies_to_sender(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        handles = self._function_text(
            source, "void BOTC_HandleListToPm (int viewer) {"
        )

        self.assertIn(
            'if (msg == "-handles") {\n        BOTC_HandleListToPm(p);',
            source,
        )
        self.assertNotIn('BOTC_DevPlayer(p) && msg == "-handles"', source)
        self.assertIn("BOTC_PmStore(viewer,", handles)
        self.assertNotIn("BOTC_PmStore(g_teller,", handles)
        self.assertIn('"【句柄】" + IntToString(p) + "：" + tok', handles)
        self.assertIn("h = PlayerHandle(p);", handles)
        self.assertIn("tok = BOTC_HandleToken(p);", handles)
        self.assertIn('tok = "@@HL" + IntToString(p) + "@@";', handles)
        self.assertNotIn("物理座位", handles)
        self.assertIn("PlayerGetColorIndex(p, false)", source)
        stats = self._function_text(source, "void BOTC_StatsRender (int p) {")
        self.assertIn("PlayerName(pid)", stats)
        self.assertNotIn("BOTC_SeatNameText", stats)
        self.assertNotIn("BOTC_PlayerNameText", stats)

    def test_first_night_marionette_info_waits_for_its_action_turn(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        demon_info = self._function_text(
            source, "void BOTC_SendFirstNightDemonInfo () {"
        )
        marionette_info = self._function_text(
            source, "void BOTC_SendFirstNightMarionetteInfo () {"
        )
        evil_step = self._function_text(
            source, "bool BOTC_AutoWakeEvilStep () {"
        )

        self.assertNotIn("是提线木偶", demon_info)
        self.assertIn("BOTC_SendMarionetteToDemons();", marionette_info)
        self.assertIn("BOTC_LunaticMarionetteAsk(lu)", marionette_info)
        self.assertIn("ord = 19;", evil_step)
        self.assertIn("BOTC_SendFirstNightMarionetteInfo();", evil_step)

    def test_lunatic_warden_is_fake_and_death_tokens_use_generic_name(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        night_order = self._function_text(source, "int BOTC_NightOrderOf (int q) {")

        self.assertIn("if (r != 163)", night_order)
        self.assertIn("if (r == 163 && !BOTC_IsLunatic(p)) {", source)
        self.assertIn(
            'g_tokName[175] = "死亡";                   '
            'g_tokShort[175] = "死亡";',
            source,
        )
        self.assertIn(
            'g_tokName[204] = "死亡";                   '
            'g_tokShort[204] = "死亡";',
            source,
        )

    def test_juggler_claim_draft_survives_phase_cleanup(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        phase_close = self._function_text(source, "void BOTC_PhaseUiForceClose () {")
        juggler_open = self._function_text(source, "void BOTC_JugglerOpen (int p) {")

        self.assertIn("int[70]     g_juggRole;", source)
        self.assertIn("BOTC_JugglerHide(q);", phase_close)
        self.assertNotIn("BOTC_JugglerCancel(q);", phase_close)
        self.assertNotIn("g_juggRole[(p * 5) + i] = 0;", juggler_open)
        self.assertIn(
            "g_juggRole[(ob * 5) + g_juggRow - 1] = idx;",
            source,
        )

    def test_wrong_damsel_guess_blocks_later_wins_for_rest_of_game(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        dawn = self._function_text(source, "void BOTC_DawnResolve () {")
        deal = self._function_text(source, "void BOTC_Deal () {")
        guess = self._function_text(source, "void BOTC_DamselGuess (int p, int q) {")

        self.assertNotIn("g_damselFailed = false;", dawn)
        self.assertIn("g_damselFailed = false;", deal)
        self.assertLess(
            guess.index("if (g_damselFailed)"),
            guess.index("BOTC_ShowWin("),
        )

    def test_guide_and_gudiao_prompts_reset_shared_answer_panel(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("BOTC_GuideOpen(p, s);", source)
        self.assertIn("void BOTC_GuideOpen (int seat, string extra) {", source)
        self.assertIn("g_miRole = 156;", source)

        gudiao_start = source.index("void BOTC_GudiaoOpen (int p) {")
        gudiao_end = source.index("void BOTC_GudiaoAnswer (int p, bool change) {", gudiao_start)
        gudiao_open = source[gudiao_start:gudiao_end]
        self.assertIn("g_limitedAsk[p] = true;", gudiao_open)
        self.assertIn(
            'libNtve_gf_SetDialogItemText(g_skillTitle[p], StringToText("是否发动技能（改变方向）"), PlayerGroupSingle(g_who[p]));',
            gudiao_open,
        )
        self.assertIn(
            "DialogSetVisible(g_skillDlg[p], PlayerGroupSingle(g_who[p]), true);",
            gudiao_open,
        )
        self.assertIn("BOTC_GudiaoAnswer(p, true);", source)
        self.assertIn("BOTC_GudiaoAnswer(p, false);", source)

    def test_private_chat_navigation_is_not_hidden_by_length_guess(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("need = (g_sessMaxSkip[p] > 0);", source)
        self.assertIn(
            "maxSkip = g_sessMaxSkip[p];\n    if (maxSkip <= 0) {",
            source,
        )
        for marker in (
            "int[14]     g_sessBar;",
            "int[14]     g_sessKnob;",
            "int[14]     g_sessPrevBtn;",
            "int[14]     g_sessNextBtn;",
            "trigger     g_tSessBarDown;",
            "void BOTC_SessNavRender (int p) {",
            "void BOTC_SessNavStep (int p, int d) {",
            "void BOTC_SessBarRender (int p) {",
            "bool BOTC_SessBarDown_Func (bool testConds, bool runActions) {",
            'g_sessBar[p] = BOTC_NewImageItem(DialogLastCreated(), 480, 8, 10, 82, "ui_sess_track.dds");',
            'g_sessKnob[p] = BOTC_NewImageItem(DialogLastCreated(), 44, 12, 10, 81, "ui_sess_knob.dds");',
            'g_sessPrevBtn[p] = BOTC_NewButton(DialogLastCreated(), 40, 22, 350, 62, "<");',
            'g_sessNextBtn[p] = BOTC_NewButton(DialogLastCreated(), 40, 22, 395, 62, ">");',
            'g_tSessBarDown = TriggerCreate("BOTC_SessBarDown_Func");',
            "g_sessXOff[p] = g_sessXOff[p] + d;",
            "g_sessKnobX[p] = v;",
            "DialogControlSetPosition(g_sessKnob[p], PlayerGroupSingle(p), c_anchorTopLeft, 10 + v, 81);",
        ):
            self.assertIn(marker, source)
        for name in ("ui_sess_track", "ui_sess_knob"):
            self.assertTrue((PROJECT_ROOT / "assets" / "source" / f"{name}.png").is_file())
            raw = (PROJECT_ROOT / "assets" / "game" / f"{name}.dds").read_bytes()
            self.assertEqual(raw[:4], b"DDS ")
            self.assertEqual(struct.unpack_from("<I", raw, 12)[0], 64)
            self.assertEqual(struct.unpack_from("<I", raw, 16)[0], 16)
        self.assertNotIn("TriggerAddEventMouseWheel(", source)
        self.assertNotIn(
            "need = (g_sessXOff[p] > 0 || (g_sessMaxSkip[p] > 0 && g_sessLong[p] > 60));",
            source,
        )

    def test_role_and_night_order_dialogs_are_per_player(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "int[14]     g_abNewDlg;",
            "int[14]     g_noDlg;",
            "int[364]    g_abNewHit;",
            "int[336]    g_noIcon;",
            "DialogSetPosition(g_abNewDlg[p], c_anchorCenter, nx, ny);",
            "DialogSetPosition(g_noDlg[p], c_anchorCenter, nx, ny);",
            "for (p = 1; p <= 13; p += 1) {\n        base = p * 24;",
            "for (p = 1; p <= 13; p += 1) {\n        base = p * 26;",
        ):
            self.assertIn(marker, source)
        self.assertNotIn("DialogSetPosition(g_abNewDlg, c_anchorCenter", source)
        self.assertNotIn("DialogSetPosition(g_noDlg, c_anchorCenter", source)

    def test_role_card_ability_text_has_one_extra_line(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn(
            "DialogControlSetPosition(g_abNewName[idx], PlayerGroupSingle(p), c_anchorTopLeft, x + 92, y);",
            source,
        )
        self.assertIn(
            "DialogControlSetPosition(g_abNewAb[idx], PlayerGroupSingle(p), c_anchorTopLeft, x + 92, y + 26);",
            source,
        )
        self.assertIn(
            "DialogControlSetSize(g_abNewAb[idx], PlayerGroupSingle(p), w, 96);",
            source,
        )
        self.assertIn("50 + ((i % 7) * 124), 460);", source)
        self.assertIn("446 + ((i / 3) * 124), 250);", source)
        self.assertIn("726 + ((i / 3) * 124), 250);", source)

    def test_pukka_bad_action_keeps_last_effective_target(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        start = source.index("void BOTC_PukkaResolve (int p, int t) {")
        end = source.index("// ■ 沙巴洛斯（45）：反刍", start)
        pukka = source[start:end]
        guard = pukka.index("if (!BOTC_SkillWorks(p)) {")
        assign = pukka.index("g_pukkaSeat = t;")
        self.assertLess(guard, assign)
        self.assertIn("上一次正常生效时选择的", pukka)
        self.assertIn("仍保持中毒", pukka)

        confirm = source.index("void BOTC_SkillConfirm (int p) {")
        pukka_branch = source.index("if (r == 44) {", confirm)
        goon_touch = source.index("BOTC_GoonTouch(p, g_skillT1[p]);", confirm)
        self.assertLess(goon_touch, pukka_branch)

    def test_exorcist_triggers_pukka_pending_death(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("BOTC_PukkaExorcistResolve (int p);", source)
        self.assertIn(
            "if (BOTC_SeatTrueRole(t) == 44) {\n                    BOTC_PukkaExorcistResolve(t);",
            source,
        )
        start = source.index("void BOTC_PukkaExorcistResolve (int p) {")
        end = source.index("// ■ 沙巴洛斯（45）：反刍", start)
        helper = source[start:end]
        for marker in (
            "if (!BOTC_SkillWorks(p)) {",
            "BOTC_DemonStrike(p, 44, old, false);",
            "+ 63] = false;",
            "g_pukkaSeat = 0;",
            "死亡标记：普卡",
            "撤掉中毒（普卡）",
        ):
            self.assertIn(marker, helper)

    def test_recent_custom_role_jinxes_are_listed(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("string[140] g_jinxText;", source)
        self.assertIn("g_jinxCount = 139;", source)
        pairs = {
            (int(a), int(b))
            for a, b in re.findall(
                r"g_jinxA\[\d+\]\s*=\s*(\d+);\s*g_jinxB\[\d+\]\s*=\s*(\d+);",
                source,
            )
        }
        normalized = {frozenset(pair) for pair in pairs}
        for pair in (
            (156, 24),
            (156, 50),
            (124, 86),
            (124, 158),
            (118, 105),
            (118, 50),
            (137, 126),
            (162, 95),
            (162, 136),
            (162, 148),
            (162, 137),
            (127, 161),
            (163, 150),
            (100, 158),
            (100, 157),
            (100, 159),
        ):
            self.assertIn(frozenset(pair), normalized)

    def test_recent_custom_role_jinx_runtime_hooks(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        for marker in (
            "BOTC_HasAbility(g_skillT1[seat], 156)",
            "BOTC_HasAbility(g_skillT2[seat], 156)",
            'if (BOTC_HasAbility(t, 86)) {',
            "BOTC_MalfNote(t, \"悟道者被邪恶能力影响后改变角色\");",
            "role == 163 && BOTC_BoardHasRole(163)",
            "if (mode == 21 && r == 162) {",
            "if (BOTC_ActRoleOf(p) == 100 && BOTC_ActingIsFirstNight(p)) {",
        ):
            self.assertIn(marker, source)

    def test_newer_role_descriptions_use_full_card_format(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        lines = {
            int(index): value
            for index, value in re.findall(
                r'g_tipLine\[(\d+)\]\s*=\s*StringToText\("([^"]*)"\);',
                source,
            )
        }
        ranges = {
            role: (at, count)
            for role, at, count in re.findall(
                r"g_tipRoleAt\[(\d+)\]\s*=\s*(\d+);\s*g_tipRoleN\[\1\]\s*=\s*(\d+);",
                source,
            )
        }
        for role in range(147, 164):
            self.assertIn(str(role), ranges)
            at, count = ranges[str(role)]
            at = int(at)
            count = int(count)
            block = [lines.get(at + offset, "") for offset in range(count)]
            # 新版详情页按章节组织：多数角色从「背景故事」开始，
            # 少数只有能力/简介/规则细节的角色直接从「角色能力」开始。
            self.assertIn(block[0], ("【背景故事】", "【角色能力】"))
            self.assertIn("【角色能力】", block)
            self.assertIn("【角色简介】", block)
        self.assertNotIn("BOTC_BluffAskStart();", source)
        self.assertIn(
            "DialogSetVisible(g_bluffDlg, PlayerGroupSingle(g_teller), true);",
            source,
        )


if __name__ == "__main__":
    unittest.main()
