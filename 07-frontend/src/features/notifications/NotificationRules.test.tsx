// ── Trace ──────────────────────────────────────────────
// Story:    US-NOT-017 (SET-12 the notification event matrix + SET-12D the event
//           rule page — CR-009)   Screens: S8
// Rules:    BR-NOT-017 (ONE HOME for every notification rule) ·
//           BR-NOT-018 (an event with no trigger is DRAWN and says so) ·
//           BR-NOT-005 (queue only — "Send test" ENQUEUES) ·
//           BR-NOT-013 (`delivered`/`failed` render NOT REPORTED, never 0) ·
//           BR-SHL-025 (a forbidden control renders disabled WITH its reason)
// ───────────────────────────────────────────────────────
// The assertions worth the file, in the order they would break:
//
//   1. **The three named-but-absent channels are DRAWN and each carries its own
//      reason.** Portal, Mail and In-app are in the PO's requirement and are
//      implemented nowhere. A screen that hid them makes the product disagree
//      with the requirement; a screen that drew live toggles for them is worse,
//      because a switch a utility can turn on is a promise.
//   2. **A row with no trigger says so, with its open-question ID**, and is
//      still fully configurable — which is exactly what BR-NOT-018 rules.
//   3. **The staff Audience card offers NO recipient** and states OQ-261. Any
//      role picker here would silently decide who a utility wakes at 3 a.m.
//   4. **The Last-30-days rail never prints a number.** `delivered` and
//      `failed` are provider facts nothing in this repo can write, so it prints
//      the server's own reason. "0 delivered of 142 sent" reads as a delivery
//      failure when the truth is that nobody is reporting.
//   5. **The escalation ladder shows the tenant's own five figures**, including
//      the $25.00 floor and the 25% pause, which have never had a screen
//      anywhere before this one (DEF-204, DEF-097).
//
// Every one was shown RED first against a stub that returned the matrix with
// `unavailable_channels: []`, `trigger_blocked_by: null` and a ladder of zeroes
// — see the lane report for the verbatim failures.
//
// No DOM library is in package.json, so these assert on react-dom/server static
// markup — real render output, no new dependency (the idiom StateFrame.test.tsx
// established and TemplateCatalog.test.tsx follows).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { defaultRequestState } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";

import "@/i18n";

import type {
  NotificationRuleDetail,
  NotificationRuleMatrix,
  NotificationRuleRow,
} from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { draftOf } from "@/api/notificationRuleEndpoints";

import {
  AudienceCard,
  ChannelsCard,
  EVENT_CODES,
  PRINT_CHANNEL,
  LADDER_KEYS,
  LadderCard,
  RuleMatrix,
  RuleRail,
  TimingCard,
  applyRuleTableState,
  eventCode,
  plainEnglishRule,
  printIsTheFloor,
  ruleTableConfig,
} from "./NotificationRules";

const NO_DISPATCHER =
  "no dispatcher run and no provider integration ship in this release, on any channel " +
  "including print. A message is composed, QUEUED and visible, and nothing leaves the " +
  "building. A rule switched on here decides what WOULD be queued.";

const NO_DELIVERY_COUNTS =
  "'delivered' needs a provider confirmation and 'bounced' needs an ESP webhook, and no " +
  "provider adapter exists on any channel. Showing 0 delivered would read as a delivery " +
  "failure when the truth is that nobody is reporting.";

// ⚠ **THIS WAS `MAIL_REASON` UNTIL 2026-09-07 AND ITS SENTENCE WAS FICTION
// BY THEN (`CR-084`).** *"there is no customer portal in this product"* stopped
// being true when `CR-068` shipped one, and this file went on passing because
// the fixture SUPPLIES the refusal it then asserts is drawn — a test asserting
// the test. The refusal MECHANISM is what is under test, so it is pointed at a
// refusal the product still makes.
const MAIL_REASON =
  "'Mail' on a disconnect notice means PHYSICAL POST, which is a fulfilment vendor and " +
  "not a channel flag. The platform's paper channel is `pdf_print` — it RENDERS the " +
  "letter; who franks and posts it is an integration nobody has chosen.";

function aRow(overrides: Partial<NotificationRuleRow> = {}): NotificationRuleRow {
  return {
    key: "bill_ready",
    category: "billing",
    audience: "customer",
    channels: ["email", "sms"],
    unavailable_channels: [{ channel: "mail", reason: MAIL_REASON }],
    template_classes: { email: "email_bill_ready" },
    trigger_blocked_by: null,
    timing_key: "on_issue",
    has_ladder: false,
    staff_recipient_policy: null,
    enabled: true,
    customer_scope: "all_contacts",
    service_scope: "all",
    plan_class: "all",
    skip_accounts_on_payment_plan: false,
    trigger_mode: "immediate",
    offset_days: null,
    fixed_time: null,
    quiet_hours_mode: "respect",
    failure_policy: "retry_3_days_then_email",
    channel_rules: [
      {
        channel: "email",
        enabled: true,
        template_code: "email_bill_ready",
        language_mode: "auto",
        dispatchable: false,
        dispatch_problem: { code: "channel_deferred" },
      },
    ],
    staff_recipient: null,
    ...overrides,
  };
}

