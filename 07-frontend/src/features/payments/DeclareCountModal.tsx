// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — §03 frame **3·3d Declare**,
//           `05-prototype/06 Payments Page Blueprint.pdf` p058–p059, read as
//           an IMAGE at scale 2.0 (B14 rule 42).
// Screens:  3·3d · a row action on `PAY-04` Counters, on an uncounted row only
// Rules:    B14 rule 10 (the asterisk on a required label) · rule 11 · rule 33
//           · rule 43 · rule 21 · CLAUDE.md hard rule 7 (a declare writes
//           `audit_log`) · `CR-136-BRC07` §3.2 · §3.3
// Tests:    src/features/payments/counterScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
// *"The system closed my till on Friday. Here is what was actually in it."*
//
// ══════════════════════════════════════════════════════════════════════════
// A LATE COUNT SITS **BESIDE** THE FORCED CLOSE, NEVER OVER IT
// ══════════════════════════════════════════════════════════════════════════
// `CR-136-BRC07` §3.2, PO ruling 2026-09-23, verbatim: *"(a) Keep it as a
// forced close and add the late count beside it"*. The worked case is the
// whole rule in one row:
//
//   Dana's till is force-closed Monday night uncounted. Tuesday she counts
//   **$1,228.00 against $1,240.00 expected — $12.00 short**, reason *"cheque
//   stuck to the bag"*. **The one row then says both**: force-closed Monday by
//   the supervisor, declared Tuesday by Dana, $12.00 short.
//
// Two things follow and both are visible on 3·1 rather than here:
//   · `close_kind` **does not move**. There is no fourth value and a forced
//     close never becomes a counted one — that would erase who counted what.
//   · the row stops answering *Not counted* the moment `declared_at` is set,
//     which is the whole of `isNotCounted` in `counterShared.tsx`.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE REASON IS REQUIRED HERE AND CONDITIONAL ON 3·3b, AND THAT IS NOT A
// ══════════════════════════════════════════════════════════════════════════
// MISTAKE. p058 ② says why in its own words: *"a declared difference is the
// only number nobody watched happen"*. On a counted close a supervisor could
// have been standing there; on a count declared the next morning, nobody was.
// `CR-136-BRC07` §3.2 restates it as a flat requirement — *"A reason is
// **required** on a declare"* — so the field is required whether the drawer
// matched or not.
import { useMemo, useState } from "react";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { declareCount } from "@/api/counterEndpoints";
import type { CounterDetail } from "@/api/counterEndpoints";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DateTimeField, FormModal, TextField, nowInZone, sameDayBounds } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { CountComparison, CounterNote, counterKicker } from "./counterShared";
import { counterQueryKey, countersQueryKey } from "./counterQueries";

/** A figure per countable method, and a reason — ALWAYS (§3.2). */
export function declareCountSchema(methods: readonly { method_id: string; countable: boolean }[]) {
  return z
    .object({
      counted: z.record(z.string(), z.string()),
      note: z.string().trim().min(1),
      declared_at: z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/),
    })
    .superRefine((value, ctx) => {
      for (const method of methods.filter((candidate) => candidate.countable)) {
        const typed = (value.counted[method.method_id] ?? "").trim();
        if (!/^\d+(\.\d{1,4})?$/.test(typed)) {
          ctx.addIssue({
            code: "custom",
            path: [`counted.${method.method_id}`],
            message: "payments.counter.count.invalid",
          });
        }
      }
    });
}

export interface DeclareCountModalProps {
  counter: CounterDetail;
  locale?: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  onClose: () => void;
  onDeclared: (counter: CounterDetail) => void;
  writeBlockedReason: string | null;
  client?: ApiClient;
}

