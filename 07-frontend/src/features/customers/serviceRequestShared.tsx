// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W4 tasks 4.10–4.13 — the pieces the three service-request
//           screens are built from. Design: B19 (04-docs/02-decisions/
//           19-cr031-service-request-capture.md) REQ-01 · REQ-02 · REQ-03.1..6
//           · REQ-03.sent. Screens: S83 · S84 · S85 (B18's proposal; A1
//           allocates none — decision D1 is unruled and nothing is minted here)
// Rules:    B14 rule 21 (Tailwind utilities; this file adds NO class to any
//           stylesheet — G31/routeBUtilities) · B14 rule 15 (row actions are
//           icons with an accessible name) · BR-SHL-025 (a control that cannot
//           act is DISABLED WITH ITS REASON, never hidden and never explained
//           in a grey box at the foot of the page) · BR-SHL-020 (plain-language
//           absence) · BR-CUS-090 · BR-CUS-092 · BR-CUS-093 · CLAUDE.md rule 2
// Tests:    ServiceRequestsListPage.test.tsx · ServiceRequestDetailPage.test.tsx
//           · ServiceRequestCapturePage.test.tsx
// ───────────────────────────────────────────────────────
//
// ⚠ **NO PAGE-LEVEL "WHAT THIS CANNOT DO YET" PANEL IS DEFINED IN THIS FILE,
// AND THAT IS A RULING, NOT AN OVERSIGHT.** The PO deleted THREE of them from
// the accounts screens on 2026-08-24: a build backlog does not belong in a grey
// box on an operator's screen. An absence is stated LOCALLY, on the thing it is
// about. (`BlockedControl` and `StatedFact`, the two local shapes this file
// once exported, were rendered by nothing after the capture wizard's redraw
// and are deleted — `DEF-GOV-10106`.)
//
// ⚠ **AND NO ABSENCE MAY STAND IN FOR A ZERO.** An empty table asserts
// *"you have none"*; a dash in a money column asserts *"zero"*. Where the
// product does not know, it says so in words.
//
// ⚠ **NO STYLESHEET CLASS IS ADDED BY THIS FILE** (B14 rule 21). Every class
// below is a Tailwind utility over the `@theme` tokens in `styles/tailwind.css`.
// The file is registered in `styles/route-b-migrated.txt`, so
// `routeBUtilities.test.ts` asks the stricter, compiler-backed question — does
// each utility generate a rule — rather than G31's "is it declared by a .css",
// which is false by design for a Tailwind file.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/Button";
import { EditableTable } from "@/components/EditableTable";
import type { UsAddressValue } from "@/components/UsAddressFields";
import { CheckboxField, SelectField } from "@/components/FormModal";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { MoneyCell, formatMoney } from "@/components/MoneyCell";
import { StatusPill } from "@/components/StatusPill";
import type { StatusTone } from "@/components/StatusPill";
import type { ChargeRow } from "@/api/endpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

import type {
  Money,
  ServiceRequestFeeLine,
  ServiceRequestFeesTab,
  ServiceRequestState,
  ServiceRequestUnavailable,
} from "./serviceRequestEndpoints";

// ══════════════════════════════════════════════════════════════════════════
// THE APPLICATION FEE IS PICKED FROM THE TENANT'S OWN CHARGE CODES
// ══════════════════════════════════════════════════════════════════════════

/**
 * **PO report 2026-09-22, row 11 — the Application fee amount comes from a
 * dropdown reading the CHARGE CODES.** One component, mounted twice (B14 rule
 * 43): on the capture wizard's fee step and inside the request's own Fees
 * panel. A hundred and twenty lines of this written inline in a page would be
 * importable by nothing, which is that rule's own wording.
 *
 * ⚠ **IT ALSO CLOSES `DEF-CUS-5904`, WHICH IS WHY IT IS ON BOTH SCREENS.**
 * `addServiceRequestFee` has existed and been exported since the module was
 * built and was **called by nothing** — hard-won law 2's dead door: the
 * endpoint works, the client works, `tsc` passes, and no clerk could raise an
 * application fee anywhere in the product.
 *
 * ⚠ **THE AMOUNT IS THE CATALOGUE'S AND IS NEVER TYPED, NEVER MULTIPLIED AND
 * NEVER ROUNDED HERE.** `amount` is the stored four-place string this posts;
 * `amount_display` is the two places a person reads, computed server-side
 * (`BR-RAT-087`) precisely so that scaling a money value in a component — which
 * is B4 arithmetic in the browser — cannot happen. CLAUDE.md rule 2.
 *
 * ⚠ **ONLY CODES THAT CAN ACTUALLY BE PRICED ARE OFFERED, AND THAT IS THE PO'S
 * OWN RULING RATHER THAN THIS LANE'S TASTE.** 2026-09-21, `DEF-MET-6110`:
 * *"Step 6 offers only charge codes a build can actually price."* `TAP` was in
 * a picker, a clerk chose it, and thirty-three acts later the screen said
 * *"Something went wrong on our side."* The predicate is IMPORTED rather than
 * re-written, because two copies of *can this be priced* drift.
 *
 * ⚠ **A FILTERED PICKER IS NOT A GUARANTEE — THAT RULING HAS TWO LAYERS AND
 * THIS IS ONLY THE FIRST.** A tenant edits a charge code on Settings this
 * afternoon (*"the amount is a SEED the tenant edits, never a constant"*), so a
 * list filtered when the panel mounted can be wrong by the time the clerk
 * presses Add. The caller must still put the server's refusal on this panel in
 * words. Do not read this filter as the check.
 */
export function chargeCodeOptions(
  rows: readonly ChargeRow[],
  canBeRaised: (row: ChargeRow) => boolean,
): readonly ChargeRow[] {
  // ⚠ **`one_time` IS THE ONLY TYPE THAT BELONGS ON AN APPLICATION.** A
  // `recurring` base charge or a `penalty` is a thing that happens to an
  // ACCOUNT over time; an application fee is taken once, at the counter,
  // against a request that has no account yet. Measured on the seeded utility:
  // 29 codes, of which 19 are one-time and 15 of those are priceable.
  return rows.filter((row) => row.charge_type === "one_time" && canBeRaised(row));
}

/**
 * The picker itself: choose a fee, see what it costs, add it to the list.
 *
 * The caller owns the fetching and the POST, so this mounts under a wizard
 * draft and under a saved request without either screen learning the other's
 * data layer.
 */
