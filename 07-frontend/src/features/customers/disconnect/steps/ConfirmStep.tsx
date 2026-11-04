// ── Trace ──────────────────────────────────────────
// Change:   the DISCONNECT WIZARD REBUILD of 2026-09-25 — **STEP 4 OF FOUR,
//           `Confirm`**, built from `Step4Confirm.png` and `MasterStep4.png` AS
//           IMAGES (B14 rule 42). It is the old step 4 and the old step 5, one
//           screen.
// Rules:    **BR-BIL-007** (fees are the tenant's own charge codes, NEVER
//           hardcoded) · **BR-CUS-103** (base and standing charges STOP at the
//           cut) · **BR-CUS-104** (the fee lands AT THE CUT — its TIMING half,
//           which `BR-CUS-1097` did not touch) · **BR-CUS-105** (a cut
//           account's balance is STATIC) · **BR-CUS-1100** (the block marks the
//           ACCOUNT and the CUSTOMER, never the address) · **BR-CUS-1098**
//           (fees are priced ONCE for the building; the owner pays) ·
//           hard rules 2 and 5 · B14 rules 20, 21, 31, 32, 33, 37, 43, 44
// Tests:    ../../DisconnectWizard.test.tsx
// ─────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · NOT ONE FEE FIGURE IS A LITERAL — B14 RULE 37 AND `BR-BIL-007`
// ══════════════════════════════════════════════════════════════════════════
// The drawings price the three fees **$35.00 · $75.00 · $45.00** on the regular
// variant and **$85.00 · $150.00 · $45.00** on the master. **Every one of those
// six is an ILLUSTRATION** (B14 rule 37: *a figure drawn in a wireframe is an
// illustration, never a fact to build to*), and `BR-BIL-007` makes the amount
// the TENANT's own charge-code row. This file renders `terms.fees[].amount` and
// contains no number.
//
// ⚠ **A ROW WITH NO AMOUNT STATES ITS ABSENCE AND NEVER A ZERO.** Measured on
// 2026-09-20, all three codes resolve on no tenant in this tree, so this is the
// COMMON case rather than an edge one. `$0.00` and *the tenant has not priced
// this* are different claims and only one of them is true.
//
// ⚠ **AND `CHARGED?` IS THE COLUMN THAT STOPS THE TABLE LYING.** The cut raises
// the reconnection fee and nothing else; the other two codes exist as names
// with no path to a bill. Three amounts listed with no such distinction read as
// three fees a customer is about to owe.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · ⛔ THE DEPOSIT DOES NOT MOVE, SO THE SCREEN DOES NOT SUBTRACT IT
// ══════════════════════════════════════════════════════════════════════════
// **`DEF-CUS-6753`.** Both drawings put a `Deposit applied − $65.00` row above
// `To clear before reconnection`. **`disconnects._to_clear` is `arrears + fee`
// and subtracts nothing**, and it cannot: applying a deposit against an arrear
// is a balance-sheet posting and **hard rule 5 leaves every journal line to the
// ledger posting service**. `DEPOSIT_APPLICATION_NOT_POSTED` says so in the
// module's own words.
//
// **So the subtraction row is NOT drawn.** Rendering it would quote a customer a
// figure nothing computes, two inches from the figure `mark_reconnecting`
// actually reads — and it is the customer-facing half of the money, on the
// screen that takes their water away.
//
// **THE CONTROL STAYS AND THE CLAIM GOES, AND THE SPLIT IS THE POINT (item
// 3.10).** *Apply it against the arrear* is a real, stored ELECTION:
// `schedule_cut` takes `deposit`, `commit_cut` records it, and
// `reconnection_terms` reads it back to answer whether a new deposit is needed
// to reconnect. It is not a dead control. What was dead was the ARITHMETIC
// beside it, and that is what is gone.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · THE FEES ARE NOT PRICED BY PLAN, AND THE PANEL DOES NOT SAY THEY ARE
// ══════════════════════════════════════════════════════════════════════════
// **`DEF-CUS-6752`.** The drawing labels the panel *Residential · Standard
// plan* and gives every row a `FROM` of *Standard plan · Residential*.
// `_fee_table()` asks `_charge_code(code)` against the TENANT's one catalogue —
// no plan, no category — so a residential and a commercial account are quoted
// the same figure.
//
// **What is drawn here instead:** the account's own plan and category, beside
// the panel, **as a fact about the ACCOUNT**. That is true — `unit_plan` is
// served and `account_type` is the platform category — and it is the fact a
// clerk wants. The `FROM` column says where the figure ACTUALLY came from,
// which is the tenant's catalogue. **Nothing on screen claims a plan priced a
// fee that plan did not price.** The backend half is lane CUTPATH's.
import { MoneyCell } from "@/components/MoneyCell";
import { Panel } from "@/components/Panel";
import { RecapBox } from "@/components/RecapBox";
import { SelectField } from "@/components/FormModal";
import { WarningBox } from "@/components/WarningBox";
import type { AccountDetail } from "@/api/endpoints";
import { serviceLabel } from "@/features/assets/assetsShared";
import type { ApiClient } from "@/api/client";

