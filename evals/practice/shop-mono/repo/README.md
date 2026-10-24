# Shop

The shop backend as a monorepo: each service lives under `apps/` and is run and deployed on its own.

| App | Language | What it does |
| --- | --- | --- |
| [`apps/orders`](apps/orders/README.md) | Python | Takes orders over HTTP and stores them. Drops a job in the shared outbox for each one. |
| [`apps/mailer`](apps/mailer/README.md) | Node | Works the outbox: sends one confirmation email per order through the team's mail relay. |

The two apps share `queue/outbox.jsonl` at the repo root: orders appends jobs, the mailer marks them done. `mail-sink/` at the repo root is the relay's drop folder. **Anything written there is sent to the team's shared test inbox within a minute**, so don't drop test mail there without telling the team.

Each app has its own README with its start command. Requirements live in each app's `REQUIREMENTS.md`.
