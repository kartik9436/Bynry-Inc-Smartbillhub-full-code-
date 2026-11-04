// ── Trace ──────────────────────────────────────────────
// Change:   `CR-139-BRC07` `P5.7` — §03 tab 5, frames **5·1 Settlements** and
//           **5·2 Settlement**, `05-prototype/06 Payments Page Blueprint.pdf`
//           p069–p072 read AS IMAGES at scale 2.0 (B14 rule 42).
// Screens:  5·1 Settlements · 5·2 Settlement (`S-NEW · PAY-P`)
// Rules:    B14 rule 31 (the address carries the provider's reference, never a
//           uuid) · rule 33 (a LABEL ≤ 3 words, a FACT ≤ 6) · rule 43 (a piece
//           of UI is a COMPONENT — these live here so BOTH screens read one
//           expression) · rule 21 (Tailwind utilities only) · BR-SHL-023 (ONE
//           money formatting path)
// Tests:    src/features/payments/settlementScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
/**
 * What 5·1 and 5·2 share — **the route, the two words, and the bank mark.**
 *
 * ⚠ **THIS FILE EXISTS BECAUSE B14 RULE 43 SAYS SO, AND THE TEST IS
 * ADDRESSABILITY.** Both screens render the bank state, both spell a payout's
 * reference, and both build the same address. Written inline in either page,
 * the other would have to copy it, and the two would drift — which is the
 * measured failure rule 43 was ruled on. It is also what lets the rules be
 * asserted without mounting a 3,600-line page.
 */
import type { ReactNode } from "react";

import { MoneyCell } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";

import type { SettlementRef, SettlementStatus } from "@/api/settlementEndpoints";

/** The tab's own address — the same string `PAYMENTS_TABS` declares, so the
 *  strip and the row link cannot point at two places. */
export const SETTLEMENTS_ROUTE = "/payments/settlements";

/**
 * 5·2's address, TENANT-RELATIVE like every route constant in this feature.
 *
 * ⚠ **THE SEGMENT IS THE PROVIDER'S OWN REFERENCE** — p071 draws
 * `/:tenant/payments/settlements/STL-260921-CARD`. B14 rule 31: an address bar
 * is the most visible field a screen has, so a primary key may not ride in it.
 * `settlements_read.settlement_by_code` is the server half, and it refuses an
 * ambiguous reference by name rather than answering the first of two.
 */
export function settlementRoute(code: SettlementRef): string {
  return `${SETTLEMENTS_ROUTE}/${encodeURIComponent(code)}`;
}

/** BR-SHL-011 filter names, shared so the chip and the request agree. */
export const SETTLEMENT_STATE_FILTER = "state";
export const SETTLEMENT_PROVIDER_FILTER = "provider";
export const SETTLEMENT_MATCHED = "matched";
export const SETTLEMENT_RECEIVED = "received";

/** React Query keys. One place, so a screen that invalidates cannot miss a
 *  sibling's cache. */
export const settlementsQueryKey = () => ["payments", "settlements"] as const;
export const settlementQueryKey = (ref: SettlementRef) =>
  ["payments", "settlement", ref] as const;
export const settlementMembersQueryKey = (ref: SettlementRef) =>
  ["payments", "settlement", ref, "members"] as const;

export type Translator = (key: string, params?: Record<string, unknown>) => string;

/**
 * ⚠ **THE BANK COLUMN IS ONE FACT DRAWN TWO WAYS, AND THE DATABASE GUARANTEES
 * THEY AGREE.** `ck_settlements_matched_has_line` makes *matched with no line*
 * unwritable, so this never has to reconcile `status` against
 * `bank_reference`: a matched payout HAS a credit, and a received one has not.
 *
 * p070 draws a green **Matched** pill in that column; p071 draws the credit's
 * own reference, `BRM-2609-0044`, as the fourth tile. Both are this one fact.
 *
 * ⚠ **A MATCHED PAYOUT WHOSE BANK LINE CARRIES NO REFERENCE STILL SAYS
 * MATCHED.** `bank_lines.reference` is nullable and B14 rule 31 forbids
 * falling back to the line's key, so the pill stands alone rather than
 * printing an id nobody could quote.
 */
export function settlementStatusTone(status: SettlementStatus): StatusTone {
  return status === SETTLEMENT_MATCHED ? "success" : "warning";
}

export function settlementStatusLabel(status: SettlementStatus, t: Translator): string {
  return t(
    status === SETTLEMENT_MATCHED
      ? "payments.settlement.state.matched"
      : "payments.settlement.state.unmatched",
  );
}

export function BankMark(props: {
  status: SettlementStatus;
  reference: string | null;
  t: Translator;
}): ReactNode {
  const { status, reference, t } = props;
  return (
    <span className="inline-flex items-center gap-2">
      <StatusPill tone={settlementStatusTone(status)}>
        {settlementStatusLabel(status, t)}
      </StatusPill>
      {reference !== null && <span className="text-neutral-700">{reference}</span>}
    </span>
  );
}

/**
 * Money on either screen, with a stated ABSENCE where a figure did not arrive.
 *
 * ⚠ **`absent` IS A SENTENCE THE CALLER CHOOSES AND NEVER A ZERO.** A day-shaped
 * tile answers `null` when the caller named no business day (`BR-TEN-043`), and
 * `?? "0"` there would turn *"we cannot answer"* into *"nothing was paid out"* —
 * `DEF-127`'s shape, which reached a live Counter tab this month.
 */
export function SettlementMoney(props: {
  amount: string | null;
  currency: string;
  locale?: string;
  absent?: string;
}): ReactNode {
  if (props.amount === null) {
    return <span className="text-neutral-700">{props.absent ?? "—"}</span>;
  }
  return <MoneyCell amount={props.amount} currency={props.currency} locale={props.locale} />;
}

/**
 * A percentage the SERVER computed, as a sentence fragment — `1.91%`.
 *
 * ⚠ **IT IS NEVER COMPUTED IN THE BROWSER.** Hard rule 2 puts money at four
 * decimals and a percentage at six, and dividing two decimal STRINGS in
 * JavaScript is a float division — the one arithmetic this product refuses to
 * do on a money path. The server sends the figure already rounded for display.
 */
export function Percent(props: { value: string | null; absent?: string }): ReactNode {
  if (props.value === null) {
    return <span className="text-neutral-700">{props.absent ?? "—"}</span>;
  }
  return <span className="tabular-nums">{`${props.value}%`}</span>;
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-139-BRC07 §4 row `P5.7` · blueprint p069–p072 as images at 2.0
// generated: 2026-09-23 by LANE P5-SCREENS
// checklist: A=n/a B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/settlementScreens.dom.test.tsx · G31 (this file is on route-b-migrated.txt)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
