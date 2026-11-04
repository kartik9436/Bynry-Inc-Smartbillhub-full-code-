// ── Trace ──────────────────────────────────────────────
// Change:  CR-005 (12-governance/11-change-requests.md) — SET-08 Numbering,
//          recorded there as **BUILT, NOT CLOSED**: *"Status:
//          BUILT-NOT-PROVEN. Every part of r11 step 2 is done except (d):
//          there has been no browser walkthrough"*.
// Story:   US-TEN-012 (EP-TEN-08) · Screens: S8 → Settings → Configure →
//          Numbering (r10 SET-08)
// Rules:   BR-TEN-035 (format grammar: literals + {YYYY}/{YY}/{MM}/{DD} +
//          EXACTLY ONE zero-padded counter; ≤24 chars; pad ≤8; restart period;
//          overflow widens and warns; duplicate prefixes warn but never block;
//          a plain prefix-free option in every category; format changes are
//          FUTURE-ONLY and issued numbers are never renumbered; next-number
//          edits are FORWARD-ONLY) · BR-SHL-025 (a control that cannot work
//          stays VISIBLE and DISABLED WITH ITS REASON — never hidden) ·
//          BR-SHL-020 (plain-language failure, never a raw key) ·
//          BR-SHL-032 (the confirm names the action) · BR-TEN-016 (audit) ·
//          BR-TEN-043 (the issue date is an input, never the wall clock)
// B14:     rule 5 (two button sizes) · 8 (5+ options searchable) · 15 (row
//          actions are icons with tooltips) · 16 (pagination — N/A, argued
//          below) · 18 (descriptions at 80%) · 20 (one table type)
// Defect:  DEF-196 · DEF-197 · DEF-198 · DEF-199 (this lane; see below)
// ───────────────────────────────────────────────────────
//
// **THE PO'S BAR, VERBATIM, IS THE ONLY REASON THIS FILE EXISTS:**
// *"we need final confirmation it working on screen"*.
//
// CR-005's own closing note says what is owed: *"TO CLOSE: the browser
// walkthrough — change a format and save it, reset a counter and see it
// refused when set backwards, watch the preview and the right-rail sample
// update live."* Backend 106 passed and 235 frontend tests were already green
// when that was written, so a green suite is explicitly NOT the bar. The same
// bar on CR-004 was met only after a walkthrough found five screens answering
// HTTP 500 with every test green (DEF-187).
//
// So every assertion below is on RENDERED TEXT a person reads, never on a
// payload. The one exception is fenced into `signInAs`/`ensureRoleUser` and
// labelled.
//
// ── WHAT THIS WALKTHROUGH FOUND: FOUR DEFECTS AND TWO B14 DIVERGENCES ─────
//
// The screen itself WORKS. Nine tests pass on the substance: every row draws,
// a format changes and saves and survives a reload, the preview and the right
// rail move before any save, the custom-format grammar is refused in readable
// English, the counter refuses to go backwards and accepts a forward move
// after a confirm that names the number, the restart guard fires, and the
// immutability sentence is on screen. Nothing 500s. This is NOT a DEF-187
// repeat.
//
// Six tests are marked `test.fail()` — Playwright's "expected to fail"
// annotation: four defects (DEF-196..199 — three now FIXED) and two B14 rules this screen does
// not meet (rule 20 one table type, rule 8 searchable dropdowns).
//
// That annotation is a deliberate choice of instrument: the test states
// the RULE, the annotation states that the product does not honour it today,
// and the run stays green. **The moment the product is fixed the run goes RED
// with "expected to fail but passed"**, which forces the annotation off and
// the defect row closed. A `expect(brokenThing).toBe(broken)` assertion would
// have done the opposite — gone green forever and had to be found again.
//
//   · **DEF-196 — the read-only role never saw the screen at all. ✅ FIXED
//     2026-08-17.** `GET /settings/number-series` was `SystemAdminOnly`, so the
//     READ answered 403 and the tab rendered *"You don't have access to this."*
//     Every `readOnly` branch in SettingsNumberingTab.tsx was DEAD UI (hard-won
//     law 2): the component tests set `readOnly={true}` as a PROP and passed,
//     while nothing in the running product could ever produce it.
//     **Fixed with one permission class** — read for an A4 "Full" or "View"
//     cell, write for "Full" only — across seven mixed-verb Settings views plus
//     the reference-data card grid.
//     ⚠ **AND THE FIRST CUT OF THAT FIX WAS WRONG IN A WAY WORTH RECORDING.**
//     It opened the read to ALL THREE roles, on this file's own summary of the
//     ruling. A4's `settings_lookups` row is
//     `{"system_admin": "Full", "executive": "View"}` — **a Billing Clerk has
//     no cell at all**, which is no access rather than read-only access. Every
//     test written for the fix agreed with the fix and passed. `US-TEN-009
//     TC-5`, a story case asserting *"clerk denied at the reference-data
//     surface"* since that surface was built, is what caught it. **The old test
//     was right and the new fix was wrong** — which is the argument for not
//     deleting a red test until you know which of the two it is.
//   · **DEF-197 — two formats are labelled "plain, no prefix" and are not.**
//     `literalPrefix()` returns "" for any format that OPENS with a token, so
//     Account offers `{YYYY}{00000} · plain, no prefix` and Bill offers
//     `{YYYY}{MM}{DD}-{0000} · plain, no prefix`. Both carry a date prefix.
//     The Account row now offers TWO options claiming to be the plain one, and
//     picking the wrong one issues `202600001`. The PO's rule is *"Plain-number
//     option is mandatory in every category … just `{00000}` with no prefix"* —
//     an affordance whose whole job is to be findable.
//   · **DEF-198 — the reset control's size class does not exist.**
//     `className="btn btn-icon-sm"` is the ONLY occurrence of `btn-icon-sm` in
//     the entire frontend; no stylesheet declares it. Measured on screen the
//     button is **43 × 35 px at 14px type**, against CR-005's own UX rule
//     *"44px min hit targets"* and against the sibling reference-data screen's
//     icon buttons (`settings-icon-btn`, 32 × 32 at 12px). B14 rule 5 allows
//     two button sizes; this screen renders 13px and 14px and no 12px small
//     tier at all.
//   · **DEF-199 — a blocked Save says nothing.** With an invalid custom format
//     the Save handler returns early (`if (blocked …) return;`). The field
//     error is on screen, which is good, but the button stays enabled and
//     pressing it produces no toast, no banner and no focus move — a user who
//     has scrolled past the bad row presses Save and the product does nothing
//     at all. B14 rule 5 / BR-SHL-020 territory; recorded, not fixed here.
//
// ⚠ **THIS SPEC WRITES, AND ONLY TO A DISPOSABLE TENANT.** Two writes, both
// deliberate and both documented:
//   1. the `receipt` format is changed and then **restored** — legal in both
//      directions, since BR-TEN-035 makes format changes future-only rather
//      than one-way;
//   2. the `service_template` counter is moved FORWARD by 500 and **cannot be
//      restored** — that is the rule under test. `service_template` is chosen
//      because it issues nothing (the Work rows ship as formats only, PO
//      2026-08-16: *"it should work standalone in settings; we will link it
//      later ith work"*), and the target is computed from whatever the screen
//      shows, so a re-run always moves forward from where the last one left it.
// It also creates ONE Executive user per run under a run-unique address.
// Point this at a disposable tenant and nothing else — the same posture, and
// the same warning, as CR-004-reference-crud.spec.ts.
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import { APP_SERVER_TAG } from "./support/census";
import {
  expectScreenInContentPane,
  signInEmail,
  signInPassword,
  signInPath,
  skipUnlessAppServer,
  tenant,
} from "./support/app";

