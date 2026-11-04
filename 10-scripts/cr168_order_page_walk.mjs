// ── Trace ──────────────────────────────────────────────
// Change:  CR-168-BRC10 round 2, lane ORDER-PAGE — PHOTOGRAPH one order in the
//          states images 03–11 draw (05-prototype/work-backoffice-2026-10-04),
//          on PostgreSQL in Chromium at 1440, into 08-qa/work-2026-10-04/after/.
//          Shape copied from `cr168_work_before_walk.mjs`.
// ───────────────────────────────────────────────────────
//
// Reads only, except opening (and dismissing, never committing) the two
// dialogs. Expects the two jobs `10-scripts/cr168_order_page_seed.py` raised:
//
//   BASE=http://127.0.0.1:5451 OUT=08-qa/work-2026-10-04/after \
//     OPEN_NO=WO-0041 DONE_NO=WO-0042 node 10-scripts/cr168_order_page_walk.mjs
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5411";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr168-order-page";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: Number(process.env.VH ?? 2400) } });
const consoleErrors = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
const failed = [];
page.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 400) failed.push(`${r.status()} ${r.request().method()} ${r.url().replace(BASE, "")}`); });
const say = (...parts) => console.log(...parts);
const settle = (ms = 1200) => page.waitForTimeout(ms);
async function shot(name, caption) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  say(`\n=== ${name}.png — ${caption} — ${page.url().replace(BASE, "")}`);
  if (failed.length) { say("API ERRORS:", JSON.stringify(failed.splice(0))); }
}
async function mainText() {
  try { return (await page.innerText("main", { timeout: 3000 })).replace(/\n{2,}/g, "\n"); }
  catch { return (await page.innerText("body")).replace(/\n{2,}/g, "\n"); }
}
async function dialogText() {
  const d = page.locator('[role="dialog"]');
  if (await d.count()) return (await d.first().innerText()).replace(/\n{2,}/g, "\n");
  return "(no dialog)";
}
async function api(method, path, body) {
  return page.evaluate(
    async ([m, p, b]) => {
      const res = await fetch(`/api/${p}`, {
        method: m, credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: b === undefined ? undefined : JSON.stringify(b),
      });
      let data = null;
      try { data = await res.json(); } catch { data = null; }
      return { status: res.status, data };
    },
    [method, `${TENANT}/${path}`, body],
  );
}
// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);


// ⚠ **THE LOCAL DOCUMENT STORE CANNOT SERVE A PICTURE TO A BROWSER**, and
// says so (`FilesystemStorage.temporary_read_url` mints `file://…`, which a page
// on http:// may not load). On S3 the same call mints a presigned https link.
// So, in THIS WALK ONLY, a photograph's link is answered with the file's own
// bytes as a `data:` URL — the server's answer is otherwise untouched, and the
// rewrite is printed so nobody mistakes it for the product's behaviour.
import { readFileSync } from "node:fs";
function inline(url) {
  if (typeof url !== "string" || !url.startsWith("file://")) return url;
  const path = decodeURIComponent(url.slice("file://".length));
  const type = path.endsWith(".png") ? "image/png" : "image/jpeg";
  return `data:${type};base64,${readFileSync(path).toString("base64")}`;
}
await page.route(/\/api\/.*\/work-orders\/[^/]+(\/attachments\/[^/?]+)?(\?.*)?$/, async (route) => {
  const response = await route.fetch();
  let body = await response.text();
  try {
    const data = JSON.parse(body);
    if (data && typeof data.url === "string") data.url = inline(data.url);
    if (data && data.signature && typeof data.signature.image_url === "string") data.signature.image_url = inline(data.signature.image_url);
    body = JSON.stringify(data);
  } catch { /* not JSON — pass through */ }
  await route.fulfill({ response, body });
});
say("WALK SHIM: file:// photograph links are inlined as data: URLs (local store only)");

// ── the two jobs `cr168_order_page_seed.py` raised ───────────────────────────
const OPEN = process.env.OPEN_NO ?? "WO-0041";
const DONE = process.env.DONE_NO ?? "WO-0042";
async function open(orderNo, tab) {
  try { await page.goto(`${BASE}/${TENANT}/work/orders/${orderNo}?tab=${tab}`, { waitUntil: "networkidle", timeout: 30000 }); }
  catch { say("goto timeout", orderNo, tab); }
  await settle(1500);
}
async function heads() {
  return page.$$eval("main table", (ts) => ts.map((t) => Array.from(t.querySelectorAll("thead th")).map((th) => th.textContent.trim()).join(" | ")));
}
async function headButtons() {
  return page.$$eval(".page-header-actions button", (bs) => bs.map((b) => b.textContent.trim()));
}
async function record(name, caption) {
  await shot(name, caption);
  say("HEAD BUTTONS:", JSON.stringify(await headButtons()));
  say("TABLE HEADS:", JSON.stringify(await heads()));
  say(await mainText());
}

await open(OPEN, "overview");
await record("03-order-overview-not-completed", "image 03 — Overview, not completed");
await open(DONE, "overview");
await record("04-order-overview-completed", "image 04 — Overview, completed");
await open(OPEN, "checklist");
await record("05-order-checklist-not-completed", "image 05 — Checklist, the plan");
await open(DONE, "checklist");
await record("06-order-checklist-completed", "image 06 — Checklist, the record");
await open(OPEN, "parts");
await record("07-order-parts", "image 07 — Parts");
await open(OPEN, "audit");
await record("08-order-audit", "image 08 — Audit");
await open(DONE, "checklist");
const thumb = page.locator("[data-photo-thumb]").first();
if (await thumb.count()) {
  await thumb.click();
  await settle(1500);
  await shot("09-order-photo-viewer-completed", "image 09 — the photo viewer");
  say(await dialogText());
  await page.keyboard.press("Escape");
} else say("NO PHOTO THUMB on", DONE);
await open(OPEN, "overview");
await page.locator(".page-header-actions button", { hasText: "Put on hold" }).click();
await settle(1500);
const reasons = await page.$$eval('[role="dialog"] select option', (os) => os.map((o) => o.textContent.trim()));
say("HOLD REASONS OFFERED:", JSON.stringify(reasons));
if (reasons.length > 1) await page.selectOption('[role="dialog"] select', { index: 1 });
await shot("10-order-put-on-hold", "image 10 — Put on hold");
say(await dialogText());
await page.keyboard.press("Escape");
await settle(500);
await page.locator(".page-header-actions button", { hasText: "Cancel order" }).click();
await settle(1000);
await shot("11-order-cancel-order", "image 11 — Cancel order");
say(await dialogText());
await page.keyboard.press("Escape");
say("CONSOLE ERRORS:", JSON.stringify(consoleErrors.slice(0, 20)));
await browser.close();
