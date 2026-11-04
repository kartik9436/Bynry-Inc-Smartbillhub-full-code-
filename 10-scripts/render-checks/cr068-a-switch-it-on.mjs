/**
 * RENDERED-OUTPUT CHECK — CR-068 wave A, "Switch it on", in a real browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: no gate in this repository looks at
 * rendered output. PO ruling 2026-09-03: *"ensure you do web walkthorugh
 * before you sign off the user story or build"*. A story is not signed off
 * until this has run green against a running product.
 *
 * ⚠ **AND B14 RULE 21 MAKES IT UNAVOIDABLE HERE.** A Tailwind utility is
 * emitted only for a file the ledger owns AND only if the theme declares it —
 * this theme clears Tailwind's stock palette, so `bg-white` and `text-lg`
 * compile to NOTHING while tsc, eslint and every `toContain` pass (DEF-974;
 * the integrations grid shipped twelve such names on 2026-09-03). The only
 * thing that can prove the portal's rules compiled is computed style in a
 * real engine — step 9 below.
 *
 * ── HOW TO RUN IT ─────────────────────────────────────────────────────────
 *   createdb sbh_cr068a
 *   DATABASE_URL=…/sbh_cr068a python3 06-backend/manage.py migrate
 *   DATABASE_URL=…/sbh_cr068a python3 06-backend/manage.py seed_portal_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_cr068a" \
 *     python3 06-backend/manage.py runserver 127.0.0.1:8068 --noreload &
 *   (cd 07-frontend && npx vite build && \
 *      PORT=4268 API_PROXY_TARGET=http://127.0.0.1:8068 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4268 \
 *   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *     node 10-scripts/render-checks/cr068-a-switch-it-on.mjs
 *
 * ⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING.** A mid-run reseed
 * looks exactly like a broken screen.
 *
 * ── WHAT IT CLICKS (the wave A demo script, 10-execution-plan.md) ─────────
 *   1  Sign in to the STAFF app as Pine Hill's System Admin; open Settings →
 *      Configure → Customer portal. The address reads `<host>/pine-hill/portal`
 *      with Copy and a QR code that actually loaded (naturalWidth > 0) — read
 *      from `tenants.subdomain`, no second column (US-CWP-069 TC-1).
 *   2  Turn the portal OFF; in a second tab `/pine-hill/portal` is a HOLDING
 *      page with no cards (defaults fail closed, law 3; R8).
 *   3  Turn it back ON; reload: SIX errand cards — all of them, in the
 *      wireframe's order — and the *Already have a login? Sign in* bar. FOUR
 *      are usable; *Check my area* is disabled by ruling (R9) and *Help &
 *      answers* is disabled because nothing is published (BR-CWP-093), each
 *      saying so in one sentence. The *Help* and *Visit us* NAV WORDS are
 *      still absent. No password field anywhere.
 *   4  Quick pay OFF; reload: the *Pay a bill* card is still THERE and now
 *      DISABLED, saying it is not offered online, and linking nowhere. Then
 *      back on.
 *
 *   ⚠ **STEPS 3 AND 4 SAID *four cards* AND *the card is GONE* UNTIL
 *      2026-09-05**, when the PO looked at a live tenant beside the blueprint
 *      and ruled *"Yoi ahev these cards - may be disable them, but for
 *      completess have them on screen"*. Both are rewritten here in the commit
 *      that carries the code, because a walkthrough asserting the old shape is
 *      a check that goes red for being right.
 *   5  *Send your own reading* reads OFF — the one switch that is (R8) — and
 *      the usage panel says *Readings are off, so nothing is counted*.
 *   6  Branding: logo, trading name and the two hexes READ-ONLY with *Edit in
 *      Company*; type a strapline — the preview updates as you type; save;
 *      reload `/pine-hill/portal`: the strapline is under the utility's name.
 *   7  `/oak-ridge/portal`: Oak Ridge's own strapline and colours, and NOT ONE
 *      Pine Hill string (BR-CWP-005).
 *   8  (G81 and G82 run in run_gates.py; their RED proofs are quoted in their
 *      docstrings — not clicked here.)
 *   9  The utilities COMPILED, read as computed style in a real engine.
 *  10  No uuid and no rule id in anything a customer or a clerk sees (B14
 *      rules 31, 32); no sideways scroll at 1440.
 *  11  MEASURED, NOT ASSERTED: the guest front page's server round trip, 30
 *      requests, min / median / p95 printed. The response-time target is
 *      `OQ-CWP-1510`, OPEN — this prints a number a person can read; it does
 *      not claim any target was met.
 */

