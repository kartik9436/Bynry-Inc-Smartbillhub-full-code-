// ── Trace ──────────────────────────────────────────────
// Story:    US-NOT-017 (SET-12 the notification event matrix + SET-12D the event
//           rule page — CR-009 · the SCREEN)   Screens: S8
// Rules:    BR-NOT-017 (ONE HOME for every notification rule — PO 2026-08-17) ·
//           BR-NOT-018 (an event with no trigger is DRAWN and says so) ·
//           BR-NOT-005 (queue only — "Send test" ENQUEUES) ·
//           BR-NOT-013 (delivery is out of this release on every channel, so
//           `delivered`/`failed` render NOT REPORTED and never 0) ·
//           BR-SHL-020 (plain-language failure) ·
//           BR-SHL-025 (a forbidden control renders DISABLED WITH its reason) ·
//           BR-TEN-024 (atomic per-page save) · B14 rules 2, 5, 6, 15, 18, 20
// ───────────────────────────────────────────────────────
// S8 → Notifications → SET-12: WHICH MESSAGES THIS UTILITY SENDS, AND TO WHOM.
//
// Until 2026-08-17 nothing stored this. There was no `notification_rules` table
// and no per-event audience, channel, timing or escalation storage anywhere, so
// a utility could not decide that a bill-ready email goes out and a hi-usage
// text does not — measured before building, and it is the bulk of CR-009.
//
// ── THE FOUR THINGS THIS SCREEN REFUSES TO SAY ────────────────────────────
//  1. **It never draws a live toggle for a channel this platform does not
//     have.** [AMENDED 2026-08-22 — this bullet listed In-app among the
//     missing; `in_app` has been a real, dispatchable channel since BR-NOT-019
//     (2026-08-18).] Portal and Mail are in the PO's requirement and are
//     implemented nowhere; each renders DISABLED with the server's own reason
//     (BR-SHL-025). "Mail" on a disconnect notice means physical post, which is
//     a fulfilment vendor and not a flag anybody can switch.
//  2. **It never implies an event will fire when nothing can fire it.** Six of
//     fifteen have no trigger — three on Work → Rules (OQ-249) and three with
//     no owner at all (OQ-262) — and each row carries that ID. They are drawn
//     because their audience, channel and template ARE this screen's to own,
//     which is what the CR asks for (BR-NOT-018).
//  3. **It never offers a recipient for a staff notification.** [AMENDED
//     2026-08-22 — this bullet carried OQ-261 as OPEN; the PO closed it
//     2026-08-17 → BR-NOT-021.] The recipient is a RULED platform policy —
//     the user who started the action, plus every active System Admin on
//     failure — and the Audience card STATES it, in the server's own words,
//     and still draws no picker: one would be a second answer beside the
//     ruled one. DEF-286's editors (2026-08-22) deliberately kept this card
//     picker-free on staff events.
//  4. **It never prints "0 delivered".** `delivered` and `failed` are PROVIDER
//     facts and no adapter exists on any channel (BR-NOT-013), so the Last-30-
//     days rail renders NOT REPORTED — the same discipline the delivery
//     dashboard beside it already keeps.
//
// ── WHAT "SEND TEST" DOES, drawn honestly ─────────────────────────────────
// It ENQUEUES. The button reads "Queue a test to me", the result states BOTH
// halves — a row is on the queue, addressed to you, and it will not leave the
// building — and the wrapper it calls posts to `…/queue-test`. There is no
// send route in this product and A11 r2 §4 makes minting one a gate failure.
//
// ── THE ESCALATION LADDER IS SHOWN HERE AND CHANGED IN ONE OTHER PLACE ────
// [AMENDED 2026-08-30 — CR-048 F5. This heading read *"IS EDITED HERE"* and
// the paragraph said the figures were "read from and written to" the settings
// contract. The card is READ-ONLY now and this file no longer writes them.]
// PO ruling 2026-08-17: *"we bring all internal external ntification rule sat
// one place and they are part of notification settings"*. The five figures —
// reminder 3 days after due, tiers 10 then 5, final 48 hours, the $25.00 floor
// and the 25% pause — are read from the EXISTING `/settings/collections`
// document, which is where the live collections engine reads them too, and the
// card NAMES that place rather than offering a second editor onto it (CR-048
// F5: *"so the collections run and the notice can never disagree about the
// same numbers"*). ONE HOME for the rule — this page, where a person reading
// the disconnect-notice rule sees the ladder that schedules it. ONE PLACE to
// change the figure — Settings › Collections. The two MONEY figures have never
// had a screen anywhere except this one (DEF-204, DEF-097), and still do.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import {
  getNotificationRule,
  getNotificationRules,
  getTenantServices,
  queueNotificationTest,
  updateNotificationRule,
} from "@/api/endpoints";
import type {
  NotificationChannelRule,
  NotificationRuleDetail,
  NotificationRuleMatrix,
  NotificationRulePatch,
  NotificationRuleRow,
  NotificationTestResult,
} from "@/api/endpoints";
import {
  CUSTOMER_SCOPES,
  FAILURE_POLICIES,
  LANGUAGE_MODES,
  PLAN_CLASSES,
  QUIET_HOURS_MODES,
  TRIGGER_MODES,
  draftOf,
  getTemplateOptionsByChannel,
  ruleSavePatch,
  timingProblem,
} from "@/api/notificationRuleEndpoints";
import type {
  NotificationRuleDraft,
  NotificationTemplateOption,
} from "@/api/notificationRuleEndpoints";
import { REFERENCE_STALE_MS } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { FilterBar } from "@/components/FilterBar";
import { CheckboxField, SelectField, TextField } from "@/components/FormModal";
import { PencilIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { defaultRequestState } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { testResultSentence } from "./testResultSentence";

import {
  ACTIONS,
  CARD_COLUMN,
  CHANNEL_PILL,
  CHANNEL_PILL_OFF,
  CODE_CELL,
  COL_CHANNELS,
  COL_EVENT,
  COL_LANGUAGE,
  COL_TEMPLATE,
  COL_TIMING,
  HINT,
  KV_KEY,
  KV_LIST,
  KV_ROW,
  KV_SENTENCE,
  MUTED,
  REASON_CLAMP,
  ROW_MARKER,
  RULE_COLUMN,
  RULE_LAYOUT,
  TABLE_SCROLL,
  UNAVAILABLE_REASON,
} from "./notificationsKit";

import {
  Panel,
  RefusalNotice,
  SettingsFrame,
  apiErrorText,
  refusalOf,
} from "../tenancy/settingsShared";
import type { Refusal, Translator } from "../tenancy/settingsShared";

/**
 * The five ladder keys the PO's "one place" ruling names, and no sixth.
 *
 * ⚠ **SET-12D NO LONGER WRITES THEM — CR-048 F5 made the ladder card
 * READ-ONLY**, so this list is no longer the partial change set this page
 * posts. It is kept, exported and tested because it is still the definitive
 * enumeration of WHICH five figures BR-NOT-017 puts on this page: the
 * collections settings family also holds payment-plan, NSF and
 * paper-suppression rows, and a future reader needs to know that those four
 * were never this screen's. `NotificationRules.test.tsx` asserts the five
 * against the card, which is what keeps the list honest now that no save
 * consumes it.
 */
export const LADDER_KEYS = [
  "reminder_days_after_due",
  "notice_tier_days",
  "final_notice_hours",
  "ladder_balance_floor_amount",
  "partial_payment_pause_percent",
] as const;

/** ⚠ NOT a display choice — BR-NOT-013. `delivered` and `failed` cannot be
 *  written by anything in this repo, so the rail says so instead of showing a
 *  zero that reads as a delivery failure. */
export const DELIVERY_COUNTS_ARE_UNREPORTABLE = true;

/** The rule in plain English, re-rendered as settings change (the CR's own
 *  right-rail requirement). Built from CATALOGUE keys rather than concatenated
 *  prose, so it translates like everything else in this product. */
export function plainEnglishRule(rule: NotificationRuleRow, t: Translator): string {
  const channels = rule.channel_rules
    .filter((row) => row.enabled)
    .map((row) => t(`notifications.rules.channel.${row.channel}`));
  const audience =
    rule.audience === "staff"
      ? t("notifications.rules.plain.audienceStaff")
      : t(`notifications.rules.plain.audience.${rule.customer_scope}`);
  const timing =
    rule.trigger_mode === "offset_days"
      ? t("notifications.rules.plain.timing.offset_days", { days: rule.offset_days ?? 0 })
      : rule.trigger_mode === "fixed_time"
        ? t("notifications.rules.plain.timing.fixed_time", { time: rule.fixed_time ?? "" })
        : t("notifications.rules.plain.timing.immediate");
  if (channels.length === 0) {
    // Not a sentence with a blank in it: a rule with no enabled channel sends
    // nothing, and saying so is the whole value of this rail.
    return t("notifications.rules.plain.noChannel", {
      event: t(`notifications.rules.event.${rule.key}`),
    });
  }
  return t("notifications.rules.plain.sentence", {
    event: t(`notifications.rules.event.${rule.key}`),
    audience,
    channels: channels.join(", "),
    timing,
    exclusions: rule.skip_accounts_on_payment_plan
      ? t("notifications.rules.plain.skipPlans")
      : t("notifications.rules.plain.noExclusions"),
  });
}

// ── SET-12 · the matrix ────────────────────────────────────────────────────
//
// ⚠ **ONE FLAT TABLE, AND THE GROUP HEADINGS ARE GONE (CR-048 F1).**
// This was five `<h4>` + `<table>` pairs, one per category, because the row
// ORDER was treated as the rule (*"the PO's own grouping"*, this file's own
// retired exception 5). Reading it needed the heading repeated above every
// block, and the fifteen events could not be sorted, filtered, searched or
// paged — the four things every other list in this product does. The category
// is a COLUMN now, which is what makes all four possible, and the shared
// `DataTable` is what supplies them (B14 rule 20: one table type).

/**
 * **THE DISPLAY CODE — `NTF-01`…`NTF-15` (CR-048 F1).**
 *
 * ⚠ **THE SERVER DOES NOT SERVE ONE, AND THIS WAS CHECKED BEFORE IT WAS
 * INVENTED.** `rule_catalog.EventClass.as_wire()` carries `key`, `category`,
 * `audience`, `channels`, `timing_key` and `has_ladder` and nothing shaped like
 * a code; `EVENT_KEYS` is the catalogue's own identifier and it is a snake_case
 * NAME, not a number. So this is a DISPLAY CONVENTION over those keys, which is
 * exactly what the CR asked for — and it is written as an explicit map rather
 * than as `index + 1` over `matrix.results` for the one reason that matters:
 *
 * **A POSITIONAL CODE IS NOT A STABLE CODE.** Waves B10 and B11 add sixteen
 * more events to this catalogue. A code derived from a row's position would
 * renumber every event below the insertion point, so the `NTF-07` a clerk wrote
 * on a support ticket last week would name a different event this week. A map
 * keyed by the event KEY renumbers nothing, ever.
 *
 * The order below is the catalogue's own (`rule_catalog.EVENTS`), so today's
 * fifteen read 01…15 down the default sort.
 *
 * ⚠ **AN EVENT WITH NO ENTRY GETS NO CODE — IT DOES NOT GET AN INVENTED ONE.**
 * `eventCode` returns `null` and the cell renders EMPTY. A wave-B11 event
 * arriving before this map is extended is identified by its name, which is
 * true, rather than by a number this screen made up, which would collide with
 * a real one the moment the map caught up (DEF-127's lesson, applied to an
 * identifier instead of to a figure).
 */
export const EVENT_CODES: Readonly<Record<string, string>> = {
  bill_ready: "NTF-01",
  bill_corrected: "NTF-02",
  payment_received: "NTF-03",
  payment_failed: "NTF-04",
  past_due_reminder: "NTF-05",
  disconnect_notice: "NTF-06",
  high_usage_alert: "NTF-07",
  appointment_window: "NTF-08",
  technician_on_the_way: "NTF-09",
  completion_receipt: "NTF-10",
  billing_run_completed: "NTF-11",
  reconciliation_exceptions: "NTF-12",
  sla_breach: "NTF-13",
  daily_digest: "NTF-14",
  security_alerts: "NTF-15",
};

/** The code for one event, or `null` when this map has never been told one. */
export function eventCode(key: string): string | null {
  return Object.prototype.hasOwnProperty.call(EVENT_CODES, key) ? EVENT_CODES[key] : null;
}

/** What a row SORTS and SEARCHES on, per column — the string the clerk can
 *  actually see, never the wire code underneath it. Sorting `category` by
 *  `billing`/`collections` would order a French tenant's screen by English
 *  words nobody on it has read. */
export function ruleSortValue(row: NotificationRuleRow, column: string, t: Translator): string {
  switch (column) {
    case "code":
      // An event with no code sorts LAST rather than first: `~` is above every
      // digit and letter in code-point order, and an empty string would put the
      // unnumbered rows at the top of the default view.
      return eventCode(row.key) ?? "~";
    case "category":
      return t(`notifications.rules.category.${row.category}`);
    case "audience":
      return t(`notifications.rules.audience.${row.audience}`);
    case "enabled":
      return row.enabled ? "1" : "0";
    case "timing":
      return t(`notifications.rules.timing.${row.timing_key}`);
    default:
      return t(`notifications.rules.event.${row.key}`);
  }
}

/**
 * Search · filter · sort · page, applied HERE rather than by the server.
 *
 * ⚠ **AND THAT IS A DELIBERATE DEPARTURE FROM IS-2, STATED RATHER THAN
 * QUIETLY DONE.** Every other list in this product pages server-side because
 * every other list is over TENANT DATA and can be a million rows.
 * `GET /notification-rules` is not: it serves a PLATFORM CONSTANT — the whole
 * catalogue, fifteen rows today and thirty-one after waves B10/B11 — in one
 * response, with no `q`, `sort`, `page` or `f.` parameters to send it. Asking
 * the server for a page of fifteen would need a new contract for no gain, so
 * the state is applied to the rows already in hand and `totalRows` is the
 * FILTERED count, which is what the pager and the "showing N of M" line both
 * mean.
 */
export function applyRuleTableState(
  rows: readonly NotificationRuleRow[],
  state: TableRequestState,
  t: Translator,
): { rows: NotificationRuleRow[]; total: number } {
  const needle = state.q.trim().toLocaleLowerCase();
  const kept = rows.filter((row) => {
    for (const [name, value] of Object.entries(state.filters)) {
      if (value === "") continue;
      if (name === "category" && row.category !== value) return false;
      if (name === "audience" && row.audience !== value) return false;
      if (name === "enabled" && String(row.enabled) !== value) return false;
    }
    if (needle === "") return true;
    // The code and the NAME — the two things a person types when they are
    // looking for an event, and the two the code column exists to give them.
    const haystack = [
      eventCode(row.key) ?? "",
      t(`notifications.rules.event.${row.key}`),
      t(`notifications.rules.category.${row.category}`),
    ]
      .join(" ")
      .toLocaleLowerCase();
    return haystack.includes(needle);
  });
  const sorted = [...kept].sort((left, right) => {
    const order = ruleSortValue(left, state.sort, t).localeCompare(
      ruleSortValue(right, state.sort, t),
    );
    // A stable secondary sort by the event KEY, exactly as IS-2 has the server
    // do behind the one user-chosen column: without it two Collections rows
    // swap places on every re-render and the list looks alive.
    const tie = left.key.localeCompare(right.key);
    return (order !== 0 ? order : tie) * (state.dir === "desc" ? -1 : 1);
  });
  const from = (state.page - 1) * state.per;
  return { rows: sorted.slice(from, from + state.per), total: sorted.length };
}

/** One cell renderer per column of the matrix. */
export interface RuleTableCells {
  code: (row: NotificationRuleRow) => ReactNode;
  event: (row: NotificationRuleRow) => ReactNode;
  category: (row: NotificationRuleRow) => ReactNode;
  audience: (row: NotificationRuleRow) => ReactNode;
  channels: (row: NotificationRuleRow) => ReactNode;
  timing: (row: NotificationRuleRow) => ReactNode;
  enabled: (row: NotificationRuleRow) => ReactNode;
  actions: (row: NotificationRuleRow) => ReactNode;
}

/** `defaultRequestState` reads only `defaultSort`, so the FIRST config — the
 *  one that seeds the request state — needs no cells. Named rather than
 *  inlined so the two `ruleTableConfig` calls cannot drift on the argument
 *  that does matter. */
const NO_CELLS: RuleTableCells = {
  code: () => null,
  event: () => null,
  category: () => null,
  audience: () => null,
  channels: () => null,
  timing: () => null,
  enabled: () => null,
  actions: () => null,
};

/** The capability row (BR-SHL-010): what this list can do is DECLARED, and the
 *  framework renders only what is declared. */
export function ruleTableConfig(
  t: Translator,
  categories: string[],
  cells: RuleTableCells,
): TableConfig<NotificationRuleRow> {
  return {
    screenId: "SET-12",
    columns: [
      { key: "code", label: t("notifications.rules.col.code"), sortable: true, cell: cells.code },
      {
        key: "event",
        label: t("notifications.rules.col.event"),
        sortable: true,
        identity: true,
        cell: cells.event,
      },
      {
        key: "category",
        label: t("notifications.rules.col.category"),
        sortable: true,
        cell: cells.category,
      },
      {
        key: "audience",
        label: t("notifications.rules.col.audience"),
        sortable: true,
        cell: cells.audience,
      },
      { key: "channels", label: t("notifications.rules.col.channels"), cell: cells.channels },
      {
        key: "timing",
        label: t("notifications.rules.col.timing"),
        sortable: true,
        cell: cells.timing,
      },
      {
        key: "enabled",
        label: t("notifications.rules.col.on"),
        sortable: true,
        cell: cells.enabled,
      },
      { key: "actions", label: t("notifications.rules.col.actions"), cell: cells.actions },
    ],
    getRowId: (row) => row.key,
    searchFields: ["code", "event"],
    // B14 rule 19 / G43 clause (a) — this list's OWN prompt, naming what the
    // box matches. "Search this list" would not tell a clerk that the code is
    // searchable, which is half of why the code exists.
    searchPlaceholder: "notifications.rules.searchPlaceholder",
    filters: [
      {
        name: "category",
        label: t("notifications.rules.col.category"),
        options: categories.map((category) => ({
          value: category,
          label: t(`notifications.rules.category.${category}`),
        })),
      },
      {
        name: "audience",
        label: t("notifications.rules.col.audience"),
        options: ["customer", "staff"].map((audience) => ({
          value: audience,
          label: t(`notifications.rules.audience.${audience}`),
        })),
      },
      {
        name: "enabled",
        label: t("notifications.rules.col.on"),
        options: [
          { value: "true", label: t("notifications.rules.filter.on") },
          { value: "false", label: t("notifications.rules.filter.off") },
        ],
      },
    ],
    // The catalogue's own order, which the code column now expresses as a
    // number a person can sort BACK to after sorting by anything else.
    defaultSort: { sort: "code", dir: "asc" },
  };
}

/** The channels cell: the event's own channels, then the ones the platform does
 *  not have — visible, quiet, and carrying their reason (BR-SHL-025). */
export function ChannelPills(props: { row: NotificationRuleRow; t: Translator }) {
  const { row, t } = props;
  return (
    <>
      {row.channel_rules.map((channel) => (
        <span
          key={channel.channel}
          className={channel.enabled ? CHANNEL_PILL : CHANNEL_PILL_OFF}
          title={channel.enabled ? undefined : t("notifications.rules.channelOff")}
        >
          {t(`notifications.rules.channel.${channel.channel}`)}
        </span>
      ))}
      {row.unavailable_channels.map((channel) => (
        <span
          key={channel.channel}
          className={CHANNEL_PILL_OFF}
          title={channel.reason}
          data-testid={`rule-unavailable-${row.key}-${channel.channel}`}
        >
          {t(`notifications.rules.channel.${channel.channel}`)}
        </span>
      ))}
    </>
  );
}

export function RuleMatrix(props: {
  matrix: NotificationRuleMatrix;
  readOnly: boolean;
  working: boolean;
  t: Translator;
  onOpen: (key: string) => void;
  onToggle: (key: string, next: boolean) => void;
}) {
  const { matrix, t } = props;
  // ⚠ LOCAL STATE, NOT THE URL. Every other list serializes this into
  // `useSearchParams` (BR-SHL-011), and this one cannot: SET-12 lives inside
  // the S8 Settings tab whose URL segment is already spoken for — `sub` is the
  // OPEN RULE (`/settings/notifications/:sub`), which is what makes a rule page
  // linkable. Two owners of one query string is a race, not a feature. The cost
  // is stated rather than hidden: a filtered view of this list is not
  // bookmarkable, and it is fifteen rows.
  const [state, setState] = useState<TableRequestState>(() =>
    defaultRequestState(ruleTableConfig(t, matrix.categories, NO_CELLS)),
  );
  const config = ruleTableConfig(t, matrix.categories, {
    code: (row) => {
      const code = eventCode(row.key);
      // Nothing, never a placeholder that could be mistaken for a code.
      return code === null ? null : <span className={CODE_CELL}>{code}</span>;
    },
    event: (row) => (
      /* The wrapper is what sizes an auto-layout column — the same move
         `channels` and `timing` make below, and for the same reason. */
      <span className={`${COL_EVENT} block`}>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => props.onOpen(row.key)}
          data-testid={`rule-open-${row.key}`}
        >
          {t(`notifications.rules.event.${row.key}`)}
        </Button>
        {row.trigger_blocked_by !== null && (
          /* BR-NOT-018 — DRAWN AND NAMED, which is what the rule requires, and
             from CR-048 wave I it is named in THREE WORDS instead of a
             paragraph.

             ⚠ **THE MARKER IS NOW WHAT SATISFIES BR-NOT-018 ON THIS ROW.** The
             rule's requirement is that an event nothing fires is drawn and
             refused BY NAME rather than silently switched on; it says nothing
             about how many words that takes. A utility that switches on
             *Autopay set up* and sees nothing happen is the defect CR-048 was
             raised to fix, so the fact may never be deleted — but it does not
             have to be delivered as three lines of red prose inside a table
             cell, repeated on every such row. PO ruling 2026-08-30, verbatim:
             *"keep the fact, kill the paragraph — a small greyed marker on the
             row, and the full sentence only when you open that event. Same
             protection, no wreckage."*

             So: a grey marker on the row, the WHOLE sentence on `title`, and
             the whole sentence again on the event's own page (`detail-noTrigger`,
             below) which this row's name opens in one click. The `enabled`
             checkbox a few cells along is still DISABLED with the same sentence
             as its tooltip (BR-SHL-025), so the protection is unchanged in
             both places a person could act on it.

             ⚠ NOT a `RefusalStrip` any more. That component carries
             `data-refusal`, the danger tier and the red rule, and B14 rule 6
             reserves that tier for a DESTRUCTIVE COMMIT. An event nobody has
             wired yet is a fact about the build, not a danger — twelve red
             boxes down one column taught a reader to stop reading them, which
             is the opposite of what BR-NOT-018 wants. */
          <span
            className={ROW_MARKER}
            data-testid={`rule-noTrigger-${row.key}`}
            // CR-016: the id stays reachable for support, off the sentence.
            data-blocked-by={row.trigger_blocked_by}
            // The paragraph, in full, one hover away — and on the rule page.
            title={t("notifications.rules.noTrigger")}
          >
            {t("notifications.rules.noTriggerMark")}
          </span>
        )}
      </span>
    ),
    category: (row) => t(`notifications.rules.category.${row.category}`),
    audience: (row) => (
      <span className={CHANNEL_PILL}>{t(`notifications.rules.audience.${row.audience}`)}</span>
    ),
    // ⚠ WAVE C1's TWO COLUMN WIDTHS, MOVED FROM THE `<th>` TO THE CELL, AND
    // THEY ARE STILL LOAD-BEARING. CR-048's second visible defect was a
    // one-line row four lines tall: no column on this matrix declared any
    // width, table layout is `auto`, so "On the escalation ladder below" broke
    // onto FOUR lines and "Text message" onto two. Wave C put the `min-width`
    // on the header cell; `DataTable` owns the header row now and
    // `TableColumnConfig` has no class of its own, so it goes on the cell's own
    // wrapper — which sizes an auto-layout column for exactly the same reason.
    // `notificationsLayout.dom.test.tsx` resolves these through the compiler.
    channels: (row) => (
      <span className={`${COL_CHANNELS} block`}>
        <ChannelPills row={row} t={t} />
      </span>
    ),
    timing: (row) => (
      <span className={`${COL_TIMING} block`}>
        {t(`notifications.rules.timing.${row.timing_key}`)}
      </span>
    ),
    enabled: (row) => {
      // CR-048 F8 · the fourth page shape. An event NOTHING FIRES stays fully
      // editable — its audience, channels and template are still this screen's
      // to own — and it CANNOT BE SWITCHED ON, because a switch that turns on
      // an event no writer reaches is a promise the product cannot keep
      // (BR-NOT-018 read forwards; BR-SHL-025 for the shape). Disabled WITH its
      // reason, never hidden — and never disabled on a row that is ALREADY on,
      // because a utility must always be able to switch something off.
      const blocked = row.trigger_blocked_by !== null && !row.enabled;
      return (
        <input
          type="checkbox"
          checked={row.enabled}
          disabled={props.readOnly || props.working || blocked}
          title={
            props.readOnly
              ? t("notifications.rules.readOnlyReason")
              : blocked
                ? t("notifications.rules.noTrigger")
                : undefined
          }
          aria-label={t("notifications.rules.col.on")}
          data-testid={`rule-toggle-${row.key}`}
          onChange={(event) => props.onToggle(row.key, event.target.checked)}
        />
      );
    },
    actions: (row) => (
      // B14 rule 15 / G37 — an ICON with a tooltip, through the ONE row-action
      // component, instead of this file's own `settings-icon-btn` glyph.
      <RowActions>
        <RowAction
          label={t("notifications.rules.action.edit")}
          icon={<PencilIcon />}
          onClick={() => props.onOpen(row.key)}
          // ⚠ `testId`, not `data-testid` — `RowAction` names the prop itself
          // and drops anything it does not name, which is a hook that silently
          // is not there (`toContain("rule-edit-…")` fails LOUDLY, which is why
          // this was caught). The component's own docstring says the preferred
          // hook is the accessible name; this id carries the one the matrix
          // already published.
          testId={`rule-edit-${row.key}`}
        />
      </RowActions>
    ),
  });
  const page = applyRuleTableState(matrix.results, state, t);
  return (
    <Panel
      title={t("notifications.rules.title")}
      hint={t("notifications.rules.hint", { count: matrix.count })}
    >
      {/* ⚠ CR-016, 2026-08-19 — THE REQUIREMENT-COUNT CALLOUT NO LONGER
          RENDERS, DELIBERATELY. It used to read: *"The written requirement
          names 16 events and describes 15."* That is a true and useful
          statement ABOUT OUR OWN REQUIREMENTS DOCUMENT, and a System Admin at a
          small utility can do nothing whatever with it. The PO photographed the
          box: *"Youa re also adding internal content and BR codes on screen,
          that is not required"*. The counts are still SERVED — only the
          sentence to the clerk is gone. */}
      {/* ⚠ DEF-NOT-10537, 2026-10-22 — THE RELEASE-POSTURE NOTE IS GONE TOO.
          It drew the server's *"… none of them leaves the building"* while
          email sends. PO: *"Each channel tells the clerk the truth about
          itself, in one short line"* — that line is the Channel status card's,
          on the same tab, so the matrix carries no release sentence. */}
      <DataTable<NotificationRuleRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={page.rows}
        totalRows={page.total}
        loading={false}
        filterBarSlot={
          <FilterBar filters={config.filters ?? []} state={state} onStateChange={setState} />
        }
        empty={{
          title: t("notifications.rules.emptyTitle"),
          helper: t("notifications.rules.emptyHelper"),
          ctaLabel: t("notifications.rules.emptyCta"),
          // BR-SHL-025 — the CTA is drawn DISABLED with its reason, because
          // there is nothing behind it: the event catalogue is a platform
          // constant and a tenant cannot add a sixteenth event.
          ctaReason: t("notifications.rules.emptyCtaReason"),
          onCta: () => undefined,
        }}
      />
    </Panel>
  );
}

