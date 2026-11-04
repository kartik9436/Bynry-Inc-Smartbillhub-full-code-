// ── Trace ──────────────────────────────────────────────
// Change:  CR-009 (12-governance/11-change-requests.md) — SET-12 the event
//          matrix · SET-12D the rule page · the C-section (C-11 staff
//          recipients · C-12 the tenant SMTP sender · C-13 the four A15
//          send-time elections · C-14 the plan-void notice). The C-section
//          record is marked **BUILT 2026-08-18 · awaiting human review** and
//          its own last line says the debt this file pays:
//          *"no browser walkthrough by this lane — hard-won law 6 is unpaid on
//          the two new S8 cards and is reported, not waived."*
// Story:   CR-009@set12 · CR-009@c11 · @c12 · @c13 · @c14
//          Screens: S8 (Settings → Notifications) · SET-12 · SET-12D ·
//          SET-09/SET-10 (the plan-void body) · shell-chrome (the bell) ·
//          S22/S33 (record payment — C-13's ONE wired consumer)
//          Routes:  /{tenant}/settings/notifications
//                   /{tenant}/settings/notifications/{event_key}
//                   /{tenant}/settings/reference-data/templates
// Rules:   BR-NOT-019 (in-app is a real channel, the platform its provider) ·
//          BR-NOT-020 (ONE message per bulk action, with its failure count) ·
//          BR-NOT-021 (the staff recipient: the person who started the action,
//          plus every active System Admin on failure) · BR-NOT-022 (the four
//          A15 elections ship DEFAULT ON) · BR-NOT-023 (SMTP-first; the secret
//          column holds a REFERENCE, never a password) · BR-NOT-005 (queue
//          only — no synchronous send anywhere) · BR-NOT-013 (no adapter on
//          email/SMS/print; `delivered`/`bounced` are unwritable) ·
//          BR-PAY-024 (a receipt is queued on a recorded payment) ·
//          BR-SHL-025 (a control that cannot work stays visible and disabled
//          WITH its reason) · BR-SHL-007/026 (the bell)
// Questions: OQ-262 OPEN — three events (high usage, daily digest, security
//          alerts) have no trigger and no owner; OQ-249 OPEN — the three field
//          -work events wait on Work. Both must be SAID on screen, and this
//          file asserts that they are.
// ───────────────────────────────────────────────────────
//
// **THE BAR THIS FILE IS WRITTEN TO** — `12-governance/13-change-process.md`
// §8, THE CLOSURE BAR (PO 2026-08-18, verbatim: *"in this session CR is not
// closed until we have confirm user is able to perform tasks using screen/
// broswer/UI"*):
//
//   · assertions on RENDERED TEXT a person reads — never on API responses or
//     component props;
//   · every task the CR promises, performed end to end — INCLUDING ITS
//     REFUSALS;
//   · re-runnable OVER ITS OWN LEFTOVERS, not only a pristine seed.
//
// So: the sender card is filled in, refused on a pasted password, saved, and
// CLEARED again — a run leaves the tenant as it found it and the next run does
// not care which state it starts in. The elections are switched off and back
// on. The payment test records money and asserts the queue TILE moved by one.
//
// ── THE INVERSION CONTRACT (the CR-007 spec's, kept deliberately) ──────────
//
// Every assertion that pins a FINDING — something the product does today that
// it should not — is wrapped in a `FINDING (n)` block stating what happens now
// and what must happen instead. Those assertions are written so that **fixing
// the finding turns this file RED at that exact line**, with the finding
// quoted in the failure message. Nobody can fix one quietly.
//
// A green run therefore means: *the screens work as described, and the
// findings still marked open are still open.* It does NOT mean the screens are
// right.
//
// ── WHAT THIS FILE COULD NOT DO, SAID HERE RATHER THAN DISCOVERED LATER ────
//
// **The C-11 worked figure — 1,204 accounts, 3 failed → ONE message, three
// bells — CANNOT BE REPRODUCED FROM A BROWSER, and finding 6 is that fact.**
// Nothing a person can click puts a message in the bell: no product surface
// fires a staff event (OQ-262), and a queued row still needs `manage.py
// dispatch_outbound` — a shell command, not a screen — before it reaches an
// inbox. The bell's assertions below are therefore on its EMPTY state, which
// is what every human on this deployment sees.
//
// ⚠ **RE-CHECKED 2026-08-19 after DEF-265's fix, because finding 5 was one of
// the three reasons above and it is gone.** A person CAN now queue an in-app
// test to themselves from SET-12D — which removes the first half of the gap
// and leaves the second: the queue row sits there until the dispatcher is run
// from a shell. So DEF-266 survives its own cause being fixed, and the bell
// test below still passes on "You're all caught up."
//
// ── THE FINDINGS THIS FILE PINS — TWELVE, FOUR OF THEM NOW CLOSED ─────────
//
// Each is stated in full at the assertion that pins it. The rows all exist in
// `12-governance/10-defect-log.csv` now; the ids below are the real ones.
//
// ⚠ **UPDATED 2026-08-19 by the CR-009 closing walkthrough.** Findings 5 and 10
// were FIXED the same morning and their pins FIRED, which is the inversion
// contract working exactly as designed — a run that goes red because the
// product got better. Both are inverted in place: the assertion now pins the
// FIXED behaviour with a failure message naming the regression, so the fix
// cannot be undone quietly either. Two new findings were opened by what the
// fix to 5 revealed.
//
//   1 · the S8 tab says both "IN-APP DELIVERS TODAY" and "Nothing is sent in
//       this release" — two endpoints, one field name               (DEF-267)
//   3 · the receipt outcome a clerk reads is the RAW KEY
//       `payments.problem.receipt_queued` / `…receipt_election_off` (DEF-268)
//   4 · the plan-void Used-by still says the body does not exist, a day after
//       C-14 wrote and seeded it                                    (DEF-270)
//   5 · ✅ **CLOSED 2026-08-19 (DEF-265, commit 9dd7862)** — "Queue a test to
//       me" refused the in-app channel with print wording. It queues now, and
//       the assertion is inverted.
//   6 · nothing browser-reachable ever fills the bell, so the C-11 worked
//       figure cannot be shown to a person                          (DEF-266)
//   7 · the matrix's unavailable-channel reason is a `title` tooltip only
//                                                                   (DEF-271)
//   8 · the plain-English rule says a laddered event is immediate, beside a
//       ladder card saying 3 days                                   (DEF-269)
//   9 · ✅ **CLOSED 2026-08-22 (DEF-272's substance, the W13 DEF-286 lane)** —
//       the service scope goes through the catalogue on both the editor and
//       the read view; the assertion is inverted.
//  10 · ✅ **CLOSED 2026-08-19 (DEF-264, commit 86f748a)** — every refusal on
//       this tab rendered the same nine words and threw the server's sentence
//       away. The catalogue key carries `{{detail}}` now, and the assertion is
//       inverted onto the secret-REFERENCE wording C-12 exists to prove.
//  11 · the queued-test sentence is CHANNEL-BLIND: in-app is told "no mail
//       provider is connected", on the one channel that needs none  (DEF-284)
//  12 · the in-app test reports the recipient as a raw user UUID    (DEF-285)
//
// ⚠ **FINDING 2 — ✅ CLOSED 2026-08-22 (DEF-286 FIXED by the W13 lane; this
// pin FIRED on the fix, the inversion contract working as designed).** It was
// CR-009's ONE blocker: SET-12D's audience/channel/timing cards were
// READ-ONLY where the CR's own requirement text asks for pickers by name. The
// cards are EDITORS now — every `EDITABLE_RULE_FIELDS` /
// `EDITABLE_CHANNEL_FIELDS` member has a control, save posts the partial diff
// in one PUT and returns to the matrix — and the pin below is inverted so the
// pickers cannot quietly become text again. (`NotificationRules.tsx`
// exception (2), whose false surface_debt claim was DEF-287, is rewritten in
// the same commit.) What deliberately did NOT land: a template VARIANT picker
// — the wire stores a CLASS code and `update_rule` accepts nothing
// variant-shaped (OQ-332, decision log 2026-08-22).
//
// ⚠ **THIS SPEC WRITES.** It edits `notification_settings` (sender columns and
// the four election flags, both restored before it finishes), toggles one
// notification rule off and on again, queues one email test message per run on
// `bill_ready`, and records two small payments on the fixture account. Point it
// at a disposable tenant only — the same posture, and the same warning, as
// CR-004-reference-crud.spec.ts and CR-007-templates.spec.ts.
import { expect, test } from "@playwright/test";
import type { Locator, Page } from "@playwright/test";

