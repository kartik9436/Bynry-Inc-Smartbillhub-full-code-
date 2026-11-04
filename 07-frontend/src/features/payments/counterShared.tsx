// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — the six Counter screens, from
//           `05-prototype/06 Payments Page Blueprint.pdf` §03 frames 3·1
//           (p051–p052), 3·2 (p052–p053) and 3·3a–d (p054–p059), **read as
//           IMAGES at scale 2.0** (B14 rule 42).
// Screens:  `PAY-04` Counters · `PAY-07` Your counter
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — this file is what that
//           rule means for the four readers of *Not counted*) · rule 31 (no
//           database id is ever the visible value of a field) · rule 33 (a
//           LABEL ≤ 3 words, a FACT ≤ 6, RATIONALE is zero words on screen) ·
//           rule 21 (Tailwind utilities; every file here is on
//           `src/styles/route-b-migrated.txt` in the same commit) · rule 36
//           (layout from the drawing, style from r10, the kit is how) ·
//           rule 37 (a drawn figure is an illustration, never a fact) ·
//           `CR-136-BRC07` §3.1 · §3.2 · §3.3
// Tests:    src/features/payments/counterScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
// The pieces the six Counter screens are built from.
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE EXISTS AT ALL — `CR-136-BRC07` §3.2, IN ITS OWN WORDS
// ══════════════════════════════════════════════════════════════════════════
// *"`Not counted` is one derived expression with four readers — screen 3·1's
// list, its filter chip, `P2.11`'s notice, and phase 2's own done-when. Write
// it once (B14 rule 43)."*
//
// `isNotCounted` below is that expression and it is written once. Two of the
// four readers are in this repository's front end and both call it; the third
// is `P2.11`'s notification and the fourth is a sentence in the CR. A
// definition copied into a second `if` is two definitions the day the ruling
// moves, which is exactly what rule 43 was ratified on.
import type { ReactNode } from "react";

import { useTranslation } from "react-i18next";

import type { CounterDetail, CounterMethodTotal, CounterRow } from "@/api/counterEndpoints";
import { formatMoney, MONEY_DISPLAY_DECIMALS } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import type { Translator } from "@/features/tenancy/settingsShared";

// ══════════════════════════════════════════════════════════════════════════
// ADDRESSES
// ══════════════════════════════════════════════════════════════════════════

/** 3·1, and it is the Counter TAB's own path — the list is the tab. */
export const COUNTERS_ROUTE = "/payments/counter";

/**
 * 3·2 — `proposed /:tenant/payments/counter/CTR-260921-DW`, drawn on p052.
 *
 * ⚠ **THE SEGMENT IS THE COUNTER'S CODE AND NOT ITS ID** (B14 rule 31). An
 * address bar is the most visible field a screen has.
 */
export function counterRoute(code: string): string {
  return `${COUNTERS_ROUTE}/${encodeURIComponent(code)}`;
}

/**
 * The address that OPENS 3·3a, rather than a click handler that does.
 *
 * ⚠ **A DOOR NEEDS AN ADDRESS, AND THAT IS `DEF-CWP-3925`'s LESSON RATHER
 * THAN A PREFERENCE.** 3·3a is drawn as *"a modal, like every other act in
 * this tab"*, and a modal opened by an `onClick` carries nothing a test can
 * assert — which is how the customer portal shipped six dead doors over live
 * screens. So the control is a link, the query opens the modal, and the
 * assertion `toContain(COUNTER_START_ROUTE)` can be written.
 *
 * It is also what `P2.7` needs: *"`Start counter →` in every payments page
 * head"* has to reach this modal from six other tabs, and only an address can.
 */
export const COUNTER_START_ROUTE = `${COUNTERS_ROUTE}?start=1`;

/** The one query the address above sets, read by 3·1 to open 3·3a. */
export const COUNTER_START_PARAM = "start";