const POSTURE = {
  dispatch_runs_in_this_release: false,
  delivery_counts_available: false,
  delivery_counts_reason: NO_DELIVERY_COUNTS,
  requirement_claims_event_count: 16,
  built_event_count: 15,
};

function aMatrix(rows: NotificationRuleRow[]): NotificationRuleMatrix {
  return {
    results: rows,
    count: rows.length,
    categories: ["billing", "payments", "collections", "field_work", "staff_system"],
    ...POSTURE,
  };
}

function aDetail(overrides: Partial<NotificationRuleDetail> = {}): NotificationRuleDetail {
  return { ...aRow(), ...POSTURE, ladder: null, ...overrides };
}

const T = (key: string, params?: Record<string, unknown>): string =>
  params === undefined ? key : `${key} ${JSON.stringify(params)}`;

/** `renderToStaticMarkup` escapes `'` to `&#x27;` and `"` to `&quot;`, so an
 *  assertion written in plain prose never matches. Normalising the OUTPUT keeps
 *  each test readable in the words the screen actually shows — the alternative
 *  is six hand-escaped string literals nobody can check against the product. */
function text(markup: string): string {
  return markup
    .replaceAll("&#x27;", "'")
    .replaceAll("&quot;", '"')
    .replaceAll("&amp;", "&");
}

/**
 * Just the `<tbody>` of the rendered markup.
 *
 * ⚠ NEEDED SINCE CR-048 F1, and the reason is worth stating: `DataTable` brings
 * a toolbar, a `+ Filter` panel, a COLUMN CHOOSER with one checkbox per column
 * and a pager with disabled buttons. A whole-markup `toContain("disabled")` or
 * a count of `type="checkbox"` now measures the framework's chrome and not the
 * rows — 18 checkboxes where the assertion means 1. Scoping to the body keeps
 * each assertion pointed at the thing it was written about.
 */
function body(markup: string): string {
  const from = markup.indexOf("<tbody");
  const to = markup.indexOf("</tbody>");
  expect(from, "no table body was rendered at all").toBeGreaterThan(-1);
  return markup.slice(from, to);
}

/** The one rendered tag carrying this `data-testid`, so an assertion about a
 *  control is asked of THAT control and not of the page around it. */
function tag(markup: string, testid: string): string {
  const match = markup.match(new RegExp(`<[a-z]+[^>]*data-testid="${testid}"[^>]*>`));
  expect(match, `nothing rendered with data-testid="${testid}"`).not.toBeNull();
  return (match as RegExpMatchArray)[0];
}

function render(node: React.ReactElement): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ToastProvider>{node}</ToastProvider>
    </QueryClientProvider>,
  );
}

