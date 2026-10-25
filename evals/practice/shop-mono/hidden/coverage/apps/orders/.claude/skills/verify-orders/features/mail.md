# Mail

The mailer turns each outbox job into one confirmation email.

## Sub-features

- mail.confirmation-sent: the mailer sends exactly one confirmation per outbox job to the customer's email, with the order ID in the subject.
- mail.marks-done: the mailer marks each job done after sending, so a second run sends nothing for it.

## How a user reaches it

- `node ../mailer/worker.js --once` from apps/orders, or the running worker, which polls the outbox every five seconds.

## Verification plan

Source: REQUIREMENTS.md SR-3. Running the mailer drops real mail into the team relay's folder (`../../mail-sink`), which forwards to the shared test inbox, so any check that runs it is an action with a shared side effect and needs the user's approval for that run.

- mail.confirmation-sent: No agreed proof yet.
- mail.marks-done: No agreed proof yet.

## How to prove it

- mail.confirmation-sent: No check yet.
- mail.marks-done: No check yet.
