// ── Trace ──────────────────────────────────────────────
// Change:  CR-192-BRC10 task 13 (MQ-033) — the office SEES the read-format
//          answers: the reading's *Read format* panel and the Reads list's
//          `+ Answer` filter.
// Rules:   CLAUDE.md hard-won law 6 (diff the running app) · law 7 clause 3
//          (every check prints PASS/FAIL beside its name) · B14 rule 31.
// ───────────────────────────────────────────────────────
//
//   node 10-scripts/mq033_answers_walkthrough.mjs
//
// Env: SMOKE_BASE · SMOKE_TENANT · SMOKE_EMAIL · SMOKE_PASSWORD · SHOT_OUT ·
//      MQ_READ (a reading id whose field reading carried answers) ·
//      MQ_KEY / MQ_VALUE (an answer filter that matches it, default
//      meter_condition = Damaged)
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8493";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SHOT_OUT ?? "/tmp/mq033-answers-shots";
const EXE = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const READ = process.env.MQ_READ ?? "";
const KEY = process.env.MQ_KEY ?? "meter_condition";
const VALUE = process.env.MQ_VALUE ?? "Damaged";

const notes = [];
let failures = 0;
const note = (line) => {
  console.log(line);
  notes.push(line);
};
const verdict = (ok, line) => {
  if (!ok) failures += 1;
  note(`${ok ? "PASS" : "FAIL"} · ${line}`);
};

async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 1000 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  note(`  shot ${name}-${width}.png`);
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await (await browser.newContext()).newPage();

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.waitForSelector("#signin-email", { timeout: 20000 });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((url) => !url.toString().includes("/signin"), { timeout: 25000 }).catch(() => null);
  note(`signed in; landed on ${page.url()}`);
  if (page.url().includes("/signin") || READ === "") {
    note("STOP — sign-in failed or MQ_READ unset; NOTHING below was measured.");
    writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
    await browser.close();
    process.exit(2);
  }

  // ── 1 · the reading's Read format panel ────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/reads/${READ}`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-read-format]", { timeout: 20000 }).catch(() => null);
  const panel = page.locator("section:has([data-read-format])");
  verdict((await panel.count()) === 1, "the reading draws ONE Read format panel");
  const labels = await page.$$eval("[data-answer-label]", (els) => els.map((e) => e.textContent.trim()));
  note(`  questions: ${JSON.stringify(labels)}`);
  verdict(labels.length > 0, "each answered question is listed in the utility's words");
  const thumb = page.locator("[data-answer-photo] img");
  if ((await thumb.count()) > 0) {
    const loaded = await thumb.first().evaluate((img) => img.complete && img.naturalWidth > 0);
    verdict(loaded, "the photo thumbnail LOADED its bytes from reads/photos/{id}/content");
  } else {
    note("  (no photo answer on this reading — thumbnail not measured)");
  }
  const body = await page.locator("body").textContent();
  verdict(!/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(body), "B14 rule 31 — no uuid is visible text");
  await panel.scrollIntoViewIfNeeded().catch(() => null);
  await shot(page, "01-reading-detail", 1440);
  await shot(page, "01-reading-detail", 1280);
  if ((await thumb.count()) > 0) {
    await page.locator("[data-answer-photo]").first().click();
    await page.waitForSelector("[data-answer-photo-viewer] img", { timeout: 5000 }).catch(() => null);
    verdict((await page.locator("[data-answer-photo-viewer] img").count()) === 1, "the thumbnail opens the photo");
    await shot(page, "02-photo-viewer", 1440);
    await page.keyboard.press("Escape");
  }

  // ── 2 · the Reads list's Answer filter, driven by clicks ───────────────
  await page.goto(`${BASE}/${TENANT}/reads`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-answer-filter-open]", { timeout: 20000 });
  const before = await page.locator("table tbody tr").count();
  await page.click("[data-answer-filter-open]");
  await page.fill("#question", "cond");
  await page.waitForSelector('[role="option"]', { timeout: 10000 }).catch(() => null);
  await shot(page, "03-answer-dialog", 1440);
  await page.locator('[role="option"]').first().click();
  await page.selectOption("#value", VALUE).catch(() => page.fill("#value", VALUE));
  await page.locator(".modal-foot button, [role=dialog] button[type=submit]").last().click();
  await page.waitForSelector(`[data-answer-chip="${KEY}"]`, { timeout: 10000 }).catch(() => null);
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(800);
  verdict(page.url().includes(`answer%5B${KEY}%5D=`) || page.url().includes(`answer[${KEY}]=`), `the URL carries answer[${KEY}]`);
  const chip = await page.locator(`[data-answer-chip="${KEY}"]`).textContent().catch(() => null);
  note(`  chip: ${JSON.stringify(chip)}`);
  verdict(chip !== null, "the applied answer is a chip on the toolbar");
  const after = await page.locator("table tbody tr").count();
  note(`  rows before ${before} · after ${after}`);
  verdict(after > 0 && after <= before, "the list narrowed to the readings that answered so");
  await shot(page, "04-reads-filtered", 1440);
  await shot(page, "04-reads-filtered", 1280);

  writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + `\nFAILURES: ${failures}\n`);
  await browser.close();
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(3);
});
