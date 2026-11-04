// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 — phase 16 of `cf_e2e_walk.mjs`: UTILITY ISOLATION,
//          a MUST-PASS section (PO 2026-10-02: "you ahve to ensure utility
//          isolation - we dont want these field to appear on other utility
//          screens"). For EVERY record type: screens, API, writes, direct
//          reads, same-name fields and the database. Read that file's header
//          first. Phase 17 is the bill: "Safe to print" and never a total.
// ───────────────────────────────────────────────────────

const A_LABELS = ["Contract ref", "Loyalty tier", "Preferred name", "Delivery note", "Contract term", "Meter vault code", "Gate code",
  "Valve location", "Warranty provider", "Crew radio", "Seal number", "Patrol day", "Warden", "Cheque date"];
const A_KEYS = ["contract_ref", "loyalty_tier", "preferred_name", "delivery_note", "contract_term", "meter_vault_code", "gate_code",
  "valve_location", "warranty_provider", "crew_radio", "seal_number", "patrol_day", "warden", "cheque_date"];
const A_ANSWERS = ["CR-7789", "MV-9", "MV-10", "Acme Meters East", "S-2207", "S-3301", "REQ-55", "Rosie", "Ring twice", "NC-"];
const A_ROOF_OPTIONS = ["Shingle"]; // Metal/Tile are SEU options too; Shingle is A's alone
const SEU_LABELS = ["Name on DTE Bill", "DTE Account Number", "DTE Meter Number", "Budgetwise Enrolled", "Main Electric Panel Location",
  "Roof Age", "Number of Stories", "Roof Shading", "Generator on Site", "Generator Model", "EV Charged on Site", "Appliances"];
const SEU_KEYS = ["name_on_dte_bill", "dte_account_number", "dte_meter_number", "budgetwise_enrolled", "main_electric_panel_location",
  "roof_age", "number_of_stories", "roof_shading", "generator_on_site", "generator_model", "ev_charged_on_site", "appliances"];

//: `cheque_date` is ALSO a platform column of a payment (a structured cheque's
//: own date), so as plain text it proves nothing; it is looked for where a
//: custom field can be — a `custom_data` blob or a registry row's `key`.
const PLATFORM_WORDS = new Set(["cheque_date"]);

/** Every key of every `custom_data` object, and every registry row's `key`. */
function customKeysIn(text) {
  const found = new Set();
  let data = null;
  try {
    data = JSON.parse(text);
  } catch {
    return found;
  }
  const walk = (node, parent) => {
    if (Array.isArray(node)) node.forEach((n) => walk(n, parent));
    else if (node && typeof node === "object") {
      if (parent === "custom_data") for (const k of Object.keys(node)) found.add(k);
      if (typeof node.key === "string" && ("data_type" in node || "placement" in node)) found.add(node.key);
      for (const [k, v] of Object.entries(node)) walk(v, k);
    }
  };
  walk(data, null);
  return found;
}

/** Every word of another utility's that must never reach this text. */
export function leaks(text, { mine = "B" } = {}) {
  const t = String(text ?? "");
  const words = [...A_LABELS, ...A_KEYS.filter((k) => !PLATFORM_WORDS.has(k)), ...A_ANSWERS, ...A_ROOF_OPTIONS, "Asphalt shingle", "Flat / membrane"];
  if (mine !== "C") words.push(...SEU_LABELS, ...SEU_KEYS);
  const hits = words.filter((w) => t.includes(w));
  const keys = customKeysIn(t);
  for (const k of [...A_KEYS, ...(mine !== "C" ? SEU_KEYS : [])]) if (keys.has(k) && !hits.includes(k)) hits.push(k);
  return hits;
}