// ══════════════════════════════════════════════════════════════════════════
// *NOT COUNTED* — THE ONE DERIVED EXPRESSION (`CR-136-BRC07` §3.2)
// ══════════════════════════════════════════════════════════════════════════

/**
 * **A till the supervisor sealed and nobody ever counted.**
 *
 * `close_kind = 'forced' AND declared_at IS NULL`, verbatim from
 * `CR-136-BRC07` §3.2.
 *
 * ⚠ **A COUNTED CLOSE IS NOT IN IT AND NEITHER IS THE SYSTEM TILL**, and both
 * omissions are load-bearing. A `counted` close was counted at the moment it
 * closed. A `system` till is nobody's — born closed, no owner, no centre, no
 * drawer — so *"nobody counted it"* is not a finding about it, it is its
 * definition. Widening this to *"anything without a counted total"* would put
 * every ACH day on a supervisor's chase list.
 *
 * ⚠ **AND A DECLARED TILL LEAVES THIS SET WITHOUT ITS CLOSE CHANGING.** §3.2:
 * *"(a) Keep it as a forced close and add the late count beside it"*. The row
 * still says force-closed, and it stops saying *Not counted*.
 */
export function isNotCounted(row: Pick<CounterRow, "close_kind" | "declared_at">): boolean {
  return row.close_kind === "forced" && row.declared_at === null;
}

/** Whether 3·3d's door is open on this row — the same question, said in the
 *  vocabulary of the control rather than of the finding. A till you may
 *  declare a count for is exactly a till nobody counted. */
export const canDeclareCount = isNotCounted;

/** A till that is still open — `closed_at IS NULL`. */
export function isOpenTill(row: Pick<CounterRow, "closed_at">): boolean {
  return row.closed_at === null;
}

/**
 * The value 3·1's `Not counted ×` chip sends, and the one the tile's count is
 * folded on. **One string, so the chip and the tile cannot disagree.**
 */
export const NOT_COUNTED_FILTER_VALUE = "not_counted";
export const OPEN_FILTER_VALUE = "open";
/** `f.<name>` per BR-SHL-011's URL grammar. */
export const COUNTER_STATE_FILTER = "state";

// ══════════════════════════════════════════════════════════════════════════
// HOW A CLOSE IS MARKED — 3·1 ANNOTATION ③, AS `CR-136-BRC07` §3.1 LEAVES IT
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE DRAWING'S ③ IS `by the system`, AND IT MARKS AN AUTO-CLOSE THE PO
// STRUCK.** p052, verbatim: *"`by the system` · an auto-close, marked so it
// can never read as a real close"*. `CR-136-BRC07` §3.1 then ruled — *"(a)
// Your ruling stands — no auto-close. A System Admin closes it"* — so **no
// midnight job is written and no till ever closes itself.**
//
// What survives is the INTENT of ③ rather than its one word: a seal that is
// not a real close is marked so it can never read as one. Two such seals
// exist and this repository already distinguishes them in
// `counter_sessions.close_kind`:
//
//   · `forced` — a supervisor sealed somebody else's drawer. §3.1's whole
//     mechanism, and the only way a forgotten till gets closed.
//   · `system` — the system till, born closed, nobody's, for ACH, card, wire
//     and lockbox (`reconciliation.py`). The drawing's own words still fit
//     this one exactly, so this one keeps them.
//
// A `counted` close is a real close and draws no mark at all, which is the
// other half of ③ working.

export function closeKindTone(kind: CounterRow["close_kind"]): StatusTone | null {
  if (kind === "forced") {
    return "warning";
  }
  if (kind === "system") {
    return "muted";
  }
  return null;
}

/** The mark beside a closing time. `null` for a counted close and for a till
 *  that is still open — a real close is not annotated. */
