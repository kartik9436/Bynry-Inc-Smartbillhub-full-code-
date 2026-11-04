// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  DEF-286 — SET-12D's cards become EDITORS (CR-009's one blocker).
// Screens: S8 (Settings → Notifications → SET-12D)
// Rules:   BR-NOT-017 (one home) · BR-NOT-021 (staff recipient is RULED — no
//          client may send one) · BR-TEN-024 (atomic per-page save) ·
//          CLAUDE.md TS/Python boundary law (DEF-522/526/531/535: five field
//          names hand-copied wrong across it in ONE day)
// ───────────────────────────────────────────────────────
// **WHAT THIS SUITE EXISTS TO PROVE: THE EXACT WIRE KEYS LEAVING THE CLIENT.**
// A static-markup test can show a select renders; only a REAL edit + save can
// show what the PUT body actually says. Every key asserted below is checked
// against `rule_service.EDITABLE_RULE_FIELDS` / `EDITABLE_CHANNEL_FIELDS`
// SPELLINGS (imported, not re-typed), because the wrong-spelling class of
// defect (DEF-522/526/531/535) is invisible to every other check: the payload
// is well-formed JSON, the server refuses it or drops it, and both sides'
// tests stay green.
//
// ⚠ **PROVED RED FIRST (law 7).** With the diff builder deliberately emitting
// `quietHoursMode` (the hand-copied-wrong spelling), the exact-body assertion
// failed:
//   AssertionError: expected { quietHoursMode: 'override' } to deeply equal
//   { quiet_hours_mode: 'override' }
// — which is precisely the defect class this file pins. Restored, GREEN.
//
// ⚠ **THE STUB SERVES THE SERVER'S REAL SHAPES, KEY FOR KEY** — copied from
// `rule_service.RuleView.as_wire()` + `rules_api.RELEASE_POSTURE` (the rule
// detail), `templates_api._catalog_row` (the template options read) and
// `apps/tenancy` services rows — NOT from the TypeScript interfaces, for the
// DEF-526/531 reason: hand-copied interfaces are the thing under test.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

const MAIL_REASON =
  "'Mail' on a disconnect notice means PHYSICAL POST, which is a fulfilment vendor and not a channel flag. The platform's paper channel is `pdf_print` — it RENDERS the letter; who franks and posts it is an integration nobody has chosen.";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ApiClient, ApiResponse } from "@/api/client";
import {
  EDITABLE_CHANNEL_FIELDS,
  EDITABLE_RULE_FIELDS,
} from "@/api/notificationRuleEndpoints";
import { ToastProvider } from "@/components/Toast";

import { RuleDetailPage } from "../notifications/NotificationRules";

const EVENT = "bill_ready";

/** `rule_service.RuleView.as_wire(include_ladder=True)` + `RELEASE_POSTURE`,
 *  exactly as `GET /notification-rules/bill_ready` answers. */
function ruleDetail(): Record<string, unknown> {
  return {
    key: EVENT,
    category: "billing",
    audience: "customer",
    channels: ["email", "sms"],
    // ⚠ **THIS FIXTURE NAMED `portal` UNTIL 2026-09-07 AND THE SENTENCE WAS
    // FICTION BY THEN (`CR-084`).** The refusal it carried — *"there is no
    // customer portal in this product"* — had been false since `CR-068` shipped
    // one, and this test went on passing because the fixture SUPPLIES the
    // refusal it then asserts is rendered: a test asserting the test. What is
    // under test here is the refusal MECHANISM, so it is pointed at the refusal
    // that is still real (`mail` on a disconnect notice is a fulfilment vendor
    // nobody has chosen) rather than at one the product no longer makes.
    unavailable_channels: [{ channel: "mail", reason: MAIL_REASON }],
    template_classes: { email: "email_bill_ready", sms: "sms_bill_ready" },
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
      {
        channel: "sms",
        enabled: false,
        template_code: "sms_bill_ready",
        language_mode: "auto",
        dispatchable: false,
        dispatch_problem: { code: "channel_deferred" },
      },
    ],
    staff_recipient: null,
    ladder: null,
    // RELEASE_POSTURE, as rules_api merges it into the same object.
    dispatch_runs_in_this_release: true,
    dispatchable_channels: ["in_app"],
    delivery_counts_available: false,
    delivery_counts_reason:
      "Nobody is reporting these back to us yet, because sending is not switched on.",
    requirement_claims_event_count: 16,
    built_event_count: 15,
  };
}

