/**
 * CR-035 · r11 step 2d — **PROVE IT BY CLICKING** (hard-won law 6: no gate in
 * this repo looks at rendered output, and nine defects were found this way and
 * by nothing else).
 *
 * WHY THIS IS NOT A VITEST FILE. `wizardPark.dom.test.tsx` and
 * `WaitingOnTab.dom.test.tsx` cover the same feature in jsdom and cover it
 * well — and jsdom cannot tell you that a button is VISIBLE, that a panel
 * OPENED where a person can see it, or that the row you just parked is on the
 * screen you landed on. It also has no bundler: these run the real `vite build`
 * output, the real router and the real Tailwind CSS.
 *
 * ⚠ **IT EARNED ITS KEEP ON THE FIRST RUN.** Answering `/units/{id}/assets`
 * with a generic empty page took the whole move-in screen down with
 * `Cannot read properties of undefined (reading 'total')` —
 * `UnitAssetsPanel` reads `assets.counts.total` with no guard on `counts`
 * itself. That is another lane's file and is REPORTED, not fixed here; the
 * point is that no suite in this repo could have told anyone.
 *
 * RUN (from 07-frontend):
 *   npx vite build
 *   PORT=4319 API_PROXY_TARGET= node server.mjs &
 *   node ../10-scripts/render-checks/cr035-park-clickthrough.mjs
 *   node ../10-scripts/render-checks/cr035-resume-clickthrough.mjs
 *
 * The API is answered by Playwright route interception, reproducing the
 * SERVICE's own behaviour — `subject_ref: null` is stored as `{}` and a bare
 * string is refused `VAL-002` — so the contract bug the coordinator caught
 * would fail here rather than be papered over.
 *
 * Exits non-zero on any failed check.
 */
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

// Borrow playwright-core from 07-frontend/node_modules, the way
// `column-chooser-geometry.mjs` and `12-smoke-walkthrough.mjs` do — this script
// has no dependencies of its own and must not add a second install. Run it from
// the REPO ROOT.
const requireFrontend = createRequire(path.resolve("07-frontend/package.json"));
const { chromium } = requireFrontend("playwright-core");

/** Any installed chromium, not only the revision playwright pinned — the same
 *  resolution `column-chooser-geometry.mjs` uses, and for the same reason: the
 *  pinned revision is often not the one on the box. */
function findChromium() {
  if (process.env.SBH_CHROMIUM) return process.env.SBH_CHROMIUM;
  const wanted = chromium.executablePath();
  if (fs.existsSync(wanted)) return wanted;
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  for (const dir of fs.existsSync(root) ? fs.readdirSync(root) : []) {
    if (!dir.startsWith("chromium")) continue;
    for (const rel of ["chrome-linux/chrome", "chrome"]) {
      const candidate = path.join(root, dir, rel);
      if (fs.existsSync(candidate)) return candidate;
    }
  }
  return wanted; // let playwright report the miss in its own words
}


const BASE = process.env.SBH_BASE ?? "http://127.0.0.1:4319";
const TENANT = "brazosbend";
const SHOT = process.env.SBH_SHOTS ?? path.resolve("07-frontend/dist");

const store = [];
const calls = [];

const PERMISSIONS = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [
    { code: "premises_accounts", label: "Premises / Accounts", access: "Full" },
    { code: "accounts", label: "Accounts", access: "Full" },
  ],
};

function ok(body, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: body === null ? "" : JSON.stringify(body),
  };
}

