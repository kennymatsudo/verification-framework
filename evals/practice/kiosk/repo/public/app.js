// The kiosk page: menu, cart, total, and placing the order.
const cart = new Map(); // sku -> { sku, name, price_cents, qty }
let menu = [];

function dollars(cents) {
  return `$${(cents / 100).toFixed(2)}`;
}

function cartTotal() {
  let total = 0;
  for (const line of cart.values()) total += line.price_cents * line.qty;
  return total;
}

function renderMenu() {
  const list = document.getElementById("menu");
  list.innerHTML = "";
  for (const item of menu) {
    const li = document.createElement("li");
    li.dataset.sku = item.sku;
    li.innerHTML = `<span>${item.name} <span class="price">${dollars(item.price_cents)}</span></span>`;
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Add";
    button.setAttribute("aria-label", `Add ${item.name}`);
    button.addEventListener("click", () => addToCart(item));
    li.appendChild(button);
    list.appendChild(li);
  }
}

function addToCart(item) {
  const line = cart.get(item.sku) || { ...item, qty: 0 };
  line.qty += 1;
  cart.set(item.sku, line);
  renderCart();
}

function renderCart() {
  const list = document.getElementById("cart");
  list.innerHTML = "";
  for (const line of cart.values()) {
    const li = document.createElement("li");
    li.dataset.sku = line.sku;
    li.innerHTML = `<span>${line.name} × <span class="qty">${line.qty}</span></span><span class="line-total">${dollars(line.price_cents * line.qty)}</span>`;
    list.appendChild(li);
  }
  const total = document.getElementById("total");
  total.textContent = dollars(cartTotal());
  total.dataset.cents = String(cartTotal());
  document.getElementById("message").textContent = "";
}

async function placeOrder() {
  const message = document.getElementById("message");
  const confirmation = document.getElementById("confirmation");
  confirmation.textContent = "";
  if (cart.size === 0) {
    message.textContent = "Add something first";
    return;
  }
  const items = [...cart.values()].map((line) => ({ sku: line.sku, qty: line.qty }));
  const response = await fetch("/api/orders", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }) });
  const result = await response.json();
  if (!response.ok) {
    message.textContent = result.error || "Something went wrong";
    return;
  }
  confirmation.textContent = `Order #${result.number} placed. Total ${dollars(result.total_cents)}.`;
  confirmation.dataset.number = String(result.number);
  cart.clear();
  renderCart();
}

async function start() {
  menu = await (await fetch("/api/menu")).json();
  renderMenu();
  renderCart();
  document.getElementById("place").addEventListener("click", placeOrder);
}

start();
