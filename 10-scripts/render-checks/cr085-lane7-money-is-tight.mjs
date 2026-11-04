// ── Trace ────────────────────────────────────────────────────────────────
// Change:   CR-085 step 2 lane 7 — WHEN MONEY IS TIGHT.
// Screens:  CWP-057 /overdue · CWP-056 /help-paying · CWP-044 /level-pay ·
//           CWP-066 /level-pay/standing · CWP-043 /plan · CWP-063 /plan-offer ·
//           CWP-042 /ask-for-a-plan · CWP-064 /protections ·
//           CWP-045 /money-back · CWP-050 /fees
// Rules:    R-10 and R-22 (PO 2026-09-11) · B14 rule 2 (ONE page header) ·
//           CLAUDE.md hard-won law 6 (no gate in this repo reads rendered
//           output) · law 7 habit 3 (a check's output must distinguish pass
//           from fail TO A READER, not merely by an exit code)
// ─────────────────────────────────────────────────────────────────────────
//
// WHAT THIS PROVES THAT NOTHING ELSE IN THE REPO DOES
// ---------------------------------------------------
// R-10 is a claim about what is ON THE SCREEN next to a sentence — "not a page
// away, not in a menu, right there". jsdom applies no CSS, so the DOM suites
// beside these screens cannot tell a control that is on the card from one that
// is `display:none`, and no gate reads rendered output at all. This walks all
// ten addresses in a real browser at BOTH widths and, for every screen that
// settles on a state card, requires a way out inside that same card.
//
// ⚠ **IT DOES NOT WAIT ON `[data-screen="CWP-…"]` TO MEAN "THE DATA ARRIVED"
// (`DEF-CWP-4941`, a defect a sibling's walkthrough caused in itself).** R-10
// and R-22 put that mark on the loading and failed branches too, which is
// right and which silently turns every such wait into a RACE: on a quiet
// machine the read finishes first and everything passes; under load the same
// code reports a layout defect that is not there. **A check whose answer
// depends on the load average is not a check.** So this waits for the LOADING
// card to detach and then reads which branch the screen actually settled in —
// which is also the fact worth reporting.
//
// ⚠ RUN IT AGAINST YOUR OWN SERVER, NOT THE SHARED ONE on :8401, which is
// several lanes' at once:
//     PORT=<free> API_PROXY_TARGET=http://127.0.0.1:8000 node 07-frontend/server.mjs
//     SBH_BASE=http://127.0.0.1:<free> SBH_TENANT=brazosbend \
//     SBH_EMAIL=… SBH_PASSWORD=… node 10-scripts/render-checks/cr085-lane7-money-is-tight.mjs
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const requireFrontend = createRequire(path.resolve("07-frontend/package.json"));
const { chromium } = requireFrontend("playwright-core");

