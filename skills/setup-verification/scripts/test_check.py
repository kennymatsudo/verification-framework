import contextlib
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("check.py")
SPEC = importlib.util.spec_from_file_location("verification_check", SCRIPT)
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)
REFERENCES = SCRIPT.resolve().parent.parent / "references"

SETTINGS = (
    "# App verification settings\n\n"
    "## Setup\n\n- Status: ready\n\n"
    "## Workflow\n\n- Requirements source: none\n\n"
    "## Repos\n\n- app: .\n\n"
    "## Commands\n\n"
    "- Start: npm run dev\n- Doctor: bin/verify doctor\n- Ready line: verify: ready\n"
    "- Probe: none yet\n"
    "- Invariants module: none yet\n- Settle signal: none\n"
)


def setup_record(name, blocker="none", next_action="none", proof="evidence/doctor.txt, 2026-10-09, app abc123"):
    return (
        f"# Results\n\n## Setup: {name}\n\n"
        "- Target: storefront\n- Findings: README.md:4 documents startup\n"
        "- Looked in: README.md and scripts/dev\n"
        f"- Blocker: {blocker}\n- Next action: {next_action}\n- Doctor proof: {proof}\n"
    )


def template(name):
    """The markdown block a reference file tells setup to copy into the harness."""
    return (REFERENCES / name).read_text().split("```markdown\n", 1)[1].split("\n```", 1)[0] + "\n"


def fill(text, harness):
    """A template with every slot filled the way a ready harness fills it."""
    text = text.replace("<harness directory name>", harness.name).replace("- Status: incomplete", "- Status: ready")
    text = re.sub(r"^(- (?:Blocker|Next action): ).*$", r"\1none", text, flags=re.M)
    while (filled := re.sub(r"<[^<>]*>", "filled", text)) != text:
        text = filled
    return text


def labels(text, section):
    _, body = check.sections(text)
    return [match.group(1) for line in body[section] if (match := check.SETTING.match(line))]


def make_harness(root):
    harness = root / ".agents" / "skills" / "verify-app"
    (harness / "features").mkdir(parents=True)
    (harness / "evidence").mkdir()
    (harness / "tools.md").write_text("# App tools\n")
    (harness / "status.md").write_text(setup_record(harness.name))
    (harness / "settings.md").write_text(SETTINGS)
    (harness / "features" / "README.md").write_text(
        "# Map\n\nRead [results](../status.md).\n\n## Features\n"
    )
    return harness


def run_check(harness, *flags):
    output = io.StringIO()
    with patch.object(sys, "argv", [str(SCRIPT), str(harness), *flags]), contextlib.redirect_stdout(output):
        result = check.main()
    return result, output.getvalue()


class FeatureIndexTest(unittest.TestCase):
    def test_status_link_is_not_a_feature_and_broken_links_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            features = harness / "features"
            (features / "README.md").write_text(
                "# Map\n\nRead [status](../status.md).\n\n"
                "## Baseline\n\nReady.\n\n## Features\n\n"
                "- [Checkout](checkout.md): pay.\n"
            )
            (features / "checkout.md").write_text(
                "# Checkout\n\n## Sub-features\n\n"
                "- checkout.pay: a paid order appears.\n\n"
                "## How a user reaches it\n\n- Checkout button.\n\n"
                "## How to prove it\n\n- checkout.pay: No check yet.\n\n"
                "## Gotchas\n\nNone.\n"
            )
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("1 features, 1 sub-features", output)

            (features / "README.md").write_text(
                "# Map\n\nRead [results](../results.md).\n\n## Features\n\n"
                "- [Checkout](checkout.md): pay.\n"
            )
            result, output = run_check(harness)
            self.assertEqual(result, 1)
            self.assertIn("README.md links ../results.md, which does not exist", output)


