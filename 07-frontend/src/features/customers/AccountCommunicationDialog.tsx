// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave K — `ACC-S16`, the communication section.
//           Step 1 lane 2 finding F11, verbatim: *"There is no way to write to
//           the customer from this screen. Seven icons and six buttons and not
//           one sends a word."* Drawing `R6`, pages 186–188 (`ACC-C01` compose,
//           `ACC-C02` history).
// Story:    US-CUS-008 (S21 detail header + action rails)   Screens: S21
// Rules:    BR-NOT-005 (queue rows only — the commit reads *Queue*, never
//           *Send*) · BR-NOT-013 (no provider on post, email or SMS in this
//           release) · BR-PAY-035 + BR-NOT-008 (a reminder's tone IS a dunning
//           tier; a regulated kind is not composed here) · BR-BIL-036 (a
//           channel with nothing on file is SHOWN, with its reason) ·
//           BR-SHL-025 (a control that cannot act carries its reason) ·
//           B14 rule 16 (every list carries its pagination footer) · rule 21
//           (Tailwind utilities, no stylesheet class) · rule 31 (no database id
//           on screen) · rule 32 (one sentence per section) · rule 33 (a label
//           ≤ 3 words · a fact ≤ 6 · an instruction ≤ 6 per sentence ·
//           RATIONALE is zero words on screen) · rule 37 (a figure in a
//           wireframe is an illustration) · rule 39 (the field kit's own
//           5 / 6 / 20 anatomy, inherited by composing it).
// Tests:    07-frontend/src/features/customers/AccountCommunication.dom.test.tsx
// Impacts:  AccountIconRail.tsx (the eighth glyph) · AccountDetailPage.tsx (the
//           page that opens this) · api/accountCommunicationEndpoints.ts.
// ───────────────────────────────────────────────────────
/**
 * Writing to a customer from their account — and reading what already went out.
 *
 * ╔══════════════════════════════════════════════════════════════════════════╗
 * ║  `ACC-S16`: *"A clerk can write to the customer from the account, and    ║
 * ║   see what has already been sent."*                                      ║
 * ╚══════════════════════════════════════════════════════════════════════════╝
 *
 * WHAT THIS SCREEN MAY HONESTLY CLAIM, AND IT IS LESS THAN THE DRAWING SHOWS
 * ─────────────────────────────────────────────────────────────────────────────
 * `R6`'s history view draws statuses reading *Delivered 09/12* and *Failed —
 * number not reachable*. **This product can write neither.** `BR-NOT-013` is
 * CONFIRMED — no provider adapter exists on post, email or SMS — and
 * `delivery_ops.UNPOPULATED_STATUSES` names `delivered` and `bounced` as the two
 * statuses nothing on this deployment can produce. B14 rule 37 settles what to
 * do about it: *"treat every number drawn in a wireframe as an illustration,
 * never a fact to build to"*. So the list renders the vocabulary the queue
 * actually holds, and the drawing's own annotation agrees with that choice:
 * *"Whether anybody opened it is not recorded, and this screen will not imply
 * that it was."*
 *
 * THREE CONTROLS IN THE DRAWING ARE NOT DRAWN HERE, EACH FOR THE SAME REASON
 * ─────────────────────────────────────────────────────────────────────────────
 * Hard-won law 2: a control that does nothing is dead UI, and its mirror — a
 * refusal that outlived its reason — costs more. So rather than ship three
 * disabled controls, this wave ships none of them and records why:
 *
 *  · **Template** (*Free message · Balance summary · Payment options · We have
 *    not heard from you*). There is ONE template class for a clerk's own words,
 *    `account_message`, so the picker would have one option. The other three are
 *    not classes this platform has wording for, and inventing the body of a
 *    customer-facing document is exactly what `catalogs.CLASSES_WITHOUT_CATALOG`
 *    refuses to do.
 *  · **Attach the balance as a statement.** `catalogs.LISTINGS` says of the
 *    statement class, in its own words, *"The wording is ready; nothing produces
 *    a statement yet."* A checkbox that attaches nothing is worse than no
 *    checkbox.
 *  · **Save as a draft.** Nothing stores a draft. `ACC-S16` commits to writing
 *    and to reading what was written; a draft store is neither.
 *
 * ⚠ **AND THE ABSENCES ARE NOT EXPLAINED ON SCREEN.** B14 rule 33: *"RATIONALE
 * — why the product works this way, why a control is absent — is ZERO WORDS ON
 * SCREEN."* It belongs here and in the register, which is where it is.
 */
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import {
  getAccountCommunication,
  queueAccountMessage,
} from "@/api/accountCommunicationEndpoints";
import type {
  CommunicationChannel,
  CommunicationForm,
  CommunicationTemplate,
} from "@/api/accountCommunicationEndpoints";
import { getOutbound } from "@/api/endpoints";
import type { OutboundRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DatePickerField, FormModal, ModalShell, SelectField, TextField } from "@/components/FormModal";
import { ListPager } from "@/components/ListPager";
import type { PageSize } from "@/components/tableTypes";
import type { RegionalDateFormat } from "@/components/DateCell";

