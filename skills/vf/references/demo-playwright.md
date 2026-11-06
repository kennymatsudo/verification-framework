# A demo scenario in Playwright

An example to adapt, not a library to import. It shows one way to meet rules.md's "Demo runs" section with Playwright for Python: a helper that paces actions, marks that carry captions and screens, the overlay from `demo-overlay.js`, and a scenario that judges each shot. A harness in another language or browser driver keeps the same shape: one object every action goes through, holds only after a verdict, and the same events.

Put both files in the harness's `demos/<name>/`, outside `scripts/`, so no check's harness code changes. Reuse the harness's own sign-in, reads, and page helpers by importing them; when the harness already reports events through a helper, use that instead of `Report` below.

## The pacing helper

```python
"""Pacing and overlay for demo scenarios: every action a demo takes goes through Pace."""

import json
import os
import time
from pathlib import Path

TYPING_DELAY_MS = 45      # per character
BEFORE_ACTION = 0.9       # seconds the pointer rests on an element before acting on it
CAPTION_HOLD = 4.5        # a caption stays at least this long
RESULT_HOLD = 5.0         # a result stays at least this long after its verdict
SWITCH_BEFORE = 2.5       # the switch card over the screen being left
SWITCH_AFTER = 2.0        # the card over the next screen once it has loaded
VIEWPORT = {"width": 1920, "height": 1080}  # the video's size; the page is never zoomed or cropped
OVERLAY = Path(__file__).with_name("demo-overlay.js")  # copied unchanged from vf's references/

# A visible pointer: Playwright's own is not drawn into the recording.
POINTER = """
(() => {
  const dot = document.createElement('div');
  Object.assign(dot.style, {position: 'fixed', width: '18px', height: '18px', borderRadius: '50%',
    background: 'rgba(239, 68, 68, 0.85)', zIndex: '2147483647', pointerEvents: 'none',
    transform: 'translate(-50%, -50%)', left: '-40px', top: '-40px'});
  addEventListener('mousemove', (event) => {
    if (!dot.isConnected && document.body) document.body.appendChild(dot);
    dot.style.left = event.clientX + 'px'; dot.style.top = event.clientY + 'px';
  }, true);
})();
"""


class Report:
    """Appends the run's events to VERIFY_REPORT, as rules.md's Evidence section defines."""

    def __init__(self, name, sub_features, reads):
        self.started = time.monotonic()
        self.path = Path(os.environ["VERIFY_REPORT"])
        self.event("check", name=name, sub_features=sub_features, reads=reads)

    def seconds(self):
        return round(time.monotonic() - self.started, 2)

    def event(self, kind, **fields):
        with self.path.open("a") as report:
            report.write(json.dumps({"event": kind, **fields}) + "\n")


class Pace:
    """Every action and caption of a demo, paced for people. Not for checks: an ordinary run never imports it."""

    def __init__(self, page, report):
        self.page, self.report, self.screen = page, report, None

    @staticmethod
    def install(context):
        """Call once on the browser context, before its first page opens."""
        context.add_init_script(path=str(OVERLAY))
        context.add_init_script(POINTER)

    def hold(self, seconds):
        self.page.wait_for_timeout(int(seconds * 1000))

    def overlay(self, key, value):
        stored = value if value is None or isinstance(value, str) else json.dumps(value)
        self.page.evaluate("([k, v]) => { v === null ? sessionStorage.removeItem(k) : sessionStorage.setItem(k, v);"
                           " window.__demoDraw && window.__demoDraw(); }", [key, stored])

    def step(self, label, caption):
        """Start a numbered step with the caption people read during it."""
        self.report.event("mark", kind="step", label=label, at=self.report.seconds(), caption=caption)
        self.overlay("demoCaption", caption)
        self.hold(CAPTION_HOLD)

    def caption(self, text, hold=CAPTION_HOLD, label=None):
        """A caption inside a step, such as what a wait is waiting for."""
        self.report.event("mark", kind="action", label=label or text, at=self.report.seconds(), caption=text)
        self.overlay("demoCaption", text)
        self.hold(hold)

    def verdict(self, name, passed, detail="", sub_features=None, hold=RESULT_HOLD):
        """Judge what the viewer was just shown, then hold it on screen. The hold comes after the verdict."""
        self.report.event("step", name=name, passed=bool(passed), at=self.report.seconds(), detail=detail,
                          **({"sub_features": sub_features} if sub_features else {}))
        if not passed:
            raise AssertionError(f"{name}: {detail}")
        self.hold(hold)

    def switch(self, person, open_page):
        """Show whose screen comes next, open it, and name it with a badge while it shows.

        person is {"badge", "title", "detail", "color"}; open_page signs that person in and loads their page."""
        card = {"title": person["title"], "detail": person["detail"], "color": person["color"]}
        if self.screen is not None:
            self.overlay("demoCaption", None)
            self.overlay("demoCard", card)
            self.hold(SWITCH_BEFORE)
        self.report.event("mark", kind="action", label=f"Switches to {person['badge']}", at=self.report.seconds(),
                          screen=person["badge"])
        open_page()
        self.overlay("demoCard", card)
        self.overlay("demoScreen", {"badge": person["badge"], "color": person["color"]})
        self.hold(SWITCH_AFTER)
        self.overlay("demoCard", None)
        self.screen = person["badge"]

    def click(self, locator):
        """Move to the element, rest there so the viewer sees where the pointer is, then click."""
        locator.wait_for()
        locator.scroll_into_view_if_needed()
        locator.hover()
        self.hold(BEFORE_ACTION)
        locator.click()

    def type(self, locator, text):
        """Type as a person does, a character at a time."""
        self.click(locator)
        locator.press_sequentially(text, delay=TYPING_DELAY_MS)
```

