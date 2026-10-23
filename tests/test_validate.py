import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"


SCRIPT = SCRIPTS / "validate.py"
SPEC = importlib.util.spec_from_file_location("verification_validate", SCRIPT)
validate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validate)
REFERENCES = SCRIPTS.parent / "references"

SETTINGS = (
    "# App verification settings\n\n"
    "## Setup\n\n- Status: ready\n\n"
    "## Workflow\n\n- Requirements source: none\n\n"
    "## Repos\n\n- app: .\n\n"
    "## Commands\n\n"
    "- Start: npm run dev\n- Stop: npm run stop\n- Doctor: bin/verify doctor\n- Ready line: verify: ready\n"
    "- Probe: none yet\n"
    "- Run scratch code: per check\n- After an edit: reloads\n"
)


def setup_record(name, blocker="none", next_action="none", proof="evidence/doctor/2026-10-09T10-00-00Z.txt, 2026-10-09, app abc123"):
    return (
        f"# Notes\n\n## Setup: {name}\n\n"
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
    _, body = validate.sections(text)
    return [match.group(1) for line in body[section] if (match := validate.SETTING.match(line))]


def lock_rules(harness):
    """Record the rules hash the way vf.py sync does."""
    lock = harness / validate.FRAMEWORK_LOCK
    lock.parent.mkdir(parents=True, exist_ok=True)
    digest = validate.rules_sha256((harness / "rules.md").read_bytes().replace(b"\r\n", b"\n"))
    lock.write_text(f"{digest}  rules.md\n")


def make_harness(root):
    harness = root / ".agents" / "skills" / "verify-app"
    (harness / "features").mkdir(parents=True)
    (harness / "evidence" / "checkout-pay").mkdir(parents=True)
    shutil.copy(REFERENCES / "rules.md", harness / "rules.md")
    lock_rules(harness)
    (harness / "tools.md").write_text("# App tools\n")
    (harness / "README.md").write_text("# Verify app\n")
    (harness / "notes.md").write_text(setup_record(harness.name))
    (harness / "status.md").write_text("# Verification status\n\n## Latest results\n\nNo behaviors in the feature map yet.\n")
    (harness / "settings.md").write_text(SETTINGS)
    (harness / "features" / "README.md").write_text(
        "# Map\n\nRead [results](../status.md).\n\n## Features\n"
    )
    return harness


def run_check(harness, *flags):
    output = io.StringIO()
    with patch.object(sys, "argv", [str(SCRIPT), str(harness), *flags]), contextlib.redirect_stdout(output):
        result = validate.main()
    return result, output.getvalue()


class RulesCopyTest(unittest.TestCase):
    def test_a_harness_with_no_recorded_rules_hash_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / validate.FRAMEWORK_LOCK).unlink()
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("framework.sha256 has no entry for rules.md; run vf", output)

    def test_edited_or_other_version_rules_fail_before_the_setup_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "settings.md").write_text(SETTINGS.replace("Status: ready", "Status: incomplete"))
            rules = harness / "rules.md"
            original = rules.read_text()

            rules.write_text(original.replace("unchanged", "as you see fit", 1))
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("rules.md differs from the copy vf last synced", output)
            self.assertNotIn("STOPPED", output)

            rules.write_text(re.sub(r"Rules version: \S+", "Rules version: 0", original, count=1))
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("rules.md differs from the copy vf last synced", output)

            rules.write_bytes(original.encode().replace(b"\n", b"\r\n"))
            self.assertIn(b"\r\n", rules.read_bytes())
            result, output = run_check(harness)
            self.assertNotIn("rules.md", output)


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
            validate.check_feature(feature, Path(directory), {}, errors)
            self.assertEqual(errors, [])
            feature.write_text(text.replace("- checkout.pay: No check yet.\n", ""))
            errors = []
            validate.check_feature(feature, Path(directory), {}, errors)
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
        for section, expected in validate.SETTINGS.items():
            self.assertEqual(labels(template("settings.md"), section), expected)
        self.assertEqual(labels(template("notes.md"), "Setup: <harness directory name>"), validate.SETUP_LABELS)

    def test_filled_templates_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "settings.md").write_text(fill(template("settings.md"), harness))
            (harness / "notes.md").write_text(fill(template("notes.md"), harness))
            (harness / "tools.md").write_text(fill(template("tool-guide.md"), harness))
            (Path(directory) / "filled").mkdir()
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)


def tool_entry(command="scripts/probe order --help", run_from="the project root", skip=None):
    lines = [
        "## Look up an order", "", "Use when: you need an order's state.", "", f"Run from {run_from}:", "",
        "`scripts/probe order o_1`", "",
        *(f"- {field}: filled." for field in validate.TOOL_FIELDS if field != skip), "",
        f"Help: `{command}`.",
    ]
    return "# App tools\n\n" + "\n".join(lines) + "\n"


