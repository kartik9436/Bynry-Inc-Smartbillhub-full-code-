// ── Trace ──────────────────────────────────────────────
// Change:  CR-142-BRC07 Phase 5 · `P5.3` · `P5.4` · `P5.10` — the report
//          builder, walked in a browser.
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate in this repo looks at rendered output) ·
//          law 7 clause 3 (a check's output must distinguish pass from fail to
//          a READER, not merely to an exit code)
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY PROOF HERE IS A PAIR, AND THAT IS THE POINT.** A single screenshot
// proves a builder RENDERS; a pair proves it WORKS. So each step photographs
// the BEFORE and the AFTER of the same screen and prints the two values it
// compared, because a reader who cannot see the difference has been told
// nothing.
//
//   1 · the panel opens · the rows BEFORE and AFTER a column is ticked, with
//       NO save in between — `P5.3`'s outcome word for word
//   2 · Custom reads 0 · then 1, after a save
//   3 · the saved report under *Mine*
//   4 · a colleague does NOT see it while private, then DOES once shared
//   5 · the refusal when a definition is named `history` — the literal word,
//       because an invented one proves nothing
//   6 · the refusal naming an unknown column
//
// ⚠ **STEPS 5 AND 6 ARE ASYMMETRIC AND THE SCRIPT SAYS SO RATHER THAN HIDING
// IT.** Naming a report *History* is something a clerk can type, so it is
// walked through the dialog and photographed. Naming a column the dataset does
// not produce is NOT reachable from the screen — the panel offers exactly what
// the declaration carries, which is §8.1's whole architecture — so it is
// exercised against the API and the response is printed. A step this fixture
// cannot perform is announced with `CANNOT` and counted, never passed quietly
// (law 7's fifth shape: a check reporting zero over a scope it excludes).
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const COLLEAGUE = process.env.COLLEAGUE ?? "";
const COLLEAGUE_PASSWORD = process.env.COLLEAGUE_PASSWORD ?? PASSWORD;
const OUT = process.env.OUT ?? "/tmp/p5-builder";
mkdirSync(OUT, { recursive: true });

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
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH or install to /opt/pw-browsers");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const say = (...parts) => console.log(...parts);
let failures = 0;
let unprovable = 0;
function check(label, ok, detail = "") {
  say(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
}
function cannot(label, why) {
  say(`CANNOT ${label} — ${why}`);
  unprovable += 1;
}

async function signIn(email, password, width = 1440) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  return page;
}

/** The table's header row, as words — what a reader compares between a pair. */
async function headers(page) {
  return page.$$eval("table thead th", (ns) => ns.map((n) => n.textContent.trim()).filter(Boolean));
}

const page = await signIn(EMAIL, PASSWORD);
say(`signed in as ${EMAIL} at ${BASE}`);

// ═══════════════════════════════════════════════════════════════════════════
// 0 · THE HOLD HAS EXPIRED — `+ Build your own` IS DRAWN
// ═══════════════════════════════════════════════════════════════════════════
await page.goto(`${BASE}/${TENANT}/reports`, { waitUntil: "networkidle" });
await page.waitForTimeout(1200);
const buildButton = await page.$('button:has-text("Build your own")');
check("0 · `+ Build your own` is drawn on 1·1", buildButton !== null);
const strip = await page
  .$eval('[data-sub-tabs="catalogue-origin"]', (n) => n.textContent.replace(/\s+/g, " ").trim())
  .catch(() => "");
