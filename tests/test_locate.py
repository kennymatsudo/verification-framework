import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "skills" / "vf" / "scripts"

sys.path.insert(0, str(SCRIPTS))
import locate  # noqa: E402

SCRIPT = SCRIPTS / "locate.py"
SKILL_MD = SCRIPTS.parent / "SKILL.md"
REPO_SKILLS = SCRIPTS.parent.parent


def make_skill(base, name):
    (base / name).mkdir(parents=True, exist_ok=True)
    (base / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")


class Locate(unittest.TestCase):
    def setUp(self):
        # Resolved, because macOS reaches its temp folder through a symlink.
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.installed = self.tmp / "installed"
        self.repo = self.tmp / "repo"
        self.home = self.tmp / "home"
        for d in (self.installed, self.repo, self.home):
            d.mkdir()
        self.router = self.installed / "vf"
        self.router.mkdir()

    def test_finds_siblings_beside_this_skill(self):
        for name in locate.SKILLS:
            make_skill(self.installed, name)
        found = locate.locate(self.router, self.repo, self.home)
        self.assertEqual(found["missing"], [])
        self.assertEqual(found["skills"]["vf-verify"], str(self.installed / "vf-verify" / "SKILL.md"))

    def test_finds_siblings_beside_the_real_folder_when_reached_by_symlink(self):
        make_skill(self.installed, "vf-verify")
        links = self.tmp / "links"
        links.mkdir()
        (links / "vf").symlink_to(self.router)
        found = locate.locate(links / "vf", self.repo, self.home)
        self.assertEqual(found["skills"]["vf-verify"], str(self.installed / "vf-verify" / "SKILL.md"))

    def test_falls_back_to_repo_then_home_skills_directories(self):
        make_skill(self.repo / ".agents/skills", "vf-verify")
        make_skill(self.home / ".claude/skills", "vf-verify")
        make_skill(self.home / ".claude/skills", "vf-explain")
        found = locate.locate(self.router, self.repo, self.home)
        self.assertEqual(found["skills"]["vf-verify"], str(self.repo / ".agents/skills/vf-verify/SKILL.md"))
        self.assertEqual(found["skills"]["vf-explain"], str(self.home / ".claude/skills/vf-explain/SKILL.md"))

    def test_reports_missing_skills(self):
        make_skill(self.installed, "vf-verify")
        found = locate.locate(self.router, self.repo, self.home)
        self.assertIsNone(found["skills"]["vf-explain"])
        self.assertIn("vf-explain", found["missing"])
        self.assertNotIn("vf-verify", found["missing"])

    def test_lists_each_harness_once_even_through_a_symlink(self):
        harness = self.repo / ".agents/skills/verify-shop"
        harness.mkdir(parents=True)
        (harness / "rules.md").write_text("")
        (self.repo / ".claude/skills").mkdir(parents=True)
        (self.repo / ".claude/skills/verify-shop").symlink_to(harness)
        make_skill(self.repo / ".agents/skills", "vf-verify")
        found = locate.locate(self.router, self.repo, self.home)
        self.assertEqual(len(found["harnesses"]), 1)

    def test_a_monorepo_app_finds_its_own_harness_before_the_top_levels(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        own = self.repo / "app" / ".agents" / "skills" / "verify-app"
        top = self.repo / ".agents" / "skills" / "verify-top"
        for harness in (own, top):
            harness.mkdir(parents=True)
            (harness / "rules.md").write_text("# rules\n")
        (self.repo / "app" / "src").mkdir()

        found = locate.locate(self.router, self.repo / "app" / "src", self.home)

        self.assertEqual(found["harnesses"], [str(own.resolve()), str(top.resolve())])

    def test_exit_codes(self):
        env = dict(os.environ, HOME=str(self.home))
        run = subprocess.run([sys.executable, SCRIPT, "--repo", str(self.repo)], capture_output=True, env=env)
        self.assertIn(run.returncode, (0, 1))
        run = subprocess.run([sys.executable, SCRIPT, "--repo", str(self.tmp / "nope")], capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertTrue(run.stderr.startswith("STOPPED:"))


class StaysInSync(unittest.TestCase):
    """Adding or renaming a skill must reach this script and the playbooks in the same change."""

    def test_every_framework_skill_is_listed(self):
        on_disk = {p.parent.name for p in REPO_SKILLS.glob("*/SKILL.md")} - {"vf"}
        self.assertEqual(set(locate.SKILLS), on_disk)

    def test_every_listed_skill_is_in_a_playbook(self):
        text = SKILL_MD.read_text()
        for name in locate.SKILLS:
            with self.subTest(skill=name):
                self.assertIn(name, text)


if __name__ == "__main__":
    unittest.main()
