// ── Trace ──────────────────────────────────────────────
// Task:     Finance blueprint `P3.2` — *"Reopen a period (screen 6·1b). The
//           endpoint and typed client wrapper exist, no component calls
//           either."* `POST /finance/periods/reopen` has been served since
//           2026-08-16 and `endpoints.reopenPeriod` has wrapped it since; a
//           period closed in error was reopened **from a shell**.
// Drawing:  05-prototype/07 Finance Blueprint.pdf — **p072** (the 6·1b heading,
//           its *Opens from* line and the top of the dialog) and **p073** (the
//           rest of the dialog, the GAP box and the FOR / DOORS / PRIMARY
//           ACTION / FIELDS / WRITE SURFACES / TODAY / TASK / RULES table).
//           p068 is 6·1's *Closed months* table, whose `↺` is the door.
//           Built from the RENDERED IMAGES (B14 rule 42).
// Rules:    BR-LED-006 (*"SysAdmin reopens"*, with a reason, audited — AMENDED
//           by the PO on 2026-09-24: closing is `system_admin` + `billing_clerk`
//           and REOPENING is `system_admin` ONLY) · BR-LED-017 (a handover
//           already sent is not recalled) · BR-TEN-038 · BR-TEN-043 (the moment
//           is an INPUT) · BR-SHL-020 · BR-SHL-025 (a control that cannot act is
//           DISABLED WITH ITS REASON) · CLAUDE.md hard rule 7 (every money
//           action is audited) · B14 rule 4 (button grammar) · 6 (danger tier on
//           a destructive commit) · 21 (Tailwind only — this file is on
//           `styles/route-b-migrated.txt`) · 31 · 32 · 33 (the caps, and
//           RATIONALE is ZERO words on screen) · 43 · 44
// Tests:    07-frontend/src/features/ledger/financeP3Doors.dom.test.tsx ·
//           10-scripts/fin_p3_screens_walkthrough.mjs (the browser walk — the
//           only check in this repo that reads rendered output)
//           08-qa/01-e2e/journeys/J19-month-end-close.md step 8
//           08-qa/01-e2e/journeys/J19-month-end-close.md step 8
// ───────────────────────────────────────────────────────
//
// 6·1b REOPEN — the undo for a month closed by mistake.
//
// ══════════════════════════════════════════════════════════════════════════
// WHO MAY PRESS IT IS RULED, AND IT IS NOT THE SAME ROLE THAT CLOSES
// ══════════════════════════════════════════════════════════════════════════
// `P3.8` used to read *"who may reopen is a role gate, not a setting — the same
// unruled question as `P4.9`"*. **The PO ruled it on 2026-09-24: closing a month
// is `system_admin` + `billing_clerk`; REOPENING is `system_admin` ONLY, reason
// required, audited.** `apps/ledger/close.reopen_period` gates it and
// `finance_api.reopen_period` gates it at the door; this dialog offers or
// withholds the control, which is BR-SHL-025's half and never the boundary.
//
// ⚠ **A NULL ROLE OFFERS THE CONTROL.** `/me/permissions` may not have answered
// yet, and a screen that hid the act on an unanswered read would teach a System
// Admin the product is broken. The server refuses if it must.
//
// ══════════════════════════════════════════════════════════════════════════
// THE CONSEQUENCE LINE, AND WHY IT IS SHORTER THAN THE DRAWING
// ══════════════════════════════════════════════════════════════════════════
// p073's FIELDS row: *"Period · Reason · a consequence line about any handover
// already sent"*, and the drawing writes it as *"Handed over 2026-10-05.
// Reopening does not recall that handover — post the difference by hand."*
//
// **That second sentence is thirteen words and B14 rule 33 caps a consequence
// at six per sentence, at most two.** Rule 44 — ratified today — puts HOW a
// thing is built with our rules and WHAT is on it with the drawing, so the
// FACT stays and the wording is ours: *"Handed over {date}."* then *"That
// handover stands. Post the difference."* Two sentences, four and five words,
// and nothing is cut below clarity.
//
// ⚠ **AND IT IS DRAWN ONLY WHEN A HANDOVER REALLY EXISTS.** The caller passes
// the batch's date or `null`; there is no *"no handover was sent"* line,
// because a stated absence nobody needs is rule 32's budget spent on nothing.
import { useState } from "react";

import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { reopenPeriod } from "@/api/endpoints";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { useToast } from "@/components/Toast";
import type { Translator } from "@/features/tenancy/settingsShared";

/** BR-LED-006 — a reopen is refused without a reason, and the refusal lands on
 *  the FIELD rather than as a round trip. The server refuses it too; this only
 *  saves the trip. */
