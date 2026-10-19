"""Every skill carries the same four guardrails, word for word.

Identical wording lets a reader trust that the rules mean the same thing in every skill, and keeps
edits to one skill from quietly drifting from the others. Change a line here and in every skill together.
"""

import pathlib
import unittest

SKILLS = pathlib.Path(__file__).resolve().parent.parent / "skills"

SHARED = [
    "- Change product code only in a scratch git worktree for a planned break or fix, and remove the worktree afterward.",
    "- Drive only app instances this run started or the user named. Stop only processes this run started, by their recorded PIDs.",
    "- Ask before committing, pushing, posting, filing, or running anything with a real or shared side effect.",
    "- Never forge an event the real system would produce, and never loosen a check to turn a run green.",
]


def guardrails(skill_md):
    text = skill_md.read_text()
    if "## Guardrails\n" not in text:
        return None
    section = text.split("## Guardrails\n", 1)[1]
    return [line for line in section.strip().split("\n\n", 1)[0].splitlines() if line.startswith("- ")]


class SharedGuardrails(unittest.TestCase):
    def test_every_skill_carries_the_shared_guardrails(self):
        for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
            name = skill_md.parent.name
            with self.subTest(skill=name):
                lines = guardrails(skill_md)
                self.assertIsNotNone(lines, "no '## Guardrails' section")
                self.assertEqual(lines[: len(SHARED)], SHARED, "shared guardrails missing, reworded, or out of order")


if __name__ == "__main__":
    unittest.main()
