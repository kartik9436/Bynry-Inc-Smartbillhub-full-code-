// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave G — G1 (`PUJ-30`), G2 (`PUJ-31`), G3 (`PUJ-32`): the
//          Assets tab of a unit. The inventory picker asked for an asset
//          NUMBER and nothing else; choosing a row finished the job on another
//          screen; and there was no way to change an attached meter's status
//          from the unit at all.
// Defects: DEF-AST-4734 (`f.assigned=false` was accepted and IGNORED — it
//          answered the whole registry) · DEF-AST-4735 (no seeded inventory
//          spare records what size it is, so *5/8* could match nothing)
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate in this repo looks at rendered output) ·
//          law 7 habit 3 (a check's output must distinguish pass from fail TO
//          A READER)
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS AND WHY EACH STEP IS HERE RATHER THAN IN A DOM TEST.
//
// A dom test seeds an answer into React Query and asserts a string is in the
// markup. It proves the component and nothing about the route, the resolver,
// the tenant's own catalogues, or the fixture. Everything below is the seeded
// `brazosbend` demo, reached the way a clerk reaches it.
//
//   1 · G1 — type *5/8 water meter inventory* into the finder and read the
//       chips back. The words are matched against THIS TENANT's catalogues, so
//       the sentence proves the vocabulary is live and not a hardcoded list.
//   2 · G2 — press **Assign ✓** on `W-5100` and watch it appear in the table
//       ABOVE, on the same screen, with no navigation.
//   3 · G3 — press the row's ✏ Status on `W-5000`, move it from *Installed* to
//       *Needs repair* with a date and a reason, and read the new stage back
//       out of the table.
//
// ⚠ **THE FIXTURE NEEDED ONE THING RECORDED FIRST, AND IT IS `DEF-AST-4735`.**
// Every seeded inventory spare has `size_class` NULL, so *5/8* matched nothing
// on any tenant. The seeder is fixed for tenants seeded from now on; this demo
// database was seeded before that, so the two water spares are given their size
// THROUGH THE PRODUCT'S OWN DOOR — `PATCH /assets/{id}` with `{"size_class":
// "W-58"}`, which is exactly what a clerk does when a meter arrives and someone
// records what it is. The script does it itself, so the run is reproducible:
//
//     PATCH /api/brazosbend/assets/<W-5100> {"size_class": "W-58"}
//     PATCH /api/brazosbend/assets/<W-5101> {"size_class": "W-58"}
import { existsSync, readdirSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8455";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr089g";
mkdirSync(OUT, { recursive: true });

// `SCW-U-001 · Unit 1` at 101 Silver Creek Rd — a unit that actually carries
// meters (`E-5000`, `W-5000`). Overridable so the same script runs against a
// re-seeded database.
const UNIT = process.env.UNIT ?? "01a077b8-2232-7f56-9a9b-ba5dedd57aef";
const SPARE = process.env.SPARE ?? "W-5100";
const ATTACHED = process.env.ATTACHED ?? "W-5000";

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const candidate = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(candidate)) return candidate;
    }
  }
  throw new Error("no chromium found — set PLAYWRIGHT_BROWSERS_PATH");
}

const results = [];
// ⚠ A CHECK'S OUTPUT MUST DISTINGUISH PASS FROM FAIL TO A READER (law 7). Every
// check prints what it looked for and, on failure, what it found instead.
function check(name, ok, detail = "") {
  results.push({ name, ok });
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1400 } });
page.on("pageerror", (e) => console.log("  page error:", e.message));

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
console.log(`signed in as ${EMAIL} on ${BASE}\n`);

