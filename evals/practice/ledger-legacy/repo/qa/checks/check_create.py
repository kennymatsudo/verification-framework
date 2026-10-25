"""Opening an account works."""
import sys
sys.path.insert(0, "qa")
from lib import call, verdict

status, body = call("POST", "/accounts", {"name": "qa-create"})
verdict(status == 201, f"status={status}")
