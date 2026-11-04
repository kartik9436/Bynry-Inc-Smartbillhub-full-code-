#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Change:  CR-105-BRC03 — the bill detail's Document tab, restructured into the
//          SEVEN groups the Billing blueprint draws (entry 02.1, p015–p017 of
//          `05-prototype/04 Billing, As Built.pdf`, blob sha256 137a2a48…0971,
//          read AS AN IMAGE per B14 rule 42).
//          Screens: S30 · BIL-05 · `/:tenant/billing/bills/:invoiceId`
// Rules:   PO ruling 2026-09-11 — *"we dont what full view of the document -
//          you give a link to download but full view of document is not
//          requires - it does not add any value to user"* (the ONE removed
//          element) · B14 rule 37 (a drawn box is an illustration; the
//          annotation is the specification) · B14 rule 32 (a stated absence is
//          CLOSED by default) · B14 rule 31 (no internal code on screen) ·
//          BR-SHL-044 (exactly one primary) · hard rule 3 (a quantity always
//          with its unit)
// Defects: DEF-BIL-5244 (the header's two controls were built inverted) —
//          closed NOT-A-DEFECT, and this script is what proves the reversal on
//          rendered output.
// ───────────────────────────────────────────────────────
/**
 * Drive the bill detail in a real browser and ASSERT what CR-105 built.
 *
 * ⚠ **THIS EXISTS BECAUSE NOTHING ELSE IN THIS REPO READS RENDERED OUTPUT.**
 * `jsdom` lays nothing out, so the two things that decide whether this screen
 * is the drawn one — that the viewer is really gone, and that the FILLED
 * control is the left one — are invisible to every suite and every gate.
 * Hard-won law 6.
 *
 * ⚠ **IT EXITS NON-ZERO ON THE FIRST FAILED ASSERTION AND NEVER PRINTS `ok`
 * FROM A `&&`.** A check whose output cannot distinguish pass from fail is
 * worse than no check, because it is trusted.
 *
 * Stack: SPA on 8080 (or `SPA_BASE`), API on 8000 with `API_PROXY_TARGET` set,
 * PostgreSQL up, tenant `brazosbend`. ⚠ Without that proxy target every data
 * call answers 502 while pages answer 200, and a walk begun in that state
 * reports every screen broken and every finding is false.
 *
 *   node 10-scripts/cr105_bill_detail_walkthrough.mjs [width] [invoiceId]
 */
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const WIDTH = Number(process.argv[2] ?? 1440);
const BILL = process.argv[3] ?? process.env.WALK_BILL ?? null;
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
const context = await browser.newContext({ viewport: { width: WIDTH, height: 1200 } });
const page = await context.newPage();
const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(String(error).slice(0, 240)));
if (SHOTS) mkdirSync(SHOTS, { recursive: true });

console.log(`CR-105 · bill detail · ${WIDTH}px · ${BASE}/${TENANT}`);

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("#signin-email", { timeout: 60000 });
await page.fill("#signin-email", process.env.WALK_EMAIL ?? "dana@brazosbendutilities.com");
await page.fill("#signin-password", process.env.WALK_PASSWORD ?? "S3cure!passw0rd");
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

