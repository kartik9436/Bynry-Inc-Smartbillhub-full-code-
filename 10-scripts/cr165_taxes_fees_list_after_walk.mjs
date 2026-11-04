// ── Trace ──────────────────────────────────────────────
// Change:  CR-165-BRC10 round 2 task 5 — the Taxes & fees LIST rebuilt from
//          images 01–03 of 05-prototype/taxes-fees-2026-10-03 (DEF-RAT-9274,
//          P21–P28). This photographs the BUILT list in the three drawn states
//          at 1440 wide and lays each beside its drawing for a side-by-side look.
// ───────────────────────────────────────────────────────
//
// Expects the same stack as `cr165_taxes_fees_before_walk.mjs`:
//   * the API — `manage.py runserver 127.0.0.1:8491` on a scratch PostgreSQL 16
//     database with `migrate` + `seed_demo` run (Brazos Bend, Dana);
//   * the SPA — `vite build --mode wolocal` then
//     `PORT=8492 API_PROXY_TARGET=http://127.0.0.1:8491 node 07-frontend/server.mjs`.
//
//   OUT=08-qa/taxes-fees-2026-10-03/after node 10-scripts/cr165_taxes_fees_list_after_walk.mjs
//
// It stages five taxes shaped like the drawing's rows (two over 20%, one ended,
// one with an end date, one open-ended) through `POST /taxes`, the same door the
// wizard uses, and maps a liability GL account onto each with `PATCH`. Every
// figure is this script's own; the drawing's are illustrations (B14 rule 37).
// Re-running it over its own leftovers creates nothing twice.
import { existsSync, mkdirSync, readdirSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join, resolve } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8492";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = resolve(process.env.OUT ?? "/tmp/cr165-list-after");
const DRAWINGS = resolve(new URL("../05-prototype/taxes-fees-2026-10-03/images", import.meta.url).pathname);
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

async function api(method, path, body) {
  return page.evaluate(
    async ([m, p, b]) => {
      const res = await fetch(`/api/${p}`, {
        method: m,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: b === undefined ? undefined : JSON.stringify(b),
      });
      let data = null;
      try {
        data = await res.json();
      } catch {
        data = null;
      }
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

// ── stage five taxes shaped like the drawing's rows ─────────────────────────
const base = {
  base_includes_usage: true,
  base_includes_base: true,
  premises_scope_kind: null,
  premises_scope_value: "",
  filing_frequency: "monthly",
  discount_treatment: "after",
};
const WANT = [
  { name: "ann arbor City", level: "city", kind: "percent", rate: "1.5", services: ["electric"], classes: [], from: "2026-09-01", to: "2027-11-10" },
  { name: "City of Ottumwa", level: "city", kind: "percent", rate: "1.5", services: ["electric", "water"], classes: ["residential"], from: "2026-09-01", to: null },
  { name: "Bexar County", level: "county", kind: "percent", rate: "0.02", services: [], classes: [], from: "2026-01-01", to: null },
  { name: "TX State Utility Tax", level: "state", kind: "percent", rate: "0.0625", services: [], classes: ["commercial", "industrial"], from: "2026-01-01", to: "2026-12-31" },
  { name: "Storm water fee", level: "city", kind: "flat_per_bill", flat: "1.25", services: ["water"], classes: [], from: "2025-07-01", to: "2026-06-30" },
];
const existing = await api("GET", "taxes?per=200");
const have = new Set((existing.data?.results ?? []).map((row) => row.name));
const accounts = await api("GET", "ledger/accounts");
const liability = (Array.isArray(accounts.data) ? accounts.data : accounts.data?.results ?? []).find((a) =>
  String(a.code).startsWith("2"),
);
for (const want of WANT) {
  if (have.has(want.name)) {
    say("kept", want.name);
    continue;
  }
  const body = {
    ...base,
    name: want.name,
    kind: want.kind,
    applies_to_services: want.services,
    applies_to_customer_classes: want.classes,
    effective_from: want.from,
    effective_to: want.to,
    jurisdiction: { name: want.name, authority: want.name, level: want.level, reference_no: null },
    ...(want.kind === "percent" ? { rate: want.rate } : { flat_amount: want.flat, flat_frequency: "per_bill" }),
  };
  const made = await api("POST", "taxes", body);
  say("create", want.name, made.status, made.status >= 300 ? JSON.stringify(made.data) : "");
  if (made.status < 300 && liability !== undefined) {
    const gl = await api("PATCH", `taxes/${made.data.id}`, { liability_gl_account_id: liability.id });
    say("  gl", liability.code, gl.status);
  }
}

// ── the three drawn states ──────────────────────────────────────────────────
const LIST = `${BASE}/${TENANT}/plans-rates/taxes-fees`;
async function photograph(name, url, drawing, after) {
  await page.goto(url, { waitUntil: "networkidle" });
  if (after) await after();
  await page.waitForTimeout(1200);
  const built = `${OUT}/${name}.png`;
  await page.screenshot({ path: built, fullPage: true });
  say(`\n=== ${name}.png`);
  say((await page.innerText("main")).replace(/\n{2,}/g, "\n").slice(0, 1600));
  // Side by side: the drawing left, the built screen right, one picture.
  const pair = await browser.newPage({ viewport: { width: 2900, height: 900 } });
  const b64 = (file) => readFileSync(file).toString("base64");
  await pair.setContent(
    `<body style="margin:0;display:flex;gap:20px;background:#888">` +
      `<img style="width:1440px" src="data:image/png;base64,${b64(join(DRAWINGS, drawing))}">` +
      `<img style="width:1440px" src="data:image/png;base64,${b64(built)}"></body>`,
  );
  await pair.screenshot({ path: `${OUT}/${name}-side-by-side.png`, fullPage: true });
  await pair.close();
}

await photograph("01-list-all", LIST, "01-list-all.png");
await photograph("02-list-active", `${LIST}?f.status=active`, "02-list-active.png");
await photograph("03-list-no-results", LIST, "03-list-no-results.png", async () => {
  await page.getByPlaceholder("Find a tax or authority").fill("zzz");
  await page.waitForTimeout(1200);
});
await browser.close();
