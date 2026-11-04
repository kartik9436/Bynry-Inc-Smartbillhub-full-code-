/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  CR-115-BRC05 §7 — *"CUSTOM URLs ON A CONNECTOR"*, PO 2026-09-17.
 *          R32 (the form) · R33 (the standard list) · R34 (a new KIND is a
 *          Runbook) · R35 (no field mapping) · R36 (Edit; standard switch only)
 *          · §7.5's five rules · §7.10's own named walk.
 * Screens: S142 the connector view — `/:tenant/settings/integrations/gis_esri`
 *          · S147 · INT-07 the set-up form ·
 *          `/:tenant/settings/connectors/gis_esri/configure`
 * Rules:   BR-INT-078 (§7.5) · B14 rule 31 (no database id on screen) · rule 33
 *          (a refusal is capped by what it is for) · CLAUDE.md hard rule 1
 *          (tenant scoping) · hard-won law 2's mirror · law 6 (no gate in this
 *          repo reads rendered output) · law 7 habit 2.
 * ───────────────────────────────────────────────────────
 *
 * ⚠⚠ **THIS WALK PROVES OUR CODE. IT PROVES NOTHING ABOUT ANN ARBOR'S DATA.**
 * The egress proxy in this environment refuses `a2mapseg.a2gov.org` — `curl`
 * returns code `000` and Django sees *Tunnel connection failed: 403 Forbidden*.
 * Not one byte of the City's register has ever been read here. Every address
 * below is a reserved `.example` host that `gis_fixtures.transport_for`
 * answers from a recording. A green run means the form, the table, the five
 * rules and the save path behave. It does NOT mean the Ann Arbor integration
 * works.
 *
 * ⚠ **AND `.example` IS THE ONE HOST THAT CANNOT FAIL TO CONNECT**, so it is
 * never used here to stand in for an unreachable City.
 *
 * RUN IT (the smoke stack's shape — the vite dev server has no /api proxy):
 *     DATABASE_URL="postgres://…/<db>?sslmode=disable" \
 *     DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \
 *     python 06-backend/manage.py runserver 127.0.0.1:8407 --noreload
 *     (cd 07-frontend && npm run build && API_PROXY_TARGET=http://127.0.0.1:8407 PORT=8408 node server.mjs)
 *     BASE=http://127.0.0.1:8408 PGURL="…" node 10-scripts/cr115_custom_apis_walkthrough.mjs
 *
 * ── WHAT WOULD MAKE EACH STEP PASS WRONGLY (law 7, habit 2) ────────────────
 *  0 A SIGN-IN THAT LANDED SOMEWHERE ELSE — `DEF-IDN-5653` bounces an invited
 *    user to `/change-password`, which has no screen. Step 0 asserts the
 *    address it actually reached, so a walk that never got into the product
 *    cannot report seven passes over a sign-in page.
 *  1 THE WORDS *Kind*, *Enabled* and *Edit* APPEAR ELSEWHERE on this screen —
 *    in the shell's nav, in a row action's tooltip. So the columns are read off
 *    `thead th`, and the row controls by `data-api-standard`, `data-edit-cell`
 *    and `data-enabled-cell`, which exist for no other reason.
 *  2 A CONTROL RENDERED ONCE somewhere on the page satisfies a page-wide count.
 *    So Edit and Delete are counted PER ROW, and the standard rows are asserted
 *    to have an EMPTY cell — the half that says R36 is obeyed rather than
 *    ignored.
 *  3 A REFUSAL THAT IS MERELY PRESENT — a disabled button with no sentence is
 *    the failure `G32` exists for. So step 3 reads the SENTENCE and the
 *    button's disabled state, and then re-counts the rows to prove nothing was
 *    created behind the refusal.
 *  5/6 **A SWITCH THAT CHANGES THE SCREEN AND NOTHING ELSE** is hard-won law
 *    2's mirror and would satisfy every assertion made against the table. So
 *    step 6 asks the SERVER, from the browser's own session, and reads the
 *    message key it answers with — the only evidence that the code which
 *    PLACES THE CALL obeys the switch.
 *  7 A SAVE THAT LOOKED FINE — `DEF-INT-5582` refused an unknown field name and
 *    broke the PO's allowed addresses; the same route now runs beside per-API
 *    rows. So step 7 saves the CONNECTOR and then re-reads the page to confirm
 *    the clerk's rows and their switch survived it.
 *
 * ⚠ **IT RESETS ITSELF, AND THE FIRST RUN PROVED WHY.** Run twice, its own
 * *Address points* row made `Address lookup` drop out of the dropdown — §7.4's
 * *"one configuration per API, never two"* working exactly as ruled — and the
 * second run read that as a broken form. A walk that cannot be re-run is a walk
 * nobody re-runs. The reset needs `app.tenant_id`: under RLS FORCE a DELETE
 * with no tenant context touches nothing and reports success.
 */
import { createRequire } from "node:module";
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { join } from "node:path";
const require = createRequire(new URL("../07-frontend/package.json", import.meta.url).pathname);
const { chromium } = require("playwright");
function chrome() {
  const want = chromium.executablePath();
  if (want && existsSync(want)) return want;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const d of readdirSync(root)) {
      const c = join(root, d, "chrome-linux", "chrome");
      if (existsSync(c)) return c;
    }
  }
  throw new Error("no chromium");
}
const BASE = process.env.BASE ?? "http://127.0.0.1:8408";
const T = "brazosbend";
const OUT = process.env.OUT ?? "/tmp/cr115-custom-apis";
mkdirSync(OUT, { recursive: true });
const PGURL = process.env.PGURL ?? "postgres://sbh:sbh@127.0.0.1:5432/sbh_capis?sslmode=disable";
const { execFileSync } = await import("node:child_process");
const raw = (q) => execFileSync("psql", [PGURL, "-tAc", q], { encoding: "utf8" })
  .split("\n").filter((l) => !["SET", "DELETE 0", ""].includes(l.trim())).join("\n").trim();
