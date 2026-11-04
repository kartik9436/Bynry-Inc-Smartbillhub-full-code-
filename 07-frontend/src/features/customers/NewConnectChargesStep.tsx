// ── Trace ──────────────────────────────────────────────
// Change:   `CR-150-BRC09` task 11 — **STEP 4 · CHARGES, REDRAWN.** Built from
//           `05-prototype/new-connect-redesign-2026-09-28/step4-charges.png`,
//           READ AS AN IMAGE (B14 rule 42), with spacing, sizes, the type
//           scale and the component kit from B14 (rule 44). The step was 6 of
//           8 and is now 4 of 5.
//
//           **WHAT THE DRAWING ADDS, AND WHAT EACH ONE COST:**
//             1 · a CONTEXT STRIP across the top — seven facts about the build
//                 a clerk is pricing, none of them typed here;
//             2 · **Billed to as a SELECT**, where the step had three radio
//                 cards. All three options stay (`DEF-CUS-7610`, PO: *"this is
//                 wring - keep previous options"*) and the two the server
//                 refuses are `disabled` from ONE declaration that names the
//                 server's own refusal code, not from a literal at each site;
//             3 · a **Billing preferences** panel — Autopay, Tax exempt,
//                 Certificate number, Exemption expires — WIRED to the owner's
//                 account through four `customers.CREATE_FIELDS` entries that
//                 have always existed and that this wizard has never sent;
//             4 · **ONE `Payment option`** where the step had *Take payment*
//                 and *Method* as two controls, and the reference label that
//                 follows it;
//             5 · a **Total · Paid now · Remaining** footer on the charges
//                 table, through `TableArray`'s `footerTrailing`.
//
//           ⛔ **THE DRAWN *EDITABLE QTY* IS NOT BUILT, AND THAT IS THE PRIME
//           DIRECTIVE RATHER THAN A SHORTFALL.** `OQ-CUS-12770` is **OPEN** —
//           *which quantities were 1, 2 and 15, and is a charge's quantity
//           typed per charge or counted?* — and `CR-150-BRC09` §5 says of it,
//           in terms: *"NOTHING IS BUILT HERE UNTIL `OQ-CUS-12770` IS RULED …
//           It multiplies a price on a real invoice."* The Qty cell therefore
//           renders the COUNT, exactly as it did, and no clerk can type over
//           it. Answering it by building the box would be choosing option (b)
//           of three, which is the one thing the prime directive forbids.
//
//           ⛔ **AND TWO THINGS STAY DELIBERATELY UNBUILT (`DEF-CUS-7704`):**
//           the third *Take payment* option (*"No, the developer pays per
//           unit"*) restates the payer and the server refuses that payer by
//           name, so it would be a control that lies; and **`Remaining` is
//           `Total − Paid now`, which is money arithmetic in a browser** —
//           forbidden by hard rule 2 and the exact shape of `DEF-088` and
//           `DEF-127`. The row is DRAWN and its figure is STATED ABSENT.
// Rules:    CLAUDE.md hard rule 2 (money is stored to 4 decimals, DISPLAYED to
//           2, rounded ONCE on the server; never a float, never client-side
//           arithmetic) · BR-BIL-020 (lines come ONLY from rules and charge
//           codes) · BR-BIL-007 (the TENANT's row carries the price) ·
//           BR-BIL-024 + PO 2026-08-23 (payment terms are captured, never
//           guessed — NO DEFAULT) · BR-MET-113 (charges are tagged to an
//           ACCOUNT number) · BR-MET-112 (nothing is written until the last
//           button) · BR-MET-1178 (a build prices itself; the quantity is
//           COUNTED) · BR-MET-1187 (the counter payment) · BR-PAY-021 (no
//           clearing date means the money has not arrived) · BR-PAY-026 (the
//           tender list is the tenant's) · BR-CUS-059 (autopay is
//           capture-only in v1) · BR-SHL-025 (a control that cannot act is
//           DISABLED WITH ITS REASON) · BR-TEN-043 / G6 (an event date, never
//           a wall clock) · B14 rules 20, 21, 31, 32, 33, 37, 42, 43, 44
// Questions: ⛔ `OQ-CUS-12770` (typed or counted quantity) — **OPEN**, and the
//           Qty cell is a FACT here because of it · `OQ-BIL-12381` (which
//           signed rule the deposit ruling supersedes) — OPEN, and nothing
//           here raises or shows a deposit · `OQ-BIL-12376` (whether a quote
//           HOLDS its price) — OPEN
// Tests:    NewConnectChargesRedesign.dom.test.tsx · NewConnectWizard.test.tsx
// ───────────────────────────────────────────────────────
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCharges, getPayments } from "@/api/endpoints";
import type { ChargeRow } from "@/api/endpoints";
import { REFERENCE_STALE_MS } from "@/api/queryClient";
import { DatePickerField, SelectField, TextField } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { RefusalStrip } from "@/components/Surfaces";
// ⚠ **THE KIT'S COLLECTION, NOT A SECOND ONE.** `TableArray` was built for
// these five drawings and its own §2 names this screen as the caller that
// would bring `footerTrailing` with it. B14 rule 20 is ONE table type and
// rule 43 is that a piece of UI is a COMPONENT — two table arrays for one
// idea is how two screens start disagreeing, which is the concern the PO
// raised by name.
import { CellSelect, CellStatic, TableArray } from "@/components/TableArray";
import { Note } from "@/components/TextBits";
// ⚠ **THE TENDER LIST COMES FROM PAYMENTS' OWN HELPER, NOT A SECOND MAPPING.**
// `methodOptions` is `BR-PAY-026`'s one reading of `methods[]` and the S22
// Record-a-payment form uses it; a second copy here would be the third
// spelling of one rule (B14 rule 43).
import { methodOptions } from "@/features/payments/paymentsShared";

import type {
  BuildChargeBasis,
  BuildChargeLine,
  NewConnectDraft,
  QuotePayer,
} from "./newConnectDraft";
import {
  BUILD_CHARGE_BASES,
  buildChargeQuantities,
  buildOpensOwnerAccount,
  ownerAccountKind,
  draftUnits,
  draftUnitServices,
  quoteLinesOf,
} from "./newConnectDraft";
import { previewConnectionQuote, QUOTE_LINE_CANNOT_BE_PRICED } from "./newConnectEndpoints";
import type { QuoteMoney as QuoteMoneyFigure, QuotePreview } from "./newConnectEndpoints";
import { takesAMeter } from "./newConnectShared";
import { FieldGrid } from "./serviceRequestShared";
import { getPlanWithSections } from "@/api/planFormEndpoints";
import { DiscountsSection, TaxSection } from "./moveInWizard/BillingExtras";
import type { StepBillingOwn } from "./moveInWizard/billingModel";
import { moveInExtrasOwn, moveInExtrasProblems } from "./newConnectDraft";
import { PreferencesPanel } from "./customerForm/PreferencesPanel";
import type { PreferencesValue } from "./customerForm/PreferencesPanel";
import type { Translator } from "./newConnectShared";
import { BuildContextStrip } from "@/features/work/buildRecord/BuildContextStrip";

/** The key every screen reads the tenant's charge catalogue under, so the
 *  Plans & Rates screens and this one share one cache and cannot drift. */
export const newConnectChargesQueryKey = ["charges", "new-connect"] as const;


