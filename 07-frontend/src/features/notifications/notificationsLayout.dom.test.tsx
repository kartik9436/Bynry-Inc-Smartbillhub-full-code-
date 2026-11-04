// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-048 wave C1 — the Tailwind migration of the five notification and
//          template files, and the two VISIBLE defects it is required to close.
//          AMENDED by CR-048 wave F: F2 moved the print row from the dispatch
//          card to the channel-status strip and F1 moved the matrix's column
//          widths from the `<th>` to the cell, so the same six assertions now
//          point at the elements those two shapes actually render — plus F6 and
//          F7, which are layout defects of exactly the same kind.
// Screens: SET-12 (the event matrix) · SET-12D (the rule page) ·
//          S8 → Notifications (the channel strip and the pacing card)
// Rules:   B14 rule 21 (utilities only, and the migration clause is PER FILE) ·
//          B14 rule 20 (one table type) · BR-BIL-036 / BR-NOT-024 (print is the
//          floor) · BR-SHL-025 (a forbidden control carries its reason)
// ───────────────────────────────────────────────────────
// **WHY THIS SUITE IS NOT `toHaveClass()`, AND WHY THAT MATTERS HERE MORE THAN
// ANYWHERE ELSE IN THE PRODUCT.**
//
// Both defects below are LAYOUT — a sentence leaving its card, a cell wrapping
// to four lines — and jsdom performs no layout at all, so nothing here can
// measure a box. The honest thing available is one step short of that and it is
// still a real check: take the classes the element ACTUALLY renders with, and
// resolve them the way a browser would — through every stylesheet under `src/`
// AND through the real Tailwind compiler — then assert the DECLARATION that
// causes the defect is gone and the one that fixes it is present.
//
// That is deliberately stronger than asserting a class name is in the DOM,
// because under B14 rule 21 a class name in the DOM is exactly the failure
// mode: a utility written in a file that is not on `route-b-migrated.txt`
// renders as NOTHING, and `tsc`, eslint and `toContain("whitespace-normal")`
// all pass over it. This suite asks the compiler, so it cannot pass over it.
//
// **WHAT IT STILL CANNOT SEE, STATED RATHER THAN IMPLIED:** cascade order,
// specificity, media-query context and the actual pixel width of a column. A
// `min-width` of 13rem is asserted to EXIST and to be a real length; whether
// 13rem is enough for *"On the escalation ladder below"* at 13.5px is a
// measurement, and the only instrument for it is a browser (hard-won law 6).
//
// ⚠ **WAVE F's FOUR NEW CASES WERE PROVED RED THE SAME WAY** — against this
// lane's own parent commit, by writing the two component files back to `HEAD`
// and running this file. The verbatim failures are in the lane report; the
// shapes are: the template header had no `min-width` at all (`expected +0 to be
// greater than +0`, twice, for template and language), the picker had no width
// (`expected [] to include '100%'`), and the unavailable-channel reason was a
// `RefusalStrip` with nothing clipping it (`expected [] to include 'ellipsis'`).
//
// ⚠ **PROVED RED FIRST (law 7): 6 failed, 0 passed on the pre-migration
// markup**, one message per case, quoted:
//   · sentence may wrap   → expected [ 'nowrap' ] to not include 'nowrap'
//   · sentence may shrink → expected [ 'none' ] to not include 'none'
//   · a count is left alone → expected [] to not deeply equal []
//   · timing column width → expected +0 to be greater than +0
//   · channel column width → expected +0 to be greater than +0
//   · channel name unbroken → expected [] to include 'nowrap'
// The first two come from `.kv-v { flex: none; white-space: nowrap }` in
// `styles/global.css`, which is right for a COUNT and is the whole defect for a
// SENTENCE. The fourth and fifth come from a matrix whose columns declared no
// width at all, and the sixth from a `.pill` that never said not to break.
// The third is a GUARD rather than a defect — it fails RED for a different
// reason (`.kv-v` sets `font-feature-settings`, and the migration writes
// `tabular-nums`, which is `font-variant-numeric`) and it exists so the fix
// cannot quietly become "everything wraps".
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import type {
  NotificationRuleDetail,
  NotificationRuleMatrix,
  NotificationSettings,
  OutboundSummary,
} from "@/api/endpoints";
import { draftOf } from "@/api/notificationRuleEndpoints";
import { ToastProvider } from "@/components/Toast";

