// ── Trace ──────────────────────────────────────────────
// Task:     Finance blueprint Phase 1, the six tasks that live in PAYMENTS'
//           code — `P1.2` (deposits onto the shared `DataTable`) · `P1.3` (the
//           refund queue's pager and its true total) · `P1.4` / `P1.5` (the
//           chips come from the server) · `P1.7` (`q` on the deposits
//           endpoint) · `P1.14` (the bank import onto `WizardFrame`).
// Defects:  DEF-PAY-6554 · DEF-PAY-6555 · DEF-PAY-6556 · DEF-PAY-6557 ·
//           DEF-PAY-6558
// Drawing:  05-prototype/07 Finance Blueprint.pdf p048–p049 (screen 3·1),
//           p053–p054 (screen 3·3, the import), p040–p041 (the refunds view).
//           Read AS IMAGES (B14 rule 42).
// Rules:    CLAUDE.md hard-won law 6 — *"diff the running app against the
//           drawing: nine defects were found this way and by nothing else"* ·
//           B14 rule 12 (search + chips) · 13 (sortable headers) · 14 (the
//           chooser) · 16 (a pagination footer) · 31 (no database id on screen)
// ───────────────────────────────────────────────────────
//
// ⚠ **IT BOOTS NOTHING, ON PURPOSE** — the smoke stack tears itself down on
// exit, which is right for a smoke run and wrong for looking at a screen. Point
// it at an already-running SPA join:
//
//     cd 06-backend && python3 manage.py runserver 127.0.0.1:8031 --noreload &
//     cd 07-frontend && ./node_modules/.bin/vite build
//     PORT=8032 API_PROXY_TARGET=http://127.0.0.1:8031 node server.mjs &
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers WEB=http://127.0.0.1:8032 \
//       node 10-scripts/fin_p1_payments_screens_walkthrough.mjs
//
// **WHAT IT ASKS, and every question is one no gate in this repo can answer:**
//   1. does 3·1 draw a SEARCH box, `+ Filter`, a COLUMN CHOOSER and a PAGER —
//      the four B14 rules p049's own RULES row says the screen broke;
//   2. does a search reach the SERVER — asserted by the row that must NOT come
//      back, never by the one that must (an endpoint ignoring `q` returns
//      everything, which looks like a hit);
//   3. does the filtered state survive a RELOAD and a paste — `P1.9`'s shape,
//      and the thing p048 note 2 records as *"unlinkable, lost on refresh"*;
//   4. is there a uuid anywhere on the body (rule 31);
//   5. does 3·3 draw a NUMBERED RAIL with two steps, and does a pasted
//      `?step=2` CLAMP back to step 1 — the forward fence, `BR-SHL-018`;
//   6. does the Revenue & AR refunds panel state a TOTAL beside its heading —
//      `P1.3`'s whole answer to *"a page lies about what is pending"*.
//
// ⚠ **AN EMPTY TENANT IS NOT A FINDING.** `DataTable` draws its empty state
// INSTEAD of the header row, so a tenant with no batches reports every column
// missing. The script says which case it is rather than printing a line that
// reads like a defect.
import { mkdirSync, existsSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// `playwright-core` is BORROWED from `07-frontend`, not imported: a bare
// specifier resolves from this module's own directory, never the CWD.
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
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error("no chromium found");
}

const WEB = process.env.WEB || "http://127.0.0.1:8032";
const TENANT = process.env.SMOKE_TENANT || "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/fin-p1-payments";
mkdirSync(OUT, { recursive: true });

const findings = [];
function note(step, what) {
  findings.push(`[${step}] ${what}`);
  console.log(`  · ${step}: ${what}`);
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => note("console", `PAGE ERROR: ${e.message}`));

async function shot(name, width) {
  await page.setViewportSize({ width, height: 1000 });
  await page.waitForTimeout(700);
  await page.screenshot({ path: `${OUT}/${name}-${width}.png`, fullPage: true });
}

