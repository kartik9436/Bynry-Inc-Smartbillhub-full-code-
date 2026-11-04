// ── Trace ──────────────────────────────────────────────
// Change:  the PO put `SR-26-0010` beside the Accounts blueprint on 2026-09-19
//          and ruled the request DETAIL page against its drawing — decision log,
//          *"THE REQUEST DETAIL PAGE AGAINST ITS DRAWING"*. Nine rulings, an
//          eighteen-row removal list approved whole (*"this is correct"*), and
//          two deliberate divergences.
// Rules:   B14 rule 42 (a screen is built from the drawing AS AN IMAGE) ·
//          rule 41 (the product UI matches the blueprint) · rule 38 (where a
//          drawing and our UI rules disagree about how a FORM is built, the UI
//          rules win) · rule 33 (on-screen text capped by what it is for) ·
//          rule 32 (a screen has a description budget) · rule 31 (no database
//          id is ever the visible value of a field) · `DEF-CUS-5872`.
// ───────────────────────────────────────────────────────
//
// ⚠ **THIS IS THE ONLY KIND OF CHECK IN THIS REPOSITORY THAT READS RENDERED
// OUTPUT** (hard-won law 6). No gate looks at a screen. Every one of the
// removals this walk asserts — a card that is gone, a sentence that is gone, a
// value that moved to the right-hand edge — is invisible to `tsc`, to every
// vitest case that asserts markup it was handed, and to all 18 gates.
//
// **WHAT IT PROVES, AND WHY EACH ONE NEEDS A BROWSER:**
//
//   1. **The left column is a definition list and not a stack of cards.** The
//      PO's words were *"label left, value right, a hairline between rows, no
//      box"*. Three of those four are COMPUTED STYLE — `text-align`, the
//      hairline's width, the absence of a background — and a unit test reading
//      a markup string cannot see any of them. This reads them off the live
//      element.
//   2. **The right rail is FEES ONLY.** A divergence from the drawing on a PO
//      instruction, so the walk asserts the two removed blocks are ABSENT —
//      the assertion that goes red if a later lane "corrects" the rail back.
//   3. **A broken document cannot read `Verified`.** `DEF-CUS-5872`: six seeded
//      rows point at a file that does not exist and four read `verified`. This
//      opens a real request against real PostgreSQL and reads the chip.
//   4. **The history's WHO column carries a NAME.** B14 rule 31 forbids the id,
//      and the fix was on the SERVER — so only a walk against a running server
//      proves it, and the same walk proves no UUID reached the page.
//   5. **The arrears search is inside the Approve dialog.** It is the only
//      control that sets `search_done`, and without it NO request in the
//      product can be approved. A unit test proves the component; this proves
//      the door on the running screen.
//
// ── HOW TO RUN IT ───────────────────────────────────────────────────────────
//   (cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
//      DATABASE_URL=postgres://sbh:...@127.0.0.1:5432/sbh?sslmode=disable \
//      JOBS_EAGER=false python3 manage.py runserver 127.0.0.1:8117 --noreload)
//   (cd 07-frontend && npx vite build && PORT=8137 \
//      API_PROXY_TARGET=http://127.0.0.1:8117 node server.mjs)
//   REQUEST=<uuid> node 10-scripts/po20260919_request_detail_drawing_walkthrough.mjs
//
// ⚠ **EVERY WAIT CARRIES A HARD TIMEOUT AND THE BROWSER CLOSES IN A `finally`**
// — `DEF-GOV-5877`, filed the same day: seven lanes sat blocked for up to ten
// hours on background runs that never returned and nothing noticed.
const { existsSync, readdirSync } = await import("node:fs");
const { createRequire } = await import("node:module");
const { join } = await import("node:path");

const requireFrontend = createRequire(new URL("../07-frontend/package.json", import.meta.url));
const { chromium } = requireFrontend("playwright-core");

const BASE = process.env.BASE ?? "http://127.0.0.1:8137";
const TENANT = process.env.TENANT ?? "brazosbend";
const EMAIL = process.env.EMAIL ?? "dana@brazosbendutilities.com";
const PASSWORD = process.env.PASSWORD ?? "S3cure!passw0rd";
const REQUEST = process.env.REQUEST;
const STEP_MS = Number(process.env.STEP_MS ?? 15000);

if (!REQUEST) {
  console.error("REQUEST=<service request uuid> is required");
  process.exit(2);
}

