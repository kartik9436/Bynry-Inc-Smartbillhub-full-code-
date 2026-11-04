// ── THE REGISTER'S HEAD, WALKED ON ALL TEN TABS ────────────────────────────
//
// `DEF-CUS-5939`. Built to the Accounts blueprint, read AS IMAGES (B14 rule
// 42): the SAME head is drawn four times — **p117** Move-outs, **p131**
// Transfers, **p41** Complaints, **p48** Services — and the four frames are the
// evidence that what this asserts generalises rather than fitting one tab.
// Run it after any change to `AccountsListPage.tsx`'s `PageHeader` block, to
// `components/crumbLeaf.ts` or to `AppShell.tsx`'s breadcrumb.
//
// **WHAT IT IS FOR.** No gate in this repository reads rendered output
// (hard-won law 6), and every single thing below is of the kind that is right
// in a fixture and wrong on screen: a kicker the shared header never drew, a
// crumb published from an effect that `renderToStaticMarkup` never runs, a
// Tailwind tier that is in the markup and styles nothing because its file is
// not on `styles/route-b-migrated.txt`. The head was wrong on ten tabs for
// eight days with `tsc`, 45 screen cases and every gate green.
//
// ⚠ **ALL TEN TABS, AT 1280 AND 1440, AND THE COUNT IS ASSERTED.** One head
// serves ten tabs; that is why two lanes deferred this and why walking one tab
// would prove nothing. `REGISTER TABS` below is the strip's own order.
//
// ⚠ **IT REFUSES A STALE BUILD** (the sibling move-out walk's guard, reused).
// Nothing on the page says how old the bundle is, and `tsc`, the suites and
// every gate are green either way because none of them look at `dist/`.
//
// ⚠ **IT WRITES NOTHING.** Every step is a GET, so the beta is left exactly as
// it was found and the account count is printed at both ends to show it.
//
//   ACC_BASE     default http://127.0.0.1:8962
//   ACC_TENANT   default brazosbend
//   ACC_EMAIL / ACC_PASSWORD  the seeded owner
//   ACC_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.ACC_BASE || "http://127.0.0.1:8962";
const T = process.env.ACC_TENANT || "brazosbend";
const EMAIL = process.env.ACC_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.ACC_PASSWORD || "S3cure!passw0rd";
const CHROME = process.env.ACC_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

// The strip's order, and the WORD each tab is drawn with. A tab renamed here
// and not in the catalogue goes red, which is the point — the head, the strip
// and the breadcrumb all read one source and this is the check that they do.
const TABS = [
  ["accounts", "Accounts"],
  ["requests", "Requests"],
  ["new-connects", "New connects"],
  ["move-ins", "Move-ins"],
  ["move-outs", "Move-outs"],
  ["transfers", "Transfers"],
  ["disconnects", "Disconnects"],
  ["complaints", "Complaints"],
  ["services", "Services"],
  ["imports", "Imports"],
];

let pass = 0;
let fail = 0;
const failures = [];
function ok(what, cond, detail = "") {
  if (cond) {
    pass += 1;
    console.log(`  ✓ ${what}`);
  } else {
    fail += 1;
    failures.push(what);
    console.log(`  ✗ ${what}${detail ? ` — ${detail}` : ""}`);
  }
}

// ⚠ A HARD TIMEOUT ON THE WHOLE RUN — a walk that hangs is a walk nobody reads.
const KILL = setTimeout(() => {
  console.error("REFUSED: walkthrough exceeded 10 minutes — killing");
  process.exit(3);
}, 600000);

async function signIn(context, width) {
  const p = await context.newPage({ viewport: { width, height: 1400 } });
  p.setDefaultTimeout(25000);
  await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
  await p.fill("#signin-email", EMAIL);
  await p.fill("#signin-password", PASSWORD);
  await Promise.all([
    p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
    p.click('button[type="submit"]'),
  ]);
  return p;
}