export function CloseKindMark(props: { kind: CounterRow["close_kind"]; t: Translator }) {
  const tone = closeKindTone(props.kind);
  if (tone === null || props.kind === null) {
    return null;
  }
  return <StatusPill tone={tone}>{props.t(`payments.counter.closeKind.${props.kind}`)}</StatusPill>;
}

// ══════════════════════════════════════════════════════════════════════════
// MONEY — DECIMAL STRINGS, ADDED AS INTEGERS OF THE SMALLEST STORED UNIT
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **NEVER `Number(a) + Number(b)`, AND HARD RULE 2 IS WHY.** Money is stored
// to four decimals and travels as a string precisely so no double ever touches
// it; `0.1 + 0.2` is the canonical counter-example and a drawer is the one
// place in this product where a figure exists to be compared with reality.
// `paymentsShared.sumDecimalStrings` already does this for the payments list
// and is REUSED rather than restated — this file adds only subtraction, which
// it had no reason to have.

/** Scale two decimal strings to a common integer basis and subtract. Returns
 *  a decimal string, or `null` when either side is not a decimal literal. */
export function subtractDecimalStrings(left: string, right: string): string | null {
  const parse = (value: string): { digits: bigint; scale: number } | null => {
    const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value.trim());
    if (match === null) {
      return null;
    }
    const fraction = match[3] ?? "";
    const digits = BigInt(`${match[1]}${match[2]}${fraction}`);
    return { digits, scale: fraction.length };
  };
  const a = parse(left);
  const b = parse(right);
  if (a === null || b === null) {
    return null;
  }
  const scale = Math.max(a.scale, b.scale);
  const lift = (side: { digits: bigint; scale: number }): bigint =>
    side.digits * 10n ** BigInt(scale - side.scale);
  const total = lift(a) - lift(b);
  if (scale === 0) {
    return total.toString();
  }
  const negative = total < 0n;
  const magnitude = (negative ? -total : total).toString().padStart(scale + 1, "0");
  const whole = magnitude.slice(0, magnitude.length - scale);
  const fraction = magnitude.slice(magnitude.length - scale);
  return `${negative ? "-" : ""}${whole}.${fraction}`;
}

/** Whether a decimal string is exactly zero. A close with a zero difference
 *  needs no note (p056) and posts nothing to the ledger (§3.3). */
export function isZeroAmount(amount: string | null): boolean {
  if (amount === null) {
    return false;
  }
  return /^-?0*(?:\.0*)?$/.test(amount.trim());
}

// ══════════════════════════════════════════════════════════════════════════
// THE COMPARISON — 3·3b AND 3·3d ARE THE SAME TABLE, TWICE
// ══════════════════════════════════════════════════════════════════════════
//
// p055's frame is captioned *"A COMPARISON, NEVER A READ-BACK"* and p058's is
// *"THE SAME COMPARISON, AFTER THE FACT"*. The drawing says they are one
// piece; rule 43 says one piece is one component.

/**
 * ⚠ **THE FLOAT SITS INSIDE THE CASH LINE RATHER THAN BEING NETTED OUT**, and
 * the blueprint files that as a decision rather than a detail (p056 GAP box).
 * The server sends the cash line already carrying it; this constant is only
 * how the screen knows which row to LABEL, and `cash` is the one tender an
 * opening float can be.
 */
export const FLOAT_RIDES_ON_METHOD_CODE = "cash";

/** The countable methods, in the drawing's order, then the rest. Only cash and
 *  cheques are countable and the server says which is which. */
export function orderMethodsForCounting(
  methods: readonly CounterMethodTotal[],
): readonly CounterMethodTotal[] {
  return [...methods].sort((left, right) => {
    if (left.countable !== right.countable) {
      return left.countable ? -1 : 1;
    }
    return 0;
  });
}

/** What the system says the COUNTABLE methods took, together. */
export function countableSystemTotal(methods: readonly CounterMethodTotal[]): string {
  return methods
    .filter((method) => method.countable)
    .reduce<string>(
      (running, method) => addDecimalStrings(running, method.system_total) ?? running,
      "0",
    );
}

