// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-4628 — no seeded tenant had ever held an account in the
//          TERMINAL state, so every screen that draws a finished tenancy had
//          never once been looked at against real seeded data.
// Rules:   CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//          output — diff the running app) · hard-won law 7 (a check's output
//          must distinguish pass from fail TO A READER) · the PO's standing
//          definition of done: *"ensure you do web walkthorugh before you sign
//          off the user story or build"*
// ───────────────────────────────────────────────────────
/**
 * OPEN THE ONE CLOSED ACCOUNT AND LOOK AT EVERY TAB.
 *
 *     SMOKE_BASE=http://127.0.0.1:8481 \
 *     node 10-scripts/def_cus_4628_closed_account_walkthrough.mjs
 *
 * ⚠ **THE QUESTION IS NOT "DID THE PAGE LOAD" — IT IS "DOES ANY TAB REFUSE".**
 * A `Closed` account is a state twelve tabs, an icon rail and eight action
 * buttons had never been rendered against, and the way this goes wrong is not
 * a crash: it is one tab that throws, or a header line that comes back blank
 * because it was composed from a field a terminal account does not carry
 * (`DEF-CUS-3653`'s shape). So each tab is opened in turn and three things are
 * counted separately and printed together — page errors, failed API calls, and
 * the app's own error panel — because a number for one without the others is
 * exactly the blind spot law 7 warns about.
 *
 * Screenshots land in `SMOKE_OUT`, one per tab.
 */
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(path.join(HERE, "..", "07-frontend", "package.json"));
const { chromium } = require("playwright");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8481";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const ACCOUNT_NO = process.env.CLOSED_ACCOUNT ?? "AC-2026-00042";
const OUT = process.env.SMOKE_OUT ?? path.join("/tmp", `sbh-closed-${Date.now()}`);
fs.mkdirSync(OUT, { recursive: true });

const TABS = [
  "overview", "bills", "payments", "credits", "plan", "usage",
  "meters", "work", "adjustments", "documents", "notes", "audit",
];

const problems = [];
const note = (m) => console.log(m);
const fail = (m) => { problems.push(m); console.log(`  ✗ ${m}`); };

/** The pinned revision is often absent on this box; an off-revision chromium
 *  beats not running at all, and the substitution is PRINTED (law 7 — a check
 *  whose output cannot distinguish pass from fail is worse than no check).
 *  Same resolution as `12-smoke-walkthrough.mjs`, which is where it was
 *  learned. */
function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && fs.existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    for (const dir of fs.readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = path.join(root, dir, sub);
        if (fs.existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error(`no chromium found: playwright wants ${wanted}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });

let pageErrors = [];
let apiFailures = [];
page.on("pageerror", (e) => pageErrors.push(String(e)));
page.on("response", (r) => {
  const u = r.url();
  if (u.includes("/api/") && r.status() >= 400) apiFailures.push(`${r.status()} ${u.replace(BASE, "")}`);
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.locator("#signin-email").fill(EMAIL);
await page.locator("#signin-password").fill(PASSWORD);
await page.locator("form button[type=submit]").first().click();
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 60000 });
note(`signed in — ${page.url()}`);

// ── 1 · the ACCOUNTS LIST, filtered to the terminal status ────────────────
note("\nS17 Accounts — is the closed row visible in the list?");
await page.goto(`${BASE}/${TENANT}/accounts?q=${ACCOUNT_NO}`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(3500);
const listRow = await page.evaluate((no) => {
  const row = Array.from(document.querySelectorAll("tbody tr")).find((tr) =>
    tr.textContent.includes(no),
  );
  return row ? row.innerText.replace(/\s*\n\s*/g, " · ") : null;
}, ACCOUNT_NO);
if (!listRow) fail(`${ACCOUNT_NO} does not appear in the Accounts list at all`);
else note(`  row: ${listRow}`);
if (listRow && !/closed/i.test(listRow)) fail("the list row does not say Closed");
await page.screenshot({ path: path.join(OUT, "01-accounts-list.png"), fullPage: false });

// ── 2 · open it, and read the header a clerk reads ────────────────────────
const href = await page.evaluate((no) => {
  const row = Array.from(document.querySelectorAll("tbody tr")).find((tr) =>
    tr.textContent.includes(no),
  );
  return row?.querySelector("a")?.getAttribute("href") ?? null;
}, ACCOUNT_NO);
if (!href) { fail("no link out of the list row — cannot open the account"); }
else {
  await page.goto(`${BASE}${href}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3500);
}

const header = await page.evaluate(() => {
  const main = document.querySelector("main") ?? document.body;
  return main.innerText.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 26);
});
note("\nS21 header, as it renders:");
header.forEach((line) => note(`  | ${line}`));
await page.screenshot({ path: path.join(OUT, "02-account-header.png"), fullPage: false });

