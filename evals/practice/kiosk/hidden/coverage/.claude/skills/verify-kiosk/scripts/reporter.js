// Append one JSON event per line to the file VERIFY_REPORT names, as the Evidence section of rules.md defines.
// A check calls check() first, step() the moment each verdict is decided, and exit() at the end. It writes no
// evidence file: vf.py run builds the record from these events.
const fs = require("fs");

const STARTED = Date.now();
let failed = false;

function elapsed() {
  return Math.round((Date.now() - STARTED) / 10) / 100;
}

function emit(event) {
  const line = JSON.stringify(event);
  if (process.env.VERIFY_REPORT) fs.appendFileSync(process.env.VERIFY_REPORT, line + "\n");
  console.error(line);
}

function check(name, subFeatures, reads = "what the user sees") {
  emit({ event: "check", name, sub_features: subFeatures, reads });
}

function step(name, passed, subFeatures, detail, evidence, snapshot) {
  const event = { event: "step", name, passed: Boolean(passed), at: elapsed() };
  if (subFeatures) event.sub_features = subFeatures;
  if (detail !== undefined) event.detail = String(detail);
  if (evidence) event.evidence = evidence;
  if (snapshot) event.snapshot = snapshot;
  emit(event);
  failed = failed || !passed;
  return Boolean(passed);
}

function mark(kind, label) {
  emit({ event: "mark", kind, label, at: elapsed() });
}

function created(kind, ids) {
  emit({ event: "created", [kind]: ids });
}

function recording(video, startsAt) {
  emit({ event: "recording", video, starts_at: startsAt });
}

function stopped(reason) {
  emit({ event: "stopped", reason, at: elapsed() });
  console.error(`STOPPED: ${reason}`);
  process.exit(2);
}

function exit() {
  process.exit(failed ? 1 : 0);
}

module.exports = { check, step, mark, created, recording, stopped, exit, elapsed, failed: () => failed };
