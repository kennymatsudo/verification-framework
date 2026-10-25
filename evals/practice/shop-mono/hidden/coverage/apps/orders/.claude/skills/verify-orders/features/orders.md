# Orders

A customer's order is stored and queued for a confirmation email.

## Sub-features

- orders.create: placing an order stores it with the customer's email, its lines, and a total of price times quantity.
- orders.enqueue: each stored order puts exactly one job in the shared outbox naming the order ID and the customer's email.

## How a user reaches it

- `POST /orders` from the storefront.

## Verification plan

Source: REQUIREMENTS.md SR-1 and SR-2.

- orders.create: place an order through the API; read the stored row and compare lines, email, and total with what was sent, using the prices SR-1 fixes.
- orders.enqueue: read the shared outbox file and count the jobs naming the order.

## How to prove it

- orders.create: `python3 .claude/skills/verify-orders/scripts/checks/orders.py`. Reads the order row (state).
- orders.enqueue: `python3 .claude/skills/verify-orders/scripts/checks/orders.py`. Reads the outbox file (state).