// A field that comes back as the literal word "undefined", "null" or an empty
// placeholder is DEF-CUS-3653's shape — a line composed from something a
// terminal account does not carry, which no test and no typecheck can see.
const joined = header.join(" ");
for (const ghost of ["undefined", "null", "NaN", "[object Object]", "{{"]) {
  if (joined.includes(ghost)) fail(`the header renders the literal ${ghost}`);
}

// ── 3 · the action buttons and the icon rail, and whether each is honest ──
const controls = await page.evaluate(() => {
  const btns = Array.from(document.querySelectorAll("button, a[role=button]"));
  return btns
    .map((b) => ({
      label: (b.getAttribute("aria-label") || b.innerText || "").trim().replace(/\s+/g, " "),
      disabled: b.hasAttribute("disabled") || b.getAttribute("aria-disabled") === "true",
      title: (b.getAttribute("title") || "").trim().replace(/\s+/g, " ").slice(0, 90),
    }))
    .filter((b) => b.label);
});
note("\nActions on a CLOSED account (disabled ones must SAY WHY):");
for (const c of controls) {
  note(`  ${c.disabled ? "·" : "▸"} ${c.label}${c.disabled ? `  — ${c.title || "NO REASON GIVEN"}` : ""}`);
  if (c.disabled && !c.title) fail(`"${c.label}" is disabled with no reason a clerk can read`);
}

// ── 4 · EVERY TAB ─────────────────────────────────────────────────────────
note("\nEvery tab, in order:");
const url = page.url().split("?")[0];
for (const tab of TABS) {
  pageErrors = [];
  apiFailures = [];
  await page.goto(`${url}?tab=${tab}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2600);
  const body = await page.evaluate(() => {
    const main = document.querySelector("main") ?? document.body;
    const text = main.innerText.replace(/\s+/g, " ").trim();
    const panel = Array.from(document.querySelectorAll('[role="alert"]'))
      .map((n) => n.innerText.replace(/\s+/g, " ").trim())
      .filter(Boolean);
    return { chars: text.length, sample: text.slice(0, 150), alerts: panel };
  });
  await page.screenshot({ path: path.join(OUT, `03-tab-${tab}.png`), fullPage: false });
  const bad = [];
  if (pageErrors.length) bad.push(`${pageErrors.length} page error(s): ${pageErrors[0].slice(0, 120)}`);
  if (apiFailures.length) bad.push(`API ${apiFailures.join(", ").slice(0, 160)}`);
  if (body.alerts.length) bad.push(`alert: ${body.alerts.join(" | ").slice(0, 160)}`);
  if (body.chars < 120) bad.push(`the tab rendered ${body.chars} characters — effectively blank`);
  if (bad.length) fail(`tab ${tab}: ${bad.join("; ")}`);
  else note(`  ✓ ${tab.padEnd(12)} ${body.chars} chars — ${body.sample.slice(0, 90)}`);
}

await browser.close();
note(`\nscreenshots: ${OUT}`);
if (problems.length) {
  note(`\nWALKTHROUGH FOUND ${problems.length} PROBLEM(S):`);
  problems.forEach((p) => note(`  - ${p}`));
  process.exit(1);
}
note("\nWALKTHROUGH CLEAN — the closed account opens and all twelve tabs render.");
