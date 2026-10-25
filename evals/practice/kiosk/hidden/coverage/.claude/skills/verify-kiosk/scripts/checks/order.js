#!/usr/bin/env node
// Check order.empty-refused and order.place: placing with an empty cart shows "Add something first" and stores nothing;
// placing a cart stores the same lines and total the customer saw, and the page shows the stored order's number.
// Stored state is read from the data file, never through the server. Run through vf.py run; --help needs nothing.
if (process.argv.includes("--help") || process.argv.includes("-h")) {
  console.log("Check order.place and order.empty-refused on the kiosk page, reading data/orders.json for what was stored. Run through vf.py run.");
  process.exit(0);
}
const path = require("path");
const reporter = require(path.join(__dirname, "..", "reporter"));
const reads = require(path.join(__dirname, "..", "reads"));
const { Screen } = require(path.join(__dirname, "..", "screen"));
const { BASE_URL } = require(path.join(__dirname, "..", "connections"));

(async () => {
  reporter.check("order", ["order.empty-refused", "order.place"], "what the user sees");
  const screen = new Screen();
  try {
    await screen.open(BASE_URL + "/");
    await screen.page.waitForSelector("#menu li", { timeout: 5000 });
  } catch (error) {
    reporter.stopped(`the kiosk page did not load: ${error.message}`);
  }
  const page = screen.page;
  try {
    screen.beginStep("Step 1: Customer places an empty order");
    const before = reads.orders().length;
    screen.action("Taps Place order with an empty cart");
    await page.getByRole("button", { name: "Place order" }).click();
    await page.waitForFunction(() => document.getElementById("message").textContent.trim() !== "", null, { timeout: 3000 }).catch(() => null);
    const message = await page.$eval("#message", (el) => el.textContent.trim());
    await screen.step("empty order refused on the page", message === "Add something first", ["order.empty-refused"], `message=${JSON.stringify(message)}`);
    await screen.step("nothing stored for the empty order", reads.orders().length === before, ["order.empty-refused"], `orders before=${before} after=${reads.orders().length}`);

    screen.beginStep("Step 2: Customer orders two lattes and a croissant");
    screen.action("Taps Add Latte twice and Add Croissant");
    await page.getByRole("button", { name: "Add Latte" }).click();
    await page.getByRole("button", { name: "Add Latte" }).click();
    await page.getByRole("button", { name: "Add Croissant" }).click();
    await page.waitForFunction(() => document.querySelectorAll("#cart li").length === 2, null, { timeout: 3000 });
    const seenTotal = Number(await page.$eval("#total", (el) => el.dataset.cents));
    screen.action("Taps Place order");
    await page.getByRole("button", { name: "Place order" }).click();
    await page.waitForFunction(() => document.getElementById("confirmation").textContent.trim() !== "", null, { timeout: 5000 }).catch(() => null);
    const confirmation = await page.$eval("#confirmation", (el) => el.textContent.trim());
    const shownNumber = Number((confirmation.match(/#(\d+)/) || [])[1]);
    const newest = reads.orders().filter((o) => o.number > before).sort((a, b) => b.number - a.number)[0] || null;
    if (newest) reporter.created("orders", [newest.number]);
    const expectedLines = [["latte", 2], ["croissant", 1]];
    const storedLines = newest ? newest.lines.map((l) => [l.sku, l.qty]) : null;
    await screen.step("order stored as the customer saw it",
      newest !== null && JSON.stringify(storedLines) === JSON.stringify(expectedLines) && newest.total_cents === seenTotal && seenTotal === 1275,
      ["order.place"], `stored=${JSON.stringify(storedLines)} total=${newest ? newest.total_cents : null} seen=${seenTotal} expected lines=${JSON.stringify(expectedLines)} total=1275`,
      newest ? { order_number: newest.number } : undefined);
    await screen.step("confirmation shows the stored order number", newest !== null && shownNumber === newest.number, ["order.place"], `confirmation=${JSON.stringify(confirmation)} stored number=${newest ? newest.number : null}`);
  } finally {
    await screen.close();
  }
  reporter.exit();
})();
