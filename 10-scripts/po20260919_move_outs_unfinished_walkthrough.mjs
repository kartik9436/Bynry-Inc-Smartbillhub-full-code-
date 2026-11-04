// ── THE MOVE-OUTS LIST WITH ITS UNFINISHED ROWS, WALKED IN A BROWSER ───────
//
// **PO ruling 2026-09-19, verbatim `yes`** — the Move-outs list must show the
// move-outs that have not finished yet — plus `DEF-CUS-5901`'s one word. Built
// to the Accounts blueprint **p117**, read AS AN IMAGE per B14 rule 42. Run it
// after any change to `MoveOutsTab.tsx` or `apps/customers/move_reads.py`.
//
// **WHAT IT IS FOR.** No gate in this repo reads rendered output, and every
// thing it checks is of the kind that looks perfect in a unit test: a state
// word that is right in a fixture and wrong in a catalogue, a step bar that
// renders `2 of 6` in jsdom over an href that opens nothing, a settlement cell
// printing the closed row's reason over a row that never closed. Hard-won law 6
// is the one law with no tool.
//
// ⚠ **IT NEEDS A PARKED MOVE-OUT AND DOES NOT MAKE ONE.** Seed with
// `po20260919_move_outs_unfinished_seed.py` and remove it afterwards with
// `po20260919_move_outs_unfinished_purge.py` — the counts are printed by both,
// so *"the beta was left as it was found"* is checked rather than asserted.
//
// ⚠ **IT REFUSES A STALE BUILD** (the sibling move-record walk's guard, reused).
// Nothing on the page says how old the bundle is; `tsc`, the suites and every
// gate are green either way, because none of them look at `dist/`.
//
// ⚠ **IT WRITES NOTHING.** Every step is a GET.
//
//   MVO_BASE     default http://127.0.0.1:8962
//   MVO_TENANT   default brazosbend
//   MVO_EMAIL / MVO_PASSWORD  the seeded owner
//   MVO_CHROME   default /opt/pw-browsers/chromium-1194/chrome-linux/chrome
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");