import { execFileSync } from "node:child_process";
import { mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const require = createRequire(join(process.cwd(), "07-frontend", "package.json"));
const { chromium } = require("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  try {
    execFileSync(wanted, ["--version"], { stdio: "ignore" });
    return wanted;
  } catch {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const candidate of [join(root, dir, "chrome-linux", "chrome"), join(root, dir)]) {
        try {
          execFileSync(candidate, ["--version"], { stdio: "ignore" });
          return candidate;
        } catch {
          // keep looking
        }
      }
    }
    return wanted;
  }
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:4268";
const TENANT = "pine-hill";
const OTHER = "oak-ridge";
const EMAIL = process.env.SMOKE_EMAIL ?? "sarah@pinehillwp.test";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "Pin3Hill!passw0rd";
const OUT = process.env.SMOKE_OUT ?? "/tmp/cr068-a";
const VIEWPORT = { width: 1440, height: 1000 };
const SETTINGS = `${BASE}/${TENANT}/settings/reference-data/customer-portal`;
const PORTAL = `${BASE}/${TENANT}/portal`;

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";
const FORBIDDEN = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /\bDEF-(?:[A-Z]{3}-)?\d{3,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** Drive a switch to the wanted state and wait for the server's answer. */
async function setSwitch(page, selector, wanted) {
  const button = page.locator(`${selector} button[role="switch"]`).first();
  const state = await button.getAttribute("data-switch-state");
  if ((state === "on") === wanted) return;
  await button.click();
  await page.waitForFunction(
    ([sel, want]) =>
      document.querySelector(`${sel} button[role="switch"]`)?.getAttribute("data-switch-state") ===
      (want ? "on" : "off"),
    [selector, wanted],
    { timeout: 15000 },
  );
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const staff = await context.newPage();
  staff.on("console", (m) => {
    if (m.type() === "error") console.log(`   [console.error] ${m.text().slice(0, 200)}`);
  });
  console.log(`cr068-a: ${BASE} tenant=${TENANT} ${VIEWPORT.width}x${VIEWPORT.height}`);

  // ═════ 1 · Settings → Configure → Customer portal ═════════════════════════
  console.log("\n── 1 · the address a utility could never find ──");
  await staff.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await staff.fill("#signin-email", EMAIL);
  await staff.fill("#signin-password", PASSWORD);
  await staff.click('button[type="submit"]');
  await staff.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 20000 });
  console.log("   signed in as Pine Hill's System Admin");
  await staff.goto(SETTINGS, { waitUntil: "networkidle" });
  await staff.waitForSelector('[data-screen="CWP-069"]', { timeout: 20000 });
  const address = (await staff.locator("[data-portal-address]").innerText()).trim();
  check(address === `${BASE}/${TENANT}/portal`, `the address reads ${address} — the slug as a path`);
  check(
    (await staff.locator("button", { hasText: "Copy" }).count()) > 0,
    "a Copy control sits beside the address",
  );
  // An SVG with no intrinsic size reports naturalWidth 0 even when it drew, so
  // the image is asked whether it finished and the SERVER is asked what it sent.
  const qrSrc = await staff.locator("[data-portal-qr]").getAttribute("src");
  const qrDone = await staff.locator("[data-portal-qr]").evaluate((img) => img.complete);
  const qr = await staff.request.get(`${BASE}${qrSrc}`);
  const qrBody = await qr.text();
  check(
    qrDone && qr.status() === 200 && (qr.headers()["content-type"] ?? "").startsWith("image/svg+xml") && qrBody.includes("<svg"),
    `the QR code is a real SVG the server drew (${qr.status()}, ${(qr.headers()["content-type"] ?? "").split(";")[0]}, ${qrBody.length} bytes)`,
  );
  check((await staff.locator('[data-switch]').count()) === 5, "five switches, each with one sentence");
  check(
    (await staff.locator("body").getAttribute("data-screen-id")) === "CWP-069",
    "the screen carries its id: CWP-069 on <body>",
  );
  await staff.screenshot({ path: join(OUT, "1-settings-overview.png"), fullPage: true });

  // ═════ 2 · OFF → the holding page ════════════════════════════════════════
  console.log("\n── 2 · off: a holding page, no cards ──");
  await setSwitch(staff, 'section:has([data-portal-live])', false);
  check(
    (await staff.locator("[data-portal-live]").getAttribute("data-portal-live")) === "off",
    "the panel reads Off",
  );
  const guest = await context.newPage();
  await guest.goto(PORTAL, { waitUntil: "networkidle" });
  await guest.waitForSelector('[data-portal-frame="guest"]', { timeout: 20000 });
  check((await guest.locator('[data-holding="true"]').count()) === 1, "the holding page is drawn");
  check((await guest.locator("[data-errand]").count()) === 0, "no errand card while the portal is off");
  check((await guest.locator("nav").count()) === 0, "no navigation while the portal is off");
  check(
    (await guest.locator("body").getAttribute("data-screen-id")) === "CWP-001",
    "the portal's own tag: CWP-001 on <body>",
  );
  await guest.screenshot({ path: join(OUT, "2-portal-off-holding.png"), fullPage: true });

  // ═════ 3 · ON → all six cards, four of them usable ══════════════════════
  console.log("\n── 3 · live: six cards, four usable, sign-in as one bar, no password field ──");
  await setSwitch(staff, 'section:has([data-portal-live])', true);
  await guest.reload({ waitUntil: "networkidle" });
  await guest.waitForSelector("[data-errand]", { timeout: 20000 });
  const cards = await guest.locator("[data-errand]").evaluateAll((n) => n.map((e) => e.getAttribute("data-errand")));
  check(
    JSON.stringify(cards) ===
      JSON.stringify([
        "pay_bill",
        "report_problem",
        "check_my_area",
        "start_service",
        "what_things_cost",
        "help_answers",
      ]),
    `all six errand cards in the wireframe's order: ${cards.join(" · ")}`,
  );
  // ⚠ THE TWO THAT CANNOT BE USED ARE ON SCREEN AND SAY WHY — read as RENDERED
  // TEXT, because that is the only thing that proves a customer can see it
  // (law 6). A `data-` attribute proves the payload, never the page.
  const areaText = await guest.locator('[data-errand="check_my_area"]').innerText();
  check(/No status page here yet/i.test(areaText), `Check my area says why (R9): ${areaText.replace(/\n/g, " ")}`);
  const helpText = await guest.locator('[data-errand="help_answers"]').innerText();
  check(
    /Nothing published here yet/i.test(helpText),
    `Help & answers says why (BR-CWP-093): ${helpText.replace(/\n/g, " ")}`,
  );
  check(
    (await guest.locator("[data-unavailable]").count()) === 2,
    "exactly two cards are disabled, and the other four are not",
  );
  // ⚠ AND NOT ONE OF THE THREE REASON CODES IS ON THE GLASS (B14 rule 31).
  const bodyText = await guest.locator("body").innerText();
  check(
    !/switched_off_by_the_utility|status_page_not_offered|nothing_published_yet|portal\.card\./.test(bodyText),
    "no reason code and no translation key is visible anywhere on the page",
  );
  // The CARDS are a catalogue; the NAV WORDS are destinations and still go.
  check((await guest.locator('[data-link="help"], [data-link="visit"]').count()) === 0, "no Help / Visit us link");
  check((await guest.locator('input[type="password"]').count()) === 0, "no password field anywhere");
  check((await guest.locator("text=Already have a login?").count()) === 1, "the sign-in bar reads its sentence");
  check((await guest.locator('[data-held="true"]').count()) >= 5, "every Start → and Sign in is HELD with its reason (R3)");
  check((await guest.locator("[data-service-chip]").count()) === 4, "four service chips (Water · Sewer · Trash · Electric)");
  await guest.screenshot({ path: join(OUT, "3-portal-live-six-cards.png"), fullPage: true });

  // ═════ 4 · Quick pay off → the card stays, disabled ═════════════════════
  console.log("\n── 4 · quick pay off: Pay a bill is disabled, not gone ──");
  await setSwitch(staff, '[data-switch="quick_pay_enabled"]', false);
  await guest.reload({ waitUntil: "networkidle" });
  await guest.waitForSelector("[data-errand]", { timeout: 20000 });
  check((await guest.locator('[data-errand="pay_bill"]').count()) === 1, "Pay a bill is still on screen");
  check((await guest.locator("[data-errand]").count()) === 6, "all six cards remain");
  const payText = await guest.locator('[data-errand="pay_bill"]').innerText();
  check(
    /Not offered online at the moment/i.test(payText),
    `Pay a bill says the utility's own switch is off: ${payText.replace(/\n/g, " ")}`,
  );
  // ⚠ VISIBLE IS NOT OPEN. The card is drawn and the door is shut — no link to
  // /pay from the card, and none in the top bar either (BR-CWP-002).
  check(
    (await guest.locator('[data-errand="pay_bill"] a').count()) === 0,
    "the disabled Pay a bill card links nowhere",
  );
  check((await guest.locator('[data-link="pay_bill"]').count()) === 0, "and no Pay a bill word in the nav");
  await guest.screenshot({ path: join(OUT, "4-quick-pay-off.png"), fullPage: true });
  await setSwitch(staff, '[data-switch="quick_pay_enabled"]', true);

  // ═════ 5 · self-read is the one switch off ══════════════════════════════
  console.log("\n── 5 · send your own reading is off, and the count says why ──");
  const selfRead = await staff
    .locator('[data-switch="self_read_enabled"] button[role="switch"]')
    .getAttribute("data-switch-state");
  check(selfRead === "off", "Send your own reading reads Off (R8)");
  check(
    (await staff.locator('[data-usage-reason="readings_off"]').count()) === 1,
    "usage says: Readings are off, so nothing is counted",
  );
  check((await staff.locator('[data-usage="requests_from_portal"]').count()) === 1, "requests from the portal is a real count");

  // ═════ 6 · Branding: read-only four, live preview, the strapline lands ══
  console.log("\n── 6 · branding: read-only shared four, the preview follows the keys ──");
  await staff.goto(`${SETTINGS}/branding`, { waitUntil: "networkidle" });
  await staff.waitForSelector('[data-screen="CWP-070"]', { timeout: 20000 });
  check((await staff.locator("[data-readonly]").count()) === 4, "logo, trading name, brand and accent are read-only");
  check((await staff.locator('[data-link="edit-in-company"]').count()) === 1, "with a link to Company → Profile");
  check(
    (await staff.locator("body").getAttribute("data-screen-id")) === "CWP-070",
    "the screen carries its id: CWP-070 on <body>",
  );
  const original = await staff.locator('[data-field="strapline"]').inputValue();
  const typed = "Pine Hill, on your phone — bills, readings, requests.";
  await staff.fill('[data-field="strapline"]', typed);
  const previewText = await staff.locator("[data-portal-preview]").innerText();
  check(previewText.includes(typed), "the preview updated as you typed");
  await staff.click('[data-action="save"]');
  await staff.waitForFunction(() => document.querySelector('[data-action="save"]')?.hasAttribute("disabled"), null, { timeout: 15000 });
  await staff.screenshot({ path: join(OUT, "6-branding.png"), fullPage: true });
  await guest.reload({ waitUntil: "networkidle" });
  await guest.waitForSelector("[data-errand]", { timeout: 20000 });
  check((await guest.locator("body").innerText()).includes(typed), "the strapline is under the utility's name on the portal");
  // put the fixture's sentence back so the next run starts where this one did
  await staff.fill('[data-field="strapline"]', original);
  await staff.click('[data-action="save"]');
  await staff.waitForFunction(() => document.querySelector('[data-action="save"]')?.hasAttribute("disabled"), null, { timeout: 15000 });

  // ═════ 7 · Oak Ridge carries nothing of Pine Hill ═══════════════════════
  console.log("\n── 7 · the other utility: its own words, its own colours ──");
  const oak = await context.newPage();
  await oak.goto(`${BASE}/${OTHER}/portal`, { waitUntil: "networkidle" });
  await oak.waitForSelector('[data-portal-frame="guest"]', { timeout: 20000 });
  const oakText = await oak.locator("body").innerText();
  const oakBrand = await oak.locator('[data-portal-frame="guest"]').evaluate((el) => getComputedStyle(el).getPropertyValue("--brand").trim());
  check(oakText.includes("Oak Ridge Water"), "Oak Ridge's name");
  check(oakText.includes("Clean water for the ridge"), "Oak Ridge's own strapline");
  check(oakBrand.toLowerCase() === "#0b6e4f", `Oak Ridge's own brand colour (${oakBrand})`);
  for (const s of ["Pine Hill", "#EC3013", "(512) 555-0100", "any time."]) {
    check(!oakText.includes(s) && !(await oak.content()).includes(s), `no Pine Hill string on Oak Ridge: "${s}"`);
  }
  await oak.screenshot({ path: join(OUT, "7-oak-ridge.png"), fullPage: true });

  // ═════ 9 · the utilities compiled ════════════════════════════════════════
  console.log("\n── 9 · computed style: the rules actually exist ──");
  const grid = await guest.locator("[data-errand]").first().evaluate((el) => {
    const card = getComputedStyle(el);
    const parent = getComputedStyle(el.parentElement);
    return { display: card.display, border: card.borderTopStyle, borderWidth: card.borderTopWidth, padding: card.paddingTop, bg: card.backgroundColor, grid: parent.display, cols: parent.gridTemplateColumns.split(" ").length };
  });
  check(grid.display === "flex", `an errand card is display:flex (got ${grid.display})`);
  check(grid.border === "solid" && grid.borderWidth === "1px", `a 1px solid rule around the card (${grid.borderWidth} ${grid.border})`);
  check(grid.padding === "16px", `p-4 compiled (padding ${grid.padding})`);
  check(grid.bg === "rgb(255, 255, 255)", `bg-[white] compiled (${grid.bg})`);
  check(grid.grid === "grid" && grid.cols === 3, `CardGrid3 is a three-column grid (${grid.cols} columns)`);
  const pineBrand = await guest.locator('[data-portal-frame="guest"]').evaluate((el) => getComputedStyle(el).getPropertyValue("--brand").trim());
  check(pineBrand.toLowerCase() === "#ec3013", `--brand is the tenant's own hex (${pineBrand})`);
  const staffPanel = await staff.locator('[data-screen="CWP-070"] section').first().evaluate((el) => getComputedStyle(el).borderTopWidth);
  check(staffPanel === "1px", `the staff panels' border compiled (${staffPanel})`);

  // ═════ 10 · nothing internal, no sideways scroll ═══════════════════════
  console.log("\n── 10 · nothing a person should not see ──");
  for (const [name, page] of [["portal", guest], ["branding", staff], ["oak ridge", oak]]) {
    const text = await page.locator("body").innerText();
    for (const pattern of FORBIDDEN) {
      const hit = text.match(pattern);
      check(hit === null, `no ${pattern} on ${name}${hit ? ` — found ${hit[0]}` : ""}`);
    }
    const sideways = await page.evaluate(SIDEWAYS);
    check(sideways === 0, `no sideways scroll on ${name} at ${VIEWPORT.width} (overflow ${sideways}px)`);
  }

  // ═════ 11 · measured, not asserted ═════════════════════════════════════
  console.log("\n── 11 · the guest front page's round trip, measured (OQ-CWP-1510 is OPEN) ──");
  const samples = [];
  for (let i = 0; i < 30; i += 1) {
    const t0 = performance.now();
    const r = await guest.request.get(`${BASE}/api/${TENANT}/portal/public/front`);
    samples.push(performance.now() - t0);
    if (r.status() !== 200) check(false, `sample ${i} answered ${r.status()}`);
  }
  samples.sort((a, b) => a - b);
  const pct = (p) => samples[Math.min(samples.length - 1, Math.floor((p / 100) * samples.length))].toFixed(0);
  console.log(
    `   GET /api/${TENANT}/portal/public/front ×30 through the SPA proxy on this box: ` +
      `min ${samples[0].toFixed(0)} ms · median ${pct(50)} ms · p95 ${pct(95)} ms · max ${samples[samples.length - 1].toFixed(0)} ms`,
  );
  console.log("   (a local single-box figure — recorded, not compared to a target; the target is OQ-CWP-1510, open)");

  await browser.close();
  console.log(`\nscreenshots: ${OUT}`);
  if (failures.length > 0) {
    console.log(`\n⛔ ${failures.length} failure(s)`);
    for (const f of failures) console.log(`   · ${f}`);
    process.exit(1);
  }
  console.log("\n✓ cr068 wave A: the portal switches on, and the front page tells the truth");
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
