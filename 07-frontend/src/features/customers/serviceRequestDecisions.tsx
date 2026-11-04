// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 wave 2 — the request's own screen, rebuilt to its
//           drawing. PO ruling 2026-09-15: *"document screens are benchmark"*,
//           and **the head carries the three decisions as MODALS**.
//           ⚠ **AMENDED 2026-09-20 — PO ratification, *"this is correct"*:
//           THE APPROVE DIALOG'S OUTCOMES ARE GATED BY THE EVIDENCE** (decision
//           log, `SEVEN PO RATIFICATIONS FROM ONE SITTING`, §2). Each radio
//           now carries its own verdict from `decision.options`; three of the
//           five can be DISABLED WITH THEIR REASON on one request, and none of
//           the five is ever hidden.
// Defects:  DEF-CUS-5389 (Refuse ships as one free-text box; Ask for more is
//           not a dialog at all and sends one canned sentence to everybody) ·
//           DEF-CUS-5995 (the five outcomes rendered flat — the server's
//           per-option verdicts were served and never read)
// Rules:    B14 rule 41 (the product matches the blueprint) · rule 42 (a screen
//           is built from the drawing AS AN IMAGE) · rule 38 (where a drawing
//           and our UI rules disagree about how a FORM is built, the UI rules
//           win — so the footer, the close control and the absent sub-line are
//           the kit's) · rule 37 (a drawn figure is an illustration) · rule 33
//           (a consequence before an irreversible act is ≤ 6 words a sentence,
//           at most two; rationale is ZERO words on screen) · rule 32 (no code
//           in clerk-facing copy) · rule 31 (no database id on screen) ·
//           rule 11 (a form writing money or service state shows a "what this
//           will do" box) · rule 21 (Tailwind utilities, no stylesheet class)
//           · **BR-SHL-025 (a control this state cannot honour is DISABLED
//           WITH ITS REASON, never hidden)** · BR-CUS-090 · BR-CUS-091 ·
//           BR-NOT-013
// Drawing:  05-prototype/02 Accounts Menu Blueprint.pdf, read AS IMAGES at
//           scale 2 — p083/p084 Approve · p084/p085 Refuse · p085/p086 Ask.
// Tests:    ServiceRequestDetailPage.test.tsx · ServiceRequestDetailPage.dom.test.tsx
//           · serviceRequestApproveVerdicts.dom.test.tsx (the per-radio
//           verdicts, in a real DOM — `disabled` is a PROPERTY and a
//           static-markup grep cannot tell one greyed radio from another)
// ───────────────────────────────────────────────────────
//
// THE THREE DECISIONS A CLERK MAKES ON AN APPLICATION, EACH AS THE DIALOG THE
// BLUEPRINT DRAWS IT AS.
//
// ⚠ **THE RATIONALE THE DRAWING PRINTS IS NOT ON THESE SCREENS, AND THAT IS
// RULE 33, NOT AN OMISSION.** Every frame carries a red or grey note explaining
// the design to the READER OF THE BLUEPRINT — *"Nothing is preselected,
// deliberately. The resolver matched this address to PR-0731 exactly, and that
// is EVIDENCE — not the decision."*, *"Refusing does not undo the money … a
// refusal that silently wrote off a receipt is how a cash drawer stops
// reconciling."*, *"This is why waiting on is a column and not a state."* B14
// rule 33's last clause is explicit: **rationale — why the product works this
// way — is ZERO WORDS ON SCREEN**, it belongs in the code and the register.
// So it is here, where the next reader of this file will find it, and the
// FACTS those notes sit beside — the money figures, the empty radio group, the
// consequence rows — are drawn.
//
// ⚠ **AND ONE OF THOSE NOTES IS ALREADY WITHDRAWN BY A RULING.** p085 says the
// request closes *"holding $25.00 that may have to be given back"*. The PO
// ruled on 2026-09-15 that an application fee is non-refundable — *"if it is
// refuse then it is application fees non refundable - it stya in books"* — and
// `refuse_request` now releases the held credit to revenue. Drawing that hedge
// would have printed a promise the product had just stopped keeping, which is
// hard-won law 1 wearing a wireframe.
//
// ⚠ **WHAT EACH BUTTON DOES IS THE SERVER'S ANSWER, NEVER THIS FILE'S GUESS.**
// `WHAT APPROVING WILL DO` is rendered from `decision.what_approving_will_do`,
// keyed by outcome, so moving a radio redraws the table with no round trip and
// no second implementation of the rule. `then` and `what` are CATALOGUE KEYS —
// the wave-1 lane published them as keys precisely so the words would be
// minted here, once, in eleven languages.
import { useState } from "react";
import { z } from "zod";

