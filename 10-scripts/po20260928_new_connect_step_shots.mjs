// ── Trace ──────────────────────────────────────────────
// Purpose: CAPTURE the New Connect wizard as the product renders it TODAY, one
//          PNG per step, so the PO looks at the screens rather than at a
//          drawing. Nothing is built, nothing is asserted, nothing is written:
//          the walk STOPS on step 8 and never presses Create.
// Rules:   hard-won law 6 (no gate in this repo reads rendered output — a diff
//          against the drawing is done by looking) · B14 rule 42 (a screen is
//          judged as it renders)
// Basis:   10-scripts/po_new_connect_clerk_walk.mjs — the clerk walk that
//          already knows this wizard's selectors and its two traps (a radio in
//          this kit is visually hidden, so `check()` can never see it in the
//          viewport; the services control is a chip multi-select and not tick
//          boxes). This is that walk with the press REMOVED, the New connects
//          LIST added in front of it, and the capture at 1440 wide, full page,
//          device scale 2.
//
// RUN:  BASE=http://127.0.0.1:8080 OUT=/tmp/nc-shots \
//         node 10-scripts/po20260928_new_connect_step_shots.mjs
// ───────────────────────────────────────────────────────
const { mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/nc-shots";
const UNITS = Number(process.env.UNITS ?? 6);
// ⚠ NEVER `playwright install` here — the installed build may not match the
// repo's playwright version, so the binary is named instead.
const CHROME =
  process.env.E2E_CHROMIUM_EXECUTABLE ??
  "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
mkdirSync(OUT, { recursive: true });

const STAMP = new Date().toISOString().replace(/[^0-9]/g, "").slice(0, 14);
const ADDRESS = `${STAMP.slice(8)} Cottonwood Bend`;
const say = (...a) => console.log(...a);
const notes = [];

const browser = await chromium.launch({ executablePath: CHROME });
const ctx = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 2,
});
const page = await ctx.newPage();
page.on("console", (m) => {
  if (m.type() === "error") notes.push(`console error: ${m.text().slice(0, 160)}`);
});
page.on("response", (r) => {
  if (r.status() >= 400 && r.url().includes("/api/")) {
    notes.push(`HTTP ${r.status()} ${r.url().replace(BASE, "")}`);
  }
});

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
say(`signed in as ${EMAIL}`);

// ⚠ **`fullPage: true` CAPTURES THE VIEWPORT AND NOTHING MORE ON THIS APP, AND
// IT DOES NOT SAY SO.** The shell is a fixed sidebar beside a `100vh` column
// that scrolls INSIDE itself, so `document.documentElement.scrollHeight` is the
// viewport height and Playwright has nothing to extend. The first run of this
// script produced nine files all exactly 2880x2000 — every one of them cut off
// below the fold, and one of them cut off ABOVE it too, because filling the
// form had scrolled the inner column and the H1 had gone. A screenshot that
// silently answers a smaller question than the one asked is hard-won law 7's
// shape in a capture tool.
//
// So: scroll the inner column back to the top, measure how much it hides, and
// GROW THE VIEWPORT by that much before shooting. The layout is `vh`-based, so
// a taller viewport is a taller shell and the content simply fits.
const BASE_HEIGHT = 1000;
async function growToFit() {
  for (let pass = 0; pass < 4; pass += 1) {
    const hidden = await page.evaluate(() => {
      let worst = 0;
      for (const node of document.querySelectorAll("*")) {
        const over = node.scrollHeight - node.clientHeight;
        if (over > worst && node.clientHeight > 200) {
          const style = getComputedStyle(node);
          if (/auto|scroll/.test(style.overflowY)) {
            node.scrollTop = 0;
            worst = over;
          }
        }
      }
      const page = document.documentElement.scrollHeight - window.innerHeight;
      return Math.max(worst, page, 0);
    });
    if (hidden < 4) return;
    const next = Math.min(page.viewportSize().height + hidden + 24, 12000);
    if (next === page.viewportSize().height) return;
    await page.setViewportSize({ width: 1440, height: next });
    await page.waitForTimeout(500);
  }
}

async function shot(name) {
  await page.waitForTimeout(700);
  // The last field filled keeps the focus ring, which is the brand accent and
  // reads as an error outline in a still image. Blur it — the screen is being
  // photographed, not driven.
  await page.evaluate(() => document.activeElement?.blur?.());
  await page.setViewportSize({ width: 1440, height: BASE_HEIGHT });
  await page.waitForTimeout(400);
  await growToFit();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  const size = page.viewportSize();
  say(`  (captured at 1440x${size.height}, device scale 2)`);
  await page.setViewportSize({ width: 1440, height: BASE_HEIGHT });
  await page.waitForTimeout(300);
  const seen = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-refusal],[role="alert"]'))
      .map((n) => n.textContent.trim())
      .filter(Boolean)
      .slice(0, 6),
  );
  if (seen.length) notes.push(`${name}: ${seen.join(" | ")}`);
  say(`  captured ${name}.png`);
}

