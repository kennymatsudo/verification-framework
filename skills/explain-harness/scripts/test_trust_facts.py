import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("trust_facts.py")
SPEC = importlib.util.spec_from_file_location("trust_facts", SCRIPT)
trust_facts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trust_facts)

VALIDATE = Path(__file__).resolve().parents[2] / "setup-verification" / "scripts" / "validate.py"

FEATURE = """# Checkout

A shopper pays.

## Sub-features

- checkout.pay: paying creates a paid order.
- checkout.saved-card: a returning shopper pays with a saved card.
- checkout.receipt: a receipt is queued.
- checkout.retry: a declined card can be retried.
- checkout.refund: a refund returns the money.

## How a user reaches it

- `POST /api/checkout`.

## Verification plan

Source: README.

- checkout.pay: submit checkout through the API; read the order row.

## How to prove it

- checkout.pay: `bin/check pay`. Reads the order row (state). Break-tested 2026-10-03: capture skipped. Evidence: evidence/pay/break-pay.json
- checkout.saved-card: `bin/check saved`. Reads the order row (state). Break-tested 2026-10-03: saved card ignored. Evidence: evidence/pay/gone.json
- checkout.receipt: `bin/check receipt`. Reads the outbox (state). Not break-tested: no way to stop the worker yet.
- checkout.retry: Unreachable: the sandbox has no declining card. Tried card 4000.
- checkout.refund: No check yet.
"""

STATUS = """# Verification status

## Where a pass can mislead

- checkout.pay: a pass shows the stored order, not the confirmation screen.
- passes ran with an uncommitted README.

## Untested cases

- Two payments at once.

## Latest results

- checkout.pay: Verified. bin/check pay, app {commit}. Evidence: evidence/pay/pass-pay.json
- checkout.refund: Not verified. No check yet.
"""


