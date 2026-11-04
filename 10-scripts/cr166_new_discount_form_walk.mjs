// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 round 2 task 4 — photograph the BUILT New discount
//          form in the same 14 states as images 05–18 of
//          `05-prototype/discounts-2026-10-03/images/`, at 1440 wide, and set
//          each beside its drawing (task brief: "Take screenshots side by side
//          with images 05–22"; 19–22 are the details page, task 6).
//          Shape copied from `cr165_new_tax_form_walk.mjs`.
// ───────────────────────────────────────────────────────
//
// Expects the stack `cr166_discounts_before_walk.mjs` names: the API on
// 127.0.0.1:8591 (scratch PostgreSQL 16, `migrate` + `seed_demo` +
// `load_sample_data --tenant brazosbend`) and the SPA built with
// `vite build --mode wolocal` served by `07-frontend/server.mjs` on 8592.
//
//   OUT=08-qa/discounts-2026-10-03/after node 10-scripts/cr166_new_discount_form_walk.mjs
//
// ⚠ `STUB_FORM_OPTIONS=1` answers `GET /discounts/form-options` IN THE
// BROWSER with the README's seeded values, for a run made before task 3's back
// end serves that route. The walk PRINTS whether it stubbed, so a photograph is
// never mistaken for proof that the server serves the lists. Nothing else is
// stubbed unless `STUB_SAVE=1`, which answers `POST /discounts` 201 in the
// browser so the saved state (image 18) can be photographed before task 3's
// server accepts `program_owner` / `eligibility` (today's server refuses them
// as `rating.unknown_field`). The walk PRINTS that too.
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8592";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr166-after";
const STUB = process.env.STUB_FORM_OPTIONS === "1";
const STUB_SAVE = process.env.STUB_SAVE === "1";
const DRAWINGS = new URL("../05-prototype/discounts-2026-10-03/images/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

/** The README's seeded values (point 3) — used only when STUB_FORM_OPTIONS=1. */
const README_OPTIONS = {
  program_owners: ["Billing", "Customer service", "Finance", "Conservation", "Community programs", "City or county agency", "State agency", "Nonprofit partner"].map((label) => ({ value: label.toLowerCase().replace(/[^a-z]+/g, "_"), label })),
  exclusivity_groups: ["None", "Low-income programs", "Age-based", "Payment method", "Government and municipal", "Military and veterans"].map((label) => ({ value: label === "None" ? "none" : label.toLowerCase().replace(/[^a-z]+/g, "_"), label })),
  eligibility: [
    ...["Everyone on the plan", "Autopay is on", "Paperless billing is on", "Government or municipal account"].map((label) => ({ value: label.toLowerCase().replace(/[^a-z0-9]+/g, "_"), label, checked_by: "system" })),
    ...["Age 65 or over", "Household income under a limit", "In a state assistance program", "Veteran or active military", "Person with a disability", "Medical equipment at home", "Nonprofit or place of worship"].map((label) => ({ value: label.toLowerCase().replace(/[^a-z0-9]+/g, "_"), label, checked_by: "proof" })),
  ],
  enrollment_modes: [{ value: "automatic", label: "Automatic" }, { value: "apply_and_approve", label: "Apply and approve" }],
  verification: [{ value: "annual_recertification", label: "Annual recertification" }, { value: "one_time_proof", label: "One-time proof" }, { value: "agency_file_monthly", label: "Agency file" }, { value: "automatic", label: "Automatic" }],
  lapse: [{ value: "notify_then_drop", label: "Notify, then drop" }, { value: "drop_silently", label: "Drop silently" }, { value: "never_expires", label: "Never expires" }],
  budget_periods: [{ value: "annual", label: "Annual" }, { value: "monthly", label: "Monthly" }, { value: "lifetime", label: "Lifetime" }],
  budget_out: [{ value: "suspend", label: "Suspend" }, { value: "refuse_new_enrolment", label: "Refuse new" }, { value: "continue_over_budget", label: "Continue" }],
  types: ["percentage", "fixed_amount", "rate_override", "charge_waiver", "usage_allowance"].map((value) => ({ value, label: value })),
  applies_to: ["whole_bill", "all_services", "specific_services", "one_service", "usage_only", "base_only", "named_codes"].map((value) => ({ value, label: value })),
};

function resolveChromium() {
  if (process.env.CHROME && existsSync(process.env.CHROME)) return process.env.CHROME;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 2000 } });
const say = (...parts) => console.log(...parts);

if (STUB) {
  await page.route("**/discounts/form-options", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(README_OPTIONS) }),
  );
}

/** Photograph the form, then set the photograph beside its drawing. */
async function shot(drawing, caption) {
  await page.waitForTimeout(700);
  const name = drawing.replace(/\.png$/, "");
  const after = `${OUT}/${name}.png`;
  await page.locator("[data-screen=new-discount]").screenshot({ path: after });
  const side = await browser.newPage({ viewport: { width: 2900, height: 400 } });
  const left = readFileSync(join(DRAWINGS, drawing)).toString("base64");
  const right = readFileSync(after).toString("base64");
  await side.setContent(
    `<body style="margin:0;display:flex;gap:20px;background:#ddd;align-items:flex-start;font:14px sans-serif">` +
      `<figure style="margin:0"><figcaption>Drawing ${drawing}</figcaption><img src="data:image/png;base64,${left}" width="1440"></figure>` +
      `<figure style="margin:0"><figcaption>Built — ${caption}</figcaption><img src="data:image/png;base64,${right}" width="1440"></figure></body>`,
  );
  await side.waitForTimeout(300);
  await side.screenshot({ path: `${OUT}/${name}-side-by-side.png`, fullPage: true });
  await side.close();
  say(`=== ${name}.png + ${name}-side-by-side.png — ${caption}`);
}

