# Rubric

Each item names a way a check can pass without earning it.

## Scenario and UI checks

- **C1 Stored state.** The check judges what the system stored or another service received, read back, not a route's response, a log line alone, or a value the harness itself set.
- **C2 One read path.** It reads by ID through the harness's read layer, not a search that can lag and not a query of its own.
- **C3 Independent expectation.** The expected value comes from what the scenario sent or a value the design fixes, never from the read being judged or the code under test.
- **C4 Empty fails.** Nothing stored, zero rows, or a missing field fails. Watch for `all()` over an empty list, a loop over zero rows, and `in` on an empty string.
- **C5 It happened.** The check proves the action ran (the send, the webhook, the handoff) before it judges the outcome.
- **C6 Errors never pass.** An exception, timeout, or unreadable response fails the check or withholds the verdict. A broad `except` that returns the all-clear value is a finding.
- **C7 Design, not current behavior.** The expectation matches the design docs. A known bug stays failing with the correct expectation.
- **C8 Specific enough.** It would fail on a plausible wrong answer: any non-empty text, a substring, or "at least one" where the design says exactly one are findings.
- **C9 Waits for its state.** A check of what a page or a polled service shows waits, up to one refresh cycle, for the state it expects. Sampling once at an instant judges timing, not the behavior.
- **C10 Developer can recheck.** A probe or documented command can rerun the same read so a developer can confirm the verdict by hand. If not, propose the command.
- **C11 Read from outside.** The read that decides the verdict, and any invariant it calls, imports none of the app's models, serializers, or business logic. A read through app code passes whenever that code is wrong in the same way the behavior is.

- **C12 A recording is not a read.** No verdict rests on a video, screenshot, clip, or snapshot existing, or on judging one. A snapshot explains a failure; the step's own read decides it.

## Unit tests

- **U1 A red case.** Each check has a test that feeds the broken case and asserts the problem is reported, not only good-path tests.
- **U2 Mock the edges only.** Mocks stand in for external services, databases, or the clock, never for the function under test or the read it judges.
- **U3 Assert the outcome.** The test asserts the result, not only that something came back or a mock was called.
- **U4 Real shapes.** Fixture rows use the columns and payload shapes the read layer and the real services return. A fixture shaped like nothing real proves nothing.

## Probe and reads

- **P1 Real reads.** A probe command reads through the read layer or its documented ad hoc path, and tells "none found" apart from "could not read".
- **P2 Errors surface.** A read from another service returns nothing only on not-found and raises on any other failure.

## Docs and skills

- **D1 Everything named exists.** Each command, flag, scenario name, probe subcommand, check name, feature ID, and path in a recipe exists today. Check with `--help`, `ls`, and `grep`.
- **D2 Recipes end on stored state.** A "how to prove it" recipe ends on a read of stored state, not a 200 or a log line.
- **D3 Ratings match evidence.** A check a coverage map rates strong or break-tested has a planned break that `break_checks.py` or a recorded live run caught.
