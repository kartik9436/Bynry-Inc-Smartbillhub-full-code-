// Walk of the three fixes of 2026-10-14 — DEF-PAY-10157 (cash at a counter
// clears on receipt), DEF-REP-10158 (Owner summary shows a balance moved to the
// owner and foots to the books), DEF-REP-10159 (Receivables by service names
// the owner, not the departed tenant). Drives the screens only; the ledger
// figures are read back separately (README). Env: WEB, TENANT, OUT, OWNER_ID,
// CLOCK (the browser's day), STEPS=counter,reports.
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB || "http://127.0.0.1:8097";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "05-prototype/walk-fixes-payments-reports-2026-10-14";
const ACCOUNT_NO = process.env.ACCOUNT || "AC-2026-00001";
const OWNER_ID = process.env.OWNER_ID || "";
const STEPS = (process.env.STEPS || "counter,reports").split(",");
mkdirSync(OUT, { recursive: true });

const exe = process.env.CHROME || "/opt/pw-browsers/chromium";
const browser = await chromium.launch({
  executablePath: existsSync(exe) ? exe : undefined,
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
if (process.env.CLOCK) await page.clock.setSystemTime(new Date(process.env.CLOCK));
let failed = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failed += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
};
const shot = async (name) => {
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  console.log(`  shot ${name}.png`);
};
const body = () => page.evaluate(() => document.body.innerText);
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));

