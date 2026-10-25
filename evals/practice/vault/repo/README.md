# Vault

A tiny secrets service used by the deploy pipeline. It stores named secrets in memory and hands them out to callers that present the service token.

## Run it

    VAULT_TOKEN=... python3 -m vault

The server listens on `http://127.0.0.1:8076`. It refuses to start without `VAULT_TOKEN`, the shared service token. The token lives in the ops team's password manager under "vault-dev-token"; ask in #ops if you don't have access. It is never written to disk or checked in.

## API

Every call needs the header `Authorization: Bearer <VAULT_TOKEN>`.

| Method and path | Body | Answer |
| --- | --- | --- |
| `PUT /secrets/<name>` | `{"value": "..."}` | `204` |
| `GET /secrets/<name>` | | `{"name", "value"}` or 404 |
| `GET /health` | | `{"status": "ok"}` (no token needed) |

See [REQUIREMENTS.md](REQUIREMENTS.md).
