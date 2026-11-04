// ── Trace ──────────────────────────────────────────────
// Defects:  DEF-CUS-6350 (Approve checked nothing about the property or the unit,
//           and the clerk processing a request was not told why it failed) ·
//           DEF-CUS-6352 (a MOVE-IN was told it raises a build, and the fee line
//           printed `45.0000 USD. Approval is not blocked.`)
// Rulings:  PO 2026-09-23 — decision log §4 of *"… AND *APPROVE* CHECKS THE
//           PROPERTY AND UNIT BEFORE IT IS PRESSED"*, *"THE *APPROVE* WINDOW'S
//           TWO LAYOUTS, APPROVED"*, *"RULED: A NEW CONNECTION ONLY WHERE THE
//           ADDRESS IS NOT IN PREMISES — IN ANY STATUS"* and *"RULED: THE
//           MOVE-IN APPROVAL FLOW, SIX STEPS"*. PO, verbatim: *"we are not
//           showing all this issues to user when they are processing hence they
//           dont understand what is happening"* · *"please please ensure you
//           follow ui styleguide and correct tailwind components"*
// Rules:    B14 rule 43 (a piece of UI is a COMPONENT — this window is its own
//           file, and `ServiceRequestDetailPage.tsx` only mounts it) · rule 36
//           (compose the kit: `FormModal`, `SegmentedControl`, `CheckList`,
//           `ConsequenceBox`, `Button`) · rule 38 (the drawing decides what the
//           window CONTAINS, our rules how it is BUILT — the PO approved this
//           construction) · rule 11 (a consequence box before a commit that
//           writes service state) · rule 21 (Tailwind utilities; on
//           route-b-migrated.txt) · rule 31 (account and unit NUMBERS, never an
//           id) · rule 33 (label ≤ 3 words, fact ≤ 6, rationale zero) ·
//           BR-SHL-025 (Approve is disabled WITH its reason, never hidden)
// Tests:    src/features/customers/ApproveChecksModal.dom.test.tsx ·
//           ServiceRequestDetailPage.dom.test.tsx (the window, mounted under the
//           real route, and where the clerk lands after Approve)
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHAT THIS WINDOW IS, IN THE PO'S APPROVED LAYOUT
// ══════════════════════════════════════════════════════════════════════════
//
//     Approve SR-26-0016 · Tim David
//     What kind    [ Move-in | New connection ]
//     Checks
//      ✓  Property    highland park, Ottumwa
//      ✓  Unit        U-00003 · 1
//      ✗  Unit free   Occupied · AC-2026-00012
//      !  Documents   2 not checked
//      ✓  Fee         $70.00 paid
//      ▌ Opens a move-in job.
//      ▌ The account opens on move day.
//                           Cancel   [ Approve ]   (disabled, with its reason)
//
// ⚠ **EVERY ROW IS A SERVER CONDITION, IN THE SERVER'S ORDER, AND NOTHING HERE
// DECIDES ONE.** `decision.what_approving_will_do[<kind>].conditions` is the same
// list `_refuse_unless_approvable` refuses on, answered as if this kind were the
// pick — so the ✗ this window draws and the refusal the server would give are one
// list, not two that agree today. This file maps a condition to a glyph, a label
// and six words; it never works out whether a unit is free.
//
// ⚠ **TWO ROWS THE DRAWING DOES NOT SHOW ARE DRAWN, AND BOTH ARE THE SERVER'S.**
// *Arrears* still BLOCKS an approval until somebody records that they searched,
// and *Search customer* below is the only door that answers it (*Link*, or *No
// match* — PO 2026-10-11, option B) — so it is a row pointing at that search
// (see `ARREARS_NOT_SEARCHED`), because a blocker the window does not show is
// the exact failure the PO reported. *Other move-in* is the ruling's
// fourth move-in check (*"no other move-in is already waiting for that unit"*).
// *Eligibility* never blocks and is drawn only when something was claimed.
//
// ⚠ **THE KIND IS A `SegmentedControl` WITH `purpose="choice"`, NOT HAND-ROLLED
// RADIOS.** B14 has no rule that picks a radio over a segment for two options;
// rule 36 names hand-rolled segmented controls as a breach and puts
// `SegmentedControl` in the kit for exactly this, and rule 38 hands a form's
// CONSTRUCTION to the kit. It is a `radiogroup` of `radio`s underneath, so the
// accessible meaning is the drawing's `(●)` and the look is r10's `.seg`.
// `BR-SHL-025` and the PO's 2026-09-20 ratification (*"this is correct"* — each
// option carries its own verdict, refused ones DISABLED WITH THEIR REASON, none
// hidden) ride on the segment's own `disabledReason`, which the kit renders as
// visible text.
//
// ⛔ **NO LINE SAYS AN UNPAID FEE MOVES ANYWHERE.** PO 2026-09-23: *"there are no
// unpaid fees either applcition fee is paid or it is waived - so this is not
// applicable anymore"*. The Fee row is a check like the others, its ✓ / ! / ✗
// read from the server's own `blocking` flag, and the money is formatted to two
// places through `formatMoney` (hard rule 2) — never the server's 4-dp string
// and code, which is what `DEF-CUS-6352`'s screenshot printed.
import { useState } from "react";
import type { ReactNode } from "react";

