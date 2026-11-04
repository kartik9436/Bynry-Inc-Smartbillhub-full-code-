// ── Trace ──────────────────────────────────────────────
// Story:    US-PAY-016 (returned mail: mark returned → bad-address flag →
//           needs-attention → paper suppressed) · US-NOT-014 (the endpoint
//           both halves call)
//           Screens: S30 (a bill's delivery row — the single mark) ·
//           S35 (the bulk mark over a Tuesday's stack, opened from S32)
// Rules:    BR-PAY-018 (VERBATIM: "Returned mail: delivery record marked
//           returned (single/bulk) → account bad-address flag →
//           needs-attention queue + banner → paper suppressed until address
//           verified (config); balances unaffected; audited.") ·
//           BR-NOT-005 (suppression holds the QUEUE ROW, never deletes it) ·
//           BR-BIL-016 (an email that did not arrive is a provider BOUNCE, not
//           returned post) · BR-TEN-043 (the business date is typed by the
//           clerk — this file reads no clock) · BR-SHL-020 (plain-language
//           failure) · BR-SHL-025 (a control this deployment cannot honour
//           renders DISABLED WITH its reason)
// ───────────────────────────────────────────────────────
// THE TUESDAY CHORE, AND THE ONE THING THAT MUST NOT CHANGE WHILE IT HAPPENS.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS
// ══════════════════════════════════════════════════════════════════════════
// `10-scripts/gates/surface_debt.txt` carried the sentence this closes:
// *"US-PAY-016 returned mail is written by `apps/payments/returned_mail.py` and
// its screens are S30's delivery rows and S35's bulk-mark, both
// billing/notifications-owned and unbuilt (notifications' own
// `POST /deliveries/returned` landed 2026-08-16 and does not draw them)."*
//
// So a clerk holding a stack of envelopes the post office sent back had a
// complete, tested, audited write path and **nowhere to type it**. Hard-won
// law 2, on a chore that happens every week.
//
// ══════════════════════════════════════════════════════════════════════════
// ONE MODULE FOR TWO SCREENS, DELIBERATELY
// ══════════════════════════════════════════════════════════════════════════
// The single mark lives on a BILL (billing's screen) and the bulk mark lives on
// PAYMENTS' summary. Both obey the same four rules — paper only, a date the
// clerk types, one event per envelope, balances untouched — and a rule written
// twice is a rule that will be enforced once. The BillDetailPage imports
// `MarkReturnedModal` from here for exactly that reason.
//
// ══════════════════════════════════════════════════════════════════════════
// FOUR THINGS THIS SURFACE REFUSES TO DO
// ══════════════════════════════════════════════════════════════════════════
//   1. **It never reads a clock.** BR-TEN-043: Tuesday's stack is marked as
//      TUESDAY even when it is worked on Wednesday. The date is a required
//      field with no default invented here — S32 hands down the business day
//      the tab is already showing, and the bill panel asks outright.
//   2. **It never offers the action on an email row.** An email that did not
//      arrive is a provider BOUNCE (BR-BIL-016) and no adapter exists to report
//      one; letting staff type it would put a hand-typed value where an ESP's
//      answer belongs. The control renders DISABLED with that sentence
//      (BR-SHL-025) rather than being hidden, so the reason is on the screen.
//   3. **It never claims paper was suppressed.** BR-PAY-018 suppresses paper
//      "per tenant config" and BR-NOT-005 holds the queue row — but the `held`
//      marker's only writer is the dispatcher, which is OUT OF THIS RELEASE by
//      PO ruling. The result panel says the address is flagged and says nothing
//      about post being stopped.
//   4. **It never implies money moved.** The server answers
//      `balances_affected: false` and this panel prints it, because "we marked
//      14 envelopes" and "we did not touch 14 balances" are two different
//      reassurances and a clerk deserves the second one in writing.
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getOutbound, markDeliveriesReturned } from "@/api/endpoints";
import type { OutboundRow } from "@/api/endpoints";
import { DateCell, formatDate } from "@/components/DateCell";
import { DatePickerField, FormModal } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import type { RegionalDateFormat } from "@/components/DateCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
// The address rule is notifications' own and is REUSED, not rewritten:
// BR-BIL-036 distinguishes "no address on file" from "nobody looked", and a
// second copy of that distinction is a second place for it to go wrong.
import { addressCell } from "@/features/notifications/SettingsNotificationsTab";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { z } from "zod";

