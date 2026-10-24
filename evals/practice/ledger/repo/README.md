# Ledger

A small accounts service: open accounts, post deposits and withdrawals, move money between accounts, and read a statement. It is an HTTP API with no UI, backed by SQLite.

## Run it

    python3 -m ledger

The server listens on `http://127.0.0.1:8071` (override with `LEDGER_PORT`) and keeps its data in `data/ledger.db` under the working directory (override with `LEDGER_DB`). It creates the database on first start. `GET /health` answers `{"status": "ok"}` once it is up. Stop it with Ctrl-C; there is no reload on edit, so restart it after changing code.

## API

| Method and path | Body | Answer |
| --- | --- | --- |
| `POST /accounts` | `{"name": "Ada"}` | `201 {"id": 1, "name": "Ada", "balance": 0}` |
| `GET /accounts/<id>` | | `{"id", "name", "balance"}` or 404 |
| `POST /accounts/<id>/transactions` | `{"amount": 25, "memo": "salary"}`; a negative amount withdraws | `201 {"id": <transaction id>, "balance": <new balance>}` |
| `POST /transfers` | `{"from": 1, "to": 2, "amount": 10}` | `201 {"id": <transfer id>}`, or `409 {"error": "insufficient funds"}` |
| `GET /accounts/<id>/statement` | | `{"transactions": [{"id", "amount", "memo", "balance_after", "at"}, ...]}` newest first |

Amounts are integers in cents. See [REQUIREMENTS.md](REQUIREMENTS.md) for the intended behavior.

## Tests

    python3 -m unittest discover -s tests
