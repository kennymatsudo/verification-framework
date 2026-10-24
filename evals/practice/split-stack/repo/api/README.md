# Stock API

Keeps the stock room's item counts. A Go service with a JSON file store; the `stock` command-line client in the `web` repo talks to it.

## Build and run

    go build -o bin/stock-api .
    ./bin/stock-api

Listens on `http://127.0.0.1:8075` (`STOCK_PORT`), stores items in `data/items.json` under the working directory (`STOCK_DATA`). `GET /health` answers once it is up. `GET /version` reports the build's version, stamped at build time with `-ldflags "-X main.version=<commit>"`; an unstamped build reports `dev`.

## API

| Method and path | Body | Answer |
| --- | --- | --- |
| `GET /items` | | `[{"name", "qty"}]` |
| `POST /items` | `{"name": "Widget", "qty": 3}` | `201 {"name", "qty"}`; `400 {"error": "qty must be zero or more"}` for a negative qty |