import { accountCategoryName, useAccountCategories } from "../../customersShared";

import { DisconnectFacts } from "../DisconnectFacts";
import type { DisconnectFact } from "../DisconnectFacts";
import { DisconnectTableArray } from "../DisconnectTableArray";
import type { DisconnectArrayColumn } from "../DisconnectTableArray";
import { servicesCut, workOrderCount } from "../disconnectDraft";
import type { DisconnectDraft, DisconnectVisitRow } from "../disconnectDraft";
import type { DisconnectFeeRow, DisconnectTerms } from "../disconnectTerms";
import { DEPOSIT_DISPOSITIONS } from "../../transferDisconnectShared";
import type { DepositDisposition, Translator } from "../../transferDisconnectShared";

export interface ConfirmStepProps {
  draft: DisconnectDraft;
  account: AccountDetail | null;
  onPatch: (next: Partial<DisconnectDraft>) => void;
  t: Translator;
  /** `GET /accounts/{id}/reconnection-terms`, or `null` while it has not
   *  answered. */
  terms: DisconnectTerms | null;
  master: boolean;
  occupants: number | null;
  /** Which protections the check step found in force, for the one warning line. */
  protectionsInForce: readonly string[];
  /** `true` when no proof of certified service is recorded — `BR-CUS-1099`. */
  proofMissing: boolean;
  /** The test seam the wizard already carries; the category names are the
   *  TENANT's own rows and this is how they are read (see `PlanAndCategory`). */
  client?: ApiClient;
}

