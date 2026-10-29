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

from harness_json import edit_feature, edit_manifest, manifest, read_manifest, write_feature, write_manifest  # noqa: E402

CHECK = ".agents/skills/verify-app/scripts/pay"


def json_template(name, key=None):
    """The JSON a reference file tells setup to copy into the harness; `key` wraps a fragment such as tool-guide.md's."""
    block = (REFERENCES / name).read_text().split("```json\n", 1)[1].split("\n```", 1)[0]
    return json.loads("{" + block + "}" if key else block)


def fill(value):
    """A template with every <slot> filled the way a ready harness fills it."""
    if isinstance(value, dict):
        return {k: fill(v) for k, v in value.items()}
    if isinstance(value, list):
        return [fill(v) for v in value]
    if isinstance(value, str):
        return re.sub(r"<[^<>]*>", "filled", value)
    return value


def lock_rules(harness):
    """Record the rules hash the way vf.py sync does."""
    lock = harness / validate.FRAMEWORK_LOCK
    lock.parent.mkdir(parents=True, exist_ok=True)
    digest = validate.rules_sha256((harness / "rules.md").read_bytes().replace(b"\r\n", b"\n"))
    lock.write_text(f"{digest}  rules.md\n")


def make_harness(root, **overrides):
    harness = root / ".agents" / "skills" / "verify-app"
    (harness / "features").mkdir(parents=True)
    (harness / "evidence" / "checkout-pay").mkdir(parents=True)
    shutil.copy(REFERENCES / "rules.md", harness / "rules.md")
    lock_rules(harness)
    (harness / "README.md").write_text("# Verify app\n")
    (harness / "notes.md").write_text("# Verification notes\n\n## Untested cases\n\nNone yet.\n")
    (harness / "status.md").write_text("# Verification status\n\n## Latest results\n\nNo behaviors in the feature map yet.\n")
    write_manifest(harness, **overrides)
    validate.write_tools(harness)
    return harness


def run_check(harness, *flags):
    output = io.StringIO()
    with patch.object(sys, "argv", [str(SCRIPT), str(harness), *flags]), \
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
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
            write_manifest(harness, setup={"status": "incomplete", "blocker": "no start command found", "next": "ask the user"})
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

    def test_written_for_passes_on_the_harness_version_and_names_the_older_side_on_a_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            version = validate.RULES_VERSION_LINE.search((harness / "rules.md").read_text()).group(1)
            _, output = run_check(harness, "--written-for", version)
            self.assertNotIn("written for", output)
            result, output = run_check(harness, "--written-for", str(int(version) + 1))
            self.assertEqual(result, 1, output)
            self.assertIn(f"written for Rules version {int(version) + 1} and the harness's rules.md is on {version}; update the harness", output)
            result, output = run_check(harness, "--written-for", "0")
            self.assertEqual(result, 1, output)
            self.assertIn("update the installed framework skills", output)