import { Button } from "@/components/Button";
import {
  CheckboxField,
  FieldStack,
  FormModal,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";

import type {
  ApplicantMessage,
  ApprovalPreviewRow,
  ServiceRequestDetail,
  ServiceRequestJob,
} from "./serviceRequestEndpoints";
import { MoneyOrAbsence } from "./serviceRequestShared";

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** The five the blueprint names under its `Reason *` select, in its own order
 *  (p084, read at scale 2). They are the server's `REFUSAL_REASONS`. */
export const REFUSAL_REASON_CODES = [
  "not_our_service_area",
  "documents_not_provided",
  "applicant_withdrew",
  "duplicate_of_another_request",
  "other",
] as const;

/** The four the blueprint ticks (p085). ⚠ The first is drawn *"A readable site
 *  plan — the one attached was rejected"* and **the clause after the dash is an
 *  illustration** (B14 rule 37): it is true of the one request in the picture
 *  and false of a request with nothing attached, so the label is the first
 *  half. The server's `INFO_NEEDED_KINDS` is this list, in this order. */
export const INFO_NEEDED_CODES = [
  "readable_site_plan",
  "proof_of_identity",
  "connection_date",
  "something_else",
] as const;

// ══════════════════════════════════════════════════════════════════════════
// THE THREE SCHEMAS — each mirrors what the SERVER refuses, never more
// ══════════════════════════════════════════════════════════════════════════

/** **Nothing is preselected**, so the schema is what makes that safe: the
 *  commit cannot fire until a radio has been moved. The drawing's own note
 *  says why it is empty and that note is rationale, so it is here. */
export const APPROVE_SCHEMA = z.object({ outcome: z.string().trim().min(1) });

/**
 * ⚠ **THE DRAWN `Reason *` IS THE CODE, AND THE SERVER'S REQUIRED `reason` IS
 * NOT DRAWN AT ALL.** p084 draws exactly two controls — a select whose five
 * values are named under it, and `What to tell them`. The server takes three
 * fields (`reason` required and internal, `reason_code` optional,
 * `message_to_applicant` optional), so the screen has to supply `reason` from
 * something a clerk actually gave it.
 *
 * **It sends the letter when one was typed, and otherwise the label the clerk
 * saw on the select** — see `refusalInternalReason`. Sending the CODE was the
 * obvious move and is the defect coming straight back: `decision_reason` is a
 * free-text column a later reader reads, and `duplicate_of_another_request` on
 * a clerk's screen is `DEF-CUS-5010`'s shape.
 */
export const REFUSE_SCHEMA = z.object({ reason_code: z.string().trim().min(1) });

/** The drawing puts an asterisk on NOTHING in the Ask dialog, so neither does
 *  this. What the server requires (`reason`) is composed from what the clerk
 *  gave — see `askInternalReason`. */
export const ASK_SCHEMA = z.object({});

/**
 * The internal register line for a refusal, from the two controls the clerk
 * actually has.
 *
 * ⚠ **IT IS NEVER THE CODE.** A code in a free-text human column is a code on a
 * screen one read later (B14 rule 31 / `DEF-CUS-5010`), so when the clerk wrote
 * no letter this stores the LABEL they chose — which is the sentence they meant
 * — and that label is in their own language, exactly as every other clerk-typed
 * note in the product is.
 */
export function refusalInternalReason(
  reasonCode: string,
  message: string,
  t: Translate,
): string {
  const typed = message.trim();
  if (typed !== "") {
    return typed;
  }
  return t(`customers.serviceRequest.refuseReason.${reasonCode}`);
}

/** The same, for Ask for more: the message if one was typed, else the ticks in
 *  the drawing's order, else the catalogue's own standing line. */
export function askInternalReason(
  needed: readonly string[],
  message: string,
  t: Translate,
): string {
  const typed = message.trim();
  if (typed !== "") {
    return typed;
  }
  if (needed.length > 0) {
    return INFO_NEEDED_CODES.filter((code) => needed.includes(code))
      .map((code) => t(`customers.serviceRequest.infoNeeded.${code}`))
      .join(" · ");
  }
  return t("customers.serviceRequest.reason.request_info");
}

// ══════════════════════════════════════════════════════════════════════════
// THE CONSEQUENCE TABLE — B14 rule 11, and the drawing's `THEN` / `WHAT`
// ══════════════════════════════════════════════════════════════════════════

/**
 * ⚠ **EVERY ROW IS A CATALOGUE KEY LOOKED UP HERE.** The server sends
 * `{"then": "now", "what": "job_is_raised_naming_this_request"}` and this turns
 * it into a sentence. A `defaultValue` is deliberately NOT passed: an unknown
 * `what` must be visible as a gap, because printing the raw key at a clerk is
 * the defect this whole wave exists to stop, and printing nothing hides a row
 * the server thinks it sent.
 */
export function ConsequenceTable(props: {
  heading: string;
  rows: readonly ApprovalPreviewRow[];
  t: Translate;
  /** The namespace the `what` keys are looked up in. */
  namespace: string;
  testId: string;
}) {
  return (
    <section className="mt-6" data-consequence={props.testId}>
      <h4 className="m-0 text-xs font-semibold tracking-wide text-accent uppercase">
        {props.heading}
      </h4>
      <table className="data-table mt-2 w-full">
        <thead>
          <tr>
            <th className="w-28">{props.t("customers.serviceRequest.willDo.then")}</th>
            <th>{props.t("customers.serviceRequest.willDo.what")}</th>
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row, index) => (
            <tr key={`${row.then}-${row.what}-${index}`} data-then={row.then}>
              <td className="text-neutral-700">
                {props.t(`customers.serviceRequest.willDo.when.${row.then}`)}
              </td>
              <td>{props.t(`${props.namespace}.${row.what}`)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

/**
 * The drawn `FEES` figures, wherever a dialog needs them.
 *
 * Every amount goes through `MoneyCell` with its own `CHAR(3)` — CLAUDE.md hard
 * rule 2, two decimals on screen — and NOTHING here does arithmetic. The
 * drawing's `$130.00 / $25.00 / $105.00` are illustrations (rule 37); the
 * figures are the payload's.
 */
export function MoneyFigures(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  heading: string;
}) {
  const fees = props.detail.fees;
  return (
    <section className="mt-6" data-money-figures="">
      <h4 className="m-0 text-xs font-semibold tracking-wide text-accent uppercase">
        {props.heading}
      </h4>
      <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-2 text-md">
        <dt className="text-neutral-700">{props.t("customers.serviceRequest.fees.quoted")}</dt>
        <dd className="m-0 text-right tabular-nums">
          <MoneyOrAbsence money={fees.quoted} t={props.t} />
        </dd>
        <dt className="text-neutral-700">{props.t("customers.serviceRequest.fees.collected")}</dt>
        <dd className="m-0 text-right tabular-nums">
          <MoneyOrAbsence money={fees.collected} t={props.t} />
        </dd>
        <dt className="border-t border-t-divider pt-2 font-semibold">
          {props.t("customers.serviceRequest.fees.outstanding")}
        </dt>
        <dd className="m-0 border-t border-t-divider pt-2 text-right font-semibold tabular-nums">
          <MoneyOrAbsence money={fees.outstanding} t={props.t} />
        </dd>
      </dl>
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// APPROVE — p083 / p084
// ══════════════════════════════════════════════════════════════════════════

/*
 * ⛔ **THE APPROVE DIALOG LEFT THIS FILE ON 2026-09-23 (`DEF-CUS-6350`,
 * `DEF-CUS-6352`).** It is `ApproveChecksModal.tsx` now — its own component,
 * built from the kit (`CheckList`, `SegmentedControl`, `ConsequenceBox`,
 * `FormModal`) to the layout the PO approved that day: every check the server
 * runs as a ✓ / ✗ / ! row, the consequence as two lines chosen PER KIND on the
 * server, and Approve disabled with its reason. What this file used to hold for
 * it — the per-outcome radios, the `THEN`/`WHAT` table over build-worded rows,
 * the *Still needed* sentences and the arrears button — is all there, re-built
 * rather than copied; the reasoning that lived here (the arrears door is
 * load-bearing, the outcome travels WITH the approval, each option carries its
 * own verdict) moved with it. `APPROVE_SCHEMA` stays here because the Refuse and
 * Ask schemas it sits beside are one family.
 */

// ══════════════════════════════════════════════════════════════════════════
// REFUSE — p084 / p085
// ══════════════════════════════════════════════════════════════════════════

export function RefuseModal(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  onClose: () => void;
  onSubmit: (input: {
    reason: string;
    reason_code: string;
    message_to_applicant: string;
  }) => Promise<FormSubmitOutcome>;
}) {
  const [reasonCode, setReasonCode] = useState("");
  const [message, setMessage] = useState("");

  // The drawn `WHAT REFUSING WILL DO` rows. They are fixed — a refusal has one
  // shape — so unlike the approval table they are not served, and they are
  // written as keys here for exactly the same reason.
  const rows: ApprovalPreviewRow[] = [
    { then: "now", what: "becomes_refused" },
    { then: "now", what: "letter_is_queued" },
    { then: "now", what: "money_stays_collected" },
    { then: "later", what: "can_be_reopened" },
  ];

  return (
    <FormModal
      title={props.t("customers.serviceRequest.refuse.title", {
        number: props.detail.header.request_no ?? "",
      })}
      schema={REFUSE_SCHEMA}
      values={{ reason_code: reasonCode }}
      submitLabel={props.t("customers.serviceRequest.refuse.submit")}
      // B14 rule 6 — refusing an application is a destructive commit and the
      // kit's danger tier is how this product says so.
      submitVariant="danger"
      onClose={props.onClose}
      onSubmit={() =>
        props.onSubmit({
          reason: refusalInternalReason(reasonCode, message, props.t),
          reason_code: reasonCode,
          message_to_applicant: message.trim(),
        })
      }
    >
      <p className="m-0 text-md text-neutral-700">
        {props.t("customers.serviceRequest.refuse.lead")}
      </p>

      <section className="mt-6" data-section="why">
        <h4 className="m-0 mb-2 text-xs font-semibold tracking-wide text-accent uppercase">
          {props.t("customers.serviceRequest.refuse.why")}
        </h4>
        {/* B14 rule 39 — one spacing scale, and a field is LABEL → INPUT →
            HELPER. The kit's own stack is what puts the gap between two
            fields; hand-spacing them here would be a second scale. */}
        <FieldStack>
        <SelectField
          id="reason_code"
          label={props.t("customers.serviceRequest.refuse.reason")}
          required
          value={reasonCode}
          onChange={setReasonCode}
          placeholder={props.t("customers.serviceRequest.refuse.reasonPlaceholder")}
          options={REFUSAL_REASON_CODES.map((code) => ({
            value: code,
            label: props.t(`customers.serviceRequest.refuseReason.${code}`),
          }))}
        />
        <TextField
          id="message_to_applicant"
          label={props.t("customers.serviceRequest.refuse.tellThem")}
          multiline
          value={message}
          onChange={setMessage}
          help={props.t("customers.serviceRequest.refuse.tellThemHelp")}
        />
        </FieldStack>
      </section>

      <ConsequenceTable
        heading={props.t("customers.serviceRequest.refuse.willDo")}
        rows={rows}
        t={props.t}
        namespace="customers.serviceRequest.willDo.refuse"
        testId="refuse"
      />

      {/* p085's money panel. The FIGURES are drawn; the paragraph beside them
          in the blueprint is rationale and is in this file's header instead. */}
      <MoneyFigures
        detail={props.detail}
        t={props.t}
        heading={props.t("customers.serviceRequest.refuse.theMoney")}
      />
    </FormModal>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// ASK FOR MORE — p085 / p086
// ══════════════════════════════════════════════════════════════════════════

export function AskForMoreModal(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  onClose: () => void;
  onSubmit: (input: {
    reason: string;
    info_needed: string[];
    message_to_applicant: string;
  }) => Promise<FormSubmitOutcome>;
}) {
  const [needed, setNeeded] = useState<string[]>([]);
  const [message, setMessage] = useState("");

  const rows: ApprovalPreviewRow[] = [
    { then: "now", what: "becomes_more_info" },
    { then: "now", what: "waiting_on_moves" },
    { then: "now", what: "message_is_queued" },
    { then: "then", what: "leaves_your_queue" },
  ];

  return (
    <FormModal
      title={props.t("customers.serviceRequest.ask.title", {
        number: props.detail.header.request_no ?? "",
      })}
      schema={ASK_SCHEMA}
      values={{}}
      submitLabel={props.t("customers.serviceRequest.ask.submit")}
      onClose={props.onClose}
      onSubmit={() =>
        props.onSubmit({
          reason: askInternalReason(needed, message, props.t),
          info_needed: INFO_NEEDED_CODES.filter((code) => needed.includes(code)),
          message_to_applicant: message.trim(),
        })
      }
    >
      <p className="m-0 text-md text-neutral-700">
        {props.t("customers.serviceRequest.ask.lead")}
      </p>

      <section className="mt-6" data-section="what-is-needed">
        <h4 className="m-0 mb-2 text-xs font-semibold tracking-wide text-accent uppercase">
          {props.t("customers.serviceRequest.ask.whatIsNeeded")}
        </h4>
        <div className="flex flex-col gap-2">
          {INFO_NEEDED_CODES.map((code) => (
            <CheckboxField
              key={code}
              id={`info-needed-${code}`}
              label={props.t(`customers.serviceRequest.infoNeeded.${code}`)}
              checked={needed.includes(code)}
              onChange={(on) =>
                setNeeded((current) =>
                  on ? [...current, code] : current.filter((row) => row !== code),
                )
              }
            />
          ))}
        </div>
        <div className="mt-4">
          <TextField
            id="ask_message_to_applicant"
            label={props.t("customers.serviceRequest.ask.message")}
            multiline
            value={message}
            onChange={setMessage}
            help={props.t("customers.serviceRequest.ask.messageHelp")}
          />
        </div>
      </section>

      <ConsequenceTable
        heading={props.t("customers.serviceRequest.ask.willDo")}
        rows={rows}
        t={props.t}
        namespace="customers.serviceRequest.willDo.ask"
        testId="ask"
      />
    </FormModal>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// WHAT THE THREE BUTTONS DID — the half hard-won law 2's mirror is about
// ══════════════════════════════════════════════════════════════════════════

/**
 * After a decision commits, the clerk is told WHAT IT CREATED and WHETHER THE
 * LETTER WENT, in the clerk's own words.
 *
 * ⚠ **THIS EXISTS BECAUSE A BUTTON THAT DOES THE THING AND SAYS NOTHING IS
 * HALF A CONTROL.** Wave 1's server answers both questions — `job` holds either
 * `raised` or `not_raised`, `applicant_message` holds either a queued letter or
 * the named reason nothing was queued — and a screen that threw both away would
 * leave the clerk to go and look on another tab for whether their approval
 * raised anything. The drawing promises *"A build is raised on the New connects
 * tab"* and *"A refusal letter is queued to the applicant"*; this is the
 * product keeping or honestly breaking each promise on the spot.
 *
 * ⚠ **`ref` IS A TENANT-FACING SERIES (`CON-26-0131`), NOT A DATABASE ID.** The
 * row's `id` is on the payload and is deliberately not drawn (B14 rule 31).
 */
export function DecisionOutcomeNote(props: {
  job?: ServiceRequestJob;
  message?: ApplicantMessage | null;
  t: Translate;
}) {
  const raised = props.job?.raised;
  const notRaised = props.job?.not_raised;
  const message = props.message ?? undefined;
  if (raised === undefined && notRaised === undefined && message === undefined) {
    return null;
  }
  return (
    <div
      role="status"
      className="mt-4 border border-divider bg-surface p-3 text-md"
      data-decision-outcome=""
    >
      {raised !== undefined && (
        <p className="m-0" data-job-raised={raised.queue}>
          {props.t("customers.serviceRequest.jobRaised", { ref: raised.ref ?? "" })}
        </p>
      )}
      {notRaised !== undefined && (
        <p className="m-0" data-job-not-raised={notRaised.code} data-br-ref={notRaised.br_ref ?? undefined}>
          {props.t(`customers.serviceRequest.jobRefusal.${notRaised.code}`)}
        </p>
      )}
      {message !== undefined && (
        <p className="m-0 mt-1" data-applicant-message={message.state}>
          {message.state === "queued" && message.address !== null
            ? props.t("customers.serviceRequest.applicantMessage.queued", {
                address: message.address,
              })
            : props.t(
                `customers.serviceRequest.applicantMessage.${message.reason ?? "unknown"}`,
              )}
        </p>
      )}
    </div>
  );
}

/** The three heads' buttons, so the drawn order is stated once. Refuse is
 *  leftmost and danger-tiered; Approve is the one primary (B14 rule 6, TC-6). */
export function DecisionButton(props: {
  label: string;
  variant: "danger" | "secondary" | "primary";
  disabled?: boolean;
  reason?: string;
  onClick: () => void;
  testId: string;
}) {
  return (
    <Button
      variant={props.variant}
      disabled={props.disabled === true}
      title={props.reason}
      data-decision-action={props.testId}
      onClick={props.onClick}
    >
      {props.label}
    </Button>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-094-BRC01 wave 2 · PO ruling 2026-09-15 · Accounts blueprint
//         entry 06, pages 82–86 read AS IMAGES at scale 2 (rule 42)
// generated: 2026-09-15 by the CR-094-BRC01 wave-2 screen lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: tsc✔ vitest✔ · G31 (Route B — this file is on route-b-migrated.txt)
// exceptions: E3 the dialog SUB-LINE the drawing puts under each title is not
//   built as a sub-line — B14 rule 38 gives a dialog's header construction to
//   the kit and the kit has no such slot; the SENTENCE is built, as the body's
//   first line, because rule 38's last clause keeps content with the drawing ·
//   E3 the red and grey annotation panels on p084/p085/p086 are NOT drawn:
//   they are rationale and B14 rule 33 puts rationale at zero words on screen ·
//   E3 p085's hedge *"holding $25.00 that may have to be given back"* is
//   withdrawn by the PO's own 2026-09-15 non-refundable ruling and is not drawn
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
