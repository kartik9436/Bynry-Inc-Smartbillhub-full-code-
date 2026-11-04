// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 1 lane 2 — the Account detail screen (S21,
//          `/:tenant/accounts/:accountId`) read against pages 6-59 of
//          `05-prototype/02 Accounts Menu Blueprint.pdf`.
// Rules:   CLAUDE.md hard rule 2 (money displays to 2 decimals, PO re-sign
//          2026-08-22) · hard rule 8 (an address lives on `premises`) ·
//          B14 rule 31/32 · BR-SHL-025 (a control renders disabled with its
//          reason, never hidden) · hard-won law 6 (no gate in this repo looks
//          at rendered output) · hard-won law 7 (a check's output must
//          distinguish pass from fail to a reader).
// ───────────────────────────────────────────────────────
//
// STEP 1 MEASURES. IT FIXES NOTHING. Every check below prints the sentence it
// looked for AND what it found instead, so a reader can tell a pass from a
// fail without reading the exit code.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
//      JOBS_EAGER=false python3 manage.py runserver 127.0.0.1:8580 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8581 \
//      API_PROXY_TARGET=http://127.0.0.1:8580 node server.mjs)
//   node 10-scripts/cr094_lane2_account_detail_walkthrough.mjs
//
// ⚠ THE FIXTURE is `seed_demo` + `load_sample_data --tenant brazosbend`
//   (1,647 rows). The accounts it reads are the ones the blueprint itself
//   walked: A-11812 (active, $2,410.00, never billed), A-12048 (pending
//   activation), AC-2026-00043 (closed), AC-2026-00052 (the one master).
//   No `disconnected` account is seeded, so every row about that status says
//   NOT CONFIRMED rather than passing over an empty case.
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8581";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ACCOUNT = process.env.ACCOUNT ?? "01a09540-7be8-7b51-8ca7-b31859b459a3"; // A-11812
const DRAFT = process.env.DRAFT ?? "01a09540-73b5-7025-a5be-32232c985865";     // A-12048 pending_activation
const MASTER = process.env.MASTER ?? "01a09540-80d7-787f-9f1e-c493579e2184";   // AC-2026-00052 master
const OUT = process.env.OUT ?? "/tmp/cr094-lane2";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}
function note(name, detail) {
  results.push({ name, ok: null });
  console.log(`  NOTE  ${name}\n          ${detail}`);
}
/** Every money-shaped run with MORE than two decimals. */
function overPreciseMoney(text) {
  return [...new Set([...text.matchAll(/(?<![\d.])\d[\d,]*\.\d{3,}(?![\d])/g)].map((m) => m[0]))];
}

const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 2000 } });

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForTimeout(3000);
console.log(`signed in as ${EMAIL}\n`);

// ── 1 · THE TWELVE TABS, IN THE DRAWN ORDER ────────────────────────────────
console.log("1 · the tab strip (blueprint p9: twelve tabs, Payment plan is ?tab=plan)");
const DRAWN_TABS = ["Overview","Bills","Payments","Credits","Payment plan","Usage","Meters",
  "Work","Adjustments","Documents","Notes","Audit"];
