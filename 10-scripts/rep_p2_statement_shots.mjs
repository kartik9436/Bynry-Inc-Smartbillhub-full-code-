// ── Trace ──────────────────────────────────────────────
// Change:  **BR-REP-038** (PO ruling 2026-09-27) · `CR-142-BRC07` `P2.8`.
//          *"it should be like bank statement … Build it on the ledger — the
//          account's running record, which holds both sides."*
// Rules:   CLAUDE.md hard-won law 6 (*"diff the running app — no gate looks at
//          rendered output"*) · law 2's mirror (a control the query cannot
//          honour) · B14 rule 31 (no database id is the visible value of a
//          field) · rule 44 (a staff screen is built at 1440 and works at 1280).
// ───────────────────────────────────────────────────────
//
// PHOTOGRAPH WHAT IS THERE. No CSS is injected, no element is hidden, no value
// is substituted. Where a state cannot be reached the script SAYS SO in
// `00-README.txt` rather than skipping it — an absence with no reason beside it
// is indistinguishable from a pass (hard-won law 7's fifth shape).
//
//   node 10-scripts/rep_p2_statement_shots.mjs
//
// Env: SMOKE_BASE (http://127.0.0.1:8090) · SMOKE_TENANT · SMOKE_EMAIL ·
//      SMOKE_PASSWORD · SHOT_OUT · REP_ACCOUNT (the subject id in the URL)
//
// ⚠ **THE ONE THING A SCREENSHOT MUST SHOW HERE IS A PAYMENT.** The whole
// ruling is that a statement holds BOTH sides; a picture of a statement with
// only charges on it is a picture of the defect. So the script counts the rows
// carrying a figure in each money column and prints both numbers beside the
// shot, because a reader cannot count a column from a PNG.
//
// ⚠ **AND IT READS THE KPI LABELS OUT OF THE DOM.** `DEF-REP-6900` is open for
// raw i18n keys reaching a clerk — `cells.basis.as_at` rendered as itself on
// seven reports because nothing compared the codes a server emits against the
// keys the catalogues hold. This lane added four keys, so the script asserts
// no label on screen contains a dot, which is what a fallen-back key looks
// like and what no English word does.

import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8090";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.SHOT_OUT ?? "/tmp/statement-shots";
const EXE = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const ACCOUNT = process.env.REP_ACCOUNT ?? "";

const notes = [];
function note(line) {
  console.log(line);
  notes.push(line);
}

async function shot(page, name, width) {
  await page.setViewportSize({ width, height: 1100 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
  note(`  shot ${name}-${width}.png`);
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: EXE });
  const page = await (await browser.newContext()).newPage();

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2500);
  note(`signed in as ${EMAIL}; landed on ${page.url()}`);

  // ── 1 · the statement with no account named — a stated absence ──────────
  const bare = `${BASE}/${TENANT}/reports/statement`;
  await page.goto(bare, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  note(`opened ${bare}`);
  const version = await page
    .locator("text=/v?2\\.\\d+\\.\\d+/")
    .first()
    .textContent()
    .catch(() => null);
  note(`version on screen: ${version ?? "NOT FOUND — reported rather than assumed"}`);
  note(`NO ACCOUNT: ${await page.locator("table tbody tr").count()} body rows`);
  await shot(page, "01-no-account-named", 1440);

  // ── 2 · the statement itself ────────────────────────────────────────────
  if (!ACCOUNT) {
    note(
      "STOP — REP_ACCOUNT is unset, so there is no subject to open. Nothing " +
        "below was photographed. Take the id from " +
        "10-scripts/rep_p2_statement_pg_proof.py, which prints the busiest account.",
    );
  } else {
    const url = `${BASE}/${TENANT}/reports/statement?subject_id=${ACCOUNT}&f.from=2000-01-01&f.to=2099-12-31`;
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForTimeout(1500);
    note(`opened ${url}`);

    const rows = await page.locator("table tbody tr").count();
    note(`STATEMENT: ${rows} body rows`);

    // ⚠ THE COUNT THAT MATTERS. A picture cannot be read for this.
    const sides = await page.$$eval("table tbody tr", (trs) => {
      let charges = 0;
      let payments = 0;
      for (const tr of trs) {
        const cells = [...tr.querySelectorAll("td")].map((td) => td.textContent.trim());
        // The statement heads charge · payment · running balance last.
        const [charge, payment] = cells.slice(-3);
        if (charge && !/^[—–-]?$/.test(charge) && !/^\$?0\.00$/.test(charge)) charges += 1;
        if (payment && !/^[—–-]?$/.test(payment) && !/^\$?0\.00$/.test(payment)) payments += 1;
      }
      return { charges, payments };
    });
    note(
      `BOTH SIDES: ${sides.charges} row(s) carry a charge · ${sides.payments} row(s) carry a payment` +
        (sides.payments === 0
          ? "  ⚠ FAIL — a statement with no payment on it is the defect BR-REP-038 reversed"
          : "  PASS"),
    );

    const labels = await page.$$eval("[data-kpi], .fin-kpi, [class*='kpi']", (nodes) =>
      nodes.map((n) => n.textContent.trim()).filter(Boolean),
    );
    note(`KPI text: ${JSON.stringify(labels).slice(0, 400)}`);
    const dotted = labels.filter((text) => /\b[a-z_]+\.[a-z_]+\b/.test(text));
    note(
      dotted.length === 0
        ? "I18N: no dotted identifier on screen — every label resolved (DEF-REP-6900's shape)"
        : `I18N ⚠ RAW KEY ON SCREEN: ${JSON.stringify(dotted)}`,
    );

    await shot(page, "02-statement", 1440);
    await shot(page, "02-statement", 1280);

    // ── 3 · a subject the ledger cannot draw — it must REFUSE ─────────────
    const refused = `${url}&subject=premises`;
    await page.goto(refused, { waitUntil: "networkidle" });
    await page.waitForTimeout(1200);
    note(`opened ${refused}`);
    note(`PREMISES SUBJECT: ${await page.locator("table tbody tr").count()} body rows (expected 0)`);
    await shot(page, "03-premises-subject-refuses", 1440);
  }

  writeFileSync(`${OUT}/00-README.txt`, notes.join("\n") + "\n");
  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
