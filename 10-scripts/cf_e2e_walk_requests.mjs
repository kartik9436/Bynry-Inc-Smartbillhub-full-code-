// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 — phases 13–15 of `cf_e2e_walk.mjs`: the staff New
//          Request with the Approve conflict pick, the customer portal's
//          new-service form ("Ask the customer" only; a "Don't ask" field
//          absent from screen AND API), and switch off / on keeping answers.
//          Read that file's header first. Selectors from the W6/W7 walks.
// ───────────────────────────────────────────────────────

export const startDate = () => {
  const d = new Date();
  d.setDate(d.getDate() + 21);
  return d.toISOString().slice(0, 10);
};

/** Approve a submitted request as a move-in, on the screen. Returns the dialog
 *  locator with the copy rows visible, or null. */
export async function openApprove(p, dialog) {
  await p.locator('[data-decision-action="approve"]').first().click();
  await dialog(p).waitFor();
  await p.locator('[data-segment="move_in"]').first().click();
  await p.waitForTimeout(800);
  // PO 2026-10-11, option B: the Arrears row only POINTS at Search customer
  // (`[data-approve-arrears-search]`); the search is run there and its answer
  // offers *No match* (`data-action="record-search"`), which records it.
  if ((await dialog(p).locator("[data-approve-arrears-search]").count()) > 0) {
    await dialog(p).locator("[data-customer-search]").first().click();
    const search = dialog(p).locator('[data-action="record-search"]');
    await search.first().waitFor({ timeout: 15000 });
    await search.first().click();
    await p.waitForTimeout(2500);
    if ((await dialog(p).count()) === 0) {
      await p.locator('[data-decision-action="approve"]').first().click();
      await dialog(p).waitFor();
    }
    await p.locator('[data-segment="move_in"]').first().click();
    await p.waitForTimeout(800);
  }
  return dialog(p);
}

