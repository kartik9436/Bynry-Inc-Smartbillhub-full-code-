#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-9822 (N1) · 9823 (N3) · 9824 (N4) · 9825 (N5) · 9826 (N6)
//          · 9827 (N7) · 9828 (N2) — the PO's NCT-01 table, 2026-10-06.
// What:    a portal-style request (Kyle Mark, Haustin Towers 2, Apt-12, a photo
//          ID) is sent from the portal, the clerk approves it into a new
//          connection, and New Connect opens with every answer arriving. Step 1
//          and steps 2/3 are photographed at 1440.
// Usage:   W_BASE=http://127.0.0.1:5828 W_OUT=<dir> node 10-scripts/nct01_new_connect_po_fixes_walk.mjs
//          (a local stack only — never the live site).
// ───────────────────────────────────────────────────────
import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.W_BASE ?? "http://127.0.0.1:5828").replace(/\/$/, "");
const TENANT = process.env.W_TENANT ?? "brazosbend";
const OUT = process.env.W_OUT ?? "/tmp/nct01-walk";
const EMAIL = process.env.W_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.W_PASSWORD ?? "S3cure!passw0rd";
mkdirSync(OUT, { recursive: true });

let fails = 0;
const check = (ok, name, detail = "") => {
  if (!ok) fails += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? " — " + String(detail).slice(0, 300) : ""}`);
};

function chrome() {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  const found = readdirSync(root)
    .filter((n) => n.startsWith("chromium"))
    .flatMap((n) => ["chrome-linux/chrome", "chrome-linux64/chrome"].map((s) => join(root, n, s)))
    .filter(existsSync);
  return found[0];
}

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

async function upload(page, path, name) {
  return page.evaluate(
    async ({ url, name }) => {
      const form = new FormData();
      const bytes = new TextEncoder().encode("%PDF-1.7\n1 0 obj\n<< /Title (Photo ID) >>\n" + "P".repeat(1500) + "\n%%EOF");
      form.append("file", new File([bytes], name, { type: "application/pdf" }));
      const res = await fetch(url, {
        method: "POST",
        credentials: "include",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] ?? "",
        },
        body: form,
      });
      return { status: res.status, body: await res.json().catch(() => null) };
    },
    { url: `/api/${TENANT}${path}`, name },
  );
}

async function shoot(page, name, selector) {
  await page.waitForTimeout(400);
  const file = join(OUT, `${name}.png`);
  if (selector) {
    await page.locator(selector).first().screenshot({ path: file });
  } else {
    await page.screenshot({ path: file, fullPage: true });
  }
  console.log(`      shot ${file}`);
}

const browser = await chromium.launch({ executablePath: process.env.CHROME ?? chrome(), args: ["--no-sandbox"] });

// ── 1 · Kyle Mark applies on the portal ─────────────────────────────────────
const guest = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const gp = await guest.newPage();
gp.setDefaultTimeout(25000);
await gp.goto(`${BASE}/${TENANT}/portal`, { waitUntil: "domcontentloaded" });
const token = randomUUID();
const start = new Date(Date.now() + 21 * 86400000).toISOString().slice(0, 10);
const saved = await call(gp, "PUT", `/portal/public/applications/${token}`, {
  address_as_given: "Haustin Towers 2",
  address_unit_as_given: "Apt-12",
  address_city_as_given: "Austin",
  address_postal_code_as_given: "78701",
  service_codes: ["water"],
  applicant_kind: "person",
  first_name: "Kyle",
  last_name: "Mark",
  email: "kyle.mark@example.test",
  phone: "(512) 555-0128",
  date_of_birth: "1990-03-14",
  requested_start: start,
  account_type_code: "residential",
  account_subtype_code: "multi_family",
  mailing_same_as_service: false,
  mailing_line1: "PO Box 4471",
  mailing_city: "Austin",
  mailing_state: "TX",
  mailing_postal_code: "78767",
});
check(saved.status === 200 || saved.status === 201, "Kyle Mark's application saved", `${saved.status} ${JSON.stringify(saved.body).slice(0, 200)}`);
const doc = await upload(gp, `/portal/public/applications/${token}/documents`, "kyle-photo-id.pdf");
check(doc.status === 200 || doc.status === 201, "the photo ID is attached on the portal", `${doc.status}`);
const sent = await call(gp, "POST", `/portal/public/applications/${token}/submit`, { paperless: false });
check(sent.status === 200 || sent.status === 201, "Kyle Mark's application sent", `${sent.status} ${sent.body?.reference ?? ""}`);
const requestId = sent.body?.request_id;

// ── 2 · the clerk ─────────────────────────────────────────────────────────
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await ctx.newPage();
page.setDefaultTimeout(30000);
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 }).catch(() => undefined);

// What a clerk adds on the request before deciding: the co-applicant Kyle
// named on the phone, and his language.
const patched = await call(page, "PATCH", `/service-requests/${requestId}`, {
  co_applicant_name: "Maya Mark",
  co_applicant_email: "maya@example.test",
  co_applicant_phone: "(512) 555-0129",
  preferred_language: "es-MX",
});
check(patched.status === 200, "co-applicant and language recorded on the request", `${patched.status} ${JSON.stringify(patched.body).slice(0, 200)}`);
// The SSN Kyle read out at the counter, typed on the request by the clerk.
const ssnPatched = await call(page, "PATCH", `/service-requests/${requestId}`, { ssn: "412-55-1234" });
console.log(`      SSN on the request ${ssnPatched.status}`);
const linked = await call(page, "POST", `/service-requests/${requestId}/customer-link`, { customer_id: null });
console.log(`      customer-link (no prior customer) ${linked.status}`);

// ── 3 · Approve, through the request page ──────────────────────────────────
await page.goto(`${BASE}/${TENANT}/requests/${requestId}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.getByRole("button", { name: "Approve", exact: true }).first().click();
await page.waitForTimeout(800);
await page.locator('[data-outcome-picker] button', { hasText: /new connection/i }).first().click().catch(() => undefined);
await page.waitForTimeout(800);
await shoot(page, "0-approve-modal");
const submit = page.locator('[role="dialog"] button').last();
await submit.click();
await page.waitForURL(/connections\/new\?build=/, { timeout: 30000 }).catch(() => undefined);
check(/connections\/new\?build=/.test(page.url()), "Approve opens New Connect on the raised build", page.url());
await page.waitForTimeout(3000);