import { APP_SERVER_TAG } from "./support/census";
import { signIn, skipUnlessAppServer, tenant } from "./support/app";

skipUnlessAppServer(test);

const RUN_STAMP = String(Date.now()).slice(-7);

function notificationsPath(): string {
  return `/${tenant()}/settings/notifications`;
}

function rulePath(eventKey: string): string {
  return `/${tenant()}/settings/notifications/${eventKey}`;
}

function templatesPath(): string {
  return `/${tenant()}/settings/reference-data/templates`;
}

function fixtureAccountNo(): string {
  return process.env.E2E_ACCOUNT_NO ?? "E2E-10001";
}

/** The S8 tab, waited for on the thing CR-009 put FIRST on it: the matrix. */
async function openNotificationsTab(page: Page): Promise<void> {
  await page.goto(notificationsPath());
  await page.getByRole("heading", { name: "Notification rules" }).waitFor({ timeout: 30_000 });
}

/** One panel, addressed by the heading a person reads. */
function panel(page: Page, title: string): Locator {
  return page.locator("section.panel").filter({ has: page.getByRole("heading", { name: title }) });
}

/** The queue summary's "Waiting" tile — the count C-13's consumer moves. */
async function waitingCount(page: Page): Promise<number> {
  const tile = panel(page, "What has gone out").locator("li", { hasText: "Waiting" }).first();
  const text = (await tile.innerText()).replace(/[^0-9]/g, "");
  return Number(text);
}

