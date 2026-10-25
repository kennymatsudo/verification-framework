# Kiosk

A self-service ordering screen for a cafe counter. Customers tap items on the menu, see their running total, and place the order; staff read orders from the data file.

## Run it

    npm start

The server listens on `http://127.0.0.1:8072` (override with `KIOSK_PORT`) and writes orders to `data/orders.json` under the working directory (override with `KIOSK_DATA`). It needs nothing but Node. Static files under `public/` are read on every request, so a page edit shows on reload; a change to `server.js` needs a restart.

## Screens and API

- `/` is the kiosk page: the menu, the cart with quantities and a total, and a "Place order" button that shows the order number.
- `GET /api/menu` lists items: `[{"sku", "name", "price_cents"}]`.
- `POST /api/orders` with `{"items": [{"sku", "qty"}]}` stores the order and answers `201 {"number", "total_cents"}`; an order with no items answers `400 {"error": "empty order"}`.
- `GET /api/orders/<number>` reads a stored order.

See [REQUIREMENTS.md](REQUIREMENTS.md) for the intended behavior.

## Tests

    npm test