// A radio in this kit is visually hidden and often below the fold, so neither
// `check()` nor `scrollIntoViewIfNeeded()` can ever succeed on it. The label is
// what a person clicks; dispatching on the input is the same event React binds.
async function pick(name, value) {
  const el = await page.$(`input[name="${name}"][value="${value}"]`);
  if (el === null) {
    notes.push(`no control named ${name}=${value}`);
    return false;
  }
  await el.evaluate((n) => n.click());
  const on = await page.evaluate(
    ([n, v]) => document.querySelector(`input[name="${n}"][value="${v}"]`)?.checked === true,
    [name, value],
  );
  if (!on) notes.push(`${name}=${value} would not take`);
  return on;
}

async function forward(label) {
  const buttons = await page.$$('[data-wizard="actions"] button');
  if (buttons.length === 0) {
    notes.push(`${label}: no wizard action buttons on the page`);
    return null;
  }
  const last = buttons[buttons.length - 1];
  const text = (await last.innerText()).trim();
  if (await last.isDisabled()) {
    notes.push(`${label}: cannot advance — "${text}" is DISABLED`);
    say(`  → ${label}: "${text}" ⛔ DISABLED`);
    return text;
  }
  await last.click();
  await page.waitForTimeout(1600);
  const stillHere = await page.evaluate(
    () => new URLSearchParams(window.location.search).get("step"),
  );
  say(`  → ${label}: pressed "${text}" — now on step ${stillHere}`);
  const refused = await page.evaluate(() =>
    Array.from(document.querySelectorAll('[data-refusal],[role="alert"]'))
      .map((n) => n.textContent.trim())
      .filter(Boolean)
      .slice(0, 4),
  );
  if (refused.length) notes.push(`${label} REFUSED: ${refused.join(" | ")}`);
  return text;
}