// ── FIXTURE · put the demo back where the script expects to find it ─────────
//
// ⚠ **A WALKTHROUGH THAT ONLY PASSES ONCE IS A WALKTHROUGH NOBODY WILL RUN
// AGAIN.** The first run of this script assigned `W-5100` and left `W-5000`
// needing repair, so the second run failed on its own first assertion and the
// reader's honest reading was *"the feature broke"*. Everything below is done
// THROUGH THE PRODUCT'S OWN ENDPOINTS — no SQL — so what it puts back is a
// state the product can reach:
//
//   · `DEF-AST-4735` — the two water spares are given their size with
//     `PATCH /assets/{id} {"size_class":"W-58"}`, which is what a clerk does
//     when a meter arrives and someone records what it is. The seeder is fixed
//     for tenants seeded from now on; this database was seeded before that.
//   · any `W-51*` spare left on the unit by an earlier run goes back to the
//     shelf with `POST /assets/{id}/reassign {"to_inventory":true}`.
//   · `W-5000` is walked back to *Installed* along BR-AST-020's own edges
//     (needs_repair → in_repair → active), because there is no other way and
//     inventing one would be a door this product does not have.
{
  const prepared = await page.evaluate(
    async ([tenant, unitId, attached]) => {
      const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
      // ⚠ **THE STATUS IS RETURNED AND PRINTED.** The first version of this
      // reset fired and ignored the answer, so a refused reassign left the
      // spare on the unit and the run failed three checks later with a message
      // about a missing table row. A setup step that cannot report its own
      // failure is hard-won law 7's *incapable of failing*, one layer down.
      const send = async (path, method, body) => {
        const res = await fetch(`/api/${tenant}${path}`, {
          method,
          credentials: "include",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify(body),
        });
        return res.status;
      };
      const all = await (
        await fetch(`/api/${tenant}/assets?f.status=all&per=250`, { credentials: "include" })
      ).json();
      const out = [];
      for (const row of all.results.filter((r) => /^W-51/.test(r.asset_no))) {
        await send(`/assets/${row.id}`, "PATCH", { size_class: "W-58" });
        if (row.assigned_unit_id) {
          // `record_final_read: false` is REQUIRED: BR-AST-022 refuses the
          // whole move when it cannot take a final read, and a shelf-bound
          // spare has none to take.
          const code = await send(`/assets/${row.id}/reassign`, "POST", {
            to_inventory: true,
            record_final_read: false,
          });
          out.push(`${row.asset_no} back to the shelf (HTTP ${code})`);
        } else {
          out.push(`${row.asset_no} sized`);
        }
      }
      const meter = all.results.find((r) => r.asset_no === attached);
      if (meter && meter.status !== "active") {
        const walk = meter.status === "needs_repair" ? ["in_repair", "active"] : ["active"];
        const codes = [];
        for (const status of walk) {
          codes.push(
            await send(`/assets/${meter.id}/maintenance`, "POST", {
              kind: "repair",
              detail: "Walkthrough reset",
              status,
            }),
          );
        }
        out.push(`${attached} walked back to Installed (HTTP ${codes.join(",")})`);
      }
      return { out, unitId };
    },
    [TENANT, UNIT, ATTACHED],
  );
  console.log(`fixture · ${prepared.out.join(" · ")}\n`);
}

async function openAssetsTab(label) {
  await page.goto(`${BASE}/${TENANT}/premises/units/${UNIT}?tab=assets`, {
    waitUntil: "networkidle",
  });
  await page.waitForSelector("table", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, `${label}.png`), fullPage: true });
  return (await page.locator("body").innerText()).replace(/\s+/g, " ");
}

// ── G1 · the inventory search takes what a clerk is holding ─────────────────
console.log("G1 · PUJ-30 · the finder reads words, not asset numbers");
{
  await openAssetsTab("g1-before");
  await page.getByRole("button", { name: "+ Assign from inventory" }).click();
  const box = page.locator("#inventory-finder");
  await box.waitFor({ timeout: 10000 });
  check(
    "the box asks for what you are holding, not for a number",
    (await box.getAttribute("placeholder")) !== "Search inventory by asset #…",
    `placeholder = ${await box.getAttribute("placeholder")}`,
  );
  await box.fill("5/8 water meter inventory depot");
  await page.waitForTimeout(1200);
  await page.screenshot({ path: join(OUT, "g1-chips.png"), fullPage: true });

  const chips = await page.locator('[data-finder-chip]').allInnerTexts();
  const chipText = chips.join(" | ");
  check("a chip for the SIZE, named the way the tenant names it", /Water 5\/8/.test(chipText), chipText);
  check("a chip for WHERE IT IS", /Inventory/.test(chipText), chipText);
  check("a chip for the KIND", /Meter/.test(chipText), chipText);
  // B14 rule 31 — the catalogue code is the filter's value and never visible.
  check("no database code on a chip", !/W-58/.test(chipText), chipText);
  const unmatched = await page.locator("[data-finder-unmatched]").innerText();
  check(
    "the word this tenant does not use is SAID, not dropped",
    /depot/.test(unmatched),
    unmatched,
  );

  const rows = await page.locator("[data-finder-row]").allInnerTexts();
  check(`the matching spares are listed (${rows.length})`, rows.length > 0, rows.join(" / "));
  check(
    `${SPARE} is among them`,
    rows.some((row) => row.includes(SPARE)),
    rows.join(" / "),
  );

  // Pressing a chip's ✕ takes its words back out of the box.
  await page.locator('[data-finder-chip="size_class"] button').click();
  await page.waitForTimeout(1000);
  check(
    "removing the size chip takes exactly its words out of the box",
    (await box.inputValue()).trim() === "meter inventory depot",
    `box now reads: ${await box.inputValue()}`,
  );
}

