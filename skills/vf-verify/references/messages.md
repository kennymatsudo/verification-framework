# Messages

Every skill in this collection writes its questions, plans, and reports in this shape. A reader faced with a long message tends to approve it unread, so every message makes its point and its ask impossible to miss.

- **Three kinds.** A message is a question, a plan to approve, or a report. A message that only informs, such as `Planned break: <edit>`, is one line and asks nothing.
- **The ask comes last.** A message that needs an answer ends with one short `Needs you:` line, and nothing follows it: no option bullets, no "Then I'll" on its own line, no closing remark. The question, the recommended answer, and what you'll do next all sit on that one line. Options that need more than a few words each go in the body above, one line each, and the ask names them. A skimming reader sees only the last lines, so the question names each thing it asks about and never asks the reader to confirm a list above it. Where a rule came from, and optional next steps, go above that line.
- **Recommend only what a source settles.** Give a recommended answer when the requirements, the project, or a granted permission point to one, and name that source. When nothing settles the question, say so and give each option with what a user would notice, and recommend none: a reader follows the recommended choice without reading the rest, and an inferred recommendation is the wrong claim this question exists to catch.
- **What to ask.** Ask only about what the sources leave unsettled. Leaving out a behavior the sources tie to the request is unsettled, so name it in the question rather than only under Gaps. Never ask what the project, the harness, or a granted permission already answers. A local, reversible effect, such as local test rows, gets one line in the plan saying so, not a question, and no line in a report; ask before a shared or irreversible one. Hold a question that depends on another's answer; batch independent ones in one picker. For a question with a few known answers, use the session's structured question tool if it has one, recommended answer first when there is one and no option preselected when nothing settles it; an open question, such as a URL or how the app starts, stays a `Needs you:` line.
- **Once per session.** State a caveat, such as an uncommitted file in the checkout, the first time it matters, and don't repeat it in later messages.
- **Plain words.** Name each behavior by what a user would notice; sub-feature IDs stay in the harness files. Define any other term in a few words, or leave it out. Call the doctor "the readiness check"; the reader doesn't know the harness's internal names.
- **Preview.** Use this shape, leaving out empty lines and any line that would say none. Give one line per behavior; past five, group them by feature with counts. Keep Won't prove to one line, and name each source by its document or file, without line numbers or quotes. The preview is the whole message, with no lead-in and no code fence, and fits in 12 lines.

  ```
  <Verify|Build> <feature or change> on <branch> (<repo> <commit>)

  Will prove: <behavior>
  How: <how the real app is driven>; reads <what is read back>
  Won't prove: <exclusions and unavailable observations>
  Gaps: <behaviors with no proof, and what would be built>
  Sources: <requirements, user answers, or recipes that set the expected behavior>

  Needs you: <question>? I recommend <answer> (<source>). Then I'll <next step>.
  ```

  When nothing settles the question, the last line reads `Needs you: <question>? No requirement settles it. <Option>: <what a user would notice>. <Option>: <what a user would notice>. Then I'll <next step>.`

- **Report.** Open with the outcome in one line, and put what went wrong before what passed. Give only what the reader acts on; the skill's `Reply:` line says what that is. A report fits in 12 lines; group behaviors with the same verdict and reason into one line. Versions, tool commands, and evidence paths stay in `status.md` unless that line asks for them, and one `Details:` line above the ask names where they are: the harness's `status.md`, and the recordings page when a run kept a recording. End with a `Needs you:` line that opens with the outcome in a few words, such as `Needs you: all 3 discount behaviors are Verified. Commit them?`, because a skimming reader reads only the end. With nothing to ask, end on the outcome: when the body runs past three lines, repeat the opening line last.