export function ConfirmStep(props: ConfirmStepProps) {
  const t = props.t;
  const account = props.account;
  const terms = props.terms;
  const cut = servicesCut(props.draft);
  // ⚠ **THE CATEGORY'S NAME IS THE TENANT'S OWN ROW, NOT THE CODE — B14 rule
  // 32, and it rendered as the code until it was read in a browser.** The Fees
  // panel printed *"commercial · Sample — Residential"*: `account_type` is a
  // platform category CODE and a clerk was being shown it raw, lower-case,
  // beside a proper name. `accountCategoryName` resolves it against the rows
  // the account screens already read, and falls back to the code only when the
  // lookup itself could not answer — which is an absence, not a label.
  const categories = useAccountCategories(props.client);

  const facts: DisconnectFact[] = [
    {
      id: "account",
      label: t("customers.disconnect.confirm.factAccount", { defaultValue: "Account" }),
      // ⚠ **THE ACCOUNT NUMBER, NEVER THE ACCOUNT ID** — B14 rule 31.
      value: account === null ? "—" : `${account.account_no ?? "—"} · ${account.name ?? ""}`,
    },
    {
      id: "address",
      label: t("customers.disconnect.confirm.factAddress", { defaultValue: "Address" }),
      value: account?.premise ?? "—",
    },
    {
      id: "reason",
      label: t("customers.disconnect.confirm.factReason", { defaultValue: "Reason" }),
      value:
        props.draft.reason === ""
          ? "—"
          : t(`customers.disconnect.reason.${props.draft.reason}`, {
              defaultValue: props.draft.reason,
            }),
    },
    {
      id: "services",
      label: t("customers.disconnect.confirm.factServices", { defaultValue: "Services" }),
      value: cut.length === 0 ? "—" : cut.map((code) => serviceLabel(code, t)).join(", "),
    },
    {
      id: "cut-date",
      label: t("customers.disconnect.confirm.factCutDate", { defaultValue: "Cut date" }),
      value: props.draft.cutOn === "" ? "—" : props.draft.cutOn,
    },
    {
      id: "work-order",
      label: t("customers.disconnect.confirm.factWorkOrder", { defaultValue: "Work order" }),
      // ⛔ Nothing raises one (see `ScheduleStep` §3), so this states the count
      // the clerk ASKED for rather than a reference nothing allocated.
      value: t("customers.disconnect.confirm.workOrdersAsked", {
        defaultValue: "{{count}} asked for",
        count: workOrderCount(props.draft),
      }),
    },
  ];

  const feeColumns: DisconnectArrayColumn<DisconnectFeeRow>[] = [
    {
      key: "charge",
      label: t("customers.disconnect.confirm.colCharge", { defaultValue: "Charge" }),
      cell: (row) => <span className="font-semibold">{row.charge}</span>,
    },
    {
      key: "from",
      // §3 — where the figure ACTUALLY came from.
      label: t("customers.disconnect.confirm.colFrom", { defaultValue: "From" }),
      cell: () => (
        <span className="text-neutral-700">
          {t("customers.disconnect.confirm.fromCatalogue", {
            defaultValue: "This utility's own rates",
          })}
        </span>
      ),
    },
    {
      key: "amount",
      label: t("customers.disconnect.confirm.colAmount", { defaultValue: "Amount" }),
      numeric: true,
      cell: (row) =>
        row.amount === null || row.amount.stored === null ? (
          // ⚠ AN ABSENCE, NEVER A ZERO. The tenant has not priced this code.
          <span className="text-neutral-700">
            {t("customers.disconnect.confirm.notPriced", { defaultValue: "Not priced" })}
          </span>
        ) : (
          <MoneyCell
            amount={row.amount.stored}
            currency={account?.balance_currency ?? "USD"}
          />
        ),
    },
    {
      key: "when",
      label: t("customers.disconnect.confirm.colWhen", { defaultValue: "When" }),
      cell: (row) => (
        <span className="text-neutral-700">
          {row.charged_on_this_cut
            ? t(`customers.disconnect.confirm.when.${row.code}`, { defaultValue: row.when })
            : t("customers.disconnect.confirm.notCharged", { defaultValue: "Not charged" })}
        </span>
      ),
    },
  ];

  const visitColumns: DisconnectArrayColumn<DisconnectVisitRow>[] = [
    {
      key: "point",
      label: t("customers.disconnect.schedule.colPoint", { defaultValue: "Service point" }),
      cell: (row) => <span className="font-semibold">{row.label}</span>,
    },
    {
      key: "visit",
      label: t("customers.disconnect.schedule.colVisit", { defaultValue: "Visit" }),
      cell: (row) => (
        <span>
          {row.visit === ""
            ? "—"
            : t(`customers.disconnect.visit.${row.visit}`, { defaultValue: row.visit })}
        </span>
      ),
    },
    {
      key: "instruction",
      label: t("customers.disconnect.schedule.colInstruction", { defaultValue: "Instruction" }),
      cell: (row) => <span>{row.instruction === "" ? "—" : row.instruction}</span>,
    },
  ];

  // ⚠ **`What happens at the cut` IS BUILT FROM THE SIGNED RULES AND NOT FROM
  // THE DRAWING.** Each row is a FACT of six words or fewer with its detail
  // beside it, and not one of them says WHY (B14 rule 33).
  const consequences = [
    {
      id: "cut",
      what: props.master
        ? t("customers.disconnect.confirm.willCutCommon", {
            defaultValue: "The common supply is cut",
          })
        : t("customers.disconnect.confirm.willCut", { defaultValue: "Service is cut" }),
      detail: props.draft.cutOn === "" ? "—" : props.draft.cutOn,
    },
    ...(props.master && props.occupants !== null
      ? [
          {
            id: "occupants",
            what: t("customers.disconnect.confirm.occupantsLose", {
              defaultValue: "{{count}} occupants lose supply",
              count: props.occupants,
            }),
            detail: t("customers.disconnect.confirm.occupantsOweNothing", {
              defaultValue: "None of them owes anything",
            }),
          },
        ]
      : []),
    {
      id: "base-stops",
      // BR-CUS-103
      what: props.master
        ? t("customers.disconnect.confirm.ownerChargesStop", {
            defaultValue: "The owner's charges stop",
          })
        : t("customers.disconnect.confirm.chargesStop", {
            defaultValue: "Base and standing charges stop",
          }),
      detail: t("customers.disconnect.confirm.fromCutDate", { defaultValue: "From the cut date" }),
    },
    {
      id: "fees",
      // BR-CUS-104's timing half.
      what: t("customers.disconnect.confirm.feesOnBalance", {
        defaultValue: "Fees go on the balance",
      }),
      detail: <ChargedFees terms={terms} account={account} t={t} />,
    },
    {
      id: "balance-static",
      // BR-CUS-105
      what: t("customers.disconnect.confirm.balanceStatic", {
        defaultValue: "The balance stops moving",
      }),
      detail: t("customers.disconnect.confirm.untilTheyPay", {
        defaultValue: "Until they pay or it is corrected",
      }),
    },
    {
      id: "ladder-stops",
      what: t("customers.disconnect.confirm.ladderStops", { defaultValue: "The ladder stops" }),
      detail: t("customers.disconnect.confirm.noFurtherNotices", {
        defaultValue: "No further notices",
      }),
    },
    {
      id: "marks",
      // ⚠ **`BR-CUS-1100` — THE ACCOUNT AND THE CUSTOMER, NEVER THE ADDRESS.**
      // The split is the load-bearing part: marking the customer catches them
      // applying at a different address; NOT marking the address means a new
      // tenant moving into that same unit is not punished for the previous
      // occupant's debt.
      what: t("customers.disconnect.confirm.marks", {
        defaultValue: "Account and customer are marked",
      }),
      detail: t("customers.disconnect.confirm.notTheAddress", {
        defaultValue: "The address is not marked",
      }),
    },
  ];

  return (
    <div className="flex flex-col gap-6" data-step="confirm">
      <Panel
        as="section"
        title={t("customers.disconnect.confirm.thisCut", { defaultValue: "This cut" })}
        data-panel="this-cut"
      >
        <DisconnectFacts facts={facts} name="this-cut" />
        {/* ONE warning line carrying both facts, six words and five. No
            explanation of either (B14 rule 33). */}
        {(props.protectionsInForce.length > 0 || props.proofMissing) && (
          <div className="mt-4">
            <WarningBox
              tone="now"
              data-warning="confirm"
              sentence={
                <strong>
                  {[
                    props.protectionsInForce.length > 0
                      ? props.master
                        ? t("customers.disconnect.confirm.occupantsProtected", {
                            defaultValue: "Occupants hold a protection.",
                          })
                        : t("customers.disconnect.confirm.protected", {
                            defaultValue: "A protection is in force.",
                          })
                      : "",
                    props.proofMissing
                      ? t("customers.disconnect.confirm.noProof", {
                          defaultValue: "No proof of service recorded.",
                        })
                      : "",
                  ]
                    .filter((part) => part !== "")
                    .join(" ")}
                </strong>
              }
            />
          </div>
        )}
      </Panel>

      <DisconnectTableArray<DisconnectFeeRow>
        title={t("customers.disconnect.confirm.fees", { defaultValue: "Fees" })}
        // §3 — a fact about the ACCOUNT, never the provenance of the figures.
        fact={<PlanAndCategory account={account} t={t} categories={categories.all} />}
        readOnly
        columns={feeColumns}
        rows={terms?.fees ?? []}
        rowKey={(row) => row.code}
        emptyText={t("customers.disconnect.confirm.noFees", {
          defaultValue: "Fees are not loaded yet.",
        })}
        collection="fees"
      />

      <Panel
        as="section"
        title={t("customers.disconnect.confirm.deposit", { defaultValue: "The deposit" })}
        data-panel="deposit"
      >
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_2fr]">
          <div>
            <p className="m-0 mb-2 text-h3 font-heading" data-deposit-held="">
              {terms === null || terms.deposit.on_file.stored === null ? (
                "—"
              ) : (
                <MoneyCell
                  amount={terms.deposit.on_file.stored}
                  currency={account?.balance_currency ?? "USD"}
                />
              )}
            </p>
            <SelectField
              id="disconnect-deposit"
              label={t("customers.disconnect.confirm.whatHappens", {
                defaultValue: "What happens",
              })}
              value={props.draft.deposit}
              onChange={(value) => props.onPatch({ deposit: value as DepositDisposition })}
              options={DEPOSIT_DISPOSITIONS.map((option) => ({
                value: option.code,
                label: t(`customers.disconnect.deposit.${option.code}`, {
                  defaultValue: option.en,
                }),
              }))}
              // A FACT about reconnection, five words. Not why.
              help={
                terms?.deposit.new_deposit_required === true
                  ? t("customers.disconnect.confirm.newDeposit", {
                      defaultValue: "New deposit required to reconnect.",
                    })
                  : undefined
              }
            />
          </div>
          {/* ⚠ §2 — THREE ROWS AND NO `Deposit applied` SUBTRACTION. Every
              figure here is the server's own; nothing is added up in a browser
              (hard rule 2). */}
          <RecapBox
            data-recap="to-clear"
            title={t("customers.disconnect.confirm.toClearTitle", {
              defaultValue: "What must be cleared",
            })}
            rows={[
              {
                label: t("customers.disconnect.confirm.owedNow", { defaultValue: "Owed now" }),
                testId: "owed-now",
                value: <Figure money={terms?.to_clear.arrears ?? null} account={account} t={t} />,
              },
              {
                label: t("customers.disconnect.confirm.feesAtCut", {
                  defaultValue: "Fees added at the cut",
                }),
                testId: "fees-at-cut",
                value: <Figure money={terms?.to_clear.fee ?? null} account={account} t={t} />,
              },
            ]}
            outcome={{
              label: t("customers.disconnect.confirm.toClear", {
                defaultValue: "To clear before reconnection",
              }),
              testId: "to-clear",
              value: <Figure money={terms?.to_clear.total ?? null} account={account} t={t} />,
            }}
          />
        </div>
      </Panel>

      {/* ⚠ **THE FIELD WORK REPEATS HERE — ITEM 3.5**, through the SAME
          component read-only, so one set of rows cannot read two ways on two
          steps of one wizard. */}
      <DisconnectTableArray<DisconnectVisitRow>
        title={t("customers.disconnect.schedule.whoGoes", { defaultValue: "Who goes" })}
        readOnly
        columns={visitColumns}
        rows={props.draft.visits}
        rowKey={(row, index) => `${row.point}-${index}`}
        emptyText={t("customers.disconnect.confirm.noVisits", {
          defaultValue: "No crew is going.",
        })}
        collection="confirm-visits"
      />

      <Panel
        as="section"
        title={t("customers.disconnect.confirm.whatHappens2", {
          defaultValue: "What happens at the cut",
        })}
        data-panel="consequences"
      >
        <dl className="m-0">
          {consequences.map((row) => (
            <div
              key={row.id}
              className="flex flex-wrap items-baseline justify-between gap-4 border-b border-b-divider py-2 last:border-b-0"
              data-consequence={row.id}
            >
              <dt className="m-0 text-base font-semibold text-neutral-900">{row.what}</dt>
              <dd className="m-0 text-right text-base text-neutral-700">{row.detail}</dd>
            </div>
          ))}
        </dl>
      </Panel>
    </div>
  );
}

