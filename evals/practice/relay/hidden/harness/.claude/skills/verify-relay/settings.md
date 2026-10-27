# Relay verification settings

The values `rules.md` refers to for this app. Change a rule in the framework that provides `rules.md`, not here.

## Setup

- Status: ready

## Workflow

- Requirements source: REQUIREMENTS.md

## Repos

- relay: .

## Commands

- Start: none
- Stop: none
- Doctor: python3 .claude/skills/verify-relay/scripts/doctor.py
- Ready line: relay ready
- Probe: python3 .claude/skills/verify-relay/scripts/probe.py
- Reloads: yes

Relay is a command-line tool with no server: nothing starts or stops, and every check runs `python3 -m relay` itself, so Start and Stop are `none`. The checks and the doctor run the tool from the checkout `VERIFY_CHECKOUT_RELAY` names, which `vf.py` sets to this checkout on an ordinary run and to a planned break's scratch copy during one; the doctor confirms that checkout holds a runnable relay and reports its code state. Each run reads the files afresh, so an edit needs no restart (Reloads: yes). Everything runs from the project root; nothing reaches an external or shared system.