skipUnlessAppServer(test);

// ── What the screen must draw ──────────────────────────────────────────────
//
// The twenty-two series and their five section kickers, transcribed from the
// running screen and cross-checked against `core.numbering.SERIES_CATALOG`.
// CR-005 names sixteen entities, r10's SET-08 draws fourteen, and they are not
// the same fourteen — the union of twenty-two ships and the trim is the PO's
// call (OQ-251). This list is therefore a TRANSCRIPTION of an open question's
// current answer, not a rule: when OQ-251 is ruled, this list changes with it.
interface Group {
  /** The section kicker, en — `settings.numbering.group.<key>`. */
  kicker: string;
  /** Entity labels in the order the screen prints them. */
  entities: string[];
}

const GROUPS: Group[] = [
  {
    kicker: "Customers & premises",
    entities: ["Account #", "Premises #", "Unit #", "Service request #"],
  },
  {
    kicker: "Billing & payments",
    entities: [
      "Bill #",
      "Payment #",
      "Receipt #",
      "Adjustment #",
      "Credit memo #",
      "Write-off #",
      "Deposit batch #",
    ],
  },
  {
    kicker: "Finance",
    entities: ["Journal entry #", "Collections notice #", "Export batch #"],
  },
  {
    kicker: "Work",
    entities: ["Work order #", "Service template #", "Dispatch batch #"],
  },
  {
    kicker: "Assets & reads",
    entities: ["Asset #", "Read batch #", "Route #", "Cycle #", "Import run #"],
  },
];

const ALL_ENTITIES = GROUPS.flatMap((group) => group.entities);

/** BR-TEN-035, in the user's words — the reason no renumber control exists. */
const IMMUTABILITY_SENTENCE = "Numbers already issued are never renumbered or reformatted.";
/** BR-SHL-025's sentence, quoted from `en.json` rather than paraphrased. */
const READ_ONLY_REASON = "Your role can view this, but not change it.";
/** What a role WITHOUT the tab sees — the state DEF-196 says is wrong here. */
const TAB_DENIED_TITLE = "You don't have access to this.";
const TAB_DENIED_HELPER = "Your role can't open this Settings tab. Ask a System Admin.";
// DEF-196: the product distinguishes TWO denials, and the walkthrough only
// found that out by clicking. `settings.denied.tab` (above) is "you may not
// open THIS tab"; `settings.denied.page` is "you have no Settings at all",
// which is what an A4 "—" cell earns. A Billing Clerk gets the second one,
// and that is the better message — it does not imply another tab would work.
const PAGE_DENIED_HELPER =
  "Settings is for System Admins. Ask one if you need something changed.";

/** Raw keys that must never reach a screen (BR-SHL-020 / DEF-188's lesson). */
const RAW_KEY_PREFIXES = ["settings.numbering.", "errors.auth", "settings.readOnlyReason"];

function numberingPath(): string {
  return `/${tenant()}/settings/reference-data/number-series`;
}

/** A series row, matched on its ENTITY header cell exactly. */
function rowFor(page: Page, entity: string): Locator {
  return page
    .locator("table.numbering-table tbody tr")
    .filter({ has: page.getByRole("rowheader", { name: entity, exact: true }) });
}

function formatSelect(page: Page, entity: string): Locator {
  return rowFor(page, entity).locator("select.numbering-format");
}

function counterInput(page: Page, entity: string): Locator {
  return rowFor(page, entity).locator("input.input-num");
}

function previewCell(page: Page, entity: string): Locator {
  return rowFor(page, entity).locator("td.numbering-preview");
}

function resetButton(page: Page, entity: string): Locator {
  return rowFor(page, entity).getByRole("button", { name: "Reset counter" });
}

/** One line of the right rail, e.g. ["Receipt", "R-0001"]. */
function railLine(page: Page, label: string): Locator {
  return page
    .locator("aside.numbering-rail .numbering-sample-line")
    .filter({ hasText: new RegExp(`^${label}\\b`) })
    .locator("b");
}

async function openNumbering(page: Page): Promise<void> {
  await page.goto(numberingPath());
  // ⚠ THE ORDER HERE IS THE ASSERTION, and CR-004's header explains why at
  // length: a bare `toHaveCount(0)` on the failure card straight after a
  // navigation PASSES INSTANTLY because the query is still in flight. So wait
  // for the body to SETTLE into one of its possible states first, then say
  // which one it must not be.
  const failureCard = page.getByText("We couldn't load your numbering.");
  const denied = page.getByText(TAB_DENIED_TITLE);
  const table = page.locator("table.numbering-table");
  await expect(failureCard.or(denied).or(table).first()).toBeVisible({ timeout: 60_000 });
  await expect(
    failureCard,
    "the numbering read answered an error and the frame rendered the failure card",
  ).toHaveCount(0);
  await expect(
    denied,
    `the numbering read answered 403 and the tab rendered "${TAB_DENIED_TITLE}"`,
  ).toHaveCount(0);
}

