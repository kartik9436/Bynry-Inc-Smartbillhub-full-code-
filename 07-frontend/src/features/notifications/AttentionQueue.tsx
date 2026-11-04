// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-NOT-10650 (PO 2026-10-29, ruled "1A 2A 3B 4B, start")
// Story:    US-NOT-013 (the delivery dashboard + re-queue, row AND bulk)
//           Screens: S8 (Settings → Notifications → Messages needing attention)
// Rules:    B14 rule 12 (a list has ONE toolbar — `SelectionToolbar`) · rule 15
//           (row actions are icons) · rule 21 (Tailwind; on route-b-migrated.txt
//           from its first commit) · rule 31 (no database id on screen — the
//           provider's reference is THEIRS and is labelled so) · rule 33 (caps)
//           · rule 43 (a piece of UI is a component) · BR-SHL-025 (a control
//           that cannot act is disabled WITH its reason)
// Tests:    src/features/notifications/attentionQueue.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// THE FOUR PIECES THE PO'S FOUR RULINGS ADD TO THE QUEUE, AS COMPONENTS.
//
//   1A  `QueueViewSwitch` — *Needing attention · All messages*, opening on the
//       first, with the server's count on it.
//   2A  `QueueSelectionBar` + `requeueOutcomeText` — *"N selected · Re-queue ·
//       Clear"*, the explicit *"Select all N matching"*, and the toast that
//       tallies each row. ⚠ **AN EMPTY SELECTION NEVER MEANS ALL**: the bar is
//       absent with nothing ticked, so there is no Re-queue to press, and the
//       server refuses an empty list anyway.
//   3B  `RetryToDialog` — *Fix address and retry*: a NEW message to the
//       corrected address. The failed one and the customer's contact are
//       unchanged, and the dialog says so in one fact.
//   4B  `MessageErrorPanel` — the LAST attempt only.
import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { retryOutboundTo } from "@/api/endpoints";
import type { OutboundRow, OutboundVocabulary, RequeueOutcome } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { SegmentedControl } from "@/components/SegmentedControl";
import { SelectionToolbar } from "@/components/SelectionToolbar";
import { useRegional } from "@/features/metering/meteringShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { Panel } from "@/features/tenancy/settingsShared";

import { addressCell, lastErrorText } from "./SettingsNotificationsTab";

/** 1A — the two views. `attention` is what the screen OPENS on. */
export type QueueView = "attention" | "all";
export const DEFAULT_QUEUE_VIEW: QueueView = "attention";

/** The `f.*` filters a view sends — the list and "Select all N matching" both
 *  read this, so the selection is the view on screen and never a second idea
 *  of it. */
export function viewFilters(view: QueueView): Record<string, string> {
  return view === "attention" ? { attention: "true" } : {};
}

/**
 * 2A — may this row carry a checkbox? Only where the server would re-queue it:
 * its status is on the server's own `requeueable_statuses` and it is not held.
 * ⚠ An older server sends no list, and then NO row is selectable (fail closed).
 */
export function canSelect(row: OutboundRow, vocabulary: OutboundVocabulary | undefined): boolean {
  const statuses = vocabulary?.requeueable_statuses ?? [];
  return !row.held && statuses.includes(row.status);
}

/** 3B — may this row offer *Fix address and retry*? The server's tuples again. */
export function canRetryTo(row: OutboundRow, vocabulary: OutboundVocabulary | undefined): boolean {
  return (
    !row.held &&
    (vocabulary?.retry_to_channels ?? []).includes(row.channel) &&
    (vocabulary?.retry_to_statuses ?? []).includes(row.status)
  );
}

/** The refusal codes `delivery_ops.requeue` writes, as a few words each. */
const REFUSAL_REASON_KEYS: Readonly<Record<string, string>> = {
  already_sent_not_requeueable: "notifications.attention.reason.alreadySent",
  held_row_not_requeueable: "notifications.attention.reason.held",
  status_not_requeueable: "notifications.attention.reason.addressRefused",
  not_found_in_this_tenant: "notifications.attention.reason.notFound",
};

/**
 * 2A — the toast, with per-row tallies: *"48 re-queued. 2 could not be:
 * already sent."* Composed HERE from the server's codes rather than shown as
 * its English `toast`, so it reads in the clerk's language.
 */
