/**
 * RENDERED-OUTPUT CHECK — CR-085 wave 3, *"I need a copy of something"*:
 * `CPB-14` (a copy of any document, not only a bill), `CPB-15` (a year of them
 * at once), `CPB-19` (view my bill never errors, and the screen and the file
 * agree) and `CPB-20` (the receipt, on the row a person is looking at).
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling: *"everything should be executed based on actual
 * code, and rules that we place, also ensure you do web walkthorugh before you
 * sign off the user story or build"*.
 *
 * ⚠ **AND EVERY CASE IN THIS WAVE IS INVISIBLE ON THE SEEDED ESTATE**, which
 * is why `cr085-w3-fixture.py` exists and why this file REFUSES to run without
 * it. On a freshly seeded Pine Hill every document a portal login can see is a
 * BILL, and every receipt in the queue was held by the dispatcher for want of a
 * published template — so the two branches this wave is about could never be
 * opened, and the run would report green over screens nobody had looked at
 * (`DEF-WRK-4121`'s shape).
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   10-scripts/proof-db.sh clone cr85w3
 *   export DATABASE_URL=… DJANGO_SETTINGS_MODULE=config.settings.local
 *   (cd 06-backend && python3 manage.py seed_portal_demo)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/def-cwp-3965-fixture.py)
 *   (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr085-w3-fixture.py)
 *   python3 06-backend/manage.py runserver 127.0.0.1:8193 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4393 API_PROXY_TARGET=http://127.0.0.1:8193 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4393 node 10-scripts/render-checks/cr085-w3-documents.mjs
 *
 * ⚠ **BUILD THE BUNDLE BEFORE YOU DRIVE IT.** `server.mjs` serves `dist/`, so a
 * stale build means every assertion passes or fails about a product nobody is
 * shipping.
 *
 * ── WHAT IT CLICKS ────────────────────────────────────────────────────────
 *   1  `CWP-031` — the list draws five documents, and the RECEIPT and the BILL
 *      each carry a live copy control pointing at this tenant's own address.
 *   2  The receipt's link is FETCHED through the signed-in session and answers
 *      real bytes beginning `%PDF` with the number in its filename.
 *   3  The receipt we kept no copy of is REFUSED, and the sentence is the true
 *      one — the fix is *the refusal is now true*, never *the refusal is gone*.
 *   4  The letter with no number of its own says where to get it instead.
 *   5  `Download a year ↓` is a live address, and the archive it answers holds
 *      one entry per kept document with its own bytes.
 *   6  `CWP-041` — the receipt is on the desk ROW and on the PHONE card, and
 *      nothing on the page says *Receipts arrive later this year*.
 *   7  `CWP-029` — the bill's frame and its download still work, and neither
 *      the screen nor the file route answers 500.
 *   8  Both screens at 390px: nothing overflows the window.
 */

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

/** ⚠ `chromium.executablePath()` returns a path for the build playwright-core
 *  was compiled against, present or not — so it is TESTED, not trusted. */
