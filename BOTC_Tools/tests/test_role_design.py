from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT))

from role_design import build_ai_prompt, compile_plan, validate_spec


class RoleDesignTests(unittest.TestCase):
    def load_example(self) -> dict:
        return json.loads(
            (TOOL_ROOT / "role_specs" / "role_dsl.example.json").read_text(
                encoding="utf-8"
            )
        )

    def test_example_is_valid(self) -> None:
        errors, _ = validate_spec(self.load_example())
        self.assertEqual(errors, [])

    def test_token_requires_duration(self) -> None:
        spec = self.load_example()
        spec["effects"] = [{"kind": "set_token", "token": "测试"}]
        errors, _ = validate_spec(spec)
        self.assertTrue(any("duration" in error for error in errors))

    def test_interference_section_is_supported(self) -> None:
        spec = self.load_example()
        spec["night_order"] = {
            "section": "interference",
            "anchor_role": "投毒者",
            "relation": "after",
            "first": None,
            "other": None,
        }
        spec["timing"] = "every_night"
        errors, _ = validate_spec(spec)
        self.assertEqual(errors, [])

    def test_night_anchor_requires_relation(self) -> None:
        spec = self.load_example()
        spec["night_order"]["anchor_role"] = "共情者"
        spec["night_order"]["relation"] = None
        errors, _ = validate_spec(spec)
        self.assertTrue(any("anchor_role" in error for error in errors))

    def test_plan_contains_integration_points(self) -> None:
        plan = compile_plan(self.load_example())
        self.assertIn("BOTC_SkillOpen", plan)
        self.assertIn("BOTC_TargetIsLiving", plan)
        self.assertIn("g_roleName[148]", plan)

    def test_prompt_requires_json_only(self) -> None:
        prompt = build_ai_prompt("每个白天，你得知一条信息。")
        self.assertIn("只输出一个 JSON", prompt)
        self.assertIn("schema_version=2", prompt)
        self.assertIn("role_change/interference", prompt)
        self.assertIn("anchor_role", prompt)


if __name__ == "__main__":
    unittest.main()
