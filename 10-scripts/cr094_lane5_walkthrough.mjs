// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 1 · lane 5 — money on an account, and the request
//          queue. Screens 13 (S23 change plan) · 14 (S24 payment plan) ·
//          15 (S68 account import) · 16 (S83 requests list) · 17 (S84 request
//          detail), drawn at blueprint pages 132–148.
// Rules:   CLAUDE.md hard rule 2 (money STORED 4dp, percentages 6dp, BOTH
//          DISPLAY 2 — PO re-sign 2026-08-22) · hard-won laws 6 (diff the
//          running app; no gate reads rendered output) and 7 (a check must be
//          able to fail) · maintenance process step REPRODUCE.
// ───────────────────────────────────────────────────────
//
// WHY A WALKTHROUGH. Step 1 classifies, and every claim it files is a claim
// about what a clerk SEES. Three of this lane's findings are invisible to the
// whole test suite: a rendered decimal count, a step rail that is declared in
// code and never mounted, and a row action chosen by a status the clerk does
// not read. A `renderToStaticMarkup` case cannot see any of them.
//
// IT MEASURES RATHER THAN DESCRIBES. Every number this lane reports comes back
// from one of the checks below as a string read off the page, never from the
// blueprint's text layer (in which every digit extracts as `&`).
//
// USAGE
//     BASE=http://127.0.0.1:8611 \
//     CHROMIUM_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome \
//     node 10-scripts/cr094_lane5_walkthrough.mjs
//
// ⚠ CHROMIUM_PATH IS NOT OPTIONAL ON THIS IMAGE, AND OMITTING IT LOOKS LIKE A
// CODE FAULT RATHER THAN A MISSING BROWSER. `playwright-core` resolves a build
// number from its own version and asks for
// `/opt/pw-browsers/chromium_headless_shell-1234/...`, which is absent; what IS
// installed is `chromium-1194`. The launch then fails with "Executable doesn't
// exist" and advises `npx playwright install`, which would download a second
// browser rather than use the one already here. Point it at the real binary.
import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8611";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ACCOUNT = process.env.ACCOUNT ?? "01a09540-727d-7b81-a750-49ddd2e237be"; // A-10432, balance 247.300000
const PLAN_ACCOUNT = process.env.PLAN_ACCOUNT ?? "01a09540-62ab-739a-80f8-ca558b2d4f26"; // AC-2026-00011
const REQUEST = process.env.REQUEST ?? "01a09540-793e-7c76-bf8a-b82578af3012"; // SR-26-0006, approved
const OUT = process.env.OUT ?? "/tmp/claude-0/-home-user-SMARTBillHub/9cbb9b39-00da-5925-a69c-c6f1b1985b49/scratchpad/cr094-l5";
mkdirSync(OUT, { recursive: true });

const results = [];
function record(id, what, got) {
  results.push({ id, what, got });
  console.log(`\n[${id}] ${what}\n${got}`);
}

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH ?? undefined,
  args: ["--no-sandbox", "--ignore-certificate-errors"],
});
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
page.on("console", (m) => { if (m.type() === "error") console.log("  console.error:", m.text().slice(0, 200)); });

async function shot(name) { await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true }); }

// ── sign in ───────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill('#signin-email', EMAIL);
await page.fill('#signin-password', PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.includes("signin"), { timeout: 30000 });
record("00", "signed in, landed on", page.url());

