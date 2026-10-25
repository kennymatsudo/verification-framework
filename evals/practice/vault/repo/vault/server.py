"""The vault server. Refuses to start without VAULT_TOKEN."""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

SECRETS = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def reply(self, status, body=None):
        data = json.dumps(body).encode() if body is not None else b""
        self.send_response(status)
        if data:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return self.headers.get("Authorization") == f"Bearer {self.server.token}"

    def do_GET(self):
        if self.path == "/health":
            return self.reply(200, {"status": "ok"})
        if not self.authorized():
            return self.reply(401, {"error": "token required"})
        name = self.path.removeprefix("/secrets/")
        if name in SECRETS:
            return self.reply(200, {"name": name, "value": SECRETS[name]})
        self.reply(404, {"error": "not found"})

    def do_PUT(self):
        if not self.authorized():
            return self.reply(401, {"error": "token required"})
        name = self.path.removeprefix("/secrets/")
        length = int(self.headers.get("Content-Length") or 0)
        SECRETS[name] = json.loads(self.rfile.read(length))["value"]
        self.reply(204)


def main():
    token = os.environ.get("VAULT_TOKEN")
    if not token:
        print("VAULT_TOKEN is required: get the service token from the ops password manager (vault-dev-token).", file=sys.stderr)
        sys.exit(2)
    server = HTTPServer(("127.0.0.1", int(os.environ.get("VAULT_PORT", "8076"))), Handler)
    server.token = token
    print("vault listening on http://127.0.0.1:8076", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