/** `templates_api._catalog_row`, the fields this page reads. */
const CATALOG_PAGE = {
  count: 3,
  results: [
    {
      code: "email_bill_ready",
      name: "Bill ready (email)",
      category: "billing",
      category_source: "cr_007",
      kind: "Email",
      variants: 1,
      used_by: "Billing run",
      edited: null,
      edited_at: null,
      group: "email",
      channel: "email",
      catalog_unavailable: null,
      body_unavailable: null,
      has_published: true,
    },
    {
      code: "email_past_due",
      name: "Past-due reminder (email)",
      category: "collections",
      category_source: "cr_007",
      kind: "Email",
      variants: 1,
      used_by: "Collections",
      edited: null,
      edited_at: null,
      group: "email",
      channel: "email",
      catalog_unavailable: null,
      body_unavailable: null,
      has_published: true,
    },
    {
      code: "sms_bill_ready",
      name: "Bill ready (SMS)",
      category: "billing",
      category_source: "cr_007",
      kind: "SMS",
      variants: 1,
      used_by: "Billing run",
      edited: null,
      edited_at: null,
      group: "sms",
      channel: "sms",
      catalog_unavailable: null,
      body_unavailable: null,
      has_published: true,
    },
  ],
  page: 1,
  per: 500,
  categories: [],
  columns: [],
  page_sizes: [50, 100, 200, 500, 1000],
  can_edit: true,
  cannot_edit_reason: null,
  create_action: "variant",
  create_action_reason: "",
};

const SERVICES = [
  {
    service: "electric",
    name: "Electric",
    enabled: true,
    primary_uom: "kWh",
    alt_uom: null,
    revenue_account: null,
    base_revenue_account: null,
    rate_schedules: null,
    active_accounts: null,
  },
];

interface RecordedCall {
  method: "GET" | "PUT";
  path: string;
  body?: unknown;
}

function ok<T>(data: T, status = 200): ApiResponse<T> {
  return { status, data, etag: null, notModified: false };
}

function stubClient(calls: RecordedCall[]): ApiClient {
  return {
    get: async <T,>(path: string): Promise<ApiResponse<T>> => {
      calls.push({ method: "GET", path });
      if (path === `/notification-rules/${EVENT}`) return ok(ruleDetail() as T);
      if (path === "/template-catalog?per=500") return ok(CATALOG_PAGE as T);
      if (path === "/settings/services") return ok(SERVICES as T);
      throw new Error(`unstubbed GET ${path}`);
    },
    put: async <T,>(path: string, body?: unknown): Promise<ApiResponse<T>> => {
      calls.push({ method: "PUT", path, body });
      if (path === `/notification-rules/${EVENT}`) return ok(ruleDetail() as T);
      throw new Error(`unstubbed PUT ${path}`);
    },
    post: async <T,>(path: string): Promise<ApiResponse<T>> => {
      throw new Error(`unstubbed POST ${path}`);
    },
  } as unknown as ApiClient;
}

function mount(calls: RecordedCall[], onBack = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RuleDetailPage
          eventKey={EVENT}
          readOnly={false}
          client={stubClient(calls)}
          onBack={onBack}
          // CR-048 wave I — the receipt election is a REQUIRED prop now (the
          // dead-UI shape law 2 forbids). This page's event is not
          // `payment_received`, so the card does not render here; passing the
          // shape is what keeps that a fact about the EVENT rather than about
          // whether somebody remembered the prop.
          receipt={{ on: true, readOnly: false, working: false, onToggle: () => undefined }}
        />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { view, onBack };
}

function putCalls(calls: RecordedCall[]): RecordedCall[] {
  return calls.filter((call) => call.method === "PUT");
}

afterEach(cleanup);

