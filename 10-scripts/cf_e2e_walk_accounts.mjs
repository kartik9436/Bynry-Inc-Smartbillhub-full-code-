// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 — phase 8 of `cf_e2e_walk.mjs`: New Account and the
//          account's own screens (accounts, customers, contacts, mailing
//          addresses, service agreements). Read that file's header first.
// ───────────────────────────────────────────────────────

export function accountPhases(H, { page }) {
  const { ok, shot, state, dialog, box, mainText, rowsOf, BASE, A } = H;
  const contBtn = (p) => p.locator("button", { hasText: /^Continue/ }).first();
  const cont = async (p) => {
    await contBtn(p).click();
    await p.waitForTimeout(1500);
  };
  async function viewValue(p, label, scope = "main") {
    const dt = p.locator(`${scope} dt`, { hasText: label }).first();
    if (!(await dt.count())) return null;
    await dt.scrollIntoViewIfNeeded().catch(() => {});
    return ((await dt.locator("xpath=following-sibling::dd[1]").textContent()) ?? "").trim();
  }
  return {
    8: {
      title: "A · New Account (Loyalty tier, Contract ref required, Delivery note, Contract term) → Account detail; Edit account, Edit customer, contact Preferred name, Change plan",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        // a vacant seeded unit (a re-run takes the next one)
        const UNIT = process.env.UNIT || H.psql(`select u.unit_no from units u join tenants t on t.id=u.tenant_id where t.subdomain='${A.t}'
          and u.unit_no in ('U-00102','U-00101-A','U-00101-B','U-00214-200','U-00318-101') and not exists (select 1 from accounts a where a.unit_id=u.id) order by u.unit_no desc limit 1`);
        await p.goto(`${BASE}/${A.t}/accounts/new`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        await p.selectOption("#account_type", "residential");
        await p.fill("#full_name", "Rosa Pemberton");
        await p.fill("#email", "rosa.pemberton@example.com");
        await p.fill("#phone", "(281) 555-0199");
        if (await p.locator("#gov_id_last4").count()) await p.fill("#gov_id_last4", "4471");
        await p.getByText("Person", { exact: true }).first().click();
        ok("New Account step 1 draws Loyalty tier (customer)", (await box(p, "loyalty_tier").count()) === 1, "", ["A", "customers", "typed"]);
        await box(p, "loyalty_tier").selectOption("Gold");
        await p.locator("#mailing_same").setChecked(false, { force: true });
        await p.fill("#mailing_line1", "PO Box 9");
        await p.fill("#mailing_city", "Katy");
        await p.locator("#mailing_state").fill("TX");
        const st = p.locator('[role="option"]', { hasText: "TX" }).first();
        if (await st.count()) await st.click();
        await p.fill("#mailing_postal_code", "77494");
        ok("New Account draws Delivery note on the mailing block", (await box(p, "delivery_note").count()) === 1, "", ["A", "addresses", "typed"]);
        await box(p, "delivery_note").fill("Ring twice");
        await shot(p, "new_account_step1", '[id="custom_data.loyalty_tier"]');
        await cont(p);
        await p.locator("#unit_id").fill(UNIT);
        const option = p.locator('[role="option"]', { hasText: UNIT }).first();
        await option.waitFor({ timeout: 60000 });
        await option.click();
        await p.fill("#opened_at", "2026-10-02");
        await box(p, "contract_term").waitFor({ timeout: 20000 }).catch(() => {});
        ok("New Account's unit step draws Contract term (service)", (await box(p, "contract_term").count()) === 1, "", ["A", "service_agreements", "typed"]);
        await box(p, "contract_term").selectOption("12 months");
        await shot(p, "new_account_unit_step", '[id="custom_data.contract_term"]');
        await cont(p);
        ok("New Account's preferences step draws Contract ref (account)", (await box(p, "contract_ref").count()) === 1, "", ["A", "accounts", "typed"]);
        // required, left blank: Continue holds and says so — or, if it lets the
        // clerk on, the commit must refuse and bring them back to the box.
        await cont(p);
        let held = (await box(p, "contract_ref").count()) === 1;
        if (!held) {
          await cont(p);
          const blankAns = p.waitForResponse((r) => r.url().endsWith(`/api/${A.t}/accounts`) && r.request().method() === "POST", { timeout: 60000 }).catch(() => null);
          await p.locator('button[data-variant="primary"]').last().click();
          const blank = await blankAns;
          await p.waitForTimeout(2000);
          state.A.new_account_blank_required = { status: blank?.status(), body: blank ? (await blank.text()).slice(0, 400) : null, back_on_box: (await box(p, "contract_ref").count()) === 1, text: (await mainText(p)).slice(0, 500) };
          await shot(p, "new_account_contract_ref_blank_commit");
          held = (await box(p, "contract_ref").count()) === 1 && blank?.status() === 422;
          ok("a blank required Contract ref: Continue lets the clerk past it (finding), the commit refuses 422 and returns to the box",
            held, JSON.stringify(state.A.new_account_blank_required), ["A", "accounts", "typed"]);
          if (!held && (await box(p, "contract_ref").count()) === 0) {
            // back to step 3 through the review's own Edit link (the third block)
            await p.locator("main").getByText(/^Edit/).nth(2).click();
            await p.waitForTimeout(1500);
          }
        } else {
          const said = await mainText(p);
          ok("a blank required Contract ref holds the step and names it", /Contract ref/.test(said), said.slice(0, 300), ["A", "accounts", "typed"]);
        }
        await shot(p, "new_account_contract_ref_required", '[id="custom_data.contract_ref"]');
        await box(p, "contract_ref").fill("CR-7788");
        for (let i = 0; i < 4 && (await p.locator("text=/Step 5 of 5/").count()) === 0 && (await contBtn(p).count()); i += 1) await cont(p);
        const answer = p.waitForResponse((r) => r.url().endsWith(`/api/${A.t}/accounts`) && r.request().method() === "POST", { timeout: 60000 });
        await p.locator('button[data-variant="primary"]').last().click();
        const res = await answer;
        const created = await res.json().catch(() => ({}));
        ok("POST /accounts answers 201", res.status() === 201, `${res.status()} ${JSON.stringify(created).slice(0, 400)}`, ["A", "accounts", "typed"]);
        state.A.account = created.id;
        const fresh = (await p.api("GET", `/accounts/${created.id}`)).body;
        ok("the account holds Contract ref CR-7788", fresh?.custom_data?.contract_ref === "CR-7788", JSON.stringify(fresh?.custom_data), ["A", "accounts", "typed"]);
        ok("the mailing row holds Delivery note", fresh?.addresses?.find((a) => a.kind === "mailing")?.custom_data?.delivery_note === "Ring twice", "", ["A", "addresses", "typed"]);
        ok("every service holds Contract term 12 months", (fresh?.service_agreements ?? []).length > 0 && fresh.service_agreements.every((a) => a.custom_data?.contract_term === "12 months"),
          JSON.stringify(fresh?.service_agreements?.map((a) => a.custom_data)), ["A", "service_agreements", "typed"]);
        const custId = fresh?.customer?.id ?? fresh?.customer_id ?? fresh?.customers?.[0]?.id;
        state.A.customer = custId;
        const cust = H.psql(`select c.custom_data->>'loyalty_tier' from customers c join customer_accounts ca on ca.customer_id=c.id where ca.account_id='${created.id}' limit 1`);
        ok("the customer holds Loyalty tier Gold", cust === "Gold", cust, ["A", "customers", "typed"]);
        // Account detail
        await p.goto(`${BASE}/${A.t}/accounts/${created.id}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(2000);
        ok("Account detail shows Contract ref", (await viewValue(p, "Contract ref")) === "CR-7788", "", ["A", "accounts", "shown"]);
        ok("Account detail header shows Loyalty tier", (await viewValue(p, "Loyalty tier")) === "Gold", "", ["A", "customers", "shown"]);
        const mailing = (await p.locator('[data-overview-group="mailing-address"]').innerText().catch(() => "")).replace(/\s+/g, " ");
        ok("Account detail mailing group shows Delivery note", /Delivery note\s*Ring twice/.test(mailing), mailing.slice(0, 200), ["A", "addresses", "shown"]);
        const service = (await p.locator('[data-overview-group="service"]').innerText().catch(() => "")).replace(/\s+/g, " ");
        ok("Account detail services group shows Contract term", /Contract term\s*12 months/.test(service), service.slice(0, 300), ["A", "service_agreements", "shown"]);
        await shot(p, "account_detail", "text=Contract ref");
        // Edit account (S21 input)
        await p.locator('button[aria-label^="Edit account"]').first().click();
        await dialog(p).waitFor();
        await box(p, "contract_ref").waitFor({ timeout: 20000 }).catch(() => {});
        ok("Edit account offers Contract ref", (await box(p, "contract_ref").count()) === 1, "", ["A", "accounts", "typed"]);
        await box(p, "contract_ref").fill("CR-7789");
        const patch = p.waitForResponse((r) => r.request().method() === "PATCH", { timeout: 60000 });
        await dialog(p).locator('button[data-variant="primary"]').last().click();
        const pr = await patch;
        ok("only the change travels and saves", pr.status() === 200 && JSON.stringify(pr.request().postDataJSON()) === '{"custom_data":{"contract_ref":"CR-7789"}}', JSON.stringify(pr.request().postDataJSON()), ["A", "accounts", "typed"]);
        await p.waitForTimeout(1200);
        // contact Preferred name (required on the contact edit)
        await p.locator('[data-overview-group="customer"] button').first().click();
        await dialog(p).waitFor();
        const pn = box(p, "preferred_name");
        await pn.waitFor({ timeout: 20000 }).catch(() => {});
        ok("the contact edit offers Preferred name", (await pn.count()) === 1, "", ["A", "contacts", "typed"]);
        await p.fill("#contact_phone", "+1 (281) 555-0188");
        await pn.fill("");
        const r1 = p.waitForResponse((r) => r.request().method() === "PATCH", { timeout: 60000 });
        await dialog(p).locator('button[data-variant="primary"]').last().click();
        const refused = await r1;
        await p.waitForTimeout(800);
        ok("a blank required Preferred name is refused, the form kept", refused.status() === 422 && (await dialog(p).count()) === 1 && (await p.inputValue("#contact_phone")) === "+1 (281) 555-0188",
          String(refused.status()), ["A", "contacts", "typed"]);
        await shot(p, "contact_required_refused");
        await pn.fill("Rosie");
        const r2 = p.waitForResponse((r) => r.request().method() === "PATCH", { timeout: 60000 });
        await dialog(p).locator('button[data-variant="primary"]').last().click();
        const saved = await r2;
        ok("Preferred name Rosie saved", saved.status() === 200, String(saved.status()), ["A", "contacts", "typed"]);
        await p.waitForTimeout(1500);
        const cg = (await p.locator('[data-overview-group="customer"]').innerText().catch(() => "")).replace(/\s+/g, " ");
        ok("Account detail → Customer shows Preferred name Rosie", /Preferred name\s*Rosie/.test(cg), cg.slice(0, 300), ["A", "contacts", "shown"]);
        await shot(p, "account_customer_group", '[data-overview-group="customer"]');
        // Edit customer (CUSTOMER_EDIT)
        const customers = await p.api("GET", `/customers?q=${encodeURIComponent("Rosa Pemberton")}`);
        const c = rowsOf(customers.body).find((x) => (x.accounts ?? []).some((a) => a.id === created.id)) ?? rowsOf(customers.body)[0];
        await p.goto(`${BASE}/${A.t}/customers?q=${encodeURIComponent("Rosa Pemberton")}`, { waitUntil: "networkidle" });
        await p.locator(`[data-testid="customer-edit-${c.id}"]`).first().click();
        await dialog(p).waitFor();
        await box(p, "loyalty_tier").waitFor({ timeout: 20000 });
        ok("Edit customer opens with Gold", (await box(p, "loyalty_tier").inputValue()) === "Gold", "", ["A", "customers", "typed"]);
        await box(p, "loyalty_tier").selectOption("Silver");
        await shot(p, "edit_customer");
        const cs = p.waitForResponse((r) => r.url().includes(`/customers/${c.id}`) && r.request().method() === "PATCH", { timeout: 60000 });
        await dialog(p).locator('button[type="submit"]').last().click();
        ok("Edit customer saves Silver", (await cs).status() === 200, "", ["A", "customers", "typed"]);
        // Change plan keeps untouched answers
        await p.goto(`${BASE}/${A.t}/accounts/${created.id}/change-plan`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1500);
        const radios = p.locator('input[type="radio"][name="rate_plan_id"]:not([disabled]):not(:checked)');
        if ((await radios.count()) > 0) {
          await p.locator(`label[for="${await radios.first().getAttribute("id")}"]`).click();
          if (await p.locator("#drop_ack").count()) await p.locator("#drop_ack").check({ force: true });
          await cont(p);
          await p.fill("#effective_on", "2026-11-01");
          const prev = p.locator("button", { hasText: /preview/i }).first();
          if (await prev.count()) {
            await prev.click();
            await p.waitForTimeout(2000);
          }
          await cont(p);
          await box(p, "contract_term").waitFor({ timeout: 20000 }).catch(() => {});
          ok("Change plan's confirm step offers Contract term", (await box(p, "contract_term").count()) === 1, "", ["A", "service_agreements", "typed"]);
          await box(p, "contract_term").selectOption("24 months");
          await shot(p, "change_plan_contract_term", '[id="custom_data.contract_term"]');
          const confirm = p.waitForResponse((r) => r.url().endsWith("/plan-changes") && r.request().method() === "POST", { timeout: 60000 });
          await p.locator('button[data-variant="primary"]').last().click();
          const cr = await confirm;
          ok("Change plan answers 200/201", [200, 201].includes(cr.status()), `${cr.status()} ${(await cr.text()).slice(0, 300)}`, ["A", "service_agreements", "typed"]);
          const after = (await p.api("GET", `/accounts/${created.id}`)).body;
          const open = (after?.service_agreements ?? []).filter((a) => a.ended_on === null);
          ok("every open service now reads 24 months", open.length > 0 && open.every((a) => a.custom_data?.contract_term === "24 months"), JSON.stringify(open.map((a) => a.custom_data)), ["A", "service_agreements", "typed"]);
          ok("Change plan left the account's other answers untouched",
            after?.custom_data?.contract_ref === "CR-7789" && after?.addresses?.find((a) => a.kind === "mailing")?.custom_data?.delivery_note === "Ring twice",
            JSON.stringify([after?.custom_data, after?.addresses?.map((a) => a.custom_data)]), ["A", "service_agreements", "typed"]);
        } else ok("Change plan offers another plan", false, "no selectable plan", ["A", "service_agreements", "typed"]);
      },
    },
  };
}
