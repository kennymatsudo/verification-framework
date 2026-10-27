import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness_json import edit_manifest, write_manifest  # noqa: E402
from support import git

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"


SCRIPT = SCRIPTS / "code_state.py"
SPEC = importlib.util.spec_from_file_location("verification_code_state", SCRIPT)
code_state = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(code_state)



def make_repo(path, branch="main"):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", branch)
    commit(path, "app.txt", "first\n")
    return path


def commit(path, name, text):
    (path / name).write_text(text)
    git(path, "add", name)
    git(path, "commit", "-qm", f"write {name}")
    return git(path, "rev-parse", "HEAD")


def make_harness(project, repos=None):
    harness = project / ".agents" / "skills" / "verify-app"
    harness.mkdir(parents=True)
    write_manifest(harness, repos={"app": "."} if repos is None else repos)
    return harness


def run_state(harness, *flags):
    output, errors = io.StringIO(), io.StringIO()
    with patch.object(sys, "argv", [str(SCRIPT), str(harness), *flags]), \
            contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        result = code_state.main()
    return result, json.loads(output.getvalue()) if result == 0 else None, errors.getvalue()


class CodeStateTest(unittest.TestCase):
    def test_dirty_hash_identifies_content_including_staged_and_untracked_files(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_repo(Path(directory))
            harness = make_harness(project)
            clean = code_state.checkout_state(project, harness)
            self.assertIsNone(clean["dirty_hash"])
            (project / "app.txt").write_text("second\n")
            first = code_state.checkout_state(project, harness)
            self.assertRegex(first["dirty_hash"], r"^[0-9a-f]{64}$")
            self.assertEqual(code_state.checkout_state(project, harness), first)
            (harness / "result.txt").write_text("harness output\n")
            self.assertEqual(code_state.checkout_state(project, harness), first)
            git(project, "add", "app.txt")
            staged = code_state.checkout_state(project, harness)
            (project / "app.txt").write_text("different staged content\n")
            git(project, "add", "app.txt")
            self.assertNotEqual(code_state.checkout_state(project, harness)["dirty_hash"], staged["dirty_hash"])
            (project / "app.txt").write_text("third\n")
            unstaged = code_state.checkout_state(project, harness)
            self.assertNotEqual(staged["dirty_hash"], unstaged["dirty_hash"])
            (project / "new file.txt").write_bytes(b"\x00first")
            untracked = code_state.checkout_state(project, harness)
            (project / "new file.txt").write_bytes(b"\x00second")
            self.assertNotEqual(code_state.checkout_state(project, harness)["dirty_hash"], untracked["dirty_hash"])
            (project / "new file.txt").unlink()
            (project / "app.txt").unlink()
            self.assertNotEqual(code_state.checkout_state(project, harness)["dirty_hash"], unstaged["dirty_hash"])

    def test_dirty_hash_ignores_ignored_files_and_matches_across_worktrees(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_repo(Path(directory) / "project")
            commit(project, ".gitignore", "cache/\n")
            harness = make_harness(project)
            git(project, "add", ".agents")
            git(project, "commit", "-qm", "harness settings")
            scratch = Path(directory) / "scratch"
            git(project, "worktree", "add", "-q", "--detach", str(scratch))
            scratch_harness = scratch / harness.relative_to(project)
            (scratch_harness / "harness.json").write_text("{}\n")
            self.assertFalse(code_state.checkout_state(scratch, harness)["dirty"])
            (project / "cache").mkdir()
            (project / "cache/output").write_text("ignored\n")
            self.assertIsNone(code_state.checkout_state(project, harness)["dirty_hash"])
            for path in (project, scratch):
                (path / "app.txt").write_text("same break\n")
                (path / "new.txt").write_text("same resource\n")
            self.assertEqual(code_state.checkout_state(project, harness)["dirty_hash"],
                             code_state.checkout_state(scratch, harness)["dirty_hash"])

    def test_reports_the_evidence_code_entry_and_dirty_as_rules_define_it(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_repo(Path(directory))
            harness = make_harness(project)
            (project / ".gitignore").write_text("cache/\n")
            commit(project, ".gitignore", "cache/\n")
            head = git(project, "rev-parse", "HEAD")
            (project / "cache").mkdir()
            (project / "cache" / "build.txt").write_text("ignored\n")
            (harness / "evidence").mkdir()
            (harness / "evidence" / "run.json").write_text("{}")

            result, state, _ = run_state(harness)
            self.assertEqual(result, 0)
            self.assertEqual(state, {"app": {"commit": head, "branch": "main", "dirty": False, "dirty_hash": None, "on_main": True}})

            (project / "migration.sql").write_text("new\n")
            _, state, _ = run_state(harness)
            self.assertTrue(state["app"]["dirty"])

    def test_on_main_follows_the_default_branch_and_is_null_when_there_is_none(self):
        for default, expected in (("main", True), ("master", True), ("trunk", None)):
            with self.subTest(default=default), tempfile.TemporaryDirectory() as directory:
                project = make_repo(Path(directory), branch=default)
                harness = make_harness(project)
                git(project, "switch", "-qc", "feature")
                commit(project, "feature.txt", "unmerged\n")

                _, state, _ = run_state(harness)
                self.assertEqual(state["app"]["branch"], "feature")
                self.assertEqual(state["app"]["on_main"], None if expected is None else False)

                git(project, "switch", "-q", default)
                _, state, _ = run_state(harness)
                self.assertEqual(state["app"]["on_main"], expected)

    def test_origin_head_outranks_a_local_main(self):
        with tempfile.TemporaryDirectory() as directory:
            origin = make_repo(Path(directory) / "origin", branch="develop")
            clone = Path(directory) / "clone"
            subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
            harness = make_harness(clone)
            git(clone, "switch", "-qc", "main")
            commit(clone, "local.txt", "only on local main\n")

            _, state, _ = run_state(harness)
            self.assertEqual(state["app"]["branch"], "main")
            self.assertFalse(state["app"]["on_main"])

    def test_checkout_override_reports_a_scratch_worktree(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_repo(Path(directory) / "project")
            head = git(project, "rev-parse", "HEAD")
            harness = make_harness(project)
            scratch = Path(directory) / "scratch"
            git(project, "worktree", "add", "-q", "--detach", str(scratch))
            (scratch / "app.txt").write_text("planned break\n")

            result, state, _ = run_state(harness, "--checkout", f"app={scratch}")
            self.assertEqual(result, 0)
            self.assertRegex(state["app"].pop("dirty_hash"), r"^[0-9a-f]{64}$")
            self.assertEqual(state["app"], {"commit": head, "branch": None, "dirty": True, "on_main": True})
            _, state, _ = run_state(harness)
            self.assertFalse(state["app"]["dirty"])

    def test_names_each_repo_from_its_locator(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_repo(Path(directory) / "project")
            worker = make_repo(Path(directory) / "worker", branch="master")
            (project / "local-dev").mkdir()
            (project / "local-dev" / ".env").write_text(f"WORKER={worker}\n")
            harness = make_harness(project, {"project": ".", "worker": "env:local-dev/.env:WORKER"})

            result, state, _ = run_state(harness)
            self.assertEqual(result, 0)
            self.assertEqual(sorted(state), ["project", "worker"])
            self.assertEqual(state["worker"]["commit"], git(worker, "rev-parse", "HEAD"))
            self.assertEqual(state["worker"]["branch"], "master")

    def test_stops_when_a_repo_cannot_be_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_repo(Path(directory) / "project")
            empty = Path(directory) / "empty"
            empty.mkdir()
            git(empty, "init", "-q")
            cases = {
                "missing checkout": ({"app": ".", "worker": "../missing"}, [], "worker: no Git checkout"),
                "invalid repo name": ({"app": ".", "Worker": "../worker"}, [], "repo name 'Worker' is not lowercase"),
                "unlisted override": ({"app": "."}, ["--checkout", f"api={project}"], "api, which harness.json does not list"),
                "no commit": ({"app": "."}, ["--checkout", f"app={empty}"], "has no commit"),
                "no repos": ({}, [], "repos must be a non-empty object"),
            }
            for case, (repos, flags, reason) in cases.items():
                with self.subTest(case):
                    harness = make_harness(Path(tempfile.mkdtemp(dir=project)), repos)
                    result, _, errors = run_state(harness, *flags)
                    self.assertEqual(result, 2)
                    self.assertIn("STOPPED:", errors)
                    self.assertIn(reason, errors)


class MonorepoTest(unittest.TestCase):
    """An app that is one folder of a larger repo: its harness sits in that folder's skills directory."""

    def make_monorepo(self, root):
        make_repo(root)
        for folder in ("app", "other"):
            (root / folder).mkdir()
            commit(root, f"{folder}/code.txt", "first\n")
        return make_harness(root / "app")

    def test_dirty_state_covers_only_the_apps_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            harness = self.make_monorepo(root)
            (root / "other" / "code.txt").write_text("another project's edit\n")
            (harness / "evidence").mkdir()
            (harness / "evidence" / "run.json").write_text("{}")

            result, state, errors = run_state(harness)
            self.assertEqual(result, 0, errors)
            self.assertFalse(state["app"]["dirty"])
            self.assertIsNone(state["app"]["dirty_hash"])
            self.assertEqual(state["app"]["commit"], git(root, "rev-parse", "HEAD"))

            (root / "app" / "code.txt").write_text("the app's edit\n")
            result, state, errors = run_state(harness)
            self.assertTrue(state["app"]["dirty"])
            self.assertRegex(state["app"]["dirty_hash"], "^[0-9a-f]{64}$")

    def test_a_repo_located_by_a_subfolder_is_dirty_only_inside_it(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_repo(Path(directory) / "project")
            services = make_repo(Path(directory) / "services")
            for folder in ("worker", "other"):
                (services / folder).mkdir()
                commit(services, f"{folder}/code.txt", "first\n")
            harness = make_harness(project, {"app": ".", "worker": "../services/worker"})

            (services / "other" / "code.txt").write_text("another service's edit\n")
            result, state, errors = run_state(harness)
            self.assertEqual(result, 0, errors)
            self.assertFalse(state["worker"]["dirty"])

            (services / "worker" / "code.txt").write_text("the worker's edit\n")
            result, state, errors = run_state(harness)
            self.assertTrue(state["worker"]["dirty"])

    def test_dirty_state_leaves_out_the_framework_skill_copies_sync_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            project = make_repo(Path(directory) / "project")
            harness = make_harness(project)
            git(project, "add", ".agents")
            git(project, "commit", "-qm", "harness settings")
            for name in ("vf",):
                (project / ".agents/skills" / name).mkdir()
                (project / ".agents/skills" / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
            lock = harness / code_state.validate.FRAMEWORK_LOCK
            lock.parent.mkdir(parents=True)
            lock.write_text("0" * 64 + "  ../vf/SKILL.md\n" + "0" * 64 + "  ../vf/references/rules.md\n")
            self.assertFalse(code_state.checkout_state(project, harness)["dirty"])
            (project / ".agents/skills/other").mkdir()
            (project / ".agents/skills/other/SKILL.md").write_text("the team's own skill\n")
            self.assertTrue(code_state.checkout_state(project, harness)["dirty"])

    def test_env_locators_read_their_file_from_the_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "monorepo"
            harness = self.make_monorepo(root)
            service = make_repo(Path(directory) / "service")
            (root / "app" / "local-dev").mkdir()
            (root / "app" / "local-dev" / ".env").write_text(f"SERVICE_DIR={service}\n")
            edit_manifest(harness, lambda d: d["repos"].update(service="env:local-dev/.env:SERVICE_DIR"))

            result, state, errors = run_state(harness)

            self.assertEqual(result, 0, errors)
            self.assertEqual(state["service"]["commit"], git(service, "rev-parse", "HEAD"))


if __name__ == "__main__":
    unittest.main()
