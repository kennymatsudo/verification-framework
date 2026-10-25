# Menu

A customer sees what they can order.

## Sub-features

- menu.shown: the kiosk page shows every menu item with its name and price: Espresso $3.00, Latte $4.50, Croissant $3.75.

## How a user reaches it

- The kiosk page at `/`, menu section.

## Verification plan

Source: REQUIREMENTS.md KR-1.

- menu.shown: open the page in a browser and read the menu list as shown; compare with the items and prices KR-1 fixes.

## How to prove it

- menu.shown: `node .claude/skills/verify-kiosk/scripts/checks/menu.js`. Reads the rendered menu (what the user sees).
