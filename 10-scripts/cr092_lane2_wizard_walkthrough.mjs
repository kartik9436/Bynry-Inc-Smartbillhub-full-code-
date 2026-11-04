// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 step 2, wave C lane 2 — the asset wizards.
//          `AST-B-14` (the opening read moves to step 2 and can be typed in) ·
//          `AST-B-27` (a sub-meter is asked how its usage is shared) ·
//          `AST-B-28` (both wizards get B19 §12.2's way out).
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate in this repo reads rendered output) ·
//          law 7 habit 3 (a check's output must distinguish pass from fail TO
//          A READER) · PO 2026-09-10 (clerk and utility-admin screens are
//          verified at 1280 and 1440, and nothing narrower)
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT THE DOM SUITES CANNOT.
//
// `AssetAddWizardFixes.dom.test.tsx` and `AssetWizardExit.dom.test.tsx` assert
// the same controls against a seeded React Query cache. Three things only a
// browser can answer:
//
//   1 · **that the opening read actually WRITES.** The DOM suite stops at the
//       payload. The whole of `AST-B-14` is a `meter_reads` row appearing on a
//       meter that did not exist a second ago, in the create's own
//       transaction — so this walk creates a real meter and the row is read
//       back from PostgreSQL by `cr092_lane2_readback.py`.
//   2 · **that a Tailwind utility PAINTS.** `DEF-MET-4984`'s first fix dimmed
//       a field with a utility that lost the cascade to `.input` in an
//       unlayered legacy stylesheet: every assertion passed and the browser
//       showed no change. `getComputedStyle` is the only instrument for that,
//       and here it is pointed the other way — the opening read must now look
//       EXACTLY like the editable field beside it.
//   3 · **that the footer has a way out on every step.** An unset optional
//       prop renders nothing, and nothing in this repo reads a footer.
//
// HOW TO RUN IT
//
//   06-backend  $ DJANGO_SETTINGS_MODULE=config.settings.local \
//                 DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
//                 python3 manage.py runserver 127.0.0.1:8550 --noreload
//   07-frontend $ npx vite build && PORT=8551 API_PROXY_TARGET=http://127.0.0.1:8550 node server.mjs
//   10-scripts  $ BASE=http://127.0.0.1:8551 node cr092_lane2_wizard_walkthrough.mjs
//
// ⚠ **IT CREATES TWO REAL ASSETS PER RUN** — one meter carrying an opening
// read and one sub-meter carrying an allocation share, per width — and prints
// their numbers at the end for the readback. The numbers carry a per-run
// suffix because `BR-AST-033` hard-blocks a duplicate asset number, and a
// fixed one would make the second run fail on its own create and read as
// *"the feature broke"*.
import { existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8551";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "lane5@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr092-lane2";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      const c = join(root, dir, "chrome-linux", "chrome");
      if (existsSync(c)) return c;
    }
  }
  throw new Error("no chromium found");
}

