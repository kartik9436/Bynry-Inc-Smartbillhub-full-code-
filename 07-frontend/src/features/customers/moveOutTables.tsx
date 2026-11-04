// ── Trace ──────────────────────────────────────────────
// Screens:  ACC-06 step 3 (`05-prototype/move-out-acc06-2026-09-24/
//           03-bill-and-deposit.png`) and step 4 (`04-review-and-close.png`),
//           ratified by the PO 2026-09-24: *"this scren drawing are correct -
//           use images to build the screen and all changes that we discussed"*.
// Rules:    B14 rule 43 — **a piece of UI is built as a COMPONENT; standalone
//           code inside a page is not reuse.** `The money` is drawn on BOTH
//           steps and is ONE component mounted twice, which is this file's
//           reason to exist: the wizard it replaces is 2,088 lines and the
//           previous shape drew the same subtraction three times.
//           · rule 44 — the drawing says WHAT is on the screen and how it is
//           arranged; our token scale, spacing and component kit say HOW it is
//           built and win every time. · rule 37 — every figure in those PNGs
//           is an ILLUSTRATION: `$147.21`, `34 kgal`, `$77.66` and `2 × $38.83`
//           tie out so a lane can check its own arithmetic, and not one of them
//           is written down here. · rule 33 — a LABEL ≤ 3 words, a FACT ≤ 6,
//           RATIONALE zero. · rule 31 — no database id is a field's visible
//           value. · rule 21 — Tailwind utilities only, and this file is on
//           `07-frontend/src/styles/route-b-migrated.txt` from its first commit.
// ───────────────────────────────────────────────────────
/**
 * THE TABLES ACC-06 DRAWS, EACH ONE A COMPONENT.
 *
 * ⚠ **WHY A NEW FILE AND NOT MORE OF `moveShared.tsx`.** That file is already
 * 3,500 lines and is shared with the move-IN wizard, which draws none of these.
 * Both files are on the migration ledger, so a Tailwind utility is lawful in
 * either (B14 rule 21); what decides it is that a move-out table has one host
 * and putting it in the shared file invites the move-in to grow a prop for it.
 *
 * ⚠ **AND `MoveOutWizard.tsx` IS NOT ON THE LEDGER, SO IT IS THE ONE PLACE
 * THESE COULD NOT HAVE GONE.** `G31` owns that file and demands every class be
 * declared by a stylesheet; a utility written there is a RED GATE at merge, and
 * the fix is a file on the ledger — never a hand-written stylesheet class,
 * which is what rule 21 forbids.
 */
import type { ReactNode } from "react";

import { Button } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { MoneyCell, formatRate } from "@/components/MoneyCell";
import { formatQuantity } from "@/components/UnitCell";
import type { Translator } from "@/features/tenancy/settingsShared";

import type { AccountRow, UnitRow } from "@/api/endpoints";

import { serviceLabel } from "@/features/assets/assetsShared";

import { Dash } from "./customersShared";
import type { ReadsDraft } from "./moveReadsCapture";
import type { UnitAssetRow } from "./UnitAssetsPanel";
import {
  Absent,
  Figure,
  MoveMatrix,
  PATH_ASKS,
  StepSection,
  finalBillRefusal,
} from "./moveShared";
import type {
  FinalBillPreview,
  MatrixColumn,
  MatrixRow,
  MoneyAmount,
  SettlementMoney,
  ShortfallChoice,
} from "./moveShared";

const NO_AMOUNT: MoneyAmount = { stored: null, display: null };

// ════════════════════════════════════════════════════════════════════════════
// `The money` — ONE COMPONENT, MOUNTED TWICE (steps 3 and 4)
// ════════════════════════════════════════════════════════════════════════════

/**
 * The subtraction, as `03-bill-and-deposit.png` and `04-review-and-close.png`
 * BOTH draw it — **the same component on both, which is the whole point.**
 *
 * ⚠ **IT REPLACES `TheSubtraction`, AND THE SHAPE CHANGED IN ONE WAY WORTH
 * NAMING: the intermediate *Outstanding* row is GONE.** Both drawings list six
 * rows — Prior balance · Final bill, net · Deposit applied · Deposit interest ·
 * Unapplied credit · **Short by** — and no subtotal between them. The served
 * figure is untouched and is still read for the arithmetic; what the drawing
 * drops is the line that restated a sum a clerk can see.
 *
 * ⚠ **TWO RENDERINGS OF ONE CLOSING POSITION IS HOW A RECAP COMES TO DISAGREE
 * WITH THE STEP IT RECAPS.** Step 4 does not copy step 3's figures; it mounts
 * this, reading the same `close-impact`. That was already true of the old step
 * 6 and it is stated again here because the merge doubled the stakes: the
 * review is now the ONLY screen between the clerk and an irreversible close.
 *
 * ⚠ **`Short by` IS THE SUBTRACTION'S OWN BOTTOM LINE, NOT A SEPARATE FACT.**
 * That is the reason old steps 3 and 4 became one step (decision log
 * 2026-09-24), so the row is drawn `strong` and nothing else restates it.
 */