class FeatureFilesTest(unittest.TestCase):
    def test_a_feature_file_counts_its_behaviors_and_a_markdown_file_beside_it_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            write_feature(harness, "checkout", {"checkout.pay": {"words": "a paid order appears"}}, gotchas=["None."])
            (harness / "features" / "checkout.md").write_text("# Checkout\n\nLong prose about the request flow.\n")
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("1 features, 1 sub-features", output)

    def test_a_feature_file_that_is_not_an_object_or_has_an_unknown_field_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "features" / "checkout.json").write_text("[]")
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("checkout.json: not a JSON object", output)
            write_feature(harness, "checkout", {"checkout.pay": {"words": "a paid order appears", "proof": "by hand"}})
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("checkout.json: checkout.pay: unknown field proof", output)

    def test_a_behavior_needs_words_and_a_check_or_an_unreachable_reason_or_neither(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "scripts").mkdir(exist_ok=True)
            (harness / "scripts" / "pay").write_text("# check\n")
            cases = (
                ({"words": "an order is paid", "plan": "submit checkout; read the order"}, None),
                ({"words": "an order is paid", "check": CHECK, "reads": "state"}, None),
                ({"words": "an order is paid", "unreachable": {"blocker": "no declining card", "tried": "card 4000"}}, None),
                ({"check": CHECK, "reads": "state"}, "checkout.pay: words is missing"),
                ({"words": "x", "check": CHECK}, "checkout.pay: reads is missing"),
                ({"words": "x", "check": CHECK, "reads": "state", "unreachable": {"blocker": "b", "tried": "t"}}, "has both a check and an unreachable reason"),
                ({"words": "x", "reads": "state"}, "reads belongs with a check"),
                ({"words": "x", "not_break_tested": "new"}, "not_break_tested belongs with a check"),
                ({"words": "x", "unreachable": "no card"}, 'unreachable must be {"blocker": ..., "tried": ...}'),
                ({"words": "x", "unreachable": {"blocker": "no card"}}, "checkout.pay unreachable: tried is missing"),
                ({"words": "x", "check": "scripts/missing"}, "check names `scripts/missing`, but scripts/missing does not exist"),
                ({"words": "x", "check": "<the command>", "reads": "state"}, "check still has an unfilled slot"),
            )
            for entry, expected in cases:
                with self.subTest(entry=entry):
                    write_feature(harness, "checkout", {"checkout.pay": entry})
                    result, output = run_check(harness)
                    if expected is None:
                        self.assertEqual(result, 0, output)
                    else:
                        self.assertEqual(result, 1, output)
                        self.assertIn(expected, output)

    def test_ids_are_well_formed_and_unique_across_files(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            write_feature(harness, "checkout", {"checkout.pay": {"words": "paid"}, "Checkout.Refund": {"words": "refunded"}})
            write_feature(harness, "orders", {"checkout.pay": {"words": "paid again"}}, name="Orders")
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("checkout.json: Checkout.Refund: an ID is lowercase letters, digits, dots, dashes, and underscores", output)
            self.assertIn("orders.json: checkout.pay: also defined in checkout.json", output)


class ManifestTest(unittest.TestCase):
    def test_the_manifest_needs_every_command_filled(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            edit_manifest(harness, lambda d: (d["commands"].pop("doctor"), d["commands"].update(ready_line="<ready line>")))
            result, output = run_check(harness)
            self.assertEqual(result, 1)
            self.assertIn("harness.json commands: doctor is missing", output)
            self.assertIn("harness.json commands: ready_line still has an unfilled slot: <ready line>", output)

    def test_the_manifest_requires_repos_a_reloads_flag_and_known_start_placeholders(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            cases = (
                (lambda d: d.pop("repos"), "repos must be a non-empty object"),
                (lambda d: d.update(repos={"Worker": "../worker"}), "repo name 'Worker' is not lowercase"),
                (lambda d: d.update(repos={"app": "/Users/sam/app"}), "app locator must be portable"),
                (lambda d: d.update(repos={"app": "env:local.env"}), "invalid locator for app"),
                (lambda d: d["commands"].update(reloads="no"), "reloads must be true or false"),
                (lambda d: d["commands"].update(start="run {checkout:api}"), "start names {checkout:api}, which is not a repo"),
                (lambda d: d["commands"].update(probe=""), "probe must be a command, or null"),
                (lambda d: d.pop("app"), "harness.json: app is missing"),
            )
            for change, expected in cases:
                with self.subTest(expected=expected):
                    write_manifest(harness)
                    edit_manifest(harness, change)
                    result, output = run_check(harness)
                    self.assertEqual(result, 1, output)
                    self.assertIn(expected, output)


class TemplateTest(unittest.TestCase):
    def test_the_tool_guide_names_exactly_the_fields_check_reads(self):
        entry = next(iter(json_template("tool-guide.md", key="tools")["tools"].values()))
        self.assertEqual(set(entry), set(validate.TOOL_REQUIRED) | set(validate.TOOL_OPTIONAL) | {"run_from"})

    def test_the_filled_manifest_template_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            data = fill(json_template("harness.md"))
            data["setup"].update(status="ready", blocker=None, next=None, doctor_proof="filled")
            data["repos"] = {"app": "."}
            data["commands"]["probe"] = None
            write_manifest(harness, data)
            validate.write_tools(harness)
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)


def tool_entry(command="scripts/probe order o_1", run_from=None, skip=None):
    entry = {"command": command, "use_when": "you need an order's state.", "permissions": "read-only.", "limits": "stored state only."}
    if run_from:
        entry["run_from"] = run_from
    if skip:
        entry.pop(skip)
    return {"probe": entry}


class ToolsTest(unittest.TestCase):
    def make_tool(self, root, body="#!/bin/sh\necho usage\n"):
        script = root / "scripts" / "probe"
        script.parent.mkdir()
        script.write_text(body)
        script.chmod(0o755)

    def with_tools(self, harness, tools):
        write_manifest(harness, tools=tools)
        validate.write_tools(harness)

    def test_a_complete_entry_with_a_working_help_passes_and_renders_the_guide(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            self.make_tool(Path(directory))
            self.with_tools(harness, tool_entry())
            result, output = run_check(harness, "--run-help")
            self.assertEqual(result, 0, output)
            guide = (harness / "tools.md").read_text()
            self.assertIn("## probe\n\nUse when: you need an order's state.\n\nRun from the project root:\n\n`scripts/probe order o_1`\n", guide)
            self.assertIn("- Limits: stored state only.\n\nHelp: `scripts/probe order o_1 --help`\n", guide)

    def test_a_hand_edited_guide_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            (harness / "tools.md").write_text((harness / "tools.md").read_text() + "\n## Added by hand\n")
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("tools.md is not what vf.py tools writes now; run it to refresh tools.md", output)

    def test_an_entry_missing_a_field_or_its_script_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            self.with_tools(harness, tool_entry(skip="limits"))
            result, output = run_check(harness)
            self.assertEqual(result, 1)
            self.assertIn("harness.json tool 'probe': limits is missing", output)
            self.assertIn("scripts/probe does not exist in .", output)

    def test_an_entry_running_from_a_missing_folder_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            self.with_tools(harness, tool_entry(run_from="services/api"))
            result, output = run_check(harness)
            self.assertEqual(result, 1)
            self.assertIn("runs from services/api, which is not a folder under the project root", output)

    def test_run_help_fails_a_help_that_errors_but_plain_validation_does_not_run_it(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            self.make_tool(Path(directory), "#!/bin/sh\nexit 3\n")
            self.with_tools(harness, tool_entry())
            self.assertEqual(run_check(harness)[0], 0)
            result, output = run_check(harness, "--run-help")
            self.assertEqual(result, 1)
            self.assertIn("'scripts/probe order o_1 --help' exited 3", output)

    def test_run_help_fails_a_help_that_hangs(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            self.make_tool(Path(directory), "#!/bin/sh\nsleep 5\n")
            self.with_tools(harness, tool_entry())
            with patch.object(validate, "HELP_TIMEOUT", 0.5):
                result, output = run_check(harness, "--run-help")
            self.assertEqual(result, 1)
            self.assertIn("help must not connect to anything", output)


class CredentialTest(unittest.TestCase):
    def test_a_credential_in_the_manifest_fails_without_echoing_it(self):
        token = "eyJhbGciOiJIUzI1NiJ9abc123def456"
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            write_manifest(harness, tools={"probe": dict(tool_entry()["probe"], environment=f"send Authorization: Bearer {token}")})
            validate.write_tools(harness)
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("harness.json:", output)
            self.assertNotIn(token, output)

    def test_a_credential_in_a_tool_fails_without_echoing_it(self):
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
            write_manifest(harness, {"setup": {"status": "incomplete", "target": "storefront", "findings": "README.md:4", "looked_in": "README.md",
                                               "blocker": "operator login is unavailable", "next": "user starts storefront with the documented login",
                                               "doctor_proof": None}})
            result, output = run_check(harness)
            self.assertEqual(result, 2, output)
            self.assertIn("operator login is unavailable", output)
            self.assertIn("Next action: user starts storefront", output)
            self.assertNotIn("features folder", output)

    def test_ready_setup_requires_proof_and_allows_zero_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory), setup={"doctor_proof": "not run"})
            result, output = run_check(harness)
            self.assertEqual(result, 1, output)
            self.assertIn("ready setup needs doctor_proof", output)

            write_manifest(harness)
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("0 features, 0 sub-features", output)

    def test_setup_rejects_a_missing_manifest_or_an_unusable_resume_record(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "verify-app"
            (harness / "features").mkdir(parents=True)
            shutil.copy(REFERENCES / "rules.md", harness / "rules.md")
            lock_rules(harness)
            incomplete = {"status": "incomplete", "target": "storefront", "findings": "f", "looked_in": "l", "blocker": "b", "next": "n"}
            cases = (
                (None, "harness.json is missing"),
                ({"setup": "later"}, "setup must be an object"),
                ({"setup": dict(incomplete, status="unknown")}, "setup.status must be incomplete or ready"),
                ({"setup": {"status": "incomplete", "target": "storefront"}}, "harness.json setup: findings is missing"),
                ({"setup": dict(incomplete, next=None)}, "incomplete setup needs a next"),
                ({"setup": dict(incomplete, status="ready", blocker=None, next=None, doctor_proof="x")}, "harness.json commands: doctor is missing"),
            )
            for data, expected in cases:
                with self.subTest(expected=expected):
                    path = harness / "harness.json"
                    if data is None:
                        path.unlink(missing_ok=True)
                    else:
                        path.write_text(json.dumps({"app": "App", **data}))
                    result, output = run_check(harness)
                    self.assertEqual(result, 1, output)
                    self.assertIn(expected, output)


class HarnessLayoutTest(unittest.TestCase):
    def test_the_harness_map_is_read_even_when_the_project_has_a_features_folder_of_its_own(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "features").mkdir()
            (root / "features" / "README.md").write_text("# Project map\n\n## Features\n\n- [Decoy](decoy.md)\n")
            (root / "features" / "decoy.md").write_text(
                "# Decoy\n\n## Sub-features\n\n- decoy.one: a project feature.\n\n"
                "## How a user reaches it\n\n- Menu.\n\n## How to prove it\n\n- decoy.one: No check yet.\n")
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
            write_feature(harness, "checkout", {"checkout.pay": {"words": "order is paid", "check": CHECK, "reads": "state"}})
            result, output = run_check(harness)
            self.assertEqual(result, 0, output)
            self.assertIn("no passing evidence for checkout.pay", output)


class ProjectRootTest(unittest.TestCase):
    def test_the_project_root_is_the_folder_holding_the_skills_directory(self):
        self.assertEqual(validate.project_root(Path("/repo/app/.agents/skills/verify-app")), Path("/repo/app").resolve())

    def test_a_monorepo_apps_recipes_resolve_from_its_own_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = Path(directory) / "app" / ".agents" / "skills" / "verify-app"
            (harness / "scripts").mkdir(parents=True)
            (harness / "scripts" / "pay").write_text("# checkout check\n")
            feature = Path(directory) / "checkout.json"
            from_app = ".agents/skills/verify-app/scripts/pay"
            from_top = "app/" + from_app
            for command, expected in ((from_app, []),
                                      (from_top, [f"checkout.json: checkout.pay: check names `{from_top}`, but {from_top} does not exist"])):
                with self.subTest(command=command):
                    feature.write_text(json.dumps({"name": "Checkout", "summary": "Pays.", "behaviors": {
                        "checkout.pay": {"words": "order is paid", "check": command, "reads": "state", "not_break_tested": "new"}}}))
                    errors = []
                    validate.check_feature(feature, validate.project_root(harness), {"app": "."}, {}, errors)
                    self.assertEqual(errors, expected)


class VerifiedResultsTest(unittest.TestCase):
    COMMIT = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
    LINE = ("- checkout.pay: Verified. checkout-pay, reads state, app a1b2c3d. Break-tested 2026-10-09: payment capture skipped. "
            "Evidence: evidence/checkout-pay/run.json")

    READS = {"check": CHECK, "reads": "state"}
    STEP = {"name": "checkout.pay: order is paid", "passed": True, "at": 21.4}
    CODE = {"ok/pay.py": "a" * 64, "ok/reads.py": "b" * 64}
    DOCTOR = {"exit_code": 0, "output": "verify: ready"}

    def make_verified_harness(self, root, proof=READS, with_break=True):
        harness = make_harness(root)
        (harness / "scripts").mkdir(exist_ok=True)
        (harness / "scripts" / "pay").write_text("# checkout check\n")
        write_feature(harness, "checkout", {"checkout.pay": {"words": "order is paid", **proof},
                                            "checkout.refund": {"words": "order is refunded"}}, gotchas=["None."])
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
            "planned_break": {"what": "payment capture skipped", "sub_features": ["checkout.pay"], "repo": "app"},
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
        repos = read_manifest(harness)["repos"]
        _, seen_ids, proofs, errors = validate.read_map(harness, project, repos)
        self.assertEqual(errors, [])
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
            (dict(self.READS, not_break_tested="no scratch copy yet."), False, {},
             "- checkout.pay: Not verified. Passed but not break-tested: no scratch copy yet. app a1b2c3d. Evidence: evidence/checkout-pay/run.json"),
            (self.READS, False, {},
             "- checkout.pay: Not verified. Passed but not break-tested: no planned break aimed at it has failed this check. app a1b2c3d. Evidence: evidence/checkout-pay/run.json"),
            (self.READS, True, {"code": {"app": {"commit": self.COMMIT, "dirty": True, "dirty_hash": "b" * 64}}},
             "- checkout.pay: Verified. checkout-pay, reads state, app a1b2c3d (uncommitted bbbbbbbb). Break-tested 2026-10-09: payment capture skipped. Evidence: evidence/checkout-pay/run.json"),
            (self.READS, True, {"sub_features": ["checkout.refund"], "steps": [dict(self.STEP, sub_features=["checkout.refund"])]},
             "- checkout.pay: Not verified. No accepted run on this machine."),
            (self.READS, True, {"accepted_by": None}, "- checkout.pay: Not verified. No accepted run on this machine."),
            (dict(self.READS, not_break_tested="no scratch copy yet."), True, {"accepted_by": None},
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
            harness = self.make_verified_harness(Path(directory), proof=dict(self.READS, not_break_tested="fails on current code (#12)."))
            edit_feature(harness, "checkout", lambda d: d["behaviors"]["checkout.refund"].update(
                unreachable={"blocker": "no declining test card", "tried": "card 4000"}))
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
            ({}, dict(self.READS, not_break_tested="no scratch copy yet."), None, "its check is not break-tested"),
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
                edit_manifest(harness, lambda d: d["repos"].update(worker="../worker"))
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
                                           ({"planned_break": {"what": "x", "sub_features": ["checkout.pay"]}},
                                            "whose repo is not one the behavior's check runs", "Pass not proven: "),
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

    def two_repo_settings(self, harness):
        """List a second repo, api, that this machine does not have."""
        edit_manifest(harness, lambda d: d["repos"].update(api="../api"))

    def test_a_behavior_names_only_the_repos_its_check_runs(self):
        # With repos named, records that hold only app prove the behavior although the manifest also lists api.
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory), proof=dict(self.READS, repos=["app"]))
            self.two_repo_settings(harness)
            self.write_results(harness, self.LINE)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 0, output)
            self.assertNotIn("api checkout cannot be found", output)
            self.assertEqual(self.render(harness)[0], self.LINE)
        # Without it, every settings repo must be in both records.
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            self.two_repo_settings(harness)
            self.write_results(harness, self.LINE)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)
            self.assertIn("records no code version for api", output)
            self.assertTrue(self.render(harness)[0].startswith("- checkout.pay: Not verified. Pass not proven: records no code version for api"))

    def test_a_behavior_cannot_name_a_repo_the_manifest_does_not_list(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory), proof=dict(self.READS, repos=["app", "mailer"]))
            self.write_results(harness, self.LINE)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)
            self.assertIn("checkout.json: checkout.pay: repos names mailer, which is not a repo in harness.json", output)

    def test_a_break_in_a_repo_the_behavior_does_not_run_proves_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory), proof=dict(self.READS, repos=["app"]))
            self.two_repo_settings(harness)
            self.write_break(harness, planned_break={"what": "payment capture skipped", "sub_features": ["checkout.pay"], "repo": "api"},
                             code={"app": {"commit": self.COMMIT, "dirty": False}, "api": {"commit": self.COMMIT, "dirty": False}})
            self.write_results(harness, self.LINE)
            result, output = run_check(harness, "--require-evidence")
            self.assertEqual(result, 1, output)
            self.assertIn("has a planned_break whose repo is not one the behavior's check runs", output)

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
             {"planned_break": {"what": "refund skipped", "sub_features": ["checkout.refund"], "repo": "app"},
              "steps": [pay, dict(refund, passed=False)]}, None),
            # Aimed at the refund, but only the payment step failed.
            (refund_line, {"planned_break": {"what": "refund skipped", "sub_features": ["checkout.refund"], "repo": "app"},
                           "steps": [dict(pay, passed=False), refund]}, "no step judging it failed in its planned break"),
        )
        for line, broken, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                edit_feature(harness, "checkout", lambda d: d["behaviors"]["checkout.refund"].update(self.READS))
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

    def test_a_break_earns_credit_only_when_every_earlier_failed_step_judges_the_same_behavior(self):
        """A payment step that failed because sign-in failed first proves nothing about the payment check, and a
        refund step that failed because the payment failed first proves nothing about refunds, even when the
        break names refunds as a target too."""
        signin = {"name": "customer signs in", "passed": False, "at": 5.0, "sub_features": []}
        pay = dict(self.STEP, sub_features=["checkout.pay"])
        refund = {"name": "checkout.refund: order is refunded", "passed": False, "at": 30.0, "sub_features": ["checkout.refund"]}
        both = ["checkout.pay", "checkout.refund"]
        pay_and_refund = {"name": "order is paid and refundable", "passed": False, "at": 10.0, "sub_features": both}
        refund_line = self.LINE.replace("checkout.pay", "checkout.refund")
        spoiled = "step 'customer signs in' failed before any step judging it in its planned break in evidence/checkout-pay/break.json"
        knock_on = "step 'checkout.pay: order is paid' failed before any step judging it in its planned break"
        cases = (
            ("setup fails first", self.LINE, ["checkout.pay"], [signin, dict(pay, passed=False)], spoiled),
            ("setup fails after the catch", self.LINE, ["checkout.pay"], [dict(pay, passed=False), signin], None),
            ("an earlier target's step fails", refund_line, both, [dict(pay, passed=False), refund], knock_on),
            ("an earlier non-target step fails", refund_line, ["checkout.refund"], [dict(pay, passed=False), refund], knock_on),
            ("the first failed step judges both targets", refund_line, both, [pay_and_refund, refund], None),
            ("the first failed step judges both targets, pay", self.LINE, both, [pay_and_refund, refund], None),
        )
        for label, line, targets, steps, expected in cases:
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                harness = self.make_verified_harness(Path(directory))
                edit_feature(harness, "checkout", lambda d: d["behaviors"]["checkout.refund"].update(self.READS))
                self.write_evidence(harness, sub_features=both, steps=[dict(pay_and_refund, passed=True), pay, dict(refund, passed=True)])
                self.write_break(harness, sub_features=both, steps=steps,
                                 planned_break={"what": "payment capture skipped", "sub_features": targets, "repo": "app"})
                self.write_results(harness, line)
                result, output = run_check(harness, "--require-evidence")
                if expected is None:
                    self.assertEqual(result, 0, output)
                else:
                    self.assertEqual(result, 1, output)
                    self.assertIn(expected, output)

    def test_only_a_planned_break_may_be_ended_early(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = self.make_verified_harness(Path(directory))
            self.write_evidence(harness, ended_early={"reason": "every target failed a step judging it", "killed": False})
            self.assertIn("Pass not proven: was ended early by vf.py run but is not a planned break.", self.render(harness)[0])

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


class BreakCatchTest(unittest.TestCase):
    """A break credits only the behavior whose step failed first, plus any other behavior that same step judges."""

    def record(self, targets, steps):
        return {"sub_features": ["shop.order", "shop.pay"],
                "planned_break": {"what": "order insert skipped", "sub_features": targets, "repo": "app"}, "steps": steps}

    def test_a_knock_on_failure_earns_nothing_even_when_its_setup_is_named_as_a_target(self):
        # The payment step failed only because skipping the order insert left nothing to pay for.
        steps = [{"name": "order is placed", "passed": False, "sub_features": ["shop.order"]},
                 {"name": "payment is saved", "passed": False, "sub_features": ["shop.pay"]}]
        for targets in (["shop.order", "shop.pay"], ["shop.pay"]):
            with self.subTest(targets=targets):
                record = self.record(targets, steps)
                self.assertEqual(validate.break_catch(record, "shop.pay"), (["payment is saved"], "order is placed"))
                self.assertEqual(validate.break_catch(record, "shop.order"), (["order is placed"], None))

    def test_a_first_failed_step_judging_two_targets_credits_both(self):
        steps = [{"name": "order is placed and paid", "passed": False, "sub_features": ["shop.order", "shop.pay"]},
                 {"name": "payment is saved", "passed": False, "sub_features": ["shop.pay"]}]
        record = self.record(["shop.order", "shop.pay"], steps)
        self.assertEqual(validate.break_catch(record, "shop.order"), (["order is placed and paid"], None))
        self.assertEqual(validate.break_catch(record, "shop.pay"), (["order is placed and paid", "payment is saved"], None))


class HarnessFingerprintTest(unittest.TestCase):
    def test_a_line_ending_rewrite_is_not_a_harness_edit(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            check = harness / "scripts" / "checks" / "pay.py"
            check.parent.mkdir(parents=True)
            check.write_bytes(b"# pay\nprint(1)\n")
            before = validate.harness_code(harness)
            check.write_bytes(b"# pay\r\nprint(1)\r\n")
            self.assertEqual(validate.harness_code(harness), before)
            self.assertEqual(validate.harness_edited_since_run(harness, {"harness_code": before}), [])
            check.write_bytes(b"# pay\r\nprint(2)\r\n")
            self.assertEqual(validate.harness_edited_since_run(harness, {"harness_code": before}),
                             [".agents/skills/verify-app/scripts/checks/pay.py changed since this run; rerun its check"])

    def test_the_manifest_is_part_of_the_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            harness = make_harness(Path(directory))
            before = validate.harness_code(harness)
            self.assertIn(".agents/skills/verify-app/harness.json", before)
            edit_manifest(harness, lambda d: d["commands"].update(doctor="true"))
            self.assertEqual(validate.harness_edited_since_run(harness, {"harness_code": before}),
                             [".agents/skills/verify-app/harness.json changed since this run; rerun its check"])


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
            write_feature(harness, "checkout", {"checkout.pay": {"words": "order is paid", "check": ".agents/skills/verify-app/scripts/checkout", "reads": "state"}})
            write_manifest(harness, repos={"project": ".", "worker": "env:local-dev/.env:WORKER"})
            validate.write_tools(harness)
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
            proofs = {"checkout.pay": {"check": "./scripts/pay"}, "checkout.refund": {"check": "./scripts/refund"}}
            with patch.object(validate, "resolve_repo", return_value=None) as resolve:
                warnings = validate.evidence_warnings(evidence, proofs, {"app": "."})
            self.assertEqual(resolve.call_count, 1)
            self.assertEqual(warnings, ["app checkout cannot be found from harness.json for checkout.pay, checkout.refund"])

    def test_each_repo_and_commit_is_checked_for_staleness_once(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory)
            (evidence / "checkout-pay").mkdir()
            (evidence / "checkout-pay" / "run.json").write_text(json.dumps({
                "passed": True, "sub_features": ["checkout.pay", "checkout.refund"], "code": {"app": {"commit": "abc1234"}},
            }))
            proofs = {"checkout.pay": {"check": "./scripts/pay"}, "checkout.refund": {"check": "./scripts/refund"}}
            with patch.object(validate, "resolve_repo", return_value=evidence), \
                    patch.object(validate, "uncommitted_files", return_value=[]), \
                    patch.object(validate, "stale_commit_warning", return_value="app last pass is 2 commits behind HEAD") as stale:
                warnings = validate.evidence_warnings(evidence, proofs, {"app": "."})
            self.assertEqual(stale.call_count, 1)
            self.assertEqual(warnings, ["app last pass is 2 commits behind HEAD for checkout.pay, checkout.refund"])

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
            check = {"check": ".agents/skills/verify-app/scripts/checkout", "reads": "state"}
            write_feature(harness, "checkout", {"checkout.pay": {"words": "order is paid", **check},
                                                "checkout.refund": {"words": "order is refunded", **check}})
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
