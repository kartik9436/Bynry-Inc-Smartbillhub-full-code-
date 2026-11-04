// ── `DEF-MET-6913` — THE PREMISES DETAIL HEADER'S UTILITY-SERVICE CHIPS, ON A
//    SEEDED TENANT, IN A BROWSER ─────────────────────────────────────────────
//
// PO, 2026-09-27, from the live beta (v2.352.0, Ottumwa Water Works, premises
// `P-00079`): *"On the premises detail page the header should show the utility
// service chips; this premises has 4 utility services but they are not visible
// in the header."*
//
// ⛔ **NO GATE IN THIS REPOSITORY READS RENDERED OUTPUT (hard-won law 6), SO
// THIS FILE IS THE ONLY CHECK THAT CAN ANSWER THE PO'S ACTUAL QUESTION.** The
// jsdom cases (`PremisesHeaderChips.dom.test.tsx`) prove the header ASKS for
// the chips; only a browser proves a clerk opening PRM-02 SEES them, at the
// width they are actually working at.
//
// ⚠ **IT WALKS THREE PREMISES, AND THE SECOND AND THIRD ARE THE ONES THAT
// CATCH A WRONG FIX.** A header that drew an empty chip strip, or a stray
// separator, on a property with no services would satisfy the PO's own case
// and be wrong on the next property they open. So it asserts FOUR chips on the
// four-service property, ONE on the one-service property, and ZERO ELEMENTS —
// not zero words — on the property with none.
//
// ⚠ **`fire` IS ASSERTED BY NAME.** It is `CR-063`'s eleventh service, the
// front end types the service list out by hand in two places, and an eleventh
// service fails SILENTLY. The customer this was reported from has it.
//
// ⚠ **IT REFUSES A STALE BUILD**, the same guard every walkthrough here
// carries: a walk against an old bundle reports landed work as absent.
//
// ⚠ **IT WRITES NOTHING.** It only reads, so there is nothing to leave behind.
//
//   MET6913_BASE     default http://127.0.0.1:8952
//   MET6913_TENANT   default brazosbend
//   MET6913_EMAIL    default dana@brazosbendutilities.com
//   MET6913_PASSWORD default S3cure!passw0rd
//   MET6913_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
//   MET6913_FOUR / _ONE / _NONE   the three premise numbers to walk
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { statSync, readdirSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.env.MET6913_ROOT || process.cwd();
const BASE = process.env.MET6913_BASE || "http://127.0.0.1:8952";
const T = process.env.MET6913_TENANT || "brazosbend";
const EMAIL = process.env.MET6913_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MET6913_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.MET6913_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const SHOTS = process.env.MET6913_SHOTS || ".";
const TAG = process.env.MET6913_TAG || "after";

function newestMtime(dir) {
  let newest = 0;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (entry.name === "node_modules" || entry.name.startsWith(".")) continue;
    const path = join(dir, entry.name);
    const at = entry.isDirectory() ? newestMtime(path) : statSync(path).mtimeMs;
    if (at > newest) newest = at;
  }
  return newest;
}
const built = statSync(join(ROOT, "07-frontend/dist/index.html")).mtimeMs;
const newestFile = newestMtime(join(ROOT, "07-frontend/src"));
if (built < newestFile) {
  console.error(
    `REFUSED: dist/ was built ${new Date(built).toISOString()} but 07-frontend/src\n` +
      `has work at ${new Date(newestFile).toISOString()}. Run \`npx vite build\` first.`,
  );
  process.exit(2);
}
console.log(`dist built ${new Date(built).toISOString()} >= src ${new Date(newestFile).toISOString()}`);

// `P-00001` carries water + sewer + trash + fire, `P-00002` water alone and
// `P-00003` none. On `seed_demo`'s own brazosbend they carry two services each,
// so the three are overridable rather than assumed.
const FOUR = process.env.MET6913_FOUR || "P-00001";
const ONE = process.env.MET6913_ONE || "P-00002";
const NONE = process.env.MET6913_NONE || "P-00003";

const R = [];
const ok = (n, c, d = "") => { R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`); console.log(R.at(-1)); };

const b = await chromium.launch({ executablePath: CHROME });

/** The header's roll-up block only — chips are asserted THERE and nowhere else,
 *  because the same service words appear again in the Overview fact row below
 *  and a page-wide assertion would pass on the unfixed screen. */
const HEAD_CHIP = '.page-header-rollup [data-testid="service-chips"] [data-service]';

async function openPremise(p, no) {
  await p.goto(`${BASE}/${T}/premises?q=${no}`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1800);
  await p.locator("tbody tr a").first().click();
  await p.waitForTimeout(2500);
}

async function walk(width) {
  const p = await b.newPage({ viewport: { width, height: 1000 } });
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);

  await openPremise(p, FOUR);
  await p.screenshot({ path: join(SHOTS, `prm-chips-${TAG}-${width}-${FOUR}-four.png`) });
  const four = await p.locator(HEAD_CHIP).allTextContents();
  ok(`${width}px · ${FOUR} · four chips in the HEADER`, four.length === 4, four.join(" | "));
  const codes = await p.locator(HEAD_CHIP).evaluateAll((n) => n.map((e) => e.dataset.service));
  ok(`${width}px · ${FOUR} · and fire is one of them (CR-063's eleventh)`, codes.includes("fire"), codes.join(","));

  await openPremise(p, ONE);
  await p.screenshot({ path: join(SHOTS, `prm-chips-${TAG}-${width}-${ONE}-one.png`) });
  const one = await p.locator(HEAD_CHIP).count();
  ok(`${width}px · ${ONE} · one service draws exactly one chip`, one === 1, `count=${one}`);

  await openPremise(p, NONE);
  await p.screenshot({ path: join(SHOTS, `prm-chips-${TAG}-${width}-${NONE}-none.png`) });
  const none = await p.locator(HEAD_CHIP).count();
  const strip = await p.locator('.page-header-rollup [data-testid="service-chips"]').count();
  ok(`${width}px · ${NONE} · no services draws NO chip and NO empty strip`, none === 0 && strip === 0, `chips=${none} strips=${strip}`);

  await p.close();
}

await walk(1440);
await walk(1280);
await b.close();
console.log("\n" + R.join("\n"));
process.exit(R.some((line) => line.startsWith("FAIL")) ? 1 : 0);
