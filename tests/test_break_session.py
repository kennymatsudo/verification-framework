import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import git

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"


SCRIPT = SCRIPTS / "break_session.py"
SPEC = importlib.util.spec_from_file_location("verification_break_session", SCRIPT)
break_session = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(break_session)
code_state = break_session.code_state

# A check that writes planned break evidence, failing when the scratch copy's app.txt holds the break.
CHECK = """
import json, os, sys
from pathlib import Path
scratch = Path(sys.argv[1]).read_text().strip()
broken = Path(scratch, "app.txt").read_text() == "broken\\n"
folder = Path(sys.argv[2], "evidence", "pay")
folder.mkdir(parents=True, exist_ok=True)
ids, _, what = os.environ["VERIFY_PLANNED_BREAK"].partition(": ")
record = {"check": "pay", "passed": not broken, "planned_break": {"what": what, "sub_features": ids.split(",")}}
(folder / f"run-{len(list(folder.glob('*.json')))}.json").write_text(json.dumps(record))
sys.exit(1 if broken else 0)
"""



def make_project(directory, point="`echo {checkout} > pointed.txt`", after_edit="reloads"):
    project = Path(directory) / "project"
    project.mkdir()
    git(project, "init", "-q", "-b", "main")
    (project / ".gitignore").write_text("pointed.txt\n")
    (project / "app.txt").write_text("first\n")
    (project / "staged.txt").write_text("first\n")
    git(project, "add", ".")
    git(project, "commit", "-qm", "first")
    harness = project / ".agents" / "skills" / "verify-app"
    harness.mkdir(parents=True)
    (harness / "settings.md").write_text(
        "# App verification settings\n\n## Repos\n\n- app: .\n\n## Commands\n\n"
        f"- Start: make dev\n- Run scratch code: {point}\n- After an edit: {after_edit}\n"
    )
    return project, harness


def run(harness, *args):
    output, errors = io.StringIO(), io.StringIO()
    with patch.object(sys, "argv", [str(SCRIPT), "--harness", str(harness), *args]), \
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        result = break_session.main()
    return result, output.getvalue(), errors.getvalue()


def check_command(project, harness):
    return ["--", sys.executable, "-c", CHECK, str(project / "pointed.txt"), str(harness)]


def ordinary_state(harness, env, overrides=None):
    with patch.dict(os.environ, env, clear=False):
        for name in ("VERIFY_PLANNED_BREAK", "VERIFY_BREAK_SESSION"):
            if name not in env:
                os.environ.pop(name, None)
        return code_state.code_state(harness, overrides or {})


