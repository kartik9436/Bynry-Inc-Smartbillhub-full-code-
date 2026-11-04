// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 (EP-TEN-07 SCOPE ADDENDUM — the S63–S71 rule-page cards; this is the
//           S66 card's sequence control) · US-PAY-006 (the within-invoice class order this
//           setting IS — the engine half shipped 2026-08-11, the storage 2026-08-15)
//           Screens: S66 (Settings → Configure → Billing defaults)
// Rules:    BR-PAY-038 (the FOUR within-invoice classes and the ruled default sequence) ·
//           BR-PAY-010 (allocation order — "tenant-configurable") · BR-SHL-035 (a rule page
//           is a CARD whose management view is a FORM — this control lives INSIDE that one
//           shell, it is not a screen) · BR-TEN-024 (the page saves atomically; this control
//           only edits the draft) · BR-SHL-025 (a forbidden control is disabled WITH its
//           reason) · BR-SHL-023 (one money formatter) · BR-TEN-080 (money reads 2 dp)
// ───────────────────────────────────────────────────────
// THE REORDER CONTROL FOR `allocation_class_order`, AND THE WORKED EXAMPLE THAT
// SAYS WHAT THE ORDER DOES.
//
// **Why this exists.** PO ruling 2026-08-12, verbatim: *"Cant we give option to
// user to set the rule in settings; Im not sure how Utilities are going to set
// settlement rules ; they might differ in case of HOA or SUb metering ; better
// to let user set the sequence; we can give default option and allow them to
// change the order"*. The storage, the permutation validation and the CALLER
// (`apps.payments.services.tenant_class_order`, read by `record_payment`) all
// landed on 2026-08-15. Nothing could reach the setting from a screen, which is
// hard-won law 2 — *built is not wired* — and this file is the wiring.
//
// **Why there is no "restore the shipped order" button.** The shipped default
// lives once, in `apps.tenancy.settings_families.BILLING_DEFAULTS`, and a copy
// of it here would be a second source of truth free to drift from the order the
// engine actually walks. Reversibility does not need one: a swap is its own
// inverse (`moveInSequence`), and the page's own Discard restores the SERVER's
// saved order. Stated here because the absence of a button is a decision.
//
// ══════════════════════════════════════════════════════════════════════════
// THE WORKED EXAMPLE, AND WHY IT IS NOT A MONEY PATH
// ══════════════════════════════════════════════════════════════════════════
// A reorder control that only lists four phrases tells a utility nothing about
// what it just changed. This panel re-walks the PO's own worked figure under
// whatever order is currently in the draft, so the consequence is on screen
// BEFORE the save rather than in next month's cash application.
//
// THE FIGURE IS THE PO'S, RATIFIED 2026-08-11 (OQ-109 → BR-PAY-038) AND
// RE-CONFIRMED UNMOVED ON 2026-08-12 AND 2026-08-15:
//
//     usage+base 100.58 + tax 8.30 + a tenant-defined service fee 15.00
//     + a late fee 5.00 = 128.88; a 120.00 payment meets 100.58, then 8.30,
//     then 11.12 of the 15.00, and the late fee stays LAST at 0.00.
//
// and the counter-case the settings lane added on 2026-08-15: move the fees
// class ahead of the tenant-defined one and the SAME payment pays the 5.00 late
// fee and 6.12 of the service charge instead. Both are asserted by this file's
// tests, so drift in either goes RED.
//
// **CLAUDE.md rule 2 is respected, not excepted.** No float and no cents column
// exists anywhere here:
//   · these five figures are FIXED CONSTANTS of a printed illustration. No
//     tenant bill, payment or balance is read, computed or written — the panel
//     would render identically for a utility with no bills at all;
//   · the walk is exact integer arithmetic on `bigint`, never `Number()`,
//     `parseFloat` or `toFixed`. MEASURED, not asserted: the identical walk in
//     IEEE-754 doubles pays the tenant-defined class **11.120000000000001**
//     and leaves **3.879999999999999** owed on it, where the PO's ruling says
//     11.12 and 3.88. That is the exact output this file's tests were shown
//     failing on before they were trusted green (hard-won law 7);
//   · the result is handed to `MoneyCell` as a decimal STRING, which is the one
//     formatter (BR-SHL-023) and the one display-rounding boundary (BR-TEN-080);
//   · the SERVER remains the only thing that allocates a real payment. This is
//     a picture of the rule, never a second implementation of it — and if the
//     two ever disagree, the engine is right and this panel is the defect.
import { useTranslation } from "react-i18next";

