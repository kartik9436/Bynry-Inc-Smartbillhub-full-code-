// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — §03 frame **3·3c Force close**,
//           `05-prototype/06 Payments Page Blueprint.pdf` p057–p058, read as
//           an IMAGE at scale 2.0 (B14 rule 42).
// Screens:  3·3c · a row action on `PAY-04` Counters
// Rules:    B14 rule 6 (danger tier) · rule 11 (the consequence) · rule 31
//           (no database id on screen) · rule 33 · rule 43 · rule 21 ·
//           BR-SHL-025 (**who may do this is a role check at the SERVICE**) ·
//           CLAUDE.md hard rule 7 (a forced close writes `audit_log`) ·
//           `CR-136-BRC07` §3.1
// Tests:    src/features/payments/counterScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
// *"Someone went home without closing their till."*
//
// ══════════════════════════════════════════════════════════════════════════
// THIS IS HOW A FORGOTTEN TILL GETS SEALED — AND NOW IT IS THE ONLY WAY
// ══════════════════════════════════════════════════════════════════════════
// `CR-136-BRC07` §3.1, PO ruling 2026-09-23, verbatim: *"(a) Your ruling
// stands — no auto-close. A System Admin closes it. Dana cannot work Tuesday
// until someone is free to do that"*. **No midnight job exists**, so this
// dialog is not a fallback for one: it carries the whole mechanism. The
// accepted cost is named in the ruling — a clerk whose supervisor is
// unavailable cannot take money that morning — and the PO chose it explicitly.
//
// ══════════════════════════════════════════════════════════════════════════
// SUPERVISOR ONLY, AND THE SCREEN DOES NOT ENFORCE THAT
// ══════════════════════════════════════════════════════════════════════════
// p057's route line reads *"supervisor only"*. `BR-SHL-025` decides where that
// lives: **at the service**, never as a hidden button — a control hidden from
// a Billing Clerk is not a guarantee, it is a guess about who is looking. The
// screen REFLECTS the deployment's answer through `writeBlockedReason`, which
// renders the refusal as a readable sentence beside a disabled commit.
//
// ══════════════════════════════════════════════════════════════════════════
// THREE THINGS THE DRAWING PUTS IN A DELIBERATE ORDER
// ══════════════════════════════════════════════════════════════════════════
//   ① *"This closes someone else's till. They will be told."* — **whose till
//      it is, said FIRST**, because this is an act on another person's work.
//   ② A reason, **required** — *"a force close with no reason is
//      indistinguishable from a mistake"*.
//   ③ *"Sealed, not counted"* — *"the two are different and the screen keeps
//      them apart"*. No count is recorded here, which is precisely why the row
//      then reads **Not counted** and why 3·3d exists at all.
import { useMemo, useState } from "react";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { forceCloseCounter } from "@/api/counterEndpoints";
import type { CounterDetail, CounterRow } from "@/api/counterEndpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DateTimeField, FormModal, TextField, nowInZone, sameDayBounds } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";

import { CounterNote, counterKicker } from "./counterShared";
import { counterQueryKey, countersQueryKey } from "./counterQueries";

/** ② — the reason is REQUIRED, and that is the whole of annotation ②. */
export const forceCloseSchema = z.object({
  note: z.string().trim().min(1),
  closed_at: z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/),
});

export interface ForceCloseCounterModalProps {
  counter: CounterRow;
  locale?: string;
  /** IS-8 — an instant always displays in TENANT time, never the browser's. */
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onForceClosed: (counter: CounterDetail) => void;
  /** BR-SHL-025 — the role check is the server's; this renders its answer. */
  writeBlockedReason: string | null;
  client?: ApiClient;
}