/** Any installed chromium, not only the revision playwright pinned. */
function findChromium() {
  if (process.env.SBH_CHROMIUM) return process.env.SBH_CHROMIUM;
  const wanted = chromium.executablePath();
  if (fs.existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  for (const dir of fs.existsSync(root) ? fs.readdirSync(root) : []) {
    // ⚠ `chromium` is a FILE in this image and `chromium-1194` is the
    // directory; a helper returning the first name starting with "chromium"
    // hands playwright a path that is not an executable.
    if (!dir.startsWith("chromium")) continue;
    for (const rel of ["chrome-linux/chrome", "chrome"]) {
      const candidate = path.join(root, dir, rel);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return wanted; // let playwright report the miss in its own words
}

const BASE = process.env.SBH_BASE ?? "http://127.0.0.1:8414";
const TENANT = process.env.SBH_TENANT ?? "brazosbend";
const EMAIL = process.env.SBH_EMAIL;
const PASSWORD = process.env.SBH_PASSWORD;
if (!EMAIL || !PASSWORD) {
  console.error("SBH_EMAIL and SBH_PASSWORD are required — this walk is of the SIGNED-IN portal.");
  process.exit(2);
}

const ROUTES = [
  ["/overdue", "CWP-057"],
  ["/help-paying", "CWP-056"],
  ["/level-pay", "CWP-044"],
  ["/level-pay/standing", "CWP-066"],
  ["/plan", "CWP-043"],
  ["/plan-offer", "CWP-063"],
  ["/ask-for-a-plan", "CWP-042"],
  ["/protections", "CWP-064"],
  ["/money-back", "CWP-045"],
  ["/fees", "CWP-050"],
];

let failures = 0;
let checks = 0;
function check(ok, what, saw) {
  checks += 1;
  if (ok) console.log(`  PASS  ${what}`);
  else {
    failures += 1;
    console.log(`  FAIL  ${what}${saw === undefined ? "" : `  — saw ${JSON.stringify(saw)}`}`);
  }
}

const browser = await chromium.launch({ executablePath: findChromium() });
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await context.newPage();
const jsErrors = [];
page.on("pageerror", (e) => jsErrors.push(`${page.url()} :: ${e.message}`));

await page.goto(`${BASE}/${TENANT}/portal/sign-in`, { waitUntil: "domcontentloaded" });
await page.fill("#portal-email", EMAIL);
await page.fill("#portal-password", PASSWORD);
await page.click('button:has-text("Sign in")');
await page.waitForURL(/\/portal\/home$/, { timeout: 60_000 });
console.log(`signed in, landed on ${page.url()}`);

for (const width of [1280, 390]) {
  await page.setViewportSize({ width, height: width === 390 ? 840 : 900 });
  console.log(`\n══ ${width}px ═══════════════════════════════════════════════`);

  for (const [route, screen] of ROUTES) {
    await page.goto(`${BASE}/${TENANT}/portal${route}`, { waitUntil: "domcontentloaded" });
    let settled = "(never drew)";
    try {
      await page.waitForSelector(`[data-screen="${screen}"]`, { state: "attached", timeout: 45_000 });
      await page
        .waitForSelector('[data-portal-state="loading"]', { state: "detached", timeout: 45_000 })
        .catch(() => {});
      settled = await page.evaluate((id) => {
        const root = document.querySelector(`[data-screen="${id}"]`);
        if (!root) return "(no screen mark)";
        const card = root.querySelector("[data-portal-state]");
        return card ? card.getAttribute("data-portal-state") : "populated";
      }, screen);
    } catch {
      /* settled stays "(never drew)" and the checks below fail honestly */
    }

    const facts = await page.evaluate((id) => {
      const root = document.querySelector(`[data-screen="${id}"]`);
      if (!root) return null;
      const card = root.querySelector("[data-portal-state]");
      const ways = card ? [...card.querySelectorAll("[data-way-out]")] : [];
      return {
        h1: document.querySelectorAll("h1").length,
        sentence: card ? (card.querySelector("[data-state-sentence]")?.textContent ?? "") : "",
        waysOut: ways.map((w) => w.getAttribute("data-way-out")),
        waysAreLive: ways.every(
          (w) => w.tagName === "A" ? !!w.getAttribute("href") : !w.hasAttribute("disabled"),
        ),
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    }, screen);

    console.log(`\n${route}  (${screen})  → ${settled}`);
    check(facts !== null, `${screen} is marked in the DOM`, settled);
    if (!facts) continue;

    // R-10: bad news carries its own way out, IN the card. An `empty` card is
    // not bad news (an empty /overdue is GOOD news), so only `failed` is held
    // to it here — which is what step 1 found breached on nine screens.
    if (settled === "failed") {
      check(facts.waysOut.length > 0, `R-10 — the failed card carries a way out`, facts.waysOut);
      check(facts.waysAreLive, `R-10 — every way out is wired, not a dead control`, facts.waysOut);
    }
    if (settled === "failed" || settled === "empty") {
      check(facts.sentence.trim().length > 0, `R-22 — the card states its case in words`, facts.sentence);
    }
    // B14 rule 2 — ONE page header. CWP-050's head is on FeesPage.tsx.
    check(facts.h1 <= 1, `B14 rule 2 — at most one <h1>`, facts.h1);
    if (width === 390) {
      check(facts.overflow <= 1, `390 — the page body does not scroll sideways`, facts.overflow);
    }
  }
}

// ── THE PHASE THAT ACTUALLY TESTS R-10 ────────────────────────────────────
// ⚠ **A SEEDED TENANT IN GOOD STANDING NEVER SHOWS A FAILED CARD**, so the two
// passes above walk ten screens and prove nothing whatever about the rule this
// lane exists for. R-10 is a claim about BAD NEWS: *"the thing they can do
// about it must be on that same screen, next to the message."* So the reads
// are refused at the network and every screen is driven onto its failed
// branch deliberately — which is hard-won law 7's "break the guard FIRST".
//
// Auth, `/portal/session`, `/portal/home` and `/portal/my-accounts` are left
// alone: refusing those signs the customer out and the walk would then be
// measuring the sign-in screen while reporting on ten others.
const REFUSE =
  /\/portal\/(fees|accounts\/[^/]+\/(arrears|help-paying|level-pay(\/standing)?|money-back|protections|plans\/(current|offer)))(\?|$)/;
await context.route("**/api/**", (route) =>
  REFUSE.test(route.request().url()) ? route.abort("failed") : route.continue(),
);

for (const width of [1280, 390]) {
  await page.setViewportSize({ width, height: width === 390 ? 840 : 900 });
  console.log(`\n══ ${width}px · EVERY READ REFUSED ════════════════════════`);

  for (const [route, screen] of ROUTES) {
    if (route === "/ask-for-a-plan") continue; // a form, not a read: no failed card
    await page.goto(`${BASE}/${TENANT}/portal${route}`, { waitUntil: "domcontentloaded" });
    let facts = null;
    try {
      await page.waitForSelector(`[data-screen="${screen}"] [data-portal-state="failed"]`, {
        state: "attached",
        timeout: 45_000,
      });
      facts = await page.evaluate((id) => {
        const card = document.querySelector(`[data-screen="${id}"] [data-portal-state="failed"]`);
        const ways = [...card.querySelectorAll("[data-way-out]")];
        return {
          role: card.getAttribute("role"),
          sentence: card.querySelector('[data-state-sentence="failed"]')?.textContent ?? "",
          ways: ways.map((w) => ({
            key: w.getAttribute("data-way-out"),
            tag: w.tagName,
            href: w.getAttribute("href"),
            disabled: w.hasAttribute("disabled"),
            // "right there" is a claim about PIXELS, and this is the only
            // instrument in the repo that can see them.
            onScreen: !!w.getClientRects().length,
          })),
        };
      }, screen);
    } catch {
      /* facts stays null and the check below fails honestly */
    }

    console.log(`\n${route}  (${screen})  → refused`);
    check(facts !== null, `${screen} draws a FAILED card when its read is refused`);
    if (!facts) continue;
    check(facts.sentence.trim().length > 0, `R-22 — the failed card says so in words`, facts.sentence);
    check(facts.role === "alert", `the failed card is announced (role=alert)`, facts.role);
    check(facts.ways.length > 0, `R-10 — a way out is ON the card`, facts.ways.map((w) => w.key));
    check(
      facts.ways.every((w) => w.onScreen),
      `R-10 — every way out is really on screen at ${width}px`,
      facts.ways,
    );
    check(
      facts.ways.every((w) => (w.tag === "A" ? !!w.href : !w.disabled)),
      `R-10 — no way out is a dead control`,
      facts.ways,
    );
  }
}

console.log(`\n──────────────────────────────────────────────────────────`);
console.log(jsErrors.length ? `JS ERRORS:\n  ${jsErrors.join("\n  ")}` : "no JS errors on any route");
console.log(`${checks - failures}/${checks} checks passed, ${failures} FAILED`);
await browser.close();
process.exit(failures === 0 ? 0 : 1);
