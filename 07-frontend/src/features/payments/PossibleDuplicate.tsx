// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-PAY-9263 — two $30.00 card payments, same account, same day,
//           same reference AUTH-S8-0030, both saved silently.
// Ruling:   PO 2026-10-03, verbatim: *"Same card or ACH payment entered twice -
//           B Warn "Looks like a duplicate", and let the clerk confirm"*.
// Rule:     BR-PAY-1199 (server: `apps/payments/duplicates.py`).
// Doors:    Take payment (account) · Record payment (S35) · the request page's
//           Take payment · New Connection step 4.
// Tests:    PossibleDuplicate.dom.test.tsx
// ───────────────────────────────────────────────────────
//
// ONE COMPONENT, FOUR DOORS (B14 rule 43). The server answers a card or ACH
// payment that matches one already recorded with 409 `BIZ-IDEMPOTENT`,
// `payments.record.possible_duplicate`, and the earlier payment in `params`.
// Nothing was saved. This panel names the earlier payment and offers two
// buttons: *Go back* (change something) and *Record anyway* (resend with the
// confirm flag, which saves it and leaves the override on the audit row).
//
// Copy is capped by B14 rule 33: a 3-word title, one 5-word fact, labels and
// two button words. Why the warning exists is RATIONALE — zero words on screen.
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { isApiError } from "@/api/client";
import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import { formatMoney } from "@/components/MoneyCell";
import { useTenantRegional } from "@/components/TenantRegional";

/** The earlier payment the server says this one resembles. */
export interface EarlierPayment {
  paymentNo: string;
  postedOn: string;
  amount: string;
  currency: string;
  confirmation: string;
  /** `DEF-PAY-10782` (P8 = A) — which match fired: `reference` (the same
   *  card/ACH authorisation today, open bill or not) or `paid_bill` (Q1). */
  matchedOn: string;
}

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/**
 * The earlier payment, when `error` is the card/ACH duplicate WARNING — else
 * `null`, and the caller renders the error the ordinary way.
 */
export function possibleDuplicateOf(error: unknown): EarlierPayment | null {
  if (!isApiError(error)) {
    return null;
  }
  const params = error.params ?? {};
  if (params.possible_duplicate !== true) {
    return null;
  }
  return {
    paymentNo: text(params.payment_no),
    postedOn: text(params.posted_on),
    amount: text(params.amount),
    currency: text(params.currency),
    confirmation: text(params.confirmation),
    matchedOn: text(params.matched_on),
  };
}

/**
 * The state every door holds: the warning (or none), and whether the NEXT
 * submit is the clerk's *Record anyway*. `confirmNext()` is called by the
 * button's click, which fires before the form's submit event; `takeConfirm()`
 * reads it once and resets it, so a later ordinary press asks again.
 */
export function useDuplicateWarning() {
  const [earlier, setEarlier] = useState<EarlierPayment | null>(null);
  const confirmed = useRef(false);
  return {
    earlier,
    warn: setEarlier,
    clear: () => setEarlier(null),
    confirmNext: () => {
      confirmed.current = true;
    },
    takeConfirm: (): boolean => {
      const value = confirmed.current;
      confirmed.current = false;
      return value;
    },
  };
}

export function PossibleDuplicateNotice(props: {
  earlier: EarlierPayment;
  onGoBack: () => void;
  /** Called on *Record anyway*. With `submits`, the button is the form's own
   *  submit button and this only marks the next submit as confirmed. */
  onRecordAnyway: () => void;
  submits?: boolean;
  working?: boolean;
}) {
  const { t } = useTranslation();
  const regional = useTenantRegional();
  const { earlier } = props;
  const day =
    regional === null || earlier.postedOn === ""
      ? earlier.postedOn
      : formatDate(earlier.postedOn, regional.timeZone, regional.dateFormat);
  const money =
    earlier.amount === "" || earlier.currency === ""
      ? earlier.amount
      : formatMoney(earlier.amount, earlier.currency);
  // DEF-PAY-10776 — the pressed commit button is disabled while the request
  // runs, so focus fell to the page; the warning takes it when it appears.
  const panelRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    panelRef.current?.focus();
  }, []);
  const rows: [string, string][] = [
    [t("payments.duplicate.receipt"), earlier.paymentNo],
    [t("payments.duplicate.date"), day],
    [t("payments.duplicate.amount"), money],
    [t("payments.duplicate.reference"), earlier.confirmation],
  ];
  return (
    <div
      ref={panelRef}
      tabIndex={-1}
      role="alert"
      data-possible-duplicate={earlier.paymentNo}
      className="flex max-w-[640px] flex-col gap-3 border border-divider border-l-4 border-l-[var(--color-warning-700)] bg-[color-mix(in_srgb,var(--color-warning-700)_8%,transparent)] px-4 py-3"
    >
      <div className="flex flex-col gap-1">
        <p className="m-0 text-base font-semibold text-neutral-900">
          {t("payments.duplicate.title")}
        </p>
        {/* `DEF-PAY-10782` — a repeated card/ACH reference is warned on an
            OPEN bill too, so "The bill is paid." would be false there. */}
        <p className="m-0 text-body text-neutral-800">
          {t(earlier.matchedOn === "reference" ? "payments.duplicate.bodyReference" : "payments.duplicate.body")}
        </p>
      </div>
      <dl className="m-0 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1 text-body">
        {rows.map(([label, value]) => (
          <div key={label} className="contents">
            <dt className="text-neutral-600">{label}</dt>
            <dd className="m-0 tabular-nums text-neutral-900">{value}</dd>
          </div>
        ))}
      </dl>
      {/* Two buttons and no third primary: the form's own commit button is
          the screen's one primary (B14 button rules). */}
      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="ghost" onClick={props.onGoBack} disabled={props.working === true}>
          {t("payments.duplicate.goBack")}
        </Button>
        <Button
          type={props.submits === true ? "submit" : "button"}
          data-record-anyway=""
          onClick={props.onRecordAnyway}
          disabled={props.working === true}
        >
          {t("payments.duplicate.recordAnyway")}
        </Button>
      </div>
    </div>
  );
}