test.describe("CR-009 · Settings → Notifications, in a browser", { tag: APP_SERVER_TAG }, () => {
  // SERIAL: later tests read what earlier ones wrote (the sender card is
  // filled then cleared; the elections are switched off then on). A parallel
  // run would have two workers editing one tenant's single settings row.
  test.describe.configure({ mode: "serial" });

  // ══════════════════════════════════════════════════════════════════════
  // 1 · SET-12 — the event matrix
  // ══════════════════════════════════════════════════════════════════════
  test("SET-12 · the event matrix is reachable by clicking and states its own gaps", async ({
    page,
  }) => {
    await signIn(page);

    // A person clicking, not a URL typed: sidebar → Settings → the
    // Notifications tab. This is the only navigation assertion in the file;
    // every later test uses the linkable URL CR-009 deliberately built.
    await page
      .getByRole("navigation", { name: "Main navigation" })
      .getByRole("link", { name: "Settings", exact: true })
      .click();
    await page.getByRole("tab", { name: "Notifications", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`${notificationsPath()}$`));

    const matrix = panel(page, "Notification rules");
    await expect(matrix).toBeVisible();

    // The hint counts what is BUILT, and the discrepancy note counts what the
    // written requirement claimed. Both are sentences a System Admin reads.
    await expect(matrix.locator("p.panel-hint").first()).toHaveText(
      "15 events — who is told what, on which channel, and when.",
    );
    await expect(page.getByTestId("rule-count-discrepancy")).toHaveText(
      "The written requirement names 16 events and describes 15. The 15 described are built; " +
        "the missing one was reported rather than invented.",
    );

    // The PO's own five groups, as headings.
    for (const category of ["Billing", "Payments", "Collections", "Field work", "Staff & system"]) {
      await expect(matrix.getByRole("heading", { name: category })).toBeVisible();
    }

    // All fifteen events, by the name a clerk reads (never by key).
    for (const event of [
      "Bill ready",
      "Bill corrected",
      "Payment received",
      "Payment failed or returned",
      "Past-due reminder",
      "Final disconnection notice",
      "Unusually high usage",
      "Appointment window",
      "Technician on the way",
      "Work completed",
      "Billing run finished or failed",
      "Reconciliation exceptions",
      "Promised deadline missed",
      "Daily summary",
      "Security alerts",
    ]) {
      await expect(matrix.getByText(event, { exact: true })).toBeVisible();
    }

    // OQ-262 and OQ-249 are DRAWN, per event, with their id. This is the
    // brief's "expect surfaces that are declared and unwired, and assert that
    // they SAY so" — six of the fifteen say it.
    await expect(page.getByTestId("rule-noTrigger-high_usage_alert")).toHaveText(
      "Nothing in the product fires this event yet (OQ-262). You can still set who it goes " +
        "to and what it says.",
    );
    await expect(page.getByTestId("rule-noTrigger-daily_digest")).toContainText("(OQ-262)");
    await expect(page.getByTestId("rule-noTrigger-security_alerts")).toContainText("(OQ-262)");
    await expect(page.getByTestId("rule-noTrigger-appointment_window")).toContainText("(OQ-249)");
    await expect(page.getByTestId("rule-noTrigger-technician_on_the_way")).toContainText(
      "(OQ-249)",
    );
    await expect(page.getByTestId("rule-noTrigger-completion_receipt")).toContainText("(OQ-249)");

    // A channel the product does NOT have is drawn as an absence rather than
    // omitted — "Customer portal" and "Postal mail" are on the row, dimmed.
    await expect(page.getByTestId("rule-unavailable-bill_ready-portal")).toHaveText(
      "Customer portal",
    );
    await expect(page.getByTestId("rule-unavailable-disconnect_notice-mail")).toHaveText(
      "Postal mail",
    );

    // FINDING (7) — OPEN, and small only until somebody needs the answer.
    //
    // The REASON is in a `title` attribute and nowhere else, so on the matrix
    // it exists for a mouse and not for a person: it is invisible to a
    // keyboard user, to a touch device, to a screen reader in most modes, and
    // to anyone who does not think to hover a greyed pill. `RuleRow`'s own
    // comment claims *"BR-SHL-025 — visible, disabled, WITH its reason"*, and
    // the rule's words are that the reason is RENDERED. SET-12D gets this
    // right (asserted below), which is what makes the matrix the outlier
    // rather than a design choice.
    //
    // TO INVERT WHEN FIXED: the reason becomes text (or a real disclosure) and
    // the `toHaveText` assertions above start failing with the full sentence.
    await expect(page.getByTestId("rule-unavailable-bill_ready-portal")).toHaveAttribute(
      "title",
      /there is no customer portal in this product/,
    );
    await expect(
      page.getByTestId("rule-unavailable-bill_ready-portal"),
      "FINDING 7 — the unavailable-channel reason is now rendered text on the matrix. " +
        "Assert the sentence and strike finding 7.",
    ).not.toContainText("BR-NOT-010");
  });

  // ══════════════════════════════════════════════════════════════════════
  // 2 · FINDING 1 — two contradictory dispatch statements on ONE tab
  // ══════════════════════════════════════════════════════════════════════
  test("FINDING 1 · the S8 tab tells a utility both that in-app delivers and that nothing is sent", async ({
    page,
  }) => {
    await signIn(page);
    await openNotificationsTab(page);

    // FINDING (1) — OPEN, and it is the product's, not this spec's.
    //
    // `GET /notification-rules` serves RELEASE_POSTURE with
    // `dispatch_runs_in_this_release: true` and the sentence below;
    // `GET /notification-settings` serves the SAME field name as `false` with
    // the opposite sentence. Both render on the same scroll of the same tab,
    // about six centimetres apart. The in-app lane amended one and not the
    // other (the CR record says the flag "flipped false → true" — it flipped
    // on ONE of the two endpoints that carry it).
    //
    // WHAT MUST HAPPEN INSTEAD: one source of truth for the posture, served by
    // both endpoints or by neither, so a System Admin reading this tab gets one
    // answer to "does switching a rule on do anything".
    //
    // TO INVERT WHEN FIXED: the second expectation below should become the
    // same sentence as the first (or the flag should disappear from the
    // settings payload); this test then goes red at that line.
    await expect(page.getByTestId("rule-release-posture")).toContainText(
      "IN-APP DELIVERS TODAY — it needs no integration",
    );
    await expect(
      page.getByTestId("no-dispatcher"),
      "FINDING 1 — if this now agrees with the in-app posture above, the contradiction is " +
        "FIXED: update this assertion and strike finding 1 from the header.",
    ).toHaveText(
      "Nothing is sent in this release. Messages are composed, queued and shown here; no " +
        "provider is called on any channel, print included. These switches record what this " +
        "utility would do, not what it does.",
    );
  });

  // ══════════════════════════════════════════════════════════════════════
  // 3 · SET-12D — the rule page, a full page and not a modal
  // ══════════════════════════════════════════════════════════════════════
  test("SET-12D · a rule opens as a full page, states itself in plain English, and comes back", async ({
    page,
  }) => {
    await signIn(page);
    await openNotificationsTab(page);

    await page.getByTestId("rule-open-bill_ready").click();
    await expect(page).toHaveURL(new RegExp(`${rulePath("bill_ready")}$`));

    // The requirement's header: category kicker, event name, subtitle.
    await expect(page.locator("span.kicker")).toHaveText("Billing");
    await expect(page.locator("h2.settings-frame-title")).toHaveText("Bill ready");

    // The right rail's plain-English sentence — the requirement's own
    // "auto-generated sentence of the full rule".
    await expect(page.getByTestId("rail-plain-english")).toHaveText(
      "Bill ready goes to every contact on the account by Email, Text message, as soon as it " +
        "happens. No accounts are left out.",
    );

    // The four left-column cards the requirement names (the ladder card is
    // collections-only and is asserted in its own test below).
    for (const card of ["Audience", "Channels & templates", "Timing"]) {
      await expect(page.getByRole("heading", { name: card })).toBeVisible();
    }
    // The counterpart to finding 7: on the RULE PAGE an unavailable channel
    // carries its reason as text a person reads, with no hover required.
    await expect(page.getByTestId("channel-unavailable-portal")).toContainText(
      "there is no customer portal in this product. A 'Portal' delivery flag would be a " +
        "switch with nothing behind it",
    );

    // ⚠ lower-case "every" is the screen's own: the audience card reuses the
    // plain-English SENTENCE fragment as a field value, so this one `<dd>`
    // starts in lower case where "All customers" beside it does not. Recorded
    // as a copy nit rather than a numbered finding — it misleads nobody.
    // ⚠ SINCE 2026-08-22 (DEF-286 closed, the W13 lane) a System Admin sees
    // EDITORS on these cards, so the values are asserted as the pickers' own
    // selected VALUES — the stored enums — while the visible option text stays
    // the catalogue's.
    await expect(page.locator("[data-testid=audience-scope] select")).toHaveValue(
      "all_contacts",
    );
    await expect(page.locator("[data-testid=audience-planClass] select")).toHaveValue("all");
    await expect(
      page.locator("[data-testid=audience-skipPlans] input[type=checkbox]"),
    ).not.toBeChecked();

    // FINDING (9) — ✅ CLOSED 2026-08-22 BY THE SAME LANE (DEF-272's substance):
    // the service scope goes through the catalogue now. For a System Admin it
    // is a select whose chosen option reads "All services"; the Executive read
    // view renders the catalogued wording too. Inverted per this pin's own
    // instruction; the raw enum must not come back.
    await expect(
      page.locator("[data-testid=audience-service] select"),
      "FINDING 9 HAS REGRESSED — the service scope is a raw enum again.",
    ).toHaveValue("all");
    await expect(
      page.locator("[data-testid=audience-service] select option:checked"),
    ).toHaveText("All services");
    await expect(page.locator("[data-testid=timing-trigger] select")).toHaveValue("immediate");
    await expect(page.locator("[data-testid=timing-quietHours] select")).toHaveValue("respect");
    await expect(page.locator("[data-testid=timing-failurePolicy] select")).toHaveValue(
      "retry_3_days_then_email",
    );

    // BR-NOT-013 on the rail: NOT REPORTED, never three zeroes.
    await expect(page.getByTestId("rail-delivery-unreported")).toContainText(
      "'delivered' needs a provider confirmation and 'bounced' needs an ESP webhook",
    );
    await expect(page.getByText("Last 30 days")).toBeVisible();
    await expect(
      page.getByText("Every save is recorded — who changed it, when, and what moved."),
    ).toBeVisible();

    // ⚠ An UNTOUCHED page cannot save any more (2026-08-22): the service
    // refuses an empty change set with a sentence, and the button now says so
    // up front instead of collecting that refusal after a round trip.
    await expect(page.getByTestId("rule-save")).toBeDisabled();

    // Save a REAL edit — quiet hours to "Send anyway", a real write through
    // the real audited service — and the page RETURNS TO THE MATRIX, which is
    // the requirement's own "Save … returns to matrix".
    await page
      .locator("[data-testid=timing-quietHours] select")
      .selectOption("override");
    await page.getByTestId("rule-save").click();
    await expect(page.locator(".toast")).toHaveText("Rule saved.");
    await expect(page).toHaveURL(new RegExp(`${notificationsPath()}$`));
    await expect(panel(page, "Notification rules")).toBeVisible();

    // RESTORE the fixture (this spec's own contract: everything it edits it
    // puts back), which also proves the edit round-trips: the page reopens
    // showing "override", is put back to "respect", and saves again.
    await page.goto(rulePath("bill_ready"));
    await expect(page.locator("[data-testid=timing-quietHours] select")).toHaveValue("override");
    await page.locator("[data-testid=timing-quietHours] select").selectOption("respect");
    await page.getByTestId("rule-save").click();
    await expect(page).toHaveURL(new RegExp(`${notificationsPath()}$`));

    // ← Back returns to the matrix too — the rule page is a URL, not a modal.
    await page.goto(rulePath("bill_ready"));
    await page.getByRole("button", { name: "← Notification rules" }).click();
    await expect(page).toHaveURL(new RegExp(`${notificationsPath()}$`));

    // FINDING (2) — ✅ CLOSED 2026-08-22 (DEF-286, the W13 lane; this pin
    // FIRED on the fix exactly as designed). The audience, channel and timing
    // cards are EDITORS for a System Admin: customer scope, service scope,
    // plan class, the payment-plan skip, per-channel enable + template picker
    // (real catalog classes) + language mode, trigger mode with its argument
    // as a pair, quiet hours and failure policy — every `EDITABLE_RULE_FIELDS`
    // member. Inverted per this pin's own instruction: the pickers must not
    // quietly become text again.
    await page.goto(rulePath("bill_ready"));
    await expect(page.getByTestId("audience-scope")).toHaveCount(1);
    await expect(
      page.locator("[data-testid=audience-scope] select"),
      "FINDING 2 HAS REGRESSED — the audience card lost its picker: DEF-286's editable " +
        "cards are the CR's own requirement and their absence blocked CR-009 once already.",
    ).toHaveCount(1);
    await expect(page.locator("[data-testid=channel-row-email] select").first()).toBeVisible();
  });

  // ══════════════════════════════════════════════════════════════════════
  // 4 · The escalation ladder — CR-009's "ONE HOME" ruling, on screen
  // ══════════════════════════════════════════════════════════════════════
  test("SET-12D · the collections ladder is here, with the $25 floor and the 25% pause", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(rulePath("past_due_reminder"));

    const ladder = panel(page, "Escalation ladder");
    await expect(ladder).toBeVisible();
    // The PO's ruling — *"we bring all internal external ntification rule sat
    // one place"* — is stated to the user as ONE COPY, which is what makes
    // DEF-204's two homes a non-question.
    await expect(ladder.locator("p.panel-hint")).toContainText("there is one copy, not two");

    for (const label of [
      "Friendly reminder, days after the due date",
      "Disconnection warnings, days before cut-off",
      "Final notice, hours before cut-off",
      "Smallest balance worth chasing",
      "Part payment that pauses the chase, as a percentage",
    ]) {
      await expect(ladder.getByText(label, { exact: true })).toBeVisible();
    }

    // THE FIGURES THEMSELVES — the ones DEF-204 said were stored with no
    // screen. This IS their screen now, and these are the numbers the
    // collections run obeys: 3 days · 10 then 5 days · 48 hours · the $25
    // floor · the 25% partial-payment pause (PO 2026-08-12).
    await expect(page.getByTestId("ladder-reminder")).toHaveValue("3");
    await expect(page.getByTestId("ladder-tiers")).toHaveValue("10,5");
    await expect(page.getByTestId("ladder-final")).toHaveValue("48");
    await expect(page.getByTestId("ladder-floor")).toHaveValue("25");
    await expect(page.getByTestId("ladder-pause")).toHaveValue("25");

    // The matrix's own Timing cell for this event, for the contradiction below.
    await expect(page.locator("main.view")).toContainText("Past-due reminder");

    // FINDING (8) — OPEN, and it is the one on this page that could mislead an
    // operator about money.
    //
    // The right rail's "rule in plain English" — the requirement's own
    // *"auto-generated sentence of the FULL rule (audience + channels + timing
    // + exclusions)"* — is built from `trigger_mode`, which is `immediate` for
    // every laddered event. So this page tells a System Admin the past-due
    // reminder goes out **"as soon as it happens"** while the matrix row says
    // *"On the escalation ladder below"* and the ladder card six centimetres
    // away says the first reminder is **3 days after the due date**. One of
    // the three is wrong and it is the sentence written to be the summary.
    //
    // WHAT MUST HAPPEN INSTEAD: `plainEnglishRule` reads `timing_key` (and the
    // ladder) for events that have one, so the sentence says "3 days after the
    // due date, then 10 and 5 days before cut-off".
    //
    // TO INVERT WHEN FIXED: assert the laddered sentence here.
    await expect(
      page.getByTestId("rail-plain-english"),
      "FINDING 8 — the plain-English sentence no longer claims a laddered event is " +
        "immediate. Assert the corrected sentence and strike finding 8.",
    ).toContainText("as soon as it happens");
    await expect(page.getByTestId("rail-plain-english")).toContainText(
      "Accounts on a payment plan are left out.",
    );

    // Save writes the ladder alongside the rule (same button, one transaction
    // per service). Values are unchanged, so the run is idempotent.
    await page.getByTestId("rule-save").click();
    await expect(page.locator(".toast").first()).toContainText("saved");
  });

  // ══════════════════════════════════════════════════════════════════════
  // 5 · C-11 — the staff recipient policy, and the test-queue refusals
  // ══════════════════════════════════════════════════════════════════════
  test("C-11 · a staff rule states the ruled recipient, and the in-app test queues", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(rulePath("billing_run_completed"));

    // BR-NOT-021 as a sentence on the audience card — the ruling the C-section
    // landed, rendered where a System Admin asks "who gets this".
    await expect(page.getByTestId("audience-staff-policy")).toContainText(
      "Sent to the user who started the action; failures also reach every active System " +
        "Admin (PO 2026-08-17, BR-NOT-021 — OQ-261 closed).",
    );

    // The in-app channel is the ONE dispatchable channel (BR-NOT-019) and is
    // offered on this staff event.
    // Since 2026-08-22 the template cell is a PICKER for a System Admin; the
    // stored class is its VALUE (the visible text is the catalog's name).
    await expect(page.getByTestId("channel-template-in_app")).toHaveValue("staff_bulk_summary");

    // FINDING (5) — **CLOSED 2026-08-19 by DEF-265's fix (commit 9dd7862), and
    // this assertion is its inversion**, written the way the contract at the top
    // of this file demands: the old pin fired on the walkthrough of 2026-08-19
    // with *"the in-app test no longer refuses"*, which is the pin doing its job
    // rather than a regression.
    //
    // What it used to do: "Queue a test to me" on the IN-APP channel REFUSED,
    // with wording written for print — *"There is no way to post a test letter
    // to yourself."* — because `rule_service._test_recipient` handled email and
    // SMS and fell through to the print sentence for everything else. The
    // button that exists to prove the pipeline refused on the only channel that
    // could prove it.
    //
    // What it does now: `_test_recipient` resolves the in-app address through
    // `in_app.address_for(actor)` — the signed-in user's own id — and the click
    // ENQUEUES. BR-NOT-005 is untouched: this is a queue row, not a send, and
    // it still waits for `manage.py dispatch_outbound` (DEF-266, open).
    await page.getByTestId("channel-test-in_app").click();
    const inAppTest = page.getByTestId("test-result");
    await expect(
      inAppTest,
      "DEF-265 HAS REGRESSED — the in-app test is refusing again. In-app is the one channel " +
        "with a real adapter (BR-NOT-019) and its address is the signed-in user's own id; a " +
        "refusal here is the button that proves the pipeline refusing on the only pipeline " +
        "that runs.",
    ).toContainText("A test message is on the queue for");

    // FINDING (11) — OPEN. DEF-265's fix cleared the REFUSAL and left the
    // SUCCESS sentence channel-blind, so the one channel that needs no provider
    // at all is told a provider is missing.
    //
    // `notifications.rules.testQueued` is ONE catalogue string for all four
    // channels — *"A test message is on the queue for {{address}}. Nothing
    // leaves the building yet — no mail provider is connected."* On in-app both
    // halves are wrong: an in-app message is not supposed to leave the building,
    // and no mail provider is involved in delivering it (BR-NOT-019 makes the
    // platform its own provider). The person who just queued the ONE message
    // this product can actually deliver is told, on screen, that nothing will
    // happen.
    //
    // This is DEF-264's shape one turn on — a single sentence standing in for
    // four different truths — and it survived the fix that was written for its
    // sibling, which is why it is pinned here rather than trusted to be noticed.
    //
    // TO INVERT WHEN FIXED: assert the in-app sentence names the bell, and drop
    // the mail-provider clause from this assertion only (the email one below
    // keeps it — on email it is TRUE).
    await expect(
      inAppTest,
      "FINDING 11 (DEF-284) — the queued sentence is no longer channel-blind. Assert the " +
        "in-app wording here and strike finding 11.",
    ).toContainText("no mail provider is connected");

    // FINDING (12) — OPEN. The address a person reads back is the raw user
    // UUID: *"A test message is on the queue for 01a013f4-311c-7320-8de2-…"*.
    // In-app's address IS the user id, correctly (`in_app.address_for`), but
    // the screen prints the storage key where every other channel prints
    // something a person recognises — their own email address on email, their
    // own mobile number on SMS. DEF-268 and DEF-272 are the same class on this
    // very surface: a machine token rendered where a human sentence belongs.
    //
    // TO INVERT WHEN FIXED: assert the signed-in user's name or email here.
    await expect(
      inAppTest,
      "FINDING 12 (DEF-285) — the in-app test no longer reports a raw UUID. Assert the " +
        "human-readable addressee and strike finding 12.",
    ).toContainText(/on the queue for [0-9a-f]{8}-[0-9a-f]{4}-/);

    // The email channel DOES queue, and says both halves — queued, and it will
    // not leave the building. BR-NOT-005 is satisfied by queueing, not by
    // refusing.
    await page.goto(rulePath("bill_ready"));
    await page.getByTestId("channel-test-email").click();
    await expect(page.getByTestId("test-result")).toContainText(
      "A test message is on the queue for dana@brazosbendutilities.com. Nothing leaves the " +
        "building yet — no mail provider is connected.",
    );
  });

  // ══════════════════════════════════════════════════════════════════════
  // 6 · The bell
  // ══════════════════════════════════════════════════════════════════════
  test("the shell bell is wired, and nothing a person can click will ever fill it", async ({
    page,
  }) => {
    await signIn(page);

    const bell = page.locator("details.shell-bell");
    await expect(bell).toBeVisible();
    // The control is an icon, so the name a person gets is its label. Unread
    // ZERO renders the plain one — "Notifications — N unread" is the other —
    // and the badge is ABSENT rather than a "0".
    await expect(bell.locator("summary")).toHaveAttribute("aria-label", "Notifications");
    await expect(bell.locator(".bell-badge")).toHaveCount(0);

    await bell.locator("summary").click();
    // FINDING (6) — OPEN. This is the honest state of CR-009's proof channel.
    //
    // The C-section's worked figure is *1,204 accounts, 3 failed → ONE message,
    // three bells*, and it CANNOT be reproduced from a browser on this
    // deployment:
    //   · no product surface fires a staff event — the bill run does not call
    //     `queue_bulk_summary` (BR-NOT-018, OQ-262);
    //   · the SET-12D test button refuses the in-app channel (finding 5);
    //   · and a queued row still needs `manage.py dispatch_outbound` — a shell
    //     command — before it becomes a message in an inbox.
    // So every human on this stack sees exactly this: "You're all caught up."
    //
    // WHAT MUST HAPPEN INSTEAD: at least one browser-reachable action that
    // delivers an in-app message (the in-app test send is the cheapest), so
    // that BR-NOT-019's claim — *"a message arriving in the bell is proof the
    // queue, the rule, the template resolution, the rendering and the
    // dispatcher all work"* — is provable by the person who has to believe it.
    //
    // TO INVERT WHEN FIXED: this becomes the bulk-summary text —
    // "Billing run finished. 1204 processed · 3 failed …" — and the assertion
    // moves to `.bell-item`.
    await expect(
      bell.locator(".bell-empty"),
      "FINDING 6 — the bell is no longer empty: something in the product now delivers an " +
        "in-app message. Assert the message text here and strike finding 6.",
    ).toHaveText("You're all caught up.");
    await expect(bell.locator(".bell-item")).toHaveCount(0);
  });

  // ══════════════════════════════════════════════════════════════════════
  // 7 · C-12 — the "Email sender" card: fill it, be refused, save, clear
  // ══════════════════════════════════════════════════════════════════════
  test("C-12 · the sender card refuses a pasted password by name, then stores a reference", async ({
    page,
  }) => {
    await signIn(page);
    await openNotificationsTab(page);

    const card = panel(page, "Email sender (SMTP)");
    await expect(card).toBeVisible();

    // The three sentences this card exists to keep true (hard-won law 1: no
    // implied verification, no implied send).
    await expect(page.getByTestId("sender-no-send")).toContainText(
      "no SMTP adapter is built and no message leaves the building on any email path " +
        "(BR-NOT-013)",
    );
    await expect(card.getByText("Secret reference (not the password)")).toBeVisible();
    await expect(card.getByText(/never the password itself/)).toBeVisible();
    await expect(card.getByText(/SPF\/DKIM verification is not built/)).toBeVisible();

    // Whatever a previous run left, the tenant starts this test unconfigured.
    for (const field of [
      "smtp_host",
      "smtp_port",
      "smtp_username",
      "smtp_secret_ref",
      "sender_from_address",
    ]) {
      await page.getByTestId(`sender-${field}`).fill("");
    }
    await card.getByRole("button", { name: "Save sender" }).click();
    await expect(page.getByTestId("sender-route")).toContainText(
      "no tenant SMTP is configured (a host and a from-address are the minimum)",
    );

    // ── THE REFUSAL. The column NEVER holds a password. ───────────────────
    await page.getByTestId("sender-smtp_secret_ref").fill("hunter2 correct horse battery");
    await card.getByRole("button", { name: "Save sender" }).click();
    const alert = page.locator("p.settings-refusal[role=alert]");
    await expect(alert).toBeVisible();
    await expect(alert).toContainText("(BR-NOT-023)");
    // …and it did NOT store it: the route still reads unconfigured.
    await expect(page.getByTestId("sender-route")).toContainText("no tenant SMTP is configured");

    // FINDING (10) — **CLOSED 2026-08-19 by DEF-264's fix (commit 86f748a), and
    // this assertion is its inversion.** It fired on the walkthrough of
    // 2026-08-19 with the whole server sentence in the "received" column, which
    // is the pin doing its job.
    //
    // What it used to do: `notifications.dispatch.refused` read "That dispatch
    // setting was refused." in all ELEVEN catalogues, with no `{{detail}}`
    // placeholder, so i18next dropped the parameter and the System Admin who
    // had just pasted a password was told nothing — not which field, not why,
    // and not that the password must never go there. It swallowed EVERY refusal
    // on this tab: quiet-hours ordering, batch size, port range, a from-address
    // with no `@`, an unknown field.
    //
    // What it does now: the key carries `{{detail}}` as its sibling
    // `notifications.queue.refused` always did, so `settings_api._refused`'s
    // own promise — *"the refusal's own sentence travels in `params.detail`,
    // WHICH IS WHAT THE SCREEN RENDERS (BR-SHL-020)"* — is finally true on the
    // one refusal C-12 exists to prove by name.
    await expect(
      alert,
      "DEF-264 HAS REGRESSED — the S8 refusal has collapsed back to its bare nine words. The " +
        "server's sentence travels in params.detail and the catalogue key must render it; " +
        "without it a System Admin who pastes a password is told nothing at all.",
    ).toContainText(
      "that does not look like a secret REFERENCE. This field holds the NAME of a secret in " +
        "your deployment's own store (an environment variable name, a vault path) — never " +
        "the password itself. The password never enters this product's database.",
    );

    // ── THE ACCEPTED FORM: a reference, not a credential. ─────────────────
    await page.getByTestId("sender-smtp_host").fill("smtp.office365.com");
    await page.getByTestId("sender-smtp_port").fill("587");
    await page.getByTestId("sender-smtp_username").fill(`billing+${RUN_STAMP}@brazosbend.test`);
    await page.getByTestId("sender-smtp_secret_ref").fill("SMTP_PASSWORD_BRAZOSBEND");
    await page.getByTestId("sender-sender_from_address").fill("billing@brazosbend.test");
    await card.getByRole("button", { name: "Save sender" }).click();
    await expect(page.locator(".toast")).toHaveText(
      "Sender saved. Nothing sends yet — this is the plug for the day an email adapter lands.",
    );

    // `sender_route()` now resolves to the tenant's own SMTP — and still says
    // nothing sends. Both halves, in the server's own words, on screen.
    await expect(page.getByTestId("sender-route")).toContainText(
      "this utility's own SMTP (smtp.office365.com) with 'billing@brazosbend.test' as the " +
        "from-address — C-12's default source. NOTHING SENDS YET",
    );

    // And the dispatch switch is UNTOUCHED by all of that: WHAT WOULD BE USED
    // and WHETHER anything sends are different questions, and the card next
    // door still reads Off.
    const dispatch = panel(page, "Dispatch settings");
    await expect(dispatch.locator("li", { hasText: "Email" }).first()).toContainText("Off");

    // ── Leave the tenant as we found it (the re-run bar). ─────────────────
    for (const field of [
      "smtp_host",
      "smtp_port",
      "smtp_username",
      "smtp_secret_ref",
      "sender_from_address",
    ]) {
      await page.getByTestId(`sender-${field}`).fill("");
    }
    await card.getByRole("button", { name: "Save sender" }).click();
    await expect(page.getByTestId("sender-route")).toContainText("no tenant SMTP is configured");
  });

  // ══════════════════════════════════════════════════════════════════════
  // 8 · C-13 — the four A15 send-time elections
  // ══════════════════════════════════════════════════════════════════════
  test("C-13 · the four elections are ON by default and say what reads each one", async ({
    page,
  }) => {
    await signIn(page);
    await openNotificationsTab(page);

    const card = panel(page, "Send-time elections");
    await expect(card).toBeVisible();
    await expect(page.getByTestId("elections-default-on")).toHaveText(
      "All four start ON by Product Owner ruling (2026-08-17). Turning one off applies from " +
        "the next action; nothing already queued is recalled — and queueing is not sending.",
    );

    for (const row of [
      "Receipt when a payment is recorded",
      "Credit-notice email",
      "Bookkeeper copies (reconcile / QuickBooks sync)",
      "Lockbox receipts",
    ]) {
      await expect(card.getByText(row, { exact: true })).toBeVisible();
    }

    // THE ONE WIRED CONSUMER says what reads it…
    await expect(
      card.getByText(/read at record time by apps\/payments\/receipts\.py/),
    ).toContainText(
      "recording a payment queues the customer's receipt (BR-PAY-024's RCT print document) " +
        "through the platform outbound queue. Queueing is not sending",
    );
    // …and the other three are honest about being read by nothing (hard-won
    // law 2 as data, which is the thing a walkthrough has to confirm is on the
    // SCREEN rather than in a payload).
    await expect(card.getByText(/the credit-issue path does not queue/)).toContainText(
      "consulted by nothing today",
    );
    await expect(card.getByText(/BR-LED-020's bookkeeper reconcile\/QB-sync copies/)).toContainText(
      "consulted by nothing today",
    );
    await expect(card.getByText(/the lockbox import does not queue receipts/)).toContainText(
      "consulted by nothing today",
    );

    // Whatever the last run left, normalise to ON, then switch OFF and back —
    // both states asserted as the text a person reads, not as a checkbox.
    const receiptRow = card.locator("tbody tr").first();
    if ((await page.getByTestId("election-receipt_on_record_payment").innerText()) === "Off") {
      await receiptRow.getByRole("button", { name: "Turn on" }).click();
      await expect(page.getByTestId("election-receipt_on_record_payment")).toHaveText("On");
    }
    await expect(page.getByTestId("election-receipt_on_record_payment")).toHaveText("On");
    await receiptRow.getByRole("button", { name: "Turn off" }).click();
    await expect(page.getByTestId("election-receipt_on_record_payment")).toHaveText("Off");
    await receiptRow.getByRole("button", { name: "Turn on" }).click();
    await expect(page.getByTestId("election-receipt_on_record_payment")).toHaveText("On");
  });

  // ══════════════════════════════════════════════════════════════════════
  // 9 · C-13's wired consumer, end to end: OFF is obeyed — and barely said
  // ══════════════════════════════════════════════════════════════════════
  test("C-13 · recording a payment queues a receipt when ON and none when OFF", async ({
    page,
  }) => {
    test.slow(); // two payments through the real money path
    await signIn(page);
    await openNotificationsTab(page);

    const card = panel(page, "Send-time elections");
    const receiptRow = card.locator("tbody tr").first();
    if ((await page.getByTestId("election-receipt_on_record_payment").innerText()) === "Off") {
      await receiptRow.getByRole("button", { name: "Turn on" }).click();
      await expect(page.getByTestId("election-receipt_on_record_payment")).toHaveText("On");
    }
    const before = await waitingCount(page);

    // ── ELECTION ON → one more message waiting. ──────────────────────────
    const firstProblems = await recordSmallPayment(page);
    await openNotificationsTab(page);
    await expect.poll(async () => waitingCount(page), { timeout: 20_000 }).toBe(before + 1);

    // FINDING (3) — OPEN. The result panel a clerk reads after recording the
    // payment prints the RAW TRANSLATION KEY, because `payments.problem.
    // receipt_queued`, `…receipt_election_off`, `…receipt_election_unreadable`,
    // `…receipt_queue_unavailable` and `…receipt_queue_refused` are absent from
    // every one of the eleven catalogues. C-13 added the outcome codes and no
    // catalogue entries; `ProblemList` renders `t(...)`, and i18next with no
    // missing-key handler returns the key.
    //
    // So the CR's *"OFF must be obeyed AND said"* is HALF met: it is obeyed
    // (proved by the tile counts here) and what the screen says is
    // "payments.problem.receipt_election_off".
    //
    // TO INVERT WHEN FIXED: assert the English sentence instead.
    expect(
      firstProblems,
      "FINDING 3 — the receipt outcome now has catalogue wording. Assert the English " +
        "sentence here and strike finding 3.",
    ).toContain("payments.problem.receipt_queued");

    // ── ELECTION OFF → nothing more waiting. ─────────────────────────────
    await openNotificationsTab(page);
    await receiptRow.getByRole("button", { name: "Turn off" }).click();
    await expect(page.getByTestId("election-receipt_on_record_payment")).toHaveText("Off");
    const afterOff = await waitingCount(page);

    const secondProblems = await recordSmallPayment(page);
    expect(secondProblems).toContain("payments.problem.receipt_election_off");
    await openNotificationsTab(page);
    // OBEYED: the queue did not grow. This is the assertion the CR's ruling
    // actually turns on, and it is a number on a card, not a payload.
    await expect.poll(async () => waitingCount(page), { timeout: 20_000 }).toBe(afterOff);

    // Leave it ON — BR-NOT-022's shipped default, and the state the next run
    // (and the next person) should find.
    await receiptRow.getByRole("button", { name: "Turn on" }).click();
    await expect(page.getByTestId("election-receipt_on_record_payment")).toHaveText("On");
  });

  // ══════════════════════════════════════════════════════════════════════
  // 10 · C-14 — the plan-void notice's default language
  // ══════════════════════════════════════════════════════════════════════
  test("C-14 · the plan-void notice has real wording, and claims no flow that exists", async ({
    page,
  }) => {
    await signIn(page);
    await page.goto(templatesPath());
    await page.locator("table.data-table").waitFor({ timeout: 30_000 });
    await page.locator("[data-testid=template-open-plan_notice_void]").click();
    await page.locator("[data-testid=template-back]").waitFor({ timeout: 30_000 });

    // THE DEFAULT LANGUAGE IS THERE, rendered through the real preview engine
    // with the sample identity — the wording a customer would receive.
    const preview = page.getByTestId("preview-pane");
    await expect(preview).toContainText(
      "The payment plan on account SAMPLE-ACCOUNT has been voided because of missed",
    );
    await expect(preview).toContainText(
      "Every payment you have made under the plan has been kept and applied to your",
    );
    // The C-14 record's own constraint: the body states NO miss threshold,
    // because no rule sets one. If a number appears here, a lane invented it.
    await expect(preview).not.toContainText("three missed");
    await expect(preview).not.toContainText("3 missed");

    // FINDING (4) — OPEN. The "Used by" line a System Admin reads still says
    // the BODY DOES NOT EXIST — `catalogs.LISTINGS["plan_notice_void"].used_by`
    // was not amended when C-14 authored and seeded that body on 2026-08-18.
    // It is DEF-230's class exactly: a stale Used-by string on a screen a
    // utility reads, which no gate can see.
    //
    // The half of the sentence that is RIGHT is the half the 'nodrop' ruling
    // protects — nothing voids a plan and nothing schedules this notice — so
    // the fix is to keep "Nothing yet" and drop "its body does not (OQ-207)".
    //
    // TO INVERT WHEN FIXED: assert the corrected sentence.
    await expect(
      page.getByTestId("where-used"),
      "FINDING 4 — the Used-by string has been corrected. Assert the new sentence and strike " +
        "finding 4.",
    ).toHaveText("Nothing yet — BR-NOT-007's class exists, its body does not (OQ-207)");

    // The other half, and it must stay true: nothing on this screen offers to
    // void a plan or to schedule the notice. The only send control is the test
    // send, and it is disabled with its reason (BR-SHL-025).
    await expect(page.getByText(/No test send in this release, on any channel/)).toBeVisible();
  });
});

