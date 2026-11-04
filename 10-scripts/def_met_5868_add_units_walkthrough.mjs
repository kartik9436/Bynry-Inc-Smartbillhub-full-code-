// ── THE PO's THREE PRM-03 REPORTS, WALKED IN A BROWSER (2026-09-19) ─────────
//
// `DEF-MET-5868` · `DEF-MET-5869` · `DEF-MET-5870`, all three reported by the
// Product Owner from the Add units screen, in their own words:
//
//   1. *"Unit add form -> square feet field present on edit form but not
//      present on add form why?"*                              (DEF-MET-5868)
//   2. *"cancel button should be bottom not on top"*           (DEF-MET-5869)
//   3. *"back arrow button is missing user not able to navigate on unit list
//      view"*                                                  (DEF-MET-5870)
//
// Run it after any change to `AddUnitsWizard.tsx` or to `WizardFrame`'s action
// row. It needs a real stack and a real PostgreSQL — see the env block below.
//
// ⚠ **IT REFUSES A STALE BUILD, AND THAT GUARD IS THE POINT.** On 2026-09-19 a
// sibling walk ran against a `dist/` built 26 hours earlier and read three
// landed fixes as ABSENT — one step from reporting that other lanes had not
// done their work. Nothing in the page says how old it is, and `tsc`, the
// suites and every gate are green either way, because none of them look at
// `dist/`. This one compares the bundle against BOTH the newest commit to
// `07-frontend/src` AND the mtime of the five files this walk is about, so an
// uncommitted edit that was never rebuilt is refused too.
//
// ⚠ **EVERY ASSERTION IS WRITTEN AGAINST ITS FALSE PASS (hard-won law 7:
// *ask what would make this check pass wrongly*).** The obvious form of each
// one passes on the broken screen, and two of them did exactly that on the
// first red run of this file, which is how they were found:
//
//   · *"a Cancel button exists"* passes while Cancel is still in the page
//     head — the very state reported. So it asserts CONTAINMENT: the button is
//     inside `[data-wizard="actions"]`, below the step content, and left of
//     the commit.
//   · *"a back control exists"* passes on a control pointing anywhere at all,
//     which is hard-won law 2's mirror — a live screen behind a dead door. So
//     it CLICKS it and asserts the URL that results.
//   · *"the form has a floor-area field"* passes if the value is dropped en
//     route. So the run is committed and the row is read back OUT OF POSTGRES,
//     never from the response.
//   · ⚠ *"Back returns to step 1"* PASSED on the unfixed build, by never
//     having moved off step 1 — the post-condition was also the
//     pre-condition. It now asserts step 2 was reached first.
//   · ⚠ *"the head carries a back link"* PASSED on the unfixed build too:
//     `headBackText !== null` is true for `undefined`, which is what the probe
//     returns when it bails early. It now demands a non-empty string.
//
// ⚠ **IT WRITES REAL ROWS, so point it at a CLONE and never at the beta.**
// `createdb -T sbh <yours>` takes seconds; purging afterwards does not, and a
// half-purged add-units run leaves units nobody can explain.
//
//   PRM03_ROOT    the worktree whose dist/ is being walked
//   PRM03_BASE    default http://127.0.0.1:8752   PRM03_TENANT  default brazosbend
//   PRM03_DB      the database `psql` reads back  PRM03_SHOTS   where PNGs land
//   PRM03_TAG     filename suffix for the shots   PRM03_EMAIL / PRM03_PASSWORD
//     (the pinned @playwright/test version does not match the preinstalled
//      browser in this container, so the Chrome path is passed explicitly —
//      see CLAUDE.md's environment note; never run `playwright install` here.)
import { createRequire } from "node:module";
const require = createRequire("/home/user/SMARTBillHub/07-frontend/package.json");
const { chromium } = require("playwright");
import { execSync } from "node:child_process";
import { statSync } from "node:fs";