// ── 1 · the Record payment modal, and how many decimals it renders ────────
await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}`, { waitUntil: "networkidle" });
const headerBalance = await page.evaluate(() => {
  const hit = [...document.querySelectorAll("*")].find(
    (el) => el.children.length === 0 && /^\$[\d,]+\.\d+$/.test((el.textContent ?? "").trim()),
  );
  return hit ? hit.textContent.trim() : "(no $ figure found in the header)";
});
record("1a", "account header / list — the SAME balance, before the modal is opened", headerBalance);
await shot("1a-account-header");

// open Record payment from the icon rail
const opened = await page.evaluate(() => {
  const btn = [...document.querySelectorAll("button,a")].find((el) =>
    /record payment/i.test(el.getAttribute("aria-label") ?? el.textContent ?? ""),
  );
  if (!btn) return false;
  btn.click();
  return true;
});
record("1b", "Record payment control found on the account", String(opened));
await page.waitForTimeout(1500);
const modal = await page.evaluate(() => {
  const dlg = document.querySelector('[role="dialog"]');
  if (!dlg) return { found: false };
  const amount = dlg.querySelector("#amount");
  const text = (dlg.textContent ?? "").replace(/\s+/g, " ");
  const money = text.match(/[\d,]+\.\d+\s*[A-Z]{3}/g) ?? [];
  return {
    found: true,
    balanceLineMatches: money,
    amountInputValue: amount ? amount.value : "(no #amount input)",
    heading: (dlg.querySelector("h1,h2,h3")?.textContent ?? "").trim(),
  };
});
record(
  "1c",
  "Record payment modal — the balance line and the pre-filled amount, AS RENDERED",
  JSON.stringify(modal, null, 2),
);
await shot("1c-record-payment-modal");

// ── 2 · Change plan wizard — is a step rail rendered? ─────────────────────
await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}/change-plan`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const changePlan = await page.evaluate(() => {
  const body = (document.body.textContent ?? "").replace(/\s+/g, " ");
  return {
    h1: (document.querySelector("h1")?.textContent ?? "").trim(),
    h1PxSize: document.querySelector("h1") ? getComputedStyle(document.querySelector("h1")).fontSize : null,
    sectionHeadings: [...document.querySelectorAll("h2,h3")].map((h) => h.textContent.trim()),
    saysStepOfThree: /Step\s*1\s*of\s*3/i.test(body),
    namesEveryStep: ["Plan", "Effective", "Confirm"].filter((w) => body.includes(w)),
    // ⛔ **`DEF-CUS-5068` — BOTH RAIL DETECTORS HERE WERE INCAPABLE OF
    //    FINDING A RAIL, AND THIS LANE'S CONCLUSION WAS RIGHT ANYWAY.**
    //
    //    `railNodes` read
    //    `[class*=step], [class*=rail], ol[class*=wiz], nav[class*=step]`,
    //    and `components/WizardFrame` carries NO such class: its own docstring
    //    records moving those handles from class names to `data-wizard`
    //    attributes so its stylesheet could go. So the query answered 0 on all
    //    ten wizards that mount the frame, including the nine that always had
    //    a rail — nine free positive controls, none of them used.
    //
    //    And `namesEveryStep` word-boundaried against `document.body
    //    .textContent`, which concatenates without whitespace: the rail reads
    //    **`1Plan2Effective3Confirm`**, where `1Plan` has no boundary between
    //    two word characters. Also always empty.
    //
    //    The step-1 finding was true — `DEF-CUS-5071`, measured a second way
    //    with these very selectors — and it was proved by the other reading.
    //    Left as they were, these two would have told the next lane that
    //    wave D's fix had not landed.
    railNodes: document.querySelectorAll("[data-wizard-step]").length,
    railLabels: [...document.querySelectorAll("[data-wizard-step]")].map((b) => b.textContent.trim()),
    railStates: [...document.querySelectorAll("[data-wizard-step]")].map((b) => b.getAttribute("data-state")),
    continueDisabled: [...document.querySelectorAll("button")]
      .filter((b) => /continue/i.test(b.textContent ?? ""))
      .map((b) => ({ label: b.textContent.trim(), disabled: b.disabled })),
    moneyOnPage: (body.match(/\$[\d,]+\.\d+/g) ?? []).slice(0, 8),
  };
});
record("2a", "Change plan (S23) step 1 — what the running screen actually draws", JSON.stringify(changePlan, null, 2));
await shot("2a-change-plan-step1");