import "./payments.css";

/** The queue's paper channel. Returned post is a PAPER event and only a paper
 *  event (US-PAY-016 TC-5); the value is notifications' own `CHANNEL_PRINT`. */
export const PAPER_CHANNEL = "pdf_print";

/** The stack still to work: paper, not yet marked returned. `f.returned=false`
 *  is a server filter (US-PAY-016), so the browser never pages through every
 *  letter the utility has posted looking for this Tuesday's fourteen. */
export const returnedMailStackQueryKey = () => ["outbound", "returned-mail-stack"] as const;

/** What the outcome panel states, in the order a clerk needs it. */
export interface MarkReturnedOutcome {
  returned_on: string;
  marked: { message_id: string; account_id: string | null; channel: string }[];
  flagged_accounts: { account_id: string | null; created: boolean }[];
  refused: { code: string; detail?: string | null; [key: string]: unknown }[];
  balances_affected: boolean;
}

/**
 * Can THIS delivery row be marked returned, and if not, why not — in a sentence
 * a clerk reads rather than a rule id.
 *
 * Pure, exported and tested directly: it is the whole of the enable/disable
 * decision on both screens, and BR-SHL-025 requires the reason to travel with
 * the refusal rather than being left as an unexplained grey button.
 */
export function markReturnedRefusal(
  row: { channel: string; returned_at: string | null },
  t: Translator,
): string | null {
  if (row.channel !== PAPER_CHANNEL) {
    return t("payments.returnedMail.notPaper");
  }
  if (row.returned_at !== null) {
    return t("payments.returnedMail.alreadyMarked");
  }
  return null;
}

/** The date is REQUIRED and is never defaulted silently (BR-TEN-043). */
export function markReturnedSchema(t: Translator) {
  return z.object({
    returned_on: z.string().min(1, t("payments.returnedMail.dateRequired")),
    message_ids: z.array(z.string()).min(1, t("payments.returnedMail.selectionRequired")),
  });
}

/**
 * WHICH piece a pick box marks, in the words its row already shows: the
 * address it went to, the account number, the day it was queued.
 *
 * All three, because one of them is not enough: the stack lists every
 * unreturned paper piece, so one account's August and September bills sit in
 * it together at the same address with the same number — only the date tells
 * them apart. Each absence is said in the row's own words (BR-BIL-036 for the
 * address, *"No account number"* for the account), and the account id is never
 * part of it (B14 rule 31).
 */
export function pieceName(
  row: OutboundRow,
  t: Translator,
  dateFormat: RegionalDateFormat,
): string {
  const address = addressCell(row);
  return [
    address.text ?? (address.reasonKey !== null ? t(address.reasonKey) : null),
    row.account_no ?? t("payments.row.noAccountNo"),
    row.queued_at !== null ? formatDate(row.queued_at, "UTC", dateFormat) : null,
  ]
    .filter((part): part is string => part !== null && part !== "")
    .join(" · ");
}

// ── The single mark — S30's delivery row ───────────────────────────────────

/**
 * One envelope, from the bill it was posted with.
 *
 * The bill's own delivery panel is where a clerk holding THAT letter already
 * is, which is why US-PAY-016 §1 names it: *"Entry: S30 delivery rows / S35
 * bulk-mark."*
 */