/** Sign in through S3's own form — never by forging a cookie (PO 2026-08-11). */
async function signInAs(page: Page, email: string, password: string): Promise<void> {
  await page.goto(signInPath());
  await page.locator("#signin-email").fill(email);
  await page.locator("#signin-password").fill(password);
  await page.locator("form button[type=submit]").first().click();
  await page.getByRole("navigation", { name: "Main navigation" }).waitFor({ timeout: 60_000 });
  await expectScreenInContentPane(page, `/${tenant()}/dashboard`);
}

async function signOut(page: Page): Promise<void> {
  await page.request.delete(`/api/${tenant()}/auth/session`).catch(() => undefined);
  await page.context().clearCookies();
}

/**
 * PRE-FLIGHT, AND EXPLICITLY NOT PART OF THE PROOF — the only API calls in
 * this file, kept in one function so that is impossible to miss.
 *
 * The Executive walkthrough needs an Executive, and the seed ships exactly one
 * user (the System Admin owner). Creating one from the Users & roles SCREEN
 * would be the purer route and it is not available: BR-IDN-022 hands back a
 * temporary password and flags `must_change_password`, and **the forced-change
 * screen at `/change-password` IS NOT BUILT** — App.tsx says so in a comment
 * and the route falls through to the catch-all. So a browser-only path from
 * "create user" to "signed in as that user" does not exist today, and this
 * function walks the three API calls a human would otherwise walk through a
 * screen. Reported rather than worked around (it is DEF-200's substance).
 */
async function ensureRoleUser(
  page: Page,
  role: string,
  email: string,
  password: string,
): Promise<void> {
  const base = `/api/${tenant()}`;
  const created = await page.request.post(`${base}/users`, {
    data: { full_name: `QA ${role} walkthrough`, email, role },
  });
  if (!created.ok()) {
    throw new Error(
      `could not create the ${role} fixture user: HTTP ${created.status()} ${await created.text()}`,
    );
  }
  const { temp_password: temp } = (await created.json()) as { temp_password: string };
  const session = await page.request.post(`${base}/auth/session`, {
    data: { email, password: temp },
  });
  expect(session.ok(), "the fixture user could not sign in with its temporary password").toBe(true);
  const changed = await page.request.post(`${base}/me/password`, {
    data: {
      current_password: temp,
      new_password: password,
      confirm_password: password,
      sign_out_other_sessions: false,
    },
  });
  expect(changed.status(), "the forced password change did not take").toBe(204);
  await signOut(page);
}

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE SCREEN DRAWS EVERY ROW, UNDER ITS KICKER, WITH ALL FIVE COLUMNS
// ══════════════════════════════════════════════════════════════════════════
test(`CR-005 · every entity renders under its kicker with format, counter, preview and reset ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  // The five section kickers, in r10 SET-08's order (CR-005 UX rule: "Section
  // kickers per group").
  const kickers = page.locator("table.numbering-table tr.numbering-group .kicker");
  await expect(kickers).toHaveText(GROUPS.map((group) => group.kicker));

  // Every entity has a row, and every row has all five things CR-005 asks for:
  // *"Each entity row shows: current format, Next counter (editable numeric
  // field), live Preview … and a reset icon"* — plus the Restart column that
  // clause (b) added.
  for (const group of GROUPS) {
    for (const entity of group.entities) {
      const row = rowFor(page, entity);
      await expect(row, `${entity} has exactly one row`).toHaveCount(1);

      // Format: a select whose VALUE is a legal BR-TEN-035 format string.
      const chosen = await formatSelect(page, entity).inputValue();
      expect(chosen, `${entity} shows a format`).toMatch(/\{0+\}/);

      // Next counter: an editable numeric field holding a whole number.
      await expect(counterInput(page, entity)).toBeEditable();
      expect(
        await counterInput(page, entity).inputValue(),
        `${entity}'s Next counter is a whole number`,
      ).toMatch(/^\d+$/);

      // Preview: the SERVER's rendering of the next number, in a sentence.
      await expect(previewCell(page, entity)).toHaveText(/^Next number will be \S+$/);

      // Reset: B14 rule 15 — an ICON with an accessible name and a tooltip.
      const reset = resetButton(page, entity);
      await expect(reset).toBeEnabled();
      await expect(reset).toHaveAttribute("title", "Reset counter");
      await expect(reset).toHaveText("↺");
    }
  }

  // Twenty-two rows and no more — a row nobody transcribed is a row nobody
  // reviewed (OQ-251 is about exactly this list).
  await expect(page.locator("table.numbering-table tbody tr:not(.numbering-group)")).toHaveCount(
    ALL_ENTITIES.length,
  );

  // The column headers CR-005 names, in its order.
  await expect(page.locator("table.numbering-table thead th")).toHaveText([
    "Entity",
    "Format",
    "Next counter",
    "Restart",
    "Preview",
    "Reset counter",
  ]);

  // BR-SHL-020: nothing on this screen speaks in developer.
  const body = await page.locator("main.view").innerText();
  for (const prefix of RAW_KEY_PREFIXES) {
    expect(body, `a raw i18n key beginning "${prefix}" reached the screen`).not.toContain(prefix);
  }
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · THE IMMUTABILITY SENTENCE IS ON THE SCREEN (CR-005: "immutable, stated
//     on screen")
// ══════════════════════════════════════════════════════════════════════════
test(`CR-005 · the screen states that issued numbers are never renumbered ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(120_000);
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);
  await expect(page.getByText(IMMUTABILITY_SENTENCE)).toBeVisible();
  // …and the lede that carries the same promise a second time, where a user
  // reading top-down meets it first.
  await expect(
    page.getByText(
      "How account, bill, payment, adjustment and asset numbers look. Changes apply to numbers issued from now on.",
    ),
  ).toBeVisible();
});

// ══════════════════════════════════════════════════════════════════════════
// 3 · CHANGE A FORMAT: THE PREVIEW AND THE RIGHT RAIL MOVE **BEFORE** SAVING,
//     THE SAVE PERSISTS, AND A RELOAD PROVES IT
//     (CR-005: *"Preview updates live as format/counter changes"* and the
//      right rail *"re-renders as formats change so the admin sees the
//      downstream effect before saving"*)
// ══════════════════════════════════════════════════════════════════════════
test(`CR-005 · a ready-made format previews live, saves, and survives a reload ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  const ENTITY = "Receipt #";
  const ORIGINAL = "R-{0000}";
  const CHOSEN = "RCPT-{YY}{MM}-{000}";

  // At rest: the stored format, the server's preview, and the rail agreeing.
  await expect(formatSelect(page, ENTITY)).toHaveValue(ORIGINAL);
  const restingPreview = (await previewCell(page, ENTITY).innerText()).replace(
    "Next number will be ",
    "",
  );
  await expect(railLine(page, "Receipt")).toHaveText(restingPreview);

  // ── LIVE, BEFORE ANY SAVE ────────────────────────────────────────────────
  await formatSelect(page, ENTITY).selectOption(CHOSEN);

  // The row's preview switches to the clearly-labelled UNSAVED echo. Both
  // previews exist on purpose and are deliberately different — the server's
  // is the truth at rest, this one is the shape of an unsaved edit.
  await expect(previewCell(page, ENTITY)).toHaveText(/^Unsaved — would be RCPT-\d{4}-\d{3}$/);
  const unsaved = (await previewCell(page, ENTITY).innerText()).replace("Unsaved — would be ", "");
  expect(unsaved, "the local echo must differ from the stored one").not.toBe(restingPreview);

  // …and the right rail re-renders from the same draft, WITHOUT a save. This
  // is the assertion CR-005 asks for by name: the admin sees the downstream
  // effect first.
  await expect(railLine(page, "Receipt")).toHaveText(unsaved);
  // The rows nobody touched do not move with it.
  await expect(railLine(page, "Account")).toHaveText(/^AC-\d{4}-\d{5}$/);

  // ── SAVE ────────────────────────────────────────────────────────────────
  await page.getByRole("button", { name: "Save formats" }).click();
  await expect(page.locator(".toast")).toHaveText(
    "Numbering saved. It applies to numbers issued from now on.",
  );

  // ── RELOAD: persisted, not merely optimistic ────────────────────────────
  await page.reload();
  await openNumbering(page);
  await expect(formatSelect(page, ENTITY)).toHaveValue(CHOSEN);
  // The preview is the SERVER's again (no "Unsaved —" prefix) and it is the
  // number the local echo promised.
  await expect(previewCell(page, ENTITY)).toHaveText(`Next number will be ${unsaved}`);
  await expect(railLine(page, "Receipt")).toHaveText(unsaved);

  // ── PUT IT BACK ─────────────────────────────────────────────────────────
  // Legal in both directions: BR-TEN-035 makes a format change future-only,
  // never one-way. The COUNTER is the forward-only half and is untouched here.
  await formatSelect(page, ENTITY).selectOption(ORIGINAL);
  await page.getByRole("button", { name: "Save formats" }).click();
  await expect(page.locator(".toast")).toHaveText(
    "Numbering saved. It applies to numbers issued from now on.",
  );
  await page.reload();
  await openNumbering(page);
  await expect(formatSelect(page, ENTITY)).toHaveValue(ORIGINAL);
  await expect(previewCell(page, ENTITY)).toHaveText(`Next number will be ${restingPreview}`);
});

