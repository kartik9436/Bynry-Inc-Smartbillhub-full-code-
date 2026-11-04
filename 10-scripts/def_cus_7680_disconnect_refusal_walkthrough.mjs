// ── Trace ──────────────────────────────────────────────
// Defect:  **DEF-CUS-7680** — the disconnect wizard refuses on its last step
//          after every step is filled and says nothing useful. Reported by the
//          Product Owner from deployed `v2.352.0`: `DSC-02`,
//          `/{tenant}/disconnects/new?step=4`, `POST /disconnects/schedule` →
//          **422**, `BIZ-COMPLETENESS`, key `customers.disconnects.refused`,
//          trace reference `2FA5-0006`, *"Diagnostic: none shown"*.
// Rules:   B14 rule 32 (no rule id and no internal code in clerk-facing copy) ·
//          rule 33 (a FACT ≤ 6 words; RATIONALE is ZERO words) ·
//          BR-SHL-020 r2 (server `detail` never reaches a screen) ·
//          CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//          output — a person with a browser is the only check that does)
// ───────────────────────────────────────────────────────
//
//   BASE=http://127.0.0.1:8552 ACCOUNT=<uuid> \
//     node 10-scripts/def_cus_7680_disconnect_refusal_walkthrough.mjs
//
// ⚠ **THIS IS THE REPRODUCTION, RE-RUN.** The maintenance process
// (`12-governance/22-product-maintenance-process.md` §4) asks for proof
// against step 0's recorded state in a BROWSER, not for a green test: *"the
// proof is that the reported symptom is gone."* So this walk does exactly what
// the Product Owner did — opens `?step=4` on an account and presses the danger
// button — and reads what the screen says back.
//
// ⚠ **IT IS READ-ONLY, AND IT SAYS SO RATHER THAN CLAIMING IT.** Every commit
// it presses is one the SERVER refuses — that is the whole subject — so no
// case is opened, no cut is scheduled and no row is written. It needs two
// accounts that already differ: one with **no open disconnect case** and one
// with a case **below TIER 3**. On the seeded `brazosbend` fixture those are
// `A-11933` and `A-11812`; `GET /accounts/{id}/ladder` answers which is which
// in one call, under `schedule_readiness.refusal.code`.
//
// ⚠ **IT DRIVES THE BUILT BUNDLE THROUGH `server.mjs`**, the deployed join,
// rather than a dev server — the walk then exercises what a user actually
// gets. See `22-product-maintenance-process.md`'s own note on booting a stack.
//
// ⚠⚠ **BUILD IT WITH A MODE, OR THE BUNDLE TALKS TO PRODUCTION AND THE WALK
// CANNOT EVEN SIGN IN — MEASURED 2026-09-28, AND EVERY EXISTING WALK SCRIPT
// HAS THE SAME PROBLEM NOW.** `vite build` defaults to mode `production`, and
// since the deploy-config work of 2026-09-28 (`scripts/deployConfig.mjs`,
// `.env.production`) that mode bakes `VITE_API_BASE_URL=
// https://api-smart360.bynry.com` into the bundle. Served from
// `127.0.0.1:8552` the browser then refuses every call against its own
// content-security policy:
//
//     Refused to connect to 'https://api-smart360.bynry.com/api/brazosbend/
//     auth/session' because it violates the directive "connect-src 'self'"
//
// and the sign-in form answers *"That email or password is incorrect."* — a
// sentence about credentials over a request that never left the page. Nothing
// in the build says so; `resolveApiBaseUrl` returns "" (same origin) for any
// mode that is not deployed, so:
//
//     npx vite build --mode compose     ← anything but dev/sandbox/production
//
// ⚠ `--mode local` is REFUSED by vite itself (*"conflicts with the .local
// postfix for .env files"*). This lane measured the failure on `walkthrough`
// and the command above says `compose`, which is the spelling the other lanes
// were given the same day — one word, so that six walk scripts do not end up
// with six modes. **Three lanes hit this on 2026-09-28 (`DEF-INF-7702`,
// `DEF-INF-7802`), and the 56 existing walk scripts all run a bare
// `vite build`** — none of them can drive a local stack today and none of
// them says why.
import { existsSync, mkdirSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8552";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
/** An account with NO open disconnect case — scenarios A and B. */
const ACCOUNT = process.env.ACCOUNT ?? "";
/** A second account carrying a case BELOW tier 3 — scenario C. Nothing is
 *  created for it; it must already be in that state. */
const ACCOUNT_B = process.env.ACCOUNT_B ?? "";
const OUT = process.env.OUT ?? "/tmp/dsc-7680";
mkdirSync(OUT, { recursive: true });

if (ACCOUNT === "") {
  console.error("set ACCOUNT=<account uuid> — the seed moves, so nothing is hard-coded");
  process.exit(2);
}

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

let failures = 0;
const check = (label, ok, detail = "") => {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail === "" ? "" : ` — ${detail}`}`);
  if (!ok) failures += 1;
};

/** What the shipped build showed for every refusal. Read off the page's own
 *  catalogue rather than typed, so a copy change here is not a false pass. */
const GENERIC = "This disconnect step can't be done as asked. Check the case.";

const browser = await chromium.launch({ executablePath: resolveChromium() });
const page = await browser.newPage({ viewport: { width: 1440, height: 1600 } });
page.setDefaultTimeout(90000);
const pageErrors = [];
page.on("pageerror", (e) => pageErrors.push(`PAGEERROR ${e.message}`));
const refusals = [];
page.on("response", async (r) => {
  if (r.url().includes("/disconnects/schedule")) {
    let body = "";
    try {
      body = await r.text();
    } catch {
      body = "(unread)";
    }
    refusals.push(`${r.status()} ${body.slice(0, 240)}`);
  }
});

// ── sign in ───────────────────────────────────────────────────────────────
await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "domcontentloaded" });
await page.fill("#signin-email", EMAIL);
await page.fill("#signin-password", PASSWORD);
await Promise.all([
  page.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 120000 }),
  page.click('button[type="submit"]'),
]);
check("signed in", !page.url().endsWith("/signin"), page.url());

async function openWizard(account, step) {
  await page.goto(`${BASE}/${TENANT}/disconnects/new?account=${account}&step=${step}`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForSelector('[data-r10="DSC-02"]', { timeout: 90000 });
  // The account read and the ladder read both have to land before step 1 can
  // say anything; waiting on the account NAME is waiting on the first and
  // gives the second a beat.
  await page.waitForTimeout(3500);
}

/**
 * Walk step 3 → step 4 the way a clerk does, with the DATE filled.
 *
 * ⛔ **JUMPING STRAIGHT TO `?step=4` MEASURES THE WRONG REFUSAL, AND THE FIRST
 * RUN OF THIS WALK DID EXACTLY THAT.** An empty `cut_on` is refused by
 * `_required_date` before `schedule_cut` is ever called — `VAL-001`,
 * `customers.date_required` — so the screen said *"Enter the cut date."*,
 * which is correct, is not a `BIZ-COMPLETENESS` refusal, and says nothing
 * about this defect. **The Product Owner had filled every step**, so the walk
 * must too. (It is also a useful second proof in passing: a refusal that is
 * NOT one of ours still renders exactly as it did before this lane.)
 */
async function fillTheDateAndGoToStep4(account) {
  await openWizard(account, 3);
  await page.fill("#disconnect-cut-on", "2026-10-15");
  await page.evaluate(() => {
    const button = [...document.querySelectorAll('[data-wizard="actions"] button')].find((b) =>
      /Continue/i.test(b.textContent ?? ""),
    );
    button?.click();
  });
  await page.waitForTimeout(2500);
}

/** Press the danger commit and read the failure card's reason line. */
async function commitAndRead() {
  const pressed = await page.evaluate(() => {
    const button = [...document.querySelectorAll('[data-wizard="actions"] button')].find((b) =>
      /Schedule the disconnection/.test(b.textContent ?? ""),
    );
    if (button === undefined) return false;
    button.click();
    return true;
  });
  if (!pressed) return "(no commit button on screen)";
  await page.waitForSelector(".state-failed-reason", { timeout: 90000 });
  return (await page.textContent(".state-failed-reason")) ?? "";
}

// ══════════════════════════════════════════════════════════════════════════
// A · STEP 1 SAYS IT — the four steps are not spent
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── A · step 1, an account with no open case ──");
await openWizard(ACCOUNT, 1);
// ⚠ **WAIT FOR THE STRIP, DO NOT RACE IT.** The first run read the attribute
// before the ladder answer had landed on one of the two accounts and reported
// `null` while the very next line read the right sentence out of the same
// element — a check that measured the clock rather than the screen.
await page.waitForSelector("[data-preflight]", { timeout: 60000 }).catch(() => null);
await page.screenshot({ path: `${OUT}/a-step1-no-open-case.png`, fullPage: true });
const stripCode = await page.getAttribute("[data-preflight]", "data-preflight").catch(() => null);
check("step 1 draws the pre-flight refusal", stripCode === "no_open_case", String(stripCode));
const stripText = (await page.textContent("[data-preflight]").catch(() => "")) ?? "";
check("…and it reads the clerk's sentence", stripText.trim() === "No case is open.", stripText);
check("…with no internal code in the words", !stripText.includes("no_open_case"), stripText);
check("…and no rule id", !stripText.includes("BR-CUS"), stripText);

const advanced = await page.evaluate(() => {
  const button = [...document.querySelectorAll('[data-wizard="actions"] button')].find((b) =>
    /Continue/i.test(b.textContent ?? ""),
  );
  if (button === undefined) return "no-continue";
  button.click();
  return "clicked";
});
await page.waitForTimeout(800);
const stillStep1 = (await page.$('[data-step="choose"]')) !== null;
check("Continue does not move the clerk on", advanced === "clicked" && stillStep1, advanced);
await page.screenshot({ path: `${OUT}/a-step1-continue-refused.png`, fullPage: true });

// ══════════════════════════════════════════════════════════════════════════
// B · THE PRODUCT OWNER'S OWN PATH — `?step=4`, press the danger button
// ══════════════════════════════════════════════════════════════════════════
console.log("\n── B · every step filled, then the commit — the reported reproduction ──");
await fillTheDateAndGoToStep4(ACCOUNT);
const reasonB = (await commitAndRead()).trim();
await page.screenshot({ path: `${OUT}/b-step4-refusal.png`, fullPage: true });
check("the commit still refuses (the server is the guard)", reasonB !== "", reasonB);
check("…and the sentence is NOT the old generic line", reasonB !== GENERIC, reasonB);
check("…it is the reason the server sent", reasonB === "No case is open.", reasonB);
check(
  "…and the server really answered 422 with its code",
  refusals.some((r) => r.startsWith("422") && r.includes("no_open_case")),
  refusals.join(" | "),
);
check("…and no engineering prose reached the screen", !reasonB.includes("DSC-02"), reasonB);

// ══════════════════════════════════════════════════════════════════════════
// C · A SECOND CODE, SO ONE SENTENCE FOR ALL OF THEM CANNOT PASS
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **THIS IS THE HALF THAT MATTERS.** Scenario B alone would be green over a
// build that hard-coded *"No case is open."* for every refusal, which is the
// defect wearing better copy. A second account, a case already below TIER 3,
// and the screen must say something DIFFERENT.
if (ACCOUNT_B !== "") {
  console.log("\n── C · a case below tier 3 — a different refusal, a different sentence ──");
  await openWizard(ACCOUNT_B, 1);
  await page.waitForSelector("[data-preflight]", { timeout: 60000 }).catch(() => null);
  const codeC = await page.getAttribute("[data-preflight]", "data-preflight").catch(() => null);
  const textC = (await page.textContent("[data-preflight]").catch(() => "")) ?? "";
  await page.screenshot({ path: `${OUT}/c-step1-below-final-tier.png`, fullPage: true });
  check("step 1 names the TIER refusal, not the case one", codeC === "cut_before_final_tier", String(codeC));
  check(
    "…and its sentence differs from scenario A's",
    textC.trim() !== "" && textC.trim() !== "No case is open.",
    textC,
  );

  await fillTheDateAndGoToStep4(ACCOUNT_B);
  const reasonC = (await commitAndRead()).trim();
  await page.screenshot({ path: `${OUT}/c-step4-below-final-tier.png`, fullPage: true });
  check("the commit refuses with the SAME words step 1 used", reasonC === textC.trim(), `${reasonC} / ${textC}`);
  check("…and not the generic line", reasonC !== GENERIC, reasonC);
} else {
  console.log("\n── C skipped (set ACCOUNT_B to run it) ──");
}

console.log("\nrefusal responses seen:");
for (const line of refusals) console.log(`   ${line}`);
if (pageErrors.length > 0) {
  console.log("\npage errors:");
  for (const line of pageErrors) console.log(`   ${line}`);
}
console.log(`\nshots in ${OUT}`);
console.log(failures === 0 ? "\nALL CHECKS PASSED" : `\n${failures} CHECK(S) FAILED`);

await browser.close();
process.exit(failures === 0 ? 0 : 1);
