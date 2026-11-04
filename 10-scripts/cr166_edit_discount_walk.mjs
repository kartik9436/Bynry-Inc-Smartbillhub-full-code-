// ── Trace ──────────────────────────────────────────────
// Change:  CR-166-BRC10 round 3 task 7 — EDIT a discount, photographed in the
//          SAME ten states as images 27–36 of
//          `05-prototype/discounts-2026-10-03/images/`, each beside its drawing
//          (B14 rule 42), and the three saves made THROUGH THE SCREEN against
//          the real API on PostgreSQL.
// ───────────────────────────────────────────────────────
//
// Expects:
//   * API — `manage.py runserver 127.0.0.1:<port>` on a scratch PostgreSQL 16
//     database with `migrate` + `seed_demo` + `load_sample_data --tenant
//     brazosbend` (Dana, System Admin);
//   * SPA — `vite build --mode wolocal`, then
//     `PORT=<port> API_PROXY_TARGET=http://127.0.0.1:<api> node 07-frontend/server.mjs`.
//
//   BASE=http://127.0.0.1:5194 OUT=08-qa/discounts-2026-10-03/edit \
//     node 10-scripts/cr166_edit_discount_walk.mjs
//
// It stages three copies of the drawings' *Senior discount* (15 % off the
// subtotal before taxes from 08/01/2026, Age 65 or over, Apply and approve,
// annual recertification) through `POST /discounts` + submit + approve, one per
// choice, so each save starts from the drawn discount: A gets a new
// verification in place, B gets 12 % from 01/01/2027, C is corrected to 1.5 %.
// It prints the three codes so the database can be read afterwards
// (`cr166_edit_one_version_per_date.py`).
import { existsSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:5194";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr166-edit-after";
const DRAWINGS = new URL("../05-prototype/discounts-2026-10-03/images/", import.meta.url).pathname;
mkdirSync(OUT, { recursive: true });

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
const page = await browser.newPage({ viewport: { width: 1440, height: 1700 } });
const say = (...parts) => console.log(...parts);

/** Photograph the page at 1440, check it is not blank, set it beside its drawing. */
async function shot(file, caption, drawing = file) {
  await page.waitForTimeout(800);
  const name = file.replace(/\.png$/, "");
  const after = `${OUT}/${name}.png`;
  await page.screenshot({ path: after, fullPage: true });
  const text = (await page.locator("[data-screen=edit-discount]").innerText()).trim();
  if (text.length < 40) throw new Error(`${name}: the screen is blank (${text.length} characters)`);
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
  say(`\n=== ${name}.png + side-by-side — ${caption} (${text.length} characters of text)`);
  say(text.replace(/\n+/g, " | ").slice(0, 900));
}

async function api(method, path, body) {
  return page.evaluate(
    async ([m, p, b]) => {
      const res = await fetch(`/api/${p}`, {
        method: m,
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: b === undefined ? undefined : JSON.stringify(b),
      });
      let data = null;
      try {
        data = await res.json();
      } catch {
        data = null;
      }
      return { status: res.status, data };
    },
    [method, `${TENANT}/${path}`, body],
  );
}
const press = (name) => page.getByRole("button", { name, exact: true }).click();

// ── sign in ─────────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say("signed in as", EMAIL);

// ── stage the drawn discount three times ────────────────────────────────────
const stamp = Date.now() % 100000;
async function stage(code) {
  const made = await api("POST", "discounts", {
    code,
    name: "Senior discount",
    program_owner: "billing",
    funding_source: "Rate-payer funded",
    report_in_assistance_filing: true,
    discount_type: "percentage",
    value: "15",
    applies_to: "whole_bill",
    exclusivity_group: "none",
    eligibility: "age_65_or_over",
    proof_required: true,
    proof_before_first_reduction: true,
    enrolment_mode: "apply_and_approve",
    verification_method: "annual_recertification",
    recertification_months: 12,
    recertification_notice_days: 30,
    recertification_grace_days: 15,
    lapse_behaviour: "notify_then_drop",
    effective_from: "2026-08-01",
    budget_period: "annual",
    exhaustion_behaviour: "suspend",
  });
  if (made.status >= 400) throw new Error(`stage ${code}: ${made.status} ${JSON.stringify(made.data)}`);
  const id = made.data.id;
  for (const act of ["submit", "approve"]) {
    const res = await api("POST", `discounts/${id}/${act}`, {});
    if (res.status >= 400) throw new Error(`${act} ${code}: ${res.status} ${JSON.stringify(res.data)}`);
  }
  return { id, code };
}
const A = await stage(`SRA${stamp}`);
const B = await stage(`SRB${stamp}`);
const C = await stage(`SRC${stamp}`);
say("staged:", JSON.stringify({ A, B, C }));
const edit = (who, mode) => `${BASE}/${TENANT}/plans-rates/discounts/${who.id}/edit?change=${mode}`;

// ── A · Name and details (images 27–30) ─────────────────────────────────────
await page.goto(edit(A, "info"), { waitUntil: "networkidle" });
await page.getByLabel(/^Bill line label/).waitFor();
await shot("27-edit-info-1-details.png", "Name and details · Details, value and limits locked");
await press("Continue");
await page.getByRole("combobox", { name: /^Who qualifies/ }).waitFor();
await shot("28-edit-info-2-eligibility.png", "Name and details · Eligibility, start locked");
await page.getByLabel(/^Verification/).selectOption("one_time_proof");
await press("Continue");
await page.locator("[data-discount-step=edit-review]").waitFor();
await shot("29-edit-info-3-review.png", "Name and details · Review, before → after, v1 in place");
await press("Save changes");
await page.locator("[data-discount-edit-saved]").waitFor();
await shot("30-edit-saved.png", "saved");

// ── B · New value from a date (images 31–33) ────────────────────────────────
await page.goto(edit(B, "change"), { waitUntil: "networkidle" });
const valueB = page.getByRole("textbox", { name: /^Percent off/ });
await valueB.waitFor();
await valueB.fill("12");
await page.getByLabel(/^New value starts/).fill("2027-01-01");
await shot("31-edit-change-1-value.png", "New value · 12% from 01/01/2027");
await page.getByLabel(/^New value starts/).fill("2026-07-01");
await press("Continue");
await page.getByText("Must be after 08/01/2026.").waitFor();
await shot("32-edit-change-1-error.png", "New value · start not after today's start");
await page.getByLabel(/^New value starts/).fill("2027-01-01");
await press("Continue");
await page.locator("[data-discount-step=edit-review]").waitFor();
await shot("33-edit-change-2-review.png", "New value · Review, v1 ends the day before, v2 new");
await press("Save new value");
await page.locator("[data-discount-edit-saved]").waitFor();
await shot("33b-edit-change-saved.png", "New value · saved (not drawn; set beside image 30)", "30-edit-saved.png");

// ── C · Fix a mistake (images 34–36) ────────────────────────────────────────
await page.goto(edit(C, "correct"), { waitUntil: "networkidle" });
const valueC = page.getByRole("textbox", { name: /^Percent off/ });
await valueC.waitFor();
await valueC.fill("1.5");
await page.getByLabel(/Why it was wrong/).fill("Typed 15 instead of 1.5.");
await shot("34-edit-correct-1-fix.png", "Fix a mistake · value, dates locked, reason");
await page.getByLabel(/Why it was wrong/).fill("");
await press("Continue");
await page.getByText("Enter the reason.").waitFor();
await shot("35-edit-correct-1-error.png", "Fix a mistake · reason missing");
await page.getByLabel(/Why it was wrong/).fill("Typed 15 instead of 1.5.");
await press("Continue");
await page.locator("[data-discount-step=edit-review]").waitFor();
await shot("36-edit-correct-2-review.png", "Fix a mistake · Review, superseded and kept");
await press("Save correction");
await page.locator("[data-discount-edit-saved]").waitFor();
await shot("36b-edit-correct-saved.png", "Fix a mistake · saved (not drawn; set beside image 30)", "30-edit-saved.png");

// ── read back what the three saves wrote ────────────────────────────────────
for (const who of [A, B, C]) {
  const row = await api("GET", `discounts/${who.id}`);
  const versions = await api("GET", `discounts/${who.id}/versions`);
  say(
    `\nread back ${who.code}: status ${row.data.status} · v${row.data.version} · ${row.data.value_display} · ` +
      `verification ${row.data.verification} · scheduled_next ${JSON.stringify(row.data.scheduled_next)}`,
  );
  for (const v of versions.data?.results ?? versions.data ?? []) {
    say(`  v${v.version_no} ${v.status} ${v.value_display} corrects=${v.corrects ? "yes" : "no"} superseded_by=${v.superseded_by ? "yes" : "no"}`);
  }
}
say(`\ncodes for the database read: ${A.code} ${B.code} ${C.code}`);
await browser.close();
