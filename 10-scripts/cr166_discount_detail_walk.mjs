// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 round 3 task 6 — the discount DETAILS page, rebuilt
//          from images 19–26 of 05-prototype/discounts-2026-10-03. This walk
//          photographs the BUILT page in the same eight states as its images
//          and puts each beside its image (B14 rules 42 and 44; hard-won law 6
//          — no gate reads rendered output).
// Defect:  DEF-RAT-9291 (D19–D34)
// ───────────────────────────────────────────────────────
//
// Expects:
//   * a scratch PostgreSQL 16 database with `migrate` + `seed_demo` +
//     `load_sample_data --tenant brazosbend` and then
//     `10-scripts/cr166_discount_detail_walk_prep.py` run;
//   * the API — `manage.py runserver 127.0.0.1:<api>`;
//   * the SPA — `vite build --mode wolocal` then
//     `PORT=<spa> API_PROXY_TARGET=http://127.0.0.1:<api> node 07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5193 OUT=08-qa/discounts-2026-10-03/details \
//     node 10-scripts/cr166_discount_detail_walk.mjs
//
// Writes `d19`–`d26` (the built page, full height at 1440 wide) and
// `d19-side`–`d26-side` (drawing left, built right), and prints what each
// state read so a reader can check it without opening a picture.
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5193";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = resolve(process.env.OUT ?? "/tmp/cr166-details");
const IMAGES = resolve(new URL("../05-prototype/discounts-2026-10-03/images", import.meta.url).pathname);
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
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const say = (...parts) => console.log(...parts);
const settle = () => page.waitForTimeout(1200);
const LIST = `${BASE}/${TENANT}/plans-rates/discounts`;

async function shot(name, caption) {
  await settle();
  // The shell scrolls INSIDE `main`, so `fullPage` alone stops at 900px. Grow
  // the window to the page's own height, photograph, and put it back.
  const tall = await page.evaluate(() => {
    const main = document.querySelector("main");
    return Math.max(900, Math.ceil((main?.scrollHeight ?? 0) + (main?.getBoundingClientRect().top ?? 0) + 40));
  });
  await page.setViewportSize({ width: 1440, height: Math.min(tall, 4000) });
  await page.waitForTimeout(400);
  const path = `${OUT}/${name}.png`;
  await page.screenshot({ path, fullPage: true });
  await page.setViewportSize({ width: 1440, height: 900 });
  const bytes = statSync(path).size;
  say(`\n=== ${name}.png — ${caption} (${bytes} bytes)`);
  const text = (await page.innerText("main")).replace(/\n+/g, " / ");
  say("MAIN:", text.slice(0, 1600));
  if (bytes < 20000) say("⚠ SMALL FILE — check it is not blank");
}

async function open(code) {
  await page.goto(`${LIST}?q=${code}`, { waitUntil: "networkidle" });
  await page.getByRole("link", { name: code, exact: true }).first().click();
  await page.waitForURL((u) => /\/plans-rates\/discounts\/[^/]+$/.test(u.pathname), { timeout: 20000 });
  await page.waitForLoadState("networkidle");
  return page.url().split("?")[0];
}

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// 00 · the list (task 5) read against the 2.478.0 shapes — `status` derived,
// `eligibility` an object — so a crash or an `[object Object]` cell shows here.
await page.goto(LIST, { waitUntil: "networkidle" });
await shot("d00-list-on-new-shapes", "List on the 2.478.0 row shapes (task 5's screen)");
say("OBJECT CELLS:", (await page.innerText("main")).includes("[object Object]") ? "PRESENT ⚠" : "none");

// 19–23 · the live discount
const live = await open("AUTOPAY");
await shot("d19-detail-active-overview", "Active · Overview (image 19)");
await page.goto(`${live}?tab=accounts`, { waitUntil: "networkidle" });
await shot("d20-detail-accounts", "Accounts tab (image 20)");
await page.goto(`${live}?tab=plans`, { waitUntil: "networkidle" });
await shot("d21-detail-plans", "Plans tab (image 21)");
await page.goto(`${live}?tab=audit`, { waitUntil: "networkidle" });
await shot("d22-detail-audit", "Audit tab (image 22)");
await page.goto(live, { waitUntil: "networkidle" });
await page.locator("[data-discount-more] summary").click();
await page.waitForTimeout(400);
say("MORE MENU:", JSON.stringify(await page.$$eval("[data-discount-more] button", (els) => els.map((e) => `${e.textContent.trim()}${e.disabled ? " (disabled: " + e.title + ")" : ""}`))));
await shot("d23-detail-active-more", "Active · More ▾ open (image 23)");

// 24–25 · the draft
const draft = await open("MILITARY");
await shot("d24-detail-draft", "Draft · Edit, Submit for approval (image 24)");
await page.goto(`${draft}?tab=accounts`, { waitUntil: "networkidle" });
await shot("d25-detail-accounts-empty", "Draft · Accounts, nobody yet (image 25)");

// 26 · waiting approval
await open("LIFELINE");
await shot("d26-detail-waiting-approval", "Waiting approval · Send back, Approve (image 26)");

// ── side by side: the drawing left, the built page right ───────────────────
const pairs = [
  ["19-detail-active-overview.png", "d19-detail-active-overview"],
  ["20-detail-accounts.png", "d20-detail-accounts"],
  ["21-detail-plans.png", "d21-detail-plans"],
  ["22-detail-audit.png", "d22-detail-audit"],
  ["23-detail-active-more.png", "d23-detail-active-more"],
  ["24-detail-draft.png", "d24-detail-draft"],
  ["25-detail-accounts-empty.png", "d25-detail-accounts-empty"],
  ["26-detail-waiting-approval.png", "d26-detail-waiting-approval"],
];
const sheet = await browser.newPage({ viewport: { width: 2900, height: 960 } });
for (const [drawn, built] of pairs) {
  const a = readFileSync(join(IMAGES, drawn)).toString("base64");
  const b = readFileSync(join(OUT, `${built}.png`)).toString("base64");
  await sheet.setContent(
    `<body style="margin:0;background:#fff;font:14px sans-serif;display:flex;gap:20px;align-items:flex-start">` +
      `<figure style="margin:0"><figcaption>drawing · ${drawn}</figcaption><img width="1440" src="data:image/png;base64,${a}"></figure>` +
      `<figure style="margin:0"><figcaption>built · ${built}.png</figcaption><img width="1440" src="data:image/png;base64,${b}"></figure></body>`,
  );
  await sheet.waitForTimeout(300);
  await sheet.screenshot({ path: `${OUT}/${built.slice(0, 3)}-side.png`, fullPage: true });
  say(`side by side: ${built.slice(0, 3)}-side.png`);
}
await browser.close();
