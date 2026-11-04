// ── Trace ──────────────────────────────────────────────
// Change:  PO 2026-09-23, verbatim: "if user makes mistake while filling t new
//          request form then system should allow to correct it using edit ,
//          there is no edit available on list view as wellas detail view".
//          Lane REQ-EDIT, `DEF-CUS-6427` (+ `DEF-CUS-5880`, `DEF-CUS-5881`).
// Rules:   `22-product-maintenance-process.md` step 4 (prove it against the
//          reproduction, in a browser) · CLAUDE.md hard-won law 6 · hard rule 7
// Screens: REQ-01 (the list's pencil) · REQ-02 (the page's Edit) · REQ-03 (the
//          wizard, loaded) · REQ-03 on an APPROVED request (refused)
// ───────────────────────────────────────────────────────
//
// THE PROOF THE COORDINATOR ASKED FOR, in the order a clerk does it: a
// SUBMITTED request with an SSN is opened from the list's pencil, ONLY the
// phone is changed, Save — and the SSN, the email and everything else are
// still what they were, with one audit row saying phone before → after.
//
// The request is created through the product's own API from the signed-in
// page (the same door the wizard uses), so nothing here writes a row by hand.
// Every line prints what the screen SAYS or what the server STORED, with a
// `●` beside anything that is still the defect.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   eval "$(10-scripts/proof-db.sh clone reqedit --export)"
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
//      python manage.py runserver 127.0.0.1:8471 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8472 \
//      API_PROXY_TARGET=http://127.0.0.1:8471 node server.mjs)
//   BASE=http://127.0.0.1:8472 node 10-scripts/po20260923_req_edit_walk.mjs
//   # the audit row, read from the database itself:
//   psql "$DATABASE_URL" -c "select before, after from audit_log where
//        action='service_request.updated' order by created_at desc limit 1"
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8472";
const TENANT = process.env.TENANT ?? "brazosbend";
const SHOTS = process.env.SHOTS ?? "/tmp/claude-0/shots/reqedit";
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
async function shot(page, name) {
  // SMALL on purpose: a jpeg of the viewport, not a full-page png.
  await page.screenshot({ path: `${SHOTS}/${name}.jpg`, type: "jpeg", quality: 55 });
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
page.setDefaultTimeout(20000);
const writes = [];
page.on("request", (r) => {
  const u = r.url();
  if (u.includes("/api/") && r.method() !== "GET") {
    writes.push({ method: r.method(), path: new URL(u).pathname, body: r.postData() ?? "" });
  }
});

/** The product's own API, from the signed-in page. */
async function api(method, path, body) {
  return page.evaluate(
    async ({ method, path, body, tenant }) => {
      const response = await fetch(`/api/${tenant}${path}`, {
        method,
        credentials: "include",
        headers: body === undefined ? {} : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      return { status: response.status, body: await response.json().catch(() => null) };
    },
    { method, path, body, tenant: TENANT },
  );
}

try {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
  await page.fill("#signin-email", "dana@brazosbendutilities.com");
  await page.fill("#signin-password", "S3cure!passw0rd");
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ── A SUBMITTED REQUEST WITH AN SSN ───────────────────────────────────────
  const created = await api("POST", "/service-requests", {
    channel: "walk_in",
    applicant_kind: "person",
    applicant_name: "Whitfield, Dana",
    applicant_email: "dana.whitfield@example.com",
    applicant_phone: "512-555-0100",
    ssn: "123-45-5236",
    drivers_licence: "TX44179566",
    date_of_birth: "1984-03-02",
    address_as_given: "212 Balcones Drive",
    address_city_as_given: "Austin",
    address_state_as_given: "TX",
    address_postal_code_as_given: "78704",
    billing_address_same: false,
    billing_line1_as_given: "PO Box 4471",
    billing_city_as_given: "Round Rock",
    billing_state_as_given: "TX",
    billing_postal_code_as_given: "78664",
    what_they_said: "Moving in on the 14th",
  });
  const id = created.body?.header?.id;
  const requestNo = created.body?.header?.request_no;
  await api("POST", `/service-requests/${id}/category`, { account_type_code: "residential" });
  await api("POST", `/service-requests/${id}/services`, {
    services: [{ code: "water", requested_start: "2026-10-14" }],
  });
  const submitted = await api("POST", `/service-requests/${id}/submit`, {});
  console.log(`\n  seeded ${requestNo} (${id}) · create ${created.status} · submit ${submitted.status}`);
  const before = (await api("GET", `/service-requests/${id}`)).body;

  // ── REQ-01 · THE LIST'S PENCIL ────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/requests?segment=all&q=${encodeURIComponent(requestNo)}`, {
    waitUntil: "domcontentloaded",
  });
  const row = page.locator("tr", { hasText: requestNo }).first();
  await row.waitFor();
  const pencil = row.getByRole("link", { name: "Edit", exact: true });
  const href = await pencil.getAttribute("href");
  check(href === `/${TENANT}/requests/new?request=${id}`, `list · ${requestNo} (Submitted) has Edit → ${href}`);
  await shot(page, "1-list");

  // ── REQ-03 · OPENED FROM THE PENCIL, LOADED ───────────────────────────────
  writes.length = 0;
  await pencil.click();
  await page.waitForSelector("#applicant_name");
  await page.waitForFunction(() => document.querySelector("#applicant_name")?.value !== "");
  const loaded = {
    name: await page.inputValue("#applicant_name"),
    email: await page.inputValue("#applicant_email"),
    phone: await page.inputValue("#applicant_phone"),
    ssnValue: await page.inputValue("#ssn"),
    ssnShown: await page.getAttribute("#ssn", "placeholder"),
    licenceShown: await page.getAttribute("#drivers_licence", "placeholder"),
  };
  console.log(`  wizard · loaded ${JSON.stringify(loaded)}`);
  check(loaded.name === "Whitfield, Dana" && loaded.email === "dana.whitfield@example.com", "wizard · the saved applicant is loaded");
  check(loaded.ssnValue === "" && loaded.ssnShown === "••• ••• • 5236", "wizard · SSN box empty, shows ••• ••• • 5236");
  check(loaded.licenceShown === "•••••9566", "wizard · licence shows •••••9566");
  check((await page.locator('[data-screen="REQ-03"]').count()) === 1, "wizard · the REQ-03 screen opened");
  await shot(page, "2-wizard-loaded");

  // ── CHANGE ONLY THE PHONE, SAVE ───────────────────────────────────────────
  await page.fill("#applicant_phone", "512-555-0199");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  await page.waitForURL((u) => u.pathname === `/${TENANT}/requests/${id}`, { timeout: 20000 });
  const patches = writes.filter((w) => w.method === "PATCH");
  console.log(`  save · writes sent: ${JSON.stringify(writes.map((w) => `${w.method} ${w.path.replace(/.*service-requests/, "…")} ${w.body}`))}`);
  check(patches.length === 1 && patches[0].body === '{"applicant_phone":"512-555-0199"}', "save · ONE PATCH carrying ONLY the phone");
  check(!writes.some((w) => /•/.test(w.body)), "save · no mask glyph sent anywhere");
  await page.waitForTimeout(1500);
  await shot(page, "3-detail-after-save");

  // ── WHAT THE SERVER HOLDS NOW ─────────────────────────────────────────────
  const after = (await api("GET", `/service-requests/${id}`)).body;
  const was = before.applicant;
  const now = after.applicant;
  console.log(`  stored · phone ${was.phone} → ${now.phone} · email ${now.email} · SSN last four ${now.identifier.ssn_last4} · licence last four ${now.identifier.drivers_licence_last4}`);
  check(now.phone === "512-555-0199", "stored · the phone changed");
  check(now.email === was.email && now.name === was.name, "stored · email and name untouched");
  check(now.identifier.ssn_present && now.identifier.ssn_last4 === "5236", "stored · SSN still on file, still ends 5236");
  check(now.identifier.drivers_licence_last4 === "9566", "stored · licence still ends 9566");
  check(
    JSON.stringify(after.location_and_services.billing_line1_as_given) === JSON.stringify(before.location_and_services.billing_line1_as_given),
    "stored · billing address untouched",
  );
  const detailText = await page.locator("main").innerText();
  check(/••• ••• • 5236/.test(detailText), "detail page · SSN reads ••• ••• • 5236");

  // ── A DECIDED REQUEST: NO DOOR, AND A TYPED ADDRESS IS REFUSED ────────────
  const list = (await api("GET", "/service-requests?segment=approved&per=5")).body;
  const approved = (list?.results ?? []).find((r) => r.state === "approved");
  if (approved) {
    await page.goto(`${BASE}/${TENANT}/requests/${approved.id}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    const editOnApproved = await page.getByRole("link", { name: "Edit", exact: true }).count();
    check(editOnApproved === 0, `approved ${approved.request_no} · no Edit on its page`);
    await page.goto(`${BASE}/${TENANT}/requests/new?request=${approved.id}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);
    const refused = await page.locator("[data-edit-refused]").innerText().catch(() => "");
    check(/Approved already/.test(refused) && (await page.locator("#applicant_name").count()) === 0, `approved · typed address → "${refused}", no form`);
    await shot(page, "4-approved-refused");
    const patched = await api("PATCH", `/service-requests/${approved.id}`, { applicant_phone: "000" });
    check(patched.status === 409 && patched.body?.message_key === "customers.serviceRequest.approvedNoEdit", `approved · server refuses a PATCH: ${patched.status} ${patched.body?.message_key}`);
  } else {
    console.log("    ● no approved request on this tenant to check against");
    defects += 1;
  }
} finally {
  await browser.close();
}
console.log(`\n  ${defects === 0 ? "ALL CLEAR" : `${defects} still the defect`}\n`);
process.exit(defects === 0 ? 0 : 1);