// ══════════════════════════════════════════════════════════════════════════
// 4 · THE PLAIN, PREFIX-FREE OPTION IS OFFERED IN EVERY CATEGORY
//     CR-005, verbatim: *"Plain-number option is mandatory in every category
//     (user rule): just `{00000}` with no prefix"*.
// ══════════════════════════════════════════════════════════════════════════
test(`CR-005 · every entity offers a bare-counter format ${APP_SERVER_TAG}`, async ({ page }) => {
  test.setTimeout(180_000);
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  for (const entity of ALL_ENTITIES) {
    const values = await formatSelect(page, entity).locator("option").evaluateAll((nodes) =>
      nodes.map((node) => (node as HTMLOptionElement).value),
    );
    // A bare counter and nothing else — `{00000}`, `{000000}`, `{0000000}`…
    // The PAD WIDTH varies by entity (Account offers `{0000000}`, Bill
    // `{00000000}`), which is a reasonable reading of "just {00000}" and is
    // reported alongside OQ-250 rather than asserted as exactly five zeros.
    const plain = values.filter((value) => /^\{0+\}$/.test(value));
    expect(plain.length, `${entity} offers no plain, prefix-free format`).toBeGreaterThanOrEqual(1);
  }

  // And the escape hatch CR-005 names next to it.
  await expect(formatSelect(page, "Account #").locator("option", { hasText: "Custom…" })).toHaveCount(
    1,
  );
});