import { Button } from "@/components/Button";
import { CheckList } from "@/components/CheckList";
import type { CheckRow, CheckState } from "@/components/CheckList";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import { FormModal } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formatMoney } from "@/components/MoneyCell";
import { SegmentedControl } from "@/components/SegmentedControl";

import { FromTheCustomer } from "./RequestCategoryToSet";
import { RequestCustomFieldCopy } from "./RequestCustomFieldCopy";
import type {
  ApprovalConditions,
  RequestCustomFieldPicks,
  ServiceRequestDetail,
  ServiceRequestOutcome,
} from "./serviceRequestEndpoints";
import { APPROVE_OUTCOMES } from "./serviceRequestEndpoints";
import { APPROVE_SCHEMA } from "./serviceRequestDecisions";

type Translate = (key: string, params?: Record<string, unknown>) => string;
type Condition = ApprovalConditions["conditions"][number];

/** What the clerk answered, sent WITH the approval. */
export interface ApproveChoice {
  /** *It's a new address* — the clerk's answer to a near match in Premises. */
  addressIsNew: boolean;
  /** `CR-161-BRC10` W6 — R5's pick per conflicting answer. Empty = keep every
   *  existing value, which is the pre-selection. */
  customFieldPicks: RequestCustomFieldPicks;
}

/** The condition keys the server names about the PLACE (`service_request.py`
 *  `MOVE_IN_PLACE_KEYS` + `NEW_CONNECTION_PLACE_KEYS`). Their labels live under
 *  `condition.*`, beside the refusal sentences; the four older conditions'
 *  short labels live under `check.*`. */
const PLACE_KEYS: ReadonlySet<string> = new Set([
  "premises_on_file",
  "unit_chosen",
  "unit_free",
  "no_other_move_in",
  "address_not_in_premises",
  "no_open_request_here",
]);

/** The one condition this window can ANSWER as well as report. */
const ARREARS_NOT_SEARCHED = "customers.serviceRequest.condition.arrearsNotSearched";
/** A near match in Premises — the question with two answers. */
const ADDRESS_LOOKS_LIKE = "customers.serviceRequest.condition.addressLooksLike";

const NS = "customers.serviceRequest";

function labelKey(key: string): string {
  return PLACE_KEYS.has(key) ? `${NS}.condition.${key}` : `${NS}.check.${key}`;
}

function suffixOf(messageKey: string | null): string | null {
  if (messageKey === null || messageKey === "") return null;
  const parts = messageKey.split(".");
  return parts[parts.length - 1] ?? null;
}

/** Whether a decimal STRING is above zero — asked of the string, never of a
 *  float (hard rule 2). `"0.0000"` and `""` are not. */
function isPositive(amount: string | null | undefined): boolean {
  if (amount === null || amount === undefined) return false;
  return /[1-9]/u.test(amount) && !amount.trim().startsWith("-");
}

/** A condition's glyph. The server's `blocking` flag decides ✗ against ! — a
 *  condition the server REPORTS but does not refuse on is never drawn red. */
export function checkStateOf(condition: Condition, answeredNew: boolean): CheckState {
  if (condition.state === "clear") return "ok";
  if (condition.state === "not_reached") return "notReached";
  if (condition.state === "choose") return answeredNew ? "ok" : "noted";
  if (condition.state === "noted") return "noted";
  return condition.blocking ? "bad" : "noted";
}