let browser;
try {
  browser = await chromium.launch({ executablePath: CHROME });

  // ── 0 · THE BUILD IS THE ONE THIS COMMIT MADE ────────────────────────────
  {
    const context = await browser.newContext();
    const p = await signIn(context, 1440);
    await p.goto(`${BASE}/${T}/accounts`, { waitUntil: "networkidle" });
    // ⚠ WAIT FOR THE HEAD, do not read whatever is there at `networkidle`. The
    // first draft read `innerText` straight after the goto, got "" on a build
    // that was perfectly correct, and printed *rebuild* — a check that cannot
    // tell a stale bundle from a slow paint tells you to do the wrong thing.
    await p.waitForSelector(".page-header h1", { timeout: 20000 }).catch(() => undefined);
    const drew = await p.$eval(".page-header-id", (n) => n.innerText).catch(() => "");
    ok(
      "the served bundle is THIS commit's (the head carries a kicker)",
      /Accounts/.test(drew) && /The register/.test(drew),
      `head read ${JSON.stringify(drew)} — rebuild with \`npx vite build\` and restart server.mjs`,
    );
    await context.close();
  }

  // ── B14 rule 36 / the skill's §6: a STAFF screen is verified at 1280 AND
  //    1440, and at nothing narrower. Both widths, the same assertions.
  for (const width of [1440, 1280]) {
    console.log(`\n═══ the register's head at ${width}px ═══`);
    const context = await browser.newContext();
    const page = await signIn(context, width);

    for (const [tab, word] of TABS) {
      console.log(`── ?tab=${tab}`);
      await page.goto(`${BASE}/${T}/accounts?tab=${tab}`, { waitUntil: "networkidle" });

      // ── 1 · THE KICKER. Four frames draw `ACCOUNTS` over the title, and it
      //        is the MODULE's word — the same word the breadcrumb ancestor
      //        uses, which is why it is read from the rendered crumb too.
      // ⚠ `innerText` RETURNS WHAT IS PAINTED, AND THE KICKER IS UPPERCASED BY
      // CSS — the first draft compared against `Accounts` and failed a correct
      // screen. The drawing shows `ACCOUNTS`, so BOTH halves are asserted: the
      // word, and the fact that it renders in capitals.
      const kicker = await page
        .$eval("[data-kicker]", (n) => [n.innerText.trim(), getComputedStyle(n).textTransform])
        .catch(() => ["", ""]);
      ok(`${tab}: the kicker reads ACCOUNTS`, kicker[0] === "ACCOUNTS", JSON.stringify(kicker));
      ok(`${tab}: and it is the module's word, uppercased by the kit`,
         kicker[1] === "uppercase", JSON.stringify(kicker));

      // ── 2 · THE TITLE, AND ITS SIZE (B14 rule 40 — 32px on every screen).
      //        ⚠ READ FROM `getComputedStyle`, NEVER FROM A CLASS NAME: a
      //        `toContain("text-h2")` passes even when the utility is emitted
      //        for no file and the element renders unstyled.
      const h1 = await page
        .$eval(".page-header h1", (n) => [n.innerText.trim(), getComputedStyle(n).fontSize])
        .catch(() => ["", ""]);
      ok(`${tab}: the title reads The register`, h1[0] === "The register", JSON.stringify(h1[0]));
      ok(`${tab}: the title is 32px (B14 rule 40)`, h1[1] === "32px", h1[1]);

      // ── 3 · THE SUB-LINE — `10 tabs · <this tab>`.
      const line = await page
        .$eval(".page-header-rollup", (n) => n.innerText.replace(/\s+/g, " ").trim())
        .catch(() => "");
      ok(`${tab}: the sub-line reads 10 tabs · ${word}`, line === `10 tabs · ${word}`, JSON.stringify(line));
      // ⛔ AND NOT A ZERO. The drawings carry a third fragment (`N open`); no
      // tab can hand this head a real one, and `0 open` is a claim rather than
      // an absence. `DEF-CUS-5953` carries it — the day it lands, this line is
      // what has to be amended, deliberately.
      ok(`${tab}: no open-count fragment is invented`, !/\bopen\b/.test(line), JSON.stringify(line));

      // ── 4 · THE BREADCRUMB — `Accounts / <Tab>`, and NOTHING on the tab
      //        that IS the module (a crumb reading `Accounts › Accounts` is
      //        not what any frame draws).
      const crumbs = await page
        .$eval("nav.crumbs", (n) => n.innerText.replace(/\s+/g, " ").trim())
        .catch(() => "");
      // ⚠ THE SEPARATOR CARRIES NO LITERAL WHITESPACE — the gap either side is
      // CSS, so `innerText` reads `Accounts›Move-outs`. Asserted as rendered.
      const wanted = tab === "accounts" ? "Accounts" : `Accounts›${word}`;
      ok(`${tab}: the breadcrumb reads ${wanted}`, crumbs === wanted, JSON.stringify(crumbs));
      // ⚠ THE ANCESTOR IS ASSERTED BY ADDRESS AND THEN CLICKED. A crumb that
      // LOOKS like a way back and is not is a defect this product has already
      // filed (`DEF-MET-5870`), and `toContain` on a string cannot tell them
      // apart.
      const up = await page.$("nav.crumbs a");
      if (tab === "accounts") {
        ok(`${tab}: a lone crumb is never a link`, up === null);
      } else {
        ok(`${tab}: the ancestor is a link`, up !== null);
        if (up !== null) {
          const href = await up.getAttribute("href");
          ok(`${tab}: it is tenant-scoped (${href})`, href === `/${T}/accounts`, String(href));
          ok(`${tab}: it is not protocol-relative`, !String(href).startsWith("//"), String(href));
        }
      }
      // BR-SHL-004's other half — the browser tab mirrors the leaf.
      const title = await page.title();
      ok(`${tab}: the browser tab reads ${word}`, title === `${word} · SMARTBillHub`, title);

      // ── 5 · THE STRIP — ten tabs, the right one selected, and NO count.
      const strip = await page.$$eval("[data-page-header-tabs] [role=tab]", (els) =>
        els.map((e) => [e.getAttribute("data-tab"), e.innerText.trim(), e.getAttribute("aria-selected")]),
      );
      ok(`${tab}: the strip is ten tabs`, strip.length === 10, String(strip.length));
      ok(`${tab}: ${word} is the selected one`,
         strip.filter(([, , s]) => s === "true").map(([id]) => id).join() === tab,
         JSON.stringify(strip.filter(([, , s]) => s === "true")));
      ok(`${tab}: no tab carries a count`, strip.every(([, w]) => !/\d/.test(w)),
         JSON.stringify(strip.map(([, w]) => w)));

      // ── 6 · THE ACTION — exactly one, QUIET, and it is this tab's.
      //        ⚠ READ THE ACTION ROW ALONE. Counting over the whole head would
      //        catch a selected chip's on-state, which is a different control
      //        (`AccountsCreateEntry.test.tsx` records why).
      const actions = await page.$$eval(".page-header-actions > *", (els) =>
        els.map((e) => [e.getAttribute("data-variant"), e.innerText.trim()]),
      );
      const tiers = actions.map(([v]) => v);
      ok(`${tab}: nothing in the head is a filled primary`,
         !tiers.includes("primary"), JSON.stringify(actions));
      ok(`${tab}: exactly one quiet tab action`,
         tiers.filter((v) => v === "ghost").length === 1, JSON.stringify(actions));
      // …and it renders as text: transparent, no border. The one thing a
      // markup assertion cannot say, so it is measured.
      // ⚠ **ASK ABOUT THE COLOUR, NOT THE WIDTH.** The first draft demanded
      // `borderTopWidth === "0px"` and failed a correct button: the kit gives
      // every tier the same 1px solid box and fills the COLOUR slot, so `ghost`
      // is `border-transparent` and measures 1px solid. What a person sees is
      // whether the border and the fill are there, and that is the colour.
      const quiet = await page
        .$eval('.page-header-actions [data-variant="ghost"]', (n) => {
          const s = getComputedStyle(n);
          return [s.backgroundColor, s.borderTopColor, s.textDecorationLine, s.color];
        })
        .catch(() => null);
      const invisible = (c) => /^rgba\(\d+, \d+, \d+, 0\)$|transparent/.test(c);
      ok(`${tab}: the action has no fill and no visible border`,
         quiet !== null && invisible(quiet[0]) && invisible(quiet[1]),
         JSON.stringify(quiet));
      // …and it is the accent word the drawing draws, not grey-on-grey.
      ok(`${tab}: and it is not rendered as disabled grey`,
         quiet !== null && quiet[3] !== quiet[0], JSON.stringify(quiet));
      // The drawing carries no underline on it either — which is why this is
      // the kit's `ghost` tier and not `link`.
      ok(`${tab}: and no underline`, quiet !== null && quiet[2] === "none", JSON.stringify(quiet));

      // ── 7 · AND THE HEAD FITS. A tab word that does not fit the line is one
      //        of the three things this lane was asked to check for all ten.
      const hscroll = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      ok(`${tab}: no horizontal page scroll at ${width}`, hscroll === 0, `${hscroll}px`);
      const wraps = await page
        .$eval(".page-header-rollup", (n) => n.getClientRects().length)
        .catch(() => 0);
      ok(`${tab}: the sub-line is one line`, wraps === 1, `${wraps} line(s)`);
    }
    await context.close();
  }
} finally {
  if (browser) await browser.close();
  clearTimeout(KILL);
}

console.log(`\n${pass} passed · ${fail} failed`);
if (fail > 0) {
  console.log("failed:");
  for (const f of failures) console.log(`  · ${f}`);
  process.exit(1);
}