import { ChevronDownIcon, ChevronUpIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { MoneyCell } from "@/components/MoneyCell";

import {
  ALLOCATION_CLASSES,
  moveInSequence,
  sequenceFromDraft,
  sequenceToDraft,
} from "./settingsRulePages";
import type { RuleParam, RulePage } from "./settingsRulePages";

// ── The illustration's fixed figures (see the header) ──────────────────────
//
// Held in MINOR UNITS as `bigint` so the walk is exact. They are not money in
// the CLAUDE.md-rule-2 sense — nothing here is stored, sent or derived from a
// tenant's books — and they never leave this module as anything but a decimal
// string.

/** The customer's payment: 120.00. */
export const EXAMPLE_PAYMENT_MINOR = 12000n;

/** What the 128.88 bill is made of, per within-invoice class (BR-PAY-038). */
export const EXAMPLE_BILL_MINOR: Readonly<Record<string, bigint>> = {
  usage_base: 10058n, // 100.58
  taxes: 830n, //         8.30
  tenant_defined: 1500n, // 15.00 — the PO's "service fee"
  fees: 500n, //           5.00 — the PO's late fee
};

const MINOR_PER_UNIT = 100n;

/**
 * `12000n → "120.00"`. Exact: integer division and remainder, no float and no
 * `toFixed`. Negative inputs cannot arise (every figure below is a floor at
 * zero) and are formatted correctly anyway rather than left to surprise.
 */
export function minorToAmount(minor: bigint): string {
  const negative = minor < 0n;
  const magnitude = negative ? -minor : minor;
  const whole = magnitude / MINOR_PER_UNIT;
  const part = magnitude % MINOR_PER_UNIT;
  return `${negative ? "-" : ""}${whole}.${part.toString().padStart(2, "0")}`;
}

export interface AllocationExampleRow {
  /** The within-invoice class, in the tenant's own order. */
  klass: string;
  /** What the bill states for it. */
  billed: string;
  /** What this payment meets. */
  met: string;
  /** What is still owed on it after this payment. */
  owed: string;
}

export interface AllocationExample {
  rows: AllocationExampleRow[];
  payment: string;
  total: string;
  stillOwed: string;
}

/**
 * Walk the PO's payment down the tenant's own order.
 *
 * The rule, in one line: each class in turn is met in full if what is left
 * covers it, and otherwise takes what is left — which is exactly what
 * `apps.payments.allocation.allocate_payment` does with the `class_order` it is
 * handed. A class the bill does not state contributes nothing and is skipped;
 * a class the ORDER does not mention is not billed at all here (the server
 * refuses to store such an order, so this can only be a transient draft).
 */
export function workedAllocation(order: readonly string[]): AllocationExample {
  let remaining = EXAMPLE_PAYMENT_MINOR;
  const rows: AllocationExampleRow[] = [];
  for (const klass of order) {
    const billed = EXAMPLE_BILL_MINOR[klass] ?? 0n;
    const met = remaining < billed ? remaining : billed;
    remaining -= met;
    rows.push({
      klass,
      billed: minorToAmount(billed),
      met: minorToAmount(met),
      owed: minorToAmount(billed - met),
    });
  }
  const total = order.reduce((sum, klass) => sum + (EXAMPLE_BILL_MINOR[klass] ?? 0n), 0n);
  const applied = EXAMPLE_PAYMENT_MINOR - remaining;
  return {
    rows,
    payment: minorToAmount(EXAMPLE_PAYMENT_MINOR),
    total: minorToAmount(total),
    stillOwed: minorToAmount(total - applied),
  };
}

/** A choice VALUE renders through the catalog too (no raw enum on screen). */
export function classLabelKey(param: RuleParam, value: string): string {
  return `settings.rules.choice.${param.key}.${value}`;
}

// ── The control ────────────────────────────────────────────────────────────

/**
 * The generic half: an ORDERED list with an explicit move up / move down on
 * every row. Deliberately buttons rather than drag-and-drop — a drag is not
 * keyboard-reachable, has no undo a person can see, and cannot say what it did;
 * two buttons are explicit, reversible and readable by a screen reader.
 *
 * Nothing here validates the permutation. The server owns that refusal
 * (`settings.param_not_permutation`) and a second copy of the check would be a
 * second copy of the rule — the moves this control offers cannot break it
 * anyway, because a swap preserves membership by construction.
 */
export function SequenceReorder(props: {
  param: RuleParam;
  order: readonly string[];
  readOnly: boolean;
  onReorder: (order: string[]) => void;
}) {
  const { t } = useTranslation();
  const { order, param } = props;
  return (
    <ol className="settings-sequence" aria-label={t("settings.rules.sequence.listLabel")}>
      {order.map((klass, index) => (
        <li key={klass} className="settings-sequence-row">
          <span className="settings-sequence-pos" aria-hidden="true">
            {index + 1}
          </span>
          <span className="settings-sequence-name">{t(classLabelKey(param, klass))}</span>
          <span className="settings-sequence-of">
            {t("settings.rules.sequence.positionLabel", {
              position: index + 1,
              count: order.length,
            })}
          </span>
          <RowActions>
            {/* BR-SHL-025: a control that cannot act is disabled WITH its
                reason. The top row's "up" has nowhere to go; a view-only role
                gets the same treatment the save bar gives.

                ⚠ THE LABEL KEEPS THE CLASS NAME. These two were already
                `aria-label`ed with the row they move — "Move up — Late fees" —
                because "Move up" alone is four identical buttons to a screen
                reader on a four-row list. That is exactly what an icon needs,
                so the label is unchanged and only the word became a chevron. */}
            <RowAction
              label={`${t("settings.rules.sequence.moveUp")} — ${t(classLabelKey(param, klass))}`}
              icon={<ChevronUpIcon />}
              reason={
                props.readOnly
                  ? t("settings.readOnlyReason")
                  : index === 0
                    ? t("settings.rules.sequence.atTop")
                    : null
              }
              onClick={() => props.onReorder(moveInSequence(order, index, -1))}
            />
            <RowAction
              label={`${t("settings.rules.sequence.moveDown")} — ${t(classLabelKey(param, klass))}`}
              icon={<ChevronDownIcon />}
              reason={
                props.readOnly
                  ? t("settings.readOnlyReason")
                  : index === order.length - 1
                    ? t("settings.rules.sequence.atBottom")
                    : null
              }
              onClick={() => props.onReorder(moveInSequence(order, index, 1))}
            />
          </RowActions>
        </li>
      ))}
    </ol>
  );
}

/**
 * The panel that says what the order DOES, recomputed from the draft on every
 * move. See this file's header for the figure and for why it is not a money
 * path.
 *
 * `currency` is the tenant's own (Regional settings, already read by the rule
 * page for its money echo). Without one the figures still render — as plain
 * numbers, with a line saying why there is no currency on them. Hiding the
 * example would be worse: the currency is decoration here and the ORDER is the
 * subject.
 */
export function AllocationWorkedExample(props: {
  param: RuleParam;
  order: readonly string[];
  currency: string | null;
}) {
  const { t } = useTranslation();
  const example = workedAllocation(props.order);
  const currency = props.currency;

  function amount(value: string) {
    if (currency === null || currency === "") {
      return <span className="cell-num">{value}</span>;
    }
    // BR-SHL-023 / BR-TEN-080: the ONE formatter, 2 dp on screen.
    return <MoneyCell amount={value} currency={currency} />;
  }

  return (
    <div className="settings-example">
      <h4 className="settings-example-title">{t("settings.rules.example.title")}</h4>
      <Note>{t("settings.rules.example.lede")}</Note>
      <table className="settings-table settings-example-table">
        <thead>
          <tr>
            <th>{t("settings.rules.example.colClass")}</th>
            <th className="cell-num">{t("settings.rules.example.colBilled")}</th>
            <th className="cell-num">{t("settings.rules.example.colMet")}</th>
            <th className="cell-num">{t("settings.rules.example.colOwed")}</th>
          </tr>
        </thead>
        <tbody>
          {example.rows.map((row) => (
            <tr key={row.klass}>
              <td>{t(classLabelKey(props.param, row.klass))}</td>
              <td className="cell-num">{amount(row.billed)}</td>
              <td className="cell-num">{amount(row.met)}</td>
              <td className="cell-num">{amount(row.owed)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">{t("settings.rules.example.billTotal")}</th>
            <td className="cell-num">{amount(example.total)}</td>
            <td className="cell-num">{amount(example.payment)}</td>
            <td className="cell-num">{amount(example.stillOwed)}</td>
          </tr>
        </tfoot>
      </table>
      {(currency === null || currency === "") && (
        <Note>{t("settings.rules.example.noCurrency")}</Note>
      )}
      <Note>{t("settings.rules.example.note")}</Note>
    </div>
  );
}

/**
 * The whole S66 field: label, help, the reorder list and the worked example.
 *
 * Dispatched from `RulePageView` on `kind === "choice_sequence"`. There is
 * exactly ONE such parameter in the product today, and the split above is the
 * honest shape of that: `SequenceReorder` is generic and would serve a second
 * one unchanged, while the worked example is `allocation_class_order`'s alone —
 * it is the PO's figure for THIS rule, not a pattern.
 */
export function AllocationOrderField(props: {
  page: RulePage;
  param: RuleParam;
  value: string | boolean;
  error?: string;
  readOnly: boolean;
  currency: string | null;
  onChange: (value: string) => void;
}) {
  const { t } = useTranslation();
  const { param, page } = props;
  const order = sequenceFromDraft(props.value);
  return (
    <div className="settings-rule-field">
      <h4 className="settings-example-title">
        {t(`settings.rules.${page.card}.${param.key}`)}
      </h4>
      {/* `DEF-TEN-6935` — the rule id that used to close this line is gone and
          nothing replaces it: B14 rule 32 clause 4 bans it, and rule 33 puts
          the *why* it was answering at zero words on screen. */}
      <p className="field-help">{t("settings.rules.sequence.help")}</p>
      <SequenceReorder
        param={param}
        order={order}
        readOnly={props.readOnly}
        onReorder={(next) => props.onChange(sequenceToDraft(next))}
      />
      {props.error !== undefined && (
        <RefusalStrip role="alert">
          {props.error}
        </RefusalStrip>
      )}
      {/* The classes the server knows about, said plainly, so an order that
          somehow arrived short is visible rather than silently four-minus-one.
          `ALLOCATION_CLASSES` is the SET — never read as the shipped order. */}
      {order.length !== ALLOCATION_CLASSES.length && (
        <p className="settings-warning" role="status">
          {t("settings.rules.sequence.incomplete", {
            count: ALLOCATION_CLASSES.length,
          })}
        </p>
      )}
      <AllocationWorkedExample param={param} order={order} currency={props.currency} />
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07, whose SCOPE ADDENDUM adds the S63–S71 cards; co-packet EP-PAY-02@0000000 for US-PAY-006's class order, a PLACEHOLDER hash because the BR-PAY-038 extension landed 2026-08-11 after that packet was cut — reported, not invented)
// generated: 2026-08-15 by story-coder (settings-screens lane — the S66 reorder control the PO's ruling of 2026-08-12 asked for and the 2026-08-15 backend lane left without a screen)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — the endpoint is the existing PUT /settings/billing-defaults; this lane adds no route) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: see the lane report — tsc✔ eslint --max-warnings 0✔ vitest✔ (the worked figure PROVED RED first: with the walk taking each class in FULL regardless of what was left, `tenant_defined` met 15.00 where the PO's ruling says 11.12) · run_gates 19 PASS / 1 FAIL (G8 on another lane's apps/billing/backbill.py — this lane's baseline, unchanged)
// exceptions: E4 the worked example's five figures are a client-side copy of a PO-ratified illustration (usage+base 100.58 · tax 8.30 · tenant-defined 15.00 · late fee 5.00 · payment 120.00). They are NOT a copy of a default or a limit — those stay the server's, per settingsRulePages.ts's own law — and a test asserts both the default-order and the fees-first outcomes so a drift from the ruling goes RED rather than quiet. REPORTED so a reviewer sees the copy · E4 no drag-and-drop: two explicit buttons per row, for keyboard reach and for reversibility a person can see — deliberate, reported · E4 no "restore the shipped order" control, because the shipped order lives once on the server and a copy here would be free to drift; Discard restores the tenant's saved order instead — deliberate, reported · E3 there is no DOM in this suite (the project's posture), so the reorder is proved at the pure function and through renderToStaticMarkup over a seeded cache, not at the pointer
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
