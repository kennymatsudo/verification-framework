// Works the outbox: one confirmation email per pending job, dropped into the relay folder, then marked done.
const fs = require("fs");
const path = require("path");

const OUTBOX = process.env.SHOP_OUTBOX || path.join(__dirname, "..", "..", "queue", "outbox.jsonl");
const SINK = process.env.MAIL_SINK || path.join(__dirname, "..", "..", "mail-sink");

function readJobs() {
  try {
    return fs.readFileSync(OUTBOX, "utf8").split("\n").filter(Boolean).map((line) => JSON.parse(line));
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
}

function send(job) {
  fs.mkdirSync(SINK, { recursive: true });
  const message = [`To: ${job.email}`, `Subject: Your order #${job.order_id}`, "", `Thanks! We received your order #${job.order_id} for $${(job.total_cents / 100).toFixed(2)}.`].join("\n");
  fs.writeFileSync(path.join(SINK, `order-${job.order_id}-${Date.now()}.eml`), message);
}

function workOnce() {
  const jobs = readJobs();
  let sent = 0;
  for (const job of jobs) {
    if (job.status !== "pending") continue;
    send(job);
    job.status = "done";
    sent += 1;
  }
  if (sent) fs.writeFileSync(OUTBOX, jobs.map((j) => JSON.stringify(j)).join("\n") + "\n");
  console.log(`mailer: sent ${sent} message(s)`);
}

if (process.argv.includes("--once")) {
  workOnce();
} else {
  workOnce();
  setInterval(workOnce, 5000);
}