try {
  console.log("step 1 · sign in");
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 25000 });

  console.log("step 2 · 3·1 Deposits — the four controls p049 says were missing");
  await page.goto(`${WEB}/${TENANT}/finance/deposits`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  const headers = await page.locator("th").allTextContents();
  note("P1.2", `columns drawn: ${JSON.stringify(headers)}`);
  if (headers.length === 0) {
    note("P1.2", "NO HEADER ROW — this tenant has no deposit batches, so DataTable drew its EMPTY STATE. Not a column defect.");
  }
  // ⚠ The search box is an `<input>` with the list's own prompt (B14 rule 19),
  // NOT a button. A selector naming the wrong element reports an absence
  // indistinguishable from a real one — law 7's *looking at the wrong thing*.
  const searchBox = await page.locator('input[placeholder*="Search batch"]').count();
  note("P1.2", `search box present: ${searchBox > 0}`);
  const filterControl = await page.locator(':text("+ Filter")').count();
  note("P1.2", `+ Filter control present: ${filterControl > 0}`);
  const pager = await page.locator(':text("Rows")').count();
  note("P1.2", `pagination footer present: ${pager > 0}`);
  const body = (await page.textContent("body")) ?? "";
  note("P1.2", UUID.test(body) ? "B14 RULE 31 BREACH: something uuid-shaped is on screen" : "no uuid on the body (rule 31 holds)");
  await shot("01-deposits", 1440);
  await shot("01-deposits", 1280);

  console.log("step 3 · P1.4 — the chips are the server's");
  if (filterControl > 0) {
    await page.locator(':text("+ Filter")').first().click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}/02-filter-panel.png` });
    const panel = (await page.textContent("body")) ?? "";
    for (const word of ["Unmatched", "In transit", "Matched", "Reconciled"]) {
      note("P1.4", `chip "${word}" offered: ${panel.includes(word)}`);
    }
    await page.keyboard.press("Escape");
  }

  console.log("step 4 · P1.7 — the search reaches the SERVER");
  // THE ASSERTION IS THE ROW THAT MUST NOT BE THERE. A term that narrows
  // nothing returns every row, which reads exactly like a hit.
  const beforeRows = await page.locator("tbody tr").count();
  await page.goto(`${WEB}/${TENANT}/finance/deposits?q=ZZZNOSUCHBATCH&sort=deposited_on&dir=desc`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1500);
  const afterRows = await page.locator("tbody tr").count();
  note("P1.7", `rows before search ${beforeRows}, rows for a term that matches nothing ${afterRows}`);
  note("P1.7", afterRows < beforeRows ? "the term reached the query" : "THE TERM CHANGED NOTHING — q is being ignored");
  await page.screenshot({ path: `${OUT}/03-search-no-match.png`, fullPage: true });

  console.log("step 5 · P1.9's shape — the filter survives a reload and travels in a link");
  await page.goto(`${WEB}/${TENANT}/finance/deposits?f.status=in_transit&sort=deposited_on&dir=desc`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1500);
  const filteredRows = await page.locator("tbody tr").count();
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const afterReload = await page.locator("tbody tr").count();
  note("P1.9", `a pasted ?f.status=in_transit drew ${filteredRows} rows, and ${afterReload} after a reload`);
  await shot("04-deposits-filtered", 1440);

  console.log("step 6 · 3·3 the bank import — the numbered rail and its fence");
  await page.goto(`${WEB}/${TENANT}/finance/deposits/import`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  const railSteps = await page.locator('[aria-current="step"], nav li, ol li').allTextContents();
  note("P1.14", `rail reads ${JSON.stringify(railSteps.slice(0, 6))}`);
  const continueBtn = await page.locator('button:has-text("Continue")').count();
  note("P1.14", `a Continue control exists: ${continueBtn > 0}`);
  await shot("05-bank-import", 1440);
  await shot("05-bank-import", 1280);
  // THE FENCE. A pasted step 2 with nothing uploaded must clamp back to 1.
  await page.goto(`${WEB}/${TENANT}/finance/deposits/import?step=2`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const afterPaste = (await page.textContent("body")) ?? "";
  note("P1.14", `?step=2 with nothing uploaded still shows the account picker: ${afterPaste.includes("Bank account")}`);
  await page.screenshot({ path: `${OUT}/06-import-step-fence.png`, fullPage: true });

  console.log("step 7 · P1.3 — the refunds panel states the true total");
  await page.goto(`${WEB}/${TENANT}/finance/revenue`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  const revenue = (await page.textContent("body")) ?? "";
  const waiting = /(\d+)\s+waiting/.exec(revenue);
  note("P1.3", waiting === null ? "no 'N waiting' on the Revenue & AR page (an empty queue draws none by design)" : `the refunds panel states "${waiting[0]}"`);
  await shot("07-revenue-ar", 1440);
} finally {
  writeFileSync(`${OUT}/findings.txt`, findings.join("\n") + "\n");
  console.log(`\n${findings.length} findings → ${OUT}/findings.txt`);
  await browser.close();
}
