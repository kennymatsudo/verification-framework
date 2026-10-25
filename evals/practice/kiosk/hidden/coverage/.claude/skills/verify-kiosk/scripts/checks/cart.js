#!/usr/bin/env node
// Check cart.add and cart.total: tapping Add puts an item in the cart and tapping again raises its quantity; the total
// shown equals the sum of price times quantity. Expected amounts come from REQUIREMENTS.md KR-1's prices. Run through
// vf.py run; --help needs no server or browser.
if (process.argv.includes("--help") || process.argv.includes("-h")) {
  console.log("Check cart.add and cart.total on the kiosk page: add Latte twice and Espresso once, expect quantity 2 and total $12.00. Run through vf.py run.");
  process.exit(0);
}
const path = require("path");
const reporter = require(path.join(__dirname, "..", "reporter"));
const { Screen } = require(path.join(__dirname, "..", "screen"));
const { BASE_URL } = require(path.join(__dirname, "..", "connections"));

(async () => {
  reporter.check("cart", ["cart.add", "cart.total"], "what the user sees");
  const screen = new Screen();
  try {
    await screen.open(BASE_URL + "/");
    await screen.page.waitForSelector("#menu li", { timeout: 5000 });
  } catch (error) {
    reporter.stopped(`the kiosk page did not load: ${error.message}`);
  }
  const page = screen.page;
  try {
    screen.beginStep("Step 1: Customer adds a latte twice and an espresso");
    screen.action("Taps Add Latte");
    await page.getByRole("button", { name: "Add Latte" }).click();
    screen.action("Taps Add Latte again");
    await page.getByRole("button", { name: "Add Latte" }).click();
    screen.action("Taps Add Espresso");
    await page.getByRole("button", { name: "Add Espresso" }).click();
    await page.waitForFunction(() => document.querySelectorAll("#cart li").length >= 2, null, { timeout: 3000 }).catch(() => null);
    const latteQty = await page.$eval('#cart li[data-sku="latte"] .qty', (el) => el.textContent.trim()).catch(() => "missing");
    const lines = await page.$$eval("#cart li", (items) => items.map((li) => li.dataset.sku));
    await screen.step("adding again raises the quantity", latteQty === "2" && lines.length === 2, ["cart.add"], `latte qty=${latteQty} lines=${JSON.stringify(lines)}`);

    screen.beginStep("Step 2: Customer reads the total");
    // 2 x 450 + 300 = 1200 cents, from the prices KR-1 fixes
    await page.waitForFunction(() => document.getElementById("total").dataset.cents !== "0", null, { timeout: 3000 }).catch(() => null);
    const totalText = await page.$eval("#total", (el) => el.textContent.trim());
    const totalCents = await page.$eval("#total", (el) => el.dataset.cents);
    await screen.step("total equals the sum of the lines", totalText === "$12.00" && totalCents === "1200", ["cart.total"], `shown=${totalText} cents=${totalCents} expected $12.00`);
  } finally {
    await screen.close();
  }
  reporter.exit();
})();
