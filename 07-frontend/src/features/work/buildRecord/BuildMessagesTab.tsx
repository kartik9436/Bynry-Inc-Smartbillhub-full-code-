// ── Trace ──────────────────────────────────────────────
// Change:   CR-150-BRC09 task 11 — the Messages tab. MOVED here from
//           `features/customers/BuildDetailTabs.tsx:1110` by `DEF-CUS-7618`,
//           unchanged in what it renders.
// Drawing:  `05-prototype/new-connect-detail-2026-09-28/06-messages.png`
// Rules:    B14 rule 20 · rule 33 (the PNG's grey caption is RATIONALE and is
//           ZERO WORDS ON SCREEN) · rule 43 · CLAUDE.md hard-won law 2's
//           MIRROR (a refusal that is still true is a refusal; a literal one
//           is a control that rots)
// Tests:    src/features/customers/BuildDetailTabs.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY NO SHARED PANEL SERVES THIS TAB
// ══════════════════════════════════════════════════════════════════════════
// The notifications module's own outbound list reads `GET /messages` and keys
// on an OUTBOUND id. The rows here have none: `_communication_rows` serves
// `code`, `channels`, `template_code`, a moment word and `state`, and every
// one is `not_sent` because a connection is not one of the fourteen things an
// outbound message may be about (`OQ-NOT-12521`, OPEN). There is nothing
// filed to list, so the shared list has nothing to read. It is new tab content
// with no shared panel, which `CR-151-BRC09` §3 puts in this kit.
//
// ⚠ **`CR-163-BRC10` (2026-10-02, lane NC-B) — THE TAB CAN SEND.** The
// paragraph above describes the world before `OQ-NOT-12521`'s `connection`
// kind was built. Each row now reads the QUEUE (State, When, copies) and
// carries Preview and Send now / Resend; a send is one letter on one channel
// to the owner or the co-applicant, through notifications' one write door,
// audited. Nothing here claims a letter REACHED anybody (`BR-NOT-013`).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import { FormModal, SelectField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { EnvelopeIcon, EyeIcon } from "@/components/icons";
import { localeLabel } from "@/i18n";
import { RowAction, RowActions } from "@/components/RowActions";
import { PlainTable } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import {
  BUILD_MESSAGE_CHANNEL,
  BUILD_MESSAGE_OCCASION,
  BUILD_MESSAGE_STATE,
  BUILD_TEMPLATE_CLASS,
  buildWord,
} from "@/features/customers/newConnectShared";
import type { Translator } from "@/features/customers/newConnectShared";

import { buildRecordQueryKey } from "../buildViews";
import { previewBuildMessage, sendBuildMessage } from "../workEndpoints";
import type { BuildRecord } from "../workEndpoints";
import { Section } from "./buildTabShell";
import type { BuildTabProps } from "./buildTabShell";

export interface BuildMessageRow {
  code: string;
  channels: string[];
  templateCode: string | null;
  state: string;
  /** The server's own reason a row is not sent yet. `null` once it is. */
  reason: string | null;
  /** The moment the newest copy was SENT, or QUEUED where nothing sent it. */
  sentAt: string | null;
  /** `false` = no published wording (item 27); `null` = could not be asked. */
  templateAvailable: boolean | null;
  /** `false` for the drawn rows that have no occasion and so no letter. */
  sendable: boolean;
  /** Queue rows already written for this letter — one per channel and copy. */
  deliveries: number;
  /** ⊕ `DEF-CUS-9195` — the languages those copies WENT in, oldest first,
   *  each once (PO 2026-10-02: step 1's language, the utility's as fallback). */
  languages: string[];
}

/** The three channels a clerk may pick — `connection_messages.SENDABLE_CHANNELS`. */
export const SENDABLE_CHANNELS = ["email", "pdf_print", "sms"] as const;

/** One recipient the record offers (`record.message_recipients`). */
export interface BuildMessageRecipient {
  code: string;
  name: string | null;
  channels: string[];
}