export function ApplicationFeeAdder(props: {
  codes: readonly ChargeRow[];
  picked: string;
  onPick: (code: string) => void;
  onAdd: () => void;
  t: Translator;
  working?: boolean;
  /** The server's last refusal, in words, on the panel that owns the field. */
  refusal?: string | null;
  /** The catalogue answered and nothing in it can be raised — a STATED
   *  absence, because an empty picker with no words is a screen a clerk cannot
   *  tell from a broken one (B14 rule 32). */
  nothingToOffer?: boolean;
  // ⛔ `onAddCode` / `addNonce` — the capture wizard's *the pick is the add*
  // row — are DELETED (`DEF-GOV-10106`): capture step 5 stopped mounting this
  // picker when REQ-03 redrew its fee table (`a503a0f4b`), so no caller passed
  // either and G13 counted the branch as dead. The request detail is this
  // component's one host and it never took that branch.
}) {
  const t = props.t;
  const chosen = props.codes.find((row) => row.code === props.picked) ?? null;
  /**
   * ⚠ **`amount_display` IS THE SERVER'S TWO PLACES, AND NOTHING HERE FORMATS
   * MONEY (`BR-RAT-087`, CLAUDE.md rule 2).** Scaling or rounding a stored
   * money value in a component is B4 arithmetic in a browser, which is why the
   * server serves both forms.
   *
   * ⚠ **AND IT IS SHOWN BARE, WITH NO CURRENCY BESIDE IT, TO MATCH THE PLACE A
   * CLERK SETS IT.** `ChargeCodesTab` renders exactly this string through
   * `rating.charges.amount.flat`, which is `{{amount}}` and nothing else. The
   * first draft put the REQUEST's currency beside it where the request had
   * one — so the same code read `25.00` on a fresh request and `$25.00` once a
   * line existed, two spellings of one catalogue price inside one panel. What
   * this shows is the CHARGE CODE's price, not the request's money; the
   * request's money is in `Quoted` and `Outstanding` above, where it carries
   * its `CHAR(3)` as it always has.
   */
  const price = chosen?.amount_display ?? null;
  return (
    <div data-fee-adder="">
      {props.nothingToOffer === true ? (
        <p className="text-sm text-neutral-700" data-fee-adder-empty="">
          {t("customers.serviceRequest.fees.noneToOffer")}
        </p>
      ) : (
        <div className="flex flex-wrap items-end gap-3" data-fee-code-picker="">
          {/* ⚠ **THE KIT'S CHOOSER, NOT A HAND-ROLLED `<select>` — B14 rules
              36 and 43.** The first draft of this component wrote its own,
              with its own border and padding utilities, and
              `routeBUtilities.test.ts` caught one of them (`border-border`)
              rendering NOTHING. That is the check doing its job, and the fix
              is never to hunt for the right utility: it is to use the piece
              the kit already has, which carries the label, the placeholder
              option, the error wiring and the disabled posture for free. */}
          <SelectField
            id="application_fee_code"
            /* Rule 33: a LABEL is at most three words and is not a sentence. */
            label={t("customers.serviceRequest.fees.pickAFee")}
            value={props.picked}
            onChange={props.onPick}
            disabled={props.working === true}
            placeholder={t("customers.serviceRequest.fees.chooseAFee")}
            options={props.codes.map((row) => ({
              value: row.code,
              label: `${row.code} · ${row.name}`,
            }))}
          />
          {/* The price is a FACT about what was chosen, not an editable field —
              it is the catalogue's number, and a clerk who wants a different
              one edits the charge code on Settings, which is what a charge code
              is for. */}
          <p className="pb-2 text-sm" data-fee-amount={chosen?.code ?? ""}>
            {price ?? t("customers.serviceRequest.fees.pickToSeeThePrice")}
          </p>
          <div className="pb-1">
            <Button
              variant="secondary"
              disabled={props.working === true || chosen === null}
              onClick={props.onAdd}
              data-fee-add=""
            >
              {t("customers.serviceRequest.fees.addToTheList")}
            </Button>
          </div>
        </div>
      )}
      {props.refusal !== null && props.refusal !== undefined && props.refusal !== "" && (
        <p className="mt-2 max-w-prose text-sm text-danger-700" data-fee-add-refused="">
          {props.refusal}
        </p>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE FEE LINES, AS ONE TABLE ON FOUR SCREENS — PO approval 2026-09-23
// ══════════════════════════════════════════════════════════════════════════

/**
 * **PO, verbatim, 2026-09-23:** *"on step 5 - for selecting fees can you use
 * table array component"* and *"fee should be in table format"* — then, shown
 * the columns, *"i like this please use this"*. `DEF-CUS-6411`.
 *
 *     Fee · Charged per · Qty · Unit price · Amount · Waive · (remove)
 *     + Add a fee ▾
 *                                        Total
 *
 * **ONE COMPONENT, FOUR SCREENS (B14 rules 20 and 43).** Capture step 5 draws
 * it EDITABLE; the review, the confirmation and the request detail draw it
 * READ-ONLY, without the Waive tick and without the remove icon; the detail
 * alone adds `Paid`. It is the kit's `EditableTable`, extended rather than
 * forked — `readOnly`, `numbered`, `footerCells` and `onRemove` were added to
 * the kit for it, each opt-in, so the six collections that predate them render
 * exactly what they did.
 *
 * ⚠ **EVERY FIGURE IS THE SERVER'S, INCLUDING THE TOTAL (hard rule 2).** Each
 * line's `unit_amount` and `amount` are `NUMERIC(18,4)` on
 * `service_request_fees`, locked at the moment of the Add (`add_fee_line` prices
 * them from the charge code, `DEF-CUS-6416`), and printed at two places with
 * their `CHAR(3)` through `MoneyCell`. **The Total is `fees.quoted`** — the
 * server's own Decimal sum of the lines that are not waived
 * (`fee_total_to_collect`) — and NOT a sum of the cells: adding money up in a
 * browser is JavaScript arithmetic on money, which is the defect the rule
 * exists to prevent. A waived line is drawn, with its reason, and is not in
 * the Total, which is exactly what `quoted` already means.
 *
 * ⚠ **`Code` IS NOT A COLUMN** — the PO took the recommendation to leave it
 * out; a clerk works by the fee's NAME. The code is the fallback for a line
 * that was stored without a description, never the first thing shown.
 */
export function FeeLinesTable(props: {
  fees: Pick<ServiceRequestFeesTab, "lines" | "quoted" | "outstanding" | "receipt_no">;
  t: Translator;
  /** `data-editable-table` — how a test or a walkthrough finds this table. */
  collection: string;
  /** The request detail only — `Receipt 8655665`, an invoice, or `—`. */
  paidColumn?: boolean;
  /** A trailing cell for the detail's per-line WAIVE row action, the one door
   *  onto a waiver once a request is submitted. Read-only tables only. */
  rowAction?: (line: ServiceRequestFeeLine) => ReactNode;
  /** Present on capture step 5 and nowhere else: the table becomes editable. */
  edit?: {
    addRow: ReactNode;
    onWaive: (line: ServiceRequestFeeLine) => void;
    onRemove: (line: ServiceRequestFeeLine) => void;
    busy: boolean;
    /** Why NO line may be removed right now — a request reopened for
     *  correction after it was submitted (OQ-357: remove while DRAFT, waive
     *  after; `remove_fee_line` refuses the same thing). Per-line reasons
     *  (waived, paid) still win, because they are the more specific truth. */
    removeBlocked?: string;
  };
}) {
  const t = props.t;
  const lines = props.fees.lines;
  const columns = [
    {
      key: "fee",
      label: t("customers.serviceRequest.fees.col.fee"),
      cell: (line: ServiceRequestFeeLine) => (
        <span data-fee-line-name={line.charge_code ?? ""}>
          {line.description ?? line.charge_code ?? ""}
        </span>
      ),
    },
    {
      key: "basis",
      label: t("customers.serviceRequest.fees.col.chargedPer"),
      cell: (line: ServiceRequestFeeLine) => basisLabel(line.basis, t),
    },
    {
      key: "qty",
      label: t("customers.serviceRequest.fees.col.qty"),
      numeric: true,
      cell: (line: ServiceRequestFeeLine) => quantityText(line.quantity),
    },
    {
      key: "unit",
      label: t("customers.serviceRequest.fees.col.unitPrice"),
      numeric: true,
      cell: (line: ServiceRequestFeeLine) => <MoneyOrAbsence money={line.unit_amount} t={t} />,
    },
    {
      key: "amount",
      label: t("customers.serviceRequest.fees.col.amount"),
      numeric: true,
      cell: (line: ServiceRequestFeeLine) => (
        <span data-fee-line-amount={line.amount.amount}>
          <MoneyOrAbsence money={line.amount} t={t} />
          {/* A WAIVED line reads as waived, with its reason — never as a tick
              on a record (PO approval 2026-09-23). */}
          {line.waived && props.edit === undefined && (
            <span className="block text-sm text-neutral-700" data-fee-line-waived="">
              {t("customers.serviceRequest.fees.waivedWithReason", {
                reason: line.waive_reason_name ?? "",
              })}
            </span>
          )}
        </span>
      ),
    },
    ...(props.edit !== undefined
      ? [
          {
            key: "waive",
            label: t("customers.serviceRequest.fees.col.waive"),
            cell: (line: ServiceRequestFeeLine) => (
              <span data-fee-line-waive={line.waived ? "waived" : ""}>
                {/* ⚠ **A TICK THAT ASKS, NOT A TICK THAT ACTS.** Ticking opens
                    the reason the endpoint REQUIRES (`waive_fee_line`: *"A
                    reason is required and recorded against your name"*); the
                    box only shows ticked once the server says the line IS
                    waived. There is no un-waive on the server, so a ticked box
                    is disabled rather than pretending it could be cleared. */}
                <CheckboxField
                  id={`fee-waive-${line.id}`}
                  label={`${t("customers.serviceRequest.fees.col.waive")} ${line.description ?? line.charge_code ?? ""}`}
                  labelHidden
                  checked={line.waived}
                  disabled={line.waived || line.settled_at !== null || props.edit?.busy === true}
                  onChange={(checked) => {
                    if (checked) props.edit?.onWaive(line);
                  }}
                />
                {line.waived && (
                  <span className="block text-sm text-neutral-700">{line.waive_reason_name ?? ""}</span>
                )}
              </span>
            ),
          },
        ]
      : []),
    ...(props.paidColumn === true
      ? [
          {
            key: "paid",
            label: t("customers.serviceRequest.fees.col.paid"),
            cell: (line: ServiceRequestFeeLine) => {
              const paid = feePaidBy(line, props.fees, t);
              return paid === null ? <Dash /> : <span data-fee-line-paid="">{paid}</span>;
            },
          },
        ]
      : []),
    ...(props.rowAction !== undefined && props.edit === undefined
      ? [
          {
            key: "action",
            label: t("customers.serviceRequest.col.actions"),
            cell: (line: ServiceRequestFeeLine) => props.rowAction?.(line),
          },
        ]
      : []),
  ];
  const footerCells = {
    fee: t("customers.serviceRequest.fees.total"),
    amount: (
      <span data-fee-total={props.fees.quoted.amount}>
        <MoneyOrAbsence money={props.fees.quoted} t={t} />
      </span>
    ),
  };
  const common = {
    "data-collection": props.collection,
    // No caption bar: every screen that draws this sits it under a heading
    // that already names it (*Application fees*, *Fees*, *Form fee*).
    caption: "",
    columns,
    rows: [...lines],
    rowKey: (line: ServiceRequestFeeLine) => line.id,
    emptyText: t("customers.serviceRequest.fees.line.none"),
    numbered: false,
    reorderable: false,
    footerCells: lines.length === 0 ? undefined : footerCells,
  };
  if (props.edit === undefined) {
    return <EditableTable<ServiceRequestFeeLine> {...common} readOnly />;
  }
  const edit = props.edit;
  return (
    <EditableTable<ServiceRequestFeeLine>
      {...common}
      addRow={edit.addRow}
      // The server owns the rows, so the ✕ asks the server — see `onRemove`.
      onChange={() => undefined}
      onRemove={(line) => edit.onRemove(line)}
      rowRemoveBlocked={(line) =>
        line.waived
          ? t("customers.serviceRequest.feeRemoveWaived")
          : line.settled_at !== null
            ? t("customers.serviceRequest.feeRemovePaid")
            : edit.removeBlocked
      }
      labels={{
        remove: t("customers.serviceRequest.fees.remove"),
        position: t("customers.serviceRequest.fees.col.fee"),
      }}
    />
  );
}

/**
 * `per request` → *Request*. The stored `basis` is free text from two writers
 * (`per request` from the capture wizard, `per meter` · `per unit` ·
 * `per premise` from a build's quote), so it is normalised to a catalogue key
 * and falls back to the stored words rather than to a code. `null` is a dash:
 * a line nobody gave a basis to.
 */
export function basisLabel(basis: string | null, t: Translator): ReactNode {
  if (basis === null || basis.trim() === "") return <Dash />;
  const key = basis.trim().toLowerCase().replace(/\s+/g, "_");
  return t(`customers.serviceRequest.fees.basis.${key}`, { defaultValue: basis.trim() });
}

/** `1.0000` → `1`, `2.5000` → `2.5`. A COUNT, never money: the stored four
 *  places are the column's precision, not something a clerk counted. */
export function quantityText(quantity: string): string {
  if (!/^-?\d+(\.\d+)?$/.test(quantity)) return quantity;
  return quantity.includes(".") ? quantity.replace(/\.?0+$/, "") : quantity;
}

/**
 * **`Paid`, on the request detail — PO approval 2026-09-23.** What settled
 * THIS line, or `null` for a dash:
 *
 *   * settled by an INVOICE → that invoice's reference;
 *   * a waived line → `null` (it is not paid, it is not owed);
 *   * otherwise, the COUNTER's receipt — but only when that receipt covers the
 *     whole quote (`outstanding` is zero or less). Counter money is taken
 *     against the REQUEST, not against a line (`BR-CUS-090`), so a part-payment
 *     cannot honestly be pinned to one row; those rows stay a dash and the
 *     panel's own line states the shortfall.
 */
export function feePaidBy(
  line: ServiceRequestFeeLine,
  fees: Pick<ServiceRequestFeesTab, "outstanding" | "receipt_no">,
  t: Translator,
): string | null {
  if (line.waived) return null;
  if (line.settled_at !== null && (line.invoice_ref ?? "") !== "") {
    return t("customers.serviceRequest.fees.paidByInvoice", { invoice: line.invoice_ref });
  }
  const receipt = fees.receipt_no ?? "";
  // Zero or less, read off the SIGN of the stored decimal string — no money is
  // parsed into a JavaScript number to ask it (hard rule 2).
  const owed = fees.outstanding.amount.trim();
  const covered = owed.startsWith("-") || /^0+(\.0+)?$/.test(owed);
  if (receipt !== "" && covered) {
    return t("customers.serviceRequest.fees.paidByReceipt", { receipt });
  }
  return null;
}

/**
 * The reason `POST …/fees/{id}/waive` requires — the TENANT's own reason list,
 * `/payments/reason-codes`, the same door the request detail's waive reads.
 *
 * `WAIVE_SCHEMA` is `RequestFeeHandoverModal`'s (`DEF-CUS-6376` moved it there
 * from the detail page), imported rather than restated, so the capture
 * wizard's per-line Waive tick and the detail's waive are held by ONE rule.
 */

// ══════════════════════════════════════════════════════════════════════════
// ADDRESSES — one line from the parts the server sends separately
// ══════════════════════════════════════════════════════════════════════════

/** `212 Balcones Drive · Unit 3 · Austin, TX 78704` — one line, from the parts
 *  the server sends separately. Empty parts drop out; an empty result is
 *  `null`, so a caller states an absence rather than drawing a stray comma.
 *
 *  Moved here from `ServiceRequestDetailPage` (2026-09-23) so the capture
 *  review and the request detail write a billing address the same way; the
 *  detail re-exports it. The punctuation is an illustration the blueprint draws
 *  two ways (p082, p083), which is why it is composed on the screen. */
export function composeAddressLine(
  street: string | null,
  locality: { city: string | null; state: string | null; postal_code: string | null } | null,
): string | null {
  const town = [locality?.city, [locality?.state, locality?.postal_code].filter(Boolean).join(" ")]
    .filter((part) => part !== null && part !== undefined && part !== "")
    .join(", ");
  const line = [street, town].filter((part) => part !== null && part !== "").join(" · ");
  return line === "" ? null : line;
}

/**
 * `DEF-CUS-10705` — the street of RECORD with the matched unit after it, the way
 * the request head draws it (p082 `212 Balcones Drive · Unit 3 · Austin`).
 *
 * The unit is drawn only where the premises holds MORE THAN ONE unit: a house's
 * one unit refines nothing, and printing its label there would be noise. A
 * label that already names itself (`Apt 2B`, `Unit 3`, `Suite 100`) is drawn as
 * stored; a bare one (`B`, `3`) gets the catalogue's word for a unit in front,
 * so the line never reads `1408 Elm St · B`. The label is the unit's own
 * refinement by LABEL (hard rule 8) — never an address of its own.
 */
export function streetWithUnit(
  street: string | null,
  unitLabel: string | null | undefined,
  premisesUnits: number | null | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): string | null {
  const label = (unitLabel ?? "").trim();
  if (street === null || street === "" || label === "" || (premisesUnits ?? 0) < 2) {
    return street;
  }
  const named = /^[A-Za-z]{2,}\.?\s/.test(label)
    ? label
    : t("customers.serviceRequest.headUnit", { label });
  return `${street} · ${named}`;
}

/**
 * **A request's billing address as the kit's `UsAddressValue` — or `null` when
 * the applicant gave none (`DEF-CUS-6408`).** For the door that opens an account
 * FROM a request (the move-in wizard), so the account's `kind='mailing'` row is
 * prefilled from what was captured rather than re-keyed.
 *
 * `null` when *Same as the service address* was ticked, and when no street line
 * was given. ⛔ **A REQUEST CAPTURED BEFORE 2026-09-23 ALSO ANSWERS `null`:** its
 * billing address is ONE free-text string (`billing_address_as_given`) and
 * splitting it into a street, a city and a ZIP is the guess `BR-NOT-029` clause
 * (a) forbids; the clerk reads it on the request detail and types it.
 */
export function requestBillingAddress(location: {
  billing_address_same: boolean;
  billing_line1_as_given: string | null;
  billing_line2_as_given: string | null;
  billing_city_as_given: string | null;
  billing_state_as_given: string | null;
  billing_postal_code_as_given: string | null;
}): UsAddressValue | null {
  const line1 = (location.billing_line1_as_given ?? "").trim();
  if (location.billing_address_same || line1 === "") {
    return null;
  }
  return {
    line1,
    line2: (location.billing_line2_as_given ?? "").trim(),
    city: (location.billing_city_as_given ?? "").trim(),
    state: (location.billing_state_as_given ?? "").trim(),
    postal_code: (location.billing_postal_code_as_given ?? "").trim(),
  };
}

/**
 * **Where the bill goes, as one line — `DEF-CUS-6408`.** Built from the five
 * parts (`PO Box 4471 · Suite 200 · Round Rock, TX 78664-1234`); where every
 * part is empty, the ONE-BOX value a request captured before 2026-09-23 holds,
 * exactly as it was typed — never parsed (`DEF-2703`, `BR-NOT-029` clause (a)).
 * `null` when there is neither.
 */
export function billingAddressLine(parts: {
  line1: string | null;
  line2: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  legacy: string | null;
}): string | null {
  const street = [parts.line1, parts.line2]
    .map((part) => (part ?? "").trim())
    .filter((part) => part !== "")
    .join(" · ");
  const composed = composeAddressLine(street === "" ? null : street, {
    city: (parts.city ?? "").trim() || null,
    state: (parts.state ?? "").trim() || null,
    postal_code: (parts.postal_code ?? "").trim() || null,
  });
  if (composed !== null) return composed;
  const legacy = (parts.legacy ?? "").trim();
  return legacy === "" ? null : legacy;
}

// ══════════════════════════════════════════════════════════════════════════
// ROUTES — tenant-relative, like every route constant since path tenancy
// landed (PO 2026-08-10). The screen that navigates puts it through
// `tenantPath()`.
// ══════════════════════════════════════════════════════════════════════════

/**
 * REQ-01 — the Requests list.
 *
 * ⚠ **B19 §12.1 DRAWS THIS AS A TAB OF THE ACCOUNTS PAGE** (`Accounts ·
 * Requests⁴² · New Connect⁷ · …`), and it is a ROUTE OF ITS OWN here. The
 * reason is scope, not design: `AccountsListPage.tsx` renders that eight-tab
 * strip and belongs to another lane in this shared tree today (hard-won law 11
 * — a pathspec commit takes the whole file, so two lanes editing one file is
 * how work gets silently reverted). The tab's body is ONE line and it is OWED,
 * not done; the lane report names it exactly. Until then the screen is
 * reachable at its own address and every link in this feature points here.
 */
export const SERVICE_REQUESTS_ROUTE = "/requests";

/** REQ-03 — the six-step capture. STATIC, so React Router ranks it above
 *  `:requestId` and a wizard is never mistaken for a request id. */
export const SERVICE_REQUEST_NEW_ROUTE = "/requests/new";

/**
 * BR-CUS-095's checklist — *"Settings grows a checklist — for each request
 * type, tick which documents are required."* System Admin only, server-side.
 *
 * Placed under `settings/reference-data` (= "Configure", CR-001's rename)
 * because B18 §W4 row 16 puts *Form definitions* there. It is a route of its
 * own rather than a tab body for the SET-06D/SET-07D reason: `SettingsPage.tsx`
 * owns the tab strip and is not this lane's file.
 */
export const SERVICE_REQUEST_DOC_SETTINGS_ROUTE = "/settings/reference-data/service-request-documents";

/** REQ-02 — the request detail. Deep-linkable, per-tab via `?tab=`. */
export function serviceRequestPath(requestId: string): string {
  return `${SERVICE_REQUESTS_ROUTE}/${encodeURIComponent(requestId)}`;
}

/** REQ-03 mid-flight: the draft already exists and already has its number
 *  (BR-CUS-093), so the wizard is addressable from step 1 onward. */
export function serviceRequestCapturePath(requestId: string): string {
  return `${SERVICE_REQUEST_NEW_ROUTE}?request=${encodeURIComponent(requestId)}`;
}

// ══════════════════════════════════════════════════════════════════════════
// STATE → PILL TONE
// ══════════════════════════════════════════════════════════════════════════

/**
 * ⚠ **`refused` AND `withdrawn` ARE `danger`; `closed` AND `completed` ARE
 * NOT.** A request that ended because its job finished is not a failure, and
 * colouring it red would tell a clerk scanning the Closed segment that
 * something went wrong on every row.
 */
const STATE_TONE: Readonly<Record<string, StatusTone>> = {
  draft: "neutral",
  submitted: "neutral",
  under_review: "warning",
  more_info: "warning",
  approved: "success",
  in_fulfilment: "success",
  on_hold: "warning",
  completed: "success",
  refused: "danger",
  withdrawn: "danger",
  closed: "neutral",
};

export function requestStateTone(state: ServiceRequestState | string): StatusTone {
  return STATE_TONE[state] ?? "neutral";
}

export function RequestStatePill(props: { state: string; t: Translator }) {
  return (
    <StatusPill tone={requestStateTone(props.state)}>
      {props.t(`customers.serviceRequest.state.${props.state}`)}
    </StatusPill>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE HEAD'S FOUR CHIPS — p082/p083, and why this is NOT `StatusPill`
// ══════════════════════════════════════════════════════════════════════════

/**
 * One fact from the request head, drawn as a chip.
 *
 * The Accounts blueprint draws FOUR facts side by side under the applicant's
 * name (p082, read as an image — B14 rule 42): the STATE, what it is WAITING
 * ON, the CHANNEL it arrived through, and the date it was RECEIVED. The
 * drawing colours them grey · amber · blue · grey.
 *
 * ⚠ **THIS IS A SEPARATE COMPONENT FROM `StatusPill` ON PURPOSE, AND THE
 * REASON IS A12's OWN RULE.** `StatusPill`'s six tones are *status meaning
 * only, never decoration*, and its docstring says a screen reaching for one
 * of them **because it likes the colour** is the rule A12 exists to stop.
 * **A channel is not a status and a date is not a status.** `Counter` says
 * where a request came in, not how it is going; `Received 05/04/2026` is a
 * fact about the calendar. Rendering either through `StatusPill` would mean
 * `info` no longer reads as *paused, and nothing is wrong* the next time a
 * clerk sees it, which is how a semantic ramp quietly becomes a palette.
 *
 * ⚠ **THE CLASSES ARE THE SAME TOKENS `StatusPill` USES**, deliberately: the
 * two must not drift into two greys. What differs is the CLAIM, not the paint.
 * B14 rule 21 — Tailwind utilities, no stylesheet class.
 *
 * The STATE keeps `RequestStatePill`, so its eleven-state tone map stays the
 * one answer to *what colour is `more_info`*.
 */
export type RequestHeadChipTone = "neutral" | "waiting" | "channel";

const HEAD_CHIP_CLASS: Readonly<Record<RequestHeadChipTone, string>> = {
  neutral: "bg-neutral-200 text-neutral-700",
  waiting: "bg-warning-100 text-warning-700",
  channel: "bg-info-100 text-info-700",
};

export function RequestHeadChip(props: {
  tone: RequestHeadChipTone;
  children: ReactNode;
  /** Goes on the element so a walkthrough can name the chip it is reading. */
  testId?: string;
  title?: string;
  /** ⚠ **THE TWO CODED FACTS KEEP THEIR OWN ATTRIBUTE**, carried over from the
   *  grey text these chips replaced. A chip identified only by its POSITION is
   *  a chip a test cannot tell from its neighbour once somebody reorders them,
   *  and `data-waiting-on="documents"` is the machine-readable half of a word
   *  the screen deliberately translates. */
  waitingOn?: string | null;
  channel?: string | null;
}) {
  return (
    <span
      className={`pill ${HEAD_CHIP_CLASS[props.tone]}`}
      data-head-chip={props.testId}
      data-waiting-on={props.waitingOn ?? undefined}
      data-channel={props.channel ?? undefined}
      title={props.title}
    >
      {props.children}
    </span>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE NUMBER — BR-CUS-093
// ══════════════════════════════════════════════════════════════════════════

/**
 * The request number, or the sentence that says why there is none.
 *
 * ✅ **BR-CUS-093 (PO 2026-08-24): *"At creation — every draft is numbered."***
 * So from 2026-08-24 this is never empty on a new row, and the clerk can read
 * `SR-26-0048` down the phone while the form is still half-filled.
 *
 * ⚠ **A ROW THAT PREDATES THE RULING CARRIES NULL FOREVER, and that is not a
 * bug to paper over.** Consequence (a): *"gaps are normal and must not be
 * treated as loss"* — nothing renumbers, backfills or reuses, because
 * renumbering afterwards moves an identifier somebody has already written
 * down. A blank cell would read as a rendering failure; the sentence says what
 * happened.
 */
export function RequestNumber(props: {
  requestNo: string | null;
  absence: { tracks: string } | null;
  t: Translator;
  /**
   * WHERE THE NUMBER OPENS — `DEF-CUS-6005`.
   *
   * ⚠ **OPTIONAL BECAUSE THE TWO CALLERS WANT DIFFERENT THINGS, NOT BECAUSE
   * NOBODY PASSES IT** (hard-won law 2 is about the second case). The LIST
   * passes it — a clerk's hand goes to the number they came here to find. The
   * request DETAIL renders this same component in its own header and must NOT,
   * because a link from a record to itself is a door onto the room you are
   * standing in.
   *
   * ⚠ **THE PO ALREADY RULED THIS ONE LIST OVER.** `NewConnectsTab.tsx:492`
   * carries their words — *"can you imporve the interaction design"* — over the
   * identical complaint: the only way into a build was an icon at the far right
   * of a nine-column row. The note there states the remedy this follows, eye
   * included: *"The eye stays: it is B14 rule 15's row action."* Move-ins and
   * Move-outs link their reference the same way. Re-putting it to the PO would
   * be hard-won law 13's bug.
   *
   * ⚠ **B14 RULE 31 IS KEPT, NOT BENT:** the visible text is still the human
   * reference `SR-26-0048`; the id is in the href alone and never on screen.
   *
   * ⛔ **AND NO LINK ROUND AN ABSENCE.** A request that predates numbering has
   * no number and renders a SENTENCE saying so; wrapping that in a link would
   * make a door out of a paragraph.
   */
  to?: string;
}) {
  if (props.requestNo !== null && props.requestNo !== "") {
    const number = props.requestNo;
    if (props.to !== undefined && props.to !== "") {
      return (
        <Link
          to={props.to}
          className="font-heading font-semibold tabular-nums text-accent-700 no-underline hover:underline focus-visible:underline"
          data-request-record={number}
        >
          {number}
        </Link>
      );
    }
    return <span className="font-heading font-semibold tabular-nums">{number}</span>;
  }
  return (
    <span
      role="note"
      className="text-sm text-neutral-700"
      data-tracks={props.absence?.tracks ?? "BR-CUS-093"}
    >
      {props.t("customers.serviceRequest.number.absent")}
    </span>
  );
}

/**
 * REQ-03's footer, on every one of the six steps.
 *
 * ⚠ **THE OLD COPY IS FALSE AND MUST NOT BE REPRODUCED.** Every step used to
 * read *"Step N of 6 · nothing is created until you submit"* — and something IS
 * created, from the first keystroke. BR-CUS-093 consequence (b) replaces it
 * with ***"Step N of 6 · saved as draft SR-26-0048"***, naming the number the
 * clerk can quote. The catalogue key is
 * `customers.serviceRequest.capture.draftFooter`.
 *
 * ⚠ **AND THE HEADER SUB-LINE COMES OUT ENTIRELY** — *"the request is created
 * and numbered when the fee is collected"* (consequence (c)). There is no
 * component here that renders it, deliberately: the way to not print a false
 * sentence is to have nowhere to print it from.
 */
export function CaptureDraftFooter(props: {
  step: number;
  steps: number;
  requestNo: string | null;
  t: Translator;
}) {
  return (
    <p className="mt-3 text-sm text-neutral-700" data-capture="draft-footer">
      {props.requestNo === null || props.requestNo === ""
        ? props.t("customers.serviceRequest.capture.draftFooterUnnumbered", {
            step: props.step,
            steps: props.steps,
          })
        : props.t("customers.serviceRequest.capture.draftFooter", {
            step: props.step,
            steps: props.steps,
            number: props.requestNo,
          })}
    </p>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// MONEY — CLAUDE.md rule 2
// ══════════════════════════════════════════════════════════════════════════

/**
 * A served figure, or a stated absence — never a dash and never a fabricated
 * currency.
 *
 * ⚠ **`currency: null` IS A REAL ANSWER AND IT IS NOT `"USD"`.** A request with
 * no fee line has no currency at all. `MoneyCell` requires one and would refuse,
 * and `?? "USD"` would print a figure in a currency nobody chose — the DEF-127
 * shape, one screen over. So this branches and says so in words.
 *
 * ⚠ **THE FIGURE ON SCREEN IS THE SERVER'S `display`, NOT A CLIENT ROUNDING.**
 * `MoneyCell` formats the 4-dp `amount` through the ONE formatting path
 * (BR-SHL-023) and the server's own 2-dp `display` rides beside it in
 * `data-display` so a test can prove the two agree without re-implementing the
 * rounding rule a third time.
 */
export function MoneyOrAbsence(props: { money: Money; t: Translator; reason?: string }) {
  if (props.money.currency === null || props.money.currency === "") {
    return (
      <span role="note" className="text-sm text-neutral-700">
        {props.reason ?? props.t("customers.serviceRequest.fees.noCurrencyYet")}
      </span>
    );
  }
  return (
    <span data-display={props.money.display}>
      <MoneyCell amount={props.money.amount} currency={props.money.currency} />
    </span>
  );
}

/**
 * Money for a SENTENCE — the stored amount through the one formatting path,
 * with its `CHAR(3)` (`$70.00`), never the server's bare two-place `display`
 * (`70.00`). `DEF-CUS-6412`: three sentences on three screens printed money
 * with no currency, one component over from `MoneyCell` printing it with one.
 * No currency is a real answer (no fee raised) and falls back to `display`
 * rather than to a currency nobody chose.
 */
export function moneyText(value: Money): string {
  return value.currency === null || value.currency === ""
    ? value.display
    : formatMoney(value.amount, value.currency);
}

// ══════════════════════════════════════════════════════════════════════════
// THE TWO HONEST SHAPES
// ══════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════
// THE DEFINITION LIST THE BLUEPRINT DRAWS — p082/p083, left column
//
// ⚠⚠ **THIS IS A SECOND SHAPE, NOT A REPLACEMENT FOR `Field`/`FieldGrid`, AND
// THAT IS DELIBERATE.** The PO put the request detail beside its drawing on
// 2026-09-19 and ruled the left column, verbatim: *"we have to match drawing
// here - Drawing: label left, value right, a hairline between rows, no box."*
// `FieldGrid` is the opposite shape in every one of those four respects — label
// ABOVE value, two across, no rules between, inside a `Panel`'s grey card — and
// it is used by dozens of screens that were never ruled on. Changing it would
// have redrawn every one of them on one screen's authority, which is exactly
// what B14 rule 38 forbids.
//
// **What the drawing shows, read as an image (B14 rule 42):** a small
// upper-case section heading with a hairline under it, then one fact per row —
// label left in the reading colour, value hard RIGHT — with a hairline between
// each. No card, no background, no border around the group.
// ══════════════════════════════════════════════════════════════════════════

/**
 * One drawn row: label left, value right, hairline beneath.
 *
 * ⚠ **THE VALUE IS RIGHT-ALIGNED AND THE LABEL IS NOT, WHICH IS WHAT MAKES THE
 * COLUMN READABLE.** The drawing's values form a straight right edge — dates,
 * counts and names all landing on it — so a clerk scanning for one fact runs
 * down an edge instead of hunting across ragged text.
 *
 * `hideWhenEmpty` exists for the eleven captured fields the drawing predates
 * (SSN, licence, date of birth, what they said, what is being built, plot or
 * parcel, billing address, language, co-applicant…). The decision log's open
 * list says they are *kept for now, hidden when empty* — so a request that
 * carries none of them reads as the drawing draws it, and one that carries a
 * licence still shows it rather than losing a captured fact off a screen.
 */
export function DrawnRow(props: {
  label: ReactNode;
  children: ReactNode;
  /** Skip the row entirely when there is nothing in it. */
  hideWhenEmpty?: boolean;
  empty?: boolean;
  testId?: string;
}) {
  if (props.hideWhenEmpty === true && props.empty === true) {
    return null;
  }
  return (
    <div
      className="flex items-baseline justify-between gap-6 border-b border-b-divider py-2.5 last:border-b-0"
      data-drawn-row={props.testId ?? ""}
    >
      <span className="text-sm text-neutral-700">{props.label}</span>
      <span className="text-right text-sm font-medium text-text">{props.children}</span>
    </div>
  );
}

/**
 * A drawn section: the upper-case heading, its hairline, and the rows.
 *
 * ⚠ **THE HEADING IS A HEADING AND IS THEREFORE CAPPED AT THREE WORDS (B14
 * rule 33).** The drawing letters these `WHAT THEY ASKED FOR` and `THE ADDRESS
 * THEY GAVE` — four words each — and the PO ruled on exactly this collision the
 * same morning: *"even if drawing sshow too much content ons creen - dont apply
 * that we have to use our rules to show content on screen"*. So the SHAPE is
 * the drawing's and the WORDS are ours: `Asked for`, `Who is asking`,
 * `Their address`.
 */
export function DrawnSection(props: {
  title: string;
  children: ReactNode;
  name?: string;
}) {
  return (
    <section className="flex flex-col" data-panel-name={props.name}>
      <h3 className="m-0 border-b border-b-divider pb-2 text-xs font-semibold uppercase tracking-wide text-neutral-700">
        {props.title}
      </h3>
      {props.children}
    </section>
  );
}

/**
 * The absence glyph for the drawn list — **an em dash, not the words *Not
 * supplied*** (PO-approved removal list, row 14, 2026-09-19).
 *
 * ⚠ **THE ABSENCE IS STILL STATED, WHICH IS WHAT B14 RULE 32 ASKS FOR** — the
 * row is present and its value is a dash. What went is six repetitions of a
 * two-word sentence down one column, which is what the PO has twice called too
 * much content. The drawing prints a dash in exactly this position (the
 * tenancy agreement's missing file, the register's WAITING ON column).
 *
 * ⚠ **IT IS SCOPED TO THIS PAGE ON PURPOSE.** `NotSupplied` is unchanged and
 * every other screen still reads *Not supplied*; the ruling was given about one
 * column of one screen.
 */
export function Dash() {
  return (
    <span className="text-neutral-700" data-absence="dash" aria-label="—">
      —
    </span>
  );
}

/** A string, or the dash. */
export function TextOrDash(props: { value: string | null | undefined }) {
  return props.value === null || props.value === undefined || props.value === "" ? (
    <Dash />
  ) : (
    <>{props.value}</>
  );
}

/** A label/value row. The value is a node so a MoneyCell, a DateCell or a pill
 *  can land in it without this file learning what any of them are. */
export function Field(props: { label: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5 py-1.5">
      <span className="text-xs uppercase tracking-wide text-neutral-700">{props.label}</span>
      <span className="text-sm text-text">{props.children}</span>
    </div>
  );
}

/** Two or three `Field`s across, collapsing to one column below 1024px. The
 *  breakpoint is `max-lg:` because our scale is DESKTOP-FIRST — `lg:` would
 *  silently mean the opposite viewport (G36). */
/**
 * ⚠ **THE ROW GAP WAS MISSING, SO TWO ROWS OF FIELDS TOUCHED (`DEF-CUS-5098`).**
 * `gap-x-6` sets `column-gap` alone; `row-gap` stayed at `normal`, ie **0**. So
 * a three-across grid put 24px between columns and NOTHING between rows, and
 * below 1024px — where `max-lg:grid-cols-1` collapses it to one column — every
 * field in it touched the next. B14 rule 39 as amended 2026-09-12 ratifies
 * **field → field 20px** (*"a) 20 everywhere — the anatomy wins"*).
 *
 * `gap-y-5` is `var(--space-5)` = 20px, the same step `FormModal`'s `FieldStack`
 * and its `[data-panel] > .field + .field` rule use for the same figure. The
 * 24px COLUMN gap is untouched: rule 39's 20 is the vertical rhythm between two
 * fields, and `--space-6` 24 is what separates side-by-side blocks — two
 * different figures for two different distances.
 */
export function FieldGrid(props: { columns?: 2 | 3; children: ReactNode }) {
  const cols = props.columns === 3 ? "grid-cols-3" : "grid-cols-2";
  return (
    <div className={`grid ${cols} gap-x-6 gap-y-5 max-lg:grid-cols-1`}>{props.children}</div>
  );
}

/** A value the server serves as `null` because nobody has entered one yet.
 *  B19 §7: *"blanks are shown as blanks, never omitted"* — the review prints
 *  `Plot or parcel → Not supplied`, and so does this. */
export function NotSupplied(props: { t: Translator }) {
  return (
    <span className="text-neutral-700">{props.t("customers.serviceRequest.notSupplied")}</span>
  );
}

export function TextOrNotSupplied(props: { value: string | null; t: Translator }) {
  return props.value === null || props.value === "" ? (
    <NotSupplied t={props.t} />
  ) : (
    <>{props.value}</>
  );
}

/**
 * ⛔ **A VALUE THAT IS A CATALOGUE KEY, RESOLVED — `DEF-CUS-5010`.**
 *
 * `service_requests.lookup_found` stores **a key, not English**, and it does so
 * deliberately: `service_request_service.py:1139` records that *"the sentence
 * renders on a customer-facing-ish screen and the 2026-08-19 ruling says a
 * screen's words come from the catalogue entry and from nothing else"*. The
 * column therefore holds `customers.serviceRequest.lookup.servedAndVacant` and
 * **the three screens that drew it handed it to `TextOrNotSupplied`, which
 * prints a string as it stands.** Measured in Chromium on `brazosbend`,
 * 2026-09-12 at `2.238.0`: the Decision tab and the Location & services tab
 * each printed the dotted key to a clerk, on every one of the eight requests.
 *
 * ⚠ **THIS IS A SEPARATE FAULT FROM THE MISSING CATALOGUE LINES AND THE LINES
 * ALONE WOULD NOT HAVE FIXED IT.** Writing all eleven catalogue entries makes
 * `t(key)` return a sentence; it does nothing whatever for a site that never
 * calls `t`. Both halves shipped together for that reason.
 *
 * ⚠ **AND IT IS A SECOND COMPONENT RATHER THAN A WIDENED `TextOrNotSupplied`.**
 * That one renders free text a person typed — `plot_or_parcel`,
 * `what_is_being_built`, an applicant's name — and putting a translator over
 * those would mean asking i18next to look up whatever a clerk wrote. Two
 * different kinds of value, two components, and the call site says which kind
 * it is holding.
 *
 * A value that resolves to nothing renders AS ITSELF rather than as an empty
 * span: an unminted key must stay visible so it is found (it was found exactly
 * this way), and a legacy row holding real English — which four test fixtures
 * and any pre-`CR-031` data still do — must keep reading as English.
 */
/**
 * ⛔ **A MACHINE TOKEN THAT RESOLVES TO NOTHING IS NOT PRINTED AT A CLERK —
 * `DEF-CUS-5422`, found by looking at the rebuilt screen and by nothing else.**
 *
 * `DEF-CUS-5420` taught that a timeline note is a clerk's own sentence on one
 * row and a STORED KEY on another, and this component was written to resolve
 * the dotted kind. It fell back to printing the value, which is right for a
 * clerk's sentence and wrong for anything machine-shaped — so
 * `applicant_supplied_no_email_or_phone` rendered verbatim in the History
 * block of `SR-26-0005` at 1440 and 1280, one row under the fix for its
 * dotted cousin.
 *
 * ⚠ **THE SAME DEFECT, ONE SHAPE ALONG, AND THAT IS WHY THE GUARD IS GENERAL
 * RATHER THAN A LIST OF FOUR CODES.** The acknowledgement path alone has four
 * (`no_delivery_adapter_in_this_product`,
 * `notifications_publishes_no_queue_document`,
 * `applicant_supplied_no_email_or_phone`,
 * `notifications_has_no_service_request_source_type`) and mapping those would
 * leave the fifth to be found by a Product Owner. **A token is anything with
 * no space in it and an internal `.` or `_`** — no clerk's sentence looks like
 * that, and a value that legitimately does (a receipt number, a premises
 * number) carries neither separator in that position.
 *
 * ⚠ **AND THE FALLBACK SAYS SOMETHING TRUE RATHER THAN NOTHING.** Rendering
 * empty would drop the fact that a system row exists at all; *"Recorded by the
 * system."* is what the row honestly is when its reason cannot be read.
 * B14 rule 32 — no internal code in clerk-facing copy.
 */
const MACHINE_TOKEN = /^[a-z0-9]+([._][a-z0-9]+)+$/i;

export function CatalogueSentence(props: { value: string | null; t: Translator }) {
  if (props.value === null || props.value === "") {
    return <NotSupplied t={props.t} />;
  }
  const resolved = props.t(props.value, { defaultValue: props.value });
  if (resolved === props.value && MACHINE_TOKEN.test(props.value.trim())) {
    return <>{props.t("customers.serviceRequest.event.systemNoteUnreadable")}</>;
  }
  return <>{resolved}</>;
}

export function DateOrNotSupplied(props: {
  value: string | null;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  withTime?: boolean;
}) {
  return props.value === null || props.value === "" ? (
    <NotSupplied t={props.t} />
  ) : (
    <DateCell
      value={props.value}
      timeZone={props.timeZone}
      dateFormat={props.dateFormat}
      withTime={props.withTime}
    />
  );
}

// ══════════════════════════════════════════════════════════════════════════
// SERVICES — the ten cards on REQ-03.2
// ══════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════
// `unavailable` — six named things this surface will not do
// ══════════════════════════════════════════════════════════════════════════

/** Look one up by code. Returns the SERVER's sentence, which is the one a
 *  clerk reads — nothing here writes a substitute for a payload that arrived
 *  without it, because a missing entry means the server stopped claiming the
 *  gap and the screen should stop claiming it too (the DEF-445 lesson). */
export function unavailableReason(
  list: readonly ServiceRequestUnavailable[] | undefined,
  code: string,
): string | null {
  const found = (list ?? []).find((row) => row.code === code);
  return found === undefined ? null : found.detail;
}

export function unavailableTracks(
  list: readonly ServiceRequestUnavailable[] | undefined,
  code: string,
): string {
  const found = (list ?? []).find((row) => row.code === code);
  return found === undefined ? code : found.br_ref;
}

/** The `unavailable` codes this feature addresses by name. Written as constants
 *  so a rename on the server is a compile-adjacent break here rather than a
 *  silently missing sentence. */
export const UNAVAILABLE = {
  // ✅ **`identifier` IS GONE — DEF-632 is closed for the Social Security
  // number (PO 2026-08-27).** It is captured, encrypted at rest and served as
  // `identifier.ssn_last4`, so the server no longer declares it unavailable and
  // a constant pointing at a code nothing emits would render a code as a
  // sentence. What survives is the HALF the ruling did not reach.
  //
  // ✅ **AND THAT HALF IS CLOSED TOO — 2026-09-15, `CR-094-BRC01` lane D
  // finishing what lane G started.** The constant read
  // `driversLicence: "applicant_drivers_licence_not_captured"` and lane G left
  // it standing ON PURPOSE for one commit: `ServiceRequestCapturePage.tsx` was
  // reading it at `driversLicenceReason`, that file belonged to the capture
  // lane building the two inputs at that moment, and deleting a symbol out
  // from under a live lane is how a revert happens (CLAUDE.md law 11).
  //
  // **All three went in the same commit, which is what lane G's record asked
  // for:** this constant, the `driversLicenceReason` fallback, and the
  // catalogue key `customers.serviceRequest.applicant.driversLicenceAbsent`.
  // The server stopped emitting the code, so a constant pointing at it would
  // make `unavailableReason` answer `null` and the screen would print a
  // catalogue sentence saying we hold no licence — over the box a clerk had
  // just typed one into. That is hard-won law 2's MIRROR: a live capability
  // behind a dead refusal, which no gate in this repo can see.
  matcher: "no_customer_matcher",
  fifthCondition: "fifth_approval_condition_unnamed",
  undrawnVerdicts: "undrawn_verdicts_are_possible_not_ruled",
  // ⛔ **`feeLineRemoval` AND `acknowledgement` ARE RETIRED — 2026-09-23,
  // `DEF-CUS-6418`**, in the same commit as the server stopped emitting
  // `fee_line_cannot_be_removed` and `acknowledgement_cannot_be_queued`. The
  // first became false when OQ-357 closed as "both" (a draft's fee line IS
  // removed now); the second had been false since 2026-09-15 (`DEF-CUS-5389`
  // — `submit` queues the acknowledgement), and the confirmation went on
  // printing *"none is waiting to be sent"* over one that was waiting. A
  // constant naming a code nothing emits is how a refusal outlives its truth.
} as const;

// ══════════════════════════════════════════════════════════════════════════
// DOCUMENTS — THE VERDICT LIVES IN `components/documents/`, NOT HERE
//
// This lane wrote a `DocumentStateChip` and a `RejectReason` here first, then
// found that `components/documents/DocumentTable.tsx` had ALREADY implemented
// the PO's 2026-09-22 ruling — two verdicts, an empty cell for an unjudged
// file, and a character-cut `shortReason` — for the capture screen. Two
// spellings of one fact is what B14 rule 43 exists to refuse, so the decision
// was EXTRACTED into `components/documents/DocumentStateCell.tsx` instead and
// both tables ask it. `documentVerdict` there is also what the Documents tab
// counts with, so its header and its rows cannot disagree.
//
// ⚠ **THE LESSON IS THIS REPO'S OWN AND IT COST HALF AN HOUR HERE:** before
// building a shared piece, look for the one that already exists. It is law
// 11's last clause — *read the listing first* — applied to components rather
// than to scripts.
// ══════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════
// AN IDENTIFIER ON A LIST SHOWS ITS LAST FOUR — PO ruling 2026-09-22
// ══════════════════════════════════════════════════════════════════════════

/**
 * **PO ruling 2026-09-22, verbatim: *"Yes, last four only"*.**
 *
 * The worked case: a driving licence offered as proof of identity, printing as
 * `865554556` in the Documents tab's `WHAT IT PROVES` cell on `SR-26-0011` —
 * a government identifier in plain text on a list screen. `BR-CUS-092(c)` has
 * required last-four-only on every read path since 2026-08-24 and this cell
 * was outside it, because the number was typed into a FREE TEXT box that had
 * nowhere else to put it.
 *
 * ⚠ **THIS MASKS, AND IT IS NOT THE FIX.** The fix is `document_number`, a
 * field of its own (decision log 2026-09-22, option (a)); this function is
 * what renders it, and what protects the rows already carrying a number in the
 * wrong box.
 *
 * `•••• 4556` — a space, the same spelling `CustomersListPage` has used since
 * `BR-CUS-092(c)` landed, so one product spells one thing one way.
 * Fewer than four characters masks to `••••` and shows nothing, because three
 * digits of a nine-digit number is a hint and a hint is what the rule refuses.
 */
export function maskLastFour(value: string | null | undefined): string | null {
  const raw = (value ?? "").replace(/\s+/g, "");
  if (raw === "") return null;
  return raw.length < 4 ? "••••" : `•••• ${raw.slice(-4)}`;
}

/**
 * Does this cell hold an IDENTIFIER rather than words?
 *
 * ⚠ **A HEURISTIC, NAMED AS ONE, AND IT GUARDS A LEGACY COLUMN ONLY.**
 * `what_it_proves` is free text: *"Identity"* is words and `865554556` is a
 * licence number, and the product has no way to know which a clerk typed. So
 * the test is deliberately narrow — **five or more characters, digits and
 * separators only, at least five digits** — which catches a licence, an SSN
 * and a passport number and leaves every English phrase alone.
 *
 * **It errs towards masking on this column and nowhere else.** A masked word
 * is a cosmetic defect a clerk reports; an unmasked government identifier on
 * a list is `BR-CUS-092(c)` broken.
 */
export function looksLikeAnIdentifier(value: string | null | undefined): boolean {
  const raw = (value ?? "").trim();
  if (raw.length < 5) return false;
  if (!/^[0-9][0-9 .\-/]*$/.test(raw)) return false;
  return raw.replace(/[^0-9]/g, "").length >= 5;
}

/** `What it proves` as a CELL: words as typed, an identifier masked. */
export function WhatItProves(props: { value: string | null }) {
  const raw = (props.value ?? "").trim();
  if (raw === "") return <Dash />;
  if (!looksLikeAnIdentifier(raw)) return <>{raw}</>;
  return (
    <span data-masked-identifier="what-it-proves">{maskLastFour(raw)}</span>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE SERVICES TABLE — ONE COMPONENT, TWO SCREENS (PO report rows 14 and 15)
// ══════════════════════════════════════════════════════════════════════════

/**
 * **`Service · Requested start · Connection date` — EXACTLY THREE COLUMNS.**
 *
 * PO ruling 2026-09-22, verbatim *"dont add these"*, refusing a proposed size,
 * charge and per-service status. The decision-log entry is titled *THE NEW
 * REQUEST REVIEW TABLE IS THREE COLUMNS* and its consequence clause is
 * explicit: **no placeholder column, no hidden column, no commented-out one**
 * — *"a column that exists and is empty is the thing this ruling is against,
 * and a commented-out column is a promise nobody is keeping"*.
 *
 * **What it replaces on the detail screen (rows 14 and 15 of the PO's list):**
 * two flat rows — `Services requested · Water · Sewer · Trash` and
 * `Requested start · 22-Sep-26, all 3` — which could state the AGREEMENT and
 * could never show one service starting on a different day from another. The
 * table can.
 *
 * ⚠ **THE TWO DATES ARE DIFFERENT FACTS, AND SINCE 2026-09-22 ONE FILLS THE
 * OTHER IN ONE DIRECTION ONLY.** `Requested start` is the per-service date;
 * `Connection date` is the WHOLE JOB's date, repeated down the column because
 * it is one fact about the request. PO ruling 2026-09-22, option (b): *"the
 * per-service dates default from the job date, and a clerk overrides where a
 * service differs"* — job → service, never the reverse (`BR-CUS-1070`
 * narrowed). **This table resolves nothing itself**: it prints what it is
 * handed. The capture review hands it `serviceStartsPayload` (the date the
 * POST carries) and the request detail hands it what the server STORED, so a
 * dash here means the request genuinely holds no date for that service.
 * ⚠ **THIS PARAGRAPH SAID *"an unanswered service prints a dash and never
 * borrows the job's date"* UNTIL 2026-09-23 (`DEF-CUS-6409`)** — true of the
 * table and the reason the PO saw `—` on the review and on the detail of
 * SR-26-0016: step 2 SHOWED the job date in every service's box and the
 * payload sent `null`, so there was nothing but a dash to print.
 *
 * ⚠ **THE SHARED TABLE TYPE, NOT A GRID (B14 rule 20 · rule 43).** One table
 * type in this product, and this is it.
 */
export function RequestedServicesTable(props: {
  services: { code: string; requested_start: string | null }[];
  /** The whole job's date — one fact about the request (REQ-03 step 4). */
  connectionDate: string | null;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** Where the caller wants this in its own DOM, for a walkthrough to find. */
  testId?: string;
}) {
  if (props.services.length === 0) {
    return (
      <p className="text-sm text-neutral-700" data-services-table="none">
        {props.t("customers.serviceRequest.services.noneAsked")}
      </p>
    );
  }
  return (
    <table className="data-table" data-services-table={props.testId ?? ""}>
      <thead>
        <tr>
          <th>{props.t("customers.serviceRequest.services.col.service")}</th>
          <th>{props.t("customers.serviceRequest.services.col.requestedStart")}</th>
          <th>{props.t("customers.serviceRequest.services.col.connectionDate")}</th>
        </tr>
      </thead>
      <tbody>
        {props.services.map((row) => (
          <tr key={row.code} data-service-row={row.code}>
            <td>{props.t(`rating.service.${row.code}`, { defaultValue: row.code })}</td>
            <td className="whitespace-nowrap">
              <DateOrDash
                value={row.requested_start}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            </td>
            <td className="whitespace-nowrap">
              <DateOrDash
                value={props.connectionDate}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** A date, or the drawn em dash. The dash is this page's absence glyph and a
 *  `Not supplied` sentence six times down one column is what the PO removed on
 *  2026-09-19. */
export function DateOrDash(props: {
  value: string | null;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  if (props.value === null || props.value === "") return <Dash />;
  return <DateCell value={props.value} timeZone={props.timeZone} dateFormat={props.dateFormat} />;
}

// ══════════════════════════════════════════════════════════════════════════
// THE APPLICATION FEE — ONE LINE, ONE STATE (PO report 2026-09-22, row 10)
// ══════════════════════════════════════════════════════════════════════════

/**
 * **PO, verbatim:** *"i dont know whether this informtion is correct - we are
 * either taking application fees or we are waiveing it off so message should
 * be in line with that"*.
 *
 * **What was there:** the SAME sentence three times, under `Quoted`,
 * `Collected` and `Outstanding`, then `Not yet: No blocking arrears.` A
 * three-way quoted/collected/outstanding split is a FINANCE BREAKDOWN for a
 * part-payment, and an application fee is not that — it is raised or it is
 * not, and it is taken or it is waived.
 *
 * **The four states, one line each, every one inside B14 rule 33's six-word
 * cap for a fact:**
 *
 * | state | the line |
 * |---|---|
 * | nothing raised | `No application fee.` |
 * | raised, not taken | `Application fee $40.00. Not taken.` |
 * | taken | `Application fee $40.00 taken. Receipt 1187.` |
 * | waived | `Application fee $40.00 waived. Hardship.` |
 *
 * ⚠ **THE FOUR-FIGURE GRID AND THE ARREARS SENTENCE BOTH GO, AND NOTHING A
 * CLERK COULD ACT ON GOES WITH THEM.** A shortfall is still an open balance
 * and is still not a write-off (`BR-CUS-090`) — that fact moves to the panel's
 * own shortfall line, which the server still serves and which is only drawn
 * when there IS one, rather than being asserted on every request.
 */
export function ApplicationFeeLine(props: {
  fees: {
    quoted: Money;
    waived?: Money;
    collected: Money;
    receipt_no: string | null;
    lines: { waived: boolean; waive_reason_name?: string | null }[];
  };
  t: Translator;
}) {
  const { fees } = props;
  const raised = fees.quoted.currency !== null && fees.quoted.currency !== "";
  /**
   * ⚠ **THE SYMBOL RIDES WITH THE FIGURE, AND ITS ABSENCE WAS A REAL MISS.**
   * `Money.display` is the SERVER's 2-dp string — `"25.00"` — and the
   * `CHAR(3)` travels beside it because this platform is multi-currency
   * (`BR-TEN-042`); everywhere else on this screen `MoneyCell` puts the two
   * together. The first draft of this line interpolated `display` straight
   * into the sentence and printed **`Application fee 25.00 taken`**, a figure
   * with no currency behind it — which is exactly what the panel's own
   * `noCurrencyYet` branch exists to refuse one block up. The suite caught it.
   *
   * ⚠ **AND IT IS A STRING RATHER THAN A `<MoneyCell>` BECAUSE THE SENTENCE
   * IS TRANSLATED.** B8 forbids translated fragments either side of a
   * component — the eleven catalogues each put the amount in their own place
   * in their own sentence — so the formatted money goes in as an interpolated
   * VALUE and the catalogue owns the words around it.
   */
  const money = (value: Money): string =>
    value.currency === null || value.currency === ""
      ? value.display
      : formatMoney(value.amount, value.currency);
  if (!raised) {
    return (
      <p className="m-0 text-md text-neutral-700" data-fee-line="none">
        {props.t("customers.serviceRequest.fees.line.none")}
      </p>
    );
  }
  const waived = fees.lines.length > 0 && fees.lines.every((line) => line.waived);
  /* ⚠ **THE NAME, NEVER THE CODE, AND THE WAIVED FIGURE, NEVER `quoted`
     (`DEF-CUS-6423`).** This read `waive_reason` — the stored Settings code —
     and `quoted`, which sums the UNWAIVED lines and so reads 0.00 on exactly
     this branch: *"Application fee $0.00 waived. BILLERR"*. */
  const waiveReason = (
    fees.lines.find((line) => line.waive_reason_name)?.waive_reason_name ?? ""
  ).trim();
  const taken = (fees.receipt_no ?? "") !== "";
  if (waived) {
    return (
      <p className="m-0 text-md" data-fee-line="waived">
        {props.t("customers.serviceRequest.fees.line.waived", {
          amount: money(fees.waived ?? fees.quoted),
          reason: waiveReason,
        })}
      </p>
    );
  }
  if (taken) {
    return (
      <p className="m-0 text-md" data-fee-line="taken">
        {props.t("customers.serviceRequest.fees.line.taken", {
          amount: money(fees.collected),
          receipt: fees.receipt_no ?? "",
        })}
      </p>
    );
  }
  /* DEF-CUS-9819 — a $0.00 application fee is not "not taken": it owes
     nothing. The panel says so once, under the table (`nothingToCollect`). */
  if (/^0+(\.0+)?$/.test(fees.quoted.amount.trim())) {
    return (
      <p className="m-0 text-md" data-fee-line="zero">
        {props.t("customers.serviceRequest.fees.line.zero", { amount: money(fees.quoted) })}
      </p>
    );
  }
  return (
    <p className="m-0 text-md" data-fee-line="not-taken">
      {props.t("customers.serviceRequest.fees.line.notTaken", { amount: money(fees.quoted) })}
    </p>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE AUDIT TAB'S `WHAT` COLUMN — PO report 2026-09-22, row 7
// ══════════════════════════════════════════════════════════════════════════

/**
 * **WHAT HAPPENED, from the row's own `note_type` — `DEF-CUS-6181`.**
 *
 * The PO read an Audit tab where **every row's WHO said `Vijay Bikkad`,
 * including the rows whose WHAT said `System`**, and where two of the entries
 * were `System / SR-26-0011` and `System / This address is not on record.` —
 * neither of which says what happened.
 *
 * ⚠ **THE COLUMN WAS RENDERING THE `kind`, AND `kind` IS A CATEGORY OF THREE,
 * NOT AN EVENT.** `state` · `note` · `system` — and `system` is the DEFAULT, so
 * every side effect a clerk causes lands in it: numbering a request, resolving
 * its address, linking a customer, attaching an outage report, taking a fee,
 * parking it, queueing the acknowledgement, sending the applicant a message.
 * Ten different acts, one word.
 *
 * ⚠ **AND THE REAL EVENT NAME HAS BEEN IN THE PAYLOAD THE WHOLE TIME.** Every
 * one of those writes passes `note_type` — `number_allocated`,
 * `address_resolved`, `fee_collected:cash`, `parked:<reason>` — and `history_tab`
 * has served it since the field existed. **No screen has ever read it.** That is
 * hard-won law 2 from the payload end, and it is the same shape as `actor_name`,
 * which the WHO column got on 2026-09-19 when somebody finally asked.
 *
 * ⚠ **THE FAMILY IS WHAT IS NAMED, NOT THE WHOLE STRING.** Four of the writers
 * append a detail with a colon — `fee_collected:cash`, `parked:not_our_area`,
 * `acknowledgement:queued`, `applicant_message:<code>:<state>` — and that tail
 * is a value, not a vocabulary a catalogue can be expected to hold. So the part
 * before the first colon names the act and the tail stays in the payload.
 *
 * ⚠ **AN UNKNOWN `note_type` FALLS BACK TO THE KIND AND NEVER TO ITS OWN
 * SNAKE_CASE.** A new writer lands in a module this screen does not read, and
 * printing `interruption_detached` at a clerk is B14 rule 32's internal code in
 * clerk-facing copy.
 */
export function eventFamily(noteType: string | null | undefined): string | null {
  const raw = (noteType ?? "").trim();
  if (raw === "") return null;
  const family = raw.split(":")[0] ?? "";
  return family === "" ? null : family;
}

/**
 * The `WHAT` cell: the act, in words.
 *
 * ⚠ **A `system` ROW WITH NO `note_type` IS A DASH AND NOT THE WORD
 * `System`** — which is the other half of row 7. `system` is the row's
 * CATEGORY; if nothing named the act, the product does not know what happened
 * and saying so is the honest cell. Printing `System` here would put the same
 * word in both columns of one row, which is the duplication the PO's sentence
 * — *"a row cannot be both System and a person"* — is about, arriving from the
 * other direction.
 *
 * `state` and `note` rows keep their own words (`Moved to`, `Note`), because
 * those two KINDS really are the act.
 */
export function EventWhat(props: { kind: string; noteType: string | null; t: Translator }) {
  const family = eventFamily(props.noteType);
  if (family === null) {
    if (props.kind === "system") return <Dash />;
    return (
      <>
        {props.t(`customers.serviceRequest.event.${props.kind}`, { defaultValue: props.kind })}
      </>
    );
  }
  const named = props.t(`customers.serviceRequest.eventType.${family}`, { defaultValue: "" });
  return (
    <span data-event-type={family}>
      {named === ""
        ? props.t(`customers.serviceRequest.event.${props.kind}`, { defaultValue: props.kind })
        : named}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W4 (B18 §W4 tasks 4.10–4.13) · B19 · BR-CUS-090..095
// generated: 2026-08-24 by the CR-031 W4 FRONTEND lane (M3)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: tsc✔ eslint✔ vitest✔ · G31 skips this file (Route B) and
//        routeBUtilities.test.ts owns it instead
// exceptions: E3 the ten service cards use the SHIPPED badge letters, not the
//   four B19 §3 draws — DEF-636 decides, B19 §9 instructs exactly this ·
//   E3 there is no page-level absence panel and there will not be one: the PO
//   deleted three from the accounts screens on 2026-08-24
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
