/**
 * ── Trace ──────────────────────────────────────────────
 * Change:  CR-110-BRC04 wave A — the connector SET-UP screen, S147 · INT-07,
 *          at `/:tenant/settings/connectors/:providerKey/configure`.
 * Rules:   CLAUDE.md hard-won law 6 (**no gate in this repo looks at rendered
 *          output**, so a green suite proves nothing about a screen) · law 2
 *          and its mirror (a live screen behind a dead control) · B14 rule 42
 *          (the screen is built from the drawing AS AN IMAGE, and this is how
 *          the built screen gets put back beside it) · BR-INT-037 (one
 *          component, 28 renderings).
 * ───────────────────────────────────────────────────────
 *
 * WHAT IT WALKS — FOUR CONNECTORS, ONE PER SHAPE
 * ══════════════════════════════════════════════════════════════════════════
 *   email_google        a vendor sign-in — the `redirect` field kind (CFG-02)
 *   erp_sap          a key WE issue them — `they_hold_ours` (CFG-10's panel)
 *   bank_lockbox_file   a file channel with a mapping editor (CFG-23)
 *   meters_neptune360   sixteen operations — the `…8 more` case (CFG-06)
 *
 * ⚠ **AND ONE THE PRODUCT HAS NEVER HEARD OF.** `BR-INT-037` says a 29th
 * connector costs no screen code, so the address for a vendor nobody has
 * written must still open the screen. A walkthrough that only opens connectors
 * we ship would pass equally well over 28 hand-written pages.
 *
 * ⚠ **IT ALSO ASSERTS WHAT IS **NOT** THERE, WHICH IS THE HALF A SCREENSHOT
 * CANNOT SHOW.** Five drawn things are deliberately unbuilt on PO rulings of
 * 2026-09-16 — the Token panel and the word *token*, the clock box, any editor
 * on the call limit, the usage count, and the card-page toggle. **An absence is
 * invisible to every check this repo has**, so each one is a named assertion
 * here rather than a sentence in a report nobody re-runs.
 *
 * HOW TO RUN IT
 *     (cd 07-frontend && npx vite build)
 *     PORT=8118 API_PROXY_TARGET=http://127.0.0.1:8099 node 07-frontend/server.mjs &
 *     BASE=http://127.0.0.1:8118 node 10-scripts/cr110_connector_setup_walkthrough.mjs
 */
import { createRequire } from "node:module";
import { mkdirSync } from "node:fs";

const require = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = require("playwright");

const BASE = process.env.BASE ?? "http://127.0.0.1:8118";
const TENANT = process.env.WT_TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const CHROME = process.env.PW_CHROME ?? "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.SHOTS ?? "/tmp/cr110-shots";

mkdirSync(SHOTS, { recursive: true });

const browser = await chromium.launch({ executablePath: CHROME, args: ["--no-sandbox"] });
// 1440 is B14's design target for a staff screen; a clerk is on a laptop.
const page = await browser.newPage({ viewport: { width: 1440, height: 1600 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 200)));
page.on("response", (r) => {
  if (r.status() >= 400 && r.url().includes("/api/")) errors.push(`${r.status()} ${r.url()}`);
});

let failed = 0;
function say(label, ok, detail = "") {
  console.log(`${ok ? "  ✓" : "  ✗"} ${label}${detail ? " — " + detail : ""}`);
  if (!ok) failed += 1;
}

await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await page.click('button[type="submit"]');
await page.waitForTimeout(2500);
console.log(`signed in at ${page.url()}\n`);

async function setUp(key) {
  await page.goto(`${BASE}/${TENANT}/settings/connectors/${key}/configure`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `${SHOTS}/${key}.png`, fullPage: true });
  return page.locator("body").innerText();
}

const SHAPES = [
  ["email_google", "a vendor sign-in (CFG-02)"],
  ["erp_sap", "a key we issue them (CFG-10)"],
  ["bank_lockbox_file", "a file channel with a mapping editor (CFG-23)"],
  ["meters_neptune360", "sixteen operations, the …8 more case (CFG-06)"],
];

