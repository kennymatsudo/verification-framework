# Order

A customer places the order, or is told to add something first.

## Sub-features

- order.place: placing the order stores it with the same lines and total the customer saw, and the page shows the stored order's number.
- order.empty-refused: placing an order with an empty cart shows "Add something first" and stores nothing.

## How a user reaches it

- The kiosk page at `/`, "Place order" button.

## Verification plan

Source: REQUIREMENTS.md KR-4 and KR-5.

- order.empty-refused: tap Place order with nothing in the cart; read the message shown and count stored orders before and after.
- order.place: build a cart of two lattes and a croissant, note the total shown, place it; read the stored order from the data file and compare its lines and total with what was shown, and the confirmation's number with the stored number.

## How to prove it

- order.place: `node .claude/skills/verify-kiosk/scripts/checks/order.js`. Reads the stored order and the confirmation shown (what the user sees).
- order.empty-refused: `node .claude/skills/verify-kiosk/scripts/checks/order.js`. Reads the message shown and the stored orders (what the user sees).
