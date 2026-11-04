// ── Trace ──────────────────────────────────────────────
// Defects: DEF-FE-4058 (`billing.budget.filter.` — the budget-bills status
//          filter and every Status pill printed their own dotted key) ·
//          DEF-LED-4638 (`finance.arrives.` — `/finance/revenue` rendered an
//          arrives-with panel headed *General ledger* whose message was the raw
//          key `finance.arrives.gl`, hiding the whole of S36)
// Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//          output — diff the running app) · law 7 (a check's output must
//          distinguish pass from fail TO A READER; and print what you SKIPPED
//          beside what you checked) · B14 rule 32 (no internal code in
//          clerk-facing copy) · PO's definition of done: *"everything should be
//          executed based on actual code … also ensure you do web walkthorugh
//          before you sign off the user story or build"*
// ───────────────────────────────────────────────────────
/**
 * OPEN THE TWO SCREENS IN A REAL BROWSER AND READ THE LINES.
 *
 *     node 10-scripts/render-checks/def-fe-4058-two-raw-keys.mjs
 *
 * ⚠ **IT WALKS TWO ORIGINS AND COMPARES THEM.** `SMOKE_BASE` serves the FIXED
 * build and `SMOKE_BASE_BEFORE`, when set, serves the same commit's parent — so
 * one run produces the before and the after against ONE database, and the
 * difference cannot be an artefact of different data. With no
 * `SMOKE_BASE_BEFORE` it simply checks the after, and says which it did.
 *
 * ⚠ **WHAT IT ASSERTS IS THE ENGLISH LITERAL, NEVER `t(key)`.** A walkthrough
 * that renders the translation on both sides of a comparison can only prove the
 * app agrees with itself, and a raw key satisfies it perfectly — that is how
 * four of the six faults on the Usage tab stayed invisible. The strings below
 * are typed out.
 *
 * ⚠ **AND IT SWEEPS FOR `{{`.** The one fault nobody can see by looking is a
 * placeholder in a label spoken only to a screen reader (`DEF-CUS-4624`). The
 * sweep reads `innerText` AND every `aria-label`/`title`/`alt` on the page.
 *
 * Screenshots land in SMOKE_OUT, one per screen per origin.
 */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