// ── DEF-197 ───────────────────────────────────────────────────────────────
// The label is the affordance. `literalPrefix()` returns "" for anything that
// OPENS with a token, so a date-prefixed format is announced as the plain one.
// **The rule, asserted; the annotation records that the product fails it.**
test(`CR-005 · DEF-197 · only bare-counter formats are labelled "plain, no prefix" ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  // FIXED 2026-08-17 — the annotation came off exactly as this file predicted.
  // `isPlainCounter()` replaced the empty-literal-prefix test; the unit-level
  // statement is in SettingsNumberingTab.test.tsx. This stays as the guard
  // that measures the RUNNING screen's option labels rather than a predicate.
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  const mislabelled: string[] = [];
  for (const entity of ALL_ENTITIES) {
    const options = await formatSelect(page, entity).locator("option").evaluateAll((nodes) =>
      nodes.map((node) => ({
        value: (node as HTMLOptionElement).value,
        label: (node as HTMLOptionElement).textContent ?? "",
      })),
    );
    for (const option of options) {
      if (option.label.includes("plain, no prefix") && !/^\{0+\}$/.test(option.value)) {
        mislabelled.push(`${entity}: "${option.label}"`);
      }
    }
  }
  expect(
    mislabelled,
    "these formats carry a date prefix and are announced as the plain one",
  ).toEqual([]);
});

// ══════════════════════════════════════════════════════════════════════════
// 5 · CUSTOM FORMAT VALIDATION, FROM THE SCREEN
//     CR-005: *"Custom (free-form pattern input, validated: max 1 counter,
//     only allowed tokens, ≤ 24 chars)"*. Each refusal must be a readable
//     sentence, never a raw key (BR-SHL-020).
// ══════════════════════════════════════════════════════════════════════════
test(`CR-005 · a custom format is refused with a readable sentence ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  const ENTITY = "Cycle #";
  const SERIES = "cycle";
  const ORIGINAL = await formatSelect(page, ENTITY).inputValue();

  await formatSelect(page, ENTITY).selectOption("__custom__");
  const custom = page.locator(`#series-format-${SERIES}`);
  const error = page.locator(`#series-format-${SERIES}-error`);
  await expect(custom).toBeVisible();
  // The help line names the grammar rather than making the user guess it.
  await expect(page.locator(`#series-format-${SERIES}-help`)).toHaveText(
    "Use {YYYY} {YY} {MM} {DD} and one counter such as {00000}.",
  );

  // Each row is [what a user types, the sentence they must be shown].
  const REFUSALS: [string, string][] = [
    ["CY-{000}-{000}", "Use exactly one counter token."],
    ["CY-{MONTH}-{000}", "Only {YYYY}, {YY}, {MM}, {DD} and one counter token are allowed."],
    ["CYCLEPREFIXCYCLEPREFIX-{0000}", "Keep the whole format to 24 characters or fewer."],
    ["CY-{0000000000}", "Use at most 8 zeros in the counter."],
    ["CY-{YYYY}", "Add one counter token, such as {00000}."],
    ["CY-{000", "A { is missing its }."],
    ["", "Enter a format."],
  ];

  for (const [typed, sentence] of REFUSALS) {
    await custom.fill(typed);
    await expect(error, `typing ${JSON.stringify(typed)}`).toHaveText(sentence);
    await expect(custom).toHaveAttribute("aria-invalid", "true");
    // While a row is refused the preview refuses to invent one.
    await expect(previewCell(page, ENTITY)).toHaveText("Unsaved — would be not available");
  }

  // The screen never answers in developer.
  const body = await page.locator("main.view").innerText();
  expect(body).not.toContain("settings.numbering.problem.");
  expect(body).not.toContain("VAL-002");

  // Refused means nothing is written: press Save anyway, then re-read the
  // server from scratch.
  await page.getByRole("button", { name: "Save formats" }).click();
  await page.waitForTimeout(1_500);
  await page.reload();
  await openNumbering(page);
  await expect(
    formatSelect(page, ENTITY),
    "a refused custom format must not have been saved",
  ).toHaveValue(ORIGINAL);

  // …and a LEGAL custom format is accepted through the same field, so the
  // refusals above are not a field that simply never works.
  await formatSelect(page, ENTITY).selectOption("__custom__");
  await page.locator(`#series-format-${SERIES}`).fill("CY-{YYYY}-{0000}");
  await expect(page.locator(`#series-format-${SERIES}-error`)).toHaveCount(0);
  await expect(previewCell(page, ENTITY)).toHaveText(/^Unsaved — would be CY-\d{4}-\d{4}$/);
  await page.getByRole("button", { name: "Save formats" }).click();
  await expect(page.locator(".toast")).toHaveText(
    "Numbering saved. It applies to numbers issued from now on.",
  );
  await page.reload();
  await openNumbering(page);
  await expect(formatSelect(page, ENTITY)).toHaveValue("CY-{YYYY}-{0000}");

  // Put it back.
  await formatSelect(page, ENTITY).selectOption(ORIGINAL);
  await page.getByRole("button", { name: "Save formats" }).click();
  await expect(page.locator(".toast")).toBeVisible();
  await page.reload();
  await openNumbering(page);
  await expect(formatSelect(page, ENTITY)).toHaveValue(ORIGINAL);
});