/** What the clerk has typed so far, across the countable methods. */
export function countedTogether(
  methods: readonly CounterMethodTotal[],
  counted: Readonly<Record<string, string>>,
): string | null {
  let running = "0";
  for (const method of methods) {
    if (!method.countable) {
      continue;
    }
    const typed = counted[method.method_id];
    if (typed === undefined || typed.trim() === "") {
      return null; // not finished counting — a partial total is a wrong total
    }
    const next = addDecimalStrings(running, typed.trim());
    if (next === null) {
      return null;
    }
    running = next;
  }
  return running;
}

/** Addition on the same integer basis as `subtractDecimalStrings`. */
export function addDecimalStrings(left: string, right: string): string | null {
  const negated = right.trim().startsWith("-") ? right.trim().slice(1) : `-${right.trim()}`;
  return subtractDecimalStrings(left, negated);
}

export interface CountRowState {
  /** Keyed by `payment_methods.id` — the shape `counted_totals` declares. */
  counted: Readonly<Record<string, string>>;
  onCountedChange: (methodId: string, value: string) => void;
}

export interface CountComparisonProps extends Partial<CountRowState> {
  methods: readonly CounterMethodTotal[];
  currency: string;
  locale?: string;
  /** Absent = the figures are already recorded and the table is read-only. */
  editable: boolean;
  t: Translator;
  /** The id the labelled inputs hang off, so two of these can never collide. */
  idPrefix: string;
}

const HEAD_CELL = "text-left text-xs uppercase tracking-wide text-neutral-700 font-bold py-2 px-3";
const HEAD_CELL_NUM = `${HEAD_CELL} text-right`;
const BODY_CELL = "py-2 px-3 border-t border-neutral-200";
const BODY_CELL_NUM = `${BODY_CELL} text-right tabular-nums`;
const TOTAL_CELL = "py-2 px-3 border-t border-neutral-900 font-bold";
const TOTAL_CELL_NUM = `${TOTAL_CELL} text-right tabular-nums`;

/**
 * METHOD · SYSTEM SAYS · YOU COUNTED · DIFFERENCE, and a `Countable together`
 * total row.
 *
 * ⚠ **AN UNCOUNTABLE METHOD GETS NO INPUT, AND THAT IS THE POINT OF THE WHOLE
 * SCREEN.** p056, verbatim: *"A close screen that demands a counted card total
 * trains clerks to type the system figure back at it, which makes the whole
 * reconciliation worthless."* Its YOU COUNTED cell says *Not counted* and its
 * DIFFERENCE cell is a dash; it is in neither total.
 */
export function CountComparison(props: CountComparisonProps) {
  const { t, methods, currency, locale } = props;
  const ordered = orderMethodsForCounting(methods);
  const counted = props.counted ?? {};
  const systemTotal = countableSystemTotal(ordered);
  const countedTotal = countedTogether(ordered, counted);
  const totalDifference =
    countedTotal === null ? null : subtractDecimalStrings(countedTotal, systemTotal);

  return (
    <table className="w-full border-collapse text-base">
      <thead>
        <tr>
          <th scope="col" className={HEAD_CELL}>
            {t("payments.counter.count.col.method")}
          </th>
          <th scope="col" className={HEAD_CELL_NUM}>
            {t("payments.counter.count.col.systemSays")}
          </th>
          <th scope="col" className={HEAD_CELL_NUM}>
            {t("payments.counter.count.col.youCounted")}
          </th>
          <th scope="col" className={HEAD_CELL_NUM}>
            {t("payments.counter.count.col.difference")}
          </th>
        </tr>
      </thead>
      <tbody>
        {ordered.map((method) => (
          <CountComparisonRow
            key={method.method_id}
            method={method}
            currency={currency}
            locale={locale}
            editable={props.editable}
            typed={counted[method.method_id] ?? ""}
            onTyped={(value) => props.onCountedChange?.(method.method_id, value)}
            idPrefix={props.idPrefix}
            t={t}
          />
        ))}
      </tbody>
      <tfoot>
        <tr>
          <th scope="row" className={TOTAL_CELL}>
            {t("payments.counter.count.togetherRow")}
          </th>
          <td className={TOTAL_CELL_NUM}>{formatMoney(systemTotal, currency, locale)}</td>
          <td className={TOTAL_CELL_NUM} data-counted-together="">
            {countedTotal === null ? "—" : formatMoney(countedTotal, currency, locale)}
          </td>
          <td className={TOTAL_CELL_NUM} data-total-difference="">
            <DifferenceFigure amount={totalDifference} currency={currency} locale={locale} />
          </td>
        </tr>
      </tfoot>
    </table>
  );
}