function resolveChromium() {
  const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? "/opt/pw-browsers";
  if (!existsSync(root)) return undefined;
  const dir = readdirSync(root).find((n) => n.startsWith("chromium-"));
  return dir ? join(root, dir, "chrome-linux", "chrome") : undefined;
}

// ⚠⚠ **THE COPY IS READ FROM THE CATALOGUE, AND THREE CHECKS HERE COULD NOT
// FAIL UNTIL IT WAS.** Run against a build from the pinned tip, *"the three
// rationale paragraphs are gone"*, *"the `Who acted is not named yet` note is
// gone"* and the append-only check all PASSED — over a screen that was still
// drawing every one of them. The checks looked for hand-typed fragments
// (*"does not stop the request being created"*) and the catalogue says
// something slightly different (*"never stops a request being created"*), so
// the substring was never going to be found on any screen, correct or not.
// That is hard-won law 7's *structurally incapable of failing*, and the only
// thing that found it was running the walk RED and reading the passes.
const CATALOGUE = JSON.parse(
  await (await import("node:fs/promises")).readFile(
    new URL("../07-frontend/src/i18n/locales/en.json", import.meta.url),
    "utf-8",
  ),
);
const say = (key) => {
  const value = CATALOGUE[key];
  if (value === undefined) throw new Error(`no such catalogue key: ${key}`);
  return value;
};

let pass = 0;
let fail = 0;
const check = (name, ok, detail = "") => {
  if (ok) {
    pass += 1;
    console.log(`PASS  ${name}${detail ? ` — ${detail}` : ""}`);
  } else {
    fail += 1;
    console.log(`FAIL  ${name}${detail ? ` — ${detail}` : ""}`);
  }
};