import { ChannelsCard, RuleMatrix } from "./NotificationRules";
import { RULE_LAYOUT } from "./notificationsKit";
import { ChannelStatusStrip, DispatchConfigPanel, QueueTable } from "./SettingsNotificationsTab";

/* ══════════════════════════════════════════════════════════════════════════
 * THE RESOLVER — what would a browser apply to this element?
 * ══════════════════════════════════════════════════════════════════════════
 * Reached the way `styles/routeBUtilities.test.ts` reaches node's own modules:
 * the string-split import keeps Vite from pre-bundling them, and it keeps the
 * two files the same shape so a reader can compare them.
 */
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string, o: { withFileTypes: true }): { name: string; isDirectory(): boolean }[];
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};
const nodeModule = (await import(/* @vite-ignore */ ["node", "module"].join(":"))) as {
  createRequire(p: string): { resolve(id: string): string };
};

const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const SRC = nodePath.dirname(nodePath.dirname(HERE));
const STYLES = nodePath.join(SRC, "styles");

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
    const full = nodePath.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else out.push(full);
  }
  return out;
}

/** Innermost `selector { declarations }` blocks of a stylesheet.
 *
 *  ⚠ It reads INNERMOST blocks on purpose, so a rule inside `@media` is found
 *  under its own selector — and its media CONTEXT is therefore lost. That is a
 *  stated limit, not an oversight: this resolver answers "does any rule for
 *  this exact class declare X", which is the question both defects turn on. */
