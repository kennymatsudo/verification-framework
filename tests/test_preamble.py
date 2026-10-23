"""Every skill that reads a harness finds it and gates on validate.py with the same two sentences.

One wording, checked here, keeps the seven procedures from drifting apart on how a harness is found and
what to do when its setup is incomplete or its framework copies are old. Change a sentence here and in
every skill together.
"""

import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "skills"

FIND = ("Find the harness: the one the user or a calling skill named, or else `verify-*/rules.md` in the skills directories "
        "(`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) of the current folder and each folder above it "
        "up to the repo's top level, nearest first. Ask which when several match; with none, stop and name vf to set one up.")
GATE = ("Run `<harness>/scripts/framework/vf.py validate` before anything else. When it stops on incomplete setup, report its "
        "blocker and next action, name vf to resume setup, and stop; when `vf.py` is missing or doesn't know `validate`, the "
        "harness predates the installed framework, so name vf to update it and stop.")

# Skills that only work on a framework harness find it and gate on it.
FINDS_AND_GATES = [
    "vf-verify/references/mode-verify.md",
    "vf-verify/references/mode-add-checks.md",
    "vf-verify/references/mode-add-tools.md",
    "vf/references/mode-audit-coverage.md",
    "vf-explain/SKILL.md",
]
# Skills that also work on a harness this framework did not build only gate on it.
GATES = [
    "vf/references/mode-audit-weak-checks.md",
    "vf/references/mode-verify-pr.md",
]


class SharedPreamble(unittest.TestCase):
    def test_every_harness_reading_skill_finds_the_harness_the_same_way(self):
        for skill_file in FINDS_AND_GATES:
            with self.subTest(skill=skill_file):
                self.assertIn(FIND, (SKILLS / skill_file).read_text(), "the find sentence is missing or reworded")
        for skill_file in GATES:
            with self.subTest(skill=skill_file):
                self.assertNotIn(FIND, (SKILLS / skill_file).read_text(), "a skill that also works on a foreign harness carries only the gate sentence")

    def test_every_harness_reading_skill_gates_on_validate_the_same_way(self):
        for skill_file in FINDS_AND_GATES + GATES:
            with self.subTest(skill=skill_file):
                self.assertIn(GATE, (SKILLS / skill_file).read_text(), "the validate sentence is missing or reworded")

    def test_vf_and_vf_verify_carry_the_same_messages_file(self):
        self.assertEqual((SKILLS / "vf/references/messages.md").read_text(), (SKILLS / "vf-verify/references/messages.md").read_text(),
                         "edit both copies of messages.md together")


if __name__ == "__main__":
    unittest.main()