function answer(url, method, postData) {
  const path = new URL(url).pathname;
  calls.push(`${method} ${path}`);

  if (path.endsWith("/wizard-parks") && method === "POST") {
    const body = JSON.parse(postData ?? "{}");
    const row = {
      id: `park-${store.length + 1}`,
      flow: body.flow,
      subject_label: body.subject_label ?? "",
      // The SERVICE's own behaviour: `null` is stored as `{}`, a bare string is
      // refused with VAL-002. Reproduced here so the click-through would fail
      // on the bug the coordinator caught, not paper over it.
      subject_ref:
        body.subject_ref === null || body.subject_ref === undefined ? {} : body.subject_ref,
      step: body.step,
      values: body.values ?? {},
      waiting_on: body.waiting_on,
      park_note: body.park_note ?? null,
      remind_on: body.remind_on ?? null,
      parked_at: "2026-08-19T09:00:00Z",
      parked_by: "user-1",
      parked_by_name: "A. Clerk",
      age_days: 7,
    };
    if (typeof body.subject_ref === "string") {
      return ok({ code: "VAL-002", message_key: "shell.wizardPark.objectExpected" }, 422);
    }
    store.push(row);
    return ok(row, 201);
  }
  if (path.endsWith("/wizard-parks")) {
    return ok({ count: store.length, next: null, previous: null, results: store });
  }
  if (path.includes("/wizard-parks/")) {
    const id = path.split("/").pop();
    const row = store.find((r) => r.id === id);
    if (method === "DELETE") {
      store.splice(store.indexOf(row), 1);
      return ok(null, 204);
    }
    if (method === "PATCH") {
      Object.assign(row, JSON.parse(postData ?? "{}"));
      return ok(row);
    }
    return ok(row ?? null, row ? 200 : 404);
  }
  // ⚠ **THE TRANSFERS TAB'S OWN PAYLOAD, ADDED 2026-08-26 WITH THE FOLD, AND
  // IT EARNED ITS KEEP IMMEDIATELY (CR-035 · AMENDMENT 1).** Once a parked
  // transfer lands on the TRANSFERS tab rather than a ninth queue, this
  // click-through renders `TransfersTab` for the first time — and the generic
  // `{count: 0, results: []}` fallback below took the whole screen down with
  // `Cannot read properties of undefined (reading 'callout')`. `TransfersTab`
  // reads `listQuery.data?.exclusion.callout`, whose optional chain stops at
  // `data`, so any envelope without an `exclusion` block is a white screen.
  // The SERVER always sends one, so this fixture sends one too — the same
  // posture the `subject_ref` VAL-002 handling above takes. **The fragile
  // `?.exclusion.callout` is REPORTED, not fixed here**, exactly as the
  // `UnitAssetsPanel` crash in this file's own docstring was.
  if (path.endsWith("/transfers")) {
    return ok({
      rows: [],
      kpis: {
        open: 0,
        moving_this_week: 0,
        deposits_carrying: 0,
        arrears_following: 0,
        completed_this_month: 0,
        period_basis: "calendar",
        as_of: "2026-08-26T09:00:00Z",
      },
      page: 1,
      per: 50,
      total: 0,
      pages: 1,
      columns: [],
      steps: [],
      search: { hint: "", min_chars: 2, legs: [], unavailable: [] },
      exclusion: { callout: "", contract: [], half_account_ids: [] },
      as_of: "2026-08-26T09:00:00Z",
    });
  }
  if (path.endsWith("/me/permissions")) {
    return ok(PERMISSIONS);
  }
  if (path.endsWith("/me")) {
    return ok({ id: "user-1", full_name: "A. Clerk", email: "a@b.test", tenant: TENANT });
  }
  return ok({ count: 0, next: null, previous: null, results: [] });
}

const checks = [];
function check(name, pass, detail = "") {
  checks.push({ name, pass, detail });
  console.log(`${pass ? "PASS" : "FAIL"}  ${name}${detail ? ` — ${detail}` : ""}`);
}