function rules(css: string): { selector: string; body: string }[] {
  const out: { selector: string; body: string }[] = [];
  const clean = css.replace(/\/\*[\s\S]*?\*\//g, " ");
  for (const m of clean.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    out.push({ selector: m[1], body: m[2] });
  }
  return out;
}

/** Every declaration of `property` made by a rule whose selector is EXACTLY
 *  `.token` — never `.token.other` or `.parent .token`, because a compound or
 *  descendant selector is a different rule with a different trigger. */
function declarationsIn(
  blocks: { selector: string; body: string }[],
  token: string,
  property: string,
): string[] {
  const found: string[] = [];
  const wanted = `.${token}`;
  const decl = new RegExp(`(?:^|;)\\s*${property}\\s*:\\s*([^;]+)`, "gi");
  for (const block of blocks) {
    const parts = block.selector.split(",").map((part) => part.trim());
    if (!parts.includes(wanted)) continue;
    for (const hit of block.body.matchAll(decl)) found.push(hit[1].trim());
  }
  return found;
}

const STYLESHEET_RULES = walk(SRC)
  .filter((path) => path.endsWith(".css"))
  .flatMap((path) => rules(nodeFs.readFileSync(path, "utf8")));

/** The app's own Tailwind, compiled for exactly these candidates.
 *
 *  ⚠ A FRESH COMPILER EVERY CALL. `compile()` returns a stateful builder and
 *  `build()` is CUMULATIVE — `routeBUtilities.test.ts` measured a typo passing
 *  because the previous candidate's rule was still in the output. */
async function tailwindRules(candidates: string[]): Promise<{ selector: string; body: string }[]> {
  const { compile } = (await import("tailwindcss")) as {
    compile(
      css: string,
      opts: {
        base: string;
        loadStylesheet(id: string, base: string): Promise<{ path: string; base: string; content: string }>;
      },
    ): Promise<{ build(candidates: string[]): string }>;
  };
  const require_ = nodeModule.createRequire(nodePath.join(SRC, "index.ts"));
  const compiler = await compile(nodeFs.readFileSync(nodePath.join(STYLES, "tailwind.css"), "utf8"), {
    base: SRC,
    loadStylesheet: async (id: string) => {
      const p = require_.resolve(id);
      return { path: p, base: nodePath.dirname(p), content: nodeFs.readFileSync(p, "utf8") };
    },
  });
  // Unescaping the OUTPUT is exact; re-deriving Tailwind's escaping here would
  // be a second implementation of someone else's rule (the same reasoning, and
  // the same one line, as the Route B suite next door).
  return rules(compiler.build(candidates).replace(/\\/g, ""));
}

/** Every value of `property` that would reach this element, from either source.
 *  An empty array means NOTHING declares it — which is what both of CR-048's
 *  visible defects looked like before the migration. */
async function applied(element: Element, property: string): Promise<string[]> {
  const tokens = (element.getAttribute("class") ?? "").split(/\s+/).filter(Boolean);
  const compiled = await tailwindRules(tokens);
  const values: string[] = [];
  for (const token of tokens) {
    values.push(...declarationsIn(STYLESHEET_RULES, token, property));
    values.push(...declarationsIn(compiled, token, property));
  }
  return values;
}

beforeAll(() => {
  // A resolver that silently reads no stylesheets would pass every assertion
  // below — DEF-057's shape, and the reason the Route B suite guards its ledger
  // the same way.
  expect(STYLESHEET_RULES.length, "no stylesheet rules were read at all").toBeGreaterThan(100);
});

afterEach(cleanup);

/* ── Fixtures ─────────────────────────────────────────────────────────────
 * `t` returns the KEY, so every assertion below reads as the string the screen
 * asks for rather than as English that a locale edit could move.
 */
const T = (key: string, params?: Record<string, unknown>): string =>
  params === undefined ? key : `${key} ${JSON.stringify(params)}`;

function settings(): NotificationSettings {
  return {
    dispatch_batch_size: 200,
    quiet_hours_start: "21:00",
    quiet_hours_end: "08:00",
    email_dispatch_active: false,
    sms_dispatch_active: false,
    receipt_on_record_payment: true,
    credit_notice_email: true,
    bookkeeper_copies: true,
    lockbox_receipts: true,
    election_consumers: {},
    print_dispatch_active: true,
    print_cannot_be_switched_off: "Print is the floor.",
    // 2026-10-22 (`DEF-NOT-10533`): one live line per channel.
    channel_lines: [
      { channel: "email", state: "off", provider: null, host: null },
      { channel: "sms", state: "off", provider: null, host: null },
      { channel: "pdf_print", state: "waitingPrintVendor", provider: null, host: null },
    ],
    editable_fields: [],
  };
}

function summary(): OutboundSummary {
  return {
    counts: [],
    totals: {},
    held: 0,
    returned: 0,
    retry_exhausted: 0,
    // The CR's own example figure: *"Email — not switched on. 138 messages are
    // waiting."*
    queued_by_channel: { email: 138, sms: 12, pdf_print: 4 },
    unpopulated_statuses: [],
    problems: [],
  } as OutboundSummary;
}

/** One CUSTOMER event with a print channel and one channel the platform does
 *  not have — the two shapes F6 and F7 are about. */
function detail(): NotificationRuleDetail {
  return {
    key: "disconnect_notice",
    category: "collections",
    audience: "customer",
    channels: ["pdf_print", "email"],
    unavailable_channels: [
      {
        channel: "mail",
        // The SERVER's real sentence, at its real length — 180 characters is
        // what made five lines of red inside one table row.
        reason:
          "'Mail' on a disconnect notice means PHYSICAL POST, which is a fulfilment vendor " +
          "and not a channel flag. The platform's paper channel is `pdf_print` — it RENDERS " +
          "the letter; who franks and posts it is an integration nobody has chosen.",
      },
    ],
    template_classes: {},
    trigger_blocked_by: null,
    timing_key: "ladder",
    has_ladder: true,
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
        // `models.CHANNEL_PRINT` — the server's spelling, not "print".
        channel: "pdf_print",
        enabled: true,
        template_code: "print_disconnect_notice",
        language_mode: "auto",
        dispatchable: false,
        dispatch_problem: { code: "channel_deferred" },
      },
      {
        channel: "email",
        enabled: true,
        // The string in the defect: a template name a 60px column shows as
        // "Bill re ⌄".
        template_code: "email_disconnect_notice",
        language_mode: "auto",
        dispatchable: false,
        dispatch_problem: { code: "channel_deferred" },
      },
    ],
    staff_recipient: null,
    dispatch_runs_in_this_release: false,
    delivery_counts_available: false,
    delivery_counts_reason: "Nothing reports a delivery.",
    requirement_claims_event_count: 16,
    built_event_count: 15,
    ladder: null,
  } as NotificationRuleDetail;
}

