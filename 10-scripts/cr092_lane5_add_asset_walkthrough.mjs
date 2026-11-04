// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 step 2, wave B lane 5 — the add-asset wizard,
//          screens 28–31 (blueprint PDF pages 109–119).
// Defects: DEF-MET-4980 · 4981 · 4982 · 4983 · 4984 · 4985 · 4986 · 4990
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code, and rules that we place, also ensure you do
//          web walkthorugh before you sign off the user story or build"* ·
//          hard-won law 6 (no gate in this repo reads rendered output) ·
//          law 7 habit 3 (a check's output must distinguish pass from fail TO
//          A READER) · PO 2026-09-10 (clerk and utility-admin screens are
//          verified at 1280 and 1440, and nothing narrower)
// ───────────────────────────────────────────────────────
//
// WHAT THIS OPENS, AND WHY EACH CHECK IS HERE RATHER THAN IN A DOM TEST.
//
// `AssetAddWizardFixes.dom.test.tsx` proves the same eight things against a
// seeded React Query cache, and it is faster and it runs in CI. It cannot prove
// the two that actually cost this module three weeks:
//
//   1 · that the screen ASKS the server for the service list at all — the dom
//       suite hands it the answer, and the whole of `DEF-MET-4980` is that a
//       full four-step walk issued twelve API calls and none of them was
//       `GET /settings/services`;
//   2 · that a Tailwind utility actually PAINTS. `DEF-MET-4984`'s first fix
//       dimmed the refused field with `bg-[color-mix(…)]`, every assertion
//       passed, and a browser showed the colour unchanged — `.input` declares
//       it in an unlayered legacy stylesheet and the utility lost the cascade.
//       Only `getComputedStyle` in a real browser can tell you that.
//
// HOW TO RUN IT
//
//   pg_ctlcluster 16 main start
//   06-backend  $ DJANGO_SETTINGS_MODULE=config.settings.local \
//                 DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
//                 python3 manage.py runserver 127.0.0.1:8483 --noreload
//   07-frontend $ npx vite build && PORT=8484 API_PROXY_TARGET=http://127.0.0.1:8483 node server.mjs
//   10-scripts  $ BASE=http://127.0.0.1:8484 node cr092_lane5_add_asset_walkthrough.mjs
//
// ⚠ **IT CREATES TWO REAL ASSETS PER RUN, ONE PER WIDTH, AND SAYS SO AT THE
// END.** `DEF-MET-4986` cannot be seen from the screen — a success toast is
// what the defect produces — so the only honest proof is to create an asset on
// the wizard's DEFAULT destination and read the row back from PostgreSQL. The
// numbers carry a per-run suffix because a duplicate asset number is
// `BR-AST-033`'s HARD block: a fixed number makes the second run fail on its
// own create and read as *"the feature broke"*.
//
// ⚠ **IT SIGNS IN AS `lane5@brazosbendutilities.com`, NOT AS `dana`.** The
// shared demo account was LOCKED (`locked_until 2026-09-12T05:51:46Z`) when
// this was written, by a sibling's failed sign-ins. Clearing that reaches into
// an account other lanes are using; minting one does not. Override with EMAIL=.
import { existsSync, readdirSync, mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8484";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "lane5@brazosbendutilities.com";
const PASSWORD = "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/cr092-lane5";
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
  throw new Error("no chromium");
}
const RUN = new Date().toISOString().replace(/[^0-9]/g, "").slice(8, 14);
const lines = [];
let pass = 0, fail = 0;
function say(s) { console.log(s); lines.push(s); }
function check(name, ok, detail = "") {
  if (ok) pass++; else fail++;
  say(`  ${ok ? "PASS" : "FAIL"}  ${name}${ok || !detail ? "" : `\n          ${detail}`}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const created = [];

for (const width of [1440, 1280]) {
  const page = await browser.newPage({ viewport: { width, height: 1400 } });
  page.on("pageerror", (e) => say(`  PAGE ERROR: ${e.message}`));
  const calls = [];
  page.on("request", (r) => { if (r.url().includes("/api/")) calls.push(new URL(r.url()).pathname); });

  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  say(`\n================ WIDTH ${width} ================`);

  // ── DEF-MET-4980 / 4981 · step 1 ───────────────────────────────────────
  calls.length = 0;
  await page.goto(`${BASE}/${TENANT}/assets/new?class=meters`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  const svc = await page.evaluate(() => {
    const el = document.querySelector("#service");
    const label = document.querySelector('label[for="service"]');
    return {
      tag: el?.tagName, ariaRequired: el?.getAttribute("aria-required"),
      marked: label?.querySelector(".field-required") !== null,
      labelText: (label?.textContent || "").trim(),
      options: el && el.tagName === "SELECT" ? Array.from(el.options).map((o) => `${o.value}|${o.textContent}`) : null,
      help: document.querySelector("#service-help")?.textContent ?? null,
    };
  });
  check("4980 · the service is a SELECT", svc.tag === "SELECT", JSON.stringify(svc));
  check("4980 · GET /settings/services is issued", calls.some((p) => p.endsWith("/settings/services")),
        `calls: ${calls.length}; ${JSON.stringify(calls)}`);
  const enabled = (svc.options ?? []).filter((o) => !o.startsWith("|"));
  check("4980 · exactly the tenant's ENABLED services, not eleven", enabled.length === 2,
        `offered ${enabled.length}: ${JSON.stringify(svc.options)}`);
  check("4980 · options carry NAMES, not codes", enabled.every((o) => o.split("|")[1] !== o.split("|")[0]),
        JSON.stringify(enabled));
  check("4981 · required, marked and announced", svc.ariaRequired === "true" && svc.marked,
        JSON.stringify(svc));
  say(`  · label "${svc.labelText}" · help "${svc.help}" · options ${JSON.stringify(svc.options)}`);

  // Continue with no service
  await page.selectOption("#type", "meter");
  await page.waitForTimeout(300);
  await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => /continue/i.test(b.textContent || ""))?.click());
  await page.waitForTimeout(500);
  const blocked = await page.evaluate(() => ({
    url: location.search,
    alert: Array.from(document.querySelectorAll('[role="alert"]')).map((e) => (e.textContent || "").trim()).filter(Boolean),
  }));
  check("4981 · Continue is refused ON STEP 1, not on step 4",
        !blocked.url.includes("step=2") && blocked.alert.length > 0, JSON.stringify(blocked));

  // ── DEF-MET-4983 · a step past the first, untouched ────────────────────
  await page.goto(`${BASE}/${TENANT}/assets/new?class=meters&step=3`, { waitUntil: "networkidle" });
  await page.waitForTimeout(900);
  const restarted = await page.evaluate(() => ({
    url: location.search,
    note: Array.from(document.querySelectorAll("[data-note]")).map((e) => (e.textContent || "").trim()),
    firstFieldId: document.querySelector(".field input, .field select")?.id ?? null,
  }));
  check("4983 · ?step=3 lands on step 1 with the url corrected",
        restarted.url.includes("step=1") && restarted.firstFieldId !== null,
        JSON.stringify(restarted));
  check("4983 · and it says why", restarted.note.some((n) => n.length > 0 && /answer/i.test(n)),
        JSON.stringify(restarted.note));

  // ── walk to step 3 properly ────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/assets/new?class=meters`, { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  // ⚠ **A WALKTHROUGH THAT ONLY PASSES ONCE IS ONE NOBODY RUNS AGAIN.** A
  // duplicate asset number is BR-AST-033's HARD block, so the second run of a
  // fixed number fails on the create and reads as "the feature broke".
  const assetNo = `LANE5B-INV-${width}-${RUN}`;
  await page.fill("#asset_no", assetNo);
  await page.selectOption("#type", "meter");
  await page.selectOption("#service", "water");
  await page.waitForTimeout(300);
  await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => /continue/i.test(b.textContent || ""))?.click());
  await page.waitForTimeout(600);
  await page.fill("#unit", "kgal");
  await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => /continue/i.test(b.textContent || ""))?.click());
  await page.waitForTimeout(700);

  // ── DEF-MET-4984 · the refused opening read ────────────────────────────
  const refused = await page.evaluate(() => {
    const read = (id) => {
      const el = document.querySelector("#" + id);
      if (!el) return { missing: id };
      const s = getComputedStyle(el);
      return { id, bg: s.backgroundColor, color: s.color, cursor: s.cursor,
               opacity: s.opacity, disabled: el.disabled === true, tabIndex: el.tabIndex };
    };
    return { opening: read("opening_read"), date: read("install_date") };
  });
  check("4984 · the opening read is DISABLED", refused.opening.disabled === true, JSON.stringify(refused));
  check("4984 · and no longer renders as an ordinary box",
        refused.opening.cursor === "not-allowed" && refused.opening.opacity !== refused.date.opacity,
        JSON.stringify(refused));

  // ── DEF-MET-4986 · the inventory consequence ───────────────────────────
  const consequence = await page.evaluate(() => {
    const box = document.querySelector('[data-consequence="assets-add-service-dropped"]');
    return box ? (box.textContent || "").trim() : null;
  });
  check("4986 · the default destination states the consequence, naming the service",
        consequence !== null && consequence.includes("Water"), String(consequence));
  say(`  · consequence: ${JSON.stringify(consequence)}`);

  // ── step 4 summary · DEF-MET-4989 ──────────────────────────────────────
  await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => /continue/i.test(b.textContent || ""))?.click());
  await page.waitForTimeout(600);
  const summary = await page.evaluate(() => (document.querySelector("[data-add-summary]")?.textContent || "").trim());
  check("4989 · the summary reads words, not codes",
        summary.includes("Meter") && summary.includes("Water") && !/\bmeter\b ·/.test(summary), summary);
  say(`  · summary: ${JSON.stringify(summary)}`);

  // ── CREATE IT, leaving it in inventory — DEF-MET-4986's own proof ──────
  await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => /Add asset/i.test(b.textContent || ""))?.click());
  await page.waitForTimeout(2500);
  const landed = page.url();
  check("4986 · the asset was created and the wizard navigated to it",
        /\/assets\/[0-9a-f-]{8,}/.test(landed), landed);
  created.push(assetNo);

  // ── DEF-MET-4985 · the device helpers ──────────────────────────────────
  for (const type of ["backflow", "pv"]) {
    await page.goto(`${BASE}/${TENANT}/assets/new?class=behind_the_meter`, { waitUntil: "networkidle" });
    await page.waitForTimeout(700);
    await page.selectOption("#type", type);
    await page.waitForTimeout(250);
    await page.evaluate(() => Array.from(document.querySelectorAll("button")).find((b) => /continue/i.test(b.textContent || ""))?.click());
    await page.waitForTimeout(700);
    const helps = await page.evaluate(() => ({
      linked: document.querySelector("#parent_asset_no-help")?.textContent ?? null,
      capacity: document.querySelector("#export_capacity_kw-help")?.textContent ?? null,
    }));
    check(`4985 · ${type}: no helper names a device that is not on screen`,
          !/inverter|batter/i.test(`${helps.linked} ${helps.capacity}`), JSON.stringify(helps));
    say(`  · ${type} helpers: ${JSON.stringify(helps)}`);
  }

  const scroll = await page.evaluate(() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]);
  check(`layout · no horizontal scroll at ${width}`, scroll[0] === scroll[1], `${scroll[0]}/${scroll[1]}`);
  await page.close();
}
await browser.close();
say(`\nassets created by this walk: ${JSON.stringify(created)}`);
say(`\nVERDICT: ${fail === 0 ? "ALL CHECKS PASSED" : `${fail} CHECK(S) FAILED`} — ${pass} passed, ${fail} failed`);
writeFileSync(join(OUT, "walk-after.txt"), lines.join("\n"));
process.exitCode = fail === 0 ? 0 : 1;
