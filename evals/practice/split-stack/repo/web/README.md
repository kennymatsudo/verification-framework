# stock

The stock room's command-line client. Talks to the Stock API, which lives in the `api` repo checked out beside this one.

## Set up

Copy `stack.env.example` to `stack.env` and set `API_CHECKOUT` to where you cloned the API (default `../api`) and `API_URL` to where it runs (default `http://127.0.0.1:8075`). Build and start the API from its own README, then:

    python3 -m stock list
    python3 -m stock add Widget 3

`add` answers `added Widget x3`; a negative quantity answers `refused: qty must be zero or more` and exits 1. `list` prints one `name  qty` line per stored item.

See [REQUIREMENTS.md](REQUIREMENTS.md).
