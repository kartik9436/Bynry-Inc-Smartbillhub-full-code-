// ── Trace ──────────────────────────────────────────────
// Change:  CR-094-BRC01 step 2 wave B — the five rows this lane repaired on
//          the Account detail screen (S21) and its S22 Record payment modal.
// Defects: DEF-CUS-4999 / DEF-CUS-5008 (one bug, found twice — six decimals
//          shown AND pre-filled in the Record payment modal) ·
//          DEF-CUS-4998 (two surfaces told a clerk the customer portal does
//          not exist) · DEF-CUS-5000 (the sub-type reached a clerk as the raw
//          database word `small_commercial`) · DEF-CUS-5005 (Close out live
//          on a pending-activation account) · DEF-CUS-5004 (three absence
//          sentences in the catalogue and on no screen).
// Rules:   CLAUDE.md hard rule 2 (money displays 2 decimals, PO re-sign
//          2026-08-22) · B14 rule 31 (no database id is the visible value of
//          a field) · BR-CUS-430 (a close-out is for an account whose service
//          was CUT) · BR-SHL-025 (a control this deployment cannot honour
//          renders DISABLED WITH its reason, never hidden) · hard-won law 6
//          (no gate in this repo looks at rendered output) · hard-won law 7
//          (a check's output must distinguish pass from fail to a READER).
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY CHECK PRINTS WHAT IT LOOKED FOR AND WHAT IT FOUND INSTEAD**, so a
// reader can tell a pass from a fail without reading the exit code. That is
// law 7's third habit, and this file's step-1 sibling
// (`cr094_lane2_account_detail_walkthrough.mjs`) is where the shape comes from.
//
// ⚠ **THE MONEY CHECKS READ COMPUTED VALUES, NOT CLASS NAMES.** `#amount`'s
// `inputValue()` is what a clerk would submit; the balance line is read as
// rendered text. A `toContain("cell-money")` would pass over `247.300000`
// wrapped in the right span, which is the false pass this file exists to rule
// out.
//
// ⚠ **TWO WIDTHS, 1280 AND 1440.** Nothing here is layout-sensitive, and it is
// run at both anyway: the fault being measured is copy and state, and a
// responsive breakpoint that hides a control would make a refusal check pass
// for the wrong reason.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
//      JOBS_EAGER=false python3 manage.py runserver 127.0.0.1:8630 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8631 \
//      API_PROXY_TARGET=http://127.0.0.1:8630 node server.mjs)
//   node 10-scripts/cr094_wave_b_walkthrough.mjs
//
// THE ACCOUNTS, AND WHY EACH
//   A-10432  balance 247.300000 — lane 5's measured figure, the money rows
//   A-11812  balance 2410.000000, sub-type `small_commercial` — lane 2's
//   A-12048  pending_activation — the Close out gate's wrong-way row
const { existsSync, readdirSync, mkdirSync, writeFileSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8631";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const MONEY = process.env.MONEY ?? "01a09540-727d-7b81-a750-49ddd2e237be"; // A-10432 · 247.300000
const SUBTYPE = process.env.SUBTYPE ?? "01a09540-7be8-7b51-8ca7-b31859b459a3"; // A-11812 · 2410.000000
const DRAFT = process.env.DRAFT ?? "01a09540-73b5-7025-a5be-32232c985865"; // A-12048 · pending_activation
const OUT = process.env.OUT ?? "/tmp/cr094-wave-b";
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
function check(width, name, ok, detail = "") {
  results.push({ width, name, ok });
  console.log(`  ${ok ? "PASS" : "FAIL"}  [${width}] ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

/**
 * Every money-shaped run with MORE than two decimals.
 *
 * ⚠ **THE VERSION BADGE IS EXCLUDED BY NAME, AND IT IS NOT A CONVENIENCE.**
 * Step 1's regex returned `["2.237", "2410.000000"]` — the sidebar's
 * `v2.237.10` matched as over-precise money. A check that reports a true
 * finding beside a permanent false one trains its reader to skim both.
 */
function overPreciseMoney(text) {
  const stripped = text.replace(/\bv?\d+\.\d+\.\d+\b/g, "");
  return [...new Set([...stripped.matchAll(/(?<![\d.])\d[\d,]*\.\d{3,}(?![\d])/g)].map((m) => m[0]))];
}

const browser = await chromium.launch({ executablePath: resolveChromium(), args: ["--no-sandbox"] });

for (const width of [1280, 1440]) {
  const page = await browser.newPage({ viewport: { width, height: 1800 } });
  console.log(`\n══════ ${width}px ══════`);
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);

  // ── 1 · DEF-CUS-4999 / DEF-CUS-5008 — MONEY, READ AS A COMPUTED VALUE ────
  console.log("\n1 · the Record payment modal (hard rule 2 — money displays 2)");
  for (const [label, accountId, expectedFigure, expectedBox] of [
    ["A-10432", MONEY, "$247.30", "247.30"],
    ["A-11812", SUBTYPE, "$2,410.00", "2410.00"],
  ]) {
    await page.goto(`${BASE}/${TENANT}/accounts/${accountId}?tab=overview`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(3000);
    await page.click('text="Record payment"').catch(() => {});
    await page.waitForTimeout(1500);
    const modalText = await page.locator(".modal-card").innerText().catch(() => "<no modal>");
    const box = await page.locator("#amount").inputValue().catch(() => "<no #amount>");
    writeFileSync(join(OUT, `${width}-modal-${label}.txt`), modalText);
    await page.screenshot({ path: join(OUT, `${width}-modal-${label}.png`) });

    check(width, `${label}: the balance line reads ${expectedFigure}`,
      modalText.includes(expectedFigure),
      `looked for "${expectedFigure}"; the modal's balance row reads: ${JSON.stringify((modalText.match(/Balance[^\n]*\n?[^\n]*/) ?? [""])[0])}`);
    check(width, `${label}: the amount box is pre-filled "${expectedBox}"`,
      box === expectedBox, `#amount inputValue() = ${JSON.stringify(box)}`);
    check(width, `${label}: nothing in the modal shows more than 2 decimals`,
      overPreciseMoney(modalText).length === 0,
      `over-precise runs found: ${JSON.stringify(overPreciseMoney(modalText))}`);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(600);
  }

  // ── 2 · DEF-CUS-4998 — NO SURFACE DENIES THE PORTAL ──────────────────────
  console.log("\n2 · the portal shipped (DEF-CUS-4998 — two surfaces denied it)");
  const DENIAL = "no customer portal in this version";
  await page.goto(`${BASE}/${TENANT}/accounts/${SUBTYPE}?tab=notes`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  await page.click('text="Add note"').catch(() => {});
  await page.waitForTimeout(1200);
  const noteText = await page.locator("body").innerText();
  writeFileSync(join(OUT, `${width}-add-note.txt`), noteText);
  await page.screenshot({ path: join(OUT, `${width}-add-note.png`) });
  check(width, "the Add note dialog does not deny the portal",
    !noteText.includes(DENIAL),
    `the sentence is on screen: ${JSON.stringify((noteText.match(/[^\n]*no customer portal[^\n]*/) ?? [""])[0])}`);
  check(width, "and it says what IS true instead",
    noteText.includes("Nothing shows it to customers yet"),
    `the hint reads: ${JSON.stringify((noteText.match(/[^\n]*Saved with the note[^\n]*/) ?? ["<not found>"])[0])}`);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(600);

  await page.goto(`${BASE}/${TENANT}/accounts/${SUBTYPE}?tab=audit`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  const hover = await page
    .locator('[data-rule-ref="BR-CUS-028"]')
    .getAttribute("title")
    .catch(() => null);
  await page.screenshot({ path: join(OUT, `${width}-audit.png`) });
  check(width, "the Audit tab's portal-actor hover does not deny the portal",
    hover !== null && !hover.includes(DENIAL), `title attribute = ${JSON.stringify(hover)}`);
  check(width, "and it states only what the log actually records",
    hover === "Who acted is recorded. The channel is not.",
    `title attribute = ${JSON.stringify(hover)}`);

  // ── 3 · DEF-CUS-5000 — NO RAW DATABASE WORD ON THE OVERVIEW ──────────────
  console.log("\n3 · the sub-type (B14 rule 31 — no database id on screen)");
  await page.goto(`${BASE}/${TENANT}/accounts/${SUBTYPE}?tab=overview`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(3000);
  const overview = await page.locator("main").innerText();
  writeFileSync(join(OUT, `${width}-overview.txt`), overview);
  await page.screenshot({ path: join(OUT, `${width}-overview.png`), fullPage: true });
  const rawEnums = [...new Set([...overview.matchAll(/\b[a-z]+_[a-z_]+\b/g)].map((m) => m[0]))];
  check(width, "the Overview prints no raw snake_case value at all",
    rawEnums.length === 0, `raw strings on screen: ${JSON.stringify(rawEnums)}`);
  check(width, "the Sub-type reads the tenant's label",
    /Sub-type\s*\n?\s*Small commercial/.test(overview),
    `the Sub-type row reads: ${JSON.stringify((overview.match(/Sub-type[^\n]*\n?[^\n]*/) ?? [""])[0])}`);
  check(width, "the Overview shows no money past 2 decimals either",
    overPreciseMoney(overview).length === 0,
    `over-precise runs: ${JSON.stringify(overPreciseMoney(overview))}`);

  // ── 4 · DEF-CUS-5004 — THREE RETIRED SENTENCES REACH NO SCREEN ───────────
  console.log("\n4 · the retired absence sentences (DEF-CUS-5004)");
  check(width, "the Customer panel no longer carries the duplicate-check paragraph",
    !overview.includes("What is still missing is the duplicate check"),
    "the retired sentence is on screen");
  check(width, "and the Customer panel still has its own live sentence",
    overview.includes("This is one contact on one account"),
    "the panel lost the sentence it DOES render — a retirement that took a live string with it");

  // ── 5 · DEF-CUS-5005 — THE CLOSE OUT GATE ────────────────────────────────
  console.log("\n5 · Close out (BR-CUS-430 — only an account whose service was CUT)");
  const REFUSAL = "Only an account whose service has been cut is closed out.";
  for (const [label, accountId] of [
    ["A-12048 · pending_activation", DRAFT],
    ["A-11812 · active", SUBTYPE],
  ]) {
    await page.goto(`${BASE}/${TENANT}/accounts/${accountId}?tab=overview`, {
      waitUntil: "networkidle",
    });
    await page.waitForTimeout(3000);
    await page.screenshot({ path: join(OUT, `${width}-closeout-${accountId.slice(-6)}.png`) });
    const state = await page
      .locator("main")
      .getByText("Close out", { exact: true })
      .first()
      .evaluate((el) => {
        const b = el.closest("button");
        if (b === null) return { found: "not a button" };
        return { disabled: b.disabled, title: b.getAttribute("title") };
      })
      .catch(() => ({ found: "not found" }));
    // BR-SHL-025 — the control stays on screen either way.
    check(width, `${label}: Close out is still ON the screen`,
      state.disabled !== undefined, `evaluate() answered ${JSON.stringify(state)}`);
    check(width, `${label}: Close out is DISABLED`,
      state.disabled === true, `button state = ${JSON.stringify(state)}`);
    check(width, `${label}: and it carries its reason`,
      (state.title ?? "").includes(REFUSAL), `title = ${JSON.stringify(state.title)}`);
  }
  // ⚠ THE ALLOW ROW CANNOT BE WALKED HERE AND SAYING SO IS THE POINT: this
  // tenant seeds NO `disconnected` account and the product cannot make one on
  // this fixture (see `cr094_wave_b_seed_cut_account.py`). It is proved instead
  // by the six-row truth table in `AccountDetailPage.test.tsx`, which renders
  // the real component on a `disconnected` detail. A gate that only ever
  // refuses passes every check above — hard-won law 7.
  console.log(
    "  NOTE  [" + width + "] the `disconnected` row is NOT walked here — no such account exists on this fixture;" +
      "\n          it is proved by the truth-table case in AccountDetailPage.test.tsx (both directions).",
  );

  await page.close();
}

await browser.close();

const pass = results.filter((r) => r.ok).length;
const fail = results.filter((r) => !r.ok).length;
console.log("\n── RESULT ─────────────────────────────────────────────");
console.log(`${pass} pass · ${fail} fail  (over 2 widths: 1280 and 1440)`);
for (const r of results.filter((r) => !r.ok)) console.log(`  FAILED [${r.width}] ${r.name}`);
console.log(`screenshots and page text under ${OUT}`);
process.exit(fail === 0 ? 0 : 1);