const ROOT = process.env.PRM03_ROOT || "/tmp/claude-0/-home-user-SMARTBillHub/da7d6dea-a84b-56ee-b035-57684ffe93fb/scratchpad/wt-prm03";
const BASE = process.env.PRM03_BASE || "http://127.0.0.1:8752";
const T = process.env.PRM03_TENANT || "brazosbend";
const SHOTS = process.env.PRM03_SHOTS || "/tmp/claude-0/-home-user-SMARTBillHub/da7d6dea-a84b-56ee-b035-57684ffe93fb/scratchpad/shots";
const TAG = process.env.PRM03_TAG || "after";
const CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
const DB = process.env.PRM03_DB || "sbh_prm03";

const built = statSync(`${ROOT}/07-frontend/dist/index.html`).mtime;
const newestSrc = new Date(execSync(`git -C ${ROOT} log -1 --format=%cI -- 07-frontend/src`).toString().trim());
const newestWork = new Date(Math.max(
  ...["components/WizardFrame.tsx", "features/metering/AddUnitsWizard.tsx",
      "features/rating/DiscountWizard.tsx", "features/rating/PlanWizard.tsx",
      "features/billing/BudgetEnrolPage.tsx"]
    .map((f) => statSync(`${ROOT}/07-frontend/src/${f}`).mtime.getTime()),
));
// Both halves: the bundle must be newer than the last COMMIT to src (a stale
// checkout) AND newer than my own uncommitted edits (a forgotten rebuild).
if (built < newestSrc || built < newestWork) {
  console.error(`REFUSED: dist/ built ${built.toISOString()}; newest src commit ` +
    `${newestSrc.toISOString()}; newest edited file ${new Date(newestWork).toISOString()}. Run vite build.`);
  process.exit(2);
}

const R = [];
const ok = (n, c, d = "") => R.push(`${c ? "PASS" : "FAIL"} · ${n}${d ? " · " + d : ""}`);
const sql = (q) => execSync(`sudo -u postgres psql -d ${DB} -tAc ${JSON.stringify(q)}`).toString().trim();
// Every browser interaction runs through this. A control that is absent on a
// regressed build makes its step FAIL and lets the walk carry on to the ones
// after it, which is the whole difference between a report and a stack trace.
let broke = null;
const step = async (name, fn) => {
  if (broke !== null) { ok(name, false, `skipped — "${broke}" did not complete`); return null; }
  try { return await fn(); }
  catch (e) { broke = name; ok(name, false, String(e).split("\n")[0]); return null; }
};

const before = sql("select count(*) from units");

const b = await chromium.launch({ executablePath: CHROME });
const p = await b.newPage({ viewport: { width: 1440, height: 1200 } });
await p.goto(`${BASE}/${T}/signin`, { waitUntil: "domcontentloaded" });
await p.fill("#signin-email", process.env.PRM03_EMAIL || "dana@brazosbendutilities.com");
await p.fill("#signin-password", process.env.PRM03_PASSWORD || "S3cure!passw0rd");
await Promise.all([
  p.waitForURL((u) => !u.pathname.endsWith("/signin"), { timeout: 30000 }),
  p.click('button[type="submit"]'),
]);

await p.goto(`${BASE}/${T}/premises/units/new`, { waitUntil: "networkidle" });
await p.waitForTimeout(2500);
await p.screenshot({ path: `${SHOTS}/addunits-step1-${TAG}.png`, fullPage: true });

// ── 1 · THE FIELD IS ON THE ADD FORM, AND IT IS `Floor`'s SHAPE ────────────
ok("1 · #square_feet is on the add form", await p.locator("#square_feet").count() > 0);
const shape = await p.evaluate(() => {
  const inp = document.querySelector("#square_feet");
  const fl = document.querySelector("#floor_label");
  if (!inp || !fl) return null;
  const labelOf = (e) => document.querySelector(`label[for="${e.id}"]`)?.textContent?.trim() ?? null;
  // the help sentence is the field wrapper's last text node under the input
  const helpOf = (e) => {
    const w = e.closest("div");
    return [...(w?.querySelectorAll("p,small,span") ?? [])]
      .map((n) => n.textContent.trim()).filter(Boolean).pop() ?? null;
  };
  return {
    label: labelOf(inp), floorLabel: labelOf(fl),
    help: helpOf(inp), floorHelp: helpOf(fl),
    required: inp.hasAttribute("required"),
    // drawn immediately after Floor, which is the precedent it follows
    afterFloor: !!(fl.compareDocumentPosition(inp) & Node.DOCUMENT_POSITION_FOLLOWING),
  };
});
ok("1 · its label is the edit form's own words", shape?.label === "Floor area", `label=${JSON.stringify(shape?.label)}`);
ok("1 · it reuses Floor's help sentence verbatim", shape !== null && shape.help === shape.floorHelp,
   `help=${JSON.stringify(shape?.help)}`);