export function TheMoney(props: {
  money: SettlementMoney | null;
  t: Translator;
  /** The drawn heading aside — a bill reference and its period, when one
   *  exists. A FACT at six words or fewer (B14 rule 33), never a sentence. */
  aside?: ReactNode;
}) {
  const { t, money } = props;
  const columns: MatrixColumn[] = [
    { key: "line", label: t("customers.moveOut.money.col.line", { defaultValue: "Line" }) },
    {
      key: "amount",
      label: t("customers.moveOut.finalBill.col.amount", { defaultValue: "Amount" }),
      numeric: true,
    },
  ];
  // ⚠ **NEVER A ZERO IN PLACE OF AN UNREAD FIGURE.** On a final settlement
  // `$0.00` is the claim that this customer owes nothing, which is a different
  // statement from *we could not read it* — `Figure` states the absence.
  const figure = (amount: MoneyAmount, tracks: string, negated?: boolean): ReactNode =>
    money === null ? (
      <Absent tracks={tracks}>
        {t("customers.moveOut.money.notStated", { defaultValue: "Not worked out yet" })}
      </Absent>
    ) : (
      <Figure
        amount={amount}
        currency={money.currency}
        tracks={tracks}
        t={t}
        {...(negated === true ? { negated: true } : {})}
      />
    );
  const rows: MatrixRow[] = [
    {
      key: "prior-balance",
      cells: {
        line: t("customers.moveOut.field.priorBalance", { defaultValue: "Prior balance" }),
        amount: figure(money?.priorBalance ?? NO_AMOUNT, "prior-balance"),
      },
    },
    {
      key: "final-bill-net",
      cells: {
        line: t("customers.moveOut.finalBill.net", { defaultValue: "Final bill, net" }),
        amount: figure(money?.finalBillNet ?? NO_AMOUNT, "final-bill-net"),
      },
    },
    {
      key: "deposit-applied",
      cells: {
        line: t("customers.moveOut.subtraction.depositApplied", {
          defaultValue: "Deposit applied",
        }),
        amount: figure(money?.depositHeld ?? NO_AMOUNT, "deposit-applied", true),
      },
    },
    {
      key: "deposit-interest",
      cells: {
        line: t("customers.moveOut.impact.money.depositInterest", {
          defaultValue: "Deposit interest",
        }),
        // BR-CUS-057 — the accrual engine is not built, so the settlement
        // reports `deposit_interest_not_accrued` and this states the absence
        // rather than printing $0.00. ⚠ The signed arithmetic INCLUDES this
        // term and the error runs against the CUSTOMER; that is a ❄️ FROZEN
        // figure question (decision log 2026-09-19), never a lane's to close.
        amount: figure(money?.depositInterest ?? NO_AMOUNT, "deposit-interest", true),
      },
    },
    {
      key: "unapplied-credit",
      cells: {
        line: t("customers.moveOut.subtraction.unappliedCredit", {
          defaultValue: "Unapplied credit",
        }),
        amount: figure(money?.unappliedCredit ?? NO_AMOUNT, "unapplied-credit", true),
      },
    },
    {
      key: "short-by",
      strong: true,
      cells: {
        line: t("customers.moveOut.subtraction.shortBy", { defaultValue: "Short by" }),
        amount: figure(money?.shortfall ?? NO_AMOUNT, "short-by"),
      },
    },
  ];
  return (
    <StepSection
      tracks="money"
      title={t("customers.moveOut.money.title", { defaultValue: "The money" })}
      {...(props.aside === undefined ? {} : { aside: props.aside })}
    >
      <MoveMatrix columns={columns} rows={rows} tracks="money" />
    </StepSection>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// `The draft bill` — step 3
// ════════════════════════════════════════════════════════════════════════════

/**
 * What the closing window will be billed, priced by the engine and posted
 * nowhere — `03-bill-and-deposit.png`'s bottom panel.
 *
 * ⚠ **THE THREE CLOSING ROWS ARE THE ENGINE'S OWN FIGURES AND ARE NOT SUMMED
 * HERE.** `Subtotal`, `Tax` and `Bill total` come off `final-bill-preview`'s
 * `subtotal`, `tax_total` and `total`. Adding the drawn rows up to reach a
 * subtotal would be customers pricing a bill, which `BR-CUS-037` forbids, and
 * it would drift the moment a proration sat between a line's quantity and its
 * amount — `one_time._line_body` says so in as many words.
 *
 * ⚠ **A TAX LINE IS NOT DRAWN AS A ROW.** The drawing's four rows sum to the
 * Subtotal and the tax is added once beneath, so `kind === "tax"` is filtered
 * out of the body. Drawing it in both places would show a clerk a bill whose
 * lines do not add up to its own subtotal.
 *
 * ⚠ **THE DRAWN `DR-26-0418` AND `Open the bill` ARE DELIBERATELY ABSENT, AND
 * THIS IS THE ONE PLACE THE SCREEN DOES NOT MATCH ITS DRAWING.** There is no
 * bill to open and no number to print: `final-bill-preview` issues nothing —
 * *"no invoice, no invoice line, no journal line, no payment, no ledger entry
 * and no bill number"* — and `core.numbering` spends a number at stage 6,
 * which is not on this path. The PO ruled on 2026-09-24 that the move-out
 * *"should generate draft bill during the process and mark it final once user
 * complete the process"*; that build is **RULED, NOT YET SIZED**. A reference
 * invented here would be a database id on screen (rule 31) or a fiction, and a
 * link would be a control that can never open anything (hard-won law 2's
 * mirror — a live screen behind a dead door). **The period IS served and IS
 * drawn**, and the `DRAFT` chip is true of what this is. When the draft-bill
 * path lands, the reference and the link arrive with it.
 */
export function DraftBill(props: {
  preview: FinalBillPreview | null;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
  /** `DEF-BIL-10052` — *Back to readings*, when values are missing. */
  onBackToReadings?: () => void;
}) {
  const { t, preview } = props;
  const currency = preview?.currency ?? null;
  const columns: MatrixColumn[] = [
    {
      key: "service",
      label: t("customers.moveOut.draftBill.col.service", { defaultValue: "Service" }),
    },
    { key: "line", label: t("customers.moveOut.finalBill.col.line", { defaultValue: "Line" }) },
    {
      key: "period",
      label: t("customers.moveOut.finalBill.col.period", { defaultValue: "Period" }),
    },
    {
      key: "quantity",
      label: t("customers.moveOut.draftBill.col.quantity", { defaultValue: "Quantity" }),
    },
    {
      key: "amount",
      label: t("customers.moveOut.finalBill.col.amount", { defaultValue: "Amount" }),
      numeric: true,
    },
  ];

  const period =
    preview === null || preview.periodStart === null || preview.periodEnd === null ? null : (
      <span className="whitespace-nowrap">
        <DateCell
          value={preview.periodStart}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
        {" — "}
        <DateCell
          value={preview.periodEnd}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
        />
      </span>
    );

  const rows: MatrixRow[] = (preview?.lines ?? [])
    .filter((line) => line.kind !== "tax")
    .map((line, index) => ({
      key: `draft-line-${index}`,
      cells: {
        // B14 rule 31 — the SERVICE CODE is the line's identity and never its
        // visible value. The catalogue names it the way every service badge in
        // the product does; an unknown code falls back to itself rather than
        // rendering blank, because a bill line with no service named is worse
        // than one naming a code a clerk can quote at us.
        service:
          line.service === null ? (
            <Dash />
          ) : (
            // ⚠ **THE PRODUCT'S ONE SERVICE LABEL, NOT A THIRD SPELLING.**
            // `serviceLabel` is `rating.service.*`, which `DEF-763` established
            // as the single label per service code product-wide — it replaced
            // `metering.service.*`, which held six of the ELEVEN codes, so an
            // asset on Storm water or Battery showed a clerk `storm_water`.
            // A `services.*` key of this screen's own invention resolved to
            // nothing and fell through to the raw code, which is a database
            // value where a person should see a name (B14 rule 31).
            serviceLabel(line.service, t)
          ),
        line: line.description ?? <Dash />,
        period: period ?? <Dash />,
        // rule 3 — a quantity NEVER travels or renders without its unit, and
        // the rate rides with it exactly as a printed bill sets it.
        quantity:
          line.quantity === null || line.unit === null ? (
            <Dash />
          ) : (
            <span className="whitespace-nowrap">
              {/* `DEF-BIL-10095` — a COMPUTED quantity (a prorated tier
                  share) reached the screen at 28 places. It shows at most 2,
                  trailing zeros dropped — `193.55 kWh` — through the product's
                  one quantity formatter. Display only; the rate keeps up to 4
                  places and the amount 2. */}
              {`${formatQuantity(line.quantity)} ${line.unit}`}
              {line.unitPrice === null || currency === null ? null : (
                <>
                  {" @ "}
                  {/* A unit PRICE, not an amount (PO 2026-10-02): up to four
                      places — `$0.0425`, never `$0.04`. */}
                  {formatRate(line.unitPrice, currency)}
                </>
              )}
              {line.estimated
                ? ` · ${t("customers.moveOut.finalBill.estimated", { defaultValue: "estimated" })}`
                : null}
            </span>
          ),
        amount:
          line.amount === null || currency === null ? (
            <Dash />
          ) : (
            <MoneyCell amount={line.amount} currency={currency} />
          ),
      },
    }));

  const closing = (
    key: string,
    label: ReactNode,
    amount: string | null,
    strong?: boolean,
  ): MatrixRow => ({
    key,
    ...(strong === true ? { strong: true } : {}),
    cells: {
      service: null,
      line: null,
      period: null,
      quantity: <span className="text-neutral-600">{label}</span>,
      amount:
        amount === null || currency === null ? (
          <Absent tracks={key}>
            {t("customers.moveOut.money.notStated", { defaultValue: "Not worked out yet" })}
          </Absent>
        ) : (
          <MoneyCell amount={amount} currency={currency} />
        ),
    },
  });

  if (rows.length > 0 || preview?.priced === true) {
    rows.push(
      closing(
        "subtotal",
        t("customers.moveOut.draftBill.subtotal", { defaultValue: "Subtotal" }),
        preview?.subtotal ?? null,
      ),
    );
    rows.push(
      closing(
        "tax",
        t("customers.moveOut.draftBill.tax", { defaultValue: "Tax" }),
        preview?.taxTotal ?? null,
      ),
    );
    rows.push(
      closing(
        "bill-total",
        t("customers.moveOut.draftBill.total", { defaultValue: "Bill total" }),
        preview?.total ?? null,
        true,
      ),
    );
  }

  return (
    <StepSection
      tracks="draft-bill"
      title={t("customers.moveOut.draftBill.title", { defaultValue: "The draft bill" })}
      aside={
        <span className="flex flex-wrap items-baseline gap-2">
          <span
            className="bg-neutral-700 px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-bg"
            data-draft-bill-state=""
          >
            {t("customers.moveOut.draftBill.draft", { defaultValue: "Draft" })}
          </span>
          {period}
          {/* ⚠ **A PO-RULED FACT THAT TRAVELLED WITH THE TABLE — `DEF-CUS-5931`,
              PO 2026-09-20, verbatim *"option b is correct"*.** Step 2 asks for
              the closing register and step 4 writes it with the close, so at
              step 3 the closing read does not exist yet and the engine prices
              what the clerk KEYED. A figure priced off an uncommitted read is a
              different claim from one priced off a committed one, and the
              screen says which. Six words — B14 rule 33's cap on a FACT — and
              no rationale beside it. It is a CLAIM ABOUT THIS BILL, so it must
              never be constant: the case below proves it is absent when the
              read is committed. */}
          {props.preview?.fromUncommittedReads === true && (
            <span data-tracks="final-bill-from-keyed-reads">
              {t("customers.moveOut.finalBill.fromKeyedReads", {
                defaultValue: "Priced from reads not yet committed.",
              })}
            </span>
          )}
        </span>
      }
    >
      {rows.length === 0 && preview?.unavailable === "values_missing" ? (
        // ══════════════════════════════════════════════════════════════════
        // `DEF-BIL-10052` (PO 2026-10-11) — *"if you dont get all those values
        // - not just 1 if 2, or 3 or 4 or any number then you should show bill
        // is not genertaed because all these valaues are missing - so that
        // user can understand"*. EVERY missing value, at once, by service and
        // meter number, with a way back to the readings — never the engine's
        // sentence or a rule id.
        // ══════════════════════════════════════════════════════════════════
        <div className="flex flex-col gap-2" data-final-bill-unavailable="values_missing" role="alert">
          <p className="m-0 font-semibold">{t("customers.moveOut.draftBill.notGenerated")}</p>
          <ul className="m-0 flex list-disc flex-col gap-1 pl-5" data-final-bill-missing="">
            {(preview.missing ?? []).map((gap) => (
              <li key={`${gap.service}-${gap.meters.join(",")}`} data-missing-service={gap.service}>
                {t(
                  gap.what === "estimate_no_history"
                    ? "customers.moveOut.draftBill.missing.noHistory"
                    : "customers.moveOut.draftBill.missing.reading",
                  {
                    service: serviceLabel(gap.service, t),
                    meters: gap.meters.length === 0 ? "—" : gap.meters.join(", "),
                  },
                )}
              </li>
            ))}
          </ul>
          {props.onBackToReadings !== undefined && (
            <span>
              <Button variant="secondary" size="sm" data-back-to-readings="" onClick={props.onBackToReadings}>
                {t("customers.moveOut.draftBill.backToReadings")}
              </Button>
            </span>
          )}
        </div>
      ) : rows.length === 0 ? (
        // ⚠ **THE CODE IS A `data-` ATTRIBUTE AND NEVER A WORD ON SCREEN** —
        // B14 rule 32. It is how a lane greps for a refusal that reached a
        // clerk as silence; what a clerk READS is the engine's own sentence.
        <span data-final-bill-unavailable={preview?.unavailable ?? ""}>
          <Absent tracks="draft-bill">
          {/* ⚠ The SERVER'S OWN sentence, quoted, never paraphrased into a
              catalogue key — `DEF-CUS-6464`. It is the ACTIONABLE half: it
              names the charge code and the size a clerk can go and price. A
              paraphrase here is a second copy of an engine message, free to
              drift from the engine. */}
          {/* ⚠ AMENDED BY `DEF-RAT-7991` — the server's sentence unless it
              carries a database uuid, which nine of the rating chain's raise
              sites put there (B14 rule 31). */}
          {finalBillRefusal(preview ?? null, t) ??
            t("customers.moveOut.draftBill.notPriced", {
              defaultValue: "The closing period is not priced.",
            })}
          </Absent>
          {/* `DEF-BIL-10052` follow-up — every unpriced draft offers the way
              back, not only the missing-values one. */}
          {props.onBackToReadings !== undefined && preview?.priced === false && (
            <span className="ml-2">
              <Button variant="secondary" size="sm" data-back-to-readings="" onClick={props.onBackToReadings}>
                {t("customers.moveOut.draftBill.backToReadings")}
              </Button>
            </span>
          )}
        </span>
      ) : (
        <MoveMatrix columns={columns} rows={rows} tracks="draft-bill" />
      )}
    </StepSection>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// `What to do with the shortfall` — step 3, and it is a MONEY DECISION
// ════════════════════════════════════════════════════════════════════════════

/**
 * The paths, as `03-bill-and-deposit.png` draws them: a table with a pick
 * per row, and **the picked row opens its fields in place**.
 *
 * ⚠ **THREE ROWS, NOT THE DRAWING'S FOUR — PO RULING 2026-10-12** (decision
 * log, *"MOVE-OUT DOES NOT WRITE OFF"*): *"we will not write off at the time
 * of move out; these charges remain outstanding on the account and followup
 * is done as per outstanding rules"*. *Write it off* is gone; the server no
 * longer offers it and refuses it by name. The balance is chased
 * (BR-CUS-082), and Finance or a System Admin writes it off later in
 * Payments. The rows are the server's, so nothing here lists them.
 *
 * ⚠ **THE NAMES ARE THE DRAWING'S AND THEY BREAK B14 RULE 33 BY RULING.**
 * *Pursue it* · *Put it on a payment plan* · *Tie it back to the master
 * account* — 5 and 7 words against a 3-word cap on a label. The PO was shown
 * the shortened set (*Pursue · Payment plan · Write off · To master account*)
 * and ruled ***"b) Leave as drawn"*** (2026-09-24). **A later copy audit must
 * not "fix" these.** The supersession is NARROW: these labels on this screen
 * and nothing else.
 *
 * ⚠⚠ **WHAT EACH PATH *NEEDS* IS STATED AND NOT YET COLLECTED, AND THAT IS
 * DELIBERATE — `DEF-CUS-6501`.** `POST /accounts/{id}/settle-shortfall` reads
 * exactly three things off the body: `path`, `final_bill` and `as_of`
 * (`api._settlement_payload` → `move_out_settlement.shortfall_decision`). A
 * forwarding address, a transfer reason and the payment plan's own terms are
 * read by **nothing**: the door spreads the
 * payload and the service names three keys, so anything else arrives and is
 * dropped while the POST answers 200. Rendering those as live inputs is
 * `DEF-CUS-6487` exactly — seven columns over a door that discarded every row
 * while reporting success — and on a money path, where the cost is a clerk
 * believing a payment plan exists.
 *
 * **So the *What it needs* column STATES what each path needs, for every row,
 * picked or not**, which is what the drawing's own unpicked rows do and what
 * this screen can honestly offer today. The plan's three boxes are drawn on the
 * picked row and are **held**, with `moveOutTables.dom.test.tsx`'s
 * hold-expiry case asserting they stay held while the door names three keys —
 * so the day `settle-shortfall` carries the terms, the suite goes RED and names
 * this component (hard-won law 2: when you write a hold, write the test that
 * fires when the hold expires, in the same commit).
 */
export function ShortfallPaths(props: {
  choices: readonly ShortfallChoice[];
  chosen: string | null;
  onChoose: (path: string) => void;
  onConfirm: () => void;
  confirming: boolean;
  t: Translator;
}) {
  const { t } = props;
  const columns: MatrixColumn[] = [
    { key: "pick", label: "" },
    { key: "path", label: t("customers.moveOut.paths.col.path", { defaultValue: "Path" }) },
    { key: "who", label: t("customers.moveOut.pathAsk.col.who", { defaultValue: "Who can" }) },
    {
      key: "needs",
      label: t("customers.moveOut.paths.col.needs", { defaultValue: "What it needs" }),
    },
  ];
  // ⚠ **DERIVED FROM THE OFFERED PATHS, so a fifth path the server adds shows
  // up here without an edit** — and an unknown one states its absence rather
  // than rendering a blank row. Never a hand-typed list (CLAUDE.md law 2's
  // eleventh service, which the sign-up screen simply never offered).
  const rows: MatrixRow[] = props.choices.map((choice) => {
    const ask = PATH_ASKS[choice.path];
    return {
      key: choice.path,
      cells: {
        pick: (
          <input
            type="radio"
            name="shortfall-path"
            value={choice.path}
            checked={props.chosen === choice.path}
            disabled={choice.blockedReason !== null}
            onChange={() => props.onChoose(choice.path)}
            aria-label={choice.label}
            data-shortfall-pick={choice.path}
          />
        ),
        path: (
          <span
            className={props.chosen === choice.path ? "font-semibold text-text" : "text-text"}
            data-shortfall-path={choice.path}
          >
            {choice.label}
          </span>
        ),
        who:
          ask === undefined ? (
            <Dash />
          ) : (
            <span className="text-neutral-700">
              {t("customers.moveOut.pathAsk.anyClerk", { defaultValue: "Any clerk" })}
            </span>
          ),
        needs: (
          <span className="text-neutral-600" data-shortfall-needs={choice.path}>
            {choice.blockedReason ??
              (ask === undefined ? (
                <Absent tracks={choice.path}>
                  {t("customers.moveOut.pathAsk.unknown", { defaultValue: "Not stated here." })}
                </Absent>
              ) : (
                t(ask.fields.key, { defaultValue: ask.fields.en })
              ))}
          </span>
        ),
      },
    };
  });
  return (
    <StepSection
      tracks="shortfall-paths"
      title={t("customers.moveOut.paths.title", {
        defaultValue: "What to do with the shortfall",
      })}
    >
      <MoveMatrix columns={columns} rows={rows} tracks="shortfall-paths" />
      {/* B14 rule 6 — this is a COMMIT of a money decision and not a
          destruction, so it is the primary tier. The danger tier is for
          destroying something; tying a debt back creates a record. */}
      <button
        type="button"
        className="mt-4 bg-accent px-3 py-1.5 text-sm font-semibold text-bg disabled:opacity-50"
        data-shortfall-confirm=""
        disabled={props.chosen === null || props.confirming}
        onClick={props.onConfirm}
      >
        {t("customers.moveOut.shortfall.confirm", { defaultValue: "Record this decision" })}
      </button>
    </StepSection>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// `The meters` — step 4, READ-ONLY
// ════════════════════════════════════════════════════════════════════════════

/**
 * What was read and what was not, as `04-review-and-close.png` draws it:
 * *Asset no · Type · Service · Closing reading · Read date · Estimate*, with
 * every value read back rather than typed.
 *
 * ⚠ **AN UNREAD REGISTER STATES ITSELF AND IS NEVER A BLANK ROW.** The drawing
 * shows three fire lines reading *Not read* beside a water meter reading
 * `1,943 kgal` — a fire line has no register to read, so *Not read* is the
 * true answer and an empty cell would read as a reading we lost.
 */
export function ClosingMeters(props: {
  /** The SAME rows step 2's reading table lists — `readableAssets(unitAssets)`,
   *  the unit's own registers. Not `detail.meters`, which is
   *  `AccountMeterRef` — an id, an asset number and a qualifier, and neither a
   *  TYPE nor a SERVICE. The drawing asks for both columns, and reading them
   *  off a second source is how a review comes to list different meters from
   *  the step it recaps. */
  assets: readonly UnitAssetRow[];
  /** Keyed by ASSET ID, exactly as step 2 keyed it — *"so two meters with the
   *  same number cannot collide"*. */
  reads: ReadsDraft;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** The move-out day, which is what an untouched row's read date MEANS: the
   *  server fills an absent `read_at` with the flow's own event date, so a row
   *  a clerk did not date is dated this, not undated. */
  movedOutOn: string;
  t: Translator;
}) {
  const { t } = props;
  const columns: MatrixColumn[] = [
    { key: "asset", label: t("customers.moveOut.meters.col.asset", { defaultValue: "Asset no" }) },
    { key: "type", label: t("customers.moveOut.meters.col.type", { defaultValue: "Type" }) },
    {
      key: "service",
      label: t("customers.moveOut.meters.col.service", { defaultValue: "Service" }),
    },
    {
      key: "reading",
      label: t("customers.moveOut.meters.col.closing", { defaultValue: "Closing reading" }),
      numeric: true,
    },
    {
      key: "readOn",
      label: t("customers.moveOut.meters.col.readDate", { defaultValue: "Read date" }),
    },
    {
      key: "estimate",
      label: t("customers.moveOut.meters.col.estimate", { defaultValue: "Estimate" }),
    },
  ];
  const rows: MatrixRow[] = props.assets.map((asset) => {
    const keyed = props.reads[asset.id];
    const read = keyed !== undefined && keyed.value.trim() !== "";
    const readAt = keyed === undefined || keyed.readAt === "" ? props.movedOutOn : keyed.readAt;
    return {
      key: asset.id,
      cells: {
        // B14 rule 31 — the ASSET NUMBER a clerk reads off the meter, never
        // the row's id, which is what keys this map.
        asset:
          asset.asset_no === null ? (
            <Dash />
          ) : (
            <span className="font-semibold">{asset.asset_no}</span>
          ),
        // The server's own `type_name`, not the code beside it (rule 31).
        type: asset.type_name ?? asset.type ?? <Dash />,
        service:
          asset.service === null ? (
            <Dash />
          ) : (
            serviceLabel(asset.service, t)
          ),
        // ⚠ **`Not read` IS THE TRUE ANSWER AND A BLANK CELL IS NOT.** The
        // drawing shows three fire lines reading *Not read* beside a water
        // meter at `1,943 kgal` — a fire line has no register to read, so an
        // empty cell would read as a reading we lost.
        reading: read ? (
          <span className="tabular-nums">{keyed!.value}</span>
        ) : (
          <Absent tracks="closing-read">
            {t("customers.moveOut.meters.notRead", { defaultValue: "Not read" })}
          </Absent>
        ),
        readOn:
          read && readAt !== "" ? (
            <DateCell value={readAt} timeZone={props.timeZone} dateFormat={props.dateFormat} />
          ) : (
            <Dash />
          ),
        estimate: !read ? (
          <Dash />
        ) : keyed!.estimate ? (
          t("common.yes", { defaultValue: "Yes" })
        ) : (
          t("common.no", { defaultValue: "No" })
        ),
      },
    };
  });
  return (
    <StepSection
      tracks="closing-meters"
      title={t("customers.moveOut.impact.meters.title", { defaultValue: "The meters" })}
    >
      {rows.length === 0 ? (
        <Absent tracks="closing-meters">
          {t("customers.moveOut.impact.meters.none", { defaultValue: "None on this account." })}
        </Absent>
      ) : (
        <MoveMatrix columns={columns} rows={rows} tracks="closing-meters" />
      )}
    </StepSection>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// MASTER ACCOUNTS — `01M-find-account-master.png` · `02M-date-and-reads-master.png`
// ════════════════════════════════════════════════════════════════════════════

/**
 * `Accounts on this master` — step 1, a MASTER only.
 *
 * ⚠ **THE `Close` LINK OPENS THIS SAME WIZARD ON THAT TENANT, WHICH IS THE
 * WHOLE OF WHAT THE REFUSAL ASKS FOR.** The PO ruled the master's refusal
 * ***"(b) Refuse until they're closed"*** (2026-09-24), and the act that clears
 * it is *close the tenant's account* — this wizard, once per tenant. A link
 * naming an act the product does not have is what the FIRST draft of that
 * ruling contained (*"move them to another master"*), and no column links a
 * tenant to a master: `sub_accounts_for_master` derives them from the premises'
 * declared ownership, so children follow the BUILDING.
 */
export function AccountsOnThisMaster(props: {
  /** The SAME rows the Master-accounts tab lists — `getAccounts({ filters: {
   *  premises_id } })`. ⚠ **NOT `detail.sub_accounts`**, which carries
   *  `{id, account_no, unit_id}` and THREE of the drawn table's six columns:
   *  no customer, no status, no balance. Mounting the drawn table over that
   *  payload is `DEF-CUS-6487`'s shape on a READ — a table asking for more
   *  than its door serves, rendering three empty columns and reporting
   *  success. This read already serves all six and is already proved. */
  rows: readonly AccountRow[];
  /** This master's OWN id, so it is not listed among its own tenants —
   *  `sub_accounts_for_master` excludes it server-side for the same reason. */
  selfId: string;
  closeHref: (accountId: string) => string;
  t: Translator;
}) {
  const { t } = props;
  const columns: MatrixColumn[] = [
    {
      key: "account",
      label: t("customers.moveOut.master.col.account", { defaultValue: "Account" }),
    },
    {
      key: "customer",
      label: t("customers.moveOut.master.col.customer", { defaultValue: "Customer" }),
    },
    { key: "unit", label: t("customers.moveOut.field.unit", { defaultValue: "Unit" }) },
    {
      key: "status",
      label: t("customers.moveOut.master.col.status", { defaultValue: "Status" }),
    },
    {
      key: "balance",
      label: t("customers.moveOut.field.balance", { defaultValue: "Balance" }),
      numeric: true,
    },
    { key: "close", label: "", numeric: true },
  ];
  const rows: MatrixRow[] = props.rows
    .filter((row) => row.id !== props.selfId)
    .map((row) => ({
      key: row.id,
      cells: {
        // B14 rule 31 — the ACCOUNT NUMBER, never the uuid behind the link.
        account: (
          <span className="font-semibold">
            {row.account_no ?? <Dash>{t("customers.account.noNumber")}</Dash>}
          </span>
        ),
        customer: row.name ?? <Dash />,
        unit: row.unit_label ?? <Dash />,
        status:
          (row.status ?? "") === "" ? (
            <Dash />
          ) : (
            t(`customers.account.status.${row.status}`, { defaultValue: row.status })
          ),
        balance:
          (row.balance ?? null) === null ? (
            <Dash />
          ) : (
            <MoneyCell amount={String(row.balance)} currency={row.currency ?? "USD"} />
          ),
        // ⚠ **THE LINK NAMES AN ACT THE PRODUCT HAS: THIS WIZARD, ONCE PER
        // TENANT.** The PO ruled the refusal ***"(b) Refuse until they're
        // closed"***, and the FIRST draft of that ruling said *"move them to
        // another master"* — which no column and no endpoint in this product
        // can do, because `sub_accounts_for_master` derives children from the
        // premises' declared ownership and children follow the BUILDING. A
        // refusal instructing a clerk to do something the product cannot do is
        // hard-won law 2's mirror.
        close: (
          <a
            className="text-accent underline"
            href={props.closeHref(row.id)}
            data-master-close={row.id}
          >
            {t("customers.moveOut.master.close", { defaultValue: "Close" })}
          </a>
        ),
      },
    }));
  return (
    <StepSection
      tracks="master-accounts"
      title={t("customers.moveOut.master.accounts", { defaultValue: "Accounts on this master" })}
    >
      {rows.length === 0 ? (
        <Absent tracks="master-accounts">
          {t("customers.moveOut.master.noAccounts", {
            defaultValue: "No accounts on this master.",
          })}
        </Absent>
      ) : (
        <MoveMatrix columns={columns} rows={rows} tracks="master-accounts" />
      )}
    </StepSection>
  );
}

/**
 * `Units on this master` — step 2, a MASTER only, and every column is READ.
 *
 * ⚠ **THE STATE COLUMN NAMES A STATE THE PRODUCT ALREADY KEEPS**, which is what
 * the PO's ruling asked for: *"you will ahve to show all units that are tagged
 * to master account - we have unit states to be used for it"* (2026-09-24).
 * Occupied · Vacant · Sub-metered is the Units list's own occupancy filter, so
 * nothing new is invented and nothing is re-derived here.
 *
 * ⚠ **`Bills here` IS REAL MONEY AND IS HALF THE REFUSAL.** An empty flat is not
 * neutral — `base_charge_only_coverage` puts every unit with no occupying
 * account onto the owner's bill, so it is a live monthly charge with nowhere to
 * go, and a master cannot close while one still bills to it (PO: *"its not
 * allowed - refule the move out"*). A unit whose tenant pays their own bill
 * states a dash, because nothing bills here for it.
 */
export function UnitsOnThisMaster(props: {
  /** The SAME rows the Units list serves — `getUnits({ filters: { premises_id
   *  } })`. `occupancy` is its own filter's vocabulary (Occupied · Vacant ·
   *  Sub-metered), which is exactly what the PO meant by *"we have unit states
   *  to be used for it"*: nothing new is invented and nothing re-derived. */
  rows: readonly UnitRow[];
  /** What each EMPTY unit bills to this master every month, keyed by unit id —
   *  `close-impact`'s `vacant_base_charges`, summed. Absent for a unit someone
   *  occupies, because nothing bills here for it. */
  billsHere: (unit: UnitRow) => { amount: string; currency: string } | null;
  t: Translator;
}) {
  const { t } = props;
  const columns: MatrixColumn[] = [
    { key: "unit", label: t("customers.moveOut.field.unit", { defaultValue: "Unit" }) },
    { key: "label", label: t("customers.moveOut.master.col.label", { defaultValue: "Label" }) },
    { key: "state", label: t("customers.moveOut.master.col.state", { defaultValue: "State" }) },
    {
      key: "account",
      label: t("customers.moveOut.master.col.account", { defaultValue: "Account" }),
    },
    {
      key: "bills",
      label: t("customers.moveOut.master.col.billsHere", { defaultValue: "Bills here" }),
      numeric: true,
    },
  ];
  const rows: MatrixRow[] = props.rows.map((row) => {
    const bills = props.billsHere(row);
    return {
      key: row.id,
      cells: {
        unit: <span className="font-semibold">{row.unit_no ?? <Dash />}</span>,
        label: row.label ?? <Dash />,
        // ⚠ **THE PRODUCT'S EXISTING OCCUPANCY VOCABULARY, NOT A NEW ONE.**
        // `metering.occupancy.*` is what the Units list prints and is in all
        // eleven catalogues; a `units.occupancy.*` key of this screen's own
        // invention resolved to NOTHING and fell through to the raw code, so
        // the column read `occupied` and `vacant` in lower case — a database
        // value where a person should see a name (B14 rule 31). Found in a
        // browser. `sub_metered` is the list's THIRD state and is a flag
        // beside the occupancy rather than a value of it, so it is read from
        // the row's own flag and named here.
        state:
          (row.occupancy ?? "") === "" ? (
            <Dash />
          ) : row.sub_metered === true ? (
            t("metering.units.occupancyFilter.sub_metered", { defaultValue: "Sub-metered" })
          ) : (
            t(`metering.occupancy.${row.occupancy}`, { defaultValue: row.occupancy })
          ),
        // ⚠ **`None` IS A FACT AND NOT A BLANK.** An empty flat with no account
        // is precisely the case that stops a master closing, so the cell has
        // to say so rather than leave a gap a clerk reads as *not looked up*.
        account:
          (row.account_no ?? "") === "" ? (
            <Absent tracks="master-unit-account">
              {t("customers.moveOut.master.noAccount", { defaultValue: "None" })}
            </Absent>
          ) : (
            [row.account_no, row.occupant].filter((part) => (part ?? "") !== "").join(" · ")
          ),
        bills:
          bills === null ? (
            <Dash />
          ) : (
            <MoneyCell amount={bills.amount} currency={bills.currency} />
          ),
      },
    };
  });
  return (
    <StepSection
      tracks="master-units"
      title={t("customers.moveOut.master.units", { defaultValue: "Units on this master" })}
    >
      {rows.length === 0 ? (
        <Absent tracks="master-units">
          {t("customers.moveOut.master.noUnits", { defaultValue: "No units on this master." })}
        </Absent>
      ) : (
        <MoveMatrix columns={columns} rows={rows} tracks="master-units" />
      )}
    </StepSection>
  );
}

/**
 * **THE MASTER'S REFUSAL — `01M-find-account-master.png`, and BOTH conditions.**
 *
 * ⚠ **THE PO RULED *REFUSE* TWICE, IN TWO DIFFERENT WORKED CASES, AND A LANE
 * MAY NOT SOFTEN IT INTO A WARNING.**
 * * *"(b) Refuse until they're closed"* — a master with any ACTIVE tenant.
 *   Closing the owner's account while tenants are still on supply leaves them
 *   billing against a closed account.
 * * *"its not allowed - refule the move out"* — a master any EMPTY unit still
 *   bills to. An empty flat is not neutral: `base_charge_only_coverage` puts
 *   every unit with no occupying account onto the owner's bill, so it is a
 *   live monthly charge with nowhere to go.
 *
 * ⚠ **WITH NEITHER, IT CONTINUES EXACTLY AS A REGULAR ACCOUNT.** A master
 * move-out is not a special flow — it is the ordinary flow with one gate at
 * the front (PO: *"if master account dont have any active child acounts in
 * that case - go to next step"*).
 *
 * ⚠ **A CONSEQUENCE, STATED SO NOBODY DISCOVERS IT LATER:** a landlord SELLING
 * a building with tenants in place cannot use the move-out at all. That case
 * is the TRANSFER flow, which already keeps the deposit and the history where
 * they are. A building EMPTYING closes here; a building CHANGING HANDS
 * transfers.
 *
 * The sentence names the two COUNTS and the table below shows which — B14 rule
 * 33 caps an instruction at six words per sentence, and two sentences of six
 * beat one of twelve.
 */
export function MasterCannotClose(props: {
  activeTenants: number;
  unitsStillBilling: number;
  t: Translator;
}) {
  const { t } = props;
  if (props.activeTenants === 0 && props.unitsStillBilling === 0) {
    return null;
  }
  return (
    <div
      role="alert"
      className="mt-4 border-l-4 border-danger-500 bg-danger-100 p-4"
      data-master-refusal=""
    >
      <p className="m-0 font-heading text-base font-semibold text-danger-700">
        {t("customers.moveOut.master.refusedTitle", {
          defaultValue: "This account cannot be closed.",
        })}
      </p>
      <p className="m-0 mt-1 text-sm text-danger-700">
        {[
          props.activeTenants > 0
            ? t("customers.moveOut.master.refusedTenants", {
                count: props.activeTenants,
                defaultValue: "{{count}} tenants are still open.",
              })
            : null,
          props.unitsStillBilling > 0
            ? t("customers.moveOut.master.refusedUnits", {
                count: props.unitsStillBilling,
                defaultValue: "{{count}} empty units still bill here.",
              })
            : null,
          t("customers.moveOut.master.refusedAct", { defaultValue: "Close them first." }),
        ]
          .filter((part) => part !== null)
          .join(" ")}
      </p>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: ACC-06 four-step rebuild · decision log 2026-09-24 (the four-step
//         shape · the draft-bill ruling · the five master-account rulings · the
//         six ratified drawings · B14 rule 44)
// generated: 2026-09-24 by lane MOVEOUT-SHAPE
// gates: tsc✔ eslint✔ vitest✔ · this file is on `route-b-migrated.txt`, so
//        `routeBUtilities.test.ts` owns it and G31 skips it
// exceptions: E3 no money figure is rendered from a literal anywhere in this
//   file — every drawn figure in the six PNGs is an illustration (B14 rule 37)
//   and not one of them appears here · E3 `DraftBill` deliberately draws
//   neither the drawn bill reference nor `Open the bill`: there is no bill and
//   no number until the draft-bill path is built, and a dead link is worse than
//   an absent one (hard-won law 2's mirror) · E3 `ShortfallPaths` STATES what
//   each path needs and collects none of it — `settle-shortfall` reads three
//   keys and drops the rest (`DEF-CUS-6501`)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
