"""Switched breaks on the ledger practice repo (ADR 0017): one edit holds every hidden break behind a
gate, the app restarts once for all of them, and a break counts only beside a passing control on the same code.
No agent runs. Skipped when a tool the practice needs is not installed.

tests/test_practice_ledger.py runs this class, so the two never start the ledger on its one port at the same time."""

import json
import pathlib
import re
import shlex
import shutil
import sys
import tempfile
import unittest

EVALS = pathlib.Path(__file__).resolve().parent.parent / "evals"
sys.path.insert(0, str(EVALS))

from vfeval import cases, scaffold  # noqa: E402

PRACTICE = "ledger"
STATUS_LINE = re.compile(r"- ([\w.-]+): (Verified|Failed|Not verified)\. (.*)")

# Each hidden break of the practice as (switch, behavior, the line it replaces, the gated line).
GATES = [
    ("deposit", "transactions.deposit",
     '        conn.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, account_id))\n',
     '        if not _live("deposit"):\n'
     '            conn.execute("UPDATE accounts SET balance = ? WHERE id = ?", (new_balance, account_id))\n'),
    ("create", "accounts.open",
     '        account_id = cur.lastrowid\n        conn.execute("COMMIT")\n',
     '        account_id = cur.lastrowid\n        conn.execute("ROLLBACK" if _live("create") else "COMMIT")\n'),
    ("credit", "transfers.move",
     '        conn.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))\n',
     '        if not _live("credit"):\n'
     '            conn.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (amount, to_id))\n'),
    ("overdraft", "transfers.refuse-overdraft",
     '        if source["balance"] < amount:\n', '        if source["balance"] < amount and not _live("overdraft"):\n'),
    ("oldest", "statement.newest-first",
     ' WHERE account_id = ? ORDER BY id DESC",\n', ' WHERE account_id = ? ORDER BY id " + ("ASC" if _live("oldest") else "DESC"),\n'),
    ("unknown", "accounts.unknown-404",
     '    if row is None:\n        raise NotFound(account_id)\n    return dict(row)\n',
     '    if row is None:\n        if _live("unknown"):\n            return {"id": account_id, "name": "", "balance": 0}\n'
     '        raise NotFound(account_id)\n    return dict(row)\n'),
]


READS_ITS_NAME = "open({path!r}).read().strip() == name"
ONLY_TESTS_FOR_THE_FILE = "__import__('os').path.exists({path!r})"


def gate_every_break(store, switch_file, test):
    """Put every hidden break into store.py behind a gate that looks at the session's switch file on each call."""
    test = test.format(path=str(switch_file))
    text = store.read_text().replace(
        "class InsufficientFunds", f"def _live(name):\n    try:\n        return {test}\n    except OSError:\n        return False\n\n\nclass InsufficientFunds", 1)
    for _, _, old, new in GATES:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    store.write_text(text)