/**
 * **CAN THIS CHARGE CODE BE RAISED ON A BUILD AT ALL?** — `DEF-MET-6110`,
 * PO ruling 2026-09-21: *"Step 6 offers only charge codes a build can price."*
 *
 * ⚠ **IT IS A MIRROR OF THREE SERVER CHECKS AND IT IS NOT THE AUTHORITY.**
 * `rating.selectors.charge_by_code` answers `amount: null` for anything that is
 * not `flat` — *"a percent rule needs a basis this read has no way to supply"* —
 * and `billing.fee_bill.charge_code_line` then refuses a null amount and a code
 * with no GL account by name. Those three are the rule; this is the same three
 * questions asked early, off the row the picker already holds.
 *
 * ⛔ **AND A MIRROR GOES STALE, WHICH IS THE WHOLE REASON LAYER 2 EXISTS.** A
 * tenant edits a charge code on Settings this afternoon — `charge_by_code` says
 * so in its own words, *"the amount is a SEED the tenant edits, never a
 * constant"* — and a picker filtered when the step mounted cannot know. The
 * commit still catches billing's refusal and answers on THIS step. **Do not
 * read this filter as a guarantee, and do not delete the catch because it is
 * here.**
 */
export function canBeRaisedOnItsOwn(row: ChargeRow): boolean {
  // `null` means the row states no rule, and `charge_by_code` reads that as
  // `flat` — the same default, in the same words, so the two cannot disagree.
  const flat = (row.amount_rule ?? "flat") === "flat";
  return flat && row.amount !== null && row.gl_account_id !== null;
}

/** The basis in the clerk's own language. ⚠ The VALUE is billing's spelling
 *  (`"per unit"`) and is never rendered raw — a machine token on screen is
 *  what B14 rule 31 and the PO's *"no Databse ID on screen"* both refuse. */
function basisWord(t: Translator, basis: BuildChargeBasis): string {
  const key = {
    "per unit": "customers.newConnect.step6.perUnit",
    "per meter": "customers.newConnect.step6.perMeter",
    "per premise": "customers.newConnect.step6.perPremise",
  }[basis];
  return String(t(key, { defaultValue: basis }));
}

// ══════════════════════════════════════════════════════════════════════════
// WHAT THE QUOTE IS COUNTED ON — the drawing's own three bases
// ══════════════════════════════════════════════════════════════════════════

/**
 * The three quantities p090's table is counted on, from THIS build's grid.
 *
 * The drawing's worked build is six dwellings plus a common area, and its
 * caption reads *"Six units, twenty service points, one premise"* — so
 * `per unit` counts the DWELLINGS (the common area has its own drawn line, at
 * `per premise`), `per meter` counts the meters the build will fit, and
 * `per premise` is the one property every unit hangs off (hard rule 8).
 *
 * ⚠ **`per meter` USES THE SAME `takesAMeter` RULE THE COMMIT USES TO BUILD
 * `meters`.** Counting raw ticks instead would be a second answer to *how many
 * meters is this* that drifts from the payload the moment a service stops
 * taking one, and p089's own rail says *"Meters to fit 20 · one per service
 * point"* about the same twenty.
 *
 * ⚠ **NO MONEY IS COMPUTED HERE, AND THAT IS NOT AN OMISSION.** These are
 * COUNTS. What a count is worth is `charge_code_line`'s to say, and that
 * function's own docstring forbids a caller doing it: *"A caller that
 * multiplied first and handed in a product would be the second rounding path
 * this comment exists to prevent, which is why there is no amount parameter for
 * it to arrive through."*
 */
export function quoteCounts(draft: NewConnectDraft): {
  units: number;
  meters: number;
  premises: number;
} {
  const units = draftUnits(draft);
  const services = draftUnitServices(draft);
  let meters = 0;
  for (const unit of units) {
    for (const service of services[unit.label] ?? []) {
      if (takesAMeter(service)) {
        meters += 1;
      }
    }
  }
  return {
    units: units.filter((unit) => !unit.isCommonArea).length,
    meters,
    premises: units.length > 0 ? 1 : 0,
  };
}

// ══════════════════════════════════════════════════════════════════════════
// WHAT IT COSTS — `DEF-CUS-6115`, and why this is a SERVER read
// ══════════════════════════════════════════════════════════════════════════

/**
 * The priced quote for THIS draft — asked of the server, cached by the lines.
 *
 * ⚠ **THE OLD COMMENT ON THIS SCREEN SAID THE MONEY WAS A MISSING DOOR AND IT
 * WAS RIGHT, SO THE DOOR WAS BUILT.** It read *"`price_quote_bill` needs an
 * `account_id` and a draft build has none until step 8 writes one, so a priced
 * preview is a missing DOOR rather than a missing screen — `DEF-BIL-5486`"*.
 * `POST /connections/quote-preview` is that door: the same lines, the same
 * `charge_code_line`, no account and no write. The refusal is DELETED rather
 * than reworded — a stated absence that outlives its cause is a lie the product
 * tells about itself (hard-won law 1).
 *
 * ⚠ **NOT ONE FIGURE IS COMPUTED HERE.** `unit_price`, `amount` and `total`
 * arrive as strings the server rounded once (CLAUDE.md hard rule 2 — 4 decimals
 * stored, 2 displayed, never a float and never client-side arithmetic), and
 * `MoneyCell` is the one formatting path that draws them (`BR-SHL-023`).
 *
 * ⚠ **THE KEY IS THE LINES, WHICH IS WHY THIS COSTS ONE REQUEST AND NOT ONE
 * PER RENDER** — and why the wizard's own step-6 gate can read the same answer
 * from the same cache instead of asking a second time. Change a tick on step 4
 * and the counts move, the key moves, and the figure moves with them.
 *
 * ⚠ **`enabled` IS THE HONEST HALF: WITH NO LINE THERE IS NOTHING TO PRICE.**
 * The server refuses an empty quote by name rather than answering `$0.00`, so
 * asking would be asking for a refusal. The screen states the absence instead.
 */