/** What one condition FOUND, in six words or fewer. */
function factOf(condition: Condition, detail: ServiceRequestDetail, t: Translate, answeredNew: boolean): string {
  const suffix = suffixOf(condition.message_key);
  const params = condition.params ?? {};
  if (condition.state === "choose" && answeredNew) {
    return t(`${NS}.checkFact.addressDeclaredNew`);
  }
  if (condition.key === "fee_settled") {
    if (suffix === "feeOutstandingAmount") {
      const currency = typeof params.currency === "string" ? params.currency : "";
      const amount = typeof params.amount === "string" ? params.amount : "";
      return currency !== "" && amount !== ""
        ? t(`${NS}.checkFact.feeOutstandingAmount`, { amount: formatMoney(amount, currency) })
        : t(`${NS}.checkFact.feeOutstanding`, { count: 1 });
    }
    if (suffix === "feeOutstanding") {
      return t(`${NS}.checkFact.feeOutstanding`, params);
    }
    const collected = detail.fees.collected;
    if (collected.currency !== null && collected.currency !== "" && isPositive(collected.amount)) {
      return t(`${NS}.checkFact.feePaid`, {
        amount: formatMoney(collected.amount, collected.currency),
      });
    }
    return t(`${NS}.checkFact.clear.fee_settled`);
  }
  if (suffix === "arrearsOutstanding") {
    const currency = detail.fees.quoted.currency;
    const amount = typeof params.amount === "string" ? params.amount : "";
    return currency !== null && currency !== "" && amount !== ""
      ? t(`${NS}.checkFact.arrearsOutstanding`, { amount: formatMoney(amount, currency) })
      : t(`${NS}.checkFact.arrearsOwedNoCurrency`);
  }
  if (suffix !== null) {
    return t(`${NS}.checkFact.${suffix}`, params);
  }
  // A condition the server sent with no sentence. Clear has its own words per
  // check; anything else is named by its state rather than guessed at — a
  // screen inventing why would be stating a rule it does not own.
  if (condition.state === "clear") {
    return t(`${NS}.checkFact.clear.${condition.key}`);
  }
  return t(`${NS}.check.state.${checkStateOf(condition, answeredNew)}`);
}

