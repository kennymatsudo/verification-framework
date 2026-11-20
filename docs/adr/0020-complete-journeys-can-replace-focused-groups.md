# ADR 0020: Complete journeys can replace focused groups

Status: Accepted. 2026-11-18. Extends ADR 0019's selection rule.

## Problem

Once every behavior in a feature has its own focused check, no request selects the check that walks the whole journey. Verifying all four staff-polling behaviors in the converted app would run two focused journeys and open two sandbox chats, although the full journey checks them with one chat. A negative-case check can also require and declare an ordinary positive case; combining it with another focused check should reuse a complete journey when all of that journey's checks are already required.

## Decision

A command declared in `check_coverage` can replace selected commands even when it is no behavior's check. It replaces two or more of them, each wholly, only when every behavior it judges, by declaration or as a behavior's check in the feature map, is requested or declared for one of the commands first selected. Declaring a prerequisite is enough, because those selected checks already judge it; a behavior mapped to a selected command but not declared for it doesn't count. Larger candidates are tried first, and ADR 0019's rule for dropping a covered command still applies afterward.

The replacement must exercise the assigned assertions in this run and record every required repository. The declaration cannot create a pass. Rules version remains 10: no manifest field, evidence format, or required harness operation changes.

## Options we passed on

- Keep one behavior's check on the full journey: a request for that behavior alone loses its focused check.
- Add costs and solve a general scheduling problem: this case needs only complete-group reuse.
- Introduce any broader declared command: partial requests could add behaviors outside the request and the selected checks' explicit declarations.

## What changes

The planner considers complete declared alternatives. Validation checks their behavior references and any named executable paths. Unit tests cover full-group selection, declared prerequisites, smaller requests, partial overlap, unrelated commands, implicit mapped behaviors, variants, absent assertions and repository recording. The converted app supplies the all-focused staff and editor selection cases.