export function useQuotePreview(draft: NewConnectDraft, client?: ApiClient) {
  const lines = quoteLinesOf(draft);
  return useQuery({
    queryKey: newConnectQuotePreviewQueryKey(lines),
    queryFn: () => previewConnectionQuote(lines, client ?? api),
    enabled: lines.length > 0,
    // A price is a fact about the catalogue, not about this draft: re-asking it
    // on every focus would flicker a figure a clerk is reading.
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
}

/** The cache key for a priced quote — the LINES, because they are the whole
 *  question. Two callers with the same lines share one request. */
export function newConnectQuotePreviewQueryKey(
  lines: ReturnType<typeof quoteLinesOf>,
): readonly unknown[] {
  return ["new-connect", "quote-preview", lines];
}

/**
 * **THE ONE REASON STEP 6 REFUSES TO LET A CLERK PAST IT — `DEF-MET-6110`.**
 *
 * Returns the refusal's own code, or `null` when there is nothing to refuse.
 *
 * ⚠ **A NETWORK FAILURE IS NOT A REFUSAL.** `TAP`, `IMPACT` and `DAMAGE` are
 * live charge codes in the demo tenant with no amount at all, and picking one
 * cost a whole seven-unit build and a bare 500 after eight steps. That is a
 * DEFINITE answer from the server and it blocks. A preview that could not be
 * fetched says nothing about the charge code, so it blocks nothing — a wizard
 * that refused on a dropped request would stop a clerk finishing a build over
 * a screen that is only advisory.
 */
export function quoteCannotBePriced(preview: QuotePreview | undefined): string | null {
  if (preview === undefined || preview.priced) {
    return null;
  }
  const refused = preview.unavailable.find((one) => one.code === QUOTE_LINE_CANNOT_BE_PRICED);
  return refused === undefined ? null : refused.code;
}

/** The server's `display` string, or `null` — and **`null` is a BLANK, never
 *  `$0.00`** (`connection_record._money`'s own rule, which this screen now
 *  matches: a zero on a money line reads as *free* and the truth is *not
 *  priced*). */
export function quoteFigureOf(money: QuoteMoneyFigure | undefined): string | null {
  if (money === undefined || money.stored === null || money.stored === "") {
    return null;
  }
  return money.stored;
}

// ══════════════════════════════════════════════════════════════════════════
// STEP 6 · CHARGES
// ══════════════════════════════════════════════════════════════════════════

/** ⊕ `CR-164-BRC10` item 19 — the five terms the PO named, in days. */
export const PAYMENT_TERM_DAYS = ["7", "15", "30", "60", "90"] as const;

export function paymentTermOptions(
  stored: string,
  t: Translator,
): { value: string; label: string }[] {
  const days: string[] = [...PAYMENT_TERM_DAYS];
  const kept = stored.trim();
  if (kept !== "" && !days.includes(kept)) days.push(kept);
  return days.map((count) => ({
    value: count,
    label: t("customers.newConnect.step6.termDays", {
      defaultValue: "{{count}} days",
      count: Number(count),
    }),
  }));
}

export function ChargesStep(props: {
  draft: NewConnectDraft;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  t: Translator;
  dateFormat: Parameters<typeof DatePickerField>[0]["dateFormat"];
  client?: ApiClient;
  /** ⊕ lane CF-1 — Continue was pressed here (Move-in's panels' refusals). */
  tried?: boolean;
}) {
  const counts = quoteCounts(props.draft);

  // ── THE TENANT'S OWN CHARGE CATALOGUE — `BR-MET-1178` ────────────────────
  // ⚠ **`status: "active"` IS NOT A TIDINESS FILTER.** A deactivated charge is
  // one the utility has stopped selling (`IS-1`, deactivate-first), and
  // offering one here would put a line on a real invoice from a price the
  // tenant retired.
  const chargesQuery = useQuery({
    queryKey: newConnectChargesQueryKey,
    queryFn: () => getCharges({ per: 200, filters: { status: "active" } }, props.client ?? api),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const chargeRows = useMemo(() => chargesQuery.data?.results ?? [], [chargesQuery.data]);
  // ⛔ **`DEF-MET-6110` — ONLY CODES A BUILD CAN ACTUALLY PRICE ARE OFFERED.**
  // PO ruling 2026-09-21. `TAP` was in this list, a clerk picked it, and the
  // last press answered *"Something went wrong on our side."* after
  // thirty-three clerk acts.
  const chargeOptions = useMemo(
    () =>
      chargeRows
        .filter(canBeRaisedOnItsOwn)
        .map((row) => ({ value: row.code, label: `${row.code} · ${row.name}` })),
    [chargeRows],
  );
  // The catalogue answered and NOTHING in it can be raised on a build. A stated
  // absence, because an empty picker with no words is a screen a clerk cannot
  // tell from a broken one (B14 rule 32 — one sentence, closed by default).
  const nothingIsBillable = chargeRows.length > 0 && chargeOptions.length === 0;
  const quantities = buildChargeQuantities(props.draft);
  // `DEF-CUS-6115` — what the commit will raise, asked of the engine that will
  // raise it. Nothing below multiplies or rounds; see `useQuotePreview`.
  const quoteQuery = useQuotePreview(props.draft, props.client);
  const quote = quoteQuery.data;
  const pricedByCode = new Map(
    (quote?.lines ?? []).map((line) => [`${line.charge_code}|${line.basis ?? ""}`, line]),
  );
  const cannotBePriced = quoteCannotBePriced(quote);
  const quoteTotal = quoteFigureOf(quote?.total);

  /** One line's replacement, by position. The array is the draft's; nothing
   *  here keeps a second copy of it. */
  function patchLine(at: number, next: Partial<BuildChargeLine>): void {
    props.onPatch({
      quoteLines: props.draft.quoteLines.map((line, index) =>
        index === at ? { ...line, ...next } : line,
      ),
    });
  }

  // ⚠ **THE SAME CODE ON THE SAME BASIS TWICE IS A LINE BILLED TWICE.** The
  // server would happily raise both, and a customer would read one charge
  // written out two ways. It was a DISABLED add button while the pair was
  // chosen in two fields above the table; the drawing edits the code in the
  // row, so the same rule is now a CELL ERROR on the row that repeats one
  // (`EditableTable`'s `cellError`, which exists for exactly this).
  function duplicateAt(index: number): boolean {
    const line = props.draft.quoteLines[index];
    if (line === undefined || line.chargeCode === "") {
      return false;
    }
    return props.draft.quoteLines.some(
      (other, at) =>
        at < index && other.chargeCode === line.chargeCode && other.basis === line.basis,
    );
  }

  return (
    <>
      {/* ══════════════════════════════════════════════════════════════════
          THE CONTEXT STRIP — `step4-charges.png`, seven cells across the top
          ══════════════════════════════════════════════════════════════════ */}
      <BuildContextStrip draft={props.draft} counts={counts} t={props.t} client={props.client} />

      {/* ⊕ **`CR-164-BRC10` item 20 — *What is charged* COMES FIRST**, above
          *Who is billed* and *Payment* (PO 2026-10-02): the clerk decides what
          is owed before who pays it and what is taken now. */}
      {/* ══════════════════════════════════════════════════════════════════
          WHAT IS CHARGED — the drawn table, through the kit's `TableArray`
          ══════════════════════════════════════════════════════════════════
          ⚠ **IT IS THE KIT'S COLLECTION AND NOT A SECOND ONE.**
          `components/TableArray.tsx` was built for these four drawings and its
          own note names this screen; B14 rule 20 is ONE table type and rule 43
          is that a piece of UI is a COMPONENT. Two components for one idea is
          how two screens start disagreeing.

          ⚠ **NOTHING ON THIS TABLE IS ADDED UP HERE.** `Each` and `Amount` are
          the server's own strings for THIS build's lines, drawn through
          `MoneyCell`, and the footer's `Total` is the engine's total for the
          same lines. Hard rule 2, `DEF-088`, `DEF-127`.

          ⛔ **THE DRAWN `$45.00`, `$150.00`, `$1,035.00` AND `3` ARE
          ILLUSTRATIONS AND NOT ONE OF THEM IS PRINTED** (B14 rule 37). */}
      <TableArray<BuildChargeLine>
        collection="quote-lines"
        title={props.t("customers.newConnect.step6.lines", { defaultValue: "What is charged" })}
        rows={props.draft.quoteLines}
        rowKey={(line, index) => `${line.chargeCode}-${line.basis}-${index}`}
        emptyText={props.t("customers.newConnect.step6.noLines")}
        removeLabel={props.t("customers.newConnect.step6.removeLine")}
        onChange={(quoteLines) => props.onPatch({ quoteLines })}
        cellError={(_line, index, columnKey) =>
          columnKey === "charge" && duplicateAt(index)
            ? props.t("customers.newConnect.charges.alreadyOnTheList", {
                defaultValue: "This charge is already listed.",
              })
            : undefined
        }
        actions={[
          {
            key: "add-charge",
            label: props.t("customers.newConnect.step6.addCharge", {
              defaultValue: "+ Add charge",
            }),
            onClick: () =>
              props.onPatch({
                quoteLines: [...props.draft.quoteLines, { chargeCode: "", basis: "per unit" }],
              }),
            blockedReason: nothingIsBillable
              ? props.t("customers.newConnect.step6.noneBillable", {
                  defaultValue: "No charge here carries a price.",
                })
              : undefined,
          },
        ]}
        footerTrailing={
          <ChargeTotals
            draft={props.draft}
            t={props.t}
            total={quoteTotal}
            currency={quote?.currency ?? null}
          />
        }
        columns={[
          {
            key: "charge",
            label: props.t("customers.newConnect.step6.charge", { defaultValue: "Charge" }),
            // B14 rule 31 — the CODE and the NAME, never the charge's uuid.
            cell: (line, index) => (
              <CellSelect
                name={`charge-${index}`}
                label={props.t("customers.newConnect.step6.charge", { defaultValue: "Charge" })}
                value={line.chargeCode}
                options={chargeOptions}
                placeholder={props.t("customers.newConnect.step6.choosePlaceholder")}
                onChange={(chargeCode) => patchLine(index, { chargeCode })}
              />
            ),
          },
          {
            key: "basis",
            label: props.t("customers.newConnect.step6.basis", { defaultValue: "Basis" }),
            cell: (line, index) => (
              <CellSelect
                name={`basis-${index}`}
                label={props.t("customers.newConnect.step6.basis", { defaultValue: "Basis" })}
                value={line.basis}
                options={BUILD_CHARGE_BASES.map((basis) => ({
                  value: basis,
                  label: basisWord(props.t, basis),
                }))}
                placeholder={props.t("customers.newConnect.step6.choosePlaceholder")}
                onChange={(basis) => patchLine(index, { basis: basis as BuildChargeBasis })}
              />
            ),
          },
          {
            key: "qty",
            label: props.t("customers.newConnect.step6.qty", { defaultValue: "Qty" }),
            numeric: true,
            // ⛔ **A FACT AND NOT A BOX, AND `OQ-CUS-12770` IS WHY.** The
            // drawing draws an editable Qty input. The question *is a charge's
            // quantity typed per charge or counted?* is **OPEN**, it is money
            // on a real invoice, and `CR-150-BRC09` §5 says of this exact cell
            // *"NOTHING IS BUILT HERE UNTIL `OQ-CUS-12770` IS RULED"*.
            // Building the input picks option (b) of the three the question
            // offers, which is the one act the prime directive forbids. The
            // COUNT is unchanged and still moves with step 3.
            cell: (line) => (
              <CellStatic name="qty">
                <span className="tabular-nums">{quantities[line.basis]}</span>
              </CellStatic>
            ),
          },
          {
            key: "each",
            label: props.t("customers.newConnect.step6.unitPrice", { defaultValue: "Each" }),
            numeric: true,
            cell: (line) => (
              <QuoteMoney
                what="unit-price"
                amount={quoteFigureOf(pricedByCode.get(`${line.chargeCode}|${line.basis}`)?.unit_price)}
                currency={quote?.currency ?? null}
              />
            ),
          },
          {
            key: "amount",
            label: props.t("customers.newConnect.step6.amount", { defaultValue: "Amount" }),
            numeric: true,
            cell: (line) => (
              <QuoteMoney
                what="amount"
                amount={quoteFigureOf(pricedByCode.get(`${line.chargeCode}|${line.basis}`)?.amount)}
                currency={quote?.currency ?? null}
              />
            ),
          },
        ]}
      >
        {/* ⚠ **A CODE THE CATALOGUE CANNOT PRICE IS REFUSED HERE, WHERE IT WAS
            PICKED — `DEF-MET-6110`.** `TAP`, `IMPACT` and `DAMAGE` are live
            charge codes with no amount at all; picking one used to commit
            eight steps of work and answer 500, losing the build. */}
        {cannotBePriced !== null && (
          <RefusalStrip data-quote-unpriceable="">
            {props.t("customers.newConnect.step6.cannotBePriced", {
              defaultValue: "This charge has no price. Choose another.",
            })}
          </RefusalStrip>
        )}
        {quoteQuery.isError && (
          /* The PRICE could not be read. It does not block: a dropped request
             says nothing about the charge code, and a wizard that refused on
             one would stop a build over an advisory screen. */
          <RefusalStrip data-quote-preview-failed="">
            {props.t("customers.newConnect.step6.previewFailed", {
              defaultValue: "The price could not be read.",
            })}
          </RefusalStrip>
        )}
        {nothingIsBillable && (
          <Note className="max-w-measure" data-no-billable-charge="">
            {props.t("customers.newConnect.step6.noneBillable", {
              defaultValue: "No charge here carries a price.",
            })}
          </Note>
        )}
      </TableArray>

      <div className="grid grid-cols-2 gap-6 max-lg:grid-cols-1">
        {/* ── WHO IS BILLED — and the choice TRAVELS ─────────────────────────
            ⚠ **A SELECT, WHERE THE STEP HAD THREE RADIO CARDS.** The drawing
            draws one chooser and prints the three options beneath it; B14 rule
            44 gives our kit the say in how it is BUILT and the kit's chooser
            is `SelectField`, which already honours a per-option `disabled`
            (`FieldOption.disabled`, added for exactly this shape:
            *"Present and unselectable beats absent … and beats selectable"*).

            ⚠ **ALL THREE STAY ON SCREEN — `DEF-CUS-7610`, PO: *"this is wring
            - keep previous options"*.** Removing the two nobody can choose was
            proposed and reversed by the Product Owner in those words.

            ⚠ **AND THEY ARE DISABLED FROM ONE DECLARATION, NOT FROM A LITERAL
            AT EACH SITE.** That is the other half of `DEF-CUS-7610`: the cards
            passed `available={false}` twice, hardcoded, so the screen's claim
            had no tie at all to the rule that makes it true. `PAYER_REFUSALS`
            below names the SERVER's own refusal code per payer, so the day
            `_quote_payer` honours one, one line moves and the screen follows.
        */}
        <Panel as="section">
          <h4 className="font-heading text-md m-0 mb-1">
            {props.t("customers.newConnect.step6.billedTo", { defaultValue: "Who is billed" })}
          </h4>
          <BilledToSelect draft={props.draft} onPatch={props.onPatch} t={props.t} />
          <FieldGrid columns={2}>
            {/* ── `DEF-CUS-6112` · REQUIRED THE MOMENT A CHARGE EXISTS ───────
                ⚠ **THERE IS NO DEFAULT AND THERE MUST NOT BE** (`BR-BIL-024`,
                PO 2026-08-23). A guessed due date starts a late-fee clock on a
                real customer's invoice. The drawing's own placeholder says the
                same thing in two words: *No default*.

                ⚠ **OPTIONAL WITH NO CHARGE ON THE LIST**, which is why this is
                a condition and not a constant: a build that charges nothing
                needs no terms, and the server REPORTS that absence rather than
                refusing the build. */}
            {/* ⊕ **`CR-164-BRC10` item 19 — A LIST OF TERMS, NOT A NUMBER
                BOX** (PO 2026-10-02: 7, 15, 30, 60 or 90 days). Still no
                default (`BR-BIL-024`: captured, never guessed). A figure a
                parked draft holds that the list lacks is kept and shown. */}
            <SelectField
              id="nc_quote_due_days"
              required={props.draft.quoteLines.length > 0}
              label={props.t("customers.newConnect.step6.dueDays", {
                defaultValue: "Payment terms",
              })}
              value={props.draft.quoteDueDays}
              onChange={(quoteDueDays) => props.onPatch({ quoteDueDays })}
              placeholder={props.t("customers.newConnect.charges.chooseTerms", {
                defaultValue: "Choose terms",
              })}
              options={paymentTermOptions(props.draft.quoteDueDays, props.t)}
            />
            {/* An EVENT date and never a clock (`BR-TEN-043`, `G6`). */}
            <DatePickerField
              id="nc_quote_posting_date"
              regional
              label={props.t("customers.newConnect.step6.postingDate", {
                defaultValue: "Posting date",
              })}
              value={props.draft.quotePostingDate}
              dateFormat={props.dateFormat}
              onChange={(quotePostingDate) => props.onPatch({ quotePostingDate })}
            />
          </FieldGrid>
        </Panel>

        {/* ══════════════════════════════════════════════════════════════
            PAYMENT — `BR-MET-1187`, `DEF-CUS-7611`
            ══════════════════════════════════════════════════════════════
            ⚠ **THE COMMIT WRITES THE CONNECTION, THE INVOICE AND THE PAYMENT
            IN ONE ACT OR NOTHING AT ALL**, so every box here reaches a real
            row. The PO reported the gap from the deployed build: *"based on
            payment type we nedd to give all paymnet fields"* — a clerk holding
            a cheque at the counter had to key it twice. */}
        <Panel as="section">
          <h4 className="font-heading text-md m-0 mb-1">
            {props.t("customers.newConnect.charges.payment", { defaultValue: "Payment" })}
          </h4>
          <PaymentTaken
            draft={props.draft}
            onPatch={props.onPatch}
            t={props.t}
            dateFormat={props.dateFormat}
            client={props.client}
          />
        </Panel>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          BILLING PREFERENCES — `step4-charges.png`, and the panel is WIRED
          ══════════════════════════════════════════════════════════════════ */}
      <BillingPreferences
        draft={props.draft}
        onPatch={props.onPatch}
        t={props.t}
        dateFormat={props.dateFormat}
        client={props.client}
        tried={props.tried}
      />

    </>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE CONTEXT STRIP lives in the build home since `DEF-GOV-10114`:
// `features/work/buildRecord/BuildContextStrip.tsx` (G93 — a build panel is
// defined ONCE and composed). Imported above.
// ══════════════════════════════════════════════════════════════════════════

// ══════════════════════════════════════════════════════════════════════════
// WHO IS BILLED — one chooser, three options, two refused BY THE SERVER
// ══════════════════════════════════════════════════════════════════════════

/**
 * **WHY EACH PAYER THE SERVER WILL NOT HONOUR IS UNSELECTABLE — ONE PLACE.**
 *
 * ⚠ **THIS IS THE OTHER HALF OF `DEF-CUS-7610`.** The step used to pass
 * `available={false}` as a hardcoded literal at two call sites, so the screen's
 * claim had no tie whatsoever to the rule that makes it true — and each card
 * carried a sentence *stating a fact nobody computed*. The map below names the
 * SERVER's own refusal code per payer, read off `connections._quote_payer`,
 * so the day that function starts honouring one the change is one line here.
 *
 * ⚠ **BOTH REFUSALS ARE UNCONDITIONAL ON THE SERVER AND THAT IS WHY THIS IS A
 * MAP AND NOT A PREDICATE.** `_quote_payer` returns `quote_payer_connection_
 * refused` and `quote_payer_per_unit_not_built` for every build, in every
 * state — they are statements about the PRODUCT, not about this draft — so a
 * per-draft check would be a computation whose answer never changes, which
 * reads as information and is not. **`owner_account` is the one the product
 * can honour**, and its own refusal (`quote_payer_owner_has_no_account`) IS
 * per-build; that one is reported by the commit, on the step the owner was
 * named, and is not this control's to pre-empt.
 *
 * ⚠ **THE THIRD DRAWN OPTION IS ABSENT ON PURPOSE.** `step4-charges.png`'s
 * *Take payment* block draws *"No, the developer pays per unit"*; that restates
 * the PAYER this control already asks and the server refuses that payer by
 * name, so it would be a control that lies (`DEF-CUS-7704`).
 */
const PAYER_REFUSALS: Readonly<Record<QuotePayer, string | null>> = {
  owner_account: null,
  each_unit_first_bill: "quote_payer_per_unit_not_built",
  connection: "quote_payer_connection_refused",
};

function BilledToSelect(props: {
  draft: NewConnectDraft;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  t: Translator;
}) {
  const owner = props.draft.owner.name.trim();
  // ⊕ `DEF-CUS-9228` — a single-family home bills the OWNER's own account
  // (PO 2026-10-02, item 1); every other build bills the master account.
  // ⊕ **`DEF-CUS-10047` — THE WORD FOLLOWS THE CASE.** *Regular account* where
  // the owner's account is a regular one (a single-family type), *Master
  // account* otherwise — `ownerAccountKind`, which also answers for a build
  // that opens none yet, so a disabled option still names the right account.
  // The existing pill word, not a second key with the same English.
  const payerWord =
    ownerAccountKind(props.draft) === "regular"
      ? props.t("customers.account.pill.kind.regular")
      : props.t("customers.newConnect.step6.payerOwner", { defaultValue: "The owner's account" });
  return (
    <SelectField
      id="nc_quote_payer"
      label={props.t("customers.newConnect.step6.billedTo", { defaultValue: "Who is billed" })}
      required
      value={props.draft.quotePayer}
      onChange={(quotePayer) => props.onPatch({ quotePayer: quotePayer as QuotePayer })}
      options={[
        {
          value: "owner_account",
          // `DEF-CUS-9196` — the catalogue word is *Master account* (PO item 28).
          // B14 rule 31 — a NAME, never a database id, and no account NUMBER
          // either: the account does not exist until the last press.
          label: owner === "" ? payerWord : `${payerWord} · ${owner}`,
          // ⊕ `DEF-CUS-9212` / `DEF-CUS-9228` — refused only where Create
          // opens no owner's account at all.
          disabled: PAYER_REFUSALS.owner_account !== null || !buildOpensOwnerAccount(props.draft),
        },
        {
          value: "each_unit_first_bill",
          label: props.t("customers.newConnect.step6.payerUnits", {
            defaultValue: "Each unit's bill",
          }),
          disabled: PAYER_REFUSALS.each_unit_first_bill !== null,
        },
        {
          value: "connection",
          label: props.t("customers.newConnect.step6.payerConnection", {
            defaultValue: "The connection",
          }),
          disabled: PAYER_REFUSALS.connection !== null,
        },
      ]}
    />
  );
}

// ══════════════════════════════════════════════════════════════════════════
// BILLING PREFERENCES — four boxes that REACH THE OWNER'S ACCOUNT
// ══════════════════════════════════════════════════════════════════════════

/**
 * **`step4-charges.png`'s *Billing preferences* panel — Autopay, Tax exempt,
 * Certificate number, Exemption expires.**
 *
 * ⚠ **IT IS WIRED, AND IT WOULD HAVE BEEN FOUR DEAD BOXES IF IT WERE NOT.**
 * `customers.CREATE_FIELDS` has listed `autopay`, `tax_exempt`,
 * `tax_exempt_ref` and `tax_exempt_expires` since the accounts module was
 * built, and New Connect's `create_owner_account` assembled a fixed dict that
 * named none of them — so a preference typed here would have reached the
 * commit and stopped. That is `DEF-CUS-5485` exactly (*"THE THREE COMMIT
 * FIELDS NOBODY SENT"*) and hard-won law 2. `commitPlanOf` sends the four on
 * the owner block and `create_owner_account` forwards them, in this commit.
 *
 * ⚠ **THE TWO BOXES ARE REFUSED WHILE THE TICK IS OFF, WITH THEIR REASON**
 * (`BR-SHL-025`). `tax_exempt_ref` and `tax_exempt_expires` describe an
 * exemption; typed against an account that claims none they would be two
 * values nobody can act on. The drawing says the same thing in its own
 * placeholder — *When exempt* — which is what is used rather than a sentence
 * of ours (B14 rule 33: rationale is ZERO words on screen, and the reason
 * above is in this docstring where it belongs).
 *
 * ⚠ **NOTHING HERE IS PRE-TICKED.** Not electing is the answer every account
 * in the product already carries, and a pre-ticked tax exemption would be this
 * wizard making a tax decision for a utility.
 */
function BillingPreferences(props: {
  draft: NewConnectDraft;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  t: Translator;
  dateFormat: Parameters<typeof DatePickerField>[0]["dateFormat"];
  client?: ApiClient;
  /** Continue was pressed on this step — the two panels show their refusals. */
  tried?: boolean;
}) {
  const { t, draft } = props;
  const client = props.client ?? api;
  // ⊕ lane CF-1 — the plan's own sections (its taxes and discounts), the read
  // step 2's *This plan* block already makes, under the same key.
  const ownerClass = draft.owner.category ?? "";
  const planDetail = useQuery({
    queryKey: ["new-connect", "plan-detail", draft.planApartments, ownerClass],
    queryFn: () => getPlanWithSections(draft.planApartments, ownerClass === "" ? [] : [ownerClass], api),
    enabled: draft.planApartments !== "",
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const sections = planDetail.data?.sections;
  const own = moveInExtrasOwn(draft);
  const setOwn = (next: StepBillingOwn) =>
    props.onPatch({
      moveInExtras: { discountsOn: next.discountsOn, discounts: next.discounts, taxOn: next.taxOn, tax: next.tax },
    });
  const problems = moveInExtrasProblems({ ...draft, moveInExtras: draft.moveInExtras ?? own });
  const comm = draft.communication;
  const prefs: PreferencesValue = {
    paperless: comm.paperlessBill,
    sms_reminders: comm.smsReminders,
    autopay: draft.billing.autopay,
    preferred_language: comm.language,
  };
  // ⊕ lane CF-1 — the tick is the clerk's; a draft from before it reads as
  // ticked when it already holds an answer.
  const prefsOn = draft.prefsOn ?? (prefs.paperless || prefs.sms_reminders || prefs.autopay);
  return (
    <div className="mt-4 flex flex-col gap-6">
      {/* ⊕ **LANE CF-1 (2026-10-18) — MOVE-IN'S DISCOUNTS AND TAX PANELS,
          MOUNTED UNCHANGED** (drawing set `customer-forms-2026-10-18`, image
          02; PO *"this is correct"*). Discounts offers the chosen plan's own
          discounts; Tax offers the exemption types of the plan's taxes, with
          certificate number, issued, expiry and the certificate file. Both
          are sent as Move-in's commit sends them (`ownerMoveInExtras`) and
          written by Move-in's server code on the owner's account
          (`move_in_preferences`, called by `create_owner_account`). */}
      <DiscountsSection
        own={own}
        set={setOwn}
        offered={sections?.discounts ?? []}
        problems={problems}
        tried={props.tried === true}
        t={t}
      />
      <TaxSection
        own={own}
        set={setOwn}
        taxes={sections?.taxes ?? []}
        problems={problems}
        tried={props.tried === true}
        dateFormat={props.dateFormat}
        client={client}
        t={t}
      />

      {/* ⊕ LANE CF-1 — Move-in's *Preferences* panel, Autopay included (a
          payment method can be saved on this account). Step 1's old
          Communication answers live here now, as image 02 draws them. */}
      <PreferencesPanel
        on={prefsOn}
        onTick={(on) =>
          props.onPatch(
            on
              ? { prefsOn: true }
              : {
                  prefsOn: false,
                  communication: { ...comm, paperlessBill: false, smsReminders: false },
                  billing: { ...draft.billing, autopay: false },
                },
          )
        }
        value={prefs}
        onChange={(next) => {
          const out: Partial<NewConnectDraft> = {};
          if (next.paperless !== undefined || next.sms_reminders !== undefined || next.preferred_language !== undefined) {
            out.communication = {
              ...comm,
              ...(next.paperless !== undefined ? { paperlessBill: next.paperless } : {}),
              ...(next.sms_reminders !== undefined ? { smsReminders: next.sms_reminders } : {}),
              ...(next.preferred_language !== undefined ? { language: next.preferred_language } : {}),
            };
          }
          if (next.autopay !== undefined) out.billing = { ...draft.billing, autopay: next.autopay };
          props.onPatch(out);
        }}
        showAutopay
        tickId="nc_prefs_on"
        t={t}
        client={props.client}
      />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// TOTAL · PAID NOW · REMAINING — the footer, and the third is STATED ABSENT
// ══════════════════════════════════════════════════════════════════════════

/**
 * `step4-charges.png`'s footer block, at the right of the `+ Add charge` row.
 *
 * ⚠⚠ **`Remaining` IS DRAWN, IS NOT COMPUTED, AND THAT IS HARD RULE 2 RATHER
 * THAN AN OMISSION.** The drawing prints `$1,035.00 − $500.00 = $535.00`.
 * That subtraction is **money arithmetic in a browser**, which hard rule 2
 * forbids outright and which `DEF-088` and `DEF-127` are the cost of. The row
 * keeps its label and its `due in {terms} days` — the terms are the clerk's own
 * number, not a computation — and **the FIGURE is stated absent**, because a
 * clerk who is shown nothing at all is simply missing a number they were
 * promised. `DEF-CUS-7704` carries the row, and the fix named there is a
 * server figure, never a subtraction moved somewhere quieter.
 *
 * ⚠ **`Total` IS THE ENGINE'S OWN FIGURE FOR THESE LINES** — `POST
 * /connections/quote-preview` over `billing.fee_bill.price_quote_preview`, the
 * same `charge_code_line` the commit will raise. **`Paid now` is the clerk's
 * own string**, unparsed: `MoneyCell` is the one display boundary
 * (`BR-SHL-023`) and it rounds once, exactly as the server's finalization
 * does.
 *
 * ⚠ **NEVER `$0.00` FOR UNKNOWN.** A zero on a money line reads as *free* and
 * the truth is *not priced* — `connection_record._money`'s rule, which every
 * money cell in this wizard follows.
 */
function ChargeTotals(props: {
  draft: NewConnectDraft;
  t: Translator;
  total: string | null;
  currency: string | null;
}) {
  const terms = props.draft.quoteDueDays.trim();
  const paid = props.draft.paymentAmount.trim();
  return (
    <div className="text-right" data-charge-totals="">
      <div className="flex items-baseline justify-end gap-6" data-charge-total="">
        <span className="font-heading text-md">
          {props.t("customers.newConnect.charges.total", { defaultValue: "Total" })}
        </span>
        {props.total === null || props.currency === null ? (
          <span className="text-sm text-neutral-700" data-charge-total-absent="">
            {props.t("customers.newConnect.step6.notPriced", { defaultValue: "Not priced" })}
          </span>
        ) : (
          <MoneyCell amount={props.total} currency={props.currency} basis="priced" />
        )}
      </div>
      <div className="flex items-baseline justify-end gap-6" data-charge-paid="">
        <span className="text-sm text-neutral-700">
          {props.t("customers.newConnect.charges.paidNow", { defaultValue: "Paid now" })}
        </span>
        {paid === "" || props.currency === null ? (
          <span className="text-sm text-neutral-700" data-charge-paid-absent="">
            {props.t("customers.newConnect.step6.nothingTakenYet")}
          </span>
        ) : (
          <MoneyCell amount={paid} currency={props.currency} basis="priced" />
        )}
      </div>
      <div className="flex items-baseline justify-end gap-6" data-charge-remaining="">
        <span className="text-sm text-neutral-700">
          {terms === ""
            ? props.t("customers.newConnect.charges.remaining", { defaultValue: "Remaining" })
            : props.t("customers.newConnect.charges.remainingInDays", {
                days: terms,
                defaultValue: `Remaining, due in ${terms} days`,
              })}
        </span>
        {/* ⛔ **THE FIGURE IS ABSENT AND IS NEVER SUBTRACTED HERE.** See this
            component's own note, hard rule 2 and `DEF-CUS-7704`. */}
        <span className="text-sm text-neutral-700" data-charge-remaining-absent="">
          {props.t("customers.newConnect.step6.outstandingAfter", {
            defaultValue: "Outstanding shows on the build.",
          })}
        </span>
      </div>
    </div>
  );
}

/**
 * **THE COUNTER PAYMENT THE COMMIT TAKES — `BR-MET-1187`, `DEF-CUS-7611`.**
 *
 * ⚠ **A COMPONENT AND NOT 120 LINES INLINE IN THE STEP** (B14 rule 43).
 *
 * ── WHAT THE REDESIGN CHANGED, AND WHY EACH ──────────────────────────────
 * ⚠ **ONE `Payment option` WHERE THERE WERE TWO CONTROLS.**
 * `step4-charges.png` draws a single chooser and names its five options in
 * its own caption: *"No payment now · Cash · Cheque · Card · Bank transfer.
 * The reference label follows the option."* The step had *Take payment* (a
 * yes/no) and *Method* (the tender) side by side, which asks a clerk two
 * questions where the drawing asks one. **The DRAFT still holds both**
 * (`takePayment` and `paymentMethod`) because the WIRE holds both — the
 * server reads `payment_method` and `_payment_taken_at_the_counter` decides
 * on the pair — so this control writes both from one press and clears both
 * together.
 *
 * ⚠ **THE TENDER LIST IS THE TENANT'S OWN AND IS NEVER TYPED HERE**
 * (`BR-PAY-026`). The drawing's four tenders are ILLUSTRATIONS (B14 rule 37);
 * what is offered is `GET /payments` `methods[]` through `methodOptions`, the
 * same reading the S22 Record-a-payment form uses. A hand-typed list hides
 * the tenders a utility added and offers ones the ledger retired, and it
 * fails SILENTLY — `SignupWizard`'s eleventh service in `CLAUDE.md`.
 *
 * ⚠ **`check`, NEVER `cheque` — PO ruling 2026-09-29.** American English. The
 * drawing says *Cheque number*; a ruling beats a drawing, and the LABEL here
 * follows the chosen tender rather than being a constant, which is the
 * drawing's own instruction.
 *
 * ── THE ONE FIELD THAT DECIDES WHETHER THE MONEY EXISTS ────────────────────
 * ⚠ **`Clearing date` IS NOT A CONVENIENCE.** `BR-PAY-021`: a payment with no
 * clearing date is `processing` — the money has not arrived — so
 * `record_payment` allocates it to no bill and posts no ledger pair. Measured
 * on real PostgreSQL while `BR-MET-1187` was built: a payment recorded without
 * it left the build's invoice **`$0.00` settled, with a receipt number on the
 * manifest**. A receipt for money that met nothing.
 *
 * ⚠ **AND IT IS NEVER DEFAULTED, PER TENDER OR OTHERWISE.** There is no rule
 * here that cash clears today and cheques do not. This MIRRORS the S22 form:
 * blank on open, no prefill, and `null` on the wire when it is empty.
 *
 * ── WHAT IS DELIBERATELY NOT DRAWN HERE ────────────────────────────────────
 * ⚠ **NO `Outstanding at activation` FIGURE, AND NO `Remaining` FIGURE.**
 * Both are `Quoted − Taken`, which is **money arithmetic in a browser** —
 * forbidden by hard rule 2 and the exact shape of `DEF-088` and `DEF-127`. The
 * server derives it on the build's own Charges tab the moment the build
 * exists (`connection_record._money`). `DEF-CUS-7704` carries the row.
 *
 * ⚠ **NO THIRD *Take payment* OPTION.** The drawing offers *"No, the developer
 * pays per unit"*, which restates the PAYER the panel beside this one asks and
 * which the server refuses by name (`quote_payer_per_unit_not_built`). A
 * control that lies is worse than an absent one; `DEF-CUS-7704` again.
 */
function PaymentTaken(props: {
  draft: NewConnectDraft;
  onPatch: (next: Partial<NewConnectDraft>) => void;
  t: Translator;
  dateFormat: Parameters<typeof DatePickerField>[0]["dateFormat"];
  client?: ApiClient;
}) {
  const taking = props.draft.takePayment === "deposit";

  // ⚠ **ASKED ALWAYS, NOT ONLY WHILE TAKING.** The chooser IS the tender list
  // now, so a step that fetched it only once a payment was being taken could
  // never draw its own options. One request, cached by `REFERENCE_STALE_MS`.
  const methodsQuery = useQuery({
    queryKey: ["payments", "new-connect-methods"],
    queryFn: () => getPayments({ per: 1 }, props.client ?? api),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const methods = methodsQuery.data?.methods ?? [];

  /** ⚠ **SWITCHING BACK TO *No payment now* CLEARS EVERY BOX.** A hidden field
   *  that keeps its value is a value that posts — `RecordPaymentPage`'s own
   *  rule, and the reason `paymentTakenOf` gates on the same flag that draws
   *  them. The two must never disagree. */
  function choosePaymentOption(next: string): void {
    if (next === "") {
      props.onPatch({
        takePayment: "none",
        paymentMethod: "",
        paymentReference: "",
        paymentAmount: "",
        paymentDate: "",
      });
      return;
    }
    props.onPatch({ takePayment: "deposit", paymentMethod: next });
  }

  return (
    <>
      <FieldGrid columns={2}>
        <SelectField
          id="nc_payment_option"
          label={props.t("customers.newConnect.charges.paymentOption", {
            defaultValue: "Payment option",
          })}
          required
          value={taking ? props.draft.paymentMethod : ""}
          onChange={choosePaymentOption}
          // The leading empty option IS *No payment now* — the drawn default
          // and the ordinary answer, rather than a prompt to choose.
          placeholder={props.t("customers.newConnect.step6.takePaymentNo", {
            defaultValue: "No payment now",
          })}
          options={methodOptions(methods)}
        />
        {/* ⚠ **`numeric` AND NOTHING ELSE — THE BROWSER NEVER PARSES THIS.**
            The clerk's characters travel to the server, which refuses a float
            rather than converting it because *"converting hides the place
            where money became binary"*. Hard rule 2. */}
        <TextField
          id="nc_payment_amount"
          numeric
          label={props.t("customers.newConnect.step6.paymentAmount", {
            defaultValue: "Amount taken",
          })}
          value={props.draft.paymentAmount}
          onChange={(paymentAmount) => props.onPatch({ paymentAmount })}
          disabled={!taking}
          required={taking}
        />
      </FieldGrid>
      <FieldGrid columns={2}>
        {/* ⚠ **THE DRAWN *Payment date*, AND IT IS A SECOND FACT RATHER THAN A
            SECOND COPY OF THE POSTING DATE.** The panel beside this one asks
            when the CHARGE posts; this asks when the MONEY was taken, and
            `CommitPlan.payment_date` has always been a separate key. Left
            blank it is not sent, and the server falls back to the charge's
            posting date — *"they are one event"* (`BR-TEN-043`, `G6`) — which
            is exactly what this wizard did before the box existed, so nothing
            already committed changes meaning. An EVENT date, never a clock. */}
        <DatePickerField
          id="nc_payment_date"
          regional
          label={props.t("customers.newConnect.charges.paymentDate", {
            defaultValue: "Payment date",
          })}
          value={props.draft.paymentDate}
          dateFormat={props.dateFormat}
          onChange={(paymentDate) => props.onPatch({ paymentDate })}
          disabled={!taking}
        />
        {/* ⚠ **THE LABEL FOLLOWS THE OPTION — the drawing's own instruction.**
            *Check number* for a check (`check`, PO ruling 2026-09-29 —
            American English, never `cheque`), and the payments module's own
            *Confirmation* for every other tender, so a clerk reads the same
            word here as on Record a payment. */}
        <TextField
          id="nc_payment_reference"
          label={referenceLabel(props.t, props.draft.paymentMethod)}
          value={props.draft.paymentReference}
          onChange={(paymentReference) => props.onPatch({ paymentReference })}
          disabled={!taking}
        />
      </FieldGrid>
      {/* ⛔ NO *Clearing date* (DEF-CUS-10324, CR-186-BRC10): the payment is
          posted at entry; bank reconciliation clears it. */}
    </>
  );
}

/**
 * **WHAT THE REFERENCE BOX IS CALLED, FOR THE TENDER THAT WAS CHOSEN.**
 *
 * ⚠ **`check`, NEVER `cheque` — PO ruling 2026-09-29, American English.**
 * `step4-charges.png` draws *Cheque number*; a ruling beats a drawing.
 *
 * ⚠ **ONE CODE IS NAMED AND EVERY OTHER TENDER FALLS BACK**, deliberately: the
 * tender list is the tenant's (`BR-PAY-026`) and a map of five labels typed
 * here would be a second catalogue that goes stale the day a utility adds one
 * — `SignupWizard`'s eleventh service. A tender with no special word gets the
 * payments module's own *Confirmation*, which is what a clerk reads on the S22
 * form for the same box.
 */
export function referenceLabel(t: Translator, methodCode: string): string {
  if (methodCode === "check") {
    return String(
      t("customers.newConnect.charges.checkNumber", { defaultValue: "Check number" }),
    );
  }
  return String(t("payments.form.confirmation"));
}

/**
 * **WHAT STEP 6 REFUSES ABOUT THE PAYMENT — asked here and answered at the
 * commit by `_payment_taken_at_the_counter`.**
 *
 * ⚠ **IT MIRRORS TWO SERVER REFUSALS AND INVENTS NOTHING.** The server refuses
 * *"an amount with no tender"* — a guessed tender is a real row on a real
 * deposit — and *"a tender with no amount"*, each by name. Asking here is the
 * `DEF-MET-6110` lesson: a rule refusal reaches the clerk on the step they
 * chose it, not as a 500 after thirty-three acts.
 *
 * ⚠ **IT SAYS NOTHING ABOUT THE CLEARING DATE, DELIBERATELY.** Blank is
 * lawful and is the honest answer for a cheque handed over today
 * (`BR-PAY-021`); refusing it would make the screen demand a date the clerk
 * does not have, and the commit already reports the consequence by name.
 *
 * Returns the message key to show, or `null` when nothing is refused.
 */
export function paymentBlocksContinue(draft: NewConnectDraft): string | null {
  if (draft.takePayment !== "deposit") {
    return null;
  }
  if (draft.paymentMethod === "") {
    return "metering.connection_payment_method_required";
  }
  if (draft.paymentAmount.trim() === "") {
    return "metering.connection_payment_amount_required";
  }
  return null;
}

/**
 * One money cell on a quote line — the SERVER's figure, or nothing.
 *
 * ⚠ **`MoneyCell` IS THE ONE FORMATTING PATH (`BR-SHL-023`) AND IT IS USED
 * HERE RATHER THAN PRINTING THE `display` STRING.** This payload CARRIES the
 * tenant's `CHAR(3)`, so the figure can be labelled properly and is.
 *
 * ⚠ **THE 4-DECIMAL `stored` STRING GOES IN, NOT THE 2-DECIMAL `display`
 * ONE.** `MoneyCell` is the display boundary and rounds once, half-up, exactly
 * as the server's finalization does; handing it an already-rounded figure
 * would round twice for no gain (`DEF-088`).
 *
 * ⚠ **A BLANK WHILE IT IS UNPRICED, NEVER `$0.00` AND NEVER A DASH.** A line
 * the server has not answered for yet shows NOTHING: an em dash is a value
 * (*none*) and on a money line a zero reads as *free*, where the truth is
 * *not priced* (`connection_record._money`'s rule).
 *
 * ⚠ **IT IS A `<span>` AND NO LONGER A `<td>`.** `TableArray` owns the cell
 * now, so a component that emitted its own `<td>` would nest one inside
 * another and the row would render wrong in every browser.
 */
//: Exported for the REVIEW step, which repeats these lines read-only and
//: must print the same server figures through the same cell rather than a
//: second money renderer of its own (B14 rule 43, `DEF-CUS-7911`).
export function QuoteMoney(props: {
  what: string;
  amount: string | null;
  currency: string | null;
}) {
  return (
    <span className="tabular-nums" data-quote-money={props.what}>
      {props.amount === null || props.currency === null ? (
        <span aria-hidden="true" />
      ) : (
        <MoneyCell amount={props.amount} currency={props.currency} />
      )}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-5483 · DEF-CUS-5485 · DEF-BIL-5486 · 05-prototype/02 Accounts
//   Menu Blueprint.pdf p090, read as an image (B14 rule 42)
// generated: 2026-09-16 by the CR-109 step-5/6 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · vitest src/features/customers
// exceptions: the drawn CHARGE/DESCRIPTION/UNIT/AMOUNT columns, the *Quoted*
//   total, *Add a charge*, *Waive a line* and the whole *Payment summary* are
//   NOT built — `DEF-BIL-5486`. Each needs money the server must compute and
//   there is no door that computes it for a build that does not exist yet.
//   Reported rather than approximated in the browser.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