function CountComparisonRow(props: {
  method: CounterMethodTotal;
  currency: string;
  locale?: string;
  editable: boolean;
  typed: string;
  onTyped: (value: string) => void;
  idPrefix: string;
  t: Translator;
}) {
  const { method, t } = props;
  const inputId = `${props.idPrefix}-${method.method_id}`;
  const recorded = method.counted_total ?? null;
  const shown = props.editable ? props.typed : (recorded ?? "");
  const difference =
    shown.trim() === "" ? null : subtractDecimalStrings(shown.trim(), method.system_total);

  return (
    <tr>
      <th scope="row" className={`${BODY_CELL} text-left font-normal`}>
        {/* p056 draws this row as `Cash incl. float`, and the GAP box beside it
            says why: the float sits INSIDE the cash line rather than being
            netted out. The method's own name everywhere else. */}
        {method.method_code === FLOAT_RIDES_ON_METHOD_CODE
          ? t("payments.counter.count.cashInclFloat")
          : method.method_name}
      </th>
      <td className={BODY_CELL_NUM}>
        {formatMoney(method.system_total, props.currency, props.locale)}
      </td>
      <td className={BODY_CELL_NUM}>
        {!method.countable ? (
          // ⚠ p056 ③ — *"you cannot count a card total in a drawer, so the
          // screen does not pretend"*. A FACT of two words (B14 rule 33).
          <span className="text-neutral-700">{t("payments.counter.notCounted")}</span>
        ) : props.editable ? (
          <>
            <label className="sr-only" htmlFor={inputId}>
              {t("payments.counter.count.countedFor", { method: method.method_name })}
            </label>
            <input
              id={inputId}
              className="w-32 text-right tabular-nums border border-field-border px-2 py-1 bg-[white] text-body"
              inputMode="decimal"
              autoComplete="off"
              value={props.typed}
              onChange={(event) => props.onTyped(event.target.value)}
            />
          </>
        ) : recorded === null ? (
          "—"
        ) : (
          formatMoney(recorded, props.currency, props.locale)
        )}
      </td>
      <td className={BODY_CELL_NUM}>
        {method.countable ? (
          <DifferenceFigure amount={difference} currency={props.currency} locale={props.locale} />
        ) : (
          "—"
        )}
      </td>
    </tr>
  );
}

/** A difference, red when it is not zero. `null` renders a dash rather than a
 *  zero somebody might read as *counted and balanced* (the `DEF-127` shape). */