// ── DEF-199 ───────────────────────────────────────────────────────────────
// A Save that is refused must SAY it was refused. Today the handler returns
// early and the screen is silent — a user who scrolled past the bad row gets
// no toast, no banner and no focus move.
test(`CR-005 · DEF-199 · pressing Save with an invalid row says something ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  // FIXED 2026-08-17. The annotation came off, and ONE ASSERTION CHANGED WITH
  // IT — deliberately, and it is worth saying why rather than quietly editing.
  //
  // This test originally also demanded `expect(save).toBeDisabled()`. That
  // would have been the WRONG fix and the defect row said so: BR-SHL-025
  // treats a greyed control with no reason as the other half of the same
  // failure. So Save stays PRESSABLE and answers. The rule under test is
  // "a press must answer where the press happened", not "a press must be
  // impossible".
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  await formatSelect(page, "Cycle #").selectOption("__custom__");
  await page.locator("#series-format-cycle").fill("CY-{000}-{000}");
  await page.getByRole("button", { name: "Save formats" }).click();

  const refusal = page.locator(".settings-refusal, [role=alert]");
  await expect(
    refusal.first(),
    "Save was blocked and the screen said nothing at all",
  ).toBeVisible({ timeout: 5_000 });
  // …and it NAMES the row, so a user who scrolled past it knows where to go.
  await expect(refusal.first()).toContainText("Cycle #");
  // …and takes them there.
  await expect(page.locator("#series-format-cycle")).toBeFocused();
});

// ══════════════════════════════════════════════════════════════════════════
// 6 · COUNTER RESET IS FORWARD ONLY
//     CR-005: *"Counter reset: allowed only forward (can't set lower than
//     current — prevents duplicate IDs); confirmation required, audit-logged"*.
//     BR-TEN-035 is the rule; a backward move could re-mint a number already
//     stamped on an immutable financial row (CLAUDE.md hard rule 4).
// ══════════════════════════════════════════════════════════════════════════
test(`CR-005 · the counter refuses to move backwards and accepts a forward move after confirm ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  // `service_template` issues nothing — the Work rows ship as FORMATS ONLY (PO
  // 2026-08-16). A forward move here cannot be undone and cannot cost anything.
  const ENTITY = "Service template #";
  const SERIES = "service_template";
  const current = Number.parseInt(await counterInput(page, ENTITY).inputValue(), 10);
  expect(Number.isFinite(current)).toBe(true);

  // ── BACKWARD IS REFUSED, WITH A SENTENCE THAT SAYS WHY ──────────────────
  await counterInput(page, ENTITY).fill(String(Math.max(0, current - 1)));
  await expect(page.locator(`#series-next-${SERIES}-error`)).toHaveText(
    `Must be ${current} or higher — numbers already issued can never be reused.`,
  );
  await expect(counterInput(page, ENTITY)).toHaveAttribute("aria-invalid", "true");
  // Not a raw key, not a code.
  const refusal = await page.locator(`#series-next-${SERIES}-error`).innerText();
  expect(refusal).not.toContain("settings.numbering");
  expect(refusal).not.toContain("VAL-");

  // A non-number is refused in its own words.
  await counterInput(page, ENTITY).fill("twelve");
  await expect(page.locator(`#series-next-${SERIES}-error`)).toHaveText("Enter a whole number.");

  // Refused means nothing is written.
  await page.reload();
  await openNumbering(page);
  expect(Number.parseInt(await counterInput(page, ENTITY).inputValue(), 10)).toBe(current);

  // ── FORWARD IS ACCEPTED, AFTER A CONFIRM THAT NAMES WHAT HAPPENS ────────
  const target = current + 500;
  await counterInput(page, ENTITY).fill(String(target));
  await expect(page.locator(`#series-next-${SERIES}-error`)).toHaveCount(0);
  const promised = (await previewCell(page, ENTITY).innerText()).replace("Unsaved — would be ", "");

  await resetButton(page, ENTITY).click();
  // BR-SHL-032 / IS-6: the confirm names the action and states what it costs.
  await expect(page.locator(".modal-title")).toHaveText(`Move the counter for ${ENTITY}?`);
  await expect(page.locator(".confirm-consequence")).toHaveText(
    `The next number issued becomes ${promised}. A counter can only move forward — numbers already issued are never reused.`,
  );
  await page.getByRole("button", { name: "Move the counter" }).click();
  await expect(page.locator(".toast")).toHaveText(`${ENTITY} numbering saved.`);

  // Persisted, and the SERVER's preview now says the same number.
  await page.reload();
  await openNumbering(page);
  expect(Number.parseInt(await counterInput(page, ENTITY).inputValue(), 10)).toBe(target);
  await expect(previewCell(page, ENTITY)).toHaveText(`Next number will be ${promised}`);

  // …and the new value is now the floor: one lower is refused against it.
  await counterInput(page, ENTITY).fill(String(target - 1));
  await expect(page.locator(`#series-next-${SERIES}-error`)).toHaveText(
    `Must be ${target} or higher — numbers already issued can never be reused.`,
  );
});

// ══════════════════════════════════════════════════════════════════════════
// 7 · THE RESTART GUARD (BR-TEN-035 clause (b) / OQ-252)
//     A restart without the date token that separates the periods would
//     re-mint a number a customer already has.
// ══════════════════════════════════════════════════════════════════════════
test(`CR-005 · a restart without its date token is refused on screen ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  // `Route #` is `RT-{000}` — no date token at all.
  const ENTITY = "Route #";
  const restart = rowFor(page, ENTITY).getByRole("combobox", { name: "Restart" });
  await restart.selectOption("yearly");
  await expect(rowFor(page, ENTITY).locator(".field-error")).toHaveText(
    "Add {YYYY} or {YY} to the format before restarting each year, or the same number would be issued twice.",
  );
  await restart.selectOption("monthly");
  await expect(rowFor(page, ENTITY).locator(".field-error")).toHaveText(
    "Add {YYYY} and {MM} to the format before restarting each month, or the same number would be issued twice.",
  );

  // Give the format its tokens and the refusal clears — the guard is about the
  // format, not about restarts.
  await formatSelect(page, ENTITY).selectOption("R-{YY}-{000}");
  await restart.selectOption("yearly");
  await expect(rowFor(page, ENTITY).locator(".field-error")).toHaveCount(0);

  // Nothing is saved by this test.
  await page.reload();
  await openNumbering(page);
  await expect(formatSelect(page, ENTITY)).toHaveValue("RT-{000}");
  await expect(rowFor(page, ENTITY).getByRole("combobox", { name: "Restart" })).toHaveValue("never");
});

// ══════════════════════════════════════════════════════════════════════════
// 8 · READ-ONLY FOR A NON-SYSTEM-ADMIN — **DEF-196**
//     PO ruling 2026-08-16 (CR-005 · CR-006 · CR-007): *"Billing Clerk and
//     Executive can LOOK at numbering formats, routes, cycles and templates;
//     they cannot change them."* BR-SHL-025: the control stays VISIBLE and
//     DISABLED WITH ITS REASON, never hidden.
// ══════════════════════════════════════════════════════════════════════════
const EXEC_STAMP = Date.now().toString().slice(-7);
const EXEC_PASSWORD = "QAexecWalk!2026";
// DEF-196: the denial page has a correct subject now — a Billing Clerk,
// whose A4 `settings_lookups` cell does not exist at all.
const CLERK_EMAIL = `qa.clerk.${EXEC_STAMP}@brazosbendutilities.com`;
const CLERK_PASSWORD = "QAclerkWalk!2026";

