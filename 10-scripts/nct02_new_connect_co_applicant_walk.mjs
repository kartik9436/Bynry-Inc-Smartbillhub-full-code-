#!/usr/bin/env node
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-9830 (PO ruling 2026-10-06 (a): the co-applicant is saved
//          as a co-owner, only her name required) · DEF-CUS-9834 (a portal
//          file names the applicant) · DEF-CUS-9835 (State is the utility's
//          own) · DEF-CUS-9836 (This plan: Taxes and Discounts summaries) ·
//          DEF-CUS-9837 (the account page lists its co-owners).
// What:    Kyle Mark applies on the portal for Haustin Towers 2, Apt-12, with a
//          photo ID attached ON ITS REQUIREMENT (as the real portal sends it —
//          NCT-01's walk sent none, which is why its photograph read "Anything
//          else"). The clerk approves it into a new connection; on New Connect
//          step 1 adds Maria Mark as co-applicant with ONLY her name; step 2's
//          State, Taxes and Discounts are read; the build is created; the
//          owner's account page names Maria. Photographed at 1440.
// Usage:   W_BASE=http://127.0.0.1:5838 W_OUT=<dir> node 10-scripts/nct02_new_connect_co_applicant_walk.mjs
//          (a local stack only — never the live site).
// ───────────────────────────────────────────────────────
import { randomUUID } from "node:crypto";
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = (process.env.W_BASE ?? "http://127.0.0.1:5838").replace(/\/$/, "");
const TENANT = process.env.W_TENANT ?? "brazosbend";
const OUT = process.env.W_OUT ?? "/tmp/nct02-walk";
const EMAIL = process.env.W_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.W_PASSWORD ?? "S3cure!passw0rd";
mkdirSync(OUT, { recursive: true });

let fails = 0;
const check = (ok, name, detail = "") => {
  if (!ok) fails += 1;
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? " — " + String(detail).slice(0, 300) : ""}`);
};
const note = (text) => console.log(`        ${text}`);

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

/** The real portal attaches each file ON a requirement (`DEF-CWP-9167`). */
async function upload(page, path, name, requirement) {
  return page.evaluate(
    async ({ url, name, requirement }) => {
      const form = new FormData();
      const bytes = new TextEncoder().encode("%PDF-1.7\n1 0 obj\n<< /Title (Photo ID) >>\n" + "P".repeat(1500) + "\n%%EOF");
      form.append("file", new File([bytes], name, { type: "application/pdf" }));
      form.append("requirement", requirement);
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
    { url: `/api/${TENANT}${path}`, name, requirement },
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

// ── 1 · Kyle Mark applies on the portal (no state: the portal asks none) ────
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
});
check(saved.status === 200 || saved.status === 201, "Kyle Mark's application saved", `${saved.status} ${JSON.stringify(saved.body).slice(0, 200)}`);
const doc = await upload(gp, `/portal/public/applications/${token}/documents`, "kyle-photo-id.pdf", "photo_id");
check(doc.status === 200 || doc.status === 201, "the photo ID is attached on its requirement", `${doc.status} ${JSON.stringify(doc.body).slice(0, 160)}`);
const sent = await call(gp, "POST", `/portal/public/applications/${token}/submit`, { paperless: false });
check(sent.status === 200 || sent.status === 201, "Kyle Mark's application sent", `${sent.status} ${sent.body?.reference ?? ""}`);
const requestId = sent.body?.request_id;

// ── 2 · the clerk approves it into a new connection ───────────────────────
const ctx = await browser.newContext({ viewport: { width: 1440, height: 1200 } });
const page = await ctx.newPage();
page.setDefaultTimeout(30000);
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 }).catch(() => undefined);
await call(page, "POST", `/service-requests/${requestId}/customer-link`, { customer_id: null });
await page.goto(`${BASE}/${TENANT}/requests/${requestId}`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.getByRole("button", { name: "Approve", exact: true }).first().click();
await page.waitForTimeout(800);
await page.locator("[data-outcome-picker] button", { hasText: /new connection/i }).first().click().catch(() => undefined);
await page.waitForTimeout(800);
await page.locator('[role="dialog"] button').last().click();
await page.waitForURL(/connections\/new\?build=/, { timeout: 30000 }).catch(() => undefined);
check(/connections\/new\?build=/.test(page.url()), "Approve opens New Connect on the raised build", page.url());
const buildId = new URL(page.url()).searchParams.get("build");
await page.waitForTimeout(3000);

// ── 3 · step 1 ─────────────────────────────────────────────────────────────
const val = (sel) => page.locator(sel).inputValue().catch(() => "");
check((await val("#nc_owner_name")) === "Kyle Mark", "owner name arrived", await val("#nc_owner_name"));
await page.fill("#nc_ssn", "412-55-1234");
const docs = page.locator('[data-step-content="owner-documents"]');
const docsText = (await docs.innerText()).replace(/\s+/g, " ");
check(docsText.includes("Proof of identity"), "DEF-CUS-9834 the photo ID reads its requirement's type (Proof of identity), not Anything else", docsText);
const byCells = await docs.locator("[data-doc-by]").allInnerTexts();
check(byCells.some((cell) => cell.includes("Kyle Mark (applicant)")), "DEF-CUS-9834 Uploaded by reads Kyle Mark (applicant)", byCells.join(" | "));
await shoot(page, "1-step1-documents-applicant", '[data-step-content="owner-documents"]');

const coCard = page.locator('[data-step-content="co-applicant"]');
const coToggle = coCard.locator('[aria-expanded="false"]').first();
if ((await coToggle.count()) > 0) await coToggle.click();
await coCard.getByRole("button", { name: /add a co-applicant/i }).first().click();
await page.waitForTimeout(400);
await coCard.locator("#nc_co_owner_name").fill("Maria Mark");
const asterisks = await coCard.locator("input[required], input[aria-required='true']").evaluateAll((ns) => ns.map((n) => n.id));
check(asterisks.length === 1 && asterisks[0] === "nc_co_owner_name", "DEF-CUS-9830 only Full name is required for the co-applicant", asterisks.join(", "));
await shoot(page, "1-step1-co-applicant-name-only", '[data-step-content="co-applicant"]');

const forward = () => page.locator('[data-wizard="actions"] button').last();
await forward().click();
await page.waitForTimeout(2500);

// ── 4 · step 2 ─────────────────────────────────────────────────────────────
check((await val("#nc_state")) === "TX", "DEF-CUS-9835 State is the utility's own (TX) for a portal request", await val("#nc_state"));
await shoot(page, "2-step2-address-state", '[data-step-content="address"]');
const pick = async (sel, prefer) => {
  const opts = await page.$$eval(`${sel} option`, (ns) => ns.filter((o) => !o.disabled && o.value !== "").map((o) => ({ v: o.value, t: o.textContent }))).catch(() => []);
  if (opts.length === 0) return null;
  const chosen = opts.find((o) => prefer && (o.v === prefer || (o.t ?? "").includes(prefer))) ?? opts[0];
  await page.selectOption(sel, chosen.v);
  return chosen.t;
};
note(`premise type: ${await pick("#nc_premise_type", "apartment_complex")}`);
await page.waitForTimeout(500);
note(`plan: ${await pick("#nc_plan", "Residential")}`);
await page.waitForTimeout(2500);
const block = page.locator("[data-this-plan]").first();
const summaryOf = async (title) =>
  ((await block.locator("button", { hasText: new RegExp(`^${title}`) }).first().innerText().catch(() => "")) || "").replace(/\s+/g, " ");
const taxes = await summaryOf("Taxes");
const discounts = await summaryOf("Discounts");
check(/^Taxes \d+ · \d+\.\d{2}% total/.test(taxes), "DEF-CUS-9836 Taxes summary reads <count> · <total>% total", taxes);
check(discounts !== "" && !/\b(PAPERLESS|SENIOR|AUTOPAY|MILITARY|MUNICIPAL)\b/.test(discounts), "DEF-CUS-9836 Discounts summary reads names, not codes", discounts);
await block.locator("button", { hasText: /^Taxes/ }).first().click().catch(() => undefined);
await block.locator("button", { hasText: /^Discounts/ }).first().click().catch(() => undefined);
await page.waitForTimeout(500);
const discountTable = (await block.locator('[data-this-plan-part="discounts"]').innerText().catch(() => "")).replace(/\s+/g, " ");
check(discountTable !== "" && !/\b(PAPERLESS|SENIOR|AUTOPAY)\b/.test(discountTable), "DEF-CUS-9836 the Discounts table reads names", discountTable.slice(0, 200));
await shoot(page, "2-step2-this-plan-taxes-discounts", "[data-this-plan]");
// A plan WITH discounts, so the names are seen on screen (the residential plan
// binds none in this world); then back to the residential plan for Create.
const plans = await page.$$eval("#nc_plan option", (ns) => ns.filter((o) => o.value !== "" && !o.disabled).map((o) => o.value));
const residential = await page.locator("#nc_plan").inputValue();
let seenDiscounts = false;
for (const value of plans) {
  await page.selectOption("#nc_plan", value);
  await page.waitForTimeout(2000);
  const words = await summaryOf("Discounts");
  if (/^Discounts [1-9]/.test(words)) {
    check(!/\b(PAPERLESS|SENIOR|AUTOPAY|MILITARY|MUNICIPAL|CAP) /.test(words), "DEF-CUS-9836 Discounts summary on a plan with discounts reads names", words);
    await block.locator("button", { hasText: /^Discounts/ }).first().click().catch(() => undefined);
    await block.locator("button", { hasText: /^Taxes/ }).first().click().catch(() => undefined);
    await page.waitForTimeout(500);
    const table = (await block.locator('[data-this-plan-part="discounts"]').innerText().catch(() => "")).replace(/\s+/g, " ");
    check(!/\b(PAPERLESS|SENIOR|AUTOPAY)\b/.test(table), "DEF-CUS-9836 its Discounts table reads names", table.slice(0, 200));
    note(`plan with discounts: Taxes "${await summaryOf("Taxes")}" · ${words}`);
    await shoot(page, "2-step2-this-plan-with-discounts", "[data-this-plan]");
    seenDiscounts = true;
    break;
  }
}
check(seenDiscounts, "a plan with discounts was found to photograph");
await page.selectOption("#nc_plan", residential);
await page.waitForTimeout(2000);
await forward().click();
await page.waitForTimeout(2500);

// ── 5 · steps 3, 4 and 5 — through to Create ──────────────────────────────
for (const step of ["units", "charges"]) {
  const h1 = await page.locator("h1, h2").first().innerText().catch(() => "");
  note(`step ${step}: ${h1}`);
  if (step === "units") {
    // The clerk's own answers for the build: a size for each service, then
    // Apply to all (the step's own instruction).
    const empties = await page.$$eval("main select", (ns) =>
      ns
        .map((n, i) => ({ i, v: n.value, opts: [...n.options].filter((o) => o.value !== "" && !o.disabled).length }))
        .filter((x) => x.v === "" && x.opts > 0)
        .map((x) => x.i),
    );
    for (const index of empties) {
      const sel = page.locator("main select").nth(index);
      const first = await sel.evaluate((n) => [...n.options].find((o) => o.value !== "" && !o.disabled)?.value ?? "");
      if (first) await sel.selectOption(first).catch(() => undefined);
    }
    await page.getByRole("button", { name: "Apply to all" }).first().click().catch(() => undefined);
    await page.waitForTimeout(800);
  }
  await shoot(page, `3-${step}`);
  const button = forward();
  if (await button.isDisabled().catch(() => false)) note(`${step}: forward disabled`);
  await button.click();
  await page.waitForTimeout(2500);
}
await shoot(page, "5-review");
const createButton = forward();
note(`review button: ${await createButton.innerText().catch(() => "")}`);
await createButton.click();
await page.waitForTimeout(6000);
const after = (await page.locator("main").innerText().catch(() => "")).replace(/\s+/g, " ");
note(`after Create: ${page.url()} :: ${after.slice(0, 200)}`);
await shoot(page, "5-after-create");

// ── 6 · the owner's account names Maria ───────────────────────────────────
const detail = await call(page, "GET", `/connections/${buildId}`);
const accountNo = detail.body?.owner_account_no ?? null;
check(accountNo !== null, "the build opened Kyle's account", `${detail.status} ${accountNo}`);
const found = await call(page, "GET", `/accounts?search=${encodeURIComponent(accountNo ?? "")}`);
const account = (found.body?.results ?? []).find((row) => row.account_no === accountNo);
check(account !== undefined, "the account is found by its number", JSON.stringify(found.body ?? {}).slice(0, 160));
if (account) {
  const read = await call(page, "GET", `/accounts/${account.id}`);
  const coOwners = read.body?.co_owners ?? [];
  check(coOwners.length === 1 && coOwners[0].full_name === "Maria Mark", "DEF-CUS-9830 Maria is a co-owner on Kyle's new account", JSON.stringify(coOwners));
  check(coOwners.length === 1 && coOwners[0].email === null && coOwners[0].phone === null, "her blank email and phone stayed blank");
  check(!JSON.stringify(read.body).includes("ssn_last4\":\"") , "no identifier is served on the account read");
  await page.goto(`${BASE}/${TENANT}/accounts/${account.id}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(2500);
  const group = page.locator('[data-overview-group="co-applicant"]');
  const groupText = (await group.innerText().catch(() => "")).replace(/\s+/g, " ");
  check(groupText.includes("Maria Mark"), "DEF-CUS-9837 the account page's Co-applicant group names Maria Mark", groupText);
  await group.scrollIntoViewIfNeeded().catch(() => undefined);
  await shoot(page, "6-account-co-applicant", '[data-overview-group="co-applicant"]');
  await shoot(page, "6-account-page");
}
console.log(`\n${fails === 0 ? "ALL PASS" : `${fails} FAIL`}`);
await browser.close();
process.exit(fails === 0 ? 0 : 1);