class FeatureSectionsTest(unittest.TestCase):
    def test_gotchas_is_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            features = harness / "features"
            (features / "README.md").write_text(
                "# Map\n\nRead [results](../status.md).\n\n## Features\n\n"
                "- [Checkout](checkout.md): pay.\n"
            )
            (features / "checkout.md").write_text(
                "# Checkout\n\n## Sub-features\n\n"
                "- checkout.pay: a paid order appears.\n\n"
                "## How a user reaches it\n\n- Checkout button.\n\n"
                "## Verification plan\n\nSource: launch checklist.\n\n"
                "## How to prove it\n\n- checkout.pay: No check yet.\n"
            )
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)

    def test_feature_accepts_verification_plan_without_relaxing_proof_requirements(self):
        with tempfile.TemporaryDirectory() as directory:
            feature = Path(directory) / "checkout.md"
            text = (
                "# Checkout\n\n## Sub-features\n\n- checkout.pay: an order is paid.\n\n"
                "## How a user reaches it\n\n- Checkout API.\n\n"
                "## Verification plan\n\nSource: launch requirements.\n"
                "Submit checkout and read matching order/payment. UI excluded.\n\n"
                "## How to prove it\n\n- checkout.pay: No check yet.\n\n"
                "## Gotchas\n\nNone.\n"
            )
            feature.write_text(text)
            errors = []
            check.check_feature(feature, Path(directory), {}, errors)
            self.assertEqual(errors, [])
            feature.write_text(text.replace("- checkout.pay: No check yet.\n", ""))
            errors = []
            check.check_feature(feature, Path(directory), {}, errors)
            self.assertIn("checkout.md: checkout.pay has no line under 'How to prove it'", errors)