export function ForceCloseCounterModal(props: ForceCloseCounterModalProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");
  const [closedAt, setClosedAt] = useState("");
  // This screen already REQUIRES the tenant's regional pair as props, so there
  // is nothing to resolve — `useRegional` would only re-derive what is here.
  const closedAtPrefill = useMemo(() => nowInZone(props.timeZone), [props.timeZone]);
  const closedAtBounds = useMemo(() => sameDayBounds(props.timeZone), [props.timeZone]);
  const { counter } = props;

  const commit = useMutation({
    mutationFn: () =>
      forceCloseCounter(client, counter.code, {
        note: note.trim(),
        // ⚠ REQUIRED by `counter_force_close`, and missing until
        // `DEF-PAY-6315`. A tenant WALL CLOCK; `_moment` anchors it.
        closed_at: closedAt,
      }),
  });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const sealed = await commit.mutateAsync();
      void queryClient.invalidateQueries({ queryKey: countersQueryKey() });
      void queryClient.invalidateQueries({ queryKey: counterQueryKey(counter.code) });
      props.onForceClosed(sealed);
      return { ok: true };
    } catch (error) {
      // BR-SHL-020 — the server's refusal is SHOWN as a sentence. A till act
      // that failed silently is the worst possible outcome on a money path.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      kicker={counterKicker(counter)}
      title={t("payments.counter.forceClose.title")}
      schema={forceCloseSchema}
      values={{ note, closed_at: closedAt }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("payments.counter.forceClose.commit")}
      submitVariant="danger"
      cancelLabel={t("payments.counter.forceClose.cancel")}
      commitBlocked={props.writeBlockedReason ?? undefined}
    >
      {/* ① — whose till it is, first. Two sentences, five words and four. */}
      <ConsequenceBox
        tone="check"
        title={t("payments.counter.forceClose.consequenceTitle")}
        body={t("payments.counter.forceClose.consequenceBody")}
        data-consequence="counter-force-close"
      />
      {/* The one FACT row the drawing puts under ①: how long it has been open
          and what is in it. Six words at most, and every value is served
          rather than composed from an id (B14 rules 31 and 33). */}
      <CounterNote tone="plain">
        {t("payments.counter.forceClose.openSince")}{" "}
        <DateCell
          value={counter.opened_at}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          withTime
        />{" "}
        ·{" "}
        {t("payments.counter.forceClose.payments", { count: counter.payment_count })} ·{" "}
        <span className="tabular-nums">
          {formatMoney(counter.taken_total, counter.currency, props.locale)}
        </span>
      </CounterNote>
      <TextField
        id="note"
        label={t("payments.counter.forceClose.why")}
        required
        value={note}
        onChange={setNote}
        help={t("payments.counter.forceClose.whyHelp")}
      />
      {/* ⚠ **THE PICKER, ON ALL FOUR COUNTER WRITES** — PO ruling 2026-09-23,
          *"(a) Picker on all four, same as opening"*. Prefilled with now on the
          utility's clock, in the utility's format, bounded to its own business
          day (`BR-PAY-1191`). Rule 33: RATIONALE is zero words on screen. */}
      <DateTimeField
        id="closed_at"
        label={t("payments.counter.close.closedAt")}
        required
        value={closedAt}
        onChange={setClosedAt}
        prefill={closedAtPrefill}
        dateFormat={props.dateFormat}
        min={closedAtBounds.min}
        max={closedAtBounds.max}
      />
      {/* ③ — *Sealed, not counted*. The two are different and this keeps them
          apart, which is what makes the row read `Not counted` afterwards. */}
      <ConsequenceBox
        tone="check"
        title={t("payments.counter.forceClose.sealsTitle", {
          counter: counter.code,
          amount: formatMoney(counter.taken_total, counter.currency, props.locale),
        })}
        body={t("payments.counter.forceClose.sealsBody")}
        data-consequence="counter-force-close-seals"
      />
    </FormModal>
  );
}

export default ForceCloseCounterModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §3.1 · §4 row `P2.6` · blueprint p057–p058 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(`POST /counters/{ref}/force-close` is `P2.2`, LANE P2-API's) C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/counterScreens.dom.test.tsx · G31 · routeBUtilities.test.ts
// exceptions: E3 the endpoint is NOT SERVED at this commit · E3 the supervisor-only rule is the SERVICE's (`BR-SHL-025`) and this screen renders the server's answer rather than hiding a control
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
