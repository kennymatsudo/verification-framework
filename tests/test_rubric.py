"""The weak-checks rubric repeats rules from rules.md word for word.

The rubric must judge a harness that has no rules.md, so it cannot point at the rules; it carries a copy
of each sentence it needs instead. Identical wording keeps the copy from drifting into a different rule.
Change a sentence in rules.md first, then here, then in the rubric.
"""

import pathlib
import unittest

REFERENCES = pathlib.Path(__file__).resolve().parent.parent / "skills" / "vf" / "references"

SHARED = [
    # Probes, Exit codes; rubric P1.
    'A reader can always tell "none found" apart from "could not read".',
    # Probes, Shared reads; rubric P2.
    "A read returns nothing only on not-found and raises on any other failure, so a check can't mistake an outage for an empty result.",
    # Probes, Read from outside the app; rubric C11.
    "The read that decides a verdict, and any read it calls, imports none of the app's models, serializers, or business logic; "
    "a read through app code passes whenever that code is wrong in the same way the behavior is.",
]


class RubricCopiesRules(unittest.TestCase):
    def test_each_shared_sentence_is_in_both_files(self):
        rules = (REFERENCES / "rules.md").read_text()
        rubric = (REFERENCES / "rubric.md").read_text()
        for sentence in SHARED:
            with self.subTest(sentence=sentence[:50]):
                self.assertIn(sentence, rules, "rules.md no longer has this sentence")
                self.assertIn(sentence, rubric, "rubric.md no longer repeats this sentence word for word")


if __name__ == "__main__":
    unittest.main()