const RUN = new Date().toISOString().replace(/[^0-9]/g, "").slice(8, 14);
const lines = [];
let pass = 0;
let fail = 0;
function say(s) { console.log(s); lines.push(s); }
function check(name, ok, detail = "") {
  if (ok) pass++; else fail++;
  say(`  ${ok ? "PASS" : "FAIL"}  ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

const clickByText = (re) => (page) =>
  page.evaluate((source) => {
    const rx = new RegExp(source, "i");
    const btn = Array.from(document.querySelectorAll("button")).find((b) => rx.test(b.textContent || ""));
    if (!btn) return false;
    btn.click();
    return true;
  }, re);

const browser = await chromium.launch({ executablePath: resolveChromium() });
const created = [];

for (const width of [1440, 1280]) {
  const page = await browser.newPage({ viewport: { width, height: 1400 } });
  page.on("pageerror", (e) => say(`  PAGE ERROR: ${e.message}`));

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  say(`\n================ WIDTH ${width} ================`);

  // ══════════════════════════════════════════════════════════════════════
  // AST-B-14 · the opening read, on step 2, enabled
  // ══════════════════════════════════════════════════════════════════════
  say("\n-- AST-B-14 · the opening read --");
  await page.goto(`${BASE}/${TENANT}/assets/new?class=meters`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  await page.selectOption("#type", "meter");
  await page.selectOption("#service", "water");
  await page.waitForTimeout(200);
  const assetNo = `L2-M-${RUN}-${width}`;
  await page.fill("#asset_no", assetNo);
  await clickByText("continue")(page);
  await page.waitForTimeout(600);

  const spec = await page.evaluate(() => {
    const el = document.querySelector("#opening_read");
    const mult = document.querySelector("#multiplier");
    const cs = el ? getComputedStyle(el) : null;
    const ms = mult ? getComputedStyle(mult) : null;
    return {
      present: el !== null,
      disabled: el?.disabled ?? null,
      readOnly: el?.readOnly ?? null,
      tabIndex: el?.tabIndex ?? null,
      background: cs?.backgroundColor ?? null,
      multBackground: ms?.backgroundColor ?? null,
      colour: cs?.color ?? null,
      multColour: ms?.color ?? null,
      cursor: cs?.cursor ?? null,
      help: document.querySelector("#opening_read-help")?.textContent ?? null,
      dateField: document.querySelector("#opening_read_date") !== null,
      dateHelp: document.querySelector("#opening_read_date-help")?.textContent ?? null,
      warning: (document.body.innerText.match(/A ×10 meter reading[^\n]*/) || [null])[0],
    };
  });
  check("the opening read is ON STEP 2", spec.present, JSON.stringify(spec));
  check("it is ENABLED — not disabled, not read-only", spec.disabled === false && spec.readOnly === false,
        JSON.stringify(spec));
  // ⚠ COMPUTED STYLE, NOT A CLASS TOKEN. `DEF-MET-4984`'s first fix passed
  // every class assertion and painted nothing.
  check("it PAINTS like the multiplier beside it",
        spec.background === spec.multBackground && spec.colour === spec.multColour,
        JSON.stringify(spec));
  check("its read date is beside it", spec.dateField, JSON.stringify(spec));
  check("the ×10 warning it was moved to sit beside is on this step",
        spec.warning !== null, JSON.stringify(spec.warning));
  say(`  · help  "${spec.help}"`);
  say(`  · date help "${spec.dateHelp}"`);
  say(`  · warning "${spec.warning}"`);

  const before = await page.evaluate(() => document.querySelector('[data-consequence="opening-read"]') !== null);
  check("B14 rule 11 · no consequence box over an EMPTY reading", before === false);
  await page.fill("#opening_read", "12481");
  await page.fill("#unit", "kgal");
  await page.waitForTimeout(250);
  const consequence = await page.evaluate(() => {
    const box = document.querySelector('[data-consequence="opening-read"]');
    return box ? (box.textContent || "").trim() : null;
  });
  check("B14 rule 11 · the consequence appears once there IS one",
        consequence !== null && /nothing is created/i.test(consequence), JSON.stringify(consequence));
  say(`  · consequence "${consequence}"`);

  await clickByText("continue")(page);
  await page.waitForTimeout(600);
  const step3 = await page.evaluate(() => ({
    installDate: document.querySelector("#install_date") !== null,
    openingRead: document.querySelector("#opening_read") !== null,
    // The refusal sentence must be gone with the control that carried it.
    oldRefusal: /cannot be captured here/i.test(document.body.innerText),
  }));
  check("step 3 is step 3", step3.installDate, JSON.stringify(step3));
  check("the opening read is GONE from step 3 — deleted, not un-disabled",
        step3.openingRead === false, JSON.stringify(step3));
  check("and its old refusal sentence went with it", step3.oldRefusal === false, JSON.stringify(step3));

  // ⚠ **THE REFUSAL THE FIRST RUN OF THIS WALK FOUND, AND A DOM TEST COULD
  // NOT.** A reading needs a date; the server defaults it to the INSTALL date
  // and refuses when there is neither. The wizard's default destination is
  // *leave it in inventory*, which needs no install date — so a clerk typing a
  // reading on step 2 walked two more steps and met the refusal on the COMMIT.
  // That is `DEF-MET-4981`'s shape one field along, and the step that can
  // repair it is this one, because the install date is on it.
  const refusedHere = await (async () => {
    await clickByText("continue")(page);
    await page.waitForTimeout(500);
    return page.evaluate(() => ({
      still: document.querySelector("#install_date") !== null,
      said: Array.from(document.querySelectorAll('[role="alert"]'))
        .map((e) => (e.textContent || "").trim())
        .filter(Boolean),
    }));
  })();
  check("a dateless reading is refused ON STEP 3, not on the commit",
        refusedHere.still && refusedHere.said.some((m) => /date/i.test(m)),
        JSON.stringify(refusedHere));
  say(`  · refusal "${refusedHere.said.join(" | ")}"`);

  await page.fill("#install_date", "2026-09-01");
  await page.waitForTimeout(200);
  await clickByText("continue")(page);
  await page.waitForTimeout(600);
  const summary = await page.evaluate(() => {
    const box = document.querySelector("[data-add-summary]");
    return box ? (box.innerText || "").replace(/\n+/g, " · ") : null;
  });
  check("the step-4 summary names the reading it is about to write",
        summary !== null && summary.includes("12481"), JSON.stringify(summary));
  say(`  · summary "${summary}"`);

  // ══════════════════════════════════════════════════════════════════════
  // AST-B-28 · a way out on every step, and a refusal that says why
  // ══════════════════════════════════════════════════════════════════════
  say("\n-- AST-B-28 · Save & exit and the Park refusal --");
  const footer = await page.evaluate(() => {
    const group = document.querySelector('[data-wizard="exit"]');
    const buttons = group ? Array.from(group.querySelectorAll("button")) : [];
    return {
      labels: buttons.map((b) => (b.textContent || "").trim()),
      parkDisabled: buttons.find((b) => /park/i.test(b.textContent || ""))?.disabled ?? null,
      reason: document.querySelector('[data-wizard="park-blocked"]')?.textContent ?? null,
      order: Array.from(document.querySelectorAll('[data-wizard="actions"] button')).map(
        (b) => (b.textContent || "").trim(),
      ),
    };
  });
  check("the add wizard's footer carries both B19 §12.2 controls",
        footer.labels.length === 2 && /save/i.test(footer.labels[0]), JSON.stringify(footer));
  check("BR-SHL-025 · Park is disabled AND carries its reason",
        footer.parkDisabled === true && (footer.reason || "").length > 0, JSON.stringify(footer));
  say(`  · footer order ${JSON.stringify(footer.order)}`);
  say(`  · refusal "${footer.reason}"`);

  // Commit — the whole path walked, not one step.
  await clickByText("add asset")(page);
  await page.waitForTimeout(2500);
  const landed = await page.evaluate(() => location.pathname);
  check("the meter was created and the wizard left the form",
        !landed.endsWith("/assets/new"), landed);
  created.push({ width, asset_no: assetNo, kind: "meter-with-opening-read", landed });

  // ══════════════════════════════════════════════════════════════════════
  // AST-B-27 · the sub-meter's allocation share
  // ══════════════════════════════════════════════════════════════════════
  say("\n-- AST-B-27 · the allocation share --");
  await page.goto(`${BASE}/${TENANT}/assets/new?class=meters`, { waitUntil: "networkidle" });
  await page.waitForTimeout(700);
  await page.selectOption("#type", "meter");
  await page.selectOption("#service", "water");
  await clickByText("continue")(page);
  await page.waitForTimeout(500);
  const meterHasAllocation = await page.evaluate(() => ({
    share: document.querySelector("#allocation_share_pct") !== null,
    rule: document.querySelector("#allocation_rule") !== null,
  }));
  check("a plain METER is not asked for an allocation share",
        meterHasAllocation.share === false && meterHasAllocation.rule === false,
        JSON.stringify(meterHasAllocation));

  await page.goto(`${BASE}/${TENANT}/assets/new?class=sub_meters`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  const subNo = `L2-S-${RUN}-${width}`;
  await page.selectOption("#type", "sub_meter");
  await page.selectOption("#service", "water");
  await page.fill("#asset_no", subNo);
  // BR-AST-003 — the parent master is a combobox: type, then click an option.
  await page.fill("#parent_asset_no", "M");
  await page.waitForTimeout(700);
  const picked = await page.evaluate(() => {
    const opt = document.querySelector('[role="option"]');
    if (!opt) return null;
    const label = opt.textContent || "";
    opt.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    return label.trim();
  });
  say(`  · master picked: ${JSON.stringify(picked)}`);
  await page.waitForTimeout(300);
  await clickByText("continue")(page);
  await page.waitForTimeout(700);
  const alloc = await page.evaluate(() => {
    const rule = document.querySelector("#allocation_rule");
    return {
      share: document.querySelector("#allocation_share_pct") !== null,
      shareHelp: document.querySelector("#allocation_share_pct-help")?.textContent ?? null,
      ruleTag: rule?.tagName ?? null,
      options: rule ? Array.from(rule.options).map((o) => `${o.value}|${o.textContent}`) : null,
    };
  });
  check("a SUB-METER is asked for its share", alloc.share, JSON.stringify(alloc));
  check("the method is a CHOOSER, never a typed code", alloc.ruleTag === "SELECT", JSON.stringify(alloc));
  // B14 rule 31 — the ratified words, not the stored codes.
  const words = (alloc.options ?? []).map((o) => o.split("|")[1]);
  check("the four ratified words are what a clerk reads",
        ["Share of the building's total", "By floor area", "Split equally", "Owner absorbs"].every((w) =>
          words.includes(w)),
        JSON.stringify(alloc.options));
  say(`  · options ${JSON.stringify(alloc.options)}`);
  say(`  · share help "${alloc.shareHelp}"`);

  await page.fill("#allocation_share_pct", "33.3");
  await page.selectOption("#allocation_rule", "sqft");
  await page.fill("#unit", "kgal");
  await clickByText("continue")(page);
  await page.waitForTimeout(500);
  await clickByText("continue")(page);
  await page.waitForTimeout(500);
  await clickByText("add asset")(page);
  await page.waitForTimeout(2500);
  const subLanded = await page.evaluate(() => location.pathname);
  check("the sub-meter was created", !subLanded.endsWith("/assets/new"), subLanded);
  created.push({ width, asset_no: subNo, kind: "sub-meter-with-allocation", landed: subLanded });

  // ══════════════════════════════════════════════════════════════════════
  // AST-B-28 · the RETIRE wizard's footer, on all three steps
  // ══════════════════════════════════════════════════════════════════════
  say("\n-- AST-B-28 · the retire wizard's way out --");
  const target = await page.evaluate(async (tenant) => {
    const res = await fetch(`/api/${tenant}/assets?per=50&tab=meters&status=active`, {
      headers: { Accept: "application/json" },
    });
    const body = await res.json();
    const rows = body.results ?? body.rows ?? [];
    return rows.length > 0 ? rows[0].id : null;
  }, TENANT);
  if (target === null) {
    check("an active meter exists to retire", false, "no row from GET /assets");
  } else {
    for (const step of [1, 2, 3]) {
      await page.goto(`${BASE}/${TENANT}/assets/${target}/retire?step=${step}`, {
        waitUntil: "networkidle",
      });
      await page.waitForTimeout(700);
      const bar = await page.evaluate(() => {
        const group = document.querySelector('[data-wizard="exit"]');
        const buttons = group ? Array.from(group.querySelectorAll("button")) : [];
        return {
          labels: buttons.map((b) => (b.textContent || "").trim()),
          parkDisabled: buttons.find((b) => /park/i.test(b.textContent || ""))?.disabled ?? null,
          reason: document.querySelector('[data-wizard="park-blocked"]')?.textContent ?? null,
          all: Array.from(document.querySelectorAll('[data-wizard="actions"] button')).map((b) =>
            (b.textContent || "").trim(),
          ),
        };
      });
      check(`retire step ${step} · a way out that is not Back`,
            bar.labels.length === 2 && bar.parkDisabled === true && (bar.reason || "").length > 0,
            JSON.stringify(bar));
      say(`    step ${step} footer ${JSON.stringify(bar.all)}`);
    }
    // Save & exit LEAVES QUIETLY and writes nothing (B19 §12.2) — the retire
    // wizard writes nothing before step 3's commit, so the asset must be
    // exactly where it was.
    await page.goto(`${BASE}/${TENANT}/assets/${target}/retire?step=1`, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    await clickByText("save . exit|save & exit")(page);
    await page.waitForTimeout(1500);
    const after = await page.evaluate(() => location.pathname);
    check("Save & exit leaves the retire wizard", !after.includes("/retire"), after);
    const stillActive = await page.evaluate(async (args) => {
      const res = await fetch(`/api/${args.tenant}/assets/${args.id}`, {
        headers: { Accept: "application/json" },
      });
      const body = await res.json();
      return body.status ?? null;
    }, { tenant: TENANT, id: target });
    check("and it wrote NOTHING — the asset is not retired", stillActive !== "retired", String(stillActive));
  }

  await page.screenshot({ path: `${OUT}/lane2-${width}.png`, fullPage: true });
  await page.close();
}

await browser.close();
say("\n================ VERDICT ================");
say(`  ${pass} passed · ${fail} failed`);
say(`  created: ${JSON.stringify(created, null, 2)}`);
say("  read the rows back:  python3 10-scripts/cr092_lane2_readback.py " +
    created.map((c) => c.asset_no).join(" "));
writeFileSync(`${OUT}/report.txt`, lines.join("\n"));
say(`  report: ${OUT}/report.txt`);
process.exit(fail === 0 ? 0 : 1);