describe("SET-12D · a real edit, a real save, and the EXACT wire keys (DEF-286)", () => {
  it("editing quiet hours sends { quiet_hours_mode } — the PARTIAL diff, spelled as the Python spells it", async () => {
    const calls: RecordedCall[] = [];
    const user = userEvent.setup();
    const { onBack } = mount(calls);

    const quietHours = await screen.findByLabelText("Quiet hours");
    await user.selectOptions(quietHours, "override");
    const save = screen.getByTestId("rule-save");
    await waitFor(() => expect(save).toBeEnabled());
    await user.click(save);

    await waitFor(() => expect(putCalls(calls)).toHaveLength(1));
    const body = putCalls(calls)[0].body as Record<string, unknown>;
    // The EXACT body — nothing unchanged travels ("pass only what is
    // changing"), and the key is rule_service's own spelling.
    expect(body).toEqual({ quiet_hours_mode: "override" });
    // Every top-level key is an EDITABLE_RULE_FIELDS member (or the channels
    // envelope) — the refusal `update_rule` makes BY NAME can never fire on
    // what this client sends.
    for (const key of Object.keys(body)) {
      expect([...EDITABLE_RULE_FIELDS, "channels"]).toContain(key);
    }
    // Save … returns to matrix — the requirement's own words.
    await waitFor(() => expect(onBack).toHaveBeenCalledTimes(1));
  });

  it("editing a channel's template + language nests them under channels.{channel}, EDITABLE_CHANNEL_FIELDS spellings only", async () => {
    const calls: RecordedCall[] = [];
    const user = userEvent.setup();
    mount(calls);

    // The email row's two pickers — the template list is the CATALOG's, so the
    // option chosen here is a real class, not an invented name.
    const template = await screen.findByTestId("channel-template-email");
    await user.selectOptions(template, "email_past_due");
    const language = screen.getByTestId("channel-language-email");
    await user.selectOptions(language, "english_only");
    await user.click(screen.getByTestId("rule-save"));

    await waitFor(() => expect(putCalls(calls)).toHaveLength(1));
    const body = putCalls(calls)[0].body as Record<string, unknown>;
    expect(body).toEqual({
      channels: {
        email: { template_code: "email_past_due", language_mode: "english_only" },
      },
    });
    const channelPatch = (body.channels as Record<string, Record<string, unknown>>).email;
    for (const key of Object.keys(channelPatch)) {
      expect([...EDITABLE_CHANNEL_FIELDS]).toContain(key);
    }
  });

  it("an untouched page cannot save — the empty save the service refuses is refused HERE first, on the button", async () => {
    const calls: RecordedCall[] = [];
    mount(calls);
    const save = await screen.findByTestId("rule-save");
    await screen.findByLabelText("Quiet hours"); // editors are up
    expect(save).toBeDisabled();
    expect(save).toHaveAttribute(
      "title",
      "Nothing has changed yet, so there is nothing to save.",
    );
    expect(putCalls(calls)).toHaveLength(0);
  });

  it("the timing PAIR: switching to offset-days without the number blocks the save with the field's own error", async () => {
    const calls: RecordedCall[] = [];
    const user = userEvent.setup();
    mount(calls);

    const trigger = await screen.findByLabelText("Trigger");
    await user.selectOptions(trigger, "offset_days");
    // The argument field appears, empty — the pair is incoherent and the save
    // must not fire (`_refuse_incoherent_timing`'s client-side half).
    const save = screen.getByTestId("rule-save");
    expect(save).toBeDisabled();
    expect(putCalls(calls)).toHaveLength(0);

    // Give it the number and the pair travels TOGETHER: mode + offset + the
    // cleared fixed_time, one payload.
    await user.type(screen.getByLabelText(/Days after the event/), "3");
    await waitFor(() => expect(save).toBeEnabled());
    await user.click(save);
    await waitFor(() => expect(putCalls(calls)).toHaveLength(1));
    expect(putCalls(calls)[0].body).toEqual({
      trigger_mode: "offset_days",
      offset_days: 3,
      fixed_time: null,
    });
  });

  it("BR-NOT-021 — no code path can put a staff recipient on the wire", async () => {
    // Not a UI walk: the assertion is on the VOCABULARY. The diff builder can
    // only emit EDITABLE_RULE_FIELDS + channels, and no recipient spelling is
    // in either list — the refusal `_refuse_staff_recipient` makes can never
    // be triggered by this client.
    for (const forbidden of ["staff_recipient", "staff_role", "recipient_role", "owner"]) {
      expect([...EDITABLE_RULE_FIELDS]).not.toContain(forbidden);
      expect([...EDITABLE_CHANNEL_FIELDS]).not.toContain(forbidden);
    }
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * CR-048 F4 — THE RAIL IS RENDERED AS A COLUMN, not as a card in the grid
 * ══════════════════════════════════════════════════════════════════════════
 * `notificationsLayout.dom.test.tsx` asks whether `RULE_LAYOUT` COMPILES to a
 * two-track grid. That is half the question and it is the half a constant can
 * answer. This is the other half and only a render can answer it: **is the
 * rail actually outside `.settings-grid`?**
 *
 * It is the difference the CR is about. The plain-English sentence, the
 * delivery half and the audit note existed before wave F — as three sections of
 * a `<Panel>` sitting inside `.settings-grid`'s
 * `repeat(auto-fit, minmax(320px, 1fr))`, which means it took whichever track
 * was free: on a wide screen it landed second in row two, between the timing
 * card and the ladder. A rail that reflows into the body is not a rail, and
 * every check in this repo passed over it (hard-won law 6).
 *
 * ⚠ PROVED RED against this lane's parent commit: `Unable to find an element by:
 * [data-testid="rule-rail"]` — there was no rail element at all.
 */
describe("CR-048 F4 · the right rail", () => {
  it("is a column of its own, not a card inside the panel grid", async () => {
    const calls: RecordedCall[] = [];
    const { view } = mount(calls);

    const rail = await screen.findByTestId("rule-rail");
    // The three things the CR asks the rail to carry. The last two are the
    // ones the wire cannot fill yet and they render a SENTENCE, never a zero
    // and never a blank name (DEF-127).
    expect(screen.getByTestId("rail-plain-english").textContent).not.toBe("");
    // DEF-NOT-10537 — the catalogue's sentence, not "because sending is not
    // switched on".
    expect(screen.getByTestId("rail-delivery-unreported").textContent).toContain(
      "No provider reports these back yet.",
    );
    expect(screen.getByTestId("rail-last-changed").textContent).not.toBe("");

    /* ⚠ **THIS ASSERTION WAS INVERTED ON 2026-08-30 AND THE INVERSION IS THE
       POINT (CR-048 wave H).** It used to require `.settings-grid` to still be
       PRESENT on the page — the rail merely had to be outside it. That was
       true of wave F and it left the defect the rail was built to fix only
       half closed: the BODY column was still a `PanelGrid`, so the four rule
       cards tiled three-across inside it. Measured in Chromium at 1728×1080,
       the tracks came out `336px 336px 336px`, and the "Channels & templates"
       table — which needs about 660px — was **325px wider than the 336px card
       holding it** and ran underneath the card beside it. That is the PO's
       *"the rules table overflows behind the next card"*, still on the screen
       with this test green.

       So the rule page now carries NO equal-column card grid at all: the body
       is a stacked column and so is the rail. This asks the stronger question,
       which is also the simpler one. */
    expect(
      view.container.querySelector(".settings-grid"),
      "a rule card is tiling in `.settings-grid` again, so a wide table has a third of the page",
    ).toBeNull();
    // And the rail is still its own column beside that body, not a card in it.
    const body = view.container.querySelector('[data-testid="rule-rail"]')?.previousElementSibling;
    expect(body, "the rail has no body column beside it").not.toBeNull();
    expect(body?.contains(rail), "the rail is inside the body column").toBe(false);
  });

  it("prints no delivery NUMBER anywhere — BR-NOT-013, and CR-048 B6 has not landed", async () => {
    // `rule_service.RuleView.as_wire()` carries no `last_30_days_*` field of any
    // kind, so there is nothing to render. A zero here would read as "every
    // message failed", which is not what is happening.
    const calls: RecordedCall[] = [];
    mount(calls);

    const rail = await screen.findByTestId("rule-rail");
    expect(rail.textContent ?? "").not.toMatch(/\b\d+\s+(sent|delivered|failed|bounced)\b/i);
  });
});