/**
 * Records one small payment on the fixture account through the real S22 form
 * and returns the result panel's problem lines — the text a clerk reads after
 * the money is recorded.
 *
 * Deliberately NOT the golden figure: W4-money-render owns GT-1, and this
 * spec only needs the RECEIPT side-effect, so it moves the smallest amount
 * that is still a payment.
 */
async function recordSmallPayment(page: Page): Promise<string[]> {
  await page.goto(`/${tenant()}/payments/record`);
  await page.getByRole("button", { name: "Record payment", exact: true }).first().click();
  const form = page.getByRole("dialog");
  await expect(form).toBeVisible();
  // ⚠ ONE CONTROL SINCE 2026-09-23 (`DEF-PAY-6319`) — type and choose on the
  // same element; the matches are `role="option"` rows in its panel.
  await form.locator("#account_id").fill(fixtureAccountNo());
  await form.getByRole("option", { name: fixtureAccountNo(), exact: true }).click();
  await form.locator("#amount").fill("1.00");
  await form.locator("#posted_at").fill("2026-07-18");
  await form.locator("#cleared_at").fill("2026-07-20");
  await form.locator("#method").selectOption({ index: 1 });
  await form.getByRole("button", { name: "Record payment", exact: true }).click();
  const problems = page.locator("ul.pay-result-problems li");
  await problems.first().waitFor({ timeout: 30_000 });
  return problems.allInnerTexts();
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-009@walkthrough (12-governance/11-change-requests.md → CR-009 in full, all four ruling sets and both build records · 12-governance/13-change-process.md §8 THE CLOSURE BAR · apps/notifications/{rule_catalog,rules_api,rule_service,sender_config,bulk_summary,staff_recipients,in_app}.py · apps/payments/receipts.py · 07-frontend/src/features/notifications/{NotificationRules,SettingsNotificationsTab}.tsx · components/{AppShell,ShellWithSession}.tsx)
// generated: 2026-08-18 by qa (CR-009 browser-walkthrough lane — paying hard-won law 6 on the C-section)
// checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
// gates: this file IS the gate. Six findings pinned; each states how to invert it when fixed.
// exceptions: (1) NO BULK-SUMMARY PROOF — finding 6: nothing browser-reachable delivers an in-app message, so the C-11 worked figure (1,204 / 3 → one message, three bells) could not be asserted from a browser and is reported rather than faked. (2) THE THREE-BELL FAN-OUT IS UNTESTABLE ON THIS FIXTURE ANYWAY — `brazosbend` has exactly ONE active System Admin (Dana), who is also the initiator, so the ruled audience resolves to one mailbox here by design (`staff_recipients.resolve_staff_recipients` dedupes the initiator against the admin list). (3) NO ROLE MATRIX — the Executive read-only and Billing-Clerk no-access halves of the settings permission rule need a second signed-in user; DEF-196's own spec owns that.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
