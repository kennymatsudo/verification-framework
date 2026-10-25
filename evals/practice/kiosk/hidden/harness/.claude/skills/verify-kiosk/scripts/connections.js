// Where the kiosk lives: its base URL and its data file. Other modules ask here instead of guessing.
const path = require("path");

const BASE_URL = `http://127.0.0.1:${process.env.KIOSK_PORT || 8072}`;
// Relative to the project root, where every harness command runs; the server creates it.
const DATA = process.env.KIOSK_DATA || path.join(process.cwd(), "data", "orders.json");

module.exports = { BASE_URL, DATA };
