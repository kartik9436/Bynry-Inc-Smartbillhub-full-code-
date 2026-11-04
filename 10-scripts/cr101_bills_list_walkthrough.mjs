#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-101-BRC03 lane 01 — blueprint §02 entry 01 "All bills"
//          (`/:tenant/billing` · second address `/:tenant/billing/all` ·
//          S30 · BIL-01), built from the REDESIGN drawn on p007 of
//          `05-prototype/04 Billing, As Built.pdf` (DEFAULT branch
//          `claude/confirm-understanding-3ktufc`, blob sha256 137a2a48…0971),
//          read AS AN IMAGE per B14 rule 42.
// Rules:   PO ruling 2026-09-12 #10 — *"We will need Print bills as tab at
//          Billing level"* · B14 rule 32 (a stated absence is a disclosure
//          CLOSED by default) · B14 rule 33 (rationale is zero words on
//          screen) · B14 rule 16 · A12 (money cells right-aligned)
// Defects: DEF-BIL-5231 (the roll-up served on one tab out of six)
// ───────────────────────────────────────────────────────
/**
 * Drive the bills list in a real browser and ASSERT what step 2 built.
 *
 * ⚠ **THIS EXISTS BECAUSE NOTHING ELSE IN THIS REPO READS RENDERED OUTPUT.**
 * `jsdom` lays nothing out, so the two findings that cost the most here —
 * a column header 35px adrift of its figures, and a header that changes
 * meaning between tabs — are invisible to every suite and every gate. Hard-won
 * law 6.
 *
 * ⚠ **IT EXITS NON-ZERO ON THE FIRST FAILED ASSERTION AND NEVER PRINTS `ok`
 * FROM A `&&`.** A check whose output cannot distinguish pass from fail is
 * worse than no check, because it is trusted.
 *
 * Stack: SPA on 8080, API on 8000 with `API_PROXY_TARGET` set, PostgreSQL up,
 * tenant `brazosbend`. ⚠ Without that proxy target every data call answers 502
 * while pages answer 200, and a walk begun in that state reports every screen
 * broken and every finding is false.
 *
 *   node 10-scripts/cr101_bills_list_walkthrough.mjs [width]     # 1440 | 1280
 */
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(
  new URL("../07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const WIDTH = Number(process.argv[2] ?? 1440);
const BASE = process.env.SPA_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOT_DIR ?? null;

const failures = [];
function check(name, condition, detail) {
  if (condition) {
    console.log(`  PASS  ${name}`);
    return;
  }
  failures.push(`${name} — ${detail}`);
  console.log(`  FAIL  ${name} — ${detail}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const context = await browser.newContext({ viewport: { width: WIDTH, height: 1100 } });
const page = await context.newPage();
const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(String(error).slice(0, 240)));
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

console.log(`CR-101 entry 01 · All bills · ${WIDTH}px · ${BASE}/${TENANT}`);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("#signin-email", { timeout: 60000 });
await page.fill("#signin-email", process.env.WALK_EMAIL ?? "dana@brazosbendutilities.com");
await page.fill("#signin-password", process.env.WALK_PASSWORD ?? "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 1 · the strip is SEVEN, and `Print bills` is last ──────────────────────
await page.goto(`${BASE}/${TENANT}/billing`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const tabs = await page.evaluate(() =>
  [...document.querySelectorAll('[role="tab"]')].map((t) => (t.textContent ?? "").trim()),
);
check("the tab strip is seven wide", tabs.length === 7, `it is ${tabs.length}: ${tabs.join(" · ")}`);
check("`Print bills` is the seventh", tabs[6] === "Print bills", `the seventh is ${JSON.stringify(tabs[6])}`);

// ── 2 · A12 — the TOTAL header sits OVER the money ─────────────────────────
const total = await page.evaluate(() => {
  const table = document.querySelector("table");
  const heads = [...table.querySelectorAll("thead th")];
  const i = heads.findIndex((th) => /TOTAL/i.test(th.innerText || ""));
  if (i < 0) return null;
  const th = heads[i];
  const td = table.querySelector("tbody tr")?.children[i];
  const gap = (cell) => {
    const outer = cell.getBoundingClientRect();
    const inner = (cell.firstElementChild ?? cell).getBoundingClientRect();
    return Math.round(outer.right - inner.right);
  };
  return { header: gap(th), cell: td ? gap(td) : null, align: getComputedStyle(th).textAlign };
});
check(
  "the TOTAL header is right-aligned",
  total !== null && total.align === "right",
  `textAlign is ${total?.align}`,
);
check(
  "the TOTAL header's right edge sits within 2px of the money's",
  total !== null && total.cell !== null && Math.abs(total.header - total.cell) <= 2,
  `header ${total?.header}px vs cell ${total?.cell}px from the right edge`,
);

// ── 3 · B14 rules 32/33 — the past-due note is a CLOSED disclosure below ───
const pastDue = await page.evaluate(() => {
  const d = document.querySelector('details[data-bil="past-due-unknown"]');
  if (!d) return null;
  const table = document.querySelector("table");
  return {
    open: d.open,
    summary: (d.querySelector("summary")?.textContent ?? "").trim(),
    below: !!(table && table.compareDocumentPosition(d) & Node.DOCUMENT_POSITION_FOLLOWING),
    prose: document.querySelector('p[data-bil="past-due-unknown"]') !== null,
  };
});
// It renders only while an issued row really has no past-due answer — derived,
// never declared — so its ABSENCE is a pass on a server that computes past-due.
if (pastDue === null) {
  console.log("  SKIP  past-due disclosure — no issued row lacks a past-due answer here");
} else {
  check("the past-due note is CLOSED by default", pastDue.open === false, "it is open");
  check("…and sits below the table", pastDue.below, "it is above the table");
  check(
    "…with the drawn summary, character for character",
    pastDue.summary === "Why no bill is marked past due",
    `it reads ${JSON.stringify(pastDue.summary)}`,
  );
  check("…and no open prose survives above the table", pastDue.prose === false, "the old <p> is still rendered");
}

// ── 4 · legend 1's other half — the ⓘ on the Status header ─────────────────
const marker = await page.evaluate(() => {
  const th = [...document.querySelectorAll("thead th")].find((e) => /STATUS/i.test(e.innerText || ""));
  const m = th?.querySelector("[data-header-note]");
  return m ? { name: m.getAttribute("aria-label"), icon: m.querySelector("svg") !== null } : null;
});
if (pastDue === null) {
  check("no ⓘ without a disclosure to point at", marker === null, "a marker outlived its footnote");
} else {
  check("an ⓘ marks the Status header", marker !== null && marker.icon, "no marker found");
  check(
    "…and it names the disclosure it points at",
    marker?.name === "Why no bill is marked past due",
    `its accessible name is ${JSON.stringify(marker?.name)}`,
  );
}

// ── 5 · legend 3 — the unresolved count is a door ──────────────────────────
const door = await page.evaluate(() => {
  const a = document.querySelector('a[data-bil="unresolved-door"]');
  return a ? { href: a.getAttribute("href"), text: (a.textContent ?? "").replace(/\s+/g, " ").trim() } : null;
});
check(
  "the unresolved figure links to the pending queue",
  door !== null && door.href === `/${TENANT}/billing/pending`,
  door === null ? "no link rendered" : `it points at ${door.href}`,
);
if (SHOTS) await page.screenshot({ path: join(SHOTS, `list-allbills-${WIDTH}.png`) });

// ── 6 · DEF-BIL-5231 — the header belongs to the SCREEN, not the tab ───────
const headerOn = async (path) => {
  await page.goto(`${BASE}/${TENANT}${path}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  return page.evaluate(() => {
    const s = [...document.querySelectorAll("span")].find((x) => /Bills lifetime/.test(x.textContent || ""));
    return s ? (s.textContent ?? "").replace(/\s+/g, " ").trim() : null;
  });
};
const onAll = await headerOn("/billing");
for (const tab of ["/billing/fix", "/billing/history", "/billing/budget"]) {
  const here = await headerOn(tab);
  check(
    `the roll-up counts the same on ${tab} as on /billing`,
    here === onAll,
    `/billing reads ${JSON.stringify(onAll)} and ${tab} reads ${JSON.stringify(here)}`,
  );
}
check(
  "…and it is a real figure, not the not-counted placeholder",
  onAll !== null && !/Bills lifetimeNot counted yet/.test(onAll),
  `it reads ${JSON.stringify(onAll)} — seed some invoices, or the roll-up is genuinely unserved`,
);

// ── 7 · the seventh tab is a DOOR, and not a one-way one ───────────────────
await page.goto(`${BASE}/${TENANT}/billing`, { waitUntil: "networkidle" });
await page.waitForTimeout(900);
await page.locator('[role="tab"]').nth(6).click();
await page.waitForTimeout(1400);
const landed = await page.evaluate(() => ({
  path: location.pathname,
  h1: document.querySelector("h1")?.textContent?.trim() ?? null,
  strip: document.querySelectorAll('[role="tab"]').length,
  selected:
    [...document.querySelectorAll('[role="tab"]')].find((t) => t.getAttribute("aria-selected") === "true")
      ?.textContent?.trim() ?? null,
}));
check("clicking it lands /billing/print", landed.path === `/${TENANT}/billing/print`, `it landed ${landed.path}`);
check("…on the Print bills screen", landed.h1 === "Print bills", `the title reads ${JSON.stringify(landed.h1)}`);
check("…which still carries the seven-tab strip", landed.strip === 7, `the strip is ${landed.strip} wide`);
check("…with Print bills selected", landed.selected === "Print bills", `${landed.selected} is selected`);
if (SHOTS) await page.screenshot({ path: join(SHOTS, `list-printbills-tab-${WIDTH}.png`) });
await page.locator('[role="tab"]').nth(0).click();
await page.waitForTimeout(1200);
check(
  "…and the way back out works — a tab is not a one-way door",
  new URL(page.url()).pathname === `/${TENANT}/billing`,
  `All bills led to ${new URL(page.url()).pathname}`,
);

// ── 8 · the frame itself ───────────────────────────────────────────────────
const scrolls = await page.evaluate(
  () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
);
check(`no horizontal scroll at ${WIDTH}`, scrolls === false, "the page body scrolls sideways");
check("no page errors", pageErrors.length === 0, pageErrors.join(" | "));

await browser.close();
if (failures.length > 0) {
  console.log(`\nREFUSED: ${failures.length} check(s) failed at ${WIDTH}px`);
  for (const f of failures) console.log(`  · ${f}`);
  process.exit(1);
}
console.log(`\nall checks passed at ${WIDTH}px`);