ok("1 · it is OPTIONAL, like Floor", shape?.required === false);
ok("1 · it sits after Floor", shape?.afterFloor === true);

// ── 2 · CANCEL IS IN THE WIZARD FOOTER, NOT THE HEAD ──────────────────────
const cancelPos = await p.evaluate(() => {
  const actions = document.querySelector('[data-wizard="actions"]');
  const head = document.querySelector(".met-head");
  const content = document.querySelector('[data-wizard="content"]');
  const cancel = document.querySelector("[data-wizard-cancel]");
  if (!cancel || !actions) return { found: false };
  const r = (e) => Math.round(e.getBoundingClientRect().top + window.scrollY);
  const back = document.querySelector(".met-back");
  return {
    found: true,
    inFooter: actions.contains(cancel),
    inHead: head ? head.contains(cancel) : false,
    belowContent: content ? r(cancel) > r(content) : null,
    cancelText: cancel.textContent.trim(),
    cancelLeft: Math.round(cancel.getBoundingClientRect().left),
    // the commit/continue is the right-hand end of the same row
    primaryLeft: Math.round([...actions.querySelectorAll("button")].pop().getBoundingClientRect().left),
    headBackText: back ? back.textContent.trim() : null,
  };
});
ok("2 · Cancel is INSIDE the wizard-actions footer", cancelPos.found && cancelPos.inFooter === true, JSON.stringify(cancelPos));
ok("2 · Cancel is NOT in the page head", cancelPos.found && cancelPos.inHead === false);
ok("2 · Cancel renders BELOW the step content", cancelPos.belowContent === true);
ok("2 · Cancel is at the LEFT of the footer row", cancelPos.found && cancelPos.cancelLeft < cancelPos.primaryLeft,
   `cancelLeft=${cancelPos.cancelLeft} primaryLeft=${cancelPos.primaryLeft}`);

// ── 3 · THE EXIT AND THE STEP-BACK: different words, different places ──────
ok("3 · the head carries a back link",
   typeof cancelPos.headBackText === "string" && cancelPos.headBackText.trim() !== "",
   `text=${JSON.stringify(cancelPos.headBackText)}`);
ok("3 · B14 rule 1 — the exit and Cancel do not share a label",
   cancelPos.headBackText !== cancelPos.cancelText,
   `head=${JSON.stringify(cancelPos.headBackText)} cancel=${JSON.stringify(cancelPos.cancelText)}`);

// ── 1+ · COMMIT A RUN AND READ THE ROW BACK OUT OF POSTGRES ────────────────
const AREA = "1737"; // a figure no seeded unit holds, so the read-back is unambiguous
await step("1 · the add form accepts a building, a count and a floor area", async () => {
  await p.locator("#premises_id").click();
  await p.waitForTimeout(400);
  await p.keyboard.type("4");
  await p.waitForTimeout(1600);
  await p.locator('[role="option"], li, button')
    .filter({ hasText: /P-\d{5}|Cypress|Bluestem|Ln|Row|St/ }).first().click();
  await p.waitForTimeout(1800);
  await p.fill("#units_per_floor", "2");
  await p.fill("#floor_label", "PRM03");
  await p.fill("#square_feet", AREA, { timeout: 8000 });
  await p.waitForTimeout(400);
});
await p.screenshot({ path: `${SHOTS}/addunits-step1-filled-${TAG}.png`, fullPage: true });

