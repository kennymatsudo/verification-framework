# Orders

Takes orders and stores them, then queues a confirmation for the mailer.

## Run it

From this folder:

    python3 -m orders

Listens on `http://127.0.0.1:8073` (`ORDERS_PORT`). Stores orders in `data/orders.db` under the working directory (`ORDERS_DB`) and appends one job per order to the shared outbox at `../../queue/outbox.jsonl` (`SHOP_OUTBOX`). `GET /health` answers once it is up. Restart after changing code.

## API

| Method and path | Body | Answer |
| --- | --- | --- |
| `POST /orders` | `{"email": "a@example.com", "items": [{"sku": "mug", "qty": 2}]}` | `201 {"id", "total_cents"}` |
| `GET /orders/<id>` | | `{"id", "email", "items", "total_cents"}` or 404 |

Prices: mug 1200, tee 2500, cap 1800 cents.
