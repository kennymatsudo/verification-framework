#!/usr/bin/env python3
"""Build, start, and check the Stock API from the api checkout.

Usage:
  api_server.py start [--restart] [--checkout NAME=PATH ...]
  api_server.py doctor

start reads every repo's code state through the framework (vf.py code-state, with any --checkout override), builds the
API from the api checkout with `-X main.version=<commit>[+<dirty_hash>]` so the binary carries the code it was built
from, and starts it through `vf.py start` with its data at data/stock-items.json under the project root. --restart stops
a running instance first. A break session passes --checkout api=<scratch copy>.

doctor runs the launcher's doctor (process up, code on disk unchanged since launch, health answering) and then compares
GET /version with the stamp of the checkout the launch record names. Prints `stock ready` and the code state as JSON
on exit 0; a reason on exit 1; STOPPED: on exit 2 when it could not tell.
"""

import json
import os
import shlex
import subprocess
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import connections  # noqa: E402

VF = connections.HARNESS / "scripts" / "framework" / "vf.py"
PROBE = f"curl -sf {connections.API_URL}/health"


def vf(*args, check=True):
    ran = subprocess.run([sys.executable, str(VF), *args], cwd=connections.PROJECT_ROOT, capture_output=True, text=True)
    if check and ran.returncode:
        print(ran.stdout + ran.stderr, end="", file=sys.stderr)
        sys.exit(2)
    return ran


def stamp(overrides):
    """<commit>[+<dirty_hash>] for the api repo, from the framework's code state with the overrides given."""
    args = ["code-state"] + [f"--checkout={name}={path}" for name, path in overrides.items()]
    state = json.loads(vf(*args).stdout)
    api = state["api"]
    return api["commit"][:12] + (f"+{api['dirty_hash'][:12]}" if api.get("dirty_hash") else "")


def start(argv):
    overrides = dict(arg.split("=", 1) for arg in argv if "=" in arg)
    if "--restart" in argv:
        vf("stop")
    checkout = Path(overrides.get("api", connections.api_checkout())).resolve()
    version = stamp(overrides)
    binary = checkout / "bin" / "stock-api"
    binary.parent.mkdir(parents=True, exist_ok=True)
    build = subprocess.run(["go", "build", "-ldflags", f"-X main.version={version}", "-o", str(binary), "."], cwd=checkout,
                           capture_output=True, text=True, env=dict(os.environ, GOFLAGS="-mod=mod", GOTOOLCHAIN="local"))
    if build.returncode:
        print(f"STOPPED: go build failed in {checkout}:\n{build.stderr}", file=sys.stderr)
        return 2
    command = ["start"] + [f"--checkout={name}={path}" for name, path in overrides.items()] + ["--until", PROBE, "--",
               "env", f"STOCK_DATA={connections.DATA_PATH}", f"STOCK_PORT={connections.API_PORT}", str(binary)]
    ran = vf(*command, check=False)
    print(ran.stdout + ran.stderr, end="")
    return ran.returncode


def doctor():
    ran = vf("doctor", "--probe", PROBE, check=False)
    if ran.returncode:
        print(ran.stdout + ran.stderr, end="")
        return ran.returncode
    record_path = connections.HARNESS / "evidence" / "launch" / "record.json"
    overrides = json.loads(record_path.read_text()).get("checkouts") or {} if record_path.is_file() else {}
    expected = stamp(overrides)
    try:
        with urllib.request.urlopen(f"{connections.API_URL}/version", timeout=5) as response:
            loaded = json.loads(response.read())["version"]
    except (OSError, ValueError, KeyError) as error:
        print(f"STOPPED: could not read /version: {error}", file=sys.stderr)
        return 2
    if loaded != expected:
        print(f"not ready: the API runs build {loaded} but the api checkout is {expected}; restart it with api_server.py start --restart")
        return 1
    print("stock ready")
    print(f"api build {loaded}")
    print(ran.stdout.split("\n", 1)[1] if "\n" in ran.stdout else "", end="")
    return 0


def main(argv):
    if not argv or "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    if argv[0] == "start":
        return start(argv[1:])
    if argv[0] == "doctor":
        return doctor()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