export function ApproveChecksModal(props: {
  detail: ServiceRequestDetail;
  t: Translate;
  onClose: () => void;
  onSubmit: (outcome: ServiceRequestOutcome, choice: ApproveChoice) => Promise<FormSubmitOutcome>;
  /** `Same property` — picks the near match onto the request (the capture
   *  door, `picked_premises_id`), after which the server refuses the new
   *  connection BY NAME. */
  onSameProperty?: (premisesId: string) => void;
  /** `DEF-CUS-9043` — the finder that LINKS a customer on file to the request
   *  (`RequestCustomerLink`). Drawn under the checks; the Arrears check reads
   *  the link, and its *No match* records the search (PO 2026-10-11, option
   *  B) — the only door that clears the arrears check. */
  customerLink?: ReactNode;
  /** ⊕ `DEF-CUS-10251` — *Set before approving*: the category pickers
   *  (`RequestCategoryToSet`), drawn first while a portal request still needs
   *  its category. The window holds Approve on `detail.applicant.
   *  category_to_be_set` whatever is passed here — the server refuses it too. */
  categoryPicker?: ReactNode;
  working?: boolean;
}) {
  const { detail, t } = props;
  const stored = detail.decision.commit.outcome;
  const verdicts = new Map((detail.decision.options ?? []).map((row) => [row.outcome, row]));
  const refused = (option: string): boolean => verdicts.get(option)?.verdict === "not_possible";
  const [outcome, setOutcome] = useState<ServiceRequestOutcome | "">(() => {
    if ((APPROVE_OUTCOMES as readonly string[]).includes(String(stored ?? "")) && !refused(String(stored))) {
      return stored as ServiceRequestOutcome;
    }
    // PO 2026-10-11, option A: at an address already in Premises the server
    // grades New connection `not_possible` (greyed out, with its reason) and
    // Move-in is picked for the clerk.
    const open = APPROVE_OUTCOMES.filter((option) => !refused(option));
    return open.length === 1 && refused("new_connection") ? open[0] : "";
  });
  const [answeredNew, setAnsweredNew] = useState(false);
  const [customFieldPicks, setCustomFieldPicks] = useState<RequestCustomFieldPicks>({});

  const suggested = APPROVE_OUTCOMES.find(
    (option) => verdicts.get(option)?.verdict === "fits_the_evidence",
  );
  const preview = outcome === "" ? undefined : detail.decision.what_approving_will_do[outcome];
  const conditions = (preview?.conditions?.conditions ?? []).filter(
    // Eligibility NEVER blocks (B19 §12.3), so it is a row only when something
    // was claimed — the *None claimed* case is not a check a clerk acts on.
    (row) => !(row.key === "eligibility_evidence" && row.state === "clear"),
  );

  const rows: CheckRow[] = conditions.map((condition) => {
    const state = checkStateOf(condition, answeredNew);
    const row: CheckRow = {
      id: condition.key,
      label: t(labelKey(condition.key)),
      state,
      fact: factOf(condition, detail, t, answeredNew),
    };
    if (
      condition.message_key === ARREARS_NOT_SEARCHED &&
      condition.blocking &&
      props.customerLink !== undefined
    ) {
      // PO 2026-10-11, option B: the row's own *Record that I searched* button
      // merged into *Search customer* below (`RequestCustomerLink`'s *No
      // match*), so the row points there rather than offering a second door.
      row.action = (
        <span className="text-sm text-neutral-700" data-approve-arrears-search="">
          {t(`${NS}.approveChecks.searchBelow`)}
        </span>
      );
    }
    if (condition.key === "fee_settled" && state === "bad") {
      // ⛔ PO 2026-09-23 (`OQ-CUS-12617`): *"either fee is paid or waived - no
      // other condition"*. The two ways out are named in words; the controls
      // that DO them are the request's own fee panel, not this window's.
      row.action = (
        <span className="text-sm text-neutral-700" data-fee-ways-out="">
          {t(`${NS}.checkFact.feeWaysOut`)}
        </span>
      );
    }
    if (condition.message_key === ADDRESS_LOOKS_LIKE && condition.state === "choose" && !answeredNew) {
      const premisesId =
        typeof condition.params?.premises_id === "string" ? condition.params.premises_id : "";
      row.action = (
        <>
          <Button
            variant="secondary"
            size="sm"
            disabled={props.working === true || premisesId === "" || props.onSameProperty === undefined}
            data-action="same-property"
            onClick={() => props.onSameProperty?.(premisesId)}
          >
            {t(`${NS}.approveChecks.sameProperty`)}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            data-action="new-address"
            onClick={() => setAnsweredNew(true)}
          >
            {t(`${NS}.approveChecks.newAddress`)}
          </Button>
        </>
      );
    }
    return row;
  });

  // ⚠ **THE COMMIT IS HELD BY THE SAME ROWS THE SERVER REFUSES ON** — the
  // server's own `blocking` list for this kind. The one row this window can
  // clear locally is the near-match question, and only by the answer the
  // approval then carries to the server (`address_is_new`), where it is checked
  // again. Nothing is cleared on a guess.
  const unansweredQuestion = conditions.some((row) => row.state === "choose" && !answeredNew);
  const blockers = conditions.filter(
    (row) => row.blocking && row.state !== "clear" && !(row.state === "choose" && answeredNew),
  );
  const commitBlocked =
    outcome === ""
      ? t(`${NS}.approveChecks.pickFirst`)
      : unansweredQuestion
        ? t(`${NS}.approveChecks.chooseFirst`)
        : blockers.length > 0
          ? t(`${NS}.approve.blocked`, {
              blockers: blockers.map((row) => t(labelKey(row.key))).join(" · "),
            })
          : undefined;

  const shape = preview?.window ?? null;
  // ⊕ `DEF-CUS-10251` — a portal request opens no account until staff set its
  // category (PO 2026-10-18, *"this is correct"*); the server refuses with
  // `customers.serviceRequest.categoryFirst` on the same fact.
  const categoryMissing =
    detail.applicant?.category_to_be_set === true &&
    (outcome === "" || outcome === "move_in" || outcome === "new_connection");
  const fromPortal = detail.header?.channel === "customer_portal" && detail.applicant !== undefined;

  return (
    <FormModal
      title={t(`${NS}.approveChecks.title`, {
        number: detail.header.request_no ?? "",
        applicant: detail.header.applicant ?? "",
      })}
      schema={APPROVE_SCHEMA}
      values={{ outcome }}
      submitLabel={t(shape === null ? `${NS}.approveChecks.submit.none` : shape.submit)}
      commitBlocked={categoryMissing ? t(`${NS}.categoryToSet.first`) : commitBlocked}
      onClose={props.onClose}
      onSubmit={() =>
        outcome === ""
          ? Promise.resolve<FormSubmitOutcome>({ ok: true })
          : props.onSubmit(outcome, { addressIsNew: answeredNew, customFieldPicks })
      }
    >
      {props.categoryPicker ?? null}
      {fromPortal ? <FromTheCustomer detail={detail} t={t} /> : null}
      <div
        className="flex flex-wrap items-center gap-x-4 gap-y-2"
        data-outcome-picker=""
      >
        <span id="approve-checks-kind" className="text-md text-neutral-700">
          {t(`${NS}.approveChecks.kind`)}
        </span>
        <SegmentedControl
          purpose="choice"
          name="approve-kind"
          labelledBy="approve-checks-kind"
          label={t(`${NS}.approveChecks.kind`)}
          active={outcome}
          onSelect={(id) => {
            setOutcome(id as ServiceRequestOutcome);
            setAnsweredNew(false);
          }}
          segments={APPROVE_OUTCOMES.map((option) => {
            const verdict = verdicts.get(option);
            return verdict?.verdict === "not_possible"
              ? {
                  id: option,
                  label: t(`${NS}.approveChecks.kindOption.${option}`),
                  // BR-SHL-025 — refused, and says why, in the server's words.
                  disabledReason:
                    verdict.message_key !== null ? t(verdict.message_key) : undefined,
                  disabled: verdict.message_key === null ? true : undefined,
                }
              : { id: option, label: t(`${NS}.approveChecks.kindOption.${option}`) };
          })}
        />
        {suggested !== undefined && (
          <span className="text-sm text-neutral-700" data-verdict-badge={suggested}>
            {t(`${NS}.approveChecks.suggested`, {
              kind: t(`${NS}.approveChecks.kindOption.${suggested}`),
            })}
          </span>
        )}
      </div>

      {preview !== undefined && (
        <section data-approve-checks={outcome}>
          <h4 className="m-0 mb-1 text-xs font-semibold tracking-wide text-accent uppercase">
            {t(`${NS}.approveChecks.checks`)}
          </h4>
          <CheckList
            rows={rows}
            label={t(`${NS}.approveChecks.checksLabel`)}
            stateLabels={{
              ok: t(`${NS}.check.state.ok`),
              bad: t(`${NS}.check.state.bad`),
              noted: t(`${NS}.check.state.noted`),
              notReached: t(`${NS}.check.state.notReached`),
            }}
          />
        </section>
      )}

      {props.customerLink ?? null}

      {/* `CR-161-BRC10` W6 — what approving does with the utility's own
          fields typed on this request; a conflict is picked here (R5). */}
      <RequestCustomFieldCopy
        blocks={detail.custom_field_copy ?? []}
        picks={customFieldPicks}
        onPick={(entity, key, pick) =>
          setCustomFieldPicks((before) => ({
            ...before,
            [entity]: { ...(before[entity] ?? {}), [key]: pick },
          }))
        }
      />

      {shape !== null && shape.lines.length === 2 && (
        <ConsequenceBox
          tone="check"
          tag={t(`${NS}.approveChecks.effectTag`)}
          title={t(shape.lines[0] ?? "")}
          body={t(shape.lines[1] ?? "")}
          data-consequence={`approve-${outcome}`}
        />
      )}
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-CUS-6350 · DEF-CUS-6352 · decision log 2026-09-23 (four entries, named in the trace) · B14 rules 11, 21, 31, 33, 36, 38, 43
// generated: 2026-09-23 by lane APPROVE-CHECKS
// checklist: A✔ B✔ C✔ D✔(the window reads the server's conditions and computes none) E✔(ServiceRequestDetailPage mounts it) F✔ G✔ H=n/a
// gates: tsc · vitest ApproveChecksModal.dom.test.tsx + ServiceRequestDetailPage.dom.test.tsx · routeBUtilities (on route-b-migrated.txt)
// exceptions: E3 the drawing's radios are the kit's SegmentedControl (B14 rules 36/38) · E3 the Arrears row is drawn though the approved layout does not show it — it still blocks and its button is the only door that clears it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
