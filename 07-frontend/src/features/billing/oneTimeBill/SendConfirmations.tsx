// ── Trace ──────────────────────────────────────────────
// Ruling: PO 2026-09-30, option B, verbatim: "B · Show all five ticks on the
//         one-time Send card." (decision log; plan F12 as amended; review
//         ledger, the one-time Send row, decision (1))
// Rules:  BR-BIL-058 (the release gate's five facts) · B14 rules 33 (a LABEL
//         ≤ 3 words), 43 (a component, not page code), 44 (the kit)
// ───────────────────────────────────────────────────────
/**
 * The one-time Send card's FIVE release confirmations — the same five a cycle
 * release asks: compliance, email, text, autopay and final.
 *
 * Until the ruling the card asked ONE question, *"I checked the amounts"*, and
 * Send recorded it as all five. BR-BIL-058 keeps them separate because *"a
 * release that went out without the compliance check is a different event from
 * one that did"*. So each is its own tick, Send stays shut until all five are
 * ticked, and the page sends them exactly as ticked.
 *
 * The ids and the state helpers are the cycle gate's own (`GATE_FACTS`,
 * `emptyGateState`, `untakenGateFacts`, `releaseConfirmations` in
 * `billRunShared.tsx`), so the two doors can never name the five differently.
 * Only the WORDS differ: the card's labels are short (B14 rule 33 — a label is
 * at most three words), where the run's gate shows each against its coverage.
 */
import { CheckboxField } from "@/components/FormModal";
import type { Translator } from "@/components/FormModal";

import { GATE_FACTS, untakenGateFacts } from "../billRunShared";
import type { GateState } from "../billRunShared";

/** Server id → the card's short label key. */
const SHORT_LABEL: Record<string, string> = {
  compliance: "billing.oneTimeBill.send.confirm.compliance",
  email_mandate: "billing.oneTimeBill.send.confirm.email",
  sms_mandate: "billing.oneTimeBill.send.confirm.sms",
  autopay_mandate: "billing.oneTimeBill.send.confirm.autopay",
  final: "billing.oneTimeBill.send.confirm.final",
};

/** True only when every one of the five is ticked. */
export function allConfirmed(state: GateState): boolean {
  return untakenGateFacts(state).length === 0;
}

export function SendConfirmations(props: {
  state: GateState;
  onChange: (id: string, checked: boolean) => void;
  t: Translator;
}) {
  const { t } = props;
  return (
    <fieldset className="m-0 border-0 p-0" data-otb-confirmations="">
      <legend className="m-0 mb-2 p-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {t("billing.oneTimeBill.send.confirmTitle")}
      </legend>
      <div className="flex flex-col gap-2">
        {GATE_FACTS.map((fact) => (
          <CheckboxField
            key={fact.id}
            id={`otb-confirm-${fact.id}`}
            label={t(SHORT_LABEL[fact.id] ?? fact.labelKey)}
            checked={props.state[fact.id] === true}
            onChange={(checked) => props.onChange(fact.id, checked)}
          />
        ))}
      </div>
    </fieldset>
  );
}