class AppSettingsTest(unittest.TestCase):
    def test_settings_need_every_label_filled(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            unfilled = SETTINGS.replace("- Doctor: bin/verify doctor\n", "").replace(
                "verify: ready", "<ready line>"
            )
            (harness / "settings.md").write_text(unfilled)
            result, output = run_check(harness)
            self.assertEqual(result, 1)
            self.assertIn("settings.md: no '- Doctor: <value>' line under '## Commands'", output)
            self.assertIn("settings.md: Ready line still has an unfilled slot: <ready line>", output)

    def test_settings_require_code_repos(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            settings = harness / "settings.md"
            settings.write_text(SETTINGS.replace("## Repos\n\n- app: .\n\n", ""))
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("no '## Repos' section", output)


class TemplateTest(unittest.TestCase):
    def test_templates_carry_exactly_the_labels_check_reads(self):
        for section, expected in check.SETTINGS.items():
            self.assertEqual(labels(template("settings.md"), section), expected)
        for name in ("status.md", "setup.md"):
            with self.subTest(template=name):
                self.assertEqual(labels(template(name), "Setup: <harness directory name>"), check.SETUP_LABELS)

    def test_filled_templates_pass(self):
        for record in ("status.md", "setup.md"):
            with self.subTest(record=record), tempfile.TemporaryDirectory() as directory:
                harness = make_harness(Path(directory))
                (harness / "settings.md").write_text(fill(template("settings.md"), harness))
                (harness / "status.md").write_text(fill(template(record), harness))
                result, output = run_check(harness)
                self.assertEqual(result, 0, output)


class SetupTest(unittest.TestCase):
    def test_incomplete_setup_stops_before_missing_commands_or_map(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "verify-app"
            harness.mkdir()
            (harness / "settings.md").write_text("# Settings\n\n## Setup\n\n- Status: incomplete\n")
            (harness / "status.md").write_text(setup_record(
                harness.name,
                blocker="operator login is unavailable",
                next_action="user starts storefront with the documented login",
                proof="not run because login is unavailable",
            ))
            result, output = run_check(harness)
            self.assertEqual(result, 2, output)
            self.assertIn("operator login is unavailable", output)
            self.assertIn("Next action: user starts storefront", output)
            self.assertNotIn("no feature index", output)

    def test_ready_setup_requires_proof_and_allows_zero_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "status.md").write_text(setup_record(harness.name, proof="not run"))
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("ready setup needs doctor proof", output)

            (harness / "status.md").write_text(setup_record(harness.name))
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("0 features, 0 sub-features", output)

    def test_setup_rejects_missing_status_or_unusable_resume_record(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "verify-app"
            harness.mkdir()
            settings = "## Setup\n\n- Status: incomplete\n"
            cases = (
                (None, None, "settings.md is missing"),
                ("## Workflow\n", None, "Status must be incomplete or ready"),
                (settings.replace("incomplete", "unknown"), None, "Status must be incomplete or ready"),
                (settings, None, "setup results cannot be read"),
                (settings, "# Results\n", "section for this harness"),
                (settings, f"## Setup: {harness.name}\n\n- Target: storefront\n", "Setup needs a filled Next action line"),
                (settings, f"## Setup: {harness.name}\n\n- Next action: none\n", "incomplete setup needs a Next action"),
            )
            for settings_text, record, expected in cases:
                with self.subTest(expected=expected):
                    for name, text in (("settings.md", settings_text), ("status.md", record)):
                        path = harness / name
                        if text is None:
                            path.unlink(missing_ok=True)
                        else:
                            path.write_text(text)
                    result, output = run_check(harness)
                    self.assertEqual(result, 1, output)
                    self.assertIn(expected, output)


class HarnessLayoutTest(unittest.TestCase):
    def test_harness_files_are_used_even_when_project_has_other_homes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "features").mkdir()
            (root / "features" / "README.md").write_text("# Unrelated project map\n")
            harness = make_harness(root)
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("0 features, 0 sub-features", output)

            path = harness / "tools.md"
            path.rename(harness / "tools.saved")
            result, output = run_check(harness)
            (harness / "tools.saved").rename(path)
            self.assertEqual(result, 1, output)
            self.assertIn("tools.md is missing", output)

            (harness / "evidence").rmdir()
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn(f"WARN no evidence directory at {harness / 'evidence'}", output)

    def test_checks_local_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "scripts").mkdir()
            (harness / "scripts" / "pay").write_text("# checkout check\n")
            (harness / "features" / "README.md").write_text(
                "# Map\n\n## Features\n\n- [Checkout](checkout.md)\n"
            )
            (harness / "features" / "checkout.md").write_text(
                "# Checkout\n\n## Sub-features\n\n- checkout.pay: order is paid.\n\n"
                "## How a user reaches it\n\n- Checkout button.\n\n"
                "## How to prove it\n\n- checkout.pay: `./scripts/pay`. "
                "Break-tested 2026-10-09: payment capture skipped.\n\n"
                "## Gotchas\n\nNone.\n"
            )
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("no passing evidence for checkout.pay", output)


class VerifiedResultsTest(unittest.TestCase):
    COMMIT = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
    LINE = "- checkout.pay: Verified. scripts/pay, lane 2, checkout API, app a1b2c3d. Evidence: evidence/pay.json\n"

    BREAK = "Break-tested 2026-10-09: payment capture skipped. Evidence: evidence/pay-break.json"
    STEP = {"name": "checkout.pay: order is paid", "passed": True, "at": 21.4}

    def make_verified_harness(self, root, proof=BREAK):
        harness = make_harness(root)
        (harness / "scripts").mkdir()
        (harness / "scripts" / "pay").write_text("# checkout check\n")
        (harness / "features" / "README.md").write_text("# Map\n\n## Features\n\n- [Checkout](checkout.md)\n")
        (harness / "features" / "checkout.md").write_text(
            "# Checkout\n\n## Sub-features\n\n- checkout.pay: order is paid.\n- checkout.refund: order is refunded.\n\n"
            "## How a user reaches it\n\n- Checkout button.\n\n"
            f"## How to prove it\n\n- checkout.pay: `./scripts/pay`. {proof}\n- checkout.refund: No check yet.\n\n"
            "## Gotchas\n\nNone.\n"
        )
        self.write_evidence(harness)
        self.write_break(harness)
        return harness

    def write_break(self, harness, **changes):
        record = {
            "check": "checkout-pay",
            "sub_features": ["checkout.pay"],
            "passed": False,
            "code": {"app": {"commit": self.COMMIT, "dirty": True}},
            "steps": [dict(self.STEP, passed=False)],
        }
        record.update(changes)
        (harness / "evidence" / "pay-break.json").write_text(json.dumps(record))

    def write_evidence(self, harness, **changes):
        record = {
            "check": "checkout-pay",
            "sub_features": ["checkout.pay"],
            "passed": True,
            "code": {"app": {"commit": self.COMMIT, "dirty": False}},
            "finished_at": "2026-10-13T14:02:40Z",
            "steps": [self.STEP],
        }
        record.update(changes)
        (harness / "evidence" / "pay.json").write_text(json.dumps(record))

    def write_results(self, harness, *lines):
        (harness / "status.md").write_text(setup_record(harness.name) + "\n## Latest results\n\n" + "".join(lines))

    def test_verified_line_backed_by_passing_break_tested_evidence_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            self.write_results(
                harness,
                self.LINE,
                "- checkout.refund: Not verified. No check yet.\n",
                "- checkout.pay: Failed. Step 'order is paid' read status=pending.\n",
            )
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 0, output)
            self.assertNotIn("status.md", output)

    def test_break_evidence_in_backticks_is_found_in_the_harness(self):
        """The cited break is a path from the harness, not a command run from the repo root."""
        with tempfile.TemporaryDirectory() as directory:
            # A real repo with the harness nested in it, so commands resolve from the repo root.
            subprocess.run(["git", "init", "-q", directory], check=True)
            proof = self.BREAK.replace("evidence/pay-break.json", "`evidence/pay-break.json`")
            harness = self.make_verified_harness(Path(directory), proof=proof)
            feature = harness / "features" / "checkout.md"
            feature.write_text(feature.read_text().replace("`./scripts/pay`", "`.agents/skills/verify-app/scripts/pay`"))
            self.write_results(harness, self.LINE)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 0, output)

    def test_verified_line_contradicted_by_evidence_or_map_fails(self):
        cases = (
            ({"passed": False}, None, None, "did not pass"),
            ({"passed": None}, None, None, "did not pass"),
            ({"sub_features": ["checkout.refund"]}, None, None, "does not cover it"),
            ({"code": {"app": {"commit": "ffffffffffffffff"}}}, None, None, "does not name app fffffff"),
            ({"code": {"app": {"commit": self.COMMIT}, "worker": {"commit": "0123456789ab"}}}, None, None, "does not name worker 0123456"),
            ({}, "Not break-tested: no scratch copy yet.", None, "its check is not break-tested"),
            ({"sub_features": ["checkout.refund"]}, None, self.LINE.replace("checkout.pay", "checkout.refund"), "the map has no check for it"),
            ({}, None, self.LINE.replace(" Evidence: evidence/pay.json", ""), "without 'Evidence: <file>.json'"),
        )
        for evidence, proof, line, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory), **({"proof": proof} if proof else {}))
                self.write_evidence(harness, **evidence)
                self.write_results(harness, line or self.LINE)
                result, output = run_check(harness)
                self.assertEqual(result, 1, output)
                self.assertIn(expected, output)

    def test_verified_line_needs_a_break_whose_failed_steps_still_run(self):
        cases = (
            ({}, {}, None, None),
            ({"steps": [self.STEP, {"name": "receipt is sent", "passed": True, "at": 30.0}]}, {}, None, None),
            ({"steps": [{"name": "order is paid in full", "passed": True, "at": 21.4}]}, {}, None,
             "step 'checkout.pay: order is paid' failed in its planned break but is not in this run"),
            ({}, {"passed": True}, None, "its planned break in evidence/pay-break.json did not fail"),
            ({}, {"steps": [dict(self.STEP)]}, None, "its planned break in evidence/pay-break.json failed no step"),
            ({}, {"sub_features": ["checkout.refund"]}, None, "its planned break in evidence/pay-break.json does not cover it"),
            ({}, {}, "Break-tested 2026-10-09: payment capture skipped.", "its break-test cites no evidence"),
        )
        for evidence, broken, proof, expected in cases:
            with self.subTest(expected=expected, evidence=evidence), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory), **({"proof": proof} if proof else {}))
                self.write_evidence(harness, **evidence)
                self.write_break(harness, **broken)
                self.write_results(harness, self.LINE)
                result, output = run_check(harness, "--require-evidence")
                if expected is None:
                    self.assertEqual(result, 0, output)
                else:
                    self.assertEqual(result, 1, output)
                    self.assertIn(expected, output)

        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            (harness / "evidence" / "pay-break.json").unlink()
            self.write_results(harness, self.LINE)
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("WARN status.md: checkout.pay is Verified, but its planned break evidence/pay-break.json is not here", output)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)

    def test_evidence_that_is_not_a_json_object_is_reported_not_a_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            (harness / "evidence" / "notes.json").write_text("[]")
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)

            for cited, expected in (("pay.json", "evidence/pay.json is not"), ("pay-break.json", "its planned break evidence/pay-break.json is not")):
                with self.subTest(cited=cited):
                    self.write_evidence(harness)
                    self.write_break(harness)
                    (harness / "evidence" / cited).write_text("[]")
                    self.write_results(harness, self.LINE)
                    result, output = run_check(harness, "--require-evidence")
                    self.assertEqual(result, 1, output)
                    self.assertIn(f"ERROR status.md: checkout.pay is Verified, but {expected} a readable JSON object", output)

    def test_break_tested_proof_needs_a_date(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory), proof=self.BREAK.replace(" 2026-10-09:", ":"))
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("checkout.pay check does not say 'Break-tested <date>: ...'", output)

    def test_missing_cited_evidence_warns_unless_required(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            (harness / "evidence" / "pay.json").unlink()
            self.write_results(harness, self.LINE)
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("WARN status.md: checkout.pay is Verified, but evidence/pay.json is not here", output)

            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)
            self.assertIn("ERROR status.md: checkout.pay is Verified, but evidence/pay.json is not here", output)


    def test_cited_evidence_needs_step_times_and_a_recording_inside_evidence(self):
        step = {"name": "order is paid", "passed": True, "at": 21.4}
        cases = (
            ({"steps": [{"name": "order is paid", "passed": True}]}, "has steps with no 'at' time: order is paid"),
            ({"steps": [dict(step, at=-1)]}, "has steps with no 'at' time"),
            ({"recording": {"video": "../video.webm", "starts_at": 0}}, "by a path inside evidence/"),
            ({"recording": {"video": "/tmp/video.webm", "starts_at": 0}}, "by a path inside evidence/"),
            ({"recording": {"video": "pay/video.webm"}}, "does not say when its recording starts"),
        )
        for evidence, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                self.write_evidence(harness, **evidence)
                self.write_results(harness, self.LINE)
                result, output = run_check(harness)
                self.assertEqual(result, 1, output)
                self.assertIn(expected, output)

    def test_missing_recording_warns_unless_required(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            recording = {"video": "pay/video.webm", "starts_at": 2.1}
            self.write_evidence(harness, steps=[self.STEP], recording=recording)
            self.write_results(harness, self.LINE)
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("WARN status.md: checkout.pay is Verified, but its recording pay/video.webm is not here", output)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)

            (harness / "evidence" / "pay").mkdir()
            (harness / "evidence" / "pay" / "video.webm").write_bytes(b"webm")
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 0, output)
            self.assertNotIn("recording", output)


