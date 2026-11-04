// ── Trace ──────────────────────────────────────────────
// Change:   `CR-138-BRC07` `P4.7` · `P4.8` · `P4.9` · `P4.11` — screens 7·1
//           Debtors, 7·2 Debtor, 7·3a Ladder and 7·3b Write-offs, and the
//           bulk bar that drops to two plus an overflow.
// Rules:    CLAUDE.md hard-won law 6 (diff the running app against the
//           drawing — no gate in this repo reads rendered output) · B14 rule
//           31 (no database id is ever the visible value of a field, and an
//           ADDRESS BAR is a visible field) · rule 42 (a screen is built from
//           the drawing as an IMAGE, so it is CHECKED against one too) ·
//           rule 16 (a pagination footer on every list) · BR-SHL-025
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS ASKS THAT NO SUITE CAN
// ══════════════════════════════════════════════════════════════════════════
// Three things, and every one of them is invisible to `tsc`, to 48 unit cases
// and to every gate in this repository:
//
//   1. **Does the screen RENDER**, or does a green suite sit over a page that
//      throws on mount? `renderToStaticMarkup` never runs an effect.
//   2. **Is there a uuid on the screen or in the ADDRESS BAR?** `P4.8`'s whole
//      routing decision is B14 rule 31, and the address bar is the most
//      visible field a screen has.
//   3. **Do the five controls the blueprint calls absent actually appear** —
//      search, the filter chips, `▦ Columns`, ⇅ headers and the pagination
//      footer.
//
// ⚠ **IT BOOTS NOTHING, ON PURPOSE.** `11-smoke-stack.sh` boots a stack and
// TEARS IT DOWN on exit, which is right for a smoke run and wrong for looking
// at four screens. Point it at an already-running SPA join:
//
//     cd 06-backend && python3 manage.py runserver 127.0.0.1:8211 --noreload &
//     cd 07-frontend && ./node_modules/.bin/vite build
//     PORT=8212 API_PROXY_TARGET=http://127.0.0.1:8211 node server.mjs &
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers WEB=http://127.0.0.1:8212 \
//       node 10-scripts/cr138_p4_debtor_screens_walkthrough.mjs
//
// ⚠ **"CONTROL MISSING" ON AN EMPTY TENANT IS NOT A FINDING.** `DataTable`
// draws its empty state INSTEAD of the header row and the pager, so a tenant
// with no debtors reports every ⇅ header absent. Read the row count printed
// beside each finding before believing one.
import { mkdirSync, existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// `playwright-core` is BORROWED from `07-frontend`, not imported: a bare
// specifier in an ESM module resolves from the MODULE's directory, never the
// CWD. `12-smoke-walkthrough.mjs` solved this first and this is its solution.
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
  throw new Error("no chromium found — and `playwright install` is forbidden here");
}

const WEB = process.env.WEB || "http://127.0.0.1:8212";
const TENANT = process.env.SMOKE_TENANT || "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/claude-0/lane-p4screens-a/shots";
mkdirSync(OUT, { recursive: true });

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;
const findings = [];
function note(step, what) {
  findings.push(`[${step}] ${what}`);
  console.log(`  · ${step}: ${what}`);
}

/** The five controls B14 asks of every list, checked on the rendered page. */
async function tableControls(page, step) {
  const rows = await page.locator("tbody tr").count();
  note(step, `${rows} row(s) rendered`);
  if (rows === 0) {
    note(step, "EMPTY STATE — the header row and the pager are not drawn, so no control check");
    return;
  }
  // ⚠ **THE FIRST SPELLING OF THESE SELECTORS REPORTED TWO CONTROLS MISSING
  // THAT ARE ON THE SCREEN**, and a photograph is what settled it. `+ Filter`
  // is a `<summary>` inside a `<details>`, not a `<button>`; the column
  // chooser is an ICON with an accessible name and the word *Columns* is
  // nowhere in its markup. **A walkthrough that cannot tell present from
  // absent is worse than none, because it is believed** — so each selector
  // below is the one the component actually renders, taken from its source.
  const checks = {
    "search box (rule 12)": 'input[type="search"], .data-table-toolbar input',
    "All chip (rule 12)": 'button:has-text("All"), summary:has-text("All")',
    "+ Filter (rule 12)": '[data-filter-bar] summary, summary:has-text("Filter")',
    "▦ Columns (rule 14)": `summary[aria-label="Show or hide columns"]`,
    "sortable header (rule 13)": "th button, th [aria-sort]",
    "pagination footer (rule 16)": '.data-table-footer, [class*="pager"], .table-pager',
  };
  for (const [what, selector] of Object.entries(checks)) {
    const seen = await page.locator(selector).count();
    note(step, `${seen > 0 ? "present" : "MISSING"} — ${what}`);
  }
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => note("console", `PAGE ERROR: ${e.message}`));