/** The two views the drawing names. */
export const COMMUNICATION_TABS = ["compose", "history"] as const;
export type CommunicationTab = (typeof COMMUNICATION_TABS)[number];

/** `communication_api.OFFERED_CHANNELS`, spelling for spelling — the order the
 *  drawing puts them in, with the portal last. */
export const COMMUNICATION_CHANNELS = ["email", "sms", "pdf_print", "portal"] as const;

/** `customer_events.MESSAGE_KIND_COURTESY`. The one kind composed here. */
export const KIND_COURTESY = "courtesy";

/** `notifications_seam.MOVE_MESSAGE_ALREADY_QUEUED` — a repeated submit finding
 *  its own row. The screen says so rather than claiming a second message. */
export const ALREADY_QUEUED = "move_message_already_queued";

/**
 * Which channels a clerk may tick, given what the account holds.
 *
 * ⚠ **A CHANNEL WITH NOTHING ON FILE IS SHOWN AND CANNOT BE TICKED** — the
 * drawing's own instruction, and `BR-BIL-036` underneath it: *"so a clerk can
 * see what is missing rather than wonder why an option vanished."* Exported so
 * the test asserts the rule rather than a rendering of it.
 */
export function tickable(channel: CommunicationChannel): boolean {
  return channel.on_file;
}

/** The default tick: the first channel that has an address. One tick, never
 *  all of them — a clerk chooses who to write to. */
export function defaultChannels(channels: CommunicationChannel[]): string[] {
  const first = channels.find(tickable);
  return first === undefined ? [] : [first.channel];
}

export interface AccountCommunicationDialogProps {
  accountId: string;
  onClose: () => void;
  /** The utility's own today, ISO. An INPUT, never a clock this component
   *  reads — `BR-TEN-043`, and the page holds the tenant's date. */
  today: string;
  /** IS-8's regional date format, held by the page like every other form on
   *  this screen — never guessed from a browser locale. */
  dateFormat: RegionalDateFormat;
  // ⛔ `initialTab` is DELETED (`DEF-GOV-10106`): neither host (the account
  // rail, the move-in details) ever opened the dialog on its history view, so
  // G13 named it dead UI. The dialog opens on compose and the tab switch
  // still reaches the history.
}

