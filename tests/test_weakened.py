import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"

sys.path.insert(0, str(SCRIPTS))
import weakened  # noqa: E402
from support import git  # noqa: E402

SCRIPT = SCRIPTS / "weakened.py"
PROCEDURE = SCRIPTS.parent / "references" / "mode-audit-weak-checks.md"



class CommitTitle(unittest.TestCase):
    def test_the_skill_titles_its_fix_commits_with_the_title_weakened_searches_for(self):
        title = weakened.AUDIT_TITLE.lstrip("^")
        skill = PROCEDURE.read_text()
        self.assertIn(f"titled `{title}: ", skill)
        self.assertIn(f'Commit these fixes as "{title}: ', skill)


CHECKS = '''def check_order():
    message = """
text at column 0 inside the check
"""
    return []


async def check_payment():
    return []


@functools.cache
def check_refund():
    return []
'''


class ChangedChecks(unittest.TestCase):
    def leads_after(self, old, new):
        with tempfile.TemporaryDirectory() as directory:
            git(directory, "init", "-q")
            checks = Path(directory) / "harness" / "checks.py"
            checks.parent.mkdir()
            checks.write_text(old)
            git(directory, "add", ".")
            git(directory, "commit", "-qm", "first")
            checks.write_text(new)
            result = subprocess.run([sys.executable, str(SCRIPT), "--since", "HEAD"], cwd=directory, capture_output=True, text=True)
            return [line for line in result.stdout.splitlines() if line.startswith("check-changed")]

    def test_a_change_is_owned_by_the_check_whose_body_or_decorator_holds_it(self):
        cases = (
            ("    return []\n\n\nasync", '    return ["late"]\n\n\nasync', "check_order"),
            ("async def check_payment():\n    return []", "async def check_payment():\n    return [1]", "check_payment"),
            ("@functools.cache", "@functools.lru_cache", "check_refund"),
        )
        for old, new, owner in cases:
            with self.subTest(owner=owner):
                self.assertEqual(self.leads_after(CHECKS, CHECKS.replace(old, new)), [f"check-changed harness/checks.py {owner}"])

    def test_a_file_that_does_not_parse_is_flagged_for_reading_by_hand(self):
        leads = self.leads_after(CHECKS, CHECKS.replace("def check_order():", "def check_order(:"))
        self.assertEqual(leads, [
            f"check-changed harness/checks.py {weakened.UNPARSED}", "check-changed harness/checks.py check_order",
        ])


class CannotRun(unittest.TestCase):
    def run_weakened(self, cwd, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True)

    def test_stops_with_2_when_there_is_no_starting_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            git(directory, "init", "-q")
            (Path(directory) / "harness").mkdir()
            (Path(directory) / "harness" / "checks.py").write_text("def check_order():\n    return []\n")
            git(directory, "add", ".")
            git(directory, "commit", "-qm", "first")
            for args, reason in (([], "--since"), (["--since", "no-such-commit"], "no-such-commit")):
                with self.subTest(args=args):
                    result = self.run_weakened(directory, *args)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn("STOPPED:", result.stderr)
                    self.assertIn(reason, result.stderr)

    def test_stops_with_2_outside_a_git_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_weakened(directory, "--since", "HEAD")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("STOPPED:", result.stderr)


if __name__ == "__main__":
    unittest.main()