// ── G2 · assigning finishes on the unit ─────────────────────────────────────
console.log("\nG2 · PUJ-31 · Assign ✓ puts the meter in the table above");
{
  const before = await openAssetsTab("g2-before");
  check(
    `${SPARE} is NOT on the unit before the press`,
    !before.includes(SPARE),
    before.slice(0, 400),
  );
  await page.getByRole("button", { name: "+ Assign from inventory" }).click();
  await page.locator("#inventory-finder").fill("5/8 water meter inventory");
  await page.waitForTimeout(1200);
  const row = page.locator(`[data-finder-row="${SPARE}"]`);
  await row.waitFor({ timeout: 10000 });
  await row.getByRole("button", { name: /Assign/ }).click();
  await page.waitForTimeout(2000);
  await page.screenshot({ path: join(OUT, "g2-assigned.png"), fullPage: true });

  const url = page.url();
  // ⚠ THE WHOLE OF `G2`: the clerk is still standing on the unit.
  check("the clerk did not leave the unit", /premises\/units/.test(url) && !/\/assets\//.test(url), url);
  const after = (await page.locator("body").innerText()).replace(/\s+/g, " ");
  check(`${SPARE} is now in the unit's own table`, after.includes(SPARE), after.slice(0, 600));

  // And it is REALLY assigned, not merely drawn: ask the server.
  const served = await page.evaluate(
    async ([tenant, unitId]) => {
      const res = await fetch(`/api/${tenant}/units/${unitId}`, { credentials: "include" });
      const body = await res.json();
      return (body.meters ?? []).map((m) => m.asset_no);
    },
    [TENANT, UNIT],
  );
  check(
    `the server agrees — GET /units/{id} lists ${SPARE}`,
    served.includes(SPARE),
    served.join(", "),
  );
}

// ── G3 · an attached asset's status changes from its row ────────────────────
console.log("\nG3 · PUJ-32 · the row's ✏ changes the stage without leaving");
{
  const before = await openAssetsTab("g3-before");
  check(
    `${ATTACHED} reads Installed before the change`,
    /Installed/.test(before),
    before.slice(0, 600),
  );
  const rows = page.locator("table").first().locator("tbody tr");
  const count = await rows.count();
  let target = null;
  for (let i = 0; i < count; i += 1) {
    if ((await rows.nth(i).innerText()).includes(ATTACHED)) {
      target = rows.nth(i);
      break;
    }
  }
  check(`${ATTACHED} has a row on the unit`, target !== null);
  if (target !== null) {
    await target.getByRole("button", { name: /Status/ }).click();
    await page.waitForSelector('[role="dialog"]', { timeout: 10000 });
    await page.waitForTimeout(800);
    await page.screenshot({ path: join(OUT, "g3-form.png"), fullPage: true });

    const options = await page.locator("#status option").allInnerTexts();
    check("the form offers the legal move", options.some((o) => /Needs repair/.test(o)), options.join(" / "));
    // BR-AST-020/030 — retire is terminal and is the System Admin's own wizard.
    check("and does NOT offer Retired", !options.some((o) => /Retired/.test(o)), options.join(" / "));

    await page.selectOption("#status", { label: "Needs repair" });
    await page.fill("#date", "2026-09-08");
    await page.fill("#detail", "Register glass cracked at the meter pit");
    // ⚠ SCOPED TO THE DIALOG. The unit's HEADER carries its own *Change
    // status* (wave D, for the unit itself), so an unscoped locator matches
    // two buttons and playwright refuses — which is the strict mode doing its
    // job rather than a defect. The two controls are about different things.
    await page
      .locator('[role="dialog"]')
      .getByRole("button", { name: "Change status" })
      .click();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: join(OUT, "g3-after.png"), fullPage: true });

    const after = (await page.locator("body").innerText()).replace(/\s+/g, " ");
    check("the clerk is still on the unit", /premises\/units/.test(page.url()), page.url());
    check("the row now reads Needs repair", /Needs repair/.test(after), after.slice(0, 800));

    // The server is the guarantee, not the markup.
    const served = await page.evaluate(
      async ([tenant, assetNo]) => {
        const res = await fetch(`/api/${tenant}/assets?q=${assetNo}&f.status=all&per=10`, {
          credentials: "include",
        });
        const body = await res.json();
        const row = (body.results ?? []).find((r) => r.asset_no === assetNo);
        return row ? { status: row.status, unit: row.assigned_unit_id } : null;
      },
      [TENANT, ATTACHED],
    );
    check(
      `the server agrees — ${ATTACHED} is needs_repair`,
      served?.status === "needs_repair",
      JSON.stringify(served),
    );
    check(
      "and it is STILL on the unit — a status change is not a removal",
      served?.unit === UNIT,
      JSON.stringify(served),
    );
  }
}

await browser.close();

const failed = results.filter((r) => !r.ok);
console.log(
  `\n${results.length - failed.length}/${results.length} checks passed · screenshots in ${OUT}`,
);
if (failed.length > 0) {
  console.log("FAILED:");
  for (const row of failed) console.log(`  · ${row.name}`);
}
process.exit(failed.length === 0 ? 0 : 1);

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-089 §6 wave G (G1 `PUJ-30` · G2 `PUJ-31` · G3 `PUJ-32`)
// generated: 2026-09-09 by the CR-089 wave G lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