class ToolGuideTest(unittest.TestCase):
    def make_tool(self, root, body="#!/bin/sh\necho usage\n"):
        script = root / "scripts" / "probe"
        script.parent.mkdir()
        script.write_text(body)
        script.chmod(0o755)

    def test_a_complete_entry_with_a_working_help_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            self.make_tool(Path(directory))
            (harness / "tools.md").write_text(tool_entry())
            result, output = run_check(harness, "--run-help")
            self.assertEqual(result, 0, output)

    def test_an_entry_missing_a_field_or_its_script_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "tools.md").write_text(tool_entry(skip="Limits"))
            result, output = run_check(harness)
            self.assertEqual(result, 1)
            self.assertIn("tools.md 'Look up an order': no '- Limits:' line", output)
            self.assertIn("scripts/probe does not exist in the project root", output)

    def test_an_entry_running_from_a_missing_folder_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "tools.md").write_text(tool_entry(run_from="services/api"))
            result, output = run_check(harness)
            self.assertEqual(result, 1)
            self.assertIn("runs from services/api, which is not a folder under the project root", output)

    def test_run_help_fails_a_help_that_errors_but_plain_validation_does_not_run_it(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            self.make_tool(Path(directory), "#!/bin/sh\nexit 3\n")
            (harness / "tools.md").write_text(tool_entry())
            self.assertEqual(run_check(harness)[0], 0)
            result, output = run_check(harness, "--run-help")
            self.assertEqual(result, 1)
            self.assertIn("'scripts/probe order --help' exited 3", output)

    def test_run_help_fails_a_help_that_hangs(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            self.make_tool(Path(directory), "#!/bin/sh\nsleep 5\n")
            (harness / "tools.md").write_text(tool_entry())
            with patch.object(validate, "HELP_TIMEOUT", 0.5):
                result, output = run_check(harness, "--run-help")
            self.assertEqual(result, 1)
            self.assertIn("help must not connect to anything", output)


class CredentialTest(unittest.TestCase):
    def test_a_credential_in_a_tool_or_the_guide_fails_without_echoing_it(self):
        token = "eyJhbGciOiJIUzI1NiJ9abc123def456"
        cases = [
            f'HEADERS = {{"Authorization": "Bearer {token}"}}\n',
            f'api_key = "{token}"\n',
            f'COOKIE = "_session_id={token}"\n',
        ]
        for line in cases:
            with self.subTest(line=line), tempfile.TemporaryDirectory() as directory:
                harness = make_harness(Path(directory))
                (harness / "scripts").mkdir(exist_ok=True)
                (harness / "scripts" / "probe.py").write_text("import os\n" + line)
                result, output = run_check(harness)
                self.assertEqual(result, 1)
                self.assertIn("scripts/probe.py:2 holds what looks like", output)
                self.assertNotIn(token, output)

    def test_lookups_env_names_and_framework_copies_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "scripts" / "framework").mkdir(parents=True, exist_ok=True)
            (harness / "scripts" / "probe.py").write_text(
                'token = os.environ["STOREFRONT_API_TOKEN"]\n'
                'TOKEN_VAR = "STOREFRONT_API_TOKEN"\n'
                'headers = {"Authorization": f"Bearer {token}"}\n'
            )
            (harness / "scripts" / "framework" / "test_fixture.py").write_text('password = "hunter2hunter2hunter2"\n')
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)