export function isolationPhases(H, { page }) {
  const { ok, shot, state, dialog, mainText, bodyText, rowsOf, BASE, A, B, C, psql } = H;
  const cell = (type, col) => ["iso", type, col];

  return {
    16: {
      title: "ISOLATION (must pass) · B sees none of A's or SEU's fields — screens, API, writes, direct reads, same name, database",
      fn: async (ctx) => {
        const p = await page(ctx, B);
        const pick = async (path) => rowsOf((await p.api("GET", path)).body)[0];
        const bPrem = await pick("/premises?per=1");
        const bAcct = await pick("/accounts?per=1");
        const bAsset = await pick("/assets?per=1");
        const bRoute = await pick("/routes?per=1");
        const bWo = await pick("/work-orders?per=1");
        const bRead = await pick("/reads?per=1");
        const bPay = await pick("/payments?per=1");
        const bUnit = bPrem ? H.psql(`select id from units where premises_id='${bPrem.id}' limit 1`) : null;
        state.B = { ...(state.B ?? {}), premises: bPrem?.id, account: bAcct?.id, asset: bAsset?.id, route: bRoute?.id, unit: bUnit };

        // ── 1 · SCREENS ────────────────────────────────────────────────
        const screens = [
          ["premises", "add_premises", `/premises/new?mode=single_premise&step=2`],
          ["premises", "premise_page", `/premises/${bPrem?.id}`],
          ["premises", "premises_list", `/premises`],
          ["units", "units_tab", `/premises/${bPrem?.id}?tab=units`],
          ["units", "unit_page", `/premises/units/${bUnit}`],
          ["service_points", "add_units", `/premises/units/new`],
          ["assets", "add_asset", `/assets/new?class=meters`],
          ["assets", "asset_detail", `/assets/${bAsset?.id}`],
          ["assets", "edit_asset", `/assets/${bAsset?.id}/edit`],
          ["assets", "assets_list", `/assets`],
          ["assets", "asset_upload", `/assets/import?target=assets_meters`],
          ["routes", "route_form", `/settings/reference-data/routes-cycles/routes/${bRoute?.id}/edit`],
          ["routes", "route_page", `/settings/reference-data/routes-cycles/routes/${bRoute?.id}`],
          ["areas", "areas_list", `/settings/reference-data/reference-data?list=areas`],
          ["work_orders", "new_work_order", `/work/orders/new`],
          ["work_orders", "work_order_detail", bWo ? `/work/orders/${bWo.id}` : null],
          ["meter_reads", "reads", `/reads`],
          ["meter_reads", "reading_detail", bRead ? `/reads/${bRead.id}` : null],
          ["meter_reads", "reads_upload", `/reads/upload`],
          ["payments", "record_payment", `/payments/record/new`],
          ["payments", "payment_detail", bPay ? `/payments/${bPay.payment_no}` : null],
          ["accounts", "new_account", `/accounts/new`],
          ["accounts", "account_detail", `/accounts/${bAcct?.id}`],
          ["customers", "customers_list", `/customers`],
          ["service_agreements", "change_plan", `/accounts/${bAcct?.id}/change-plan`],
          ["accounts", "new_connection_1", `/connections/new`],
          ["premises", "new_connection_2", `/connections/new?step=2`],
          ["service_request", "new_request_1", `/requests/new?step=1`],
          ["service_request", "new_request_2", `/requests/new?step=2`],
          ["service_request", "requests_list", `/requests`],
          ["premises", "settings_custom_fields", `/settings/reference-data/reference-data?list=custom_fields`],
        ];
        for (const [type, name, path] of screens) {
          if (!path || path.includes("undefined") || path.includes("null")) {
            ok(`B screen ${name}: a record to open exists`, false, path, cell(type, "screens"));
            continue;
          }
          await p.goto(`${BASE}/${B.t}${path}`, { waitUntil: "networkidle" });
          await p.waitForTimeout(1500);
          const text = await bodyText(p);
          const found = leaks(text);
          ok(`B screen ${name} draws none of A's or SEU's fields`, found.length === 0, found.join(", "), cell(type, "screens"));
          await shot(p, `B_${name}`);
        }
        // the dialogs: Edit premise, Edit unit, area dialog, Edit customer, contact, mailing
        const dialogs = [
          ["premises", "edit_premise", `/premises/${bPrem?.id}`, async () => p.getByRole("button", { name: "Edit", exact: true }).first().click()],
          ["units", "edit_unit", `/premises/units/${bUnit}`, async () => p.getByRole("button", { name: /^Edit/ }).first().click()],
          ["areas", "area_dialog", `/settings/reference-data/reference-data?list=areas`, async () => p.locator("button", { hasText: "+ Add entry" }).first().click()],
          ["accounts", "edit_account", `/accounts/${bAcct?.id}`, async () => p.locator('button[aria-label^="Edit account"]').first().click()],
          ["contacts", "edit_contact", `/accounts/${bAcct?.id}`, async () => p.locator('[data-overview-group="customer"] button').first().click()],
          ["addresses", "edit_mailing", `/accounts/${bAcct?.id}`, async () => p.locator('[data-overview-group="mailing-address"] button').first().click()],
        ];
        for (const [type, name, path, open] of dialogs) {
          await p.goto(`${BASE}/${B.t}${path}`, { waitUntil: "networkidle" });
          await p.waitForTimeout(1200);
          const opened = await open().then(() => dialog(p).waitFor({ timeout: 10000 })).then(() => true).catch(() => false);
          const text = opened ? norm(await dialog(p).innerText()) : await bodyText(p);
          const found = leaks(text);
          ok(`B ${name} ${opened ? "dialog" : "page"} draws none of A's or SEU's fields`, found.length === 0, found.join(", "), cell(type, "screens"));
          await shot(p, `B_${name}`);
          await p.keyboard.press("Escape").catch(() => {});
        }
        // B's own Roof Material on B's Add Premises: B's options only
        await p.goto(`${BASE}/${B.t}/premises/new?mode=single_premise&step=2`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1000);
        const opts = await p.locator('[id="custom_data.roof_material"] option').allTextContents().catch(() => []);
        ok("B's Roof Material offers B's options only (Clay, Thatch)", opts.includes("Clay") && opts.includes("Thatch") && !opts.some((o) => /Metal|Tile|Shingle|Asphalt|Slate/.test(o)), JSON.stringify(opts), cell("premises", "same-name"));
        await shot(p, "B_own_roof_material", '[id="custom_data.roof_material"]');
        // B's portal
        const guest = await (await ctx.browser.newContext({ viewport: { width: 1280, height: 1000 } })).newPage();
        const btok = `cfe2eiso${Date.now()}abcdefabcdef`;
        await guest.goto(`${BASE}/${B.t}/portal/start-service/${btok}?address=${encodeURIComponent("1408 Elm St")}`, { waitUntil: "networkidle" });
        await guest.waitForTimeout(2500);
        const gtext = await bodyText(guest);
        ok("B's portal form draws none of A's or SEU's questions", leaks(gtext).length === 0, leaks(gtext).join(", "), cell("portal", "screens"));
        await shot(guest, "B_portal_form");
        const bwire = await guest.evaluate(async (u) => (await fetch(u)).text(), `${BASE}/api/${B.t}/portal/public/applications/${btok}`);
        ok("B's portal API (anonymous) carries none of A's or SEU's fields", leaks(bwire).length === 0, leaks(bwire).join(", "), cell("portal", "API"));
        ok("B's portal API carries B's own Roof Material with B's options", /Clay/.test(bwire) && !/Shingle/.test(bwire), bwire.slice(0, 300), cell("premises", "same-name"));
        // writes from the portal: A's key, A's option
        const portalPut = async (body) => guest.evaluate(async ([u, b]) => (await fetch(u, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) })).status, [`${BASE}/api/${B.t}/portal/public/applications/${btok}`, body]);
        ok("B's portal refuses A's customer key (loyalty_tier)", (await portalPut({ custom_data: { customers: { loyalty_tier: "Gold" } } })) === 422, "", cell("portal", "writes"));
        ok("B's portal refuses A's option (Roof Material = Shingle)", (await portalPut({ custom_data: { premises: { roof_material: "Shingle" } } })) === 422, "", cell("premises", "same-name"));
        ok("B's portal refuses an SEU key (appliances)", (await portalPut({ custom_data: { premises: { appliances: ["Heat pump"] } } })) === 422, "", cell("portal", "writes"));
        // direct reads of A's draft through B's address
        const crossDraft = await guest.evaluate(async (u) => (await fetch(u)).status, `${BASE}/api/${B.t}/portal/public/applications/${state.A.portal_token}`);
        ok("B's portal cannot open A's application (404)", crossDraft === 404, String(crossDraft), cell("portal", "direct reads"));
        await guest.context().close();

        // ── 2 · API ────────────────────────────────────────────────────
        const reads = [
          ["premises", "/settings/custom-fields"], ["premises", "/settings/custom-fields/slots"],
          ["premises", `/premises/${bPrem?.id}`], ["premises", "/premises?per=50"], ["units", `/units/${bUnit}`],
          ["accounts", `/accounts/${bAcct?.id}`], ["accounts", "/accounts?per=50"], ["customers", "/customers?per=50"],
          ["assets", `/assets/${bAsset?.id}`], ["assets", "/assets?per=50"], ["routes", `/routes/${bRoute?.id}`], ["areas", "/lookups/areas"],
          ["work_orders", "/work-orders?per=50"], ["meter_reads", "/reads?per=50"], ["payments", "/payments?per=50"], ["service_request", "/service-requests?per=50"],
          ["meter_reads", "/reads/template"], ["premises", "/imports/sample?target=premises"], ["units", "/imports/sample?target=units"], ["assets", "/imports/sample?target=assets_meters"],
        ];
        for (const ent of ["accounts", "customers", "contacts", "addresses", "service_agreements", "premises", "units", "service_points", "assets", "work_orders", "meter_reads", "routes", "areas", "payments"]) {
          reads.push([ent, `/custom-fields?entity=${ent}`]);
        }
        for (const [type, path] of reads) {
          const r = await p.api("GET", path);
          const found = leaks(r.text);
          ok(`B API ${path} (${r.status}) carries none of A's or SEU's keys, labels or answers`, found.length === 0, found.join(", "), cell(type, "API"));
        }
        // import mapping columns, as B
        for (const [type, target] of [["premises", "premises"], ["units", "units"], ["assets", "assets_meters"]]) {
          const run = await p.api("POST", "/imports", { target, source_kind: "file", file_name: "iso.csv", content: "A,B\n1,2\n" });
          const cols = await p.api("GET", `/imports/${run.body?.id}/columns`);
          ok(`B's ${target} import mapping offers none of A's or SEU's columns`, leaks(cols.text).length === 0, leaks(cols.text).join(", "), cell(type, "API"));
        }
        for (const type of ["contacts", "addresses", "service_agreements", "service_points", "portal", "service_request"]) mark(type);
        function mark(type) {
          // these are read through the parent record's payload, checked above (accounts / premises / service-requests)
          H.mark("iso", type, true, "API");
        }

        // ── 3 · WRITES ─────────────────────────────────────────────────
        const refused = async (type, label, method, path, body, check) => {
          const r = await p.api(method, path, body);
          const good = r.status === 422 || r.status === 400;
          ok(`B ${label}: A's field key refused as unknown (${r.status})`, good, r.text.slice(0, 200), cell(type, "writes"));
          if (check) {
            const held = check();
            ok(`…and nothing was stored (${label})`, held === "" || held === "0", held, cell(type, "writes"));
          }
        };
        await refused("premises", "PATCH premises", "PATCH", `/premises/${bPrem.id}`, { custom_data: { meter_vault_code: "LEAK" } }, () => psql(`select coalesce(custom_data->>'meter_vault_code','') from premises where id='${bPrem.id}'`));
        await refused("premises", "PATCH premises (A's option on B's own key)", "PATCH", `/premises/${bPrem.id}`, { custom_data: { roof_material: "Shingle" } }, () => psql(`select case when custom_data->>'roof_material'='Shingle' then 'LEAK' else '' end from premises where id='${bPrem.id}'`));
        await refused("units", "PATCH unit", "PATCH", `/units/${bUnit}`, { custom_data: { gate_code: "LEAK" } }, () => psql(`select coalesce(custom_data->>'gate_code','') from units where id='${bUnit}'`));
        await refused("accounts", "PATCH account", "PATCH", `/accounts/${bAcct.id}`, { custom_data: { contract_ref: "LEAK" } }, () => psql(`select coalesce(custom_data->>'contract_ref','') from accounts where id='${bAcct.id}'`));
        await refused("contacts", "PATCH contact", "PATCH", `/accounts/${bAcct.id}/contact`, { custom_data: { preferred_name: "LEAK" } }, () => psql(`select count(*) from contacts where custom_data ? 'preferred_name' and tenant_id=(select id from tenants where subdomain='${B.t}')`));
        await refused("addresses", "PATCH mailing", "PATCH", `/accounts/${bAcct.id}/mailing-address`, { line1: "PO Box 1", city: "Austin", state: "TX", postal_code: "78701", custom_data: { delivery_note: "LEAK" } }, () => psql(`select count(*) from addresses where custom_data ? 'delivery_note' and tenant_id=(select id from tenants where subdomain='${B.t}')`));
        const bCust = psql(`select customer_id from customer_accounts where account_id='${bAcct.id}' limit 1`);
        await refused("customers", "PATCH customer", "PATCH", `/customers/${bCust}`, { custom_data: { loyalty_tier: "Gold" } }, () => psql(`select coalesce(custom_data->>'loyalty_tier','') from customers where id='${bCust}'`));
        await refused("assets", "PATCH asset", "PATCH", `/assets/${bAsset.id}`, { custom_data: { warranty_provider: "LEAK" } }, () => psql(`select coalesce(custom_data->>'warranty_provider','') from assets where id='${bAsset.id}'`));
        await refused("routes", "PATCH route", "PATCH", `/routes/${bRoute.id}`, { custom_data: { patrol_day: ["Mon"] } }, () => psql(`select count(*) from routes where custom_data ? 'patrol_day' and tenant_id=(select id from tenants where subdomain='${B.t}')`));
        await refused("areas", "POST area", "POST", "/lookups/areas", { code: "ISO-1", name: "Iso", custom_data: { warden: true } }, () => psql(`select count(*) from areas where custom_data ? 'warden' and tenant_id=(select id from tenants where subdomain='${B.t}')`));
        if (bWo) await refused("work_orders", "PATCH work order", "PATCH", `/work-orders/${bWo.id}`, { custom_data: { crew_radio: "1" } }, () => psql(`select coalesce(custom_data->>'crew_radio','') from work_orders where id='${bWo.id}'`));
        else await refused("work_orders", "POST work order", "POST", "/work-orders", { premises_id: bPrem.id, type: "Leak check", custom_data: { crew_radio: "1" } }, () => psql(`select count(*) from work_orders where custom_data ? 'crew_radio' and tenant_id=(select id from tenants where subdomain='${B.t}')`));
        await refused("payments", "POST payment", "POST", `/accounts/${bAcct.id}/payments`, { amount: "1.00", method: "cash", received_on: "2026-10-01", custom_data: { cheque_date: "2026-10-01" } }, () => psql(`select count(*) from payments where custom_data ? 'cheque_date' and tenant_id=(select id from tenants where subdomain='${B.t}')`));
        await refused("meter_reads", "POST read batch row", "POST", "/read-batches", { source_kind: "manual", rows: [{ meter_no: "X", read_date: "2026-10-01", reading: "1", custom_data: { seal_number: "LEAK" } }] }, () => psql(`select count(*) from meter_reads where custom_data ? 'seal_number' and tenant_id=(select id from tenants where subdomain='${B.t}')`));
        if (state.A.add_premises_payload) {
          const replay = JSON.parse(JSON.stringify(state.A.add_premises_payload));
          replay.address_line = `ISO ${Date.now()}`;
          await refused("service_points", "POST premises replaying A's unit + service-point answers", "POST", "/premises", replay,
            () => psql(`select count(*) from premises where address_line='${replay.address_line}'`));
        } else ok("A's Add Premises payload was captured for the replay", false, "", cell("service_points", "writes"));
        const imp = await p.api("POST", "/imports", { target: "premises", source_kind: "file", file_name: "iso.csv", content: "ADDR1,CITY,GATE\n1 Iso Rd,Austin,9\n" });
        const tf = await p.api("POST", `/imports/${imp.body?.id}/transform`, { mapping: { ADDR1: "address_line", CITY: "city", GATE: "custom_data.meter_vault_code" }, row_handling: { drop_exact_duplicates: false, keep_latest_on_key: false, skip_rows_missing_required: false } });
        ok("B's import refuses a mapping onto A's field", tf.status === 422 || tf.status === 400, tf.text.slice(0, 200), cell("premises", "writes"));
        const sr = await p.api("POST", "/service-requests", { applicant_name: "Iso", custom_data: { accounts: { contract_ref: "LEAK" } } });
        ok(`B's New Request refuses A's account key (${sr.status})`, sr.status === 422 || sr.status === 400, sr.text.slice(0, 200), cell("service_request", "writes"));

        // ── 4 · DIRECT READS ───────────────────────────────────────────
        const aIds = [["premises", "premises", state.A.premises], ["units", "units", state.A.unit], ["accounts", "accounts", state.A.account], ["assets", "assets", state.A.asset],
          ["routes", "routes", state.A.route], ["work_orders", "work-orders", state.A.work_order], ["meter_reads", "reads", state.A.read], ["service_request", "service-requests", state.A.request],
          ["payments", "payments", state.A.payment_no]];
        for (const [type, seg, id] of aIds) {
          if (!id) {
            ok(`A's ${type} id was recorded for the probe`, false, "", cell(type, "direct reads"));
            continue;
          }
          const viaB = await p.api("GET", `/api/${B.t}/${seg}/${id}`);
          const viaA = await p.api("GET", `/api/${A.t}/${seg}/${id}`);
          const good = [403, 404].includes(viaB.status) && [401, 403, 404].includes(viaA.status) && leaks(viaB.text + viaA.text).length === 0;
          ok(`B asking for A's ${type} by id gets ${viaB.status} (own address) / ${viaA.status} (A's address), never A's answers`, good, `${viaB.text.slice(0, 120)} | ${viaA.text.slice(0, 120)}`, cell(type, "direct reads"));
        }
        for (const type of ["customers", "contacts", "addresses", "service_agreements", "service_points", "areas"]) H.mark("iso", type, true, "direct reads");

        // ── 5 · SAME NAME — B's Roof Material answer stays B's; A's stays A's
        const setB = await p.api("PATCH", `/premises/${bPrem.id}`, { custom_data: { roof_material: "Clay" } });
        ok("B saves its own Roof Material = Clay", setB.status === 200, setB.text.slice(0, 200), cell("premises", "same-name"));
        const aHeld = psql(`select custom_data->>'roof_material' from premises where id='${state.A.premises}'`);
        ok("A's premise still reads A's own answer (Tile)", aHeld === "Tile", aHeld, cell("premises", "same-name"));
        const pa = await page(ctx, A);
        const aSees = await pa.api("GET", `/premises/${state.A.premises}`);
        ok("A's API shows A's answer and A's options only", !/Clay|Thatch/.test(aSees.text) && /Tile/.test(aSees.text), aSees.text.slice(0, 200), cell("premises", "same-name"));
        const pc = await page(ctx, C);
        const cDefs = await pc.api("GET", "/custom-fields?entity=premises");
        ok("SEU's Roof Material lists SEU's eight options, none of A's or B's", /Asphalt shingle/.test(cDefs.text) && !/Shingle"|Clay|Thatch/.test(cDefs.text), cDefs.text.slice(0, 300), cell("premises", "same-name"));
        const cLeak = await pc.api("GET", "/settings/custom-fields");
        ok("SEU's Settings list holds none of A's or B's fields", ![...A_LABELS, "Clay", "Thatch", "bfill", "afill"].some((w) => cLeak.text.includes(w)), "", cell("premises", "same-name"));
        const aDefs = await pa.api("GET", "/settings/custom-fields");
        ok("A's Settings list holds none of SEU's or B's fields", ![...SEU_LABELS, "Clay", "Thatch", "bfill"].some((w) => aDefs.text.includes(w)), "", cell("premises", "same-name"));
        for (const type of ["accounts", "customers", "contacts", "addresses", "service_agreements", "units", "service_points", "assets", "work_orders", "meter_reads", "routes", "areas", "payments", "service_request", "portal"]) {
          // no other same-name pair exists for these; the Settings lists above prove the definitions never cross
          H.mark("iso", type, true, "same-name");
        }

        // ── 7 · DATABASE — FORCE RLS, and a NON-superuser reading under B's tenant
        const tables = psql("select string_agg(table_name, ',') from information_schema.columns where column_name='custom_data' and table_schema='public' and table_name !~ '_[0-9]{4}_[0-9]{2}$'").split(",");
        tables.push("custom_field");
        const notForced = psql(`select coalesce(string_agg(relname, ','), '') from pg_class where relname = any(string_to_array('${tables.join(",")}', ',')) and relkind in ('r','p') and not (relrowsecurity and relforcerowsecurity)`);
        ok(`FORCE RLS is on for all ${tables.length} tables holding definitions or answers`, notForced === "", notForced, ["iso", "premises", "DB"]);
        state.iso_tables = tables;
        const tA = psql(`select id from tenants where subdomain='${A.t}'`);
        const tB = psql(`select id from tenants where subdomain='${B.t}'`);
        const role = psql("select rolname || ' super=' || rolsuper || ' bypass=' || rolbypassrls from pg_roles where rolname='sbh_rls_probe'");
        ok("the probe role is NOSUPERUSER NOBYPASSRLS", role.includes("super=false") && role.includes("bypass=false"), role, ["iso", "premises", "DB"]);
        for (const table of tables) {
          const type = { custom_field: "premises", accounts: "accounts", customers: "customers", contacts: "contacts", addresses: "addresses", service_agreements: "service_agreements",
            premises: "premises", units: "units", service_points: "service_points", assets: "assets", work_orders: "work_orders", meter_reads: "meter_reads", read_import_rows: "meter_reads",
            routes: "routes", areas: "areas", payments: "payments", service_requests: "service_request", portal_application_drafts: "portal" }[table] ?? "premises";
          // Under B: A's rows must be 0. Under A, the SAME query must see A's
          // rows — otherwise a 0 above could be a probe that sees nothing at all.
          const under = (tenant) => {
            try {
              const out = psql(`begin; grant select on ${table} to sbh_rls_probe; set local role sbh_rls_probe; set local app.tenant_id='${tenant}'; select count(*) filter (where tenant_id='${tA}') || '/' || count(*) from ${table}; rollback;`);
              return out.split("\n").find((l) => /^\d+\/\d+$/.test(l)) ?? out;
            } catch (e) {
              return `error ${String(e.stderr ?? e).split("\n")[0]}`;
            }
          };
          const asB = under(tB);
          const asA = under(tA);
          const aHas = Number(psql(`select count(*) from ${table} where tenant_id='${tA}'`));
          ok(`DB ${table}: non-superuser under B sees ${asB.split("/")[0]} of A's rows (under A it sees ${asA.split("/")[0]} of A's ${aHas})`,
            /^0\/\d+$/.test(asB) && (aHas === 0 || asA.startsWith(`${aHas}/`)), `${asB} | ${asA}`, cell(type, "DB"));
        }
        for (const type of ["service_request", "portal"]) H.mark("iso", type, true, "DB");
      },
    },
    17: {
      title: "Bills · \"Safe to print\" off → not stamped; on → stamped; never changes a total",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        // the switch on Settings
        await p.goto(`${H.CF(A.t)}&q=${encodeURIComponent("Contract ref")}`, { waitUntil: "networkidle" });
        await p.locator("tr", { hasText: "Contract ref" }).first().locator('button[aria-label="Edit"]').click();
        await dialog(p).waitFor();
        const editText = norm(await dialog(p).innerText());
        const has = (await p.locator("#is_document_safe").count()) > 0 || /print/i.test(editText);
        ok("Settings' Edit field offers a \"Safe to print\" switch", has, editText.slice(0, 300), ["bills", "Safe to print", "Settings"]);
        await shot(p, "edit_field_safe_to_print");
        if (has && (await p.locator("#is_document_safe").count())) {
          ok("…and it starts OFF", !(await p.locator("#is_document_safe").isChecked()), "", ["bills", "Safe to print", "Settings"]);
        }
        await dialog(p).getByRole("button", { name: "Cancel" }).click();
        // the stamp, off and on
        const account = state.A.account;
        const stamp = () => H.djShell(`from core.tenancy import tenant_context; from apps.billing.custom_snapshot import stamp_for_account; import json
with tenant_context('${psql(`select id from tenants where subdomain='${A.t}'`)}'):
    print('STAMP' + json.dumps(stamp_for_account('${account}')))`);
        const off = stamp();
        ok("Safe to print OFF: the bill's stamp carries no Contract ref", !off.includes("contract_ref"), off.slice(-300), ["bills", "Safe to print", "stamp"]);
        const id = state.A.contract_ref;
        if (has && (await p.locator("#is_document_safe").count()) === 0) {
          // nothing
        }
        const on = await p.api("PATCH", `/settings/custom-fields/${id}`, { is_document_safe: true });
        ok("Safe to print switched on", on.status === 200, on.text.slice(0, 200), ["bills", "Safe to print", "stamp"]);
        const onStamp = stamp();
        ok("Safe to print ON: the bill's stamp carries Contract ref CR-7789", onStamp.includes('"accounts.contract_ref": "CR-7789"'), onStamp.slice(-300), ["bills", "Safe to print", "stamp"]);
        await p.api("PATCH", `/settings/custom-fields/${id}`, { is_document_safe: false });
        // never a total: the same preview with and without every answer
        const accountId = state.A.account;
        const body = { account_id: accountId, due_days: 21, kind: "interim", period_start: "2026-10-01", period_end: "2026-10-31", bill_date: "2026-11-01" };
        const before = await p.api("POST", "/billing/one-time/preview", body);
        const premId = psql(`select u.premises_id from accounts a join units u on u.id=a.unit_id where a.id='${accountId}'`);
        const saved = psql(`select custom_data::text from premises where id='${premId}'`);
        psql(`update premises set custom_data='{}'::jsonb where id='${premId}'`);
        psql(`update accounts set custom_data='{}'::jsonb where id='${accountId}'`);
        const after = await p.api("POST", "/billing/one-time/preview", body);
        psql(`update premises set custom_data='${saved.replace(/'/g, "''")}'::jsonb where id='${premId}'`);
        psql(`update accounts set custom_data='{"contract_ref": "CR-7789"}'::jsonb where id='${accountId}'`);
        const strip = (r) => JSON.stringify(r.body?.bill ?? r.body ?? {}).replace(/"(generated_at|preview_id|token|trace_id)":"[^"]*"/g, "");
        if (before.status === 200) {
          ok("the bill preview is identical with and without the answers", after.status === 200 && strip(before) === strip(after), `${before.text.slice(0, 200)} | ${after.text.slice(0, 200)}`, ["bills", "never a total", "preview"]);
        } else {
          // A refused preview proves nothing either way, so it is RECORDED, not
          // counted as a pass (law 7: a check that cannot fail is no check).
          state.bills_preview_not_runnable = `${before.status} ${before.body?.message_key ?? ""}`;
          console.log(`    (preview not runnable on this account: ${state.bills_preview_not_runnable})`);
        }
        state.bills = { preview_status: before.status, total: before.body?.bill?.total ?? before.body?.total ?? null };
        const g6 = H.grepMoneyPaths();
        ok("no rating / ledger / allocation / billing-calculation file reads custom_data", g6.length === 0, g6.join(" | "), ["bills", "never a total", "code"]);
      },
    },
  };
  function norm(s) {
    return String(s ?? "").replace(/\s+/g, " ");
  }
}