/** A server figure, or its absence. ⚠ **NEVER A ZERO AND NEVER A DASH THAT
 *  READS AS ONE** — `DEF-127`: the books being unreadable and the account owing
 *  nothing are different claims. */
function Figure(props: {
  money: { stored: string | null } | null;
  account: AccountDetail | null;
  t: Translator;
}) {
  if (props.money === null || props.money.stored === null) {
    return (
      <span className="text-neutral-700">
        {props.t("customers.disconnect.confirm.notKnown", { defaultValue: "Not known" })}
      </span>
    );
  }
  return (
    <MoneyCell
      amount={props.money.stored}
      currency={props.account?.balance_currency ?? "USD"}
    />
  );
}

/** The total of the fees this cut will actually raise. ⚠ **IT IS THE SERVER'S
 *  `to_clear.fee` AND IS NOT SUMMED FROM THE TABLE** — a total of money summed
 *  in JavaScript is the thing hard rule 2 exists to prevent, and `RecapBox`'s
 *  own docstring says the kit renders what it is handed and adds nothing up. */
function ChargedFees(props: {
  terms: DisconnectTerms | null;
  account: AccountDetail | null;
  t: Translator;
}) {
  return <Figure money={props.terms?.to_clear.fee ?? null} account={props.account} t={props.t} />;
}