export function AccountCommunicationDialog(props: AccountCommunicationDialogProps) {
  const { t } = useTranslation();
  const [tab, setTab] = useState<CommunicationTab>("compose");
  const [form, setForm] = useState<CommunicationForm | null>(null);
  // ⚠ Minted ONCE per dialog, not once per submit: it is the idempotency key
  // (CLAUDE.md rule 6), so a double-clicked commit meets its own row. A new
  // message needs a new dialog, which is what Close and re-open is.
  const [messageId] = useState(() => crypto.randomUUID());
  const [kind, setKind] = useState(KIND_COURTESY);
  const [channels, setChannels] = useState<string[]>([]);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [signedBy, setSignedBy] = useState("");
  //: The template the words came from, or "" for the clerk's own. Held so the
  //: control shows what was picked; the BODY is what is queued either way.
  const [fromTemplate, setFromTemplate] = useState("");
  const [when, setWhen] = useState<"now" | "on">("now");
  const [onDate, setOnDate] = useState(props.today);

  useEffect(() => {
    let live = true;
    void getAccountCommunication(props.accountId).then((answer) => {
      if (!live) {
        return;
      }
      setForm(answer);
      setChannels(defaultChannels(answer.channels));
      setSignedBy(answer.customer_name === null ? "" : "");
    });
    return () => {
      live = false;
    };
  }, [props.accountId]);

  const kicker = form === null ? "" : [form.customer_name, form.account_no].filter(Boolean).join(" · ");
  const title = t("customers.account.communication.title");

  const tabs = (
    <div className="mb-4 flex gap-4 border-b border-divider" role="tablist">
      {COMMUNICATION_TABS.map((one) => (
        <button
          key={one}
          type="button"
          role="tab"
          aria-selected={tab === one}
          data-communication-tab={one}
          onClick={() => setTab(one)}
          className={
            tab === one
              ? "-mb-px border-b-2 border-accent px-1 pb-2 text-base font-semibold text-accent"
              : "-mb-px border-b-2 border-transparent px-1 pb-2 text-base text-neutral-600 hover:text-text"
          }
        >
          {t(`customers.account.communication.tab.${one}`)}
        </button>
      ))}
    </div>
  );

  if (tab === "history") {
    return (
      <ModalShell title={title} kicker={kicker} onClose={props.onClose}>
        <div className="modal-body">
          {tabs}
          <CommunicationHistory accountId={props.accountId} />
        </div>
        {/* ⚠ `className="btn"` HERE UNTIL 2026-09-13, AND IT RENDERED AS BARE
            TEXT (PO: *"also buttons at the botttom"*).

            ⚠ **THE FIRST DIAGNOSIS WRITTEN HERE WAS WRONG AND IS CORRECTED
            (DEF-CUS-5156).** It said `.btn` was declared in a stylesheet
            nothing on this page imports. **It is loaded.** Vite emits ONE
            stylesheet for the whole app — `dist/assets/index-*.css`, 164K,
            and `.btn` is in it — so a CSS file's importer decides nothing
            about whether its rules are live.

            **The real cause is narrower and worth more.** `.btn`'s base rule
            is deliberately invisible — `background: transparent`, `border: 1px
            solid transparent` — and CR-018 Phase 4a (2026-08-20) DELETED the
            six variant rules that used to paint it. Since that day the look
            lives only in `buttonKit`'s Tailwind classes, which the kit's
            `Button` applies. **So a bare `className="btn"` is a ghost button
            BY DESIGN**, and the fault is not a missing stylesheet but reaching
            past the kit — B14 rule 36's clause exactly.

            A product-wide sweep found this was the ONLY bare-`btn` site, so
            the fault was one element and not a class of them. `AuditLogPage`
            was already the precedent for this very footer, and `forms.close`
            is the shared key, so no twelfth spelling of *Close* was minted. */}
        <div className="modal-foot">
          <Button variant="secondary" onClick={props.onClose}>
            {t("forms.close")}
          </Button>
          <Button variant="secondary" onClick={() => setTab("compose")}>
            {t("customers.account.communication.tab.compose")}
          </Button>
        </div>
      </ModalShell>
    );
  }

  const refused = form?.kinds.find((one) => one.kind === kind && !one.allowed);
  const picked = (form?.channels ?? []).filter((one) => channels.includes(one.channel));
  const schema = z.object({
    body: z.string().trim().min(1, t("customers.account.communication.error.bodyEmpty")),
    channels: z.array(z.string()).min(1, t("customers.account.communication.error.noChannel")),
  });

  return (
    <FormModal
      title={title}
      kicker={kicker}
      schema={schema}
      values={{ body, channels }}
      submitLabel={t("customers.account.communication.queue")}
      // ⚠ `BR-SHL-025` through the frame's own prop rather than a bespoke
      // disabled button: the FORM stays live and only the COMMIT is refused,
      // so a clerk who picked a regulated kind reads why and can pick another.
      commitBlocked={
        refused === undefined
          ? undefined
          : t(`customers.account.communication.refused.${refused.refusal}`)
      }
      onClose={props.onClose}
      onSubmit={async () => {
        const queued = await queueAccountMessage(props.accountId, {
          message_id: messageId,
          kind,
          channels,
          subject,
          body,
          signed_by: signedBy,
          on_date: when === "now" ? props.today : onDate,
        });
        return {
          ok: true,
          toast: t(
            queued.outcome === ALREADY_QUEUED
              ? "customers.account.communication.toast.already"
              : "customers.account.communication.toast.queued",
          ),
        };
      }}
    >
      {tabs}
      <Section label={t("customers.account.communication.section.what")}>
        <SelectField
          id="communication-kind"
          label={t("customers.account.communication.field.kind")}
          value={kind}
          onChange={setKind}
          required
          options={(form?.kinds ?? []).map((one) => ({
            value: one.kind,
            label: t(`customers.account.communication.kind.${one.kind}`),
          }))}
        />
      </Section>

      <Section label={t("customers.account.communication.section.who")}>
        <TextField
          id="communication-customer"
          label={t("customers.account.communication.field.customer")}
          value={form?.customer_name ?? ""}
          onChange={() => undefined}
          readOnly
        />
        <TextField
          id="communication-language"
          label={t("customers.account.communication.field.language")}
          value={form?.language ?? ""}
          onChange={() => undefined}
          readOnly
          help={t("customers.account.communication.help.language")}
        />
        <ChannelTable
          channels={form?.channels ?? []}
          picked={channels}
          onToggle={(channel) =>
            setChannels((held) =>
              held.includes(channel) ? held.filter((one) => one !== channel) : [...held, channel],
            )
          }
        />
      </Section>

      <Section label={t("customers.account.communication.section.message")}>
        {/* ⚠ **THE UTILITY'S OWN AGREED WORDING, FIRST IN THE SECTION BECAUSE
            IT IS WHAT FILLS THE TWO FIELDS BELOW IT.** PO, 2026-09-13: *"it
            should also have ready to use messages from our Notification rules -
            user will not write it every time"*. The list is SERVED — resolved
            for this account's language through the same `BR-BIL-025` order the
            dispatcher uses — so a class published, re-worded or archived on
            Settings → Templates changes this picker with no release here.
            Absent when the tenant has published nothing, rather than an empty
            control a clerk would read as broken. */}
        {(form?.templates ?? []).length > 0 ? (
          <SelectField
            id="communication-template"
            label={t("customers.account.communication.field.template")}
            value={fromTemplate}
            placeholder={t("customers.account.communication.template.none")}
            onChange={(code) => {
              setFromTemplate(code);
              const filled = applyTemplate(form?.templates ?? [], code, { subject, body });
              setSubject(filled.subject);
              setBody(filled.body);
            }}
            options={(form?.templates ?? []).map((one) => ({
              value: one.code,
              label: one.name,
            }))}
          />
        ) : null}
        <TextField
          id="communication-subject"
          label={t("customers.account.communication.field.subject")}
          value={subject}
          onChange={setSubject}
          help={t("customers.account.communication.help.subject")}
        />
        <TextField
          id="communication-signed"
          label={t("customers.account.communication.field.signedBy")}
          value={signedBy}
          onChange={setSignedBy}
        />
        <TextField
          id="communication-body"
          label={t("customers.account.communication.field.body")}
          value={body}
          onChange={setBody}
          required
          multiline
        />
      </Section>

      <Section label={t("customers.account.communication.section.when")}>
        <SelectField
          id="communication-when"
          label={t("customers.account.communication.field.when")}
          value={when}
          onChange={(value) => setWhen(value === "on" ? "on" : "now")}
          options={[
            { value: "now", label: t("customers.account.communication.when.now") },
            { value: "on", label: t("customers.account.communication.when.on") },
          ]}
        />
        {when === "on" ? (
          <DatePickerField
            id="communication-date"
            label={t("customers.account.communication.field.date")}
            value={onDate}
            onChange={setOnDate}
            dateFormat={props.dateFormat}
            help={t("customers.account.communication.help.date")}
          />
        ) : null}
      </Section>

      <Recap channels={picked} signedBy={signedBy} when={when} date={onDate} />
    </FormModal>
  );
}