/** The record's `communication` section, narrowed. */
export function messageRows(record: BuildRecord | null): BuildMessageRow[] {
  return (record?.sections.communication.results ?? []).map((raw) => ({
    code: typeof raw.code === "string" ? raw.code : "",
    channels: Array.isArray(raw.channels) ? (raw.channels as string[]) : [],
    templateCode: typeof raw.template_code === "string" ? raw.template_code : null,
    state: typeof raw.state === "string" ? raw.state : "",
    reason: typeof raw.reason === "string" && raw.reason !== "" ? raw.reason : null,
    sentAt: typeof raw.sent_at === "string" ? raw.sent_at : null,
    templateAvailable:
      typeof raw.template_available === "boolean" ? raw.template_available : null,
    sendable: raw.sendable !== false,
    deliveries: Array.isArray(raw.deliveries) ? raw.deliveries.length : 0,
    languages: Array.isArray(raw.deliveries)
      ? [
          ...new Set(
            (raw.deliveries as Array<{ language?: unknown }>)
              .map((one) => (typeof one.language === "string" ? one.language : ""))
              .filter((code) => code !== ""),
          ),
        ]
      : [],
  }));
}

export function messageRecipients(record: BuildRecord | null): BuildMessageRecipient[] {
  return (record?.message_recipients ?? []).filter((one) => one.code !== "");
}

/**
 * **Why THIS row cannot be sent now, or `null` when it can** (`CR-163-BRC10`
 * items 26–27). The refusal is the PAYLOAD's, never a literal: a row with no
 * occasion or no published wording says *No template*, and a build with
 * nobody to address says so. The day a template is published the same row
 * goes live with no change here — the hold-expiry case in
 * `BuildDetailTabs.dom.test.tsx` asserts both directions.
 */
export function resendRefusal(
  row: BuildMessageRow,
  t: Translator,
  recipients: readonly BuildMessageRecipient[] = [{ code: "owner", name: null, channels: [...SENDABLE_CHANNELS] }],
): string | null {
  if (!row.sendable || row.templateCode === null || row.templateAvailable === false) {
    return t("customers.build.messages.noTemplateShort", { defaultValue: "No template" });
  }
  if (recipients.length === 0) {
    return t("customers.build.messages.noOwner", { defaultValue: "No owner account" });
  }
  return null;
}

const SEND_SCHEMA = z.object({ channel: z.string().min(1), recipient: z.string().min(1) });

/** *Send now* / *Resend* — channel and recipient, then ONE send (item 26). */
export function BuildSendMessageDialog(props: {
  t: Translator;
  connectionId: string;
  row: BuildMessageRow;
  recipients: readonly BuildMessageRecipient[];
  client?: ApiClient;
  onClose: () => void;
  onSent: () => void;
}) {
  const { t, row } = props;
  const [channel, setChannel] = useState<string>(row.channels[0] ?? "email");
  const offered = props.recipients.filter((one) => one.channels.includes(channel));
  const [recipient, setRecipient] = useState<string>(props.recipients[0]?.code ?? "owner");
  const chosen = offered.some((one) => one.code === recipient)
    ? recipient
    : (offered[0]?.code ?? "");
  const resend = row.deliveries > 0;

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await sendBuildMessage(
        props.connectionId,
        row.code,
        { channel, recipient: chosen },
        props.client,
      );
      props.onSent();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  const word = resend
    ? t("customers.build.messages.resendCopy", { defaultValue: "Resend" })
    : t("customers.build.messages.sendNow", { defaultValue: "Send now" });
  return (
    <FormModal
      title={t("customers.build.messages.sendTitle", { defaultValue: "Send message" })}
      kicker={buildWord(BUILD_MESSAGE_OCCASION, row.code, "customers.build.messages.occasion", t)}
      schema={SEND_SCHEMA}
      values={{ channel, recipient: chosen }}
      submitLabel={word}
      onClose={props.onClose}
      onSubmit={submit}
    >
      <SelectField
        id="build-message-channel"
        label={t("customers.build.messages.channelField", { defaultValue: "Channel" })}
        required
        value={channel}
        onChange={setChannel}
        options={SENDABLE_CHANNELS.map((code) => ({
          value: code,
          label: buildWord(BUILD_MESSAGE_CHANNEL, code, "customers.build.messages.channel", t),
        }))}
      />
      <SelectField
        id="build-message-recipient"
        label={t("customers.build.messages.recipientField", { defaultValue: "Send to" })}
        required
        value={chosen}
        onChange={setRecipient}
        options={offered.map((one) => ({
          value: one.code,
          label: [
            t(`customers.build.messages.recipient.${one.code}`, { defaultValue: one.code }),
            one.name,
          ]
            .filter((part): part is string => part !== null && part !== "")
            .join(" · "),
        }))}
      />
    </FormModal>
  );
}