try {
  console.log("step 1 · sign in");
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 25000 });

  console.log("step 2 · 7·1 Debtors");
  await page.goto(`${WEB}/${TENANT}/payments/outstandings`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/01-debtors-7-1-1440.png`, fullPage: true });
  const tiles = await page.locator(".kpi").count();
  note("7·1", `${tiles} KPI tile(s) — the drawing draws FOUR`);
  const tileLabels = await page.locator(".kpi .k").allTextContents();
  note("7·1", `tile labels: ${JSON.stringify(tileLabels)}`);
  const cards = await page.locator("[data-ageing-cards] button").count();
  note("7·1", `${cards} ageing card(s), each a filter — the drawing draws FIVE`);
  await tableControls(page, "7·1");
  const body71 = (await page.textContent("body")) ?? "";
  if (UUID.test(body71)) note("7·1", "B14 RULE 31 BREACH: something uuid-shaped is on screen");

  console.log("step 3 · the row's door into 7·2 — the door the blueprint says does not exist");
  const firstAccount = await page.locator("tbody tr td a").first().getAttribute("href");
  note("7·1", `the first row's door = ${JSON.stringify(firstAccount)}`);
  if (firstAccount && UUID.test(firstAccount)) {
    note("7·1", "B14 RULE 31 BREACH: the door carries a uuid");
  }

  console.log("step 4 · 7·2 Debtor");
  if (firstAccount) {
    await page.goto(`${WEB}${firstAccount}`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: `${OUT}/02-debtor-7-2-1440.png`, fullPage: true });
    note("7·2", `address bar = ${JSON.stringify(page.url().replace(WEB, ""))}`);
    if (UUID.test(page.url())) note("7·2", "B14 RULE 31 BREACH: a uuid is in the ADDRESS BAR");
    const h1 = await page.textContent("h1").catch(() => null);
    note("7·2", `title reads ${JSON.stringify(h1)}`);
    const kpis = await page.locator(".kpi .k").allTextContents();
    note("7·2", `tiles: ${JSON.stringify(kpis)}`);
    const headings = await page.locator("h3").allTextContents();
    note("7·2", `cards: ${JSON.stringify(headings)}`);
    const body72 = (await page.textContent("body")) ?? "";
    if (UUID.test(body72)) note("7·2", "B14 RULE 31 BREACH: something uuid-shaped is on screen");
    // The door the bulk bar said did not exist for 38 days (DEF-PAY-6253).
    const plan = await page.locator('button:has-text("Offer a plan")').count();
    const planDisabled = plan
      ? await page.locator('button:has-text("Offer a plan")').first().isDisabled()
      : null;
    note("7·2", `Offer a plan: ${plan} control(s), disabled=${planDisabled}`);
  } else {
    note("7·2", "NOT REACHED — no row on 7·1 to open");
  }

  console.log("step 5 · 7·3a the ladder board");
  await page.goto(`${WEB}/${TENANT}/payments/collections`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/03-ladder-7-3a-1440.png`, fullPage: true });
  await tableControls(page, "7·3a");

  console.log("step 6 · 7·3b the write-off queue, on Finance › Revenue & AR");
  // ⚠ THE TAB ID IS `revenue`, NOT `revenue-ar`. The first spelling landed on
  // General ledger and reported the write-off panel absent — a walkthrough at
  // the wrong address, which reads exactly like a missing screen.
  await page.goto(`${WEB}/${TENANT}/finance/revenue`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/04-writeoffs-7-3b-1440.png`, fullPage: true });
  // The panel's heading key is `finance.writeOffs.title`, not the word
  // "Write-off" — the first spelling of this line found nothing and said so,
  // which read as an absent panel rather than as a wrong selector.
  const queueHeading = await page.locator("h3").allTextContents();
  note("7·3b", `panel headings on Revenue & AR: ${JSON.stringify(queueHeading)}`);
  // ⚠ **SCOPED TO THE PANEL, NOT THE PAGE.** Revenue & AR carries ELEVEN
  // panels and a page-wide control count reads another one's toolbar as this
  // one's — which the first run did, reporting five controls missing over a
  // queue whose own toolbar was simply not on screen because the queue is
  // EMPTY on this tenant. An empty `DataTable` draws its empty state INSTEAD
  // of the header row and the pager, so nothing is wrong and nothing is
  // proved; the row count below is what tells the two apart.
  // The PANEL, not the heading's immediate parent — `Panel` wraps its head in
  // a `div` of its own, so `xpath=..` lands on the head and every control in
  // the body reads as absent.
  const panel = page
    .locator('h3:has-text("Write-offs waiting")')
    .locator('xpath=ancestor::*[contains(@class,"panel")][1]');
  const queueRows = await panel.locator("tbody tr").count();
  note("7·3b", `${queueRows} row(s) IN THE QUEUE PANEL`);
  if (queueRows === 0) {
    const empty = await panel.textContent();
    note("7·3b", `empty state reads ${JSON.stringify((empty ?? "").slice(-160))}`);
  } else {
    for (const [what, selector] of [
      ["search box", 'input[type="search"]'],
      ["+ Filter", "summary"],
      ["sortable header", "th button"],
      ["pagination footer", '[class*="pager"], .data-table-footer'],
    ]) {
      const seen = await panel.locator(selector).count();
      note("7·3b", `${seen > 0 ? "present" : "MISSING"} — ${what}`);
    }
  }

  console.log("step 7 · 1280, the laptop minimum — nothing may scroll sideways");
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${WEB}/${TENANT}/payments/outstandings`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1800);
  await page.screenshot({ path: `${OUT}/05-debtors-7-1-1280.png`, fullPage: true });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  note("1280", `horizontal overflow on the PAGE = ${overflow}px (0 is the requirement)`);
} finally {
  console.log("\n── findings ──");
  for (const line of findings) console.log(line);
  console.log(`\nshots in ${OUT}`);
  await browser.close();
}
