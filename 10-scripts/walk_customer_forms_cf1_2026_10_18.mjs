// Walk of lane CF-1 (2026-10-18) — the shared customer form on Move-in, the
// staff service request and New connect, built from the drawing set
// `04-docs/05-modules/03-customers/wireframes/customer-forms-2026-10-18/`.
// Env: WEB (SPA origin), TENANT, OUT, EMAIL, PASSWORD, STEP (which scenario).
// Each STEP drives the real screens, prints what it saw, and leaves
// screenshots in OUT. Data a scenario needs is set up on the private copy
// beforehand (the README says how).
import { existsSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const WEB = process.env.WEB || "http://127.0.0.1:8112";
const T = process.env.TENANT || "brazosbend";
const OUT = process.env.OUT || "05-prototype/walk-customer-forms-cf1-2026-10-18";
const STEP = process.env.STEP || "request";
mkdirSync(OUT, { recursive: true });

const exe = process.env.CHROME || "/opt/pw-browsers/chromium";
const browser = await chromium.launch({
  executablePath: existsSync(exe) ? exe : undefined,
  args: ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: Number(process.env.VH || 4200) } });
page.on("pageerror", (e) => console.log(`  PAGE ERROR ${e.message}`));
page.on("response", async (r) => {
  if (r.url().includes("/api/") && r.status() >= 400 && !r.url().includes("page-policy")) {
    let body = "";
    try {
      body = (await r.text()).slice(0, 400);
    } catch {
      body = "";
    }
    console.log(`  HTTP ${r.status()} ${r.request().method()} ${r.url().replace(/^.*\/api\//, "/api/")} ${body}`);
  }
});

const shot = async (name, full = true) => {
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: full });
  console.log(`  shot ${name}.png`);
};
const api = async (method, path, body) =>
  page.evaluate(
    async ({ method, path, body, T }) => {
      const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
      const r = await fetch(`/api/${T}${path}`, {
        method,
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: body ? JSON.stringify(body) : undefined,
      });
      let data = null;
      try {
        data = await r.json();
      } catch {
        data = null;
      }
      return { status: r.status, data };
    },
    { method, path, body, T },
  );

