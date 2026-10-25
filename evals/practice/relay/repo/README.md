# Relay

A command-line converter the finance team runs before uploading expense sheets: it turns a CSV of names and dollar amounts into the JSON the upload tool wants, with amounts in cents and a total.

## Run it

    python3 -m relay convert examples/expenses.csv out.json
    python3 -m relay --version

No server, no install, Python 3 only. Each run reads the input, writes the output file, and exits: 0 when converted, 2 when the input is malformed (the message names the line, and no output file is written).

## Format

Input CSV with a header row `name,amount`, amounts in dollars such as `12.30`. Output: `{"rows": [{"name": "...", "amount_cents": 1230}, ...], "total_cents": <sum>}`.

See [REQUIREMENTS.md](REQUIREMENTS.md).
