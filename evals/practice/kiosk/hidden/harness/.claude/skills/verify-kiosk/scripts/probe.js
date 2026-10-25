#!/usr/bin/env node
// Read the kiosk's stored orders without loading server code.
//
// Usage:
//   probe.js order NUMBER   one stored order: number, lines, total_cents, placed_at
//   probe.js orders         every stored order's number and total
//
// Reads data/orders.json under the project root (or KIOSK_DATA); the server need not be running. Prints one JSON
// object. Exit 0 when answered; 1 when the order does not exist, with {"not_found", "hint"}; 2 when the file could
// not be read, with STOPPED: <reason> on stderr.
const HELP = require("fs").readFileSync(__filename, "utf8").split("\n").filter((l) => l.startsWith("//")).map((l) => l.slice(3)).join("\n");

const args = process.argv.slice(2);
if (args.length === 0 || args.includes("--help") || args.includes("-h")) {
  console.log(HELP);
  process.exit(0);
}
const reads = require("./reads");
try {
  if (args[0] === "order") {
    const found = reads.order(args[1]);
    if (!found) {
      console.log(JSON.stringify({ not_found: `order ${args[1]}`, hint: "probe.js orders" }));
      process.exit(1);
    }
    console.log(JSON.stringify({ ...found, next: ["probe.js orders"] }));
  } else if (args[0] === "orders") {
    console.log(JSON.stringify({ orders: reads.orders().map((o) => ({ number: o.number, total_cents: o.total_cents })), next: ["probe.js order <number>"] }));
  } else {
    console.log(HELP);
    process.exit(2);
  }
} catch (error) {
  console.error(`STOPPED: ${error.message}`);
  process.exit(2);
}
