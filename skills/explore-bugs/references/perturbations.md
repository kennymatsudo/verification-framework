# Perturbation kinds

Start each round from a normal, real user flow and apply one or two perturbations.

| Kind | Examples |
| -- | -- |
| timing | Delay a response, retry a request, two actions at once, a slow network |
| order | Act after the flow ended, reply before the record exists, end twice, poll responses out of order |
| identity | A second tab, a second account, the same email on two users, an admin acting as a user |
| input-shape | Empty, very long, past a documented limit, unicode and emoji, odd file types |
| lifecycle | Reload or navigate away mid-action, a session that expires mid-flow, a restart between steps |
| external-side | What a third-party system or operator can do on its side: close, reassign, merge, edit fields, fire a webhook late or twice |
| code-reading | No perturbation chosen up front: read recent diffs and error branches, then name an input that reaches an untested branch |

## Browser races

To test what a user sees under a race, hold named network responses and release them in a chosen order instead of adding random delays. In Playwright, `page.route` holds a request and `route.fetch()` sends it on, so only the browser's view is delayed. Block service workers so they cannot hide requests. Run pairs of orderings first, and full orderings only for three or four events. Save each failing ordering as a plain test.

Race-prone patterns to look for in front-end code: optimistic IDs reconciled with server IDs, poll results merged with local state, effects without cleanup, and controls that can be clicked twice.

## Comparison oracles

Some breaks have no invariant to name them. Compare instead:

- Replaying an event changes nothing.
- The same actions in a different order reach the same final state, where the design says order does not matter.
- Stored state matches what the third-party system's own API reports.
