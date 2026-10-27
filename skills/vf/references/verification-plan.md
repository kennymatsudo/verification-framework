# Verification plan

Follow this before building a proof or running checks on an agreed scope. The feature file's `sources` list and each behavior's `plan`, whose format the harness's `rules.md` gives under Feature map, record what this settles.

Show a preview in the shape `references/messages.md` gives. Derive available observations from the real read code, never from the behavior's wording; name an unavailable one as a gap. Keep commands and implementation details secondary.

For a change, include the behaviors it could affect and explain any related behavior included in scope. For a request to check a whole feature, cover its mapped behaviors and disclose unmapped or unchecked gaps. Running every mapped check does not establish complete product coverage.

Proceed when the request and its sources settle the acceptance conditions. When a meaningful one is inferred, conflicting, or unresolved, ask one concise question and wait before building or running the dependent proof, recommending an answer only when a source settles it, as `references/messages.md` says. Code explains implementation, not product intent. Action permission is separate from agreement on expected behavior.

Record the agreed plan in each behavior's `plan` and its sources in the feature file's `sources`. Name each source so it can be reopened, with the revision it was read at when it has one: a commit for a file in a repo, a version or last-edited date for a document, the last-updated time for a ticket, the date for a user's answer. Project acceptance recipes can be a source; the harness owns its proof plan. Compare each check's actions and observations with that plan before trusting it.

Before running checks on a plan agreed earlier, reopen each recorded source with a tool of its kind the session has. When it changed since the recorded revision, show the change and ask whether the expected behavior changed, as a question in the preview, before running the dependent checks; code merged since never answers it. A source no tool here can open goes in the preview's Sources line as unread, never treated as unchanged.

Before running a new or materially changed check, spawn a read-only subagent on a mid-tier model for a blind review: give it the agreed plan, its original sources, and the check's files, not the author's reasoning. It compares the check's real entry points, reads, assertions, and exclusions with the plan, and confirms the reads deciding each verdict use no app code. Resolve unsupported assertions, app-code reads, or scope changes before running; ask the user when a finding changes an acceptance condition. Any later change to what a check drives, reads, or asserts, whether it answers the review or follows a failed run, makes the check materially changed again and goes back for review before the next run: when the session can resume the reviewer, send it the diff; otherwise spawn a fresh reviewer with the same materials and the diff. Either way, leave out your reason for the change. The review adds to the planned break, never replaces it.

A passing check and a planned break validate detection only for the agreed claim; an observation alone is not a verdict.
