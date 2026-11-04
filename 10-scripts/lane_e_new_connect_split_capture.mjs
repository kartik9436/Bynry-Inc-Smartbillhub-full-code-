// ── Trace ──────────────────────────────────────────────
// Change:  Lane E wave 1 — `NewConnectWizard.tsx` split into one file per step.
// Rules:   CLAUDE.md hard-won law 6 (no gate in this repo looks at rendered
//          output, so a browser is the ONLY thing that can see a broken move) ·
//          law 7 (a check's output must distinguish pass from fail to a READER)
// ───────────────────────────────────────────────────────
//
// WHAT THIS PROVES, AND WHY IT IS SHAPED LIKE THIS.
//
// A pure move is proved by showing NOTHING CHANGED, which no assertion about
// what a screen contains can do — an assertion only pins what its author
// thought to name, and the whole risk of a file split is the thing nobody
// thought to name. So this captures the wizard's rendered DOM for **all eight
// steps at both staff widths**, twice over (an EMPTY draft and the drawn
// 26-unit build, because half the conditional branches only render on one of
// them), and writes it to a file. Run it against the build BEFORE the split and
// again AFTER, then `diff` the two: an identical dump is the proof, and any
// line of difference names the step that broke.
//
// ⚠ THE FILLED PASS CLICKS THROUGH AND NEVER RELOADS. `?step=` is URL state
// (A9) and the ANSWERS are component state — a reload keeps the place and
// empties the draft — so navigating by URL between steps would capture the
// empty screen every time and the filled pass would silently prove nothing.
const { mkdirSync, writeFileSync, existsSync, readdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8098";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/laneE";
const TAG = process.env.TAG ?? "capture";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  throw new Error("no chromium found");
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1280, height: 1200 } });
const lines = [];
const say = (s) => { console.log(s); lines.push(s); };

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });

const SCREEN = '[data-screen="S87"]';
const RAIL = "[data-wizard-step]";

/** The wizard's whole rendered subtree, with the volatile bits neutralised so a
 *  diff reports a MOVE defect and never a clock or a React id. */
async function dump() {
  await page.waitForSelector(SCREEN, { timeout: 20000 });
  return page.evaluate((sel) => {
    const root = document.querySelector(sel);
    return root.outerHTML
      .replace(/\sid="(:r[^"]*:)"/g, ' id="[react]"')
      .replace(/\sfor="(:r[^"]*:)"/g, ' for="[react]"')
      .replace(/aria-(labelledby|describedby|controls)="[^"]*:r[^"]*"/g, 'aria-$1="[react]"');
  }, SCREEN);
}

async function rail() {
  return page.evaluate((sel) => {
    const cell = document.querySelector(sel);
    const r = cell.parentElement;
    const cells = [...r.querySelectorAll("[data-wizard-step]")];
    const last = cells[cells.length - 1];
    return `${cells.length} cells · scrollWidth ${r.scrollWidth} · clientWidth ${r.clientWidth} ` +
      `· overflow ${r.scrollWidth - r.clientWidth}px · last "${last.innerText.replace(/\s+/g," ").trim()}" ` +
      `hangs ${Math.max(0, Math.round(last.getBoundingClientRect().right - r.getBoundingClientRect().right))}px outside`;
  }, RAIL);
}

// ══════════════════════════════════════════════════════════════════════════
// PASS 1 · THE EMPTY DRAFT — every step reached by URL, both widths
// ══════════════════════════════════════════════════════════════════════════
for (const width of [1280, 1440]) {
  await page.setViewportSize({ width, height: 1200 });
  for (let n = 1; n <= 8; n += 1) {
    await page.goto(`${BASE}/${TENANT}/connections/new?step=${n}`, { waitUntil: "networkidle" });
    say(`### EMPTY @${width} step ${n} · rail: ${await rail()}`);
    say(await dump());
  }
}