export function requestPhases(H, { page }) {
  const { ok, shot, state, dialog, box, mainText, bodyText, rowsOf, BASE, A, signIn } = H;
  // a seeded building with many VACANT units: each approval below is a move-in
  // and takes one, so a re-run still finds a free one
  const ADDRESS = process.env.REQ_ADDRESS || "500 Main St";
  const PREMISE_NO = process.env.REQ_PREMISE_NO || "P-00059";
  const vacantUnit = (premisesId) => H.psql(`select u.id from units u where u.premises_id='${premisesId}' and not exists (select 1 from accounts a where a.unit_id=u.id) and not u.is_common_area and not exists (select 1 from service_requests sr where sr.resolved_unit_id=u.id) order by u.unit_no limit 1`);

  return {
    13: {
      title: "A · Staff New Request (Loyalty tier, Contract ref, Roof Material) → Request detail read-only → Approve onto a premises holding Metal: Existing pre-selected, pick Tile → premises Tile; audit row",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        const picked = await p.api("GET", `/premises/picker?q=${encodeURIComponent(ADDRESS)}&per=50`);
        const premises = rowsOf(picked.body).find((r) => r.premise_no === PREMISE_NO);
        const metal = await p.api("PATCH", `/premises/${premises.id}`, { custom_data: { roof_material: "Metal" } });
        ok("the property holds Roof Material Metal", metal.status === 200, metal.text.slice(0, 200));
        await p.goto(`${BASE}/${A.t}/requests/new?step=1`, { waitUntil: "networkidle" });
        await p.waitForSelector("#account_type_code", { timeout: 30000 });
        const step1 = p.locator("[data-request-custom-input]").first();
        await step1.waitFor({ timeout: 30000 }).catch(() => {});
        const s1 = (await step1.innerText().catch(() => "")).replace(/\s+/g, " ");
        ok("New Request step 1 draws Loyalty tier (customer)", s1.includes("Loyalty tier"), s1.slice(0, 200), ["A", "customers", "typed"]);
        ok("New Request step 1 draws Contract ref (account)", s1.includes("Contract ref"), s1.slice(0, 200), ["A", "accounts", "typed"]);
        await p.fill("#applicant_name", "Rivera, Elena");
        await p.selectOption("#account_type_code", { index: 1 });
        await box(p, "loyalty_tier").selectOption("Silver");
        await box(p, "contract_ref").fill("REQ-55");
        await shot(p, "new_request_step1", "[data-request-custom-input]");
        await p.locator("button", { hasText: /^Continue/ }).last().click();
        await p.waitForSelector("#address_as_given", { timeout: 30000 });
        await p.fill("#address_as_given", ADDRESS);
        await p.waitForTimeout(2500);
        await p.locator(`[data-premises-option="${PREMISE_NO}"]`).first().click();
        await p.waitForTimeout(1000);
        if ((await p.locator("select#address_unit_as_given").count()) > 0) await p.selectOption("select#address_unit_as_given", { index: 1 });
        const panel = p.locator('[data-request-custom-input="premises"]');
        await panel.waitFor({ timeout: 30000 });
        ok("New Request step 2 draws Roof Material", (await panel.innerText()).includes("Roof Material"), "", ["A", "premises", "typed"]);
        ok("…but not the clerk-only Meter vault code", !(await panel.innerText()).includes("Meter vault code"), "", ["A", "premises", "typed"]);
        await p.selectOption('[id="custom_data.roof_material"]', "Tile");
        await shot(p, "new_request_step2", '[data-request-custom-input="premises"]');
        await p.locator("button", { hasText: /^Continue/ }).last().click();
        await p.waitForTimeout(3000);
        const requestId = new URL(p.url()).searchParams.get("request");
        ok("the request draft exists", Boolean(requestId), p.url(), ["A", "service_request", "typed"]);
        let detail = await p.api("GET", `/service-requests/${requestId}`);
        const cd = detail.body?.custom_data ?? {};
        ok("the request's own copy holds all three answers",
          cd.premises?.roof_material === "Tile" && cd.customers?.loyalty_tier === "Silver" && cd.accounts?.contract_ref === "REQ-55", JSON.stringify(cd), ["A", "service_request", "typed"]);
        const sub = await p.api("POST", `/service-requests/${requestId}/submit`, {});
        ok("submitted", sub.status === 200, sub.text.slice(0, 300), ["A", "service_request", "typed"]);
        state.A.request = requestId;
        // the clerk points the request at a vacant unit of that building
        await p.api("PATCH", `/service-requests/${requestId}`, { picked_premises_id: premises.id, picked_unit_id: vacantUnit(premises.id) });
        await p.goto(`${BASE}/${A.t}/requests/${requestId}?tab=applicant`, { waitUntil: "networkidle" });
        const view = p.locator("[data-request-custom-detail]");
        await view.locator("dt", { hasText: "Roof Material" }).waitFor({ timeout: 30000 });
        const vt = (await view.innerText()).replace(/\s+/g, " ");
        ok("Request detail shows Tile, Silver and REQ-55 read-only",
          /Roof Material\s*Tile/.test(vt) && /Loyalty tier\s*Silver/.test(vt) && /Contract ref\s*REQ-55/.test(vt) && (await view.locator("select,input").count()) === 0, vt.slice(0, 300), ["A", "service_request", "shown"]);
        await shot(p, "request_detail", "[data-request-custom-detail]");
        const dlg = await openApprove(p, dialog);
        const conflict = dlg.locator('[data-copy-row="roof_material"]');
        await conflict.waitFor({ timeout: 30000 });
        const existing = conflict.locator('[data-segment="existing"]');
        const requested = conflict.locator('[data-segment="requested"]');
        ok("Approve: Existing Metal shown and pre-selected, Requested Tile beside it",
          ((await existing.textContent()) ?? "").includes("Metal") && (await existing.getAttribute("aria-checked")) === "true" && ((await requested.textContent()) ?? "").includes("Tile"), "", ["A", "service_request", "typed"]);
        await conflict.scrollIntoViewIfNeeded();
        await shot(p, "approve_conflict");
        await requested.click();
        const submit = dlg.locator("button", { hasText: /^Approve$/ }).last();
        ok("Approve is enabled", !(await submit.isDisabled()), ((await dlg.textContent()) ?? "").slice(0, 300), ["A", "service_request", "typed"]);
        await submit.click();
        await p.waitForTimeout(4000);
        const after = await p.api("GET", `/premises/${premises.id}`);
        ok("the property now reads Tile", after.body?.custom_data?.roof_material === "Tile", JSON.stringify(after.body?.custom_data), ["A", "service_request", "typed"]);
        detail = await p.api("GET", `/service-requests/${requestId}`);
        ok("the request is approved", detail.body?.header?.state === "approved", detail.body?.header?.state, ["A", "service_request", "typed"]);
        const audit = H.psql(`select after::text from audit_log where action='service_request.custom_fields_copied' and entity_id='${requestId}'`);
        ok("the audit row records the pick and the copy", audit.includes('"requested"') && audit.includes('"roof_material": "Tile"'), audit.slice(0, 400), ["A", "service_request", "typed"]);
        state.A.request_audit = audit.slice(0, 600);
        await shot(p, "after_approval");
      },
    },
    14: {
      title: "A · Portal new-service form (Loyalty tier + Roof Material asked; Meter vault code \"Don't ask\" absent from screen AND API) → staff Request detail → Approve copy",
      fn: async (ctx) => {
        const guestCtx = await ctx.browser.newContext({ viewport: { width: 1280, height: 1000 } });
        const g = await guestCtx.newPage();
        g.setDefaultTimeout(40000);
        const tok = `cfe2ewalk${Date.now()}abcdefabcdef`;
        await g.goto(`${BASE}/${A.t}/portal/start-service/${tok}?address=${encodeURIComponent(ADDRESS)}`, { waitUntil: "networkidle" });
        const block = g.locator('[data-portal-questions="premises"]');
        await block.waitFor({ timeout: 30000 });
        ok("portal step 2 asks Roof Material", ((await block.textContent()) ?? "").includes("Roof Material"), "", ["A", "portal", "typed"]);
        const body = await bodyText(g);
        ok("the Don't-ask Meter vault code is not on the portal screen", !body.includes("Meter vault code"), "", ["A", "portal", "isolation-of-dont-ask"]);
        const wire = await g.evaluate(async (u) => (await fetch(u)).text(), `${BASE}/api/${A.t}/portal/public/applications/${tok}`);
        ok("the portal API names Roof Material and Loyalty tier", wire.includes("roof_material") && wire.includes("loyalty_tier"), wire.slice(0, 300), ["A", "portal", "typed"]);
        ok("…and never the Don't-ask field, a clerk-only field, or a placement map",
          !/meter_vault_code|Meter vault code|contract_ref|gate_code|placement|REQUEST_DETAIL/.test(wire), wire.slice(0, 400), ["A", "portal", "isolation-of-dont-ask"]);
        await g.fill("#requested_start", startDate());
        await g.locator("#requested_start").blur();
        await g.locator("#cf-premises-roof_material").selectOption("Tile");
        await g.waitForTimeout(1200);
        await shot(g, "portal_step2_roof", '[data-portal-questions="premises"]');
        await g.click('[data-action="continue"]');
        await g.waitForSelector('[data-step="about"]');
        await g.fill("#first_name", "Amara");
        await g.locator("#first_name").blur();
        await g.fill("#last_name", "Okafor");
        await g.locator("#last_name").blur();
        await g.fill("#email", "amara.okafor@example.test");
        await g.locator("#email").blur();
        await g.fill("#phone", "(281) 555-0144");
        await g.locator("#phone").blur();
        const lt = g.locator("#cf-customers-loyalty_tier");
        ok("portal step 3 asks Loyalty tier", (await lt.count()) === 1, "", ["A", "portal", "typed"]);
        if (await lt.count()) await lt.selectOption("Gold");
        await g.waitForTimeout(1200);
        await shot(g, "portal_step3_loyalty", '[data-portal-questions="customers"]');
        await g.click('[data-action="continue"]');
        await g.waitForSelector('[data-screen="CWP-009"]');
        await g.waitForTimeout(1200);
        ok("Check and send restates both answers",
          ((await g.locator('[data-kv="cf-premises-roof_material"]').textContent()) ?? "").includes("Tile") && ((await g.locator('[data-kv="cf-customers-loyalty_tier"]').textContent()) ?? "").includes("Gold"), "", ["A", "portal", "typed"]);
        await shot(g, "portal_check_and_send");
        const sneak = await g.evaluate(async (u) => (await fetch(u, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ custom_data: { premises: { meter_vault_code: "999" } } }) })).status,
          `${BASE}/api/${A.t}/portal/public/applications/${tok}`);
        ok("the portal cannot write the Don't-ask field (422)", sneak === 422, String(sneak), ["A", "portal", "isolation-of-dont-ask"]);
        await g.click('[data-action="send"]');
        await g.waitForSelector("[data-reference]", { timeout: 30000 });
        const reference = ((await g.locator("[data-reference]").textContent()) ?? "").trim();
        ok("sent, with a reference", /^SR-/.test(reference), reference, ["A", "portal", "typed"]);
        await shot(g, "portal_sent");
        state.A.portal_token = tok;
        await guestCtx.close();
        const p = await page(ctx, A);
        const found = await p.api("GET", `/service-requests?q=${encodeURIComponent(reference)}`);
        const hit = rowsOf(found.body).find((r) => r.request_no === reference) ?? rowsOf(found.body)[0];
        const requestId = hit?.id;
        state.A.portal_request = requestId;
        const detail = await p.api("GET", `/service-requests/${requestId}`);
        ok("the request holds Tile and Gold from the portal",
          detail.body?.custom_data?.premises?.roof_material === "Tile" && detail.body?.custom_data?.customers?.loyalty_tier === "Gold", JSON.stringify(detail.body?.custom_data), ["A", "portal", "shown"]);
        await p.goto(`${BASE}/${A.t}/requests/${requestId}?tab=applicant`, { waitUntil: "networkidle" });
        const view = p.locator("[data-request-custom-detail]");
        await view.locator("dt", { hasText: "Roof Material" }).waitFor({ timeout: 30000 });
        ok("staff Request detail shows the portal's answers", /Roof Material\s*Tile/.test((await view.innerText()).replace(/\s+/g, " ")), "", ["A", "portal", "shown"]);
        await shot(p, "portal_request_detail", "[data-request-custom-detail]");
        const picked = await p.api("GET", `/premises/picker?q=${encodeURIComponent(ADDRESS)}&per=50`);
        const premises = rowsOf(picked.body).find((r) => r.premise_no === PREMISE_NO);
        await p.api("PATCH", `/premises/${premises.id}`, { custom_data: { roof_material: "Metal" } });
        const unitId = vacantUnit(premises.id);
        await p.api("PATCH", `/service-requests/${requestId}`, { picked_premises_id: premises.id, picked_unit_id: unitId });
        await p.goto(`${BASE}/${A.t}/requests/${requestId}?tab=applicant`, { waitUntil: "networkidle" });
        const dlg = await openApprove(p, dialog);
        const conflict = dlg.locator('[data-copy-row="roof_material"]');
        await conflict.waitFor({ timeout: 30000 });
        await conflict.locator('[data-segment="requested"]').click();
        const submit = dlg.locator("button", { hasText: /^Approve$/ }).last();
        const enabled = !(await submit.isDisabled());
        if (!enabled) await shot(p, "portal_approve_disabled");
        ok("Approve is enabled for the portal's request", enabled, ((await dlg.textContent()) ?? "").slice(0, 400), ["A", "portal", "typed"]);
        if (enabled) {
          await submit.click();
          await p.waitForTimeout(4000);
        }
        const prem = await p.api("GET", `/premises/${premises.id}`);
        ok("Approve copied the portal's Tile onto the property", prem.body?.custom_data?.roof_material === "Tile", JSON.stringify(prem.body?.custom_data), ["A", "portal", "typed"]);
      },
    },
    15: {
      title: "A · switch a field OFF → gone from input screens, answers kept; ON → answers return",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        const roofId = state.A.roof_material;
        const premId = state.A.premises;
        const off = await p.api("PATCH", `/settings/custom-fields/${roofId}`, { active: false });
        ok("Roof Material switched off", off.status === 200, off.text.slice(0, 200), ["A", "premises", "off/on"]);
        await p.goto(`${BASE}/${A.t}/premises/new?mode=single_premise&step=2`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        ok("Add Premises no longer draws Roof Material", !(await mainText(p)).includes("Roof Material"), "", ["A", "premises", "off/on"]);
        await shot(p, "off_add_premises");
        await p.goto(`${BASE}/${A.t}/premises/${premId}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        ok("the Premise page no longer shows it", !(await mainText(p)).includes("Roof Material"), "", ["A", "premises", "off/on"]);
        const held = H.psql(`select custom_data->>'roof_material' from premises where id='${premId}'`);
        ok("the stored answer is kept while off", held === "Tile", held, ["A", "premises", "off/on"]);
        // a premises save while off does not wipe it
        await p.api("PATCH", `/premises/${premId}`, { custom_data: { meter_vault_code: "MV-10" } });
        const still = H.psql(`select custom_data->>'roof_material' from premises where id='${premId}'`);
        ok("an edit while it is off leaves the answer alone", still === "Tile", still, ["A", "premises", "off/on"]);
        const on = await p.api("PATCH", `/settings/custom-fields/${roofId}`, { active: true });
        ok("switched back on", on.status === 200, "", ["A", "premises", "off/on"]);
        await p.goto(`${BASE}/${A.t}/premises/${premId}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        ok("the answer returns on the Premise page", /Roof Material\s*Tile/.test(await mainText(p)), "", ["A", "premises", "off/on"]);
        await shot(p, "on_premise_page", "text=Roof Material");
      },
    },
  };
}
