# Cart

A customer builds their order and watches the total.

## Sub-features

- cart.add: tapping "Add" on an item puts one of it in the cart; tapping it again raises the quantity by one.
- cart.total: the total shown on the page equals the sum of each cart line's price times its quantity.

## How a user reaches it

- The kiosk page at `/`, "Add" buttons and the "Your order" section.

## Verification plan

Source: REQUIREMENTS.md KR-2 and KR-3, with KR-1's prices. KR-6's tax line is undecided and has no check.

- cart.add: tap Add Latte twice and Add Espresso once; read the cart lines and the latte quantity as shown.
- cart.total: read the total as shown; expect $12.00, computed from KR-1's prices, not from the page's own arithmetic.

## How to prove it

- cart.add: `node .claude/skills/verify-kiosk/scripts/checks/cart.js`. Reads the rendered cart (what the user sees).
- cart.total: `node .claude/skills/verify-kiosk/scripts/checks/cart.js`. Reads the rendered total (what the user sees).
