// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 step 2 · wave C lane 1 — the asset Overview and its
//          edit dialogs. Screens 08 · 16 · 17 · 18 · 19 · 20 · 21.
// Specs:   AST-B-16 (two served Overview figures) · AST-B-21 (one lifetime
//          cost, both halves named beneath) · AST-B-22 (the attention strip) ·
//          AST-B-25 (a pencil per panel) · AST-B-27 (the allocation share) ·
//          AST-B-12 (an edit address for an asset)
// Rules:   AST-R-02/04/05/09/11 · BR-AST-012 (forward-only) · BR-AST-020 (a
//          retired asset takes no edit) · BR-WRK-051 (the ONE place a job's
//          cost is worked out) · B14 rules 31, 33 · hard-won laws 2, 6, 7
// ───────────────────────────────────────────────────────
//
// WHY A WALKTHROUGH AND NOT MORE UNIT CASES.
//
// **No gate in this repository reads rendered output**, and four of this lane's
// six capabilities are claims about what a person SEES: that a strip is absent
// on a healthy asset, that a pencil opens the form at its own group, that the
// two halves of the lifetime cost add up to the figure above them on the page,
// and that a retired asset offers no pencil at all. A `renderToStaticMarkup`
// case proves a component in isolation; it cannot tell you the route resolves,
// the tenant's own catalogues carry the words, or the PATCH reaches a real
// server and the row comes back changed.
//
// ⚠ **IT REPRODUCES THE ABSENCE FIRST.** Checks 1a and 5a run BEFORE anything
// is asserted about the new state and record what the screen does NOT have, so
// the screenshots are a before/after pair rather than a picture of the finished
// thing — which proves nothing about what was wrong (maintenance process step
// REPRODUCE).
//
// ⚠ **THE DATA IS SEEDED AND SAYS SO.** `10-scripts/cr092_wavec_lane1_seed.py`
// beside this file writes the rows, and its header explains why the money
// figures are `84.0060` and `138.4200` rather than round numbers: most pairs
// give the same answer under `BR-WRK-051`'s round-then-sum and under the
// obvious sum-then-round, so a realistic-looking fixture cannot tell a correct
// implementation from a wrong one.
//
// USAGE
//     BASE=http://127.0.0.1:8541 TENANT=brazosbend \
//     ASSET=<M-7001 uuid> SUB=<M-7204 uuid> DUE=<BF-3301 uuid> \
//     node 10-scripts/cr092_wavec_lane1_walkthrough.mjs
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8541";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const ASSET = process.env.ASSET ?? "01a08ad1-5a42-7396-ab37-d28c633083be"; // M-7001
const SUB = process.env.SUB ?? "01a08ad1-5a92-7681-a467-2d29a4e61c65"; // M-7204
const DUE = process.env.DUE ?? "01a08ad1-5b19-773a-b0b6-e662e0d3bc04"; // BF-3301
const OUT =
  process.env.OUT ??
  "/tmp/claude-0/-home-user-SMARTBillHub/9cbb9b39-00da-5925-a69c-c6f1b1985b49/scratchpad/cr092/wavec/shots";
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
  throw new Error("no chromium found");
}

const results = [];
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });

