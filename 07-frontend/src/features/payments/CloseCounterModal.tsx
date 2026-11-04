// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — §03 frame **3·3b Close**,
//           `05-prototype/06 Payments Page Blueprint.pdf` p055–p056, read as
//           an IMAGE at scale 2.0 (B14 rule 42).
// Screens:  3·3b · opened from `PAY-07` Your counter
// Rules:    B14 rule 6 (the DANGER tier on a destructive commit — p056's own
//           *Primary action* row says so) · rule 11 (a consequence before the
//           commit) · rule 33 (a CONSEQUENCE ≤ 6 words per sentence, at most
//           two) · rule 36 · rule 38 · rule 43 · rule 21 ·
//           CLAUDE.md hard rule 4 (`counter_sessions` is NOT one of its four
//           frozen tables — a close writes the closing columns of the row it
//           seals) · hard rule 7 (a close is a money action and writes
//           `audit_log`) · `CR-136-BRC07` §3.3
// Tests:    src/features/payments/counterScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
// *"My shift is over — does the drawer match?"*
//
// ══════════════════════════════════════════════════════════════════════════
// A COMPARISON, NEVER A READ-BACK — p055's own caption
// ══════════════════════════════════════════════════════════════════════════
// The clerk types what is in the drawer. The screen puts it beside what the
// system says and shows the difference. **Only cash and cheques are
// countable**, and p056's GAP box is explicit about why the card row has no
// input: *"A close screen that demands a counted card total trains clerks to
// type the system figure back at it, which makes the whole reconciliation
// worthless."* The total row says `Countable together` rather than pretending
// otherwise, and the opening float sits INSIDE the cash line rather than being
// netted out.
//
// All of that is `CountComparison` in `counterShared.tsx`, because 3·3d draws
// the identical table after the fact (B14 rule 43).
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHAT THIS SCREEN DOES NOT SAY ABOUT THE LEDGER, AND WHY THAT CHANGED
// ══════════════════════════════════════════════════════════════════════════
// The blueprint's §4 table reads *"Close · The ledger: **Nothing — counting is
// not a posting**"*. `CR-136-BRC07` §3.3 SUPERSEDES that line: PO ruling
// 2026-09-23, verbatim *"(b) Post it. A short writes a balanced pair to a cash
// over/short account the day it is declared."* A non-zero difference now DOES
// post, at the moment the money is counted — here on a counted close, and at
// declare on a forced one.
//
// **So this screen says nothing at all about the ledger**, which is the one
// thing it must not get wrong in either direction: the old sentence is now
// false, and the new one is RATIONALE, which B14 rule 33 puts at zero words on
// screen. The posting is `P2.22`'s, at the service.
import { useMemo, useState } from "react";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { closeCounter } from "@/api/counterEndpoints";
import type { CounterDetail } from "@/api/counterEndpoints";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { DateTimeField, FormModal, TextField, nowInZone, sameDayBounds } from "@/components/FormModal";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import type { FormSubmitOutcome } from "@/components/FormModal";

import {
  CountComparison,
  countableSystemTotal,
  countedTogether,
  counterKicker,
  isZeroAmount,
  subtractDecimalStrings,
} from "./counterShared";
import { counterQueryKey, countersQueryKey } from "./counterQueries";

/**
 * A counted figure for every COUNTABLE method, and a note **only when the
 * difference is not zero** — p056's own *Fields* row, verbatim: *"A counted
 * figure per countable method, and a note that is required only when a
 * difference is not zero."*
 *
 * The conditional half cannot live in a static schema, so it is `superRefine`
 * over the methods the caller is actually counting. A schema that always
 * demanded a note would refuse the ordinary balanced close, and one that never
 * did would let a $12 hole through with nothing beside it.
 */
