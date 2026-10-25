#!/usr/bin/env python3
"""Check orders.create and orders.enqueue on the running orders service.

Places an order through POST /orders, then reads the stored row and counts the outbox jobs naming it. Run through
vf.py run from apps/orders; --help needs no server.
"""

import sys
from pathlib import Path

if "--help" in sys.argv or "-h" in sys.argv:
    print(__doc__)
    sys.exit(0)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import api  # noqa: E402
import reads  # noqa: E402
import reporter  # noqa: E402

reporter.check("orders", ["orders.create", "orders.enqueue"])
items = [{"sku": "mug", "qty": 2}, {"sku": "cap", "qty": 1}]
try:
    status, body = api.place_order("check@example.com", items)
except OSError as error:
    reporter.stopped(f"the orders service did not answer: {error}")
if status != 201 or "id" not in body:
    reporter.stopped(f"could not place the test order: {status} {body}")
order_id = body["id"]
reporter.created("orders", [order_id])

with reporter.guarded("order stored with its lines and total", ["orders.create"]):
    stored = reads.order(order_id)
    expected_total = 2 * 1200 + 1800
    reporter.step("order stored with its lines and total",
                  stored is not None and stored["email"] == "check@example.com" and stored["items"] == items and stored["total_cents"] == expected_total,
                  ["orders.create"], detail=f"stored={stored} expected total={expected_total}", evidence={"order_id": order_id})

with reporter.guarded("exactly one outbox job names the order", ["orders.enqueue"]):
    jobs = reads.jobs_for_order(order_id)
    reporter.step("exactly one outbox job names the order",
                  len(jobs) == 1 and jobs[0].get("email") == "check@example.com" and jobs[0].get("kind") == "order-confirmation",
                  ["orders.enqueue"], detail=f"jobs={jobs}")

reporter.exit()