/** ⚠ **THE WALK RESETS ITSELF, AND THE FIRST RUN PROVED WHY.** Run twice, its
 *  own *Address points* row had made `Address lookup` drop out of the dropdown
 *  — §7.4's *"one configuration per API, never two"* working exactly as ruled —
 *  and the second run read that as a broken form. A walk that cannot be re-run
 *  is a walk nobody re-runs. ⚠ The GUC is required: under RLS FORCE a DELETE
 *  with no `app.tenant_id` touches nothing and reports success. */
const TENANT = execFileSync("psql", [PGURL, "-tAc", "select id from tenants where subdomain='brazosbend'"], { encoding: "utf8" }).trim();
raw(`set app.tenant_id='${TENANT}'; delete from integration_api`);
console.log(`  >> reset: integration_api emptied for ${TENANT}`);

let fails = 0;
const say = (l, ok, d = "") => (console.log(`  ${ok ? "PASS" : "FAIL"}  ${l}${d ? " — " + d : ""}`), ok || fails++);

const b = await chromium.launch({ executablePath: chrome(), args: ["--no-sandbox"] });
const p = await b.newPage({ viewport: { width: 1600, height: 1400 } });
const errors = [];
p.on("pageerror", (e) => errors.push(String(e)));
p.on("response", (r) => { if (r.url().includes("/api/") && r.status() >= 500) errors.push(`${r.status()} ${r.url()}`); });

