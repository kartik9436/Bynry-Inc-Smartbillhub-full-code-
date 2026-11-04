// ── Trace ──────────────────────────────────────────────
// Change:  PO reports 2026-09-23 on `New request` (REQ-03) and the request
//          detail (REQ-02), v2.344.0 — the billing address as a US address,
//          fees as a table on step 5 and on the review, the requested start
//          reading `—` on the review AND on the detail, and `Capture another`
//          leaving the clerk on the confirmation. Lane REQ-FIX.
// Rules:   `22-product-maintenance-process.md` step 0 (REPRODUCE before reading
//          code) and its proof step · CLAUDE.md hard-won law 6
// Screens: REQ-03.3 · REQ-03.5 · REQ-03.6 · REQ-03.sent · REQ-02
// ───────────────────────────────────────────────────────
//
// ONE SCRIPT FOR BEFORE AND AFTER. It prints what the screen SAYS and what
// the server STORED, and a `●` beside every line that is still the defect.
// Run it on the code before the fix (every `●` present) and after (none).
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   eval "$(10-scripts/proof-db.sh clone reqfix --export)"
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
//      python manage.py runserver 127.0.0.1:8388 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8389 \
//      API_PROXY_TARGET=http://127.0.0.1:8388 node server.mjs)
//   BASE=http://127.0.0.1:8389 node 10-scripts/po20260923_req_fix_walk.mjs
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8389";
const TENANT = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots/reqfix";
mkdirSync(SHOTS, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const dir of readdirSync("/opt/pw-browsers")) {
    if (!dir.startsWith("chromium")) continue;
    for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
      const c = join("/opt/pw-browsers", dir, sub);
      if (existsSync(c)) return c;
    }
  }
  throw new Error("no chromium");
}

