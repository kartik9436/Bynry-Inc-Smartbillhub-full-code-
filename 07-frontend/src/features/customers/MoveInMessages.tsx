// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.33 (lane MVI-WIZ-REV) — **REDRAWN FROM IMAGES 45
//           AND 46**, the four-step move-in's *Messaging* table: SEND ·
//           MESSAGE * · TO · CHANNEL · WHEN, the two defaults first, then the
//           rows a clerk adds with *+ Add message*, and *n will send* on the
//           footer. Built on the kit's `TableArray` (B14 rule 43 — every
//           selection table is the kit's).
// Defect:   DEF-CUS-6365 — the review once drew a 60-word *"what this move-in
//           will not write"* paragraph where the blueprint draws the
//           customer's messages (PO 2026-09-23, *"reduce this text"*). Still
//           true: no row here is typed into this file.
// Rules:    B14 rule 33 (a fact ≤ 6 words; RATIONALE is ZERO words on screen)
//           · rule 41 (the product matches the drawing) · rule 44 (our UI
//           standard decides how it is built) · rule 34 (one word per thing —
//           the channels are the notification rules screen's own words) ·
//           rule 21 (Tailwind only; this file is on `route-b-migrated.txt`) ·
//           BR-NOT-013 (nothing is dispatched — no row claims a delivery) ·
//           hard-won law 2 (a control that cannot act is a fact, not an input)
// Server:   `GET /move-ins/messages` → `customers.notifications_seam
//           .move_in_message_plan` (the defaults) · `GET /move-ins/message-
//           templates` → `move_in_complete.template_choices` (what *+ Add
//           message* may pick) · Complete's `extra_messages` (§9.FLOW P1.20)
// Tests:    MoveInMessages.dom.test.tsx · moveInWizard/StepReview.dom.test.tsx
// Hosts:    moveInWizard/StepReview.tsx (step 4, Review)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · THE DEFAULT ROWS ARE THE SERVER'S ANSWER, AND THEIR CELLS ARE FACTS
// ══════════════════════════════════════════════════════════════════════════
// The welcome and the service agreement (and a deposit receipt or letter when
// the deposit is taken) are decided by the SAME calls Complete makes —
// `services.channel_decision` per event — so the review and the queue cannot
// disagree. Images 45/46 draw their TO, CHANNEL and WHEN as dropdowns and
// their SEND as a live tick. **Complete has no parameter for any of the four
// on a default** — `extra_messages` refuses a default by name
// (`customers.moveIn.messages.defaultTwice`) and nothing else names one — so a
// live control would be hard-won law 2's mirror: a control over a door that
// would ignore it. They are drawn as the facts they are: the tick disabled and
// ticked from `channels.length > 0`, the rest as text, and the row's ✕
// disabled with its reason. **The day Complete takes a choice for a default,
// `MoveInMessages.dom.test.tsx` goes red on the disabled box and names this
// file.** Recorded as a difference from the drawing (CR-171, lane MVI-WIZ-REV record).
//
// ⚠ **THAT DAY CAME — CR-190-BRC10, 2026-10-22.** PO, verbatim: *"A: allow
// untick and channel change per move-in"*. Complete now takes
// `default_messages: [{key, send, channel?}]` and validates it server-side, so
// a row the server marks `editable` gets a LIVE tick and, where its template
// class allows more than one channel (`allowed_channels`, derived by the
// server — never typed here), a live channel select. Settings still supply the
// starting answer. The deposit receipt and letter are queued by the payment at
// *Pay now*, not by Complete, so the server does not mark them editable and
// they stay facts (`DEF-CUS-10444`). The hold-expiry test now asserts the LIVE
// box on an editable row and the disabled one on a fact row.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · AN ADDED ROW IS A REAL INPUT, AND IT IS EXACTLY `extra_messages`
// ══════════════════════════════════════════════════════════════════════════
// Message (a published template, by NAME — B14 rule 31), To (the customer, a
// co-owner the customer step holds, or the unit's owner), Channel (email,
// text, letter, portal) and When (on complete, the day before the move-in, on
// the move-in date, the day before the visit — the last only while a visit is
// planned). An unticked added row is kept on screen and NOT sent; a row with
// no message chosen is not sent either, and Continue does not need to hold for
// it because a blank added row commits nothing. What Complete then does with a
// row (queued now, or planned with its reason) is its answer, shown on the
// completed screen — never promised here (BR-NOT-013).
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · TWO OF p077's FIVE ROWS ARE STILL NOT DRAWN
// ══════════════════════════════════════════════════════════════════════════
// *The readings this account opened on* and *That a meter still has to be
// read* name no template class this product holds (decision log 2026-09-24).
// When either is authored, the server's plan grows the row and this table
// draws it without a change here.
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { CheckboxField, SelectField } from "@/components/FormModal";
import { LoadingSkeleton } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import type { Translator } from "@/features/tenancy/settingsShared";

