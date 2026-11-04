// ── Trace ──────────────────────────────────────────────
// Change:  Lane H wave 2 — new connect steps 3 and 4 (PO 2026-09-16: the units
//          table arrives filled in, and step 4 becomes one row per unit per
//          service with seven defaulted columns).
// Rules:   hard-won law 6 (NO GATE IN THIS REPO READS RENDERED OUTPUT — nine
//          defects were found by diffing the running app and by nothing else) ·
//          B14 rule 42 (a screen is built from the drawing AS AN IMAGE) ·
//          PO definition of done, verbatim: *"ensure you do web walkthorugh
//          before you sign off the user story or build"*
// ───────────────────────────────────────────────────────
//
// WHAT THIS MEASURES THAT NO UNIT TEST CAN, AND IT IS THE WHOLE REASON IT EXISTS
//
// **THE TEST ENVIRONMENT DOES NO LAYOUT.** Every element is zero by zero in
// jsdom, so `offsetWidth` is 0, nothing overflows and nothing can be seen to
// overflow. The step rail on this same wizard overflowed by 244px for three
// days and not one of 41 passing cases could see it. A SEVEN-COLUMN GRID OVER
// SIX UNITS IS EXACTLY THAT HAZARD, which is why this script's headline number
// is a WIDTH and not a count.
//
// It also counts the rows and reads the three counts off the rendered page, so
// the figures in the report are measured rather than computed twice.
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const requireFrontend = createRequire(
  path.join(process.cwd(), "07-frontend", "node_modules", "x.js"),
);
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/laneh_w2";
const UNITS = Number(process.env.UNITS ?? 6);

fs.mkdirSync(OUT, { recursive: true });
const say = (...a) => console.log(...a);

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (fs.existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!fs.existsSync(root)) continue;
    for (const dir of fs.readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const rel of [
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
        "chrome-linux64/chrome",
      ]) {
        const candidate = path.join(root, dir, rel);
        if (fs.existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });

