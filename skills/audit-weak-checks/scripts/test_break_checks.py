import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("break_checks.py")


class FindsChecks(unittest.TestCase):
    def test_async_checks_are_broken_like_any_other(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "harness"
            harness.mkdir()
            (harness / "checks.py").write_text("async def check_payment() -> list:\n    return []\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--harness", str(harness), "--list"], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("check_payment -> return []", result.stdout)


class CannotRun(unittest.TestCase):
    def test_a_file_that_cannot_be_parsed_stops_with_2_and_names_it(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "harness"
            harness.mkdir()
            (harness / "checks.py").write_text("def check_order(:\n")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--harness", str(harness), "--list"], capture_output=True, text=True
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(f"STOPPED: cannot parse {harness / 'checks.py'}", result.stderr)


if __name__ == "__main__":
    unittest.main()
