// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-REP-7070 — the report editor, screen 2·2, walked in a browser
//          at 1440 and 1280 on the same report the Product Owner opened.
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code … ensure you do web walkthorugh before you
//          sign off"* · hard-won law 6 (no gate in this repo looks at rendered
//          output) · law 7 clause 3 (a check's output must distinguish pass
//          from fail to a READER)
// ───────────────────────────────────────────────────────
//
// ⚠ **IT PRINTS THE PANEL'S OWN TEXT, NOT A VERDICT.** The four things this
// lane changed are all things a person has to READ — an account box at the
// top, words instead of `posted_on`, a reason above the table instead of four
// screens below it, and `1 of 5` instead of `7 of 5`. So the script
// photographs the screen and prints the rail verbatim, and the reader compares
// `TAG=before` with `TAG=after`. A boolean here would be a claim about
// rendering that jsdom already makes and that neither of us can check.
//
// ⚠ **IT ALSO WALKS A REPORT THAT NEEDS NO PARAMETER** — the billing register
// — because the dangerous half of the account chooser is not whether it
// appears, it is whether it appears where nothing is required.
//
//   BASE=http://127.0.0.1:8391 TAG=before OUT=/tmp/rep-editor-a \
//     node 10-scripts/rep_editor_quick_pass_walkthrough.mjs
//
// ⚠ **SEVEN SECONDS, NOT TWO.** At 2.5s the statement editor photographs as a
// loading skeleton on this container and the panel is not in the DOM yet — a
// screenshot that proves nothing and reads exactly like a broken screen. The
// first run of this script produced four of them.
// Report editor quick pass — walked in a browser at 1440 and 1280.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");
const requireFrontend = createRequire(new URL("/home/user/SMARTBillHub/07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8391";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "/tmp/rep-editor-a";
const TAG = process.env.TAG ?? "before";
mkdirSync(OUT, { recursive: true });

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  for (const root of [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean)) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-linux/headless_shell"]) {
        const c = join(root, dir, sub);
        if (existsSync(c)) return c;
      }
    }
  }
  throw new Error("no chromium");
}
const browser = await chromium.launch({ executablePath: resolveChromium() });
const say = (...p) => console.log(...p);

async function signIn(width) {
  const page = await browser.newPage({ viewport: { width, height: 1000 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  return page;
}

for (const width of [1440, 1280]) {
  const page = await signIn(width);
  await page.goto(`${BASE}/${TENANT}/reports/statement?edit=1`, { waitUntil: "networkidle" });
  await page.waitForTimeout(7000);
  await page.screenshot({ path: `${OUT}/${TAG}-statement-edit-${width}.png`, fullPage: true });
  if (width === 1440) {
    const panelText = await page
      .$eval("[data-report-edit-panel]", (n) => n.innerText.replace(/\n+/g, " | "))
      .catch(() => "(no panel)");
    say(`[${TAG}] panel @${width}: ${panelText}`);
    const body = await page.$eval("body", (n) => n.innerText.replace(/\n+/g, " | "));
    say(`[${TAG}] body @${width}: ${body.slice(0, 2200)}`);
    const payload = await page.evaluate(async (t) => {
      const r = await fetch(`/api/${t}/reports/statement`, { headers: { Accept: "application/json" } });
      const j = await r.json().catch(() => ({}));
      return { status: r.status, keys: Object.keys(j), sample: JSON.stringify(j).slice(0, 1800) };
    }, TENANT);
    say(`[${TAG}] payload: ${JSON.stringify(payload)}`);
  }
  // a report that needs NO parameter — proves task 1 adds no step where none is needed
  await page.goto(`${BASE}/${TENANT}/reports/billing_register?edit=1`, { waitUntil: "networkidle" });
  await page.waitForTimeout(7000);
  await page.screenshot({ path: `${OUT}/${TAG}-register-edit-${width}.png`, fullPage: true });
  if (width === 1440) {
    const panelText = await page
      .$eval("[data-report-edit-panel]", (n) => n.innerText.replace(/\n+/g, " | "))
      .catch(() => "(no panel)");
    say(`[${TAG}] register panel @${width}: ${panelText}`);
  }
  await page.close();
}
await browser.close();
say(`shots in ${OUT}`);