async function signIn() {
  await page.goto(`${WEB}/${T}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", process.env.EMAIL || "dana@brazosbendutilities.com");
  await page.fill("#signin-password", process.env.PASSWORD || "S3cure!passw0rd");
  await Promise.all([
    page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 90000 }),
    page.click('button[type="submit"]'),
  ]);
  await page.waitForTimeout(1500);
}

async function typeDate(id, mmddyyyy) {
  const box = page.locator(`#${id}`);
  await box.click();
  await box.fill(mmddyyyy);
  await box.press("Tab");
}

async function pickState(id, typed, code) {
  await page.fill(`#${id}`, typed);
  await page.click(`#${id}-opt-${code}`);
}

// ── A · staff service request, step 1: every field, then Continue ──────────
async function request() {
  await page.goto(`${WEB}/${T}/requests/new?step=1`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-request-customer-form]", { timeout: 60000 });
  await page.waitForSelector('#account_type option[value="residential"]', { state: "attached" });
  await page.selectOption("#account_type", "residential");
  await page.fill("#full_name", "Maria Lopez");
  await page.fill("#email", "maria.lopez@example.com");
  await page.fill("#phone", "(734) 555-0182");
  await typeDate("dob", "04/12/1988");
  await page.selectOption("#contact_by", "text");
  await page.fill("#ssn", "123-45-4471");
  await page.fill("#driving_licence", "MI L-552-118-903");
  await page.fill("#gov_id_last4", "9001");
  await page.check("#co_owner_enabled", { force: true });
  await page.fill("#co_owner_0_full_name", "Daniel Lopez");
  await page.selectOption("#co_owner_0_relationship", "spouse");
  await page.selectOption("#co_owner_0_responsible_for_bills", "yes");
  await page.fill("#co_owner_0_phone", "(734) 555-0144");
  await page.fill("#co_owner_0_email", "dan.lopez@example.com");
  await typeDate("co_owner_0_date_of_birth", "09/30/1986");
  await page.fill("#co_owner_0_ssn", "987-65-2208");
  const same = page.locator("#mailing_same");
  if (await same.isChecked()) await same.uncheck({ force: true });
  await page.fill("#mailing_line1", "PO Box 2210");
  await page.fill("#mailing_city", "Ypsilanti");
  await pickState("mailing_state", "Mich", "MI");
  await page.fill("#mailing_postal_code", "48197");
  await page.check("#request_prefs_on", { force: true });
  await page.selectOption("#paperless", "on");
  await page.selectOption("#sms_reminders", "on");
  await shot("request-step1-filled");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForTimeout(3000);
  const url = new URL(page.url());
  const id = url.searchParams.get("id") || url.pathname.split("/").pop();
  console.log(`  after Continue: ${page.url()}`);
  const list = await api("GET", "/service-requests?search=Maria%20Lopez");
  const row = (list.data?.results || [])[0];
  console.log(`  request row: ${row ? row.request_no : "none"} (id param ${id})`);
  if (row) {
    const detail = await api("GET", `/service-requests/${row.id}`);
    const a = detail.data?.applicant || {};
    console.log(
      "  SAVED:",
      JSON.stringify({
        name: a.name,
        email: a.email,
        phone: a.phone,
        dob: a.date_of_birth,
        contact_by: a.contact_by,
        gov_id_last4: a.gov_id_last4,
        ssn_last4: a.identifier?.ssn_last4,
        licence_last4: a.identifier?.drivers_licence_last4,
        co_applicants: a.co_applicants,
        mailing: a.mailing_address,
        preferences: a.preferences,
      }),
    );
  }
}

// ── A2 · a business request: the Tax ID is sent and saved ───────────────────
async function requestBusiness() {
  await page.goto(`${WEB}/${T}/requests/new?step=1`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-request-customer-form]", { timeout: 60000 });
  await page.locator("[data-customer-panel=who]").getByText("Company", { exact: true }).click();
  await page.waitForSelector('#account_type option[value="commercial"]', { state: "attached" });
  await page.selectOption("#account_type", "commercial");
  await page.fill("#full_name", "Kestrel Bakery LLC");
  await page.fill("#tax_id", "47-1234567");
  await shot("request-business-step1");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForTimeout(3000);
  const list = await api("GET", "/service-requests?search=Kestrel");
  const row = (list.data?.results || [])[0];
  const detail = row ? await api("GET", `/service-requests/${row.id}`) : null;
  console.log(`  SAVED tax id last4: ${detail?.data?.applicant?.identifier?.tax_id_last4}`);
}

// ── B · Move-in from an approved request: every field arrives filled in ────
async function movein() {
  const rid = process.env.REQUEST_ID;
  await page.goto(`${WEB}/${T}/move-ins/new?request=${rid}&step=2`, { waitUntil: "networkidle" });
  await page.waitForTimeout(4000);
  await shot("movein-from-request-landing");
  if (!(await page.locator("#full_name").count())) {
    // Step 1 opens on the request's unit; the meter needs its opening read.
    const boxes = page.locator('table input:not([type=checkbox])');
    console.log(`  opening-read boxes: ${await boxes.count()}`);
    if (await boxes.count()) await boxes.first().fill(process.env.OPENING || "8700");
    // The request starts in November; a read cannot be dated after today.
    if ((await boxes.count()) > 1) {
      await boxes.nth(1).fill(process.env.READ_DATE || "10/18/2026");
      await boxes.nth(1).press("Tab");
    }
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(3000);
    await shot("movein-after-step1");
  }
  await page.waitForSelector("#full_name", { timeout: 60000 });
  await page.waitForTimeout(2000);
  const v = async (id) => ((await page.locator(`#${id}`).count()) ? page.locator(`#${id}`).inputValue() : null);
  console.log(
    "  PREFILLED:",
    JSON.stringify({
      name: await v("full_name"),
      email: await v("email"),
      phone: await v("phone"),
      contact_by: await v("contact_by"),
      gov_id_last4: await v("gov_id_last4"),
      ssn_placeholder: await page.locator("#ssn").getAttribute("placeholder"),
      mailing_line1: await v("mailing_line1"),
      mailing_city: await v("mailing_city"),
      co_owner_tick: await page.locator("#co_owner_enabled").isChecked(),
      co_owner_text: (await page.locator('[data-tick-panel="co_owner"]').innerText()).slice(0, 120),
    }),
  );
  await shot("movein-from-request-customer-step");
  if (process.env.COMPLETE !== "1") return;
  // Finish the move-in: a phone (the request held none), then on to the end.
  await page.fill("#phone", "(281) 555-0110");
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForTimeout(3000);
  await shot("movein-billing-step");
  const addToBill = page.getByRole("radio", { name: "Add to bill" });
  if (await addToBill.count()) await addToBill.click({ force: true });
  else await page.getByText("Add to bill", { exact: true }).click();
  await page.getByRole("button", { name: "Continue" }).click();
  await page.waitForTimeout(3000);
  await shot("movein-review-step");
  const finish = page.getByRole("button", { name: /Complete/ }).last();
  const posted = page.waitForResponse((r) => r.url().includes("/move-ins") && r.request().method() === "POST", {
    timeout: 60000,
  });
  await finish.click();
  const res = await posted.catch(() => null);
  const body = res ? await res.json().catch(() => null) : null;
  console.log(`  COMPLETE: ${res ? res.status() : "no POST"} ${JSON.stringify(body).slice(0, 400)}`);
  await page.waitForTimeout(3000);
  await shot("movein-completed");
  const accountId = body?.account_id || body?.account?.id || body?.id;
  if (accountId) {
    const acct = await api("GET", `/accounts/${accountId}`);
    const d = acct.data || {};
    console.log(
      "  ACCOUNT:",
      JSON.stringify({
        account_no: d.account_no,
        co_owners: d.co_owners,
        addresses: d.addresses,
        contacts: d.contacts,
        customer_identity: d.customer?.identity,
        paperless: d.paperless,
        sms: d.sms_reminders,
      }).slice(0, 1500),
    );
  }
}

// ── B2 · finish a move-in from wherever the wizard resumed ──────────────────
async function moveinComplete() {
  const rid = process.env.REQUEST_ID;
  await page.goto(`${WEB}/${T}/move-ins/new?request=${rid}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  let answer = null;
  for (let turn = 0; turn < 8 && answer === null; turn += 1) {
    if (await page.locator("#full_name").count()) {
      if ((await page.locator("#phone").inputValue()) === "") await page.fill("#phone", "(281) 555-0110");
    } else if (await page.getByText("Add to bill", { exact: true }).count()) {
      await page.getByText("Add to bill", { exact: true }).click();
    } else if (await page.locator("table input:not([type=checkbox])").count()) {
      const boxes = page.locator("table input:not([type=checkbox])");
      if ((await boxes.first().inputValue()) === "") await boxes.first().fill("8700");
      await boxes.nth(1).fill(process.env.READ_DATE || "10/17/2026");
      await boxes.nth(1).press("Tab");
    }
    const complete = page.getByRole("button", { name: /^Complete/ });
    if (await complete.count()) {
      await shot("movein-review-step");
      const posted = page.waitForResponse(
        (r) => r.url().includes("/move-ins") && r.request().method() === "POST",
        { timeout: 90000 },
      );
      await complete.last().click();
      const res = await posted.catch(() => null);
      answer = res ? { status: res.status(), body: await res.json().catch(() => null) } : { status: 0 };
      break;
    }
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(2500);
    await shot(`movein-turn-${turn}`);
  }
  console.log(`  COMPLETE: ${JSON.stringify(answer).slice(0, 600)}`);
  await page.waitForTimeout(3000);
  await shot("movein-completed");
}

// ── C · New connect owner step ───────────────────────────────────────────────
async function newconnect() {
  const cid = process.env.CONNECTION_ID;
  const path = cid ? `/connections/new?build=${cid}&step=1` : "/connections/new?step=1";
  await page.goto(`${WEB}/${T}${path}`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-new-connect-customer-form]", { timeout: 60000 });
  await page.waitForTimeout(2000);
  await shot("newconnect-owner-step");
}

// ── C2 · New connect to Create: mailing unticked, a co-owner, tax exempt ────
async function newconnectCreate() {
  const cid = process.env.CONNECTION_ID;
  await page.goto(`${WEB}/${T}/connections/new?build=${cid}&step=1`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-new-connect-customer-form]", { timeout: 60000 });
  await page.waitForTimeout(2000);
  const kinds = await page.locator("#nc_owner_kind option").allTextContents();
  console.log(`  owner types: ${kinds.join(" | ")}`);
  if (process.env.OWNER_TYPE) await page.selectOption("#nc_owner_kind", { label: process.env.OWNER_TYPE });
  else await page.selectOption("#nc_owner_kind", { index: 1 });
  let answer = null;
  for (let turn = 0; turn < 10 && answer === null; turn += 1) {
    // Any required choice still unanswered on steps 2–4 takes the first
    // real option (premise type, plan, terms): this walk is about the owner.
    const pickByWord = async (label, word) => {
      const box = typeof label === "string" && label.startsWith("#") ? page.locator(label) : page.locator("main select").and(page.getByLabel(label));
      if ((await box.count()) !== 1 || (await box.inputValue()) !== "") return;
      const options = await box.locator("option").evaluateAll((os) => os.map((o) => [o.value, o.textContent]));
      const hit = options.find(([v, text]) => v !== "" && (text || "").includes(word)) ?? options.find(([v]) => v !== "");
      if (hit) await box.selectOption(hit[0]);
    };
    await pickByWord("Premise type", "Single");
    await pickByWord("#nc_plan", process.env.PLAN_WORD || "Residential");
    const apply = page.getByRole("button", { name: "Apply to all" });
    if ((await apply.count()) && !(await page.locator("[data-units-applied]").count())) {
      // Step 3's common selection: a size for the meter, no field visit (this
      // walk is about the owner, and the copy's templates are not the point).
      const common = page.locator("table").first();
      const selects = common.locator("select");
      for (let i = 0; i < (await selects.count()); i += 1) {
        const one = selects.nth(i);
        const options = await one.locator("option").evaluateAll((os) => os.map((o) => [o.value, o.textContent]));
        const label = (await one.getAttribute("aria-label")) || (await one.getAttribute("name")) || "";
        if (/work/i.test(label)) {
          const none = options.find(([v]) => v === "");
          if (none) await one.selectOption("");
        } else if ((await one.inputValue()) === "") {
          const first = options.find(([v]) => v !== "");
          if (first) await one.selectOption(first[0]);
        }
      }
      await apply.click();
      await page.waitForTimeout(800);
      await shot("newconnect-units-applied");
    }
    if (process.env.REMOVE_WORK === "1") {
      const removers = page.locator('[data-array*="work"] button[aria-label*="Remove"], [data-array*="work"] [data-array-remove]');
      while ((await removers.count()) > 0) {
        await removers.first().click();
        await page.waitForTimeout(200);
      }
    }
    if (turn > 0) {
      const selects = page.locator("main select[required]:not([disabled]):not([id^=nc_payment])");
      for (let i = 0; i < (await selects.count()); i += 1) {
        const one = selects.nth(i);
        if ((await one.inputValue()) === "" && (await one.locator("option").count()) > 1) {
          const values = await one.locator("option:not([disabled])").evaluateAll((os) => os.map((o) => o.value));
          const first = values.find((v) => v !== "");
          if (first !== undefined) await one.selectOption(first).catch(() => undefined);
        }
      }
    }
    // The charges step: Move-in's Discounts and Tax panels (DEF-CUS-10233).
    if (await page.locator("#move_in_tax_on").count()) {
      if (!(await page.locator("#move_in_discounts_on").isChecked())) {
        await page.check("#move_in_discounts_on", { force: true });
        await page.waitForTimeout(500);
        const pick = page.locator('[data-billing-section="discounts"] select').first();
        const options = await pick.locator("option").evaluateAll((os) => os.map((o) => [o.value, o.textContent]));
        console.log(`  discounts offered: ${options.map((o) => o[1]).join(" | ")}`);
        const want = options.find(([v, text]) => v !== "" && new RegExp(process.env.DISCOUNT_WORD || "Senior").test(text || "")) ?? options.find(([v]) => v !== "");
        if (want) await pick.selectOption(want[0]);
      }
      if (!(await page.locator("#move_in_tax_on").isChecked())) {
        await page.check("#move_in_tax_on", { force: true });
        await page.waitForTimeout(800);
        const cats = await page.locator("#move_in_tax_category option").evaluateAll((os) => os.map((o) => [o.value, o.textContent]));
        console.log(`  exemption types: ${cats.map((o) => o[1]).join(" | ")}`);
        const cat = cats.find(([v]) => v !== "");
        if (cat) await page.selectOption("#move_in_tax_category", cat[0]);
        await page.fill("#move_in_tax_ref", "EX-55-90211");
        await typeDate("move_in_tax_issued", "01/05/2026").catch(() => page.fill("#move_in_tax_issued", "2026-01-05"));
        await typeDate("move_in_tax_expires", "01/04/2029").catch(() => page.fill("#move_in_tax_expires", "2029-01-04"));
        await page.setInputFiles("#move_in_tax_certificate", {
          name: "exempt-cert.pdf",
          mimeType: "application/pdf",
          buffer: Buffer.from("%PDF-1.4 exemption certificate"),
        });
        await page.waitForTimeout(800);
      }
      if (!(await page.locator("#nc_prefs_on").isChecked())) await page.check("#nc_prefs_on", { force: true });
      await shot("newconnect-charges-tax-discount");
    }
    const create = page.getByRole("button", { name: /^Create/ });
    if (await create.count()) {
      await shot("newconnect-review-step");
      const posted = page.waitForResponse(
        (r) => r.url().includes("/connections") && r.request().method() === "POST" && r.url().includes("commit"),
        { timeout: 120000 },
      );
      await create.last().click();
      const res = await posted.catch(() => null);
      answer = res ? { status: res.status(), body: await res.json().catch(() => null) } : { status: 0 };
      break;
    }
    await page.getByRole("button", { name: "Continue" }).click();
    await page.waitForTimeout(2500);
    await shot(`newconnect-turn-${turn}`);
  }
  console.log(`  CREATE: ${JSON.stringify(answer).slice(0, 700)}`);
  await page.waitForTimeout(3000);
  await shot("newconnect-done");
}

// ── D · Search customer ID with three matches (Move-in) ─────────────────────
async function search() {
  // New connect step 1 (a Move-in reaches its customer step only after a unit).
  await page.goto(`${WEB}/${T}/connections/new?step=1`, { waitUntil: "networkidle" });
  await page.waitForSelector("#full_name", { timeout: 60000 });
  const person = page.getByRole("radio", { name: "Person" });
  if (await person.count()) await page.locator("[data-customer-panel=who]").getByText("Person", { exact: true }).click();
  await page.fill("#full_name", "Maria Lopez");
  await page.fill("#phone", "(734) 555-0182");
  await typeDate("dob", "04/12/1988");
  await page.fill("#ssn", "123-45-4471");
  await page.click("[data-search-customer-id]");
  await page.waitForSelector("[data-match-table]", { timeout: 30000 });
  const rows = await page.locator("[data-match-row]").count();
  console.log(`  SEARCH ROWS: ${rows}`);
  await shot("search-three-matches");
  await page.locator("[data-match-row] td:first-child button").first().click().catch(() => undefined);
  await page.waitForTimeout(800);
  await shot("search-accounts-open");
  await page.locator('[data-testid^="match-link-"]').first().click();
  await page.waitForTimeout(800);
  await shot("search-linked");
}

await signIn();
const steps = { request, requestBusiness, movein, moveinComplete, newconnect, newconnectCreate, search };
await steps[STEP]();
await browser.close();