## A scenario

```python
"""Demo: a shopper pays, and the store's staff sees the order. Shot list approved by the developer on 2026-11-06."""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from pacing import VIEWPORT, Pace, Report

SHOPPER = {"badge": "Shopper view: Checkout", "title": "Shopper side", "detail": "A shopper pays for an order",
           "color": "#047857"}
STAFF = {"badge": "Staff view: Orders", "title": "Staff side", "detail": "Store staff watch new orders",
         "color": "#5b21b6"}


def main():
    if os.environ.get("VERIFY_DEMO") != "1":
        print("This is a demo scenario; run it with vf.py run --demo --user-approved", file=sys.stderr)
        return 2
    report = Report("checkout-demo", ["checkout.pay", "orders.list"], "what the shopper and staff see")
    run_dir = Path(os.environ["VERIFY_RUN_DIR"])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport=VIEWPORT, record_video_dir=str(run_dir),
                                      record_video_size=VIEWPORT)
        Pace.install(context)
        page = context.new_page()
        report.event("recording", video="video.webm", starts_at=report.seconds())
        demo = Pace(page, report)
        try:
            demo.switch(SHOPPER, lambda: page.goto("http://localhost:8000/cart"))
            demo.step("Step 1: the shopper pays", "A shopper pays for the two items in their cart")
            demo.type(page.get_by_label("Card number"), "4242 4242 4242 4242")
            demo.click(page.get_by_role("button", name="Pay"))
            # The read keeps the timeout an ordinary check gives it; no pause sits between the click and this read.
            shown = page.get_by_text("Thanks for your order").is_visible(timeout=10_000)
            demo.verdict("the confirmation shows", shown, sub_features=["checkout.pay"])

            demo.switch(STAFF, lambda: page.goto("http://localhost:8000/staff/orders"))
            demo.step("Step 2: staff see the order", "The order appears for store staff within seconds")
            demo.caption("Waiting for the order list to refresh", hold=0)
            listed = page.get_by_text("2 items").first.is_visible(timeout=15_000)
            demo.verdict("the order is listed", listed, sub_features=["orders.list"])
        except AssertionError as failure:
            print(failure, file=sys.stderr)
            return 1
        finally:
            video = page.video
            context.close()
            browser.close()
            if video:
                Path(video.path()).replace(run_dir / "video.webm")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run it, after the person approved the demo run:

```
<harness>/scripts/framework/vf.py run --demo --user-approved -- python3 <harness>/demos/checkout/run.py
```

Things the example gets right that are easy to break:

- **The read is never paced.** `click` rests before acting, and `verdict` holds after judging, so the time between the click and the read that times its result is the same as in an ordinary run.
- **One browser for both people.** Switching cookies or URLs in one context records one continuous video. When the two people need separate browsers at once, record each context, report one `recording` per context with its `screen`, and keep the `screen` marks on the switches; `vf.py demo` cuts between the videos at those marks without losing time.
- **It refuses outside a demo run.** The scenario paces every action, so it is never run as a check.
