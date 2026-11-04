/**
 * `CR-093-BRC01` item 4 / `DEF-SHL-4947` — THE PAGE-HEAD TITLE IS 32px.
 *
 * **B14 rule 40**, PO ruling 2026-09-12: *"use 32 pixels — for every ordinary
 * screen"*, confirmed *"Please use 32 pixels"*.
 *
 * ⚠ **WHY THIS IS A BROWSER PROBE AND NOT A `toContain("text-h2")` ASSERTION.**
 * A Tailwind utility is emitted ONLY for a file listed in
 * `07-frontend/src/styles/route-b-migrated.txt`. Write one in a file that is not
 * on that list and the class IS in the DOM, `tsc` passes, eslint passes, and
 * every `toContain` assertion passes — while the element renders as **nothing at
 * all**. The skill's §7.1 names this as the trap that costs most in this repo.
 * Only a computed style read against the BUILT stylesheet can tell a working
 * class from a class no stylesheet declares.
 *
 * ⚠ **IT READS `dist/`, SO IT MEASURES WHAT SHIPS.** Run `npx vite build` first
 * or it measures a stale stylesheet — it refuses when `dist/assets/*.css` is
 * missing rather than reporting a pass over nothing (law 7: a check must not be
 * structurally incapable of failing).
 *
 * Usage:
 *   node 10-scripts/render-checks/cr093-page-title-size.mjs
 *   node 10-scripts/render-checks/cr093-page-title-size.mjs --before   # RED proof
 *
 * `--before` renders the markup this component shipped until 2026-09-12 — a bare
 * `<h1>` — and MUST fail at 40px. That is law 7's red proof through the same
 * entry point the green run uses, rather than a different one.
 */
import pw from "/home/user/SMARTBillHub/07-frontend/node_modules/playwright-core/index.js";
import fs from "node:fs";
import path from "node:path";
const { chromium } = pw;

const DIST = "/home/user/SMARTBillHub/07-frontend/dist/assets";
const EXPECTED = "32px";
const BEFORE = process.argv.includes("--before");

if (!fs.existsSync(DIST)) {
  console.error(`REFUSING: ${DIST} does not exist — run \`npx vite build\` first.`);
  process.exit(2);
}
const sheets = fs.readdirSync(DIST).filter((f) => f.endsWith(".css")).map((f) => path.join(DIST, f));
if (!sheets.length) {
  console.error(`REFUSING: no built stylesheet in ${DIST} — run \`npx vite build\` first.`);
  process.exit(2);
}

// The two shapes PageHeader renders. The h2 branch is the ONE legitimate caller
// (`TemplateDetail`, drawn inside Settings, which already owns the document h1)
// — it must be the same SIZE at a different LEVEL, which is the whole point of
// setting the size on the element rather than inheriting it from the tag.
const CASES = BEFORE
  ? [{ what: "h1 as shipped BEFORE the fix", markup: "<h1>Assets</h1>" }]
  : [
      { what: "h1 — every ordinary screen", markup: '<h1 class="text-h2">Assets</h1>' },
      { what: "h2 — a head nested under another page's h1", markup: '<h2 class="text-h2">Assets</h2>' },
    ];

const css = sheets.map((f) => `<style>${fs.readFileSync(f, "utf8")}</style>`).join("");
let failures = 0;

const browser = await chromium.launch({
  executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
});
// Staff app: 1280 and 1440 are the two the skill's §6 makes mandatory. Below
// 1280 is deliberately unsupported and is NOT measured.
for (const width of [1280, 1440]) {
  for (const c of CASES) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.setContent(
      `${css}<div class="page-header"><div class="page-header-top">` +
        `<div class="page-header-id">${c.markup}</div></div></div>`,
    );
    const got = await page.evaluate(() => {
      const el = document.querySelector(".page-header-id h1, .page-header-id h2");
      if (!el) return null;
      const s = getComputedStyle(el);
      return { tag: el.tagName, size: s.fontSize, weight: s.fontWeight, lineHeight: s.lineHeight };
    });
    const ok = got && got.size === EXPECTED;
    if (!ok) failures += 1;
    console.log(
      `  ${ok ? "PASS" : "FAIL"}  ${width}px  ${c.what} → ` +
        (got ? `${got.tag} ${got.size} (weight ${got.weight}, line-height ${got.lineHeight})` : "ELEMENT NOT FOUND") +
        (ok ? "" : `  — expected ${EXPECTED}`),
    );
    await page.close();
  }
}
await browser.close();

if (BEFORE) {
  // The red proof inverts the verdict: the pre-fix markup MUST fail, and a run
  // where it passes means this check cannot fail and is worthless.
  if (failures === 0) {
    console.error("\nRED PROOF DID NOT GO RED — the pre-fix markup measured 32px, so this check cannot fail.");
    process.exit(1);
  }
  console.log(`\nRED PROOF OK: the pre-fix markup failed ${failures} of ${CASES.length * 2} measurement(s).`);
  process.exit(0);
}
console.log(
  failures === 0
    ? `\ncr093-page-title-size: every page head measures ${EXPECTED} at 1280 and 1440.`
    : `\ncr093-page-title-size: ${failures} measurement(s) not ${EXPECTED}.`,
);
process.exit(failures === 0 ? 0 : 1);
