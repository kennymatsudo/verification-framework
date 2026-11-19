# ADR 0020: Complete journeys can replace focused groups

Status: Accepted. 2026-11-18. Extends ADR 0019's selection rule.

## Problem

Once every behavior in a feature has a focused recipe, no request selects its complete journey. Verifying all four staff-polling behaviors in the converted app would run two focused journeys and open two sandbox chats, although the full journey checks them with one chat. A negative-case check can also require and declare an ordinary positive case; combining it with another focused check should reuse a complete journey when all of that journey's checks are already required.

## Decision

A `check_coverage` command can be a complete alternative without being a behavior's default recipe. It replaces multiple selected commands only when every behavior it declares or maps is requested or explicitly declared by an initially selected command. Those selected checks already judge the declared prerequisites. Other mapped behaviors do not expand eligibility. Each replaced command must be wholly covered. Larger complete groups are considered first. Existing selected-command suppression still applies.

The replacement must exercise the assigned assertions in this run and record every required repository. The declaration cannot create a pass. Rules version remains 10: no manifest field, evidence format, or required harness operation changes.

## Options we passed on

- Keep one arbitrary behavior on the full recipe: single-behavior requests lose their focused path.
- Add costs and solve a general scheduling problem: this case needs only complete-group reuse.
- Introduce any broader declared command: partial requests could add behaviors outside the request and the selected checks' explicit declarations.

## What changes

The planner considers complete declared alternatives. Validation checks their behavior references and any named executable paths. Unit tests cover full-group selection, declared prerequisites, smaller requests, partial overlap, unrelated commands, implicit mapped behaviors, variants, absent assertions and repository recording. The converted app supplies the all-focused staff and editor selection cases.