/** What the letter would say for THIS build — read only, nothing queued. */
export function BuildMessagePreviewPanel(props: {
  t: Translator;
  connectionId: string;
  code: string;
  client?: ApiClient;
  onClose: () => void;
}) {
  const { t } = props;
  const query = useQuery({
    queryKey: ["connection", props.connectionId, "message-preview", props.code],
    queryFn: () => previewBuildMessage(props.connectionId, props.code, props.client),
    retry: false,
  });
  const shown = query.data ?? null;
  return (
    <Section
      id="message-preview"
      title={t("customers.build.messages.previewTitle", { defaultValue: "Message preview" })}
    >
      <div data-message-preview={props.code}>
        {query.isPending ? null : shown === null || !shown.available ? (
          <p className="text-sm text-neutral-700" data-preview-none="">
            {t("customers.build.messages.previewNone", {
              defaultValue: "No published wording to show.",
            })}
          </p>
        ) : (
          <>
            {shown.subject !== null && shown.subject !== undefined && shown.subject !== "" && (
              <p className="m-0 font-semibold" data-preview-subject="">
                {shown.subject}
              </p>
            )}
            <pre className="mt-2 whitespace-pre-wrap font-body text-sm" data-preview-body="">
              {shown.body}
            </pre>
          </>
        )}
        <p className="mt-3">
          <Button size="sm" onClick={props.onClose} data-preview-close="">
            {t("customers.build.messages.close", { defaultValue: "Close" })}
          </Button>
        </p>
      </div>
    </Section>
  );
}