describe("SET-12 · the event matrix", () => {
  it("draws a channel the platform does not have, WITH its reason, and not as a toggle", () => {
    // BR-SHL-025. Hiding it makes the product disagree with the requirement;
    // a live toggle for it would be a promise.
    // ⚠ CR-048 F1 — through `RuleMatrix` now, because the per-row component is
    // gone: the matrix is one flat `DataTable` and a row is its cell
    // renderers. The REAL component either way; a harness that re-implemented
    // the markup would assert that the TEST draws a reason, which is the one
    // thing this file must not prove.
    const markup = text(
      render(
        <RuleMatrix
          matrix={aMatrix([aRow()])}
          readOnly={false}
          working={false}
          t={T}
          onOpen={() => undefined}
          onToggle={() => undefined}
        />,
      ),
    );
    expect(markup).toContain(MAIL_REASON);
    // and it is NOT a checkbox — the only checkbox in a row is the On toggle.
    const checkboxes = body(markup).match(/type="checkbox"/g) ?? [];
    expect(checkboxes).toHaveLength(1);
  });

  // ⚠ INVERTED, NOT DELETED (CR-016, 2026-08-19). This test used to be called
  // *"prints the count discrepancy instead of hiding it"* and asserted that the
  // screen rendered `notifications.rules.countDiscrepancy` with `claimed: 16`
  // and `built: 15`. It PINNED AS A FACT the thing the Product Owner objected
  // to — a sentence about our own requirements document, shown to a System
  // Admin at a small utility who can do nothing with it. Deleting the test would
  // leave the callout free to come back; inverting it keeps the ruling enforced.
  it("does NOT print the requirement count discrepancy to a utility user", () => {
    const markup = text(
      render(
      <RuleMatrix
        matrix={aMatrix([aRow()])}
        readOnly={false}
        working={false}
        t={T}
        onOpen={() => undefined}
        onToggle={() => undefined}
      />,
      ),
    );
    expect(markup).not.toContain("notifications.rules.countDiscrepancy");
    expect(markup).not.toContain("rule-count-discrepancy");
    // The counts themselves are still SERVED — only the sentence is gone — so a
    // reader of the API still sees the discrepancy reported rather than hidden.
    expect(aMatrix([aRow()]).requirement_claims_event_count).toBe(16);
    expect(aMatrix([aRow()]).built_event_count).toBe(15);
  });

  it("states the release posture in the server's own words", () => {
    const markup = text(
      render(
      <RuleMatrix
        matrix={aMatrix([aRow()])}
        readOnly={false}
        working={false}
        t={T}
        onOpen={() => undefined}
        onToggle={() => undefined}
      />,
      ),
    );
    // DEF-NOT-10537 — the matrix draws no release sentence: it said nothing
    // leaves the building while email sends. Each channel's line is the
    // Channel status card's.
    expect(markup).not.toContain(NO_DISPATCHER);
    expect(markup).not.toContain("rule-release-posture");
    expect(markup).not.toContain("leaves the building");
  });

  it("BR-NOT-018 — a row with no trigger is drawn AND says so, with the id off the sentence", () => {
    const markup = text(
      render(
      <RuleMatrix
        matrix={aMatrix([aRow({ key: "daily_digest", trigger_blocked_by: "OQ-262" })])}
        readOnly={false}
        working={false}
        t={T}
        onOpen={() => undefined}
        onToggle={() => undefined}
      />,
      ),
    );
    // Drawn… — addressed by the event button the row opens with, because
    // `DataTable` owns the `<tr>` and stamps no id of its own on it.
    expect(markup).toContain("rule-open-daily_digest");
    // …and honest about it. The SENTENCE is what a utility user reads and it
    // still says the event does not fire.
    expect(markup).toContain("notifications.rules.noTrigger");
    // ⚠ INVERTED (CR-016, 2026-08-19). This line used to assert
    // `'"oq":"OQ-262"'` — the open-question id INTERPOLATED INTO THE SENTENCE, so
    // a System Admin read "Nothing in the product fires this event yet
    // (OQ-262)". The PO objected to exactly that: *"you should follow screen
    // that is given - you are adding your own content and details on screen/Ui"*.
    // The id is not lost and this test still pins it — it moved to an attribute,
    // which support can read off the DOM and a clerk never sees.
    expect(markup).not.toContain('"oq":"OQ-262"');
    expect(markup).toContain('data-blocked-by="OQ-262"');
  });

  it("a read-only role sees the toggle DISABLED with its reason, never missing", () => {
    const markup = text(
      render(
      <RuleMatrix
        matrix={aMatrix([aRow()])}
        readOnly
        working={false}
        t={T}
        onOpen={() => undefined}
        onToggle={() => undefined}
      />,
      ),
    );
    expect(markup).toContain('type="checkbox"');
    expect(markup).toContain("disabled");
    expect(markup).toContain("notifications.rules.readOnlyReason");
  });
});

/** The editors' draft, seeded exactly as the page seeds it. */
function draftFor(detail: NotificationRuleDetail) {
  return draftOf(detail);
}

const NOOP = () => undefined;

