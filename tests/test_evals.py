"""The skills evaluation suite's own parts: case files load, the prompt frontmatter parses, the simulated developer
answers from the sheet, and the transcript parser reads a headless run. No agent and no app runs here."""

import json
import pathlib
import sys
import unittest

EVALS = pathlib.Path(__file__).resolve().parent.parent / "evals"
sys.path.insert(0, str(EVALS))

from vfeval import agent, cases, fixtures, graders  # noqa: E402


class Cases(unittest.TestCase):
    def test_every_case_loads_and_names_known_parts(self):
        problems = fixtures.check_cases()
        self.assertEqual(problems, [], "\n".join(problems))

    def test_every_practice_declares_what_the_graders_need(self):
        for name in cases.practice_names():
            with self.subTest(practice=name):
                practice = cases.load_practice(name)
                for key in ("summary", "setup", "ports", "repos", "project_root", "harness", "behaviors", "breaks"):
                    self.assertIn(key, practice, f"{name}: practice.json lacks {key}")
                for brk in practice["breaks"]:
                    self.assertIn(brk["sub_feature"], practice["behaviors"], f"{name}: break {brk['patch']} targets an unknown behavior")
                    self.assertTrue((practice["dir"] / "hidden" / brk["patch"]).is_file(), f"{name}: {brk['patch']} is missing")
                for change in practice.get("changes", {}).values():
                    self.assertTrue((practice["dir"] / "hidden" / change["patch"]).is_file(), f"{name}: {change['patch']} is missing")
                self.assertTrue((practice["dir"] / "hidden" / "answers.json").is_file() or practice.get("base"), f"{name}: hidden/answers.json is missing")

    def test_every_case_pins_the_agent_model(self):
        for name in cases.case_names():
            with self.subTest(case=name):
                self.assertEqual(cases.load_case(name)["settings"].get("model"), "claude-opus-5-5", "prompt.md frontmatter should pin the model the suite is calibrated on")

    def test_frontmatter_parses_lists_numbers_and_strings(self):
        settings, body = cases.frontmatter("---\ntags: [smoke, setup]\nmax_turns: 120\nmodel: claude-x\n---\n\nDo the thing.\n")
        self.assertEqual(settings, {"tags": ["smoke", "setup"], "max_turns": 120, "model": "claude-x"})
        self.assertEqual(body, "Do the thing.\n")


class SimulatedDeveloper(unittest.TestCase):
    SHEET = {"rules": [{"pattern": "daily|limit", "answer": "Not decided; leave it out."}, {"pattern": "commit", "answer": "Don't commit."}], "default": "Go ahead."}

    def test_question_is_the_last_needs_you_line(self):
        self.assertEqual(agent.question_in("Will prove: x\n\nNeeds you: proceed? I recommend yes."), "proceed? I recommend yes.")
        self.assertIsNone(agent.question_in("All 3 behaviors are Verified."))

    def test_first_matching_rule_wins_and_default_covers_the_rest(self):
        self.assertEqual(agent.answer_from_rules(self.SHEET, "What is the daily transfer limit?", "")[0], "Not decided; leave it out.")
        self.assertEqual(agent.answer_from_rules(self.SHEET, "Shall I commit the harness?", "")[0], "Don't commit.")
        self.assertEqual(agent.answer_from_rules(self.SHEET, "Which port?", "")[0], "Go ahead.")


class AgentCommand(unittest.TestCase):
    def test_the_case_loads_only_the_plugin_under_test(self):
        command = agent.claude_command("hi")
        self.assertEqual(command[command.index("--setting-sources") + 1], "project,local")
        self.assertEqual(command[command.index("--plugin-dir") + 1], str(agent.FRAMEWORK))
        self.assertEqual(command[command.index("--permission-mode") + 1], "bypassPermissions")


class TranscriptParser(unittest.TestCase):
    def test_reads_session_tools_and_result_from_stream_json(self):
        lines = [
            json.dumps({"type": "system", "subtype": "init", "session_id": "s1", "model": "claude-opus-5-5"}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}}),
            json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "Done.\n\nNeeds you: commit?"}]}}),
            json.dumps({"type": "result", "subtype": "success", "result": "Done.\n\nNeeds you: commit?", "session_id": "s1", "total_cost_usd": 0.5, "duration_ms": 1200, "num_turns": 3,
                        "modelUsage": {"claude-opus-5-5": {}, "claude-sonnet-5-5": {}}}),
        ]
        turn = agent.parse_stream(lines, agent.Turn())
        self.assertEqual(turn.session_id, "s1")
        self.assertEqual([use["name"] for use in turn.tool_uses], ["Bash"])
        self.assertEqual(agent.question_in(turn.final_text), "commit?")
        self.assertEqual(turn.cost_usd, 0.5)
        self.assertEqual(turn.model, "claude-opus-5-5")
        self.assertEqual(turn.models_used, ["claude-opus-5-5", "claude-sonnet-5-5"])
        self.assertIsNone(turn.error)


class Graders(unittest.TestCase):
    def test_every_grader_has_a_one_line_doc(self):
        for name, function in graders.GRADERS.items():
            with self.subTest(grader=name):
                self.assertTrue((function.__doc__ or "").strip(), f"{name} has no docstring")

    def test_project_root_grader_reads_a_workspace_reached_through_a_symlink(self):
        # macOS hands out temp folders under /var, a symlink to /private/var.
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            real = pathlib.Path(directory).resolve()
            link = real.parent / (real.name + "-link")
            link.symlink_to(real)
            try:
                harness = real / ".claude" / "skills" / "verify-x"
                harness.mkdir(parents=True)
                (harness / "rules.md").write_text("")
                practice = {"project_root": ".", "harness": ".claude/skills/verify-x"}
                ctx = graders.Context(link, practice, {}, {}, [])
                self.assertTrue(graders.GRADERS["harness_in_project_root"](ctx).passed)
            finally:
                link.unlink()

    def test_status_lines_parse(self):
        ctx = graders.Context.__new__(graders.Context)
        ctx.status_snapshot = "- a.b: Verified. x\n- c.d: Not verified. No check yet.\n- e.f: Failed. Step 'x'.\n"
        self.assertEqual({k: v[0] for k, v in ctx.verdicts().items()}, {"a.b": "Verified", "c.d": "Not verified", "e.f": "Failed"})


if __name__ == "__main__":
    unittest.main()