export function closeCounterSchema(methods: readonly { method_id: string; countable: boolean }[]) {
  return z
    .object({
      counted: z.record(z.string(), z.string()),
      note: z.string(),
      // A tenant wall clock, `YYYY-MM-DDTHH:mm`, with the seconds some
      // browsers append. Never an instant — see `CloseCounterBody`.
      closed_at: z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/),
    })
    .superRefine((value, ctx) => {
      const countable = methods.filter((method) => method.countable);
      for (const method of countable) {
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

export interface CloseCounterModalProps extends RegionalProps {
  counter: CounterDetail;
  locale?: string;
  onClose: () => void;
  onClosed: (counter: CounterDetail) => void;
  /** BR-SHL-025: null = this deployment can commit it. */
  writeBlockedReason: string | null;
  client?: ApiClient;
}

export function CloseCounterModal(props: CloseCounterModalProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const [counted, setCounted] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [closedAt, setClosedAt] = useState("");
  // IS-8 / BR-SHL-023 — an explicit prop wins, the shell's tenant settings are
  // the fallback, and there is no seed default in the shipped bundle.
  const { timeZone, dateFormat } = useRegional(props);
  const closedAtPrefill = useMemo(() => nowInZone(timeZone), [timeZone]);
  const closedAtBounds = useMemo(() => sameDayBounds(timeZone), [timeZone]);

  const { counter } = props;
  const systemTotal = countableSystemTotal(counter.methods);
  const countedTotal = countedTogether(counter.methods, counted);
  const difference =
    countedTotal === null ? null : subtractDecimalStrings(countedTotal, systemTotal);
  // A note is required exactly when the drawer does not match. Until the clerk
  // has finished counting there is no difference to explain, so neither.
  const noteRequired = difference !== null && !isZeroAmount(difference);

  const commit = useMutation({
    mutationFn: () =>
      closeCounter(client, counter.code, {
        counted_totals: counted,
        ...(note.trim() === "" ? {} : { note: note.trim() }),
        // ⚠ **REQUIRED BY `counter_close`, AND MISSING UNTIL `DEF-PAY-6315`.**
        // `BR-TEN-043` / gate G6: nothing under `apps/payments/` reads a clock,
        // so the moment the drawer was sealed is an INPUT. A tenant WALL CLOCK,
        // which `_moment` anchors in the utility's own zone (BR-TEN-081) —
        // never an offset computed a second time in the browser.
        closed_at: closedAt,
      }),
  });

  async function submit(): Promise<FormSubmitOutcome> {
    if (noteRequired && note.trim() === "") {
      return {
        ok: false,
        error: {
          code: "VAL_REQUIRED",
          message_key: "payments.counter.close.noteRequired",
          field_errors: [{ field: "note", message_key: "payments.counter.close.noteRequired" }],
        },
      };
    }
    try {
      const sealed = await commit.mutateAsync();
      void queryClient.invalidateQueries({ queryKey: countersQueryKey() });
      void queryClient.invalidateQueries({ queryKey: counterQueryKey(counter.code) });
      props.onClosed(sealed);
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
      title={t("payments.counter.close.title")}
      schema={closeCounterSchema(counter.methods)}
      values={{ counted, note, closed_at: closedAt }}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("payments.counter.close.commit")}
      // B14 rule 6 — p056: *"Close batch, danger tier — B14 rule 6, and it is
      // irreversible."*
      submitVariant="danger"
      cancelLabel={t("payments.counter.close.cancel")}
      commitBlocked={props.writeBlockedReason ?? undefined}
    >
      {/* ① — the consequence before an irreversible act. p056 draws it as two
          sentences and annotates it *"two sentences, five words each"*, which
          is B14 rule 33's consequence cap met rather than approached. */}
      <ConsequenceBox
        tone="check"
        title={t("payments.counter.close.consequenceTitle")}
        body={t("payments.counter.close.consequenceBody", { counter: counter.code })}
        data-consequence="counter-close"
      />
      <CountComparison
        methods={counter.methods}
        currency={counter.currency}
        locale={props.locale}
        editable
        counted={counted}
        onCountedChange={(methodId, value) =>
          setCounted((current) => ({ ...current, [methodId]: value }))
        }
        idPrefix="counter-close"
        t={t}
      />
      <TextField
        id="note"
        label={t("payments.counter.close.note")}
        value={note}
        onChange={setNote}
        required={noteRequired}
        help={t("payments.counter.close.noteHelp")}
      />
      {/* ⚠ **THE PICKER, ON ALL FOUR COUNTER WRITES** — PO ruling 2026-09-23,
          *"(a) Picker on all four, same as opening"*, answering the worked
          case *"Dana closes the till at 17:05 but counts the cash at 17:20 —
          which is the closing time?"*. Prefilled with now on the utility's
          clock, in the utility's format, and bounded to the utility's own
          business day (`BR-PAY-1191`). No help line: rule 33 puts RATIONALE at
          ZERO WORDS ON SCREEN. */}
      <DateTimeField
        id="closed_at"
        label={t("payments.counter.close.closedAt")}
        required
        value={closedAt}
        onChange={setClosedAt}
        prefill={closedAtPrefill}
        dateFormat={dateFormat}
        min={closedAtBounds.min}
        max={closedAtBounds.max}
      />
    </FormModal>
  );
}

export default CloseCounterModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §3.3 · §4 row `P2.6` · blueprint p055–p056 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(`POST /counters/{ref}/close` is `P2.2`, LANE P2-API's) C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/counterScreens.dom.test.tsx · G31 · routeBUtilities.test.ts
// exceptions: E3 the endpoint is NOT SERVED at this commit · E3 no sentence about the ledger appears on this screen — the blueprint's *"counting is not a posting"* was superseded by `CR-136-BRC07` §3.3 and its replacement is rationale, which B14 rule 33 keeps off the screen
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