/** A block heading. B14 rule 39's 16px between BLOCKS — the fields inside keep
 *  the kit's own 20px, which is why they are composed and not re-spaced. */
function Section(props: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-4">
      <p className="mb-2 text-xs font-bold uppercase tracking-wide text-accent">{props.label}</p>
      {props.children}
    </div>
  );
}

/**
 * CHANNEL · GOES TO · ON FILE? — and the column the drawing could not have.
 *
 * ⚠ **A CHANNEL THAT DOES NOT DELIVER SAYS SO IN ITS OWN ROW.** Without it this
 * table would show a tickable Email over an address nothing will ever write to
 * (`BR-NOT-013`), and the clerk would put the phone down believing the customer
 * had been emailed.
 */
/**
 * What the two message fields become when a clerk picks a ready-made message.
 *
 * Exported because it is the only DECISION in the picker, and a decision inside
 * an `onChange` is a decision no test can reach. Two rules, and the second is
 * the one worth protecting:
 *
 *  * picking nothing — the placeholder — CHANGES NOTHING. It is how a clerk
 *    goes back to their own words, not a command to erase them;
 *  * an SMS class carries NO SUBJECT, so picking one leaves a subject the clerk
 *    has already typed exactly where it is. Writing `""` over it would be a
 *    silent deletion, and the field is the one place the clerk cannot see the
 *    template's shape to know why.
 */
