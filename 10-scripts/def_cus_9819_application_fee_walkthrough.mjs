// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-9819 (PO request 2026-10-06) — the application fee is added
//          to every new request automatically; $0.00 reads "Nothing to collect".
// Runs:    W_BASE=http://127.0.0.1:5619 W_OUT=<dir> node 10-scripts/def_cus_9819_application_fee_walkthrough.mjs
//          against a booted stack (runserver + 07-frontend/server.mjs) on the
//          matrix world (tenant `mvimatrix`, Marcus = System Admin), at 1440.
// ───────────────────────────────────────────────────────
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { randomUUID } from "node:crypto";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");
const BASE = process.env.W_BASE ?? "http://127.0.0.1:5619";
const TENANT = process.env.W_TENANT ?? "mvimatrix";
const OUT = process.env.W_OUT ?? "/tmp/walk-9819";
const PASSWORD = "S3cure!passw0rd"; // the matrix world's lane fixture credential
mkdirSync(OUT, { recursive: true });
let fails = 0;
const check = (ok, name, detail = "") => {
  if (!ok) fails += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? " — " + detail : ""}`);
};

async function call(page, method, path, body) {
  return page.evaluate(
    async ({ method, url, body }) => {
      const res = await fetch(url, {
        method,
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ?? "",
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return { status: res.status, body: await res.json().catch(() => null) };
    },
    { method, url: `/api/${TENANT}${path}`, body },
  );
}

const start = new Date(Date.now() + 21 * 86400000).toISOString().slice(0, 10);
async function portalDraft(page, token, name) {
  return call(page, "PUT", `/portal/public/applications/${token}`, {
    address_as_given: "410 Packard St",
    service_codes: ["water"],
    applicant_kind: "person",
    first_name: name.split(" ")[0],
    last_name: name.split(" ")[1],
    email: "kyle.mark@example.test",
    phone: "(734) 555-0190",
    requested_start: start,
  });
}
async function checkAndSend(page, token) {
  await page.goto(`${BASE}/${TENANT}/portal/start-service/${token}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-screen="CWP-009"]', { timeout: 30000 });
  await page.waitForSelector('[data-kv="application_fee"] dd', { timeout: 30000 });
  return (await page.locator('[data-kv="application_fee"] dd').textContent())?.trim();
}
async function requestPage(page, id) {
  await page.goto(`${BASE}/${TENANT}/requests/${id}`, { waitUntil: "domcontentloaded" });
  await page.waitForSelector('[data-panel-name="fees"]', { timeout: 30000 });
  await page.waitForLoadState("networkidle").catch(() => undefined);
  await page.waitForTimeout(400);
  return page.locator('[data-panel-name="fees"]');
}