const browser = await chromium.launch({ executablePath: resolveChromium(), headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.setDefaultTimeout(STEP_MS);

  // ── sign in ──────────────────────────────────────────────────────────────
  await page.goto(`${BASE}/${TENANT}/signin`, { waitUntil: "networkidle", timeout: STEP_MS });
  await page.fill("#signin-email", EMAIL);
  await page.fill("#signin-password", PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL(`**/${TENANT}/dashboard`, { timeout: STEP_MS });

  // ══ 1 · THE APPLICANT TAB IS THE DRAWN DEFINITION LIST ═══════════════════
  await page.goto(`${BASE}/${TENANT}/requests/${REQUEST}`, {
    waitUntil: "networkidle",
    timeout: STEP_MS,
  });
  await page.waitForSelector('[data-tab-body="applicant"]', { timeout: STEP_MS });

  for (const name of ["what-they-asked-for", "who-is-asking", "the-address-they-gave"]) {
    check(
      `the drawn section "${name}" is on the Applicant tab`,
      (await page.locator(`[data-panel-name="${name}"]`).count()) === 1,
    );
  }

  const rows = page.locator("[data-drawn-row]");
  const rowCount = await rows.count();
  check("the left column is built from drawn rows", rowCount > 5, `${rowCount} rows`);

  // ⚠⚠ **EVERY STYLE CHECK BELOW IS SKIPPED — LOUDLY — WHEN THERE IS NO ROW TO
  // READ, AND THE FIRST DRAFT CRASHED INSTEAD.** Run against a build from the
  // pinned tip, `rows.first().evaluate(…)` threw a 15-second Playwright
  // timeout and the walk DIED after four lines, so the red proof reported four
  // results out of twenty-eight and named none of the real differences. A
  // check whose output cannot distinguish pass from fail to a READER is worse
  // than no check (hard-won law 7, habit 3) — and a RED proof that stops at
  // the first failure is exactly that. Each skipped check is counted as a
  // FAIL, never passed over, because an absent row means the drawn list is
  // absent.
  const SKIPPED = "no drawn row on the page to read";
  if (rowCount === 0) {
    for (const name of [
      "the VALUE is right-aligned",
      "the LABEL is not",
      "there is a hairline under the row",
      "the label sits at the left edge and the value at the right",
      "the drawn rows are NOT inside a card",
    ]) {
      check(name, false, SKIPPED);
    }
  }
  const shape = rowCount === 0 ? null : await rows.first().evaluate((row) => {
    const label = row.firstElementChild;
    const value = row.lastElementChild;
    const cs = getComputedStyle(row);
    const vs = getComputedStyle(value);
    const ls = getComputedStyle(label);
    return {
      valueAlign: vs.textAlign,
      labelAlign: ls.textAlign,
      hairline: cs.borderBottomWidth,
      rowBackground: cs.backgroundColor,
      labelLeft: label.getBoundingClientRect().left,
      valueRight: value.getBoundingClientRect().right,
      rowRight: row.getBoundingClientRect().right,
      rowLeft: row.getBoundingClientRect().left,
    };
  });
  if (shape !== null) {
  check("the VALUE is right-aligned", shape.valueAlign === "right", shape.valueAlign);
  check("the LABEL is not", shape.labelAlign !== "right", shape.labelAlign);
  check(
    "there is a hairline under the row",
    parseFloat(shape.hairline) > 0 && parseFloat(shape.hairline) <= 2,
    `${shape.hairline}`,
  );
  check(
    "the label sits at the left edge and the value at the right",
    Math.abs(shape.labelLeft - shape.rowLeft) < 2 && Math.abs(shape.valueRight - shape.rowRight) < 2,
    `label ${Math.round(shape.labelLeft - shape.rowLeft)}px from left, value ${Math.round(shape.rowRight - shape.valueRight)}px from right`,
  );
  // "no box" — the row is not inside a Panel card.
  const inCard = await rows
    .first()
    .evaluate((row) => row.closest("[data-panel]") !== null);
  check("the drawn rows are NOT inside a card", inCard === false);
  }

  // ══ 2 · WHAT THE REMOVAL LIST TOOK OFF THIS PAGE ═════════════════════════
  const body = (await page.locator('[data-tab-body="applicant"]').innerText()).trim();
  check(
    "`Not supplied` is gone from this page",
    !body.includes(say("customers.serviceRequest.notSupplied")),
  );
  check(
    "an absence is an em dash",
    (await page.locator('[data-tab-body="applicant"] [data-absence="dash"]').count()) > 0,
  );
  check(
    "the `Acting for` row is gone",
    !body.includes(say("customers.serviceRequest.applicant.actingFor")) &&
      !body.includes(say("customers.serviceRequest.applicant.actingForAbsent")),
  );
  check(
    "the Customer match CARD is gone",
    (await page.locator('[data-panel-name="customer-match"]').count()) === 0,
  );
  check(
    "the customer match is ONE row",
    (await page.locator('[data-drawn-row="customer-match"]').count()) === 1,
  );
  check(
    "the arrears search (No match, `record-search`) is NOT on the Applicant tab",
    (await page.locator('[data-tab-body="applicant"] [data-action="record-search"]').count()) === 0,
  );

  // ══ 3 · THE RIGHT RAIL IS FEES ONLY ══════════════════════════════════════
  check("Fees is in the rail", (await page.locator('[data-panel-name="fees"]').count()) === 1);
  for (const gone of ["documents-summary", "history-summary"]) {
    check(
      `the rail does NOT carry "${gone}" (PO divergence from the drawing)`,
      (await page.locator(`[data-panel-name="${gone}"]`).count()) === 0,
    );
  }

  // ══ 4 · THE DOCUMENTS TAB IS THE DRAWN TABLE ═════════════════════════════
  await page.goto(`${BASE}/${TENANT}/requests/${REQUEST}?tab=documents`, {
    waitUntil: "networkidle",
    timeout: STEP_MS,
  });
  await page.waitForSelector("[data-panel]", { timeout: STEP_MS });
  // ⚠ **COMPARED CASE-INSENSITIVELY, AND THAT IS NOT A LOOSENING.** The
  // `data-table` style uppercases its headers, so `innerText` answers `WHEN`
  // where the catalogue holds `When`. A first draft compared the raw strings
  // and went red over a screen that was correct — hard-won law 7's check that
  // fails wrongly, which is worse than no check because it is trusted.
  const heads = (list) => list.map((h) => h.trim().toLowerCase());
  const docHeads = heads(await page.locator("table.data-table thead th").allInnerTexts());
  check(
    "the drawn columns are Document · File · State",
    docHeads[0] === "document" && docHeads[1] === "file" && docHeads[2] === "state",
    docHeads.join(" · "),
  );
  const docsText = (await page.locator("[data-panel]").first().innerText()).trim();
  check(
    "the three rationale paragraphs are gone",
    !docsText.includes(say("customers.serviceRequest.documents.gateCreation")) &&
      !docsText.includes(say("customers.serviceRequest.documents.checklistEmpty")),
  );
  // ⛔ `DEF-CUS-5872` — a row whose file does not exist may not read `Verified`.
  const broken = page.locator('tr[data-file-present="false"]').first();
  if ((await broken.count()) > 0) {
    const cells = await broken.locator("td").allInnerTexts();
    check(
      "a document with no real file shows a dash, never a file name",
      cells[1].trim() === "—",
      `file cell = ${JSON.stringify(cells[1].trim())}`,
    );
    check(
      "…and reads `Nothing attached`, whatever its state column says",
      cells[2].trim() === "Nothing attached",
      `state chip = ${JSON.stringify(cells[2].trim())}`,
    );
  } else {
    check("a row with no real file was on this request to read", false, "none found — DEF-CUS-5872 cannot be proved here");
  }

  // ══ 5 · THE HISTORY TAB IS THE DRAWN WHEN · WHAT · WHO ═══════════════════
  await page.goto(`${BASE}/${TENANT}/requests/${REQUEST}?tab=history`, {
    waitUntil: "networkidle",
    timeout: STEP_MS,
  });
  await page.waitForSelector("[data-panel]", { timeout: STEP_MS });
  const histHeads = heads(await page.locator("table.data-table thead th").allInnerTexts());
  check(
    "the drawn columns are When · What · Who",
    histHeads[0] === "when" && histHeads[1] === "what" && histHeads[2] === "who",
    histHeads.join(" · "),
  );
  const named = await page.locator('td[data-actor-named="true"]').count();
  check("at least one row names WHO acted", named > 0, `${named} named rows`);
  const histText = (await page.locator("table.data-table").count()) === 0
    ? ""
    : await page.locator("table.data-table").first().innerText();
  check(
    "no UUID reached the WHO column (B14 rule 31)",
    !/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}/i.test(histText),
  );
  const tabText = await page.locator("[data-panel]").first().innerText();
  check(
    "the `Who acted is not named yet` note is gone",
    !tabText.includes(say("customers.serviceRequest.history.actorNotNamed")),
  );
  check(
    "the append-only sentence is gone",
    !tabText.includes(say("customers.serviceRequest.history.appendOnly")),
  );

  // ══ 6 · THE ARREARS SEARCH IS INSIDE THE APPROVE DIALOG ══════════════════
  await page.goto(`${BASE}/${TENANT}/requests/${REQUEST}`, {
    waitUntil: "networkidle",
    timeout: STEP_MS,
  });
  await page.waitForSelector('[data-decision-action="approve"]', { timeout: STEP_MS });
  await page.click('[data-decision-action="approve"]');
  await page.waitForSelector('[role="dialog"]', { timeout: STEP_MS });
  // 2026-10-11: the kind is the kit's SegmentedControl, not radios.
  const firstOutcome = page
    .locator('[role="dialog"] [data-segmented="approve-kind"] [data-segment]:not([disabled])')
    .first();
  if ((await firstOutcome.count()) > 0) {
    await firstOutcome.click();
    await page.waitForTimeout(400);
  }
  // ⚠ PO 2026-10-11, option B: the Arrears row no longer carries a button.
  // It POINTS at *Search customer* ("Search customer below."), and the search
  // there answers with *No match* (`data-action="record-search"`) or *Link*.
  const pointer = page.locator('[role="dialog"] [data-approve-arrears-search]');
  const pointerText = (await pointer.count()) > 0 ? ((await pointer.first().textContent()) ?? "").trim() : null;
  if (pointerText === null) {
    const dialog = await page.locator('[role="dialog"]').innerText();
    check(
      "the Approve dialog carries the arrears search where it blocks",
      !dialog.includes("held an account before"),
      "this request is already searched, so the condition is clear",
    );
  } else {
    check(
      "the Arrears row points at Search customer, with no button of its own",
      pointerText === "Search customer below." &&
        (await page.locator('[role="dialog"] [data-approve-arrears-search] button').count()) === 0,
      pointerText,
    );
    check(
      "No match is not offered before a search has answered",
      (await page.locator('[role="dialog"] [data-action="record-search"]').count()) === 0,
    );
    await page.click('[role="dialog"] [data-customer-search]');
    const noMatch = page.locator('[role="dialog"] [data-action="record-search"]');
    await noMatch.waitFor({ timeout: STEP_MS }).catch(() => {});
    check(
      "after Search customer answers, No match is offered (not pressed — this walk writes nothing)",
      (await noMatch.count()) === 1 && ((await noMatch.textContent()) ?? "").trim() === "No match",
      ((await noMatch.textContent().catch(() => "")) ?? "").trim(),
    );
  }

  console.log(`\n${pass} PASS / ${fail} FAIL`);
  process.exitCode = fail === 0 ? 0 : 1;
} finally {
  // ⚠ `DEF-GOV-5877` — the browser closes whatever happened above.
  await browser.close();
}