// ── 3 · Payment plan wizard — same question ──────────────────────────────
// ⚠ **`PLAN_ACCOUNT` CARRIES A LIVE PLAN, SO THIS SCREEN DRAWS NO WIZARD** —
// `BR-CUS-043` allows exactly one, and the server answers *"this account
// already has a live payment plan"*. The reading below is therefore of the
// REFUSED screen, which is correct behaviour and not an empty step 1. To read
// the wizard itself, point this at `ACCOUNT` (`A-10432`, which holds none),
// as `10-scripts/cr094_wave_d_walkthrough.mjs` does for exactly this reason.
await page.goto(`${BASE}/${TENANT}/accounts/${PLAN_ACCOUNT}/payment-plan`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const paymentPlan = await page.evaluate(() => {
  const body = (document.body.textContent ?? "").replace(/\s+/g, " ");
  return {
    h1: (document.querySelector("h1")?.textContent ?? "").trim(),
    sectionHeadings: [...document.querySelectorAll("h2,h3")].map((h) => h.textContent.trim()),
    saysStepOfThree: /Step\s*1\s*of\s*3/i.test(body),
    // `DEF-CUS-5068` — plain `includes`, for the reason above: a rail's own
    // text has no whitespace between the number and the word.
    namesEveryStep: ["Terms", "Schedule", "Agreement"].filter((w) => body.includes(w)),
    railNodes: document.querySelectorAll("[data-wizard-step]").length,
    railLabels: [...document.querySelectorAll("[data-wizard-step]")].map((b) => b.textContent.trim()),
    fieldLabels: [...document.querySelectorAll("label")].map((l) => l.textContent.trim()).slice(0, 14),
    moneyOnPage: (body.match(/[\d,]+\.\d{2,}/g) ?? []).slice(0, 10),
  };
});
record("3a", "Payment plan (S24) step 1 — what the running screen actually draws", JSON.stringify(paymentPlan, null, 2));
await shot("3a-payment-plan-step1");

// ── 4 · the Imports tab — which row action a finished run with rejects gets ─
await page.goto(`${BASE}/${TENANT}/accounts?tab=imports`, { waitUntil: "networkidle" });
await page.waitForTimeout(1800);
const imports = await page.evaluate(() => {
  const rows = [...document.querySelectorAll("tbody tr")].map((tr) => {
    const cells = [...tr.querySelectorAll("td")].map((td) => td.textContent.trim());
    const actions = [...tr.querySelectorAll("button,a")].map((b) => ({
      label: (b.getAttribute("aria-label") ?? b.textContent ?? "").trim(),
      disabled: b.disabled === true || b.getAttribute("aria-disabled") === "true",
      title: b.getAttribute("title") ?? b.getAttribute("aria-description") ?? "",
    }));
    return { cells, actions };
  });
  const body = (document.body.textContent ?? "").replace(/\s+/g, " ");
  return {
    kpiStrip: body.match(/RUNS.{0,220}/i)?.[0] ?? "(no KPI strip text)",
    rows,
  };
});
record("4a", "Imports tab — every run row, its figures and the row action it is offered", JSON.stringify(imports, null, 2));
await shot("4a-imports-tab");

// ── 5 · the requests list and one request's detail ───────────────────────
await page.goto(`${BASE}/${TENANT}/requests`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const reqList = await page.evaluate(() => {
  const body = (document.body.textContent ?? "").replace(/\s+/g, " ");
  return {
    h1: (document.querySelector("h1")?.textContent ?? "").trim(),
    columns: [...document.querySelectorAll("thead th")].map((th) => th.textContent.trim()),
    rowCount: document.querySelectorAll("tbody tr").length,
    firstRow: [...(document.querySelector("tbody tr")?.querySelectorAll("td") ?? [])].map((td) => td.textContent.trim()),
    footer: body.match(/Showing[^·]{0,60}|1[–-]\d+ of \d+/)?.[0] ?? "(no footer)",
    moneyOnPage: (body.match(/\$[\d,]+\.\d+/g) ?? []).slice(0, 6),
  };
});
record("5a", "Service requests list (S83) — columns and first row", JSON.stringify(reqList, null, 2));
await shot("5a-requests-list");

await page.goto(`${BASE}/${TENANT}/requests/${REQUEST}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const reqDetail = await page.evaluate(() => {
  const body = (document.body.textContent ?? "").replace(/\s+/g, " ");
  return {
    h1: (document.querySelector("h1")?.textContent ?? "").trim(),
    tabs: [...document.querySelectorAll('[role="tab"], nav a')].map((t) => t.textContent.trim()).slice(0, 14),
    sectionHeadings: [...document.querySelectorAll("h2,h3")].map((h) => h.textContent.trim()),
    moneyOnPage: (body.match(/[\d,]+\.\d{2,}\s*(?:USD)?/g) ?? []).slice(0, 12),
    primaryButtons: [...document.querySelectorAll("button")]
      .map((b) => ({ label: b.textContent.trim(), disabled: b.disabled }))
      .filter((b) => b.label.length > 0)
      .slice(0, 16),
  };
});
record("5b", "Service request detail (S84) — headings, money and its controls", JSON.stringify(reqDetail, null, 2));
await shot("5b-request-detail");

writeFileSync(`${OUT}/measurements.json`, JSON.stringify(results, null, 2));
console.log(`\n\nwrote ${results.length} measurements to ${OUT}/measurements.json and screenshots beside it`);
await browser.close();
