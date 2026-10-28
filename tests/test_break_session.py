import contextlib
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness_json import edit_manifest, write_manifest  # noqa: E402
from support import alive, git, start_break_runner, wait_until_gone

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"


SCRIPT = SCRIPTS / "break_session.py"
SPEC = importlib.util.spec_from_file_location("verification_break_session", SCRIPT)
break_session = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(break_session)
code_state = break_session.code_state
validate = break_session.validate

# A check that writes planned break evidence, failing when the scratch copy's app.txt holds the break.
CHECK = """
import json, os, sys
from pathlib import Path
scratch = Path(sys.argv[1]).read_text().strip()
broken = Path(scratch, "app.txt").read_text() == "broken\\n"
folder = Path(sys.argv[2], "evidence", "pay")
folder.mkdir(parents=True, exist_ok=True)
ids, _, what = os.environ["VERIFY_PLANNED_BREAK"].partition(": ")
record = {"check": "pay", "passed": not broken, "planned_break": {"what": what, "sub_features": ids.split(","), "repo": "app"}}
(folder / f"run-{len(list(folder.glob('*.json')))}.json").write_text(json.dumps(record))
sys.exit(1 if broken else 0)
"""



def make_project(directory, start="echo {checkout:app} > pointed.txt", stop="none", reloads="yes"):
    project = Path(directory) / "project"
    project.mkdir()
    git(project, "init", "-q", "-b", "main")
    (project / ".gitignore").write_text("pointed.txt\nrestarted.txt\n")
    (project / "app.txt").write_text("first\n")
    (project / "staged.txt").write_text("first\n")
    git(project, "add", ".")
    git(project, "commit", "-qm", "first")
    harness = project / ".agents" / "skills" / "verify-app"
    harness.mkdir(parents=True)
    write_manifest(harness, commands={"start": start, "stop": stop, "reloads": reloads == "yes"})
    return project, harness