export function BuildMessagesTab(props: BuildTabProps) {
  const { t } = props;
  const queryClient = useQueryClient();
  const toast = useToast();
  const rows = messageRows(props.record);
  const recipients = messageRecipients(props.record);
  const connectionId = props.detail.id;
  const [sending, setSending] = useState<BuildMessageRow | null>(null);
  const [previewing, setPreviewing] = useState<string | null>(null);
  // Re-read the record after a send, so State, When and the copies come back
  // from the QUEUE rather than being patched here.
  const reread = useMutation({
    mutationFn: async () => {
      await queryClient.invalidateQueries({ queryKey: buildRecordQueryKey(connectionId) });
    },
  });

  return (
    <>
      <Section
        id="messages"
        title={t("customers.build.messages.title", { defaultValue: "What went out" })}
      >
        {rows.length === 0 ? (
          <p className="text-sm text-neutral-700" data-build-empty="messages">
            {t("customers.build.messages.none", { defaultValue: "Nothing went out." })}
          </p>
        ) : (
          <PlainTable data-table="build-messages">
            <thead>
              <tr>
                <th>{t("customers.build.messages.col.message", { defaultValue: "Message" })}</th>
                <th>{t("customers.build.messages.col.channel", { defaultValue: "Channel" })}</th>
                <th>{t("customers.build.messages.col.template", { defaultValue: "Template" })}</th>
                <th>{t("customers.build.messages.col.when", { defaultValue: "When" })}</th>
                <th>{t("customers.build.messages.col.state", { defaultValue: "State" })}</th>
                <th>{t("customers.build.messages.col.language", { defaultValue: "Language" })}</th>
                <th>{t("customers.build.messages.col.actions", { defaultValue: "Actions" })}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const refusal = resendRefusal(row, t, recipients);
                const noTemplate =
                  !row.sendable || row.templateCode === null || row.templateAvailable === false;
                return (
                  <tr key={row.code} data-message-row={row.code}>
                    <td>
                      {buildWord(BUILD_MESSAGE_OCCASION, row.code, "customers.build.messages.occasion", t)}
                    </td>
                    <td>
                      {row.channels
                        .map((channel) =>
                          buildWord(BUILD_MESSAGE_CHANNEL, channel, "customers.build.messages.channel", t),
                        )
                        .join(" · ")}
                    </td>
                    {/* `DEF-CUS-9188` — a row with no wording says how to add
                        one, rather than printing nothing. */}
                    <td data-message-template="">
                      {noTemplate ? (
                        <span className="text-sm text-neutral-700" data-no-template="">
                          {t("customers.build.messages.noTemplate", {
                            defaultValue: "No template — add one in Settings → Templates",
                          })}
                        </span>
                      ) : (
                        buildWord(
                          BUILD_TEMPLATE_CLASS,
                          row.templateCode as string,
                          "customers.build.messages.template",
                          t,
                        )
                      )}
                    </td>
                    {/* `DEF-CUS-9188` — When is the queue's own moment. */}
                    <td data-message-when="">
                      {row.sentAt === null ? null : (
                        <DateCell
                          value={row.sentAt}
                          timeZone={props.timeZone}
                          dateFormat={props.dateFormat}
                          withTime
                        />
                      )}
                    </td>
                    <td data-message-state={row.state}>
                      {row.state === "not_sent" && row.reason === "sent_on_approval"
                        ? t("customers.build.messages.reason.sent_on_approval", {
                            defaultValue: "Sent on approval",
                          })
                        : t(`customers.build.messages.state.${row.state}`, {
                            defaultValue: BUILD_MESSAGE_STATE[row.state] ?? row.state,
                          })}
                    </td>
                    {/* ⊕ `DEF-CUS-9195` — which language each copy went in. */}
                    <td data-message-language={row.languages.join(" ")}>
                      {row.languages
                        .map((code) =>
                          t(`settings.regional.language.${code}`, { defaultValue: localeLabel(code) }),
                        )
                        .join(" · ")}
                    </td>
                    <td>
                      <RowActions>
                        <RowAction
                          icon={<EyeIcon />}
                          label={t("customers.build.messages.preview", { defaultValue: "Preview" })}
                          reason={noTemplate ? refusal : null}
                          testId={`preview-${row.code}`}
                          onClick={() => setPreviewing(row.code)}
                        />
                        <RowAction
                          icon={<EnvelopeIcon />}
                          label={
                            row.deliveries > 0
                              ? t("customers.build.messages.resendCopy", { defaultValue: "Resend" })
                              : t("customers.build.messages.sendNow", { defaultValue: "Send now" })
                          }
                          // ⊕ `DEF-MET-9238` — a read-only role may preview, never send.
                          reason={props.readOnlyReason ?? refusal}
                          testId={`send-${row.code}`}
                          onClick={() => setSending(row)}
                        />
                      </RowActions>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </PlainTable>
        )}
      </Section>
      {previewing !== null && (
        <BuildMessagePreviewPanel
          t={t}
          connectionId={connectionId}
          code={previewing}
          client={props.client}
          onClose={() => setPreviewing(null)}
        />
      )}
      {sending !== null && (
        <BuildSendMessageDialog
          t={t}
          connectionId={connectionId}
          row={sending}
          recipients={recipients}
          client={props.client}
          onClose={() => setSending(null)}
          onSent={() => {
            setSending(null);
            toast(t("customers.build.messages.queuedToast", { defaultValue: "Message queued." }));
            reread.mutate();
          }}
        />
      )}
    </>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-7618 · CR-150-BRC09 task 11 · `06-messages.png` (rule 42)
// generated: 2026-09-28 by the DETAIL PAGE lane; MOVED into the kit the same
//   day by the DEF-CUS-7618 lane, with no change to what it renders
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO)
// amended: 2026-10-02 by lane NC-B (CR-163-BRC10) — items 26–27, DEF-CUS-9188
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
