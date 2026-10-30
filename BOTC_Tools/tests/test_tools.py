from __future__ import annotations

import sys
import unittest
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT))

from build_map import (
    replace_custom_script,
    split_custom_script,
    split_trigger_custom_scripts,
    verify_packed_script,
    verify_split_map_script,
    verify_split_triggers,
)
from galaxy_check import scan_galaxy
from role_workflow import default_spec
from ui_embed import (
    strip_ui_dependency_document_info,
    strip_ui_dependency_header,
)


class BuildMapTests(unittest.TestCase):
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


class RoleSpecTests(unittest.TestCase):
    def test_default_spec_has_release_checks(self) -> None:
        spec = default_spec(148, "测试", "townsfolk", "good")
        self.assertEqual(spec["index"], 148)
        self.assertGreaterEqual(len(spec["acceptance"]), 5)
        self.assertIn("state_fields", spec["implementation"])


class UIDependencyTests(unittest.TestCase):
    def test_document_info_removes_only_uihide(self) -> None:
        source = (
            "<Dependencies>\n"
            "  <Value>bnet:Void/1.0/1</Value>\n"
            "  <Value>bnet:UIHIDE/1.4/188066</Value>\n"
            "</Dependencies>\n"
        ).encode()
        updated = strip_ui_dependency_document_info(source).decode()
        self.assertIn("bnet:Void/1.0/1", updated)
        self.assertNotIn("UIHIDE", updated)

    def test_document_info_removes_local_uihide(self) -> None:
        source = (
            "<Dependencies>\n"
            "  <Value>bnet:Void/1.0/1</Value>\n"
            r"  <Value>file:Mods\UIHIDE55.SC2Mod</Value>"
            "\n</Dependencies>\n"
        ).encode()
        updated = strip_ui_dependency_document_info(source).decode()
        self.assertIn("bnet:Void/1.0/1", updated)
        self.assertNotIn("UIHIDE", updated)

    def test_document_header_removes_dependency_and_count(self) -> None:
        header = bytearray(b"H2CS")
        header.extend(b"\0" * 36)
        header.extend((2).to_bytes(4, "little"))
        header.extend(b"bnet:Void/1.0/1\0")
        header.extend(b"bnet:UIHIDE/1.4/188066\0")
        header.extend((7).to_bytes(4, "little"))
        header.extend(b"tail")
        updated = strip_ui_dependency_header(bytes(header))
        self.assertEqual(int.from_bytes(updated[40:44], "little"), 1)
        self.assertIn(b"bnet:Void/1.0/1", updated)
        self.assertNotIn(b"UIHIDE", updated)
        self.assertTrue(updated.endswith((7).to_bytes(4, "little") + b"tail"))

    def test_document_header_removes_local_uihide(self) -> None:
        header = bytearray(b"H2CS")
        header.extend(b"\0" * 36)
        header.extend((2).to_bytes(4, "little"))
        header.extend(b"bnet:Void/1.0/1\0")
        header.extend(b"file:Mods\\UIHIDE55.SC2Mod\0")
        header.extend((1).to_bytes(4, "little"))
        updated = strip_ui_dependency_header(bytes(header))
        self.assertEqual(int.from_bytes(updated[40:44], "little"), 1)
        self.assertNotIn(b"UIHIDE", updated)


if __name__ == "__main__":
    unittest.main()