import { Dash } from "./customersShared";

/** What `_plan_template` pins: the class, the name a human gave it, its
 *  version. `null` when nothing is published (`BR-NOT-002`). */
export interface MoveInMessageTemplate {
  code: string;
  name: string;
  version: number;
}

export interface MoveInMessageRow {
  /** The event key, or `service_agreement` for the one row that is not an
   *  event. Unknown keys still render (the server owns this list, not us). */
  key: string;
  /** The channels this save will really queue on. EMPTY means nothing goes
   *  out — which is a true answer and never a missing one. */
  channels: string[];
  template: MoveInMessageTemplate | null;
  /** CR-190-BRC10 — the clerk may untick this default or change its channel
   *  for this move-in. Absent on a fact row (the deposit receipt and letter). */
  editable?: boolean;
  /** The channels the clerk may pick, derived by the server from the template
   *  class (and the move letter's print floor). */
  allowed_channels?: string[];
}

/** CR-190-BRC10 — one move-in's answer for one default. `channel: null` keeps
 *  the Settings channel. */
export interface DefaultChoice {
  send: boolean;
  channel: string | null;
}
export type DefaultChoices = Record<string, DefaultChoice>;

/** Complete's `default_messages` — only the defaults the clerk CHANGED. An
 *  untouched default is not sent, so the payload of a move-in where nothing
 *  changed is byte for byte what it was. */
export function defaultMessagesPayload(choices: DefaultChoices): Record<string, unknown>[] {
  return Object.entries(choices)
    .filter(([, choice]) => !choice.send || choice.channel !== null)
    .map(([key, choice]) => ({
      key,
      send: choice.send,
      ...(choice.send && choice.channel !== null ? { channel: choice.channel } : {}),
    }));
}

/** A parked draft's default answers, distrusted as every parked value is. */
export function hydrateDefaultChoices(raw: unknown): DefaultChoices {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) return {};
  const out: DefaultChoices = {};
  for (const [key, value] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof value !== "object" || value === null) continue;
    const item = value as Record<string, unknown>;
    out[key] = {
      send: item.send !== false,
      channel: typeof item.channel === "string" && item.channel !== "" ? item.channel : null,
    };
  }
  return out;
}

export interface MoveInMessagePlan {
  results: MoveInMessageRow[];
  /** False when notifications published no answer at all. The table then says
   *  so instead of drawing an empty list, which would read as *nothing goes
   *  out* — the opposite claim. */
  served: boolean;
}

export function moveInMessagesPath(query: {
  category: string;
  depositTaken: boolean;
  depositCleared: boolean;
}): string {
  const params = new URLSearchParams({
    category: query.category,
    deposit_taken: query.depositTaken ? "true" : "false",
    deposit_cleared: query.depositCleared ? "true" : "false",
  });
  return `/move-ins/messages?${params.toString()}`;
}

export const moveInMessagesQueryKey = (
  category: string,
  depositTaken: boolean,
  depositCleared: boolean,
) => ["customers", "move-in", "messages", category, depositTaken, depositCleared] as const;

