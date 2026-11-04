// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-28 — *"the report editor — panel or its own page
//          - own page"*. Screen 2·2 at `/{tenant}/reports/{key}/edit`.
// Defects: DEF-REP-7080 (13 stacked filter rows) · DEF-REP-7073 (a control
//          closed the editor) · DEF-REP-7072 (columnChoices)
// Rules:   PO definition of done, verbatim: *"everything should be executed
//          based on actual code … ensure you do web walkthorugh before you
//          sign off"* · hard-won law 6 (no gate in this repo looks at rendered
//          output) · law 7 clause 3 (a check's output must distinguish pass
//          from fail to a READER)
// ───────────────────────────────────────────────────────
//
// ⚠ **IT PRINTS NUMBERS AND THE SCREEN'S OWN TEXT, NOT A VERDICT.** Every
// claim this lane makes is a thing a person has to READ — how many filter rows
// there are, how many preview rows, how many column headings, and what address
// the browser is standing at after a control is pressed. So the script
// photographs the screen and prints the counts, and the reader compares them
// with the drawing.
//
// ⚠ **IT PRESSES A CONTROL AND THEN ASKS FOR THE URL.** `DEF-REP-7073` was a
// screen that closed itself, and a screenshot taken before the keystroke
// cannot see that. The URL after the press is the whole check.
//
//   BASE=http://127.0.0.1:8412 OUT=scratchpad/po-shots/rep-editor-page \
//     node 10-scripts/rep_editor_page_walkthrough.mjs
//
// ⚠ **SEVEN SECONDS, NOT TWO.** At 2.5s the statement editor photographs as a
// loading skeleton on this container and the sections are not in the DOM yet —
// a screenshot that proves nothing and reads exactly like a broken screen.
const { existsSync, readdirSync, mkdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");
const requireFrontend = createRequire(
  new URL("/home/user/SMARTBillHub/07-frontend/package.json", import.meta.url),
);
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8412";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const OUT = process.env.OUT ?? "scratchpad/po-shots/rep-editor-page";
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
  const page = await browser.newPage({ viewport: { width, height: 1100 } });
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 });
  return page;
}

