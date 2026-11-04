// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 round 2 task 5 — the Discounts LIST, rebuilt from
//          images 01–04 of 05-prototype/discounts-2026-10-03. This walk
//          photographs the BUILT list in the same four states as its images and
//          puts each beside its image, so a person can compare them (B14 rules
//          42 and 44; hard-won law 6 — no gate reads rendered output).
// Defect:  DEF-RAT-9290 (D14–D17)
// ───────────────────────────────────────────────────────
//
// Expects the same stack as `cr166_discounts_before_walk.mjs`:
//   * the API — `manage.py runserver 127.0.0.1:8591` on a scratch PostgreSQL 16
//     database with `migrate` + `seed_demo` + `load_sample_data --tenant
//     brazosbend` run;
//   * the SPA — `vite build --mode wolocal` then
//     `PORT=8592 API_PROXY_TARGET=http://127.0.0.1:8591 node 07-frontend/server.mjs`.
//
//   OUT=08-qa/discounts-2026-10-03/after node 10-scripts/cr166_discounts_list_after_walk.mjs
//
// Writes `a01`–`a04` (the built screen) and `a01-side`–`a04-side` (drawing on
// the left, built screen on the right), and prints what each state read.
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8592";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = resolve(process.env.OUT ?? "/tmp/cr166-list-after");
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
const settle = () => page.waitForTimeout(900);
const LIST = `${BASE}/${TENANT}/plans-rates/discounts`;

async function shot(name, caption) {
  await settle();
  await page.screenshot({ path: `${OUT}/${name}.png` });
  say(`\n=== ${name}.png — ${caption}`);
  say("COLUMNS:", JSON.stringify(await page.$$eval("main th", (ths) => ths.map((th) => th.textContent.trim()))));
  const rows = await page.$$eval("main tbody tr", (trs) =>
    trs.map((tr) => [...tr.querySelectorAll("td")].map((td) => td.innerText.replace(/\s+/g, " ").trim()).join(" | ")),
  );
  for (const row of rows) say("  ROW:", row);
}

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// 01 · All
await page.goto(LIST, { waitUntil: "networkidle" });
await shot("a01-list-all", "List · All (image 01)");
say("PARAGRAPH ABOVE THE TABLE:", (await page.innerText("main")).includes("overlay") ? "PRESENT" : "absent");

// 02 · + Filter open
await page.getByText("+ Filter", { exact: false }).first().click();
await page.waitForTimeout(400);
say("FILTER MENU:", JSON.stringify(await page.$$eval("main details[open] label, main details[open] button", (els) => els.map((e) => e.textContent.trim()))));
await shot("a02-list-filter-menu", "List · + Filter open (image 02)");

// 03 · Status: Active chip
await page.goto(`${LIST}?f.status=active`, { waitUntil: "networkidle" });
await shot("a03-list-filter-chip", "List · Status: Active chip (image 03)");

// 04 · a search with no results
await page.goto(LIST, { waitUntil: "networkidle" });
await page.getByPlaceholder("Search code or name").fill("zzz");
await page.waitForTimeout(1200);
await shot("a04-list-no-results", "List · search with no results (image 04)");
say("MAIN TEXT:", (await page.innerText("main")).replace(/\n+/g, " / ").slice(0, 400));

// ── side by side: the drawing left, the built screen right ─────────────────
const pairs = [
  ["01-list-all.png", "a01-list-all"],
  ["02-list-filter-menu.png", "a02-list-filter-menu"],
  ["03-list-filter-chip.png", "a03-list-filter-chip"],
  ["04-list-no-results.png", "a04-list-no-results"],
];
const sheet = await browser.newPage({ viewport: { width: 2900, height: 960 } });
for (const [drawn, built] of pairs) {
  const a = readFileSync(join(IMAGES, drawn)).toString("base64");
  const b = readFileSync(join(OUT, `${built}.png`)).toString("base64");
  await sheet.setContent(
    `<body style="margin:0;background:#fff;font:14px sans-serif;display:flex;gap:20px">` +
      `<figure style="margin:0"><figcaption>drawing · ${drawn}</figcaption><img width="1440" src="data:image/png;base64,${a}"></figure>` +
      `<figure style="margin:0"><figcaption>built · ${built}.png</figcaption><img width="1440" src="data:image/png;base64,${b}"></figure></body>`,
  );
  await sheet.waitForTimeout(300);
  await sheet.screenshot({ path: `${OUT}/${built.slice(0, 3)}side-${drawn}`, fullPage: true });
  say(`side by side: ${built.slice(0, 3)}side-${drawn}`);
}
await browser.close();