const browser = await chromium.launch({
  executablePath: process.env.CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
const admin = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const page = await admin.newPage();
page.setDefaultTimeout(25000);
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", "marcus@cedarford.example");
await page.fill("#signin-password", PASSWORD);
await Promise.all([page.waitForURL((u) => !u.pathname.endsWith("/signin")), page.click('button[type="submit"]')]);

// 1 · the utility marks its application fee — APP-FEE $10.00, one-time, Application fee: Yes.
const made = await call(page, "POST", "/charges", {
  code: "APP-FEE",
  name: "Application fee",
  charge_type: "one_time",
  amount_rule: "flat",
  amount: "10.00",
  kind: "other",
  is_application_fee: true,
});
if (made.status === 201 || made.status === 200) check(true, "APP-FEE $10.00 saved as the application fee");
else console.log(`  INFO  APP-FEE already exists (${made.status}) — a re-run over its own leftovers`);
let chargeId = made.body?.id;
if (!chargeId) {
  // A re-run over its own leftovers: the code exists — put it back to $10.00.
  const listed = await call(page, "GET", "/charges?per=500");
  const rows = listed.body?.results ?? listed.body?.items ?? listed.body ?? [];
  chargeId = rows.find((row) => row.code === "APP-FEE")?.id;
  const back = await call(page, "PATCH", `/charges/${chargeId}`, { amount: "10.00", is_application_fee: true, reason: "Walk re-run at ten dollars" });
  check(back.status === 200, "re-run: APP-FEE back at $10.00", String(back.status));
}
const second = await call(page, "POST", "/charges", {
  code: "APP-FEE2",
  name: "Second fee",
  charge_type: "one_time",
  amount_rule: "flat",
  amount: "5.00",
  kind: "other",
  is_application_fee: true,
});
check(second.status === 422 || second.status === 400, "a second application fee is refused by name", JSON.stringify(second.body?.error?.message_key ?? second.body?.message_key ?? second.status));
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${chargeId}`, { waitUntil: "domcontentloaded" });
await page.waitForLoadState("networkidle").catch(() => undefined);
await page.waitForTimeout(800);
const bills = page.locator("section, div").filter({ has: page.getByRole("heading", { name: "How it bills" }) }).last();
await bills.scrollIntoViewIfNeeded();
const billsText = (await bills.textContent()) ?? "";
check(/Application fee\s*Yes/.test(billsText), "charge-code details · How it bills reads Application fee Yes");
await page.screenshot({ path: join(OUT, "1-charge-code-app-fee.png") });
await page.goto(`${BASE}/${TENANT}/plans-rates/charge-codes/${chargeId}/edit`, { waitUntil: "domcontentloaded" });
await page.waitForSelector("#cc-application-fee", { timeout: 30000 });
check((await page.locator("#cc-application-fee").inputValue()) === "yes", "the charge-code form asks Application fee, and it reads Yes");
await page.locator("#cc-application-fee").scrollIntoViewIfNeeded();
await page.screenshot({ path: join(OUT, "1b-charge-code-form-application-fee.png") });

// 2 · the portal shows it before Send, and the application arrives with it.
const guest = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const gp = await guest.newPage();
gp.setDefaultTimeout(25000);
await gp.goto(`${BASE}/${TENANT}/portal`, { waitUntil: "domcontentloaded" });
const token = randomUUID();
const saved = await portalDraft(gp, token, "Kyle Mark");
check(saved.status === 200, "Kyle Mark's draft saved", String(saved.status));
const shown = await checkAndSend(gp, token);
check(shown === "$10.00", "Check and send — Application fee $10.00", shown);
await gp.screenshot({ path: join(OUT, "2-portal-check-and-send-10.png"), fullPage: true });
const sent = await call(gp, "POST", `/portal/public/applications/${token}/submit`, { paperless: false });
check(sent.status === 200 || sent.status === 201, "Kyle Mark's application sent", `${sent.status} ${sent.body?.reference}`);

const kyle = await requestPage(page, sent.body.request_id);
const kyleText = await kyle.textContent();
check(kyleText.includes("Application fee $10.00. Not taken."), "Kyle Mark's request arrives with Application fee $10.00 on it");
check((await kyle.getByRole("button", { name: "Record what was handed over" }).count()) === 1, "and the clerk can take it");
await page.screenshot({ path: join(OUT, "3-request-auto-fee-10.png"), fullPage: true });

// 3 · a utility that charges nothing — the same code at $0.00.
const zeroed = await call(page, "PATCH", `/charges/${chargeId}`, { amount: "0.00", reason: "We charge no application fee" });
check(zeroed.status === 200, "APP-FEE re-priced to $0.00 (a $0.00 price saves)", String(zeroed.status));
const staff = await call(page, "POST", "/service-requests", {
  channel: "counter",
  applicant_kind: "person",
  applicant_name: "Rivera, Ana",
  applicant_phone: "734-555-0144",
  address_as_given: "12 Maple Ave",
  what_they_said: "New service",
});
check(staff.status === 201 || staff.status === 200, "a counter request is opened", String(staff.status));
const staffId = staff.body?.header?.id ?? staff.body?.id;
const submitted = await call(page, "POST", `/service-requests/${staffId}/submit`, {});
check(submitted.status === 200, "and submitted", String(submitted.status));
const zero = await requestPage(page, staffId);
check((await zero.locator('[data-fee-collect="nothing"]').count()) === 1, "it reads Nothing to collect.");
check((await zero.getByRole("button", { name: "Record what was handed over" }).count()) === 0, "and draws no collect button");
await zero.getByText("Application fees").first().click();
await page.waitForTimeout(400);
check((await zero.getByRole("button", { name: /Waive this fee/ }).count()) >= 1, "the $0.00 line can still be waived");
await page.screenshot({ path: join(OUT, "4-request-zero-nothing-to-collect.png"), fullPage: true });

const token0 = randomUUID();
await portalDraft(gp, token0, "Lee Park");
const shown0 = await checkAndSend(gp, token0);
check(shown0 === "Nothing to pay", "Check and send at $0.00 — Nothing to pay", shown0);
await gp.screenshot({ path: join(OUT, "5-portal-check-and-send-zero.png"), fullPage: true });

const version = (await page.locator("body").textContent()).match(/v?2\.\d+\.\d+/)?.[0];
console.log(`\n${fails === 0 ? "ALL PASS" : `${fails} FAIL`} · build ${version ?? "?"}`);
await browser.close();
process.exit(fails === 0 ? 0 : 1);