for (const [key, shape] of SHAPES) {
  console.log(`${key} — ${shape}`);
  const body = await setUp(key);

  // THE ADDRESS OPENS SOMETHING. This is the whole wave in one line.
  say("the address opens a screen, not *not built yet*", !/not built yet/i.test(body));
  say(
    "the screen is S147 and it is bound to THIS connector",
    (await page.locator('[data-screen="S147"]').count()) === 1 &&
      (await page.locator(`[data-provider="${key}"]`).count()) === 1,
  );

  // THE DRAWN FRAME — back link, kicker, title, the two panels, the footer.
  say("the back link reads Connectors", /←\s*Connectors/.test(body));
  say("the API panel is drawn", /API[s]? on this connector/.test(body));
  say(
    "the API table carries all five drawn columns, the clipped Test one included",
    /API · Endpoint/i.test(body) &&
      /Direction/i.test(body) &&
      /When/i.test(body) &&
      /Rate limit/i.test(body) &&
      /\bTest\b/i.test(body),
  );
  say("the environment control offers both rows", /Production/.test(body) && /Sandbox/.test(body));
  say("the footer commits and cancels", /Save and test/.test(body) && /Cancel/.test(body));

  // ⚠ THE ACCENT PANEL — the PO's own ruling, *"i want you to use panel with
  // acsent - where ever shown it that way"*. Asserted as a COMPUTED border
  // rather than a class name, because a class in the DOM proves nothing about
  // what the browser painted (`DEF-SHL-5088`: a utility the theme does not
  // define compiles to nothing and `toContain` still passes).
  const accentTop = await page
    .locator('[data-panel]')
    .first()
    .evaluate((el) => getComputedStyle(el).borderTopWidth);
  say("the first panel carries the accent rule the drawing shows", accentTop === "2px", accentTop);

  // ══ THE ABSENCES — each one a PO ruling of 2026-09-16 ══════════════════
  say('the word "token" is nowhere on the screen', !/token/i.test(body));
  say("there is no Token address field", !/Token address/i.test(body));
  say("there is no clock box", !/Your time zone/i.test(body) && !/When it runs/i.test(body));
  say("nothing offers to re-authorise or renew", !/Re-authorise/i.test(body) && !/Renew/i.test(body));
  say("the card-page choice is absent", !/hosted by them/i.test(body) && !/embedded/i.test(body));
  say("the usage count is not drawn", !/Calls used/i.test(body));
  // The limit is a VALUE IN A CELL. No input may exist for it anywhere.
  say(
    "the call limit has no editor",
    (await page.locator('input[name*="rate" i], input[name*="limit" i]').count()) === 0,
  );
  // B14 rule 32 — no rule id or internal code in clerk-facing copy.
  say("no rule id reaches the clerk", !/\bCR-\d|\bRAN-\d|\bBR-[A-Z]{3}-/.test(body));

  console.log("");
}

// ⚠ THE SHAPE-SPECIFIC HALVES, so a pass above is not four renderings of the
// same empty frame.
console.log("the four shapes actually differ, which is what BR-INT-037 claims");
let body = await setUp("erp_sap");
say("the key-issuing connector draws the key panel", /key for them to use/i.test(body));
say("…and calls it a key, never a token", /Generate a key/i.test(body));

body = await setUp("email_google");
say("the sign-in connector draws no key panel", !/key for them to use/i.test(body));
// ⚠ THE PROMISE AND THE CONTROL THAT KEEPS IT, ASSERTED TOGETHER. The screen
// says *"you will be sent to Google Workspace and brought back here"*; if no
// button can send you, that sentence is a lie every check passes over
// (`DEF-INT-5494`). A redirect connector has NO Save at all — the round trip
// IS the save — so this button is its whole commit path.
say("it promises to send the clerk to the vendor", /brought back here/i.test(body));
const signIn = page.locator("[data-sign-in]");
say("…and a real button exists to do it", (await signIn.count()) === 1);
say("…which is enabled, not a dead control", (await signIn.count()) === 1 && (await signIn.isEnabled()));

body = await setUp("meters_neptune360");
const rows = await page.locator("[data-operation]").count();
say("the sixteen-operation connector shows eight and offers the rest", rows === 8, `${rows} rows`);
say("…behind a *…N more* control", /…8 more/.test(body));

body = await setUp("bank_lockbox_file");
say(
  "the file channel draws its mapping editor",
  (await page.locator('[data-kind="mapping_editor"]').count()) > 0,
);

// ⚠ THE 29TH CONNECTOR — the address for a vendor nobody has written.
console.log("\nBR-INT-037 · a connector the product has never heard of");
body = await setUp("a_vendor_nobody_has_written_yet");
say("the address still opens the screen", !/not built yet/i.test(body));
say("and the screen says so plainly", /No connector with that name/i.test(body));

console.log(`\nconsole errors / failed API calls: ${errors.length}`);
for (const e of errors.slice(0, 8)) console.log("   " + e);
console.log(`screenshots in ${SHOTS}`);
console.log(failed === 0 ? "\nALL CHECKS PASSED" : `\n${failed} CHECK(S) FAILED`);
await browser.close();
process.exit(failed === 0 ? 0 : 1);