export function MarkReturnedModal(props: {
  messageId: string;
  /** The clerk's business day, proposed into the field and always overridable. */
  proposedDate: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  onClose: () => void;
  onMarked: (outcome: MarkReturnedOutcome) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const [returnedOn, setReturnedOn] = useState("");

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const outcome = await markDeliveriesReturned(
        [props.messageId],
        returnedOn,
        props.client ?? api,
      );
      props.onMarked(outcome);
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
      title={t("payments.returnedMail.single.title")}
      kicker={t("payments.returnedMail.single.kicker")}
      schema={markReturnedSchema(translate)}
      values={{ returned_on: returnedOn, message_ids: [props.messageId] }}
      submitLabel={t("payments.returnedMail.single.submit")}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <DatePickerField
        id="returned_on"
        label={t("payments.returnedMail.dateLabel")}
        value={returnedOn}
        onChange={setReturnedOn}
        prefill={props.proposedDate}
        dateFormat={props.dateFormat}
        required
      />
      {/* The guarantee, on the form and not only in the response: a clerk about
          to flag a customer's address should be able to read that nothing about
          what they owe is changing (BR-PAY-018 "balances unaffected"). */}
      <p className="met-panel-hint">{t("payments.returnedMail.invariance")}</p>
    </FormModal>
  );
}

// ── The bulk mark — S35, over a Tuesday's stack ────────────────────────────

/**
 * J18's 09:00: **fourteen envelopes, one action.**
 *
 * The list is the server's `f.channel=pdf_print&f.returned=false` — the pile
 * still to work — because a screen that listed everything ever posted would
 * make a clerk hunt for their own fourteen inside nine hundred.
 *
 * **Per-row results, never one boolean.** A stack where one piece was already
 * marked is a normal Tuesday: the other thirteen must still land, and the
 * outcome panel names what was refused and why (`apps/payments/returned_mail`
 * takes exactly this posture from the other side).
 */
