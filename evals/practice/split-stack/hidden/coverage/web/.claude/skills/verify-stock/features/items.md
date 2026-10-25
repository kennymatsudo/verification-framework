# Items

A stock-room worker adds and lists items from the command line.

## Sub-features

- items.add: adding an item through the command stores it in the API with the exact name given and its quantity, and the command confirms what it added.
- items.list: listing shows every stored item with its quantity.
- items.reject-negative: a negative quantity is refused: the command prints the refusal, exits 1, and nothing is stored.

## How a user reaches it

- `python3 -m stock add NAME QTY` and `python3 -m stock list` from the web checkout, which call the Stock API.

## Verification plan

Source: REQUIREMENTS.md ST-1 to ST-3.

- items.add: add an item with a unique name; read the API's data file for that exact name and quantity, and the command's confirmation line.
- items.list: list; compare every line with the stored items.
- items.reject-negative: add with quantity -1; expect exit 1, a refusal message, and no stored item of that name.

## How to prove it

- items.add: `python3 .claude/skills/verify-stock/scripts/checks/items.py`. Reads the API's data file and the command's output (state).
- items.list: `python3 .claude/skills/verify-stock/scripts/checks/items.py`. Reads the listing and the data file (what the user sees).
- items.reject-negative: `python3 .claude/skills/verify-stock/scripts/checks/reject.py`. Reads the exit code, the message, and the data file (state).
