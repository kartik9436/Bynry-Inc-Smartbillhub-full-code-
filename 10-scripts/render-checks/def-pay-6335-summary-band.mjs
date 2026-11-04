/**
 * `DEF-PAY-6335` — **THE S32 SUMMARY TAB'S "Figures for" BAND, MEASURED.**
 *
 * PO, walking S32 on 2026-09-23: *"these detailsa re not aligned on ui -
 * Figures for*"*. Three things share one band — the business-day field, the two
 * counters, and the *Mark returned post* button — and they sat on three
 * different baselines, because `.pay-toolbar` is `align-items: flex-end` and the
 * field grew from two lines to FOUR (label · input · help sentence · the IS-8
 * tenant-format echo). Flex-end aligns to the bottom of all four, so the
 * counters and the button floated two lines below the input.
 *
 * ── WHY THIS IS NOT A VITEST FILE, AND IT IS NOT A PREFERENCE ──────────────
 * Every claim here is GEOMETRIC — *is the counter on the input's row*, *is the
 * date printed twice*, *is the band one component*. jsdom computes no layout:
 * `SummaryTab.test.tsx` renders the identical markup and was green through the
 * whole misalignment, and could not have seen it. That is this defect's
 * `escape_reason` in one sentence, and this file is the instrument it asks for.
 *
 * ⚠ **PROVED RED BEFORE IT WAS TRUSTED GREEN, THROUGH THIS SAME ENTRY POINT**
 * (hard-won law 7, both halves — a red proof through a path nobody runs is no
 * proof of the thing that matters). `--before` rewrites the band back to the
 * pre-fix markup IN THE PAGE and re-measures; checks 2, 3 and 4 MUST fail
 * there. Run both modes; a run where `--before` passes means this check cannot
 * fail and is worth less than nothing.
 *
 * ⚠ **AND `--before` REPRODUCES THE LAYOUT, NOT THE PAINTING — WHICH IS WHY IT
 * WAS VALIDATED AGAINST THE REAL UNFIXED BUNDLE RATHER THAN TRUSTED.** It
 * rebuilds `.pay-toolbar > [.field, .pay-chips]` in the page, but this build's
 * `payments.css` no longer declares `.pay-chip`'s box, so the reconstruction is
 * unstyled where the original was a bordered chip. A reconstruction that is
 * *nearly* the old screen is exactly the shape that quietly stops reproducing
 * anything, so the numbers were compared against a measurement taken on the
 * ACTUAL pre-fix bundle at `bbd0b8ec8` before this file was trusted:
 *
 *     real pre-fix bundle   counters mid=314/314, button mid=316, input mid=268, band row 83px
 *     `--before` here       counters mid=316/316, button mid=316, input mid=268, band row 83px
 *
 * Same defect, to within the two pixels the chip's own padding used to add. If
 * a later lane finds `--before` passing, the reconstruction has drifted away
 * from the defect and must be repaired — never deleted, and never "fixed" by
 * loosening the tolerance below.
 *
 * ── RUN (from the REPO ROOT) ──────────────────────────────────────────────
 *   (cd 07-frontend && npx vite build)
 *   (cd 07-frontend && PORT=4329 API_PROXY_TARGET= node server.mjs &)
 *   node 10-scripts/render-checks/def-pay-6335-summary-band.mjs            # after
 *   node 10-scripts/render-checks/def-pay-6335-summary-band.mjs --before   # MUST fail
 *
 * ⚠ **REBUILD THE BUNDLE.** A stale `dist` from another lane looks exactly
 * like a fix that did not work.
 *
 * ⚠ **AND IF `vite build` IS RED ON A FILE YOU DID NOT TOUCH, BUILD IN A
 * PRIVATE WORKTREE RATHER THAN CONCLUDING ANYTHING.** Several lanes share this
 * checkout, so an in-flight sibling file that does not compile yet takes the
 * whole bundle down and with it every render-check in this directory — on
 * 2026-09-23 it was an untracked `RecordPaymentPage.tsx` importing a symbol
 * that does not exist. That is not this screen's defect and it is not a reason
 * to skip the measurement:
 *
 *     git worktree add --detach /tmp/wt "$(git rev-parse origin/<branch>)"
 *     cp <your changed files> /tmp/wt/<same paths>
 *     ln -s "$PWD/07-frontend/node_modules" /tmp/wt/07-frontend/node_modules
 *     (cd /tmp/wt/07-frontend && npx vite build && PORT=4330 API_PROXY_TARGET= node server.mjs &)
 *     SBH_BASE=http://127.0.0.1:4330 SBH_FE=/tmp/wt/07-frontend node 10-scripts/render-checks/def-pay-6335-summary-band.mjs
 *
 * It is also the cleaner measurement: the tip plus your own change, with no
 * sibling's half-finished screen in the bundle.
 *
 * The API is answered by Playwright route interception — no database, no
 * backend. The tenant's `date_format` is `DD-MMM-YY` on purpose: that is what
 * makes the IS-8 echo render at all (`regionalDateEcho` returns null when the
 * browser's own rendering already says the same thing), and it is the tenant
 * the PO was looking at. Exits non-zero on any failed check.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const FE = process.env.SBH_FE ?? path.resolve("07-frontend");
const requireFrontend = createRequire(path.join(FE, "package.json"));
const { chromium } = requireFrontend("playwright-core");

function findChromium() {
  if (process.env.SBH_CHROMIUM) return process.env.SBH_CHROMIUM;
  const wanted = chromium.executablePath();
  if (fs.existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  for (const dir of fs.existsSync(root) ? fs.readdirSync(root) : []) {
    if (!dir.startsWith("chromium")) continue;
    for (const rel of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome"]) {
      const c = path.join(root, dir, rel);
      if (fs.existsSync(c)) return c;
    }
  }
  return wanted;
}

const BASE = process.env.SBH_BASE ?? "http://127.0.0.1:4329";
const TENANT = "brazosbend";
const BEFORE = process.argv.includes("--before");
const AS_OF = "2026-09-23";

// ⚠ `payments_record` IS `PAYMENTS_PERMISSION`'s OWN VALUE (`paymentsShared.tsx`)
// AND NOT A NAME THAT READS RIGHT. A first draft wrote `payments_receipts`, which
// is a plausible A4 cell and is not this screen's: `PaymentsPage` renders
// `PermissionDenied` for it, the band never mounts, and the run dies on a
// 20-second `waitFor` that says nothing about alignment. A fixture that cannot
// reach the screen is law 7's *incapable of passing*.
const PERMISSIONS = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "payments_record", label: "Payments", access: "Full" }],
};

// The tenant the PO was looking at. `DD-MMM-YY` is the whole reason the IS-8
// echo line exists on this screen: the native input renders `09/23/2026` in the
// BROWSER's locale and the tenant's own format is the only thing that line says.
const SHELL_DISPLAY = {
  regional: {
    country: "US",
    timezone: "America/Chicago",
    language: "en",
    first_day_of_week: "sunday",
    currency: "USD",
    number_format: "1,234.56",
    date_format: "DD-MMM-YY",
    time_format: "12h",
  },
  company: {
    legal_name: "Brazos Bend Utilities",
    dba_name: null,
    has_logo: false,
    mark: { kind: "initials", value: "BB" },
    brand_primary_hex: null,
  },
  period: { fy_label: "FY2026", period: 9, start: "2026-09-01", end: "2026-09-30", status: "open" },
};

// US-PAY-005's five panels. The two chip counts are NON-ZERO on purpose: at
// zero the band still renders, and a check that only ever saw zeros would not
// notice a counter that stopped printing its figure.
const SUMMARY = {
  as_of: AS_OF,
  today: { amount: "4101.1000", count: 41, average: "100.0268" },
  method_mix: [
    { method: "cash", method_name: "Cash", amount: "1996.7500", count: 17, share: "48.7" },
    { method: "cheque", method_name: "Cheque", amount: "1284.6000", count: 14, share: "31.3" },
    { method: "card", method_name: "Card", amount: "819.7500", count: 10, share: "20.0" },
  ],
  failed: [],
  collections: { accounts_owing: 27, total_owed: "8480.9400", write_offs_ytd: "0.0000" },
  chips: { autopay_scheduled: 3, returned_mail: 5 },
  problems: [],
};

const calls = [];
function ok(body, status = 200) {
  return { status, contentType: "application/json", body: body === null ? "" : JSON.stringify(body) };
}

function answer(url, method) {
  const u = new URL(url);
  const p = u.pathname;
  calls.push(`${method} ${p}`);
  if (p.endsWith("/shell/display")) return ok(SHELL_DISPLAY);
  if (p.endsWith("/me/permissions")) return ok(PERMISSIONS);
  if (p.endsWith("/me")) {
    return ok({ id: "user-1", full_name: "Dana Whitfield", email: "dana@b.test", tenant: TENANT });
  }
  if (p.endsWith("/payments/summary")) return ok(SUMMARY);
  if (p.includes("/user-preferences/")) return ok({ key: "k", value: null });
  if (p.endsWith("/payments")) {
    return ok({ count: 0, next: null, previous: null, results: [], currency: "USD" });
  }
  return ok({ count: 0, next: null, previous: null, results: [] });
}

const checks = [];
function check(name, pass, detail = "") {
  checks.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

const browser = await chromium.launch({ executablePath: findChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
await page.route("**/api/**", async (route) => {
  const r = route.request();
  await route.fulfill(answer(r.url(), r.method()));
});

await page.goto(`${BASE}/${TENANT}/payments/summary`, { waitUntil: "networkidle" });
await page.locator("#summary_as_of").waitFor({ state: "visible", timeout: 20000 });
await page.waitForTimeout(500);

// ── `--before`: put the PRE-FIX markup back and re-measure ─────────────────
// The band is rebuilt in the page as `.pay-toolbar > [.field, .pay-chips]`,
// which is exactly what SummaryTab rendered at `bbd0b8ec8`, so the three checks
// below are pointed at the geometry the PO reported rather than at a class
// name. If this block ever stops reproducing the defect, the check has become
// a check that cannot fail and must be repaired, not deleted.
if (BEFORE) {
  await page.evaluate(() => {
    const band = document.querySelector("[data-band='summary-figures']");
    if (band === null) throw new Error("--before: no band to rewrite; the fix is not in this bundle");
    const field = band.querySelector(".field");
    const counters = [...band.querySelectorAll("[data-counter]")];
    const button = band.querySelector("button");
    const toolbar = document.createElement("div");
    toolbar.className = "pay-toolbar";
    toolbar.setAttribute("data-band", "summary-figures");
    const chips = document.createElement("div");
    chips.className = "pay-chips";
    for (const c of counters) {
      const chip = document.createElement("span");
      chip.className = "pay-chip";
      chip.setAttribute("data-counter", c.getAttribute("data-counter") ?? "");
      const label = document.createElement("span");
      label.className = "pay-chip-label";
      label.textContent = c.querySelector("[data-counter-label]")?.textContent ?? "";
      const value = document.createElement("span");
      value.className = "pay-chip-value";
      value.setAttribute("data-counter-value", "");
      value.textContent = c.querySelector("[data-counter-value]")?.textContent ?? "";
      chip.append(label, value);
      chips.append(chip);
    }
    if (button !== null) chips.append(button);
    if (field !== null) toolbar.append(field);
    toolbar.append(chips);
    band.replaceWith(toolbar);
  });
  await page.waitForTimeout(200);
}

// ── 1 · The band exists and the wire was actually read ────────────────────
check(
  "the Summary tab read GET /payments/summary (a band over no data proves nothing)",
  calls.some((c) => c.endsWith("/payments/summary")),
  calls.filter((c) => c.includes("payments")).join(" | ") || "no payments call",
);

const band = page.locator("[data-band='summary-figures']").first();
const bandBox = await band.boundingBox();
const input = page.locator("#summary_as_of");
const inputBox = await input.boundingBox();
check(
  "the band and the business-day input are on screen",
  bandBox !== null && inputBox !== null,
  `band=${JSON.stringify(bandBox && round(bandBox))} input=${JSON.stringify(inputBox && round(inputBox))}`,
);

function round(b) {
  return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
}

// ── 2 · THE DEFECT — every counter sits on the INPUT's row ────────────────
// The test is the one the PO applied by eye: does this thing line up with the
// date box, or with whatever happens to be printed under it? Measured as
// vertical-centre against vertical-centre, which is what "on the same row"
// means for boxes of different heights, and tolerant to half a control height.
const ROW_TOLERANCE = 18; // half a 36px control — generous, and still refuses a whole line
const counterBoxes = [];
const counters = page.locator("[data-counter]");
const counterCount = await counters.count();
for (let i = 0; i < counterCount; i++) {
  const value = counters.nth(i).locator("[data-counter-value]").first();
  const b = await value.boundingBox().catch(() => null);
  if (b !== null) counterBoxes.push({ name: (await counters.nth(i).getAttribute("data-counter")) ?? `#${i}`, box: b });
}
check(
  "both counters are rendered with their figures",
  counterBoxes.length === 2,
  `${counterBoxes.length} of 2: ${counterBoxes.map((c) => c.name).join(", ")}`,
);

const inputMid = inputBox === null ? NaN : inputBox.y + inputBox.height / 2;
const offRow = counterBoxes.filter((c) => Math.abs(c.box.y + c.box.height / 2 - inputMid) > ROW_TOLERANCE);
check(
  "every counter's figure sits on the business-day input's ROW, not below the field",
  offRow.length === 0,
  counterBoxes
    .map((c) => `${c.name} mid=${Math.round(c.box.y + c.box.height / 2)}`)
    .concat(`input mid=${Math.round(inputMid)}`)
    .join(" · "),
);

// ── 3 · The action shares that row too ─────────────────────────────────────
const markButton = page.getByRole("button", { name: "Mark returned post" }).first();
const buttonBox = await markButton.boundingBox().catch(() => null);
check(
  "the `Mark returned post` button sits on that same row",
  buttonBox !== null && Math.abs(buttonBox.y + buttonBox.height / 2 - inputMid) <= ROW_TOLERANCE,
  buttonBox === null
    ? "absent"
    : `button mid=${Math.round(buttonBox.y + buttonBox.height / 2)} input mid=${Math.round(inputMid)}`,
);

// ── 4 · The band is ONE control-row tall above its own help lines ─────────
// A band that wrapped is a band that is not aligned, whatever its parts' tops
// say individually. Measured from the band's top to the bottom of the tallest
// thing on the control row.
const rowBottom = Math.max(
  inputBox === null ? 0 : inputBox.y + inputBox.height,
  ...counterBoxes.map((c) => c.box.y + c.box.height),
  buttonBox === null ? 0 : buttonBox.y + buttonBox.height,
);
const rowTop = Math.min(
  inputBox === null ? 1e9 : inputBox.y,
  ...counterBoxes.map((c) => c.box.y),
  buttonBox === null ? 1e9 : buttonBox.y,
);
check(
  "the control row is ONE band — nothing on it starts a second line",
  rowBottom - rowTop <= 48,
  `${Math.round(rowBottom - rowTop)}px from the highest control's top to the lowest one's bottom`,
);

// ── 5 · THE DATE IS PRINTED ONCE AS A VALUE, AND ONCE AS THE TENANT'S ─────
// `23-Sep-26` is NOT a duplicate: it is the IS-8 regional echo
// (`regionalDateEcho`, CR-043 finding 15), and it is the only place a tenant
// whose format differs from the browser's ever sees their own. The rule it
// obeys is *say the tenant's format whenever the control is not already saying
// it* — so what must be true is that the two lines are in DIFFERENT formats
// and that no third copy of the date exists in the band.
const bandText = (await band.innerText()).replace(/\s+/g, " ").trim();
console.log("BAND TEXT:", JSON.stringify(bandText));
const inputValue = await input.inputValue();
check(
  "the input holds the business day as a calendar date",
  inputValue === AS_OF,
  JSON.stringify(inputValue),
);
const echoes = (bandText.match(/23-Sep-26/g) ?? []).length;
check(
  "the tenant's own format (`DD-MMM-YY`) is stated exactly ONCE — the IS-8 echo, not a second copy",
  echoes === 1,
  `${echoes} occurrence(s) of 23-Sep-26`,
);
check(
  "and it is not the same string the control is already showing (`regionalDateEcho` would return null)",
  !bandText.includes("09/23/2026"),
  bandText.includes("09/23/2026") ? "the echo repeats the browser rendering" : "different formats",
);

// The echo is the FIELD's, so it must sit inside the field's own column rather
// than adrift in the band — that is what turns "a bare repeated date" back into
// "this field, in your format".
const echo = page.locator(".field-date-display").first();
const echoBox = await echo.boundingBox().catch(() => null);
check(
  "the format echo sits under the input, inside the field's own column",
  echoBox !== null &&
    inputBox !== null &&
    echoBox.y > inputBox.y &&
    Math.abs(echoBox.x - inputBox.x) < 8 &&
    echoBox.width <= inputBox.width + 8,
  echoBox === null
    ? "absent — the tenant format never reaches the screen"
    : `echo=${JSON.stringify(round(echoBox))} input=${JSON.stringify(inputBox && round(inputBox))}`,
);

// ── 6 · B14 rule 33 — measured, not assumed ───────────────────────────────
const RULE_33 = [
  ["label", "Figures for", 3],
  ["counter label", "Automatic payments", 3],
  ["counter label", "Returned post", 3],
  ["button", "Mark returned post", 3],
];
for (const [kind, text, cap] of RULE_33) {
  const words = text.trim().split(/\s+/).length;
  check(`rule 33 — the ${kind} "${text}" is <= ${cap} words`, words <= cap, `${words} words`);
}
const help = await page.locator("#summary_as_of-help").innerText();
const helpWords = help.replace(/[.]$/, "").trim().split(/\s+/).length;
check(
  "rule 33 — the help sentence is a FACT about the field and measures <= 6 words",
  helpWords <= 6,
  `"${help}" = ${helpWords} words`,
);

// ── 7 · Rule 43 — the band is a COMPONENT, addressable by a sibling ───────
const src = fs.readFileSync(path.join(FE, "src/features/payments/summaryFiguresBar.tsx"), "utf8");
check(
  "rule 43 — the band is its own component file, not markup inside a page",
  /export function SummaryFiguresBar/.test(src),
  "features/payments/summaryFiguresBar.tsx exports SummaryFiguresBar",
);
const tab = fs.readFileSync(path.join(FE, "src/features/payments/SummaryTab.tsx"), "utf8");
check(
  "and SummaryTab mounts it rather than re-implementing it",
  /SummaryFiguresBar/.test(tab) && !/pay-chips/.test(tab),
  /pay-chips/.test(tab) ? "SummaryTab still writes .pay-chips itself" : "mounted",
);

// ── 8 · Rule 21 — the new component adds NO class to a stylesheet ─────────
const ledger = fs.readFileSync(path.join(FE, "src/styles/route-b-migrated.txt"), "utf8");
check(
  "rule 21 — the new component is on the Route B ledger (G31 skips it; routeBUtilities.test.ts owns it)",
  ledger.includes("features/payments/summaryFiguresBar.tsx"),
  "route-b-migrated.txt",
);
const css = fs.readFileSync(path.join(FE, "src/features/payments/payments.css"), "utf8");
check(
  "rule 21 — and payments.css gained no class for it",
  !/summary-figures|figures-bar/.test(css),
  "payments.css",
);

await page.screenshot({
  path: path.join(process.env.SBH_SHOTS ?? path.join(FE, "dist"), `def-pay-6335-${BEFORE ? "before" : "after"}.png`),
  clip: bandBox === null ? undefined : { x: bandBox.x - 8, y: bandBox.y - 8, width: Math.min(1400, bandBox.width + 16), height: bandBox.height + 24 },
});

await browser.close();

const failed = checks.filter((c) => !c.pass);
console.log(`\n${checks.length - failed.length}/${checks.length} checks passed${BEFORE ? "  (--before: checks 2-4 MUST be among the failures)" : ""}`);
if (failed.length > 0) {
  console.log("FAILED:\n  " + failed.map((c) => `${c.name}${c.detail ? ` — ${c.detail}` : ""}`).join("\n  "));
}
process.exit(failed.length === 0 ? 0 : 1);
