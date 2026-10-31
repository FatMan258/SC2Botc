from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
sys.path.insert(0, str(TOOL_ROOT))

from build_map import (
    collect_local_assets,
    replace_custom_script,
    split_custom_script,
    split_trigger_custom_scripts,
    verify_packed_script,
    verify_split_map_script,
    verify_split_triggers,
)
from galaxy_check import find_forward_call_errors, scan_galaxy
from role_workflow import default_spec


class BuildMapTests(unittest.TestCase):
    def test_collects_local_assets_with_relative_paths(self) -> None:
        root = Path(__file__).resolve().parent / "fixtures" / "local-assets"
        assets = collect_local_assets(root)
        self.assertEqual(
            [name for name, _ in assets],
            ["example.bin", "nested/data.dat"],
        )

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
        for name in ("BOTC.txt", "BOTC_test.txt"):
            source = (PROJECT_ROOT / "scripts" / name).read_text(
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


class RoleSpecTests(unittest.TestCase):
    def test_default_spec_has_release_checks(self) -> None:
        spec = default_spec(148, "测试", "townsfolk", "good")
        self.assertEqual(spec["index"], 148)
        self.assertGreaterEqual(len(spec["acceptance"]), 5)
        self.assertIn("state_fields", spec["implementation"])


if __name__ == "__main__":
    unittest.main()