// ⚠ THIS TEST CHANGED ITS SUBJECT WHEN DEF-196 WAS FIXED, and the reason is
// worth reading before editing it.
//
// It used to assert that an EXECUTIVE was denied the tab — today's behaviour,
// pinned so the next lane inherited a fact rather than a memory. That behaviour
// was the defect and is gone. But the denial page itself is NOT gone and is NOT
// wrong: A4's `settings_lookups` row is
// `{"system_admin": "Full", "executive": "View"}`, so a **Billing Clerk has no
// cell at all** — no access, not read-only access.
//
// So the assertion is kept and its subject corrected, rather than deleted. The
// first cut of the DEF-196 fix opened the read to all three roles and every
// test written for the fix agreed with it; `US-TEN-009 TC-5` — a story case
// asserting "clerk denied at the reference-data surface" since that surface was
// built — is what caught it. This is that guard, on the screen.
test(`CR-005 · DEF-196 · a Billing Clerk is DENIED the tab, because A4 gives them no cell ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signInAs(page, signInEmail(), signInPassword());
  await ensureRoleUser(page, "billing_clerk", CLERK_EMAIL, CLERK_PASSWORD);
  await signInAs(page, CLERK_EMAIL, CLERK_PASSWORD);

  // The role's own A4 row carries NO settings cell — the matrix in the
  // product's own vocabulary, read from the running server.
  const permissions = await (
    await page.request.get(`/api/${tenant()}/me/permissions`)
  ).json();
  const cell = (permissions.permissions as { code: string; access: string }[]).find(
    (row) => row.code === "settings_lookups",
  );
  // The server SENDS the row and renders the absent cell as an em-dash rather
  // than omitting it — which is the better shape (the screen can say "your role
  // has no access to this" by name), and is worth asserting exactly rather than
  // as "absent", because the two are different contracts.
  expect(cell?.access, "a Billing Clerk's A4 Settings cell is empty").toBe("—");

  await page.goto(numberingPath());
  await expect(page.getByText(TAB_DENIED_TITLE)).toBeVisible({ timeout: 60_000 });
  // The PAGE-level refusal, not the tab-level one — an A4 "—" cell means no
  // Settings at all, and the copy says exactly that.
  await expect(page.getByText(PAGE_DENIED_HELPER)).toBeVisible();
  await expect(page.getByText(TAB_DENIED_HELPER)).toHaveCount(0);
  // The whole table is absent — not disabled, absent. For THIS role that is
  // correct: there is no "View" to render read-only.
  await expect(page.locator("table.numbering-table")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Save formats" })).toHaveCount(0);
  await expect(page.getByText(READ_ONLY_REASON)).toHaveCount(0);
});

// ✅ THE RULE, AND IT IS GREEN NOW (DEF-196 fixed 2026-08-17). The annotation
// came off exactly as this file predicted it would have to: `GET
// /settings/number-series` lets an A4 "View" role read, so every `readOnly`
// branch in the tab is reachable code for the first time.
test(`CR-005 · DEF-196 · an Executive sees the numbering table read-only, with the reason on the controls ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(240_000);
  await signInAs(page, signInEmail(), signInPassword());
  await ensureRoleUser(page, "executive", `qa.exec.${EXEC_STAMP}@brazosbendutilities.com`, EXEC_PASSWORD);
  await signInAs(page, `qa.exec.${EXEC_STAMP}@brazosbendutilities.com`, EXEC_PASSWORD);
  await openNumbering(page);

  // BR-SHL-025, control by control: visible, disabled, reason attached.
  await expect(page.locator("table.numbering-table")).toBeVisible();
  const save = page.getByRole("button", { name: "Save formats" });
  await expect(save).toBeVisible();
  await expect(save).toBeDisabled();
  await expect(save).toHaveAttribute("title", READ_ONLY_REASON);
  await expect(page.getByText(READ_ONLY_REASON).first()).toBeVisible();

  await expect(formatSelect(page, "Bill #")).toBeDisabled();
  await expect(formatSelect(page, "Bill #")).toHaveAttribute("title", READ_ONLY_REASON);
  await expect(resetButton(page, "Bill #")).toBeDisabled();
  await expect(resetButton(page, "Bill #")).toHaveAttribute("title", READ_ONLY_REASON);
  // …and the numbers are still READABLE, which is the point of View.
  await expect(previewCell(page, "Bill #")).toHaveText(/^Next number will be \S+$/);
});

// ══════════════════════════════════════════════════════════════════════════
// 9 · B14 — the newly ratified UI conventions, measured on this screen
//     04-docs/02-decisions/14-ui-conventions.md. Rules 5, 15, 16, 18, 20 were
//     named for this walkthrough; 8 is added because the screen trips it.
// ══════════════════════════════════════════════════════════════════════════
test(`CR-005 · B14 rules 15 and 18 hold on this screen ${APP_SERVER_TAG}`, async ({ page }) => {
  test.setTimeout(180_000);
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  // RULE 15 — row actions are ICONS with tooltips, never text links, max 2
  // visible. This screen has exactly one row action and it is an icon with an
  // accessible name (which is the assertion that matters: an icon with no name
  // passes a text-absence check and is unusable without a mouse).
  for (const entity of ALL_ENTITIES) {
    const actions = rowFor(page, entity).locator("td:last-child button");
    await expect(actions, `${entity} row actions`).toHaveCount(1);
    await expect(actions).toHaveText("↺");
    await expect(actions).toHaveAccessibleName("Reset counter");
    await expect(actions).toHaveAttribute("title", "Reset counter");
  }

  // RULE 18 — descriptions cap at 80% of the content width, through the
  // `--desc-measure` token (amended from r10's 66% by PO ruling 2026-08-16:
  // *"make it 80%"*, *"across the app"*).
  const measured = await page.evaluate(() => ({
    token: getComputedStyle(document.documentElement).getPropertyValue("--desc-measure").trim(),
    ledes: [...document.querySelectorAll(".settings-tab > .settings-lede")].map(
      (node) => getComputedStyle(node).maxWidth,
    ),
  }));
  expect(measured.token).toBe("80%");
  expect(measured.ledes.length).toBeGreaterThan(0);
  for (const maxWidth of measured.ledes) {
    expect(maxWidth, "a description is not capped by --desc-measure").toBe("80%");
  }

  // RULE 16 — pagination. It does NOT apply here and the argument is recorded
  // rather than assumed: SET-08 is a complete, grouped configuration table of
  // a fixed twenty-two rows, not a paged list of records. Paging it would hide
  // half the tenant's numbering behind a control. So the assertion is that the
  // screen shows EVERY row, which is the property pagination would break.
  await expect(page.locator(".table-pager, .table-pager-range")).toHaveCount(0);
  await expect(page.locator("table.numbering-table tbody tr:not(.numbering-group)")).toHaveCount(
    ALL_ENTITIES.length,
  );
});

// ── DEF-198 ───────────────────────────────────────────────────────────────
// ✅ FIXED 2026-08-17. `btn-icon-sm` was the only occurrence of that class name
// in the frontend and no stylesheet declared it, so the reset control fell
// through to the default tier and measured 34.8px at 14px type — NEITHER of the
// two sizes B14 rule 5 allows.
test(`CR-005 · DEF-198 · the reset control renders at B14's ratified small tier ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  // ✅ FIXED 2026-08-17 — the PO decided it "as per rule", and the rule is B14
  // rule 5: two sizes, small is 12px, and `settings-icon-btn` (32×32) is that
  // tier. So this test's 44px expectation is NOT what shipped and the
  // assertions below are re-pointed at the ratified size. The 44px argument
  // (WCAG target size) is live as OQ-259, product-wide, not on this button.
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  const box = await resetButton(page, "Bill #").boundingBox();
  expect(box).not.toBeNull();
  // B14 rule 5's small tier is 32 × 32. Asserted EXACTLY rather than as a
  // minimum: ">= 32" would also pass on the 34.8px default tier this defect was
  // about, so the loose assertion could not tell the fix from the bug.
  expect(Math.round(box!.height), "reset control height").toBe(32);
  expect(Math.round(box!.width), "reset control width").toBe(32);
  // ⚠ NOT 44 × 44. That figure is CR-005's prose, not B14, and the PO ruled
  // "as per rule" on 2026-08-17. The WCAG target-size argument is alive and
  // product-wide as OQ-259 — if it is ever ruled, this is one of the tests
  // that must move, and it says so here rather than in a commit message.

  // B14 rule 5: the small tier is 12px, and it is what the sibling
  // reference-data screen's icon buttons already render at.
  const fontSize = await resetButton(page, "Bill #").evaluate(
    (node) => getComputedStyle(node).fontSize,
  );
  expect(fontSize, "B14 rule 5 — small buttons are 12px").toBe("12px");
});