// ── SET-12D · the rule page ────────────────────────────────────────────────

/** The service-scope options: `all` plus the tenant's OWN services, or — when
 *  the services read failed — `all` plus whatever the rule currently holds, so
 *  the select always shows the truth it opened with and never invents a code. */
export function serviceScopeOptions(
  current: string,
  services: { service: string; name: string }[] | null,
  t: Translator,
): { value: string; label: string }[] {
  const options = [{ value: "all", label: t("notifications.rules.serviceScope.all") }];
  for (const row of services ?? []) {
    options.push({ value: row.service, label: row.name });
  }
  if (!options.some((option) => option.value === current)) {
    // The stored value survives a failed services read — dropping it would
    // make the select silently rewrite the rule on the next save.
    options.push({ value: current, label: current });
  }
  return options;
}

export function AudienceCard(props: {
  rule: NotificationRuleDetail;
  readOnly: boolean;
  t: Translator;
  draft: NotificationRuleDraft;
  /** null = `GET /settings/services` failed or has not answered. */
  serviceRows: { service: string; name: string }[] | null;
  onChange: (change: Partial<NotificationRuleDraft>) => void;
}) {
  const { rule, t } = props;
  if (rule.staff_recipient_policy !== null) {
    // BR-NOT-021 (OQ-261 CLOSED 2026-08-17) — the recipient is a RULED
    // platform policy, so this card STATES it and still offers no picker —
    // DEF-286's editors included: the PO chose "the user who started the
    // action, plus all System Admins for failures" over every per-rule picker
    // option, and drawing one would be a second answer beside the ruled one.
    // (`rule_service._validated` refuses a customer_scope on a staff rule by
    // the same reasoning, so an editor here could only ever be refused.) The
    // sentence is the SERVER's own, rendered verbatim (hard-won law 1: a
    // screen that re-worded the policy would drift from it).
    return (
      <Panel title={t("notifications.rules.card.audience")}>
        <p className={HINT} data-desc role="note" data-testid="audience-staff-policy">
          <span className={MUTED}>{t("notifications.rules.staffRecipientRuled")}</span>{" "}
          {rule.staff_recipient_policy}
        </p>
      </Panel>
    );
  }
  if (props.readOnly) {
    // An Executive READS the rule (DEF-196's split). The house select has no
    // disabled state, so the read view stays the definition list it always
    // was, with the standing reason beside it (BR-SHL-025) — decision-log row
    // 2026-08-22.
    return (
      <Panel title={t("notifications.rules.card.audience")}>
        <dl>
          <dt>{t("notifications.rules.field.customerScope")}</dt>
          <dd data-testid="audience-scope">
            {t(`notifications.rules.plain.audience.${rule.customer_scope}`)}
          </dd>
          <dt>{t("notifications.rules.field.serviceScope")}</dt>
          <dd data-testid="audience-service">
            {rule.service_scope === "all"
              ? t("notifications.rules.serviceScope.all")
              : rule.service_scope}
          </dd>
          <dt>{t("notifications.rules.field.planClass")}</dt>
          <dd data-testid="audience-planClass">
            {t(`notifications.rules.planClass.${rule.plan_class}`)}
          </dd>
          <dt>{t("notifications.rules.field.skipPlans")}</dt>
          <dd data-testid="audience-skipPlans">
            {rule.skip_accounts_on_payment_plan
              ? t("notifications.rules.yes")
              : t("notifications.rules.no")}
          </dd>
        </dl>
        <Note role="note">{t("notifications.rules.readOnlyReason")}</Note>
      </Panel>
    );
  }
  // DEF-286 — the CR's own pickers. Every field below is in
  // `EDITABLE_RULE_FIELDS` and nothing outside it is drawn.
  return (
    <Panel title={t("notifications.rules.card.audience")}>
      <div data-testid="audience-scope">
        <SelectField
          id="rule-customer-scope"
          label={t("notifications.rules.field.customerScope")}
          value={props.draft.customer_scope}
          onChange={(value) => props.onChange({ customer_scope: value })}
          options={CUSTOMER_SCOPES.map((scope) => ({
            value: scope,
            label: t(`notifications.rules.plain.audience.${scope}`),
          }))}
        />
      </div>
      <div data-testid="audience-service">
        <SelectField
          id="rule-service-scope"
          label={t("notifications.rules.field.serviceScope")}
          value={props.draft.service_scope}
          onChange={(value) => props.onChange({ service_scope: value })}
          options={serviceScopeOptions(props.draft.service_scope, props.serviceRows, t)}
        />
      </div>
      <div data-testid="audience-planClass">
        <SelectField
          id="rule-plan-class"
          label={t("notifications.rules.field.planClass")}
          value={props.draft.plan_class}
          onChange={(value) => props.onChange({ plan_class: value })}
          options={PLAN_CLASSES.map((planClass) => ({
            value: planClass,
            label: t(`notifications.rules.planClass.${planClass}`),
          }))}
        />
      </div>
      <div data-testid="audience-skipPlans">
        <CheckboxField
          id="rule-skip-plans"
          label={t("notifications.rules.field.skipPlans")}
          checked={props.draft.skip_accounts_on_payment_plan}
          onChange={(checked) => props.onChange({ skip_accounts_on_payment_plan: checked })}
        />
      </div>
    </Panel>
  );
}