// ── 0 · The New connects list, before the wizard is entered ───────────────
await page.goto(`${BASE}/${TENANT}/accounts?tab=new-connects`, { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await shot("00-new-connects-list");

// ── 1 · Owner & scope ─────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/connections/new`, { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await page.selectOption("#nc_owner_kind", "builder_developer").catch(() => {});
await page.fill("#nc_owner_name", "Cottonwood Bend Developments LLC").catch(() => {});
await page.selectOption("#nc_owner_subcategory", "permanent").catch(() => {});
await page.fill("#nc_owner_email", "build@cottonwoodbend.example").catch(() => {});
await page.fill("#nc_owner_phone", "512-555-0143").catch(() => {});
await pick("nc_party_kind", "company");
await page.waitForTimeout(400);
if (await page.$("#nc_tax_id")) await page.fill("#nc_tax_id", `74-${STAMP.slice(7, 14)}`).catch(() => {});
await page.fill("#nc_prefix", "Apt").catch(() => {});
await pick("nc_scope", "new_premise");
await pick("nc_mode", "our_crew");
await shot("01-step1-owner-and-scope");
await forward("step 1 · Owner & scope");

// ── 2 · The premise ───────────────────────────────────────────────────────
await page.fill("#nc_address", ADDRESS).catch(() => {});
for (const [sel, val] of [
  ["#nc_city", "Austin"],
  ["#nc_state", "TX"],
  ["#nc_zip", "78704"],
  ["#nc_premise_name", "Cottonwood Bend Court"],
  ["#nc_parcel", "0412-88-0031"],
]) {
  if (await page.$(sel)) await page.fill(sel, val).catch(() => {});
}
const ptypes = await page
  .$$eval("#nc_premise_type option", (ns) => ns.map((o) => o.value).filter(Boolean))
  .catch(() => []);
if (ptypes.length) {
  // A multi-unit type, so the Units step has something to ask for.
  const want = ptypes.find((v) => /apart|multi|complex/i.test(v)) ?? ptypes[0];
  await page.selectOption("#nc_premise_type", want).catch(() => {});
  say(`  premise types offered: ${ptypes.join(", ")} — took ${want}`);
}
const routes = await page
  .$$eval("#nc_route option", (ns) => ns.map((o) => o.value).filter(Boolean))
  .catch(() => []);
if (routes.length) await page.selectOption("#nc_route", routes[0]).catch(() => {});
// The services control is a CHIP MULTI-SELECT reading the tenant's own enabled
// services, not tick boxes.
await page.waitForSelector("#services_available-add", { timeout: 15000 }).catch(() => {});
if ((await page.$("#services_available-add")) === null) {
  notes.push("step 2: no services chip control found");
} else {
  const offered = await page.$$eval("#services_available-add option", (ns) =>
    ns.map((o) => o.value).filter(Boolean),
  );
  say(`  services this utility sells: ${offered.length} — ${offered.join(", ")}`);
  for (const code of offered) {
    await page.selectOption("#services_available-add", code).catch(() => {});
    await page.waitForTimeout(250);
  }
}
const plans = await page
  .$$eval("#nc_plan option", (ns) =>
    ns.map((o) => ({ v: o.value, t: o.textContent.trim() })).filter((o) => o.v),
  )
  .catch(() => []);
if (plans.length === 0) notes.push("step 2: #nc_plan offered no plan");
else {
  // A residential plan for an apartment complex — the first option is
  // `Industrial`, which draws the screen's own WON'T COVER warning and is a
  // less plausible thing for a clerk to have chosen here.
  const want = plans.find((p) => /resid/i.test(p.t)) ?? plans[0];
  await page.selectOption("#nc_plan", want.v).catch(() => {});
  say(`  plans offered on step 2: ${plans.map((p) => p.t).join(", ")} — took ${want.t}`);
}
await shot("02-step2-the-premise");
await forward("step 2 · Premise");

// ── 3 · The units ─────────────────────────────────────────────────────────
await page.fill("#nc_from", "1").catch(() => {});
await page.fill("#nc_to", String(UNITS)).catch(() => {});
await page.waitForTimeout(900);
await shot("03-step3-the-units");
await forward("step 3 · Units");

// ── 4 · Which services per unit ───────────────────────────────────────────
await page.waitForTimeout(1500);
const grid = await page.evaluate(() => ({
  assets: document.querySelectorAll('[id^="nc_asset_"]').length,
  sizes: document.querySelectorAll('[id^="nc_size_"]').length,
  installs: document.querySelectorAll('[id^="nc_install_"]').length,
}));
say(`  grid: ${grid.assets} asset cells · ${grid.sizes} size cells · ${grid.installs} install dates`);
await shot("04-step4-which-services-per-unit");
await forward("step 4 · Map services");

// ── 5 · Work orders ───────────────────────────────────────────────────────
await page.waitForTimeout(1200);
await shot("05-step5-work-orders");
await forward("step 5 · Work orders");

// ── 6 · Charges ───────────────────────────────────────────────────────────
await page.waitForTimeout(1200);
const codes = await page
  .$$eval("#nc_quote_charge_code option", (ns) =>
    ns.map((o) => ({ v: o.value, t: o.textContent.trim() })).filter((o) => o.v),
  )
  .catch(() => []);
if (codes.length === 0) notes.push("step 6: no charge codes offered");
else {
  // Prefer a code the catalogue can actually price — `TAP`, `IMPACT` and
  // `DAMAGE` are live codes with NO amount and the step refuses them by name.
  const priced = codes.find((c) => /connect|tap|service/i.test(c.t)) ?? codes[0];
  await page.selectOption("#nc_quote_charge_code", priced.v).catch(() => {});
  say(`  charge codes offered: ${codes.length}, took ${priced.v} (${priced.t})`);
  await page.waitForTimeout(1500);
  // ⚠ **PICKING THE CODE IS NOT ADDING THE CHARGE.** The first run of this
  // script selected a code and a basis and walked on, and step 8 printed
  // `One-time charges —` — the build carried no charge at all. `+ Charge` is
  // the act; the two pickers above it are only the answer to what.
  const add = await page.$('button:has-text("+ Charge")');
  if (add === null) notes.push("step 6: no `+ Charge` button");
  else {
    await add.click();
    await page.waitForTimeout(2000);
    const lines = await page.evaluate(() => document.body.innerText.includes("No charge on this build."));
    if (lines) notes.push("step 6: `+ Charge` was pressed and the build still says `No charge on this build.`");
  }
}
if (await page.$("#nc_quote_due_days")) await page.fill("#nc_quote_due_days", "30").catch(() => {});
await page.waitForTimeout(1200);
await shot("06-step6-charges");
await forward("step 6 · Charges");

// ── 7 · Telling the customer ──────────────────────────────────────────────
await page.waitForTimeout(1200);
await shot("07-step7-telling-the-customer");
await forward("step 7 · Communication");

// ── 8 · What will be created — CAPTURE AND STOP. NOTHING IS PRESSED. ──────
await page.waitForTimeout(2000);
await shot("08-step8-what-will-be-created");
const finalButton = await page.evaluate(() => {
  const bs = Array.from(document.querySelectorAll('[data-wizard="actions"] button'));
  const last = bs[bs.length - 1];
  return last === undefined ? null : { text: last.innerText.trim(), disabled: last.disabled };
});
say(`\nthe button NOT pressed: ${JSON.stringify(finalButton)}`);

say(`\n══ WHAT THE WALK NOTICED: ${notes.length} ══`);
notes.forEach((n) => say("  · " + n));
say(`\nscreens: ${OUT}`);
await browser.close();

// ── Lifecycle ─────────────────────────────────────────────
// packet: PO request 2026-09-28 — "show me the real screens, not the drawing"
// status: CAPTURE TOOL — it asserts nothing and writes nothing to the product
// ──────────────────────────────────────────────────────────
