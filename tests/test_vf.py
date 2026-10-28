import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from harness_json import edit_feature, edit_manifest, write_feature, write_manifest  # noqa: E402
from support import git, start_break_runner, wait_until_gone

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"

sys.path.insert(0, str(SCRIPTS))
import vf  # noqa: E402

validate = vf.sibling("validate")

SCRIPT = SCRIPTS / "vf.py"


def run_sync(harness, *flags, script=SCRIPT):
    return subprocess.run([sys.executable, str(script), "sync", str(harness), *flags], capture_output=True, text=True)


def with_version(rules, version):
    return vf.RULES_VERSION_LINE.sub(f"Rules version: {version}", rules, count=1)


class Sync(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.harness = self.tmp / ".agents" / "skills" / "verify-app"
        self.source_rules = vf.SOURCE_RULES.read_text()
        self.version = vf.rules_version(vf.SOURCE_RULES.read_bytes(), "source")

    def framework_copy(self, name):
        return self.harness / "scripts" / "framework" / name

    def test_creates_rules_and_every_framework_script_in_a_new_harness(self):
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.harness / "rules.md").read_text(), self.source_rules)
        for name in vf.FRAMEWORK_SCRIPTS:
            self.assertEqual(self.framework_copy(name).read_bytes(), (vf.SCRIPTS_DIR / name).read_bytes())
        self.assertIn("created rules.md", result.stdout)
        self.assertIn("created scripts/framework/vf.py", result.stdout)

    def test_reports_current_copies_without_rewriting_them(self):
        run_sync(self.harness)
        written = self.framework_copy("vf.py").stat().st_mtime_ns
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "framework copies already current")
        self.assertEqual(self.framework_copy("vf.py").stat().st_mtime_ns, written)

    def test_replaces_only_the_scripts_that_differ(self):
        run_sync(self.harness)
        self.framework_copy("clip.py").write_text("# old clip\n")
        self.write_lock(**{"scripts/framework/clip.py": vf.file_hash(b"# old clip\n")})
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout.strip(), "replaced scripts/framework/clip.py\nreplaced scripts/framework/framework.sha256")
        self.assertEqual(self.framework_copy("clip.py").read_bytes(), (vf.SCRIPTS_DIR / "clip.py").read_bytes())

    def test_refuses_to_downgrade_a_newer_harness(self):
        self.harness.mkdir(parents=True)
        newer = with_version(self.source_rules, self.version + 1)
        (self.harness / "rules.md").write_text(newer)
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 1)
        self.assertIn("update the installed framework skills", result.stdout)
        self.assertEqual((self.harness / "rules.md").read_text(), newer)
        self.assertFalse(self.framework_copy("vf.py").exists())

    def test_shows_an_edited_rules_copy_and_leaves_it_until_restore_is_passed(self):
        run_sync(self.harness)
        edited = self.source_rules.replace("Rules version", "An app-specific note.\n\nRules version", 1)
        (self.harness / "rules.md").write_text(edited)
        self.framework_copy("clip.py").write_text("# old clip\n")

        refused = run_sync(self.harness)
        self.assertEqual(refused.returncode, 1)
        self.assertIn("rules.md, scripts/framework/clip.py edited since the last sync", refused.stdout)
        self.assertIn("+An app-specific note.", refused.stdout)
        self.assertEqual((self.harness / "rules.md").read_text(), edited)
        self.assertEqual(self.framework_copy("clip.py").read_text(), "# old clip\n")

        restored = run_sync(self.harness, "--restore")
        self.assertEqual(restored.returncode, 0)
        self.assertEqual((self.harness / "rules.md").read_text(), self.source_rules)
        self.assertEqual(self.framework_copy("clip.py").read_bytes(), (vf.SCRIPTS_DIR / "clip.py").read_bytes())

    def write_lock(self, **hashes):
        lock = self.harness / validate.FRAMEWORK_LOCK
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("".join(f"{digest}  {name}\n" for name, digest in hashes.items()))

    def test_records_every_copied_files_hash_in_the_format_shasum_checks(self):
        run_sync(self.harness)
        recorded = vf.read_lock(self.harness / validate.FRAMEWORK_LOCK)
        self.assertEqual(recorded["rules.md"], vf.file_hash(vf.SOURCE_RULES.read_bytes()))
        for name in vf.FRAMEWORK_SCRIPTS:
            self.assertEqual(recorded[f"scripts/framework/{name}"], vf.file_hash((vf.SCRIPTS_DIR / name).read_bytes()))
        checked = subprocess.run(["shasum", "-a", "256", "-c", str(validate.FRAMEWORK_LOCK)], cwd=self.harness, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
        errors = []
        validate.check_rules(self.harness, errors)
        self.assertEqual(errors, [])

    def test_converts_a_harness_with_older_copies_and_no_hash_record(self):
        self.harness.mkdir(parents=True)
        (self.harness / "rules.md").write_text(with_version(self.source_rules, self.version - 1) + "A rule since dropped.\n")
        for name in vf.FRAMEWORK_SCRIPTS[:-1]:
            self.framework_copy(name).parent.mkdir(parents=True, exist_ok=True)
            self.framework_copy(name).write_text(f"# {name} as an earlier framework shipped it\n")
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"Rules version {self.version - 1} -> {self.version}", result.stdout)
        self.assertIn("replaced rules.md", result.stdout)
        self.assertIn("replaced scripts/framework/validate.py", result.stdout)
        self.assertIn("created scripts/framework/vf.py", result.stdout)
        self.assertIn("created scripts/framework/framework.sha256", result.stdout)
        errors = []
        validate.check_rules(self.harness, errors)
        self.assertEqual(errors, [])

    def test_an_unedited_copy_is_replaced_even_when_the_framework_kept_its_rules_version(self):
        self.harness.mkdir(parents=True)
        older = self.source_rules + "A rule the framework later dropped.\n"
        (self.harness / "rules.md").write_text(older)
        self.write_lock(**{"rules.md": vf.file_hash(older.encode())})
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual((self.harness / "rules.md").read_text(), self.source_rules)

    def test_an_edit_to_an_older_version_is_still_an_edit(self):
        self.harness.mkdir(parents=True)
        older = with_version(self.source_rules, self.version - 1)
        (self.harness / "rules.md").write_text(older + "An app-specific note.\n")
        self.write_lock(**{"rules.md": vf.file_hash(older.encode())})
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 1)
        self.assertIn("rules.md edited since the last sync", result.stdout)

    def test_line_ending_conversion_is_not_an_edit(self):
        run_sync(self.harness)
        crlf = self.source_rules.replace("\n", "\r\n").encode()
        (self.harness / "rules.md").write_bytes(crlf)
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "framework copies already current")
        self.assertEqual((self.harness / "rules.md").read_bytes(), crlf)

    def test_stops_when_run_from_a_harness_copy(self):
        run_sync(self.harness)
        other = self.tmp / "other"
        result = run_sync(other, script=self.framework_copy("vf.py"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("run sync from the installed vf skill", result.stderr)
        self.assertIn(vf.INSTALL_COMMAND, result.stderr)
        self.assertFalse(other.exists())

    def test_commits_the_skill_beside_the_harness_without_its_scripts(self):
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = vf.SCRIPTS_DIR.parent.parent
        for name in vf.COMMITTED_SKILLS:
            copy = self.harness.parent / name
            self.assertEqual((copy / "SKILL.md").read_bytes(), (installed / name / "SKILL.md").read_bytes())
            self.assertFalse((copy / "scripts").exists(), f"{name}/scripts stays with the installed skill")
            self.assertEqual(list(copy.rglob("__pycache__")), [])
        self.assertIn("created ../vf/SKILL.md", result.stdout)
        self.assertFalse((self.harness.parent / "vf-verify").exists(), "the framework ships one skill")
        recorded = vf.read_lock(self.harness / validate.FRAMEWORK_LOCK)
        self.assertEqual(recorded["../vf/SKILL.md"], vf.file_hash((installed / "vf" / "SKILL.md").read_bytes()))

    def test_names_the_files_of_an_earlier_harness_format_without_touching_them(self):
        self.harness.mkdir(parents=True)
        (self.harness / "settings.md").write_text("## Setup\n- Status: ready\n")
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("WARN: settings.md is from an earlier harness format", result.stdout)
        self.assertIn("harness.json", result.stdout)
        self.assertTrue((self.harness / "settings.md").is_file(), "sync leaves the team's files alone")

    def test_copies_the_skill_into_every_skills_directory_at_the_project_root(self):
        other = self.tmp / ".claude" / "skills"
        other.mkdir(parents=True)
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((other / "vf" / "SKILL.md").is_file())
        self.assertIn("created ../../../.claude/skills/vf/SKILL.md", result.stdout)
        self.assertFalse((self.tmp / ".cursor").exists(), "a skills directory the team doesn't use is not created")

    def test_an_audit_script_an_earlier_framework_vendored_is_removed_and_not_recopied(self):
        run_sync(self.harness)
        for name in ("break_checks.py", "smells.py", "weakened.py"):
            self.assertNotIn(name, vf.FRAMEWORK_SCRIPTS)
            self.assertFalse(self.framework_copy(name).exists(), f"{name} belongs to the installed skill only")
        stale = self.framework_copy("smells.py")
        stale.write_text("# vendored by an earlier framework\n")
        lock = self.harness / validate.FRAMEWORK_LOCK
        lock.write_text(lock.read_text() + f"{vf.file_hash(stale.read_bytes())}  scripts/framework/smells.py\n")
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("removed scripts/framework/smells.py", result.stdout)
        self.assertFalse(stale.exists())

    def test_removes_a_file_an_earlier_sync_recorded_that_the_framework_no_longer_ships(self):
        run_sync(self.harness)
        stale = self.harness.parent / "vf" / "references" / "dropped.md"
        stale.write_text("gone from the framework\n")
        lock = self.harness / validate.FRAMEWORK_LOCK
        lock.write_text(lock.read_text() + f"{vf.file_hash(stale.read_bytes())}  ../vf/references/dropped.md\n")
        result = run_sync(self.harness)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("removed ../vf/references/dropped.md", result.stdout)
        self.assertFalse(stale.exists())


class ScriptCommands(unittest.TestCase):
    def test_every_command_names_a_framework_script(self):
        for script, _ in vf.SCRIPT_COMMANDS.values():
            self.assertIn(script, vf.FRAMEWORK_SCRIPTS)

    def test_passes_arguments_output_and_exit_code_through(self):
        arguments = ["--not-a-flag", "--nor-this"]
        direct = subprocess.run([sys.executable, str(vf.SCRIPTS_DIR / "validate.py"), *arguments], capture_output=True, text=True)
        through_vf = subprocess.run([sys.executable, str(SCRIPT), "validate", *arguments], capture_output=True, text=True)
        self.assertNotEqual(direct.returncode, 0)
        self.assertIn("unrecognized arguments: --not-a-flag --nor-this", direct.stderr)
        self.assertEqual(through_vf.returncode, direct.returncode)
        self.assertEqual(through_vf.stdout, direct.stdout)
        self.assertEqual(through_vf.stderr, direct.stderr)

# A check that reports its run as events in VERIFY_REPORT, shaped by the JSON spec in argv[1].
CHECK = """
import json, os, sys
from pathlib import Path
spec = json.loads(sys.argv[1])
if spec.get("touch"):
    Path("app.txt").write_text("edited while running\\n")
if spec.get("touch_harness"):
    Path(spec["touch_harness"]).write_text("loosened while running\\n")
run_dir = Path(os.environ["VERIFY_RUN_DIR"])
for name in spec.get("files", []):
    (run_dir / name).write_text("x")
events = spec.get("events")
if events is None:
    events = [{"event": "check", "name": spec.get("name", "pay"), "sub_features": ["app.pay"], "reads": "state"}]
    if "needs_checkout" in sys.argv[2:]:
        events += [{"event": "step", "name": "order is paid", "passed": True, "at": 1.0,
                    "detail": os.environ.get("VERIFY_CHECKOUT_APP", "")}]
    else:
        events += spec.get("steps", [{"event": "step", "name": "order is paid", "passed": True, "at": 1.0}])
    events += spec.get("more", [])
if not spec.get("no_report"):
    with open(os.environ["VERIFY_REPORT"], "a") as report:
        for event in events:
            report.write(json.dumps(event) + "\\n")
        for line in spec.get("raw", []):
            report.write(line + "\\n")
sys.exit(spec.get("exit", 0))
"""

# A check that reports its steps as it goes, then waits, cleaning up in a finally block as a plain Python
# check would; it installs no signal handler, so only a signal Python turns into an exception runs it.
WAITING_CHECK = """
import json, os, sys, time
from pathlib import Path
spec = json.loads(sys.argv[1])
report = open(os.environ["VERIFY_REPORT"], "a")
def report_event(event):
    report.write(json.dumps(event) + "\\n")
    report.flush()
try:
    report_event({"event": "check", "name": "pay", "sub_features": spec.get("sub_features", ["app.pay"]), "reads": "state"})
    for step in spec["steps"]:
        report_event(step)
    time.sleep(spec["wait"])
    Path(spec["finished"]).write_text("ran to the end\\n")
except KeyboardInterrupt:
    report_event({"event": "stopped", "reason": "interrupted"})
    sys.exit(3)
finally:
    Path(spec["cleaned"]).write_text("cleaned up\\n")
sys.exit(spec.get("exit", 0))
"""

CHECK_EVENT = {"event": "check", "name": "pay", "sub_features": ["app.pay"], "reads": "state"}
PASSED_STEP = {"event": "step", "name": "order is paid", "passed": True, "at": 1.0}
FAILED_STEP = [{"event": "step", "name": "order is paid", "passed": False, "at": 1.0, "detail": "status=pending"}]



class BreakStop(unittest.TestCase):
    def test_the_stop_reaches_cleanup_when_vf_run_was_started_ignoring_sigint(self):
        # A shell's background job starts with SIGINT ignored, and a child inherits that across exec.
        child = (
            "import json, os, sys, time\n"
            "from pathlib import Path\n"
            "try:\n"
            "    open(os.environ['VERIFY_REPORT'], 'a').write(json.dumps({'event': 'step', 'name': 's', 'passed': False}) + '\\n')\n"
            "    time.sleep(60)\n"
            "finally:\n"
            "    Path(sys.argv[1]).write_text('cleaned up')\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            report, cleaned = folder / "report.jsonl", folder / "cleaned"
            report.write_text("")
            previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                _, ended = vf.run_break_check([sys.executable, "-c", child, str(cleaned)], folder,
                                              {**os.environ, "VERIFY_REPORT": str(report)}, report,
                                              lambda events: "judged" if events else None)
            finally:
                signal.signal(signal.SIGINT, previous)
            self.assertEqual(ended, {"reason": "judged", "killed": False})
            self.assertTrue(cleaned.exists())


class BreakCheckGroup(unittest.TestCase):
    def test_a_hangup_reaches_the_check_and_the_group_file_lasts_only_while_it_runs(self):
        # A closed terminal or an agent's timeout signals vf.py run's process group, which the check is not in.
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            group_file = folder / "check-group"
            runner, check = start_break_runner(SCRIPT, folder, group_file)
            self.assertEqual(group_file.read_text(), str(check))

            os.killpg(runner.pid, signal.SIGHUP)

            self.assertTrue(wait_until_gone(check), "the check kept running after vf.py run got SIGHUP")
            runner.wait(10)
            self.assertFalse(group_file.exists())


class HarnessCommands(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.project)
        git(self.project, "init", "-q", "-b", "main")
        (self.project / "app.txt").write_text("first\n")
        git(self.project, "add", ".")
        git(self.project, "commit", "-qm", "first")
        self.harness = self.project / ".agents" / "skills" / "verify-app"
        self.assertEqual(vf.sync(self.harness)[1], 0)
        self.write_settings()
        (self.harness / "scripts" / "pay.py").write_text("# the check\n")

    def write_settings(self, doctor="echo verify: ready", start="echo {checkout:app} > pointed.txt", reloads=False):
        write_manifest(self.harness, commands={"start": start, "stop": "none", "doctor": doctor, "reloads": reloads})

    def run_check(self, env=None, named=(), **spec):
        command = [sys.executable, str(self.harness / "scripts/framework/vf.py"), "run", "--",
                   sys.executable, "-c", CHECK, json.dumps(spec), *named]
        return subprocess.run(command, capture_output=True, text=True, env={**os.environ, **(env or {})})

    def open_break_session(self):
        """Open a planned break session on the app repo, closed when the test ends."""
        (self.project / ".gitignore").write_text("pointed.txt\n.agents/\n")
        git(self.project, "add", ".gitignore")
        git(self.project, "commit", "-qm", "ignore")
        started = subprocess.run([sys.executable, str(self.harness / "scripts/framework/vf.py"), "break", "start", "app"],
                                 capture_output=True, text=True)
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.addCleanup(subprocess.run, [sys.executable, str(self.harness / "scripts/framework/vf.py"), "break", "end", "app"],
                        capture_output=True)

    def assemble(self, events, exit_code, files=()):
        """The record and problems vf.assemble builds from a check's events, with files present in its run folder."""
        run_dir = self.project / "run"
        run_dir.mkdir(exist_ok=True)
        for name in files:
            (run_dir / name).write_text("x")
        problems = []
        record, _ = vf.assemble([dict(event) for event in events], exit_code, run_dir, problems)
        return record, problems

    def evidence(self, check="pay"):
        files = list((self.harness / "evidence" / check).glob("*.json"))
        self.assertEqual(len(files), 1, files)
        return files[0]

    def record(self, check="pay"):
        return json.loads(self.evidence(check).read_text())

    def assert_refused(self, result, reason, folder="pay"):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn(reason, result.stdout)
        self.assertEqual(list((self.harness / "evidence").glob("*/*.json")), [])
        refused = list((self.harness / "evidence" / folder).glob("*.json.refused"))
        self.assertEqual(len(refused), 1, refused)
        return json.loads(refused[0].read_text())

    def test_accepts_a_sound_pass_and_keeps_the_checks_exit_code(self):
        (self.project / "e2e").mkdir()
        (self.project / "e2e" / "pay.sh").write_text("#!/bin/sh\n")
        result = self.run_check(named=["e2e/pay.sh"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"Accepted evidence/pay/\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z\.json")
        self.assertNotIn("not refreshed", result.stdout, "no feature map yet is an empty map, so status.md is refreshed")
        self.assertTrue((self.harness / "status.md").is_file())
        record = self.record()
        self.assertEqual(record["accepted_by"], "vf.py run")
        self.assertEqual((record["check"], record["sub_features"], record["reads"], record["passed"]), ("pay", ["app.pay"], "state", True))
        self.assertEqual(record["steps"], [{"name": "order is paid", "passed": True, "at": 1.0}])
        self.assertEqual(record["code"]["app"]["commit"], git(self.project, "rev-parse", "HEAD"))
        self.assertEqual(record["doctor"], {"exit_code": 0, "output": "verify: ready"})
        self.assertEqual(list(record["harness_code"]),
                         [".agents/skills/verify-app/harness.json", ".agents/skills/verify-app/scripts/pay.py", "e2e/pay.sh"])
        self.assertIsNone(record["planned_break"])
        self.assertIsNone(record["stopped"])
        self.assertLessEqual(record["started_at"], record["finished_at"])
        self.assertTrue(self.evidence().with_suffix("").joinpath("replay.html").is_file())
        self.assertNotIn("Recording kept", result.stdout)

    def test_a_failed_step_with_exit_1_is_a_sound_failure(self):
        record, problems = self.assemble([CHECK_EVENT, *FAILED_STEP], 1)
        self.assertEqual(problems, [])
        self.assertFalse(record["passed"])
        self.assertEqual(record["steps"][0]["detail"], "status=pending")

    def test_a_verdict_its_exit_code_contradicts_is_a_problem(self):
        cases = (([CHECK_EVENT, PASSED_STEP], 1, "exited 1 but no step failed"),
                 ([CHECK_EVENT, *FAILED_STEP], 0, "exited 0 but step 'order is paid' failed"),
                 ([CHECK_EVENT, PASSED_STEP, {"event": "stopped", "reason": "browser crashed"}], 0, "reported it stopped but exited 0"))
        for events, exit_code, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(self.assemble(events, exit_code)[1], [expected])

    def test_a_crash_keeps_the_steps_that_finished(self):
        record, problems = self.assemble([CHECK_EVENT, PASSED_STEP], 3)
        self.assertEqual(problems, [])
        self.assertEqual((record["passed"], record["stopped"]), (None, "the check exited 3"))
        self.assertEqual(record["steps"][0]["name"], "order is paid")

    def test_a_report_line_that_is_not_an_event_is_a_problem(self):
        report = self.project / "report.jsonl"
        report.write_text(json.dumps(CHECK_EVENT) + "\n\nnot json\n{\"event\": \"hello\"}\n")
        events, problems = vf.report_events(report)
        self.assertEqual(events, [CHECK_EVENT])
        self.assertEqual(problems, ["report line 3 is not JSON: not json",
                                    "report line 4 names no event among check, step, mark, recording, created, stopped: {\"event\": \"hello\"}"])

    def test_refuses_a_run_that_reported_no_check(self):
        self.assert_refused(self.run_check(no_report=True), "reported no check event", folder=".pending")

    def test_the_check_event_may_come_after_its_steps(self):
        record, problems = self.assemble([PASSED_STEP, CHECK_EVENT], 0)
        self.assertEqual(problems, [])
        self.assertEqual(record["sub_features"], ["app.pay"])

    def test_steps_name_the_sub_features_a_check_covers_in_order_without_repeats(self):
        steps = [{"name": "order is paid", "sub_features": ["app.pay"]},
                 {"name": "receipt is sent", "sub_features": ["app.receipt", "app.pay"]}, {"name": "setup"}]
        self.assertEqual(vf.judged_by_steps(steps), ["app.pay", "app.receipt"])

    def test_a_check_that_stops_before_any_step_is_recorded_against_what_the_map_says_it_proves(self):
        script = self.harness / "scripts" / "pay_check.py"
        script.write_text(CHECK)
        stop = {"events": [{"event": "check", "name": "pay", "reads": "state"},
                           {"event": "stopped", "reason": "the daily budget is spent"}], "exit": 2}
        command = ["python3", ".agents/skills/verify-app/scripts/pay_check.py", json.dumps(stop)]
        write_feature(self.harness, "pay", {"app.pay": {"words": "the order is paid", "check": shlex.join(command), "reads": "state"},
                                            "app.refund": {"words": "the order is refunded"}}, name="Pay")
        result = subprocess.run([sys.executable, str(self.harness / "scripts/framework/vf.py"), "run", "--", *command],
                                capture_output=True, text=True, cwd=self.project)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        record = self.record()
        self.assertEqual((record["sub_features"], record["passed"], record["stopped"]), (["app.pay"], None, "the daily budget is spent"))
        self.assertIn("app.pay: Not verified. Run stopped", (self.harness / "status.md").read_text())

        # A command the map doesn't prove anything with is refused, as it can't say what it covers.
        shutil.rmtree(self.harness / "evidence" / "pay")
        self.assert_refused(self.run_check(**stop), "has invalid sub_features")

    def test_a_break_run_that_stops_after_its_setup_steps_is_recorded_as_stopped_and_proves_no_break(self):
        script = self.harness / "scripts" / "pay_check.py"
        script.write_text(CHECK)
        stop = {"events": [{"event": "check", "name": "pay", "reads": "state"},
                           {"event": "step", "name": "customer signs in", "passed": True, "at": 1.0, "sub_features": ["app.login"]},
                           {"event": "stopped", "reason": "the sandbox listed no ticket"}], "exit": 2}
        command = ["python3", ".agents/skills/verify-app/scripts/pay_check.py", json.dumps(stop)]
        self.open_break_session()
        write_feature(self.harness, "pay", {"app.login": {"words": "the customer signs in"},
                                            "app.pay": {"words": "the order is paid", "check": shlex.join(command), "reads": "state"}}, name="Pay")
        result = subprocess.run([sys.executable, str(self.harness / "scripts/framework/vf.py"), "run", "--", *command],
                                capture_output=True, text=True, cwd=self.project,
                                env={**os.environ, "VERIFY_PLANNED_BREAK": "app.pay: payment skipped"})
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("Accepted evidence/pay/", result.stdout)
        record = self.record()
        self.assertEqual((record["sub_features"], record["stopped"]), (["app.login", "app.pay"], "the sandbox listed no ticket"))
        self.assertEqual(vf.sibling("break_session").record_breaks(self.harness, self.evidence()),
                         ["No break recorded: the break run stopped (the sandbox listed no ticket); run the break again"])

    def test_refuses_a_check_name_that_is_not_a_folder_name(self):
        self.assert_refused(self.run_check(name="pay/../refund"), "names check 'pay/../refund'", folder=".pending")

    def test_refuses_a_run_during_which_the_code_or_the_harness_changed(self):
        result = self.run_check(touch=True, touch_harness=str(self.harness / "scripts" / "pay.py"))
        self.assert_refused(result, "ran while the code changed in app")
        self.assertIn("ran while the harness's own code changed", result.stdout)

    def test_the_doctor_runs_first_and_a_not_ready_app_stops_the_run(self):
        self.write_settings(doctor="echo not ready: process 42 has exited; exit 1")
        result = self.run_check()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("STOPPED: the app is not ready (doctor exited 1); no check ran:\nnot ready: process 42 has exited", result.stderr)
        self.assertFalse((self.harness / "evidence").exists() and any((self.harness / "evidence").rglob("*.json*")))

        self.write_settings(doctor="exit 2")
        result = self.run_check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("the doctor could not tell whether the app is ready (doctor exited 2)", result.stderr)

        edit_manifest(self.harness, lambda d: d["commands"].pop("doctor"))
        result = self.run_check()
        self.assertEqual(result.returncode, 2)
        self.assertIn("harness.json names no doctor command", result.stderr)

    def test_run_hands_each_repo_checkout_to_the_doctor_and_the_check(self):
        # The doctor and the check both get VERIFY_CHECKOUT_APP naming the checkout the run records.
        self.write_settings(doctor='test "$VERIFY_CHECKOUT_APP" = "$PWD" && echo verify: ready')
        result = self.run_check(named=("needs_checkout",))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.record()["doctor"]["exit_code"], 0)
        self.assertEqual(self.record()["steps"][0]["detail"], str(self.project.resolve()))

    def test_other_checks_under_scripts_checks_are_not_fingerprinted_with_the_named_one(self):
        checks = self.harness / "scripts" / "checks"
        (checks / "refund").mkdir(parents=True)
        (checks / "pay.py").write_text("# pay check\n")
        (checks / "refund" / "main.py").write_text("# refund check\n")
        (checks / "refund" / "steps.py").write_text("# refund steps\n")
        (self.harness / "scripts" / "reads.py").write_text("# shared reads\n")
        harness = ".agents/skills/verify-app"
        shared = [f"{harness}/harness.json", f"{harness}/scripts/pay.py", f"{harness}/scripts/reads.py"]

        def manifest(*named):
            return sorted(validate.harness_code(self.harness, [sys.executable, "-c", CHECK, "{}", *named]))

        self.assertEqual(manifest(f"{harness}/scripts/checks/pay.py"), sorted(shared + [f"{harness}/scripts/checks/pay.py"]))
        self.assertEqual(manifest(f"{harness}/scripts/checks/refund/main.py"),
                         sorted(shared + [f"{harness}/scripts/checks/refund/main.py", f"{harness}/scripts/checks/refund/steps.py"]))
        # A command that names no check could be running any of them, so every check stays in scope.
        self.assertEqual(manifest(), sorted(shared + [f"{harness}/scripts/checks/pay.py", f"{harness}/scripts/checks/refund/main.py",
                                                      f"{harness}/scripts/checks/refund/steps.py"]))

    def test_a_planned_break_records_the_repo_of_its_session_and_needs_one(self):
        env = {"VERIFY_PLANNED_BREAK": "app.pay: payment skipped"}
        result = self.run_check(env=env, exit=1, steps=FAILED_STEP)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("no break session open", result.stderr)
        self.assertFalse((self.harness / "evidence" / "pay").exists())

        self.open_break_session()
        result = self.run_check(env=env, exit=1, steps=FAILED_STEP)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(self.record()["planned_break"], {"what": "payment skipped", "sub_features": ["app.pay"], "repo": "app"})

    def run_waiting_break(self, steps, wait, exit):
        """Run WAITING_CHECK as a planned break aimed at app.pay. Returns the result, the break's record, and
        whether the check's cleanup ran and whether it ran to its end."""
        marks = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, marks)
        spec = {"steps": steps, "wait": wait, "exit": exit, "cleaned": str(marks / "cleaned"), "finished": str(marks / "finished")}
        result = subprocess.run([sys.executable, str(self.harness / "scripts/framework/vf.py"), "run", "--",
                                 sys.executable, "-c", WAITING_CHECK, json.dumps(spec)],
                                capture_output=True, text=True, timeout=60,
                                env={**os.environ, "VERIFY_PLANNED_BREAK": "app.pay: payment skipped"})
        records = [json.loads(path.read_text()) for path in (self.harness / "evidence" / "pay").glob("*.json")]
        broken = [record for record in records if record["planned_break"]]
        self.assertEqual(len(broken), 1, result.stdout + result.stderr)
        return result, broken[0], (marks / "cleaned").exists(), (marks / "finished").exists()

    def test_a_break_run_ends_once_every_target_failed_and_lets_the_check_clean_up(self):
        self.open_break_session()
        result, record, cleaned, finished = self.run_waiting_break(FAILED_STEP, wait=30, exit=1)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual((cleaned, finished), (True, False))
        self.assertEqual(record["ended_early"], {"reason": "every target failed a step judging it", "killed": False})
        # The stop the check reported while cleaning up is not the run's verdict, so the break still counts.
        self.assertEqual((record["passed"], record["stopped"]), (False, None))
        self.assertEqual(vf.sibling("break_session").record_breaks(self.harness, self.evidence()),
                         ["Break recorded for app.pay: step 'order is paid' caught it"])

    def test_a_missed_break_ends_after_the_last_step_that_judged_a_target_in_the_latest_pass_and_exits_0(self):
        self.assertEqual(self.run_check().returncode, 0)
        self.open_break_session()
        result, record, cleaned, finished = self.run_waiting_break([PASSED_STEP], wait=30, exit=0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((cleaned, finished), (True, False))
        self.assertRegex(record["ended_early"]["reason"],
                         r"^step 'order is paid' passed, the last step to judge a target in evidence/pay/[^ ]+\.json$")
        self.assertEqual((record["passed"], record["stopped"]), (True, None))
        self.assertIn("Accepted evidence/pay/", result.stdout)

    def test_a_break_with_no_earlier_pass_runs_to_the_end(self):
        self.open_break_session()
        result, record, cleaned, finished = self.run_waiting_break([PASSED_STEP], wait=1, exit=0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((cleaned, finished), (True, True))
        self.assertNotIn("ended_early", record)

    def test_a_pass_of_other_harness_code_cannot_end_a_missed_break(self):
        self.assertEqual(self.run_check().returncode, 0)
        (self.harness / "scripts" / "pay.py").write_text("# the check, edited since its pass\n")
        self.open_break_session()
        result, record, cleaned, finished = self.run_waiting_break([PASSED_STEP], wait=1, exit=0)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((cleaned, finished), (True, True))
        self.assertNotIn("ended_early", record)

    def test_a_planned_break_in_a_checkout_two_repos_share_names_the_repo_its_session_was_started_for(self):
        (self.project / "mailer").mkdir()
        (self.project / "mailer" / "app.txt").write_text("first\n")
        git(self.project, "add", "mailer")
        git(self.project, "commit", "-qm", "mailer")
        edit_manifest(self.harness, lambda d: d["repos"].update(mailer="mailer"))
        self.open_break_session()
        scratch = Path((self.project / "pointed.txt").read_text().strip())
        (scratch / "mailer" / "app.txt").write_text("broken\n")
        env = {"VERIFY_PLANNED_BREAK": "app.pay: payment skipped"}

        result = self.run_check(env=env, exit=1, steps=FAILED_STEP)

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        record = self.record()
        self.assertEqual(record["planned_break"]["repo"], "app")
        self.assertTrue(record["code"]["mailer"]["dirty"])
        self.assertFalse(vf.sibling("code_state").checkout_state(self.project / "mailer", self.harness)["dirty"])

        # Sessions on two separate checkouts still leave the break without one repo to name.
        service = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, service)
        git(service, "init", "-q", "-b", "main")
        (service / "app.txt").write_text("first\n")
        git(service, "add", ".")
        git(service, "commit", "-qm", "first")
        edit_manifest(self.harness, lambda d: d["repos"].update(service=os.path.relpath(service, self.project)))
        framework_vf = str(self.harness / "scripts/framework/vf.py")
        started = subprocess.run([sys.executable, framework_vf, "break", "start", "service"], capture_output=True, text=True)
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.addCleanup(subprocess.run, [sys.executable, framework_vf, "break", "end", "service"], capture_output=True)
        result = self.run_check(env=env, exit=1, steps=FAILED_STEP)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("break sessions are open on app, service", result.stderr)

    def test_a_kept_recording_and_snapshot_move_into_the_run_folder(self):
        failed = [{"event": "step", "name": "order is paid", "passed": False, "at": 4.0,
                   "snapshot": {"screenshot": "step-1-failed.png", "text": "step-1-failed.txt"}}]
        marks = [{"event": "mark", "kind": "step", "label": "Step 1: Customer pays", "at": 0.5},
                 {"event": "recording", "video": "video.webm", "starts_at": 0.2},
                 {"event": "created", "orders": ["o_1"]}, {"event": "created", "orders": ["o_2"]}]
        result = self.run_check(exit=1, steps=failed, more=marks, files=["video.webm", "step-1-failed.png", "step-1-failed.txt"])
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        record, path = self.record(), self.evidence()
        stamp = path.stem
        self.assertEqual(record["recording"], {"video": f"pay/{stamp}/video.webm", "starts_at": 0.2})
        self.assertEqual(record["steps"][0]["snapshot"], {"screenshot": f"pay/{stamp}/step-1-failed.png", "text": f"pay/{stamp}/step-1-failed.txt"})
        self.assertEqual(record["created"], {"orders": ["o_1", "o_2"]})
        self.assertEqual(record["marks"][0]["label"], "Step 1: Customer pays")
        self.assertTrue((self.harness / "evidence" / record["recording"]["video"]).is_file())
        self.assertFalse((self.harness / "evidence" / ".pending").exists())
        self.assertIn(f"Recording kept. Watch it at {self.harness / 'recordings.html'}", result.stdout)

    def test_refuses_a_recording_or_snapshot_that_is_not_in_the_run_folder(self):
        self.assert_refused(self.run_check(more=[{"event": "recording", "video": "video.webm", "starts_at": 0.2}]),
                            "names recording video.webm, which is not in the run folder")
        shutil.rmtree(self.harness / "evidence" / "pay")
        self.assert_refused(self.run_check(more=[{"event": "recording", "video": "../video.webm", "starts_at": 0.2}], files=["video.webm"]),
                            "names recording '../video.webm', which is not a file name in the run folder")
        shutil.rmtree(self.harness / "evidence" / "pay")
        self.assert_refused(self.run_check(steps=[{"event": "step", "name": "order is paid", "passed": True, "at": 1.0, "snapshot": {"before": "shot.png"}}]),
                            "names snapshot before shot.png, which is not in the run folder")

    def test_a_planned_break_run_through_vf_run_records_the_scratch_code_and_logs_the_break(self):
        (self.project / ".gitignore").write_text("pointed.txt\n.agents/\n")
        git(self.project, "add", ".gitignore")
        git(self.project, "commit", "-qm", "ignore")
        self.write_map()
        framework = self.harness / "scripts" / "framework"

        def framework_command(*args):
            return subprocess.run([sys.executable, str(framework / "vf.py"), *args], capture_output=True, text=True)

        started = framework_command("break", "start", "app")
        self.assertEqual(started.returncode, 0, started.stdout + started.stderr)
        self.addCleanup(framework_command, "break", "end", "app")
        scratch = Path((self.project / "pointed.txt").read_text().strip())
        (scratch / "app.txt").write_text("broken\n")
        check = [sys.executable, "-c", CHECK, json.dumps({"exit": 1, "steps": FAILED_STEP})]

        result = framework_command("break", "run", "app", "app.pay: payment skipped", "--",
                                   sys.executable, str(framework / "vf.py"), "run", "--", *check)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Accepted evidence/pay/", result.stdout)
        record, path = self.record(), self.evidence()
        self.assertEqual(record["accepted_by"], "vf.py run")
        self.assertTrue(record["code"]["app"]["dirty"])
        self.assertEqual(record["planned_break"], {"what": "payment skipped", "sub_features": ["app.pay"], "repo": "app"})
        self.assertIn("+broken", path.with_suffix(".patch").read_text())
        self.assertIn("Break recorded for app.pay: step 'order is paid' caught it", result.stdout)
        logged = json.loads((self.harness / "evidence" / "breaks.jsonl").read_text().splitlines()[0])
        self.assertEqual((logged["sub_feature"], logged["check"], logged["what"], logged["step"], logged["evidence"]),
                         ("app.pay", "pay", "payment skipped", "order is paid", f"evidence/pay/{path.name}"))
        self.assertEqual((self.harness / "features" / "app.json").read_text(), self.feature_text())
        self.assertIn("- app.pay: Not verified. No accepted run on this machine. No scratch copy yet.", (self.harness / "status.md").read_text())

        framework_command("break", "end", "app")
        passed = self.run_check()
        self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
        self.assertRegex((self.harness / "status.md").read_text(),
                         r"- app\.pay: Verified\. pay, reads state, app [0-9a-f]{7}\. Break-tested \d{4}-\d{2}-\d{2}: payment skipped\. Evidence: ")

    def test_stops_outside_a_harness(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "run", "--", "true"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("vf.py run works from a harness's scripts/framework/", result.stderr)

    def feature_text(self, command="true"):
        return json.dumps(self.feature_data(command), indent=2) + "\n"

    def feature_data(self, command="true"):
        return {"name": "App", "summary": "The app.", "reach": ["Pay button."], "behaviors": {
            "app.pay": {"words": "order is paid", "check": command, "reads": "state", "not_break_tested": "no scratch copy yet."},
            "app.refund": {"words": "order is refunded"}}}

    def write_map(self, command="true"):
        features = self.harness / "features"
        features.mkdir(exist_ok=True)
        (features / "app.json").write_text(self.feature_text(command))
        (self.harness / "notes.md").write_text("# Verification notes\n\n## Untested cases\n\n- Two payments at once.\n")

    def check_command(self, **spec):
        """A proof-line command that runs the fake check, saved as a script, from the project root."""
        (self.project / "e2e").mkdir(exist_ok=True)
        (self.project / "e2e" / "check.py").write_text(CHECK)
        return " ".join(shlex.quote(part) for part in (sys.executable, "e2e/check.py", json.dumps(spec)))

    def test_run_records_only_the_repos_the_behavior_names_and_tolerates_a_missing_other(self):
        edit_manifest(self.harness, lambda d: d["repos"].update(api="../nowhere"))
        command = self.check_command(name="pay")
        (self.harness / "notes.md").write_text("# Verification notes\n")

        def proof(repos):
            entry = {"words": "order is paid", "check": command, "reads": "state"}
            if repos:
                entry["repos"] = repos
            write_feature(self.harness, "app", {"app.pay": entry}, name="App")

        # Without repos named the run needs every manifest repo, and api is not on this machine.
        proof(None)
        result = self.framework("run", "--", *shlex.split(command))
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("api: no Git checkout at ../nowhere", result.stderr)

        # Naming app alone lets the run record app only, and the check gets only app's checkout.
        proof(["app"])
        result = self.framework("run", "--", *shlex.split(command))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(list(self.record()["code"]), ["app"])
        self.assertIn("- app.pay: Not verified. Passed but not break-tested", (self.harness / "status.md").read_text())

    def test_verify_runs_each_named_behaviors_check_once_and_reports_its_result(self):
        self.write_map(self.check_command(name="pay"))
        edit_feature(self.harness, "app", lambda d: d["behaviors"]["app.refund"].update(check=self.check_command(name="pay"), reads="state"))
        result = self.framework("verify", "app.pay", "app.refund", "app.pay")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("Running `"), 1)
        self.assertEqual(result.stdout.count("Accepted evidence/pay/"), 1)
        self.assertRegex(result.stdout, r"\n- app\.pay: Not verified\. Passed but not break-tested: no scratch copy yet\. app [0-9a-f]{7}( \(uncommitted [0-9a-f]{8}\))?\. Evidence: evidence/pay/.*\n- app\.refund: Not verified\. No accepted run on this machine\.\n$")

    def test_verify_stops_when_the_app_is_not_ready_and_names_a_behavior_the_map_lacks(self):
        self.write_map(self.check_command())
        self.write_settings(doctor="echo not ready: nothing on port 3000; exit 1")
        result = self.framework("verify", "app.pay")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("STOPPED: the app is not ready (doctor exited 1); no check ran:\nnot ready: nothing on port 3000", result.stdout)
        self.assertEqual(list((self.harness / "evidence").glob("*/*.json")), [])
        result = self.framework("verify", "app.nothing")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not in the feature map: app.nothing", result.stderr)

    def test_verify_with_start_starts_the_app_when_the_doctor_says_not_ready(self):
        self.write_map(self.check_command())
        marker = self.project / "up.txt"
        self.write_settings(doctor=f"test -f {marker}", start=f"touch {marker}")
        (self.project / ".gitignore").write_text("up.txt\n")
        git(self.project, "add", ".gitignore")
        git(self.project, "commit", "-qm", "ignore")
        refused = self.framework("verify", "app.pay")
        self.assertEqual(refused.returncode, 2, refused.stdout)
        result = self.framework("verify", "app.pay", "--start")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"Starting the app: touch {marker}\nThe doctor reports the app ready.\n", result.stdout)
        self.assertIn("Accepted evidence/pay/", result.stdout)
        self.write_settings(doctor="exit 1", start="user")
        result = self.framework("verify", "app.pay", "--start")
        self.assertEqual(result.returncode, 2)
        self.assertIn("only a person starts the app", result.stderr)

    def framework(self, *args):
        return subprocess.run([sys.executable, str(self.harness / "scripts/framework/vf.py"), *args], capture_output=True, text=True)

    def test_an_accepted_run_refreshes_latest_results(self):
        self.write_map()
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        status = (self.harness / "status.md").read_text()
        self.assertTrue(status.startswith("# Verification status\n\n## Latest results\n\n"), status)
        self.assertIn("- app.pay: Not verified. Passed but not break-tested: no scratch copy yet. app "
                      + git(self.project, "rev-parse", "HEAD")[:7] + f". Evidence: evidence/pay/{self.evidence().name}\n", status)
        self.assertIn("- app.refund: Not verified. No check yet.\n", status)
        self.assertNotIn("Untested", status)
        self.assertEqual((self.harness / "notes.md").read_text(), "# Verification notes\n\n## Untested cases\n\n- Two payments at once.\n")

    def test_a_harness_with_no_features_folder_has_an_empty_map(self):
        # Git keeps no empty folder, so a fresh clone of a harness with no feature yet has no features/ at all.
        result = self.framework("status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.harness / "status.md").read_text().startswith("# Verification status\n"))
        self.assertNotIn("Not verified", (self.harness / "status.md").read_text())
        result = self.framework("verify", "app.pay")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("app.pay", result.stdout + result.stderr)

    def test_status_writes_latest_results_and_prints_them(self):
        self.write_map()
        result = self.framework("status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["- app.pay: Not verified. No accepted run on this machine. No scratch copy yet.",
                                                      "- app.refund: Not verified. No check yet."])
        self.assertIn("- app.pay: Not verified. No accepted run on this machine.", (self.harness / "status.md").read_text())

        (self.harness / "features" / "app.json").write_text("[]")
        before = (self.harness / "status.md").read_text()
        result = self.framework("status")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("status.md not written: fix the feature map first", result.stdout)
        self.assertEqual((self.harness / "status.md").read_text(), before)

    def test_status_creates_the_first_status_md(self):
        # Setup runs status to create the file the harness README links.
        self.write_map()
        (self.harness / "status.md").unlink(missing_ok=True)
        result = self.framework("status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.harness / "status.md").read_text().startswith("# Verification status\n\n## Latest results\n"))
        self.assertIn("- app.refund: Not verified. No check yet.", (self.harness / "status.md").read_text())

    def test_status_warns_when_the_latest_pass_is_not_on_this_checkouts_head(self):
        self.write_map()
        (self.project / "app.txt").write_text("second\n")
        git(self.project, "commit", "-qam", "second")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("WARN", self.framework("status").stdout)

        git(self.project, "commit", "-q", "--allow-empty", "-m", "third")
        self.assertIn("WARN app last pass is 1 commit behind HEAD for app.pay", self.framework("status").stdout)

        # Rewriting the tested commit, as a rebase does, leaves HEAD without it rather than behind it.
        git(self.project, "reset", "-q", "--hard", "HEAD~1")
        git(self.project, "commit", "-q", "--amend", "-m", "second, reworded")
        tested = self.record()["code"]["app"]["commit"]
        self.assertIn(f"WARN app last pass ran on {tested[:12]}, which is not in HEAD's history (rebased, or another branch) for app.pay",
                      self.framework("status").stdout)

    def test_not_verified_records_a_reason_that_a_later_run_lifts(self):
        self.write_map()
        result = self.framework("not-verified", "app.pay", "the sandbox account expired; tried the saved-card route")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Recorded app.pay: Not verified. the sandbox account expired; tried the saved-card route", result.stdout)
        self.assertIn("- app.pay: Not verified. The sandbox account expired; tried the saved-card route. Recorded ", result.stdout)
        entry = json.loads((self.harness / "evidence" / "not-verified.jsonl").read_text().splitlines()[0])
        self.assertEqual(entry["sub_feature"], "app.pay")
        self.assertNotIn("until", entry)

        # A run after the record lifts it; the record is backdated so the run need not wait for the next second.
        log = self.harness / "evidence" / "not-verified.jsonl"
        log.write_text(json.dumps(dict(entry, at="2000-01-01T00:00:00Z")) + "\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("- app.pay: Not verified. Passed but not break-tested", (self.harness / "status.md").read_text())

        result = self.framework("not-verified", "app.pay", "the paid step was rewritten", "--until-break")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("a new planned break lifts it.", result.stdout)
        self.assertIn("WARN app.pay has stood Not verified for today (the paid step was rewritten); a new planned break aimed at it lifts it", result.stdout)
        status = self.framework("status")
        self.assertIn("WARN app.pay has stood Not verified for today", status.stdout)
        result = self.framework("not-verified", "app.nothing", "x")
        self.assertEqual(result.returncode, 2)
        self.assertIn("app.nothing is not a sub-feature in the feature map", result.stderr)


if __name__ == "__main__":
    unittest.main()