class SetupTest(unittest.TestCase):
    def test_incomplete_setup_stops_before_missing_commands_or_map(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "verify-app"
            harness.mkdir()
            shutil.copy(REFERENCES / "rules.md", harness / "rules.md")
            lock_rules(harness)
            (harness / "settings.md").write_text("# Settings\n\n## Setup\n\n- Status: incomplete\n")
            (harness / "notes.md").write_text(setup_record(
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
            (harness / "notes.md").write_text(setup_record(harness.name, proof="not run"))
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("ready setup needs doctor proof", output)

            (harness / "notes.md").write_text(setup_record(harness.name))
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
                (settings, None, "the Setup record cannot be read"),
                (settings, "# Results\n", "section for this harness"),
                (settings, f"## Setup: {harness.name}\n\n- Target: storefront\n", "Setup needs a filled Next action line"),
                (settings, f"## Setup: {harness.name}\n\n- Next action: none\n", "incomplete setup needs a Next action"),
            )
            for settings_text, record, expected in cases:
                with self.subTest(expected=expected):
                    for name, text in (("settings.md", settings_text), ("notes.md", record)):
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

            for filename in ("README.md", "tools.md"):
                with self.subTest(filename=filename):
                    path = harness / filename
                    path.rename(harness / "saved.md")
                    result, output = run_check(harness)
                    (harness / "saved.md").rename(path)
                    self.assertEqual(result, 1, output)
                    self.assertIn(f"{filename} is missing", output)

            shutil.rmtree(harness / "evidence")
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn(f"WARN no evidence directory at {harness / 'evidence'}", output)

    def test_checks_local_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "scripts").mkdir(exist_ok=True)
            (harness / "scripts" / "pay").write_text("# checkout check\n")
            (harness / "features" / "README.md").write_text(
                "# Map\n\n## Features\n\n- [Checkout](checkout.md)\n"
            )
            (harness / "features" / "checkout.md").write_text(
                "# Checkout\n\n## Sub-features\n\n- checkout.pay: order is paid.\n\n"
                "## How a user reaches it\n\n- Checkout button.\n\n"
                "## How to prove it\n\n- checkout.pay: `.agents/skills/verify-app/scripts/pay`. "
                "Reads the order row.\n\n"
                "## Gotchas\n\nNone.\n"
            )
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("no passing evidence for checkout.pay", output)


class ProjectRootTest(unittest.TestCase):
    def test_the_project_root_is_the_folder_holding_the_skills_directory(self):
        self.assertEqual(validate.project_root(Path("/repo/app/.agents/skills/verify-app")), Path("/repo/app").resolve())

    def test_a_monorepo_apps_recipes_resolve_from_its_own_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            harness = make_harness(root / "app")
            (harness / "scripts").mkdir(exist_ok=True)
            (harness / "scripts" / "pay").write_text("# checkout check\n")
            (harness / "features" / "README.md").write_text("# Map\n\n## Features\n\n- [Checkout](checkout.md)\n")
            feature = (
                "# Checkout\n\n## Sub-features\n\n- checkout.pay: order is paid.\n\n"
                "## How a user reaches it\n\n- Checkout button.\n\n"
                "## How to prove it\n\n- checkout.pay: `{command}`. Not break-tested: new.\n"
            )
            for command, errors in ((".agents/skills/verify-app/scripts/pay", 0), ("app/.agents/skills/verify-app/scripts/pay", 1)):
                with self.subTest(command=command):
                    (harness / "features" / "checkout.md").write_text(feature.format(command=command))
                    result, output = run_check(harness)
                    self.assertIn(f"{errors} errors", output)


class VerifiedResultsTest(unittest.TestCase):
    COMMIT = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
    LINE = ("- checkout.pay: Verified. checkout-pay, reads state, app a1b2c3d. Break-tested 2026-10-09: payment capture skipped. "
            "Evidence: evidence/checkout-pay/run.json")

    READS = "Reads the order row (state)."
    STEP = {"name": "checkout.pay: order is paid", "passed": True, "at": 21.4}
    CODE = {"ok/pay.py": "a" * 64, "ok/reads.py": "b" * 64}
    DOCTOR = {"exit_code": 0, "output": "verify: ready"}

    def make_verified_harness(self, root, proof=READS, with_break=True):
        harness = make_harness(root)
        (harness / "scripts").mkdir(exist_ok=True)
        (harness / "scripts" / "pay").write_text("# checkout check\n")
        (harness / "features" / "README.md").write_text("# Map\n\n## Features\n\n- [Checkout](checkout.md)\n")
        (harness / "features" / "checkout.md").write_text(
            "# Checkout\n\n## Sub-features\n\n- checkout.pay: order is paid.\n- checkout.refund: order is refunded.\n\n"
            "## How a user reaches it\n\n- Checkout button.\n\n"
            f"## How to prove it\n\n- checkout.pay: `.agents/skills/verify-app/scripts/pay`. {proof}\n- checkout.refund: No check yet.\n\n"
            "## Gotchas\n\nNone.\n"
        )
        self.write_evidence(harness)
        if with_break:
            self.write_break(harness)
        return harness

    def write_break(self, harness, **changes):
        record = {
            "check": "checkout-pay",
            "sub_features": ["checkout.pay"],
            "passed": False,
            "code": {"app": {"commit": self.COMMIT, "dirty": True, "dirty_hash": "a" * 64}},
            "harness_code": dict(self.CODE),
            "doctor": dict(self.DOCTOR),
            "planned_break": {"what": "payment capture skipped", "sub_features": ["checkout.pay"]},
            "started_at": "2026-10-09T09:59:00Z",
            "finished_at": "2026-10-09T10:00:00Z",
            "steps": [dict(self.STEP, passed=False)],
            "accepted_by": "vf.py run",
        }
        record.update(changes)
        (harness / "evidence" / "checkout-pay" / "break.json").write_text(json.dumps(record))

    def write_evidence(self, harness, **changes):
        record = {
            "check": "checkout-pay",
            "sub_features": ["checkout.pay"],
            "passed": True,
            "reads": "state",
            "code": {"app": {"commit": self.COMMIT, "dirty": False}},
            "harness_code": dict(self.CODE),
            "doctor": dict(self.DOCTOR),
            "started_at": "2026-10-13T14:02:11Z",
            "finished_at": "2026-10-13T14:02:40Z",
            "steps": [self.STEP],
            "accepted_by": "vf.py run",
        }
        record.update(changes)
        (harness / "evidence" / "checkout-pay" / "run.json").write_text(json.dumps(record))

    def write_results(self, harness, *lines):
        (harness / "status.md").write_text("# Verification status\n\n## Latest results\n\n" + "".join(line + "\n" for line in lines))

    def render(self, harness):
        """Write Latest results the way vf.py status does and return its result lines."""
        project = validate.project_root(harness)
        _, seen_ids, proofs, errors = validate.read_map(harness, project)
        self.assertEqual(errors, [])
        repos = validate.parse_repos(validate.sections((harness / "settings.md").read_text())[1])[0]
        return validate.render_status(harness, validate.compute_verdicts(harness, seen_ids, proofs, repos))

    def test_status_renders_verified_from_passing_break_tested_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            lines = self.render(harness)
            self.assertEqual(lines, [self.LINE, "- checkout.refund: Not verified. No check yet."])
            status = (harness / "status.md").read_text()
            self.assertTrue(status.startswith("# Verification status\n\n## Latest results\n\n" + validate.RENDERED_NOTE + "\n\n" + self.LINE + "\n"), status)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 0, output)
            self.assertNotIn("status.md", output)

    def test_status_is_rewritten_whole_and_leaves_notes_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            (harness / "status.md").write_text("# Verification status\n\n## Latest results\n\nstale\n\n## Untested cases\n\n- Two payments at once.\n")
            notes = (harness / "notes.md").read_text()
            self.render(harness)
            status = (harness / "status.md").read_text()
            self.assertNotIn("stale", status)
            self.assertNotIn("Untested cases", status)
            self.assertEqual(status.count("## Latest results"), 1)
            self.assertEqual((harness / "notes.md").read_text(), notes)
            self.render(harness)
            self.assertEqual((harness / "status.md").read_text(), status)

    def test_status_renders_a_rendered_line_for_every_proof_state(self):
        failed = {"passed": False, "steps": [dict(self.STEP, passed=False, detail="status=pending")]}
        cases = (
            (self.READS, True, failed, "- checkout.pay: Failed. Step 'checkout.pay: order is paid': status=pending. app a1b2c3d. Evidence: evidence/checkout-pay/run.json"),
            (self.READS, True, {"passed": None, "stopped": "browser crashed", "steps": []},
             "- checkout.pay: Not verified. Run stopped: Browser crashed. app a1b2c3d. Evidence: evidence/checkout-pay/run.json"),
            ("Not break-tested: no scratch copy yet.", False, {},
             "- checkout.pay: Not verified. Passed but not break-tested: no scratch copy yet. app a1b2c3d. Evidence: evidence/checkout-pay/run.json"),
            (self.READS, False, {},
             "- checkout.pay: Not verified. Passed but not break-tested: no planned break aimed at it has failed this check. app a1b2c3d. Evidence: evidence/checkout-pay/run.json"),
            (self.READS, True, {"code": {"app": {"commit": self.COMMIT, "dirty": True, "dirty_hash": "b" * 64}}},
             "- checkout.pay: Verified. checkout-pay, reads state, app a1b2c3d (uncommitted bbbbbbbb). Break-tested 2026-10-09: payment capture skipped. Evidence: evidence/checkout-pay/run.json"),
            (self.READS, True, {"sub_features": ["checkout.refund"], "steps": [dict(self.STEP, sub_features=["checkout.refund"])]},
             "- checkout.pay: Not verified. No accepted run on this machine."),
            (self.READS, True, {"accepted_by": None}, "- checkout.pay: Not verified. No accepted run on this machine."),
            ("Not break-tested: no scratch copy yet.", True, {"accepted_by": None},
             "- checkout.pay: Not verified. No accepted run on this machine. No scratch copy yet."),
        )
        for proof, with_break, evidence, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory), proof=proof, with_break=with_break)
                self.write_evidence(harness, **evidence)
                lines = self.render(harness)
                self.assertEqual(lines[0], expected)
                result, output = run_check(harness, "--require-evidence")
                self.assertEqual(result, 0, output)

    def test_unreachable_and_failed_runs_render_their_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory), proof="Not break-tested: fails on current code (#12).")
            feature = harness / "features" / "checkout.md"
            feature.write_text(feature.read_text().replace("- checkout.refund: No check yet.",
                                                           "- checkout.refund: Unreachable: no declining test card. Tried card 4000"))
            self.write_evidence(harness, passed=False, steps=[dict(self.STEP, passed=False)])
            (harness / "evidence" / "checkout-pay" / "run").mkdir()
            (harness / "evidence" / "checkout-pay" / "run" / "replay.html").write_text("<html>")
            lines = self.render(harness)
            self.assertEqual(lines, [
                "- checkout.pay: Failed. Step 'checkout.pay: order is paid'. app a1b2c3d. Evidence: evidence/checkout-pay/run.json. Replay: evidence/checkout-pay/run/replay.html",
                "- checkout.refund: Not verified. Unreachable: no declining test card. Tried card 4000.",
            ])

    def test_the_latest_accepted_run_decides(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            later = json.loads((harness / "evidence" / "checkout-pay" / "run.json").read_text())
            later.update(passed=False, finished_at="2026-10-14T09:00:00Z", steps=[dict(self.STEP, passed=False)])
            (harness / "evidence" / "checkout-pay" / "later.json").write_text(json.dumps(later))
            lines = self.render(harness)
            self.assertTrue(lines[0].startswith("- checkout.pay: Failed."), lines[0])
            self.assertIn("Evidence: evidence/checkout-pay/later.json", lines[0])

    def test_a_hand_written_verified_line_fails_unless_status_would_write_it(self):
        cases = (
            ({"passed": False, "steps": [dict(self.STEP, passed=False)]}, None, None, "its latest run evidence/checkout-pay/run.json did not pass"),
            ({"passed": None, "steps": []}, None, None, "its latest run evidence/checkout-pay/run.json stopped"),
            ({"sub_features": ["checkout.refund"], "steps": [dict(self.STEP, sub_features=["checkout.refund"])]}, None, None, "no accepted run covers it"),
            ({"code": {"app": {"commit": "ffffffffffffffff", "dirty": False}}}, None, None, "the line is not what vf.py status writes now"),
            ({}, "Not break-tested: no scratch copy yet.", None, "its check is not break-tested"),
            ({}, None, self.LINE.replace("checkout.pay", "checkout.refund", 1), "the map has no check for it"),
            ({}, None, self.LINE.replace(" Evidence: evidence/checkout-pay/run.json", ""), "the line is not what vf.py status writes now"),
            ({}, None, self.LINE.replace("evidence/checkout-pay/run.json", "evidence/pay.json"), "the line is not what vf.py status writes now"),
        )
        for evidence, proof, line, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory), **({"proof": proof, "with_break": False} if proof else {}))
                self.write_evidence(harness, **evidence)
                self.write_results(harness, line or self.LINE)
                result, output = run_check(harness, "--require-evidence")
                self.assertEqual(result, 1, output)
                self.assertIn(f"ERROR status.md: {'checkout.refund' if line and 'refund: Verified' in line else 'checkout.pay'} is Verified, but {expected}", output)

    def test_a_hand_written_not_verified_or_failed_line_is_never_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            self.write_results(harness, "- checkout.pay: Not verified. Written by hand.", "- checkout.refund: Failed. Also by hand.")
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 0, output)

    def test_verified_rejects_inconsistent_or_malformed_run_evidence(self):
        cases = (
            ({"steps": [dict(self.STEP, passed=False)]}, "has a step that did not pass"),
            ({"stopped": "app crashed"}, "records a stopped run"),
            ({"steps": []}, "has no check steps"),
            ({"steps": [{"name": None, "passed": True, "at": 1}]}, "invalid step"),
            ({"steps": [dict(self.STEP, passed=1)]}, "invalid step"),
            ({"steps": [self.STEP, self.STEP]}, "duplicate step"),
            ({"check": "other-check"}, "its check is not break-tested"),
            ({"check": None}, "check name"),
            ({"harness_code": None}, "records no harness_code fingerprint"),
            ({"harness_code": {"ok/pay.py": "short"}}, "records no harness_code fingerprint"),
            ({"doctor": None}, "ran without the doctor reporting the app ready"),
            ({"doctor": {"exit_code": 1, "output": "not ready: process exited"}}, "ran without the doctor reporting the app ready"),
            ({"sub_features": "checkout.pay"}, "no accepted run covers it"),
            ({"steps": [dict(self.STEP, sub_features=["checkout.refund"])]}, "whose sub_features are not among the run's"),
            ({"steps": [dict(self.STEP, sub_features="checkout.pay")]}, "whose sub_features are not among the run's"),
            ({"planned_break": {"what": "x", "sub_features": ["checkout.pay"]}}, "no accepted run covers it"),
            ({"finished_at": None}, "has no finished_at in UTC"),
            ({"finished_at": "2026-10-13 14:02"}, "has no finished_at in UTC"),
            ({"started_at": 5}, "has no started_at in UTC"),
            ({"code": []}, "code version"),
            ({"code": {"app": "bad"}}, "code version"),
            ({"code": {"app": {"commit": self.COMMIT, "dirty": True}}}, "dirty_hash"),
            ({"code": {"app": {"commit": self.COMMIT, "dirty": True, "dirty_hash": "bad"}}}, "dirty_hash"),
            ({"code": {"app": {"commit": self.COMMIT, "dirty": True, "dirty_hash": 10 ** 63}}}, "dirty_hash"),
            ({"code": {"app": {"commit": self.COMMIT, "dirty": False, "dirty_hash": "a" * 64}}}, "clean repo"),
        )
        for evidence, expected in cases:
            with self.subTest(evidence=evidence), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                self.write_evidence(harness, **evidence)
                self.write_results(harness, self.LINE)
                result, output = run_check(harness, "--require-evidence")
                self.assertEqual(result, 1, output)
                self.assertIn(expected, output)
                lines = self.render(harness)
                self.assertFalse(lines[0].startswith("- checkout.pay: Verified"), lines[0])

    def test_both_pass_and_break_must_record_every_configured_repo(self):
        for filename in ("run.json", "break.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                settings = harness / "settings.md"
                settings.write_text(settings.read_text().replace("- app: .", "- app: .\n- worker: ../worker"))
                for name in ("run.json", "break.json"):
                    path = harness / "evidence" / "checkout-pay" / name
                    record = json.loads(path.read_text())
                    if name != filename:
                        record["code"]["worker"] = {"commit": self.COMMIT, "dirty": False, "dirty_hash": None}
                    path.write_text(json.dumps(record))
                self.write_results(harness, self.LINE.replace("app a1b2c3d", "app a1b2c3d, worker a1b2c3d"))
                result, output = run_check(harness, "--require-evidence")
                self.assertEqual(result, 1, output)
                self.assertIn("records no code version for worker", output)

    def test_stopped_or_malformed_break_is_not_detection_proof(self):
        for broken, expected, rendered in (({"stopped": "app crashed"}, "records a stopped run", "Pass not proven: "),
                                           ({"steps": [{"name": None, "passed": False}]}, "invalid step", "Pass not proven: "),
                                           ({"code": {"app": {"commit": self.COMMIT, "dirty": True}}}, "dirty_hash", "Pass not proven: "),
                                           ({"doctor": "skipped"}, "ran without the doctor reporting the app ready", "Pass not proven: "),
                                           ({"planned_break": {"sub_features": ["checkout.pay"]}}, "does not say what was broken", "Pass not proven: "),
                                           ({"check": "other"}, "its check is not break-tested", "Passed but not break-tested: ")):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                self.write_break(harness, **broken)
                self.write_results(harness, self.LINE)
                result, output = run_check(harness, "--require-evidence")
                self.assertEqual(result, 1, output)
                self.assertIn(expected, output)
                lines = self.render(harness)
                self.assertTrue(lines[0].startswith("- checkout.pay: Not verified. " + rendered), lines[0])

    def test_a_pass_or_break_vf_run_did_not_accept_is_not_proof(self):
        for write, expected in (("write_evidence", "no accepted run covers it"), ("write_break", "its check is not break-tested")):
            with self.subTest(write=write), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                getattr(self, write)(harness, accepted_by=None)
                self.write_results(harness, self.LINE)
                result, output = run_check(harness, "--require-evidence")
                self.assertEqual(result, 1, output)
                self.assertIn(expected, output)

    def test_a_not_verified_record_stands_until_a_later_run_or_break(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            entry = validate.record_not_verified(harness, "checkout.pay", "the sandbox account expired; tried the saved-card route")
            self.assertEqual(entry["sub_feature"], "checkout.pay")
            lines = self.render(harness)
            day = entry["at"][:10]
            self.assertEqual(lines[0], f"- checkout.pay: Not verified. The sandbox account expired; tried the saved-card route. Recorded {day}.")
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 0, output)
            self.assertIn("WARN checkout.pay has stood Not verified for today (the sandbox account expired; tried the saved-card route); a rerun of its check lifts it", output)
            verdicts = {"checkout.pay": {"standing": dict(entry, at="2026-10-01T00:00:00Z", until="break")}}
            self.assertEqual(validate.standing_warnings(verdicts, today=datetime.date(2026, 10, 21)),
                             ["checkout.pay has stood Not verified for 20 days (the sandbox account expired; tried the saved-card route); a new planned break aimed at it lifts it"])

            # A run after the record lifts it.
            self.write_evidence(harness, finished_at="2099-01-01T00:00:00Z")
            lines = self.render(harness)
            self.assertEqual(lines[0], self.LINE)

            # One that stands until a break is not lifted by a run alone.
            validate.record_not_verified(harness, "checkout.pay", "the paid step was rewritten", until_break=True)
            self.write_evidence(harness, finished_at="2099-01-02T00:00:00Z")
            lines = self.render(harness)
            self.assertIn("Not verified. The paid step was rewritten. Recorded ", lines[0])
            self.assertTrue(lines[0].endswith("; a new planned break lifts it."), lines[0])
            self.write_break(harness, finished_at="2099-01-03T00:00:00Z")
            lines = self.render(harness)
            self.assertEqual(lines[0], self.LINE.replace("Break-tested 2026-10-09", "Break-tested 2099-01-03"))

            (harness / validate.NOT_VERIFIED_LOG).write_text("not json\n" + json.dumps({"sub_feature": "checkout.pay"}) + "\n")
            self.assertEqual(validate.not_verified_entries(harness), [])

    def test_verified_line_needs_a_break_whose_failed_steps_still_run(self):
        cases = (
            ({}, {}, None),
            ({"steps": [self.STEP, {"name": "receipt is sent", "passed": True, "at": 30.0}]}, {}, None),
            ({"steps": [{"name": "order is paid in full", "passed": True, "at": 21.4}]}, {},
             "step 'checkout.pay: order is paid' caught its planned break and does not judge it in this run"),
            # A step that failed without judging the behavior, such as setup, need not stay.
            ({}, {"steps": [dict(self.STEP, passed=False), {"name": "cart is ready", "passed": False, "at": 2.0, "sub_features": []}]},
             None),
            ({}, {"passed": True}, "its planned break in evidence/checkout-pay/break.json did not fail"),
            ({}, {"doctor": "skipped"}, "its planned break in evidence/checkout-pay/break.json ran without the doctor reporting the app ready"),
            ({}, {"steps": [dict(self.STEP)]}, "no step judging it failed in its planned break in evidence/checkout-pay/break.json"),
            ({}, {"steps": [dict(self.STEP), {"name": "cart is ready", "passed": False, "at": 2.0, "sub_features": []}]},
             "no step judging it failed in its planned break"),
            ({}, {"planned_break": None}, "its check is not break-tested"),
        )
        for evidence, broken, expected in cases:
            with self.subTest(expected=expected, evidence=evidence), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                self.write_evidence(harness, **evidence)
                self.write_break(harness, **broken)
                self.write_results(harness, self.LINE)
                result, output = run_check(harness, "--require-evidence")
                if expected is None:
                    self.assertEqual(result, 0, output)
                else:
                    self.assertEqual(result, 1, output)
                    self.assertIn(expected, output)

        # The newest break of the check decides, so a later break that did not fail withdraws the proof.
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            later = json.loads((harness / "evidence" / "checkout-pay" / "break.json").read_text())
            later.update(passed=True, finished_at="2026-10-12T10:00:00Z", steps=[dict(self.STEP)])
            (harness / "evidence" / "checkout-pay" / "later.json").write_text(json.dumps(later))
            self.write_results(harness, self.LINE)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)
            self.assertIn("its planned break in evidence/checkout-pay/later.json did not fail", output)

    def test_a_missing_break_record_leaves_the_pass_not_break_tested(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            self.render(harness)
            (harness / "evidence" / "checkout-pay" / "break.json").unlink()
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("ERROR status.md: checkout.pay is Verified, but its check is not break-tested", output)
            lines = self.render(harness)
            self.assertTrue(lines[0].startswith("- checkout.pay: Not verified. Passed but not break-tested: no planned break aimed at it has failed this check."), lines[0])

    def test_a_check_edited_since_its_break_is_not_proven_until_the_break_is_replayed(self):
        changed = dict(self.CODE, **{"ok/reads.py": "c" * 64})
        removed = {"ok/pay.py": "a" * 64}
        added = dict(self.CODE, **{"ok/new_probe.py": "d" * 64})
        cases = (
            (changed, "ok/reads.py changed since its planned break; replay the break with vf.py break replay"),
            (removed, "ok/reads.py was removed since its planned break; replay the break with vf.py break replay"),
            (added, None),
        )
        for manifest, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                self.write_evidence(harness, harness_code=manifest)
                self.write_results(harness, self.LINE)
                result, output = run_check(harness, "--require-evidence")
                lines = self.render(harness)
                if expected is None:
                    self.assertEqual(result, 0, output)
                    self.assertEqual(lines[0], self.LINE)
                else:
                    self.assertEqual(result, 1, output)
                    self.assertIn(f"ERROR status.md: checkout.pay is Verified, but {expected}", output)
                    self.assertEqual(lines[0], f"- checkout.pay: Not verified. Pass not proven: {expected}. app a1b2c3d. Evidence: evidence/checkout-pay/run.json")

        # Replaying the break on the edited check restores the proof.
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            self.write_evidence(harness, harness_code=changed)
            (harness / "evidence" / "checkout-pay" / "replayed.json").write_text(
                (harness / "evidence" / "checkout-pay" / "break.json").read_text()
                .replace("2026-10-09T10:00:00Z", "2026-10-12T10:00:00Z").replace("b" * 64, "c" * 64))
            lines = self.render(harness)
            self.assertEqual(lines[0], self.LINE.replace("Break-tested 2026-10-09", "Break-tested 2026-10-12"))

    def test_a_check_edited_since_its_pass_is_not_proven_until_it_runs_again(self):
        key = ".agents/skills/verify-app/scripts/pay"
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory), with_break=False)
            check = harness / "scripts" / "pay"
            ran = {key: hashlib.sha256(check.read_bytes()).hexdigest()}
            self.write_evidence(harness, harness_code=ran)
            self.write_break(harness, harness_code=ran)
            self.assertEqual(self.render(harness)[0], self.LINE)

            check.write_text("# checkout check, every step forced to pass\n")
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)
            expected = f"{key} changed since this run; rerun its check"
            self.assertIn(f"ERROR status.md: checkout.pay is Verified, but {expected}", output)
            self.assertEqual(self.render(harness)[0],
                             f"- checkout.pay: Not verified. Pass not proven: {expected}. app a1b2c3d. Evidence: evidence/checkout-pay/run.json")

            # The rerun records the edited check, which its planned break never ran.
            self.write_evidence(harness, harness_code={key: hashlib.sha256(check.read_bytes()).hexdigest()})
            self.assertIn(f"{key} changed since its planned break; replay the break with vf.py break replay", self.render(harness)[0])

    def test_a_break_proves_only_the_behaviors_it_was_aimed_at_and_whose_own_steps_failed(self):
        """Breaking payment fails the refund step after it too, but nobody broke the refund."""
        pay = dict(self.STEP, sub_features=["checkout.pay"])
        refund = {"name": "checkout.refund: order is refunded", "passed": True, "at": 30.0, "sub_features": ["checkout.refund"]}
        both = ["checkout.pay", "checkout.refund"]
        refund_line = self.LINE.replace("checkout.pay", "checkout.refund")
        cases = (
            (self.LINE, {}, None),
            (refund_line, {}, "its check is not break-tested"),
            (refund_line.replace("payment capture skipped", "refund skipped"),
             {"planned_break": {"what": "refund skipped", "sub_features": ["checkout.refund"]}}, None),
            # Aimed at the refund, but only the payment step failed.
            (refund_line, {"planned_break": {"what": "refund skipped", "sub_features": ["checkout.refund"]},
                           "steps": [dict(pay, passed=False), refund]}, "no step judging it failed in its planned break"),
        )
        for line, broken, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                feature = harness / "features" / "checkout.md"
                feature.write_text(feature.read_text().replace(
                    "- checkout.refund: No check yet.", f"- checkout.refund: `.agents/skills/verify-app/scripts/pay`. {self.READS}"))
                self.write_evidence(harness, sub_features=both, steps=[pay, refund])
                self.write_break(harness, **{"sub_features": both, "steps": [dict(pay, passed=False), dict(refund, passed=False)],
                                             **broken})
                self.write_results(harness, line)
                result, output = run_check(harness, "--require-evidence")
                if expected is None:
                    self.assertEqual(result, 0, output)
                else:
                    self.assertEqual(result, 1, output)
                    self.assertIn(expected, output)

    def test_a_run_covering_several_behaviors_needs_steps_that_name_them(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            self.write_evidence(harness, sub_features=["checkout.pay", "checkout.refund"])
            self.write_results(harness, self.LINE)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)
            self.assertIn("no step in evidence/checkout-pay/run.json judges it", output)

    def test_evidence_that_is_not_a_json_object_is_not_proof_and_does_not_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            (harness / "evidence" / "checkout-pay" / "notes.json").write_text("[]")
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)

            for cited, expected in (("run.json", "no accepted run covers it"),
                                    ("break.json", "its check is not break-tested")):
                with self.subTest(cited=cited):
                    self.write_evidence(harness)
                    self.write_break(harness)
                    (harness / "evidence" / "checkout-pay" / cited).write_text("[]")
                    self.write_results(harness, self.LINE)
                    result, output = run_check(harness, "--require-evidence")
                    self.assertEqual(result, 1, output)
                    self.assertIn(f"ERROR status.md: checkout.pay is Verified, but {expected}", output)

    def test_a_break_tested_clause_in_the_map_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory), proof="Break-tested 2026-10-09: payment capture skipped.")
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("checkout.pay says Break-tested, but nobody writes that: vf.py status computes it from the evidence", output)

    def test_missing_cited_evidence_warns_unless_required(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            self.render(harness)
            (harness / "evidence" / "checkout-pay" / "run.json").unlink()
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("WARN status.md: checkout.pay is Verified, but evidence/checkout-pay/run.json is not here", output)

            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)
            self.assertIn("ERROR status.md: checkout.pay is Verified, but evidence/checkout-pay/run.json is not here", output)

            lines = self.render(harness)
            self.assertEqual(lines[0], "- checkout.pay: Not verified. No accepted run on this machine.")

    def test_cited_evidence_needs_step_times_and_a_recording_inside_evidence(self):
        step = {"name": "order is paid", "passed": True, "at": 21.4}
        cases = (
            ({"steps": [{"name": "order is paid", "passed": True}]}, "has steps with no 'at' time: order is paid"),
            ({"steps": [dict(step, at=-1)]}, "has steps with no 'at' time"),
            ({"steps": [dict(step, at=float("inf"))]}, "has steps with no 'at' time"),
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

            (harness / "evidence" / "pay").mkdir(exist_ok=True)
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
            (harness / "scripts").mkdir(exist_ok=True)
            (harness / "scripts" / "checkout").write_text("# checkout check\n")
            (harness / "features" / "README.md").write_text("# Features\n\n## Features\n\n- [Checkout](checkout.md)\n")
            (harness / "features" / "checkout.md").write_text(
                "# Checkout\n\n## Sub-features\n\n- checkout.pay: order is paid.\n\n"
                "## How a user reaches it\n\n- Checkout button.\n\n"
                "## How to prove it\n\n- checkout.pay: `.agents/skills/verify-app/scripts/checkout`. Reads the order row.\n\n"
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
            evidence = harness / "evidence" / "checkout-pay" / "run.json"
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
            (evidence / "checkout-pay").mkdir()
            (evidence / "checkout-pay" / "run.json").write_text(json.dumps({
                "passed": True, "sub_features": ["checkout.pay", "checkout.refund"], "code": {"app": {"commit": "abc1234"}},
            }))
            proofs = {"checkout.pay": "`./scripts/pay`", "checkout.refund": "`./scripts/refund`"}
            with patch.object(validate, "resolve_repo", return_value=None) as resolve:
                warnings = validate.evidence_warnings(evidence, proofs, evidence, {"app": "."})
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
            (harness / "scripts").mkdir(exist_ok=True)
            (harness / "scripts" / "checkout").write_text("# checkout check\n")
            (harness / "features" / "README.md").write_text("# Features\n\n## Features\n\n- [Checkout](checkout.md)\n")
            (harness / "features" / "checkout.md").write_text(
                "# Checkout\n\n## Sub-features\n\n- checkout.pay: order is paid.\n- checkout.refund: order is refunded.\n\n"
                "## How a user reaches it\n\n- Checkout button.\n\n"
                "## How to prove it\n\n"
                "- checkout.pay: `.agents/skills/verify-app/scripts/checkout`.\n"
                "- checkout.refund: `.agents/skills/verify-app/scripts/checkout`.\n"
            )
            (harness / "evidence" / "checkout-pay" / "run.json").write_text(json.dumps({
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
