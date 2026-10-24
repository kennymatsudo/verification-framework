// One wrapper around Playwright for checks that drive the kiosk page. It records the run, keeps the video only when
// the run failed or VERIFY_KEEP_RECORDING=1 is set, saves a screenshot and the visible text for a failed step, and
// writes console output and failed requests, all into the folder VERIFY_RUN_DIR names.
const fs = require("fs");
const path = require("path");
const reporter = require("./reporter");

const RUN_DIR = process.env.VERIFY_RUN_DIR || null;

class Screen {
  async open(url) {
    const { chromium } = require("playwright");
    this.browser = await chromium.launch();
    this.videoDir = RUN_DIR ? path.join(RUN_DIR, "video-tmp") : null;
    this.context = await this.browser.newContext(this.videoDir ? { recordVideo: { dir: this.videoDir, size: { width: 960, height: 720 } } } : {});
    this.page = await this.context.newPage();
    this.startedAt = reporter.elapsed();
    this.console = [];
    this.requests = [];
    this.page.on("console", (m) => this.console.push({ at: reporter.elapsed(), text: `${m.type()}: ${m.text()}` }));
    this.page.on("requestfailed", (r) => this.requests.push({ at: reporter.elapsed(), text: `${r.method()} ${r.url()} ${r.failure() ? r.failure().errorText : ""}` }));
    this.page.on("response", (r) => { if (r.status() >= 400) this.requests.push({ at: reporter.elapsed(), text: `${r.request().method()} ${r.url()} -> ${r.status()}` }); });
    await this.page.goto(url, { waitUntil: "networkidle" });
    return this.page;
  }

  action(label) {
    reporter.mark("action", label);
  }

  beginStep(label) {
    reporter.mark("step", label);
  }

  async snapshot(name) {
    if (!RUN_DIR) return undefined;
    const base = name.replace(/[^a-z0-9]+/gi, "-").toLowerCase();
    await this.page.screenshot({ path: path.join(RUN_DIR, `${base}.png`) });
    fs.writeFileSync(path.join(RUN_DIR, `${base}.txt`), await this.page.innerText("body"));
    return { screenshot: `${base}.png`, text: `${base}.txt` };
  }

  // A step's verdict with a snapshot when it failed; the reporter decides pass or fail from `passed`.
  async step(name, passed, subFeatures, detail, evidence) {
    const snapshot = passed ? undefined : await this.snapshot(name);
    return reporter.step(name, passed, subFeatures, detail, evidence, snapshot);
  }

  async close() {
    const video = this.page ? this.page.video() : null;
    await this.context.close();
    if (RUN_DIR) {
      fs.writeFileSync(path.join(RUN_DIR, "console.json"), JSON.stringify(this.console));
      fs.writeFileSync(path.join(RUN_DIR, "requests.json"), JSON.stringify(this.requests));
    }
    if (video && this.videoDir) {
      const source = await video.path();
      if (reporter.failed() || process.env.VERIFY_KEEP_RECORDING === "1") {
        fs.renameSync(source, path.join(RUN_DIR, "video.webm"));
        reporter.recording("video.webm", this.startedAt);
      }
      fs.rmSync(this.videoDir, { recursive: true, force: true });
    }
    await this.browser.close();
  }
}

module.exports = { Screen };
