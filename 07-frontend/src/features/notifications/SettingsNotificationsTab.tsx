// ── Trace ──────────────────────────────────────────────
// Story:    US-NOT-013 (the platform delivery dashboard + re-queue — the
//           dispatch home, drawn)   Screens: S8 (Settings → Notifications)
// Rules:    BR-TEN-041 #8 (Settings → Notifications IS the delivery/dispatch
//           home) · BR-NOT-005 (the platform-wide queue; the dispatcher is the
//           only sender, and a re-queue never bypasses batching) ·
//           BR-SHL-011 (list grammar) · BR-SHL-020 (plain-language failure) ·
//           BR-SHL-025 (a forbidden control renders disabled WITH its reason) ·
//           BR-PAY-018 (a held row releases only on address verification) ·
//           BR-BIL-036 (an account with NO email address is normal — the
//           absence is STATED, never a blank cell)
// ───────────────────────────────────────────────────────
// S8 → Notifications: WHAT THIS UTILITY HAS SENT, AND WHAT IS STUCK.
//
// DEF-128: `apps/notifications` held 7,084 lines of tested engine behind an
// `api.py` of 72 bytes that no URLconf named, and this tab rendered
// *"arrives with the delivery-queue story"*. So a clerk could not see whether
// last night's bills had gone out, could not re-queue the six that failed, and
// could not tell an unresolved address from an absent one. The routes landed on
// 2026-08-16 (A11 Addendum r4) and this screen is their first caller — built is
// not wired, closed on both sides in one commit (hard-won law 2).
//
// ── THE TWO THINGS THIS SCREEN REFUSES TO SAY ─────────────────────────────
//  1. **It never prints "0 delivered".** `delivered` and `bounced` are PROVIDER
//     facts and no provider adapter exists on any channel — delivery is out of
//     this release by PO ruling (2026-08-15). The server carries them on
//     `unpopulated_statuses` and this screen renders NOT REPORTED, because "0
//     delivered of 142 sent" reads as a delivery failure when the truth is that
//     nobody is reporting. Same discipline as `apps/billing/release.py`'s
//     mandate coverage: *"'0 of 1,122 hold an address' and 'we could not count'
//     must never render the same."*
//  2. **It never shows a blank where an address is missing.** BR-BIL-036 makes
//     a missing email NORMAL; the row states WHY it has none, and
//     `recipient_not_resolvable` ("nobody looked") is rendered differently from
//     `no_email_address` ("this account holds none") because they are different
//     facts about a customer.
//
// ── WHAT IS DELIBERATELY NOT DRAWN, said where a clerk would look for it ───
//  · **No CSV download.** The S8 capability row's export rides the platform
//    `POST /api/exports` (IS-9) and `outbound` is not a registered exportable
//    resource — so a button here would post to a registry that cannot serve it.
//  · **No re-send control on this tab.** `POST /outbound/{id}/resend` exists and
//    requires the clerk to state WHICH copy (rule 6); its home is S35's payment
//    /account surface (US-NOT-011 §5), and putting a second door on a settings
//    dashboard would be two places to get a certified letter posted twice.
//  · **No mark-returned control here either** — US-NOT-014 TC-1 puts it on the
//    S30/S35 delivery rows, where the clerk is holding the envelope.
//  · ⚠ **THIS BULLET USED TO SAY THERE WAS NO DISPATCH CONFIG. IT WAS WRONG FOR
//    A DAY AND IS DEF-228.** It read *"batch size, quiet hours, the two
//    channel flags … US-NOT-004 and its endpoints are not mounted"* while this
//    same file imported `getNotificationSettings` and rendered
//    `DispatchConfigPanel` twenty lines below. `GET|PATCH
//    /notification-settings` mounted on 2026-08-16. Corrected 2026-08-17 by the
//    CR-009 lane — hard-won law 1: a comment claiming a gap is not the gap, and
//    no gate compares an exception sentence against the code beside it.
//    ⚠ **AND IT IS IN TWO CARDS SINCE 2026-08-30 (CR-048 F2).** The dispatch
//    config split along the line between two questions a clerk asks: *can
//    anything leave the building?* — the two go-live switches, print's locked
//    row, the release posture and a per-channel waiting count, now a STRIP
//    across the top of the list where that question is asked — and *how fast,
//    and when?*, which is the batch size and the send window, now called
//    PACING. Nothing was deleted. The defect was that the go-live switches sat
//    beside a matrix of fifteen per-event channel toggles and read as a second
//    copy of them.
//  · **No per-event RULE EDITING beyond the On toggle and the escalation
//    ladder** (CR-009). The audience, channel and timing pickers are the
//    honest remainder: the backend accepts every one of them and is tested
//    doing so — see `NotificationRules.tsx`'s own exception (2).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import type { ApiClient } from "@/api/client";
import {
  getNotificationSender,
  getNotificationSettings,
  getOutbound,
  getOutboundSelection,
  getOutboundSummary,
  requeueOutbound,
  requeueOutboundBulk,
  updateNotificationSettings,
} from "@/api/endpoints";
import type {
  ChannelLine,
  ChannelLineState,
  NotificationSender,
  NotificationSettings,
  NotificationSettingsPatch,
  OutboundRow,
  OutboundSummary,
  OutboundVocabulary,
} from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { Button, ButtonLink } from "@/components/Button";
import { DocumentIcon, EyeIcon, FetchIcon, InfoIcon, PencilIcon } from "@/components/icons";
import { ListPager } from "@/components/ListPager";
import { RowAction, RowActions, RowActionsMore, RowMenuAction } from "@/components/RowActions";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { RefusalStrip } from "@/components/Surfaces";
import { useTenantPath } from "@/routing/tenantPath";