// ── 4 · step 1 ─────────────────────────────────────────────────────────────
const val = (sel) => page.locator(sel).inputValue().catch(() => "");
check((await val("#nc_owner_name")) === "Kyle Mark", "N2 owner name arrived", await val("#nc_owner_name"));
check((await val("#nc_owner_email")) === "kyle.mark@example.test", "N2 email arrived", await val("#nc_owner_email"));
check((await val("#nc_owner_category")) === "residential", "N2 category arrived", await val("#nc_owner_category"));
const subOptions = await page.$$eval("#nc_owner_subcategory option", (ns) => ns.filter((o) => o.value !== "").map((o) => o.textContent));
check(!subOptions.includes("Construction temporary") && subOptions.includes("Multi-family"), "N1 sub-category offers Residential's sub-types", subOptions.join(", "));
check((await val("#nc_owner_subcategory")) === "multi_family", "N2 sub-category arrived", await val("#nc_owner_subcategory"));
check((await page.locator('[data-from-request="owner"]').count()) === 1, "N2 Owner is marked from the request");
const ssnType = await page.locator("#nc_ssn").getAttribute("type");
check(ssnType === "password", "N6 SSN masked by default", ssnType);
check((await page.locator('[data-reveal="nc_ssn"]').count()) === 1, "N6 Show beside SSN");
if (ssnPatched.status === 200) {
  const govText = (await page.locator('[data-step-content="gov-id"]').innerText()).replace(/\s+/g, " ");
  check(govText.includes("Provided on the request · ends 1234"), "N2 the request's SSN is acknowledged as its last four, box empty", govText);
  check((await val("#nc_ssn")) === "", "N2 the SSN is never copied into the box");
  await shoot(page, "1b0-step1-govid-from-request", '[data-step-content="gov-id"]');
}
await page.fill("#nc_ssn", "123-45-6789");
await page.locator('[data-reveal="nc_ssn"]').click();
check((await page.locator("#nc_ssn").getAttribute("type")) === "text", "N6 Show reveals the SSN");
await page.locator('[data-reveal="nc_driving_licence"]').scrollIntoViewIfNeeded();
await shoot(page, "1a-step1-owner-govid-show", '[data-step-content="owner"]');
await shoot(page, "1b-step1-govid-revealed", '[data-step-content="gov-id"]');
await page.locator('[data-reveal="nc_ssn"]').click();
const coCard = page.locator('[data-step-content="co-applicant"]');
// The two cards are closed and show their one-line answer (CR-164-BRC10 item
// 10); the build arrives after the first paint, so they are opened here.
check((await coCard.innerText()).includes("Maya Mark"), "N2 the closed co-applicant card reads Maya Mark");
for (const card of ["co-applicant", "mailing"]) {
  const toggle = page.locator(`[data-step-content="${card}"] [aria-expanded="false"]`).first();
  if ((await toggle.count()) > 0) await toggle.click();
}
await page.waitForTimeout(400);
check((await coCard.locator("#nc_co_owner_name").inputValue().catch(() => "")) === "Maya Mark", "N2 co-applicant arrived", await coCard.innerText().catch(() => ""));
check((await coCard.locator("#nc_co_owner_kind, #nc_co_owner_category, #nc_co_owner_subcategory, [name=\"nc_co_party_kind\"]").count()) === 0, "N7 co-applicant has no owner type, category, sub-category or person/company");
check((await coCard.locator('[data-reveal="nc_co_ssn"]').count()) === 1, "N6 co-applicant SSN has Show/Hide");
await shoot(page, "1c-step1-co-applicant-short-form", '[data-step-content="co-applicant"]');
const mailing = page.locator('[data-step-content="mailing"]');
check((await mailing.locator("#nc_mail_address").inputValue().catch(() => "")) === "PO Box 4471", "N2 mailing address arrived");
const docs = page.locator('[data-step-content="owner-documents"]');
const docsText = (await docs.innerText()).replace(/\s+/g, " ");
check(docsText.includes("kyle-photo-id.pdf"), "N2 the request's photo ID is listed as already brought in", docsText);
check((await docs.locator('[data-from-request="documents"]').count()) === 1, "N2 Documents marked from the request");
check((await docs.getByRole("button", { name: "Add another document" }).count()) === 0, "N3 no Add another document");
check((await docs.getByRole("button", { name: "Attach a file" }).count()) === 1, "N3 one Attach a file");
// N4 — attach a file in the draft.
await docs.locator('input[type="file"]').setInputFiles({ name: "lease.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 lease") });
await docs.getByRole("button", { name: "Attach a file" }).click();
await page.waitForTimeout(600);
const byCells = await docs.locator("[data-doc-by]").allInnerTexts();
check(byCells.some((cell) => /Dana/.test(cell)), "N4 Uploaded by names the clerk for the draft file", byCells.join(" | "));
// N5 — View on the draft file and on the request's file.
const eyes = docs.getByRole("button", { name: "Open" });
const eyeCount = await eyes.count();
check(eyeCount >= 2, "N5 View on both rows", String(eyeCount));
const [popup1] = await Promise.all([ctx.waitForEvent("page", { timeout: 8000 }).catch(() => null), eyes.nth(0).click()]);
check(popup1 !== null && /\/service-requests\/.+\/documents\/.+\/content\?as=view/.test(popup1.url()), "N5 the request's photo ID opens through the request", popup1?.url() ?? "no tab");
if (popup1) await popup1.close();
const [popup2] = await Promise.all([ctx.waitForEvent("page", { timeout: 8000 }).catch(() => null), eyes.nth(1).click()]);
check(popup2 !== null && popup2.url().startsWith("blob:"), "N5 the draft file opens from the browser", popup2?.url() ?? "no tab");
if (popup2) await popup2.close();
await shoot(page, "1d-step1-documents", '[data-step-content="owner-documents"]');
await shoot(page, "1-step1-full");