// ── DEF-198 (second half) · B14 rule 20 ───────────────────────────────────
// *"Table type is one size (13.5px) everywhere; no inline overrides."* This
// screen drew a bespoke `.numbering-table` at 13px while the shared
// `DataTable` on the sibling Reference-data tab rendered cells at 14px. Two
// table types, two sizes, neither of them 13.5px — one click apart inside the
// same Configure screen.
//
// ✅ FIXED 2026-08-19 by CR-016's design-system slice (DEF-310). Both now read
// `--table-font-size` and render at the ratified 13.5px, and the `test.fail()`
// annotation came off exactly as the note below said it must: the run went RED
// with "expected to fail but passed" on the commit that fixed it, which is the
// annotation doing its job rather than a test needing repair.
test(`CR-005 · B14 rule 20 · the numbering table matches the product's one table type ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  await signInAs(page, signInEmail(), signInPassword());

  await page.goto(`/${tenant()}/settings/reference-data?list=areas`);
  await page.locator("table.data-table").waitFor({ timeout: 60_000 });
  const shared = await page
    .locator("table.data-table td")
    .first()
    .evaluate((node) => getComputedStyle(node).fontSize);

  await openNumbering(page);
  const numbering = await page
    .locator("table.numbering-table tbody td")
    .first()
    .evaluate((node) => getComputedStyle(node).fontSize);

  expect(numbering, "two table types one click apart render at different sizes").toBe(shared);
  // And it is not merely "the same" — it is the ratified figure. Without this
  // the test would still pass if both tables drifted to 14px together.
  expect(numbering, "B14 rule 20 — table body type is 13.5px").toBe("13.5px");
});

// ── B14 rule 8 ────────────────────────────────────────────────────────────
// *"Dropdowns share one chevron style; 5+ options are searchable
// (type-to-filter)."* CR-005's own prose asks for a *"searchable dropdown"*.
// The Account and Bill format pickers offer seven options each and are native
// `<select>` elements. The CR-005 lane recorded this as a knowing exception
// (*"the format picker is a NATIVE select, as r10 SET-08 draws it"*) — B14
// ratified the rule AFTER that exception was written, so it is re-raised here
// as a finding rather than left settled by one lane's note.
test(`CR-005 · B14 rule 8 · a format picker with 5+ options is searchable ${APP_SERVER_TAG}`, async ({
  page,
}) => {
  test.setTimeout(180_000);
  // KNOWN DEFECT: this test states the RULE; the annotation records that the
  // product does not honour it. When it is fixed this run goes RED with
  // "expected to fail but passed" and the annotation must come off.
  test.fail();
  await signInAs(page, signInEmail(), signInPassword());
  await openNumbering(page);

  for (const entity of ["Account #", "Bill #"]) {
    const select = formatSelect(page, entity);
    const options = await select.locator("option").count();
    expect(options, `${entity} option count`).toBeGreaterThanOrEqual(5);
    // A searchable picker is not a bare <select>: it exposes a text input the
    // user can type into to filter.
    const tag = await select.evaluate((node) => node.tagName.toLowerCase());
    expect(tag, `${entity} format picker is a bare <select> with ${options} options`).not.toBe(
      "select",
    );
  }
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-005 §"BUILT, NOT CLOSED" · PO bar "we need final confirmation it
//   working on screen" · B14 rules 5/8/15/16/18/20
// generated: 2026-08-17 by the CR-005 browser-walkthrough QA lane
// gates: run against `08-qa/01-e2e/stack/boot_stack.sh` on a seeded
//   `brazosbend`; every quoted string copied from the running screen, not from
//   the catalogue
// exceptions: this spec WRITES — one format changed and restored, one counter
//   moved FORWARD and unrestorable by rule, one Executive user created per run.
//   Point it at a disposable tenant only, the same posture as
//   CR-004-reference-crud.spec.ts · the `ensureRoleUser` pre-flight uses the
//   API because `/change-password` is not built, so no browser-only path exists
//   from "create a user" to "signed in as that user" (DEF-200)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