import {
  DEFAULT_QUEUE_VIEW,
  MessageErrorPanel,
  QueueSelectionBar,
  QueueViewSwitch,
  RetryToDialog,
  canRetryTo,
  canSelect,
  requeueOutcomeText,
  viewFilters,
} from "./AttentionQueue";
import type { QueueView } from "./AttentionQueue";
import { BLOCKED_SCREEN_ID, BLOCKED_SUB, BlockedAddressesTab } from "./BlockedAddresses";
import { NotificationRulesSection, PRINT_CHANNEL } from "./NotificationRules";
import type { ReceiptElection } from "./NotificationRules";
import {
  ACTIONS,
  CARD_COLUMN,
  KV_FIGURE,
  KV_KEY,
  KV_LIST,
  KV_ROW,
  MUTED,
  PAGE_STACK,
  REASON_CLAMP,
  RULE_LAYOUT,
  SINGLE_CARD,
  STRIP,
  STRIP_CHANNEL,
  STRIP_FIGURE,
  STRIP_HEAD,
  STRIP_ITEM,
  STRIP_STATE,
  BREAK_ANYWHERE_CELL,
  TABLE_SCROLL,
} from "./notificationsKit";
import {
  Panel,
  RefusalNotice,
  SettingsDenied,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "../tenancy/settingsShared";
// CR-049 task 3 (PO 2026-08-30, BR-NOT-027) — "show me what we actually sent".
// ⚠ THIS IS THE WIRE, and it is the whole point of the task. The document store,
// the dispatcher's freeze and `reproduce()` all shipped on 2026-08-30 and NOTHING
// CALLED THEM: the task-2 lane closed with *"no endpoint serves a frozen document
// yet, so a screen could still re-render one and nothing I wrote would notice"*.
// A guarantee no screen reads is dead code that every test passes over — hard-won
// law 2, which this file has already recorded twice.
import { FrozenDocumentPanel } from "./FrozenDocumentPanel";
// The one-time code becomes readable in beta (decision log 2026-09-05).
// ⚠ ITS SIBLING, NEVER ITS REPLACEMENT: the panel above serves the sealed
// copy of a message we SENT and may not render; this one serves what is
// WAITING on a channel with nothing behind it. Two facts, two panels — a
// single one would be one edit away from drawing a re-render where a legal
// original belongs.
import { UnsentMessagePanel } from "./UnsentMessagePanel";
// CR-007 — the five rights clauses a disconnection notice carries (BR-NOT-015).
// Its own file because it is the only card on this tab that edits the WORDS a
// customer reads, and because it fails alone: a tenant whose rights footer
// cannot be read must still be able to see the queue.
import type { Refusal, Translator } from "../tenancy/settingsShared";

/**
 * The page size the queue OPENS on — the shared ladder's first rung, and the
 * only one this constant decides.
 *
 * ⚠ **IT USED TO BE THE WHOLE LIST (`DEF-NOT-5746`).** This tab asked
 * `GET /outbound` for one page of fifty and then sliced those fifty again in
 * the browser, with the footer counting the array it had been handed — so a
 * utility with four thousand queued messages read *"1–50 of 50"* and page two
 * reached nothing. `GET /outbound` has paged in the DATABASE since it was
 * written (`StandardPagination`, a real `count`, `page` and `per` honoured);
 * the screen simply never asked. The page number and the size are state now and
 * both travel on the request.
 */
export const QUEUE_PAGE: PageSize = DEFAULT_PAGE_SIZE;

/** CR-048 wave I — the `:sub` segment that means "the worklist", not "a rule".
 *
 *  Notifications has ONE URL segment below the tab and it was already spoken
 *  for by the open rule page. Rather than mint a second one — two owners of
 *  one query string is a race, not a feature — the second tab takes a
 *  RESERVED value in the same namespace. It is safe because every other
 *  value is a `rule_catalog` event key and none of them is this word; the
 *  layout suite asserts that rather than leaving it true by luck. */
export const MESSAGES_SUB = "messages";

/* ⚠ `RIGHTS_SUB` AND `SENDER_SUB` ARE GONE, 2026-10-22. Their two tabs left
   Notifications by PO ruling: the Customer rights wording moved to Configure →
   Templates, *"next to the disconnection letter it prints on"*, and the mail
   server moved to Connectors, *"We have to move everything in connector not
   any other place"* (`DEF-NOT-10534`). The old addresses redirect
   (`LEGACY_NOTIFICATIONS_SUB_PATHS` in `SettingsPage.tsx`). */

export { BLOCKED_SCREEN_ID, BLOCKED_SUB };

/** Every reserved `:sub` value — a segment that means A TAB rather than a rule.
 *
 *  ⚠ ONE LIST, read by the guard below AND by the strip, because two places
 *  that must agree about which segments are tabs are two places that
 *  eventually will not. A segment missing from here falls through to the rule
 *  page and renders an empty screen, which is precisely what
 *  `/settings/notifications/rights` did before this landed.
 *
 *  ⚠ **`BLOCKED_SUB` IS THE FIFTH (`DEF-NOT-5637`) and it is IMPORTED from the
 *  screen that owns it rather than spelled again here** — a second literal is
 *  how a strip and a guard come to disagree about one segment, which is the
 *  defect the paragraph above records. */
export const TAB_SUBS: readonly string[] = [MESSAGES_SUB, BLOCKED_SUB];

/** The three CONFIG reads' cache keys. Named here so the tab and its tests use
 *  one spelling; a second copy is how a mutation invalidates nothing. */
export const notificationSettingsKey = ["notifications", "settings"] as const;

/**
 * The counts a person can act on, in the order the dispatch home reads them.
 *
 * PURE, and exported, so the "not reported" rule is testable without a browser:
 * a status the server names in `unpopulated_statuses` comes back with
 * `reported: false` and NO number, and a screen that renders a 0 for it is
 * making a claim about delivery that nobody in this product can support.
 */
export function statusTiles(summary: OutboundSummary): {
  status: string;
  count: number | null;
  reported: boolean;
}[] {
  const unreported = new Set(summary.unpopulated_statuses);
  const seen = new Set([...Object.keys(summary.totals), ...summary.unpopulated_statuses]);
  return [...seen].sort().map((status) => ({
    status,
    count: unreported.has(status) ? null : (summary.totals[status] ?? 0),
    reported: !unreported.has(status),
  }));
}

/**
 * Whether the Re-queue control may fire for a row, and WHY NOT when it may not.
 *
 * BR-SHL-025: a forbidden control renders DISABLED carrying its reason, rather
 * than firing and being refused. The server refuses these same two cases by
 * name (`held_row_not_requeueable`, `already_sent_not_requeueable`) and stays
 * the enforcement — this is the explanation, not the guard.
 */
export function requeueBlockedReason(row: OutboundRow): string | null {
  if (row.held) return "notifications.queue.blocked.held";
  if (row.status === "sent" || row.status === "delivered") {
    return "notifications.queue.blocked.alreadySent";
  }
  return null;
}

/**
 * `DEF-BIL-10530` — the failure REASONS this platform writes as a code, in
 * words. `last_error` otherwise holds a provider's own sentence and is shown as
 * it arrived; these two are ours, so a clerk reads a fact rather than a code
 * (B14 rule 32). `template_not_resolved` is the dispatcher's (a message whose
 * wording cannot be loaded fails rather than waiting forever);
 * `stuck_wrong_template_pin_2026_10_22` is notifications 0023's, for the bill
 * emails already stuck on 2026-10-22 (PO: *"mark them failed"*).
 */
const KNOWN_FAILURE_REASONS: Readonly<Record<string, string>> = {
  template_not_resolved: "notifications.queue.error.template_not_resolved",
  stuck_wrong_template_pin_2026_10_22:
    "notifications.queue.error.stuck_wrong_template_pin_2026_10_22",
};

export function lastErrorText(lastError: string | null, t: Translator): string {
  if (lastError === null) return "";
  const key = KNOWN_FAILURE_REASONS[lastError];
  return key === undefined ? lastError : t(key);
}

/**
 * What a row's address cell says. Three outcomes and never a blank.
 *
 * BR-BIL-036 made this a rule rather than a nicety: an account with no email
 * address is NORMAL, and `recipient_not_resolvable` is not that fact — it says
 * the owning module publishes no read, so NOBODY LOOKED. Rendering both as an
 * empty cell would put "142 customers have no email address" on a dashboard
 * when the truth is that the question was never asked.
 */
export function addressCell(row: OutboundRow): { text: string | null; reasonKey: string | null } {
  // DEF-NOT-9666 — an in-app row is addressed to a staff member by USER ID; the
  // cell shows their NAME, never the id (B14 rule 31).
  if (row.channel === "in_app") {
    return row.recipient_name
      ? { text: row.recipient_name, reasonKey: null }
      : { text: null, reasonKey: "notifications.queue.address.noneOnFile" };
  }
  if (row.recipient_address !== null && row.recipient_address !== "") {
    return { text: row.recipient_address, reasonKey: null };
  }
  if (row.unavailable_reason === "recipient_not_resolvable") {
    return { text: null, reasonKey: "notifications.queue.address.notLookedUp" };
  }
  // DEF-NOT-9668 / DEF-NOT-9669 — a text with no number names which of two
  // facts about the CUSTOMER it is: no phone held, or texts never chosen.
  if (row.unavailable_reason === "no_mobile_number") {
    return { text: null, reasonKey: "notifications.queue.address.noPhone" };
  }
  if (row.unavailable_reason === "no_sms_opt_in") {
    return { text: null, reasonKey: "notifications.queue.address.textsNotChosen" };
  }
  return { text: null, reasonKey: "notifications.queue.address.noneOnFile" };
}

/**
 * US-NOT-004 — the four values the dispatcher obeys, and what the RELEASE does
 * with them.
 *
 * `apps/notifications/dispatch_config.py` shipped complete, role-gated and
 * audited on 2026-08-15 and had no route, so this card's own header read *"no
 * dispatch config — US-NOT-004 has no mounted endpoint"* for a day: nobody
 * could see or change the batch size or the send window. It is drawn now.
 *
 * ⚠ **THE TWO CHANNEL SWITCHES DO NOT SEND ANYTHING**, and the card says so
 * rather than leaving a tenant to infer it from a toggle that looks live. R2
 * has no dispatcher run and no provider integration on any channel (PO
 * 2026-08-16, *"I already confirm it before it Queue them"*), which the server
 * carries on `dispatch_runs_in_this_release` — the same posture as refusing to
 * print "0 delivered".
 */
/**
 * **CR-048 F2 — CHANNEL STATUS IS A STRIP ACROSS THE TOP, NOT A CARD OF
 * SWITCHES BESIDE A MATRIX OF SWITCHES.**
 *
 * ⚠ **THE DEFECT IS THAT THE TWO CONTROLS READ AS THE SAME CONTROL.** These
 * two switches are the GO-LIVE GATE for the whole utility: nothing on any
 * channel leaves the building until they are on. The SET-12 matrix under them
 * carries a per-event channel toggle for every one of fifteen events. Sitting
 * them in a `.settings-grid` card beside that matrix made them read as a second
 * copy of the per-event toggle, so the question a clerk actually arrives with —
 * *why is nothing sending?* — was asked at a row and answered nowhere.
 *
 * The strip answers it above the list, in a sentence and a count: *"Email — not
 * switched on. 138 messages are waiting."* The count is the queue's own
 * (`OutboundSummary.queued_by_channel`), so the sentence is checkable rather
 * than reassuring.
 *
 * ⚠ **PRINT IS ON THIS STRIP AND HAS NO SWITCH — BR-NOT-024 / BR-BIL-036.**
 * It is a channel STATUS, which is what this strip is for; it is not a channel
 * a utility may turn off, so it is drawn locked with its reason rather than
 * omitted. Omitting it would leave a clerk counting two channels on a screen
 * that queues three.
 */
/**
 * **ONE TRUE LINE PER CHANNEL** — PO 2026-10-22, verbatim: *"A. Each channel
 * tells the clerk the truth about itself, in one short line."*
 *
 * The SERVER computes the state from the channel's live switch and connector
 * (`settings_api.channel_lines`), so this screen holds no second opinion —
 * only one catalogue key per state. It replaced the card-wide *"Nothing is sent
 * in this release …"*, which was false once email sent (`DEF-NOT-10533`).
 * A fact is six words at most, plus the host (B14 rule 33).
 */
export const CHANNEL_LINE_KEYS: Readonly<Record<ChannelLineState, string>> = {
  off: "notifications.channels.line.off",
  sending: "notifications.channels.line.sending",
  notWorking: "notifications.channels.line.notWorking",
  noMailServer: "notifications.channels.line.noMailServer",
  noTextProvider: "notifications.channels.line.noTextProvider",
  waitingTextProvider: "notifications.channels.line.waitingTextProvider",
  waitingPrintVendor: "notifications.channels.line.waitingPrintVendor",
};

/** The one line for a channel, or null when the server sent none for it. */
export function channelLineText(line: ChannelLine | undefined, t: Translator): string | null {
  if (line === undefined) {
    return null;
  }
  const params = { provider: line.provider ?? "", host: line.host ?? "" };
  if (line.state === "sending" && line.host) {
    return t("notifications.channels.line.sendingHost", params);
  }
  const key = CHANNEL_LINE_KEYS[line.state];
  return key === undefined ? null : t(key, params);
}

export function ChannelStatusStrip(props: {
  settings: NotificationSettings;
  summary: OutboundSummary;
  readOnly: boolean;
  working: boolean;
  t: Translator;
  onSave: (patch: NotificationSettingsPatch) => void;
}) {
  const { settings, summary, t } = props;
  const waiting = (channel: string): number => summary.queued_by_channel[channel] ?? 0;
  const lineFor = (channel: string): ChannelLine | undefined =>
    (settings.channel_lines ?? []).find((line) => line.channel === channel);
  const channels: {
    channel: string;
    active: boolean;
    /** false = this channel has no switch (print, BR-BIL-036). */
    hasSwitch: boolean;
    turnOn: NotificationSettingsPatch;
    turnOff: NotificationSettingsPatch;
    onLabel: string;
    offLabel: string;
  }[] = [
    {
      channel: "email",
      active: settings.email_dispatch_active,
      hasSwitch: true,
      turnOn: { email_dispatch_active: true },
      turnOff: { email_dispatch_active: false },
      onLabel: "notifications.dispatch.turnEmailOn",
      offLabel: "notifications.dispatch.turnEmailOff",
    },
    {
      channel: "sms",
      active: settings.sms_dispatch_active,
      hasSwitch: true,
      turnOn: { sms_dispatch_active: true },
      turnOff: { sms_dispatch_active: false },
      onLabel: "notifications.dispatch.turnSmsOn",
      offLabel: "notifications.dispatch.turnSmsOff",
    },
    {
      // ⚠ `pdf_print` — `models.CHANNEL_PRINT`'s VALUE, which is the only one of
      // the four that differs from its constant's name. `queued_by_channel` is
      // keyed by that value and so is the catalogue
      // (`notifications.rules.channel.pdf_print`), so a `"print"` here would
      // print a raw key and count zero waiting letters, silently and forever.
      channel: PRINT_CHANNEL,
      active: settings.print_dispatch_active,
      // Print has no switch; its line says what happens to the LETTER.
      hasSwitch: false,
      turnOn: {},
      turnOff: {},
      onLabel: "",
      offLabel: "",
    },
  ];
  return (
    <Panel title={t("notifications.channels.title")} hint={t("notifications.channels.hint")}>
      <ul className={STRIP} data-testid="channel-status-strip">
        {channels.map((row) => (
          <li
            key={row.channel}
            className={STRIP_ITEM}
            data-testid={`channel-status-${row.channel}`}
          >
            <div className={STRIP_HEAD}>
              <span className={STRIP_CHANNEL}>
                {t(`notifications.rules.channel.${row.channel}`)}
              </span>
              <span className={STRIP_FIGURE} data-testid={`channel-waiting-${row.channel}`}>
                {waiting(row.channel) === 0
                  ? t("notifications.channels.waitingNone")
                  : t("notifications.channels.waiting", { count: waiting(row.channel) })}
              </span>
            </div>
            <span className={STRIP_STATE} data-testid={`channel-line-${row.channel}`}>
              {channelLineText(lineFor(row.channel), t)}
            </span>
            {row.hasSwitch && (
              <div className={ACTIONS}>
                <Button
                  variant="secondary"
                  disabled={props.readOnly || props.working}
                  title={props.readOnly ? t("notifications.dispatch.adminOnly") : undefined}
                  data-testid={`channel-switch-${row.channel}`}
                  onClick={() => props.onSave(row.active ? row.turnOff : row.turnOn)}
                >
                  {t(row.active ? row.offLabel : row.onLabel)}
                </Button>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

/**
 * **CR-048 F2 — WHAT IS LEFT OF THE DISPATCH CARD, AND IT IS CALLED PACING.**
 *
 * Batch size and the send window: HOW FAST the queue drains and WHEN, which is
 * a different question from WHETHER anything sends at all. The two channel
 * switches, print's locked row and the release posture all moved to
 * `ChannelStatusStrip` above, because they answer the second question and this
 * card answers the first. Nothing was deleted; the card was split along the
 * line the two questions fall on.
 *
 * ⚠ IT TAKES NO `readOnly`, `working` OR `onSave` ANY MORE, and that is not an
 * oversight: both figures are DISPLAYS. `US-NOT-004`'s editors for them have
 * never existed on this screen — `editable_fields` is served and nothing reads
 * it — so a prop nothing could act on would be exactly the dead wiring G13
 * exists to catch (hard-won law 2).
 */
export function DispatchConfigPanel(props: { settings: NotificationSettings; t: Translator }) {
  const { settings, t } = props;
  return (
    <Panel title={t("notifications.pacing.title")} hint={t("notifications.pacing.hint")}>
      <ul className={KV_LIST}>
        <li className={KV_ROW}>
          <span className={KV_KEY}>{t("notifications.dispatch.batchSize")}</span>
          <span className={KV_FIGURE}>{settings.dispatch_batch_size}</span>
        </li>
        <li className={KV_ROW}>
          <span className={KV_KEY}>{t("notifications.dispatch.window")}</span>
          <span className={KV_FIGURE}>
            {settings.quiet_hours_start} – {settings.quiet_hours_end}
          </span>
        </li>
      </ul>
    </Panel>
  );
}

/** The mail-server read's cache key, one spelling (the notificationSettingsKey rule). */
export const notificationSenderKey = ["notifications", "sender"] as const;

/** Connectors' own words for a connection's state (`integrations.state.*`). */
const CONNECTOR_STATE_KEYS: Readonly<Record<string, string>> = {
  not_set_up: "integrations.state.not_set_up",
  untested: "integrations.state.untested",
  working: "integrations.state.working",
  not_working: "integrations.state.not_working",
  off: "integrations.state.off",
};

/**
 * **THE MAIL SERVER, READ FROM CONNECTORS — never a form (`DEF-NOT-10534`).**
 *
 * PO 2026-10-22, verbatim: *"We have to move everything in connector not any
 * other place"*, and of this badge, *"this is correct"*. It replaced the
 * *Email sender (SMTP)* tab, whose five fields wrote columns no sender read.
 * It shows *Active: Custom SMTP (smtp.office365.com)*, the sender address and
 * the connector's state in Connectors' own words, and opens Connectors.
 * *Active* is printed only when the connector can actually send.
 */
export function MailServerPanel(props: {
  sender: NotificationSender | undefined;
  failed: boolean;
  t: Translator;
}) {
  const { sender, t } = props;
  const tenantPath = useTenantPath();
  const connection = sender?.connection ?? null;
  const providerKey =
    connection?.provider_key ?? sender?.connectors_provider_key ?? "email_smtp";
  const heading = (() => {
    if (connection === null || !connection.connected) {
      return t("notifications.mailServer.none");
    }
    const params = { provider: connection.provider_name ?? "", host: connection.host ?? "" };
    if (connection.active) {
      return connection.host
        ? t("notifications.mailServer.active", params)
        : t("notifications.mailServer.activeNoHost", params);
    }
    return connection.host
      ? t("notifications.mailServer.notActive", params)
      : t("notifications.mailServer.notActiveNoHost", params);
  })();
  const stateKey =
    connection?.status !== null && connection?.status !== undefined
      ? CONNECTOR_STATE_KEYS[connection.status]
      : undefined;
  return (
    <Panel title={t("notifications.mailServer.title")}>
      {sender === undefined && props.failed ? (
        <p className={MUTED} data-testid="mail-server-unavailable">
          {t("notifications.mailServer.unavailable")}
        </p>
      ) : (
        <div className="flex flex-col gap-3" data-testid="mail-server-status">
          <p className={STRIP_CHANNEL} data-testid="mail-server-heading">
            {heading}
          </p>
          {connection !== null && connection.connected && (
            <ul className={KV_LIST}>
              <li className={KV_ROW}>
                <span className={KV_KEY}>{t("notifications.mailServer.sender")}</span>
                <span className={KV_FIGURE} data-testid="mail-server-sender">
                  {connection.send_from ?? "—"}
                </span>
              </li>
              <li className={KV_ROW}>
                <span className={KV_KEY}>{t("notifications.mailServer.state")}</span>
                <span className={KV_FIGURE} data-testid="mail-server-state">
                  {stateKey !== undefined ? t(stateKey) : "—"}
                </span>
              </li>
            </ul>
          )}
          <div className={ACTIONS}>
            <ButtonLink
              variant="secondary"
              to={tenantPath(`/settings/integrations/${providerKey}`)}
              data-testid="mail-server-open-connectors"
            >
              {t("notifications.mailServer.open")}
            </ButtonLink>
          </div>
        </div>
      )}
    </Panel>
  );
}

function SummaryPanel(props: { summary: OutboundSummary; t: Translator }) {
  const { summary, t } = props;
  return (
    <Panel
      title={t("notifications.queue.summaryTitle")}
      hint={t("notifications.queue.summaryHint")}
    >
      <ul className={KV_LIST}>
        {statusTiles(summary).map((tile) => (
          <li key={tile.status} className={KV_ROW}>
            <span className={KV_KEY}>{t(`notifications.queue.status.${tile.status}`)}</span>
            <span className={KV_FIGURE}>
              {/* ⚠ NOT a zero. See this file's header — a provider fact nobody
                  reports is rendered as such, because a 0 beside "sent: 142"
                  reads to a clerk as 142 failed deliveries. */}
              {tile.reported ? tile.count : t("notifications.queue.notReported")}
            </span>
          </li>
        ))}
        <li className={KV_ROW}>
          <span className={KV_KEY}>{t("notifications.queue.held")}</span>
          <span className={KV_FIGURE}>{summary.held}</span>
        </li>
        <li className={KV_ROW}>
          <span className={KV_KEY}>{t("notifications.queue.returned")}</span>
          <span className={KV_FIGURE}>{summary.returned}</span>
        </li>
        <li className={KV_ROW}>
          <span className={KV_KEY}>{t("notifications.queue.retryExhausted")}</span>
          <span className={KV_FIGURE}>{summary.retry_exhausted}</span>
        </li>
      </ul>
    </Panel>
  );
}

function QueueRow(props: {
  row: OutboundRow;
  readOnly: boolean;
  working: boolean;
  t: Translator;
  /** ⚠ THE SERVER'S ANSWER, NOT A GUESS. The channels whose content may be
   *  read right now — empty for a tenant with providers connected, and it
   *  empties itself the day one is. A screen that inferred this from
   *  `status === "queued"` would offer the control on rows the server refuses,
   *  because a row can be queued on a perfectly connected channel. */
  disclosableChannels: readonly string[];
  /** DEF-NOT-10650 — the server's own re-queue / retry-to vocabulary. */
  vocabulary: OutboundVocabulary | undefined;
  selected: boolean;
  onToggle: (id: string) => void;
  onRequeue: (id: string) => void;
  onShowDocument: (id: string) => void;
  onShowUnsent: (id: string) => void;
  onShowDetails: (id: string) => void;
  onRetryTo: (id: string) => void;
}) {
  const { row, t } = props;
  // ⚠ **`readOnly` IS PART OF THE CONDITION, NOT DECORATION.** On this screen
  // read-only means an Executive (A4: Settings is View for them, and a Billing
  // Clerk is refused the door entirely), and the route behind this control is
  // `AdminOrClerk` — a one-time code is a credential, not a settings read. A
  // control that opens a 403 is the mirror of dead UI: it looks like a feature
  // and is not one.
  const mayReadContent = !props.readOnly && props.disclosableChannels.includes(row.channel);
  // ⚠ `DEF-NOT-10654` — the server's own re-queueable set, now that the list
  // serves it: a hard bounce or a complaint was offered *Try again* and always
  // refused, because `requeueBlockedReason` copies only two of the three
  // refusals. Without a served list the old two-case answer stands.
  const requeueable = props.vocabulary?.requeueable_statuses;
  const blocked =
    requeueBlockedReason(row) ??
    (requeueable !== undefined && !requeueable.includes(row.status)
      ? "notifications.queue.blocked.notRetryable"
      : null);
  const address = addressCell(row);
  // DEF-NOT-10650 (3B) — offered only where the server would take it, and
  // never to a read-only viewer (the route is AdminOrClerk).
  const mayRetryTo = !props.readOnly && canRetryTo(row, props.vocabulary);
  /* ⚠ B14 RULE 15 — ICONS, TWO VISIBLE, THE REST BEHIND *MORE* (DEF-NOT-10650).
     This row drew three TEXT buttons until the attention lane added two more
     actions; five words in a cell is the shape the rule forbids. *Try again*
     and *Error details* are the two a clerk working failures presses; the
     rest go in the menu — unless only ONE is left, because a menu of one is
     a button wearing a costume (`RowActionsMore`'s own rule). */
  const extra: { key: string; label: string; icon: ReactNode; testId?: string; onClick: () => void }[] = [];
  if (mayRetryTo) {
    extra.push({
      key: "retry-to",
      label: t("notifications.retryTo.action"),
      icon: <PencilIcon />,
      testId: "queue-retry-to",
      onClick: () => props.onRetryTo(row.id),
    });
  }
  /* ⚠ *Show what we sent* IS OFFERED ON EVERY ROW, INCLUDING ONES WITH NOTHING
     STORED — and that is deliberate. The answer *"no sealed copy was kept, so
     anything shown here would be a rebuild and not the letter"* is a real answer
     a clerk needs, and hiding the control for those rows would leave them unable
     to find out. `BR-NOT-027`'s honest half only works if it is reachable. */
  extra.push({
    key: "document",
    label: t("notifications.queue.showDocument"),
    icon: <DocumentIcon />,
    onClick: () => props.onShowDocument(row.id),
  });
  /* ⚠ *Show the message* IS **ABSENT, NOT DISABLED, WHEN A PROVIDER IS
     CONNECTED** — and that is the honest signal rather than a tidier one. A
     disabled control with a tooltip would say *this message can be read, but
     not by you*; the truth is that there is nothing to read here, because the
     message went out through somebody's mailbox. Decision log 2026-09-05. It
     is read fresh off every list response, so the day a provider is connected
     this disappears with no edit (hard-won law 2's mirror, DEF-CWP-3925). */
  if (mayReadContent) {
    extra.push({
      key: "unsent",
      label: t("notifications.unsent.open", { defaultValue: "Show the message" }),
      icon: <EyeIcon />,
      testId: "queue-show-unsent",
      onClick: () => props.onShowUnsent(row.id),
    });
  }
  return (
    <tr data-selected={props.selected ? "true" : undefined}>
      {!props.readOnly && (
        <td className="w-8">
          {canSelect(row, props.vocabulary) ? (
            <input
              type="checkbox"
              checked={props.selected}
              aria-label={t("notifications.attention.selectRow", {
                recipient: address.text ?? "",
              })}
              data-testid="queue-row-select"
              onChange={() => {
                props.onToggle(row.id);
              }}
            />
          ) : null}
        </td>
      )}
      <td>{t(`notifications.queue.source.${row.source_type}`)}</td>
      <td>{t(`notifications.queue.channel.${row.channel}`)}</td>
      <td>
        {t(`notifications.queue.status.${row.status}`)}
        {/* DEF-NOT-10665 (PO 2026-10-29, D1 A) — already sent on to a
            corrected address, so it has left Needing attention. */}
        {row.retried_to_new_address === true ? (
          <span className={`block ${MUTED}`} data-testid="queue-row-retried">
            {t("notifications.attention.retriedToNewAddress")}
          </span>
        ) : null}
      </td>
      <td className={BREAK_ANYWHERE_CELL}>
        {address.text ?? (
          <span className={MUTED}>{address.reasonKey === null ? "" : t(address.reasonKey)}</span>
        )}
      </td>
      <td>{row.attempts}</td>
      <td className={BREAK_ANYWHERE_CELL}>{lastErrorText(row.last_error, t)}</td>
      <td>
        <RowActions>
          <RowAction
            icon={<FetchIcon />}
            label={t("notifications.queue.requeue")}
            reason={
              blocked !== null
                ? t(blocked)
                : props.readOnly
                  ? t("notifications.queue.readOnly")
                  : null
            }
            working={props.working}
            onClick={() => {
              props.onRequeue(row.id);
            }}
          />
          <RowAction
            icon={<InfoIcon />}
            label={t("notifications.attention.details.open")}
            testId="queue-show-details"
            onClick={() => {
              props.onShowDetails(row.id);
            }}
          />
          {extra.length === 1 ? (
            <RowAction
              icon={extra[0].icon}
              label={extra[0].label}
              testId={extra[0].testId}
              onClick={extra[0].onClick}
            />
          ) : (
            <RowActionsMore label={t("notifications.attention.more")}>
              {extra.map((action) => (
                <RowMenuAction
                  key={action.key}
                  icon={action.icon}
                  label={action.label}
                  testId={action.testId}
                  onClick={action.onClick}
                />
              ))}
            </RowActionsMore>
          )}
        </RowActions>
      </td>
    </tr>
  );
}

/**
 * S8 → Notifications, the dashboard half of BR-TEN-041 #8.
 *
 * `readOnly` is the caller's A4 answer and is PASSED, not defaulted — the whole
 * DEF-007..010 class is a component with an optional prop nothing supplies, and
 * `SettingsPage` hands both props exactly as it does every other tab body.
 */
export function NotificationsTab(props: {
  readOnly: boolean;
  client: ApiClient;
  /** `/settings/notifications/:sub` — the event key of an open SET-12D page,
   *  or undefined for the matrix. URL state, so a rule page is linkable and
   *  the browser Back button works. */
  sub: string | undefined;
  onOpenRule: (eventKey: string | null) => void;
}) {
  const { t } = useTranslation();
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  // CR-049 task 3 — which sent message a clerk has asked to SEE. `null` = none
  // open. Local rather than URL state: it is a look at one row, not a place.
  const [documentFor, setDocumentFor] = useState<string | null>(null);
  // …and which UNSENT one, which is a different question about a different
  // state (decision log 2026-09-05). Two pieces of state rather than one
  // discriminated union: opening either must close the other, and that is one
  // line here instead of a shape both panels have to agree about.
  const [unsentFor, setUnsentFor] = useState<string | null>(null);

  const summary = useQuery({
    queryKey: queryKeys.outboundSummary,
    queryFn: () => getOutboundSummary(props.client),
    staleTime: REFERENCE_STALE_MS,
  });
  /**
   * **THE WINDOW OF THE QUEUE THIS SCREEN IS LOOKING AT (`DEF-NOT-5746`).**
   *
   * ⚠ **IT LIVES HERE AND NOT IN `QueueTable`, WHICH IS THE WHOLE FIX.** The
   * page number used to be state inside the table, where the only thing it
   * could do was slice the fifty rows the tab had already fetched. A page is a
   * REQUEST — `NFR-3` — so it has to be held by whatever makes the request.
   */
  const [queuePage, setQueuePage] = useState(1);
  const [queuePer, setQueuePer] = useState<PageSize>(QUEUE_PAGE);
  /** DEF-NOT-10650 (1A) — the screen OPENS on *Needing attention*. */
  const [queueView, setQueueView] = useState<QueueView>(DEFAULT_QUEUE_VIEW);
  /** DEF-NOT-10650 (2A) — the ticked rows, by id. Never sent empty. */
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  /** DEF-NOT-10650 (4B / 3B) — the row whose error details are open, and the
   *  row a clerk is fixing the address of. Held as the ROW, not the id, so the
   *  panel keeps what it showed while the list refetches under it. */
  const [detailsFor, setDetailsFor] = useState<OutboundRow | null>(null);
  const [retryFor, setRetryFor] = useState<OutboundRow | null>(null);
  const queue = useQuery({
    queryKey: queryKeys.outboundQueue(queuePer, queuePage, queueView),
    queryFn: () =>
      getOutbound(
        { page: queuePage, per: queuePer, filters: viewFilters(queueView) },
        props.client,
      ),
    staleTime: REFERENCE_STALE_MS,
  });
  // US-NOT-004 / 005 / 006 / 010 / 016 — the CONFIG half, added 2026-08-16.
  // `retry: false` on all three: each answers a settings question, and a
  // silently retried failure is a card that takes four times as long to say it
  // could not answer.
  const settings = useQuery({
    queryKey: notificationSettingsKey,
    queryFn: () => getNotificationSettings(props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  // CR-009 C-12 — the sender card's own read; its own failure branch, so a
  // tenant whose sender row cannot be read still sees the queue.
  const sender = useQuery({
    queryKey: notificationSenderKey,
    queryFn: () => getNotificationSender(props.client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const saveSettings = useMutation({
    mutationFn: (patch: Parameters<typeof updateNotificationSettings>[0]) =>
      updateNotificationSettings(patch, props.client),
    onSuccess: async () => {
      setRefusal(null);
      fireToast(t("notifications.dispatch.saved"));
      await queryClient.invalidateQueries({ queryKey: notificationSettingsKey });
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  const afterRequeue = async () => {
    await queryClient.invalidateQueries({ queryKey: queryKeys.outboundSummary });
    // ⚠ **THE PREFIX, NOT ONE PAGE.** A re-queue moves a row out of the
    // failures the server sorts first, so it changes the COUNT and it changes
    // which rows sit on every later page — not only the page being looked at.
    await queryClient.invalidateQueries({ queryKey: queryKeys.outboundQueueAll });
  };
  /** DEF-NOT-10650 (2A) — the bulk re-queue over the ticked rows. */
  const requeueSelected = useMutation({
    mutationFn: (messageIds: string[]) => requeueOutboundBulk(messageIds, props.client),
    onSuccess: async (outcome) => {
      setRefusal(null);
      setSelected(new Set());
      fireToast(requeueOutcomeText(outcome, t));
      await afterRequeue();
    },
    onError: (error: unknown) => {
      setRefusal(refusalOf(error, t));
    },
  });
  /** DEF-NOT-10650 (2A) — *"Select all N matching"*, resolved by the SERVER
   *  from the same filter the list used; above the cap it is refused. */
  const selectMatching = useMutation({
    mutationFn: () =>
      getOutboundSelection({ filters: viewFilters(queueView) }, props.client),
    onSuccess: (selection) => {
      setRefusal(null);
      setSelected(new Set(selection.message_ids));
    },
    onError: (error: unknown) => {
      setRefusal(refusalOf(error, t));
    },
  });

  const requeue = useMutation({
    mutationFn: (messageId: string) => requeueOutbound(messageId, props.client),
    onSuccess: async (outcome) => {
      setRefusal(null);
      // The tally the bulk action uses too (DEF-NOT-10650): it counts what
      // moved AND what refused, in the clerk's language.
      fireToast(requeueOutcomeText(outcome, t));
      await queryClient.invalidateQueries({ queryKey: queryKeys.outboundSummary });
      // ⚠ **THE PREFIX, NOT ONE PAGE.** A re-queue moves a row out of the
      // failures the server sorts first, so it changes the COUNT and it changes
      // which rows sit on every later page — not only the page being looked at.
      await queryClient.invalidateQueries({ queryKey: queryKeys.outboundQueueAll });
    },
    onError: (error: unknown) => {
      setRefusal(refusalOf(error, t));
    },
  });

  if (isPermissionDenied(summary.error) || isPermissionDenied(queue.error)) {
    return <SettingsDenied helper={t("notifications.queue.denied")} />;
  }
  if (summary.isPending || queue.isPending) {
    return <LoadingSkeleton variant="table" />; // A18 §3
  }
  if (summary.error !== null || queue.error !== null) {
    return (
      <FailedWithRetry
        title={t("notifications.queue.failedTitle")}
        reason={apiErrorText(summary.error ?? queue.error, t)}
        onRetry={() => {
          void summary.refetch();
          void queue.refetch();
        }}
        onDownloadReport={() => undefined}
        onCancel={() => {
          void summary.refetch();
          void queue.refetch();
        }}
      />
    );
  }

  /* CR-048 wave I — THE ONE LIVE SEND-TIME ELECTION, ON ITS WAY TO THE EVENT
     THAT OWNS IT.

     The *"Send-time elections"* card that used to hold four of these is gone
     (PO, 2026-08-30: *"Four switches. Three of them do nothing and say so in
     their own text. We built the switches ahead of the features."*). Three of
     the four were stored and read by nothing; their COLUMNS are untouched, so
     the features they were built ahead of still find their setting when they
     arrive — what went is the UI, not the data.

     The fourth is read on every recorded payment by `apps/payments/receipts.py`,
     so it is a live switch and dropping it would leave a setting no screen can
     reach. It moves to the `Payment received` rule page, one click from the
     matrix row of the same name. `null` while the read is in flight or refused
     — see `ReceiptElection`. */
  const receipt: ReceiptElection = {
    on: settings.data?.receipt_on_record_payment ?? null,
    readOnly: props.readOnly,
    working: saveSettings.isPending,
    onToggle: (next) => {
      saveSettings.mutate({ receipt_on_record_payment: next });
    },
  };

  // CR-009 — SET-12D is a FULL PAGE (the requirement is explicit), so when a
  // rule is open it replaces the tab body rather than nesting inside the panel
  // grid. A modal was refused by the requirement itself.
  //
  // ⚠ CR-048 wave I — `:sub` IS ONE NAMESPACE HOLDING TWO KINDS OF THING now:
  // an EVENT KEY (a rule page) and a RESERVED TAB SEGMENT. They cannot collide
  // because every event key is a `rule_catalog` code and none of the thirty is
  // `messages`, `rights` or `sender`, and `waveIDeclutter.dom.test.tsx` pins
  // that rather than leaving it to be true by luck.
  //
  // ⚠ **THE LIST IS `TAB_SUBS` AND NOT A HAND-WRITTEN CHAIN OF `!==`.** This
  // line read `props.sub !== MESSAGES_SUB` when the rights and sender tabs were
  // added, so `/settings/notifications/rights` fell through to the rule page
  // and rendered a screen with nothing on it but the Settings heading. That is
  // hard-won law 2 with the route present: the tab existed and no route reached
  // its content.
  if (props.sub !== undefined && props.sub !== "" && !TAB_SUBS.includes(props.sub)) {
    return (
      <NotificationRulesSection
        readOnly={props.readOnly}
        client={props.client}
        sub={props.sub}
        onOpen={props.onOpenRule}
        receipt={receipt}
      />
    );
  }

  const onMessages = props.sub === MESSAGES_SUB;
  const onBlocked = props.sub === BLOCKED_SUB;
  const onSettings = !onMessages && !onBlocked;
  const rows = queue.data.results;
  /**
   * ⚠ **THE SERVER'S COUNT, NEVER `rows.length` (`DEF-NOT-5746`).** `rows` is
   * ONE PAGE, so counting it printed *"1–50 of 50"* under a queue of four
   * thousand — the one figure a clerk needs in order to know whether the
   * failures in front of them are the work or the tip of it.
   */
  const queueTotal = queue.data.count;
  /**
   * The page a re-queue emptied stops existing, so the number in hand can point
   * past the end. Clamped for the NEXT request rather than in an effect: an
   * effect would fetch the empty page first and draw it.
   */
  const queuePages = Math.max(1, Math.ceil(queueTotal / queuePer));
  if (queuePage > queuePages) {
    setQueuePage(queuePages);
  }
  const vocabulary = queue.data.vocabulary;
  const selectionCap = vocabulary?.selection_cap ?? 500;
  const pageSelectable = rows.filter((row) => canSelect(row, vocabulary)).map((row) => row.id);
  return (
    /* ══ CR-048 wave H · SET-12 IS CARDS AND A RAIL, AND IT WAS NOT ════════
       Measured at 1728×1080 before wave H: `.settings-grid` resolved to
       `330px 330px 330px 330px` and every one of this tab's TEN sections was
       330px — widest : narrowest **exactly 1.00 : 1**, the arithmetic proof
       that a page drawn as "cards on the left, a rail on the right" had no
       rail at all. `RULE_LAYOUT` is REUSED from the rule page rather than a
       second constant spelled the same: SET-12 and SET-12D are one screen and
       its detail, and two grids that must agree are two grids that eventually
       will not.

       ══ CR-048 wave I · AND THE TAB HAS TWO HALVES, WHICH ARE TWO TABS ═════
       *"'Messages needing attention' gets its own tab under Notifications."*
       — PO, 2026-08-30. Everything else on this screen CONFIGURES something;
       that one block is today's work, and mixing a worklist into a settings
       page means a person who came to fix a stuck message reads six cards of
       configuration first. Its summary — *"What has gone out"* — moves with it,
       because it is the same list counted rather than a setting.

       ══ AND THREE SECTIONS ARE GONE, NOT MOVED (same ruling) ═══════════════
       *"i agree - please remove"*, of each in turn:
         · **Send-time elections** — four switches, three of which said in their
           own text that nothing read them. The live one is above.
         · **Which letter each tone sends** — *"It's a reference table about the
           collections ladder. The ladder itself is set on Settings →
           Collections and shown read-only on the rule page. This is a third
           place telling you about it."*
         · **Letters this utility can produce** — *"That's the Templates screen,
           duplicated."*
       Nothing a person can CHANGE was in any of the three except the one switch
       rehomed above; the other two were read-only restatements of screens that
       own the same facts. */
    <div className={PAGE_STACK} data-testid="notifications-layout">
      <RefusalNotice refusal={refusal} />
      {/* The second level. `settings-tabs` is a SHARED declared class, not a
          utility: Company's and Configure's strips render it, `SettingsPage.css`
          owns it, and B14 rule 21's migration clause keeps a shared class
          exactly as it is until the phase that retires it (this file's entry in
          `route-b-migrated.txt` names the eight it keeps for that reason). */}
      <div
        className="settings-tabs"
        role="tablist"
        aria-label={t("notifications.tabs.label")}
        data-testid="notifications-subtabs"
      >
        <button
          type="button"
          role="tab"
          aria-selected={onSettings}
          className={onSettings ? "active" : undefined}
          data-testid="notifications-tab-settings"
          onClick={() => props.onOpenRule(null)}
        >
          {t("notifications.tabs.rules")}
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={onMessages}
          className={onMessages ? "active" : undefined}
          data-testid="notifications-tab-messages"
          onClick={() => props.onOpenRule(MESSAGES_SUB)}
        >
          {t("notifications.queue.listTitle")}
        </button>
        {/* ⚠ THE *EMAIL SENDER (SMTP)* AND *CUSTOMER RIGHTS WORDING* TABS ARE
            GONE (PO 2026-10-22): the mail server lives on Connectors only, and
            the rights wording sits on Templates beside the disconnection
            letter it prints on. Each old address redirects. */}
        {/* ⚠ **THE DOOR — `DEF-NOT-5637`.** `GET /suppressions` and its Release
            were served with no screen behind them, so the one action the Product
            Owner asked for by name could only be performed by an engineer. This
            is where a clerk looks for it: Settings → Notifications IS the
            delivery home (`BR-TEN-041` #8), and *the addresses we must not send
            to* is a fact about delivery. Same mechanism as the three tabs above,
            never a second one. */}
        <button
          type="button"
          role="tab"
          aria-selected={onBlocked}
          className={onBlocked ? "active" : undefined}
          data-testid="notifications-tab-blocked"
          onClick={() => props.onOpenRule(BLOCKED_SUB)}
        >
          {t("notifications.blocked.title")}
        </button>
      </div>
      {onMessages ? (
        <div className={RULE_LAYOUT}>
          <div className={CARD_COLUMN} data-testid="notifications-main">
            <Panel
              title={t("notifications.queue.listTitle")}
              hint={t("notifications.queue.listHint")}
            >
              {/* ⚠ **`queueTotal`, NOT `rows.length` (`DEF-NOT-5746`).** On a
                  server-paged list an empty PAGE and an empty QUEUE are
                  different facts, and *"Nothing is waiting"* over a page that
                  merely ran off the end is a lie the clamp above would then
                  silently correct behind it. */}
              <QueueViewSwitch
                view={queueView}
                attentionCount={queue.data.attention_count}
                onView={(next) => {
                  setQueueView(next);
                  setQueuePage(1);
                  // A selection belongs to the view it was made in.
                  setSelected(new Set());
                }}
                t={t}
              />
              {!props.readOnly && (
                <QueueSelectionBar
                  selected={selected.size}
                  matching={queueTotal}
                  cap={selectionCap}
                  working={requeueSelected.isPending}
                  resolving={selectMatching.isPending}
                  onRequeue={() => {
                    // ⚠ Never an empty list — the bar does not exist at zero —
                    // and never "all": these are the ticked ids, one by one.
                    if (selected.size > 0) requeueSelected.mutate([...selected]);
                  }}
                  onSelectAllMatching={() => {
                    selectMatching.mutate();
                  }}
                  onClear={() => {
                    setSelected(new Set());
                  }}
                  t={t}
                />
              )}
              {queueTotal === 0 ? (
                <p className={MUTED}>
                  {t(
                    queueView === "attention"
                      ? "notifications.attention.empty"
                      : "notifications.queue.empty",
                  )}
                </p>
              ) : (
                <QueueTable
                  rows={rows}
                  total={queueTotal}
                  page={Math.min(queuePage, queuePages)}
                  per={queuePer}
                  onPage={setQueuePage}
                  onPer={(next) => {
                    setQueuePer(next);
                    // Back to page one: a page number that survives a size
                    // change points at rows that are no longer there, and the
                    // footer would say "101–150 of 60".
                    setQueuePage(1);
                  }}
                  readOnly={props.readOnly}
                  working={requeue.isPending}
                  t={t}
                  /* ⚠ `?? []` IS THE FAIL-CLOSED READ AND NOT DEFENSIVE NOISE.
                     An older server, or any response this screen cannot fully
                     understand, means we do not KNOW that nothing could have
                     sent these messages — and *cannot tell* must land on the
                     same side as *a provider is connected*. No list, no
                     control. The backend leans the same way for the same
                     reason (`unsent_preview.py`). */
                  disclosableChannels={queue.data.vocabulary?.disclosable_channels ?? []}
                  vocabulary={vocabulary}
                  selected={selected}
                  pageSelectable={pageSelectable}
                  onToggle={(id) => {
                    setSelected((current) => {
                      const next = new Set(current);
                      if (next.has(id)) next.delete(id);
                      else next.add(id);
                      return next;
                    });
                  }}
                  onTogglePage={(all) => {
                    setSelected((current) => {
                      const next = new Set(current);
                      for (const id of pageSelectable) {
                        if (all) next.add(id);
                        else next.delete(id);
                      }
                      return next;
                    });
                  }}
                  onShowDetails={(id) => {
                    setDetailsFor(rows.find((row) => row.id === id) ?? null);
                  }}
                  onRetryTo={(id) => {
                    setRetryFor(rows.find((row) => row.id === id) ?? null);
                  }}
                  onRequeue={(id) => {
                    requeue.mutate(id);
                  }}
                  onShowDocument={(id) => {
                    setDocumentFor(id);
                    setUnsentFor(null);
                  }}
                  onShowUnsent={(id) => {
                    setUnsentFor(id);
                    setDocumentFor(null);
                  }}
                />
              )}
            </Panel>
            {/* DEF-NOT-10650 (4B) — the LAST attempt's diagnostics. */}
            {detailsFor !== null ? (
              <MessageErrorPanel
                row={detailsFor}
                onClose={() => {
                  setDetailsFor(null);
                }}
              />
            ) : null}
            {/* DEF-NOT-10650 (3B) — this message only. `client` is PASSED
                (law 2), as for the two panels below. */}
            {retryFor !== null ? (
              <RetryToDialog
                row={retryFor}
                client={props.client}
                onClose={() => {
                  setRetryFor(null);
                }}
                onRetried={(address) => {
                  setRetryFor(null);
                  fireToast(t("notifications.retryTo.done", { address }));
                  void afterRequeue();
                }}
              />
            ) : null}
            {/* CR-049 task 3 — the letter we KEPT, or an honest statement that we
                kept none. `client` is PASSED and never defaulted at this call
                site: a component with an optional prop nothing supplies is the
                whole DEF-007..010 class (hard-won law 2). */}
            {documentFor !== null ? (
              <FrozenDocumentPanel
                messageId={documentFor}
                client={props.client}
                onClose={() => {
                  setDocumentFor(null);
                }}
              />
            ) : null}
            {/* The message we have NOT sent, and cannot — a different fact from
                the panel above, which serves the sealed copy of one we did.
                `client` is PASSED here too, for the same reason (law 2). */}
            {unsentFor !== null ? (
              <UnsentMessagePanel
                messageId={unsentFor}
                client={props.client}
                onClose={() => {
                  setUnsentFor(null);
                }}
              />
            ) : null}
          </div>
          <div className={CARD_COLUMN} data-testid="notifications-rail">
            <SummaryPanel summary={summary.data} t={t} />
          </div>
        </div>
      ) : onBlocked ? (
        /* ══ THE BLOCKED-ADDRESSES LIST AND ITS RELEASE — `DEF-NOT-5637` ════
           `SINGLE_CARD` and not `RULE_LAYOUT`: this tab is ONE list and has no
           rail, and a two-column grid with nothing in the second column draws a
           gap a clerk reads as a missing panel. */
        <div className={SINGLE_CARD} data-testid="notifications-blocked-tab">
          <BlockedAddressesTab readOnly={props.readOnly} client={props.client} />
        </div>
      ) : (
        <>
          {/* CR-048 F2 — ABOVE THE LIST, because *"why is nothing sending?"* is
              asked at a row of that list and this is the only thing that answers
              it. When the settings read fails the strip is absent and the
              `dispatch-unavailable` note below says so — a strip that guessed at
              "not switched on" would be worse than no strip. */}
          {settings.data !== undefined && (
            <ChannelStatusStrip
              settings={settings.data}
              summary={summary.data}
              readOnly={props.readOnly}
              working={saveSettings.isPending}
              t={t}
              onSave={(patch) => {
                saveSettings.mutate(patch);
              }}
            />
          )}
          {/* CR-009 · SET-12. First on the tab because it is what the tab is
              FOR: which messages this utility sends.

              ⚠ **AND IT IS FULL WIDTH, WHICH IS A MEASUREMENT AND NOT A
              PREFERENCE (CR-048 wave H).** Inside the 1056px body column this
              matrix needed 1157px and hung 101px past its own card; on the full
              1392px page it fits, with the event column at its readable 15rem.
              A list that has to be scrolled sideways to be read is the defect
              one level along. */}
          <NotificationRulesSection
            readOnly={props.readOnly}
            client={props.client}
            sub={undefined}
            onOpen={props.onOpenRule}
            receipt={receipt}
          />
          <div className={RULE_LAYOUT}>
            <div className={CARD_COLUMN} data-testid="notifications-main">
              {/* The CONFIG half. Each card renders its own failure rather than
                  darkening the whole tab. */}
              {settings.data === undefined && settings.error !== null && (
                <RefusalStrip
                  role="note"
                  className={REASON_CLAMP}
                  data-testid="dispatch-unavailable"
                >
                  {t("notifications.dispatch.unavailable", {
                    reason: apiErrorText(settings.error, t),
                  })}
                </RefusalStrip>
              )}
              {/* The mail server, READ from Connectors (PO 2026-10-22). */}
              <MailServerPanel sender={sender.data} failed={sender.error !== null} t={t} />
              {/* ⚠ THE SENDER FORM AND THE RIGHTS CARD ARE NOT ON THIS SCREEN
                  (PO 2026-10-22): the mail server is set on Connectors, and the
                  rights wording is on Templates under the disconnection
                  letter. A second copy of either here is the defect. */}
            </div>
            <div className={CARD_COLUMN} data-testid="notifications-rail">
              {settings.data !== undefined && (
                <DispatchConfigPanel settings={settings.data} t={t} />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/**
 * The queue list, with the pagination footer B14 rule 16 requires on every list
 * table.
 *
 * ⚠ **THIS TABLE HAD NO FOOTER AT ALL, WHICH IS THE HALF OF THE PO'S
 * PAGINATION REPORT THAT IS A REAL DEFECT.** Measured on the running app: this
 * tab rendered **125 rows in five tbodies**, and only the rules matrix — a
 * `DataTable` — carried a pager. The queue put 50 rows on the page and the
 * letter library 38, both with no footer, no range and no rows-per-page.
 *
 * ⚠ **THE OTHER HALF IS NOT A DEFECT AND IS NOT FIXED HERE.** The PO's words
 * are *"pagination shows more than 10 rows"*, and the page-size ladder is
 * **50 / 100 / 200 / 500, default 50** — ratified by the PO themselves on
 * 2026-08-09 (A11 r2 Lane C: *"page sizes 50/100/200/500/1000, default 50"*)
 * and carried by B14 rule 16. Changing it would restyle every list in the
 * product against a signed figure, so it is RAISED rather than taken: see the
 * change-request row. `ListPager` uses the shared `PAGE_SIZES`, so if the
 * ladder is ever re-signed this footer moves with every other one and not
 * separately.
 *
 * ⚠ **AND THE FOOTER USED TO BE FURNITURE OVER A LIE (`DEF-NOT-5746`,
 * 2026-09-18).** The sentence that stood here said *"`ListPager` + `pageSlice`
 * … the queue is a client-held array with no request state"*, and it was wrong
 * in the one way that matters: the array was never the queue. The tab asked
 * `GET /outbound` for a single page of fifty — the endpoint has paged in the
 * DATABASE since it was written — and this table then sliced those fifty again
 * and counted them for its own total. So a utility with four thousand queued
 * messages read *"1–50 of 50"*, and pressing `›` reached nothing, because there
 * was no second page in the browser to reach.
 *
 * **It has no state of its own now. The window is the caller's**, because the
 * caller is what issues the request, and `NFR-3` makes a page a REQUEST rather
 * than a slice. `ListPager` is still the shared footer — one footer in the
 * product — and `pageSlice` is simply not part of this screen any more.
 */
export function QueueTable(props: {
  /** ONE PAGE, as the server sliced it. Never the whole queue. */
  rows: readonly OutboundRow[];
  /** The server's own `count` — what the footer says after *of*. */
  total: number;
  page: number;
  per: PageSize;
  onPage: (page: number) => void;
  onPer: (per: PageSize) => void;
  readOnly: boolean;
  working: boolean;
  t: Translator;
  disclosableChannels: readonly string[];
  /** DEF-NOT-10650 — the server's re-queue / retry-to vocabulary. */
  vocabulary: OutboundVocabulary | undefined;
  /** DEF-NOT-10650 (2A) — the ticked ids, and the ids on THIS page that may be
   *  ticked (the header box selects exactly those). */
  selected: ReadonlySet<string>;
  pageSelectable: readonly string[];
  onToggle: (id: string) => void;
  onTogglePage: (all: boolean) => void;
  onRequeue: (id: string) => void;
  onShowDocument: (id: string) => void;
  onShowUnsent: (id: string) => void;
  onShowDetails: (id: string) => void;
  onRetryTo: (id: string) => void;
}) {
  const shown = props.rows;
  const pageAll =
    props.pageSelectable.length > 0 && props.pageSelectable.every((id) => props.selected.has(id));
  return (
    <>
      {/* A wide table scrolls INSIDE its own box; the page body never scrolls
          sideways. Harmless when it fits — which, after the layout fix above,
          is the normal case. */}
      <div className={TABLE_SCROLL}>
        <table className="data-table">
          <thead>
            <tr>
              {!props.readOnly && (
                <th className="w-8">
                  <input
                    type="checkbox"
                    checked={pageAll}
                    disabled={props.pageSelectable.length === 0}
                    aria-label={props.t("notifications.attention.selectPage")}
                    data-testid="queue-select-page"
                    onChange={() => {
                      props.onTogglePage(!pageAll);
                    }}
                  />
                </th>
              )}
              <th>{props.t("notifications.queue.col.type")}</th>
              <th>{props.t("notifications.queue.col.channel")}</th>
              <th>{props.t("notifications.queue.col.status")}</th>
              <th>{props.t("notifications.queue.col.recipient")}</th>
              <th>{props.t("notifications.queue.col.attempts")}</th>
              <th>{props.t("notifications.queue.col.lastError")}</th>
              <th aria-label={props.t("notifications.queue.col.action")} />
            </tr>
          </thead>
          <tbody>
            {shown.map((row) => (
              <QueueRow
                key={row.id}
                row={row}
                readOnly={props.readOnly}
                working={props.working}
                t={props.t}
                disclosableChannels={props.disclosableChannels}
                vocabulary={props.vocabulary}
                selected={props.selected.has(row.id)}
                onToggle={props.onToggle}
                onRequeue={props.onRequeue}
                onShowDocument={props.onShowDocument}
                onShowUnsent={props.onShowUnsent}
                onShowDetails={props.onShowDetails}
                onRetryTo={props.onRetryTo}
              />
            ))}
          </tbody>
        </table>
      </div>
      {/* B14 rule 16. Every figure in it is the SERVER'S — the total is
          `count`, and both controls issue a request rather than re-slicing an
          array the browser is already holding (`DEF-NOT-5746`). */}
      <ListPager
        total={props.total}
        page={props.page}
        per={props.per}
        onPage={props.onPage}
        onPer={props.onPer}
      />
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-NOT-013@6c2a90f (the same packet apps/notifications/delivery_ops.py and selectors.py were cut from — 04-docs/05-modules/10-notifications/06-epics/EP-NOT-04-delivery-ops.md US-NOT-013 §1/§3/§5 + its capability matrix · 10-notifications/02-business-rules.md · 04-docs/01-spec/11-api-contracts.md Addendum r4 · 08-qa/01-e2e/journeys/J17-delivery-life.md — because this is that story's SCREEN half and a second packet hash would make one story look like two)
// generated: 2026-08-16 by story-coder (DEF-128 notifications API lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest (SettingsNotificationsTab.test.tsx) · run_gates✔ including G13 (both props are passed by SettingsPage — this file exists because the OPPOSITE, a component nothing calls, is the defect class it closes)
// exceptions: (1) NO CSV DOWNLOAD. The S8 capability row's export rides the platform POST /api/exports (IS-9) and `outbound` is not a registered exportable resource — a button here would post to a registry that cannot serve it (DEF-135 names the same gap for invoices, payments, reads and audit).
//         (2) NO RE-SEND AND NO MARK-RETURNED CONTROL. Both endpoints exist; their screens are S35 and S30 (US-NOT-011 §5, US-NOT-014 TC-1), where the clerk is holding the payment or the envelope. A second door onto a re-send from a settings dashboard is two places to get a certified letter posted twice.
//         (3) ⚠ CORRECTED 2026-08-17 (CR-009 lane) — DEF-228. This exception used to read "NO DISPATCH CONFIG — batch size, quiet hours and the two channel-activation flags are US-NOT-004 and have no mounted endpoint", and the same file has imported `getNotificationSettings`/`updateNotificationSettings` and rendered `DispatchConfigPanel` since the endpoint mounted on 2026-08-16. The dispatch config IS here and IS editable. Hard-won law 1, in the file's own trailer.
//         (6) [CR-009 2026-08-17 · AMENDED 2026-08-22, DEF-286] THE SET-12 EVENT MATRIX MOUNTS HERE and SET-12D replaces the tab body when a rule is open (the requirement says full page, not modal). What this tab writes for a rule: the On toggle, the escalation ladder, AND — since the W13 lane closed DEF-286 — every field in `EDITABLE_RULE_FIELDS`/`EDITABLE_CHANNEL_FIELDS` through SET-12D's editors. The old sentence here called the pickers "a named deferral in NotificationRules.tsx exception (2)"; that deferral is built and the exception rewritten.
//         (4) [RETIRED 2026-10-29, DEF-NOT-10650] This read "NO BULK SELECTION YET … a checkbox column with no server-side selection story is where an empty selection quietly means 'all'". The PO ruled the story (2A): checkboxes on re-queueable rows only, "Select all on this page", an explicit "Select all N matching" RESOLVED BY THE SERVER (`GET /outbound/selection`, capped at 500 and refused above it), and a bar that does not exist at zero — so an empty selection has no button to press, and the server refuses `[]` anyway. See `AttentionQueue.tsx`.
//         (5) `delivered` AND `bounced` RENDER AS "NOT REPORTED", NEVER 0 — see the header. This is the one rendering decision in the file that is a RULE rather than a layout choice.
//         (7) [CR-048 F2, 2026-08-30] THE DISPATCH CARD IS SPLIT IN TWO, AND THE LINE IT IS SPLIT ON IS A QUESTION. `ChannelStatusStrip` answers "can anything leave the building, and how much is waiting" — the two go-live switches, print's locked row, the release posture and a per-channel queue count, across the top of the list where that question is actually asked. `DispatchConfigPanel` keeps "how fast and when" and is renamed PACING. The defect was that the two go-live switches sat in a card beside a matrix of fifteen per-event channel toggles and read as a second copy of them. Nothing was deleted; every control and every sentence is still on the tab.
//         (8) [CR-048 F2, 2026-08-30] THE PACING CARD TAKES NO `readOnly`, `working` OR `onSave` ANY MORE, and that is deliberate rather than an oversight: both figures are DISPLAYS. `editable_fields` is served and nothing on this screen reads it, so US-NOT-004's editors for the batch size and the send window have never existed here — a prop nothing could act on is the dead wiring G13 exists to catch (hard-won law 2). When those editors are built the props come back with them.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