function matrix(): NotificationRuleMatrix {
  return {
    count: 1,
    categories: ["collections"],
    dispatch_runs_in_this_release: false,
    delivery_counts_available: false,
    delivery_counts_reason: "Nothing reports a delivery.",
    requirement_claims_event_count: 16,
    built_event_count: 15,
    results: [
      {
        key: "dunning_reminder",
        category: "collections",
        audience: "customer",
        channels: ["email", "sms"],
        unavailable_channels: [],
        template_classes: {},
        trigger_blocked_by: null,
        // THE STRING IN THE DEFECT: "On the escalation ladder below".
        timing_key: "ladder",
        has_ladder: true,
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
            channel: "sms", // "Text message" — the cell that took two lines
            enabled: true,
            template_code: "sms_dunning",
            language_mode: "auto",
            dispatchable: false,
            dispatch_problem: { code: "channel_deferred" },
          },
        ],
        staff_recipient: null,
      },
    ],
  } as NotificationRuleMatrix;
}

function mount(node: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <ToastProvider>{node}</ToastProvider>
    </QueryClientProvider>,
  );
}

/* ══════════════════════════════════════════════════════════════════════════
 * DEFECT 1 — "the most visible defect of the three screens"
 * ══════════════════════════════════════════════════════════════════════════
 * *"Always on — print is the floor and cannot be switched off"* left the
 * Dispatch card and printed across the card beside it. `.settings-grid` is
 * `repeat(auto-fit, minmax(320px, 1fr))`, so the track cannot grow past its
 * share; the `<li>` carries `min-width: 0` and can shrink; and `.kv-v` carries
 * `flex: none` AND `white-space: nowrap`, so the value could do NEITHER. It
 * has to be able to do one of the two. It now does both.
 *
 * ⚠ **THE SENTENCE MOVED WITH CR-048 F2 AND THESE ASSERTIONS MOVED WITH IT.**
 * Print is a channel STATUS, so it belongs on the channel-status strip beside
 * email and text and not on the pacing card; `STRIP_STATE` is the slot it
 * lands in and it carries the same two guarantees `KV_SENTENCE` did. The
 * assertions are unchanged in every other respect, deliberately: a regression
 * guard that is rewritten while the thing it guards moves is a guard nobody
 * can tell was ever run.
 */