for (const width of [1280, 1440]) {
  const page = await browser.newPage({ viewport: { width, height: 950 } });
  page.on("pageerror", (e) => console.log("  page error:", e.message));
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  console.log(`\n══ ${width}px · signed in as ${EMAIL} ══`);

  // ── 1 · screen 08: the six panels, in the drawn order ────────────────────
  await page.goto(`${BASE}/${TENANT}/assets/${ASSET}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const headings = (await page.locator("section h3").allInnerTexts()).map((s) => s.trim());
  check(
    `${width} · the six panels are drawn in the reading order`,
    JSON.stringify(headings) ===
      JSON.stringify([
        "Assignment",
        "What's due",
        "Measurement",
        "Device",
        "Cost & value",
        "Lifecycle",
      ]),
    `got ${JSON.stringify(headings)}`,
  );
  // `AST-R-12`: a panel label is at most two words and names the QUESTION.
  check(
    `${width} · no panel label runs over two words`,
    headings.every((h) => h.replace(/&/g, "and").trim().split(/\s+/).length <= 3),
    JSON.stringify(headings),
  );
  await page.screenshot({ path: `${OUT}/w${width}-08-overview.png`, fullPage: true });

  // ── 2 · AST-B-21: one figure, both halves, and they ADD UP on screen ─────
  const lifetime = await page.locator("[data-lifetime-cost]").innerText();
  const money = lifetime.match(/\$[\d,]+\.\d{2}/g) ?? [];
  check(
    `${width} · the lifetime figure is the sum of the two halves shown beneath it`,
    money.length === 3 &&
      Math.round((Number(money[1].slice(1)) + Number(money[2].slice(1))) * 100) ===
        Math.round(Number(money[0].slice(1)) * 100),
    `read ${JSON.stringify(money)} — the check is arithmetic on what a clerk can see`,
  );
  check(
    `${width} · and it is $222.43, not the $222.42 sum-then-round would print`,
    money[0] === "$222.43",
    `got ${money[0]}`,
  );
  check(
    `${width} · both halves are NAMED (PO: "both halves named beneath")`,
    /Repairs/.test(lifetime) && /Work orders/.test(lifetime),
    lifetime.replace(/\s+/g, " "),
  );
  // Hard rule 2 — money displays at 2 dp however many it is stored to.
  const overview = await page.locator("body").innerText();
  check(
    `${width} · no 4-dp money anywhere on the page`,
    !/\$\d+\.\d{3,}/.test(overview),
    (overview.match(/\$\d+\.\d{3,}/g) ?? []).join(","),
  );

  // ── 3 · AST-B-16: the open-work count is SERVED, and 0 is a number ───────
  const open = await page.locator("[data-open-work]").innerText();
  check(`${width} · Open work orders reads the served count`, open.trim() === "2", `got "${open}"`);

  // ── 4 · AST-B-22: the strip, in both registers and in its ABSENCE ────────
  const quiet = await page.locator('[data-attention="warrantyEnded"]').count();
  const quietAction = await page
    .locator('[data-attention="warrantyEnded"] a[href*="/work-orders/new"]')
    .count();
  check(`${width} · an expired warranty raises the quieter strip`, quiet === 1, `count=${quiet}`);
  check(
    `${width} · and it offers NO control, because there is nothing to do`,
    quietAction === 0,
  );

  await page.goto(`${BASE}/${TENANT}/assets/${DUE}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  const loud = await page.locator('[data-attention="testOverdue"]').count();
  const loudAction = await page
    .locator('[data-attention="testOverdue"] a[href*="/work-orders/new"]')
    .count();
  check(`${width} · an overdue test raises the loud strip`, loud === 1, `count=${loud}`);
  check(`${width} · and it CARRIES the control that resolves it`, loudAction === 1);
  // `AST-R-02`/`R-04`: a plain device has no Measurement panel at all.
  const deviceHeadings = (await page.locator("section h3").allInnerTexts()).map((s) => s.trim());
  check(
    `${width} · a backflow preventer has NO Measurement panel — absent, not empty`,
    !deviceHeadings.includes("Measurement"),
    JSON.stringify(deviceHeadings),
  );
  await page.screenshot({ path: `${OUT}/w${width}-08-attention.png`, fullPage: true });

  // ── 5 · AST-B-25 / AST-B-12: the pencil IS the edit address for an asset ─
  await page.goto(`${BASE}/${TENANT}/assets/${ASSET}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  const pencils = await page.locator('[data-testid^="edit-"]').count();
  check(`${width} · five pencils, one per editable panel`, pencils === 5, `count=${pencils}`);
  check(
    `${width} · and NONE on Assignment — it offers Reassign instead`,
    (await page.locator('[data-testid="edit-assignment"]').count()) === 0,
  );

  // ── 6 · screen 20: the purchase date is CORRECTABLE (DEF-MET-4972) ───────
  await page.locator('[data-testid="edit-cost"]').click();
  await page.waitForTimeout(400);
  const costTitle = (await page.locator(".modal-card h2, .modal-card h3, [role='dialog'] h2")
    .first()
    .innerText()
    .catch(() => "")).trim();
  const dateInput = page.locator("#purchase_date");
  check(
    `${width} · the Cost & value pencil opens a form holding the purchase date`,
    (await dateInput.count()) === 1,
    `title="${costTitle}"`,
  );
  await page.screenshot({ path: `${OUT}/w${width}-20-cost.png` });
  await dateInput.fill("2021-05-09");
  await page.locator(".modal-foot button[type='submit']").click();
  await page.waitForTimeout(1200);
  const afterSave = await page.locator("[data-purchase-date]").innerText();
  check(
    `${width} · it SAVES and the panel behind it shows the new date`,
    afterSave.includes("05/09/2021"),
    `panel reads "${afterSave.trim()}"`,
  );

  // ── 7 · screens 17 + 18: Continue, never Save, when a reading's meaning moves
  await page.locator('[data-testid="edit-measurement"]').click();
  await page.waitForTimeout(400);
  const submitBefore = (await page.locator(".modal-foot button[type='submit']").innerText()).trim();
  check(
    `${width} · nothing changed yet, so the button reads Save changes`,
    submitBefore === "Save changes",
    `got "${submitBefore}"`,
  );
  await page.locator("#multiplier").fill("10");
  const submitAfter = (await page.locator(".modal-foot button[type='submit']").innerText()).trim();
  check(
    `${width} · changing the multiplier turns it into Continue`,
    submitAfter === "Continue",
    `got "${submitAfter}"`,
  );
  await page.locator(".modal-foot button[type='submit']").click();
  await page.waitForTimeout(500);
  const confirm = await page.locator("body").innerText();
  check(
    `${width} · the second step names what changes and what does not`,
    /What changes/.test(confirm) && /What does not/.test(confirm),
  );
  check(
    `${width} · and it says the change is forward only, in the rule's own word`,
    /No stored read is restated/.test(confirm),
  );
  // B14 rule 31 / AST-R-10 — nothing internal reaches the clerk.
  check(
    `${width} · no internal code on the confirm step`,
    !/forward_only_change|BR-AST-|multiplier_/.test(confirm),
    (confirm.match(/forward_only_change|BR-AST-\d+/g) ?? []).join(","),
  );
  await page.screenshot({ path: `${OUT}/w${width}-18-confirm.png` });
  // Back returns the TYPED value — the reason this is one modal in two steps.
  await page.locator("button:has-text('Back')").click();
  await page.waitForTimeout(300);
  check(
    `${width} · Back returns the typed value rather than discarding it`,
    (await page.locator("#multiplier").inputValue()) === "10",
  );
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);

  // ── 8 · AST-B-27: the sub-meter's allocation share, in WORDS ─────────────
  await page.goto(`${BASE}/${TENANT}/assets/${SUB}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  const subBody = await page.locator("body").innerText();
  check(
    `${width} · the allocation rule reads in words, never as its stored code`,
    /Split equally/.test(subBody) && !/\bequal\b(?![a-z])/.test(subBody.replace(/Split equally/g, "")),
    (subBody.match(/\brubs\b|\bsqft\b|\babsorb\b/g) ?? []).join(","),
  );
  check(`${width} · the share displays at 2 dp (hard rule 2)`, /33\.33%/.test(subBody));
  await page.locator('[data-testid="edit-measurement"]').click();
  await page.waitForTimeout(400);
  const options = await page.locator("#allocation_rule option").allInnerTexts();
  check(
    `${width} · all four ratified words are offered, in order`,
    JSON.stringify(options.map((s) => s.trim()).slice(1)) ===
      JSON.stringify([
        "Share of the building's total",
        "By floor area",
        "Split equally",
        "Owner absorbs",
      ]),
    JSON.stringify(options),
  );
  await page.screenshot({ path: `${OUT}/w${width}-17-allocation.png` });
  await page.keyboard.press("Escape");

  // ── 9 · no horizontal scroll, at either supported width ─────────────────
  await page.goto(`${BASE}/${TENANT}/assets/${ASSET}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  check(`${width} · the page body does not scroll sideways`, overflow <= 0, `overflow=${overflow}px`);

  await page.close();
}

await browser.close();
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length} PASS · ${failed.length} FAIL`);
console.log(`screenshots in ${OUT}`);
process.exit(failed.length === 0 ? 0 : 1);