// ── 5 · steps 2 and 3 ──────────────────────────────────────────────────────
const forward = page.locator('[data-wizard="actions"] button').last();
await forward.click();
await page.waitForTimeout(2500);
const address = page.locator('[data-step-content="address"]');
const addressText = (await address.innerText().catch(() => "")).replace(/\s+/g, " ");
const values = await address.locator("input").evaluateAll((ns) => ns.map((n) => n.value));
check(values.includes("Haustin Towers 2") && values.includes("Austin") && values.includes("78701"), "N2 step 2 street, town and ZIP arrived", values.join(" | "));
check((await address.locator('[data-from-request="address"]').count()) === 1, "N2 step 2 marked from the request", addressText.slice(0, 120));
await shoot(page, "2-step2-address", '[data-step-content="address"]');
await shoot(page, "2-step2-full");
// Step 3 — the clerk answers what the request could not (the property type and
// the plan), and the unit Kyle named is waiting.
const pick = async (sel, prefer) => {
  const opts = await page.$$eval(`${sel} option`, (ns) => ns.filter((o) => !o.disabled && o.value !== "").map((o) => o.value)).catch(() => []);
  if (opts.length > 0) await page.selectOption(sel, opts.includes(prefer) ? prefer : opts[0]);
};
await pick("#nc_premise_type", "apartment_complex");
await page.waitForTimeout(500);
await pick("#nc_plan");
await page.waitForTimeout(800);
await forward.click();
await page.waitForTimeout(2500);
const step3 = (await page.locator("main").innerText().catch(() => "")).replace(/\s+/g, " ");
const unitValues = await page.locator("input").evaluateAll((ns) => ns.map((n) => n.value));
check(/Apt 12/.test(step3) || (unitValues.includes("Apt") && unitValues.includes("12")), "N2 step 3 holds Kyle's unit (Apt 12)", unitValues.filter((v) => v !== "").slice(0, 12).join(" | "));
await shoot(page, "3-step3-units");
console.log(`\n${fails === 0 ? "ALL PASS" : `${fails} FAIL`}`);
await browser.close();
process.exit(fails === 0 ? 0 : 1);