class MultiRepoTest(unittest.TestCase):
    def test_evidence_names_each_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            worker = Path(directory) / "worker"
            for path in (project, worker):
                path.mkdir()
                subprocess.run(["git", "init", "-q", str(path)], check=True)
            harness = make_harness(project)
            (project / "local-dev").mkdir()
            (project / "local-dev" / ".env").write_text(f"WORKER={worker}\n")
            (harness / "scripts").mkdir()
            (harness / "scripts" / "checkout").write_text("# checkout check\n")
            (harness / "features" / "README.md").write_text("# Features\n\n## Features\n\n- [Checkout](checkout.md)\n")
            (harness / "features" / "checkout.md").write_text(
                "# Checkout\n\n## Sub-features\n\n- checkout.pay: order is paid.\n\n"
                "## How a user reaches it\n\n- Checkout button.\n\n"
                "## How to prove it\n\n- checkout.pay: `.agents/skills/verify-app/scripts/checkout`. "
                "Break-tested 2026-10-09: payment capture skipped.\n\n"
                "## Gotchas\n\nNone.\n"
            )
            (harness / "settings.md").write_text(SETTINGS.replace(
                "- app: .\n", "- project: .\n- worker: env:local-dev/.env:WORKER\n"
            ))
            for path in (project, worker):
                (path / "version.txt").write_text("first\n")
                subprocess.run(["git", "-C", str(path), "add", "version.txt"], check=True)
                subprocess.run(
                    ["git", "-C", str(path), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "first"],
                    check=True,
                )
            commits = {
                name: subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
                for name, path in (("project", project), ("worker", worker))
            }
            commits["project"] = commits["project"][:11]
            evidence = harness / "evidence" / "checkout.json"
            evidence.write_text(json.dumps({
                "passed": True,
                "sub_features": ["checkout.pay"],
                "finished_at": "2026-10-09T12:00:00Z",
                "code": {name: {"commit": commit, "dirty": False} for name, commit in commits.items()},
            }))
            (worker / "version.txt").write_text("second\n")
            subprocess.run(["git", "-C", str(worker), "add", "version.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(worker), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "second"],
                check=True,
            )

            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("worker last pass is 1 commit behind HEAD for checkout.pay", output)
            self.assertNotIn("project last pass", output)

            evidence.write_text(json.dumps({
                "passed": True,
                "sub_features": ["checkout.pay"],
                "finished_at": "2026-10-09T12:00:00Z",
                "code": {"project": {"commit": commits["project"], "dirty": False}},
            }))
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("worker last pass ran on an unknown commit", output)

    def test_each_repo_is_looked_up_once_however_many_checks_it_backs(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            (evidence / "run.json").write_text(json.dumps({
                "passed": True, "sub_features": ["checkout.pay", "checkout.refund"], "code": {"app": {"commit": "abc1234"}},
            }))
            proofs = {"checkout.pay": "`./scripts/pay`", "checkout.refund": "`./scripts/refund`"}
            with patch.object(check, "resolve_repo", return_value=None) as resolve:
                warnings = check.evidence_warnings(evidence, proofs, evidence, {"app": "."})
            self.assertEqual(resolve.call_count, 1)
            self.assertEqual(warnings, ["app checkout cannot be found from settings.md for checkout.pay, checkout.refund"])

    def test_uncommitted_code_ignores_the_harness_and_warns_once_per_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            (project / "app.txt").write_text("first\n")
            subprocess.run(["git", "-C", str(project), "add", "app.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(project), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "first"],
                check=True,
            )
            commit = subprocess.check_output(["git", "-C", str(project), "rev-parse", "HEAD"], text=True).strip()
            harness = make_harness(project)
            (harness / "scripts").mkdir()
            (harness / "scripts" / "checkout").write_text("# checkout check\n")
            (harness / "features" / "README.md").write_text("# Features\n\n## Features\n\n- [Checkout](checkout.md)\n")
            (harness / "features" / "checkout.md").write_text(
                "# Checkout\n\n## Sub-features\n\n- checkout.pay: order is paid.\n- checkout.refund: order is refunded.\n\n"
                "## How a user reaches it\n\n- Checkout button.\n\n"
                "## How to prove it\n\n"
                "- checkout.pay: `.agents/skills/verify-app/scripts/checkout`. Break-tested 2026-10-09: capture skipped.\n"
                "- checkout.refund: `.agents/skills/verify-app/scripts/checkout`. Break-tested 2026-10-09: refund skipped.\n"
            )
            (harness / "evidence" / "checkout.json").write_text(json.dumps({
                "passed": True,
                "sub_features": ["checkout.pay", "checkout.refund"],
                "finished_at": "2026-10-09T12:00:00Z",
                "code": {"app": {"commit": commit, "dirty": True}},
            }))

            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertNotIn("has uncommitted code now", output)
            self.assertEqual(output.count("app last pass used uncommitted code"), 1, output)
            self.assertIn("app last pass used uncommitted code for checkout.pay, checkout.refund", output)

            (project / "app.txt").write_text("edited\n")
            (project / "new_module.txt").write_text("new\n")
            result, output = run_check(harness)
            self.assertIn("app checkout has uncommitted code now: app.txt, new_module.txt", output)


if __name__ == "__main__":
    unittest.main()