export function requeueOutcomeText(outcome: RequeueOutcome, t: Translator): string {
  const moved = t("notifications.attention.toast.requeued", { count: outcome.requeued.length });
  if (outcome.refused.length === 0) return moved;
  const tally = new Map<string, number>();
  for (const entry of outcome.refused) {
    const key = REFUSAL_REASON_KEYS[entry.code] ?? "notifications.attention.reason.other";
    tally.set(key, (tally.get(key) ?? 0) + 1);
  }
  const reasons = [...tally.entries()]
    .map(([key, count]) => (tally.size === 1 ? t(key) : `${t(key)} (${count})`))
    .join(", ");
  return `${moved} ${t("notifications.attention.toast.refused", {
    count: outcome.refused.length,
    reasons,
  })}`;
}

/** 1A — *Needing attention · All messages*, with the count on the first. */
export function QueueViewSwitch(props: {
  view: QueueView;
  attentionCount: number | undefined;
  onView: (view: QueueView) => void;
  t: Translator;
}) {
  return (
    <SegmentedControl
      className="mb-3"
      name="queue-view"
      label={props.t("notifications.attention.viewLabel")}
      active={props.view}
      onSelect={(id) => props.onView(id as QueueView)}
      segments={[
        {
          id: "attention",
          label: props.t("notifications.attention.view.attention"),
          ...(props.attentionCount !== undefined ? { count: props.attentionCount } : {}),
        },
        { id: "all", label: props.t("notifications.attention.view.all") },
      ]}
    />
  );
}

/**
 * 2A — the bar that swaps in when something is ticked. Absent at zero, so an
 * empty selection has no Re-queue to press.
 */
export function QueueSelectionBar(props: {
  selected: number;
  /** The server's count for the view on screen — the N in "Select all N". */
  matching: number;
  cap: number;
  working: boolean;
  resolving: boolean;
  onRequeue: () => void;
  onSelectAllMatching: () => void;
  onClear: () => void;
  t: Translator;
}) {
  const { t } = props;
  if (props.selected === 0) return null;
  const overCap = props.matching > props.cap;
  return (
    <SelectionToolbar
      label={t("notifications.attention.bar.label")}
      count={t("notifications.attention.bar.selected", { count: props.selected })}
      role="status"
      data-testid="queue-selection-bar"
    >
      <Button
        variant="primary"
        size="sm"
        disabled={props.working}
        data-testid="queue-bulk-requeue"
        onClick={props.onRequeue}
      >
        {t("notifications.attention.bar.requeue")}
      </Button>
      {props.matching > props.selected && (
        <Button
          variant="secondary"
          size="sm"
          disabled={overCap || props.resolving || props.working}
          title={overCap ? t("notifications.attention.bar.overCap", { cap: props.cap }) : undefined}
          data-testid="queue-select-all-matching"
          onClick={props.onSelectAllMatching}
        >
          {t("notifications.attention.bar.selectAllMatching", { count: props.matching })}
        </Button>
      )}
      <Button variant="secondary" size="sm" data-testid="queue-clear-selection" onClick={props.onClear}>
        {t("notifications.attention.bar.clear")}
      </Button>
      {overCap && props.matching > props.selected ? (
        <span className="text-sm">{t("notifications.attention.bar.overCap", { cap: props.cap })}</span>
      ) : null}
    </SelectionToolbar>
  );
}

const KV_ROW = "flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-divider py-2 last:border-b-0";
const KV_KEY = "w-40 flex-none text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]";
const KV_VALUE = "min-w-0 flex-1 [overflow-wrap:anywhere]";

function Fact(props: { label: string; children: ReactNode; testId?: string }) {
  return (
    <li className={KV_ROW}>
      <span className={KV_KEY}>{props.label}</span>
      <span className={KV_VALUE} data-testid={props.testId}>
        {props.children}
      </span>
    </li>
  );
}

/** The provider's answer, formatted. A string stays a string; anything else is
 *  pretty-printed JSON, because it is what the provider SAID and support reads
 *  it back to them. */
