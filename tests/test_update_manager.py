import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "update_manager.py"
spec = importlib.util.spec_from_file_location("update_manager", MODULE_PATH)
update_manager = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules["update_manager"] = update_manager
spec.loader.exec_module(update_manager)


class UpdateManagerTests(unittest.TestCase):
    def test_parse_requirements_line(self):
        self.assertEqual(
            update_manager.parse_requirements_line("fastapi>=0.100.0"),
            ("fastapi", ">=", "0.100.0"),
        )
        self.assertEqual(
            update_manager.parse_requirements_line("openai==1.64.0"),
            ("openai", "==", "1.64.0"),
        )
        self.assertEqual(
            update_manager.parse_requirements_line("jupyter"),
            ("jupyter", "", ""),
        )
        self.assertEqual(
            update_manager.parse_requirements_line("starlette-context>=0.3.6,<0.4"),
            ("starlette-context", "complex", ">=0.3.6,<0.4"),
        )
        self.assertEqual(update_manager.parse_requirements_line("# comment"), (None, None, None))

    def test_is_newer_numeric(self):
        self.assertTrue(update_manager.is_newer("0.19.0", "0.18.3"))
        self.assertFalse(update_manager.is_newer("0.18.3", "0.18.3"))
        self.assertTrue(update_manager.is_newer("full-cuda-b5350", "full-cuda-b5343"))

    def test_apply_replacements_does_not_touch_frozen_file(self):
        with tempfile.TemporaryDirectory() as td:
            frozen_path = Path(td) / "requirements.txt"
            frozen_path.write_text("openai==1.0.0\n", encoding="utf-8")

            original_frozen = update_manager.REQ_FROZEN
            update_manager.REQ_FROZEN = frozen_path
            try:
                reps = [
                    update_manager.Replacement(
                        source_file=frozen_path,
                        old="openai==1.0.0",
                        new="openai==2.0.0",
                    )
                ]
                with self.assertRaises(RuntimeError):
                    update_manager.apply_replacements(preview_only=False, replacements=reps)
            finally:
                update_manager.REQ_FROZEN = original_frozen


if __name__ == "__main__":
    unittest.main()