/** The template `<select>`'s options for ONE channel: the catalog's REAL
 *  classes for that channel (never an invented name), the empty "no template"
 *  choice, and — if the catalog page somehow missed it — the code the rule
 *  already stores, so the select opens showing the truth. */
export function templateOptionsFor(
  channel: string,
  current: string,
  byChannel: Record<string, NotificationTemplateOption[]> | null,
  t: Translator,
): { value: string; label: string }[] {
  const options = [{ value: "", label: t("notifications.rules.noTemplate") }];
  for (const option of byChannel?.[channel] ?? []) {
    options.push({
      value: option.code,
      label: option.has_published
        ? option.name
        : `${option.name} — ${t("notifications.rules.templateUnpublished")}`,
    });
  }
  if (current !== "" && !options.some((option) => option.value === current)) {
    options.push({ value: current, label: current });
  }
  return options;
}

/**
 * **BR-NOT-024 — PRINT CANNOT BE SWITCHED OFF ON A CUSTOMER DOCUMENT.**
 *
 * PO ruling 2026-08-29, answering what happens when a utility switches an event
 * off completely: *"this is correct - don't switch of print for any document it
 * is awayls on"*. The four customer kinds carry the floor — `invoice`,
 * `payment`, `notice` and `plan` — and the ruling's own reason is the one that
 * matters here: **the printed disconnection letter is the legal instrument**, a
 * precondition of cutting somebody's water off, and a per-channel toggle beside
 * it could suppress a legal instrument with nothing on any screen saying so.
 *
 * ⚠ **AND THE SERVER'S FLOOR IS AT THE QUEUE, NOT AT THIS TOGGLE.** Wave A put
 * `CHANNEL_FLOOR_BY_SOURCE` on the queue path, so the print row is written
 * whatever this checkbox says — which makes an enabled-looking print toggle a
 * control whose only effect is to LOOK like one (BR-SHL-025's exact shape).
 * Drawn LOCKED WITH ITS REASON, checked, and never as a live switch.
 *
 * Only `disconnect_notice` offers a print channel row today
 * (`rule_catalog.EVENTS`), which is why this reads as "the collections page
 * shape" in CR-048 F8 — but it is keyed on the CHANNEL and not on the event, so
 * the receipt and payment-plan letters of waves B10/B11 inherit it rather than
 * needing to be remembered.
 *
 * ⚠ **THE CHANNEL IS SPELLED `pdf_print`, NOT `print`, AND THIS LANE WROTE
 * `print` FIRST.** `models.CHANNEL_PRINT = "pdf_print"` — it is the only one of
 * the four whose constant name and value differ, and the catalogue key
 * (`notifications.rules.channel.pdf_print`) says so too. A `=== "print"` test
 * is not an error anywhere: it compiles, it lints, and it simply never matches,
 * so the lock would never draw and the legal instrument would sit under an
 * enabled-looking toggle on the live screen. **The unit test did not catch it
 * either — its fixture spelled the channel `print` as well**, which is a test
 * asserting the test. What caught it was reading `models.py`. Hence the
 * constant: one spelling, in one place, checked against the backend.
 */