try {
  console.log("\n0 · SIGN IN AND REACH THE CONNECTOR FROM SETTINGS (the surrounding journey)");
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "networkidle" });
  await p.fill("#signin-email", "dana@brazosbendutilities.com");
  await p.fill("#signin-password", "S3cure!passw0rd");
  await p.click('button[type="submit"]');
  await p.waitForTimeout(2500);
  say("signed in, not bounced to /change-password", !p.url().includes("change-password"), p.url());

  await p.goto(`${BASE}/${T}/settings/integrations`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2000);
  await p.screenshot({ path: `${OUT}/10-connectors.png`, fullPage: true });
  const esriRow = await p.locator('text=Esri ArcGIS').first().count();
  say("the connector list shows Esri ArcGIS", esriRow > 0);

  // Reach the connection the way a clerk does — the row's View action.
  const viewLink = p.locator('a[href*="/settings/integrations/gis_esri"]').first();
  const hasDoor = await viewLink.count();
  say("there is a door from the list to the connector", hasDoor > 0);
  if (hasDoor > 0) { await viewLink.click(); await p.waitForTimeout(2500); }
  else { await p.goto(`${BASE}/${T}/settings/integrations/gis_esri`, { waitUntil: "networkidle" }); await p.waitForTimeout(2000); }
  say("landed on the connector view", p.url().includes("gis_esri"), p.url());
  await p.screenshot({ path: `${OUT}/11-before.png`, fullPage: true });

  console.log("\n1 · THE TABLE NOW CARRIES KIND, ENABLED AND EDIT");
  const heads = await p.locator("table thead th").allInnerTexts();
  console.log("     columns:", heads.join(" | "));
  say("KIND is a column", heads.some((h) => /kind/i.test(h)));
  say("ENABLED is a column", heads.some((h) => /enabled/i.test(h)));
  say("EDIT is a column", heads.some((h) => /edit/i.test(h)));
  say("three standard rows", (await p.locator("tbody tr[data-operation]").count()) === 3);
  say("all three are marked standard",
      (await p.locator('[data-api-standard-mark]').count()) === 3);
  say("no standard row offers Edit",
      (await p.locator('[data-edit-cell] button').count()) === 0);
  const addBtn = p.locator("[data-add-api]");
  say("the + API control is drawn", (await addBtn.count()) === 1);

  console.log("\n2 · ADD A CUSTOM ADDRESS LOOKUP (the PO's own walk)");
  await addBtn.click();
  await p.waitForTimeout(800);
  await p.screenshot({ path: `${OUT}/12-form.png`, fullPage: true });
  const kinds = await p.locator("#custom-api-kind option").allInnerTexts();
  console.log("     kinds offered:", kinds.filter((k) => k.trim()).join(" | "));
  say("no field-mapping control on the form (R35)",
      (await p.locator('#custom-api-kind, #custom-api-name, #custom-api-url').count()) === 3
      && !(await p.locator('.modal-body').innerText()).toLowerCase().includes("mapping"));
  say("no Key field on the form (deferred, DEF-INT-5680)",
      !(await p.locator(".modal-body").innerText()).toLowerCase().includes("key"));
  await p.selectOption("#custom-api-kind", "address_lookup");
  await p.fill("#custom-api-name", "Address points");
  await p.fill("#custom-api-url", "https://points.brazosbend.example/addr");
  await p.screenshot({ path: `${OUT}/13-form-filled.png`, fullPage: true });
  await p.locator('form button[type="submit"]').click();
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${OUT}/14-added.png`, fullPage: true });
  const bodyNow = await p.locator("body").innerText();
  say("the new API is in the table", bodyNow.includes("Address points"));
  say("it carries its own address", bodyNow.includes("points.brazosbend.example"));
  const customRow = p.locator('tbody tr[data-api-standard="no"]');
  say("exactly one custom row", (await customRow.count()) === 1);
  say("the custom row offers Edit and Delete",
      (await customRow.locator("[data-edit-cell] button").count()) === 2);
  const src = await customRow.locator("[data-endpoint]").getAttribute("data-endpoint-source");
  say("the screen READS the served provenance", src === "api_row", `endpoint_source=${src}`);
  const kpi = await p.locator('[data-kpi="working"]').innerText();
  console.log("     Working tile:", kpi);
  say("Working counts four now", kpi.includes("4"), kpi);

  console.log("\n3 · A SECOND SCHEDULED SYNC IS REFUSED IN WORDS");
  await p.locator("[data-add-api]").click();
  await p.waitForTimeout(800);
  await p.selectOption("#custom-api-kind", "scheduled_sync");
  await p.waitForTimeout(600);
  await p.screenshot({ path: `${OUT}/15-refused.png`, fullPage: true });
  const modal = await p.locator(".modal-body, form").first().innerText();
  const refused = /one scheduled sync only/i.test(modal);
  say("the refusal is a SENTENCE a clerk can read", refused,
      (modal.split("\n").find((l) => /scheduled sync only/i.test(l)) ?? "NOT FOUND").trim());
  // ⚠ FormModal swaps the submit for a plain DISABLED button when
  // `commitBlocked` is set, so it has no `type="submit"` to find. Addressed by
  // its LABEL, which is what a clerk sees.
  const addBtn2 = p.locator('form button:has-text("Add")').last();
  say("Add cannot be pressed while refused", await addBtn2.isDisabled());
  await p.locator('form button:has-text("Cancel")').first().click();
  await p.waitForTimeout(900);
  say("the second sync was never created",
      (await p.locator('tbody tr[data-api-standard="no"]').count()) === 1);

  console.log("\n4 · EDIT A CUSTOM ROW");
  await p.locator('tbody tr[data-api-standard="no"] [data-edit-cell] button').first().click();
  await p.waitForTimeout(900);
  await p.screenshot({ path: `${OUT}/16-edit.png`, fullPage: true });
  const nameVal = await p.locator("#custom-api-name").inputValue();
  say("the edit form opens on THEIR name", nameVal === "Address points", nameVal);
  await p.fill("#custom-api-name", "Qualified addresses");
  await p.locator('form button[type="submit"]').click();
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${OUT}/17-edited.png`, fullPage: true });
  say("the rename is on the screen",
      (await p.locator("body").innerText()).includes("Qualified addresses"));

  console.log("\n5 · SWITCH IT OFF");
  const sw = p.locator('tbody tr[data-api-standard="no"] [data-enabled-cell] [role="switch"]');
  say("the custom row has a switch", (await sw.count()) === 1);
  say("it is ON", (await sw.getAttribute("data-switch-state")) === "on");
  await sw.click();
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${OUT}/18-switched-off.png`, fullPage: true });
  const after = p.locator('tbody tr[data-api-standard="no"] [data-enabled-cell] [role="switch"]');
  say("it is now OFF", (await after.getAttribute("data-switch-state")) === "off");
  const kpi2 = await p.locator('[data-kpi="working"]').innerText();
  say("the Working tile stops counting it (rule 4)", kpi2.includes("3"), kpi2);
  const state = await p.locator('body').innerText();
  console.log("     state word region:", (state.split("\n").slice(0, 30).find((l) => /Not tested|Working|Not working/i.test(l)) ?? "").trim());

  console.log("\n6 · A SWITCHED-OFF API IS NOT CALLED (rule 3), THROUGH THE REAL HTTP STACK");
  // ⚠ **ASKED OF THE SERVER FROM THE BROWSER'S OWN SESSION**, not of the
  // screen. A screen can only draw what it was handed; the question rule 3
  // actually asks is whether the code that PLACES THE CALL obeys the switch.
  // With the custom lookup already off, switching the standard one off leaves
  // no enabled lookup at all — and the honest answer is a sentence, not an
  // empty list. *No matching address found* and *nobody is looking* are
  // different facts.
  const askSearch = () =>
    p.evaluate(async (t) => {
      const r = await fetch(`/api/${t}/integrations/gis_esri/address-search?q=100 Maple`, {
        headers: { Accept: "application/json" },
      });
      return { status: r.status, body: await r.text() };
    }, T);
  const before6 = await askSearch();
  say("with a lookup ON the search answers normally", before6.status === 200
      && !before6.body.includes("lookup_off"), `status ${before6.status}`);

  const std = p.locator('tbody tr[data-api-standard="yes"][data-operation="address_search"] [role="switch"]');
  await std.click();
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${OUT}/20-all-lookups-off.png`, fullPage: true });
  say("the standard lookup is OFF", (await p.locator('tbody tr[data-operation="address_search"][data-api-standard="yes"] [role="switch"]').getAttribute("data-switch-state")) === "off");
  const after6 = await askSearch();
  const parsed = JSON.parse(after6.body);
  say("nothing was dialled and the reason is said out loud",
      (parsed.data ?? parsed).message_key === "integrations.gis.lookup_off",
      (parsed.data ?? parsed).message_key ?? after6.body.slice(0, 120));
  say("and no candidates are asserted", ((parsed.data ?? parsed).candidates ?? []).length === 0);

  console.log("\n7 · THE CONNECTOR EDIT SAVE DOES NOT DESTROY THE ROWS (CR §3 risk 1)");
  // ⚠ **THE NAMED REGRESSION RISK, PROVED IN A BROWSER RATHER THAN BY A TEST**
  // (§7.6). The connector save path prunes `config` to what the manifest still
  // declares — `DEF-INT-5582`, the defect that broke the PO's allowed
  // addresses — so rows kept there would vanish on exactly this click.
  const rowsBefore = await p.locator('tbody tr[data-api-standard="no"]').count();
  await p.locator('[data-edit]').first().click();
  await p.waitForTimeout(1800);
  await p.screenshot({ path: `${OUT}/21-edit-connector.png`, fullPage: true });
  const urlBox = p.locator('input#base_url, input[name="base_url"], #integration-field-base_url').first();
  if (await urlBox.count()) {
    await urlBox.fill("https://gis.brazosbend.example/addr2");
  }
  const saveBtn = p.locator('form button[type="submit"], button:has-text("Save")').first();
  await saveBtn.click();
  await p.waitForTimeout(3000);
  await p.screenshot({ path: `${OUT}/22-after-connector-save.png`, fullPage: true });
  const bodyAfterSave = await p.locator("body").innerText();
  say("the save was accepted, not refused for an unknown field",
      !/unknown|not recognised|VAL-/i.test(bodyAfterSave),
      (bodyAfterSave.split("\n").find((l) => /unknown|VAL-/i.test(l)) ?? "no refusal").trim());
  await p.goto(`${BASE}/${T}/settings/integrations/gis_esri`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2200);
  await p.screenshot({ path: `${OUT}/23-rows-survived.png`, fullPage: true });
  say("the custom rows survived the connector save",
      (await p.locator('tbody tr[data-api-standard="no"]').count()) === rowsBefore,
      `${rowsBefore} before`);
  say("the switch a clerk set is still off",
      (await p.locator('tbody tr[data-api-standard="no"] [role="switch"]').getAttribute("data-switch-state")) === "off");

  console.log("\nPAGE ERRORS / 5xx:", errors.length === 0 ? "none" : errors.join(" · "));
  if (errors.length) fails++;
} finally {
  await p.screenshot({ path: `${OUT}/19-final.png`, fullPage: true }).catch(() => {});
  await b.close();
}
console.log(fails === 0 ? "\nALL STEPS PASSED" : `\n${fails} STEP(S) FAILED`);
process.exit(fails === 0 ? 0 : 1);

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-115-BRC05 §7 (the 2026-09-17 rulings verbatim) + §7.10's named walk
// generated: 2026-09-17 by the CR-115-BRC05 per-API lane
// checklist: A=n/a B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: this file IS the gate law 6 asks for — no gate in this repo reads rendered output
// exceptions: the City of Ann Arbor is unreachable from this environment; every address here is a recorded `.example` host
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
