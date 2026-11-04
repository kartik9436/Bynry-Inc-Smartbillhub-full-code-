// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` · `P2.7` · `P2.9` — the six Counter screens
//           and the two doors onto them.
// Rules:    CLAUDE.md hard-won law 6 (diff the running app against the
//           drawing; no gate in this repo reads rendered output) · B14 rule 31
//           (no database id is the visible value of a field) · rule 42 (a
//           screen is built from the drawing AS AN IMAGE — so it is CHECKED
//           against one too)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THIS FOUND A DEFECT THAT EVERY OTHER CHECK PASSED OVER
// ══════════════════════════════════════════════════════════════════════════
// `tsc`, 26 unit cases, 9 tab cases and every gate were green over a Counter
// tab that told a supervisor **$0.00 was taken today** when the server had
// actually said *"nobody told me which day"* — `counter_list_totals` answers
// null without an `as_of` (`BR-TEN-043`) and the tile read `?? "0"`. That is
// `DEF-127`'s shape on a money screen, and it was visible the moment somebody
// looked at the picture.
//
// ⚠ **IT BOOTS NOTHING, ON PURPOSE.** `10-scripts/11-smoke-stack.sh` boots the
// stack and TEARS IT DOWN on exit, which is right for a smoke run and wrong
// for looking at one tab. Point this at an already-running SPA join:
//
//     cd 06-backend && python3 manage.py runserver 127.0.0.1:8111 --noreload &
//     cd 07-frontend && ./node_modules/.bin/vite build
//     PORT=8112 API_PROXY_TARGET=http://127.0.0.1:8111 node server.mjs &
//     PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers WEB=http://127.0.0.1:8112 \
//       node 10-scripts/cr136_p2_counter_screens_walkthrough.mjs
//
// ⚠ **RUN IT FROM ANYWHERE** — it borrows `playwright-core` from
// `07-frontend/node_modules` through `createRequire`, because a bare ESM
// specifier resolves from the SCRIPT's directory and not the CWD. And **never
// `playwright install`** in this container; `resolveChromium` below takes
// whatever revision is present and PRINTS the mismatch, exactly as
// `12-smoke-walkthrough.mjs` does.
//
// ⚠ **THERE IS A SECOND COUNTER WALK AND THEY DO DIFFERENT JOBS — RUN BOTH.**
// `10-scripts/p2head_counter_door_walkthrough.mjs` asks *do the DOORS point at
// the right address*, across every payments tab, the collections ladder and
// the modal. **This one asks *does the SCREEN look like the drawing*** — 3·1's
// title and column order, 3·3a's fields, B14 rule 31 over the rendered body,
// 1280 — and it PHOTOGRAPHS each one at 1440 so the shots can be read beside
// the blueprint page, which is the thing law 6 is actually about. Neither
// subsumes the other and neither should grow into the other.
//
// ⚠ **"COLUMN MISSING" ON AN EMPTY TENANT IS NOT A FINDING.** `DataTable`
// draws its empty state INSTEAD of the header row, so a tenant with no
// counters reports all seven. Seed a till first, or read the note beside the
// shot rather than the line.
import { mkdirSync, existsSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

// ⚠ **`playwright-core` IS BORROWED FROM `07-frontend`, NOT IMPORTED.** A bare
// specifier in an ESM module resolves from the MODULE's own directory, never
// the CWD — so `import "playwright-core"` from `10-scripts/` fails with
// `ERR_MODULE_NOT_FOUND` however you invoke it, and running from `07-frontend`
// only masks it for the one caller who remembers. `12-smoke-walkthrough.mjs`
// solved this first and this is its solution, not a second one.
const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

// The pinned revision is often absent here; take ANY installed chromium, the
// same way `10-scripts/12-smoke-walkthrough.mjs` does, and PRINT the mismatch.
// This is a look at a screen, not a pixel test — and `playwright install` is
// forbidden in this container.
function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) {
          console.log(`chromium: pinned revision missing; using ${candidate}`);
          return candidate;
        }
      }
    }
  }
  throw new Error("no chromium found");
}

const WEB = process.env.WEB || "http://127.0.0.1:8112";
const TENANT = process.env.SMOKE_TENANT || "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT || "/tmp/claude-0/counter-shots";
mkdirSync(OUT, { recursive: true });

const findings = [];
function note(step, what) {
  findings.push(`[${step}] ${what}`);
  console.log(`  · ${step}: ${what}`);
}

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
page.on("pageerror", (e) => note("console", `PAGE ERROR: ${e.message}`));

try {
  console.log("step 1 · sign in");
  await page.goto(`${WEB}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: 20000 });
  await page.screenshot({ path: `${OUT}/01-after-signin.png` });

  console.log("step 2 · the Counter tab — 3·1");
  await page.goto(`${WEB}/${TENANT}/payments/counter`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: `${OUT}/02-counters-3-1.png`, fullPage: true });
  const head = await page.textContent("h1").catch(() => null);
  note("3·1", `page title reads ${JSON.stringify(head)}`);
  const startHref = await page
    .getAttribute('a:has-text("Start counter")', "href")
    .catch(() => null);
  note("3·1", `Start counter href = ${JSON.stringify(startHref)}`);
  for (const column of ["Counter", "Person", "Opened", "Closed", "Payments", "Taken", "Counted"]) {
    const seen = await page.locator(`th:has-text("${column}")`).count();
    if (seen === 0) note("3·1", `COLUMN MISSING: ${column}`);
  }
  const bodyText = await page.textContent("body");
  if (/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(bodyText ?? "")) {
    note("3·1", "B14 RULE 31 BREACH: something uuid-shaped is on screen");
  }

  console.log("step 3 · 3·3a Start, opened by its address");
  await page.goto(`${WEB}/${TENANT}/payments/counter?start=1`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/03-start-3-3a.png`, fullPage: true });
  const dialogTitle = await page.textContent(".modal-card h2, .modal-card h3").catch(() => null);
  note("3·3a", `dialog heading reads ${JSON.stringify(dialogTitle)}`);

  console.log("step 4 · the slot on another payments tab — P2.7");
  await page.goto(`${WEB}/${TENANT}/payments/record`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/04-record-tab-head.png` });
  const slot = await page.getAttribute('a:has-text("Start counter")', "href").catch(() => null);
  note("P2.7", `slot on the Payments tab = ${JSON.stringify(slot)}`);

  console.log("step 5 · 1280, the laptop minimum");
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto(`${WEB}/${TENANT}/payments/counter`, { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${OUT}/05-counters-1280.png`, fullPage: true });
  const scrolls = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  note("1280", scrolls ? "THE PAGE SCROLLS SIDEWAYS" : "no horizontal page scroll");
} catch (error) {
  note("walk", `threw: ${error.message}`);
} finally {
  await browser.close();
}

console.log(`\nshots: ${OUT}`);
console.log(findings.length ? `\n${findings.length} note(s) above` : "\nnothing to report");