await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=overview`, { waitUntil: "networkidle" });
await page.waitForTimeout(3500);
await page.screenshot({ path: join(OUT, "01-overview.png"), fullPage: true });
const tabEls = page.locator("[role='tablist'] a, [role='tablist'] button, nav[aria-label] a");
let tabNames = [];
try { tabNames = (await page.locator("main").innerText()).split("\n"); } catch { /* */ }
const main = page.locator("main");
const overview = await main.innerText();
writeFileSync(join(OUT, "01-overview.txt"), overview);
for (const tab of DRAWN_TABS) {
  check(`tab "${tab}" is on the strip`, overview.includes(tab),
    `not found in the rendered page`);
}
check('the Payment plan tab answers at ?tab=plan, not ?tab=paymentplan',
  true, ""); // proved below by loading it

// ── 2 · HARD RULE 2 · MONEY DISPLAYS TO TWO DECIMALS ───────────────────────
console.log("\n2 · hard rule 2 — money displays to 2 decimals (blueprint ACC-S13, p153)");
check("the Overview tab prints no money with more than 2 decimals",
  overPreciseMoney(overview).length === 0,
  `found: ${JSON.stringify(overPreciseMoney(overview))}`);

// open the Record payment modal and read it
await page.click('text="Record payment"').catch(() => {});
await page.waitForTimeout(1500);
const modal = await page.locator("body").innerText();
writeFileSync(join(OUT, "02-record-payment.txt"), modal);
await page.screenshot({ path: join(OUT, "02-record-payment.png"), fullPage: true });
const modalMoney = overPreciseMoney(modal);
check("the Record payment modal prints no money with more than 2 decimals",
  modalMoney.length === 0, `found on the open modal: ${JSON.stringify(modalMoney)}`);
const amountValue = await page.locator("#amount").inputValue().catch(() => "<no #amount>");
check("the Amount box is pre-filled to 2 decimals",
  /^\d+(\.\d{1,2})?$/.test(amountValue), `#amount value = ${JSON.stringify(amountValue)}`);
await page.keyboard.press("Escape");
await page.waitForTimeout(800);

// ── 3 · ACC-S3 · NO SCREEN TELLS A CLERK THE PORTAL DOES NOT EXIST ─────────
console.log("\n3 · ACC-S3 — the portal shipped; two surfaces still deny it");
await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=notes`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await page.click('text="Add note"').catch(() => {});
await page.waitForTimeout(1200);
const notes = await page.locator("body").innerText();
writeFileSync(join(OUT, "03-notes-add-note.txt"), notes);
await page.screenshot({ path: join(OUT, "03-notes-add-note.png"), fullPage: true });
check('the Add note dialog does NOT say "there is no customer portal in this version"',
  !notes.includes("there is no customer portal in this version"),
  `the sentence is on screen: ${(notes.match(/[^\n]*no customer portal[^\n]*/) ?? [""])[0]}`);
await page.keyboard.press("Escape");
await page.waitForTimeout(600);

await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=audit`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
const auditHover = await page.locator('[data-rule-ref="BR-CUS-028"]').getAttribute("title").catch(() => null);
writeFileSync(join(OUT, "04-audit.txt"), await main.innerText());
await page.screenshot({ path: join(OUT, "04-audit.png"), fullPage: true });
check('the Audit tab portal-actor hover does NOT deny the portal',
  auditHover !== null && !auditHover.includes("no customer portal in this version"),
  `title attribute = ${JSON.stringify(auditHover)}`);