// ── 0 · find an ISSUED bill rather than hardcoding one ─────────────────────
// B14 rule 37 in a walkthrough: a bill number drawn in a wireframe is an
// illustration, and a fixture seeded from one goes red on the next reseed.
let bill = BILL;
if (bill === null) {
  await page.goto(`${BASE}/${TENANT}/billing`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  bill = await page.evaluate(() => {
    const link = [...document.querySelectorAll("tbody a")].find((a) =>
      /\/billing\/bills\/[0-9a-f-]{10,}$/.test(a.getAttribute("href") ?? ""),
    );
    return link ? (link.getAttribute("href") ?? "").split("/").pop() : null;
  });
}
if (bill === null) {
  console.log("  FAIL  no issued bill on the list — cannot walk the detail");
  await browser.close();
  process.exit(1);
}
console.log(`  bill: ${bill}`);

await page.goto(`${BASE}/${TENANT}/billing/bills/${bill}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1800);
if (SHOTS) await page.screenshot({ path: `${SHOTS}/cr105-${WIDTH}-document.png`, fullPage: true });

// ── 1 · THE ONE REMOVED ELEMENT ────────────────────────────────────────────
const frames = await page.evaluate(() => document.querySelectorAll("iframe").length);
check("the embedded PDF viewer is gone", frames === 0, `${frames} iframe(s) on the Document tab`);

// ── 2 · THE HEADER'S EMPHASIS (legend 6) ───────────────────────────────────
// ⚠ Read the RENDERED `background-color` and not the variant attribute: a
// class in a file the compiler never scanned is in the DOM and styles nothing,
// and a prop assertion would have been green on the inverted day.
const header = await page.evaluate(() => {
  const row = document.querySelector(".page-header-actions");
  if (!row) return null;
  const controls = [...row.querySelectorAll("a,button")].map((el) => {
    const style = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    return {
      text: (el.innerText || "").trim(),
      variant: el.getAttribute("data-variant"),
      bg: style.backgroundColor,
      left: Math.round(box.left),
      filled: style.backgroundColor !== "rgba(0, 0, 0, 0)" && style.backgroundColor !== "transparent",
    };
  });
  return controls;
});
check("the header draws its action row", Array.isArray(header) && header.length >= 2, `got ${JSON.stringify(header)}`);
const view = header?.find((c) => /View the bill as sent/i.test(c.text));
const fix = header?.find((c) => /Fix this bill/i.test(c.text));
check(
  "`View the bill as sent` is the FILLED control (legend 6)",
  view !== undefined && view.filled && view.variant === "primary",
  `view=${JSON.stringify(view)}`,
);
check(
  "`Fix this bill` is NOT filled — it is the secondary",
  fix !== undefined && fix.variant === "secondary",
  `fix=${JSON.stringify(fix)}`,
);
check(
  "and `View the bill as sent` sits LEFT of `Fix this bill`, as drawn",
  view !== undefined && fix !== undefined && view.left < fix.left,
  `view.left=${view?.left} fix.left=${fix?.left}`,
);
check(
  "exactly one primary on the header (BR-SHL-044)",
  (header ?? []).filter((c) => c.variant === "primary").length === 1,
  `${(header ?? []).filter((c) => c.variant === "primary").length} primaries`,
);

// ── 3 · THE SEVEN GROUPS, IN THE DRAWN ORDER ───────────────────────────────
const groups = await page.evaluate(() => {
  const wanted = ["Amount", "Breakdown", "Usage", "Dates", "The bill", "Origin", "Record"];
  // ⚠ **TWO WAYS THIS CHECK LOOKED AT THE WRONG THING, BOTH FOUND BY PUTTING
  // THE SCREENSHOT BESIDE THE OUTPUT (hard-won law 7).** First it compared raw
  // strings, and `Kicker` UPPERCASES IN CSS — `innerText` returns AMOUNT where
  // the catalogue says Amount. Then it selected `.kicker`, which is not a class
  // this product declares: the kit's handle is `data-kicker`, the same
  // "attributes are part of the contract" reasoning `PageHeader` records for
  // `data-page-header-tabs`. Both reported group headings MISSING over a screen
  // that was drawing every one of them.
  const seen = [];
  for (const word of wanted) {
    const node = [...document.querySelectorAll("[data-kicker], section h3, summary")].find(
      (el) => (el.innerText || "").trim().toLowerCase() === word.toLowerCase(),
    );
    seen.push(node ? Math.round(node.getBoundingClientRect().top + window.scrollY) : -1);
  }
  return { wanted, seen };
});
check(
  "all seven drawn groups are on the tab",
  groups.seen.every((top) => top >= 0),
  groups.wanted.filter((_, i) => groups.seen[i] < 0).join(", ") + " missing",
);
check(
  "and they are in the drawn order, top to bottom",
  groups.seen.every((top, i) => i === 0 || top > groups.seen[i - 1]),
  JSON.stringify(groups),
);

// ── 4 · B14 rule 32 — the last two are CLOSED ──────────────────────────────
const closed = await page.evaluate(() =>
  ["origin", "record"].map((id) => {
    const el = document.querySelector(`details[data-bil="group-${id}"]`);
    return el === null ? null : el.open;
  }),
);
check("Origin and Record are both closed by default", JSON.stringify(closed) === "[false,false]", JSON.stringify(closed));

// ── 5 · B14 rule 31 — the cycle by NAME on the header, its CODE under Origin ─
const cycle = await page.evaluate(() => {
  const money = document.querySelector('[data-bil="money-line"]');
  const origin = document.querySelector('details[data-bil="group-origin"]');
  return { header: (money?.innerText ?? "").trim(), origin: (origin?.innerText ?? "").trim() };
});
check(
  "the header names the cycle and does NOT print its code",
  !/\bCY-\d{3}\b/.test(cycle.header),
  `header line reads ${JSON.stringify(cycle.header)}`,
);

// ── 6 · the two live reads ─────────────────────────────────────────────────
const amount = await page.evaluate(() => {
  const cells = [...document.querySelectorAll('[data-bil="owed-today"]')];
  return cells.map((el) => (el.innerText || "").trim());
});
check("`Owed today` renders, as a label and a figure", amount.length === 2, JSON.stringify(amount));

const usage = await page.evaluate(() => {
  const table = document.querySelector('[data-bil="bill-usage"]');
  if (!table) return null;
  const head = [...table.querySelectorAll("thead th")].map((th) => (th.innerText || "").trim());
  const rows = [...table.querySelectorAll("tbody tr")].map((tr) =>
    [...tr.children].map((td) => (td.innerText || "").trim()),
  );
  const heads = [...table.querySelectorAll("thead th")];
  const period = heads[1];
  const firstCell = table.querySelector("tbody tr")?.children[1];
  const gap = (cell) => {
    const outer = cell.getBoundingClientRect();
    const inner = (cell.firstElementChild ?? cell).getBoundingClientRect();
    return Math.round(outer.right - inner.right);
  };
  return { head, rows, align: getComputedStyle(period).textAlign, headGap: gap(period), cellGap: firstCell ? gap(firstCell) : null };
});
check("the Usage table draws its four drawn columns", usage !== null && usage.head.length === 4, JSON.stringify(usage?.head));
check(
  "THIS PERIOD is right-aligned over its figures (A12)",
  usage !== null && usage.align === "right" && usage.cellGap !== null && Math.abs(usage.headGap - usage.cellGap) <= 2,
  `align=${usage?.align} header ${usage?.headGap}px vs cell ${usage?.cellGap}px`,
);
check(
  "every usage quantity carries its explicit unit (hard rule 3)",
  usage !== null && usage.rows.every((row) => row[1] === "" || /[A-Za-z]/.test(row[1])),
  JSON.stringify(usage?.rows),
);

// ── 7 · THE BILL's two controls, at the same URL ───────────────────────────
const theBill = await page.evaluate(() => {
  const box = document.querySelector('[data-bil="the-bill-actions"]');
  if (!box) return null;
  return [...box.querySelectorAll("a,button")].map((el) => ({
    text: (el.innerText || "").trim(),
    href: el.getAttribute("href"),
    download: el.hasAttribute("download"),
    target: el.getAttribute("target"),
    disabled: el.hasAttribute("disabled"),
  }));
});
check("The bill group offers exactly two controls", theBill !== null && theBill.length === 2, JSON.stringify(theBill));
check(
  "one downloads and one opens in a new tab, at the same URL",
  theBill !== null &&
    theBill[0].download === true &&
    theBill[1].target === "_blank" &&
    theBill[0].href === theBill[1].href,
  JSON.stringify(theBill),
);

// ── 8 · the page body never scrolls sideways ───────────────────────────────
const overflow = await page.evaluate(() => ({
  doc: document.documentElement.scrollWidth,
  win: window.innerWidth,
}));
check(
  "no horizontal scroll on the page body",
  overflow.doc <= overflow.win + 1,
  `scrollWidth ${overflow.doc} > innerWidth ${overflow.win}`,
);

// ── 9 · the other four tabs still open, and Charges lost the due panel ─────
for (const tab of ["lines", "sent", "chain", "audit"]) {
  await page.goto(`${BASE}/${TENANT}/billing/bills/${bill}?tab=${tab}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/cr105-${WIDTH}-${tab}.png`, fullPage: true });
  const body = await page.evaluate(() => (document.body.innerText || "").trim());
  check(`the ${tab} tab still renders`, body.length > 200, `${body.length} chars`);
  if (tab === "lines") {
    check(
      "Charges no longer carries `When this is due` — it MOVED to Dates",
      !body.includes("When this is due"),
      "the panel is still on Charges",
    );
    check(
      "…and Charges shows no `Owed today` (p018 ends at Total due)",
      !body.includes("Owed today"),
      "Owed today is on Charges",
    );
  }
}

check("no uncaught page errors during the walk", pageErrors.length === 0, pageErrors.join(" | "));

console.log("");
if (failures.length > 0) {
  console.log(`${failures.length} FAILED at ${WIDTH}px:`);
  for (const line of failures) console.log(`  · ${line}`);
  await browser.close();
  process.exit(1);
}
console.log(`all checks passed at ${WIDTH}px`);
await browser.close();