let defects = 0;
function check(ok, message) {
  if (!ok) defects += 1;
  console.log(`    ${ok ? "✓" : "●"} ${message}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 1400 } })).newPage();
page.setDefaultTimeout(20000);
const posted = [];
page.on("request", (r) => {
  const u = r.url();
  if (u.includes("/api/") && r.method() !== "GET") {
    posted.push({ method: r.method(), url: u.replace(BASE, ""), body: r.postData() ?? "" });
  }
});
async function main() {
  return (await page.locator("main").innerText().catch(() => "")).replace(/\s+\n/g, "\n");
}
async function cont() {
  await page.locator('button:has-text("Continue")').last().click();
  await page.waitForTimeout(1800);
}

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ── STEP 1 ────────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/requests/new`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  await page.fill("#applicant_name", "Rivera, Ana");
  await page.fill("#applicant_email", "ana.rivera@example.com");
  await page.fill("#applicant_phone", "8555555");
  const dob = page.locator("#date_of_birth");
  if ((await dob.count()) > 0) await dob.fill("1984-03-02");
  // An SSN, so the review's SSN row — and anything printed beside it — shows.
  const ssn = page.locator("#ssn");
  if ((await ssn.count()) > 0 && (await ssn.isEnabled())) await ssn.fill("123-45-5236");
  await cont();

  // ── STEP 2 ────────────────────────────────────────────────────────────────
  const category = page.locator("#account_type_code");
  if ((await category.count()) > 0) await category.selectOption("residential").catch(() => {});
  await page.waitForTimeout(500);
  for (let i = 0; i < 2; i += 1) {
    const add = page.locator("[data-chip-add='capture-services']");
    const values = await add.locator("option").evaluateAll((os) => os.map((o) => o.value).filter(Boolean));
    await add.selectOption(values[0]);
    await page.waitForTimeout(300);
  }
  const connection = await page.locator("#requested_start").inputValue();
  const firstStart = await page.locator("[data-table='service-starts'] input").first().inputValue();
  console.log(`\n  step 2 · connection date ${connection} · first service box shows ${firstStart}`);
  await cont();

  // ── STEP 3 ────────────────────────────────────────────────────────────────
  await page.fill("#address_as_given", "212 Balcones Drive");
  const city = page.locator("#address_city_as_given");
  if ((await city.count()) > 0) await city.fill("Austin");
  await page.locator("label[for=billing_address_same], label:has(#billing_address_same)").first().click();
  await page.waitForTimeout(300);
  const structured = (await page.locator("#billing_line1, #billing_city, #billing_postal_code").count()) === 3;
  check(structured, `step 3 · billing address is a US address (street · unit · city · state · ZIP)`);
  if (structured) {
    await page.fill("#billing_line1", "PO Box 4471");
    await page.fill("#billing_line2", "Suite 200");
    await page.fill("#billing_city", "Round Rock");
    await page.fill("#billing_postal_code", "78664-1234");
    const state = page.locator("#billing_state");
    await state.click();
    await state.fill("Tex");
    await page.locator("#billing_state-opt-TX").click();
  } else {
    await page.fill("#billing_address_as_given", "PO Box 4471, Round Rock TX 78664");
  }
  const star = await page.locator("[data-billing-address] [aria-required='true'], [data-billing-address] abbr").count();
  check(star === 0, `step 3 · no required marker on the billing address (${star})`);
  await page.screenshot({ path: `${SHOTS}/step3.png`, fullPage: true });
  await cont();
  await cont(); // documents

  // ── STEP 5 ────────────────────────────────────────────────────────────────
  const onFive = await main();
  const table = (await page.locator("[data-editable-table='application-fees']").count()) > 0;
  check(table, "step 5 · fees are a table (EditableTable)");
  if (table) {
    // `+ Add a fee ▾` — three picks; the third is then REMOVED with its ✕.
    for (let i = 0; i < 3; i += 1) {
      const picker = page.locator("#application_fee_code");
      await picker.waitFor({ state: "visible" });
      const codes = await page
        .locator("[id^='application_fee_code-opt-']")
        .evaluateAll((os) => os.map((o) => o.id.replace("application_fee_code-opt-", "")));
      await picker.click();
      await picker.fill(codes[i].slice(0, 2));
      await page.locator(`[id='application_fee_code-opt-${codes[i]}']`).click();
      await page.waitForTimeout(1800);
    }
    await page.locator("[data-editable-table='application-fees'] [data-remove-row='3']").click();
    await page.waitForTimeout(1800);
    const rows = await page.locator("[data-editable-table='application-fees'] tbody tr").count();
    const total = await page.locator("[data-editable-table='application-fees'] [data-fee-total]").innerText();
    console.log(`  step 5 · ${rows} fee rows after one removal · Total ${total}`);
    check(rows === 2 && /\$/.test(total), "step 5 · add ×3, remove ×1 → two rows and a Total with its currency");
    const offered = await page.locator("#fee_method option").evaluateAll((os) => os.map((o) => o.value).filter(Boolean));
    check(!offered.includes("waive"), `step 5 · 'Waive' is not a tender (${offered.join(", ")})`);
  }
  check(
    !/keeps the person who takes the money/.test(onFive),
    "step 5 · the 25-word rationale under 'When is it being paid?' is gone",
  );
  await page.selectOption("#fee_method", "cash").catch(() => {});
  const five = await main();
  console.log(`  step 5 reads:\n${five.split("\n").slice(0, 40).map((l) => `      ${l}`).join("\n")}`);
  await page.screenshot({ path: `${SHOTS}/step5.png`, fullPage: true });
  await cont();

  // ── STEP 6 · REVIEW ───────────────────────────────────────────────────────
  const review = await main();
  await page.screenshot({ path: `${SHOTS}/step6.png`, fullPage: true });
  const reviewStarts = await page
    .locator("[data-services-table='review'] tbody tr td:nth-child(2)")
    .allInnerTexts();
  console.log(`\n  review · REQUESTED START column: ${JSON.stringify(reviewStarts)}`);
  check(reviewStarts.length > 0 && reviewStarts.every((v) => v.trim() !== "—"), "review · requested start shows the date");
  check(!/1984-03-02/.test(review), "review · date of birth in the tenant's date format");
  check(!/\b8555555\b/.test(review), "review · phone is formatted");
  check(!/stored encrypted/i.test(review), "review · no 'stored encrypted' rationale");
  check((await page.locator("[data-editable-table='review-fees']").count()) > 0, "review · fees are a table");
  check(!/Documents gate this, not money/.test(review), "review · no rationale sentence under the fees");
  const billingLine = await page.locator("[data-review-billing]").innerText().catch(() => "");
  console.log(`  review · billing address: ${billingLine}`);
  check(/PO Box 4471.*Suite 200.*Round Rock, TX 78664-1234/.test(billingLine), "review · billing address written from its five parts");

  // ── SUBMIT ────────────────────────────────────────────────────────────────
  await page.locator('button:has-text("Submit the request")').first().click();
  await page.waitForTimeout(3500);
  const sent = await main();
  await page.screenshot({ path: `${SHOTS}/sent.png`, fullPage: true });
  console.log(`\n  confirmation reads:\n${sent.split("\n").map((l) => `      ${l}`).join("\n")}`);
  const requestNo = await page.locator("[data-request-no]").first().getAttribute("data-request-no");
  const requestId = new URL(page.url()).searchParams.get("request");
  // `\b` sits between `$` and the digit too, so a boundary would match the
  // FIXED text; the figure must not follow a `$`.
  check(!/(^|[^$\d])\d+\.\d{2} collected of/.test(sent), "confirmation · money carries its currency");
  check(!/\bcash\b/.test(sent), "confirmation · the method is its label, not the code");
  check(!/none is waiting/.test(sent), "confirmation · the acknowledgement is the request's own state");
  check((await page.locator("[data-editable-table='sent-fees']").count()) > 0, "confirmation · the fee lines are the same table");

  // ── CAPTURE ANOTHER ───────────────────────────────────────────────────────
  await page.locator('button:has-text("Capture another")').click();
  await page.waitForTimeout(2000);
  const after = await main();
  const stillSent = (await page.locator("[data-screen='REQ-03.sent']").count()) > 0;
  const nameBox = page.locator("#applicant_name");
  const name = (await nameBox.count()) > 0 ? await nameBox.inputValue() : "(no box)";
  console.log(`\n  after Capture another · url ${page.url().replace(BASE, "")} · name box '${name}'`);
  check(!stillSent && name === "" && !after.includes(requestNo ?? "\u0000"), "Capture another · a blank step 1");
  await page.screenshot({ path: `${SHOTS}/capture-another.png`, fullPage: true });

  // ── DETAIL ────────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/requests/${requestId}`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(3000);
  const detail = await main();
  await page.screenshot({ path: `${SHOTS}/detail.png`, fullPage: true });
  const detailStarts = await page.locator("[data-services-table] tbody tr td:nth-child(2)").allInnerTexts();
  console.log(`\n  detail · REQUESTED START column: ${JSON.stringify(detailStarts)}`);
  check(detailStarts.length > 0 && detailStarts.every((v) => v.trim() !== "—"), "detail · requested start shows the date");
  check(/Round Rock/.test(detail), "detail · the billing address is shown");
  check(!/\b8555555\b/.test(detail), "detail · phone is formatted");
  check(!/stored encrypted/i.test(detail), "detail · no 'stored encrypted' rationale");

  console.log(`\n  POSTs/PATCHes carrying the billing address or services:`);
  for (const c of posted.filter((p) => /billing|services/.test(p.body))) {
    console.log(`      ${c.method} ${c.url}\n        ${c.body.slice(0, 600)}`);
  }
  console.log(`\n  request ${requestNo} (${requestId}) · ${defects} defect line(s) still present`);
} catch (e) {
  console.log(`  stopped: ${e.message}`);
  await page.screenshot({ path: `${SHOTS}/ERROR.png`, fullPage: true }).catch(() => {});
} finally {
  await browser.close();
}
