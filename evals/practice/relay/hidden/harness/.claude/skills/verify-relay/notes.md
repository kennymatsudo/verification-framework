# Verification notes

## Setup notes

Relay is a command-line tool with no server: nothing starts or stops, and every check runs `python3 -m relay` itself, so Start and Stop are `none`. The checks and the doctor run the tool from the checkout `VERIFY_CHECKOUT_RELAY` names, which `vf.py` sets to this checkout on an ordinary run and to a planned break's scratch copy during one; the doctor confirms that checkout holds a runnable relay and reports its code state. Each run reads the files afresh, so an edit needs no restart (Reloads: yes). Everything runs from the project root; nothing reaches an external or shared system.

## Known failing checks

None yet.

## Where a pass can mislead

None yet.

## Untested cases

- Inputs with thousands of rows.
