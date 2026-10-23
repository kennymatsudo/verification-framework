import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from support import git

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"

SCRIPT = SCRIPTS / "launch.py"

# A stand-in app: writes a ready file after a moment and sleeps until stopped, or exits at once with --crash.
APP = """
import sys, time
from pathlib import Path
if "--crash" in sys.argv:
    print("boom", flush=True)
    sys.exit(3)
print("starting", flush=True)
time.sleep(0.2)
Path("ready.txt").write_text("ready")
time.sleep(600)
"""



class Launch(unittest.TestCase):
    def setUp(self):
        self.project = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.project)
        git(self.project, "init", "-q", "-b", "main")
        (self.project / ".gitignore").write_text("ready.txt\n.agents/\n")
        (self.project / "app.py").write_text(APP)
        git(self.project, "add", ".")
        git(self.project, "commit", "-qm", "app")
        self.harness = self.project / ".agents" / "skills" / "verify-app"
        framework = self.harness / "scripts" / "framework"
        framework.mkdir(parents=True)
        for name in ("launch.py", "code_state.py", "validate.py"):
            shutil.copy(SCRIPTS / name, framework / name)
        (self.harness / "settings.md").write_text(
            "# App verification settings\n\n## Repos\n\n- app: .\n\n## Commands\n\n- Ready line: verify: ready\n")
        self.addCleanup(self.launch, "stop")

    def launch(self, *args):
        return subprocess.run([sys.executable, str(self.harness / "scripts/framework/launch.py"), *args], capture_output=True, text=True)

    def start(self, *extra):
        return self.launch("start", "--until", "test -f ready.txt", "--timeout", "10", *extra, "--", sys.executable, "app.py")

    def record(self):
        return json.loads((self.harness / "evidence" / "launch" / "record.json").read_text())

    def test_start_records_the_process_and_the_code_then_doctor_says_ready(self):
        result = self.start()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("started", result.stdout.splitlines()[-1])
        record = self.record()
        self.assertEqual(record["command"], [sys.executable, "app.py"])
        self.assertEqual(record["code"]["app"]["commit"], git(self.project, "rev-parse", "HEAD"))
        self.assertFalse(record["code"]["app"]["dirty"])
        self.assertTrue((self.project / "ready.txt").is_file())

        doctor = self.launch("doctor", "--probe", "test -f ready.txt")
        self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
        self.assertEqual(doctor.stdout.splitlines()[0], "verify: ready")
        self.assertEqual(json.loads("\n".join(doctor.stdout.splitlines()[1:]))["app"]["commit"], record["code"]["app"]["commit"])

        status = self.launch("status")
        self.assertEqual(json.loads(status.stdout)["state"], "running")

    def test_a_second_start_refuses_while_the_first_runs(self):
        self.assertEqual(self.start().returncode, 0)
        pid = self.record()["pid"]
        again = self.start()
        self.assertEqual(again.returncode, 1, again.stdout)
        self.assertIn(f"still running as process {pid}; stop it with `vf.py stop`", again.stdout)

    def test_stop_ends_the_process_group_and_removes_the_record_and_is_safe_to_repeat(self):
        self.assertEqual(self.start().returncode, 0)
        pid = self.record()["pid"]
        stopped = self.launch("stop")
        self.assertEqual(stopped.returncode, 0, stopped.stdout)
        self.assertIn(f"process {pid} stopped; record removed", stopped.stdout)
        self.assertFalse((self.harness / "evidence" / "launch" / "record.json").exists())
        time.sleep(0.2)
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)
        self.assertEqual(self.launch("stop").stdout.strip(), "nothing to stop")
        doctor = self.launch("doctor")
        self.assertEqual(doctor.returncode, 1)
        self.assertIn("no instance was started with vf.py start", doctor.stdout)

    def test_doctor_is_not_ready_when_the_checkout_changed_or_the_process_died_or_the_probe_fails(self):
        self.assertEqual(self.start().returncode, 0)
        (self.project / "app.py").write_text(APP + "\n# edited\n")
        doctor = self.launch("doctor")
        self.assertEqual(doctor.returncode, 1, doctor.stdout)
        self.assertIn("not ready: app changed since start (app ", doctor.stdout)
        self.assertIn("restart with vf.py stop and vf.py start", doctor.stdout)
        git(self.project, "checkout", "--", "app.py")

        doctor = self.launch("doctor", "--probe", "test -f missing.txt")
        self.assertEqual(doctor.returncode, 1, doctor.stdout)
        self.assertIn("not ready: `test -f missing.txt` exited 1", doctor.stdout)

        pid = self.record()["pid"]
        os.killpg(pid, 9)
        time.sleep(0.3)
        doctor = self.launch("doctor")
        self.assertEqual(doctor.returncode, 1, doctor.stdout)
        self.assertIn(f"not ready: process {pid} has exited", doctor.stdout)

        # A record whose process has exited never blocks the next start.
        self.assertEqual(self.start().returncode, 0)

    def test_an_app_that_crashes_or_never_becomes_ready_leaves_no_record_and_shows_its_output(self):
        crashed = self.launch("start", "--until", "test -f ready.txt", "--timeout", "5", "--", sys.executable, "app.py", "--crash")
        self.assertEqual(crashed.returncode, 1, crashed.stdout)
        self.assertIn("the app exited 3 before it was ready", crashed.stdout)
        self.assertIn("boom", crashed.stdout)
        self.assertFalse((self.harness / "evidence" / "launch" / "record.json").exists())

        slow = self.launch("start", "--until", "test -f never.txt", "--timeout", "1", "--", sys.executable, "app.py")
        self.assertEqual(slow.returncode, 1, slow.stdout)
        self.assertIn("did not satisfy `test -f never.txt` within 1s", slow.stdout)
        self.assertFalse((self.harness / "evidence" / "launch" / "record.json").exists())

    def test_start_without_until_returns_at_once(self):
        result = self.launch("start", "--", sys.executable, "app.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("started\n", result.stdout + "\n")
        self.assertTrue(result.stdout.startswith("started process "))

    def test_a_checkout_override_is_recorded_and_used_by_doctor(self):
        worktree = self.project.parent / (self.project.name + "-scratch")
        git(self.project, "worktree", "add", "-q", "--detach", str(worktree), "HEAD")
        self.addCleanup(git, self.project, "worktree", "remove", "--force", str(worktree))
        (worktree / "app.py").write_text(APP + "\n# scratch edit\n")
        result = self.start("--checkout", f"app={worktree}")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.record()["code"]["app"]["dirty"])
        self.assertEqual(self.record()["checkouts"], {"app": str(worktree)})
        doctor = self.launch("doctor")
        self.assertEqual(doctor.returncode, 0, doctor.stdout)
        (worktree / "app.py").write_text(APP + "\n# another edit\n")
        self.assertEqual(self.launch("doctor").returncode, 1)

    def test_stops_outside_a_harness(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "status"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("has no settings.md", result.stderr)

    def test_vf_passes_the_command_name_through(self):
        shutil.copy(SCRIPTS / "vf.py", self.harness / "scripts" / "framework" / "vf.py")
        launched = subprocess.run([sys.executable, str(self.harness / "scripts/framework/vf.py"), "doctor"], capture_output=True, text=True)
        self.assertEqual(launched.returncode, 1, launched.stdout + launched.stderr)
        self.assertIn("no instance was started with vf.py start", launched.stdout)


if __name__ == "__main__":
    unittest.main()