export function reopenSchema(t: Translator) {
  return z.object({
    reason: z.string().trim().min(1, t("finance.reopen.reasonRequired")),
  });
}

export interface ReopenPeriodDialogProps {
  /** The closed period, both ends the SERVER's own — never composed here. */
  period: { start: string; end: string };
  /** What the period is called on screen, already formatted by the caller. */
  periodLabel: string;
  /** The day this period was handed over to an accounting package, or `null`.
   *  BR-LED-017 — reopening does not recall a handover. */
  handedOverOn: string | null;
  /** BR-TEN-043 — the instant the reopen is stamped with, supplied by the
   *  caller so a double-press stamps one moment and a test can state it. */
  now: () => string;
  t: Translator;
  client?: ApiClient;
  onClose: () => void;
  onReopened: () => Promise<void> | void;
}

export function ReopenPeriodDialog(props: ReopenPeriodDialogProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const toast = useToast();
  const [reason, setReason] = useState("");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await reopenPeriod(
        {
          from: props.period.start,
          to: props.period.end,
          reopened_at: props.now(),
          reason: reason.trim(),
        },
        client,
      );
      toast(t("finance.reopen.doneToast", { period: props.periodLabel }));
      await props.onReopened();
      props.onClose();
      return { ok: true };
    } catch (error) {
      // The System-Admin refusal lands HERE, in the form-message slot, where a
      // `role="alert"` announces it — never as a `title` tooltip a clerk on the
      // telephone cannot read.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      // ⚠ **THE PERIOD IS THE KICKER, NOT THE TITLE.** The drawing writes
      // *"Reopen September 2026?"*; this product's period is a WINDOW and not a
      // month name (BR-TEN-022 — a quarterly tenant closes a quarter), so
      // interpolating it produced *"Reopen 2026-07-01 to 2026-07-31?"* — a
      // heading of eight tokens where B14 rule 33 allows three. Rule 44 gives
      // the FACT to the drawing and the construction to us, and 6·1a's *Close
      // the month* dialog one component along already puts its window in the
      // kicker. Same shape, same place.
      title={t("finance.reopen.title")}
      kicker={props.periodLabel}
      schema={reopenSchema(props.t)}
      values={{ reason }}
      // B14 rule 4 — `Verb ✓` commits. B14 rule 6 — the DANGER tier,
      // because a period lock coming off is destructive in effect, exactly as
      // 6·1a's own *Close the month* is.
      submitVariant="danger"
      submitLabel={t("finance.reopen.confirm")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      {/* p072's own two sentences: six words and six words. */}
      <p className="m-0 text-md leading-body">{t("finance.reopen.whatHappens")}</p>
      <div className="mt-4">
        <TextField
          id="reopen-period-reason"
          label={t("finance.reopen.reasonLabel")}
          value={reason}
          onChange={setReason}
          required
          help={t("finance.reopen.reasonHelp")}
        />
      </div>
      {props.handedOverOn !== null && (
        <p className="mt-4 text-md leading-body" data-testid="reopen-handover-note">
          {t("finance.reopen.handedOver", { date: props.handedOverOn })}{" "}
          {t("finance.reopen.handoverStands")}
        </p>
      )}
    </FormModal>
  );
}

export default ReopenPeriodDialog;

// ── Lifecycle ─────────────────────────────────────
// packet: 05-prototype/07 Finance Blueprint.pdf p016 (P3.2 · P3.8) + p068 (6·1's Closed months and its ↺) + p072–p073 (6·1b, rendered at 2.2 and read as IMAGES, B14 rule 42) · 06-backend/apps/ledger/close.py reopen_period · finance_api.py:709 · 12-governance/02-decision-log.md 2026-09-24 (the PO's reopen role ruling) · 04-docs/02-decisions/14-ui-conventions.md rules 4/6/21/31/32/33/43/44
// generated: 2026-09-24 by LANE FIN-P3
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions:
//   E1 **THE CONSEQUENCE SENTENCE IS OURS, NOT THE DRAWING'S** — the drawn one
//      is thirteen words and B14 rule 33 caps it at six per sentence. Rule 44
//      gives the FACT to the drawing and the wording to us. The fact is intact.
//   E2 **A MODAL, NOT A SCREEN** (B14 §5): one field, one outcome, returns to
//      the list it was launched from, and nothing needs to link to it. The
//      blueprint draws it as `modal` in its own heading.
//   E3 **THE HANDOVER DATE IS THE CALLER'S.** This file reads no export batch:
//      `CloseExportPage` already holds `GET /finance/export/batches` for its
//      drift panel, and a second read of one fact is how two screens come to
//      disagree about whether a month was sent.
// status: VERIFIED-UNRATIFIED
// ────────────────────────────────────────────────────