function resolveChromium() {
  let declared = null;
  try { declared = chromium.executablePath(); } catch { declared = null; }
  if (declared && existsSync(declared)) return declared;
  const found = execFileSync("bash", ["-lc",
    "ls -d /opt/pw-browsers/chromium-*/chrome-linux/chrome /opt/pw-browsers/chromium-*/chrome-linux64/chrome 2>/dev/null | head -1",
  ]).toString().trim();
  if (!found) throw new Error(`no chromium: playwright named ${declared ?? "(nothing)"}`);
  return found;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4393";
const TENANT = "pine-hill";
const EMAIL = process.env.SMOKE_EMAIL ?? "ana@example.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pine-Hill-2026!";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr085-w3";
const PORTAL = `${BASE}/${TENANT}/portal`;
const API = `${BASE}/api/${TENANT}/portal`;

const KEPT_RECEIPT = "PMT-2608-W3KEPT";
const LOST_RECEIPT = "PMT-2608-W3LOST";

let failures = 0;
function check(ok, what) {
  console.log(`   ${ok ? "✓" : "✗"} ${what}`);
  if (!ok) failures += 1;
}

async function main() {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  const page = await context.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr085-w3: ${BASE} tenant=${TENANT}`);

  console.log("\n── 0 · sign in, and refuse without the fixture ──");
  await page.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await page.fill("#portal-email", EMAIL);
  await page.fill("#portal-password", PASSWORD);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
  check(true, `signed in as ${EMAIL}`);

  const accounts = await (await context.request.get(`${API}/accounts`)).json();
  const held = accounts.accounts ?? [];
  const account = held[0];
  if (!account) {
    console.log("\nRED — this login holds no account.");
    process.exit(1);
  }
  const listed = await (
    await context.request.get(`${API}/accounts/${account.id}/documents`)
  ).json();
  const rows = listed.documents ?? [];
  const byRef = (ref) => rows.find((one) => one.reference === ref);
  if (!byRef(KEPT_RECEIPT) || !byRef(LOST_RECEIPT)) {
    console.log(
      "\nRED — this account has no receipt with a kept copy and none without. " +
      "Run cr085-w3-fixture.py; without it every assertion below about a " +
      "non-bill document passes vacuously.",
    );
    process.exit(1);
  }
  console.log(`   ${rows.length} document(s) on ${account.account_no}`);

  // ── 1 · CWP-031, the row controls ──────────────────────────────────────
  console.log("\n── 1 · CWP-031 · a copy of any document, not only a bill ──");
  await page.goto(`${PORTAL}/documents`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-031"]', { timeout: 20000 });
  await page.waitForTimeout(500);

  const copyHref = async (reference) =>
    page.locator(`tr:has-text("${reference}") a[aria-label="Download this document"]`)
      .first()
      .getAttribute("href");

  const receiptHref = await copyHref(KEPT_RECEIPT);
  check(
    receiptHref === `/api/${TENANT}/portal/documents/${KEPT_RECEIPT}/file`,
    `the receipt's copy control points at ${receiptHref}`,
  );
  const billRow = rows.find((one) => one.group === "bill" && one.reference);
  const billHref = await copyHref(billRow.reference);
  check(
    billHref === `/api/${TENANT}/portal/documents/${billRow.reference}/file`,
    `the bill keeps a copy control too (${billHref})`,
  );

  // ── 2 · the bytes ──────────────────────────────────────────────────────
  console.log("\n── 2 · and it answers real bytes, through this session ──");
  const served = await context.request.get(`${BASE}${receiptHref}`);
  const body = await served.body();
  check(served.status() === 200, `the receipt link answers ${served.status()}`);
  check(
    body.slice(0, 4).toString() === "%PDF",
    `${body.length} bytes beginning ${JSON.stringify(body.slice(0, 4).toString())}`,
  );
  check(
    (served.headers()["content-disposition"] ?? "").includes(`${KEPT_RECEIPT}.pdf`),
    `named ${served.headers()["content-disposition"]}`,
  );

  // ── 3 · the refusal that is now TRUE ───────────────────────────────────
  console.log("\n── 3 · and the one we kept no copy of is still refused ──");
  const lost = page
    .locator(`tr:has-text("${LOST_RECEIPT}") button[aria-label="Download this document"]`)
    .first();
  check(await lost.isDisabled(), "the control is visibly held, not missing");
  check(
    (await lost.getAttribute("title")) === "We kept no copy of this.",
    `and its reason is ${JSON.stringify(await lost.getAttribute("title"))}`,
  );

  // ── 4 · a letter with no number of its own ─────────────────────────────
  console.log("\n── 4 · a letter with no number says where to get it instead ──");
  const letter = rows.find((one) => one.reference === null);
  if (!letter) {
    check(false, "no reference-less document on this account — fixture not run?");
  } else {
    const held = page
      .locator('tr:has-text("No reference number") button[aria-label="Download this document"]')
      .first();
    check(await held.isDisabled(), "held, because there is no number to look it up by");
    check(
      (await held.getAttribute("title")) === "Use Download a year instead",
      `and it names the way out: ${JSON.stringify(await held.getAttribute("title"))}`,
    );
  }

  // ── 5 · Download a year ────────────────────────────────────────────────
  console.log("\n── 5 · CPB-15 · a year of documents, in one file ──");
  const yearHref = await page
    .locator('[data-download="documents-year"]')
    .first()
    .getAttribute("href");
  check(
    yearHref === `/api/${TENANT}/portal/accounts/${account.id}/documents/year.zip`,
    `Download a year is live at ${yearHref}`,
  );
  check(
    (await page.locator("text=Downloads are not ready yet").count()) === 0,
    "and the old hold is off the screen",
  );
  const archive = await context.request.get(`${BASE}${yearHref}`);
  const zip = await archive.body();
  check(archive.status() === 200, `the archive answers ${archive.status()}`);
  check(zip.slice(0, 2).toString() === "PK", `${zip.length} bytes beginning "PK"`);
  const kept = archive.headers()["x-documents-kept"];
  const all = archive.headers()["x-documents-listed"];
  check(
    Number(kept) > 0 && Number(kept) <= Number(all),
    `it carries ${kept} of ${all} listed — the shortfall is reported, not hidden`,
  );
  writeFileSync(join(OUT, "year.zip"), zip);

  // ── 6 · CWP-041, the receipt where a person looks for it ───────────────
  console.log("\n── 6 · CPB-20 · the receipt on the money list ──");
  await page.goto(`${PORTAL}/payments`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-041"]', { timeout: 20000 });
  await page.waitForTimeout(500);
  // ⚠ **ADDRESSED BY THE ROW, NOT BY POSITION.** The first draft of this file
  // read `.first()` and caught the row for the receipt we kept NO copy of —
  // which is how the third state was found: the screen was offering a live
  // download over a document the server refuses. Asserting a row by its own
  // number is what makes that visible instead of confusing.
  const deskReceipt = await page
    .locator(`[data-list="CWP-041"] tr:has-text("38.44") a[aria-label="Download this receipt"]`)
    .first()
    .getAttribute("href");
  check(
    deskReceipt === `/api/${TENANT}/portal/documents/${KEPT_RECEIPT}/file`,
    `the desk row serves ${deskReceipt}`,
  );
  const lostRow = page
    .locator(`[data-list="CWP-041"] tr:has-text("21.00") button[aria-label="Download this receipt"]`)
    .first();
  check(
    await lostRow.isDisabled(),
    "and the payment whose receipt we kept no copy of is HELD, not offered",
  );
  const cardReceipt = await page
    .locator('[data-money-card] [data-card-receipt]')
    .first()
    .getAttribute("href");
  check(
    cardReceipt === `/api/${TENANT}/portal/documents/${KEPT_RECEIPT}/file`,
    `and so does the phone card (${cardReceipt})`,
  );
  check(
    (await page.locator("text=Receipts arrive later this year").count()) === 0,
    "and nothing on the page says receipts arrive later this year",
  );

  // ── 7 · CWP-029, and the two routes that used to disagree ──────────────
  console.log("\n── 7 · CPB-19 · view my bill, and the file behind it ──");
  await page.goto(`${PORTAL}/bills/${billRow.reference}/document`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-029"]', { timeout: 20000 });
  await page.waitForTimeout(400);
  const read = await (
    await context.request.get(`${API}/bills/${billRow.reference}/document`)
  ).json();
  const file = await context.request.get(
    `${API}/bills/${billRow.reference}/document.pdf?view=1`,
  );
  check(file.status() !== 500, `the file route answers ${file.status()}, not 500`);
  check(
    // ⚠ **THE WHOLE OF `CPB-19` IS THIS ONE LINE.** The screen believes
    // `available`; the customer meets the file route. They have to agree.
    read.available === (file.status() === 200),
    `the screen says available=${read.available} and the file answers ${file.status()}`,
  );
  check(
    (await page.locator('[data-document-preview]').count()) === 1,
    "the issued page is framed on screen",
  );

  // ── 8b · CWP-043's agreement ───────────────────────────────────────────
  console.log("\n── 8b · CPB-14 · the SIGNED plan agreement on CWP-043 ──");
  const plans = await (
    await context.request.get(`${API}/accounts/${account.id}/plans/current`)
  ).json();
  const live = (plans.plans ?? []).find((one) => one.live);
  if (!live) {
    // ⚠ **THIS REFUSES; IT USED TO SKIP, AND THE SKIP WAS PERMANENT.**
    // `ana@` holds no plan on the seeded estate, so every run of this file
    // printed "SKIPPED" and went green over `CPB-14`'s FOURTH control — the
    // one released from `portal.yourPlan.agreementHeld` — which therefore
    // reached this branch having never been drawn in a browser at all. A skip
    // that can never stop being a skip is not a smaller check, it is the shape
    // this repository calls *a check that cannot fail* (hard-won law 7), and
    // it sat inside the walkthrough written to prevent exactly that.
    // `cr085-w3-fixture.py` plants the plan now, so an absence here is a
    // fixture that was not run and never an account that happens to lack one.
    console.log(
      "\nRED — this login holds no live plan, so CWP-043's agreement control " +
      "cannot be walked. Run cr085-w3-fixture.py; without it CPB-14's plan " +
      "agreement passes vacuously.",
    );
    process.exit(1);
  }
  await page.goto(`${PORTAL}/plan`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="CWP-043"]', { timeout: 20000 });
  await page.waitForTimeout(400);
  const drawn = await page.locator('[data-download="plan-agreement"]').count();
  check(
    drawn === (live.agreement_available ? 1 : 0),
    `the agreement control matches agreement_available=${live.agreement_available}`,
  );
  check(
    (await page.locator("text=Downloads arrive later this year").count()) === 0,
    "and the rotted hold is off the screen",
  );
  // ⚠ **AND THE CONTROL IS FOLLOWED, NOT MERELY COUNTED.** The whole wave is
  // about a promise and a serving path agreeing; a drawn button asserts the
  // promise and nothing else. This fetches it through the signed-in session,
  // the way a customer's browser would.
  const agreementHref = await page
    .locator('[data-download="plan-agreement"]')
    .first()
    .getAttribute("href");
  check(
    agreementHref ===
      `/api/${TENANT}/portal/accounts/${account.id}/plans/current/agreement`,
    `the agreement is addressed as this account's live plan (${agreementHref})`,
  );
  const agreement = await context.request.get(`${BASE}${agreementHref}`);
  const agreementBody = await agreement.body();
  check(agreement.status() === 200, `the agreement answers ${agreement.status()}, not 500`);
  check(
    agreementBody.slice(0, 4).toString() === "%PDF",
    `${agreementBody.length} bytes beginning "%PDF"`,
  );
  // ⚠ **B14 rule 31 — no plan id travels.** `current_plans` publishes none and
  // the route resolves the live plan server-side; a walkthrough that did not
  // look would not notice one appearing in the address.
  // The ACCOUNT's id is in the path here and always has been — `documents/
  // year.zip` above carries it too, and rule 31 governs the visible value of a
  // FIELD, not a route segment. What must not appear is a PLAN id, because
  // `current_plans` deliberately publishes none for the browser to put there.
  check(
    agreementHref.split("/plans/")[1] === "current/agreement",
    `and the plan is named "current", never by id (…/plans/${agreementHref.split("/plans/")[1]})`,
  );

  // ── 8 · a phone ────────────────────────────────────────────────────────
  console.log("\n── 8 · 390px — nothing overflows ──");
  const small = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const phone = await small.newPage();
  await phone.goto(`${PORTAL}/sign-in`, { waitUntil: "networkidle" });
  await phone.fill("#portal-email", EMAIL);
  await phone.fill("#portal-password", PASSWORD);
  await phone.getByRole("button", { name: /sign in/i }).click();
  await phone.waitForSelector('[data-portal-frame="shell"]', { timeout: 20000 });
  for (const [path, screen] of [["/documents", "CWP-031"], ["/payments", "CWP-041"]]) {
    await phone.goto(`${PORTAL}${path}`, { waitUntil: "networkidle" });
    await phone.waitForSelector(`[data-screen="${screen}"]`, { timeout: 20000 });
    await phone.waitForTimeout(400);
    const overflow = await phone.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    check(overflow <= 0, `${screen} at 390px overflows by ${overflow}px`);
    await phone.screenshot({ path: join(OUT, `${screen}-390.png`), fullPage: true });
  }
  await page.goto(`${PORTAL}/documents`, { waitUntil: "networkidle" });
  await page.waitForTimeout(400);
  await page.screenshot({ path: join(OUT, "CWP-031-1280.png"), fullPage: true });

  await browser.close();
  console.log(`\n${failures === 0 ? "GREEN" : `RED — ${failures} check(s) failed`}`);
  process.exit(failures === 0 ? 0 : 1);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
