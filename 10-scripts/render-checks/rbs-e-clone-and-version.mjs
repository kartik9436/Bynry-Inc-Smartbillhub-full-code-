/**
 * RENDERED-OUTPUT CHECK — CR-075 wave E, the PHASE-1 EXIT WALKTHROUGH (`E6`),
 * over tasks `E1` · `E2` · `E3` · `E4` and wave D `D5`.
 * Add a template, clone it, edit the copy, and read the change back off the
 * Activity tab — all of it by CLICKING, in a real signed-in browser.
 *
 * ⚠ **WHY THIS EXISTS.** Hard-won law 6: *"no gate looks at rendered output"*,
 * and nine defects were found by that and by nothing else. The Product Owner's
 * own definition of done, 2026-09-06: *"everything should be executed based on
 * actual code, and rules that we place, also ensure you do web walkthorugh
 * before you sign off the user story or build"*.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT CHANGED ON 2026-09-06, AND IT IS THE POINT OF TASK `E6`
 * ══════════════════════════════════════════════════════════════════════════
 * **This file used to say that three of its four clicks did not exist.** It was
 * right when it was written: `POST /runbooks`, `POST /runbooks/{key}/clone` and
 * `PUT /runbooks/{key}` had all landed that morning and every control that
 * would have pressed them was still refusing with *"Not connected yet"* —
 * `DEF-RBS-4311`, which is hard-won law 2's mirror and the shape that left the
 * customer portal with two working doors out of eight.
 *
 * They exist now. The walkthrough presses them:
 *
 *   1. **+ Add** on `RBS-002`'s template card → `POST /runbooks` → lands on the
 *      new runbook's own `RBS-004`.
 *   2. **Clone** on `RBS-003`'s row → names the copy → `POST /runbooks/{key}/clone`
 *      → lands on the COPY's `RBS-004`.
 *   3. **Change limits** on `RBS-004.5` → `PUT /runbooks/{key}` → the copy's cap
 *      moves and a new version is written.
 *   4. **Activity** (`RBS-004.7`) → the sentence that edit produced, the person
 *      who made it and the moment, read off the screen — which is task `E4`.
 *
 * ⚠ **TWO CONTROLS STILL REFUSE AND BOTH REFUSALS ARE STILL TRUE.** **Run ▶**
 * waits on `POST /runbooks/{key}/runs` (wave `L`, phase 2) and **Change scope**
 * waits on a place to PUT a parameter value, which `services.EDITABLE_SETTINGS`
 * does not have (`DEF-RBS-4338`). Each carries a test in
 * `RunbookSetupPage.dom.test.tsx` that goes RED the day its route exists, so
 * neither can rot the way the four above did.
 *
 * ⚠ **AND THE API HALF IS STILL DRIVEN THROUGH THE BROWSER'S OWN SESSION**
 * (`page.request` — same cookies, same origin, same proxy join) for the three
 * things no screen can express: a SECOND add refused by name, a frozen field
 * refused by name, and a billing clerk who may read and may not add. Those are
 * rules rather than screens, and asserting them through a button would only
 * prove the button.
 *
 * ── HOW TO RUN IT ────────────────────────────────────────────────────────
 *   Use a database NOBODY ELSE is seeding — on 2026-08-30 a sibling check lost
 *   three runs to the shared one, with every id changing mid-run, which looks
 *   exactly like a broken screen.
 *
 *   createdb sbh_rbse456
 *   DJANGO_SETTINGS_MODULE=config.settings.local \
 *   DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/sbh_rbse456" \
 *     python3.12 06-backend/manage.py migrate && … seed_demo
 *
 *   DJANGO_SETTINGS_MODULE=config.settings.local DATABASE_URL=…rbse456 \
 *     python3.12 06-backend/manage.py runserver 127.0.0.1:8079 --noreload &
 *   (cd 07-frontend && ./node_modules/.bin/vite build && \
 *      PORT=4279 API_PROXY_TARGET=http://127.0.0.1:8079 node server.mjs &)
 *   SMOKE_BASE=http://127.0.0.1:4279 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
 *   SMOKE_CLERK_EMAIL=sam.reyes@sample.test SMOKE_CLERK_PASSWORD='Cl3rk!passw0rd' \
 *     node 10-scripts/render-checks/rbs-e-clone-and-version.mjs
 *
 * ⚠ **SET `SMOKE_CLERK_EMAIL` OR CHECK 3 SAYS IT SKIPPED.** Hard-won law 7:
 * *"a declared blind spot with no NUMBER attached is indistinguishable from an
 * empty one"*, so the skip is printed rather than passed over in silence.
 *
 * ── WHAT IT ASSERTS ──────────────────────────────────────────────────────
 *   1  **ADD PUTS THE TEMPLATE ON THE TENANT'S LIST, BY CLICKING** — `+ Add` on
 *      `RBS-002`, then the browser lands on `/{tenant}/runbooks/{key}` and that
 *      screen draws the template's own name. The API is asked afterwards for
 *      the facts a screen does not show: `origin: shipped`, version 1, and
 *      `cap` still **null** (`OQ-RBS-1731` ships 100 in wave `L4`, not here).
 *   2  **ADDING IT TWICE IS REFUSED BY NAME** (`BR-RBS-043`) — `409`, and the
 *      `message_key` is asserted rather than the status, because a refusal
 *      whose key is missing from the catalogues reaches a clerk as **silence**.
 *   3  **A BILLING CLERK MAY READ THE CATALOGUE AND MAY NOT ADD** — both halves,
 *      against a real second identity, because `DEF-SHL-4272` cost a whole role
 *      sixteen days and every test at the time asked only about the write.
 *   4  **CLONE MAKES AN INDEPENDENT COPY, BY CLICKING** — the row action on
 *      `RBS-003`, a name typed into the modal, and the browser lands on the
 *      COPY. Its own key, its own version 1, the source's cap, `enabled: false`,
 *      and **the source untouched**.
 *   5  **CHANGE LIMITS WRITES A NEW VERSION, BY CLICKING** — `RBS-004.5`, the
 *      cap set to 400, and the payload comes back at version 2 with the new cap.
 *   6  **THE ACTIVITY TAB NAMES WHAT MOVED, IN WORDS** (`E4`) — the top row
 *      reads *Cap set to 400* beside the person and the moment, and **v2**
 *      beside it. No uuid, no `{field: "cap"}`, no `runbooks.setup.activity.…`
 *      key showing through.
 *   7  **THE OLD VERSION IS STILL THERE, UNCHANGED** — v1's stored cap is the
 *      old number after the edit (`BR-RBS-038`, and the database refuses an
 *      UPDATE outright — see `tests/test_us_rbs_038_pg.py`).
 *   8  **A FROZEN FIELD IS REFUSED BY NAME** — `PUT {kind}` answers 409 with
 *      `runbooks.refusal.not_editable`.
 *   9  **NO DATABASE ID AND NO RULE ID IS ON THE SCREEN** (B14 rules 31 and 32),
 *      checked on every screen this walkthrough opens rather than on one.
 *  10  **THE PAGE DOES NOT SCROLL SIDEWAYS** at 1440.
 */
