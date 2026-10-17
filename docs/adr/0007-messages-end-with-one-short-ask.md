# ADR 0007: Messages end with one short ask

Status: Accepted. 2026-10-16.

## Problem

The skills pause for the user at a few trusted points: the proof preview, acceptance questions, the setup note, and approval of side effects. Messages came out long, with commands and paths beside verdicts and questions buried mid-message. One report shape for every skill forced verify-change's content onto setup, whose final report listed doctor runs as Verified items. In practice runs, a simulated developer read only the last five lines of each message, the way a busy person skims, and couldn't tell from the end whether checks passed or whether the agent was waiting. A reader who can't spot the decision approves without reading, which empties the checkpoint the trust contract relies on.

## Decision

`rules.md`'s Messages section is the shape every skill follows.

- **Three kinds.** A message is a question, a plan to approve, or a report. A message that only informs is one line.
- **The ask is short and last.** A `Needs you:` line holds the question, the recommended answer with its reason, and what happens next, phrased "Then I'll ...". Whatever the reader needs to judge it, and any optional next steps, go above it. In a report, that line opens with the outcome in a few words.
- **One preview shape.** Will prove, How, Won't prove, Gaps, Sources. Leave out any line that would say none, keep Won't prove to one line, name sources by document or file without line numbers or quotes, and fit in 12 lines.
- **Reports share a frame, not a template.** Outcome first, what went wrong before what passed, only what the reader acts on, and one `Needs you` or nothing. Versions, commands, and evidence paths stay in `status.md` unless a skill's `Reply:` line asks for them. Each `Reply:` line says what its reader acts on: verify-change keeps its Verified, Failed, and Not verified lines; setup says the harness is ready, any fix the developer needs, and the two skills to run next, without picking one.
- **Plain names.** Messages call the doctor "the readiness check".

audit-weak-checks and verify-pr also run on harnesses without `rules.md`, so they carry the shape in their own text.

## Options we passed on

- **Each skill defines its own format.** Formats drift, and readers relearn every skill.
- **One report shape for every skill.** It bloated the setup report with content only verify-change needs.
- **A strict template for every message.** Only the preview recurs enough to fix its lines.
- **Fewer checkpoints instead of clearer ones.** The preview and acceptance questions are where a user catches a wrong claim.
- **Outcome only at the top.** Skimmers read the end, so the result gets missed.
- **A question and a list of next steps at the end.** The last line stops telling the reader whether the agent is waiting.
- **Drop Sources or Won't prove from previews.** They are what the developer checks before approving a claim.

## What changes

`rules.md`'s Messages and Reporting sections, every skill's `Reply:` line, setup's example note, and USAGE.md's "Read a message". `check.py` and the settings template don't change, because nothing app-specific varies.