try {
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(1500);

  if (STEPS.includes("counter")) {
    console.log("DEF-PAY-10157 — cash into a counter");
    if (process.env.COUNTER) {
      // A till already open today (one per clerk): walk into it.
      await page.goto(`${WEB}/${T}/payments/counter/${process.env.COUNTER}`, { waitUntil: "networkidle" });
    } else {
      await page.goto(`${WEB}/${T}/payments/counter?start=1`, { waitUntil: "networkidle" });
      await page.waitForTimeout(1500);
      await page.selectOption("#service_centre", { index: 1 }).catch(() => undefined);
      await page.fill("#opening_float", "200.00");
      await page.locator('.modal-card button:has-text("Start"), [role="dialog"] button:has-text("Start")').last().click();
    }
    await page.waitForTimeout(2500);
    const code = new URL(page.url()).pathname.split("/").pop();
    check("a counter is open", /^CTR-/.test(code), code);
    await shot("1-01-counter-open");
    await page.locator('a:has-text("Record payment"), button:has-text("Record payment")').first().click();
    await page.waitForTimeout(2500);
    await page.fill("#account_id", ACCOUNT_NO);
    await page.waitForTimeout(2500);
    await page.locator('[role="option"]', { hasText: ACCOUNT_NO }).first().click();
    await page.waitForTimeout(1200);
    await page.fill("#amount", "25.00");
    const methods = await page.$$eval("#method option", (o) => o.map((x) => x.value));
    await page.selectOption("#method", "check");
    await page.waitForTimeout(800);
    const cheque = await body();
    check("a cheque leaves Clearing date blank", (await page.inputValue("#cleared_at")) === "");
    check("…and the Check box says it meets no bill", cheque.includes("It meets no bill until cleared."));
    await shot("1-02-cheque-not-cleared");
    await page.selectOption("#method", methods.find((m) => m === "cash") || "cash");
    await page.waitForTimeout(800);
    const posted = await page.inputValue("#posted_at");
    const cleared = await page.inputValue("#cleared_at");
    const form = await body();
    check("cash proposes the posting date as the clearing date", cleared !== "" && cleared === posted, `${posted} / ${cleared}`);
    check("the Check box: $25.00 goes to this account, oldest bills first",
      form.includes("$25.00 goes to this account.") && form.includes("It meets the oldest bills first."));
    check("the form names the till", form.includes(code));
    await shot("1-03-cash-clears-on-receipt");
    const [resp] = await Promise.all([
      page.waitForResponse((r) => r.request().method() === "POST" && /\/payments$/.test(new URL(r.url()).pathname)),
      page.locator('button[type="submit"]').last().click(),
    ]);
    const created = await resp.json().catch(() => ({}));
    check("the payment is recorded CLEARED", created.status === "cleared", `${created.payment_no} ${created.status}`);
    await page.waitForTimeout(2500);
    await shot("1-04-payment-recorded");
    console.log(`  PAYMENT ${created.payment_no} ${created.status} counter ${code}`);
  }

  if (STEPS.includes("reports")) {
    console.log("DEF-REP-10159 — receivables over 90 days by service, as at 2027-03-31");
    await page.goto(`${WEB}/${T}/reports/receivables-over-90-by-service?f.to=2027-03-31`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2500);
    await shot("3-01-receivables-over-90-by-service");
    // The debtor, per account × service: the builder's Receivables subject,
    // sorted by account number so both accounts land together.
    await page.goto(`${WEB}/${T}/reports/custom/new`, { waitUntil: "networkidle" });
    await page.waitForTimeout(2000);
    await page.locator("#report-edit-dataset").selectOption("receivables");
    await page.waitForTimeout(2500);
    for (const label of ["Account", "Service", "Over 90 days", "Total"]) {
      const box = page.locator(`input[type="checkbox"][aria-label="${label}"]`).first();
      if ((await box.count()) > 0 && !(await box.isChecked())) await box.check();
    }
    await page.waitForTimeout(1500);
    await page.getByRole("button", { name: "Save as" }).click();
    await page.locator("input#name").fill("Who owes what, by service (walk)");
    await page.waitForTimeout(500);
    const group = page.locator("select#group");
    if ((await group.count()) > 0) await group.selectOption({ label: "Receivables" }).catch(() => undefined);
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: "Save", exact: true }).click();
    await page.waitForTimeout(3000);
    const seg = new URL(page.url()).pathname.split("/").filter(Boolean);
    const keySeg = seg[seg.indexOf("reports") + 1];
    await page.goto(`${WEB}/${T}/reports/${keySeg}?f.to=2027-03-31&sort=account_no&dir=desc`,
      { waitUntil: "networkidle" });
    await page.waitForTimeout(3000);
    const rows = await page.$$eval("table tbody tr", (trs) => trs.map((tr) => tr.innerText.replace(/\s+/g, " ")));
    const tenantRows = rows.filter((r) => r.includes("AC-2026-00044"));
    const ownerRows = rows.filter((r) => r.includes("AC-2026-00053"));
    check("the departed tenant AC-2026-00044 is on no row", tenantRows.length === 0, `${rows.length} rows read`);
    check("the owner AC-2026-00053 owes the tenant's services", ownerRows.length >= 4, ownerRows.join(" / "));
    if (ownerRows.length) {
      await page.locator("table tbody tr", { hasText: "AC-2026-00053" }).first().scrollIntoViewIfNeeded();
    }
    await page.screenshot({ path: `${OUT}/3-02-receivables-builder-owner-rows.png`, fullPage: false });
    console.log("  shot 3-02-receivables-builder-owner-rows.png");
    console.log("DEF-REP-10158 — owner summary, Mill Pond, 10/01–10/31");
    await page.goto(
      `${WEB}/${T}/reports/owner_summary?f.from=2026-10-01&f.to=2026-10-31&subject_id=${OWNER_ID}`,
      { waitUntil: "networkidle" },
    );
    await page.waitForSelector("table tbody tr");
    await page.waitForTimeout(1500);
    const text = await body();
    check("the column Moved from tenants is drawn", /moved from tenants/i.test(text));
    check("the tile In the books is drawn", /in the books/i.test(text));
    check("the move $25.45 is on the property's row", text.includes("$25.45"));
    check("no 'differs from the books' sentence when it foots", !text.includes("The total differs from the books."));
    check("no database id on screen", !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i.test(text));
    await shot("2-01-owner-summary-foots");
    await page.goto(
      `${WEB}/${T}/reports/owner_summary?f.from=2026-12-01&f.to=2026-12-31&subject_id=${OWNER_ID}`,
      { waitUntil: "networkidle" },
    );
    await page.waitForSelector("table tbody tr");
    await page.waitForTimeout(1500);
    const later = await body();
    check("a period with nothing moved says it differs from the books",
      later.includes("The total differs from the books."));
    await shot("2-02-owner-summary-december-differs");
  }
} catch (error) {
  failed += 1;
  console.log(`  threw: ${error.message}`);
  await shot("zz-where-it-stopped").catch(() => undefined);
} finally {
  await browser.close();
  console.log(failed === 0 ? "WALK PASSED" : `WALK: ${failed} FAILED`);
}