export function DeclareCountModal(props: DeclareCountModalProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const [counted, setCounted] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [declaredAt, setDeclaredAt] = useState("");
  // The regional pair is already required on this screen's props.
  const declaredAtPrefill = useMemo(() => nowInZone(props.timeZone), [props.timeZone]);
  const declaredAtBounds = useMemo(() => sameDayBounds(props.timeZone), [props.timeZone]);
  const { counter } = props;

  const commit = useMutation({
    mutationFn: () =>
      declareCount(client, counter.code, {
        counted_totals: counted,
        note: note.trim(),
        // ⚠ REQUIRED by `counter_declare`, and missing until `DEF-PAY-6315`.
        // ⚠ **THIS IS THE ONE THE PICKER EARNS MOST.** A late count is by
        // definition made at a time other than the press, so a machine stamp
        // recorded when the clerk opened this dialog rather than when they
        // counted the drawer. The PO ruled a picker on all four (2026-09-23).
        declared_at: declaredAt,
      }),
  });

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const declared = await commit.mutateAsync();
      void queryClient.invalidateQueries({ queryKey: countersQueryKey() });
      void queryClient.invalidateQueries({ queryKey: counterQueryKey(counter.code) });
      props.onDeclared(declared);
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
      title={t("payments.counter.declare.title")}
      schema={declareCountSchema(counter.methods)}
      values={{ counted, note, declared_at: declaredAt }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("payments.counter.declare.commit")}
      // ⚠ NOT the danger tier, and p059's own *Primary action* row is why:
      // *"Declare — it records a count, it does not move money, so it is the
      // standard tier."* The balanced pair `CR-136-BRC07` §3.3 adds is the
      // SERVICE's consequence, not a destruction this screen performs.
      cancelLabel={t("payments.counter.declare.cancel")}
      commitBlocked={props.writeBlockedReason ?? undefined}
    >
      {/* ① — *why this is open at all*, said plainly as a FACT.
          ⚠ **THE DRAWING SAYS *Closed by the system* AND THIS SAYS WHO.**
          p058 ① reads *"an auto-close is a fact, said plainly"* over the
          sentence *"Closed by the system on 09/18 23:59. Nobody counted it."*
          `CR-136-BRC07` §3.1 struck the auto-close, so there is no system to
          name: a till reaches this dialog because a SUPERVISOR force-closed
          it, and §3.2's worked case says so in as many words — *"force-closed
          Monday by the supervisor"*. Naming the person is also what makes
          §3.2's *"the one row says both"* true at the moment of the count. */}
      <CounterNote tone="warning">
        {t("payments.counter.declare.sealedBy", {
          person: counter.closed_by_name ?? t("payments.counter.declare.aSupervisor"),
        })}{" "}
        {counter.closed_at !== null && (
          <DateCell
            value={counter.closed_at}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            withTime
          />
        )}{" "}
        {t("payments.counter.declare.nobodyCounted")}
      </CounterNote>
      <CountComparison
        methods={counter.methods}
        currency={counter.currency}
        locale={props.locale}
        editable
        counted={counted}
        onCountedChange={(methodId, value) =>
          setCounted((current) => ({ ...current, [methodId]: value }))
        }
        idPrefix="counter-declare"
        t={t}
      />
      <TextField
        id="note"
        label={t("payments.counter.declare.why")}
        required
        value={note}
        onChange={setNote}
        help={t("payments.counter.declare.whyHelp")}
      />
      {/* ⚠ **THE PICKER, ON ALL FOUR COUNTER WRITES** — PO ruling 2026-09-23,
          *"(a) Picker on all four, same as opening"*. Prefilled with now on the
          utility's clock, in the utility's format, bounded to its own business
          day (`BR-PAY-1191`). Rule 33: RATIONALE is zero words on screen. */}
      <DateTimeField
        id="declared_at"
        label={t("payments.counter.declare.declaredAt")}
        required
        value={declaredAt}
        onChange={setDeclaredAt}
        prefill={declaredAtPrefill}
        dateFormat={props.dateFormat}
        min={declaredAtBounds.min}
        max={declaredAtBounds.max}
      />
    </FormModal>
  );
}

export default DeclareCountModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §3.2 · §3.3 · §4 row `P2.6` · blueprint p058–p059 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(`POST /counters/{ref}/declare` is `P2.2`, LANE P2-API's) C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/counterScreens.dom.test.tsx · G31 · routeBUtilities.test.ts
// exceptions: E3 the endpoint is NOT SERVED at this commit · E3 ①'s sentence names the SUPERVISOR who sealed the till where the drawing names *the system*, because `CR-136-BRC07` §3.1 struck the auto-close the drawing was describing · E3 the cash row is labelled `Cash incl. float` here where p058 labels it `Cash` — one label for one quantity, and p056 draws the same figure; reported
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
