import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"

SCRIPT = SCRIPTS / "smells.py"


class CannotRun(unittest.TestCase):
    def test_a_file_that_cannot_be_parsed_stops_with_2_and_names_it(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "harness"
            harness.mkdir()
            (harness / "test_orders.py").write_text("def test_paid(:\n")
            result = subprocess.run([sys.executable, str(SCRIPT), str(harness)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(f"STOPPED: cannot parse {harness / 'test_orders.py'}", result.stderr)


class BreakAware(unittest.TestCase):
    def scan(self, files):
        """smells.py's exit code and output over a harness holding the files, by path from the harness."""
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "verify-app"
            for name, text in files.items():
                (harness / name).parent.mkdir(parents=True, exist_ok=True)
                (harness / name).write_text(text)
            result = subprocess.run([sys.executable, str(SCRIPT), str(harness)], capture_output=True, text=True)
            return result.returncode, result.stdout.replace(str(harness) + "/", "")

    def test_flags_a_check_in_any_language_that_can_tell_it_is_in_a_planned_break(self):
        code, output = self.scan({
            "scripts/checks/pay.py": "import os\nif os.environ.get('VERIFY_PLANNED_BREAK'):\n    raise SystemExit(1)\n",
            "scripts/checks/refund.ts": "const session = process.env.VERIFY_BREAK_SESSION;\n",
        })
        self.assertEqual(code, 1, output)
        self.assertEqual(output.splitlines(), [
            "break-aware scripts/checks/pay.py:2 reads VERIFY_PLANNED_BREAK; vf.py run ends a planned break's run, "
            "so a check must do the same in a break as in a pass",
            "break-aware scripts/checks/refund.ts:1 reads VERIFY_BREAK_SESSION; vf.py run ends a planned break's run, "
            "so a check must do the same in a break as in a pass",
        ])

    def test_leaves_alone_a_clean_check_the_framework_copies_and_files_outside_scripts(self):
        code, output = self.scan({
            "scripts/checks/pay.py": "import os\nreport = os.environ['VERIFY_REPORT']\n",
            "scripts/framework/vf.py": "planned = os.environ.get('VERIFY_PLANNED_BREAK')\n",
            "rules.md": "sets `VERIFY_PLANNED_BREAK=<sub-feature IDs>: <what was broken>`\n",
        })
        self.assertEqual((code, output.strip()), (0, "No smells found."))


if __name__ == "__main__":
    unittest.main()
