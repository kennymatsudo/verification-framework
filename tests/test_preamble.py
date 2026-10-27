"""Every mode that reads a harness finds it and gates on validate.py with the same two sentences, and every
mode only a person may start opens with the same sentence saying so.

One wording, checked here, keeps the procedures from drifting apart on how a harness is found, what to do
when its setup is incomplete or its framework copies are old, and which jobs wait to be asked for by name.
Change a sentence here and in every mode together.
"""

import pathlib
import re
import unittest

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "skills"
# The gate names the Rules version the skills were written for, so a bump in rules.md must reach every skill.
RULES_VERSION = re.search(r"^Rules version: (\S+)$", (SKILLS / "vf/references/rules.md").read_text(), re.MULTILINE).group(1)

FIND = ("Find the harness: the one the user or a calling skill named, or else `verify-*/rules.md` in the skills directories "
        "(`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) of the current folder and each folder above it "
        "up to the repo's top level, nearest first. Ask which when several match; with none, stop and name vf to set one up.")
GATE = (f"Run `<harness>/scripts/framework/vf.py validate --written-for {RULES_VERSION}` before anything else. When it stops on incomplete setup, report its "
        "blocker and next action, name vf to resume setup, and stop; when `vf.py` is missing or doesn't know `validate`, the "
        "harness predates the installed framework, so name vf to update it and stop; when it reports a Rules version mismatch, "
        "relay which side it says to update, and stop.")

# Modes that only work on a framework harness find it and gate on it.
FINDS_AND_GATES = [
    "vf/references/mode-verify.md",
    "vf/references/mode-add-checks.md",
    "vf/references/mode-add-tools.md",
    "vf/references/mode-audit-coverage.md",
    "vf/references/mode-explain.md",
]
# Modes that also work on a harness this framework did not build only gate on it.
GATES = [
    "vf/references/mode-audit-weak-checks.md",
    "vf/references/mode-verify-pr.md",
]
# Modes a person starts by name open with this sentence; the others never carry it.
PERSON_ONLY = "Run it only when the person asked for this job by name in this session; otherwise offer it in one line and stop."
PERSON_ONLY_MODES = ["mode-setup", "mode-audit-coverage", "mode-audit-weak-checks", "mode-verify-pr"]
AGENT_MODES = ["mode-verify", "mode-add-checks", "mode-add-tools", "mode-explain"]


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

    def test_person_only_modes_say_so_in_the_same_words(self):
        for mode in PERSON_ONLY_MODES:
            with self.subTest(mode=mode):
                text = (SKILLS / "vf/references" / f"{mode}.md").read_text()
                self.assertIn(PERSON_ONLY, text.split("\n\n")[1], "the person-only sentence is missing from the opening paragraph or reworded")
        for mode in AGENT_MODES:
            with self.subTest(mode=mode):
                self.assertNotIn(PERSON_ONLY, (SKILLS / "vf/references" / f"{mode}.md").read_text(), "an agent may start this mode")

    def test_every_mode_in_the_skill_table_has_its_file(self):
        body = (SKILLS / "vf/SKILL.md").read_text()
        for mode in PERSON_ONLY_MODES + AGENT_MODES:
            with self.subTest(mode=mode):
                self.assertIn(f"`references/{mode}.md`", body)
                self.assertTrue((SKILLS / "vf/references" / f"{mode}.md").is_file())


if __name__ == "__main__":
    unittest.main()