/** Walk the wizard to step 4 at one viewport width and measure it there. */
async function walk(width) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

  // ⚠ CLICKED THROUGH, NEVER NAVIGATED BY URL — the draft lives in this page's
  // own state and does not survive a reload, so `?step=4` would arrive empty.
  await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);

  const forward = async () => {
    const buttons = await page.$$('[data-wizard="actions"] button');
    await buttons[buttons.length - 1].click();
    await page.waitForTimeout(1300);
  };

  // 1 · Owner & scope
  await page.selectOption("#nc_owner_kind", "builder_developer");
  await page.fill("#nc_owner_name", "Lane H Grid Walk LLC");
  await page.selectOption("#nc_owner_subcategory", "permanent");
  for (const [sel, val] of [
    ["#nc_owner_party_kind", "company"],
    ["#nc_party_kind", "company"],
  ]) {
    if ((await page.$(sel)) !== null) {
      await page.selectOption(sel, val).catch(() => undefined);
    }
  }
  for (const sel of ["#nc_tax_id", "#nc_owner_tax_id"]) {
    if ((await page.$(sel)) !== null) await page.fill(sel, `TX-${STAMP.slice(8)}`);
  }
  await page.fill("#nc_prefix", "").catch(() => undefined);
  await page.check('input[name="nc_scope"][value="new_premise"]', { force: true });
  await page.check('input[name="nc_mode"][value="our_crew"]', { force: true });
  await forward();

  // 2 · Premise
  await page.fill("#nc_address", `${STAMP.slice(8)} Lane H Grid Walk`);
  await page.waitForTimeout(900);
  for (const [sel, val] of [
    ["#nc_city", "Austin"],
    ["#nc_postal_code", "78704"],
    ["#nc_zip", "78704"],
  ]) {
    if ((await page.$(sel)) !== null) await page.fill(sel, val).catch(() => undefined);
  }
  if ((await page.$("#nc_state")) !== null) {
    await page.selectOption("#nc_state", "TX").catch(() => undefined);
  }
  const types = await page.$$eval("#nc_premise_type option", (ns) =>
    ns.map((o) => o.value).filter((v) => v !== ""),
  );
  if (types.length > 0) await page.selectOption("#nc_premise_type", types[0]);
  await forward();

  // 3 · Units — MEASURED HERE TOO, because the Occupancy column is new.
  await page.fill("#nc_from", "1");
  await page.fill("#nc_to", String(UNITS));
  await page.waitForTimeout(900);
  const step3 = await page.evaluate(() => {
    const cells = [...document.querySelectorAll("td[data-occupancy]")];
    const table = document.querySelector("table");
    return {
      occupancyCells: cells.length,
      vacant: cells.filter((c) => c.dataset.occupancy === "vacant_service_off").length,
      dashes: cells.filter((c) => c.dataset.occupancy === "none").length,
      headers: [...document.querySelectorAll("th")].map((h) => h.textContent.trim()),
      tableWidth: table === null ? 0 : Math.round(table.getBoundingClientRect().width),
      docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
  await page.screenshot({ path: `${OUT}/step3-${width}.png`, fullPage: true });
  await forward();

  // 4 · Map services — tick the three the blueprint draws, then measure.
  // ⚠ **EACH TICK IS VERIFIED AND RETRIED, NEVER FIRED AND HOPED FOR.** The
  // input is `sr-only` under a drawn mark, so `check()` needs `force` — and a
  // forced click that lands on a stale handle after React re-renders is a
  // silent no-op. The first version of this script swallowed that in a
  // `.catch()` and measured a 7-row grid as though it were the 21-row one.
  // ⚠ **WAIT FOR THE STEP, NOT FOR A NUMBER OF MILLISECONDS.** At 1280 — which
  // is simply the FIRST page this script opens, so the coldest — a fixed 1300ms
  // after `Continue` left the walk still on step 3, and every tick below then
  // found nothing. The run that "measured" a 7-row grid was measuring a screen
  // it had not arrived at.
  await page.waitForSelector("#nc_premise_services_electric", { timeout: 30000 });
  const ticked = [];
  for (const code of ["electric", "water", "sewer"]) {
    const sel = `#nc_premise_services_${code}`;
    for (let attempt = 0; attempt < 4; attempt += 1) {
      const on = await page.$eval(sel, (n) => n.checked).catch(() => false);
      if (on) break;
      // ⚠ **`.click()` ON THE INPUT ITSELF, NOT `page.check()`.** The tick is an
      // `sr-only` input under a drawn `<span data-checkbox-mark>`; Playwright's
      // actionability check scrolls to the input and clicks its POINT, which
      // lands on the drawn mark's label — sometimes toggling, sometimes not,
      // and `force` does not change where the point is. Clicking the element
      // in the page fires React's change handler directly, every time.
      await page.$eval(sel, (n) => n.click()).catch((error) => {
        if (attempt === 3) throw error;
      });
      await page.waitForTimeout(500);
    }
    if (await page.$eval(sel, (n) => n.checked).catch(() => false)) ticked.push(code);
  }
  if (ticked.length !== 3) {
    throw new Error(`only ticked ${JSON.stringify(ticked)} — a partial grid is not a measurement`);
  }
  // ⚠ **WAIT FOR THE GRID TO BE THE SIZE IT WILL BE, NOT MERELY PRESENT.**
  // The first run of this script measured 7 rows and 0 asset selects at 1280
  // and 21 rows at 1440 — the same build, two different answers, because a
  // fixed sleep raced the ticks and the two lookup reads. A width measured
  // over a third of the grid is worse than no width at all: it is a number
  // that looks like a measurement.
  await page
    .waitForFunction(
      (want) => document.querySelectorAll("[data-grid-row]").length >= want,
      UNITS * 3 + 3,
      { timeout: 30000 },
    )
    .catch(() => undefined);
  await page
    .waitForFunction(() => document.querySelectorAll('[id^="nc_asset_"]').length > 0, undefined, {
      timeout: 30000,
    })
    .catch(() => undefined);
  await page.waitForTimeout(800);

  const step4 = await page.evaluate(() => {
    const grid = document.querySelector("[data-unit-service-grid]");
    const read = (name) => {
      const cell = document.querySelector(`[data-count="${name}"]`);
      return cell === null ? null : cell.textContent.trim();
    };
    const rows = [...document.querySelectorAll("[data-grid-row]")];
    return {
      rows: rows.length,
      headers:
        grid === null ? [] : [...grid.querySelectorAll("thead th")].map((h) => h.textContent.trim()),
      gridWidth: grid === null ? 0 : Math.round(grid.getBoundingClientRect().width),
      gridRight: grid === null ? 0 : Math.round(grid.getBoundingClientRect().right),
      servicePoints: read("service-points"),
      meters: read("meters"),
      workOrders: read("work-orders"),
      // THE NUMBER THIS SCRIPT EXISTS FOR: how far the page scrolls sideways.
      docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      shortcuts: [...document.querySelectorAll("[data-grid-shortcuts] button")].map((b) =>
        b.textContent.trim(),
      ),
      assetSelects: document.querySelectorAll('[id^="nc_asset_"]').length,
      sizeSelects: document.querySelectorAll('[id^="nc_size_"]').length,
      installInputs: document.querySelectorAll('[id^="nc_install_"]').length,
      dashCells: [...document.querySelectorAll("[data-grid-row] td")].filter(
        (td) => td.textContent.trim() === "—",
      ).length,
    };
  });
  await page.screenshot({ path: `${OUT}/step4-${width}.png`, fullPage: true });
  await page.close();
  return { step3, step4 };
}

for (const width of [1280, 1440]) {
  say(`\n═══ viewport ${width} ═══`);
  const { step3, step4 } = await walk(width);
  say("STEP 3  headers:", JSON.stringify(step3.headers));
  say(
    `STEP 3  occupancy cells ${step3.occupancyCells} (vacant ${step3.vacant}, dash ${step3.dashes})`,
  );
  say(`STEP 3  table ${step3.tableWidth}px · page overflow ${step3.docOverflow}px`);
  say("STEP 4  headers:", JSON.stringify(step4.headers));
  say(`STEP 4  rows ${step4.rows}`);
  say(
    `STEP 4  counts — service points ${step4.servicePoints} · meters ${step4.meters} · work orders ${step4.workOrders}`,
  );
  say(
    `STEP 4  controls — asset ${step4.assetSelects}, size ${step4.sizeSelects}, install ${step4.installInputs}, dashes ${step4.dashCells}`,
  );
  say("STEP 4  shortcuts:", JSON.stringify(step4.shortcuts));
  say(`STEP 4  GRID ${step4.gridWidth}px, right edge ${step4.gridRight}px`);
  say(`STEP 4  PAGE OVERFLOW ${step4.docOverflow}px  ${step4.docOverflow > 0 ? "⛔" : "✅"}`);
}

await browser.close();
say(`\nscreenshots in ${OUT}`);