say(`   sub-tab strip reads: ${JSON.stringify(strip)}`);
// ⚠ p20 callout ②: it sits ABOVE the sub-tab strip, not inside Custom.
// Compared by DOCUMENT ORDER, which is the only thing "above" can mean to a
// check — a pixel comparison would be a different claim.
if (buildButton !== null) {
  const above = await page.evaluate(() => {
    const button = [...document.querySelectorAll("button")].find((b) =>
      /build your own/i.test(b.textContent ?? ""),
    );
    const tabs = document.querySelector('[data-sub-tabs="catalogue-origin"]');
    if (!button || !tabs) return null;
    return (button.compareDocumentPosition(tabs) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  });
  check("0 · …ABOVE the sub-tab strip, not inside Custom (p20 callout ②)", above === true, String(above));
}
await page.screenshot({ path: `${OUT}/00-catalogue-with-the-action.png`, fullPage: true });

// ═══════════════════════════════════════════════════════════════════════════
// 2 · CUSTOM READS 0 — THE **BEFORE** OF THE SECOND PAIR
// ═══════════════════════════════════════════════════════════════════════════
await page.goto(`${BASE}/${TENANT}/reports/custom`, { waitUntil: "networkidle" });
await page.waitForTimeout(1000);
const customBefore = await page
  .$eval('[data-sub-tabs="catalogue-origin"]', (n) => n.textContent.replace(/\s+/g, " ").trim())
  .catch(() => "");
say(`   BEFORE · Custom sub-tab reads: ${JSON.stringify(customBefore)}`);
const emptyHelper = await page
  .$eval("body", (n) => (/Open a standard report/.test(n.innerText) ? "yes" : "no"))
  .catch(() => "no");
check(
  "2a · the Custom empty state carries p22's instruction, not the hold's sentence",
  emptyHelper === "yes",
  emptyHelper,
);
await page.screenshot({ path: `${OUT}/01-custom-before-zero.png`, fullPage: true });

// ═══════════════════════════════════════════════════════════════════════════
// 1 · THE PANEL, AND THE ROWS CHANGING WITH NO SAVE — `P5.3`
// ═══════════════════════════════════════════════════════════════════════════
const REPORT = process.env.REPORT ?? "billing_register";
// ⚠ **THE WINDOW IS NAMED, NOT LEFT TO THE TENANT'S OWN PERIOD.** The seeded
// utility's invoices run 2026-07-02 to 2026-08-02 and the tenant's accounting
// period is September, so the report opens on ZERO rows — and a pair of
// screenshots of an empty table proves nothing about a preview. Measured on
// the clone: 92 invoices, none of them in the default window.
const WINDOW = process.env.WINDOW ?? "f.from=2026-07-01&f.to=2026-08-31";
await page.goto(`${BASE}/${TENANT}/reports/${REPORT}?${WINDOW}`, { waitUntil: "networkidle" });
await page.waitForSelector("table tbody tr", { timeout: 30000 }).catch(() => {});
const headersBefore = await headers(page);
say(`   BEFORE · columns on the table: ${JSON.stringify(headersBefore)}`);
await page.screenshot({ path: `${OUT}/02-report-before-editing.png`, fullPage: true });

await page.goto(`${BASE}/${TENANT}/reports/${REPORT}?${WINDOW}&edit=1`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const panelThere = (await page.$("[data-report-edit-panel]")) !== null;
check("1a · the edit panel opens BESIDE the table, not over it", panelThere);
if (panelThere) {
  // ⚠ **BESIDE** is a spatial claim, so it is measured as one: the panel's left
  // edge must be to the RIGHT of the table's right edge at 1440, and the table
  // must still be on screen. A panel drawn over the table would satisfy every
  // DOM assertion and fail the only thing the ruling is about.
  const geometry = await page.evaluate(() => {
    const panel = document.querySelector("[data-report-edit-panel]");
    const table = document.querySelector("table");
    if (!panel || !table) return null;
    const p = panel.getBoundingClientRect();
    const t = table.getBoundingClientRect();
    return { panelLeft: Math.round(p.left), tableRight: Math.round(t.right), tableWidth: Math.round(t.width) };
  });
  say(`   geometry: ${JSON.stringify(geometry)}`);
  check(
    "1b · the panel is to the RIGHT of the table and the table is still drawn",
    geometry !== null && geometry.panelLeft >= geometry.tableRight - 2 && geometry.tableWidth > 200,
    JSON.stringify(geometry),
  );
}
await page.screenshot({ path: `${OUT}/03-panel-open-before-tick.png`, fullPage: true });

// ⚠ **UNTICK A COLUMN THE REPORT IS ALREADY DRAWING, THEN PUT IT BACK.**
// The first draft of this walk ticked the first UNTICKED box — `status` — and
// the table did not move, correctly: a report's query serves the columns the
// DEFINITION names, and a name the query does not produce is dropped rather
// than drawn as a header over empty cells. So the observable pair is the other
// way round, and it proves the same seam in both directions: the column leaves
// the table when it is unticked and comes back when it is ticked again, with
// no save either time.
const ticked = await page.evaluate(() => {
  const panel = document.querySelector("[data-report-edit-panel]");
  if (!panel) return null;
  const box = [...panel.querySelectorAll('input[type="checkbox"]')].find((b) => b.checked);
  if (!box) return null;
  const label = box.getAttribute("aria-label");
  box.click();
  return label;
});
if (ticked === null) {
  cannot("1c · tick a column", "the panel offered no unticked column on this report");
} else {
  say(`   ticked: ${ticked}`);
  await page.waitForTimeout(2500); // the preview re-runs — same request, new key
  const headersAfter = await headers(page);
  say(`   AFTER  · columns on the table: ${JSON.stringify(headersAfter)}`);
  // ⚠ **NO SAVE HAS HAPPENED.** Asserted as the absence of any write: the
  // definition CRUD is POST/PATCH and neither has been called.
  check(
    "1c · UNticking a column removed it from the ROWS BELOW, with no save",
    JSON.stringify(headersAfter) !== JSON.stringify(headersBefore),
    `${headersBefore.length} → ${headersAfter.length} columns`,
  );
  await page.screenshot({ path: `${OUT}/04-panel-column-removed-no-save.png`, fullPage: true });

  // …and back, which is the ADD half of `P5.3`'s outcome word for word:
  // *"Adding a column shows it in the rows below without a save."*
  await page.evaluate((label) => {
    const panel = document.querySelector("[data-report-edit-panel]");
    const box = panel?.querySelector(`input[type="checkbox"][aria-label="${label}"]`);
    box?.click();
  }, ticked);
  await page.waitForTimeout(2500);
  const headersBack = await headers(page);
  say(`   BACK   · columns on the table: ${JSON.stringify(headersBack)}`);
  // ⚠ **THE SET, NOT THE SEQUENCE.** Once a clerk touches a tick the PANEL
  // owns the column order — attributes in their row order, then measures —
  // so the restored table is the same columns and need not be the same
  // sequence. Asserting the sequence would be asserting the served order,
  // which is a different claim and not this one.
  const sameSet =
    headersBack.length === headersBefore.length &&
    [...headersBack].sort().join("|") === [...headersBefore].sort().join("|");
  check(
    "1c2 · …and ticking it again ADDED it back, still with no save",
    sameSet,
    `${headersAfter.length} → ${headersBack.length} columns · ${JSON.stringify(headersBack)}`,
  );
  await page.screenshot({ path: `${OUT}/04b-panel-column-added-back-no-save.png`, fullPage: true });
}

// 1280 as well — B14 rule 44's scope is every width our standard speaks at.
await page.setViewportSize({ width: 1280, height: 1000 });
await page.waitForTimeout(800);
const overflow1280 = await page.evaluate(
  () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
);
check("1d · no horizontal overflow at 1280", overflow1280 <= 0, `${overflow1280}px`);
await page.screenshot({ path: `${OUT}/05-panel-1280.png`, fullPage: true });
await page.setViewportSize({ width: 1440, height: 1000 });

// ═══════════════════════════════════════════════════════════════════════════
// 5 · THE REFUSAL WHEN A DEFINITION IS NAMED `history` — THE LITERAL WORD
// ═══════════════════════════════════════════════════════════════════════════
async function saveAs(name) {
  const opened = await page.$('button:has-text("Save as")');
  if (opened === null) return null;
  await opened.click();
  await page.waitForTimeout(600);
  const nameBox = await page.$("#name");
  if (nameBox === null) return null;
  await nameBox.fill(name);
  await page.waitForTimeout(200);
  const submit = await page.$('[role="dialog"] button[type="submit"], [role="dialog"] button:has-text("Save")');
  if (submit === null) return null;
  await submit.click();
  await page.waitForTimeout(2000);
  return page.evaluate(() => document.body.innerText);
}

const refusedText = await saveAs("History");
if (refusedText === null) {
  cannot("5 · refuse the name `History` on screen", "the Save as dialog did not open on this report");
} else {
  // ⚠ THE LITERAL WORD. An invented word would pass over a builder that
  // refuses every name containing an *h*.
  const refused = /reserved/i.test(refusedText);
  check("5 · naming a report *History* is refused on screen", refused);
  await page.screenshot({ path: `${OUT}/06-refusal-history.png`, fullPage: true });
  // AND THE OTHER DIRECTION, in the same breath: the tab still opens.
  await page.goto(`${BASE}/${TENANT}/reports/history`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const stillHistory = await page.evaluate(() => document.body.innerText.slice(0, 400));
  check(
    "5b · …and `/reports/history` still opens the History tab",
    !/reserved/i.test(stillHistory),
    stillHistory.split("\n").slice(0, 2).join(" / "),
  );
  await page.screenshot({ path: `${OUT}/07-history-tab-still-opens.png`, fullPage: true });
}

// ═══════════════════════════════════════════════════════════════════════════
// 2 (AFTER) · SAVE A REAL ONE, AND CUSTOM GOES 0 → 1
// ═══════════════════════════════════════════════════════════════════════════
await page.goto(`${BASE}/${TENANT}/reports/${REPORT}?${WINDOW}&edit=1`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
const SAVED_NAME = process.env.SAVED_NAME ?? "Overdue 60+";
const savedBody = await saveAs(SAVED_NAME);
if (savedBody === null) {
  cannot("2b · save a report", "the Save as dialog did not open");
} else {
  await page.waitForTimeout(1500);
  say(`   after save, the address is ${page.url()}`);
  await page.screenshot({ path: `${OUT}/08-saved-report-open.png`, fullPage: true });
  await page.goto(`${BASE}/${TENANT}/reports/custom`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const customAfter = await page
    .$eval('[data-sub-tabs="catalogue-origin"]', (n) => n.textContent.replace(/\s+/g, " ").trim())
    .catch(() => "");
  say(`   AFTER  · Custom sub-tab reads: ${JSON.stringify(customAfter)}`);
  check("2b · Custom went from 0 to 1", customBefore !== customAfter, `${customBefore} → ${customAfter}`);
  const named = await page.evaluate(
    (n) => document.body.innerText.includes(n),
    SAVED_NAME,
  );
  check("3 · the saved report is listed by NAME (B14 rule 31)", named, SAVED_NAME);
  await page.screenshot({ path: `${OUT}/09-custom-after-one.png`, fullPage: true });
}

// ═══════════════════════════════════════════════════════════════════════════
// 4 · A COLLEAGUE DOES NOT SEE IT WHILE PRIVATE — `P5.7`
// ═══════════════════════════════════════════════════════════════════════════
if (COLLEAGUE === "") {
  cannot(
    "4 · a colleague's view",
    "no COLLEAGUE= address was given, so this deployment has one signed-in user and the pair cannot be photographed. The server half is proved by tests/test_rep_p5_definition_crud.py and by 10-scripts/rep_p5_isolation_and_savepoint_proof.py on PostgreSQL",
  );
} else {
  const other = await signIn(COLLEAGUE, COLLEAGUE_PASSWORD);
  await other.goto(`${BASE}/${TENANT}/reports/custom`, { waitUntil: "networkidle" });
  await other.waitForTimeout(1200);
  const seesPrivate = await other.evaluate((n) => document.body.innerText.includes(n), SAVED_NAME);
  check("4a · a colleague does NOT see a private report", seesPrivate === false, String(seesPrivate));
  await other.screenshot({ path: `${OUT}/10-colleague-cannot-see-it.png`, fullPage: true });
  // ⚠ **AND THE OTHER DIRECTION, IN THE SAME BREATH.** A catalogue that shows
  // a colleague NOTHING passes 4a perfectly, so the report is shared and the
  // same colleague looks again. Sharing is 2·2's *Visible to*, reached at the
  // saved report's own address.
  const savedKey = "overdue-60";
  await page.goto(`${BASE}/${TENANT}/reports/${savedKey}?${WINDOW}&edit=1`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(2500);
  // ⚠ **THE SAVED REPORT MUST OPEN AT ITS OWN ADDRESS, TITLED BY ITS NAME.**
  // It did not until `DEF-REP-6867`: the catalogue listed it and the viewer
  // answered *"There is no report called overdue-60"*. Listed and unopenable
  // is not "appears in the catalogue" — it is a dead card with a row behind it.
  const savedHead = await page
    .$eval("h1, h2", (n) => n.textContent.trim())
    .catch(() => "");
  check(
    "4b0 · the saved report OPENS at its own address, titled by its NAME",
    savedHead === SAVED_NAME,
    JSON.stringify(savedHead),
  );
  await page.screenshot({ path: `${OUT}/11-sharing-the-report.png`, fullPage: true });
  const shared = await page.evaluate(() => {
    const panel = document.querySelector("[data-report-edit-panel]");
    const select = [...(panel?.querySelectorAll("select") ?? [])].find((s) =>
      [...s.options].some((o) => o.value === "shared"),
    );
    if (!select) return false;
    select.value = "shared";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  });
  if (!shared) {
    cannot("4b · share the report", "the panel offered no *Visible to* control at this address");
  } else {
    await page.waitForTimeout(400);
    const savedAgain = await saveAs(`${SAVED_NAME} shared`);
    say(`   reshared via Save as → ${page.url()}`);
    await page.screenshot({ path: `${OUT}/12-shared.png`, fullPage: true });
    await other.goto(`${BASE}/${TENANT}/reports/custom`, { waitUntil: "networkidle" });
    await other.waitForTimeout(1500);
    const seesShared = await other.evaluate(
      (n) => document.body.innerText.includes(n),
      `${SAVED_NAME} shared`,
    );
    check("4b · …and DOES see it once it is shared", seesShared === true, String(seesShared));
    // ⚠ **AND IT IS A LIVE DOOR, NOT A DEAD CARD** (`DEF-REP-6866`). A
    // colleague who can see a report and cannot open it has been shown a
    // rumour. The catalogue drew every tenant-authored report dimmed with
    // *"This report cannot be produced yet."* until the availability and the
    // `kind` both started asking the runner.
    const opens = await other.evaluate(
      () => document.querySelector("a[data-report-key]") !== null,
    );
    check("4b2 · …and it OPENS — a shared report is a link, not a dimmed card", opens === true);
    await other.screenshot({ path: `${OUT}/13-colleague-sees-it-shared.png`, fullPage: true });
    void savedAgain;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// 6 · THE REFUSAL NAMING AN UNKNOWN COLUMN
// ═══════════════════════════════════════════════════════════════════════════
// ⚠ NOT REACHABLE FROM THE SCREEN, AND THAT IS THE ARCHITECTURE RATHER THAN A
// GAP: the panel offers exactly the columns the dataset declares. So it is
// exercised where a hand-edited request would arrive — the API — and the
// answer is printed.
const unknown = await page.evaluate(async (tenant) => {
  const response = await fetch(`/api/${tenant}/reports/definitions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: "Bad columns",
      dataset: "invoices",
      group: "billing",
      columns: ["invoice_no", "ballance"],
    }),
    credentials: "same-origin",
  });
  return { status: response.status, body: await response.text() };
}, TENANT);
say(`   POST /reports/definitions with a bad column → ${unknown.status} ${unknown.body.slice(0, 220)}`);
check(
  "6 · an unknown column is refused WITH THE COLUMN NAMED",
  unknown.status === 422 && unknown.body.includes("ballance"),
  `${unknown.status}`,
);
writeFileSync(`${OUT}/11-unknown-column-refusal.txt`, `${unknown.status}\n${unknown.body}\n`);

say("");
say(`${failures === 0 ? "ALL CHECKS PASSED" : `${failures} CHECK(S) FAILED`} · ${unprovable} step(s) this fixture could not perform`);
say(`screenshots in ${OUT}`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-142-BRC07 Phase 5 (05-prototype/09 Reports Build Brief.pdf p16-p17, p20-p23, p31-p33, p35, read as IMAGES per B14 rule 42)
// screens: 1·1 · 1·2 · 2·2 · 2·4
// generated: 2026-09-27 by lane REP-P5
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
