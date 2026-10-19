import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("smells.py")


class CannotRun(unittest.TestCase):
    def test_a_file_that_cannot_be_parsed_stops_with_2_and_names_it(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "harness"
            harness.mkdir()
            (harness / "test_orders.py").write_text("def test_paid(:\n")
            result = subprocess.run([sys.executable, str(SCRIPT), str(harness)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(f"STOPPED: cannot parse {harness / 'test_orders.py'}", result.stderr)


if __name__ == "__main__":
    unittest.main()
