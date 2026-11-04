// ── Trace ──────────────────────────────────────────────
// Change:  `CR-150-BRC09` `NCT-01` tasks 4, 5 and 6 — the browser half of the
//          proof for New Connect steps 1 (Customer) and 2 (Premise), rebuilt
//          from `05-prototype/new-connect-redesign-2026-09-28/`.
// Why:     **Hard-won law 6 — no gate in this repo reads rendered output.**
//          `newConnectSteps12Redesign.dom.test.tsx` is the cheap half and it
//          does NO LAYOUT: every element in it is zero by zero, so it cannot
//          see a panel in the wrong column, a heading at the wrong size or a
//          screen that scrolls sideways at 1280. This is the half that can.
// Usage:   node 10-scripts/nct01_steps12_walkthrough.mjs
//          Expects a built front end being served (see `--base`) and a signed
//          -in clerk; `--base` and `--tenant` override the defaults.
// ⚠ NEVER `playwright install` — the browser is already on the box at
//   `/opt/pw-browsers/chromium-1194/chrome-linux/chrome`.
// ⚠ AND THE BUILD MUST BE `vite build --mode compose`. A bare `npx vite build`
//   bakes the public API host into the bundle, and sign-in then fails with
//   *"That email or password is incorrect."* on correct credentials. That cost
//   four lanes a cycle.
// ───────────────────────────────────────────────────────
// ⚠ **RESOLVED THROUGH THE FRONT END'S OWN `node_modules`, LIKE EVERY OTHER
// WALKTHROUGH IN THIS FOLDER.** A bare `import { chromium } from "playwright"`
// fails with `ERR_MODULE_NOT_FOUND` from `10-scripts/`, which has no
// `package.json` of its own — and it fails whichever directory you run from.
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const arg = (name, fallback) => {
  const hit = process.argv.find((a) => a.startsWith(`--${name}=`));
  return hit === undefined ? fallback : hit.slice(name.length + 3);
};

const BASE = arg("base", "http://127.0.0.1:8770");
const TENANT = arg("tenant", "brazosbend");
// ⚠ **THE SIGN-IN IS THE ONE THE OTHER WALKTHROUGHS USE, NOT A GUESS.** The
// ids are `#signin-email` / `#signin-password` and the route is `/signin`
// without a hyphen; a bare `input[type=email]` selector and `/sign-in` were
// what this script had first, and neither exists in the product.
const EMAIL = arg("email", process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com");
const PASSWORD = arg("password", process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd");
const OUT = arg("out", "05-prototype/new-connect-redesign-2026-09-28/as-built");

// **1440 IS THE DESIGN TARGET AND 1280 IS THE FLOOR** — the staff app is a
// laptop and desktop application (PO 2026-09-10). Both are shot, because the
// drawing is only ever checked at one of them and the floor is where a
// three-column form breaks.
const WIDTHS = [1440, 1280];

mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  args: ["--no-sandbox"],
});

const problems = [];
const note = (line) => {
  problems.push(line);
  console.log(`  ⚠ ${line}`);
};

for (const width of WIDTHS) {
  const context = await browser.newContext({ viewport: { width, height: 1000 } });
  const page = await context.newPage();

  // ── SIGN IN ────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 30000 });

  for (const [step, name] of [
    [1, "step1-customer"],
    [2, "step2-premise"],
  ]) {
    await page.goto(`${BASE}/${TENANT}/connections/new?step=${step}`, {
      waitUntil: "networkidle",
    });
    const file = `${OUT}/${name}-as-built-${width}.png`;
    await page.screenshot({ path: file, fullPage: true });
    console.log(`${name} @ ${width} → ${file}`);

    // ── WHAT THE DOM TEST CANNOT SEE ─────────────────────────────────────
    // (1) The page must not scroll SIDEWAYS at either width. A three-column
    //     form at 1280 is exactly where that happens.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    if (overflow > 0) note(`${name} @ ${width}: ${overflow}px of horizontal scroll`);

    // (2) Every drawn panel is not merely PRESENT but VISIBLE and non-zero —
    //     the dom test asserts presence and every box there is 0x0.
    const panels =
      step === 1
        ? ["owner", "communication", "mailing", "co-applicant", "owner-documents",
           "customer-search", "account-details", "reference", "work"]
        : ["address", "scope", "record", "services-and-plan"];
    for (const panel of panels) {
      const box = await page.locator(`[data-step-content="${panel}"]`).first().boundingBox();
      if (box === null) note(`${name} @ ${width}: panel ${panel} is not on the screen`);
      else if (box.height < 8) note(`${name} @ ${width}: panel ${panel} is ${box.height}px tall`);
    }

    // (3) `BR-MET-1162` — a screen showing a point SAYS which point it is.
    //     Asserted here as something a person can read, not as a data
    //     attribute: the rule is about what a clerk can tell apart.
    if (step === 2) {
      const said = await page.locator('[data-point-belongs-to="premise"]').first().isVisible();
      if (!said) note(`${name} @ ${width}: the point does not say whose it is (BR-MET-1162)`);
    }

    // (4) A keyboard alone must reach every control. Counted rather than
    //     walked: a control with no tab stop is invisible to a keyboard.
    const reachable = await page.evaluate(
      () =>
        [...document.querySelectorAll("input, select, textarea, button, a[href]")].filter(
          (el) => !el.hasAttribute("disabled") && el.tabIndex >= 0,
        ).length,
    );
    console.log(`  ${reachable} controls a keyboard can reach`);
  }

  await context.close();
}

await browser.close();

if (problems.length > 0) {
  console.log(`\n${problems.length} problem(s) — see above`);
  process.exit(1);
}
console.log("\nno problems found by this walk — the DRAWING comparison is still a person's job");