class BreakSessionTest(unittest.TestCase):
    def test_start_copies_the_code_under_test_and_blocks_ordinary_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            project, harness = make_project(directory)
            (project / "staged.txt").write_text("staged edit\n")
            git(project, "add", "staged.txt")
            (project / "app.txt").write_text("unstaged edit\n")
            (project / "new.txt").write_text("untracked\n")
            under_test = code_state.checkout_state(project, harness)

            result, output, errors = run(harness, "start", "app")

            self.assertEqual(result, 0, errors)
            scratch = Path((project / "pointed.txt").read_text().strip())
            self.assertIn(str(scratch), output)
            self.assertEqual(code_state.checkout_state(scratch, harness)["dirty_hash"], under_test["dirty_hash"])
            self.assertEqual(git(scratch, "diff", "--cached", "--name-only"), "staged.txt")
            with self.assertRaisesRegex(code_state.StateError, "break session is open"):
                ordinary_state(harness, {})
            planned = ordinary_state(harness, {"VERIFY_PLANNED_BREAK": "app.pay: skipped"})
            self.assertEqual(planned["app"]["dirty_hash"], under_test["dirty_hash"])
            self.assertEqual(run(harness, "start", "app")[0], 1)

    def test_run_saves_the_break_beside_its_evidence_and_restores_the_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            project, harness = make_project(directory)
            (project / "app.txt").write_text("under test\n")
            under_test = code_state.checkout_state(project, harness)
            run(harness, "start", "app")
            scratch = Path((project / "pointed.txt").read_text().strip())
            (scratch / "app.txt").write_text("broken\n")

            result, output, errors = run(harness, "run", "app", "app.pay: payment skipped", *check_command(project, harness))

            self.assertEqual(result, 0, errors)
            self.assertIn("Check exited 1", output)
            evidence = harness / "evidence" / "pay" / "run-0.json"
            self.assertEqual(json.loads(evidence.read_text())["planned_break"],
                             {"what": "payment skipped", "sub_features": ["app.pay"]})
            self.assertIn("+broken", (harness / "evidence" / "pay" / "run-0" / "break.patch").read_text())
            self.assertEqual((scratch / "app.txt").read_text(), "under test\n")
            self.assertEqual(code_state.checkout_state(scratch, harness)["dirty_hash"], under_test["dirty_hash"])
            self.assertEqual((project / "app.txt").read_text(), "under test\n")

            result, output, errors = run(harness, "replay", "app", str(evidence), *check_command(project, harness))

            self.assertEqual(result, 0, errors)
            self.assertIn("Check exited 1", output)
            replayed = json.loads((harness / "evidence" / "pay" / "run-1.json").read_text())
            self.assertEqual(replayed["planned_break"]["sub_features"], ["app.pay"])
            self.assertFalse(replayed["passed"])

    def test_checkout_overrides_cannot_bypass_an_open_session(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory)
            other = Path(directory) / "other"
            git(project, "clone", "-q", str(project), str(other))
            self.assertEqual(run(harness, "start", "app")[0], 0)
            cleanup.callback(run, harness, "end", "app")
            scratch = Path((project / "pointed.txt").read_text().strip())
            (scratch / "app.txt").write_text("broken\n")
            for checkout in (project, scratch, other):
                with self.subTest(checkout=checkout):
                    with self.assertRaisesRegex(code_state.StateError, "break session is open"):
                        ordinary_state(harness, {}, {"app": checkout})
            env = {"VERIFY_PLANNED_BREAK": "app.pay: skipped"}
            with self.assertRaisesRegex(code_state.StateError, "break session is open"):
                ordinary_state(harness, {"VERIFY_BREAK_SESSION": "other"})
            state = ordinary_state(harness, env, {"app": scratch})
            self.assertEqual(state["app"], code_state.checkout_state(scratch, harness))
            for checkout in (project, other):
                with self.subTest(checkout=checkout):
                    with self.assertRaisesRegex(code_state.StateError, "must name the session checkout"):
                        ordinary_state(harness, env, {"app": checkout})

            # An override into a repo with a session also blocks a harness whose locator names another repo.
            other_harness = other / ".agents" / "skills" / "verify-other"
            other_harness.mkdir(parents=True)
            (other_harness / "settings.md").write_text((harness / "settings.md").read_text())
            with self.assertRaisesRegex(code_state.StateError, "belongs to"):
                ordinary_state(other_harness, env, {"app": scratch})

    def test_another_harness_cannot_record_or_operate_the_session(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory)
            other_harness = harness.with_name("verify-other")
            other_harness.mkdir()
            (other_harness / "settings.md").write_text((harness / "settings.md").read_text())
            self.assertEqual(run(harness, "start", "app")[0], 0)
            cleanup.callback(run, harness, "end", "app")
            scratch = Path((project / "pointed.txt").read_text().strip())
            for env in ({}, {"VERIFY_PLANNED_BREAK": "app.pay: skipped"}, {"VERIFY_BREAK_SESSION": "app"}):
                with self.subTest(env=env):
                    with self.assertRaisesRegex(code_state.StateError, "belongs to"):
                        ordinary_state(other_harness, env)
            for action in (("start", "app"), ("run", "app", "app.pay: skipped", "--", sys.executable, "-c", "pass"),
                           ("end", "app")):
                with self.subTest(action=action):
                    result, _, errors = run(other_harness, *action)
                    self.assertEqual(result, 2)
                    self.assertIn(str(harness.resolve()), errors)
                    self.assertIsNotNone(code_state.open_session(project))
                    self.assertEqual(Path((project / "pointed.txt").read_text().strip()), scratch)
            self.assertIn(str(harness.resolve()), run(other_harness, "status")[1])
            self.assertEqual(run(harness, "end", "app")[0], 0)
            self.assertIsNotNone(ordinary_state(other_harness, {})["app"])

    def test_per_check_starts_the_app_from_scratch_and_records_its_loaded_version(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory, point="per check")
            app = project / "app.py"
            app.write_text('import json, subprocess, sys\nfrom pathlib import Path\n'
                           'code = json.loads(subprocess.check_output([sys.executable, *sys.argv[1:]], text=True))\n'
                           'print(json.dumps({"behavior": "working", "code": code, '
                           '"checkout": str(Path(__file__).resolve().parent)}))\n')
            git(project, "add", "app.py")
            git(project, "commit", "-qm", "CLI app")
            state_script = SCRIPT.with_name("code_state.py")
            healthy_command = [sys.executable, str(app), str(state_script), str(harness)]
            self.assertEqual(json.loads(subprocess.check_output(healthy_command, text=True))["behavior"], "working")
            self.assertEqual(run(harness, "start", "app")[0], 0)
            cleanup.callback(run, harness, "end", "app")
            scratch = Path(code_state.open_session(project)["scratch"])
            check = '''
import json, os, subprocess, sys
from pathlib import Path
checkout, harness, state_script = map(Path, sys.argv[1:])
app = json.loads(subprocess.check_output([sys.executable, str(checkout / "app.py"), str(state_script),
                                        str(harness), "--checkout", f"app={checkout}"], text=True))
assert Path(app["checkout"]) == checkout
ids, _, what = os.environ["VERIFY_PLANNED_BREAK"].partition(": ")
record = {"check": "cli", "passed": app["behavior"] == "working", "code": app["code"],
          "planned_break": {"what": what, "sub_features": ids.split(",")}}
folder = harness / "evidence" / "cli"
folder.mkdir(parents=True, exist_ok=True)
(folder / f"run-{len(list(folder.glob('*.json')))}.json").write_text(json.dumps(record))
sys.exit(0 if record["passed"] else 1)
'''
            command = ["--", sys.executable, "-c", check, str(scratch), str(harness),
                       str(SCRIPT.with_name("code_state.py"))]
            with self.assertRaisesRegex(code_state.StateError, "break session is open"):
                ordinary_state(harness, {})
            (scratch / "app.py").write_text(app.read_text().replace('"working"', '"broken"'))
            broken_code = code_state.checkout_state(scratch, harness)
            result, output, errors = run(harness, "run", "app", "app.cli: wrong output", *command)
            self.assertEqual(result, 0, errors)
            self.assertIn("Check exited 1", output)
            evidence = harness / "evidence" / "cli" / "run-0.json"
            record = json.loads(evidence.read_text())
            self.assertFalse(record["passed"])
            self.assertEqual(record["code"]["app"], broken_code)
            self.assertEqual((scratch / "app.py").read_text(), app.read_text())
            self.assertEqual(run(harness, "replay", "app", str(evidence), *command)[0], 0)
            self.assertFalse(json.loads(evidence.with_name("run-1.json").read_text())["passed"])
            self.assertEqual(run(harness, "end", "app")[0], 0)
            healthy = subprocess.check_output(healthy_command, text=True)
            self.assertEqual(json.loads(healthy)["behavior"], "working")

    def test_run_refuses_without_an_edit_or_after_the_developer_checkout_changed(self):
        with tempfile.TemporaryDirectory() as directory:
            project, harness = make_project(directory)
            run(harness, "start", "app")

            result, _, errors = run(harness, "run", "app", "app.pay: nothing", *check_command(project, harness))
            self.assertEqual(result, 1)
            self.assertIn("holds no edit", errors)

            (project / "app.txt").write_text("broken\n")
            result, _, errors = run(harness, "run", "app", "app.pay: wrong place", *check_command(project, harness))
            self.assertEqual(result, 1)
            self.assertIn("changed since the session started", errors)
            self.assertFalse((harness / "evidence").exists())

    def test_run_restores_the_copy_when_the_check_writes_no_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            project, harness = make_project(directory, after_edit="`touch restarted.txt`")
            run(harness, "start", "app")
            scratch = Path((project / "pointed.txt").read_text().strip())
            (scratch / "app.txt").write_text("broken\n")

            result, _, errors = run(harness, "run", "app", "app.pay: skipped", "--", sys.executable, "-c", "raise SystemExit(3)")

            self.assertEqual(result, 1)
            self.assertIn("last-break.patch", errors)
            self.assertTrue((project / "restarted.txt").exists())
            self.assertEqual((scratch / "app.txt").read_text(), "first\n")

    def test_end_points_back_removes_the_copy_and_reports_a_changed_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            project, harness = make_project(directory)
            run(harness, "start", "app")
            scratch = Path((project / "pointed.txt").read_text().strip())

            result, _, errors = run(harness, "end", "app")

            self.assertEqual(result, 0, errors)
            self.assertEqual(Path((project / "pointed.txt").read_text().strip()), project.resolve())
            self.assertFalse(scratch.exists())
            self.assertNotIn(str(scratch), git(project, "worktree", "list"))
            self.assertEqual(ordinary_state(harness, {})["app"]["dirty_hash"], None)
            self.assertEqual(run(harness, "end", "app")[0], 0)

            run(harness, "start", "app")
            (project / "app.txt").write_text("edited in the wrong place\n")
            result, _, errors = run(harness, "end", "app")
            self.assertEqual(result, 1)
            self.assertIn("app.txt", errors)
            self.assertIsNone(code_state.open_session(project))

    def test_a_session_follows_an_env_locator_the_point_command_rewrites(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Path(directory) / "service"
            service.mkdir()
            git(service, "init", "-q", "-b", "main")
            (service / "app.txt").write_text("first\n")
            git(service, "add", ".")
            git(service, "commit", "-qm", "first")
            project, harness = make_project(directory, point="echo SERVICE_DIR={checkout} > local.env")
            (project / ".gitignore").write_text("pointed.txt\nlocal.env\n")
            git(project, "commit", "-qam", "ignore local.env")
            (project / "local.env").write_text(f"SERVICE_DIR={service}\n")
            settings = harness / "settings.md"
            settings.write_text(settings.read_text().replace("- app: .\n", "- app: .\n- service: env:local.env:SERVICE_DIR\n"))

            self.assertEqual(run(harness, "start", "service")[0], 0)
            scratch = Path((project / "local.env").read_text().partition("=")[2].strip())
            self.assertNotEqual(scratch, service.resolve())
            (scratch / "app.txt").write_text("broken\n")
            result, _, errors = run(harness, "run", "service", "service.read: broken", "--", sys.executable, "-c", "pass")
            self.assertEqual(result, 1)
            self.assertIn("one planned break evidence file", errors)

            result, _, errors = run(harness, "end", "service")

            self.assertEqual(result, 0, errors)
            self.assertEqual((project / "local.env").read_text().strip(), f"SERVICE_DIR={service.resolve()}")
            self.assertFalse(scratch.exists())

    def test_start_stops_when_the_app_cannot_run_scratch_code(self):
        with tempfile.TemporaryDirectory() as directory:
            project, harness = make_project(directory, point="none")

            result, _, errors = run(harness, "start", "app")

            self.assertEqual(result, 2)
            self.assertIn("Not break-tested", errors)
            self.assertIsNone(code_state.open_session(project))

    def test_a_command_setting_loses_its_backticks_and_must_be_present(self):
        with tempfile.TemporaryDirectory() as directory:
            _, harness = make_project(directory)
            self.assertEqual(break_session.command_setting(harness, "Run scratch code"), "echo {checkout} > pointed.txt")
            (harness / "settings.md").write_text("# App verification settings\n\n## Commands\n\n- Start: make dev\n")
            with self.assertRaisesRegex(code_state.StateError, "has no '- Run scratch code:' line"):
                break_session.command_setting(harness, "Run scratch code")


if __name__ == "__main__":
    unittest.main()