// Resolved from THIS file, never from a typed absolute path (DEF-524: a
// hardcoded path outlived the file it named and reported PASS through six UI
// defects).
const require = createRequire(path.join(HERE, "..", "..", "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

const AFTER = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const BEFORE = process.env.SMOKE_BASE_BEFORE ?? "";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SMOKE_OUT ?? path.join("/tmp", `fe4058-${Date.now()}`);
fs.mkdirSync(OUT, { recursive: true });

const problems = [];
const ok = (m) => console.log("  ✓ " + m);
const bad = (m) => {
  problems.push(m);
  console.log("  ✗ " + m);
};

/** The two screens under test, by ADDRESS — never by a nav click, so a broken
 *  door cannot be mistaken for a broken screen. */
const SCREENS = [
  { id: "finance-revenue", path: `/${TENANT}/finance/revenue`, name: "Finance → Revenue & AR (S36)" },
  { id: "billing-budget", path: `/${TENANT}/billing/budget`, name: "Billing → Budget Bills (S30)" },
];

async function signIn(page, base) {
  await page.goto(`${base}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  // ⚠ NOT `waitForURL`. Sign-in navigates through the router with `pushState`,
  // which fires NO load event, so `waitForURL`'s default `waitUntil: "load"`
  // waits thirty seconds for something that already happened and then throws —
  // over a sign-in that SUCCEEDED. The condition is read in the page instead.
  await page.waitForFunction(() => !location.pathname.endsWith("/signin"), null, {
    timeout: 30000,
  });
  await page.waitForLoadState("networkidle");
}

/** Everything a person or a screen reader receives from this page. */
async function readable(page) {
  return page.evaluate(() => {
    const attrs = [];
    for (const el of document.querySelectorAll("[aria-label],[title],[alt],[placeholder]")) {
      for (const name of ["aria-label", "title", "alt", "placeholder"]) {
        const value = el.getAttribute(name);
        if (value) attrs.push(value);
      }
    }
    const tabs = [...document.querySelectorAll('[role="tab"]')].map((el) => ({
      id: el.getAttribute("data-tab"),
      selected: el.getAttribute("aria-selected"),
      label: (el.textContent || "").trim(),
    }));
    const seg = [...document.querySelectorAll(".seg .seg-opt, .seg button")].map((el) =>
      (el.textContent || "").trim(),
    );
    return { text: document.body.innerText, attrs, tabs, seg, heads: [...document.querySelectorAll("h1,h2,h3")].map((h) => (h.textContent || "").trim()) };
  });
}

/** A raw catalogue key that reached a human. The namespaces are the FIRST
 *  segment of each key in the flat `en.json`, read from disk so this cannot
 *  drift from the catalogue the app shipped with. */
const NAMESPACES = [
  ...new Set(
    Object.keys(
      JSON.parse(
        fs.readFileSync(
          path.join(HERE, "..", "..", "07-frontend", "src", "i18n", "locales", "en.json"),
          "utf8",
        ),
      ),
    ).map((key) => key.split(".")[0]),
  ),
];
const KEY_RE = new RegExp(`\\b(?:${NAMESPACES.join("|")})(?:\\.[A-Za-z0-9_-]+)+`, "g");

function scan(view) {
  const haystack = [view.text, ...view.attrs].join("\n");
  return {
    keys: [...new Set(haystack.match(KEY_RE) ?? [])],
    braces: [...new Set(haystack.match(/\{\{[^}]*\}\}/g) ?? [])],
  };
}

async function walk(base, label) {
  const browser = await chromium.launch({
    executablePath: process.env.SMOKE_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const seen = {};
  try {
    await signIn(page, base);
    for (const screen of SCREENS) {
      await page.goto(`${base}${screen.path}`, { waitUntil: "networkidle" });
      await page.waitForTimeout(900);
      const shot = path.join(OUT, `${label}-${screen.id}.png`);
      await page.screenshot({ path: shot, fullPage: true });
      const view = await readable(page);
      seen[screen.id] = { ...scan(view), view, shot };
    }
  } finally {
    await browser.close();
  }
  return seen;
}

function report(label, seen) {
  console.log(`\n══ ${label} ══`);
  for (const screen of SCREENS) {
    const found = seen[screen.id];
    console.log(`\n  ${screen.name}  —  ${found.shot}`);
    console.log(`    headings : ${JSON.stringify(found.view.heads.slice(0, 4))}`);
    const strip = found.view.tabs.filter((t) => t.id).map((t) => `${t.id}${t.selected === "true" ? "*" : ""}`);
    if (strip.length) console.log(`    tab strip: ${strip.join(" ")}   (* = selected)`);
    if (found.view.seg.length) console.log(`    filter   : ${JSON.stringify(found.view.seg)}`);
    console.log(`    raw keys : ${found.keys.length ? JSON.stringify(found.keys) : "none"}`);
    console.log(`    {{ }}    : ${found.braces.length ? JSON.stringify(found.braces) : "none"}`);
  }
}

const after = await walk(AFTER, "after");
if (BEFORE) report(`BEFORE — ${BEFORE}`, await walk(BEFORE, "before"));
report(`AFTER — ${AFTER}`, after);

console.log("\n══ the assertions ══");
for (const screen of SCREENS) {
  const found = after[screen.id];
  if (found.keys.length === 0) ok(`${screen.name}: no raw catalogue key reaches a human`);
  else bad(`${screen.name}: raw key on screen — ${JSON.stringify(found.keys)}`);
  if (found.braces.length === 0) ok(`${screen.name}: no unfilled {{placeholder}}, text or label`);
  else bad(`${screen.name}: unfilled placeholder — ${JSON.stringify(found.braces)}`);
}

// The English literals, typed out. A translated comparison would pass on a key.
const finance = after["finance-revenue"];
const revenueTab = finance.view.tabs.find((t) => t.id === "revenue");
if (revenueTab && revenueTab.selected === "true") ok("Revenue & AR is the SELECTED tab on its own address");
else bad(`Revenue & AR is not the selected tab — strip reads ${JSON.stringify(finance.view.tabs)}`);
if (!finance.view.heads.includes("General ledger")) ok("S36 no longer announces itself as General ledger");
else bad("S36 still renders the General ledger arrives-with panel");

const budget = after["billing-budget"];
for (const literal of ["On budget billing", "Taken off"]) {
  if (budget.view.seg.includes(literal)) ok(`budget filter reads "${literal}"`);
  else bad(`budget filter is missing "${literal}" — reads ${JSON.stringify(budget.view.seg)}`);
}

// ⚠ SCOPE, PRINTED. This walks TWO screens at ONE role on ONE tenant. Every
// other screen in the product is UNCHECKED by this file — a declared blind spot
// with no number attached is indistinguishable from an empty one (law 7).
console.log(
  `\nscope: ${SCREENS.length} screens · 1 role (${EMAIL}) · tenant ${TENANT} · ` +
    `${BEFORE ? "before+after" : "after only"} · every other screen UNCHECKED here`,
);
console.log(`screenshots: ${OUT}`);
console.log(problems.length ? `\nFAIL — ${problems.length} problem(s)` : "\nPASS — every line reads as a sentence");
process.exit(problems.length ? 1 : 0);