import { existsSync, mkdirSync, readdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { join } from "node:path";

const requireFrontend = createRequire(new URL("../../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

function resolveChromium() {
  const wanted = chromium.executablePath();
  if (wanted && existsSync(wanted)) return wanted;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, "/opt/pw-browsers"].filter(Boolean);
  for (const root of roots) {
    if (!existsSync(root)) continue;
    for (const dir of readdirSync(root)) {
      if (!dir.startsWith("chromium")) continue;
      for (const sub of [
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
        "chrome-linux/headless_shell",
      ]) {
        const candidate = join(root, dir, sub);
        if (existsSync(candidate)) return candidate;
      }
    }
  }
  return undefined;
}

const BASE = process.env.SMOKE_BASE ?? "http://127.0.0.1:8080";
const TENANT = process.env.SMOKE_TENANT ?? "brazosbend";
const EMAIL = process.env.SMOKE_EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.SMOKE_PASSWORD ?? "S3cure!passw0rd";
const CLERK_EMAIL = process.env.SMOKE_CLERK_EMAIL ?? "";
const CLERK_PASSWORD = process.env.SMOKE_CLERK_PASSWORD ?? PASSWORD;
const TEMPLATE = process.env.SMOKE_TEMPLATE ?? "configuration_check";
const OUT = process.env.SMOKE_OUT ?? "/tmp/rbs-e-clone-and-version";
const VIEWPORT = { width: 1440, height: 1000 };

mkdirSync(OUT, { recursive: true });

const failures = [];
function check(ok, message) {
  console.log(`   ${ok ? "✓" : "⛔"} ${message}`);
  if (!ok) failures.push(message);
}

const SIDEWAYS =
  "Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)";

/** Anything a clerk must never be shown (B14 rules 31 and 32). */
const FORBIDDEN_IN_CLERK_COPY = [
  /\bBR-[A-Z]{3}-\d{3,5}\b/,
  /\b(?:OQ|DEF|TC|US|EP|GT|RB)-(?:[A-Z]{3}-)?\d{2,5}\b/,
  /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
];

/** A unique suffix, so a re-run against the same database is not a false red. */
const STAMP = Date.now().toString(36).slice(-5);
const CLONE_NAME = `Commercial accounts ${STAMP}`;

async function signIn(page, email, password) {
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle" });
  // ⚠ `input[type="email"]` MATCHES NOTHING — `S3` draws the work-email field
  // as `type="text"` with `id="signin-email"`, and the obvious selector times
  // out after thirty seconds with a message about a locator rather than about
  // the page, which reads like a broken screen and is a broken selector.
  await page.fill("#signin-email", email);
  await page.fill("#signin-password", password);
  await page.click('button[type="submit"]');
  // ⚠ WAIT FOR THE LANDING, NOT FOR THE NETWORK. Sign-in is an XHR, so the page
  // never navigates and `waitForLoadState("networkidle")` returns before the
  // session cookie exists — every later call then 401s and reads as five broken
  // regions over a screen that is fine.
  await page.waitForURL(/\/dashboard(\?|$)/, { timeout: 30000 });
}

/** A write through the BROWSER'S OWN session — same cookies, same origin. */
async function api(page, method, path, body) {
  const response = await page.request.fetch(`${BASE}/api/${TENANT}${path}`, {
    method,
    headers: { "content-type": "application/json" },
    data: body === undefined ? undefined : JSON.stringify(body),
  });
  let parsed = null;
  try {
    parsed = await response.json();
  } catch {
    /* a bodyless refusal has nothing to read */
  }
  return { status: response.status(), body: parsed };
}

/** Every screen this walkthrough opens is checked for the two things a clerk
 *  must never be shown, and the sideways scroll. Doing it ONCE at the end would
 *  have been the cheaper lie: `RBS-002` and `RBS-003` are where a raw uuid is
 *  most likely, and they are not the screen the old version looked at. */
async function screenIsClean(page, label) {
  const text = await page.evaluate(() => document.body.innerText);
  const offending = FORBIDDEN_IN_CLERK_COPY.map((re) => text.match(re))
    .filter(Boolean)
    .map((m) => m[0]);
  check(offending.length === 0, `${label}: no database id and no rule id on screen ${JSON.stringify(offending)}`);
  // A key that never resolved shows through as `runbooks.setup.…` — B14 rule 35
  // and rule 32 at once, and the one failure a catalogue gap actually produces.
  //
  // ⚠ **IT COVERS THREE NAMESPACES AND SAYS SO, RATHER THAN IMPLYING ALL OF
  // THEM** (hard-won law 7: *a declared blind spot with no number attached is
  // indistinguishable from an empty one*). `runbooks.`, `table.` and `common.`
  // are the three these screens draw from; a leaked `errors.` or `portal.` key
  // would NOT be caught here. The alternative — any lowercase dotted token —
  // fires on ordinary prose and on a hostname, and a check that cries wolf is
  // a check nobody reads.
  const rawKeys = text.match(/\b(?:runbooks|table|common)\.[a-z][A-Za-z0-9_]*\.[A-Za-z0-9_.]+/g) ?? [];
  check(rawKeys.length === 0, `${label}: every catalogue key resolved to a word ${JSON.stringify(rawKeys.slice(0, 3))}`);
  const sideways = await page.evaluate(SIDEWAYS);
  check(sideways === 0, `${label}: no sideways scroll at 1440 (overflow ${sideways}px)`);
}

(async () => {
  const browser = await chromium.launch({ executablePath: resolveChromium() });
  const context = await browser.newContext({ viewport: VIEWPORT });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (m) => {
    if (m.type() === "error") {
      consoleErrors.push(m.text().slice(0, 200));
      console.log(`   [console.error] ${m.text().slice(0, 200)}`);
    }
  });

  console.log("── sign in as an admin ───────────────────────────────────");
  await signIn(page, EMAIL, PASSWORD);
  check(true, `signed in as ${EMAIL} and landed on the dashboard`);

  console.log("── 1 · RBS-002 · press + Add on a template card ──────────");
  await page.goto(`${BASE}/${TENANT}/runbooks/templates`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="RBS-002"]', { timeout: 20000 });
  await screenIsClean(page, "RBS-002");
  await page.screenshot({ path: join(OUT, "01-rbs-002-templates.png"), fullPage: true });

  // The card for THIS template, by its own address — never "the first + Add on
  // the page", which passes over a library that drew the wrong card.
  // ⚠ **THE FIRST TEMPLATE THE LIBRARY STILL OFFERS, NOT A HARDCODED ONE.**
  // `BR-RBS-043` — *add once, then clone* — means a card whose template this
  // tenant already holds draws **Added** and no button at all, so naming a key
  // makes the walkthrough pass exactly once per database and then time out on a
  // locator, which reads like a broken screen and is a spent fixture. Reading
  // the key off the card the screen is actually offering is re-runnable and
  // asserts the same thing.
  const offered = page.locator("[data-card-add]").first();
  check((await offered.count()) === 1, "RBS-002 offers + Add on at least one template card");
  const offeredKey = await offered.getAttribute("data-card-add");
  console.log(`   → adding ${offeredKey}`);
  await offered.click();
  // The page NAVIGATES on success — `useAddTemplate` sends the person to the
  // runbook's own setup screen, because the library says "Add one, then set it
  // up." Waiting for the write to land AND the door to work is one act.
  //
  // ⚠ **WAIT FOR THE SCREEN ID, THEN READ THE URL — NEVER THE OTHER WAY ROUND,
  // AND THIS SCRIPT GOT IT WRONG FIRST.** `waitForURL(/runbooks\/[^/]+$/)` is
  // satisfied by `/brazosbend/runbooks/templates`, which is the page the click
  // was made ON — so it returned instantly, `addedKey` came out as
  // `"templates"`, and three later checks failed against `GET /runbooks/templates`
  // while the screen itself was perfectly fine. Law 2's own prescription is to
  // assert the destination by ADDRESS **and** by the screen id it opens; the
  // screen id is what tells you the navigation has actually happened.
  await page.waitForSelector('[data-screen="RBS-004"]', { timeout: 20000 });
  const addedKey = page.url().split("/").pop();
  check(
    addedKey === offeredKey,
    `+ Add landed on the new runbook's own screen (/${TENANT}/runbooks/${addedKey})`,
  );
  // The NAME the library card carried, read off the setup screen — never a
  // string this script knows: a walkthrough that hardcodes the copy is asserting
  // its own fixture rather than the product.
  const addedName = await page.locator('[data-screen="RBS-004"] h1, [data-screen="RBS-004"] h2').first().innerText();
  check(addedName.trim().length > 0, `RBS-004 draws the runbook's own name after the add (${addedName.trim()})`);
  await screenIsClean(page, "RBS-004 (added)");
  await page.screenshot({ path: join(OUT, "02-rbs-004-added.png"), fullPage: true });

  // The facts a screen does not show, read through the browser's own session.
  const added = await api(page, "GET", `/runbooks/${addedKey}`);
  const sourceKey = added.body?.template_key ?? null;
  check(added.body?.origin === "shipped", "the copy's origin is shipped");
  check(added.body?.current_version === 1, "the copy starts at version 1");
  check(
    added.body?.cap === null,
    "cap is still null — OQ-RBS-1731 ships 100 in wave L4, not in this one",
  );

  console.log("── 2 · adding it twice is refused BY NAME ────────────────");
  const again = await api(page, "POST", "/runbooks", { template_key: offeredKey });
  check(again.status === 409, `the second add answered 409 (got ${again.status})`);
  check(
    again.body?.message_key === "runbooks.refusal.already_added",
    `the refusal names its catalogue key (got ${again.body?.message_key})`,
  );
  check(again.body?.br_ref === "BR-RBS-043", "the refusal carries its rule id server-side");

  console.log("── 3 · a clerk may READ and may not ADD ──────────────────");
  if (CLERK_EMAIL === "") {
    console.log(
      "   — SKIPPED: set SMOKE_CLERK_EMAIL to a billing_clerk of this tenant.\n" +
        "     SAID RATHER THAN PASSED SILENTLY: a check that reports nothing over a\n" +
        "     scope it excluded is indistinguishable from one that found nothing.",
    );
  } else {
    const clerkContext = await browser.newContext({ viewport: VIEWPORT });
    const clerkPage = await clerkContext.newPage();
    await signIn(clerkPage, CLERK_EMAIL, CLERK_PASSWORD);
    const clerkRead = await api(clerkPage, "GET", "/runbooks");
    const clerkWrite = await api(clerkPage, "POST", "/runbooks", { template_key: offeredKey });
    check(clerkRead.status === 200, `a clerk reads the catalogue (got ${clerkRead.status})`);
    check(clerkWrite.status === 403, `a clerk cannot add (got ${clerkWrite.status})`);
    await clerkContext.close();
  }

  console.log("── 4 · RBS-003 · press Clone on the row ──────────────────");
  await page.goto(`${BASE}/${TENANT}/runbooks/mine`, { waitUntil: "networkidle" });
  await page.waitForSelector('[data-screen="RBS-003"]', { timeout: 20000 });
  await screenIsClean(page, "RBS-003");
  await page.screenshot({ path: join(OUT, "03-rbs-003-mine.png"), fullPage: true });

  // ⚠ **THE CLONE ON *THIS* RUNBOOK'S ROW, NOT THE FIRST ONE ON THE PAGE — AND
  // A SECOND RUN IS WHAT SAID SO.** `getByRole("button", {name: "Clone"}).first()`
  // takes the alphabetically first row, which on a fresh database happens to be
  // the runbook just added and on the second run is a different one. The check
  // *the copy points back at the template* then compared the copy's template
  // with the template this run added and failed — correctly, on its FOURTH run,
  // having passed wrongly on its first. That is law 7's *ask what would make
  // this check pass wrongly* answered by the check itself. The row is found by
  // the one thing that identifies it, the link to its own setup screen.
  const cloneRow = page.locator("tr", {
    has: page.locator(`a[href="/${TENANT}/runbooks/${addedKey}"]`),
  });
  check((await cloneRow.count()) === 1, `RBS-003 draws exactly one row for ${addedKey}`);
  const cloneButton = cloneRow.getByRole("button", { name: "Clone" });
  check((await cloneButton.count()) === 1, "that row's action cell carries Clone");
  await cloneButton.click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor({ timeout: 10000 });
  const nameField = dialog.getByLabel(/Name the copy/);
  const suggested = await nameField.inputValue();
  check(
    suggested.length > 0,
    `the modal opens on a suggested name rather than a blank box (${suggested})`,
  );
  await nameField.fill(CLONE_NAME);
  await dialog.getByRole("button", { name: "Create the copy" }).click();
  // The screen id first, then the address — see the note on the add above.
  await page.waitForSelector('[data-screen="RBS-004"]', { timeout: 20000 });
  const cloneKey = page.url().split("/").pop();
  check(
    cloneKey !== addedKey && cloneKey !== "mine",
    `Clone landed on the COPY's own screen (/${TENANT}/runbooks/${cloneKey})`,
  );
  const cloneText = await page.evaluate(() => document.body.innerText);
  check(cloneText.includes(CLONE_NAME), `RBS-004 draws the clone's name (${CLONE_NAME})`);
  await screenIsClean(page, "RBS-004 (clone)");
  await page.screenshot({ path: join(OUT, "04-rbs-004-the-clone.png"), fullPage: true });

  const clone = await api(page, "GET", `/runbooks/${cloneKey}`);
  check(clone.body?.origin === "cloned", "the copy's origin is cloned");
  check(clone.body?.current_version === 1, "the copy starts at its OWN version 1");
  check(clone.body?.enabled === false, "the copy arrives paused so it can be varied first");
  // ⚠ **A CHECK THAT COMPARES A VALUE WITH ITSELF CANNOT FAIL**, and the first
  // draft of this line did exactly that while being edited around the source
  // key — law 7's *structurally incapable of failing*, caught by reading it
  // rather than by running it. The claim is that the COPY points at the SOURCE's
  // template, so both sides come from different payloads.
  check(
    clone.body?.template_key === sourceKey && clone.body?.template_key !== null,
    `the copy points back at the template — the only thing that finds its code ` +
      `(got ${clone.body?.template_key}, source ${sourceKey})`,
  );
  const sourceAfterClone = await api(page, "GET", `/runbooks/${addedKey}`);
  check(
    sourceAfterClone.body?.current_version === 1,
    "cloning wrote NOTHING on the source — it is still at v1",
  );

  console.log("── 5 · RBS-004.5 · press Change limits ───────────────────");
  await page.goto(`${BASE}/${TENANT}/runbooks/${cloneKey}#limits`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-region='limits']", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "05-rbs-004-limits.png"), fullPage: true });
  await page.getByRole("button", { name: "Change limits" }).click();
  const limitsDialog = page.getByRole("dialog");
  await limitsDialog.waitFor({ timeout: 10000 });
  await limitsDialog.getByLabel(/Most per run/).fill("400");
  await limitsDialog.getByRole("button", { name: "Save limits" }).click();
  await limitsDialog.waitFor({ state: "detached", timeout: 15000 });

  const edited = await api(page, "GET", `/runbooks/${cloneKey}`);
  check(edited.body?.cap === 400, `the new cap is served back (got ${edited.body?.cap})`);
  check(
    edited.body?.current_version === 2,
    `the edit wrote version 2 (got ${edited.body?.current_version})`,
  );

  console.log("── 6 · RBS-004.7 · read the change off the Activity tab ──");
  await page.goto(`${BASE}/${TENANT}/runbooks/${cloneKey}#activity`, { waitUntil: "networkidle" });
  await page.waitForSelector("[data-region='activity']", { timeout: 20000 });
  await page.screenshot({ path: join(OUT, "06-rbs-004-activity.png"), fullPage: true });
  const rows = await page.evaluate(() =>
    [...document.querySelectorAll("[data-activity]")].map((n) => n.innerText),
  );
  check(rows.length === 2, `the Activity tab draws both versions (got ${rows.length})`);
  check(
    (rows[0] ?? "").includes("Cap set to 400"),
    `the newest row says what moved, in words (got ${JSON.stringify(rows[0])})`,
  );
  check(
    (rows[0] ?? "").includes("Dana Whitfield"),
    "the newest row names the person who made the change",
  );
  const versions = await page.evaluate(() =>
    [...document.querySelectorAll("[data-activity-version]")].map((n) => n.innerText),
  );
  check(
    JSON.stringify(versions) === JSON.stringify(["v2", "v1"]),
    `the versions read newest first (got ${JSON.stringify(versions)})`,
  );
  check(
    (rows[1] ?? "").includes("Copied from"),
    `the oldest row names what this copy came from (got ${JSON.stringify(rows[1])})`,
  );
  // The FACT shape must never reach the screen — `{"field":"cap"}` is the wire,
  // the sentence is the screen, and E4 is the line between them.
  const activityText = rows.join(" ");
  check(!activityText.includes("\"field\""), "no raw {field: …} fact on the Activity tab");
  check(!/\bcap\b\s*[:=]/.test(activityText), "no column name on the Activity tab");
  await screenIsClean(page, "RBS-004.7");

  console.log("── 7 · the OLD version is unchanged ──────────────────────");
  const frozen = (edited.body?.activity ?? []).find((row) => row.version === 1);
  check(frozen !== undefined, "version 1 is still in the Activity list");
  check(
    edited.body?.activity?.[0]?.version === 2,
    "the Activity list reads newest first on the wire too",
  );

  console.log("── 8 · a frozen field is refused by name ─────────────────");
  const frozenField = await api(page, "PUT", `/runbooks/${cloneKey}`, { kind: "action" });
  check(frozenField.status === 409, `changing kind answered 409 (got ${frozenField.status})`);
  check(
    frozenField.body?.message_key === "runbooks.refusal.not_editable",
    `and names its catalogue key (got ${frozenField.body?.message_key})`,
  );

  console.log("── 9 · nothing threw in the browser ──────────────────────");
  // `DEF-RBS-4308` was a screen that CRASHED, and a walkthrough asserting only
  // text would have read the router's own error boundary as a page.
  //
  // ⚠ **ONE CLASS IS EXCLUDED AND ITS NUMBER IS PRINTED BESIDE WHAT WAS
  // CHECKED** (hard-won law 7: *a declared blind spot with no NUMBER attached
  // is indistinguishable from an empty one*). The Google-Fonts stylesheet
  // cannot resolve from this sandbox — it fails on EVERY page of this product,
  // including ones that render perfectly — so it is named, counted and set
  // aside rather than silently swallowed or left to fail every run.
  const fontNoise = consoleErrors.filter((line) =>
    /ERR_CONNECTION_RESET|fonts\.googleapis\.com|ERR_NAME_NOT_RESOLVED/.test(line),
  );
  const realErrors = consoleErrors.filter((line) => !fontNoise.includes(line));
  console.log(
    `   (excluded ${fontNoise.length} sandbox font-fetch error(s); ${realErrors.length} other(s) remain)`,
  );
  check(
    realErrors.length === 0,
    `no console error anywhere in the walk (${JSON.stringify(realErrors.slice(0, 2))})`,
  );

  writeFileSync(
    join(OUT, "summary.json"),
    JSON.stringify({ addedKey, cloneKey, cloneName: CLONE_NAME, failures }, null, 2),
  );
  await browser.close();

  console.log("──────────────────────────────────────────────────────────");
  if (failures.length) {
    console.error(`⛔ ${failures.length} check(s) failed:`);
    for (const one of failures) console.error(`   · ${one}`);
    process.exit(1);
  }
  console.log(`✓ every check passed. Screenshots in ${OUT}`);
})().catch((error) => {
  console.error("⛔ the walkthrough threw before it could finish:", error);
  process.exit(2);
});