export const PRINT_CHANNEL = "pdf_print";

/**
 * `CR-084` — THE CHANNEL WHOSE MESSAGE IS THE DOCUMENT.
 *
 * ⚠ **A CHANNEL NAME IS SPELLED HERE ONCE, FOR `PRINT_CHANNEL`'s REASON.** The
 * paragraph above records what `print` vs `pdf_print` cost when a channel was
 * typed twice: it compiles, it lints, it never matches, and the control it
 * governs quietly never draws.
 *
 * ⚠ **AND WHY THIS IS A LIST OF ONE RATHER THAN A SERVED FIELD.** The Template
 * column asks *which wording goes out*, and for every other channel that is a
 * real question with a real picker. The customer portal publishes the DOCUMENT
 * — the bill itself — so it has no wording of its own and never will; the
 * catalogue records that as an absence (`template_classes` has no entry) and
 * the cell used to render that absence as *"No template for this channel yet"*.
 * **That sentence has a clock in it.** *Yet* promises wording that is not
 * coming, on a channel that is working correctly, which is precisely the shape
 * of refusal this whole change request exists to delete. It says what is true
 * instead.
 */
export const DOCUMENT_IS_THE_MESSAGE: readonly string[] = ["portal"];

export function documentIsTheMessage(channel: string): boolean {
  return DOCUMENT_IS_THE_MESSAGE.includes(channel);
}

/** ⚠ `printIsFloor` — the SERVER's answer (`DEF-PAY-10651`, PO 2026-10-29).
 *  The past-due reminder rides the floorless `reminder` kind, so its Print
 *  switch is a real switch (the letter is the fallback for a customer no email
 *  or consented text reaches). `false` from the server unlocks it; a server
 *  that does not say keeps the old, safe reading. */
export function printIsTheFloor(
  channel: string,
  audience: string,
  printIsFloor?: boolean | null,
): boolean {
  return channel === PRINT_CHANNEL && audience === "customer" && printIsFloor !== false;
}