class SwitchedBreaks(unittest.TestCase):
    def setUp(self):
        self.practice = cases.load_practice(PRACTICE)
        gone = [tool for tool in self.practice.get("requires", []) if shutil.which(tool) is None]
        if gone:
            self.skipTest(f"{PRACTICE} needs {', '.join(gone)}")
        self.workspace = pathlib.Path(tempfile.mkdtemp(prefix="vf-switched-")) / "ws"
        self.addCleanup(shutil.rmtree, self.workspace.parent, ignore_errors=True)
        self.log = []
        scaffold.scaffold(self.practice, self.workspace, prepare="verified", log=self.log)
        self.harness = scaffold.harness_dir(self.practice, self.workspace)
        self.root = scaffold.project_root(self.practice, self.workspace)
        self.vf = f"{shlex.quote(sys.executable)} {shlex.quote(str(scaffold.framework_vf(self.practice, self.workspace)))}"
        # Forget the breaks the scaffold ran one restart at a time, so only switched breaks can earn a Verified line.
        for path in (self.harness / "evidence").glob("*/*.json"):
            if json.loads(path.read_text()).get("planned_break"):
                path.unlink()
        scaffold.start_app(self.practice, self.workspace, self.log)
        self.addCleanup(scaffold.stop_app, self.practice, self.workspace, self.log)
        self.addCleanup(self.run_vf, "break end ledger")

    def run_vf(self, arguments, expect=0):
        code, output = scaffold.shell(f"{self.vf} {arguments}", self.root, timeout=300)
        if expect is not None:
            self.assertEqual(code, expect, output)
        return output

    def verdicts(self):
        self.run_vf("status", expect=None)
        lines = (STATUS_LINE.match(line.strip()) for line in (self.harness / "status.md").read_text().splitlines())
        return {match.group(1): (match.group(2), match.group(3)) for match in lines if match}

    def session(self, test=READS_ITS_NAME):
        """Open a session and gate every break in its copy; the check commands by the gates they catch."""
        output = self.run_vf("break start ledger")
        scratch = pathlib.Path(next(line.split(" in ", 1)[1].split(",")[0].strip() for line in output.splitlines() if "uncommitted edit in" in line))
        gate_every_break(scratch / "ledger" / "store.py", re.search(r"reads (\S+) when", output).group(1), test)
        checks = {}
        for name, sub_id, _, _ in GATES:
            checks.setdefault(scaffold.proof_command(self.harness, sub_id), []).append((name, sub_id))
        return output, checks

    def switched(self, name, sub_id, command):
        return self.run_vf(f"break run ledger {shlex.quote(f'{sub_id}: switched {name}')} --switch {name} -- {self.vf} run -- {command}")

    def control(self, command):
        return self.run_vf(f"break control ledger -- {self.vf} run -- {command}")

    def test_six_breaks_share_one_restart_and_count_only_beside_a_control(self):
        targets = [sub_id for _, sub_id, _, _ in GATES]
        self.assertEqual({self.verdicts()[sub_id][0] for sub_id in targets}, {"Not verified"})

        output, checks = self.session()
        for command, gates in checks.items():
            for name, sub_id in gates:
                output += self.switched(name, sub_id, command)
        # Every switched break failed its own step, and none counts yet: nothing shows the edit is harmless when off.
        for sub_id in targets:
            kind, text = self.verdicts()[sub_id]
            self.assertEqual(kind, "Not verified", text)
            self.assertIn("no control shows the check passing", text)

        for command in checks:
            said = self.control(command)
            self.assertIn("Control recorded", said)
            output += said
        self.assertIn("discard", scaffold.shell(f"{self.vf} break run ledger 'accounts.open: x' -- true", self.root)[1])
        output += self.run_vf("break end ledger")
        # The session's own start, one restart for the edit holding all six breaks, and the end: three, where
        # one restart per break takes eight.
        self.assertEqual(len(re.findall(r"^Running: .*vf\.py start ", output, re.M)), 3, output)

        self.run_vf(f"verify {' '.join(scaffold.feature_ids(self.harness))}", expect=None)
        for name, sub_id, _, _ in GATES:
            kind, text = self.verdicts()[sub_id]
            self.assertEqual(kind, "Verified", text)
            self.assertIn(f"switched {name}", text)
        self.run_vf("validate --require-evidence")

    def test_a_gate_that_only_tests_for_the_file_fails_its_control_and_earns_nothing(self):
        # The switch file exists for the whole session, so this gate makes every break live at once.
        _, checks = self.session(test=ONLY_TESTS_FOR_THE_FILE)
        for command, gates in checks.items():
            self.assertIn("No control recorded", self.control(command))
            for name, sub_id in gates:
                self.switched(name, sub_id, command)
        self.run_vf("break end ledger")
        self.run_vf(f"verify {' '.join(scaffold.feature_ids(self.harness))}", expect=None)
        for _, sub_id, _, _ in GATES:
            self.assertEqual(self.verdicts()[sub_id][0], "Not verified")

