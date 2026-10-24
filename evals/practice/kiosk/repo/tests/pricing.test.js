const test = require("node:test");
const assert = require("node:assert");

// The pricing rule as the server applies it: price times quantity, summed.
function price(lines) {
  return lines.reduce((sum, line) => sum + line.price_cents * line.qty, 0);
}

test("prices multiply by quantity", () => {
  assert.strictEqual(price([{ price_cents: 300, qty: 2 }, { price_cents: 450, qty: 1 }]), 1050);
});