describe("SET-12D · the rule page", () => {
  // ⚠ AMENDED 2026-08-18 — this case used to assert the OQ-261 refusal note
  // ("staffRecipientUnresolved" + the OQ id). The PO closed the question
  // (2026-08-17 → BR-NOT-021), so the card now STATES the ruled policy in the
  // server's own words. NOT loosened: still no picker of any kind, because the
  // recipient is platform law, not a per-rule choice — and since the DEF-286
  // editors landed (2026-08-22) this assertion is the one that keeps them off
  // the staff card.
  it("BR-NOT-021 — a staff rule STATES the ruled recipient policy and still offers no picker", () => {
    const POLICY =
      "Sent to the user who started the action; failures also reach every active " +
      "System Admin (PO 2026-08-17, BR-NOT-021 — OQ-261 closed).";
    const detail = aDetail({
      key: "sla_breach",
      audience: "staff",
      staff_recipient_policy: POLICY,
    });
    const markup = text(
      render(
      <AudienceCard
        rule={detail}
        readOnly={false}
        t={T}
        draft={draftFor(detail)}
        serviceRows={null}
        onChange={NOOP}
      />,
      ),
    );
    expect(markup).toContain("notifications.rules.staffRecipientRuled");
    expect(markup).toContain("audience-staff-policy");
    // The SERVER's sentence, verbatim — the screen must not re-word the rule.
    expect(markup).toContain("BR-NOT-021");
    // No picker of any kind — the whole point. `readOnly={false}` above is
    // what makes this the load-bearing case: even for a System Admin, a staff
    // audience card draws no editor.
    expect(markup).not.toContain("<select");
    expect(markup).not.toContain("audience-scope");
  });

  it("DEF-286 — a customer rule's audience card is PICKERS for a System Admin, every field an EDITABLE_RULE_FIELDS member", () => {
    const detail = aDetail();
    const markup = text(
      render(
        <AudienceCard
          rule={detail}
          readOnly={false}
          t={T}
          draft={draftFor(detail)}
          serviceRows={[{ service: "electric", name: "Electric" }]}
          onChange={NOOP}
        />,
      ),
    );
    expect(markup).toContain("audience-scope");
    // The four editors — customer scope, service scope, plan class, the
    // payment-plan skip — and nothing that is not an editable rule field.
    expect(markup).toContain("<select");
    expect(markup).toContain('id="rule-customer-scope"');
    expect(markup).toContain('id="rule-service-scope"');
    expect(markup).toContain('id="rule-plan-class"');
    expect(markup).toContain('id="rule-skip-plans"');
    // The service picker offers the tenant's REAL service beside `all`.
    expect(markup).toContain("Electric");
    expect(markup).toContain("notifications.rules.serviceScope.all");
    expect(markup).not.toContain("notifications.rules.staffRecipientRuled");
  });

  it("DEF-196's split — an Executive keeps the READ view of the audience, with the standing reason", () => {
    const markup = text(
      render(
        <AudienceCard
          rule={aDetail()}
          readOnly={true}
          t={T}
          draft={draftFor(aDetail())}
          serviceRows={null}
          onChange={NOOP}
        />,
      ),
    );
    expect(markup).toContain("audience-scope");
    expect(markup).not.toContain("<select");
    expect(markup).toContain("notifications.rules.readOnlyReason");
  });

  it("BR-NOT-013 — the Last 30 days rail prints the reason, never a zero", () => {
    const markup = text(render(<RuleRail rule={aDetail()} t={T} />));
    // DEF-NOT-10537 — the screen's own key, in eleven languages; the server's
    // English sentence (here the fixture's) is no longer drawn.
    expect(markup).toContain("notifications.rules.rail.deliveryUnreported");
    expect(markup).not.toContain(NO_DELIVERY_COUNTS);
    expect(markup).not.toMatch(/>0</);
  });

  it("CR-048 F4 — the rail carries all three halves, and invents neither of the two it cannot fill", () => {
    // 1 · the rule in plain English · 2 · the last thirty days · 3 · who
    // changed it last. The wire fills only the first: there is no
    // `last_30_days_*` field on `RuleView.as_wire()` (CR-048 wave B6 is the
    // task that adds it and it has not landed) and no `updated_at`/actor
    // either, even though the model HAS `updated_at` and the save writes a
    // full before→after audit row. So the second prints the server's reason
    // and the third says where the record IS.
    const markup = text(render(<RuleRail rule={aDetail()} t={T} />));
    expect(markup).toContain("rail-plain-english");
    expect(markup).toContain("notifications.rules.rail.last30");
    expect(markup).toContain("notifications.rules.rail.lastChanged");
    expect(markup).toContain("rail-last-changed");
    // No invented figure — DEF-127. ⚠ Asked as "no element whose text IS a
    // number", not as a phrase match: the server's own reason contains the
    // words *"Showing 0 delivered would read as a delivery failure"*, so a
    // regex looking for "0 delivered" fires on the sentence that exists to
    // prevent exactly that. The first draft did, and passed nothing.
    expect(markup).not.toMatch(/>\s*[\d,]+\s*</);
  });

  it("a channel with no template says so and cannot be tested — nor ENABLED, and the enable control says why", () => {
    const detail = aDetail({
      channel_rules: [
        {
          channel: "sms",
          enabled: false,
          template_code: null,
          language_mode: "auto",
          dispatchable: false,
          dispatch_problem: null,
        },
      ],
    });
    const markup = text(
      render(
      <ChannelsCard
        rule={detail}
        readOnly={false}
        working={false}
        t={T}
        draft={draftFor(detail)}
        templateOptions={{}}
        onChannelChange={NOOP}
        onQueueTest={NOOP}
      />,
      ),
    );
    expect(markup).toContain("notifications.rules.noTemplate");
    // The ✉ control is present and DISABLED — visible with its reason, never
    // hidden (BR-SHL-025).
    expect(markup).toContain("channel-test-sms");
    expect(markup).toContain("disabled");
    // DEF-286's editors keep the service's own refusal visible up front: the
    // enable checkbox for a template-less channel is disabled WITH the reason
    // ("a channel can't be enabled if its variant is deactivated").
    expect(markup).toContain("channel-enabled-sms");
  });

  it("DEF-286 — the template picker lists REAL catalog classes for the channel, and the stored code survives a failed catalog read", () => {
    const detail = aDetail();
    const withCatalog = text(
      render(
        <ChannelsCard
          rule={detail}
          readOnly={false}
          working={false}
          t={T}
          draft={draftFor(detail)}
          templateOptions={{
            email: [
              { code: "email_bill_ready", name: "Bill ready (email)", has_published: true },
              { code: "email_past_due", name: "Past-due reminder (email)", has_published: false },
            ],
          }}
          onChannelChange={NOOP}
          onQueueTest={NOOP}
        />,
      ),
    );
    expect(withCatalog).toContain("channel-template-email");
    expect(withCatalog).toContain("Bill ready (email)");
    // An unpublished class is OFFERED and labelled, never hidden (BR-SHL-025).
    expect(withCatalog).toContain("notifications.rules.templateUnpublished");
    // Language mode is a picker too, over BR-NOT-006's two modes.
    expect(withCatalog).toContain("channel-language-email");
    expect(withCatalog).toContain("notifications.rules.language.english_only");

    const withoutCatalog = text(
      render(
        <ChannelsCard
          rule={detail}
          readOnly={false}
          working={false}
          t={T}
          draft={draftFor(detail)}
          templateOptions={null}
          onChannelChange={NOOP}
          onQueueTest={NOOP}
        />,
      ),
    );
    // The stored code is still the selected option — a failed catalog read
    // must not let the select silently rewrite the rule on the next save.
    expect(withoutCatalog).toContain("email_bill_ready");
  });

  it("the test control is labelled as a QUEUE action, not a send", () => {
    // BR-NOT-005 in the copy itself: the button a person reads must not promise
    // a transmission the product cannot make.
    const detail = aDetail();
    const markup = text(
      render(
      <ChannelsCard
        rule={detail}
        readOnly={false}
        working={false}
        t={T}
        draft={draftFor(detail)}
        templateOptions={null}
        onChannelChange={NOOP}
        onQueueTest={NOOP}
      />,
      ),
    );
    expect(markup).toContain("notifications.rules.action.queueTest");
    expect(markup).not.toContain("notifications.rules.action.send");
  });

  it("DEF-286 — the timing card edits the trigger and its ARGUMENT as a pair, and an empty offset is an error the field wears", () => {
    const detail = aDetail({ trigger_mode: "offset_days", offset_days: 3 });
    const draft = { ...draftFor(detail), offset_days: "" };
    const markup = text(
      render(
        <TimingCard
          rule={detail}
          readOnly={false}
          working={false}
          t={T}
          draft={draft}
          onChange={NOOP}
        />,
      ),
    );
    expect(markup).toContain('id="rule-trigger-mode"');
    expect(markup).toContain("timing-offsetDays");
    // The pair rule, client-side half: the argument's absence is an error ON
    // THE FIELD (the server's `_refuse_incoherent_timing` stays the law).
    expect(markup).toContain("notifications.rules.offsetFormat");
    expect(markup).toContain('id="rule-quiet-hours"');
    expect(markup).toContain('id="rule-failure-policy"');
    // The fixed-time argument is NOT drawn while the mode is offset_days —
    // two argument fields at once would be the two-instructions save the
    // service refuses.
    expect(markup).not.toContain("timing-fixedTime");
  });
});

