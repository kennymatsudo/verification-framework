// One function per fact a verdict relies on, read straight from the data file. No server code is loaded.
// A read returns null only when the record is absent and throws on any other failure.
const fs = require("fs");
const { DATA } = require("./connections");

function orders() {
  try {
    return JSON.parse(fs.readFileSync(DATA, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

function order(number) {
  return orders().find((o) => o.number === Number(number)) || null;
}

module.exports = { orders, order };
