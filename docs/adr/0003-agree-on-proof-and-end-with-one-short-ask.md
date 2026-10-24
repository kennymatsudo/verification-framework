# ADR 0003: Agree on proof before building it, and end every message with one short ask

Status: Accepted. 2026-10-21.

## Problem

A check can pass, and even catch a deliberate break, while proving the wrong behavior. Only the person can say what counts, and the skills pause for them at a few points: the proof preview, acceptance questions, the setup note, and approval of side effects. Messages at those points came out long, with commands and paths beside verdicts and the question buried mid-message. In practice runs a simulated developer read only the last five lines, as a busy person skims, and couldn't tell whether checks passed or whether the agent was waiting. A reader who can't spot the decision approves without reading, which empties the checkpoint the trust contract relies on. Tools built on the way to a check were also hidden behind verification instructions, where an agent debugging couldn't find them.

## Decision

- **Preview, then agree.** Before building or running proof, show the behavior, real actions, observations, and exclusions, grounded in requirements or user answers. Ask about meaningful acceptance conditions the agent inferred; established conditions need no approval. Store the agreed plan apart from the check. A separate reviewer compares each new check with that plan, and the check must catch its planned break. Reports use the plan's wording.
- **One message shape**, in `references/messages.md`, identical in vf and vf-verify and checked by a test. A message is a question, a plan to approve, or a report; one that only informs is one line. The ask is short and last: a `Needs you:` line with the question, what happens next, and a recommended answer only when the requirements, the project, or a granted permission settles it, naming that source. When nothing settles it, the line gives each option as what a user would notice and recommends none, since a reader follows the recommendation without reading the rest, and an inferred one is the wrong claim the question exists to catch. A preview is Will prove, How, Won't prove, Gaps, Sources, in twelve lines. A report opens with the outcome, puts what went wrong before what passed, keeps versions, commands, and evidence paths in the harness unless a `Reply:` line asks for them, and names where they are on one `Details:` line. Messages call the doctor "the readiness check".

## Options we passed on

- **Let checks define acceptance.** A passing assertion can measure the wrong thing.
- **Ask approval for every established condition.** Repetitive questions teach people to stop reading.
- **Each skill defines its own format, or one strict template for all.** Formats drift, or the template bloats the reports that need less.
- **Fewer checkpoints instead of clearer ones.** The preview and acceptance questions are where a user catches a wrong claim.
- **Outcome only at the top.** Skimmers read the end.
- **Always recommend an answer.** On an open question the agent infers one, and the reader follows it unread.

## What changes

vf-verify's `references/verification-plan.md` and its add-checks mode, both copies of `references/messages.md`, every skill's `Reply:` line, and USAGE.md.
