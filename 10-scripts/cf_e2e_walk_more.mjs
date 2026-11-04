// ── Trace ──────────────────────────────────────────────
// Change:  CR-161-BRC10 — phases 4 onward of `cf_e2e_walk.mjs`: utility A
//          using every field in the order a utility lives. Read that file's
//          header first.
// ───────────────────────────────────────────────────────
import { readFileSync } from "node:fs";

export function more(H, { page }) {
  const { ok, shot, state, dialog, box, mainText, rowsOf, BASE, A } = H;
  const cont = async (p) => {
    await p.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => /^continue/i.test((b.textContent || "").trim()))?.click());
    await p.waitForTimeout(900);
  };

  return {
    4: {
      title: "A · Add Premises (Roof Material required), unit Gate code, service-point Valve location → Premise page, Units tab, list column, Edit premise, Edit unit, Add units",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        const addr = `4410 Roofline Dr ${Date.now().toString(36).slice(-4)}`;
        await p.goto(`${BASE}/${A.t}/premises/new?mode=single_premise&step=2`, { waitUntil: "networkidle" });
        await p.waitForTimeout(800);
        const m = await mainText(p);
        ok("Add Premises Step 2 draws Roof Material", m.includes("Roof Material"), "", ["A", "premises", "typed"]);
        ok("Add Premises Step 2 draws Gate code (first unit)", m.includes("Gate code"), "", ["A", "units", "typed"]);
        ok("Add Premises Step 2 draws Valve location per service", (await p.locator("text=Valve location").count()) >= 1, "", ["A", "service_points", "typed"]);
        ok("Add Premises Step 2 draws Meter vault code (clerk-only field)", m.includes("Meter vault code"), "", ["A", "premises", "typed"]);
        await p.fill("#address_line", addr);
        await box(p, "gate_code").fill("4471");
        await box(p, "valve_location").first().fill("Front curb");
        await box(p, "meter_vault_code").fill("MV-9");
        await shot(p, "add_premises_step2");
        await p.getByRole("button", { name: "Continue" }).click();
        await p.waitForTimeout(800);
        await p.getByRole("button", { name: /Create premise/ }).click();
        await p.waitForTimeout(2500);
        const roofBox = box(p, "roof_material");
        ok("blank required Roof Material refused ON its box", (await roofBox.getAttribute("aria-invalid")) === "true", "", ["A", "premises", "typed"]);
        ok("…the rest of the form kept", (await box(p, "gate_code").inputValue()) === "4471" && (await p.inputValue("#address_line")) === addr, "", ["A", "premises", "typed"]);
        await shot(p, "add_premises_required_refused", '[id="custom_data.roof_material"]');
        await roofBox.selectOption("Tile");
        const sent = p.waitForRequest((r) => /\/api\/[^/]+\/premises$/.test(r.url()) && r.method() === "POST", { timeout: 30000 }).catch(() => null);
        await p.getByRole("button", { name: /Retry/ }).click();
        const req = await sent;
        // kept so the isolation phase can replay A's exact payload as utility B
        if (req) state.A.add_premises_payload = req.postDataJSON();
        await p.waitForTimeout(3000);
        const found = await p.api("GET", `/premises?q=${encodeURIComponent(addr)}&per=5`);
        const prem = rowsOf(found.body)[0];
        ok("the premise saved Tile", prem?.custom_data?.roof_material === "Tile", JSON.stringify(prem?.custom_data), ["A", "premises", "typed"]);
        state.A.premises = prem?.id;
        await p.goto(`${BASE}/${A.t}/premises/${prem.id}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        const pg = await mainText(p);
        ok("Premise page shows Roof Material Tile", /Roof Material\s*Tile/.test(pg), pg.slice(0, 300), ["A", "premises", "shown"]);
        ok("Premise page shows Meter vault code MV-9", /Meter vault code\s*MV-9/.test(pg), "", ["A", "premises", "shown"]);
        await shot(p, "premise_page", "text=Roof Material");
        await p.goto(`${BASE}/${A.t}/premises/${prem.id}?tab=units`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        const units = await mainText(p);
        ok("Units tab shows Gate code 4471", /gate code/i.test(units) && units.includes("4471"), units.slice(-300), ["A", "units", "shown"]);
        ok("Units tab shows Valve location, naming the service", /valve location/i.test(units) && /Front curb/.test(units), units.slice(-300), ["A", "service_points", "shown"]);
        await shot(p, "premise_units_tab");
        // Edit premise
        await p.goto(`${BASE}/${A.t}/premises/${prem.id}`, { waitUntil: "networkidle" });
        await p.getByRole("button", { name: "Edit", exact: true }).first().click();
        const editBox = p.locator('[role="dialog"] [id="custom_data.roof_material"]');
        await editBox.waitFor({ timeout: 20000 });
        ok("Edit premise opens with Tile", (await editBox.inputValue()) === "Tile", "", ["A", "premises", "typed"]);
        await editBox.selectOption("Shingle");
        await shot(p, "edit_premise");
        await p.getByRole("button", { name: "Save premise" }).click();
        await p.waitForTimeout(2500);
        const after = await p.api("GET", `/premises/${prem.id}`);
        ok("Edit premise saved Shingle, Meter vault code untouched",
          after.body?.custom_data?.roof_material === "Shingle" && after.body?.custom_data?.meter_vault_code === "MV-9", JSON.stringify(after.body?.custom_data), ["A", "premises", "typed"]);
        await p.api("PATCH", `/premises/${prem.id}`, { custom_data: { roof_material: "Tile" } });
        // premises list column
        await p.goto(`${BASE}/${A.t}/premises?q=${encodeURIComponent("Roofline")}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        ok("Premises list carries a Roof Material column", (await p.locator("main th", { hasText: "Roof Material" }).count()) > 0, "", ["A", "premises", "shown"]);
        ok("…reading Tile on the new row", (await p.locator("main tr", { hasText: addr }).first().innerText().catch(() => "")).includes("Tile"), "", ["A", "premises", "shown"]);
        await shot(p, "premises_list_column");
        // Edit unit (UNIT_EDIT)
        const detail = await p.api("GET", `/premises/${prem.id}`);
        const unitId = detail.body?.units?.[0]?.id ?? H.psql(`select id from units where premises_id='${prem.id}' limit 1`);
        state.A.unit = unitId;
        await p.goto(`${BASE}/${A.t}/premises/units/${unitId}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1500);
        const editBtn = p.getByRole("button", { name: /^Edit/ }).first();
        if (await editBtn.count()) await editBtn.click();
        const gb = p.locator('[role="dialog"] [id="custom_data.gate_code"]');
        const drawn = await gb.waitFor({ timeout: 15000 }).then(() => true).catch(() => false);
        ok("Edit unit draws Gate code holding 4471", drawn && (await gb.inputValue()) === "4471", "", ["A", "units", "typed"]);
        if (drawn) {
          await gb.fill("4472");
          await shot(p, "edit_unit");
          await dialog(p).locator('button[data-variant="primary"], button[type="submit"]').last().click();
          await p.waitForTimeout(2000);
          const held = H.psql(`select custom_data->>'gate_code' from units where id='${unitId}'`);
          ok("Edit unit saved 4472", held === "4472", held, ["A", "units", "typed"]);
        } else await shot(p, "edit_unit_missing");
        // Add units wizard (UNIT_ADD)
        await p.goto(`${BASE}/${A.t}/premises/units/new`, { waitUntil: "networkidle" });
        await p.waitForTimeout(2000);
        ok("Add units draws Gate code", (await box(p, "gate_code").count()) > 0, "", ["A", "units", "typed"]);
        // pick the building just made: its services decide the service-point blocks
        await p.locator("#premises_id").click();
        await p.keyboard.type(addr.slice(0, 18));
        await p.waitForTimeout(2000);
        const opt = p.locator('[role="option"]').filter({ hasText: "Roofline" }).first();
        if (await opt.count()) await opt.click();
        await p.waitForTimeout(2000);
        if (await p.locator("#units_per_floor").count()) await p.fill("#units_per_floor", "1");
        // the building already has unit "1" (Add Premises made it): number from 2
        if (await p.locator("#seq_start").count()) await p.fill("#seq_start", "2");
        await p.waitForTimeout(600);
        ok("Add units draws Valve location once the building's services are known", (await box(p, "valve_location").count()) > 0, (await mainText(p)).slice(0, 400), ["A", "service_points", "typed"]);
        if (await box(p, "gate_code").count()) await box(p, "gate_code").fill("7777");
        if (await box(p, "valve_location").count()) await box(p, "valve_location").first().fill("Rear wall");
        await shot(p, "add_units_step1", '[id="custom_data.gate_code"]');
        await p.locator('[data-wizard="actions"] button').last().click();
        await p.waitForTimeout(3500);
        const review = await mainText(p);
        ok("Add units review lists Gate code 7777", /Gate code\s*7777/.test(review), review.slice(-400), ["A", "units", "typed"]);
        await shot(p, "add_units_review");
        await p.locator('[data-wizard="actions"] button').last().click();
        await p.waitForTimeout(4000);
        const made = H.psql(`select count(*) from units where premises_id='${prem.id}' and custom_data->>'gate_code'='7777'`);
        const sp = H.psql(`select count(*) from service_points sp join units u on u.id=sp.unit_id where u.premises_id='${prem.id}' and sp.custom_data->>'valve_location'='Rear wall'`);
        ok("Add units created the unit with Gate code 7777", made === "1", made, ["A", "units", "typed"]);
        ok("…and its service point with Valve location Rear wall", Number(sp) >= 1, sp, ["A", "service_points", "typed"]);
      },
    },
    5: {
      title: "A · premises IMPORT with the Roof Material column (good loads, Purple refused, blank loads, update merges)",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        const tag = Date.now().toString(36).slice(-4);
        const csv = `ADDR1,CITY,ROOF\n500 Import Rd ${tag},Katy,Shingle\n501 Import Rd ${tag},Katy,Purple\n502 Import Rd ${tag},Katy,\n`;
        const run = await p.api("POST", "/imports", { target: "premises", source_kind: "file", file_name: "cfe2e_roof.csv", content: csv });
        ok("import extracted", [200, 201].includes(run.status), run.text.slice(0, 200), ["A", "premises", "imported"]);
        const runId = run.body?.id;
        const tf = await p.api("POST", `/imports/${runId}/transform`, {
          mapping: { ADDR1: "address_line", CITY: "city", ROOF: "custom_data.roof_material" },
          row_handling: { drop_exact_duplicates: false, keep_latest_on_key: false, skip_rows_missing_required: false },
        });
        ok("the mapping accepts Roof Material", tf.status === 200, tf.text.slice(0, 300), ["A", "premises", "imported"]);
        await p.api("POST", `/imports/${runId}/validate`, { write_mode: "insert" });
        const load = await p.api("POST", `/imports/${runId}/load`, { write_mode: "insert", approved: true });
        ok("loaded", [200, 202].includes(load.status), load.text.slice(0, 300), ["A", "premises", "imported"]);
        await p.waitForTimeout(2000);
        const got = await p.api("GET", `/premises?q=${encodeURIComponent(`Import Rd ${tag}`)}&per=10`);
        const by = Object.fromEntries(rowsOf(got.body).map((r) => [r.address_line, r]));
        ok("the Shingle row loaded with its answer", by[`500 Import Rd ${tag}`]?.custom_data?.roof_material === "Shingle", JSON.stringify(Object.keys(by)), ["A", "premises", "imported"]);
        ok("the Purple row refused on its row", by[`501 Import Rd ${tag}`] === undefined, "", ["A", "premises", "imported"]);
        ok("the blank row loaded (required never blocks an import)", by[`502 Import Rd ${tag}`] !== undefined, "", ["A", "premises", "imported"]);
        await p.goto(`${BASE}/${A.t}/imports/${runId}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1500);
        await shot(p, "premises_import_run");
        // the mapping screen offers the column by its LABEL (Settings > Import, stage 2)
        const cols = await p.api("GET", `/imports/${runId}/columns`);
        ok("the premises import's MAPS TO list offers Roof Material by its label",
          cols.text.includes("custom_data.roof_material") && cols.text.includes("Roof Material"), cols.text.slice(0, 300), ["A", "premises", "imported"]);
        const urun = await p.api("POST", "/imports", { target: "units", source_kind: "file", file_name: "cfe2e_units.csv", content: "PREMISE,UNIT,GATE\nP-00001,U-x,1\n" });
        const ucols = await p.api("GET", `/imports/${urun.body?.id}/columns`);
        ok("the units import's MAPS TO list offers Gate code", ucols.text.includes("custom_data.gate_code"), ucols.text.slice(0, 300), ["A", "units", "imported"]);
        state.A.units_import_run = urun.body?.id;
        // PO 2026-10-02, added in discussion: "every import includes one column
        // per custom field (premises, units, assets, accounts, readings)"
        const arun = await p.api("POST", "/imports", { target: "accounts", source_kind: "file", file_name: "cfe2e_accounts.csv", content: "UNIT,NAME,REF\nU-00001,X,1\n" });
        const acols = await p.api("GET", `/imports/${arun.body?.id}/columns`);
        ok("the accounts import's MAPS TO list offers Contract ref", acols.text.includes("custom_data.contract_ref"), acols.text.slice(0, 200), ["A", "accounts", "imported"]);
        // DEF-MET-9239 (2.467.15) — the accounts sheet carries the column, a good
        // cell is written, a bad one is refused on its row in plain words.
        await p.goto(`${BASE}/${A.t}/accounts/import`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1500);
        const adl = await Promise.all([p.waitForEvent("download", { timeout: 15000 }), p.getByRole("button", { name: "Download a sample CSV" }).click()]).then(([d]) => d).catch(() => null);
        const asample = adl ? readFileSync(await adl.path(), "utf8") : "";
        state.A.accounts_sample_header = asample.split("\n")[0];
        ok("the accounts sample CSV (downloaded on the screen) carries a Contract ref column", asample.split("\n")[0].includes("Contract ref"), asample.split("\n")[0].slice(-200), ["A", "accounts", "imported"]);
        const vacant = H.psql(`select string_agg(unit_no, '|' order by unit_no) from (select u.unit_no from units u join premises p on p.id=u.premises_id
          where p.tenant_id=(select id from tenants where subdomain='${A.t}') and u.rate_plan_id is not null and not u.is_common_area
            and exists (select 1 from service_points sp where sp.unit_id=u.id) and not exists (select 1 from accounts a where a.unit_id=u.id)
          order by u.unit_no limit 2) v`).split("|");
        if (vacant.length === 2 && vacant[0]) {
          const long = "X".repeat(501);
          const acsv = `UNIT,ACCT,NAME,KIND,SSN,TYPE,OPENED,CONTRACT\n${vacant[0]},CF-${tag}-1,Ana Diaz,person,111-22-3333,residential,2026-01-05,C-${tag}\n${vacant[1]},CF-${tag}-2,Ben Cole,person,987-65-4321,residential,2026-01-05,${long}\n`;
          const ar = await p.api("POST", "/imports", { target: "accounts", source_kind: "file", file_name: "cfe2e_accounts_cf.csv", content: acsv });
          const aid = ar.body?.id;
          const at = await p.api("POST", `/imports/${aid}/transform`, {
            mapping: { UNIT: "unit_ref", ACCT: "account_no", NAME: "customer_name", KIND: "customer_kind", SSN: "customer_ssn", TYPE: "account_type", OPENED: "opened_at", CONTRACT: "custom_data.contract_ref" },
            row_handling: { drop_exact_duplicates: false, keep_latest_on_key: false, skip_rows_missing_required: false },
          });
          ok("the accounts mapping accepts Contract ref", at.status === 200, at.text.slice(0, 300), ["A", "accounts", "imported"]);
          await p.api("POST", `/imports/${aid}/validate`, { write_mode: "insert" });
          const rej = await p.api("GET", `/imports/${aid}`);
          ok("the too-long Contract ref is refused on its row, in words", (rej.text || "").includes("Contract ref is longer than 500 characters"), (rej.text || "").slice(0, 300), ["A", "accounts", "imported"]);
          const al = await p.api("POST", `/imports/${aid}/load`, { write_mode: "insert", approved: true });
          await p.waitForTimeout(2000);
          const held = H.psql(`select custom_data->>'contract_ref' from accounts where account_no='CF-${tag}-1'`);
          ok("the good account row is written with its Contract ref", held === `C-${tag}`, `${al.status} ${held} ${al.text.slice(0, 200)}`, ["A", "accounts", "imported"]);
          ok("the refused row wrote no account", H.psql(`select count(*) from accounts where account_no='CF-${tag}-2'`) === "0", "", ["A", "accounts", "imported"]);
          await p.goto(`${BASE}/${A.t}/imports/${aid}`, { waitUntil: "networkidle" });
          await p.waitForTimeout(1500);
          await shot(p, "accounts_import_run");
        } else ok("two vacant planned units for the accounts import", false, JSON.stringify(vacant), ["A", "accounts", "imported"]);
        // update merges
        const target = by[`500 Import Rd ${tag}`];
        if (target?.premise_no) {
          await p.api("PATCH", `/premises/${target.id}`, { custom_data: { meter_vault_code: "KEEP-1" } });
          // The premises file's identity is our own number; the address stays a
          // required column on every premises file, so the clerk's update file
          // repeats it unchanged.
          const up = await p.api("POST", "/imports", { target: "premises", source_kind: "file", file_name: "cfe2e_roof_up.csv",
            content: `PNO,ADDR1,CITY,ROOF\n${target.premise_no},500 Import Rd ${tag},Katy,Metal\n` });
          const t2 = await p.api("POST", `/imports/${up.body?.id}/transform`, { mapping: { PNO: "premise_no", ADDR1: "address_line", CITY: "city", ROOF: "custom_data.roof_material" }, row_handling: { drop_exact_duplicates: false, keep_latest_on_key: false, skip_rows_missing_required: false } });
          const v2 = await p.api("POST", `/imports/${up.body?.id}/validate`, { write_mode: "upsert" });
          const l2 = await p.api("POST", `/imports/${up.body?.id}/load`, { write_mode: "upsert", approved: true });
          await p.waitForTimeout(2000);
          const after = await p.api("GET", `/premises/${target.id}`);
          ok("an update import merges: Roof Material Metal, Meter vault code kept",
            after.body?.custom_data?.roof_material === "Metal" && after.body?.custom_data?.meter_vault_code === "KEEP-1",
            `${t2.status}/${v2.status}/${l2.status} ${JSON.stringify(after.body?.custom_data)} ${t2.text.slice(0, 200)} ${v2.text.slice(0, 200)} ${l2.text.slice(0, 200)}`, ["A", "premises", "imported"]);
        } else ok("the imported premise has a number to update by", false, JSON.stringify(target).slice(0, 200), ["A", "premises", "imported"]);
        state.A.import_premises = target?.id;
      },
    },
    6: {
      title: "A · Add asset + Edit asset (Warranty provider) → Asset detail, assets list column, asset upload column",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        await p.goto(`${BASE}/${A.t}/assets/new?class=meters`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        const assetNo = `CFE2E-${Date.now().toString(36).slice(-5).toUpperCase()}`;
        await p.fill("#asset_no", assetNo);
        await p.selectOption("#type", "meter");
        await p.selectOption("#service", { index: 1 });
        let drawnAt = 0;
        for (let i = 1; i <= 4; i += 1) {
          if ((await box(p, "warranty_provider").count()) > 0) { drawnAt = i; break; }
          if ((await p.locator("#unit").count()) && (await p.inputValue("#unit").catch(() => "x")) === "") await p.fill("#unit", "kWh");
          await cont(p);
        }
        ok("Add asset draws Warranty provider", drawnAt > 0, "", ["A", "assets", "typed"]);
        if (drawnAt) {
          await box(p, "warranty_provider").fill("Acme Meters");
          await shot(p, "add_asset_warranty", '[id="custom_data.warranty_provider"]');
          let posted = null;
          for (let i = 0; i < 4 && !posted; i += 1) {
            const add = p.locator("button", { hasText: /^Add asset/ });
            if (await add.count()) {
              const ans = p.waitForResponse((r) => /\/assets$/.test(r.url()) && r.request().method() === "POST", { timeout: 30000 }).catch(() => null);
              await add.last().click();
              posted = (await ans) ?? "none";
              break;
            }
            await cont(p);
          }
          const res = posted && posted !== "none" ? posted : null;
          ok("Add asset posts and saves the answer", res && res.status() === 201 && JSON.stringify(res.request().postDataJSON()).includes("Acme Meters"),
            res ? `${res.status()} ${(await res.text()).slice(0, 300)}` : "no POST", ["A", "assets", "typed"]);
          await p.waitForTimeout(1500);
          if (!res || res.status() !== 201) await shot(p, "add_asset_not_saved");
        }
        let asset = rowsOf((await p.api("GET", `/assets?q=${assetNo}&per=5`)).body)[0];
        if (!asset) asset = rowsOf((await p.api("GET", "/assets?per=1")).body)[0];
        state.A.asset = asset?.id;
        await p.goto(`${BASE}/${A.t}/assets/${asset.id}/edit`, { waitUntil: "networkidle" });
        await box(p, "warranty_provider").waitFor({ timeout: 20000 });
        await box(p, "warranty_provider").fill("Acme Meters East");
        await shot(p, "edit_asset", '[id="custom_data.warranty_provider"]');
        await p.getByRole("button", { name: "Save asset" }).click();
        await p.waitForTimeout(3000);
        const t = await mainText(p);
        ok("Asset detail shows Warranty provider", /Warranty provider\s*Acme Meters East/.test(t), t.slice(-300), ["A", "assets", "shown"]);
        await shot(p, "asset_detail", "text=Warranty provider");
        await p.goto(`${BASE}/${A.t}/assets?q=${encodeURIComponent(asset.asset_no)}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        ok("Assets list has the Warranty provider column", (await p.locator("main th", { hasText: "Warranty provider" }).count()) > 0, "", ["A", "assets", "shown"]);
        await shot(p, "assets_list_column");
        await p.goto(`${BASE}/${A.t}/assets/import?target=assets_meters`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1500);
        await shot(p, "asset_upload_screen");
        const dl = await Promise.all([p.waitForEvent("download", { timeout: 15000 }), p.getByRole("button", { name: "Download a sample CSV" }).click()]).then(([d]) => d).catch(() => null);
        const sample = dl ? readFileSync(await dl.path(), "utf8") : "";
        state.A.asset_sample_header = sample.split("\n")[0];
        ok("the asset upload's sample CSV carries a Warranty provider column", /Warranty provider/.test(sample), sample.split("\n")[0], ["A", "assets", "imported"]);
        const arun = await p.api("POST", "/imports", { target: "assets_meters", source_kind: "file", file_name: "cfe2e_assets.csv", content: "Asset ID,Warranty provider\nX-1,Acme\n" });
        const acols = await p.api("GET", `/imports/${arun.body?.id}/columns`);
        ok("the asset upload's MAPS TO list offers Warranty provider", acols.text.includes("custom_data.warranty_provider"), acols.text.slice(0, 300), ["A", "assets", "imported"]);
        state.A.asset_import_run = arun.body?.id;
      },
    },
    7: {
      title: "A · Routes (Patrol day, multi-select) and Areas (Warden, Yes/No)",
      fn: async (ctx) => {
        const p = await page(ctx, A);
        const route = rowsOf((await p.api("GET", "/routes?per=5")).body)[0];
        state.A.route = route?.id;
        await p.goto(`${BASE}/${A.t}/settings/reference-data/routes-cycles/routes/${route.id}/edit`, { waitUntil: "networkidle" });
        await p.locator('[id="custom_data.patrol_day.Tue"]').waitFor({ timeout: 30000 });
        ok("the route form draws Patrol day as five ticks", (await p.locator('[id^="custom_data.patrol_day."]').count()) === 5, "", ["A", "routes", "typed"]);
        await p.locator('[id="custom_data.patrol_day.Tue"]').check({ force: true });
        await p.locator('[id="custom_data.patrol_day.Thu"]').check({ force: true });
        await shot(p, "route_wizard_patrol_day", '[id="custom_data.patrol_day.Tue"]');
        for (let i = 0; i < 3; i += 1) {
          await p.locator("button", { hasText: /^Continue/ }).last().click();
          await p.waitForTimeout(1200);
        }
        const saved = p.waitForResponse((r) => r.url().includes(`/routes/${route.id}`) && r.request().method() === "PATCH", { timeout: 60000 });
        await p.locator("button", { hasText: /✓/ }).last().click();
        const res = await saved;
        ok("route save sends Patrol day = [Tue, Thu]", res.status() === 200 && JSON.stringify(res.request().postDataJSON().custom_data) === '{"patrol_day":["Tue","Thu"]}',
          JSON.stringify(res.request().postDataJSON().custom_data), ["A", "routes", "typed"]);
        await p.goto(`${BASE}/${A.t}/settings/reference-data/routes-cycles/routes/${route.id}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        ok("the route page shows Patrol day Tue, Thu", /Patrol day\s*Tue, Thu/.test(await mainText(p)), "", ["A", "routes", "shown"]);
        await shot(p, "route_page", "text=Patrol day");
        const AREAS = `${BASE}/${A.t}/settings/reference-data/reference-data?list=areas`;
        await p.goto(AREAS, { waitUntil: "networkidle" });
        await p.locator("button", { hasText: "+ Add entry" }).first().click();
        await dialog(p).waitFor();
        const code = `CFE-${Date.now().toString(36).slice(-4).toUpperCase()}`;
        await p.fill("#code", code);
        await p.fill("#name", `CFE North ${code}`);
        await box(p, "warden").waitFor({ timeout: 15000 });
        await box(p, "warden").selectOption("true"); // DEF-SHL-9240: a Yes / No pick
        await shot(p, "area_dialog_warden");
        const areaSave = p.waitForResponse((r) => /\/lookups\/areas/.test(r.url()) && r.request().method() === "POST", { timeout: 60000 });
        await dialog(p).locator('button[data-variant="primary"]').last().click();
        const ar = await areaSave;
        ok("area saved with Warden = yes", ar.status() === 201 && JSON.stringify(ar.request().postDataJSON()).includes('"warden":true'),
          `${ar.status()} ${JSON.stringify(ar.request().postDataJSON())}`, ["A", "areas", "typed"]);
        state.A.area_code = code;
        await p.goto(`${AREAS}&q=${code}`, { waitUntil: "networkidle" });
        await p.waitForTimeout(1200);
        ok("the Areas list carries a Warden column", (await p.locator("main th", { hasText: "Warden" }).count()) > 0, "", ["A", "areas", "shown"]);
        ok("…reading Yes on the new row", /Yes/.test(await p.locator("tr", { hasText: code }).first().innerText().catch(() => "")), "", ["A", "areas", "shown"]);
        await shot(p, "areas_list_warden");
      },
    },
  };
}