describe("BR-NOT-017 · the escalation ladder has ONE home and ONE store", () => {
  const LADDER = {
    reminder_days_after_due: 3,
    notice_tier_days: [10, 5],
    final_notice_hours: 48,
    balance_floor_amount: "25",
    partial_payment_pause_percent: "25",
    unavailable_reason: null,
    write_endpoint: "/settings/collections",
  };

  it("shows the tenant's own five figures, the two money ones included", () => {
    // The $25.00 floor and the 25% pause have never had a screen anywhere
    // before this one (DEF-204, DEF-097 reopened), and CR-048 F5 keeps them
    // here — it takes the EDITORS away, not the figures.
    const markup = text(
      render(
        <LadderCard
          rule={aDetail({ key: "past_due_reminder", has_ladder: true, ladder: LADDER })}
          t={T}
        />,
      ),
    );
    expect(markup).toContain(">3<");
    expect(markup).toContain("10, 5");
    expect(markup).toContain(">48<");
    expect(markup).toContain("ladder-floor");
    expect(markup).toContain("ladder-pause");
    expect(markup).toContain(">25<");
  });

  it("CR-048 F5 — it is READ-ONLY: no input, no select, no save of its own", () => {
    // ⚠ The change wave F makes, and the reason it is a change rather than a
    // tidy-up: two DOORS onto one store is how the collections run and the
    // notice that announces it come to disagree about the same number. The
    // figures stay; the second door closes.
    const markup = text(
      render(
        <LadderCard
          rule={aDetail({ key: "past_due_reminder", has_ladder: true, ladder: LADDER })}
          t={T}
        />,
      ),
    );
    expect(markup).not.toContain("<input");
    expect(markup).not.toContain("<select");
    expect(markup).not.toContain("<textarea");
  });

  it("CR-048 F5 — and it NAMES where they are changed, so the card is not a dead end", () => {
    const markup = text(
      render(
        <LadderCard
          rule={aDetail({ key: "past_due_reminder", has_ladder: true, ladder: LADDER })}
          t={T}
        />,
      ),
    );
    // A read-only card that does not say where the control lives is worse than
    // an editor: the reader is left hunting.
    expect(markup).toContain("notifications.rules.ladderChangedIn");
  });

  it("names exactly the five keys the PO's ruling names, and no sixth", () => {
    // A sixth key here would name a payment-plan or NSF setting nobody ruled
    // on. Nothing WRITES this list any more (F5), so this assertion is what
    // keeps it honest — and the card below is checked against it.
    expect([...LADDER_KEYS]).toEqual([
      "reminder_days_after_due",
      "notice_tier_days",
      "final_notice_hours",
      "ladder_balance_floor_amount",
      "partial_payment_pause_percent",
    ]);
    const markup = text(
      render(
        <LadderCard
          rule={aDetail({ key: "past_due_reminder", has_ladder: true, ladder: LADDER })}
          t={T}
        />,
      ),
    );
    for (const key of LADDER_KEYS) {
      expect(markup).toContain(`notifications.rules.ladder.${key}`);
    }
  });

  it("an unreadable ladder prints its reason and NOT a row of zeroes", () => {
    // "We could not read this tenant's ladder" and "this utility chases from
    // day 0" are different facts.
    const markup = text(
      render(
        <LadderCard
          rule={aDetail({
            has_ladder: true,
            ladder: { ...LADDER, unavailable_reason: "the settings family cannot be read" },
          })}
          t={T}
        />,
      ),
    );
    expect(markup).toContain("the settings family cannot be read");
    expect(markup).not.toContain(">0<");
  });

  it("a figure the tenant has never set says so, rather than printing nothing", () => {
    const markup = text(
      render(
        <LadderCard
          rule={aDetail({
            has_ladder: true,
            ladder: { ...LADDER, balance_floor_amount: null },
          })}
          t={T}
        />,
      ),
    );
    expect(markup).toContain("notifications.rules.ladderUnset");
  });

  it("a non-collections event draws no ladder at all", () => {
    const markup = text(render(<LadderCard rule={aDetail()} t={T} />));
    // The card contributes NOTHING — the only markup is the test harness's own
    // toast region, which every render() in this file carries.
    expect(markup).not.toContain("panel");
    expect(markup).not.toContain("ladder-");
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * CR-048 F1 — one flat table, with a short stable code and category as columns
 * ══════════════════════════════════════════════════════════════════════════ */
describe("CR-048 F1 · the matrix is one flat, sortable, filterable table", () => {
  const CATEGORIES = ["billing", "payments", "collections", "field_work", "staff_system"];

  function state(overrides: Partial<TableRequestState> = {}): TableRequestState {
    return {
      ...defaultRequestState(
        ruleTableConfig(T, CATEGORIES, {
          code: () => null,
          event: () => null,
          category: () => null,
          audience: () => null,
          channels: () => null,
          timing: () => null,
          enabled: () => null,
          actions: () => null,
        }),
      ),
      ...overrides,
    };
  }

  const ROWS = [
    aRow({ key: "bill_ready", category: "billing" }),
    aRow({ key: "disconnect_notice", category: "collections", enabled: false }),
    aRow({ key: "daily_digest", category: "staff_system", audience: "staff" }),
  ];

  it("draws ONE table and no repeated category headings", () => {
    const markup = text(
      render(
        <RuleMatrix
          matrix={aMatrix(ROWS)}
          readOnly={false}
          working={false}
          t={T}
          onOpen={() => undefined}
          onToggle={() => undefined}
        />,
      ),
    );
    // ⚠ THE DEFECT, stated as arithmetic: five categories meant five <table>
    // elements and five <h4> headings, and the list needed the heading
    // repeated above every block to be readable.
    expect((markup.match(/<table/g) ?? []).length).toBe(1);
    expect(markup).not.toContain("rule-category-billing");
    expect(markup).not.toContain("<h4");
  });

  it("carries the code and the category as COLUMNS", () => {
    const markup = text(
      render(
        <RuleMatrix
          matrix={aMatrix(ROWS)}
          readOnly={false}
          working={false}
          t={T}
          onOpen={() => undefined}
          onToggle={() => undefined}
        />,
      ),
    );
    expect(markup).toContain("notifications.rules.col.code");
    expect(markup).toContain("notifications.rules.col.category");
    expect(markup).toContain("NTF-01");
    expect(markup).toContain("NTF-06");
    expect(markup).toContain("notifications.rules.category.collections");
  });

  it("the code is STABLE — keyed by event, never by row position", () => {
    // Waves B10/B11 add sixteen more events. A positional code would renumber
    // every event below the insertion point, so the NTF-07 a clerk wrote on a
    // ticket last week would name a different event this week.
    expect(eventCode("bill_ready")).toBe("NTF-01");
    expect(eventCode("security_alerts")).toBe("NTF-15");
    expect(Object.keys(EVENT_CODES)).toHaveLength(15);
    expect(new Set(Object.values(EVENT_CODES)).size).toBe(15);
  });

  it("an event this map has never been told gets NO code, not an invented one", () => {
    // DEF-127's lesson applied to an identifier: a made-up NTF-16 would
    // collide with a real one the moment the map caught up.
    expect(eventCode("move_in_confirmation")).toBeNull();
    const markup = text(
      render(
        <RuleMatrix
          matrix={aMatrix([aRow({ key: "move_in_confirmation" })])}
          readOnly={false}
          working={false}
          t={T}
          onOpen={() => undefined}
          onToggle={() => undefined}
        />,
      ),
    );
    expect(markup).toContain("notifications.rules.event.move_in_confirmation");
    expect(markup).not.toMatch(/NTF-\d\d/);
  });

  it("SORTS by the string a person can see, and holds a stable secondary order", () => {
    const byCode = applyRuleTableState(ROWS, state({ sort: "code", dir: "asc" }), T);
    expect(byCode.rows.map((row) => row.key)).toEqual([
      "bill_ready",
      "disconnect_notice",
      "daily_digest",
    ]);
    const reversed = applyRuleTableState(ROWS, state({ sort: "code", dir: "desc" }), T);
    expect(reversed.rows.map((row) => row.key)).toEqual([
      "daily_digest",
      "disconnect_notice",
      "bill_ready",
    ]);
  });

  it("FILTERS by category, by audience and by whether the rule is on", () => {
    expect(
      applyRuleTableState(ROWS, state({ filters: { category: "collections" } }), T).rows.map(
        (row) => row.key,
      ),
    ).toEqual(["disconnect_notice"]);
    expect(
      applyRuleTableState(ROWS, state({ filters: { audience: "staff" } }), T).rows.map(
        (row) => row.key,
      ),
    ).toEqual(["daily_digest"]);
    expect(
      applyRuleTableState(ROWS, state({ filters: { enabled: "false" } }), T).rows.map(
        (row) => row.key,
      ),
    ).toEqual(["disconnect_notice"]);
  });

  it("SEARCHES the code as well as the name — which is half of why a code exists", () => {
    const byCode = applyRuleTableState(ROWS, state({ q: "ntf-06" }), T);
    expect(byCode.rows.map((row) => row.key)).toEqual(["disconnect_notice"]);
    expect(byCode.total).toBe(1);
    const byName = applyRuleTableState(ROWS, state({ q: "daily_digest" }), T);
    expect(byName.rows.map((row) => row.key)).toEqual(["daily_digest"]);
  });

  it("PAGES, and the total it reports is the FILTERED count", () => {
    const paged = applyRuleTableState(ROWS, state({ per: 50, page: 1 }), T);
    expect(paged.total).toBe(3);
    const filtered = applyRuleTableState(ROWS, state({ filters: { audience: "staff" } }), T);
    // Not 3. A pager that counted the unfiltered list would say "showing 1 of
    // 3" over a one-row view.
    expect(filtered.total).toBe(1);
  });

  it("declares a search prompt of its own — B14 rule 19 / G43 clause (a)", () => {
    const config = ruleTableConfig(T, CATEGORIES, {
      code: () => null,
      event: () => null,
      category: () => null,
      audience: () => null,
      channels: () => null,
      timing: () => null,
      enabled: () => null,
      actions: () => null,
    });
    // A list that declares searchFields and no prompt fails G43 outright, and
    // "Search this list" would not tell a clerk that the CODE is searchable.
    expect(config.searchFields).not.toBeUndefined();
    expect(config.searchPlaceholder).toBe("notifications.rules.searchPlaceholder");
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * CR-048 F8 — the four page shapes
 * ══════════════════════════════════════════════════════════════════════════ */
describe("CR-048 F8 · an event nothing fires cannot be switched ON", () => {
  it("draws the toggle DISABLED with its reason, and still draws the row", () => {
    // BR-NOT-018 read forwards. The row is DRAWN and stays fully editable —
    // its audience, channel and template are this screen's to own — but a
    // switch that turns on an event no writer reaches is a promise the product
    // cannot keep, so it is disabled WITH its reason (BR-SHL-025), never
    // hidden.
    const markup = text(
      render(
        <RuleMatrix
          matrix={aMatrix([
            aRow({ key: "daily_digest", trigger_blocked_by: "OQ-262", enabled: false }),
          ])}
          readOnly={false}
          working={false}
          t={T}
          onOpen={() => undefined}
          onToggle={() => undefined}
        />,
      ),
    );
    const toggle = tag(markup, "rule-toggle-daily_digest");
    expect(toggle).toContain("disabled");
    expect(toggle).toContain("notifications.rules.noTrigger");
    expect(markup).toContain("notifications.rules.noTrigger");
    // …and it is still opened for editing.
    expect(markup).toContain("rule-edit-daily_digest");
  });

  it("but an event ALREADY on can always be switched OFF", () => {
    // The mirror case, and it matters: a utility must never be locked into
    // sending something. Only turning one ON is refused.
    const markup = text(
      render(
        <RuleMatrix
          matrix={aMatrix([
            aRow({ key: "daily_digest", trigger_blocked_by: "OQ-262", enabled: true }),
          ])}
          readOnly={false}
          working={false}
          t={T}
          onOpen={() => undefined}
          onToggle={() => undefined}
        />,
      ),
    );
    const toggle = tag(markup, "rule-toggle-daily_digest");
    expect(toggle).toContain('checked=""');
    expect(toggle).not.toContain("disabled");
  });
});

describe("CR-048 F8 / BR-NOT-024 · a printed customer document cannot be switched off", () => {
  const PRINT_ROW = {
    // ⚠ THE SERVER'S SPELLING. `models.CHANNEL_PRINT = "pdf_print"`. The first
    // draft of this fixture said `print`, matched a component that also said
    // `print`, and proved nothing about the product — a test asserting the
    // test. The two assertions below now pin the spelling itself.
    channel: "pdf_print",
    enabled: true,
    template_code: "print_disconnect_notice",
    language_mode: "auto",
    dispatchable: false,
    dispatch_problem: null,
  };

  it("draws the print toggle LOCKED ON, with its reason beside it", () => {
    // PO 2026-08-29: *"this is correct - don't switch of print for any
    // document it is awayls on"*. The printed disconnection letter is the
    // legal instrument, and the server's own floor is at the QUEUE — so an
    // enabled-looking toggle here is a control whose only effect is to look
    // like one.
    const detail = aDetail({
      key: "disconnect_notice",
      category: "collections",
      audience: "customer",
      channel_rules: [PRINT_ROW],
    });
    const markup = text(
      render(
        <ChannelsCard
          rule={detail}
          readOnly={false}
          working={false}
          t={T}
          draft={draftFor(detail)}
          templateOptions={null}
          onChannelChange={() => undefined}
          onQueueTest={() => undefined}
        />,
      ),
    );
    expect(markup).toContain("channel-enabled-pdf_print");
    expect(markup).toContain("disabled");
    expect(markup).toContain('checked=""');
    // The reason is VISIBLE, not only a tooltip: this one is the difference
    // between a courtesy and a legal instrument.
    expect(markup).toContain("channel-floor-pdf_print");
    expect(markup).toContain("notifications.rules.printFloor");
  });

  it("and the rule is keyed on the CHANNEL, so waves B10/B11 inherit it", () => {
    // A receipt and a payment-plan letter are customer documents too
    // (BR-NOT-024 names four kinds). Keying on `disconnect_notice` would mean
    // remembering this rule again for each of them.
    expect(printIsTheFloor("pdf_print", "customer")).toBe(true);
    expect(printIsTheFloor("pdf_print", "staff")).toBe(false);
    expect(printIsTheFloor("email", "customer")).toBe(false);
    // ⚠ AND THE SPELLING ITSELF, because getting it wrong is silent: a
    // `=== "print"` test compiles, lints and never matches, so the lock simply
    // never draws. `models.CHANNEL_PRINT` is `"pdf_print"`.
    expect(PRINT_CHANNEL).toBe("pdf_print");
    expect(printIsTheFloor("print", "customer")).toBe(false);
  });

  it("DEF-PAY-10651: the past-due reminder's letter is a fallback the server says is NOT floored", () => {
    // PO 2026-10-29, 1A/2A — the reminder rides the floorless `reminder` kind,
    // so its Print switch is a real switch; drawing it "Always on" would be a
    // dead control over a setting the server honours.
    expect(printIsTheFloor("pdf_print", "customer", false)).toBe(false);
    expect(printIsTheFloor("pdf_print", "customer", true)).toBe(true);
    // A server that does not say keeps the old, safe reading.
    expect(printIsTheFloor("pdf_print", "customer", undefined)).toBe(true);
  });
});

describe("the rule in plain English", () => {
  it("names the audience, the channels, the timing and the exclusions", () => {
    const sentence = plainEnglishRule(aRow({ skip_accounts_on_payment_plan: true }), T);
    expect(sentence).toContain("notifications.rules.plain.sentence");
    expect(sentence).toContain("notifications.rules.plain.skipPlans");
  });

  it("says a rule with no enabled channel sends NOTHING, rather than leaving a blank", () => {
    const sentence = plainEnglishRule(
      aRow({
        channel_rules: [
          {
            channel: "email",
            enabled: false,
            template_code: "email_bill_ready",
            language_mode: "auto",
            dispatchable: false,
            dispatch_problem: null,
          },
        ],
      }),
      T,
    );
    expect(sentence).toContain("notifications.rules.plain.noChannel");
  });
});
