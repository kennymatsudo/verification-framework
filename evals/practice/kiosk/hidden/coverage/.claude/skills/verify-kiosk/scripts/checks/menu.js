#!/usr/bin/env node
// Check menu.shown: the kiosk page lists every menu item with its name and price, as REQUIREMENTS.md KR-1 fixes them.
// Run through vf.py run; --help needs no server or browser.
if (process.argv.includes("--help") || process.argv.includes("-h")) {
  console.log("Check menu.shown: the kiosk page lists Espresso $3.00, Latte $4.50, and Croissant $3.75. Run through vf.py run.");
  process.exit(0);
}
const path = require("path");
const reporter = require(path.join(__dirname, "..", "reporter"));
const { Screen } = require(path.join(__dirname, "..", "screen"));
const { BASE_URL } = require(path.join(__dirname, "..", "connections"));

const EXPECTED = [["Espresso", "$3.00"], ["Latte", "$4.50"], ["Croissant", "$3.75"]];

(async () => {
  reporter.check("menu", ["menu.shown"], "what the user sees");
  const screen = new Screen();
  try {
    await screen.open(BASE_URL + "/");
  } catch (error) {
    reporter.stopped(`the kiosk page did not load: ${error.message}`);
  }
  try {
    screen.beginStep("Step 1: Customer looks at the menu");
    await screen.page.waitForSelector("#menu li", { timeout: 5000 }).catch(() => null);
    const shown = await screen.page.$$eval("#menu li", (items) => items.map((li) => [li.querySelector("span > span") ? li.textContent.replace(li.querySelector(".price").textContent, "").trim() : li.textContent.trim(), li.querySelector(".price") ? li.querySelector(".price").textContent.trim() : ""]));
    const names = shown.map(([name, price]) => [name.replace(/\s*Add$/, "").trim(), price]);
    const same = JSON.stringify(names) === JSON.stringify(EXPECTED);
    await screen.step("menu lists every item with its price", same, ["menu.shown"], `shown=${JSON.stringify(names)} expected=${JSON.stringify(EXPECTED)}`);
  } finally {
    await screen.close();
  }
  reporter.exit();
})();
