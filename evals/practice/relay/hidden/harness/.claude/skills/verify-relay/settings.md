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
- Run scratch code: python3 .claude/skills/verify-relay/scripts/doctor.py --point {checkout}
- After an edit: reloads

Relay is a command-line tool with no server: nothing starts or stops, and every check runs `python3 -m relay` itself, so Start and Stop are `none`. The checks run the tool from the checkout the pointer file `evidence/launch/checkout.txt` names, which is this checkout unless a break session has pointed it elsewhere with `doctor.py --point`; the doctor confirms that checkout holds a runnable relay and reports its code state. Each run reads the files afresh, so an edit needs no reload. Everything runs from the project root; nothing reaches an external or shared system.
