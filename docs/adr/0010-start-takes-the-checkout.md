# ADR 0010: Start takes the checkout, so one command points the app at the code under test

Status: Accepted. 2026-10-27. First step of the redesign in [redesign-proposal.md](../redesign-proposal.md).

## Problem

A planned break has to make the running app load a scratch copy of the code. Settings carried two commands for this beyond `Start`: `Run scratch code`, which repointed the running app at a checkout, and `After an edit`, which restarted it between breaks. In four of the five reference harnesses both lines were the same `stop && start --checkout {repo}={checkout}` string as each other, and a near-copy of `Start`. A third mechanism, `per check`, said each check starts the app itself and skipped the doctor; a fourth, the relay practice repo's pointer file, worked around `per check` by writing the checkout into a file the checks read. `code_state.py` also stopped a run when any settings repo was missing, so a teammate without one repo could not run checks that never touch it. Four of the eleven open questions in `design.md` were about this tangle.

## Decision

`Start` names each repo's checkout as `{checkout:<repo>}`. `vf.py` fills it with that repo's checkout on an ordinary run, and with a planned break's scratch copy for the repo being broken. The one command both launches the app and points it at the code under test, so `Run scratch code` and `After an edit` are gone.

- **One `Reloads` line** replaces `After an edit`: `yes` when the app picks up an edit to its checkout without a restart, `no` when a planned break must restart it. A break of a reloading app skips the restart.
- **`Start: none`** means each check starts the app itself; **`Start: user`** means only a person can, so planned breaks are blocked. The doctor runs in every case (the `per check` doctor skip is gone), so a check that starts the app still proves its readiness.
- **Every command runs with `VERIFY_CHECKOUT_<REPO>`** set for each settings repo (the name in capitals, other characters underscores), naming the checkout the run records. A doctor or check that runs the code itself reads the checkout from there, which retires the relay pointer file.
- **A break restarts through `Start`:** `vf.py break` runs Stop then Start to point the app at the scratch copy, and again at the developer's checkout when the session ends; with `Reloads: no` it also restarts between breaks.
- The Rules version rises to 4. A harness on an earlier version fails `validate.py` until `sync` rewrites its settings.

## Options we passed on

- **Keep `Run scratch code` and `After an edit`.** Two commands that in practice duplicated `Start`, and a format every break reader had to carry.
- **Keep `per check` as a doctor skip.** A check that starts the app can still have a doctor that confirms readiness; skipping it lost that proof and was a branch in every reader.
- **A generic `{checkout}` with no repo name.** It could not say which repo's checkout to fill in a monorepo, where two repos resolve to different folders of one worktree.
- **Infer reloads from the start command.** Not knowable from a command string; a wrong guess either wastes a restart or runs a break against stale code.

## What changes

`rules.md` (Doctor, Evidence; Rules version to 4), the `settings.md` template, `validate.py` (the Commands labels, the `{checkout:<repo>}` and `Reloads` checks, `fill_checkouts`, `checkout_placeholders`), `code_state.py` (`recorded_checkouts`, `checkout_env`, `env_name`), `break_session.py` (the start/run/end pointing through `Start`/`Stop`), `vf.py` (the doctor, run, and start-app paths export `VERIFY_CHECKOUT_<REPO>`), the eval scaffold and graders, the five reference harnesses and the relay scripts, `docs/internals.md`, and the gate version in every skill. Per-behavior `repos` (so a run needs only the repos its check touches) is noted in the proposal and left to a later step.