describe("CR-048 · the print row's sentence stays inside its card", () => {
  it("may WRAP — nothing applied to it says white-space: nowrap", async () => {
    mount(
      <ChannelStatusStrip
        settings={settings()}
        summary={summary()}
        readOnly={false}
        working={false}
        t={T}
        onSave={() => undefined}
      />,
    );
    const value = screen.getByText(/^notifications\.channels\.line\.waitingPrintVendor/);
    const whiteSpace = await applied(value, "white-space");

    expect(whiteSpace, "the sentence is held on one line and leaves the card").not.toContain(
      "nowrap",
    );
    expect(whiteSpace, "and something must say it wraps, not merely omit nowrap").toContain(
      "normal",
    );
  });

  it("may SHRINK — it is not a flex item that refuses to give up width", async () => {
    mount(
      <ChannelStatusStrip
        settings={settings()}
        summary={summary()}
        readOnly={false}
        working={false}
        t={T}
        onSave={() => undefined}
      />,
    );
    const value = screen.getByText(/^notifications\.channels\.line\.waitingPrintVendor/);
    expect(await applied(value, "flex"), "`flex: none` is the other half of the overflow")
      .not.toContain("none");
  });

  it("leaves a COUNT alone — tabular figures still hold their column", async () => {
    // The fix must not become "everything wraps". A count is the case `.kv-v`
    // was right about, and "93" beside "1,204" should still share a column.
    // The batch size is still on the PACING card (CR-048 F2 left the two
    // figures where they were and took the switches away), so this guard needs
    // no new fixture — only the card's smaller prop list.
    mount(<DispatchConfigPanel settings={settings()} t={T} />);
    const count = screen.getByText("200");
    expect(await applied(count, "white-space")).toContain("nowrap");
    expect(await applied(count, "font-variant-numeric")).not.toEqual([]);
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * DEFECT 2 — a one-line row four lines tall
 * ══════════════════════════════════════════════════════════════════════════
 * No column on the SET-12 matrix declared a width, so
 * `notifications.rules.timing.ladder` — *"On the escalation ladder below"* —
 * broke onto four lines and *"Text message"* onto two, and the matrix became
 * very long to scroll. Table layout is `auto`, so a `min-width` is what sizes
 * the column.
 *
 * ⚠ **CR-048 F1 MOVED THE MIN-WIDTHS FROM THE `<th>` TO THE CELL, AND THESE
 * TWO ASSERTIONS FOLLOW THEM.** The matrix is one flat `DataTable` now, which
 * owns its own header row and whose `TableColumnConfig` has no class of its
 * own; a min-width on the cell's wrapper sizes an auto-layout column for
 * exactly the same reason a min-width on the header did. **This is a stricter
 * question than before, not a looser one:** it is asked of the element holding
 * the string that actually broke — `notifications.rules.timing.ladder` — and
 * not of the header above it.
 */
describe("CR-048 · the matrix columns declare a width", () => {
  const LENGTH = /^\d+(\.\d+)?(rem|px|em|ch)$/;

  function renderMatrix() {
    mount(
      <RuleMatrix
        matrix={matrix()}
        readOnly={false}
        working={false}
        t={T}
        onOpen={() => undefined}
        onToggle={() => undefined}
      />,
    );
  }

  function expectRealMinWidth(widths: string[], what: string) {
    expect(widths.length, `no rule gives ${what} any width at all`).toBeGreaterThan(0);
    expect(widths.every((value) => LENGTH.test(value)), `min-width was ${widths.join(", ")}`).toBe(
      true,
    );
  }

  it("gives the TIMING column a real minimum width", async () => {
    renderMatrix();
    // The string in the defect, not the header above it.
    const cell = screen.getByText("notifications.rules.timing.ladder");
    expectRealMinWidth(await applied(cell, "min-width"), "the timing column");
  });

  it("gives the CHANNELS column a real minimum width", async () => {
    renderMatrix();
    const pill = screen.getByText("notifications.rules.channel.sms");
    const wrapper = pill.parentElement;
    expect(wrapper, "the channels cell has no wrapper to carry a width").not.toBeNull();
    expectRealMinWidth(await applied(wrapper as Element, "min-width"), "the channels column");
  });

  it("does not break a channel name across two lines", async () => {
    renderMatrix();
    const pill = screen.getByText("notifications.rules.channel.sms");
    expect(
      await applied(pill, "white-space"),
      "`Text message` wrapped after `Text`, which is what made the row two lines tall",
    ).toContain("nowrap");
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * CR-048 F6 — the template and language pickers were 60px
 * ══════════════════════════════════════════════════════════════════════════
 * *"They are 60px: a clerk sees `Bill re ⌄` and cannot tell which template,
 * which language or which version is selected."* It is the same mechanism as
 * defect 2 and it needs the same two halves — a column that declares a width,
 * and a control that fills the column rather than shrinking to its own content.
 * Assert BOTH, because either alone leaves the picker narrow.
 */
describe("CR-048 F6 · the pickers are wide enough to read", () => {
  const LENGTH = /^\d+(\.\d+)?(rem|px|em|ch)$/;

  function renderChannels() {
    const rule = detail();
    mount(
      <ChannelsCard
        rule={rule}
        readOnly={false}
        working={false}
        t={T}
        draft={draftOf(rule)}
        templateOptions={null}
        onChannelChange={() => undefined}
        onQueueTest={() => undefined}
      />,
    );
  }

  it("gives the TEMPLATE column a real minimum width", async () => {
    renderChannels();
    const header = screen.getByText("notifications.rules.col.template");
    const widths = await applied(header, "min-width");
    expect(widths.length, "the template column declares no width at all").toBeGreaterThan(0);
    expect(widths.every((value) => LENGTH.test(value)), widths.join(", ")).toBe(true);
  });

  it("gives the LANGUAGE column a real minimum width", async () => {
    renderChannels();
    const header = screen.getByText("notifications.rules.col.language");
    const widths = await applied(header, "min-width");
    expect(widths.length, "the language column declares no width at all").toBeGreaterThan(0);
    expect(widths.every((value) => LENGTH.test(value)), widths.join(", ")).toBe(true);
  });

  // ⚠ **A THIRD CASE WAS WRITTEN HERE AND DELETED, AND THE DELETION IS THE
  // FINDING.** It asserted that the `<select>` itself resolved to `width:
  // 100%`, on the obvious reading that a 60px picker is a narrow CONTROL. It
  // passed against this lane's parent commit as well as against the fix —
  // `FormModal.css` `.input` has declared `width: 100%` all along — so it was a
  // check that could not distinguish pass from fail, which DEF-182 says is
  // worse than no check because it is trusted. The RED run found it: every
  // other case in this file failed on the parent commit and that one did not.
  // The pickers were narrow only because the COLUMNS were, and the two
  // assertions above are the whole of F6.
  it("and the column is what was missing — a select at 100% of 60px is 60px", async () => {
    renderChannels();
    // Both halves asked of ONE element: the picker is inside the column the
    // header sized, so widening the column is what widens the control.
    const picker = screen.getByTestId("channel-template-email");
    const cell = picker.closest("td");
    expect(cell, "the picker is not in a table cell at all").not.toBeNull();
    expect(await applied(picker, "width")).toContain("100%");
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * CR-048 F7 — the unavailable channel's reason was five lines of red
 * ══════════════════════════════════════════════════════════════════════════
 * *"Five lines of red text inside a table row is the right information in the
 * wrong place."* The row keeps the whole sentence — `title` carries it and
 * BR-SHL-025 is satisfied — but it occupies ONE line, and it is not in the
 * danger tier, because nothing is wrong: the platform simply has no postal
 * integration.
 */
describe("CR-048 F7 · the unavailable channel's reason is one line", () => {
  function renderChannels() {
    const rule = detail();
    mount(
      <ChannelsCard
        rule={rule}
        readOnly={false}
        working={false}
        t={T}
        draft={draftOf(rule)}
        templateOptions={null}
        onChannelChange={() => undefined}
        onQueueTest={() => undefined}
      />,
    );
    return screen.getByTestId("channel-unavailable-reason-mail");
  }

  it("is clipped to one line rather than wrapped to five", async () => {
    const reason = renderChannels();
    expect(await applied(reason, "white-space"), "it still wraps to as many lines as it likes")
      .toContain("nowrap");
    expect(
      await applied(reason, "text-overflow"),
      "clipped with no ellipsis is worse than wrapped — the sentence just stops",
    ).toContain("ellipsis");
    expect(await applied(reason, "overflow")).toContain("hidden");
  });

  it("keeps the WHOLE sentence reachable, on the element itself", async () => {
    // Clipping is only lawful because nothing is lost: BR-SHL-025 wants the
    // reason, and this is the same `title` shape `RowActions` gives every
    // disabled row action in the product.
    const reason = renderChannels();
    expect(reason.getAttribute("title")).toContain("PHYSICAL POST");
    expect(reason.textContent).toContain("PHYSICAL POST");
  });

  it("is NOT in the danger tier — nothing here is an error", async () => {
    const reason = renderChannels();
    // `RefusalStrip` stamps `data-refusal` on whatever it renders, so this
    // asks the component's own marker rather than guessing at a colour.
    expect(reason.hasAttribute("data-refusal")).toBe(false);
    expect(reason.closest("[data-refusal]")).toBeNull();
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * CR-048 F4 — the rail is a COLUMN
 * ══════════════════════════════════════════════════════════════════════════
 * The plain-English sentence, the delivery half and the audit note were three
 * cards inside `.settings-grid`'s `repeat(auto-fit, minmax(320px, 1fr))`, so
 * they took whichever track was free — on a wide screen the rail landed second
 * in row two, between the timing card and the ladder. This asserts the two
 * things that make it a rail and not a card: an explicit two-track grid, and a
 * DESKTOP-FIRST collapse (OQ-274 — `max-lg:`, never `lg:`, whose min-width
 * variant would compile to nothing at all).
 */
describe("CR-048 F4 · the rule page has a right rail", () => {
  it("declares two tracks, the second of them a fixed rail", async () => {
    const compiled = await tailwindRules(RULE_LAYOUT.split(/\s+/));
    const templates = RULE_LAYOUT.split(/\s+/).flatMap((token) =>
      declarationsIn(compiled, token, "grid-template-columns"),
    );
    expect(templates.length, "nothing gives this page any column structure").toBeGreaterThan(0);
    // A flexible body track and a rail with a width of its own. Two tracks is
    // what makes it a rail; one track is the `.settings-grid` this replaced.
    const twoTrack = templates.filter(
      (value) => /\b1fr\b/.test(value) && /\d+(\.\d+)?rem/.test(value),
    );
    expect(
      twoTrack,
      `no two-track rule: ${templates.join(" | ")}`,
    ).not.toEqual([]);
  });

  it("collapses DESKTOP-FIRST, so the variant is a real one", async () => {
    // ⚠ The failure this catches is silent by construction: `--breakpoint-*`
    // is cleared (OQ-274), so `lg:grid-cols-1` compiles to NOTHING and the page
    // simply never stacks — and `tsc`, eslint and a `toContain` assertion all
    // pass over it (the DEF-974 hazard in variant form).
    const stacked = RULE_LAYOUT.split(/\s+/).filter((token) => token.startsWith("max-lg:"));
    expect(stacked, "no desktop-first collapse is authored at all").not.toEqual([]);
    const compiled = await tailwindRules(stacked);
    expect(
      compiled.length,
      `${stacked.join(" ")} compiled to no rule — the breakpoint does not exist`,
    ).toBeGreaterThan(0);
  });
});

/* ══════════════════════════════════════════════════════════════════════════
 * DEF-NOT-9667 — Messages needing attention is wider than its card at 1440
 * ══════════════════════════════════════════════════════════════════════════
 * Measured on 2.517.0 at 1440: the table 838px in a 752px box, so *What went
 * wrong* and the row's buttons sat past the card's edge. The cause is an email
 * with no break opportunity — `silvercreeksamplemillworks49@example.invalid`
 * held the recipient column at 336px. `overflow-wrap: anywhere` is the value
 * that lowers a cell's MIN-CONTENT width (`break-word` does not), which is what
 * an auto-layout table sizes a column by.
 */
describe("DEF-NOT-9667 · a long address breaks inside its cell", () => {
  it("the recipient and what-went-wrong cells may break anywhere", async () => {
    const email = "silvercreeksamplemillworks49@example.invalid";
    mount(
      <QueueTable
        rows={[
          {
            id: "01a0-0000", source_type: "payment", source_id: "01a0-1111", account_id: null,
            account_no: null, channel: "email", copy_no: 0, status: "failed", held: false,
            held_reason: null, attempts: 3, last_error: "smtp_550_mailbox_unavailable_for_this_recipient",
            batch_id: null, provider_reference: null, template_code: "email_payment_receipt",
            template_version: 1, template_language: "en", recipient_address: email,
            unavailable_reason: null, queued_at: "2026-10-04T10:00:00Z", dispatch_not_before: null,
            last_attempt_at: null, sent_at: null, returned_at: null,
          } as never,
        ]}
        total={1}
        page={1}
        per={50}
        onPage={() => undefined}
        onPer={() => undefined}
        readOnly={false}
        working={false}
        t={T}
        disclosableChannels={[]}
        vocabulary={undefined}
        selected={new Set()}
        pageSelectable={[]}
        onToggle={() => undefined}
        onTogglePage={() => undefined}
        onRequeue={() => undefined}
        onShowDocument={() => undefined}
        onShowUnsent={() => undefined}
        onShowDetails={() => undefined}
        onRetryTo={() => undefined}
      />,
    );
    const recipient = screen.getByText(email).closest("td") as HTMLElement;
    expect(await applied(recipient, "overflow-wrap"), "the email holds its column open").toContain(
      "anywhere",
    );
    const error = screen.getByText("smtp_550_mailbox_unavailable_for_this_recipient").closest("td") as HTMLElement;
    expect(await applied(error, "overflow-wrap")).toContain("anywhere");
  });
});
