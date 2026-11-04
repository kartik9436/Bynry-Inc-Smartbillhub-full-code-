// ── Trace ──────────────────────────────────────────────
// Drawing: 05-prototype/one-time-bill-2026-09-30/*-1-account.png (inventory.md §1.2)
// Plan:    12-one-time-bill-build-plan.md F3
// ───────────────────────────────────────────────────────
/**
 * The six kinds as six equal cards in one row — name bold, use line muted
 * below; the chosen one carries the accent rule and border.
 *
 * Each card is a `<button>` with `aria-pressed`, so the choice is one a
 * keyboard can make and a screen reader can hear. The list is the model's
 * `ONE_TIME_BILL_KIND_ORDER`; the words are the catalogue's.
 */
import type { OneTimeBillKind } from "@/api/billingOpsEndpoints";
import type { Translator } from "@/components/FormModal";

import { ONE_TIME_BILL_KIND_ORDER } from "./oneTimeBillModel";

const CARD =
  "flex min-w-0 flex-col items-start gap-1 border bg-surface px-3 py-3 text-left " +
  "cursor-pointer focus-visible:outline-2 focus-visible:outline-accent";
const CARD_REST = "border-divider border-t-2 border-t-transparent";
const CARD_CHOSEN = "border-accent border-t-2 border-t-accent";

export function KindCards(props: {
  value: OneTimeBillKind;
  onChange: (kind: OneTimeBillKind) => void;
  t: Translator;
  disabled?: boolean;
}) {
  return (
    <div
      className="grid grid-cols-6 gap-2"
      role="group"
      aria-label={props.t("billing.oneTimeBill.kindsLabel")}
      data-otb-kinds=""
    >
      {ONE_TIME_BILL_KIND_ORDER.map((kind) => {
        const chosen = kind === props.value;
        return (
          <button
            key={kind}
            type="button"
            className={`${CARD} ${chosen ? CARD_CHOSEN : CARD_REST}`}
            aria-pressed={chosen}
            disabled={props.disabled === true}
            data-kind={kind}
            onClick={() => props.onChange(kind)}
          >
            <span className="font-heading text-md font-semibold text-text">
              {props.t(`billing.oneTimeBill.kind.${kind}`)}
            </span>
            <span className="text-sm text-neutral-700">
              {props.t(`billing.oneTimeBill.kindUse.${kind}`)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export default KindCards;