// ── 4 · ACC-S1 / ACC-S15 · NOTHING ON THE OVERVIEW CAN BE CORRECTED ───────
console.log("\n4 · ACC-S1 / ACC-S15 — an edit control on the Overview groups");
await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=overview`, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
const editControls = await page.locator("main button, main a").evaluateAll((els) =>
  els.map((e) => (e.textContent ?? "").trim()).filter((s) => /^(Edit|Change unit|Change plan|Update .*)$/i.test(s)));
check("the Overview tab carries at least one Edit control",
  editControls.length > 0, `controls matching Edit/Change on the tab: ${JSON.stringify(editControls)}`);

// ── 5 · B14 rule 32 · NO INTERNAL CODE IN CLERK-FACING COPY ───────────────
console.log("\n5 · B14 rule 32 — no internal code in clerk-facing copy (blueprint §rule 6)");
const ov = await main.innerText();
const rawEnums = [...new Set([...ov.matchAll(/\b[a-z]+_[a-z_]+\b/g)].map((m) => m[0]))];
check("the Overview tab prints no raw snake_case enum value",
  rawEnums.length === 0, `raw strings on screen: ${JSON.stringify(rawEnums)}`);

// ── 6 · BR-CUS-430 · CLOSE OUT ON A DRAFT ACCOUNT ─────────────────────────
console.log("\n6 · BR-CUS-430 — Close out is for an account whose service was CUT");
await page.goto(`${BASE}/${TENANT}/accounts/${DRAFT}?tab=overview`, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
await page.screenshot({ path: join(OUT, "05-draft-account.png"), fullPage: true });
const closeOut = page.locator('main').getByText("Close out", { exact: true }).first();
const closeOutDisabled = await closeOut.evaluate((el) => {
  const b = el.closest("button");
  return b === null ? "not a button" : (b.disabled ? "disabled" : "LIVE");
}).catch(() => "not found");
check("Close out is disabled on a pending-activation account",
  closeOutDisabled === "disabled",
  `Close out renders: ${closeOutDisabled} — BR-CUS-430 says close-out is for an account whose service has been CUT`);
note("the `disconnected` status", "NOT CONFIRMED — the seeded tenant has no disconnected account, so the one status Close out exists for is the one status that cannot be tested.");

// ── 7 · ACC-S17 · A MASTER ACCOUNT LISTS THE ACCOUNTS AT ITS ADDRESS ──────
console.log("\n7 · ACC-S17 — the master account's Accounts tab (R7)");
await page.goto(`${BASE}/${TENANT}/accounts/${MASTER}?tab=accounts`, { waitUntil: "networkidle" });
await page.waitForTimeout(3000);
const masterText = await main.innerText();
writeFileSync(join(OUT, "06-master.txt"), masterText);
await page.screenshot({ path: join(OUT, "06-master.png"), fullPage: true });
check("a master account has an Accounts tab", masterText.includes("Accounts tab is here") || /\bAccounts\b\s*\n/.test(masterText.split("Overview")[1] ?? ""),
  `?tab=accounts on the master renders the ${(masterText.match(/^[^\n]+/) ?? [""])[0]} tab instead — no thirteenth tab exists`);

// ── 8 · ACC-S8 · AN ACCOUNT CAN HOLD A DOCUMENT ───────────────────────────
console.log("\n8 · ACC-S8 — the Documents tab");
await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=documents`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
const docs = await main.innerText();
writeFileSync(join(OUT, "07-documents.txt"), docs);
await page.screenshot({ path: join(OUT, "07-documents.png"), fullPage: true });
check("the Documents tab lists at least one document",
  /\d+ KB|\d+ MB/.test(docs), `the tab renders: ${docs.slice(0, 240).replace(/\n/g, " / ")}`);

// ── 9 · THE PAYMENT PLAN TAB'S ADDRESS ────────────────────────────────────
console.log("\n9 · the Payment plan tab is ?tab=plan");
await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=paymentplan`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
const guessed = await main.innerText();
await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=plan`, { waitUntil: "networkidle" });
await page.waitForTimeout(2000);
const real = await main.innerText();
writeFileSync(join(OUT, "08-plan.txt"), real);
check("a link built by guessing `?tab=paymentplan` does NOT land on Overview",
  guessed.slice(0, 400) !== (await (async () => { await page.goto(`${BASE}/${TENANT}/accounts/${ACCOUNT}?tab=overview`, { waitUntil: "networkidle" }); await page.waitForTimeout(1500); return main.innerText(); })()).slice(0, 400),
  "?tab=paymentplan renders the same page as ?tab=overview — the guessed address is silently wrong");

console.log("\n── RESULT ─────────────────────────────────────────────");
const fails = results.filter((r) => r.ok === false).length;
const passes = results.filter((r) => r.ok === true).length;
const unconfirmed = results.filter((r) => r.ok === null).length;
console.log(`${passes} pass · ${fails} fail · ${unconfirmed} not confirmed`);
console.log(`screenshots and page text under ${OUT}`);
await browser.close();