// Continue → step 2 (the frame's primary is the last button in the row)
await step("1 · Continue reaches the review", async () => {
  await p.locator('[data-wizard="actions"] button').last().click();
  await p.waitForTimeout(3500);
});
const step2 = await p.evaluate(() => document.body.innerText);
ok("1 · the REVIEW names the floor area before the commit",
   /1,737 sq ft/.test(step2), `review ${/1,737 sq ft/.test(step2) ? "shows" : "does NOT show"} "1,737 sq ft"`);
await p.screenshot({ path: `${SHOTS}/addunits-step2-${TAG}.png`, fullPage: true });

// ── 3 · `← Back` MEANS PREVIOUS STEP, NOT THE LIST ────────────────────────
const onStep2 = await p.evaluate(() =>
  document.querySelector('[data-wizard-step="2"]')?.getAttribute("data-state") === "active");
ok("3 · the walk actually reached step 2", onStep2 === true,
   "without this the next check passes by never having moved");
const backBtn = p.locator('[data-wizard="actions"] button').filter({ hasText: /^Back$/ }).first();
ok("3 · step 2 offers a footer Back", await backBtn.count() > 0);
await step("3 · the footer Back can be pressed", async () => {
  await backBtn.click();
  await p.waitForTimeout(2000);
});
const afterBack = await p.evaluate(() => ({
  url: location.pathname,
  step: document.querySelector('[data-wizard-step="1"]')?.getAttribute("data-state"),
  area: document.querySelector("#square_feet")?.value,
}));
ok("3 · footer Back returns to STEP 1, not to the units list",
   onStep2 === true && /\/premises\/units\/new$/.test(afterBack.url) && afterBack.step === "active",
   JSON.stringify({ reachedStep2: onStep2, ...afterBack }));
ok("3 · and it keeps what was typed", afterBack.area === AREA, `square_feet=${afterBack.area}`);

// forward again and COMMIT
await step("1 · the run commits", async () => {
  await p.locator('[data-wizard="actions"] button').last().click();
  await p.waitForTimeout(3500);
  await p.locator('[data-wizard="actions"] button').last().click();
  await p.waitForTimeout(5000);
});
const landed = p.url();
ok("1 · the commit lands back on the units list", /\/premises\/units(\?|$)/.test(landed), landed);

const after = sql("select count(*) from units");
ok("1 · rows were created", Number(after) > Number(before), `${before} → ${after}`);
const rows = sql(`select label||'='||coalesce(square_feet::text,'NULL')||'/'||coalesce(floor_label,'NULL') from units where floor_label='PRM03' order by label`);
ok("1 · THE DATABASE HOLDS THE FLOOR AREA (not the response — the row)",
   rows.split("\n").every((r) => r.endsWith(`=${AREA}/PRM03`)) && rows.length > 0,
   `rows: ${rows.replace(/\n/g, " · ")}`);

// ── 3 · THE HEADER LINK ACTUALLY GOES TO THE UNITS LIST ───────────────────
await p.goto(`${BASE}/${T}/premises/units/new`, { waitUntil: "networkidle" });
await p.waitForTimeout(2000);
await step("3 · the header link can be pressed", async () => {
  await p.locator(".met-back").click({ timeout: 8000 });
  await p.waitForTimeout(2500);
});
ok("3 · clicking the header link LANDS on the units list",
   /\/premises\/units(\?|$)/.test(p.url()), p.url());

// ── 3 · THE BREADCRUMB, MEASURED RATHER THAN ASSUMED ──────────────────────
await p.goto(`${BASE}/${T}/premises/units/new`, { waitUntil: "networkidle" });
await p.waitForTimeout(1500);
const crumb = await p.evaluate(() => {
  const c = document.querySelector("nav.crumbs");
  return c ? { text: c.innerText, links: [...c.querySelectorAll("a")].map((a) => a.getAttribute("href")) } : null;
});
ok("3 · (recorded) the breadcrumb offers NO link to the units list",
   crumb !== null && !crumb.links.some((h) => /\/premises\/units$/.test(h || "")),
   `crumbs=${JSON.stringify(crumb)}`);

console.log(R.join("\n"));
const fails = R.filter((r) => r.startsWith("FAIL")).length;
console.log(`\n${R.length - fails}/${R.length} PASS`);
await b.close();
process.exit(fails === 0 ? 0 : 1);