export function applyTemplate(
  templates: CommunicationTemplate[],
  code: string,
  held: { subject: string; body: string },
): { subject: string; body: string } {
  const one = templates.find((each) => each.code === code);
  if (one === undefined) {
    return held;
  }
  return {
    subject: one.subject === "" ? held.subject : one.subject,
    body: one.body,
  };
}

export function ChannelTable(props: {
  channels: CommunicationChannel[];
  picked: string[];
  onToggle: (channel: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <table className="w-full text-base" data-communication-channels="">
      <thead>
        <tr className="border-b border-divider text-left text-xs uppercase tracking-wide text-neutral-600">
          <th className="w-8 px-3 py-2" />
          <th className="px-3 py-2">{t("customers.account.communication.column.channel")}</th>
          <th className="px-3 py-2">{t("customers.account.communication.column.goesTo")}</th>
          <th className="px-3 py-2">{t("customers.account.communication.column.state")}</th>
        </tr>
      </thead>
      <tbody>
        {props.channels.map((one) => (
          <tr key={one.channel} className="border-b border-divider" data-channel={one.channel}>
            <td className="px-3 py-2">
              <input
                type="checkbox"
                aria-label={t(`customers.account.communication.channel.${one.channel}`)}
                checked={props.picked.includes(one.channel)}
                disabled={!tickable(one)}
                onChange={() => props.onToggle(one.channel)}
              />
            </td>
            <td className="px-3 py-2">
              {t(`customers.account.communication.channel.${one.channel}`)}
            </td>
            <td className="px-3 py-2">
              {one.address ?? (
                <span className="text-neutral-600">
                  {t("customers.account.communication.noAddress")}
                </span>
              )}
            </td>
            <td className="px-3 py-2">
              {one.delivers
                ? t("customers.account.communication.state.delivers")
                : t("customers.account.communication.state.waits")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** *What pressing the button will do* — the drawing's REVIEW block, and its
 *  bold pair kept word for word because it is the true sentence. */
export function Recap(props: {
  channels: CommunicationChannel[];
  signedBy: string;
  when: "now" | "on";
  date: string;
}) {
  const { t } = useTranslation();
  const none = props.channels.length === 0;
  return (
    <div className="mb-4" data-communication-recap="">
      <ConsequenceBox
        tone="check"
        title={t("customers.account.communication.recap.title")}
        body={
          none
            ? t("customers.account.communication.recap.nothing")
            : t("customers.account.communication.recap.queued")
        }
        tag={t("customers.account.communication.recap.tag")}
        data-consequence="communication"
      />
    </div>
  );
}

/**
 * *What has already gone out* — `GET /outbound` filtered to this account.
 *
 * ⚠ **NOT ONE LINE OF NEW SERVER CODE, AND THAT IS THE DESIGN.** The queue list
 * already carries the capability row's search and filters, the ratified *failed
 * and bounced first* sort, and server pagination. The drawing says so itself:
 * *"Resend and Requeue are real endpoints; composing a new message from an
 * account is the part that does not exist."*
 *
 * ⚠ **AND IT IS PAGED (B14 rule 16, `NFR-3`).** `CLAUDE.md` counts four live
 * unpaginated lists that named the old 3,000-connection ceiling as their excuse;
 * a long-lived account's correspondence is not the fifth.
 */
export function CommunicationHistory(props: { accountId: string }) {
  const { t } = useTranslation();
  const [rows, setRows] = useState<OutboundRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(50);

  useEffect(() => {
    let live = true;
    void getOutbound({ page, per, filters: { account_id: props.accountId } }).then((answer) => {
      if (!live) {
        return;
      }
      setRows(answer.results);
      // `Paginated.count` is the TRUE total, which is what makes
      // *"Showing 1-50 of N"* a true sentence (B14 rule 16).
      setTotal(answer.count);
    });
    return () => {
      live = false;
    };
  }, [props.accountId, page, per]);

  if (rows !== null && rows.length === 0) {
    // The drawing's empty case, and `correspondence_reads`' instruction: a
    // sentence naming what will fill the page, never column heads over nothing.
    return <p className="text-base text-neutral-600">{t("customers.account.communication.empty")}</p>;
  }

  return (
    <div data-communication-history="">
      <table className="w-full text-base">
        <thead>
          <tr className="border-b border-divider text-left text-xs uppercase tracking-wide text-neutral-600">
            <th className="px-3 py-2">{t("customers.account.communication.column.queuedOn")}</th>
            <th className="px-3 py-2">{t("customers.account.communication.column.what")}</th>
            <th className="px-3 py-2">{t("customers.account.communication.column.channel")}</th>
            <th className="px-3 py-2">{t("customers.account.communication.column.goesTo")}</th>
            <th className="px-3 py-2">{t("customers.account.communication.column.state")}</th>
          </tr>
        </thead>
        <tbody>
          {(rows ?? []).map((row) => (
            <tr key={row.id} className="border-b border-divider" data-outbound-row={row.id}>
              <td className="px-3 py-2">{row.queued_at?.slice(0, 10) ?? ""}</td>
              <td className="px-3 py-2">
                {/* B14 rule 31 — the template CODE is a code, never the value a
                    clerk reads, so it resolves through the catalogue and falls
                    back to the honest generic rather than to an identifier.
                    DEF-CUS-10653 (PO D2 A) — a row with NO class (a printed or
                    portal bill, laid out by the bill template) is named by its
                    source kind, *Bill*, rather than "A message". */}
                {row.template_code === null
                  ? t(`notifications.queue.source.${row.source_type}`, {
                      defaultValue: t("customers.account.communication.what.unknown"),
                    })
                  : t(`notifications.templateClass.${row.template_code}`, {
                      defaultValue: t("customers.account.communication.what.unknown"),
                    })}
              </td>
              <td className="px-3 py-2">
                {t(`customers.account.communication.channel.${row.channel}`, {
                  defaultValue: row.channel,
                })}
              </td>
              <td className="px-3 py-2">
                {row.recipient_address ?? (
                  <span className="text-neutral-600">
                    {t("customers.account.communication.noAddress")}
                  </span>
                )}
              </td>
              {/* ⚠ The QUEUE's own status, never a delivery claim. `delivered`
                  and `bounced` cannot be written on this deployment. */}
              <td className="px-3 py-2">
                {t(`customers.account.communication.status.${row.status}`, {
                  defaultValue: row.status,
                })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <ListPager total={total} page={page} per={per} onPage={setPage} onPer={setPer} />
    </div>
  );
}
