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
            "BOTC_WudChangeOpen(chosen[i], p);",
            "BOTC_TaotieToggle(g_who[p], q);",
            "if (demonPick == 154)",
            "if (g_rsPick[154])",
            "g_noAllOther[154] = 63;",
        ):
            self.assertIn(marker, source)

    def test_recent_role_dds_use_uncompressed_rgba_format(self) -> None:
        for index in (148, 149, 150, 151, 154):
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


class BoardPaginationTests(unittest.TestCase):
    def test_cheng_shuang_cheng_dui_board_and_page_two(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "BOTC.galaxy").read_text(
            encoding="utf-8-sig"
        )
        self.assertIn("if (g_boardPage == 2)", source)
        self.assertIn("g_boardPage = 1;", source)
        self.assertIn("g_boardPrevBtn = BOTC_NewButton", source)
        self.assertIn("g_boardNextBtn = BOTC_NewButton", source)
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


if __name__ == "__main__":
    unittest.main()