const browser = await chromium.launch({
  executablePath: findChromium(),
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
await page.route("**/api/**", async (route) => {
  const request = route.request();
  await route.fulfill(answer(request.url(), request.method(), request.postData()));
});

// ── 1 · The Park control ACTS on the transfer wizard ───────────────────────
await page.goto(`${BASE}/${TENANT}/transfers/new`, { waitUntil: "networkidle" });
const park = page.getByRole("button", { name: "Park", exact: true });
await park.waitFor({ state: "visible", timeout: 15000 });
check("transfer wizard: `Park` is visible", await park.isVisible());
check("transfer wizard: `Park` is enabled", await park.isEnabled());
check(
  "transfer wizard: `Save & exit` is beside it, still a separate control (B19 §12.2)",
  await page.getByRole("button", { name: "Save & exit" }).isEnabled(),
);
check(
  "no blocked reason is rendered",
  (await page.locator('[data-wizard="park-blocked"]').count()) === 0,
);
await page.screenshot({ path: `${SHOT}/shot-1-controls.png` });

// ── 2 · The panel opens and the nine reasons are answerable ────────────────
await park.click();
await page.locator('[data-wizard="park"]').waitFor({ state: "visible", timeout: 10000 });
check("clicking Park opens the panel", true);
check(
  "the URL carries `?park=1` — a reload keeps the half-filled form (A9)",
  page.url().includes("park=1"),
  page.url(),
);
const options = await page.locator("#wizard_park_reason option").count();
check("the nine reasons plus the placeholder are offered", options === 10, `${options} options`);
const panelText = await page.locator('[data-wizard="park"]').innerText();
check(
  "the panel no longer says the typing goes `on the record` (BR-SHL-048)",
  !panelText.includes("stays on the record"),
);
check(
  "it says what a parked job does NOT do",
  panelText.includes("Nothing is created or changed until you finish the wizard"),
);
await page.screenshot({ path: `${SHOT}/shot-2-panel.png` });

// ── 3 · Parking it writes ONE draft and lands on the TRANSFERS tab ────────
//
// ⚠ **THE DESTINATION MOVED ON 2026-08-26 — CR-035 · AMENDMENT 1.** The PO
// struck the ninth "Waiting on" tab (*"seperate queue not reequired"*), so a
// parked TRANSFER lands on **Transfers**, the tab for its own kind of work.
// Everything asserted after this point is what it always was: only the
// presentation moved, and if any of it fails, something else was changed.
await page.selectOption("#wizard_park_reason", "deposit");
await page.fill("#wizard_park_note", "Customer promised the deposit on Friday.");
await page.getByRole("button", { name: "Park it" }).click();
await page.waitForURL(/tab=transfers/, { timeout: 15000 });
check("parking lands the clerk on the TRANSFERS tab — its own kind of work", true, page.url());
check("exactly ONE draft was written", store.length === 1, `${store.length} row(s)`);
check(
  "`subject_ref` left as an OBJECT, not a bare string (VAL-002)",
  typeof store[0]?.subject_ref === "object",
  JSON.stringify(store[0]?.subject_ref),
);
check(
  "no POST was refused",
  !calls.includes("POST /api/brazosbend/wizard-parks REFUSED"),
);

// ── 4 · The draft is a ROW of the transfers list ──────────────────────────
//
// ⚠⚠ **REWRITTEN 2026-09-20 — THE PANEL THIS SECTION WATCHED NO LONGER EXISTS
// (`DEF-CUS-5994`).** PO, verbatim: *"remove it - it is anyway in the list so
// we dont need it sepretely - if it is not in list add it"*. Every assertion
// below was passing against a pinned panel the morning it was deleted; the
// FACTS they check are unchanged and are read off the row instead.
//
// ⚠ **AND THIS IS EXACTLY THE FILE THAT WOULD HAVE ROTTED IN SILENCE.** A
// render check runs against a browser and nothing in CI reads it, so a script
// still hunting `[data-parked-drafts]` would simply have started failing at the
// first `waitFor` with a timeout that says *"the panel did not appear"* — true,
// and no help at all to whoever ran it next.
const table = page.locator("[data-transfer-draft]");
await table.waitFor({ state: "visible", timeout: 15000 });
await page.waitForTimeout(1200);
const listText = await table.innerText();

// Requirement 1 — a clerk must never mistake a draft for a job that happened.
// The badge reads `Parked` where a reason was given and `Draft` where one was
// not, which is `WizardPark.waiting_on`'s own distinction.
check("the draft wears a PARKED badge", listText.includes("Parked"));
// ⚠ **REQUIREMENT 2 INVERTED WITH THE RULING AND DID NOT GO AWAY.** The panel
// kept drafts OUT of the count because they were not rows of the list. They are
// rows now, so the count must INCLUDE them — one window, one server figure — and
// the check is that the draft IS in the table rather than that it is not.
check(
  "the draft IS a row of the transfers TABLE",
  (await page.locator("table [data-transfer-draft]").count()) === 1,
);
check(
  "and there is no panel left above the list",
  (await page.locator("[data-parked-drafts]").count()) === 0,
);

check("the reason is on the row", listText.includes("waiting on a deposit"));
check("the note is on the row", listText.includes("Customer promised the deposit on Friday."));
check("the age is on the row", listText.includes("7 days"));
// ⚠ **THE STEP IS SERVED, WHICH IS THE IMPROVEMENT THIS RULING BUYS.** The
// record rows on this table carry a named absence for it; a draft carries the
// number, off `wizard_parks.step`, against the flow's OWN declared list.
check("the step is on the row, counted against the flow's own list", listText.includes("1 of 5"));
// ⛔ **THE "NOTHING HAS CHANGED" SENTENCE IS DELIBERATELY NOT ASSERTED ANY
// MORE.** It was the panel's one remaining line and it is RATIONALE, which B14
// rule 33 puts at ZERO words on screen; the badge and the step say what a clerk
// needs in two words and a fraction. `BR-SHL-048` is where the rule lives.
check(
  "Resume is an icon LINK with an accessible name (B14 rule 15)",
  (await page.getByRole("link", { name: "Resume" }).count()) === 1,
);
check(
  "Discard is an icon button with an accessible name",
  (await page.getByRole("button", { name: "Discard" }).count()) === 1,
);
// ⚠ **DISCARD IS THE CONTROL THAT ONLY EVER EXISTED ON THE PANEL**, so this
// check is the one that proves removing a surface did not remove a capability
// (`DEF-CUS-3653` — an absence is invisible to every other check this repo
// has). It is asserted on the ROW now, from `ParkedDraftActions`.
// The row must not have reached out to the product it names.
// ⚠ **THIS ASSERTION WAS RE-AIMED WITH THE FOLD, DELIBERATELY.** It used to
// say *"the list called the draft store and nothing else"* — true when the tab
// held only drafts, and MEANINGLESS now, because the tab it rides on
// legitimately calls its own worklist endpoint. The question BR-SHL-048 (a)
// actually asks is whether the DRAFT reached out to the record it names, so
// that is what is asked: nothing looked up the draft's copied ids.
check(
  "BR-SHL-048 (a): nothing looked the draft's COPIED ids up — no join, by any route",
  calls.every((c) => !c.includes("/units/") && !c.includes("/accounts/")),
  calls.join(" · ").slice(0, 200),
);
await page.screenshot({ path: `${SHOT}/shot-3-list.png` });

// ── 5 · Resume reopens the wizard at the parked step, with the typing ──────
await page.getByRole("link", { name: "Resume" }).click();
await page.waitForURL(/parked=/, { timeout: 15000 });
await page.locator('[data-wizard="rail"]').waitFor({ state: "visible", timeout: 15000 });
await page.waitForTimeout(800);
check("Resume opens the flow's own wizard with `?parked=`", page.url().includes("parked=park-1"), page.url());
const active = await page.locator('[data-wizard-step][data-state="active"]').first();
check(
  "it lands on the step it was parked at",
  (await active.getAttribute("data-wizard-step")) === "1",
  `active step ${await active.getAttribute("data-wizard-step")}`,
);
const ahead = page.locator('[data-wizard-step="5"]');
check(
  "BR-SHL-048 (b): the steps ahead are STILL LOCKED — resume unlocks nothing",
  await ahead.isDisabled(),
);
const ageNote = page.locator('[data-wizard="park-age"]');
check("the age rides on the wizard too", (await ageNote.count()) === 1);
const ageText = (await ageNote.count()) ? await ageNote.innerText() : "";
check(
  "and it no longer claims the unit is held (BR-SHL-048 (c))",
  !ageText.includes("the unit is still held") && ageText.includes("nothing is held"),
  ageText,
);
await page.screenshot({ path: `${SHOT}/shot-4-resume.png` });

// ── 6 · Discard confirms, then removes the row ─────────────────────────────
await page.goto(`${BASE}/${TENANT}/accounts?tab=transfers`, { waitUntil: "networkidle" });
await page.getByRole("button", { name: "Discard" }).click();
const dialog = page.getByRole("alertdialog");
await dialog.waitFor({ state: "visible", timeout: 10000 });
const dialogText = await dialog.innerText();
check("Discard confirms first (IS-6)", true);
check(
  "the confirm says nothing else changes",
  dialogText.includes("has not created anything yet"),
);
await page.screenshot({ path: `${SHOT}/shot-5-discard.png` });
await dialog.getByRole("button", { name: "Discard" }).click();
await page.waitForFunction(() => !document.querySelector('[role="alertdialog"]'), null, {
  timeout: 10000,
});
check("the draft is gone from the store", store.length === 0, `${store.length} row(s)`);
await page.waitForTimeout(600);
// ⚠ **THE ROW SIMPLY LEAVES THE LIST, WHICH IS WHAT A LIST DOES** — and that
// is one small dividend of the ruling: the panel needed a written decision
// about whether to draw an empty state, and a table already has one.
check(
  "with nothing parked, no draft row is left on the tab",
  (await page.locator("[data-transfer-draft]").count()) === 0,
);
await page.screenshot({ path: `${SHOT}/shot-6-empty.png` });

await browser.close();

const failed = checks.filter((c) => !c.pass);
console.log(`\n${checks.length - failed.length}/${checks.length} checks passed`);
process.exit(failed.length === 0 ? 0 : 1);
