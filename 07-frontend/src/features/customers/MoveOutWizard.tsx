// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-005 (S20 Move-Out wizard, four steps, and the BR-CUS-031
//           final-bill handoff) · US-CUS-007 (the deposit fields inside S20
//           step 3 — every one of which the server refuses)
//           Screens: S20 (entered from S21's Move-out action)
// Rules:    BR-CUS-021 (final reads commit through the metering service) ·
//           BR-CUS-025 (deposit applies to the final bill FIRST; the refund leg
//           is payments' `refunds`) · BR-CUS-030 (move-out writes `closed_at`,
//           the terminal status, every service agreement's `ended_on`, stops
//           dunning and queues the close-out documents) · BR-CUS-031 (the
//           final-bill handoff contract to billing) · BR-CUS-055 (the seeded,
//           tenant-extensible statuses and their behaviour classes) ·
//           BR-CUS-056 (the OUTGOING account pays the move day) · BR-CUS-057
//           (deposit interest accrual) · BR-BIL-004 (issued invoices are
//           immutable — a move-out may not be backdated behind one) ·
//           BR-MET-036 (the unit flips to Vacant by DERIVATION, never manually) ·
//           BR-MET-044 (the unit KEEPS its plan as the next tenant's prefill) ·
//           BR-SHL-018 (wizard rail semantics) · BR-SHL-019 (ONE transactional
//           commit) · BR-SHL-020 (plain-language absence) · BR-SHL-023 (one
//           money path) · BR-SHL-025 (a forbidden control is disabled WITH its
//           reason) · BR-SHL-033 (dates use the date control) · BR-SHL-034 (one
//           date formatter) · BR-SHL-044 (one page header)
// ───────────────────────────────────────────────────────
// S20 — the guided Move-out page. `POST /accounts/{id}/move-out` landed on
// 2026-08-11 with no screen calling it; this is that screen, and it collects
// EXACTLY the one field the endpoint accepts.
//
// `services.MOVE_OUT_FIELDS` is `{moved_out_on, status}`. Everything else the
// four prototype steps draw is in `services.REFUSED_FIELDS`, each with the rule
// that owns it, and NONE of it is collected here — a field that looks
// collectable and is thrown away is worse than an absent one:
//
//   · ✅ **The reason LEFT THIS LIST ON 2026-09-20** (PO ruling, option A).
//     It read *"`accounts.close_reason` is PROPOSED-SCHEMA and was not built,
//     so `reason` / `close_reason` are refused (BR-CUS-030). The step names the
//     five options and stores none."* The column is built, `MOVE_OUT_FIELDS`
//     accepts `reason`, and step 2 collects it in a required select. The
//     COLUMN's own name stays refused on every door, so there is one spelling
//     in. Hard-won law 1: a stale reason is a stale claim.
//   · **The final reads** (step 2's per-meter table with its Δ usage line).
//     `final_reads` is refused (BR-CUS-021): reads commit through metering's
//     batch path, whose idempotency fingerprint is scoped to (period, cycle,
//     route, service, source), and minting a single-meter batch inside it could
//     collide with the month's real import. The meters are LISTED so it is
//     visible which registers go unread — and no reading is taken from them.
//   · **The deposit disposition and the refund method** (step 3's radios).
//     Both refused (BR-CUS-025): apply-first needs the final bill, and the
//     refund leg is payments' `refunds`, which has no tables. `deposit_interest_
//     accrued` is refused too (BR-CUS-057 — the accrual engine is US-CUS-023 §7
//     and is not built), so no interest figure is shown or implied.
//   · **The final-bill preview** (step 3's six priced lines and its $184.20
//     total). There is no preview route: `POST /accounts/{id}/move-out/preview`
//     is deliberately not mounted, because the preview is B4.3 final-bill math
//     over invoices billing does not have. A rendered amount would be invented
//     money (CLAUDE.md #2).
//   · **The close-out checkboxes** (step 4's five). One of the five — the
//     unit's return to Vacant — happens by DERIVATION (BR-MET-036) and is
//     therefore stated as a consequence, not offered as a switch. The other
//     four queue through notifications and collections, neither of which has
//     tables.
//
// TWO DEPARTURES FROM THE PROTOTYPE, both deliberate:
//
//   1. ⚠ **AMENDED 2026-08-26 (PO ruling, lane MOVEENTRY) — THIS DEPARTURE IS
//      NOW HALF OF THE STORY.** It read: *"Step 1 does not search. The endpoint
//      is account-scoped, so the account arrives in the URL from S21 and the
//      step CONFIRMS it."* That is still exactly true of
//      `/accounts/:accountId/move-out` and it is why nothing there changed. It
//      was ALSO the argument for leaving the Accounts header's `Move-out`
//      disabled, and the PO overruled that argument in their own words —
//      *"-Enable Move in /move out"*. So `/move-outs/new` mounts the SAME
//      wizard with nothing in the path, and step 1 searches (the shared
//      `AccountFinder`, DEF-732) instead of confirming. The old worry — *"it
//      could pick an account this page could not then act on"* — is answered
//      where it always was: BR-CUS-030's occupant check runs on the chosen
//      account before step 1 will validate, and the server refuses regardless.
//   2. **One commit, and the answer is not navigated away from.** The prototype
//      ends on two buttons ("Complete & start move-in →" beside "Complete
//      move-out ✓"). BR-SHL-019 allows exactly one transactional commit, and
//      the nine warnings the server answers with ARE the honest statement of
//      what did not happen — so the commit is single and its result replaces the
//      wizard with a confirmation that renders every warning, the BR-CUS-031
//      handoff, and BOTH exits as links. The chain survives; the report does not
//      flash past on the way to the next screen.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountDetail, getAccounts, getUnits, moveOutAccount } from "@/api/endpoints";
import type {
  AccountDetail,
  AccountMoveOutResult,
  FinalBillHandoff,
  MoveOutFinalBill,
  UnitRow,
} from "@/api/endpoints";
import { ButtonLink } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { DatePickerField, FieldStack, SelectField } from "@/components/FormModal";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { useToast } from "@/components/Toast";
import { InlineLinkTo, RefusalStrip } from "@/components/Surfaces";
import { WarningBox } from "@/components/WarningBox";
import { formatMoney } from "@/components/MoneyCell";
import { Note } from "@/components/TextBits";
import { Panel } from "@/components/Panel";
// ⚠ **`FieldVisitOrders` AND NOT `RaiseFieldWork` SINCE 2026-09-24 — the PO
// approved the seven-column table for the move-out (*"this si correct - use
// it"*), and the move-out is the one flow of three that never mounted it.**
// `RaiseFieldWork` offered only the utility's PUBLISHED TEMPLATES — none at a
// utility that has written none, which is most of them — so the panel a clerk
// saw was usually empty. This is the component the move-in and the transfer
// already mount; nothing new is built.
import {
  FieldVisitOrders,
  emptyFieldVisit,
  fieldVisitPayload,
  fieldVisitProblem,
} from "@/features/work/FieldVisitOrders";
import type { FieldVisitValue } from "@/features/work/FieldVisitOrders";
import { WizardFrame } from "@/components/WizardFrame";
import type { LeaveDraft } from "@/components/LeaveGuard";
import type {
  WizardCommitOutcome,
  WizardExit,
  WizardNavState,
  WizardStep,
} from "@/components/WizardFrame";
import {
  CELL_FULL,
  Fact,
  FactList,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { billDetailPath } from "@/features/billing/billingShared";

import { accountDetailQueryKey } from "./AccountDetailPage";
import { BalanceToOwnerState } from "./BalanceToOwnerState";
import { useAccountSearch } from "./accountFinder";
import type { AccountSearchState } from "./accountFinder";
import {
  CLOSE_REASONS,
  CloseImpactPanels,
  DepositDisposition,
  MOVE_OUTS_TAB_PATH,
  MOVE_OUT_STEPS,
  moveOutStoredStep,
  vacantChargesLine,
  MoveOutAccountPick,
  PickFirstNote,
  StepColumns,
  WizardSectionStack,
  closeImpactPort,
  finalBillPreviewPort,
  flowProgress,
  landingOf,
  parkStoreBlockedReason,
  shortfallChoices,
  stepFromParam,
} from "./moveShared";
import type { FinalBillPreview, ShortfallChoice } from "./moveShared";
import { unitAssetsQueryKey, getUnitAssets } from "./UnitAssetsPanel";
import type { UnitAssetRow } from "./UnitAssetsPanel";
import {
  MoveReadsResult,
  eventReadRows,
  readableAssets,
  readsPayloadPart,
  useReadsDraft,
} from "./moveReadsCapture";
import type { ReadsDraft } from "./moveReadsCapture";
// ⚠ **THE PO-APPROVED NINE-COLUMN TABLE (2026-09-24, *"this si correct use
// it"*), MOUNTED RATHER THAN COPIED.** `OQ-394`'s prefill does NOT come from
// this component — it comes from `useReadsDraft` above, which lays the clerk's
// entries over the prior finals as a DERIVED value. The table renders the
// draft, so the move-out gets its opening figure and the move-in stays empty.
import { MoveOutServicesTable, missingFinalReads } from "./MoveOutServicesTable";
import { withReadDraft } from "./moveReadsCapture";
import { FetchMeterReading } from "@/features/metering/FetchMeterReading";
import { MoveOutEstimateNote } from "./MoveOutEstimateNote";
// ACC-06 step 1's account panel, as `01-find-account.png` draws it — two
// columns, which the kit's two-column `FactList` cannot do (B14 rule 43).
import { MoveOutAccountPanel } from "./moveOutAccountPanel";
import { FROM_MOVE_IN_VALUE, forgetTenancyAfterMoveOut, moveInResumePath } from "./moveInWizard/moveInUnitSearch";
import type { CloseImpact, CloseImpactTerms, MoneyLanding } from "./moveShared";
// CR-035 — the park store, its resume handle and the list a park lands on.
import { parkedHomePath, parkedString, useWizardPark } from "./wizardPark";
import {
  ACCOUNTS_PERMISSION,
  ACCOUNTS_ROUTE,
  DASHBOARD_ROUTE,
  Dash,
  NotRecorded,
  WarningList,
  accountDetailPath,
  accountHeadline,
  accountMoveInPath,
  accountMoveOutPath,
  accountStatusLabel,
  accountStatusTone,
  isOccupyingAccount,
  useAccountCategories,
} from "./customersShared";
import type { AccountCategoryOption } from "./customersShared";
// ⚠ **THE DRAWN TABLES ARE COMPONENTS IN THEIR OWN FILE — B14 rule 43, and
// because `MoveOutWizard.tsx` is NOT on `route-b-migrated.txt`.** G31 owns
// this file and demands every class be declared by a stylesheet, so a Tailwind
// utility written here is a RED GATE at merge; `moveOutTables.tsx` is on the
// ledger and is where they belong.
import {
  AccountsOnThisMaster,
  ClosingMeters,
  DraftBill,
  MasterCannotClose,
  ShortfallPaths,
  TheMoney,
  UnitsOnThisMaster,
} from "./moveOutTables";

import "./customers.css";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/**
 * ⚠ **SIX, NOT FOUR — `BR-SHL-046` (PO 2026-08-24, closing DEF-648, verbatim
 * *"6 steps"*).** This wizard shipped with four (`account · date · settlement ·
 * closeout`) while its own design header read *"Six steps · final bill,
 * deposit, and what happens to the unit"* and B19 §15.3 drew six. The PO ruled
 * the header right and `MVO-01`'s four-segment STEP column the defect.
 *
 * **The ids are NOT a list here.** BR-SHL-046's durable half is the mechanism:
 * *"the list's progress bar and the wizard's step bar must be driven by ONE
 * declared step list"* — `MOVE_OUT_STEPS` in `moveShared`. These two exports
 * DERIVE from it so the wizard cannot drift from the list, and the Move-outs
 * tab reads the same constant for its segment count.
 */
export const MOVE_OUT_STEP_IDS = MOVE_OUT_STEPS.map((step) => step.id);
export const MOVE_OUT_STEP_COUNT = MOVE_OUT_STEPS.length;
/** A9 / B13 §1: the step number is URL state, so a half-done flow is linkable. */
export const STEP_PARAM = "step";
/** A9: `?park=1` is URL state for the same reason the step is — a clerk who
 *  reloads mid-park still has the form they were filling in. */
export const PARK_PARAM = "park";

/** BR-SHL-011's spirit: an out-of-range `?step=` clamps, it never errors. */
export function moveOutStepFromParam(raw: string | null): number {
  return stepFromParam(raw, MOVE_OUT_STEPS);
}

/**
 * US-CUS-005 §5 + the server's own two refusals, in the order a user meets
 * them. `required` is BR-CUS-030's `move_out_date_required`; `before_start` is
 * "a tenancy cannot end before it started" — the server raises it, and saying
 * it here means the user is not told after a round trip that they could have
 * been told before one. The SERVER stays authoritative either way, and the
 * third refusal it can raise (BR-BIL-004, behind an already-issued bill) is
 * deliberately NOT mirrored: billing has no `invoices` table, so this screen
 * genuinely cannot know it.
 */
export type MoveOutDateProblem = "required" | "before_start";

export function moveOutDateProblem(
  movedOutOn: string,
  openedAt: string | null,
): MoveOutDateProblem | null {
  if (movedOutOn === "") {
    return "required";
  }
  if (openedAt !== null && movedOutOn < openedAt) {
    return "before_start";
  }
  return null;
}

/**
 * *Final reads* on step 5, as a FACT about what the clerk keyed rather than a
 * guess. Pure, so it is provable without a mount.
 *
 * `total` is every register the draft offers; `taken` is a register with a
 * figure in it; `estimated` is one the clerk marked *could not be read*. A row
 * with neither is counted in `total` and in neither of the other two — which
 * is the honest third state, and it is why this does not return a percentage.
 */
/**
 * ⚠ **THE TWO READ KEYS, DECLARED ONCE AND EXPORTED — and this is not tidiness.**
 * `renderWizard` seeded `["close-impact", id]` and the component asked for
 * `["close-impact", id, total, date]` the moment the stated terms joined the
 * key; five cases went red pointing at the SCREEN, and a sixth would have gone
 * green over a screen that never received the impact it was handed. A fixture
 * that cannot address what the component asks for is a check that does not
 * check. One builder, both callers.
 */
export function closeImpactQueryKey(
  accountId: string,
  finalBillTotal: string | null,
  movedOutOn: string,
): readonly unknown[] {
  return ["close-impact", accountId, finalBillTotal ?? "", movedOutOn];
}

/**
 * The preview's key, for the same reason — **and it carries the READS.**
 *
 * ⚠ **PO ruling 2026-09-20, option C: *re-price when, and only when, a read
 * moved between step 3 and the close*.** Always re-pricing is correct and buys
 * a pass nobody needs; never re-pricing ships a figure the reads no longer
 * support. Putting the capture in the key is that rule and not an
 * approximation of it: React Query refetches when a key changes and serves the
 * cached answer when it does not, so a clerk who corrects 52,410 to 52,401 on
 * step 2 gets a re-priced bill on step 3, and a clerk who walks back and forth
 * between the steps gets the figure they already saw.
 *
 * **The key is the ROWS THE PAYLOAD WILL CARRY, not the whole draft.**
 * `eventReadRows` drops a blank register and strips a value from an estimate
 * row, so a keystroke that changes nothing the server will be told does not
 * re-price — and a row that WILL be sent always does.
 */
export function finalBillPreviewQueryKey(
  accountId: string,
  movedOutOn: string,
  keyedReads: readonly Record<string, unknown>[] = [],
): readonly unknown[] {
  return ["final-bill-preview", accountId, movedOutOn, JSON.stringify(keyedReads)];
}

export function readsProgress(draft: ReadsDraft): {
  taken: number;
  estimated: number;
  total: number;
} {
  const rows = Object.values(draft);
  return {
    taken: rows.filter((row) => !row.estimate && row.value.trim() !== "").length,
    estimated: rows.filter((row) => row.estimate).length,
    total: rows.length,
  };
}

/**
 * The `POST /accounts/{id}/move-out` body — EXACTLY `services.MOVE_OUT_FIELDS`
 * minus `status`, which is omitted so the server picks the tenant's own seeded
 * terminal status (BR-CUS-055; a tenant may add a second one, and choosing for
 * them here would decide something nobody asked this screen to decide).
 *
 * Every other field the four steps draw is absent BY CONSTRUCTION rather than
 * filtered out downstream: a payload carrying `deposit_disposition` or
 * `refund_method` is refused WHOLE by the endpoint, and a screen that stripped
 * them before sending would be the same lie one layer down.
 *
 * ⚠ **`reason` LEFT THAT LIST ON 2026-09-20** (PO ruling of that date, option
 * A). `MOVE_OUT_FIELDS` accepts it and it lands in `accounts.close_reason`.
 */
export function moveOutPayload(
  movedOutOn: string,
  /**
   * ⚠ **BR-CUS-021's FINAL READS — ADDED 2026-08-26 (CR-038 W9 task 4).** The
   * docstring above listed `final_reads` among the fields *"absent BY
   * CONSTRUCTION"* because the endpoint refused them; `MOVE_OUT_FIELDS` accepts
   * them now and they commit through `seams.commit_event_reads` with the event
   * `move_out`, BEFORE the close, so `accounts.final_read_state` and the
   * BR-CUS-031 handoff read the heads this very commit produced.
   *
   * `deposit_disposition` and `refund_method` are STILL absent by
   * construction, and for the same unchanged reasons.
   */
  reads: ReadsDraft = {},
  /**
   * ⚠ **THE FIELD VISIT — CR-070 wave P, `US-WRK-039`, `BR-WRK-055`.** What the
   * clerk elected on STEP 2. `MOVE_OUT_FIELDS` accepts `field_visit`; the raise
   * happens AFTER the account is closed and settled, so a job that cannot be
   * created cannot stop somebody moving out.
   *
   * ⚠ **THE WHOLE ELECTION SINCE `DEF-CUS-6487`, NOT A LIST OF TEMPLATE IDS.**
   * It is `fieldVisitPayload`'s output — `{none: true}`, or `{orders: [...]}`,
   * or `undefined` when there is nothing to say — built by the ONE function the
   * move-in and the transfer also call, so three flows cannot drift on what a
   * field visit looks like on the wire. The door reads all three parts.
   */
  fieldVisit: Record<string, unknown> | undefined = undefined,
  /**
   * ✅ **WHY THIS TENANCY ENDED — PO ruling 2026-09-20, option A.** One of
   * `CLOSE_REASONS`, landing in `accounts.close_reason`. The wizard requires
   * it; this builder does not, because its other callers (the tests, and any
   * future door) must still be able to build a lawful payload without one.
   */
  reason: string = "",
): Record<string, unknown> {
  // ⛔ The key is OMITTED, never `[]`: an empty list is refused on purpose
  // (`customers.event_reads.rows_required`) and a move-out that took no
  // readings is lawful. `field_visit` is omitted for its own version of the
  // same reason — no visit needed is the ordinary answer and sending an empty
  // election would put a key on the wire that means nothing.
  return {
    moved_out_on: movedOutOn,
    ...readsPayloadPart("final_reads", reads),
    ...(fieldVisit === undefined ? {} : { field_visit: fieldVisit }),
    // ⛔ OMITTED WHEN EMPTY, for `field_visit`'s reason one line up: a `""` on
    // the wire is a value the far end has to test for, and a key that is
    // simply absent is not. `_clean_close_reason` treats both alike, and this
    // is the side that gets to not rely on that.
    ...(reason === "" ? {} : { reason }),
  };
}

/**
 * BR-CUS-031: the four elements of the handoff that have no source in this
 * repository, paired with the SERVER's own rule id for each. Read off the
 * record rather than typed here, so a screen can never cite a rule the server
 * did not (the `plan_snapshot_unavailable` posture, one layer out).
 */
export function handoffGaps(handoff: FinalBillHandoff): { labelKey: string; ruleRef: string }[] {
  return [
    // ⚠ **FINAL READS DROPS OUT WHEN IT IS SERVED (2026-08-26, CR-038 W9 task
    // 4).** This entry was unconditional and `final_reads_unavailable` was
    // typed non-nullable, so a move-out that DID commit its closing readings
    // would still have listed them as a gap the product could not fill — the
    // pessimistic direction of hard-won law 1, and the one nobody checks.
    // FIVE became four-or-five, decided by the SERVER's own rule id.
    ...(handoff.final_reads_unavailable === null
      ? []
      : [
          {
            labelKey: "customers.moveOut.handoff.finalReads",
            ruleRef: handoff.final_reads_unavailable,
          },
        ]),
    {
      labelKey: "customers.moveOut.handoff.planSnapshot",
      ruleRef: handoff.plan_snapshot_unavailable,
    },
    {
      labelKey: "customers.moveOut.handoff.interest",
      ruleRef: handoff.deposit_interest_unavailable,
    },
    {
      labelKey: "customers.moveOut.handoff.disposition",
      ruleRef: handoff.deposit_disposition_unavailable,
    },
    {
      labelKey: "customers.moveOut.field.refundMethod",
      ruleRef: handoff.refund_method_unavailable,
    },
  ];
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface MoveOutWizardProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function MoveOutWizard(props: MoveOutWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);

  // ══════════════════════════════════════════════════════════════════════════
  // TWO WAYS IN, ONE WIZARD — PO ruling 2026-08-26 ("-Enable Move in /move out")
  // ══════════════════════════════════════════════════════════════════════════
  // `/accounts/:accountId/move-out` — the account arrived in the URL from S21,
  // and step 1 CONFIRMS it. Unchanged; nothing that worked before stops.
  //
  // `/move-outs/new` — nothing arrived, so step 1 FINDS it. This is the entry
  // point the Accounts header was missing; the file header's departure 1 ("step
  // 1 does not search") described the account-scoped road and is now half of
  // the story rather than all of it.
  //
  // ⚠ **EVERY STEP AFTER THE FIRST IS THE SAME CODE READING THE SAME STATE.**
  // The only thing the two roads disagree about is where `accountId` comes
  // from, so there is no second flow to keep in step with this one.
  const routeAccountId = params.accountId ?? "";
  const standalone = routeAccountId === "";
  // DEF-732's own note, one flow over: what the clerk TYPED is held by the
  // WIZARD and not by step 1, because the step's content unmounts on the way to
  // step 2 and a search term that vanished on the way back would look like the
  // wizard forgot the account.
  const [accountTerm, setAccountTerm] = useState("");
  const [pickedAccountId, setPickedAccountId] = useState("");
  const accountId = standalone ? pickedAccountId : routeAccountId;
  // The forward fence is the step itself: a user can always go BACK to a step
  // they have been on, and forward only through Continue (BR-SHL-018).
  const step = moveOutStepFromParam(searchParams.get(STEP_PARAM));
  const nav: WizardNavState = { step, reached: step };
  function setStep(next: WizardNavState): void {
    const query = new URLSearchParams(searchParams);
    query.set(STEP_PARAM, String(next.step));
    setSearchParams(query, { replace: true });
  }
  const [movedOutOn, setMovedOutOn] = useState("");
  const [result, setResult] = useState<AccountMoveOutResult | null>(null);
  // A9: `?park=1`, exactly like `?step=` — a reload mid-park keeps the form.
  const parkOpen = searchParams.get(PARK_PARAM) === "1";
  function setParkOpen(open: boolean): void {
    const query = new URLSearchParams(searchParams);
    if (open) {
      query.set(PARK_PARAM, "1");
    } else {
      query.delete(PARK_PARAM);
    }
    setSearchParams(query, { replace: true });
  }

  const cell = useAccessCell(ACCOUNTS_PERMISSION, client);
  // BR-SHL-025: "Full" writes; anything else renders the flow with the reason.
  // The server refuses regardless — this only saves a round trip.
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("customers.accounts.rbac.readOnly");

  const detailQuery = useQuery({
    queryKey: accountDetailQueryKey(accountId),
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
  });

  // The PUBLISHED account search (BR-CUS-053) — account #, customer #, customer
  // name, service address and meter #, in the tenant's own RLS scope. The same
  // hook `TransferWizard` and `DisconnectWizard` call, and NO new endpoint:
  // `accountFinder.tsx` reports that finding at length.
  const accountSearch: AccountSearchState = useAccountSearch(accountTerm, client);

  // ⚠ **THE TENANT'S OWN CATEGORY NAMES, SO `Type` SHOWS A NAME AND NOT A CODE
  // (B14 rule 31).** `account_type` is a platform category CODE on the wire;
  // the list is the tenant's and is read once here rather than inside the
  // panel, so the panel stays a pure render and the query is not re-issued on
  // every step. The fallback is the CODE and never an invented label —
  // `DEF-684` is what inventing one costs.
  const accountCategories = useAccountCategories(client);

  // ── CR-038 W9 task 4 · BR-CUS-021's final reads ───────────────────────────
  const unitId = detailQuery.data?.unit_id ?? "";
  const unitAssetsQuery = useQuery({
    queryKey: unitAssetsQueryKey(unitId),
    queryFn: () => getUnitAssets(unitId, client),
    enabled: unitId !== "",
  });
  // ⚠ **SEEDED, NOT EMPTY (`OQ-394`, PO 2026-08-27: *"(a) Box opens with 42,864
  // in it"*).** `useReadsDraft` fills every readable register with its prior
  // final the moment the unit's assets arrive, so the draft the payload is
  // built from IS the draft the boxes render. Both wizards call the one hook:
  // a prefill that shipped on move-out and not move-in is how BR-CUS-021 came
  // to mean two things in the first place.
  const [readsDraft, setReadsDraft] = useReadsDraft(unitAssetsQuery.data);

  // ══════════════════════════════════════════════════════════════════════════
  // THE MASTER VARIANT — `01M-find-account-master.png` · `02M-…-master.png`
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **A MASTER MOVE-OUT IS NOT A SPECIAL FLOW. It is the ordinary flow with
  // ONE GATE AT THE FRONT** (PO 2026-09-24: *"if master account dont have any
  // active child acounts in that case - go to next step"*). So these two reads
  // are the only things that differ, and they are DISABLED on a regular
  // account rather than branched around.
  //
  // ⚠ **BOTH ARE READS THE PRODUCT ALREADY MAKES, on purpose.** The tenants
  // come from the same `GET /accounts?f.premises_id=` the Master-accounts tab
  // lists, and the units from the same `GET /units?f.premises_id=` the Units
  // list serves — which is what the PO meant by *"we have unit states to be
  // used for it"*. `detail.sub_accounts` was NOT used: it carries
  // `{id, account_no, unit_id}` and the drawn table has six columns, so
  // mounting it over that payload would render three empty columns and report
  // success (`DEF-CUS-6487`'s shape on a read).
  //
  // ⚠ **A MASTER HANGS OFF THE ADDRESS AND NAMES NO UNIT** (`BR-CUS-1010`),
  // which is why both filter on the PREMISES and neither on a link from the
  // account. Children follow the BUILDING.
  const isMaster = (detailQuery.data?.kind ?? "") === "master";
  const masterPremisesId = isMaster ? (detailQuery.data?.premises_id ?? "") : "";
  const masterAccountsQuery = useQuery({
    queryKey: ["move-out-master-accounts", masterPremisesId],
    queryFn: () =>
      getAccounts({ per: 200, filters: { premises_id: masterPremisesId } }, client),
    enabled: masterPremisesId !== "",
    retry: false,
  });
  const masterUnitsQuery = useQuery({
    queryKey: ["move-out-master-units", masterPremisesId],
    queryFn: () => getUnits({ per: 200, filters: { premises_id: masterPremisesId } }, client),
    enabled: masterPremisesId !== "",
    retry: false,
  });
  const masterAccounts = masterAccountsQuery.data?.results ?? [];
  const masterUnits = masterUnitsQuery.data?.results ?? [];

  // ── THE REFUSAL'S TWO COUNTS — ONE derivation, read by the screen AND the
  //    gate, because a gate that can disagree with the sentence above it
  //    refuses a clerk for a reason the screen does not name.
  //
  // ⚠ **ACTIVE IS THE STATUS'S BEHAVIOUR CLASS AND MUST NOT BE RE-DEFINED
  // HERE** (`BR-CUS-055`, `BR-CUS-171`). `sub_accounts_for_master` keys off it
  // server-side, so a closed tenant drops out the day they close and a pending
  // one never counts. `TERMINAL_BEHAVIOR_CLASS` is the shared vocabulary; this
  // reads the row's own `status` against it rather than minting a second list.
  // ⚠ **`detailQuery.data`, NOT `detail` — `detail` IS DECLARED 350 LINES
  // BELOW THIS AND A `const` IN ITS TEMPORAL DEAD ZONE THROWS AT RUNTIME.**
  // This read `detail?.id` and white-screened the whole master wizard with
  // *"Cannot access 'ma' before initialization"* — a ReferenceError inside
  // `Array.filter`, so nothing rendered at all. **`tsc` was clean and all 71
  // wizard cases were green**, because no case mounts a MASTER and nothing in
  // this repository reads rendered output (hard-won law 6). It was found by
  // opening the screen in a browser, which is the only check there is.
  const masterActiveTenants = masterAccounts.filter(
    (row) => row.id !== detailQuery.data?.id && (row.status ?? "") === "active",
  ).length;
  // ⚠ **AN EMPTY FLAT IS NOT NEUTRAL — it is a live monthly charge with
  // nowhere to go.** `base_charge_only_coverage` puts every unit with NO
  // OCCUPYING ACCOUNT onto the owner's bill — *"the exclusion test is the
  // ACCOUNT, never a flag"* — so what counts is a unit with no account, and
  // not a flag saying *vacant*.
  const masterEmptyUnits = masterUnits.filter((row) => (row.account_no ?? "") === "");
  const masterUnitsStillBilling = masterEmptyUnits.length;
  const masterRefused = isMaster && (masterActiveTenants > 0 || masterUnitsStillBilling > 0);

  // ══════════════════════════════════════════════════════════════════════════
  // THE FINAL-BILL PREVIEW — the keystone of steps 3, 4 and 5 (PO 2026-09-19)
  // ══════════════════════════════════════════════════════════════════════════
  // `GET /accounts/{id}/final-bill-preview?moved_out_on=` prices the closing
  // window through the bill run's OWN stages 1–5 and **writes nothing** — no
  // invoice, no journal line, no bill number — which is what makes it safe
  // inside a wizard a clerk may abandon. Its `total` is then STATED to
  // `close-impact`, which is the term the settlement has always required and
  // that no caller in this product ever supplied.
  //
  // ⚠ **KEYED ON THE MOVE-OUT DATE**, because the date IS the window's end
  // (BR-CUS-056) and the day the deposit interest accrues to. A clerk who
  // corrects the date on step 2 gets a re-priced figure on step 3 rather than
  // yesterday's answer about a different period.
  // ⚠ **STEP 3 PRICES WHAT STEP 2 KEYED — PO 2026-09-20, *"option b is
  // correct"* (`DEF-CUS-5931`).** The reads are read from the SAME draft the
  // step-6 payload is built from (`eventReadRows`, one derivation), so the
  // figure on screen and the bill Billing later raises come from one set of
  // registers. Nothing is written here: the reads still commit with the close,
  // in the one transaction, exactly as blueprint p111 requires.
  const keyedReads = eventReadRows(readsDraft);
  const previewPort = finalBillPreviewPort(client);
  const previewQuery = useQuery({
    queryKey: finalBillPreviewQueryKey(accountId, movedOutOn, keyedReads),
    queryFn: () => previewPort.read(accountId, movedOutOn, keyedReads),
    enabled: accountId !== "" && movedOutOn !== "",
    // The route may not be mounted on this deployment yet. An absent preview
    // is a STATED ABSENCE on step 3, never a retry storm and never a figure.
    retry: false,
  });
  const preview: FinalBillPreview | null = previewQuery.data ?? null;

  /** What the clerk has keyed, so step 5's *Final reads* is a fact. */
  const readsSummary = readsProgress(readsDraft);

  // ── CR-070 wave P · the field visit (US-WRK-039, BR-WRK-055) ──────────────
  //
  // ⚠ **ON STEP 2 AND NOT STEP 4 — `DEF-WRK-3725`, and it is worth the four
  // lines.** The wave plan put this panel on step 4. `MOVE_OUT_STEPS[3]` is the
  // SHORTFALL step and it carries `conditional: true` (`moveShared.tsx`): on a
  // move-out that settles cleanly — the common case — it renders greyed and
  // *skipped*, so the control would have been invisible on the very move-outs
  // that need it. Step 2 is *Date & final reads*, which is where a clerk is
  // already deciding whether somebody has to go and read the meter.
  // ⛔ **THE TEMPLATE OFFER QUERY WENT WITH `RaiseFieldWork` (2026-09-24).**
  // `GET /field-work/offer?flow=move_out` served the utility's PUBLISHED
  // templates and nothing else, so at a utility that has published none — most
  // of them — the panel it fed was empty. `FieldVisitOrders` reads its own job
  // types and crews from Work's catalogue, which every tenant has. The endpoint
  // is untouched and still serves the disconnect flow.
  // `DEF-CUS-6487` — the WHOLE election now, not a list of template ids: the
  // rows a clerk adds, and *No visit needed* as an answer in its own right.
  // The door was widened to read all three in the same commit; before that it
  // parsed `orders` out of the payload and threw them away, which would have
  // made this table a live control over a door that raised nothing.
  const [fieldVisit, setFieldVisit] = useState<FieldVisitValue>(emptyFieldVisit);
  /** Continue has been pressed on step 2 — only then is a row refusal red. */
  const [visitTried, setVisitTried] = useState(false);
  /** `DEF-CUS-10051` — Continue pressed on step 2, so a missing reading is red. */
  const [readsTried, setReadsTried] = useState(false);

  // ✅ **WHY THIS TENANCY ENDED — PO ruling 2026-09-20, option A.** `""` until
  // the clerk chooses; `reasonTouched` turns the field red only once they have
  // pressed Continue, so it is never red before they have had a chance.
  const [closeReason, setCloseReason] = useState("");
  // `DEF-CUS-10190` — the parked move-in this move-out was raised from
  // (`POST /move-ins/handover` wrote it on the draft); `""` for an ordinary one.
  const [fromMoveIn, setFromMoveIn] = useState("");
  const [reasonTouched, setReasonTouched] = useState(false);
  // `CR-185-BRC10` — the shortfall path step 3's server RECORDED. Only
  // `transfer` travels on the commit: the move-out posts the tie-back.
  const [shortfallPath, setShortfallPath] = useState<string | null>(null);

  // ⚠ **A REF, FOR THE HOOK-ORDER REASON `MoveInWizard` RECORDS AT LENGTH
  // (`CR-122-BRC06`).** `useWizardPark` must sit below every early return and
  // this mutation is declared above it, so reading `park.parkedId` here would
  // be a use-before-declare. The effect just under the hook syncs the ref, and
  // the mutation reads it at CLICK time — long after any render has settled.
  const parkIdRef = useRef<string | null>(null);

  const queryClient = useQueryClient();
  const close = useMutation({
    mutationFn: () =>
      moveOutAccount(
        accountId,
        {
          ...moveOutPayload(movedOutOn, readsDraft, fieldVisitPayload(fieldVisit), closeReason),
          // `CR-185-BRC10` — POSTED AT COMMIT: the tie-back rides the commit.
          ...(shortfallPath === "transfer" ? { shortfall_path: "transfer" } : {}),
          // PO ruling 2026-09-20 item 9 — the draft this move-out was keyed
          // into, so the finished record ADOPTS its `MVO-` number rather than
          // being filed under a second one the clerk was never told. OMITTED
          // rather than sent empty, exactly as `MoveInWizard` omits it.
          ...(parkIdRef.current === null || parkIdRef.current === ""
            ? {}
            : { wizard_park_id: parkIdRef.current }),
        },
        client,
      ),
  });

  /**
   * ✅ **THE CLOSE IMPACT IS READ FROM THE MOUNTED ROUTE — DEF-669.**
   *
   * ⛔ **WHAT STOOD HERE WAS FALSE, AND IT WENT FALSE ON THE COMMIT THAT
   * MOUNTED THE ROUTE.** This comment read *"`GET /accounts/{id}/close-impact`
   * … is NOT MOUNTED — grep the repository and the only hits are that table"*,
   * and `closeImpactPort()` returned `null` to match. Both were accurate on
   * 2026-08-24 and both were wrong from 2026-08-25, when
   * `apps/customers/api.py` mounted the four W5 routes. The screen went on
   * telling a clerk the feature was unbuilt for two days. Hard-won law 1: a
   * string describing an absence is not a plan, and it must change with the
   * fact it describes — nothing in this repository makes that check
   * systematic, because the lane that mounts a route has no reason to grep the
   * frontend for prose about it.
   *
   * ⚠ **WHAT IS STILL ABSENT IS NARROWER, AND IT IS PER FIELD.**
   * `settlement_for` serves the LANDING, `open_sub_accounts` and B19 §15.9's
   * money. Six of task 5.7's impact fields belong to other modules and are
   * served by nobody: they arrive as an explicit `null` and each panel states
   * its own absence (see `moveShared.closeImpactPort`). No figure is derived
   * client-side — inventing the five landings here would be inventing money
   * (CLAUDE.md #2).
   */
  const impactPort = closeImpactPort(props.client);
  // ═══════════════════════════════════════════════════════════════════════════
  // 🔒 **THE TWO STATED TERMS, DECLARED ONCE FOR THE READ AND THE WRITE —
  //    `DEF-CUS-5927`.**
  // ═══════════════════════════════════════════════════════════════════════════
  // The settlement invents neither term, so BOTH calls have to state them and
  // **they have to be the same two values**. Step 4's `POST
  // /accounts/{id}/settle-shortfall` sent `{path}` alone until 2026-09-19: the
  // server re-derived the settlement without a final bill, landed on `null`
  // and refused `customers.move_out.no_shortfall` — on a screen that was at
  // that moment printing `Short by $1,591.85` from the read that DID state it.
  //
  // **One object, both call sites.** Two expressions would be two chances to
  // drift, and the whole defect is two halves disagreeing about one customer's
  // money. `CloseImpactTerms` is the read's own type, reused rather than
  // re-declared for the same reason.
  const statedTerms: CloseImpactTerms = {
    finalBill: preview?.total ?? null,
    // BR-CUS-057 accrues TO the move day, and gate G6 keeps a clock off a
    // money path: the date is the clerk's stated business fact, never now.
    asOf: movedOutOn === "" ? null : movedOutOn,
  };
  const impactQuery = useQuery({
    // ⚠ **THE STATED TERMS ARE PART OF THE KEY.** They change the answer — a
    // settlement read with a final bill is a different settlement from one
    // read without it — so a shared key would serve step 3 the landing-less
    // version it had cached before the preview arrived.
    queryKey: closeImpactQueryKey(accountId, statedTerms.finalBill ?? null, movedOutOn),
    queryFn: (): Promise<CloseImpact | null> => impactPort.read(accountId, statedTerms),
    enabled: accountId !== "",
  });
  const impact: CloseImpact | null = impactQuery.data ?? null;

  // What an EMPTY unit bills to this master each month. The per-service
  // standing charges are the settlement's, summed by `vacantChargesLine`; a
  // unit somebody occupies bills nothing here, which is a dash and not a zero.
  const masterVacantCharge = vacantChargesLine(impact?.vacant_base_charges ?? null);
  const masterBillsHere = (unit: UnitRow): { amount: string; currency: string } | null =>
    (unit.account_no ?? "") !== "" || masterVacantCharge === null
      ? null
      : { amount: masterVacantCharge.total, currency: masterVacantCharge.currency };

  const landing = landingOf(impact);
  // `BR-CUS-1082` — a master with open children is WARNED, not refused (PO
  // ruling 2026-09-20 closing `OQ-CUS-12515` on option (b)). **The count is
  // the settlement's own `open_sub_accounts`**, the field `settlement_for` has
  // served since `CR-056` W6, so the screen and `services.move_out` say ONE
  // number and cannot disagree about who a child is
  // (`selectors.sub_accounts_for_master`, `BR-CUS-171`).
  //
  // ⚠ **THERE IS DELIBERATELY NO `hasOpenSubAccounts` FLAG ANY MORE.** It
  // existed to gate step 1's `validate`, and a derived boolean left behind
  // after the thing it gated is gone is how a refusal grows back by accident.
  // The count is read where it is DRAWN, and nowhere else.

  // ══════════════════════════════════════════════════════════════════════════
  // CR-035 — PARK AND RESUME, ABOVE EVERY EARLY RETURN (see MoveInWizard)
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **AND THIS IS THE FLOW THE RULING'S STATED COST IS ABOUT.** BR-SHL-048 (c)
  // accepts, in writing, that *"a parked move-out is invisible, so the account
  // KEEPS BILLING and nobody downstream knows a closure is coming."* Nothing on
  // this screen may soften that: no status change, no flag on the account, no
  // hint on the unit. The remind-on date and the age on the "Waiting on" list
  // are the whole of the mitigation the PO chose.
  const park = useWizardPark({
    steps: MOVE_OUT_STEPS,
    step,
    // ⚠ **THE OLD→NEW MAP, PASSED RATHER THAN LEFT TO THE CLAMP.** This flow
    // went SIX steps to FOUR on 2026-09-24, so a draft parked before today
    // carries an index off the old list. The clamp is right by luck on five of
    // those six numbers and wrong on the one that matters: old 4 — *The
    // shortfall* — is in range for a four-step list, so it passes straight
    // through onto *Review & close*, one step PAST the money step it belongs
    // on. See `moveOutStoredStep`'s own six-row table.
    storedStep: moveOutStoredStep,
    parkOpen,
    context: {
      flow: "move_out",
      // The account as the clerk knows it — number and name, copied, never a
      // join (BR-SHL-048 (a)).
      subjectLabel:
        detailQuery.data === undefined ? "" : accountHeadline(detailQuery.data, translate),
      subjectRef: { account_id: accountId === "" ? null : accountId },
      values: {
        account_id: accountId,
        account_term: accountTerm,
        moved_out_on: movedOutOn,
        // PO ruling 2026-09-20 item 3 — parked with the rest of what was
        // typed. BR-SHL-048 (b): a draft holds the FORM and nothing is
        // written outside the draft store, so this is the clerk's answer kept
        // for them, never a reason recorded against the account.
        close_reason: closeReason,
        // DEF-CUS-10190 — kept on the draft so a park and a resume keep it.
        [FROM_MOVE_IN_VALUE]: fromMoveIn === "" ? null : fromMoveIn,
      },
    },
    t: translate,
    client,
    // BR-SHL-048 (b): the search TERM and the chosen id come back; the account
    // itself does not. `detailQuery` re-reads it, so a balance settled while
    // this sat parked is today's balance and not the parked one.
    onHydrate: (row) => {
      setAccountTerm(parkedString(row.values, "account_term"));
      setPickedAccountId(parkedString(row.values, "account_id"));
      setMovedOutOn(parkedString(row.values, "moved_out_on"));
      // ⚠ **RESUMED WITH THE REST, AND FORGETTING IT WOULD HAVE BEEN THE
      // EXACT DEFECT THIS RULING CLOSES ONE LAYER DOWN** — a clerk who picked
      // a reason, parked, and came back to an empty select would have been
      // asked twice and believed the first answer was stored.
      setCloseReason(parkedString(row.values, "close_reason"));
      setFromMoveIn(parkedString(row.values, FROM_MOVE_IN_VALUE));
    },
    // CR-035 · AMENDMENT 1 (PO 2026-08-26) — a parked draft lands on the tab
    // for its OWN kind of work, not on a ninth queue. `parkedHomePath` is the
    // one place those five destinations are named.
    onParked: () => navigate(tenantPath(parkedHomePath("move_out"))),
  });
  // `DEF-SHL-10001` — the leave-page popup's *Save as draft* writes the
  // same `wizard_parks` row this wizard's Park writes, as a draft.
  const leaveDraft: LeaveDraft = {
    onSave: park.saveDraft,
    savedMessage: t("leaveGuard.saved", { place: t("customers.accounts.tab.moveOuts") }),
  };
  // PO ruling 2026-09-20 item 9 — see `parkIdRef`. `park.parkedId` is
  // `?parked=`, which is set the moment a draft is written, so from that point
  // on the commit can hand the server the draft whose number it should adopt.
  useEffect(() => {
    parkIdRef.current = park.parkedId;
  }, [park.parkedId]);

  /**
   * CR-030 W5 task 5.1 · BR-SHL-047 · CR-035 — the two controls, once, on the
   * frame, and **they stay two** (B19 §12.2). `Save & exit` writes nothing;
   * `Park` records what is being waited on, a note and a reminder.
   *
   * ⚠ **DECLARED ONCE FOR BOTH ROADS**, above the early returns: the
   * no-account-yet road used to build its own inline `exit` with a stub
   * `onPark`, and two park paths is how one of them quietly stops working.
   */
  const exit: WizardExit = {
    // The standalone road has no account page to return to until one is chosen
    // — and once it is, the account IS where a clerk expects to land.
    onSaveAndExit: () =>
      navigate(tenantPath(accountId === "" ? MOVE_OUTS_TAB_PATH : accountDetailPath(accountId))),
    parkBlockedReason: parkStoreBlockedReason(translate),
    parkOpen,
    onParkOpenChange: setParkOpen,
    onPark: park.onPark,
    dateFormat,
    // ✅ BR-SHL-047's open half is SETTLED by BR-SHL-048 (c) and in the opposite
    // direction: a parked move-out holds NOTHING, so no wizard can block
    // anything. The age is still rendered — it is what stops a draft sitting
    // forever — and no limit is invented, because none was ruled.
    parkedAt: park.parkedAt,
  };

  async function commit(): Promise<WizardCommitOutcome> {
    try {
      const answered = await close.mutateAsync();
      // `DEF-CUS-10193` — the account this browser cached as Active, and the
      // unit's move-in reads, are forgotten before anything reads them again.
      void forgetTenancyAfterMoveOut(queryClient, { accountId, unitId, moveInParkId: fromMoveIn });
      setResult(answered);
      fireToast(t("customers.moveOut.toast", { account: answered.account_no ?? "" }));
      return { ok: true };
    } catch (error) {
      // BR-SHL-020: the server's own message_key through the catalog — this is
      // where BR-CUS-030's "not an occupant", BR-CUS-055's "that status does
      // not close" and BR-BIL-004's "behind an issued bill" reach the user,
      // with the date they entered still on screen (the frame keeps it).
      return { ok: false, reason: moveOutRefusalText(error, translate) };
    }
  }

  if (isDenied(cell)) {
    // BR-SHL-003 / A18 §6: a surface this role cannot reach is not drawn.
    return (
      <PermissionDenied
        helper={t("customers.accounts.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  // ⚠ **THE WHOLE-PAGE STATES BELONG TO THE ACCOUNT-SCOPED ROAD ONLY.** With an
  // account in the URL there is nothing else this page could be doing, so a
  // skeleton or a failure card IS the page. On `/move-outs/new` the same two
  // facts are about ONE FIELD in a flow the clerk is standing in — replacing the
  // wizard with a failure card there would throw away the search box that is the
  // way out of the failure. So they render INSIDE step 1 instead (the shape
  // `DisconnectWizard` already uses for its own finder).
  if (!standalone) {
    if (detailQuery.isPending) {
      return <LoadingSkeleton variant="card" />; // A18 §3
    }
    if (detailQuery.data === undefined) {
      if (isPermissionDenied(detailQuery.error)) {
        return (
          <PermissionDenied
            helper={t("customers.accounts.denied")}
            onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
          />
        );
      }
      // A cross-tenant id and an unknown id are ONE answer server-side (HR-1).
      return (
        <FailedWithRetry
          title={t("customers.account.detail.failedTitle")}
          reason={apiErrorText(detailQuery.error, translate)}
          onRetry={() => void detailQuery.refetch()}
          onDownloadReport={() => undefined}
          onCancel={() => navigate(tenantPath(ACCOUNTS_ROUTE))}
        />
      );
    }
  }

  // Null ONLY on the standalone road with nothing chosen yet (or with a chosen
  // account still in flight / refused) — the guard above returns before this
  // line whenever an account came from the URL.
  const detail: AccountDetail | null = detailQuery.data ?? null;

  // The commit answered. The wizard is REPLACED rather than navigated away
  // from, because the nine warnings are the point of this screen: they are the
  // honest statement of what a move-out did not do, and a toast on the way to
  // another page shows none of them.
  if (result !== null) {
    return (
      <MoveOutDone
        result={result}
        t={translate}
        timeZone={timeZone}
        dateFormat={dateFormat}
        backToMoveIn={fromMoveIn === "" ? null : moveInResumePath(fromMoveIn)}
      />
    );
  }

  // BR-CUS-030: only an OCCUPANT can move out — said before the commit rather
  // than discovered by it (the S18 step-3 precedent).
  const occupant = detail !== null && isOccupyingAccount(detail);

  /** The standalone road's step 1, or null on the account-scoped one. */
  const finder = !standalone ? null : (
    <MoveOutAccountPick
      term={accountTerm}
      onTermChange={setAccountTerm}
      search={accountSearch}
      value={pickedAccountId}
      onChange={setPickedAccountId}
      detail={detail}
      loading={detailQuery.isPending}
      failedReason={detailQuery.isError ? apiErrorText(detailQuery.error, translate) : null}
      t={translate}
    />
  );

  // ⚠ **THE RAIL KEEPS ALL SIX WHILE THE ACCOUNT IS UNCHOSEN — BR-SHL-046.**
  // The step number is an INDEX (a Move-outs row reopens this wizard AT one), so
  // a step that vanished would misaddress every step after it. Each later step
  // says what it is waiting for and refuses to validate, which is what stops
  // Continue rather than a missing rail segment.
  if (detail === null) {
    const pending: WizardStep[] = MOVE_OUT_STEPS.map((defn, index) => ({
      id: defn.id,
      label: t(defn.labelKey, { defaultValue: defn.en }),
      content:
        index === 0 && finder !== null ? (
          finder
        ) : (
          <PickFirstNote>
            {t("customers.moveOut.find.pickFirst", {
              defaultValue: "Find the account above first — the rest of the move-out is about it.",
            })}
          </PickFirstNote>
        ),
      validate: () => false,
    }));
    return (
      <MoveOutShell
        backTo={{
          to: tenantPath(MOVE_OUTS_TAB_PATH),
          label: t("customers.accounts.tab.moveOuts"),
        }}
        writeBlockedReason={writeBlockedReason}
        step={step}
        nav={nav}
        onNavChange={setStep}
        steps={pending}
        // Nothing can be committed with no account, and the frame never reaches
        // its commit anyway — every step above refuses to validate.
        onCommit={() =>
          Promise.resolve({
            ok: false,
            reason: t("customers.moveOut.find.pickFirst", {
              defaultValue: "Find the account above first — the rest of the move-out is about it.",
            }),
          })
        }
        exit={exit}
        saveDraft={leaveDraft}
        t={translate}
      />
    );
  }

  const steps: WizardStep[] = [
    {
      id: "account",
      label: t("customers.moveOut.step.account"),
      content: (
        <>
          {finder}
          <AccountStep
            detail={detail}
            occupant={occupant}
            picked={standalone}
            // ⚠ **NOT ON A MASTER — the refusal below already says it, with
            // BOTH counts.** `BR-CUS-1082`'s warning is for a REGULAR account
            // with open children, which the PO ruled a clerk may walk past
            // (`OQ-CUS-12515` option (b)). On a master the same fact is a
            // REFUSAL, and stating it twice in two tones is B14 rule 32's
            // *a row never repeats what its own control offers* — worse here,
            // because one of the two says "walk past" and the other says
            // "you cannot".
            openSubAccounts={isMaster ? null : (impact?.open_sub_accounts ?? null)}
            categories={accountCategories.all}
            t={translate}
            timeZone={timeZone}
            dateFormat={dateFormat}
          />
          {/* ── THE MASTER VARIANT — `01M-find-account-master.png` ──────────
              The SAME panel with `Kind: Master`, then the refusal, then the
              table of accounts on this master with a Close link per row.
              Continue is dead while either condition holds; with neither, the
              flow continues exactly as a regular account's. */}
          {isMaster && (
            <>
              <MasterCannotClose
                activeTenants={masterActiveTenants}
                unitsStillBilling={masterUnitsStillBilling}
                t={translate}
              />
              <AccountsOnThisMaster
                rows={masterAccounts}
                selfId={detail.id}
                closeHref={(id) => tenantPath(accountMoveOutPath(id))}
                t={translate}
              />
            </>
          )}
        </>
      ),
      // ⚠ **`BR-CUS-1082` IS NOT IN THIS PREDICATE, AND ITS ABSENCE IS THE
      // RULING (PO 2026-09-20, `OQ-CUS-12515` option (b)).** Open
      // sub-accounts used to stand here beside `occupant` and stop the
      // clerk; they are now a WARNING the clerk may walk past, drawn by
      // `AccountStep` below. `occupant` stays, because BR-CUS-030 really
      // does refuse a non-occupant at the commit and step 1 is the courtesy
      // that says so early — the split this line has always taken. Putting
      // the count back here would re-refuse a lawful act the PO permitted.
      // ⚠ **THE MASTER'S GATE IS *AND*-ed ON TOP OF `occupant`, AND IT IS THE
      // SAME COUNTS THE SCREEN SHOWS.** The PO ruled *refuse* twice in two
      // worked cases (*"(b) Refuse until they're closed"* and *"its not
      // allowed - refule the move out"*), so a master cannot pass step 1 while
      // any tenant is active or any empty unit still bills to it. **The screen
      // and the gate read ONE derivation** — a gate that can disagree with the
      // sentence above it is how a clerk is refused for a reason the screen
      // does not name.
      // ⚠ **A REFUSED MASTER RETURNS THE SENTENCE, NOT `false`.**
      // `WizardStepVerdict` is `boolean | string`, and a bare `false` stops the
      // step SILENTLY — a clerk presses Continue, nothing happens, and they
      // press it again. The drawing greys Continue out; the shared frame every
      // one of the fifteen wizards mounts offers no disabled-Continue, and
      // changing that contract is not this lane's (REPORTED). Saying WHY on
      // the press is the honest half of the same thing, and it is the half
      // that matters — a control that looks live and can never succeed is
      // hard-won law 2's mirror.
      validate: () => {
        if (!masterRefused) {
          return occupant;
        }
        return t("customers.moveOut.master.refusedTitle", {
          defaultValue: "This account cannot be closed.",
        });
      },
    },
    {
      id: "date",
      label: t("customers.moveOut.step.date"),
      content: (
        <DateStep
          client={client}
          detail={detail}
          value={movedOutOn}
          problem={moveOutDateProblem(movedOutOn, detail.opened_at)}
          dateFormat={dateFormat}
          onChange={setMovedOutOn}
          reason={closeReason}
          onReasonChange={setCloseReason}
          reasonProblem={reasonTouched && closeReason === ""}
          t={translate}
          reads={readsDraft}
          onReadsChange={setReadsDraft}
          fieldVisit={fieldVisit}
          onFieldVisitChange={setFieldVisit}
          fieldVisitShowErrors={visitTried}
          readsShowErrors={readsTried}
          timeZone={timeZone}
          masterUnits={isMaster ? masterUnits : null}
          vacantBillsHere={masterBillsHere}
        />
      ),
      // ⚠ **THE REASON IS REQUIRED ON THE SCREEN AND OPTIONAL AT THE DOOR, AND
      // THAT SPLIT IS DELIBERATE** (PO ruling 2026-09-20, option A). The
      // ruling is that the wizard must stop asking and forgetting; a clerk in
      // front of the form is asked and answers. `services.move_out` still
      // accepts a move-out with no reason, because a caller with no clerk in
      // front of it — an import, a script, the scenario suite — must still be
      // able to close an account. Demanding it at the door would have turned a
      // ruling about COLLECTING a fact into a new refusal on a money path.
      //
      // `reasonTouched` is set here rather than on blur so the field goes red
      // when they press Continue, not while they are still reading it.
      validate: () => {
        setReasonTouched(true);
        // `DEF-CUS-6487` — a field-visit row with no job type is refused by the
        // server BEFORE the transaction opens, so stopping it here costs the
        // clerk nothing and keeps the refusal beside the row that caused it
        // rather than on the commit three steps later. Set on the press, not on
        // blur, so nothing is red while they are still filling it in.
        setVisitTried(true);
        // `DEF-CUS-10051` (PO 2026-10-11): a METERED row needs a reading or
        // Estimate; share and capacity rows have no register and need nothing.
        setReadsTried(true);
        return (
          moveOutDateProblem(movedOutOn, detail.opened_at) === null &&
          closeReason !== "" &&
          fieldVisitProblem(fieldVisit) === null &&
          missingFinalReads(unitAssetsQuery.data, readsDraft).length === 0
        );
      },
    },
    {
      id: "settlement",
      // ⚠ **THE STEP'S OWN NAME IS THE DRAWING'S** —
      // `03-bill-and-deposit.png` titles it *Bill & deposit*, and the rail,
      // the `Step 3 of 4 · …` line and the Move-outs tab's STEP column all
      // read the ONE declared list (`moveShared.MOVE_OUT_STEPS`, BR-SHL-046's
      // durable half), so this is only the fallback for a catalogue not yet
      // merged.
      label: t("customers.moveOut.step.settlement", { defaultValue: "Bill & deposit" }),
      content: (
        <SettlementStep
          onBackToReadings={() => setStep({ step: 2, reached: nav.reached })}
          accountId={accountId}
          detail={detail}
          preview={preview}
          impact={impact}
          terms={statedTerms}
          movedOutOn={movedOutOn}
          timeZone={timeZone}
          dateFormat={dateFormat}
          t={translate}
          onDecided={setShortfallPath}
        />
      ),
    },
    {
      id: "review",
      label: t("customers.moveOut.step.review", { defaultValue: "Review & close" }),
      content: (
        <CloseoutStep
          detail={detail}
          movedOutOn={movedOutOn}
          landing={landing}
          impact={impact}
          preview={preview}
          reads={readsSummary}
          assets={readableAssets(unitAssetsQuery.data)}
          readsDraft={readsDraft}
          dateFormat={dateFormat}
          timeZone={timeZone}
          t={translate}
        />
      ),
    },
  ];

  return (
    <MoveOutShell
      backTo={{
        to: tenantPath(accountDetailPath(accountId)),
        label: accountHeadline(detail, translate),
      }}
      writeBlockedReason={writeBlockedReason}
      step={step}
      nav={nav}
      onNavChange={setStep}
      steps={steps}
      onCommit={
        writeBlockedReason === null
          ? commit
          : // Nothing is posted from a role the server would refuse; the
            // refusal renders in the frame's own A18 §4 card.
            () => Promise.resolve({ ok: false, reason: writeBlockedReason })
      }
      exit={exit}
      saveDraft={leaveDraft}
      t={translate}
    />
  );
}

export default MoveOutWizard;

/**
 * THE PAGE AROUND THE RAIL — header, role refusal, `Step n of 6`, frame, audit
 * line — declared ONCE and rendered by BOTH roads.
 *
 * ⚠ **IT IS EXTRACTED RATHER THAN COPIED FOR ONE REASON: BR-SHL-046.** The
 * `Step n of 6` line and the rail must be driven by the same declared list, and
 * the surest way to break that is a second copy of the page that renders a
 * different header while the account is still being found. There is no second
 * copy; the unchosen road passes six refusing steps into this.
 */
function MoveOutShell(props: {
  backTo: { to: string; label: string };
  writeBlockedReason: string | null;
  step: number;
  nav: WizardNavState;
  onNavChange: (next: WizardNavState) => void;
  steps: WizardStep[];
  onCommit: () => Promise<WizardCommitOutcome>;
  /** `DEF-SHL-10001` — the leave-page popup's draft. */
  saveDraft: LeaveDraft;
  exit: WizardExit;
  t: Translator;
}) {
  const { t } = props;
  // BR-SHL-046 — ONE declared list answers the count, the rail and this line.
  const progress = flowProgress(MOVE_OUT_STEPS, props.step);
  const current = MOVE_OUT_STEPS[progress.step - 1];
  return (
    <div className="cus-page">
      {/* US-SHL-020 / BR-SHL-044: the shared header. The prototype's own kicker,
          H1 and step line, with the back link the component draws its arrow for. */}
      <PageHeader
        backTo={props.backTo}
        kicker={t("customers.moveOut.kicker")}
        title={t("customers.moveOut.title")}
        /* ⛔ **THE ROLLUP IS DELETED, NOT SHORTENED — `DEF-CUS-6480`, PO
           2026-09-24: *"too much text reduce it"*.** It was 48 words standing
           over EVERY ONE of the six steps, and B14 rule 33 puts RATIONALE —
           *"because none of them can happen yet"* — at ZERO words on screen.
           Rule 33's own instruction is that rationale is REMOVED rather than
           trimmed, so nothing replaces it.

           ⚠ **NOTHING FACTUAL IS LOST, WHICH IS WHY IT COULD GO.** The step
           COUNT and the step's NAME are rendered directly below by
           `customers.wizard.stepOfNamed` (*"Step 1 of 6 · Find account"*), and
           the rail names all six — so `{{steps}} steps` was a third statement
           of one fact, which is B14 rule 32's *a row never repeats what its own
           control offers*. The Accounts blueprint agrees: p112–p118 draw this
           page head as kicker, title and step line, and NO paragraph.

           `customers.moveOut.subSteps` is retired from all eleven catalogues
           through `10-scripts/i18n_fanin.py` in the same commit, so G18 does
           not inherit a dead key. BR-SHL-046 is untouched — it is about the
           step list driving the count, and the count still comes from it. */
      />

      {props.writeBlockedReason !== null && (
        <RefusalStrip role="alert">{props.writeBlockedReason}</RefusalStrip>
      )}

      {/* BR-SHL-046: the same index the Move-outs tab draws in its STEP column,
          read off the ONE declared step list rather than a literal. A row
          reopens this wizard at a number, so the two must address the same
          scale — `4 of 4` beside a six-step rail is DEF-648 exactly.
          ⚠ **AND THE STEP'S NAME IS THE HALF THAT WAS MISSING.** The blueprint
          (pages 98–106) writes `Step 1 of 6 · Find account` under the title of
          every one of the six screens; this line has read `Step 1 of 6` since
          it was written, so a clerk arriving at a parked draft on step 4 was
          told a number and not what the step is. The name comes off the SAME
          array as the count and the rail, which is BR-SHL-046's durable clause
          — *"driven by ONE declared step list"* — so a seventh step needs no
          edit here. A NEW key rather than a rewritten default: `…moveOut.stepOf`
          is in all eleven catalogues without the name, and a catalogue entry
          beats a `defaultValue` (the DEF-731 shape). */}
      <Note>
        {t("customers.wizard.stepOfNamed", {
          ...progress,
          name: t(current.labelKey, { defaultValue: current.en }),
          defaultValue: "Step {{step}} of {{of}} · {{name}}",
        })}
      </Note>

      {/* B13 §1 / BR-SHL-018/019: the SHARED wizard frame owns the numbered
          rail, Back/Continue, the ✓ confirm, its working state and the ONE
          transactional commit. This screen declares steps and a payload. */}
      <WizardFrame
        steps={props.steps}
        nav={props.nav}
        onNavChange={props.onNavChange}
        commitLabel={t("customers.moveOut.commit")}
        commitFailedTitle={t("customers.moveOut.commitFailed")}
        onCommit={props.onCommit}
        onCommitted={() => undefined}
        exit={props.exit}
        saveDraft={props.saveDraft}
      />

      {/* ⛔ **THE AUDIT LINE IS DELETED, NOT SHORTENED — `DEF-CUS-6550`.**
          It read *"Closing an account is recorded in the audit log by the
          server, with who, when, and everything that changed."* — NINETEEN
          words under the footer of every step of ACC-06, and its whole job
          was to reassure a clerk about how the product works. That is
          RATIONALE, and B14 rule 33 puts rationale at ZERO words on screen.

          ⚠ **RULE 33 DOES NAME *an audit line* AMONG ITS SIX-WORD FACTS, so
          deleting rather than trimming is a JUDGMENT and is recorded as one**
          (decision log 2026-09-24). The kinds are told apart by what the
          sentence is FOR: a fact says something about THIS record — who
          closed it, when — and this one says nothing about this account at
          all. It is a promise about the system, which a clerk cannot act on
          and did not ask for. The repo's own precedent is deletion:
          `CorrectionRetentionNote` and the transfer wizard's six sentences
          (`DEF-CUS-6385`) were removed rather than cut, and the PO's approved
          remedy list for this very screen deletes *What confirming writes*
          and *What confirming does not do* for the same reason.

          **THE GUARANTEE ITSELF IS UNTOUCHED AND IS NOT A COMMENT'S CLAIM
          (hard-won law 1):** CLAUDE.md hard rule 7 makes every money action
          write `audit_log`, the close writes one, and
          `test_move_out_scenarios.py` is what holds that — not this sentence.
          `customers.moveOut.auditLine` is retired from all eleven catalogues
          through `10-scripts/i18n_fanin.py` in this same commit, so G18 does
          not inherit a dead key.

          ⚠ **THE FOUR SIBLINGS ARE LEFT ALONE AND FILED INSTEAD** —
          `customers.moveIn.auditLine`, `customers.newAccount.auditLine`,
          `assets.auditLine` and `metering.auditLine` are the same sentence on
          screens this lane was not asked to change and nobody has reviewed
          today. They are `DEF-CUS-6551`. */}
    </div>
  );
}

// ── Steps ──────────────────────────────────────────────────────────────────

function AccountStep(props: {
  detail: AccountDetail;
  occupant: boolean;
  /** True on `/move-outs/new`, where the clerk FOUND this account in the box
   *  directly above this panel — which makes one of its sentences false. */
  picked: boolean;
  /** `BR-CUS-1082` — how many accounts are still open beneath this master,
   *  from the settlement's `open_sub_accounts`. **`null` is "not measured
   *  yet", never zero**: the close-impact read may be in flight or may have
   *  failed, and a strip drawn over an unknown count would appear on every
   *  account in the product — which would pass a test of the master case
   *  exactly as a correct one does. The null case draws nothing and the
   *  server's own warning is what the clerk then reads on the receipt. */
  openSubAccounts: number | null;
  /** The tenant's own account categories, so `Type` shows a NAME not a code. */
  categories: readonly AccountCategoryOption[];
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { detail, t } = props;
  return (
    <Panel>
      {/* ⛔ **THE STEP'S OWN `<h3>` IS GONE — it was printed TWICE on screen.**
          `MoveOutAccountPanel` draws the drawing's own heading (*This
          account*), and this one drew the step's question above it, so a clerk
          read two headings one line apart. Found on the browser walk; invisible
          to every unit case, because both strings are well-formed keys that
          resolve in all eleven catalogues. The step is already named by the
          rail and by the `Step 1 of N · Find account` line above it (B14 rule
          32: a row never repeats what its own frame already says). `DEF-CUS-6497`. */}
      {/* ⛔ **ONE SENTENCE ON THE PICKED ROAD, AND NONE ON THE OTHER —
          `DEF-CUS-6481`, PO 2026-09-24: *"too much text reduce  this; Account
          and matching account"*.**

          **Picked road** (`/move-outs/new`, an account chosen above): the hint
          was 24 words and only its first clause was an INSTRUCTION. *"every
          step after this closes it"* is a CONSEQUENCE of steps not yet taken
          and *"This is the account you found above"* restates the panel the
          clerk is looking at, so both go and the ACT stays — six words, which
          is B14 rule 33's cap for an instruction.

          **Account-scoped road** (`/accounts/:accountId/move-out`): the hint
          was 37 words explaining WHY there is no search here — textbook
          RATIONALE, which rule 33 puts at ZERO words on screen. It is DELETED
          rather than shortened. Nothing is lost: the panel below names the
          account, and a clerk who wants a different one uses the ← exit this
          header already draws (B14 rule 1).

          Both keys are retired from all eleven catalogues through
          `10-scripts/i18n_fanin.py`; `account.hintPicked` is replaced by
          `account.checkRight`, a NEW key rather than a rewritten default,
          because a catalogue entry beats a `defaultValue` and a rewritten
          default ships a green suite over a user still reading the old words
          (the DEF-731 shape this comment has always named). */}
      {props.picked && (
        <p className="met-panel-hint">
          {t("customers.moveOut.account.checkRight", {
            defaultValue: "Check this is the right account.",
          })}
        </p>
      )}

      {/* ── *This account*, AS `01-find-account.png` DRAWS IT ────────────────
          ⚠ **A COMPONENT, NOT A FACT LIST INLINE HERE (B14 rule 43).** The
          drawing puts these facts in TWO COLUMNS and the kit's `FactList` is a
          two-column grid holding ONE label-and-value pair per row, so it cannot
          draw the panel as drawn. Writing the four-column layout HERE was the
          other option and it is the one rule 21 forbids: this file is not on
          `route-b-migrated.txt`, so a Tailwind utility written here fails `G31`
          at merge, and reaching for a stylesheet class instead is exactly what
          rule 21 exists to stop. `moveOutAccountPanel.tsx` is listed.

          ⚠ **FOUR ROWS ARE NEW AND EVERY ONE WAS ALREADY ON THE WIRE** — the
          mailing address, the type, the sub-type and the kind. The payload has
          carried `addresses`, `account_type`, `account_subtype_name` and `kind`
          all along; nothing was added to serve them. That is `DEF-CUS-6476`'s
          whole lesson: **an absence is invisible to every check this repo
          has**, so a panel is diffed against its drawing row by row or the gap
          is never found. */}
      <MoveOutAccountPanel
        detail={detail}
        categories={props.categories}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
        t={t}
      />


      {props.occupant ? null : (
        // BR-CUS-030: the commit WILL be refused — said now, not after it.
        <RefusalStrip role="alert">{t("customers.moveOut.account.notOccupant")}</RefusalStrip>
      )}

      {/* `BR-CUS-1082` — a parent with open children is WARNED, not refused
          (PO ruling 2026-09-20 closing `OQ-CUS-12515` on option (b)). The
          blueprint's p110 puts the fact on STEP 1 (*What is open on this
          account* → `Sub-accounts`) and that is unchanged; what changed is
          that the clerk may now read it and continue.

          ⚠ **A WARNING, AND THE DOM SAYS SO RATHER THAN ONLY THE COLOUR.**
          This was a `RefusalStrip`: danger tier, `role="alert"`,
          `data-refusal` in the markup. A warning left inside that wrapper
          would be a screen that still reads as a refusal to a clerk and still
          announces itself as one to a screen reader, whatever the words say.
          `WarningBox` is the kit's warning tier (B14 rule 36 — the shared
          component kit is how a screen complies): amber, `role="status"` so
          it is reached in the page's own order rather than interrupting, and
          `data-warning` for the walkthrough and the tests to find. It also
          brings its OWN classes from a Route-B file, which is why nothing
          here gains a Tailwind utility: `MoveOutWizard.tsx` is NOT on
          `styles/route-b-migrated.txt` and G31 still owns every class in it.

          ⚠ **REWORDED FROM AN INSTRUCTION TO A FACT**, which is the ruling's
          own words. The sentence used to end *Close or reassign them first* —
          an instruction that is no longer true, because there is now nothing
          the clerk must do first. All eleven catalogues drop that half and
          keep the fact.

          ⚠ **NO RULE ID AND NO REASON ON SCREEN** — B14 rule 32 keeps an
          internal code out of clerk-facing copy and rule 33 makes RATIONALE
          zero words there. WHY a landlord may leave tenants beneath them — a
          sale is a transfer, and a transfer carries them — lives in the
          decision log and in `br_ref`, never in this copy.

          ⚠ **NO ACKNOWLEDGEMENT, AND THAT IS A DECISION THE RULING LEFT
          OPEN.** The clerk may walk straight past this. A tick-to-continue
          would be a refusal with an extra click — the thing the PO removed —
          and there are five more steps and a named commit button between
          reading this and closing anything. */}
      {props.openSubAccounts !== null && props.openSubAccounts > 0 ? (
        <WarningBox
          tone="soon"
          data-warning="customers-open-sub-accounts"
          sentence={t("customers.account.has_open_sub_accounts", {
            count: props.openSubAccounts,
            defaultValue: "{{count}} sub-accounts are still open.",
          })}
        />
      ) : null}
    </Panel>
  );
}

function DateStep(props: {
  /** `DEF-CUS-10051` task 7 — the Fetch reading control asks the server. */
  client: ApiClient;
  detail: AccountDetail;
  value: string;
  problem: MoveOutDateProblem | null;
  dateFormat: RegionalDateFormat;
  onChange: (value: string) => void;
  /** PO ruling 2026-09-20 item 3 — why this tenancy ended, one of `CLOSE_REASONS`. */
  reason: string;
  onReasonChange: (value: string) => void;
  /** True once Continue has been pressed with nothing chosen. */
  reasonProblem: boolean;
  t: Translator;
  /** CR-038 W9 task 4 — the clerk's draft, with `OQ-394`'s prefill under it. */
  reads: ReadsDraft;
  onReadsChange: (draft: ReadsDraft) => void;
  /** `DEF-CUS-6487` — the whole field-visit election, not a list of ids. */
  fieldVisit: FieldVisitValue;
  onFieldVisitChange: (next: FieldVisitValue) => void;
  /** True once Continue has been pressed, so nothing is red before then. */
  fieldVisitShowErrors: boolean;
  /** `DEF-CUS-10051` — Continue pressed: a metered row with no reading is red. */
  readsShowErrors: boolean;
  timeZone: string;
  /** ⚠ **A MASTER ONLY — `02M-date-and-reads-master.png`.** Every unit tagged
   *  to this master and the state it is in. `null` on a regular account, which
   *  is a different thing from an empty list: a regular account HAS no units
   *  beneath it, and a master with none is a building with nothing on it. */
  masterUnits: readonly UnitRow[] | null;
  /** What each EMPTY unit bills to this master each month. */
  vacantBillsHere: (unit: UnitRow) => { amount: string; currency: string } | null;
}) {
  const { detail, t } = props;
  return (
    <Panel>
      <h3>{t("customers.moveOut.date.title")}</h3>
      {/* ⚠⚠ **THE STEP'S SECTIONS ARE STACKED, NOT LEFT TO THEIR OWN MARGINS
          — `DEF-CUS-6763`, PO on `v2.351.98`: *"spacing problem reason and
          table start"*.** Measured in Chromium at 1440 before this: **0px**
          between the Reason select and the `Meters on this unit` heading, and
          **20px** between the meters table and `Field visit`. B14 rule 39 puts
          sections at `--space-6` (24px) and rule 44 says our standard decides
          spacing whatever a drawing shows. `WizardSectionStack` carries the
          utilities, because this file is not on the Tailwind ledger. */}
      <WizardSectionStack>
      {/* ⛔ **THE SECTION BLURB IS DELETED — `DEF-CUS-6477`, PO 2026-09-24:
          *"too much text on this screen please reduce it"*.** It was 30 words
          and every one of them was RATIONALE, which B14 rule 33 puts at ZERO
          words on screen: *"The date is the whole of what this step stores"*
          describes our storage, and *"charges run through it, and whoever moves
          in next starts the day after"* teaches the rule behind the field. The
          one clause a clerk acts on — charges run through this day — is now the
          date field's own help line below, where B14 rule 39 puts a helper.
          `customers.moveOut.date.hint` is retired from all eleven catalogues
          through `10-scripts/i18n_fanin.py`. */}

      {/* ⚠ **TWO FIELDS SINCE 2026-09-20, AND `FieldStack` IS WHY THEY DO NOT
          TOUCH.** A run of bare `.field`s inside a `Panel` is `display: block`
          with `gap: normal`, so adjacent fields measure 0px apart — B14 rule
          39 wants 20px, and adding the second field without this wrapper would
          have manufactured exactly the defect `DEF-CUS-5098` was filed for. */}
      <FieldStack>
        {/* BR-CUS-056: the move day belongs to THIS account. */}
        <DatePickerField
          id="moved_out_on"
          label={t("customers.moveOut.field.movedOutOn")}
          required
          value={props.value}
          dateFormat={props.dateFormat}
          onChange={props.onChange}
          /* ⛔ **30 WORDS DOWN TO FIVE — `DEF-CUS-6477`.** It read *"Charges run
             through this day for this account. It cannot be earlier than the
             day the account opened, and the server refuses one that falls
             behind a bill already issued."* Only the first clause is a FACT the
             clerk acts on; the rest teaches two server rules, which is
             RATIONALE at ZERO words on screen (B14 rule 33). **The rules
             themselves are NOT weakened and are not being hidden** — both
             refusals still fire and both still say so, through
             `customers.moveOut.date.beforeStart` and the commit's own refusal
             below, which is where a consequence belongs: at the moment it
             happens, not as a warning a clerk reads past. A NEW key, not a
             rewritten default (the DEF-731 shape). */
          help={t("customers.moveOut.date.chargesThrough", {
            defaultValue: "Charges run through this day.",
          })}
          error={
            props.problem === "before_start" ? t("customers.moveOut.date.beforeStart") : undefined
          }
        />

        {/* ✅ **WHY THIS TENANCY ENDED — COLLECTED AND STORED SINCE 2026-09-20**
            (PO ruling of that date, option A). This was a `NotRecorded` reading
            *"Not stored"*, over a rationale sentence explaining that the column
            was proposed and never built. Both are gone: the column exists
            (`accounts.close_reason`, migration 0058) and `reason` is an
            accepted field on this one endpoint.

            ⚠ **IT IS A FORM CONTROL AND SO IT LEFT THE FACT LIST** — B14 rule
            38, *"where a drawing and our UI rules disagree about how a FORM is
            built, the UI rules win"*. A `Fact` states something already true;
            this asks the clerk for something. It sits beside the date because
            the two are one question — when they left, and why.

            ⚠ **THE FIVE OPTIONS ARE DERIVED, NEVER TYPED HERE** (§12 — never
            hand-type a list). `CLOSE_REASONS` in `moveShared` is the one place
            they are named, keyed to the server's own vocabulary, so a sixth
            reason cannot reach the server without appearing on this screen. */}
        <SelectField
          id="close_reason"
          label={t("customers.moveOut.field.reason")}
          required
          value={props.reason}
          onChange={props.onReasonChange}
          placeholder={t("customers.moveOut.reasonPlaceholder")}
          options={CLOSE_REASONS.map((code) => ({
            value: code,
            label: t(`customers.moveOut.reason.${code}`),
          }))}
          error={props.reasonProblem === true ? t("customers.moveOut.reasonRequired") : undefined}
        />
      </FieldStack>

      {/* ── THE METERS, AS THE PO-APPROVED NINE-COLUMN TABLE ────────────────
          **PO 2026-09-24, on the move-in's table put to them again for the
          move-out: *"this si correct use it"*.** What stood here was a bare
          `<ul>` of the ACCOUNT's meter numbers over a separate
          `MoveReadsCapture` panel — two lists of the same registers, one of
          them without a reading box.

          ⚠ **NOTHING NEW IS BUILT. `MoveInReadingsTable` IS MOUNTED** (B14
          rule 43 — a piece of UI is a COMPONENT), with the two props that make
          a shared table serve a second flow: its HEADING, because a master has
          no unit of its own and reads *Meters on the common areas*, and its
          DOM-id prefix, because two wizards addressing `moveIn-read-<id>` is a
          collision waiting for the first screen that mounts both.

          ⚠ **`OQ-394`'s PREFILL IS NOT A PROP AND MUST NOT BECOME ONE.** The
          move-out's Reading box opens with the register's last reading and the
          move-in's opens empty — signed law, both ways. That difference lives
          in the DRAFT: `useReadsDraft` above lays the clerk's entries over
          `prefilledReadsDraft` as a DERIVED value, so the figure on screen and
          the figure in the payload are the same expression at every instant,
          including the first frame. `MoveInWizard` holds a plain
          `useState<ReadsDraft>({})` and gets the empty box. **Adding a prefill
          flag to the table would be a second answer to one question, and the
          one that drifted would be the one closing accounts.** */}
      {/* ⚠ **AN ACCOUNT WITH NO UNIT STATES THE ABSENCE — `DEF-CUS-6492`, found
          by walking this screen in a browser and by nothing else.**
          `MoveInReadingsTable` returns `null` on an empty `unitId`, which is
          RIGHT for the move-in — it mounts the table before a unit has been
          chosen and must draw nothing there — and wrong the moment a second
          host inherits it. On a MASTER account `unit_id` is NULL by
          `BR-CUS-1010`, so step 2 rendered no heading, no table and no sentence
          at all: not broken, just silently not there, which is
          indistinguishable from a panel nobody ever drew.

          **The guard is HERE rather than in the component** because the
          decision is the HOST's: the move-in genuinely wants nothing, and a
          flag on the shared table would be two answers to one question. Every
          jsdom case seeds unit assets, so the table is always present in the
          suite; this is the state only a real tenant reaches.

          ⚠ **AND ON A MASTER IT IS NO LONGER AN ABSENCE — 2026-09-24.**
          `02M-date-and-reads-master.png` draws *Units on this master* above,
          and heads the meters panel **the COMMON AREAS**, because a master
          hangs off the ADDRESS and has no unit of its own (`BR-CUS-1010`).
          The sentence below is now only for an account that names no unit and
          is not a master at all — which is a real state and still says so. */}
      {props.masterUnits !== null && (
        <UnitsOnThisMaster
          rows={props.masterUnits}
          billsHere={props.vacantBillsHere}
          t={t}
        />
      )}
      {(detail.unit_id ?? "") === "" ? (
        <section data-move-out-meters={props.masterUnits === null ? "no-unit" : "common-areas"}>
          <h4 className="cus-subhead">
            {props.masterUnits === null
              ? t("customers.moveOut.date.metersTitle")
              : t("customers.moveOut.date.commonAreaMeters", {
                  defaultValue: "Meters on the common areas",
                })}
          </h4>
          <Note>
            {props.masterUnits === null
              ? t("customers.moveOut.date.noUnit", {
                  defaultValue: "This account holds no unit.",
                })
              : t("customers.moveOut.date.noCommonMeters", {
                  defaultValue: "No meters on the common areas.",
                })}
          </Note>
        </section>
      ) : (
      // ⚠ **EVERY SERVICE ON THE UNIT, GROUPED BY HOW IT IS BILLED —
      // `DEF-CUS-10051`, PO 2026-10-11 (*"this is correct"*).** Metered rows
      // keep the nine reading columns (the ONE builder `MoveInReadingsTable`
      // also uses) plus the fetch slot; share and capacity rows are facts.
      // BR-CUS-030: `closed_at` IS the move-out date, and BR-TEN-043 says the
      // readings take the flow's own event date, never a clock.
      <MoveOutServicesTable
        unitId={detail.unit_id ?? ""}
        draft={props.reads}
        onChange={props.onReadsChange}
        moveOutDate={props.value}
        showErrors={props.readsShowErrors}
        titleText={t("customers.moveOut.date.metersTitle")}
        // `DEF-CUS-10051` task 7 — Move-in's shared Fetch reading control
        // (`DEF-CUS-10050`), asked AS OF the move-out date: the reading on or
        // last before it, so the final bill carries no usage after the
        // customer left (PO 2026-10-11). A fetched value fills the Reading and
        // its real date; typing still works and replaces it.
        renderFetch={(row) =>
          row.assetNo === null || row.assetNo === undefined || row.assetNo === "" ? null : props
              .reads[row.assetId]?.estimate === true ? (
            // `DEF-BIL-10052` task 5 — Estimate ticked: the estimate itself,
            // from the draft bill's own path, in place of the fetch button.
            <MoveOutEstimateNote
              client={props.client}
              accountId={props.detail.id}
              meterNo={row.assetNo}
              movedOutOn={row.moveOutDate}
              t={t}
            />
          ) : (
            <FetchMeterReading
              meterNo={row.assetNo}
              asOf={row.moveOutDate === "" ? undefined : row.moveOutDate}
              client={props.client}
              t={t}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
              expectedUnit={row.uom}
              disabled={props.reads[row.assetId]?.estimate === true}
              currentValue={props.reads[row.assetId]?.value ?? ""}
              onFetched={(reading) =>
                props.onReadsChange(
                  withReadDraft(props.reads, row.assetId, row.assetNo ?? "", {
                    value: reading.value,
                    readAt: reading.read_on,
                  }),
                )
              }
            />
          )
        }
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
        t={t}
      />
      )}

      {/* ── DOES SOMEBODY HAVE TO ATTEND? (US-WRK-039, BR-WRK-055) ───────────
          ⚠ **HERE AND NOT ON THE MONEY STEP — `DEF-WRK-3725`.** The shortfall
          renders greyed and *skipped* whenever the account settles, so a
          control placed there is invisible on the ordinary move-out. This is
          the step where a clerk is already deciding about the final read.

          ⚠ **`FieldVisitOrders`, THE COMPONENT ALL THREE FLOWS NOW MOUNT.** The
          PO approved its seven columns for the move-out on 2026-09-24 and kept
          *No visit needed* in the same exchange (*"(a) Keep 'No visit
          needed'"*), having been asked both ways rather than guessed at.
          `RaiseFieldWork`, which stood here, offered only the utility's
          PUBLISHED TEMPLATES — none at a utility that has written none — so a
          clerk usually saw an empty panel.

          ⚠ **THE DOOR WAS WIDENED IN THE SAME COMMIT — `DEF-CUS-6487`.**
          `POST /accounts/{id}/move-out` read `field_visit.template_ids` alone,
          so this table's rows and its *No visit needed* answer would have been
          parsed out of the payload and dropped while the move-out reported
          success. Mounting it over that door was hard-won law 2's mirror: a
          control that renders, accepts input, succeeds, and sends nobody. */}
      <FieldVisitOrders
        flowKind="move_out"
        value={props.fieldVisit}
        onChange={props.onFieldVisitChange}
        showErrors={props.fieldVisitShowErrors}
        dateFormat={props.dateFormat}
        timeZone={props.timeZone}
        t={t}
      />
      </WizardSectionStack>
    </Panel>
  );
}

/**
 * ⚠ **STEP 3, REBUILT TO ITS DRAWING — PO 2026-09-19, verbatim: *"we need to
 * do it"*** (blueprint p112 + the top of p113, read as IMAGES per B14 rule 42).
 *
 * **WHAT STOOD HERE, AND WHY IT WAS HONEST AND STILL WRONG.** It rendered an
 * `ArrivesWith` panel and five `NotRecorded` facts, over a sentence that was
 * exactly right — *"There is no preview route and no invoice to price from — an
 * amount here would be invented money"*. That instinct is the reason this
 * screen never shipped a wrong figure. What it could not do was notice that
 * **the absence was the keystone of the whole flow**: `settlement_for` takes a
 * final-bill figure THE CALLER STATES, nothing in the product ever stated one,
 * so `landing` came back null on every account, so step 4's radios rendered
 * live over a `POST` that refused every time, and step 5 had nothing to state.
 *
 * **The chain is now closed in one direction:** `GET /accounts/{id}/
 * final-bill-preview` prices the closing window and posts nothing, its `total`
 * is handed to `GET /accounts/{id}/close-impact?final_bill=`, and the drawn
 * table is assembled from BOTH answers. Until that route lands on this branch
 * the read simply fails and **every figure states its own absence** — which is
 * what this step already did, in the drawing's own shape instead of a panel of
 * prose.
 *
 * ⚠ **NO BILL IS ISSUED BY THIS SCREEN**, and p112 says so in its own dashed
 * panel. The preview writes no invoice, no invoice line, no journal line and
 * no bill number; the figures are a settlement position, not an invoice.
 */
function SettlementStep(props: {
  /** `DEF-BIL-10052` — the draft bill's *Back to readings*. */
  onBackToReadings: () => void;
  accountId: string;
  detail: AccountDetail;
  preview: FinalBillPreview | null;
  impact: CloseImpact | null;
  /** 🔒 The SAME two terms the close-impact read was made with, handed down
   *  rather than recomputed — `DEF-CUS-5927`. See `settleShortfall`. */
  terms: CloseImpactTerms;
  movedOutOn: string;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  t: Translator;
  /** `CR-185-BRC10` — the path the server RECORDED, handed up so the commit
   *  carries it (`shortfall_path`) and posts the tie-back inside the move-out. */
  onDecided?: (path: string) => void;
}) {
  const { t, impact } = props;
  const money = impact?.money ?? null;
  const landing = landingOf(impact);

  // 🔒 MONEY PATH. 1 · NOTHING IS PRESELECTED — a default here would be the
  // product deciding where a departing tenant's debt goes.
  const [chosen, setChosen] = useState<string | null>(null);
  const settle = useMutation({
    mutationFn: (path: string) => settleShortfall(props.accountId, path, props.terms),
    onSuccess: (_data, path) => props.onDecided?.(path),
  });
  // ⚠ THE SERVER'S VERDICT, NEVER A DERIVED ONE. `?? false` is the fail-closed
  // direction: an unread value offers NOTHING rather than four paths over a
  // POST that will refuse them.
  const shortfallLive = impact?.step_4_live ?? false;
  const choices = ourBlockedReasons(shortfallChoices(impact?.shortfall_paths ?? []), t);

  return (
    <Panel>
      {/* ⛔ **`FiveLandings` AND `OtherThreeAsk` ARE DELETED, NOT MOVED —
          `DEF-CUS-6499`, and the PO named both of them on their own screen on
          2026-09-24.** *The five landings, one arithmetic* tabulated our own
          derivation (`Settled · nothing left either way`, `Short · above
          zero`) and *What the other three would ask for* listed the fields of
          three deposit options a clerk cannot take. Both are RATIONALE — why
          the product landed where it did, what a control would want if it were
          offered — which B14 rule 33 puts at ZERO WORDS ON SCREEN and says to
          REMOVE rather than shorten. The LANDING itself is not hidden: it is
          the *Short by* row of the table below, which is the only form of it a
          clerk acts on. Their catalogue keys are retired through
          `10-scripts/i18n_fanin.py` in this commit. */}
      <StepColumns
        left={
          <TheMoney
            money={money}
            t={t}
            {...(props.preview?.priced === true
              ? {
                  aside: t("customers.moveOut.money.draftAside", {
                    defaultValue: "Draft bill",
                  }),
                }
              : {})}
          />
        }
        right={
          <DepositDisposition
            money={money}
            landing={landing}
            movedOutOn={props.movedOutOn}
            depositOnFile={props.detail.deposit_on_file}
            currency={props.detail.currency}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            t={t}
          />
        }
      />

      {/* ⚠ **THE SHORTFALL IS ABSORBED, NOT SKIPPED — PO ruling 2026-09-24.**
          It was step 4 of six and is now a SECTION of step 3, shown only when
          the subtraction lands `short`, which is what the drawing's own
          heading says: *Shown only when the account is short*. The merge is
          why: *Short by* is this subtraction's bottom line rather than a
          separate fact, so giving it a step of its own repeated the same
          figures three times (decision log 2026-09-24).

          ⚠ **`step_4_live` IS THE SERVER'S AND STILL DECIDES IT.** The name is
          now one step out of date and the VALUE is not: it is the settlement
          saying this account is genuinely short and a `settle-shortfall` POST
          would be accepted. Renaming it is a wire change and a wire change is
          not this lane's; what matters is that the control is not offered over
          a door that would refuse it (`DEF-CUS-5920`, hard-won law 2's
          mirror). */}
      {shortfallLive && (
        <ShortfallPaths
          choices={choices}
          chosen={chosen}
          onChoose={setChosen}
          onConfirm={() => {
            if (chosen !== null) settle.mutate(chosen);
          }}
          confirming={settle.isPending}
          t={t}
        />
      )}
      {settle.isError && <RefusalStrip role="alert">{apiErrorText(settle.error, t)}</RefusalStrip>}
      {settle.isSuccess && (
        <Note>
          {settle.data?.postsAtCompletion === true
            ? // `CR-185-BRC10` — only money IN THE BOOKS moves: step 3 says
              // it moves when the final bill is sent, with the preview figure.
              t("customers.moveOut.shortfall.whenBillSent", {
                amount: formatMoney(settle.data.amount ?? "0", props.detail.currency ?? "USD"),
                account: settle.data.toAccountNo ?? "",
              })
            : settle.data?.posted === true
              ? t("customers.moveOut.shortfall.posted")
              : t("customers.moveOut.shortfall.recorded", {
                  defaultValue: "Recorded, with your name on it.",
                })}
        </Note>
      )}

      <DraftBill
        preview={props.preview}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
        t={t}
        onBackToReadings={props.onBackToReadings}
      />
    </Panel>
  );
}

/**
 * B19 §15.9.4 · §15.9.1 — step 4, and it is CONDITIONAL (BR-SHL-046).
 *
 * `Short by` is the only landing that opens it: the deposit did not cover
 * everything outstanding and *"that balance has to go somewhere before the
 * account can close"*. In every other landing the step renders
 * `Shortfall · skipped` — greyed, named, and still one of the six.
 *
 * ⚠ **THE FOUR OPTIONS ARE NOT BUILT HERE.** They are W5 task 5.8 (`full 🔒`,
 * with option ④ disabled carrying BR-CUS-068's landlord-agreement reason) and
 * they post to `POST /accounts/{id}/settle-shortfall`, **mounted since
 * 2026-08-25** — this line said "not mounted" until DEF-669 corrected it. This
 * step states which case it is in and names what is missing; it does not draw
 * four radios that post nowhere.
 */
// ════════════════════════════════════════════════════════════════════════════
// STEP 4 — THE SHORTFALL, AND THE CLERK'S ACT THAT MOVES A DEBT
//
// 🔒 MONEY PATH · HUMAN-REVIEW-PENDING — this control is the thing that moves
// $175.20 of a departed tenant's debt onto a landlord's account. Ledger row:
// 12-governance/09-human-review-ledger.md.
//
// **BR-CUS-097 AS QUALIFIED 2026-08-27 (PO, closing OQ-531's fifth part),
// verbatim:** *"if U1 leave and dont pay $500 then $500 Debt is shifted to
// Owner A, **if clark tied back to A during move out process**"*.
//
// The rule as written on 2026-08-24 reads as AUTOMATIC — *"the residue moves
// to the master account the sub-account hangs off"* — and it is NOT. An
// automatic transfer would move a departing tenant's debt onto a landlord who
// never agreed to it, silently, on every move-out in the product. **The clerk's
// action is the consent**, which is why this step is a control a person must
// operate and never a consequence the screen states.
//
// So three properties are load-bearing here and each is asserted in
// `MoveOutWizard.test.tsx`:
//   1. **NOTHING IS PRESELECTED.** `chosen` starts null. A default would be the
//      product choosing where a debt goes.
//   2. **THE TARGET IS NAMED, NEVER TYPED.** The master arrives resolved from
//      the server (BR-CUS-097: *"a transfer cannot be built against an
//      ambiguous target"*), so this screen has no free-text account field and
//      a forged transfer is unrepresentable rather than merely rejected.
//   3. **THE CONSEQUENCE IS SHOWN BEFORE THE CLICK, NOT AFTER.** OQ-366 closed
//      2026-08-27 — *"Sub account is closed when debt is trasnfer hence we now
//      follow with owner for debt"* — so tying the debt back also points the
//      reminder ladder at the landlord. A clerk must read that before they
//      consent to it, not discover it in a letter.
// ════════════════════════════════════════════════════════════════════════════

/**
 * ⚠ **THE SECOND FETCHER OF `GET /accounts/{id}/close-impact` IS RETIRED
 * (2026-09-19, `DEF-CUS-5920`).** `ShortfallReadModel` and `readShortfallPaths`
 * stood here and read the SAME route this screen already reads through
 * `moveShared.closeImpactPort`, for three of its fields. Two callers of one
 * route is how `DEF-CUS-5072` lost a leading slash on one of them and not the
 * other for two days — *"nothing in this repository compares two callers of
 * one route"*. It got worse today: the close-impact read now states the final
 * bill (`?final_bill=`) and this fetcher stated nothing, so **step 4 would
 * have read a different settlement from step 3 on the same screen, about the
 * same customer's money.** One read, one settlement, and `shortfall_paths`,
 * `refund_methods` and `step_4_live` arrive on it.
 */

/**
 * `POST /accounts/{id}/settle-shortfall` — the clerk's act, and the ONLY way
 * a residue reaches a master account. No target is sent: BR-CUS-097 resolves
 * it server-side, so this call cannot name an account it was not given.
 *
 * ⚠⚠ **IT STATES THE SAME TWO TERMS THE READ STATES — `DEF-CUS-5927`, and
 * without them this call could never succeed on any account in the product.**
 * The body was `{path}` alone from 2026-08-25 until 2026-09-19. The server
 * does not remember the read: `shortfall_decision` calls `settlement_for`
 * again from the POST body, so a body with no `final_bill` re-derives a
 * settlement with `final_bill_not_stated` in its gaps, no landing at all, and
 * refuses `customers.move_out.no_shortfall` — **measured on
 * `AC-2026-00031`: 409 with `params {landing: null, gaps:
 * ["final_bill_not_stated"]}` while the very same screen was printing `Short
 * by $1,591.85`.** Fail-closed is the right posture for a settlement with an
 * unread term; the caller was the half that was wrong.
 *
 * ⚠ **`terms` IS THE READ'S OWN OBJECT, PASSED THROUGH, NEVER A SECOND
 * COMPUTATION.** `MoveOutWizard` declares `statedTerms` once and hands the
 * same value to `closeImpactPort.read` and to here, so the settlement this
 * call records against is the settlement the clerk was looking at. Computing
 * the figure a second time here — even correctly — would put two arithmetics
 * on one customer's closing money, which is the fault this fixes rather than a
 * tidier version of it.
 *
 * The wire names are the server's: `final_bill` and `as_of`
 * (`api._settlement_payload`). Neither is sent when absent — an empty
 * `final_bill` would be a stated figure of nothing rather than no figure, and
 * the service's own `_stated_final_bill` refuses a non-decimal by name.
 */
export async function settleShortfall(
  accountId: string,
  path: string,
  terms: CloseImpactTerms = {},
  client: ApiClient = api,
): Promise<ShortfallOutcome> {
  const body: Record<string, unknown> = { path };
  if ((terms.finalBill ?? "") !== "") {
    body.final_bill = String(terms.finalBill);
  }
  if ((terms.asOf ?? "") !== "") {
    body.as_of = String(terms.asOf);
  }
  // ⚠ The same leading slash, and the same reason — `DEF-CUS-5072`. This one is
  // a WRITE, so the missing character did not merely blank a step: choosing a
  // path and confirming it would have 404'd, and the screen would have shown a
  // transport failure where a business refusal belongs.
  const res = await client.post<{
    posting?: {
      posted?: boolean;
      posts_at?: string;
      amount?: { display?: string | null };
      to_account_no?: string | null;
    } | null;
  }>(
    `/accounts/${accountId}/settle-shortfall`,
    body,
  );
  // 🔒 `OQ-1250` CLOSED 2026-10-14 → (a), PO D5 — and ONLY MONEY IN THE
  // BOOKS MOVES (coordinator ruling the same day): on an account still open
  // the server RECORDS the tie-back and previews the figure (`posts_at`); it
  // posts when the final bill is issued. On a closed account it posts now
  // unless a final bill still waits. The screen reads the server's verdict
  // rather than inferring it from the path.
  const posting = res.data?.posting ?? null;
  return {
    posted: posting?.posted === true,
    postsAtCompletion: posting?.posts_at === "final_bill_issue",
    amount: posting?.amount?.display ?? null,
    toAccountNo: posting?.to_account_no ?? null,
  };
}

/** What a shortfall decision did to the books — the server's word for it. */
export interface ShortfallOutcome {
  posted: boolean;
  /** Recorded now, moved when the final bill is issued (`CR-185-BRC10`). */
  postsAtCompletion?: boolean;
  /** The PREVIEW figure, 2-dp display string, symbol-less. */
  amount?: string | null;
  toAccountNo?: string | null;
}

/**
 * Every blocked shortfall path, with the SERVER'S reason replaced by ours.
 *
 * ⚠ **EXPORTED AND PURE ON PURPOSE, AND THE FIRST DRAFT WAS NEITHER.** It began
 * as an inline `.map` inside `ShortfallStep`, and the case written to prove it
 * mounted the whole wizard at step 4 — which rendered **nothing**, so the
 * assertion failed for the right reason by luck and would have PASSED over an
 * empty frame if it had been written the other way round. That is the exact
 * shape this repository files as *a check that does not check*, and the skill's
 * own warning about mounting. A pure function cannot be defeated by a mount.
 */
export function ourBlockedReasons(
  choices: ShortfallChoice[],
  t: Translator,
): ShortfallChoice[] {
  return choices.map((choice) =>
    choice.blockedReason === null
      ? choice
      : {
          ...choice,
          blockedReason: t("customers.moveOut.shortfall.blockedNoOwner", {
            defaultValue: "This address has no owner account.",
          }),
        },
  );
}

/* ⛔ **`ShortfallStep` IS DELETED — the step it drew no longer exists.**
   PO ruling 2026-09-24: old steps 3 and 4 are ONE subtraction, so *Short by*
   is this settlement's bottom line rather than a step of its own, and giving
   it one repeated the same figures three times. Everything it did that a
   clerk ACTS on moved into `SettlementStep` above, as a section shown only
   when the account is genuinely short (`step_4_live`, the server's own
   verdict): the four paths, nothing preselected, the target named and never
   typed, and the consequence stated before the click. **The three properties
   `BR-CUS-097` made load-bearing are unchanged and are still asserted.**

   What did NOT move is the prose it carried: `ShortfallHeadline`, the
   *undecided* row reading *"The subtraction has not run yet."*, the
   *settled elsewhere* row and `ChosenPathWillDo`. Those are RATIONALE about a
   state, at zero words on screen (B14 rule 33) — a clerk with no shortfall now
   simply sees no shortfall section, which is the honest form of the same
   fact. */

/**
 * ⚠ **STEP 6 IS SIGNED OFF AS BUILT — PO 2026-09-19, verbatim: *"this si
 * correct"* — AND IT RECAPS 1, 2, 3 AND 5, SO WHAT LANDED ON 3 AND 5 TODAY HAS
 * TO REACH IT.** p115–p116 draw the recap with a `Step n` badge on each block:
 * *The account and the unit* (1) · *Date and final reads* (2) · *Final bill
 * and deposit* (3) · *The shortfall* (4) · *What happens next* (5). The two
 * blocks added below are the 3 and the 5 — a new section on this step would
 * otherwise be a step nobody re-reads, and a clerk would confirm a close whose
 * money they last saw three screens ago.
 *
 * ⚠ **THE SAME COMPONENT, NOT A SECOND COPY OF THE FIGURES.** The subtraction
 * is `TheSubtraction` — the one step 3 draws — reading the one settlement.
 * Two renderings of one customer's closing position is how a recap comes to
 * disagree with the step it recaps.
 */
function CloseoutStep(props: {
  detail: AccountDetail;
  movedOutOn: string;
  landing: MoneyLanding | null;
  impact: CloseImpact | null;
  preview: FinalBillPreview | null;
  reads: { taken: number; estimated: number; total: number };
  /** The unit's own registers — the SAME rows step 2 listed, so the review
   *  cannot list different meters from the step it recaps. */
  assets: readonly UnitAssetRow[];
  readsDraft: ReadsDraft;
  dateFormat: RegionalDateFormat;
  timeZone: string;
  t: Translator;
}) {
  const { detail, t } = props;
  return (
    <Panel>
      {/* ⛔ **THE STEP'S OWN `<h3>` IS GONE WITH THE STEP IT NAMED.** The page
          head already says *Step 4 of 4 · Review & close* and the rail names
          it a third time; a heading here was B14 rule 32's *a row never
          repeats what its own control offers*. `04-review-and-close.png`
          opens on the account bar and no heading. */}

      {/* ── THE ACCOUNT / UNIT / DATE BAR ────────────────────────────────
          The drawing's own top strip: who is closing, which unit, and when.
          Three FACTS, read back from what the clerk already stated. */}
      <FactList>
        <Fact label={t("customers.moveOut.field.account")}>
          {/* B14 rule 31 — the account NUMBER and the customer's name, never
              the row's id. */}
          {accountHeadline(detail, t) === "" ? (
            <Dash>{t("customers.account.noNumber")}</Dash>
          ) : (
            accountHeadline(detail, t)
          )}
        </Fact>
        <Fact label={t("customers.moveOut.field.unit")}>
          {/* ⚠ **`premise` ALREADY ENDS WITH THE UNIT LABEL ON MOST TENANTS**,
              so joining the two rendered *401 Quarry Hill Ct · Suite 1 · Suite
              1* — found in a browser, not by a test. The label is appended only
              when the premises line does not already carry it. */}
          {(() => {
            const premise = detail.premise ?? "";
            const unit = detail.unit_label ?? "";
            const parts =
              unit === "" || premise.endsWith(unit) ? [premise] : [premise, unit];
            const line = parts.filter((part) => part !== "").join(" · ");
            return line === "" ? <Dash /> : line;
          })()}
        </Fact>
        <Fact label={t("customers.moveOut.field.movedOutOn")}>
          {props.movedOutOn === "" ? (
            <Dash />
          ) : (
            <DateCell
              value={props.movedOutOn}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          )}
        </Fact>
      </FactList>

      {/* ── THE SIX PANELS ──────────────────────────────────────────────
          ⚠ **OLD STEPS 5 AND 6 ARE ONE STEP — PO ruling 2026-09-24.** Old
          step 5 had **no input anywhere on it**: every panel was read-only, so
          it was a review page sitting one click before the review page. The
          merge removes a step and not a single fact — every panel it drew is
          here, and the two that are NOT are deleted by the same ruling for
          being rationale rather than fact (see `CloseImpactPanels`).

          ⚠ **`The money` AND `The meters` ARE MOUNTED HERE AND HANDED IN.**
          `TheMoney` is the SAME component step 3 draws (B14 rule 43, and the
          specification's own instruction that it is ONE component mounted
          twice), so the review cannot disagree with the step it recaps —
          which matters more since the merge, because this is now the only
          screen between the clerk and an irreversible close. They travel as
          nodes because `moveOutTables.tsx` imports `moveShared.tsx`, and
          importing back would be a cycle. */}
      <CloseImpactPanels
        detail={detail}
        impact={props.impact}
        money={props.impact?.money ?? null}
        moneyPanel={<TheMoney money={props.impact?.money ?? null} t={t} />}
        metersPanel={
          <ClosingMeters
            assets={props.assets}
            reads={props.readsDraft}
            movedOutOn={props.movedOutOn}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            t={t}
          />
        }
        movedOutOn={props.movedOutOn}
        reads={props.reads}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
        t={t}
      />
    </Panel>
  );
}

// ── The answer ─────────────────────────────────────────────────────────────

/**
 * `DEF-CUS-10093` — the final bill the move-out drafted: its number, linked to
 * the bill's own page (where *Approve* and *Cancel draft* live), its amount,
 * and the word *Draft*. Nothing here issues it.
 */
export function MoveOutFinalBillFact(props: { finalBill: MoveOutFinalBill; t: Translator }) {
  const { finalBill, t } = props;
  const tenantPath = useTenantPath();
  if (finalBill.outcome !== "drafted" || finalBill.invoice_id === undefined) {
    return <>{t("customers.moveOut.done.finalBillNone")}</>;
  }
  return (
    <span data-move-out-final-bill={finalBill.invoice_no ?? ""}>
      <InlineLinkTo to={tenantPath(billDetailPath(finalBill.invoice_id))}>
        {finalBill.invoice_no ?? t("customers.moveOut.done.finalBillDraft")}
      </InlineLinkTo>
      {finalBill.total !== undefined && finalBill.currency ? (
        <>
          {" · "}
          <MoneyCell amount={finalBill.total} currency={finalBill.currency} />
        </>
      ) : null}
      {" · "}
      {t("customers.moveOut.done.finalBillDraft")}
    </span>
  );
}

/**
 * The commit's refusal, and — for `DEF-CUS-10093`'s *"the final bill could
 * not be created"* — the engine's own reason after it, when billing named one
 * in a catalogue key (`cause_key`): *"No billing cycle. Assign one on the
 * account."*, *"Draft already exists for this period."*.
 */
export function moveOutRefusalText(error: unknown, t: Translator): string {
  const head = apiErrorText(error, t);
  if (!isApiError(error)) return head;
  const params = (error.params ?? {}) as Record<string, unknown>;
  const cause = typeof params.cause_key === "string" ? params.cause_key : "";
  const said = cause === "" ? "" : t(cause, params);
  // An unknown key comes back as itself: a code is never shown (B14 rule 31).
  if (said === "" || said === cause) return head;
  return `${head} ${said}`;
}

/**
 * What the server actually did, what it could not do, and the BR-CUS-031
 * record it assembled for a bill run that does not exist yet. This replaces the
 * wizard instead of following it, because every one of the nine warnings would
 * otherwise be lost behind a navigation.
 */
export function MoveOutDone(props: {
  result: AccountMoveOutResult;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** `DEF-CUS-10190` — this move-out was raised FROM a move-in: the parked
   *  move-in's address, resumed with the closing reads carried. */
  backToMoveIn?: string | null;
}) {
  const { result, t } = props;
  const tenantPath = useTenantPath();
  const handoff = result.final_bill_handoff;
  return (
    <div className="cus-page">
      <PageHeader
        backTo={{ to: tenantPath(ACCOUNTS_ROUTE), label: t("customers.accounts.title") }}
        kicker={t("customers.moveOut.kicker")}
        title={t("customers.moveOut.done.title")}
        rollup={t("customers.moveOut.done.sub")}
        status={
          <StatusPill tone={accountStatusTone(result)}>{accountStatusLabel(result, t)}</StatusPill>
        }
      />

      {props.backToMoveIn ? (
        // `DEF-CUS-10190` — the PO's *"once it completes, the clerk returns
        // to the move-in"*: one button, back to the parked move-in.
        <Panel as="section" data-move-out-back-to-move-in="">
          <ButtonLink variant="primary" to={tenantPath(props.backToMoveIn)}>
            {t("customers.moveOut.done.backToMoveIn")}
          </ButtonLink>
        </Panel>
      ) : null}

      <Panel as="section">
        <h3>{t("customers.moveOut.done.writtenTitle")}</h3>
        <FactList>
          <Fact label={t("customers.moveOut.field.account")}>
            {result.account_no ?? <Dash>{t("customers.account.noNumber")}</Dash>}
          </Fact>
          <Fact label={t("customers.moveOut.done.closedOn")}>
            {result.closed_at !== null ? (
              <DateCell
                value={result.closed_at}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            ) : (
              <Dash />
            )}
          </Fact>
          <Fact label={t("customers.moveOut.field.unit")}>
            {result.premise ?? result.unit_label ?? <Dash />}
          </Fact>
          {/* `DEF-CUS-10093` (PO 2026-10-13, option B) — Complete drafted the
              final bill before the close. Named by its number and amount, and
              linked: the clerk reviews and sends it from Billing. */}
          {result.final_bill !== undefined && (
            <Fact label={t("customers.moveOut.done.finalBill")}>
              <MoveOutFinalBillFact finalBill={result.final_bill} t={t} />
            </Fact>
          )}
          {/* `CR-185-BRC10` — the tie-back the commit recorded: pending until
              the final bill is sent (the usual case), or posted when nothing
              was left to bill. From the server's answer and nothing else. */}
          {(result.balance_to_owner?.posted === true ||
            result.balance_to_owner?.pending === true) && (
            <Fact label={t("customers.moveOut.done.balanceToOwner")}>
              <BalanceToOwnerState
                state={result.balance_to_owner}
                currency={result.currency ?? "USD"}
                t={t}
                testId="move-out-done-balance-to-owner"
              />
            </Fact>
          )}
        </FactList>
        <p className="met-panel-hint">{t("customers.moveOut.done.unitVacant")}</p>
        {/* ⚠ **WHAT WAS ACTUALLY CAPTURED (CR-038 W9 task 4).** The refused
            estimates matter most on a CLOSE: a register with no final reading
            is a register the final bill cannot be worked out from, and
            `final_reads_not_committed` no longer rides a flow that committed
            some — so this panel is the only place the shortfall is named. */}
        <MoveReadsResult answer={result.event_reads} t={t} />
      </Panel>

      {/* The nine. Not a summary of them — every code the server sent. */}
      <WarningList warnings={result.warnings} title={t("customers.account.warningsTitle")} t={t} />

      {/* BR-CUS-031: assembled, returned, and stored nowhere. */}
      <Panel as="section">
        <h3>{t("customers.moveOut.handoff.title")}</h3>
        {/* ⛔ **DELETED — `DEF-CUS-6477`.** 43 words describing where the record
            is kept (*"it is stored nowhere: no table, queue or outbox exists for
            it, so it lives in this answer and in the audit row"*). That is our
            storage design read aloud to a clerk — RATIONALE, zero words on
            screen (B14 rule 33). The facts below are unchanged, and each
            absence still states itself through `NotRecorded` with the server's
            own rule id on `data-rule-ref`. `customers.moveOut.handoff.hint` is
            retired from all eleven catalogues.

            ⚠ **THE `why` TOOLTIPS ON `NotRecorded` ARE DELIBERATELY LEFT.**
            They are a `title` attribute, not text on the screen, the PO did not
            report them, and the prop is on a SHARED component whose other
            callers are not this lane's to move (B14 rule 43's blast radius).
            REPORTED rather than taken. */}
        <FactList>
          <Fact label={t("customers.moveOut.handoff.billThrough")}>
            {/* DEF-332 — the DATE is what a clerk reads; the rule that produced
                it rides on `data-br-ref` where support can still find it. */}
            <span data-br-ref={handoff.bill_through_br_ref}>
              <DateCell
                value={handoff.bill_through}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            </span>
          </Fact>
          <Fact label={t("customers.moveOut.field.priorBalance")}>
            {handoff.prior_balance !== null ? (
              <MoneyCell amount={handoff.prior_balance} currency={handoff.currency} />
            ) : (
              <Dash />
            )}
          </Fact>
          <Fact label={t("customers.account.field.depositOnFile")}>
            {handoff.deposit_on_file !== null ? (
              <MoneyCell amount={handoff.deposit_on_file} currency={handoff.currency} />
            ) : (
              <Dash />
            )}
          </Fact>
          {handoffGaps(handoff).map((gap) => (
            <Fact key={gap.labelKey} label={t(gap.labelKey)}>
              <NotRecorded
                label={t("customers.moveOut.handoff.absent")}
                why={t("customers.moveOut.handoff.absentWhy")}
                ruleRef={gap.ruleRef}
              />
            </Fact>
          ))}
          <Fact label={t("customers.moveOut.handoff.stored")}>
            {handoff.persisted ? (
              t("customers.account.yes")
            ) : (
              <NotRecorded
                label={t("customers.moveOut.handoff.notPersisted")}
                why={t("customers.moveOut.handoff.notPersistedWhy")}
                ruleRef={handoff.persistence_unavailable}
              />
            )}
          </Fact>
        </FactList>
      </Panel>

      {/* The prototype's second commit button, as a link off the answer: the
          unit is free, and BR-CUS-056 fixes the incoming start at the day after
          the move-out. Both exits are here so neither is a dead end. */}
      <Panel as="section">
        <h3>{t("customers.moveOut.done.nextTitle")}</h3>
        <p className="met-panel-hint">{t("customers.moveOut.done.chainHint")}</p>
        <p>
          <ButtonLink variant="primary" to={tenantPath(accountMoveInPath(result.id))}>
            {t("customers.moveOut.done.chain")}
          </ButtonLink>
        </p>
        <p>
          <InlineLinkTo to={tenantPath(accountDetailPath(result.id))}>
            {t("customers.moveOut.done.openAccount")}
          </InlineLinkTo>
        </p>
      </Panel>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-005@bbed56d (story+rules snapshot — EP-CUS-02 move-out lead story; co-packets US-CUS-004@bbed56d · US-CUS-007@bbed56d · customers 02-business-rules@f125a9c)
// generated: 2026-08-11 by story-coder (W2 customers FRONTEND lane 3 — S20, the screen `POST /accounts/{id}/move-out` shipped without) · AMENDED 2026-08-24 by the CR-030 W5 FRONTEND lane (N2 — tasks 5.1 park & resume and 5.7 the impact screen; BR-SHL-046 · BR-SHL-047)
// amended: 2026-08-26 by lane MOVEENTRY — **PO ruling**, verbatim: *"Move-in and
//         move-out stay disabled, on purpose … The live control is on the
//         account's own page and the button says so. -Enable Move in /move out"*.
//         The wizard gains a SECOND door, `/move-outs/new`, with nothing in the
//         path: `MOVE_OUT_STEPS[0]` was already `Find account`, so what was
//         missing was an entry point and not a step. Step 1 renders the shared
//         `AccountFinder` (DEF-732) when `params.accountId` is absent and every
//         step after it is the same code reading the same state. The
//         account-scoped road is untouched. ⚠ It asks for a NEW key,
//         `customers.moveOut.account.hintPicked`: `…account.hint` is in all
//         ELEVEN catalogues saying *"there is no search on this step"*, a
//         catalogue beats a `defaultValue`, and rewriting the default alone
//         would have shipped the fix dead (the DEF-731 shape).
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 702 passed / 168 todo across 51 files✔ (670 passed / 160 todo across 49 files was the pre-lane baseline — this lane adds 32 passing + 8 todo and dropped nothing) · vite build✔ · run_gates 12 PASS · 2 FAIL · 1 SKIP — and the two FAILs ARE NOT THIS LANE'S, stated rather than rounded up (hard-won law 1): G7 names six 06-backend files (db/rls_ledger_w5.sql, db/rls_notifications_w3.sql, ledger 0002_rls_w5_and_immutability.py, notifications 0002_rls_w3_outbound_queue.py …) with no human-review-ledger row, and G10 names US-BIL-023/024 · US-NOT-002/015 · US-PAY-014 with no backend TC test. All eleven belong to the W3/W5 billing·notifications·ledger lanes landing in 06-backend during this session; this lane touched no backend file. The FRONTEND half of G10 is clean (0 of the frontend-cited stories miss a test, US-CUS-004/005 included), and G13 unwired-props, G14 prototype-conformance and G15 i18n-parity (5 locales × 2466 keys, identical sets) all PASS. The pre-lane baseline for this session was 14 PASS · 0 FAIL · 1 SKIP
// exceptions: ⚠ E1 [2026-08-24, CR-030 W5 · N2] THE STEPS ARE SIX, NOT FOUR — BR-SHL-046 (PO, verbatim "6 steps", closing DEF-648). The four this file shipped with became `account · date · settlement · SHORTFALL · IMPACT · review`, and the ids come from `moveShared.MOVE_OUT_STEPS` so the Move-outs tab's STEP column and this rail cannot drift; B18 §4.3's "move-out stays four" is superseded by that ruling · ⚠ **E3 CORRECTED 2026-08-27 (DEF-669) — BOTH ROUTES WERE MOUNTED ON 2026-08-25 AND THESE TWO SENTENCES WENT ON SAYING OTHERWISE FOR TWO DAYS.** They now read: E3 step 4 (the shortfall) states WHICH case it is in; the four options are W5 task 5.8 and post to `POST /accounts/{id}/settle-shortfall`, **mounted** · E3 step 5 (the impact screen, task 5.7) renders NINE consequence panels and `GET /accounts/{id}/close-impact` is **mounted and read** — it answers the LANDING, `open_sub_accounts` and B19 §15.9's money, and serves NONE of the other six task-5.7 impact fields (premises occupancy, the BR-MET-105a owner, the master account, the vacant base charge, payment-plan progress), which arrive as an explicit `null` and are stated per panel. No money landing is derived client-side · E4 the collections sentence, the payment-plan label and the six outgoing messages are PURE FUNCTIONS of the money landing (`moveShared`), never literals: B19 §15.10 captured them in ONE scenario and `Dunning · Stops on close` is FALSE under `Short by` since BR-CUS-082 · E3 step 1 does NOT search: `POST /accounts/{id}/move-out` is account-scoped (11b §S20), so the account arrives in the URL from S21 and this step confirms it — a second picker here could choose an account the page cannot act on · ✅ **E3 THE MOVE-OUT REASON IS COLLECTED AND STORED SINCE 2026-09-20** (PO ruling, option A, `v2.314.0`) — this entry read *"the move-out REASON is not collected: `accounts.close_reason` is PROPOSED-SCHEMA and unbuilt, so `reason` is a REFUSED field (BR-CUS-030); the five options the design offers are named in the reason text and none is stored"*, which is what the blueprint's p110 calls *"worse than not asking"*. Step 2 now draws a required select over `moveShared.CLOSE_REASONS` and the value lands in `accounts.close_reason` through `MOVE_OUT_FIELDS`; the record page reads it back. Required on the screen, optional at the door, so a caller with no clerk in front of it can still close an account · E3 no final-read control (BR-CUS-021 — `final_reads` is refused; reads commit through metering's batch path, whose idempotency fingerprint is scoped to period/cycle/route/service/source). The unit's meters are LISTED so it is visible which registers go unread, and no Δ usage is computed · E3 step 3 renders NO final-bill preview and no priced line: `POST /accounts/{id}/move-out/preview` is deliberately not mounted server-side, and an amount drawn here would be invented money · E3 the deposit disposition and the refund method are not collected (BR-CUS-025 — apply-first needs the final bill and the refund leg is payments' `refunds`, no tables); deposit interest renders as not-recorded with BR-CUS-057, never $0.00 · E3 the five step-4 checkboxes are not drawn: the unit's return to Vacant is a DERIVATION (BR-MET-036) and is stated as a consequence, and the other four queue through notifications/collections, which have no tables · E4 the prototype's two final buttons ("Complete & start move-in →" beside "Complete move-out ✓") become ONE commit (BR-SHL-019) whose ANSWER carries both exits as links — the chain survives and the nine server warnings are not lost behind a navigation · E4 `status` is omitted from the payload so the server picks the tenant's own seeded terminal status (BR-CUS-055 is tenant-extensible; choosing one here would decide for them) · E4 the BR-BIL-004 refusal (a move-out behind an already-issued bill) is NOT mirrored client-side: billing has no `invoices` table, so this screen genuinely cannot know it — the server answers it, and every move-out warns that the check could not run · E4 the prototype's page-head "Cancel" button is the shared header's BACK LINK (US-SHL-020/BR-SHL-044): one way out, drawn by the component, pointing at the account this flow acts on rather than at a generic list · E4 [CLOSED 2026-09-05, DEF-SHL-3964] the tenant TZ + date format come from the pair `ShellWithSession` publishes; there is no seed fallback behind them
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