async function measure(page, label) {
  const counts = await page.evaluate(() => ({
    filterRows: document.querySelectorAll("[data-report-filter]").length,
    addFilter: document.querySelectorAll('[data-report-edit-panel] select').length,
    sampleHeads: document.querySelectorAll("[data-report-sample] thead th").length,
    sampleRows: document.querySelectorAll("[data-report-sample] tbody tr").length,
    shapeHeads: document.querySelectorAll("[data-report-shape] thead th").length,
    attrBoxes: document.querySelectorAll('[data-report-edit-panel] input[type="checkbox"]').length,
    variant: document.querySelector("[data-report-edit-panel]")?.getAttribute("data-report-edit-variant") ?? "(none)",
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));
  say(`[${label}] ${JSON.stringify(counts)}`);
  return counts;
}

for (const width of [1440, 1280]) {
  const page = await signIn(width);

  // ── the door, from where a person would actually click ────────────────────
  await page.goto(`${BASE}/${TENANT}/reports/billing-register`, { waitUntil: "networkidle" });
  await page.waitForTimeout(5000);
  await page.click('button:has-text("Edit")');
  await page.waitForTimeout(7000);
  say(`[door @${width}] url after Edit: ${new URL(page.url()).pathname}`);
  await page.screenshot({ path: `${OUT}/register-editor-${width}.png`, fullPage: true });
  await measure(page, `register @${width}`);
  if (width === 1440) {
    const sections = await page
      .$eval("[data-report-edit-panel]", (n) => n.innerText.replace(/\n+/g, " | "))
      .catch(() => "(no sections)");
    say(`[register @${width}] sections: ${sections}`);
  }

  // ── DEF-REP-7073 · press a control, then ask for the address ──────────────
  const before = new URL(page.url()).pathname;
  const box = await page.$('[data-report-edit-panel] input[type="checkbox"]');
  if (box) await box.click();
  await page.waitForTimeout(4000);
  const after = new URL(page.url()).pathname;
  say(`[7073 @${width}] before=${before} after=${after} still-the-editor=${before === after}`);
  await page.screenshot({ path: `${OUT}/register-after-tick-${width}.png`, fullPage: true });
  await measure(page, `after tick @${width}`);

  // ── DEF-REP-7080 · add a filter, then remove it ───────────────────────────
  const add = await page.$('[data-report-edit-panel] select[aria-label="Add filter"]');
  if (add) {
    const options = await page.$$eval(
      '[data-report-edit-panel] select[aria-label="Add filter"] option',
      (os) => os.map((o) => o.value).filter((v) => v !== ""),
    );
    say(`[7080 @${width}] offered: ${options.length} — ${options.join(", ")}`);
    if (options.length > 0) {
      await add.selectOption(options[0]);
      await page.waitForTimeout(2500);
      await measure(page, `after add filter @${width}`);
      await page.screenshot({ path: `${OUT}/register-filter-added-${width}.png`, fullPage: true });
    }
  } else {
    say(`[7080 @${width}] NO + Add filter control found`);
  }

  // ── THE WHOLE POINT: a report that HAS rows, so the preview is live ───────
  // ⚠ **THE BILLING REGISTER'S DEFAULT WINDOW IS EMPTY ON THIS SEED**, so the
  // first run of this script photographed four SHAPE previews and proved
  // nothing about the thing the page exists for. The AR ageing is a position
  // at a date and answers 26 rows with no window at all.
  await page.goto(`${BASE}/${TENANT}/reports/ar-aging/edit`, { waitUntil: "networkidle" });
  await page.waitForTimeout(7000);
  await page.screenshot({ path: `${OUT}/ageing-editor-${width}.png`, fullPage: true });
  const live = await measure(page, `ageing @${width}`);
  say(
    `[preview @${width}] live rows drawn=${live.sampleRows} (the report serves 26) ` +
      `headings=${live.sampleHeads} shape-instead=${live.shapeHeads}`,
  );
  if (width === 1440) {
    const sample = await page
      .$eval("[data-report-sample]", (n) => n.innerText.replace(/\n+/g, " | "))
      .catch(() => "(no live preview)");
    say(`[preview @${width}] ${sample}`);
    // ⚠ **THE PREVIEW MUST STILL BE IN VIEW WHEN THE SECTIONS ARE SCROLLED.**
    // That is the one respect in which the page beats the panel, and a
    // screenshot of the top of the page cannot show it.
    await page.evaluate(() => window.scrollTo(0, 900));
    await page.waitForTimeout(1200);
    const inView = await page.evaluate(() => {
      const el = document.querySelector("[data-report-sample]");
      if (el === null) return "(none)";
      const r = el.getBoundingClientRect();
      return `top=${Math.round(r.top)} bottom=${Math.round(r.bottom)} viewport=${window.innerHeight}`;
    });
    say(`[sticky @${width}] after scrolling 900px the preview sits at ${inView}`);
    await page.screenshot({ path: `${OUT}/ageing-scrolled-${width}.png` });
    await page.evaluate(() => window.scrollTo(0, 0));
  }

  // ── the statement: columnChoices, and the required-record chooser ─────────
  await page.goto(`${BASE}/${TENANT}/reports/statement/edit`, { waitUntil: "networkidle" });
  await page.waitForTimeout(7000);
  await page.screenshot({ path: `${OUT}/statement-editor-${width}.png`, fullPage: true });
  await measure(page, `statement @${width}`);
  if (width === 1440) {
    const sections = await page
      .$eval("[data-report-edit-panel]", (n) => n.innerText.replace(/\n+/g, " | "))
      .catch(() => "(no sections)");
    say(`[statement @${width}] sections: ${sections}`);
  }

  // ── the retired address still answers ─────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/reports/billing-register?edit=1`, { waitUntil: "networkidle" });
  await page.waitForTimeout(5000);
  say(`[legacy @${width}] ?edit=1 landed on ${new URL(page.url()).pathname}${new URL(page.url()).search}`);

  await page.close();
}
await browser.close();
