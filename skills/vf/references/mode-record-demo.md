# Record a demo of a feature

Follow this when vf runs in record-demo mode. Run it only when the person asked for this job by name in this session; otherwise offer it in one line and stop. The Guardrails in vf's `SKILL.md` apply throughout. Verify-pr runs steps 3 to 9 of this mode for its own demo, inside the approval it already asked for.

You own one video a person can show other people: the feature at real speed, at a person's pace, with captions written for the audience, recorded from a demo run whose own reads judge every shot. A demo shows; it never decides a verdict, and it needs no check to exist first. Rules.md's "Demo runs" section is the contract; read it in full first.

## 1. Find the harness

Find the harness: the one the user or a calling skill named, or else `verify-*/rules.md` in the skills directories (`.claude/skills/`, `.agents/skills/`, `.pi/skills/`, `.cursor/skills/`) of the current folder and each folder above it up to the repo's top level, nearest first. Ask which when several match; with none, stop and name vf to set one up.

Run `<harness>/scripts/framework/vf.py validate --written-for 9` before anything else. When it stops on incomplete setup, report its blocker and next action, name vf to resume setup, and stop; when `vf.py` is missing or doesn't know `validate`, the harness predates the installed framework, so name vf to update it and stop; when it reports a Rules version mismatch, relay which side it says to update, and stop.

Done when you have the harness path and have read its `rules.md`, `harness.json`, `notes.md`, the feature files the request names, and every existing demo in its `demos/`.

## 2. Draft the shot list from the feature

Write the story from what the feature is for, never from the code: the feature file's summary and behaviors' `words`, the change or pull request being verified with its ticket, and the design docs the feature names in `sources`. Say who the audience is and the two or three things they should leave knowing. Then list the shots, one row each: whose screen, what that person does, the caption they read, and what must be true on screen at the end, with the sub-feature it shows when the feature map has one. A wait the viewer sits through gets its own row with a caption saying what is being waited for. A step that needs a person with no screen, such as an action through an API, gets a banner over the screen that sees its result, captioned with where it really happened.

Name what the video can't show, such as a sound or a race only a watcher in the page counts, and leave it out rather than stage it. When the feature's point can't be seen at all, say so and stop.

Show the shot list and wait for the person's yes or changes. Write nothing before then.

Done when the person approved a shot list in which every shot ends in something a read can judge.

## 3. Find or write the demo

Reuse the demo in `demos/` that tells this story, updated to the approved shot list. Else, when one check's steps already tell the story with nothing else between them, that check may run as the demo: it paces through the harness's demo helpers only when `VERIFY_DEMO=1`, as rules.md says. Else write a new scenario in `demos/<name>/`, adapting `references/demo-playwright.md` (or the same shape in the harness's own driver), with `references/demo-overlay.js` copied beside it unchanged.

Write it only under `demos/`. It imports the harness's sign-in, reads, and page helpers and never edits them, or anything else under `scripts/`, or `harness.json`, so no check's harness code changes and no pass goes stale; a change those files need is a separate request. Each shot ends in a step that reads what the shot showed, with the timeout an ordinary check gives that read. Name a sub-feature only when the shot shows exactly that behavior; never borrow a nearby one to give the demo proof it doesn't have. Captions come from the shot list, on the marks where they appear. Pace only before actions and hold only after verdicts; when the story needs a pause inside a timed wait, the scenario can't show it, so change the shot list with the person instead.

Run the harness's unit tests, and any test it has for its demos. Then confirm with `git status` that nothing outside `demos/` changed.

Done when the demo exists under `demos/`, every shot ends in a judged read, and the harness's code outside `demos/` is unchanged.

## 4. Note what already proves it

For each sub-feature the demo names, read `status.md` and the evidence for its latest ordinary run. Note any that passed on the code the demo will run; they go in the hand-off. Nothing here blocks the demo, and no check reruns for it unless the person asks.

Done when you know which behaviors the demo shows have a pass on that code, and which don't.

## 5. Ask once

In one message, name the demo run and its cost in time, shared resources, and side effects, such as tickets opened in a shared sandbox. Say what the video will show and the step range you expect to use. Wait for the person's yes; it covers exactly that run. Verify-pr has already asked for its demo in its own approval, so it skips this step.

Done when the person approved the runs, or dropped the demo.

## 6. Run the demo

Run `<harness>/scripts/framework/vf.py run --demo --user-approved -- <demo command>`, passing the demo's own approval flag when it reaches a shared system. A demo run that fails is a finding: diagnose it like a failed check, and record or file it as the harness's notes say; never make a video from it, and never loosen a read to get one.

Done when the demo run passed and its record is under `evidence/demos/`, or it failed and the finding is recorded.

## 7. Pick the range

List its steps with `<harness>/scripts/framework/vf.py demo <record>`. Pick the first step that shows the feature through the step after its result, leaving out setup and sign-in before it. Everything between plays as it happened. Give the range with a one-line reason.

Done when the range is chosen and every step in it has a caption.

## 8. Make and check the video

Find the code host's upload limit from the session's tools: GitHub allows 100 MB on paid plans and 10 MB on free ones. Then run `vf.py demo <record> --steps <range> --max-mb <limit>`. If `vf.py demo --check` says this machine can't make it, give its install line instead; never install it unasked.

Read every still it prints. Each must show its caption whole and readable, the badge of the screen it names, and the switch card where it lists one. Look in each for anything that shouldn't be public, such as real customer data, secrets, or internal addresses. When a still is wrong, fix the demo and run it again after the person's yes, or pick another range; never edit the video.

Done when every still matches what it lists, the length the tool checked matches the steps, and each file is under the limit.

## 9. Hand it back

Give each MP4's path, length, size, and resolution; the range with its reason; and, from step 4, any ordinary pass on the same code of a behavior it shows. Upload, attach, or post it only when the person says to.

Done when the person has the video and what proves it.

## Guardrails for this mode

- Write only under the harness's `demos/` and `evidence/demos/`. Never edit a check, a harness tool, `harness.json`, or product code for a demo.
- Never run a demo without the person's approval naming it, and never run one to test a change to the demo machinery without asking first and naming its cost.
- Never stage what the app should do: no forged event, no faked response, no read loosened to pass.
- A demo run never counts as proof, and its result never goes into `status.md`.

Reply: in the shape `references/messages.md` gives. One line on the outcome, then the video's path, length, size, and range with its reason, and any ordinary passes on the same code. End with `Needs you:` to share it, or the one decision left.
