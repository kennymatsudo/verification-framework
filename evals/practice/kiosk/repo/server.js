// The kiosk server: static files from public/ and a small JSON API over a file store.
const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.env.KIOSK_PORT || 8072);
const DATA = process.env.KIOSK_DATA || path.join(process.cwd(), "data", "orders.json");
const PUBLIC = path.join(__dirname, "public");

const MENU = [
  { sku: "espresso", name: "Espresso", price_cents: 300 },
  { sku: "latte", name: "Latte", price_cents: 450 },
  { sku: "croissant", name: "Croissant", price_cents: 375 },
];

function readOrders() {
  try {
    return JSON.parse(fs.readFileSync(DATA, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

function writeOrders(orders) {
  fs.mkdirSync(path.dirname(DATA), { recursive: true });
  fs.writeFileSync(DATA, JSON.stringify(orders, null, 2));
}

function priceOrder(items) {
  const lines = [];
  let total = 0;
  for (const item of items) {
    const menuItem = MENU.find((m) => m.sku === item.sku);
    const qty = Number(item.qty);
    if (!menuItem || !Number.isInteger(qty) || qty < 1) throw new Error(`bad line ${JSON.stringify(item)}`);
    lines.push({ sku: menuItem.sku, name: menuItem.name, qty, price_cents: menuItem.price_cents });
    total += menuItem.price_cents * qty;
  }
  return { lines, total_cents: total };
}

function json(res, status, body) {
  const data = JSON.stringify(body);
  res.writeHead(status, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) });
  res.end(data);
}

function serveStatic(res, file) {
  const target = path.join(PUBLIC, file === "/" ? "index.html" : file);
  if (!target.startsWith(PUBLIC)) return json(res, 404, { error: "not found" });
  fs.readFile(target, (error, data) => {
    if (error) return json(res, 404, { error: "not found" });
    const type = target.endsWith(".js") ? "text/javascript" : target.endsWith(".css") ? "text/css" : "text/html";
    res.writeHead(200, { "Content-Type": type });
    res.end(data);
  });
}

function body(req) {
  return new Promise((resolve, reject) => {
    let text = "";
    req.on("data", (chunk) => (text += chunk));
    req.on("end", () => {
      try { resolve(text ? JSON.parse(text) : {}); } catch (error) { reject(error); }
    });
  });
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://localhost");
  try {
    if (req.method === "GET" && url.pathname === "/api/menu") return json(res, 200, MENU);
    if (req.method === "GET" && url.pathname === "/api/health") return json(res, 200, { status: "ok" });
    if (req.method === "POST" && url.pathname === "/api/orders") {
      const payload = await body(req);
      const items = Array.isArray(payload.items) ? payload.items : [];
      if (items.length === 0) return json(res, 400, { error: "empty order" });
      const priced = priceOrder(items);
      const orders = readOrders();
      const order = { number: orders.length + 1, ...priced, placed_at: new Date().toISOString() };
      orders.push(order);
      writeOrders(orders);
      return json(res, 201, { number: order.number, total_cents: order.total_cents });
    }
    const match = url.pathname.match(/^\/api\/orders\/(\d+)$/);
    if (req.method === "GET" && match) {
      const order = readOrders().find((o) => o.number === Number(match[1]));
      return order ? json(res, 200, order) : json(res, 404, { error: "not found" });
    }
    if (req.method === "GET" && !url.pathname.startsWith("/api/")) return serveStatic(res, url.pathname);
    return json(res, 404, { error: "not found" });
  } catch (error) {
    return json(res, 400, { error: error.message });
  }
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`kiosk listening on http://127.0.0.1:${PORT}, orders in ${DATA}`);
});