def make_monorepo(directory):
    """A monorepo whose harness sits in orders/ and lists orders and its neighbour mailer, both in one Git checkout."""
    root = Path(directory) / "monorepo"
    for folder in ("orders", "mailer"):
        (root / folder).mkdir(parents=True)
        (root / folder / "app.txt").write_text("first\n")
    git(root, "init", "-q", "-b", "main")
    (root / ".gitignore").write_text("pointed.txt\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "first")
    harness = root / "orders" / ".agents" / "skills" / "verify-orders"
    harness.mkdir(parents=True)
    write_manifest(harness, repos={"orders": ".", "mailer": "../mailer"},
                   commands={"start": "echo {checkout:orders} > pointed.txt", "stop": "none", "reloads": True})
    return root, harness


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
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory)
            (project / "staged.txt").write_text("staged edit\n")
            git(project, "add", "staged.txt")
            (project / "app.txt").write_text("unstaged edit\n")
            (project / "new.txt").write_text("untracked\n")
            under_test = code_state.checkout_state(project, harness)

            result, output, errors = run(harness, "start", "app")
            cleanup.callback(run, harness, "end", "app")

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
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory)
            (project / "app.txt").write_text("under test\n")
            under_test = code_state.checkout_state(project, harness)
            run(harness, "start", "app")
            cleanup.callback(run, harness, "end", "app")
            scratch = Path((project / "pointed.txt").read_text().strip())
            (scratch / "app.txt").write_text("broken\n")

            result, output, errors = run(harness, "run", "app", "app.pay: payment skipped", *check_command(project, harness))

            self.assertEqual(result, 0, errors)
            self.assertIn("Check exited 1", output)
            evidence = harness / "evidence" / "pay" / "run-0.json"
            self.assertEqual(json.loads(evidence.read_text())["planned_break"],
                             {"what": "payment skipped", "sub_features": ["app.pay"], "repo": "app"})
            self.assertIn("+broken", (harness / "evidence" / "pay" / "run-0.patch").read_text())
            self.assertEqual((scratch / "app.txt").read_text(), "under test\n")
            self.assertEqual(code_state.checkout_state(scratch, harness)["dirty_hash"], under_test["dirty_hash"])
            self.assertEqual((project / "app.txt").read_text(), "under test\n")

            result, output, errors = run(harness, "replay", str(evidence), *check_command(project, harness))

            self.assertEqual(result, 0, errors)
            self.assertIn("Check exited 1", output)
            replayed = json.loads((harness / "evidence" / "pay" / "run-1.json").read_text())
            self.assertEqual(replayed["planned_break"]["sub_features"], ["app.pay"])
            self.assertFalse(replayed["passed"])

    def test_replay_refuses_a_break_that_does_not_name_its_repo(self):
        with tempfile.TemporaryDirectory() as directory:
            _, harness = make_project(directory)
            evidence = harness / "evidence" / "pay" / "run-0.json"
            evidence.parent.mkdir(parents=True)
            evidence.write_text(json.dumps({"check": "pay", "planned_break": {"what": "skipped", "sub_features": ["app.pay"]}}))
            evidence.with_suffix(".patch").write_text("")

            result, _, errors = run(harness, "replay", str(evidence), "--", sys.executable, "-c", "pass")

            self.assertEqual(result, 2)
            self.assertIn("doesn't name the repo its break edited", errors)

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
            (other_harness / "harness.json").write_text((harness / "harness.json").read_text())
            with self.assertRaisesRegex(code_state.StateError, "belongs to"):
                ordinary_state(other_harness, env, {"app": scratch})

    def test_another_harness_cannot_record_or_operate_the_session(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory)
            other_harness = harness.with_name("verify-other")
            other_harness.mkdir()
            (other_harness / "harness.json").write_text((harness / "harness.json").read_text())
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

    def test_start_none_lets_each_check_run_the_code_from_its_checkout(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory, start="none")
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
          "planned_break": {"what": what, "sub_features": ids.split(","), "repo": "app"}}
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
            self.assertEqual(run(harness, "replay", str(evidence), *command)[0], 0)
            self.assertFalse(json.loads(evidence.with_name("run-1.json").read_text())["passed"])
            self.assertEqual(run(harness, "end", "app")[0], 0)
            healthy = subprocess.check_output(healthy_command, text=True)
            self.assertEqual(json.loads(healthy)["behavior"], "working")

    def test_run_refuses_without_an_edit_or_after_the_developer_checkout_changed(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory)
            run(harness, "start", "app")
            cleanup.callback(run, harness, "end", "app")

            result, _, errors = run(harness, "run", "app", "app.pay: nothing", *check_command(project, harness))
            self.assertEqual(result, 1)
            self.assertIn("holds no edit", errors)

            (project / "app.txt").write_text("broken\n")
            result, _, errors = run(harness, "run", "app", "app.pay: wrong place", *check_command(project, harness))
            self.assertEqual(result, 1)
            self.assertIn("changed since the session started", errors)
            self.assertFalse((harness / "evidence").exists())

    def test_run_restores_the_copy_when_the_check_writes_no_evidence(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory, start="echo {checkout:app} > pointed.txt && touch restarted.txt", reloads="no")
            run(harness, "start", "app")
            cleanup.callback(run, harness, "end", "app")
            scratch = Path((project / "pointed.txt").read_text().strip())
            (project / "restarted.txt").unlink()
            (scratch / "app.txt").write_text("broken\n")

            result, _, errors = run(harness, "run", "app", "app.pay: skipped", "--", sys.executable, "-c", "raise SystemExit(3)")

            self.assertEqual(result, 1)
            self.assertIn("last-break.patch", errors)
            self.assertTrue((project / "restarted.txt").exists(), "Reloads: no restarts the app before the break check")
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

    def test_a_break_runs_on_a_repo_found_through_an_env_locator(self):
        with tempfile.TemporaryDirectory() as directory:
            service = Path(directory) / "service"
            service.mkdir()
            git(service, "init", "-q", "-b", "main")
            (service / "app.txt").write_text("first\n")
            git(service, "add", ".")
            git(service, "commit", "-qm", "first")
            # Start names the service checkout; vf fills it, so the env file never needs rewriting.
            project, harness = make_project(directory, start="echo {checkout:service} > pointed.txt")
            (project / ".gitignore").write_text("pointed.txt\nlocal.env\n")
            git(project, "commit", "-qam", "ignore local.env")
            (project / "local.env").write_text(f"SERVICE_DIR={service}\n")
            data = json.loads((harness / "harness.json").read_text())
            data["repos"]["service"] = "env:local.env:SERVICE_DIR"
            (harness / "harness.json").write_text(json.dumps(data))

            self.assertEqual(run(harness, "start", "service")[0], 0)
            scratch = Path((project / "pointed.txt").read_text().strip())
            self.assertNotEqual(scratch, service.resolve())
            self.assertTrue(scratch.is_relative_to(Path(code_state.open_session(service)["worktree"])))
            (scratch / "app.txt").write_text("broken\n")
            result, _, errors = run(harness, "run", "service", "service.read: broken", "--", sys.executable, "-c", "pass")
            self.assertEqual(result, 1)
            self.assertIn("one planned break evidence file", errors)

            result, _, errors = run(harness, "end", "service")

            self.assertEqual(result, 0, errors)
            self.assertEqual((project / "local.env").read_text().strip(), f"SERVICE_DIR={service}")
            self.assertEqual(Path((project / "pointed.txt").read_text().strip()), service.resolve())
            self.assertFalse(scratch.exists())

    def test_one_session_serves_every_repo_in_a_shared_checkout(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            root, harness = make_monorepo(directory)
            orders, mailer = root / "orders", root / "mailer"
            (mailer / "app.txt").write_text("the mailer's own edit\n")
            mailer_state = code_state.checkout_state(mailer, harness)

            self.assertEqual(run(harness, "start", "orders")[0], 0)
            cleanup.callback(run, harness, "end", "orders")
            scratch = Path((orders / "pointed.txt").read_text().strip())

            # A start, run, or end on the other repo names the repo whose session is open.
            for action in (("start", "mailer"), ("run", "mailer", "mailer.send: skipped", "--", sys.executable, "-c", "pass"),
                           ("end", "mailer")):
                with self.subTest(action=action):
                    result, _, errors = run(harness, *action)
                    self.assertEqual(result, 1)
                    self.assertIn("open for orders", errors)
                    self.assertIn("vf.py break end orders", errors)
            # Ordinary recording stays refused for both repos.
            for name, locator in (("orders", "."), ("mailer", "../mailer")):
                with self.subTest(repo=name), patch.dict(os.environ):
                    os.environ.pop("VERIFY_PLANNED_BREAK", None)
                    os.environ.pop("VERIFY_BREAK_SESSION", None)
                    with self.assertRaisesRegex(code_state.StateError, "break end orders"):
                        code_state.recorded_checkout(name, locator, None, harness)
            # A break run names the repo the session was started for and records each repo from its folder in the copy.
            self.assertEqual(code_state.break_session_repo(harness), "orders")
            planned = ordinary_state(harness, {"VERIFY_PLANNED_BREAK": "orders.pay: skipped"})
            self.assertEqual(planned["orders"], code_state.checkout_state(scratch, harness))
            self.assertEqual(planned["mailer"]["dirty_hash"], mailer_state["dirty_hash"])
            status = run(harness, "status")[1]
            self.assertIn(f"orders: break session open on {scratch}", status)
            self.assertIn(f"mailer: break session for orders open on {scratch}", status)

            self.assertEqual(run(harness, "end", "orders")[0], 0)
            self.assertIsNone(code_state.open_session(mailer))
            self.assertEqual(run(harness, "start", "mailer")[0], 0)
            cleanup.callback(run, harness, "end", "mailer")
            self.assertEqual(code_state.break_session_repo(harness), "mailer")
            self.assertEqual(run(harness, "end", "mailer")[0], 0)

    def test_start_stops_when_only_a_person_can_start_the_app(self):
        with tempfile.TemporaryDirectory() as directory:
            project, harness = make_project(directory, start="user")

            result, _, errors = run(harness, "start", "app")

            self.assertEqual(result, 2)
            self.assertIn("Not break-tested", errors)
            self.assertIsNone(code_state.open_session(project))

    def test_a_command_setting_must_be_present(self):
        with tempfile.TemporaryDirectory() as directory:
            _, harness = make_project(directory)
            self.assertEqual(break_session.command_setting(harness, "start"), "echo {checkout:app} > pointed.txt")
            (harness / "harness.json").write_text(json.dumps({"commands": {"stop": "none"}}))
            with self.assertRaisesRegex(code_state.StateError, "names no start command"):
                break_session.command_setting(harness, "start")


def make_pr_worktree(directory, reloads=False):
    """A project with its harness committed, and a marked worktree of it whose harness copy is the one that runs,
    as verify-pr sets one up. The app already runs the worktree, as pointed.txt says; every Start also appends
    the checkout it got to starts.txt, and the doctor is ready only while the app runs the checkout under test."""
    project, harness = make_project(directory, start="echo {checkout:app} > pointed.txt && echo {checkout:app} >> starts.txt",
                                    reloads="yes" if reloads else "no")
    edit_manifest(harness, lambda data: data["commands"].update(doctor='test "$(cat pointed.txt)" = "$VERIFY_CHECKOUT_APP"'))
    (project / ".gitignore").write_text("pointed.txt\nstarts.txt\n")
    git(project, "add", ".")
    git(project, "commit", "-qm", "harness")
    pr = Path(directory) / "pr"
    result, _, errors = run(harness, "worktree", "app", str(pr), "HEAD", "--branch", "vf-pr/1-checks")
    assert result == 0, errors
    pr = pr.resolve()
    (pr / "pointed.txt").write_text(f"{pr}\n")
    return project, pr, pr / harness.relative_to(project)


def marker_path(checkout):
    return break_session.git_dirs(checkout)[0] / break_session.OWNER_MARKER


def starts(project):
    """The checkouts Start was given, in order; empty when it never ran."""
    path = project / "starts.txt"
    return path.read_text().split() if path.exists() else []


def write_check(path):
    """A check command that writes path, a file in the copy, and nothing else."""
    return ["--", sys.executable, "-c", "import sys; open(sys.argv[1], 'w').write('made by the check')", str(path)]


class InPlaceSessionTest(unittest.TestCase):
    def test_worktree_refuses_a_path_that_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            project, harness = make_project(directory)
            existing = Path(directory) / "existing"
            existing.mkdir()

            result, _, errors = run(harness, "worktree", "app", str(existing), "HEAD")

            self.assertEqual(result, 1)
            self.assertIn("already exists", errors)
            self.assertEqual(len(git(project, "worktree", "list").splitlines()), 1)
            self.assertEqual(list(existing.iterdir()), [])

    def test_start_breaks_in_place_in_a_marked_worktree_without_restarting_the_app(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, pr, harness = make_pr_worktree(directory)
            # A commit of harness files alone keeps the product code the marker names.
            (harness / "notes.md").write_text("checks being built\n")
            git(pr, "add", ".")
            git(pr, "commit", "-qm", "checks")

            result, output, errors = run(harness, "start", "app")
            cleanup.callback(run, harness, "end", "app")

            self.assertEqual(result, 0, errors)
            self.assertIn(f"in place: {pr}", output)
            self.assertEqual(starts(pr), [])
            self.assertEqual(len(git(project, "worktree", "list").splitlines()), 2)
            with self.assertRaisesRegex(code_state.StateError, "break session is open"):
                ordinary_state(harness, {})
            with self.assertRaisesRegex(code_state.StateError, "belongs to"):
                ordinary_state(project / harness.relative_to(pr), {})
            planned = ordinary_state(harness, {"VERIFY_PLANNED_BREAK": "app.pay: skipped"})
            self.assertEqual(planned["app"], code_state.checkout_state(pr, harness))
            self.assertIn(f"app: break session open in place on {pr}, at its starting state", run(harness, "status")[1])

    def test_start_in_place_refuses_when_the_doctor_says_the_app_runs_other_code(self):
        with tempfile.TemporaryDirectory() as directory:
            project, pr, harness = make_pr_worktree(directory)
            (pr / "pointed.txt").write_text(f"{project}\n")

            result, _, errors = run(harness, "start", "app")

            self.assertEqual(result, 1, errors)
            self.assertIn("the app is not ready", errors)
            self.assertIsNone(code_state.open_session(pr))
            self.assertEqual(starts(pr), [])

    def test_start_copies_an_unmarked_checkout_as_before(self):
        with tempfile.TemporaryDirectory() as directory:
            project, _, _ = make_pr_worktree(directory)
            mine = Path(directory) / "mine"
            git(project, "worktree", "add", "-q", str(mine), "HEAD")
            for name, checkout in (("the main worktree", project), ("a developer's worktree", mine.resolve())):
                with self.subTest(name):
                    harness = checkout / ".agents" / "skills" / "verify-app"
                    result, output, errors = run(harness, "start", "app")
                    self.assertEqual(result, 0, errors)
                    self.assertIn("in a new scratch worktree", output)
                    scratch = Path((checkout / "pointed.txt").read_text().strip())
                    self.assertNotEqual(scratch, checkout)
                    self.assertEqual(run(harness, "end", "app")[0], 0)
                    self.assertFalse(scratch.exists())

    def test_start_refuses_a_marked_worktree_that_fails_a_precondition(self):
        def uncommitted(project, pr, harness):
            (pr / "app.txt").write_text("someone's edit\n")
            return "uncommitted product code"

        def product_commit(project, pr, harness):
            (pr / "app.txt").write_text("new code\n")
            git(pr, "commit", "-qam", "new code")
            return "no longer matches"

        def other_repo(project, pr, harness):
            marker = json.loads(marker_path(pr).read_text())
            marker_path(pr).write_text(json.dumps({**marker, "repo": "other"}))
            return "another harness or repo"

        def unreadable(project, pr, harness):
            marker_path(pr).write_text("{not json")
            return "can't be read"

        def main_worktree(project, pr, harness):
            marker_path(project).write_text(marker_path(pr).read_text())
            return "main worktree"

        for case in (uncommitted, product_commit, other_repo, unreadable, main_worktree):
            with self.subTest(case.__name__), tempfile.TemporaryDirectory() as directory:
                project, pr, harness = make_pr_worktree(directory)
                reason = case(project, pr, harness)
                if case is main_worktree:
                    harness = project / harness.relative_to(pr)

                result, _, errors = run(harness, "start", "app")

                self.assertEqual(result, 1, errors)
                self.assertIn(reason, errors)
                self.assertIsNone(code_state.open_session(project))
                self.assertEqual(len(git(project, "worktree", "list").splitlines()), 2)
                self.assertEqual(starts(harness.parents[2]), [])

    def test_run_restores_product_code_and_keeps_the_harness_work(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, pr, harness = make_pr_worktree(directory)
            new_check = harness / "scripts" / "checks" / "pay.py"
            new_check.parent.mkdir(parents=True)
            new_check.write_text("# a check being built\n")
            (harness / "notes.md").write_text("staged\n")
            git(pr, "add", str(harness / "notes.md"))
            self.assertEqual(run(harness, "start", "app")[0], 0)
            cleanup.callback(run, harness, "end", "app")
            (pr / "app.txt").write_text("broken\n")
            (pr / "added.txt").write_text("a file the break added\n")
            new_check.write_text("# a check edited during the session\n")

            result, output, errors = run(harness, "run", "app", "app.pay: payment skipped", *check_command(pr, harness))

            self.assertEqual(result, 0, errors)
            self.assertIn("Check exited 1", output)
            patch_text = (harness / "evidence" / "pay" / "run-0.patch").read_text()
            self.assertIn("+broken", patch_text)
            self.assertNotIn("pay.py", patch_text)
            self.assertEqual((pr / "app.txt").read_text(), "first\n")
            self.assertFalse((pr / "added.txt").exists())
            self.assertEqual(new_check.read_text(), "# a check edited during the session\n")
            self.assertEqual(git(pr, "diff", "--cached", "--name-only"), str(harness.relative_to(pr) / "notes.md"))
            self.assertEqual(break_session.validate.uncommitted_files(pr, harness), [])
            self.assertEqual(starts(pr), [str(pr)])
            self.assertEqual(run(harness, "replay", str(harness / "evidence" / "pay" / "run-0.json"),
                                 *check_command(pr, harness))[0], 0)
            self.assertFalse(json.loads((harness / "evidence" / "pay" / "run-1.json").read_text())["passed"])
            self.assertEqual((pr / "app.txt").read_text(), "first\n")

    def test_a_session_in_place_restarts_once_per_break_and_once_at_end_unless_the_app_reloads(self):
        for reloads, expected in ((False, 3), (True, 0)):
            with self.subTest(reloads=reloads), tempfile.TemporaryDirectory() as directory:
                _, pr, harness = make_pr_worktree(directory, reloads=reloads)
                self.assertEqual(run(harness, "start", "app")[0], 0)
                for number in range(2):
                    (pr / "app.txt").write_text("broken\n")
                    result, _, errors = run(harness, "run", "app", f"app.pay: break {number}", *check_command(pr, harness))
                    self.assertEqual(result, 0, errors)

                self.assertEqual(run(harness, "end", "app")[0], 0)

                self.assertEqual(starts(pr), [str(pr)] * expected)

    def test_a_file_changed_during_the_check_holds_the_session_in_either_mode(self):
        def in_place(directory):
            _, pr, harness = make_pr_worktree(directory)
            self.assertEqual(run(harness, "start", "app")[0], 0)
            return harness, pr

        def scratch_copy(directory):
            project, harness = make_project(directory)
            self.assertEqual(run(harness, "start", "app")[0], 0)
            return harness, Path((project / "pointed.txt").read_text().strip())

        for setup in (in_place, scratch_copy):
            with self.subTest(setup.__name__), tempfile.TemporaryDirectory() as directory:
                harness, copy = setup(directory)
                (copy / "app.txt").write_text("broken\n")

                result, _, errors = run(harness, "run", "app", "app.pay: skipped", *write_check(copy / "generated.txt"))

                self.assertEqual(result, 1, errors)
                self.assertIn("generated.txt changed", errors)
                self.assertEqual((copy / "app.txt").read_text(), "broken\n")
                self.assertTrue((copy / "generated.txt").exists())
                self.assertIn("held: generated.txt changed", run(harness, "status")[1])
                result, _, errors = run(harness, "run", "app", "app.pay: skipped", *check_command(copy, harness))
                self.assertEqual(result, 1)
                self.assertIn("is held", errors)
                self.assertFalse((harness / "evidence").exists())
                with self.assertRaisesRegex(code_state.StateError, "break session is open"):
                    ordinary_state(harness, {})
                self.assertEqual(run(harness, "end", "app")[0], 0)
                self.assertIsNone(code_state.open_session(harness))

    def test_a_held_run_leaves_no_evidence_that_could_count_as_a_break(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            _, pr, harness = make_pr_worktree(directory)
            self.assertEqual(run(harness, "start", "app")[0], 0)
            cleanup.callback(run, harness, "end", "app")
            (pr / "app.txt").write_text("broken\n")
            # The check writes its evidence, then something else in the copy changes before restore.
            both = ("import subprocess, sys; subprocess.run([sys.executable, '-c', sys.argv[1], *sys.argv[2:4]]); "
                    "open(sys.argv[4], 'w').write('made during the check')")
            command = ["--", sys.executable, "-c", both, CHECK, str(pr / "pointed.txt"), str(harness), str(pr / "generated.txt")]

            # vf.py run writes status.md and recordings.html from the break before it is held, so both are rebuilt after.
            refreshed, rebuilt = [], []
            real_load = break_session._load
            def load(name, filename):
                module = real_load(name, filename)
                if filename == "vf.py":
                    module.refresh_status = lambda harness, validate: refreshed.append(break_session.evidence_files(harness)) or []
                    module.build_pages = lambda *arguments: rebuilt.append((arguments, break_session.evidence_files(harness))) or ""
                return module
            with patch.object(break_session, "_load", load):
                result, _, errors = run(harness, "run", "app", "app.pay: skipped", *command)

            self.assertEqual(result, 1, errors)
            self.assertIn("generated.txt changed", errors)
            self.assertEqual(break_session.evidence_files(harness), set())
            self.assertTrue(list((harness / "evidence").glob("*/*.held")))
            self.assertEqual(refreshed, [set()])
            self.assertEqual(rebuilt, [(("--recordings", str(harness)), set())])

    def test_a_restore_that_misses_holds_the_session(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            _, pr, harness = make_pr_worktree(directory)
            self.assertEqual(run(harness, "start", "app")[0], 0)
            cleanup.callback(run, harness, "end", "app")
            (pr / "app.txt").write_text("broken\n")

            with patch.object(break_session, "restore", lambda *args: None):
                result, _, errors = run(harness, "run", "app", "app.pay: skipped", *check_command(pr, harness))

            self.assertEqual(result, 1)
            self.assertIn("didn't return to its starting state (app.txt)", errors)
            self.assertIn("held", run(harness, "status")[1])
            self.assertEqual(run(harness, "end", "app")[0], 0)
            self.assertEqual((pr / "app.txt").read_text(), "first\n")

    def test_end_refuses_while_head_moved_and_keeps_the_session(self):
        with tempfile.TemporaryDirectory() as directory:
            _, pr, harness = make_pr_worktree(directory)
            self.assertEqual(run(harness, "start", "app")[0], 0)
            (pr / "app.txt").write_text("a break, committed\n")
            git(pr, "commit", "-qam", "break")

            result, _, errors = run(harness, "end", "app")

            self.assertEqual(result, 1)
            self.assertIn("HEAD moved", errors)
            session = code_state.open_session(pr)
            self.assertIsNotNone(session)
            self.assertFalse(session["ending"])
            self.assertEqual((pr / "app.txt").read_text(), "a break, committed\n")
            self.assertEqual(starts(pr), [])
            git(pr, "reset", "-q", "--hard", "HEAD~1")
            self.assertEqual(run(harness, "end", "app")[0], 0)

    def test_the_ending_field_ends_planned_break_recording(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            project, harness = make_project(directory)
            self.assertEqual(run(harness, "start", "app")[0], 0)
            cleanup.callback(run, harness, "end", "app")
            scratch = Path((project / "pointed.txt").read_text().strip())
            (scratch / "app.txt").write_text("broken\n")
            session = code_state.open_session(project)
            break_session.save_session(code_state.session_folder(project), {**session, "ending": True})

            with self.assertRaisesRegex(code_state.StateError, "break session is open"):
                ordinary_state(harness, {"VERIFY_PLANNED_BREAK": "app.pay: skipped"})
            with self.assertRaisesRegex(code_state.StateError, "no break session open"):
                code_state.break_session_repo(harness)
            pointing_back = ordinary_state(harness, {"VERIFY_BREAK_SESSION": "app"})
            self.assertEqual(pointing_back["app"], code_state.checkout_state(project, harness))
            result, _, errors = run(harness, "run", "app", "app.pay: skipped", *check_command(project, harness))
            self.assertEqual(result, 1)
            self.assertIn("is ending", errors)
            self.assertIn("ending; run end again", run(harness, "status")[1])

    def test_end_restores_restarts_and_keeps_the_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            project, pr, harness = make_pr_worktree(directory)
            self.assertEqual(run(harness, "start", "app")[0], 0)
            (pr / "app.txt").write_text("broken, never run\n")

            result, output, errors = run(harness, "end", "app")

            self.assertEqual(result, 0, errors)
            self.assertIn("stays in place", output)
            self.assertEqual((pr / "app.txt").read_text(), "first\n")
            self.assertEqual(starts(pr), [str(pr)])
            self.assertIn(str(pr), git(project, "worktree", "list"))
            self.assertTrue(marker_path(pr).exists())
            self.assertIsNone(code_state.open_session(pr))
            self.assertIsNotNone(ordinary_state(harness, {})["app"])



class LeftoverCheckTest(unittest.TestCase):
    def test_start_run_and_end_stop_a_check_its_killed_vf_run_left_running(self):
        vf_script = SCRIPTS / "vf.py"
        for action in (["start", "app"], ["run", "app", "app.pay: skipped", "--", sys.executable, "-c", "pass"], ["end", "app"]):
            with self.subTest(action[0]), tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
                project, harness = make_project(directory)
                self.assertEqual(run(harness, "start", "app")[0], 0)
                cleanup.callback(run, harness, "end", "app")
                folder = code_state.session_folder(project)
                runner, check = start_break_runner(vf_script, Path(directory), folder / code_state.CHECK_GROUP)
                cleanup.callback(wait_until_gone, check, 0)
                # What an agent's command timeout does: kill vf.py run outright, so nothing is passed on.
                os.killpg(runner.pid, signal.SIGKILL)
                runner.wait(10)
                self.assertTrue(alive(check))

                _, output, errors = run(harness, *action)

                self.assertTrue(wait_until_gone(check, 2), errors)
                self.assertIn(f"Stopped the check a killed `vf.py run` left running (process group {check}", output)
                self.assertFalse((folder / code_state.CHECK_GROUP).exists())


def make_two_repo_pr(directory):
    """A harness repo and a service repo the harness finds by a relative locator, as verify-pr meets them: the
    checks worktree of the harness repo, made from the developer's harness, holds the harness copy that runs,
    and a relative locator there still reaches the developer's own service checkout. The service PR's commit
    is one behind the developer's checkout, so a run shows which one it recorded."""
    directory = Path(directory).resolve()
    service = directory / "service"
    service.mkdir()
    git(service, "init", "-q", "-b", "main")
    (service / "app.txt").write_text("first\n")
    git(service, "add", ".")
    git(service, "commit", "-qm", "first")
    pr_commit = git(service, "rev-parse", "HEAD")
    (service / "app.txt").write_text("second\n")
    git(service, "commit", "-qam", "second")
    project, harness = make_project(directory, start="echo {checkout:service} > pointed.txt && echo {checkout:service} >> starts.txt",
                                    reloads="no")
    edit_manifest(harness, lambda data: (data["repos"].update(service="../service"),
                                         data["commands"].update(doctor="echo verify: ready")))
    (project / ".gitignore").write_text("pointed.txt\nstarts.txt\n")
    git(project, "add", ".")
    git(project, "commit", "-qm", "harness")
    checks = directory / "checks"
    result, output, errors = run(harness, "worktree", "app", str(checks), "HEAD", "--branch", "vf-pr/1-checks")
    assert result == 0, errors
    assert "holds this harness" in output, output
    return service, pr_commit, checks, checks / harness.relative_to(project), harness


class RecordedWorktreeTest(unittest.TestCase):
    def test_the_harness_repo_records_nothing_since_its_harness_copy_runs_there(self):
        with tempfile.TemporaryDirectory() as directory:
            _, _, _, checks_harness, harness = make_two_repo_pr(directory)
            self.assertIsNone(validate_file(harness))
            self.assertIsNone(validate_file(checks_harness))

    def test_the_other_repos_worktree_is_recorded_used_announced_and_cleared(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            service, pr_commit, checks, harness, developer_harness = make_two_repo_pr(directory)
            pr = Path(directory).resolve() / "service-pr"
            self.assertEqual(ordinary_state(harness, {})["service"]["commit"], git(service, "rev-parse", "HEAD"))
            fingerprint = validate.harness_code(harness, [])

            result, output, errors = run(harness, "worktree", "service", str(pr), pr_commit)

            self.assertEqual(result, 0, errors)
            self.assertIn(f"This harness now uses {pr} as service's checkout", output)
            self.assertEqual(json.loads(validate_file(harness).read_text()), {str(harness): {"service": str(pr)}})
            self.assertTrue(validate_file(harness).is_relative_to(Path(git(checks, "rev-parse", "--absolute-git-dir"))))
            self.assertEqual(git(checks, "status", "--porcelain"), "")
            self.assertEqual(validate.harness_code(harness, []), fingerprint)
            # The developer's own harness is untouched.
            self.assertIsNone(validate_file(developer_harness))
            self.assertEqual(ordinary_state(developer_harness, {})["service"]["commit"], git(service, "rev-parse", "HEAD"))

            # Every command that finds the checkout says it uses the recorded worktree.
            announced = f"service: using {pr}, the worktree `vf.py break worktree` recorded"
            validate.ANNOUNCED_WORKTREES.clear()
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                state = ordinary_state(harness, {})
            self.assertEqual(state["service"]["commit"], pr_commit)
            self.assertEqual(errors.getvalue().count(announced), 1)

            validate.ANNOUNCED_WORKTREES.clear()
            result, output, errors = run(harness, "start", "service")
            cleanup.callback(run, harness, "end", "service")
            self.assertEqual(result, 0, errors)
            self.assertIn(f"in place: {pr}", output)
            self.assertIn(announced, errors)
            self.assertEqual(run(harness, "end", "service")[0], 0)
            self.assertEqual((checks / "pointed.txt").read_text().strip(), str(pr))

            self.assertEqual(run(harness, "worktree", "--clear", "service")[0], 0)
            self.assertIsNone(validate_file(harness))
            validate.ANNOUNCED_WORKTREES.clear()
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                state = ordinary_state(harness, {})
            self.assertEqual(state["service"]["commit"], git(service, "rev-parse", "HEAD"))
            self.assertEqual(errors.getvalue(), "")
            self.assertIn(str(pr), git(service, "worktree", "list"))

    def test_clear_is_refused_while_a_break_session_is_open_on_the_worktree(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.ExitStack() as cleanup:
            _, pr_commit, _, harness, _ = make_two_repo_pr(directory)
            pr = Path(directory).resolve() / "service-pr"
            self.assertEqual(run(harness, "worktree", "service", str(pr), pr_commit)[0], 0)
            self.assertEqual(run(harness, "start", "service")[0], 0)
            cleanup.callback(run, harness, "end", "service")

            result, _, errors = run(harness, "worktree", "--clear", "service")

            self.assertEqual(result, 1)
            self.assertIn("break session is open", errors)
            self.assertEqual(validate.recorded_worktree(harness, "service"), pr)


def validate_file(harness):
    """The harness project's recorded-worktrees file when it exists, else None."""
    path = validate.worktrees_file(harness)
    return path if path and path.exists() else None

if __name__ == "__main__":
    unittest.main()