export function ChannelsCard(props: {
  rule: NotificationRuleDetail;
  readOnly: boolean;
  working: boolean;
  t: Translator;
  draft: NotificationRuleDraft;
  /** null = the Templates catalog read failed or has not answered; the
   *  pickers then hold only the stored value rather than guessing a list. */
  templateOptions: Record<string, NotificationTemplateOption[]> | null;
  onChannelChange: (
    channel: string,
    patch: Partial<{ enabled: boolean; template_code: string; language_mode: string }>,
  ) => void;
  onQueueTest: (channel: string) => void;
}) {
  const { rule, t } = props;
  const editable = !props.readOnly;
  return (
    <Panel title={t("notifications.rules.card.channels")}>
      {/* CR-048 wave H — a wide table scrolls INSIDE its own box. This one
          needs about 660px and was measured 325px wider than the 336px card
          it sat in, so it ran underneath the card beside it. The layout fix
          above gives it the room; this is the belt that means a narrower
          window scrolls the TABLE and never the page body. */}
      <div className={TABLE_SCROLL}>
        <table className="data-table">
          <thead>
            <tr>
              <th>{t("notifications.rules.col.on")}</th>
              <th>{t("notifications.rules.col.channel")}</th>
              {/* ⚠ CR-048 F6 — THESE TWO COLUMNS WERE 60px WIDE, so the pickers
                inside them were too: a clerk saw `Bill re ⌄` and could not tell
                WHICH template, WHICH language or WHICH version was selected on
                a screen whose whole job is to say which. Table layout is
                `auto`, so a `min-width` on the header cell is what sizes the
                column — the same mechanism as wave C1's matrix widths — and
                `PICKER` is the other half: a `<select>` shrinks to its own
                content unless it is told to fill the column its header sized. */}
              <th className={COL_TEMPLATE}>{t("notifications.rules.col.template")}</th>
              <th className={COL_LANGUAGE}>{t("notifications.rules.col.language")}</th>
              <th aria-label={t("notifications.rules.col.actions")} />
            </tr>
          </thead>
          <tbody>
            {rule.channel_rules.map((channel: NotificationChannelRule) => {
              const edited = props.draft.channels[channel.channel] ?? {
                enabled: channel.enabled,
                template_code: channel.template_code ?? "",
                language_mode: channel.language_mode,
              };
              const floor = printIsTheFloor(channel.channel, rule.audience, rule.print_is_floor);
              return (
                <tr key={channel.channel} data-testid={`channel-row-${channel.channel}`}>
                  <td>
                    {/* DEF-286 — the CR's "one row per channel: enable toggle".
                      Disabled while no template is chosen, because the service
                      refuses that save by name ("a channel can't be enabled if
                      its variant is deactivated") and BR-SHL-025 wants the
                      refusal stated where the control is.
                      ⚠ AND LOCKED ON FOR PRINT — BR-NOT-024, see
                      `printIsTheFloor` above. */}
                    <input
                      type="checkbox"
                      checked={floor ? true : editable ? edited.enabled : channel.enabled}
                      // ⚠ **THE "no template" LOCK MUST NOT REACH A CHANNEL
                      // WHOSE MESSAGE IS THE DOCUMENT (`CR-084`).** The rule is
                      // sound for email and SMS — switching a channel on with
                      // no wording pinned would queue a message with nothing in
                      // it. The customer portal has no wording BY DESIGN, so
                      // this condition made its switch ONE-WAY: turn it off,
                      // `template_code === ""` and `!enabled` both become true,
                      // the checkbox greys out and there is no way back on. It
                      // would have been the mirror of the very defect this CR
                      // fixes — a working screen behind a dead control.
                      disabled={
                        floor ||
                        !editable ||
                        props.working ||
                        (edited.template_code === "" &&
                          !edited.enabled &&
                          !documentIsTheMessage(channel.channel))
                      }
                      title={
                        floor
                          ? t("notifications.rules.printFloor")
                          : props.readOnly
                            ? t("notifications.rules.readOnlyReason")
                            : edited.template_code === "" &&
                                !edited.enabled &&
                                !documentIsTheMessage(channel.channel)
                              ? t("notifications.rules.noTemplate")
                              : undefined
                      }
                      aria-label={t("notifications.rules.channelEnable", {
                        channel: t(`notifications.rules.channel.${channel.channel}`),
                      })}
                      data-testid={`channel-enabled-${channel.channel}`}
                      onChange={(event) =>
                        props.onChannelChange(channel.channel, { enabled: event.target.checked })
                      }
                    />
                  </td>
                  <td>
                    {t(`notifications.rules.channel.${channel.channel}`)}
                    {floor && (
                      // The lock says WHY it is locked, where the lock is
                      // (BR-SHL-025). A `title` alone is a rule only a mouse can
                      // read, and this one is the difference between a courtesy
                      // and a legal instrument.
                      <span className={MUTED} data-testid={`channel-floor-${channel.channel}`}>
                        {" "}
                        {t("notifications.rules.printFloor")}
                      </span>
                    )}
                    {!floor && !editable && !channel.enabled && (
                      <Note as="span">{t("notifications.rules.channelOff")}</Note>
                    )}
                  </td>
                  <td>
                    {documentIsTheMessage(channel.channel) ? (
                      // `CR-084` — no picker, because there is nothing to pick
                      // between. A select holding one option that cannot change
                      // is a control that can only ever refuse.
                      <span data-testid={`channel-template-${channel.channel}`}>
                        {t("notifications.rules.templateIsTheDocument")}
                      </span>
                    ) : editable ? (
                      // The CR's template picker, listing REAL classes from the
                      // Templates catalog (`GET /template-catalog`) for this
                      // channel — never an invented name.
                      <select
                        className="input"
                        value={edited.template_code}
                        aria-label={t("notifications.rules.col.template")}
                        data-testid={`channel-template-${channel.channel}`}
                        disabled={props.working}
                        onChange={(event) =>
                          props.onChannelChange(channel.channel, {
                            template_code: event.target.value,
                          })
                        }
                      >
                        {templateOptionsFor(
                          channel.channel,
                          edited.template_code,
                          props.templateOptions,
                          t,
                        ).map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span data-testid={`channel-template-${channel.channel}`}>
                        {/* A channel with no template class SAYS so — a picker
                          over nothing is a control that can only ever refuse. */}
                        {channel.template_code ?? t("notifications.rules.noTemplate")}
                      </span>
                    )}
                  </td>
                  <td>
                    {editable ? (
                      <select
                        className="input"
                        value={edited.language_mode}
                        aria-label={t("notifications.rules.col.language")}
                        data-testid={`channel-language-${channel.channel}`}
                        disabled={props.working}
                        onChange={(event) =>
                          props.onChannelChange(channel.channel, {
                            language_mode: event.target.value,
                          })
                        }
                      >
                        {LANGUAGE_MODES.map((mode) => (
                          <option key={mode} value={mode}>
                            {t(`notifications.rules.language.${mode}`)}
                          </option>
                        ))}
                      </select>
                    ) : (
                      t(`notifications.rules.language.${channel.language_mode}`)
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="settings-icon-btn"
                      title={t("notifications.rules.action.queueTest")}
                      aria-label={t("notifications.rules.action.queueTest")}
                      data-testid={`channel-test-${channel.channel}`}
                      disabled={props.readOnly || props.working || channel.template_code === null}
                      onClick={() => props.onQueueTest(channel.channel)}
                    >
                      ✉
                    </button>
                  </td>
                </tr>
              );
            })}
            {rule.unavailable_channels.map((channel) => (
              <tr key={channel.channel} data-testid={`channel-unavailable-${channel.channel}`}>
                <td />
                <td>{t(`notifications.rules.channel.${channel.channel}`)}</td>
                {/* ⚠ CR-048 F7 — ONE LINE, AND NOT IN THE DANGER TIER.
                  This was `<RefusalStrip colSpan={3}>`: the server's reason for
                  Portal is 180 characters, `RefusalStrip` paints a red
                  paragraph, and three unavailable channels made this card
                  taller than the rest of the rule page put together. The
                  information is RIGHT — BR-SHL-025 requires a forbidden control
                  to carry its reason — and the PLACE was wrong.
                  The row keeps the whole sentence: `truncate` clips what does
                  not fit and `title` carries all of it, which is the same shape
                  `RowActions` uses for every disabled row action in the
                  product, and the same shape the matrix row beside this one
                  already used for this exact fact. Nothing is hidden that was
                  not already a tooltip somewhere else on the screen. */}
                <td colSpan={3}>
                  <span
                    className={UNAVAILABLE_REASON}
                    title={channel.reason}
                    data-testid={`channel-unavailable-reason-${channel.channel}`}
                  >
                    {channel.reason}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

export function TimingCard(props: {
  rule: NotificationRuleDetail;
  readOnly: boolean;
  working: boolean;
  t: Translator;
  draft: NotificationRuleDraft;
  onChange: (change: Partial<NotificationRuleDraft>) => void;
}) {
  const { rule, t } = props;
  if (props.readOnly) {
    // The Executive read view — unchanged, with the standing reason
    // (DEF-196's split; the house select has no disabled state).
    return (
      <Panel title={t("notifications.rules.card.timing")}>
        <dl>
          <dt>{t("notifications.rules.field.trigger")}</dt>
          <dd data-testid="timing-trigger">
            {t(`notifications.rules.trigger.${rule.trigger_mode}`)}
            {rule.offset_days !== null && ` · ${String(rule.offset_days)}`}
            {rule.fixed_time !== null && ` · ${rule.fixed_time}`}
          </dd>
          <dt>{t("notifications.rules.field.quietHours")}</dt>
          <dd data-testid="timing-quietHours">
            {t(`notifications.rules.quietHours.${rule.quiet_hours_mode}`)}
          </dd>
          <dt>{t("notifications.rules.field.failurePolicy")}</dt>
          <dd data-testid="timing-failurePolicy">
            {t(`notifications.rules.failurePolicy.${rule.failure_policy}`)}
          </dd>
        </dl>
        <Note role="note">{t("notifications.rules.readOnlyReason")}</Note>
      </Panel>
    );
  }
  // DEF-286 — the trigger mode and its ARGUMENT edit as the PAIR the service
  // validates (`_refuse_incoherent_timing`): the argument field drawn is the
  // chosen mode's, and the diff builder clears the other on save, so a save
  // can never carry two instructions about when to send.
  const problem = timingProblem(props.draft);
  return (
    <Panel title={t("notifications.rules.card.timing")}>
      <div data-testid="timing-trigger">
        <SelectField
          id="rule-trigger-mode"
          label={t("notifications.rules.field.trigger")}
          value={props.draft.trigger_mode}
          onChange={(value) => props.onChange({ trigger_mode: value })}
          options={TRIGGER_MODES.map((mode) => ({
            value: mode,
            label: t(`notifications.rules.trigger.${mode}`),
          }))}
        />
      </div>
      {props.draft.trigger_mode === "offset_days" && (
        <div data-testid="timing-offsetDays">
          <TextField
            id="rule-offset-days"
            label={t("notifications.rules.field.offsetDays")}
            value={props.draft.offset_days}
            numeric
            required
            onChange={(value) => props.onChange({ offset_days: value })}
            error={problem === "offset_days" ? t("notifications.rules.offsetFormat") : undefined}
          />
        </div>
      )}
      {props.draft.trigger_mode === "fixed_time" && (
        <div data-testid="timing-fixedTime">
          <TextField
            id="rule-fixed-time"
            label={t("notifications.rules.field.fixedTime")}
            value={props.draft.fixed_time}
            required
            placeholder="09:30"
            onChange={(value) => props.onChange({ fixed_time: value })}
            error={problem === "fixed_time" ? t("notifications.rules.timeFormat") : undefined}
          />
        </div>
      )}
      <div data-testid="timing-quietHours">
        <SelectField
          id="rule-quiet-hours"
          label={t("notifications.rules.field.quietHours")}
          value={props.draft.quiet_hours_mode}
          onChange={(value) => props.onChange({ quiet_hours_mode: value })}
          options={QUIET_HOURS_MODES.map((mode) => ({
            value: mode,
            label: t(`notifications.rules.quietHours.${mode}`),
          }))}
        />
      </div>
      <div data-testid="timing-failurePolicy">
        <SelectField
          id="rule-failure-policy"
          label={t("notifications.rules.field.failurePolicy")}
          value={props.draft.failure_policy}
          onChange={(value) => props.onChange({ failure_policy: value })}
          options={FAILURE_POLICIES.map((policy) => ({
            value: policy,
            label: t(`notifications.rules.failurePolicy.${policy}`),
          }))}
        />
      </div>
    </Panel>
  );
}

/**
 * **CR-048 F5 — THE ESCALATION LADDER, READ-ONLY, NAMING WHERE IT IS CHANGED.**
 *
 * ⚠ **THIS CARD USED TO BE FIVE TEXT INPUTS AND A SECOND SAVE, AND THAT IS WHAT
 * CHANGED.** BR-NOT-017 (PO 2026-08-17, *"we bring all internal external
 * ntification rule sat one place and they are part of notification settings"*)
 * put the ladder on this page and the CR-009 lane read it as EDIT HERE. The
 * figures were always written to the EXISTING `/settings/collections` contract,
 * so there was never a second store — but there were two DOORS onto one store,
 * and CR-048 F5 closes one of them: *"read-only, carrying this utility's own
 * figures, and naming where they are changed … so the collections run and the
 * notice can never disagree about the same numbers"*.
 *
 * **Read that as narrowing BR-NOT-017 rather than reversing it.** One home for
 * the RULE is still this page — a person reading the disconnect-notice rule
 * still sees the ladder that schedules it, in the tenant's own figures, without
 * leaving. One home for the FIGURE is Settings › Collections, which is where
 * the live collections engine (`apps/payments/settings_seam.py`,
 * `apps/notifications/notices.py`) reads them from. Two editors onto one store
 * is how a notice and the run that schedules it come to disagree.
 *
 * The $25.00 floor and the 25% pause are still shown here, which is still the
 * only screen in the product that shows them at all (DEF-204, DEF-097).
 *
 * ⚠ **COLLECTIONS EVENTS ONLY, AND THE SERVER DECIDES WHICH.** `ladder` is
 * non-null exactly when `rule_catalog` marks the event `has_ladder`, and that
 * flag is per EVENT and not per category on purpose — its own comment says so:
 * *"'hi-usage alert' is a collections-category row with no ladder"*. This card
 * asks the wire, never the category string.
 */
export function LadderCard(props: { rule: NotificationRuleDetail; t: Translator }) {
  const { rule, t } = props;
  if (rule.ladder === null) return null;
  if (rule.ladder.unavailable_reason !== null) {
    // Never zeroes. "We could not read the tenant's ladder" and "this utility
    // chases from day 0" are different facts.
    return (
      <Panel title={t("notifications.rules.card.ladder")}>
        <RefusalStrip role="note" className={REASON_CLAMP} data-testid="ladder-unavailable">
          {rule.ladder.unavailable_reason}
        </RefusalStrip>
      </Panel>
    );
  }
  const ladder = rule.ladder;
  // The unit keys are the SETTINGS catalogue's own — the same strings the
  // collections rule page prints beside these figures, so a utility reads
  // "days" and "hours" in exactly the words it always did.
  const rows: { testid: string; labelKey: string; value: string; unitKey: string | null }[] = [
    {
      testid: "ladder-reminder",
      labelKey: "notifications.rules.ladder.reminder_days_after_due",
      value: ladder.reminder_days_after_due === null ? "" : String(ladder.reminder_days_after_due),
      unitKey: "settings.rules.unit.days",
    },
    {
      testid: "ladder-tiers",
      labelKey: "notifications.rules.ladder.notice_tier_days",
      value: ladder.notice_tier_days.join(", "),
      unitKey: "settings.rules.unit.days",
    },
    {
      testid: "ladder-final",
      labelKey: "notifications.rules.ladder.final_notice_hours",
      value: ladder.final_notice_hours === null ? "" : String(ladder.final_notice_hours),
      unitKey: "settings.rules.unit.hours",
    },
    // ⚠ MONEY. The server's canonical decimal STRING, rendered as it arrived
    // and never parsed into a number on this path (CLAUDE.md rule 2).
    {
      testid: "ladder-floor",
      labelKey: "notifications.rules.ladder.ladder_balance_floor_amount",
      value: ladder.balance_floor_amount ?? "",
      unitKey: null,
    },
    {
      testid: "ladder-pause",
      labelKey: "notifications.rules.ladder.partial_payment_pause_percent",
      value: ladder.partial_payment_pause_percent ?? "",
      unitKey: "settings.rules.unit.percent",
    },
  ];
  return (
    <Panel
      title={t("notifications.rules.card.ladder")}
      // WHERE THEY ARE CHANGED, in words, on the card. Not a disabled input a
      // person clicks three times before giving up (BR-SHL-025's spirit): the
      // control is not here at all, so the card has to say where it is.
      hint={t("notifications.rules.ladderChangedIn")}
    >
      <ul className={KV_LIST} data-testid="ladder-figures">
        {rows.map((row) => (
          <li key={row.testid} className={KV_ROW}>
            <span className={KV_KEY}>
              {t(row.labelKey)}
              {row.unitKey !== null && <> ({t(row.unitKey)})</>}
            </span>
            {/* ⚠ `KV_SENTENCE`, NOT `KV_FIGURE`, for a reason wave C1 measured:
                `notice_tier_days` is a LIST — "10, 5" today and "14, 10, 5, 2"
                for a utility with four tiers — and a value that can neither wrap
                nor shrink is what put a sentence across the card beside it. */}
            <span className={KV_SENTENCE} data-testid={row.testid}>
              {row.value === "" ? (
                <span className={MUTED}>{t("notifications.rules.ladderUnset")}</span>
              ) : (
                row.value
              )}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/**
 * **CR-048 F4 — THE RIGHT RAIL: what makes this page checkable.**
 *
 * Three things, and the second and third are the ones the wire cannot fill yet.
 * Both render NOTHING rather than a zero or a blank name — DEF-127's lesson,
 * *"a figure nobody counted rendering as a figure somebody counted"*.
 *
 *  1. **The rule as a plain-English sentence**, rebuilt from catalogue keys as
 *     the settings change, so it translates like everything else here.
 *  2. **The last thirty days of delivery.** `delivery_counts_available` is
 *     `false` on every deployment and `NotificationReleasePosture` carries the
 *     server's own reason for it: `delivered` needs a provider confirmation and
 *     `bounced` needs an ESP webhook, and no adapter exists on any channel
 *     (BR-NOT-013). **CR-048 wave B6 is the task that fills this and it has not
 *     landed** — no `last_30_days_*` field exists on
 *     `rule_service.RuleView.as_wire()` — so the rail prints the reason. When
 *     B6 lands, this is where its numbers go.
 *  3. **Who changed it last.** `NotificationRule` HAS `updated_at` and the save
 *     path writes a full before→after audit row (`audit.money_action`,
 *     `notification_rule.update`), and **neither reaches the wire**: `as_wire`
 *     carries no timestamp and no actor. So this rail says where the record IS
 *     rather than inventing a name for it. Serving the last audit row on the
 *     rule detail is the backend half; it is not this lane's to write.
 */
export function RuleRail(props: { rule: NotificationRuleDetail; t: Translator }) {
  const { rule, t } = props;
  return (
    <Panel title={t("notifications.rules.card.rail")}>
      <p data-testid="rail-plain-english">{plainEnglishRule(rule, t)}</p>
      <h4>{t("notifications.rules.rail.last30")}</h4>
      {/* BR-NOT-013 — NOT REPORTED, never 0. "0 delivered of 142 sent" reads as
          a delivery failure when the truth is that nobody is reporting. */}
      {/* DEF-NOT-10537 — a catalogue key, in all eleven languages; the
          server's English sentence read *"because sending is not switched on"*. */}
      <RefusalStrip role="note" className={REASON_CLAMP} data-testid="rail-delivery-unreported">
        {t("notifications.rules.rail.deliveryUnreported")}
      </RefusalStrip>
      <h4>{t("notifications.rules.rail.lastChanged")}</h4>
      <Note data-testid="rail-last-changed">{t("notifications.rules.rail.auditNote")}</Note>
    </Panel>
  );
}

/**
 * CR-048 wave I — THE ONE SEND-TIME ELECTION THAT IS ACTUALLY WIRED, and the
 * home it moved to when the card holding it was deleted.
 *
 * *"Four switches. Three of them do nothing and say so in their own text. We
 * built the switches ahead of the features. Only the receipt one is live, and
 * that's better expressed as an ordinary rule in the table above it."* — the
 * Product Owner, 2026-08-30, reading the deployed Notifications screen.
 *
 * ⚠ **THE SWITCH IS MOVED, NOT DROPPED, AND THAT IS THE WHOLE POINT OF THE
 * TYPE.** `receipt_on_record_payment` is a per-tenant column that
 * `apps/payments/receipts.py` reads on every recorded payment: turning it off
 * is the difference between a customer getting a receipt and not. Deleting the
 * card that held it without rehoming the switch would leave a live setting
 * with no screen, which is the shape mandate 5 exists to forbid.
 *
 * ⚠ **AND IT IS A DIFFERENT STORE FROM THE RULE ON THIS PAGE, WHICH IS WHY IT
 * SAVES ON ITS OWN CLICK.** The rule is `notification_rules`, written by
 * `update_rule`; the election is `notification_settings`, written by the
 * settings endpoint. Folding it into this page's Save button would report one
 * transaction where there are two, and a partial failure would then be a lie
 * about what was saved. The genuinely durable fix is a SERVER change — one
 * `payment_received` rule owning both — and that is named in this lane's report
 * rather than guessed at here.
 */
export interface ReceiptElection {
  /** `null` while the settings read is in flight or was refused. A switch
   *  drawn over an unknown state is a switch that lies about what is on. */
  on: boolean | null;
  readOnly: boolean;
  working: boolean;
  onToggle: (next: boolean) => void;
}

/** The event whose page carries the receipt election. It is `payment_received`
 *  because that IS the event the election governs — a receipt goes out when a
 *  payment is recorded — so the setting sits with the rule a person came here
 *  to read, one click from the matrix row of the same name. */
export const RECEIPT_ELECTION_EVENT = "payment_received";

function ReceiptElectionCard(props: { election: ReceiptElection; t: Translator }) {
  const { election, t } = props;
  return (
    /* ⚠ The testid rides a WRAPPER, not `Panel`. `Panel` names four props and
       drops anything else, which is a hook that silently is not there — the
       same trap `RowActions` records for `data-testid` vs `testId`. */
    <div data-testid="receipt-election">
      <Panel title={t("notifications.receipt.title")} hint={t("notifications.receipt.hint")}>
        {election.on === null ? (
          <p className={MUTED} data-testid="receipt-election-unknown">
            {t("notifications.receipt.unknown")}
          </p>
        ) : (
          <div className={ACTIONS}>
            <span data-testid="receipt-election-state">
              {t(election.on ? "notifications.dispatch.on" : "notifications.dispatch.off")}
            </span>
            <Button
              variant="secondary"
              disabled={election.readOnly || election.working}
              title={election.readOnly ? t("notifications.dispatch.adminOnly") : undefined}
              data-testid="receipt-election-toggle"
              onClick={() => {
                election.onToggle(!election.on);
              }}
            >
              {t(election.on ? "notifications.elections.turnOff" : "notifications.elections.turnOn")}
            </Button>
          </div>
        )}
      </Panel>
    </div>
  );
}

export function RuleDetailPage(props: {
  eventKey: string;
  readOnly: boolean;
  client: ApiClient;
  onBack: () => void;
  /** CR-048 wave I — required, never optional: an optional prop nothing passes
   *  is the dead-UI shape G13 exists for (hard-won law 2), and this one is a
   *  live money-adjacent switch that must not quietly stop rendering. */
  receipt: ReceiptElection;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [test, setTest] = useState<NotificationTestResult | null>(null);
  // DEF-286 — the editors' draft. Seeded from the server's rule; null until
  // the read answers, so no editor ever renders over invented values.
  const [draft, setDraft] = useState<NotificationRuleDraft | null>(null);

  const rule = useQuery({
    queryKey: ["notification-rule", props.eventKey],
    queryFn: () => getNotificationRule(props.eventKey, props.client),
    staleTime: REFERENCE_STALE_MS,
  });
  // ⚠ CR-048 F5 — THE SECOND READ OF `/settings/collections` IS GONE WITH THE
  // EDITOR IT FED. The five figures are already on `rule.ladder`
  // (`RuleView.as_wire(include_ladder=True)` reads the same settings family),
  // so the page fetched the same document twice to fill inputs that no longer
  // exist. One read, one store, no editor.
  // The pickers' vocabularies — both reads fail SOFT: a failed catalog read
  // degrades the template picker to the stored value (never a guessed list),
  // and a failed services read leaves the scope select holding `all` plus the
  // stored code. `retry: false` — each answers a settings question, and a
  // silently retried failure is a picker that takes four times as long to say
  // it could not load (the SettingsNotificationsTab idiom).
  const templates = useQuery({
    queryKey: ["notification-rule-template-options"],
    queryFn: () => getTemplateOptionsByChannel(props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
    enabled: !props.readOnly,
  });
  const services = useQuery({
    queryKey: ["notification-rule-service-options"],
    queryFn: () => getTenantServices(props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
    enabled: !props.readOnly && rule.data?.audience === "customer",
  });

  useEffect(() => {
    if (rule.data !== undefined) setDraft(draftOf(rule.data));
  }, [rule.data]);

  const saveRule = useMutation({
    mutationFn: (patch: NotificationRulePatch) =>
      updateNotificationRule(props.eventKey, patch, props.client),
    onSuccess: () => {
      setRefusal(null);
      toast(t("notifications.rules.saved"));
      void queryClient.invalidateQueries({ queryKey: ["notification-rules"] });
      void queryClient.invalidateQueries({ queryKey: ["notification-rule", props.eventKey] });
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  const queueTest = useMutation({
    mutationFn: (channel: string) => queueNotificationTest(props.eventKey, channel, props.client),
    onSuccess: (result) => {
      setRefusal(null);
      setTest(result);
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  if (rule.isPending) return <LoadingSkeleton variant="card" />;
  if (rule.error !== null || rule.data === undefined) {
    return (
      <FailedWithRetry
        title={t("notifications.rules.failedTitle")}
        reason={apiErrorText(rule.error, t)}
        onRetry={() => {
          void rule.refetch();
        }}
        onDownloadReport={() => undefined}
        onCancel={props.onBack}
      />
    );
  }
  const detail = rule.data;
  const working = saveRule.isPending || queueTest.isPending;
  const activeDraft = draft ?? draftOf(detail);
  const draftProblem = timingProblem(activeDraft);
  // The PARTIAL change set — `update_rule`'s own contract, "pass only what is
  // changing". null = nothing moved.
  const patch = draftProblem === null ? ruleSavePatch(detail, activeDraft) : null;
  // An empty save is refused by the SERVICE with a good sentence; the button
  // says so up front instead of collecting the refusal after a round trip.
  // ⚠ CR-048 F5 — `&& !detail.has_ladder` is GONE with the ladder editor. It
  // was there because the ladder rode this same button over its own store, so a
  // laddered event always had something to save even when the rule had not
  // moved. A read-only ladder has nothing to save, so an untouched disconnect
  // -notice page is now correctly refused like every other untouched page.
  const nothingToSave = patch === null;
  const saveBlocked = props.readOnly || working || draftProblem !== null || nothingToSave;

  return (
    <SettingsFrame
      onBack={props.onBack}
      backLabel={t("notifications.rules.back")}
      kicker={t(`notifications.rules.category.${detail.category}`)}
      title={t(`notifications.rules.event.${detail.key}`)}
      description={plainEnglishRule(detail, t)}
      actions={
        <Button
          variant="primary"
          data-testid="rule-save"
          disabled={saveBlocked}
          title={
            props.readOnly
              ? t("notifications.rules.readOnlyReason")
              : nothingToSave
                ? t("notifications.rules.nothingToSave")
                : undefined
          }
          onClick={() => {
            // DEF-286 — Save is ONE call to update_rule's endpoint (rule
            // fields + channel rows, one transaction server-side); the ladder
            // rides the same click over its own EXISTING contract
            // (`/settings/collections`, BR-NOT-017's one-store ruling). After
            // a successful RULE save the page returns to the matrix — the
            // requirement's own words.
            void (async () => {
              try {
                if (patch !== null) {
                  await saveRule.mutateAsync(patch);
                  props.onBack();
                }
              } catch {
                // The refusal is already on screen via the mutation's onError;
                // the page stays put so nothing typed is lost.
              }
            })();
          }}
        >
          {t("notifications.rules.save")}
        </Button>
      }
    >
      <RefusalNotice refusal={refusal} />
      {detail.trigger_blocked_by !== null && (
        <RefusalStrip
          role="note"
          data-testid="detail-noTrigger"
          // CR-016: the id stays reachable for support, off the sentence.
          data-blocked-by={detail.trigger_blocked_by}
        >
          {t("notifications.rules.noTrigger")}
        </RefusalStrip>
      )}
      {test !== null && (
        // BOTH halves. "Queued" alone reads, to the person who just clicked, as
        // "a test email is on its way" (BR-NOT-013).
        <Note role="status" data-testid="test-result">
          {test.queued ? testResultSentence(test, t) : (test.unavailable_reason ?? "")}
        </Note>
      )}
      {/* CR-048 F4 — A REAL RAIL. These five cards were all children of
          `.settings-grid` (`repeat(auto-fit, minmax(320px, 1fr))`), so the rail
          took whichever track was free and the page had no rail at all: on a
          wide screen it landed second in row two, between the timing card and
          the ladder. A rail is a COLUMN. */}
      {/* ⚠ CR-048 wave H — AND THE BODY COLUMN WAS STILL A CARD GRID INSIDE
          THE RAIL, which is why F4's rail did not finish the job. Measured at
          1728×1080: this `PanelGrid` resolved to `336px 336px 336px`, so the
          four rule cards tiled three-across inside the 1056px body column and
          the "Channels & templates" table — which needs about 660px — was
          **325px wider than the 336px section holding it** and ran underneath
          the card beside it. A rail is a column, and so is the body: cards
          stack down it and each one gets the whole width. */}
      <div className={RULE_LAYOUT}>
        <div className={CARD_COLUMN}>
          <AudienceCard
            rule={detail}
            readOnly={props.readOnly}
            t={t}
            draft={activeDraft}
            serviceRows={services.data ?? null}
            onChange={(change) => setDraft({ ...activeDraft, ...change })}
          />
          <ChannelsCard
            rule={detail}
            readOnly={props.readOnly}
            working={working}
            t={t}
            draft={activeDraft}
            templateOptions={templates.data ?? null}
            onChannelChange={(channel, channelPatch) =>
              setDraft({
                ...activeDraft,
                channels: {
                  ...activeDraft.channels,
                  [channel]: {
                    ...(activeDraft.channels[channel] ?? {
                      enabled: false,
                      template_code: "",
                      language_mode: "auto",
                    }),
                    ...channelPatch,
                  },
                },
              })
            }
            onQueueTest={(channel) => queueTest.mutate(channel)}
          />
          <TimingCard
            rule={detail}
            readOnly={props.readOnly}
            working={working}
            t={t}
            draft={activeDraft}
            onChange={(change) => setDraft({ ...activeDraft, ...change })}
          />
          <LadderCard rule={detail} t={t} />
          {/* CR-048 wave I — the receipt election's new home. Rendered ONLY on
              the event it governs, because a send-time election on an event it
              does not affect is a switch that does nothing, which is what the
              PO deleted the old card for. */}
          {detail.key === RECEIPT_ELECTION_EVENT && (
            <ReceiptElectionCard election={props.receipt} t={t} />
          )}
        </div>
        <div className={RULE_COLUMN} data-testid="rule-rail">
          <RuleRail rule={detail} t={t} />
        </div>
      </div>
    </SettingsFrame>
  );
}

/**
 * The SET-12 half, mounted inside the S8 Notifications tab. `sub` is the URL's
 * own state (`/settings/notifications/:sub`), so a rule page is linkable and
 * the browser Back button works — the same shape every other Settings sub-view
 * in this product uses.
 */
export function NotificationRulesSection(props: {
  readOnly: boolean;
  client: ApiClient;
  sub: string | undefined;
  onOpen: (eventKey: string | null) => void;
  /** CR-048 wave I — the live send-time election, passed down to the event
   *  page that owns it. Required for the reason `RuleDetailPage` states. */
  receipt: ReceiptElection;
}) {
  const { t } = useTranslation();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const matrix = useQuery({
    queryKey: ["notification-rules"],
    queryFn: () => getNotificationRules(props.client),
    staleTime: REFERENCE_STALE_MS,
  });

  const toggle = useMutation({
    mutationFn: (input: { key: string; next: boolean }) =>
      updateNotificationRule(input.key, { enabled: input.next }, props.client),
    onSuccess: () => {
      setRefusal(null);
      toast(t("notifications.rules.saved"));
      void queryClient.invalidateQueries({ queryKey: ["notification-rules"] });
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  if (props.sub !== undefined && props.sub !== "") {
    return (
      <RuleDetailPage
        eventKey={props.sub}
        readOnly={props.readOnly}
        client={props.client}
        onBack={() => props.onOpen(null)}
        receipt={props.receipt}
      />
    );
  }

  if (matrix.isPending) return <LoadingSkeleton variant="table" />;
  if (matrix.error !== null || matrix.data === undefined) {
    return (
      <FailedWithRetry
        title={t("notifications.rules.failedTitle")}
        reason={apiErrorText(matrix.error, t)}
        onRetry={() => {
          void matrix.refetch();
        }}
        onDownloadReport={() => undefined}
        onCancel={() => {
          void matrix.refetch();
        }}
      />
    );
  }

  return (
    <>
      <RefusalNotice refusal={refusal} />
      <RuleMatrix
        matrix={matrix.data}
        readOnly={props.readOnly}
        working={toggle.isPending}
        t={t}
        onOpen={(key) => props.onOpen(key)}
        onToggle={(key, next) => toggle.mutate({ key, next })}
      />
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-NOT-017@cr009a17 (12-governance/11-change-requests.md → CR-009 in full including the three PO ruling sets of 2026-08-17 · 04-docs/02-decisions/14-ui-conventions.md (B14 rules 2/5/6/15/18/20) · apps/notifications/rule_catalog.py and rules_api.py, whose wire shape this consumes)
// generated: 2026-08-17 by story-coder (CR-009 SET-12/SET-12D lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest (NotificationRules.test.tsx) · every assertion was shown RED first against a stub that returned an empty matrix
// exceptions: (1) NO SEND CONTROL ANYWHERE. The ✉ action calls `queueNotificationTest` → `POST …/queue-test`, and the result states BOTH halves (queued, and will not be delivered). BR-NOT-005 stands.
//         (2) [CLOSED 2026-08-22 — DEF-286, the W13 lane] THE CARDS ARE EDITORS NOW. Every field in `EDITABLE_RULE_FIELDS` and `EDITABLE_CHANNEL_FIELDS` has a control for a System Admin (audience scope/service/class/skip, per-channel enable + template picker from the REAL catalog + language mode, trigger mode with its argument as a pair, quiet hours, failure policy); an Executive keeps the read view with the standing reason. Save posts the PARTIAL diff in ONE `PUT /notification-rules/{event}` and returns to the matrix. The old text here claimed the deferral was "named in surface_debt.txt" and it was NOT — that false claim is DEF-287, struck with the deferral it lied about. What is still deliberately absent: a template VARIANT picker (the wire stores a CLASS code and `update_rule` accepts nothing variant-shaped — OQ-332, decision log 2026-08-22) and any per-rule `enabled` control here beyond the matrix's own On toggle.
//         (3) NO STAFF RECIPIENT PICKER — BR-NOT-021 (OQ-261 closed): the ruled policy is STATED and no editor renders on a staff audience card, because `_validated` refuses a customer_scope on a staff rule and a recipient picker would be a second answer beside the ruled one.
//         (4) NO "LAST 30 DAYS" NUMBERS — BR-NOT-013; the rail prints the server's own reason instead of three zeroes.
//         (5) [SUPERSEDED 2026-08-30 by CR-048 F1 — HALF OF IT] It read "NO EXPORT AND NO SORTING on the matrix … the row order IS the rule (the PO's own grouping), not a preference". SORTING IS BUILT. The CR asks for one flat table with a short stable code and category as columns, "so it sorts, filters and pages like every other list", which is the PO overruling that reading: the grouping was a way of making a five-heading list readable, and a category COLUMN does the same job while a person can also sort by code, audience or on/off. NO EXPORT still stands — `notification_rules` is still not a registered IS-9 resource and a button here would post to a registry that cannot serve it.
//         (6) [CR-048 F1, 2026-08-30] SEARCH, SORT, FILTER AND PAGING ARE APPLIED CLIENT-SIDE, which departs from IS-2's server-side rule and is stated rather than hidden. `GET /notification-rules` serves a PLATFORM CONSTANT — the whole catalogue in one response, fifteen rows today and thirty-one after waves B10/B11 — with no `q`, `sort`, `page` or `f.` parameters to send it. `applyRuleTableState` is a pure function with its own tests, and `totalRows` is the FILTERED count so the pager cannot say "1 of 3" over a one-row view.
//         (7) [CR-048 F1, 2026-08-30] THE `NTF-01…NTF-15` CODES ARE A DISPLAY CONVENTION AND THE SERVER SERVES NONE. Checked before inventing: `rule_catalog.EventClass.as_wire()` carries no code and `EVENT_KEYS` is a snake_case name. The map is keyed by EVENT KEY and not by row position, so waves B10/B11 renumber nothing; an event with no entry renders an EMPTY code cell rather than an invented number.
//         (8) [CR-048 F5, 2026-08-30 — A CHANGE TO WHAT BR-NOT-017 BUILT, NOT A TIDY-UP] THE ESCALATION LADDER IS READ-ONLY HERE NOW, and the second `GET|PUT /settings/collections` round trip is gone with the editors. BR-NOT-017 (PO 2026-08-17, "we bring all internal external ntification rule sat one place") put the ladder on this page and the CR-009 lane read that as EDIT HERE; CR-048 F5 says "read-only … naming where they are changed … so the collections run and the notice can never disagree about the same numbers". Read as NARROWING it: one home for the RULE is still this page, one home for the FIGURE is Settings › Collections. ⚠ THE BUSINESS-RULE ROW FOR BR-NOT-017 STILL DESCRIBES THE EDITOR and this lane does not own `04-docs/05-modules/10-notifications/02-business-rules.md` — it needs the same amendment, dated, and the merge lane is asked for it in the lane report (hard-won law 10).
//         (9) [CR-048 F4, 2026-08-30] THE RAIL'S SECOND AND THIRD HALVES ARE STILL UNFILLABLE AND BOTH RENDER A SENTENCE, NEVER A ZERO OR A BLANK NAME. "Thirty days of delivery" needs CR-048 wave B6, which has not landed — there is no `last_30_days_*` field of any kind on `rule_service.RuleView.as_wire()`. "Who changed it last" needs a backend half nobody has written: `NotificationRule` HAS `updated_at` and `update_rule` writes a full before→after `audit.money_action` row, and NEITHER reaches the wire. DEF-127's lesson — a figure nobody counted must not render as a figure somebody counted.
//         (10) [CR-048 F8 / BR-NOT-024, 2026-08-30] THE PRINT CHANNEL IS DRAWN LOCKED ON WITH ITS REASON, keyed on the CHANNEL and the customer audience rather than on `disconnect_notice`, so the receipt and payment-plan letters of waves B10/B11 inherit it. The server's floor is at the QUEUE (`CHANNEL_FLOOR_BY_SOURCE`, wave A), so a live-looking toggle here is a control whose only effect is to look like one — which is exactly BR-SHL-025's shape.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