/**
 * The account's plan and its category — §3.
 *
 * ⚠ **A FACT ABOUT THE ACCOUNT AND NOT THE PROVENANCE OF A FIGURE.**
 * `unit_plan` is the plan the account's UNIT carries (`DEF-2419`: served since
 * 2026-09-01 under its own key, because `plan` is the SNAPSHOT that priced old
 * bills and is still not held). `account_type` is the platform category code
 * and is rendered through its catalogue, never raw (B14 rule 32).
 */
function PlanAndCategory(props: {
  account: AccountDetail | null;
  t: Translator;
  categories: readonly { code: string; name: string }[];
}) {
  const account = props.account;
  if (account === null) {
    return null;
  }
  const category = accountCategoryName(account.account_type, props.categories);
  const plan = account.unit_plan?.name ?? null;
  return (
    <span data-plan-and-category="">
      {plan === null
        ? category
        : props.t("customers.disconnect.confirm.planAndCategory", {
            defaultValue: "{{category}} · {{plan}}",
            category,
            plan,
          })}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the disconnect wizard rebuild, 2026-09-25 · `Step4Confirm.png` ·
//         `MasterStep4.png` · blueprint p139 · `DEF-CUS-6752` ·
//         `DEF-CUS-6753` · BR-BIL-007 · BR-CUS-103 · BR-CUS-104 ·
//         BR-CUS-105 · BR-CUS-1098 · BR-CUS-1100 · hard rules 2 and 5 ·
//         B14 rules 20, 21, 31, 32, 33, 37, 42, 43, 44
// generated: 2026-09-25 by lane WIZARD
// exceptions:
//   E3 **the drawn `Deposit applied` SUBTRACTION IS NOT RENDERED** (§2,
//      `DEF-CUS-6753`). Nothing applies a deposit and `_to_clear` subtracts
//      nothing; the election is offered because it is real and stored.
//   E3 **the `FROM` column names the tenant's catalogue and not a plan** (§3,
//      `DEF-CUS-6752`). The panel's right-hand fact is the ACCOUNT's plan and
//      category, which is true of the account.
//   E3 **the master's `TIMES` and `TOTAL` columns are not drawn.**
//      `BR-CUS-1098` prices a building's fee ONCE, which the table already says
//      by carrying one amount per code; `_fee_table()` serves no multiplier and
//      a `× 1` computed here would be arithmetic this screen invented.
//   E3 **blueprint p139's `Take a payment now` section is NOT drawn.** It is
//      absent from the new drawing, and taking money is a PAYMENTS act with its
//      own screen, its own receipt and its own audit row. REPORTED rather than
//      carried forward.
//   E3 **no fee figure is a literal** — six drawn amounts, all illustrations.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