export function DifferenceFigure(props: {
  amount: string | null;
  currency: string;
  locale?: string;
}) {
  if (props.amount === null) {
    return <>—</>;
  }
  const zero = isZeroAmount(props.amount);
  return (
    <span className={zero ? undefined : "text-danger-700"}>
      {formatMoney(props.amount, props.currency, props.locale)}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE TILL'S OWN NAME, EVERYWHERE A DIALOG OPENS OVER IT
// ══════════════════════════════════════════════════════════════════════════

/** `CTR-260921-DW · DANA WHITFIELD` — the eyebrow every act in this tab draws
 *  above its heading (3·3b p055, 3·3c p057, 3·3d p058). Whose till it is, said
 *  FIRST, because these are acts on another person's work. */
export function counterKicker(row: Pick<CounterRow, "code" | "owner_name">): string {
  // The separator is punctuation and carries no language, so this composes no
  // catalogue key. The system till has no owner by constraint, and then the
  // eyebrow is the code alone rather than a dangling separator.
  return row.owner_name === null ? row.code : `${row.code} · ${row.owner_name.toLocaleUpperCase()}`;
}

/**
 * **A FACT ABOUT THE TILL, STATED ABOVE A FORM.** Two readers, which is why it
 * is a component and not three lines inside each of them (B14 rule 43):
 *
 *   · 3·3c's *"Open since 09/21 09:10 · 6 payments · $402.15"* (p057)
 *   · 3·3d's *"…on 09/18 23:59. Nobody counted it."* (p058 ①)
 *
 * ⚠ **IT IS NOT `ConsequenceBox` AND NOT `AccentBand`, ON PURPOSE.** A
 * consequence says what a commit WILL DO and carries a tag word; this says
 * what is already true. `AccentBand` requires a small-caps legend, and neither
 * drawing has one — adding a word to satisfy a component is how on-screen text
 * grows past B14 rule 33 without anybody deciding to.
 */
export function CounterNote(props: {
  tone: "plain" | "warning";
  children: ReactNode;
  /** A sibling lane's walk finds the record banner by this
   *  (`10-scripts/p2head_counter_door_walkthrough.mjs`); absent renders
   *  byte-for-byte what every existing caller renders today. */
  "data-counter-banner"?: string;
}) {
  const rule = props.tone === "warning" ? "border-l-warning-500" : "border-l-neutral-400";
  return (
    <p
      role="note"
      data-counter-note={props.tone}
      data-counter-banner={props["data-counter-banner"]}
      className={`m-0 border-l-[3px] ${rule} px-3 py-2 text-base text-neutral-800`}
    >
      {props.children}
    </p>
  );
}

/** A money figure rendered for reading, at `MONEY_DISPLAY_DECIMALS` — two,
 *  however many are stored (CLAUDE.md hard rule 2). */
export function CounterMoney(props: {
  amount: string | null;
  currency: string;
  locale?: string;
  absent: string;
}): ReactNode {
  if (props.amount === null) {
    return <span className="text-neutral-700">{props.absent}</span>;
  }
  return <span className="tabular-nums">{formatMoney(props.amount, props.currency, props.locale)}</span>;
}

/** The display precision, re-exported so a Counter screen never reaches for a
 *  second formatter (BR-SHL-023: ONE money formatting path). */
export { MONEY_DISPLAY_DECIMALS };

/** A translator bound to the current catalogue, for components that take one
 *  rather than calling the hook themselves. */
export function useCounterTranslator(): Translator {
  const { t } = useTranslation();
  return (key: string, params?: Record<string, unknown>) =>
    params === undefined ? t(key) : t(key, params);
}

/** Everything a dialog needs about the till it is acting on, without either
 *  screen having to know whether it holds a row or a detail. */
export type CounterSubject = CounterRow | CounterDetail;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §2 · §3.1 · §3.2 · §3.3 · §4 row `P2.6` · blueprint p051–p059 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/counterScreens.dom.test.tsx · G31 (every file listed on src/styles/route-b-migrated.txt in this commit) · routeBUtilities.test.ts
// exceptions: E3 3·1 annotation ③'s word `by the system` is kept for `close_kind = 'system'` and a forced close is marked `Forced` instead — the auto-close ③ described was struck by `CR-136-BRC07` §3.1 · E3 p058 labels the cash row `Cash` where p056 labels the same quantity `Cash incl. float`; one label is used for one quantity and the divergence is reported
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