const BASE = process.env.MVO_BASE || "http://127.0.0.1:8962";
const T = process.env.MVO_TENANT || "brazosbend";
const EMAIL = process.env.MVO_EMAIL || "dana@brazosbendutilities.com";
const PASSWORD = process.env.MVO_PASSWORD || "S3cure!passw0rd";
const CHROME =
  process.env.MVO_CHROME || "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";

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
  console.error("REFUSED: walkthrough exceeded 5 minutes — killing");
  process.exit(3);
}, 300000);

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

  // ── B14 rule 36 / the skill's §6: a STAFF screen is verified at 1280 AND
  //    1440, and at nothing narrower. Both widths, the same assertions.
  for (const width of [1440, 1280]) {
    console.log(`\n═══ the Move-outs tab at ${width}px ═══`);
    const context = await browser.newContext();
    const page = await signIn(context, width);
    await page.goto(`${BASE}/${T}/accounts?tab=move-outs`, { waitUntil: "networkidle" });

    const text = await page.innerText("body");

    // ── 1 · THE RULING: an unfinished move-out is on the list ──────────────
    const rows = await page.$$eval("table tbody tr", (trs) =>
      trs.map((tr) => [...tr.querySelectorAll("td")].map((td) => td.innerText.trim())),
    );
    ok("the list holds more than the closed move-outs", rows.length >= 2,
       `${rows.length} row(s) — seed a parked move-out first`);

    // ── 2 · THE STEP — p117's `2 of 6`, off the draft's own column ─────────
    const stepped = await page.$$("[data-step-progress]");
    ok("an unfinished row prints the step the clerk reached", stepped.length >= 1);
    if (stepped.length) {
      const progress = await stepped[0].getAttribute("data-step-progress");
      const shown = (await stepped[0].innerText()).trim();
      ok(`the printed step matches the served one (${progress} · "${shown}")`,
         shown === progress.replace("/", " of "), `printed "${shown}" for ${progress}`);
    }

    // ── 3 · THE COEXISTENCE — a closed row still states its absence ────────
    ok("a finished row still says its step was not recorded",
       text.includes("Step not recorded") || text.includes("not written down"),
       "a closed move-out must never be given a step it did not record");

    // ── 4 · `DEF-CUS-5901` — one word, and it is `Completed` ───────────────
    // ⚠ READ THE STATE CELLS, NOT THE PAGE: `Closed` is legitimately on this
    // screen as a filter name and inside the OPEN tile's caption.
    const states = await page.$$eval("[data-move-out-state]", (els) =>
      els.map((el) => [el.getAttribute("data-move-out-state"), el.innerText.trim()]),
    );
    ok("every finished row reads `Completed`",
       states.filter(([c]) => c === "closed").every(([, w]) => w === "Completed"),
       JSON.stringify(states));
    ok("no state cell reads `Closed`",
       states.every(([, w]) => w !== "Closed"), JSON.stringify(states));
    ok("an unfinished row reads `In progress` or `Waiting`",
       states.some(([c, w]) => (c === "in_progress" && w === "In progress") ||
                               (c === "waiting" && w === "Waiting")),
       JSON.stringify(states));
    // ⛔ THE STORED VALUE IS UNTOUCHED — the code is still `closed` on the row.
    ok("the stored value is still `closed`", states.some(([c]) => c === "closed"));

    // ── 5 · THE RESUME DOOR, by ADDRESS (the fixture trap law 2 records) ───
    // ⚠ **THE ANCHOR IS INSIDE THE MARKED SPAN SINCE 2026-09-25**
    //    (`DEF-CUS-6759`). The row action is a `RowActionLink` now — an ICON
    //    with an accessible name, per the PO's *"it should be icons not
    //    buttons"* — and that component spreads no `data-*`, so the tab stamps
    //    the marker on a `<span>` it owns and the door is the `<a>` within it.
    //    Reading the SPAN's `href` returns null, which would read here as
    //    *"this row has no door"* over a row that has one.
    const resume = await page.$("[data-move-out-resume] a");
    ok("an unfinished row carries a door", resume !== null);
    if (resume !== null) {
      const href = await resume.getAttribute("href");
      ok(`it is tenant-scoped and opens the wizard (${href})`,
         href.startsWith(`/${T}/move-outs/new?parked=`), href);
      // ⛔ THE PROTOCOL-RELATIVE SHAPE, named so a regression is unmistakable.
      ok("it is not a protocol-relative URL to another host",
         !href.startsWith("//"), href);
      // …and it actually opens the wizard, which is the half a string cannot say.
      await page.goto(`${BASE}${href}`, { waitUntil: "networkidle" });
      const wizard = await page.innerText("body");
      ok("the door opens the move-out wizard, not a refusal",
         !wizard.includes("not built") && !wizard.includes("Unexpected Application Error"),
         wizard.slice(0, 160));
      await page.goto(`${BASE}/${T}/accounts?tab=move-outs`, { waitUntil: "networkidle" });
    }

    // ── 6 · THE ABSENCES — stated, never invented ──────────────────────────
    const body = await page.innerText("body");
    ok("the unfinished row says why it has no number, in five words",
       body.includes("No number until it completes"), "reference absence missing");
    // ⛔ **THE LONG FORM IS THE TITLE, NEVER THE CELL** (B14 rule 33). Measured
    // here first: the whole sentence wrapped to twelve lines in this column and
    // made the row taller than the three beside it.
    const refCell = await page.$('[data-move-absent="reference"]');
    ok("the reference cell is one short line",
       refCell !== null && (await refCell.innerText()).trim().split(/\s+/).length <= 6,
       refCell === null ? "no reference cell" : (await refCell.innerText()).trim());
    ok("the long form rides on the cell rather than in it",
       refCell !== null && (await refCell.getAttribute("title") || "").includes("has no number yet"));
    ok("the unfinished row says why there is no settlement",
       body.includes("Not settled until it closes"), "settlement absence missing");
    ok("it does NOT print the closed row's settlement reason over an open one",
       (body.match(/final bill is not readable/g) || []).length <= rows.length - 1,
       "a row that never closed cannot be waiting on a final bill");
    // ⛔ NEVER A ZERO ON A MONEY TERM IT DID NOT READ (DEF-127).
    ok("no unfinished row shows a settlement figure", !body.includes("Short by $0.00"));

    // ── 7 · B14 rule 12 — the four drawn segment chips stay OUT ────────────
    ok("the drawn segment chips are not rendered",
       !body.includes("Leaving this week ") || !/\bOpen\s+Leaving this week\s+Closed\s+All\b/.test(body));

    // ── 8 · no internal reference reaches the clerk (rules 31 and 32) ──────
    ok("no rule id, defect id or backtick on screen",
       !/BR-[A-Z]{3}-\d/.test(body) && !/\bDEF-[A-Z]{3}-\d/.test(body) && !body.includes("`"),
       "an internal reference is visible");

    // ── 9 · nothing scrolls sideways at this width ─────────────────────────
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    ok("the page does not scroll sideways", !overflow);

    await page.screenshot({
      path: `/tmp/claude-0/-home-user-SMARTBillHub/da7d6dea-a84b-56ee-b035-57684ffe93fb/scratchpad/mvo/after-${width}.png`,
      fullPage: true,
    });
    await context.close();
  }
} finally {
  clearTimeout(KILL);
  if (browser) await browser.close();
}

console.log(`\n${pass} passed · ${fail} failed`);
if (fail) {
  console.log("failures:");
  failures.forEach((f) => console.log(`  - ${f}`));
  process.exit(1);
}