// ══════════════════════════════════════════════════════════════════════════
// PASS 2 · THE DRAWN BUILD — 500 Main Street, Apt 101–125 plus the common area.
// Clicked through without a reload, so the answers survive step to step.
// ══════════════════════════════════════════════════════════════════════════
// The forward control is the LAST button of the action row — targeted
// structurally rather than by its word, because a step may declare its own
// forward label (`WizardStep.continueLabel`) and a text match would then miss.
async function continueOn() {
  const buttons = await page.$$('[data-wizard="actions"] button');
  await buttons[buttons.length - 1].click();
  await page.waitForTimeout(400);
}
for (const width of [1280, 1440]) {
  await page.setViewportSize({ width, height: 1200 });
  await page.goto(`${BASE}/${TENANT}/connections/new?step=1`, { waitUntil: "networkidle" });

  await page.selectOption("#nc_owner_kind", "builder_developer");
  await page.fill("#nc_owner_name", "Brazos Bend Homes LLC");
  await page.selectOption("#nc_owner_subcategory", "permanent");
  await page.fill("#nc_owner_email", "build@example.test");
  await page.fill("#nc_owner_phone", "555-0100");
  await page.fill("#nc_prefix", "Apt");
  await page.fill("#nc_external_ref", "LEGACY-7788");
  say(`### FILLED @${width} step 1 · rail: ${await rail()}`);
  say(await dump());
  await continueOn();

  await page.fill("#nc_address", "500 Main Street");
  // ⚠ **PICK BY POSITION, NEVER BY CODE.** This read `multi_unit` until
  // 2026-09-16 and hung the moment `PREMISE_TYPES` became the seeded six
  // (`BR-MET-034`): `selectOption` waits 30s for a value that no longer
  // exists and the run dies at step 2 with a TimeoutError. The list is a
  // TENANT's, so no literal in this file can be safe — take whatever the
  // second option is, which is a choice a person could make on any tenant.
  await page.selectOption("#nc_premise_type", { index: 1 });
  await page.fill("#nc_parcel", "PARCEL-42");
  await page.fill("#nc_route", "R-07");
  say(`### FILLED @${width} step 2 · rail: ${await rail()}`);
  say(await dump());
  await continueOn();

  await page.fill("#nc_from", "101");
  await page.fill("#nc_to", "125");
  await page.waitForTimeout(150);
  say(`### FILLED @${width} step 3 · rail: ${await rail()}`);
  say(await dump());
  await continueOn();

  // ⚠ `CheckboxField` renders its `<input>` `sr-only`, so `page.check()` waits
  // forever on a control that is deliberately invisible. The LABEL is what a
  // person clicks, so it is what this clicks.
  const tick = (id) => page.click(`label[for="${id}"]`);
  for (const code of ["electric", "water", "sewer", "trash", "storm_water"]) {
    await tick(`nc_premise_services_${code}`);
  }
  await page.waitForTimeout(200);
  for (const code of ["electric", "water", "sewer"]) {
    await tick(`nc_unit_services_${code}`);
  }
  for (const code of ["trash", "storm_water"]) {
    await tick(`nc_common_services_${code}`);
  }
  await page.waitForTimeout(250);
  say(`### FILLED @${width} step 4 · rail: ${await rail()}`);
  say(await dump());
  await continueOn();

  say(`### FILLED @${width} step 5 · rail: ${await rail()}`);
  say(await dump());
  await continueOn();

  say(`### FILLED @${width} step 6 · rail: ${await rail()}`);
  say(await dump());
  await continueOn();

  say(`### FILLED @${width} step 7 · rail: ${await rail()}`);
  say(await dump());
  await continueOn();

  say(`### FILLED @${width} step 8 · rail: ${await rail()}`);
  say(await dump());
}

writeFileSync(`${OUT}/${TAG}.html`, lines.join("\n") + "\n");
console.log(`\nWROTE ${OUT}/${TAG}.html — ${lines.length} blocks`);
await browser.close();
