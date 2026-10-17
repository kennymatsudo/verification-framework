import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import ledger

SCRIPT = Path(__file__).with_name("ledger.py")


class AddHelp(unittest.TestCase):
    def test_help_describes_every_field_and_verdict_add_enforces(self):
        self.assertEqual(set(ledger.FIELDS), set(ledger.REQUIRED))
        self.assertEqual(set(ledger.MEANINGS), set(ledger.VERDICTS))

    def test_help_runs_without_a_harness(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--harness", "unused", "add", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        for name in ledger.REQUIRED + ledger.VERDICTS:
            self.assertIn(name, result.stdout)


class Ledger(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.harness = Path(self.directory.name)
        (self.harness / "rules.md").write_text("")

    def tearDown(self):
        self.directory.cleanup()

    def run_ledger(self, *args):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--harness", str(self.harness), *args],
            capture_output=True, text=True,
        )
        return result.returncode, json.loads(result.stdout) if result.returncode == 0 else result.stderr

    def add(self, verdict, **extra):
        row = {
            "sweep": "2026-10-16", "hypothesis": "pay clicked twice charges once", "kind": "timing",
            "command": "scripts/explore pay-twice", "signature": ["invariant:one-payment"], "verdict": verdict,
        }
        return self.run_ledger("add", json.dumps({**row, **extra}))

    def open_rounds(self):
        _, summary = self.run_ledger("summary")
        return [finding["round"] for finding in summary["open_findings"]]

    def test_closing_a_finding_or_lead_removes_it_from_open_findings(self):
        self.add("finding")
        self.add("lead")
        self.add("finding")
        result, entry = self.run_ledger("close", "1", "2")
        self.assertEqual(result, 0, entry)
        self.assertEqual(entry["closed"], [1, 2])
        self.assertEqual(self.open_rounds(), [3])

    def test_close_line_is_not_counted_as_a_round(self):
        self.add("finding")
        self.run_ledger("close", "1")
        _, row = self.add("no-break")
        self.assertEqual(row["round"], 2)

    def test_close_refuses_a_round_that_is_not_an_open_finding_or_lead(self):
        self.add("finding")
        self.add("no-break")
        ledger_file = self.harness / "evidence" / "exploration-ledger.jsonl"
        for rounds in (["2"], ["9"], ["x"], ["1", "2"]):
            result, _ = self.run_ledger("close", *rounds)
            self.assertEqual(result, 2, rounds)
            self.assertEqual(len(ledger_file.read_text().splitlines()), 2, f"close {rounds} wrote a line")
        self.run_ledger("close", "1")
        result, error = self.run_ledger("close", "1")
        self.assertEqual(result, 2)
        self.assertIn("round 1", error)
        self.assertEqual(self.open_rounds(), [])

    def test_three_rounds_with_no_new_signature_force_a_new_approach(self):
        for _ in range(3):
            self.add("no-break")
        _, summary = self.run_ledger("summary")
        self.assertEqual(summary["rounds_since_new_signature"], 2)
        self.assertFalse(summary["must_change_approach"])
        self.add("no-break")
        _, summary = self.run_ledger("summary")
        self.assertTrue(summary["must_change_approach"])
        self.assertEqual(summary["kinds_tried"]["timing"], 4)
        self.assertEqual(summary["kinds_tried"]["order"], 0)

    def test_add_refuses_rows_summary_could_not_read(self):
        for extra, reason in (({"created_open": "o_1"}, "created_open"), ({"created_open": [1]}, "created_open")):
            with self.subTest(extra=extra):
                result, error = self.add("no-break", **extra)
                self.assertEqual(result, 2)
                self.assertIn(reason, error)
        result, error = self.run_ledger("add", "5")
        self.assertEqual(result, 2)
        self.assertIn("JSON object", error)
        self.assertEqual(self.run_ledger("summary")[1]["rounds"], 0)

    def test_planted_kind_and_planted_verdicts_go_together(self):
        for kind, verdict in (("planted", "finding"), ("planted", "no-break"), ("timing", "planted-caught")):
            with self.subTest(kind=kind, verdict=verdict):
                result, error = self.add(verdict, kind=kind)
                self.assertEqual(result, 2)
                self.assertIn("planted", error)
        result, _ = self.add("planted-caught", kind="planted")
        self.assertEqual(result, 0)
        self.assertEqual(self.run_ledger("summary")[1]["planted_caught"], "1/1")

    def test_add_refuses_an_unknown_kind(self):
        result, error = self.add("lead", kind="weather")
        self.assertEqual(result, 2)
        self.assertIn("kind must be one of timing", error)

    def test_add_keeps_the_numbering_and_line_kinds_it_owns(self):
        for field in ("round", "at", "cleaned", "closed"):
            result, error = self.add("finding", **{field: 1})
            self.assertEqual(result, 2, field)
            self.assertIn(field, error)
        _, row = self.add("finding")
        self.assertEqual(row["round"], 1)


if __name__ == "__main__":
    unittest.main()