async function openForm() {
  await page.goto(`${BASE}/${TENANT}/plans-rates/discounts/new`, { waitUntil: "networkidle" });
  await page.waitForSelector("#discount-code", { timeout: 30000 });
  await page.waitForTimeout(800);
}

async function basics({ code = "SENIOR", label = "Senior discount", owner = "billing", funding = "Rate-payer funded", type = "percentage" } = {}) {
  await page.fill("#discount-code", code);
  await page.fill("#discount-label", label);
  await page.selectOption("#discount-owner", owner).catch(() => say("  (no program owner list)"));
  await page.fill("#discount-funding", funding);
  await page.selectOption("#discount-type", type).catch(() => say("  (no type list)"));
  await page.check("#discount-assistance", { force: true });
}

async function cont() {
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.waitForTimeout(700);
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
if (STUB_SAVE) {
  await page.route("**/discounts", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "stub", name: JSON.parse(route.request().postData() ?? "{}").name }) })
      : route.continue(),
  );
}
page.on("response", async (res) => {
  if (res.request().method() === "POST" && res.url().endsWith("/discounts")) {
    say("POST /discounts ->", res.status(), (await res.text().catch(() => "")).slice(0, 400));
    say("  body sent:", res.request().postData());
  }
});
say(STUB_SAVE ? "POST /discounts STUBBED in the browser" : "POST /discounts goes to the API");
say("signed in as", EMAIL, STUB ? "— form-options STUBBED in the browser (README values)" : "— form-options from the API");

const served = await page.evaluate(async (t) => (await fetch(`/api/${t}/discounts/form-options`, { credentials: "include" })).status, TENANT);
say("GET /discounts/form-options answered", served, STUB ? "(browser stub)" : "");

// 05 · percentage, Limits closed
await openForm();
await basics();
await page.fill("#discount-value", "15");
await shot("05-new-1-details-pct.png", "percentage, Limits closed");

// 06 · Limits open
await page.getByRole("button", { name: /Limits/ }).click();
await page.fill("#discount-stacking", "40");
await shot("06-new-1-limits-open.png", "Limits open");

// 07 · fixed amount, limits set
await openForm();
await basics({ code: "CAP", label: "CAP / low-income credit", owner: "customer_service", funding: "State grant", type: "fixed_amount" });
await page.fill("#discount-value", "25");
await page.getByRole("button", { name: /Limits/ }).click();
await page.fill("#discount-cap-bill", "25");
await page.fill("#discount-cap-year", "300");
await page.fill("#discount-cap-lifetime", "1200");
await page.fill("#discount-floor", "5");
await page.getByRole("button", { name: /Limits/ }).click();
await shot("07-new-1-details-fixed.png", "fixed amount, 4 limits set");

// 08–10 · the other three types
for (const [drawing, type, value] of [
  ["08-new-1-type-rate-override.png", "rate_override", null],
  ["09-new-1-type-charge-waiver.png", "charge_waiver", null],
  ["10-new-1-type-usage-allowance.png", "usage_allowance", "2"],
]) {
  await openForm();
  await basics({ type });
  if (value !== null) await page.fill("#discount-value", value);
  await shot(drawing, `type ${type}`);
}

// 11 · one service
await openForm();
await basics();
await page.fill("#discount-value", "15");
await page.selectOption("#discount-applies", "one_service");
await page.selectOption("#discount-service", { index: 1 }).catch(() => say("  (no services)"));
await shot("11-new-1-applies-service.png", "applies to one service");

// 12 · named charge codes, list open
await page.selectOption("#discount-applies", "named_codes");
await page.click("#discount-codes");
await shot("12-new-1-applies-codes.png", "named charge codes, list open");

// 13 · empty, Continue pressed
await openForm();
await cont();
await shot("13-new-1-errors.png", "empty, Continue pressed");

// 14 · 150 %
await basics();
await page.fill("#discount-value", "150");
await cont();
await shot("14-new-1-value-over-100.png", "150% refused");

// 15 · step 2 filled
await page.fill("#discount-value", "15");
await cont();
await page.selectOption("#discount-who", { label: "Age 65 or over" }).catch(() => say("  (no who-qualifies list)"));
await page.selectOption("#discount-enrollment", "apply_and_approve").catch(() => {});
await page.check("#discount-proof-before", { force: true }).catch(() => {});
await page.fill("#discount-recertify", "12");
await page.fill("#discount-notice", "30");
await page.fill("#discount-grace", "15");
await page.fill("#discount-starts", "2026-11-01");
say("  enrollment options:", JSON.stringify(await page.$$eval("#discount-enrollment option", (os) => os.map((o) => `${o.textContent}${o.disabled ? " [DISABLED]" : ""}`))));
await shot("15-new-2-eligibility.png", "Eligibility filled");

// 16 · who missing, end before start
await page.selectOption("#discount-who", "");
await page.fill("#discount-ends", "2026-01-01");
await cont();
await shot("16-new-2-errors.png", "who missing, ends before starts");

// 17 · Review
await page.selectOption("#discount-who", { label: "Age 65 or over" }).catch(() => {});
await page.fill("#discount-ends", "");
await cont();
await shot("17-new-3-review.png", "Review");

// 18 · saved
await page.getByRole("button", { name: "Save as draft", exact: true }).click();
await page.waitForTimeout(2000);
const savedTitle = await page.$eval("#discount-saved-title", (el) => el.textContent).catch(() => null);
say("SAVED:", savedTitle ?? "(not saved)");
if (savedTitle === null) say("  page says:", (await page.innerText("main")).slice(0, 600));
await shot("18-new-4-saved.png", savedTitle === null ? "save refused by the server" : "saved as a draft");

await browser.close();