export function BulkMarkReturnedModal(props: {
  /** The business day the calling screen is already showing (BR-TEN-043). */
  proposedDate: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  onClose: () => void;
  onMarked: (outcome: MarkReturnedOutcome) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const [returnedOn, setReturnedOn] = useState("");
  const [selected, setSelected] = useState<string[]>([]);

  const stackQuery = useQuery({
    queryKey: returnedMailStackQueryKey(),
    queryFn: () =>
      getOutbound(
        { filters: { channel: PAPER_CHANNEL, returned: "false" }, per: 200 },
        client,
      ),
    retry: false,
  });
  const stack: OutboundRow[] = stackQuery.data?.results ?? [];

  function toggle(id: string, on: boolean): void {
    setSelected((current) =>
      on ? [...current, id] : current.filter((candidate) => candidate !== id),
    );
  }

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      const outcome = await markDeliveriesReturned(selected, returnedOn, client);
      props.onMarked(outcome);
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
      title={t("payments.returnedMail.bulk.title")}
      kicker={t("payments.returnedMail.bulk.kicker")}
      schema={markReturnedSchema(translate)}
      values={{ returned_on: returnedOn, message_ids: selected }}
      submitLabel={t("payments.returnedMail.bulk.submit", { count: selected.length })}
      onSubmit={handleSubmit}
      onClose={props.onClose}
    >
      <DatePickerField
        id="returned_on"
        label={t("payments.returnedMail.dateLabel")}
        value={returnedOn}
        onChange={setReturnedOn}
        prefill={props.proposedDate}
        dateFormat={props.dateFormat}
        required
      />
      {stackQuery.isError ? (
        // BR-SHL-020: the server's own sentence, never this screen's guess.
        <p className="met-panel-hint" role="alert">
          {apiErrorText(stackQuery.error, translate)}
        </p>
      ) : stackQuery.data === undefined ? (
        <LoadingSkeleton variant="table" />
      ) : stack.length === 0 ? (
        // A18 zero state, and it is a REAL answer: every paper row has already
        // been marked, or none has been queued. Never an empty table, which
        // would read as "the list is broken".
        <p className="met-panel-hint">{t("payments.returnedMail.bulk.empty")}</p>
      ) : (
        <div className="pay-returned-stack">
          <p className="met-panel-hint">
            {t("payments.returnedMail.bulk.selected", { count: selected.length })}
          </p>
          <PlainTable>
            <thead>
              <tr>
                <th>{t("payments.returnedMail.col.pick")}</th>
                <th>{t("payments.returnedMail.col.recipient")}</th>
                <th>{t("payments.returnedMail.col.account")}</th>
                <th>{t("payments.returnedMail.col.queuedAt")}</th>
              </tr>
            </thead>
            <tbody>
              {stack.map((row) => (
                <tr key={row.id}>
                  <td>
                    {/* ⚠ **NO VISIBLE WORDS BESIDE THE BOX, AND A NAME THAT SAYS
                        WHICH PIECE** (`DEF-PAY-6344`). This cell used to be
                        `CheckboxField` with the label *"Mark this piece"* — the
                        same three words printed beside every box under a column
                        already headed PICK, and the same accessible name nine
                        times over, so a screen-reader user could not tell which
                        envelope a box marked. The name is now the row itself —
                        address · account number · queued date — which is also
                        what tells two of one account's monthly bills apart.
                        `aria-label` over a native box is the product's row-select
                        pattern (`PaymentsPage`, `AssetRegistryPage`,
                        `OrdersPage`); `CheckboxField` always prints its label,
                        and it has no hidden-label option to reach for. */}
                    <input
                      type="checkbox"
                      id={`piece_${row.id}`}
                      aria-label={t("payments.returnedMail.pickLabel", {
                        piece: pieceName(row, translate, props.dateFormat),
                      })}
                      checked={selected.includes(row.id)}
                      onChange={(event) => toggle(row.id, event.target.checked)}
                    />
                  </td>
                  <td>
                    {/* BR-BIL-036 made visible: an absent address is STATED,
                        and WHICH absence it is — "no address on file" and
                        "nobody looked" are different facts. */}
                    {addressCell(row).text ?? (
                      <span className="cus-awaits">{t(addressCell(row).reasonKey ?? "")}</span>
                    )}
                  </td>
                  <td>
                    {/* ⛔ THE NUMBER, NEVER THE ID (B14 rule 31 — PO 2026-08-30,
                        *"no Databse ID on screen - that is a rule"*). Until
                        `DEF-PAY-6344` this cell printed `row.account_id`, so the
                        PO read `01a07fa5-1034-71f7-995c-05da83d1c972` on every
                        row of the deployed build. An absent number is STATED —
                        the words the collections ladder and outstandings already
                        use — and there is deliberately no fallback to the id,
                        which would be the same defect with extra steps. */}
                    {row.account_no ?? (
                      <span className="cus-awaits">{t("payments.row.noAccountNo")}</span>
                    )}
                  </td>
                  <td>
                    {row.queued_at !== null ? (
                      <DateCell
                        value={row.queued_at}
                        timeZone="UTC"
                        dateFormat={props.dateFormat}
                      />
                    ) : (
                      <span className="cus-awaits">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}
      <p className="met-panel-hint">{t("payments.returnedMail.invariance")}</p>
    </FormModal>
  );
}

// ── The outcome, said in a clerk's words ───────────────────────────────────

/**
 * What the mark actually did — and the two things it did NOT do.
 *
 * Rendered after either modal closes. It states the count marked, the accounts
 * now flagged, every refusal WITH ITS REASON, and BR-PAY-018's invariance in
 * plain English. A toast saying "14 marked" would hide the one that was not.
 */
export function ReturnedMailOutcome(props: { outcome: MarkReturnedOutcome }) {
  const { t } = useTranslation();
  const { outcome } = props;
  return (
    <Panel className="pay-returned-outcome" as="section" role="status">
      <h3>{t("payments.returnedMail.outcome.title")}</h3>
      <p>
        {t("payments.returnedMail.outcome.marked", {
          count: outcome.marked.length,
          accounts: outcome.flagged_accounts.length,
          date: outcome.returned_on,
        })}
      </p>
      {outcome.refused.length > 0 && (
        <ul className="pay-returned-refused">
          {outcome.refused.map((refusal, index) => (
            <li key={`${refusal.code}-${index}`}>
              {/* The SERVER's own sentence — `delivery_ops` writes a
                  clerk-readable `detail` on every refusal. The fallback names
                  the code rather than inventing a reason this screen does not
                  know (BR-SHL-020). */}
              {refusal.detail ?? t("payments.returnedMail.refusalUnnamed", { code: refusal.code })}
            </li>
          ))}
        </ul>
      )}
      {/* Printed off the SERVER's own field rather than asserted by this
          screen: if a future build ever answered `true`, the sentence would
          change with it instead of lying confidently. */}
      <p className="met-panel-hint">
        {outcome.balances_affected
          ? t("payments.returnedMail.outcome.balancesTouched")
          : t("payments.returnedMail.invariance")}
      </p>
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-PAY-016@EP-PAY-04 (04-docs/05-modules/08-payments/06-epics/EP-PAY-04-outstandings-collections.md US-PAY-016 §1/§3/§5 · 08-payments/02-business-rules.md BR-PAY-018 · 10-notifications/02-business-rules.md BR-NOT-005 · 08-qa/01-e2e/journeys/J18-returned-mail-tuesday.md · 05-prototype/UtilityBilling.html)
// generated: 2026-08-16 by story-coder (returned-mail surface lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest✔ (every case RED-PROVED first — see the lane report) · run_gates✔
// exceptions: (1) NO SUPPRESSION IS CLAIMED ANYWHERE ON THIS SURFACE. BR-PAY-018 suppresses paper per tenant config and BR-NOT-005 holds the queue row, and the `held` marker's only writer is the dispatcher (US-NOT-002), which is OUT OF THIS RELEASE by PO ruling. The panel reports the flag and says nothing about post being stopped — a screen implying letters were held would be a claim about a customer's mail that nothing in this build makes true. (2) NO CLOCK. The date is required and is proposed from the CALLING screen's business day; this file never reads `new Date()` (BR-TEN-043). (3) THE PROTOTYPE DRAWS NO RETURNED-MAIL SCREEN — `05-prototype/UtilityBilling.html` has no returned-post surface at all (its "returned" strings are all NSF returned CHEQUES, which are payments' money flow and a different story entirely), so the layout here follows the S35 modal family's own conventions rather than a prototype panel. REPORTED rather than invented silently. (4) ⚠ REWRITTEN 2026-09-23 (`DEF-PAY-6344`, PO on the deployed build: *"this modal is showing db keys"*). THE ACCOUNT COLUMN SHOWS THE ACCOUNT NUMBER — `GET /outbound` serves `account_no` beside `account_id`, read for the whole page in one statement through `apps/notifications/customers_seam.py` — and where there is none it says *"No account number"*, never the id. Until that day this line read *"THE ACCOUNT COLUMN SHOWS AN ID, not a customer name"* and defended it with BR-AUD-006, and the defence never held: BR-AUD-006 governs PII inside AUDIT PAYLOADS, not a list; the choice it framed — the id or the customer's full name and postal address — left out the account NUMBER, which is neither and satisfies both rules; and the SENT TO column on this same modal already printed the street address. It was written 2026-08-16, before B14 rule 31 was ratified (2026-08-30), and became a defect that day; `DEF-1122` named it on 2026-08-27. ⚠ AN `exceptions:` LINE RECORDS WHERE A BUILD DEPARTS FROM A DRAWING. IT CANNOT OVERRULE A RATIFIED RULE — a departure from one is a defect row. (5) THE DATE FIELD CARRIES NO HELP LINE (`DEF-PAY-6344`, B14 rule 33). It read *"Tuesday's stack is marked as Tuesday, even when you work through it on Wednesday."* — fourteen words saying WHY the date is the stack's own, which is RATIONALE and is zero words on screen. The label *"Date it came back"* is the instruction; the why lives in box 1 above and in BR-TEN-043. (6) THE PICK BOX HAS NO VISIBLE LABEL and its accessible name is the row — address · account number · queued date — so a screen reader can tell nine boxes apart (`DEF-PAY-6344`)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
