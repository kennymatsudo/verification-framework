#!/usr/bin/env python3
"""Is relay runnable from the checkout the checks point at, and which code is it?

Usage: doctor.py [--point CHECKOUT]

Without --point, runs `python3 -m relay --version` from the pointed checkout and prints `relay ready`, the version, and
that checkout's code state as JSON (exit 0); exit 1 with the reason when relay does not run there; exit 2 when it
could not tell. With --point, writes CHECKOUT to the pointer file evidence/launch/checkout.txt (`.` for this checkout)
and then runs the same check, so a break session's Run scratch code command repoints and confirms in one step.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import connections  # noqa: E402


def main(argv):
    if "--help" in argv or "-h" in argv:
        print(__doc__)
        return 0
    if argv[:1] == ["--point"]:
        if len(argv) != 2:
            print("usage: doctor.py --point CHECKOUT", file=sys.stderr)
            return 2
        connections.POINTER.parent.mkdir(parents=True, exist_ok=True)
        target = Path(argv[1]).resolve()
        connections.POINTER.write_text("." if target == connections.PROJECT_ROOT.resolve() else str(target))
    checkout = connections.checkout()
    if not (checkout / "relay" / "cli.py").is_file():
        print(f"not ready: {checkout} has no relay/cli.py")
        return 1
    ran = subprocess.run(connections.relay_command() + ["--version"], cwd=checkout, capture_output=True, text=True, timeout=30)
    if ran.returncode != 0:
        print(f"not ready: relay --version exited {ran.returncode} in {checkout}: {ran.stderr.strip()[-200:]}")
        return 1
    vf = connections.HARNESS / "scripts" / "framework" / "vf.py"
    state = subprocess.run([sys.executable, str(vf), "code-state", "--checkout", f"relay={checkout}"], cwd=connections.PROJECT_ROOT, capture_output=True, text=True, timeout=60)
    if state.returncode != 0:
        print(f"STOPPED: could not read the code state of {checkout}: {state.stderr.strip()[-200:]}", file=sys.stderr)
        return 2
    print("relay ready")
    print(ran.stdout.strip(), "from", checkout)
    print(state.stdout.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