export function providerResponseText(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

/** 4B — the error details panel. The LAST attempt only; nothing is implied
 *  about earlier ones. */
export function MessageErrorPanel(props: { row: OutboundRow; onClose: () => void }) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const regional = useRegional({});
  const { row } = props;
  // Opened from a row icon, possibly fifty rows above: bring it into view, or
  // the click reads as doing nothing. Guarded — jsdom has no scrollIntoView.
  const frame = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    frame.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [row.id]);
  const address = addressCell(row);
  const response = providerResponseText(row.provider_response);
  const none = t("notifications.attention.details.none");
  const when = (value: string | null | undefined) =>
    value ? (
      <DateCell value={value} timeZone={regional.timeZone} dateFormat={regional.dateFormat} withTime />
    ) : (
      none
    );
  return (
    <div ref={frame} data-testid="queue-error-details">
      <Panel title={t("notifications.attention.details.title")}>
        <ul className="m-0 mb-3 list-none p-0">
          <Fact label={t("notifications.attention.details.channel")}>
            {t(`notifications.queue.channel.${row.channel}`)}
          </Fact>
          <Fact label={t("notifications.attention.details.recipient")}>
            {address.text ?? (address.reasonKey === null ? none : t(address.reasonKey))}
          </Fact>
          <Fact label={t("notifications.attention.details.status")}>
            {t(`notifications.queue.status.${row.status}`)}
          </Fact>
          <Fact label={t("notifications.attention.details.created")}>{when(row.queued_at)}</Fact>
          <Fact label={t("notifications.attention.details.attempts")}>{row.attempts}</Fact>
          <Fact label={t("notifications.attention.details.lastAttempt")}>
            {when(row.last_attempt_at)}
          </Fact>
          <Fact label={t("notifications.attention.details.nextAttempt")}>
            {when(row.next_attempt_at)}
          </Fact>
          <Fact label={t("notifications.attention.details.lastError")} testId="queue-error-last">
            {row.last_error === null ? none : lastErrorText(row.last_error, translate)}
          </Fact>
          <Fact
            label={t("notifications.attention.details.providerReference")}
            testId="queue-error-reference"
          >
            {row.provider_reference ?? none}
          </Fact>
          <Fact
            label={t("notifications.attention.details.providerResponse")}
            testId="queue-error-response"
          >
            {response === null ? (
              none
            ) : (
              <pre className="m-0 max-h-60 overflow-auto whitespace-pre-wrap bg-bg p-2 font-mono text-sm">
                {response}
              </pre>
            )}
          </Fact>
        </ul>
        {/* A row of its own, so the panel's column does not stretch the
            button across the card (seen on the walkthrough at 1440). */}
        <div className="flex">
          <Button variant="secondary" size="sm" onClick={props.onClose}>
            {t("notifications.attention.details.close")}
          </Button>
        </div>
      </Panel>
    </div>
  );
}

/** The field a clerk types into, checked the way the server checks it. */
export function retryToSchema(channel: string, t: Translator) {
  const message = t(
    channel === "sms"
      ? "notifications.retryTo.addressInvalidPhone"
      : "notifications.retryTo.addressInvalid",
  );
  const address = z
    .string()
    .trim()
    .min(1, message)
    .refine((value) => {
      if (channel === "email") return z.string().email().safeParse(value).success;
      const digits = value.replace(/\D/g, "");
      return (
        !value.includes("@") &&
        ((digits.length === 10 && !value.trim().startsWith("+")) ||
          (digits.length === 11 && digits.startsWith("1")))
      );
    }, message);
  return z.object({ address });
}

/**
 * 3B — *Fix address and retry*. ⚠ **THIS MESSAGE ONLY.** The server queues a
 * NEW message to the address typed here; the failed one stays as the record
 * and the customer's contact is not written. The one fact the dialog states is
 * that, because it is what a clerk would otherwise assume the opposite of.
 */
export function RetryToDialog(props: {
  row: OutboundRow;
  client?: ApiClient;
  onClose: () => void;
  onRetried: (address: string) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [address, setAddress] = useState("");
  const sms = props.row.channel === "sms";

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      await retryOutboundTo(props.row.id, address.trim(), props.client ?? api);
      props.onRetried(address.trim());
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("notifications.retryTo.title")}
      /* The address that failed is the kicker — what the clerk recognises.
         Never the message id (B14 rule 31). */
      kicker={addressCell(props.row).text ?? undefined}
      schema={retryToSchema(props.row.channel, translate)}
      values={{ address }}
      submitLabel={t("notifications.retryTo.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <p className="m-0 mb-3 text-md leading-body" data-testid="retry-to-scope">
        {t("notifications.retryTo.scope")}
      </p>
      <TextField
        id="address"
        label={t(sms ? "notifications.retryTo.phoneLabel" : "notifications.retryTo.emailLabel")}
        value={address}
        onChange={setAddress}
        required
      />
    </FormModal>
  );
}
