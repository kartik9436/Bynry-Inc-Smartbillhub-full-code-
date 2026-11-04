// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 — phases 18–20 of `cf_e2e_walk.mjs`: the SEU mapping
//          (PO 2026-10-02, TEST ONLY — "use this only for testing purpose dont
//          set it up - i want to test wether we are able to manage this now").
//          Thirteen fields set up through Settings in phase 2, then every
//          field through all THREE input routes: (1) a clerk on the create /
//          edit screens, (2) the customer on the portal's new-service form,
//          (3) a clerk on Staff New Request, approved, copied by the system.
//          Read `cf_e2e_walk.mjs`'s header first.
// ───────────────────────────────────────────────────────
import { openApprove, startDate } from "./cf_e2e_walk_requests.mjs";

export function seuPhases(H, { page }) {
  const { ok, shot, state, dialog, box, mainText, rowsOf, BASE, C, SEU_FIELDS, psql } = H;
  const ACC = SEU_FIELDS.filter((f) => f.entity === "accounts");
  const PRM = SEU_FIELDS.filter((f) => f.entity === "premises");
  let ADDRESS = "500 Main St";
  let PREMISE_NO = "P-00053";
  // route 2 applies at an address the utility has never served: no property,
  // no customer and no account exist when the request is approved
  /** `[premise_no, address, unit_no]` of a vacant home a move-in can open: it
   *  has a plan and services, is not a common area and no request holds it. */
  const eligibleHome = () =>
    psql(`select p.premise_no || '|' || p.address_line || '|' || u.unit_no from units u join premises p on p.id=u.premises_id
      where p.tenant_id='${tid()}' and u.rate_plan_id is not null and not u.is_common_area
        and exists (select 1 from service_points sp where sp.unit_id=u.id)
        and not exists (select 1 from accounts a where a.unit_id=u.id)
        and not exists (select 1 from service_requests sr where sr.resolved_unit_id=u.id)
      order by p.premise_no, u.unit_no limit 1`).split("|");
  const NEW_ADDRESS = `${100 + (Date.now() % 800)} ${Date.now().toString(36).slice(-5)} Lane`;
  const cell = (f, col) => ["SEU", f.label, col];
  const tid = () => psql(`select id from tenants where subdomain='${C.t}'`);
  const vacantUnit = (premisesId, requestId = '00000000-0000-0000-0000-000000000000') => psql(`select u.id from units u where u.premises_id='${premisesId}' and not exists (select 1 from accounts a where a.unit_id=u.id) and not u.is_common_area and u.rate_plan_id is not null and exists (select 1 from service_points sp where sp.unit_id=u.id) and not exists (select 1 from service_requests sr where sr.resolved_unit_id=u.id and sr.id <> '${requestId}') order by u.unit_no limit 1`);

  /** A second set of answers, so each route is told apart from the others. */
  const ALT = {
    name_on_dte_bill: "M. Okafor (portal)", dte_account_number: "9100 0000 1111", dte_meter_number: "DTE-11111", budgetwise_enrolled: false,
    main_electric_panel_location: "Basement", roof_age: "Over 20", number_of_stories: "2", roof_material: "Asphalt shingle",
    roof_shading: "Light (under 25%)", generator_on_site: false, generator_model: "None installed", ev_charged_on_site: true,
    appliances: ["Gas furnace", "Central A/C"],
  };
  const REQ = {
    name_on_dte_bill: "Okafor Holdings (request)", dte_account_number: "9100 2222 3333", dte_meter_number: "DTE-22222", budgetwise_enrolled: true,
    main_electric_panel_location: "Don't know", roof_age: "Don't know", number_of_stories: "1", roof_material: "Don't know",
    roof_shading: "Heavy (over 50%)", generator_on_site: true, generator_model: "Kohler 14kW", ev_charged_on_site: false,
    appliances: ["None of these"],
  };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const shown = (f, v) => (f.type === "boolean" ? (v ? "Yes" : "No") : Array.isArray(v) ? v.join(", ") : String(v));

  /** Staff screen (CustomFieldControl): fill one SEU answer. */
  async function staffFill(scope, f, v) {
    if (f.type === "text") await scope.locator(`[id="custom_data.${f.key}"]`).fill(String(v));
    else if (f.type === "select") await scope.locator(`[id="custom_data.${f.key}"]`).selectOption(String(v));
    // DEF-SHL-9240 (2.467.12): a Yes/No is a Yes / No pick on staff screens, as on the portal
    else if (f.type === "boolean") await scope.locator(`[id="custom_data.${f.key}"]`).selectOption(v ? "true" : "false");
    else if (f.type === "multi_select") {
      for (const o of f.options) await tick(scope.locator(`[id="custom_data.${f.key}.${o}"]`), v.includes(o));
    }
  }
  /** The kit's tick box is a visually hidden input under its label: a click on
   *  the element itself, as a person's click on the label would make. */
  async function tick(loc, want) {
    if ((await loc.count()) === 0) return;
    if ((await loc.evaluate((n) => n.checked)) !== want) await loc.evaluate((n) => n.click());
  }
  /** Staff screen: does this field's box (and its help) draw, options in order, wording exact? */
  async function staffDrawn(scope, f, where, col) {
    let drawn = false;
    let detail = "";
    if (f.type === "multi_select") {
      const labels = [];
      for (const o of f.options) if ((await scope.locator(`[id="custom_data.${f.key}.${o}"]`).count()) === 1) labels.push(o);
      drawn = same(labels, f.options);
      detail = JSON.stringify(labels);
    } else {
      drawn = (await scope.locator(`[id="custom_data.${f.key}"]`).count()) === 1;
      if (drawn && f.type === "select") {
        const opts = (await scope.locator(`[id="custom_data.${f.key}"] option`).allTextContents()).map((o) => o.trim()).filter((o) => f.options.includes(o) || o === "");
        const real = opts.filter((o) => o !== "");
        drawn = same(real, f.options);
        detail = JSON.stringify(real);
      }
    }
    ok(`SEU ${where}: ${f.label} draws${f.options ? " with its options in order, exact wording" : ""}`, drawn, detail, cell(f, col));
    if (f.help) {
      const text = (await scope.innerText().catch(() => "")).replace(/\s+/g, " ");
      ok(`SEU ${where}: ${f.label}'s help "${f.help}" shows`, text.includes(f.help), "", cell(f, col));
    }
    return drawn;
  }

  return {
    18: {
      title: "SEU · route 1 — a clerk types every field on the create/edit screens (New Account, Account detail, Add Premises, Premise page, Edit premise, New Connection steps 1/2)",
      fn: async (ctx) => {
        const p = await page(ctx, C);
        state.C = state.C ?? {};
        // ── Add Premises step 2: the nine premises fields
        const addr = `61 Solar Row ${Date.now().toString(36).slice(-4)}`;
        await p.goto(`${BASE}/${C.t}/premises/new?mode=single_premise&step=2`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1500);
        for (const f of PRM) await staffDrawn(p.locator("main"), f, "Add Premises", "route 1 · clerk");
        await p.fill("#address_line", addr);
        for (const f of PRM) await staffFill(p.locator("main"), f, f.sample);
        await shot(p, "seu_add_premises_step2", '[id="custom_data.main_electric_panel_location"]');
        await p.getByRole("button", { name: "Continue" }).click();
        await p.waitForTimeout(1000);
        const recap = await mainText(p);
        ok("SEU Add Premises step 3 lists Appliances with all three ticks", recap.includes("Heat pump, Electric range, None of these"), recap.slice(-500), ["SEU", "Appliances", "route 1 · clerk"]);
        await shot(p, "seu_add_premises_step3");
        const sent = p.waitForRequest((r) => /\/premises$/.test(r.url()) && r.method() === "POST", { timeout: 30000 }).catch(() => null);
        await p.getByRole("button", { name: /Create premise/ }).click();
        await sent;
        await p.waitForTimeout(3000);
        const prem = rowsOf((await p.api("GET", `/premises?q=${encodeURIComponent(addr)}&per=5`)).body)[0];
        state.C.premises = prem?.id;
        for (const f of PRM) {
          const held = prem?.custom_data?.[f.key];
          ok(`SEU route 1: ${f.label} stored exactly as typed`, same(held, f.sample), `${JSON.stringify(held)} vs ${JSON.stringify(f.sample)}`, cell(f, "route 1 · clerk"));
        }
        await p.goto(`${BASE}/${C.t}/premises/${prem.id}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1500);
        const page1 = await mainText(p);
        for (const f of PRM) {
          ok(`SEU Premise page shows ${f.label} = ${shown(f, f.sample)}`, page1.includes(f.label) && page1.includes(shown(f, f.sample)), "", cell(f, "view · Account detail / Premise page"));
        }
        await shot(p, "seu_premise_page", "text=Main Electric Panel Location");
        // Edit premise: change two, the rest unchanged
        await p.getByRole("button", { name: "Edit", exact: true }).first().click();
        const dlg = dialog(p);
        await dlg.waitFor();
        // the own-fields block draws once its registry read answers
        await dlg.locator('[id="custom_data.main_electric_panel_location"]').waitFor({ timeout: 20000 }).catch(() => {});
        await p.waitForTimeout(800);
        for (const f of PRM) await staffDrawn(dlg, f, "Edit premise", "edit screen");
        await dlg.locator('[id="custom_data.roof_age"]').selectOption("6–10");
        await tick(dlg.locator('[id="custom_data.appliances.Gas dryer"]'), true);
        await shot(p, "seu_edit_premise");
        await p.getByRole("button", { name: "Save premise" }).click();
        await p.waitForTimeout(2500);
        const after = (await p.api("GET", `/premises/${prem.id}`)).body?.custom_data ?? {};
        ok("SEU Edit premise saves Roof Age 6–10 and adds Gas dryer in the tenant's own option order",
          after.roof_age === "6–10" && same(after.appliances, ["Heat pump", "Electric range", "Gas dryer", "None of these"]), JSON.stringify(after), ["SEU", "Appliances", "edit screen"]);
        ok("SEU Edit premise leaves the other answers alone", after.generator_model === "Generac 22kW" && after.roof_shading === "Partial (25–50%)", JSON.stringify(after), ["SEU", "Roof Age", "edit screen"]);
        // ── New Account: the four account fields on Account preferences
        const unitNo = eligibleHome()[2];
        await p.goto(`${BASE}/${C.t}/accounts/new`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        await p.selectOption("#account_type", { index: 1 });
        await p.fill("#full_name", "Maria Okafor");
        await p.fill("#email", "maria.okafor@example.test");
        await p.fill("#phone", "(313) 555-0101");
        if (await p.locator("#gov_id_last4").count()) await p.fill("#gov_id_last4", "1188");
        await p.getByText("Person", { exact: true }).first().click();
        await p.locator("button", { hasText: /^Continue/ }).first().click();
        await p.waitForTimeout(1500);
        await p.locator("#unit_id").fill(unitNo);
        const opt = p.locator('[role="option"]', { hasText: unitNo }).first();
        await opt.waitFor({ timeout: 60000 });
        await opt.click();
        await p.fill("#opened_at", "2026-10-02");
        await p.locator("button", { hasText: /^Continue/ }).first().click();
        await p.waitForTimeout(1500);
        for (const f of ACC) await staffDrawn(p.locator("main"), f, "New Account", "route 1 · clerk");
        for (const f of ACC) await staffFill(p.locator("main"), f, f.sample);
        await shot(p, "seu_new_account_prefs", '[id="custom_data.name_on_dte_bill"]');
        for (let i = 0; i < 3 && (await p.locator("text=/Step 5 of 5/").count()) === 0; i += 1) {
          await p.locator("button", { hasText: /^Continue/ }).first().click();
          await p.waitForTimeout(1500);
        }
        const ans = p.waitForResponse((r) => r.url().endsWith(`/api/${C.t}/accounts`) && r.request().method() === "POST", { timeout: 60000 });
        await p.locator('button[data-variant="primary"]').last().click();
        const res = await ans;
        const created = await res.json().catch(() => ({}));
        ok("SEU New Account answers 201", res.status() === 201, `${res.status()} ${JSON.stringify(created).slice(0, 300)}`, ["SEU", "Name on DTE Bill", "route 1 · clerk"]);
        state.C.account = created.id;
        const acct = (await p.api("GET", `/accounts/${created.id}`)).body?.custom_data ?? {};
        for (const f of ACC) ok(`SEU route 1: ${f.label} stored exactly as typed`, same(acct[f.key], f.sample), JSON.stringify(acct[f.key]), cell(f, "route 1 · clerk"));
        await p.goto(`${BASE}/${C.t}/accounts/${created.id}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(2000);
        const ad = await mainText(p);
        for (const f of ACC) ok(`SEU Account detail shows ${f.label} = ${shown(f, f.sample)}`, ad.includes(f.label) && ad.includes(shown(f, f.sample)), "", cell(f, "view · Account detail / Premise page"));
        await shot(p, "seu_account_detail", "text=Name on DTE Bill");
        await p.locator('button[aria-label^="Edit account"]').first().click();
        await dialog(p).waitFor();
        await dialog(p).locator('[id="custom_data.name_on_dte_bill"]').waitFor({ timeout: 20000 }).catch(() => {});
        for (const f of ACC) await staffDrawn(dialog(p), f, "Account detail edit", "edit screen");
        await dialog(p).locator(`[id="custom_data.budgetwise_enrolled"]`).selectOption("false"); // DEF-SHL-9240
        await shot(p, "seu_account_edit");
        const patch = p.waitForResponse((r) => r.request().method() === "PATCH", { timeout: 60000 });
        await dialog(p).locator('button[data-variant="primary"]').last().click();
        const pr = await patch;
        ok("SEU Account detail edit saves Budgetwise Enrolled = No", pr.status() === 200 && JSON.stringify(pr.request().postDataJSON()) === '{"custom_data":{"budgetwise_enrolled":false}}', JSON.stringify(pr.request().postDataJSON()), ["SEU", "Budgetwise Enrolled", "edit screen"]);
        await p.waitForTimeout(1500);
        ok("SEU Account detail reads Budgetwise Enrolled No", /Budgetwise Enrolled\s*No/.test(await mainText(p)), "", ["SEU", "Budgetwise Enrolled", "view · Account detail / Premise page"]);
        // ── New Connection: account fields on step 1, premises fields on step 2 (drawn; A's walk commits one)
        await p.goto(`${BASE}/${C.t}/connections/new`, { waitUntil: "networkidle" });
        await p.waitForTimeout(2000);
        for (const f of ACC) await staffDrawn(p.locator("main"), f, "New Connection step 1", "New Connection step");
        await shot(p, "seu_nc_step1", '[id="custom_data.name_on_dte_bill"]');
        await p.goto(`${BASE}/${C.t}/connections/new?step=2`, { waitUntil: "networkidle" });
        await p.waitForTimeout(2000);
        for (const f of PRM) await staffDrawn(p.locator("main"), f, "New Connection step 2", "New Connection step");
        await shot(p, "seu_nc_step2", '[id="custom_data.main_electric_panel_location"]');
      },
    },
    19: {
      title: "SEU · route 2 — the customer answers all 13 on the portal; the request holds them; Approve copies them to the account and the premises",
      fn: async (ctx) => {
        const guestCtx = await ctx.browser.newContext({ viewport: { width: 1280, height: 1000 } });
        const g = await guestCtx.newPage();
        g.setDefaultTimeout(40000);
        const tok = `cfe2eseu${Date.now()}abcdefabcdef`;
        await g.goto(`${BASE}/${C.t}/portal/start-service/${tok}?address=${encodeURIComponent(NEW_ADDRESS)}`, { waitUntil: "networkidle" });
        const pblock = g.locator('[data-portal-questions="premises"]');
        await pblock.waitFor({ timeout: 30000 });
        const wire = await g.evaluate(async (u) => (await fetch(u)).text(), `${BASE}/api/${C.t}/portal/public/applications/${tok}`);
        for (const f of SEU_FIELDS) {
          const id = `cf-${f.entity}-${f.key}`;
          ok(`SEU portal API names ${f.label}`, wire.includes(f.key), "", cell(f, "route 2 · portal"));
          if (f.options) ok(`SEU portal API keeps ${f.label}'s options in order`, wire.includes(JSON.stringify(f.options)), "", cell(f, "route 2 · portal"));
          if (f.entity === "premises") {
            const q = g.locator(`[data-question="${f.key}"]`);
            ok(`SEU portal step 2 asks ${f.label}`, (await q.count()) === 1, "", cell(f, "route 2 · portal"));
            if (f.help) ok(`SEU portal shows ${f.label}'s help "${f.help}"`, ((await q.innerText().catch(() => "")) ?? "").includes(f.help), "", cell(f, "route 2 · portal"));
            await portalFill(g, f, ALT[f.key], id);
          }
        }
        await g.fill("#requested_start", startDate());
        await g.locator("#requested_start").blur();
        // a new address: the applicant ticks what they want (electric)
        const svc = g.locator('[data-service-pick="electric"] input');
        if ((await svc.count()) && !(await svc.isChecked())) await svc.click();
        await g.waitForTimeout(1000);
        await shot(g, "seu_portal_step2", '[data-portal-questions="premises"]');
        await g.click('[data-action="continue"]');
        await g.waitForSelector('[data-step="about"]');
        await g.fill("#first_name", "Amara");
        await g.locator("#first_name").blur();
        await g.fill("#last_name", "Okafor");
        await g.locator("#last_name").blur();
        await g.fill("#email", "amara.seu@example.test");
        await g.locator("#email").blur();
        await g.fill("#phone", "(313) 555-0144");
        await g.locator("#phone").blur();
        for (const f of ACC) {
          const q = g.locator(`[data-question="${f.key}"]`);
          ok(`SEU portal step 3 asks ${f.label}`, (await q.count()) === 1, "", cell(f, "route 2 · portal"));
          if (f.help) ok(`SEU portal shows ${f.label}'s help "${f.help}"`, ((await q.innerText().catch(() => "")) ?? "").includes(f.help), "", cell(f, "route 2 · portal"));
          await portalFill(g, f, ALT[f.key], `cf-${f.entity}-${f.key}`);
        }
        await g.waitForTimeout(1200);
        await shot(g, "seu_portal_step3", '[data-portal-questions="accounts"]');
        await g.click('[data-action="continue"]');
        await g.waitForSelector('[data-screen="CWP-009"]');
        await g.waitForTimeout(1200);
        await shot(g, "seu_portal_check_and_send");
        await g.click('[data-action="send"]');
        await g.waitForSelector("[data-reference]", { timeout: 30000 });
        const reference = ((await g.locator("[data-reference]").textContent()) ?? "").trim();
        ok("SEU portal: sent, with a reference", /^SR-/.test(reference), reference, ["SEU", "Name on DTE Bill", "route 2 · portal"]);
        await guestCtx.close();
        const p = await page(ctx, C);
        const found = await p.api("GET", `/service-requests?q=${encodeURIComponent(reference)}`);
        const requestId = (rowsOf(found.body).find((r) => r.request_no === reference) ?? rowsOf(found.body)[0])?.id;
        const held = (await p.api("GET", `/service-requests/${requestId}`)).body?.custom_data ?? {};
        for (const f of SEU_FIELDS) ok(`SEU portal → request holds ${f.label} exactly`, same(held?.[f.entity]?.[f.key], ALT[f.key]), JSON.stringify(held?.[f.entity]?.[f.key]), cell(f, "route 2 · portal"));
        await approveAndCompare(ctx, p, requestId, ALT, "route 2 · portal", "seu_portal", { newAddress: NEW_ADDRESS });
      },
    },
    20: {
      title: "SEU · route 3 — a clerk types all 13 on Staff New Request; Request detail shows them; Approve copies them",
      fn: async (ctx) => {
        const p = await page(ctx, C);
        // a home a move-in can open, at an address already on the register
        [PREMISE_NO, ADDRESS] = eligibleHome();
        await p.goto(`${BASE}/${C.t}/requests/new?step=1`, { waitUntil: "networkidle" });
        await p.waitForSelector("#account_type_code", { timeout: 30000 });
        const s1 = p.locator("[data-request-custom-input]").first();
        await s1.waitFor({ timeout: 30000 }).catch(() => {});
        for (const f of ACC) await staffDrawn(s1, f, "Staff New Request step 1", "Staff New Request");
        await p.fill("#applicant_name", "Okafor, Maria");
        await p.selectOption("#account_type_code", { index: 1 });
        for (const f of ACC) await staffFill(s1, f, REQ[f.key]);
        await shot(p, "seu_new_request_step1", "[data-request-custom-input]");
        await p.locator("button", { hasText: /^Continue/ }).last().click();
        await p.waitForSelector("#address_as_given", { timeout: 30000 });
        await p.fill("#address_as_given", ADDRESS);
        await p.waitForTimeout(2500);
        await p.locator(`[data-premises-option="${PREMISE_NO}"]`).first().click();
        await p.waitForTimeout(1000);
        if ((await p.locator("select#address_unit_as_given").count()) > 0) await p.selectOption("select#address_unit_as_given", { index: 1 });
        const panel = p.locator('[data-request-custom-input="premises"]');
        await panel.waitFor({ timeout: 30000 });
        for (const f of PRM) await staffDrawn(panel, f, "Staff New Request step 2", "Staff New Request");
        for (const f of PRM) await staffFill(panel, f, REQ[f.key]);
        await shot(p, "seu_new_request_step2", '[data-request-custom-input="premises"]');
        await p.locator("button", { hasText: /^Continue/ }).last().click();
        await p.waitForTimeout(3000);
        const requestId = new URL(p.url()).searchParams.get("request");
        const held = (await p.api("GET", `/service-requests/${requestId}`)).body?.custom_data ?? {};
        for (const f of SEU_FIELDS) ok(`SEU New Request holds ${f.label} exactly`, same(held?.[f.entity]?.[f.key], REQ[f.key]), JSON.stringify(held?.[f.entity]?.[f.key]), cell(f, "Staff New Request"));
        const sub = await p.api("POST", `/service-requests/${requestId}/submit`, {});
        ok("SEU New Request submitted", sub.status === 200, sub.text.slice(0, 300), ["SEU", "Name on DTE Bill", "Staff New Request"]);
        await approveAndCompare(ctx, p, requestId, REQ, "Staff New Request", "seu_request");
      },
    },
  };

  async function portalFill(g, f, v, id) {
    if (f.type === "text") {
      await g.fill(`#${id}`, String(v));
      await g.locator(`#${id}`).blur();
    } else if (f.type === "select") await g.locator(`#${id}`).selectOption(String(v));
    else if (f.type === "boolean") await g.locator(`#${id}`).selectOption(v ? "true" : "false");
    else if (f.type === "multi_select") {
      const fs = g.locator(`[data-question="${f.key}"]`);
      for (const o of f.options) {
        const input = fs.locator("label", { hasText: new RegExp(`^\\s*${o.replace(/[.*+?^${}()|[\]\\/]/g, "\\$&")}\\s*$`) }).locator("input");
        if ((await input.count()) && (await input.isChecked()) !== v.includes(o)) await input.click();
      }
    }
  }

  /** The move-in the approval raised, completed: the account and customer it
   *  opens are the FIRST records for this applicant (`DEF-CUS-9211`, fixed in
   *  2.467.5, carries the request's answers onto them). The same POST the
   *  Move-in wizard's last button sends. */
  async function completeMoveIn(p, unitId, requestId, name) {
    const r = await p.api("POST", `/units/${unitId}/move-in`, {
      account_type: "residential",
      opened_at: new Date().toISOString().slice(0, 10),
      contact: { full_name: name, phone: "(313) 555-0177" },
      customer: { display_name: name, kind: "person", identity: { phone: "(313) 555-0177", date_of_birth: "1987-12-04" } },
      service_request_id: requestId,
      // the services this unit actually takes
      services: psql(`select coalesce(string_agg(s.code, ','), '') from service_points sp join services s on s.id=sp.service_id where sp.unit_id='${unitId}'`).split(",").filter(Boolean),
    });
    return r;
  }

  /** New address: Approve as a NEW CONNECTION lands on the New Connection
   *  wizard holding the draft build; the clerk finishes steps 2–5 and Create
   *  makes the property — which must then hold the request's answers. */
  async function finishBuild(p, addr) {
    const pick = async (selector, preferred) => {
      if (!(await p.locator(selector).count())) return;
      const opts = await p.$$eval(`${selector} option`, (ns) => ns.filter((o) => !o.disabled && o.value !== "").map((o) => ({ v: o.value, t: o.textContent.trim() })));
      if (!opts.length) return;
      const cur = await p.inputValue(selector).catch(() => "");
      if (cur) return;
      const hit = preferred ? opts.find((o) => preferred.test(o.t) || preferred.test(o.v)) : null;
      await p.selectOption(selector, (hit ?? opts[0]).v);
    };
    const forward = async () => {
      const b = p.locator('[data-wizard="actions"] button').last();
      if (await b.isDisabled()) return false;
      await b.click();
      await p.waitForTimeout(2200);
      return true;
    };
    const h1 = async () => (await p.locator("h1").first().innerText().catch(() => "")).trim();
    for (let guard = 0; guard < 8; guard += 1) {
      const head = await h1();
      if (head === "Who is asking, and what for?") {
        await pick("#nc_owner_kind", /owner_occupier|landlord/);
        await pick("#nc_owner_category", /residential/i);
        await pick("#nc_owner_subcategory");
        await pick("#nc_mode", /our_crew/);
      } else if (head === "The premise") {
        if ((await p.inputValue("#nc_address").catch(() => "")) === "") await p.fill("#nc_address", addr);
        for (const [sel, v] of [["#nc_city", "Detroit"], ["#nc_state", "MI"], ["#nc_zip", "48201"]]) {
          if ((await p.locator(sel).count()) && (await p.inputValue(sel).catch(() => "")) === "") await p.fill(sel, v);
        }
        await pick("#nc_premise_type", /single_family/);
        await pick("#nc_route");
        await pick("#nc_scope", /new_premise/);
        if ((await p.locator("#services_available-add").count()) && !(await p.locator("main").innerText()).includes("Water")) {
          await p.selectOption("#services_available-add", "water").catch(() => {});
        }
        await p.waitForTimeout(800);
        await pick("#nc_plan", /Residential/);
        await p.waitForTimeout(1000);
        await shot(p, "seu_build_step2", '[id="custom_data.main_electric_panel_location"]');
      } else if (head === "The units") {
        if ((await p.inputValue("#nc_from").catch(() => "")) === "") await p.fill("#nc_from", "1").catch(() => {});
        if ((await p.inputValue("#nc_to").catch(() => "")) === "") await p.fill("#nc_to", "1").catch(() => {});
        await pick("#nc_common_occupancy", /VAC/);
        await pick("#nc_common_unit_type", /Residential/);
      } else if (head === "Charges") {
        await p.selectOption("#nc_payment_option", "").catch(() => {});
      } else if (head === "What will be created") {
        await shot(p, "seu_build_review");
        const wait = p.waitForResponse((r) => r.url().includes("/connections/commit"), { timeout: 120000 }).catch(() => null);
        await p.locator('[data-wizard="actions"] button').last().click();
        const resp = await wait;
        await p.waitForTimeout(3000);
        return resp;
      }
      if (!(await forward())) {
        await shot(p, `seu_build_held_${guard}`);
        return null;
      }
    }
    return null;
  }

  /** Request detail (view), then Approve, taking every Requested answer; the
   *  account and premises must then hold EXACTLY what was asked.
   *  `newAddress`: the property does not exist — Approve as a New connection,
   *  the clerk finishes the build in the New Connection wizard, Create makes
   *  the property. Otherwise a move-in onto a vacant unit of `PREMISE_NO`.
   *  Either way the applicant is FIRST-TIME: their customer and account do not
   *  exist at approval and are opened by the move-in afterwards. */
  async function approveAndCompare(ctx, p, requestId, want, routeCol, tag, { newAddress = null } = {}) {
    let prem = null;
    let unitId = null;
    if (!newAddress) {
      prem = rowsOf((await p.api("GET", `/premises/picker?q=${encodeURIComponent(ADDRESS)}&per=50`)).body).find((r) => r.premise_no === PREMISE_NO);
      // the unit the clerk picked on step 2 when it is this building's, else a vacant one
      const picked = psql(`select coalesce(resolved_unit_id::text, '') from service_requests where id='${requestId}'`);
      const ofThis = picked ? psql(`select count(*) from units where id='${picked}' and premises_id='${prem.id}' and rate_plan_id is not null`) : "0";
      unitId = ofThis === "1" ? picked : vacantUnit(prem.id, requestId);
      await p.api("PATCH", `/service-requests/${requestId}`, { picked_premises_id: prem.id, picked_unit_id: unitId });
    }
    await p.goto(`${BASE}/${C.t}/requests/${requestId}?tab=applicant`, { waitUntil: "networkidle" });
    const view = p.locator("[data-request-custom-detail]");
    await view.locator("dt").first().waitFor({ timeout: 30000 }).catch(() => {});
    const vt = (await view.innerText().catch(() => "")).replace(/\s+/g, " ");
    for (const f of SEU_FIELDS) {
      // a blank answer (a Yes/No left unticked on a staff screen, DEF-SHL-9240) has nothing to show
      if (want[f.key] === false && routeCol === "Staff New Request") continue;
      ok(`SEU Request detail (${tag}) shows ${f.label} = ${shown(f, want[f.key])}`, vt.includes(f.label) && vt.includes(shown(f, want[f.key])), "", cell(f, "view · Request detail"));
    }
    ok(`SEU Request detail (${tag}) is read-only`, (await view.locator("select,input,textarea").count()) === 0, "", ["SEU", "Appliances", "view · Request detail"]);
    await shot(p, `${tag}_request_detail`, "[data-request-custom-detail]");
    // Approve
    await p.locator('[data-decision-action="approve"]').first().click();
    const dlg = dialog(p);
    await dlg.waitFor();
    const kind = newAddress ? "new_connection" : "move_in";
    await p.locator(`[data-segment="${kind}"]`).first().click();
    await p.waitForTimeout(800);
    // PO 2026-10-11, option B: the Arrears row only POINTS at Search customer;
    // run the search, then its *No match* (`data-action="record-search"`).
    if ((await dlg.locator("[data-approve-arrears-search]").count()) > 0) {
      await dlg.locator("[data-customer-search]").first().click();
      const search = dlg.locator('[data-action="record-search"]');
      await search.first().waitFor({ timeout: 15000 });
      await search.first().click();
      await p.waitForTimeout(2500);
      if ((await dialog(p).count()) === 0) {
        await p.locator('[data-decision-action="approve"]').first().click();
        await dialog(p).waitFor();
      }
      await p.locator(`[data-segment="${kind}"]`).first().click();
      await p.waitForTimeout(800);
    }
    // an address that looks like one on file asks "Same property / It's a new address"
    const isNew = dlg.getByText("It's a new address", { exact: true });
    if (newAddress && (await isNew.count())) await isNew.first().click();
    for (const f of SEU_FIELDS) {
      const row = dlg.locator(`[data-copy-row="${f.key}"]`);
      if ((await row.count()) && (await row.getAttribute("data-copy-state")) === "conflict") await row.locator('[data-segment="requested"]').click();
    }
    await shot(p, `${tag}_approve`);
    const submit = dlg.locator("button", { hasText: /^Approve/ }).last();
    const enabled = (await submit.count()) > 0 && !(await submit.isDisabled());
    ok(`SEU Approve (${tag}, ${kind}) is enabled`, enabled, ((await dlg.textContent().catch(() => "")) ?? "").slice(0, 400), ["SEU", "Name on DTE Bill", "copied on approval"]);
    if (enabled) {
      await submit.click();
      await p.waitForTimeout(4500);
    }
    if (newAddress) {
      ok(`SEU ${tag}: Approve as New connection opens the build in the New Connection wizard`, /\/connections\/new\?build=/.test(p.url()), p.url(), ["SEU", "Roof Material", "copied on approval"]);
      const resp = await finishBuild(p, newAddress);
      ok(`SEU ${tag}: the build is created`, resp && resp.status() < 300, resp ? `${resp.status()} ${(await resp.text()).slice(0, 300)}` : "the wizard held", ["SEU", "Roof Material", "copied on approval"]);
      const pid = psql(`select id from premises where tenant_id='${tid()}' and address_line ilike '${newAddress.replace(/'/g, "''")}%' order by created_at desc limit 1`);
      prem = pid ? { id: pid } : null;
      unitId = pid ? psql(`select id from units where premises_id='${pid}' and not is_common_area order by unit_no limit 1`) : null;
    }
    const premHeld = prem ? ((await p.api("GET", `/premises/${prem.id}`)).body?.custom_data ?? {}) : {};
    for (const f of PRM) {
      ok(`SEU ${tag}: the ${newAddress ? "property the build created" : "property"} holds ${f.label} exactly as entered`, same(premHeld[f.key], want[f.key]),
        `${JSON.stringify(premHeld[f.key])} vs ${JSON.stringify(want[f.key])}`, cell(f, "copied on approval"));
    }
    // the first-time applicant's account: opened by the move-in, after approval
    let acctHeld = {};
    let acctId = null;
    if (unitId) {
      const moved = await completeMoveIn(p, unitId, requestId, tag === "seu_portal" ? "Amara Okafor" : "Maria Okafor");
      acctId = moved.body?.id ?? null;
      ok(`SEU ${tag}: the move-in opens the applicant's first account`, moved.status === 201, moved.text.slice(0, 300), ["SEU", "Name on DTE Bill", "copied on approval"]);
      acctHeld = acctId ? ((await p.api("GET", `/accounts/${acctId}`)).body?.custom_data ?? {}) : {};
      if (acctId) {
        await p.goto(`${BASE}/${C.t}/accounts/${acctId}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1800);
        await shot(p, `${tag}_new_account`, "text=Name on DTE Bill");
      }
    }
    for (const f of ACC) ok(`SEU ${tag}: the account the move-in opened holds ${f.label} exactly as entered`, same(acctHeld[f.key], want[f.key]), `${acctId} ${JSON.stringify(acctHeld[f.key])}`, cell(f, "copied on approval"));
    state.C[`${tag}_account`] = acctId;
    for (const f of SEU_FIELDS) {
      H.mark("SEU", f.label, same((f.entity === "premises" ? premHeld : acctHeld)[f.key], want[f.key]), routeCol === "route 2 · portal" ? "route 2 · portal" : "route 3 · request → approve");
    }
  }
}