export async function getMoveInMessages(
  query: { category: string; depositTaken: boolean; depositCleared: boolean },
  client: ApiClient = api,
): Promise<MoveInMessagePlan> {
  const response = await client.get<MoveInMessagePlan>(moveInMessagesPath(query));
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ── *+ Add message* — what may be picked (P2.33) ───────────────────────────

export interface MoveInTemplateChoice {
  code: string;
  name: string;
}

export interface MoveInTemplateChoices {
  served: boolean;
  results: MoveInTemplateChoice[];
}

export const MOVE_IN_MESSAGE_TEMPLATES_PATH = "/move-ins/message-templates";
export const moveInMessageTemplatesQueryKey = ["customers", "move-in", "message-templates"] as const;

export async function getMoveInMessageTemplates(client: ApiClient = api): Promise<MoveInTemplateChoices> {
  const response = await client.get<MoveInTemplateChoices>(MOVE_IN_MESSAGE_TEMPLATES_PATH);
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** §9.FLOW P1.20 — the vocabulary `move_in_extras` checks, in the drawn order. */
export const EXTRA_RECIPIENTS = ["customer", "co_owner", "unit_owner"] as const;
export const EXTRA_CHANNELS = ["email", "text", "letter", "portal"] as const;
export const EXTRA_SEND_WHEN = [
  "on_complete",
  "day_before_move_in",
  "on_move_in_date",
  "day_before_visit",
] as const;
export type ExtraRecipient = (typeof EXTRA_RECIPIENTS)[number];
export type ExtraChannel = (typeof EXTRA_CHANNELS)[number];
export type ExtraSendWhen = (typeof EXTRA_SEND_WHEN)[number];

/** One row a clerk added. `key` is the row's own and never sent. */
export interface ExtraMessageRow {
  key: string;
  send: boolean;
  template_key: string;
  recipient: ExtraRecipient;
  /** Required by the server for `co_owner` — a co-owner written by the same
   *  Complete, named as the customer step names them. */
  co_owner_name: string;
  channel: ExtraChannel;
  send_when: ExtraSendWhen;
}

let extraCounter = 0;
/** Image 46's new row: *Choose…*, the customer, Email, On complete. */
export function newExtraMessage(): ExtraMessageRow {
  extraCounter += 1;
  return {
    key: `xm-${Date.now().toString(36)}-${extraCounter}`,
    send: true,
    template_key: "",
    recipient: "customer",
    co_owner_name: "",
    channel: "email",
    send_when: "on_complete",
  };
}

/**
 * The commit's `extra_messages` — only a TICKED row with a message chosen. An
 * unticked or blank row is kept on screen and sends nothing; the defaults are
 * never rows (the server refuses one as `defaultTwice`).
 */
export function extraMessagesPayload(rows: readonly ExtraMessageRow[]): Record<string, unknown>[] {
  return rows
    .filter((row) => row.send && row.template_key !== "")
    .map((row) => ({
      template_key: row.template_key,
      recipient: row.recipient,
      ...(row.recipient === "co_owner" ? { co_owner_name: row.co_owner_name } : {}),
      channel: row.channel,
      send_when: row.send_when,
    }));
}

function oneOf<T extends string>(value: unknown, allowed: readonly T[], fallback: T): T {
  return typeof value === "string" && (allowed as readonly string[]).includes(value) ? (value as T) : fallback;
}

/** A parked draft's rows, distrusted as every parked value is (BR-SHL-048). */
export function hydrateExtraMessages(raw: unknown): ExtraMessageRow[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null)
    .map((item) => ({
      ...newExtraMessage(),
      send: item.send !== false,
      template_key: typeof item.template_key === "string" ? item.template_key : "",
      recipient: oneOf(item.recipient, EXTRA_RECIPIENTS, "customer"),
      co_owner_name: typeof item.co_owner_name === "string" ? item.co_owner_name : "",
      channel: oneOf(item.channel, EXTRA_CHANNELS, "email"),
      send_when: oneOf(item.send_when, EXTRA_SEND_WHEN, "on_complete"),
    }));
}

/** The table's channel → the notification rules screen's word for it (B14
 *  rule 34): *text* is `sms`, *letter* is `pdf_print`. */
const EXTRA_CHANNEL_WORD: Record<ExtraChannel, string> = {
  email: "email",
  text: "sms",
  letter: "pdf_print",
  portal: "portal",
};

/**
 * The channels, in the server's own order, in the words the notification rules
 * screen already uses — `notifications.rules.channel.*`, shared rather than
 * copied so *Text message* cannot come to mean two things in one product
 * (B14 rule 34).
 */
export function channelsText(channels: readonly string[], t: Translator): string {
  return channels
    .map((channel) => t(`notifications.rules.channel.${channel}`, { defaultValue: channel }))
    .join(" · ");
}

/** How many rows will be handed to Complete: each default that goes out on a
 *  channel, and each ticked added row with a message chosen. */
export function willSendCount(
  plan: readonly MoveInMessageRow[],
  extra: readonly ExtraMessageRow[],
  defaults: DefaultChoices = {},
): number {
  return (
    plan.filter((row) => row.channels.length > 0 && defaults[row.key]?.send !== false).length +
    extraMessagesPayload(extra).length
  );
}

type Line = { kind: "default"; row: MoveInMessageRow } | { kind: "extra"; row: ExtraMessageRow };

export function MoveInMessages(props: {
  /** The account category the customer step collected — the axis a template
   *  variant resolves on (`BR-BIL-025`). `""` resolves the default variant. */
  category: string;
  /** The deposit answers. A deposit that is not taken queues no receipt and
   *  no letter. `depositCleared` means *held* — the register moved — which,
   *  since CR-186-BRC10, is every deposit taken at the counter. */
  depositTaken: boolean;
  depositCleared: boolean;
  /** The customer's name, as the customer step holds it. */
  to: string;
  /** The rows the clerk added, and their setter. */
  extra: readonly ExtraMessageRow[];
  onExtraChange: (next: ExtraMessageRow[]) => void;
  /** CR-190-BRC10 — this move-in's answers for the editable defaults. */
  defaults: DefaultChoices;
  onDefaultsChange: (next: DefaultChoices) => void;
  /** Co-owners or owners the customer step holds, by name — the *To* choices
   *  beside the customer. Empty offers none. */
  coOwners: readonly string[];
  /** The unit owner's name, or `null` when the unit has none on record. */
  unitOwner: string | null;
  /** A field visit is planned — only then is *Day before the visit* offered. */
  visitPlanned: boolean;
  t: Translator;
  client?: ApiClient;
}) {
  const { t } = props;
  const client = props.client ?? api;
  const query = useQuery({
    queryKey: moveInMessagesQueryKey(props.category, props.depositTaken, props.depositCleared),
    queryFn: () =>
      getMoveInMessages(
        {
          category: props.category,
          depositTaken: props.depositTaken,
          depositCleared: props.depositCleared,
        },
        client,
      ),
  });
  const templates = useQuery({
    queryKey: moveInMessageTemplatesQueryKey,
    queryFn: () => getMoveInMessageTemplates(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const name = props.to.trim() === "" ? t("customers.moveIn.messages.toCustomer") : props.to.trim();
  const toCustomer = t("customers.moveIn.messages.to.customer", { name });
  const recipientOptions = [
    { value: "customer", label: toCustomer },
    ...props.coOwners.map((owner) => ({
      value: `co_owner:${owner}`,
      label: t("customers.moveIn.messages.to.coOwner", { name: owner }),
    })),
    ...(props.unitOwner === null
      ? []
      : [{ value: "unit_owner", label: t("customers.moveIn.messages.to.unitOwner", { name: props.unitOwner }) }]),
  ];
  const recipientValue = (row: ExtraMessageRow): string =>
    row.recipient === "co_owner" ? `co_owner:${row.co_owner_name}` : row.recipient;
  const channelOptions = EXTRA_CHANNELS.map((channel) => ({
    value: channel,
    label: t(`notifications.rules.channel.${EXTRA_CHANNEL_WORD[channel]}`),
  }));
  const whenOptions = EXTRA_SEND_WHEN.filter((when) => when !== "day_before_visit" || props.visitPlanned).map(
    (when) => ({ value: when, label: t(`customers.moveIn.messages.when.${when}`) }),
  );
  const templateOptions = (templates.data?.results ?? []).map((one) => ({ value: one.code, label: one.name }));

  const plan = query.data?.results ?? [];
  const lines: Line[] = [
    ...plan.map((row): Line => ({ kind: "default", row })),
    ...props.extra.map((row): Line => ({ kind: "extra", row })),
  ];
  const setExtra = (key: string, patch: Partial<ExtraMessageRow>) =>
    props.onExtraChange(props.extra.map((row) => (row.key === key ? { ...row, ...patch } : row)));
  const choiceOf = (row: MoveInMessageRow): DefaultChoice =>
    props.defaults[row.key] ?? { send: true, channel: null };
  const setDefault = (row: MoveInMessageRow, patch: Partial<DefaultChoice>) =>
    props.onDefaultsChange({ ...props.defaults, [row.key]: { ...choiceOf(row), ...patch } });
  /** A default the clerk may act on: the server says so AND it goes out today. */
  const live = (row: MoveInMessageRow) => row.editable === true && row.channels.length > 0;
  const allowedOf = (row: MoveInMessageRow) => row.allowed_channels ?? [];
  /** The channel the select shows: the clerk's pick, else the first of the
   *  Settings channels the class allows. */
  const channelValue = (row: MoveInMessageRow) =>
    choiceOf(row).channel ?? row.channels.find((channel) => allowedOf(row).includes(channel)) ?? "";
  const idFor = (line: Line, field: string) =>
    `mi_msg_${line.kind === "default" ? line.row.key : line.row.key}_${field}`;

  const columns: TableArrayColumn<Line>[] = [
    {
      key: "send",
      label: t("customers.moveIn.messages.colSend"),
      cell: (line) =>
        line.kind === "default" ? (
          live(line.row) ? (
            <CheckboxField
              id={idFor(line, "send")}
              label={t("customers.moveIn.messages.colSend")}
              labelHidden
              checked={choiceOf(line.row).send}
              onChange={(checked) => setDefault(line.row, { send: checked })}
            />
          ) : (
            <CheckboxField
              id={idFor(line, "send")}
              label={t("customers.moveIn.messages.colSend")}
              labelHidden
              checked={line.row.channels.length > 0}
              disabled
              onChange={() => undefined}
            />
          )
        ) : (
          <CheckboxField
            id={idFor(line, "send")}
            label={t("customers.moveIn.messages.colSend")}
            labelHidden
            checked={line.row.send}
            onChange={(checked) => setExtra(line.row.key, { send: checked })}
          />
        ),
    },
    {
      key: "message",
      label: t("customers.moveIn.messages.colMessage"),
      header: (
        <>
          {t("customers.moveIn.messages.colMessage")}
          <span className="field-required" aria-hidden="true">
            {" *"}
          </span>
        </>
      ),
      cell: (line) =>
        line.kind === "default" ? (
          // An unknown key still renders, and renders as its CODE: this
          // catalogue does not get to decide which of the server's rows a
          // clerk may see.
          <>
            <span className="font-semibold" data-message-name={line.row.key}>
              {t(`customers.moveIn.messages.say.${line.row.key}`, { defaultValue: line.row.key })}
            </span>
            {/* `DEF-CUS-9743` — a default with no published template is still
                queued at Complete and HOLDS at dispatch (the queue's
                `template_pin_unresolved`). Said as the fact, in New
                Connection's own two words; why it holds is rationale (B14
                rule 33). */}
            {line.row.channels.length > 0 && line.row.template === null ? (
              <span className="block text-sm text-neutral-700" data-message-no-template="">
                {t("customers.build.messages.noTemplateShort")}
              </span>
            ) : null}
          </>
        ) : (
          <SelectField
            id={idFor(line, "message")}
            label={t("customers.moveIn.messages.colMessage")}
            labelHidden
            placeholder={t("customers.moveIn.messages.choose")}
            value={line.row.template_key}
            options={templateOptions}
            onChange={(value) => setExtra(line.row.key, { template_key: value })}
          />
        ),
    },
    {
      key: "to",
      label: t("customers.moveIn.messages.colTo"),
      cell: (line) =>
        line.kind === "default" ? (
          toCustomer
        ) : (
          <SelectField
            id={idFor(line, "to")}
            label={t("customers.moveIn.messages.colTo")}
            labelHidden
            value={recipientValue(line.row)}
            options={recipientOptions}
            onChange={(value) =>
              setExtra(
                line.row.key,
                value.startsWith("co_owner:")
                  ? { recipient: "co_owner", co_owner_name: value.slice("co_owner:".length) }
                  : { recipient: oneOf(value, EXTRA_RECIPIENTS, "customer"), co_owner_name: "" },
              )
            }
          />
        ),
    },
    {
      key: "channel",
      label: t("customers.moveIn.messages.colChannel"),
      cell: (line) =>
        line.kind === "default" ? (
          // A dash, not a sentence: why a row has no channel is RATIONALE (B14
          // rule 33), and the clear box beside it already says it goes nowhere.
          line.row.channels.length === 0 || (live(line.row) && !choiceOf(line.row).send) ? (
            <Dash />
          ) : live(line.row) && allowedOf(line.row).length > 1 ? (
            <SelectField
              id={idFor(line, "channel")}
              label={t("customers.moveIn.messages.colChannel")}
              labelHidden
              value={channelValue(line.row)}
              options={allowedOf(line.row).map((channel) => ({
                value: channel,
                label: t(`notifications.rules.channel.${channel}`, { defaultValue: channel }),
              }))}
              onChange={(value) => setDefault(line.row, { channel: value })}
            />
          ) : (
            channelsText(line.row.channels, t)
          )
        ) : (
          <SelectField
            id={idFor(line, "channel")}
            label={t("customers.moveIn.messages.colChannel")}
            labelHidden
            value={line.row.channel}
            options={channelOptions}
            onChange={(value) => setExtra(line.row.key, { channel: oneOf(value, EXTRA_CHANNELS, "email") })}
          />
        ),
    },
    {
      key: "when",
      label: t("customers.moveIn.messages.colWhen"),
      cell: (line) =>
        line.kind === "default" ? (
          t("customers.moveIn.messages.when.on_complete")
        ) : (
          <SelectField
            id={idFor(line, "when")}
            label={t("customers.moveIn.messages.colWhen")}
            labelHidden
            value={line.row.send_when}
            options={whenOptions}
            onChange={(value) =>
              setExtra(line.row.key, { send_when: oneOf(value, EXTRA_SEND_WHEN, "on_complete") })
            }
          />
        ),
    },
  ];

  const unread = query.isError || (query.data !== undefined && !query.data.served);
  return (
    <div data-move-in-messages="">
      <TableArray<Line>
        title={t("customers.moveIn.messages.title")}
        fact={t("customers.moveIn.messages.fact")}
        collection="move-in-messages"
        columns={columns}
        rows={lines}
        rowKey={(line) => `${line.kind}:${line.row.key}`}
        emptyText={t("customers.moveIn.messages.none")}
        removeLabel={t("customers.moveIn.messages.remove")}
        rowRemoveBlocked={(line) =>
          line.kind === "default" ? t("customers.moveIn.messages.defaultKept") : undefined
        }
        onChange={(next) =>
          props.onExtraChange(
            next.filter((line): line is Extract<Line, { kind: "extra" }> => line.kind === "extra").map((line) => line.row),
          )
        }
        actions={[
          {
            key: "add",
            label: t("customers.moveIn.messages.add"),
            onClick: () => props.onExtraChange([...props.extra, newExtraMessage()]),
          },
        ]}
        footerTrailing={
          <span className="text-base text-neutral-700" data-will-send="">
            {t("customers.moveIn.messages.willSend", {
              count: willSendCount(plan, props.extra, props.defaults),
            })}
          </span>
        }
        lead={
          query.isPending ? (
            <LoadingSkeleton variant="table" />
          ) : unread ? (
            <RefusalStrip>{t("customers.moveIn.messages.unread")}</RefusalStrip>
          ) : undefined
        }
      />
    </div>
  );
}
