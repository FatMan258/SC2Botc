import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from galaxy_check import find_trigger_callback_errors


class TriggerCallbackTests(unittest.TestCase):
    def test_rejects_previous_log_callback(self):
        source = '''void BOTC_LogTick_Func () {}
void Init () { TriggerCreate("BOTC_LogTick_Func"); }'''
        self.assertEqual(len(find_trigger_callback_errors(source)), 1)

    def test_accepts_engine_signature(self):
        source = '''bool BOTC_LogTick_Func (bool testConds, bool runActions) { return true; }
void Init () { TriggerCreate("BOTC_LogTick_Func"); }'''
        self.assertEqual(find_trigger_callback_errors(source), [])

    def test_ignores_comments_strings_and_external_libraries(self):
        source = '''// TriggerCreate("BOTC_Missing");
void Init () {
    string example = "TriggerCreate(\\\"BOTC_Missing\\\")";
    TriggerCreate("libExternal_Callback");
}'''
        self.assertEqual(find_trigger_callback_errors(source), [])

    def test_rejects_missing_local_callback_and_wrong_parameter(self):
        source = '''bool BOTC_Wrong (bool testConds, int runActions) { return true; }
void Init () { TriggerCreate("BOTC_Wrong"); TriggerCreate("BOTC_Missing"); }'''
        self.assertEqual(len(find_trigger_callback_errors(source)), 2)


if __name__ == '__main__':
    unittest.main()
