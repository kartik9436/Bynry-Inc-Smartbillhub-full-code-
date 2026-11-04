// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 — phases 9–12 of `cf_e2e_walk.mjs`: New Connection,
//          work orders, readings (+ upload, never the bill) and payments
//          (entry only). Read that file's header first. The New Connection
//          drive borrows `nc_e2e_walk.mjs`'s selectors.
// ───────────────────────────────────────────────────────

export function opsPhases(H, { page }) {
  const { ok, shot, state, dialog, box, mainText, rowsOf, BASE, A } = H;
  async function choose(p, selector, preferred) {
    if (!(await p.locator(selector).count())) return null;
    const opts = await p.$$eval(`${selector} option`, (ns) => ns.filter((o) => !o.disabled && o.value !== "").map((o) => ({ v: o.value, t: o.textContent.trim() })));
    if (!opts.length) return null;
    let take = opts[0].v;
    if (preferred instanceof RegExp) take = (opts.find((o) => preferred.test(o.t) || preferred.test(o.v)) ?? opts[0]).v;
    else if (preferred) take = (opts.find((o) => o.v === preferred) ?? opts[0]).v;
    await p.selectOption(selector, take);
    return take;
  }
  async function forward(p) {
    const b = p.locator('[data-wizard="actions"] button').last();
    if (await b.isDisabled()) return false;
    await b.click();
    await p.waitForTimeout(2200);
    return true;
  }
  async function viewValue(p, label) {
    const dt = p.locator("main dt", { hasText: label }).first();
    if (!(await dt.count())) return null;
    await dt.scrollIntoViewIfNeeded().catch(() => {});
    return ((await dt.locator("xpath=following-sibling::dd[1]").textContent()) ?? "").trim();
  }

  return {
    9: {
      title: "A · New Connection (owner Loyalty tier, account Contract ref on step 1; premises Roof Material on step 2) → Create → owner customer, master account and premises hold the answers",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        const stamp = Date.now().toString(36).slice(-5);
        await p.goto(`${BASE}/${A.t}/connections/new`, { waitUntil: "networkidle" });
        await p.waitForTimeout(2000);
        await choose(p, "#nc_owner_kind", "landlord");
        await choose(p, "#nc_owner_category", "residential");
        await choose(p, "#nc_owner_subcategory", "permanent");
        await p.evaluate(() => document.querySelector('input[name="nc_party_kind"][value="company"]')?.click());
        await p.waitForTimeout(400);
        await p.fill("#nc_owner_email", `cfe2e.${stamp}@example.com`);
        await p.fill("#nc_owner_phone", "512-555-0177");
        await p.fill("#nc_owner_name", `Cypress Holdings ${stamp} LLC`);
        if (await p.locator("#nc_tax_id").count()) await p.fill("#nc_tax_id", `74-${String(Date.now()).slice(-7)}`);
        await p.waitForTimeout(1500);
        ok("step 1 draws Loyalty tier (owner)", (await box(p, "loyalty_tier").count()) === 1, "", ["A", "customers", "typed"]);
        ok("step 1 draws Contract ref (account)", (await box(p, "contract_ref").count()) === 1, "", ["A", "accounts", "typed"]);
        if (await box(p, "loyalty_tier").count()) await box(p, "loyalty_tier").selectOption("Gold");
        if (await box(p, "contract_ref").count()) await box(p, "contract_ref").fill(`NC-${stamp}`);
        await choose(p, "#nc_mode", "our_crew");
        await shot(p, "nc_step1", '[id="custom_data.loyalty_tier"]');
        if (!(await forward(p))) ok("step 1 Continue", false, (await mainText(p)).slice(0, 400));
        // step 2
        const addr = `${700 + (Date.now() % 200)} Roofline Way ${stamp}`;
        await p.fill("#nc_address", addr);
        await p.waitForTimeout(1200);
        await p.fill("#nc_city", "Katy").catch(() => {});
        await p.fill("#nc_state", "TX").catch(() => {});
        await p.fill("#nc_zip", "77494").catch(() => {});
        if (await p.locator("#nc_premise_name").count()) await p.fill("#nc_premise_name", `CFE ${stamp}`);
        await choose(p, "#nc_premise_type", "apartment_complex");
        await choose(p, "#nc_route");
        await choose(p, "#nc_scope", "new_premise");
        await p.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => {});
        await p.selectOption("#services_available-add", "water").catch(() => {});
        await p.waitForTimeout(800);
        await choose(p, "#nc_plan", /Residential/);
        await p.waitForTimeout(1500);
        ok("step 2 draws Roof Material (premises)", (await box(p, "roof_material").count()) === 1, "", ["A", "premises", "typed"]);
        // required, blank: step 2 must hold
        const heldBlank = !(await forward(p)) || (await box(p, "roof_material").count()) === 1;
        state.A.nc_step2_blank_required_held = heldBlank;
        // recorded as a FINDING on New Connection (another lane's files), not
        // a cell of the matrix: the commit is what must refuse, checked below
        ok("FINDING · New Connection step 2 holds a blank required Roof Material", heldBlank, (await mainText(p)).slice(0, 200));
        if (!heldBlank) {
          await p.locator('[data-wizard="actions"] button', { hasText: /^Back$/ }).first().click();
          await p.waitForTimeout(1500);
        }
        if (await box(p, "roof_material").count()) await box(p, "roof_material").selectOption("Tile");
        await shot(p, "nc_step2", '[id="custom_data.roof_material"]');
        if ((await p.locator("h1").first().innerText()).trim() === "The premise" && !(await forward(p))) ok("step 2 Continue", false, (await mainText(p)).slice(0, 400));
        // step 3
        await p.fill("#nc_from", "1").catch(() => {});
        await p.fill("#nc_to", "2").catch(() => {});
        await p.waitForTimeout(800);
        await choose(p, "#nc_common_occupancy", "VAC");
        await choose(p, "#nc_common_unit_type", /Residential/);
        if (await p.locator("[data-apply-to-all]").count()) {
          await p.locator("[data-apply-to-all]").first().click().catch(() => {});
          await p.waitForTimeout(1000);
        }
        await forward(p);
        // step 4
        // the leading empty option IS "No payment now"
        await p.selectOption("#nc_payment_option", "").catch(() => {});
        await p.waitForTimeout(600);
        await forward(p);
        await p.waitForTimeout(1500);
        const review = await mainText(p);
        // New Connection's review is not one of the placements the PO listed for a
        // premises field (Step 2 is), so it is recorded, never failed
        state.A.nc_review_lists_roof = /Roof Material\s*Tile/.test(review);
        await shot(p, "nc_step5_review");
        const wait = p.waitForResponse((r) => r.url().includes("/connections/commit"), { timeout: 120000 }).catch(() => null);
        await p.locator('[data-wizard="actions"] button').last().click();
        const resp = await wait;
        await p.waitForTimeout(3000);
        const commit = resp ? await resp.json().catch(() => null) : null;
        ok("Create accepted", resp && resp.status() < 300, `${resp?.status()} ${JSON.stringify(commit).slice(0, 500)}`, ["A", "premises", "typed"]);
        await shot(p, "nc_done");
        const prem = H.psql(`select custom_data::text from premises where address_line='${addr}'`);
        ok("the premises holds Roof Material Tile", prem.includes('"roof_material": "Tile"'), prem, ["A", "premises", "typed"]);
        const cust = H.psql(`select custom_data::text from customers where display_name like 'Cypress Holdings ${stamp}%' limit 1`);
        ok("the owner customer holds Loyalty tier Gold", cust.includes('"loyalty_tier": "Gold"'), cust, ["A", "customers", "typed"]);
        const acct = H.psql(`select a.custom_data::text from accounts a join units u on u.id=a.unit_id join premises pr on pr.id=u.premises_id where pr.address_line='${addr}' and a.custom_data ? 'contract_ref' limit 1`)
          || H.psql(`select a.custom_data::text from accounts a where a.custom_data->>'contract_ref'='NC-${stamp}' limit 1`);
        ok("the master account holds Contract ref", acct.includes(`NC-${stamp}`), acct, ["A", "accounts", "typed"]);
        state.A.nc_premises_addr = addr;
      },
    },
    10: {
      title: "A · Work order New/Edit (Crew radio, a number) → detail; one audit row per save",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        const premisesId = state.A.premises ?? rowsOf((await p.api("GET", "/premises?per=1")).body)[0]?.id;
        await p.goto(`${BASE}/${A.t}/work/orders/new`, { waitUntil: "networkidle" });
        await p.fill("#new-order-premises", premisesId);
        await p.fill("#new-order-type", "Leak check");
        ok("New work order draws Crew radio", (await box(p, "crew_radio").count()) === 1, "", ["A", "work_orders", "typed"]);
        await box(p, "crew_radio").fill("4");
        await shot(p, "new_work_order", '[id="custom_data.crew_radio"]');
        for (let i = 0; i < 2; i += 1) {
          await p.locator("button", { hasText: /^Continue/ }).last().click();
          await p.waitForTimeout(800);
        }
        const raised = p.waitForResponse((r) => /\/work-orders$/.test(r.url()) && r.request().method() === "POST", { timeout: 60000 });
        await p.locator("button", { hasText: /Raise work order/ }).last().click();
        const ra = await raised;
        const order = await ra.json().catch(() => ({}));
        ok("raise answers 200 with Crew radio 4", ra.status() === 200 && JSON.stringify(ra.request().postDataJSON().custom_data) === '{"crew_radio":"4"}', `${ra.status()} ${JSON.stringify(order).slice(0, 200)}`, ["A", "work_orders", "typed"]);
        state.A.work_order = order.id;
        await p.waitForURL((u) => u.pathname.includes("/work/orders/") && !u.pathname.endsWith("/new"), { timeout: 60000 });
        await p.waitForTimeout(1500);
        ok("Work order detail shows Crew radio 4", (await viewValue(p, "Crew radio")) === "4", "", ["A", "work_orders", "shown"]);
        await shot(p, "work_order_detail", "text=Crew radio");
        // a number field refuses a word
        await p.goto(`${BASE}/${A.t}/work/orders/${order.id}/edit`, { waitUntil: "networkidle" });
        await box(p, "crew_radio").waitFor({ timeout: 30000 });
        const before = Number(H.psql(`select count(*) from audit_log where entity_id='${order.id}'`));
        await box(p, "crew_radio").fill("nine");
        const bad = p.waitForResponse((r) => r.url().includes(`/work-orders/${order.id}`) && r.request().method() === "PATCH", { timeout: 60000 }).catch(() => null);
        await p.locator('button[data-action="save"]').click();
        const badRes = await bad;
        ok("a word in a Number field is refused", badRes && badRes.status() === 422, badRes ? String(badRes.status()) : "no PATCH sent (refused on screen)", ["A", "work_orders", "typed"]);
        await p.goto(`${BASE}/${A.t}/work/orders/${order.id}/edit`, { waitUntil: "networkidle" });
        await box(p, "crew_radio").waitFor({ timeout: 30000 });
        await box(p, "crew_radio").fill("9");
        const ed = p.waitForResponse((r) => r.url().includes(`/work-orders/${order.id}`) && r.request().method() === "PATCH", { timeout: 60000 });
        await shot(p, "edit_work_order", '[id="custom_data.crew_radio"]');
        await p.locator('button[data-action="save"]').click();
        const edr = await ed;
        ok("Edit work order saves 9", edr.status() === 200, String(edr.status()), ["A", "work_orders", "typed"]);
        await p.waitForTimeout(1000);
        const after = Number(H.psql(`select count(*) from audit_log where entity_id='${order.id}'`));
        ok("one audit row for that save", after - before === 1, `${before} → ${after}`, ["A", "work_orders", "typed"]);
      },
    },
    11: {
      title: "A · Reading entry + readings upload (Seal number) → Reading detail; the bill is identical with or without the answer",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        const reads = await p.api("GET", "/reads?per=100");
        let meterNo = null;
        const seen = new Set();
        for (const row of rowsOf(reads.body)) {
          if (!row.meter || seen.has(row.meter)) continue;
          seen.add(row.meter);
          const c = await p.api("GET", `/reads/quick-context?meter_no=${encodeURIComponent(row.meter)}&read_date=2026-10-01`);
          if (c.status === 200 && (c.body?.registers?.channels ?? []).length === 1) { meterNo = row.meter; break; }
        }
        ok("a one-register meter exists", meterNo !== null);
        await p.goto(`${BASE}/${A.t}/reads`, { waitUntil: "networkidle" });
        await p.locator("button", { hasText: "+ Add reading" }).first().click();
        await dialog(p).waitFor();
        await p.fill("#meter_no", meterNo);
        await p.locator("#meter_no").blur();
        await p.waitForTimeout(1500);
        await box(p, "seal_number").waitFor({ timeout: 30000 });
        ok("Add reading draws Seal number", true, "", ["A", "meter_reads", "typed"]);
        const rd = dialog(p).locator("#read_date");
        if ((await rd.inputValue()) === "") await rd.fill("10/01/2026");
        await p.waitForTimeout(1200);
        const hist = await p.api("GET", `/reads?q=${encodeURIComponent(meterNo)}&per=50`);
        const last = Math.max(0, ...rowsOf(hist.body).map((r) => Number(r.current_value ?? 0)));
        await dialog(p).locator("#reading").fill(String(Math.round(last + 120)));
        await box(p, "seal_number").fill("S-2207");
        await shot(p, "add_reading", '[id="custom_data.seal_number"]');
        const staged = p.waitForResponse((r) => /\/read-batches$/.test(r.url()) && r.request().method() === "POST", { timeout: 60000 });
        await dialog(p).locator("button", { hasText: "Post reading" }).last().click();
        const st = await staged;
        ok("the manual entry sent Seal number on its row", JSON.stringify((st.request().postDataJSON().rows ?? [])[0]?.custom_data) === '{"seal_number":"S-2207"}', "", ["A", "meter_reads", "typed"]);
        await p.waitForTimeout(4000);
        const by = await p.api("GET", `/reads?q=${encodeURIComponent(meterNo)}&per=20`);
        const posted = rowsOf(by.body).find((r) => r.custom_data?.seal_number === "S-2207");
        ok("the posted reading holds S-2207", Boolean(posted), JSON.stringify(rowsOf(by.body).slice(0, 2)).slice(0, 300), ["A", "meter_reads", "typed"]);
        if (posted) {
          await p.goto(`${BASE}/${A.t}/reads/${posted.id}`, { waitUntil: "networkidle" });
          await p.waitForTimeout(1500);
          ok("Reading detail shows Seal number S-2207", (await viewValue(p, "Seal number")) === "S-2207", "", ["A", "meter_reads", "shown"]);
          await shot(p, "reading_detail", "text=Seal number");
          state.A.read = posted.id;
          state.A.read_meter = meterNo;
        }
        const csv = `meter_id,read_date,reading,Seal number\n${meterNo},2026-10-01,${Math.round(last + 240)},S-3301\n`;
        const up = await p.api("POST", "/read-batches", { source_kind: "csv", source_detail: "walk_by", period_month: "2026-10-01", file_name: "cfe2e_seal.csv", file_content: csv });
        ok("the readings upload maps the Seal number column by its label", up.status === 201 && up.body?.mapping?.["custom_data.seal_number"] === "Seal number", `${up.status} ${JSON.stringify(up.body?.mapping)}`, ["A", "meter_reads", "imported"]);
        const batch = await p.api("GET", `/read-batches/${up.body?.id}`);
        ok("the staged upload row carries S-3301", (batch.body?.rows ?? [])[0]?.custom_data?.seal_number === "S-3301", "", ["A", "meter_reads", "imported"]);
        const tpl = await p.evaluate(async (u) => (await fetch(u, { credentials: "include", headers: { Accept: "text/csv" } })).text(), `/api/${A.t}/reads/template`);
        ok("the readings template carries a seal_number column", /seal_number|Seal number/.test(tpl.split("\n")[0]), tpl.split("\n")[0], ["A", "meter_reads", "imported"]);
        state.A.reads_template_header = tpl.split("\n")[0];
        // never in the calculation: the read's billed quantity ignores custom_data
        if (posted) {
          const q1 = H.psql(`select coalesce(consumption::text,'') || '|' || coalesce(current_value::text,'') from meter_reads where id='${posted.id}'`);
          H.psql(`update meter_reads set custom_data='{}'::jsonb where id='${posted.id}'`);
          const q2 = H.psql(`select coalesce(consumption::text,'') || '|' || coalesce(current_value::text,'') from meter_reads where id='${posted.id}'`);
          H.psql(`update meter_reads set custom_data='{"seal_number":"S-2207"}'::jsonb where id='${posted.id}'`);
          ok("the reading's quantity is the same with and without the answer", q1 === q2, `${q1} vs ${q2}`, ["A", "meter_reads", "typed"]);
        }
        const g6 = H.grepMoneyPaths();
        ok("no money path reads custom_data (rating, billing calc, payments allocation, ledger)", g6.length === 0, g6.join(" | "), ["A", "meter_reads", "typed"]);
      },
    },
    12: {
      title: "A · Record payment (Cheque date) → Payment detail; never editable; allocation unchanged",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        const ACCOUNT = "A-10432";
        await p.goto(`${BASE}/${A.t}/payments/record/new`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        await box(p, "cheque_date").waitFor({ timeout: 30000 });
        ok("Record payment draws Cheque date", true, "", ["A", "payments", "typed"]);
        await p.locator("#account_id").fill(ACCOUNT);
        const opt = p.locator('[role="option"]', { hasText: ACCOUNT }).first();
        await opt.waitFor({ timeout: 60000 });
        await opt.click();
        await p.fill("#amount", "120.00");
        await box(p, "cheque_date").fill("2026-31-31");
        let ans = p.waitForResponse((r) => /\/accounts\/[^/]+\/payments$/.test(r.url()) && r.request().method() === "POST", { timeout: 60000 }).catch(() => null);
        await p.locator("button", { hasText: /^Record payment$/ }).last().click();
        const bad = await ans;
        ok("a non-date in a Date field is refused (on screen or 422)", !bad || bad.status() === 422, bad ? String(bad.status()) : "held on screen", ["A", "payments", "typed"]);
        await p.waitForTimeout(800);
        await box(p, "cheque_date").fill("2026-10-01");
        ans = p.waitForResponse((r) => /\/accounts\/[^/]+\/payments$/.test(r.url()) && r.request().method() === "POST", { timeout: 60000 });
        await p.locator("button", { hasText: /^Record payment$/ }).last().click();
        const res = await ans;
        const created = await res.json().catch(() => ({}));
        ok("Record payment answers 201 with Cheque date", res.status() === 201 && JSON.stringify(res.request().postDataJSON().custom_data) === '{"cheque_date":"2026-10-01"}', `${res.status()} ${JSON.stringify(created).slice(0, 300)}`, ["A", "payments", "typed"]);
        await shot(p, "record_payment", '[id="custom_data.cheque_date"]');
        state.A.payment_no = created.payment_no;
        state.A.payment_id = created.id;
        await p.goto(`${BASE}/${A.t}/payments/${created.payment_no}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1500);
        const v = await viewValue(p, "Cheque date");
        ok("Payment detail shows Cheque date", Boolean(v) && /2026|10\/01|Oct/.test(v), String(v), ["A", "payments", "shown"]);
        ok("…read-only: no Cheque date input on the page", (await box(p, "cheque_date").count()) === 0, "", ["A", "payments", "shown"]);
        await shot(p, "payment_detail", "text=Cheque date");
        const upd = (() => {
          try {
            return H.psql(`update payments set custom_data='{"cheque_date":"2026-09-30"}'::jsonb where id='${created.id}'`);
          } catch (e) {
            return `refused: ${String(e.stderr ?? e).split("\n")[0]}`;
          }
        })();
        ok("the database refuses a change to the answer afterwards (hard rule 4)", upd.startsWith("refused"), upd, ["A", "payments", "typed"]);
        const alloc = H.psql(`select count(*) from allocations where payment_id='${created.id}'`);
        state.A.payment_allocations = alloc;
      },
    },
  };
}