def git(path, *args):
    return subprocess.run(
        ["git", "-C", str(path), "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


class TrustFacts(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        git(self.repo, "init", "-q", "-b", "main")
        (self.repo / "app.txt").write_text("one\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "one")
        self.tested = git(self.repo, "rev-parse", "HEAD")
        (self.repo / "app.txt").write_text("two\n")
        git(self.repo, "commit", "-qam", "two")

        self.harness = self.repo / ".agents" / "skills" / "verify-shop"
        (self.harness / "scripts" / "framework").mkdir(parents=True)
        (self.harness / "features").mkdir()
        (self.harness / "evidence" / "pay").mkdir(parents=True)
        shutil.copy(VALIDATE, self.harness / "scripts" / "framework" / "validate.py")
        (self.harness / "settings.md").write_text("# Settings\n\n## Repos\n\n- app: .\n")
        (self.harness / "features" / "README.md").write_text("# Map\n\n## Features\n\n- [Checkout](checkout.md): pay.\n")
        (self.harness / "features" / "checkout.md").write_text(FEATURE)
        (self.harness / "status.md").write_text(STATUS.format(commit=self.tested[:7]))
        self.write_evidence("break-pay.json", passed=False, steps=[
            {"name": "order is created", "passed": True}, {"name": "order is paid", "passed": False}], planned_break=self.AIMED_AT_PAY)
        self.write_evidence("pass-pay.json", passed=True, steps=[{"name": "order is paid", "passed": True}])

    AIMED_AT_PAY = {"what": "capture skipped", "sub_features": ["checkout.pay"]}

    def write_evidence(self, name, passed, steps, planned_break=None):
        record = {"check": "pay", "planned_break": planned_break, "sub_features": ["checkout.pay"], "passed": passed, "reads": "state",
                  "code": {"app": {"commit": self.tested, "dirty": True, "dirty_hash": "d" * 64, "dirty_files": ["README.md"], "on_main": True}},
                  "finished_at": "2026-10-03T14:02:40Z", "steps": steps}
        (self.harness / "evidence" / "pay" / name).write_text(json.dumps(record))

    def behaviors(self):
        return {b["id"]: b for b in trust_facts.gather(self.harness)["behaviors"]}

    def test_break_that_failed_a_step_counts_as_caught(self):
        pay = self.behaviors()["checkout.pay"]
        self.assertEqual(pay["break"]["what"], "capture skipped")
        self.assertEqual(pay["break"]["failed_steps"], ["order is paid"])
        self.assertEqual(pay["plan"], "submit checkout through the API; read the order row.")
        self.assertEqual(pay["reads"], "Reads the order row (state).")

    def test_break_whose_evidence_is_missing_is_not_counted_as_caught(self):
        saved = self.behaviors()["checkout.saved-card"]
        self.assertFalse(saved["break"]["on_hand"])
        self.assertEqual(trust_facts.gather(self.harness)["tally"]["break_not_on_hand"], 1)

    def test_break_that_failed_no_step_is_not_counted_as_caught(self):
        self.write_evidence("break-pay.json", passed=False, steps=[{"name": "order is paid", "passed": True}],
                            planned_break=self.AIMED_AT_PAY)
        self.assertEqual(self.behaviors()["checkout.pay"]["break"]["failed_steps"], [])
        self.assertEqual(trust_facts.gather(self.harness)["tally"]["caught_a_break"], 0)

    def test_break_aimed_at_another_behavior_is_not_counted_as_caught(self):
        self.write_evidence("break-pay.json", passed=False, steps=[{"name": "order is paid", "passed": False}],
                            planned_break={"what": "card lookup skipped", "sub_features": ["checkout.saved-card"]})
        pay = self.behaviors()["checkout.pay"]
        self.assertEqual(pay["break"]["failed_steps"], [])
        self.assertEqual(trust_facts.caught_cell(pay), "Break on 2026-10-03 was aimed at something else: capture skipped")
        self.assertEqual(trust_facts.gather(self.harness)["tally"]["caught_a_break"], 0)

    def test_each_kind_of_proof_is_tallied(self):
        tally = trust_facts.gather(self.harness)["tally"]
        self.assertEqual(
            {k: tally[k] for k in ("behaviors", "checked", "caught_a_break", "never_broken", "no_check", "unreachable")},
            {"behaviors": 5, "checked": 3, "caught_a_break": 1, "never_broken": 1, "no_check": 1, "unreachable": 1},
        )
        receipt = self.behaviors()["checkout.receipt"]
        self.assertEqual(receipt["not_break_tested"], "no way to stop the worker yet.")

    def test_result_reports_how_far_its_commit_is_behind_head(self):
        result = self.behaviors()["checkout.pay"]["result"]
        self.assertEqual(result["verdict"], "Verified")
        self.assertEqual(result["code"]["app"]["behind_head"], 1)
        self.assertEqual(result["code"]["app"]["dirty_files"], ["README.md"])
        self.assertEqual(result["code"]["app"]["dirty_hash"], "d" * 64)
        tally = trust_facts.gather(self.harness)["tally"]
        self.assertEqual((tally["verified"], tally["not_verified"], tally["no_result"], tally["behind_head"]), (1, 1, 3, 1))

    def test_result_finds_checkout_from_monorepo_env_locator(self):
        project = self.repo / "shop"
        project.mkdir()
        shutil.move(str(self.repo / ".agents"), str(project / ".agents"))
        self.harness = project / ".agents" / "skills" / "verify-shop"
        (project / "local-dev").mkdir()
        (project / "local-dev" / ".env").write_text("APP=.\n")
        (self.harness / "settings.md").write_text("# Settings\n\n## Repos\n\n- app: env:local-dev/.env:APP\n")

        result = self.behaviors()["checkout.pay"]["result"]

        self.assertEqual(result["code"]["app"]["behind_head"], 1)

    def test_last_result_line_wins_even_when_it_cites_an_older_run(self):
        self.write_evidence("old-pay.json", passed=True, steps=[{"name": "order is paid", "passed": True}])
        old = json.loads((self.harness / "evidence" / "pay" / "old-pay.json").read_text())
        old["finished_at"], old["passed"] = "2026-10-01T09:00:00Z", False
        (self.harness / "evidence" / "pay" / "old-pay.json").write_text(json.dumps(old))
        with (self.harness / "status.md").open("a") as status:
            status.write("\nEarlier run:\n\n- checkout.pay: Failed. Evidence: evidence/pay/old-pay.json\n")
        result = self.behaviors()["checkout.pay"]["result"]
        self.assertEqual((result["verdict"], result["evidence"]), ("Failed", "evidence/pay/old-pay.json"))

    def test_later_result_without_evidence_supersedes_a_timestamped_pass(self):
        for verdict in ("Not verified", "Failed"):
            with self.subTest(verdict=verdict):
                (self.harness / "status.md").write_text(STATUS.format(commit=self.tested[:7]) +
                    f"\n- checkout.pay: {verdict}. App unavailable.\n")
                result = self.behaviors()["checkout.pay"]["result"]
                self.assertEqual(result["verdict"], verdict)
                self.assertIsNone(result["evidence"])
                self.assertEqual(trust_facts.gather(self.harness)["tally"]["verified"], 0)

    def test_caveats_attach_to_their_behavior(self):
        facts = trust_facts.gather(self.harness)
        pay = {b["id"]: b for b in facts["behaviors"]}["checkout.pay"]
        self.assertEqual(pay["caveats"], ["a pass shows the stored order, not the confirmation screen."])
        self.assertEqual(facts["may_mislead"], ["passes ran with an uncommitted README."])
        self.assertEqual(facts["untested"], ["Two payments at once."])

    def test_page_escapes_harness_text(self):
        (self.harness / "features" / "checkout.md").write_text(FEATURE.replace("paying creates", "<b>paying</b> creates"))
        page = trust_facts.render_html(trust_facts.gather(self.harness))
        self.assertIn("&lt;b&gt;paying&lt;/b&gt; creates", page)
        self.assertIn("Failed when we broke it (2026-10-03): capture skipped", page)

    def test_stops_without_the_harness_check_script(self):
        (self.harness / "scripts" / "framework" / "validate.py").unlink()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), patch("sys.argv", ["trust_facts.py", str(self.harness)]):
            self.assertEqual(trust_facts.main(), 2)
        self.assertIn("STOPPED:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
