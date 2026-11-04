// ── Trace ──────────────────────────────────────────────
// Change:   CR-030 W6 task 6.11 — **S87 `NCT-03`, THE NEW CONNECT WIZARD**, all
//           NINE steps as drawn 2026-08-25 (B18 §5.4.10). §11's task row says
//           eight; the DRAWING says nine and names them, and the screen is the
//           reference (PO 2026-08-16), so nine ship.
//           Lane TEXT — 2026-09-28 — **THE PER-STEP DRAFT NOTICE IS
//           DELETED** (PO reported bug 1, *"To Much text on every step
//           reduce it"*). *"Nothing is written until step 8. Create
//           connection writes it."* was rationale on all eight screens;
//           B14 rule 33 gives rationale zero words. The review step is
//           now handed the quote's `stored` figure and its `CHAR(3)` so
//           its money row can go through `MoneyCell` (`BR-SHL-023`).
// Rules:    BR-MET-112 (*"nothing is written until step 8"* — steps 1–8 make no
//           request at all) · BR-MET-111 (the owner captured at step 1 BECOMES
//           a customer, which is what makes them billable at step 6) ·
//           BR-MET-113 (OQ-367 CLOSED — the owner gets an ACCOUNT and the quote
//           is tagged to it) · BR-MET-105 (the $30.50 empty-unit base charge
//           accrues to the owner — step 8's second occupancy option) ·
//           BR-MET-115 (a utility user marking the job complete IS the send;
//           the `On creation` trigger is REMOVED — DEF-679) · BR-SHL-018/019
//           (rail semantics, ONE transactional commit) · BR-SHL-025 (a control
//           that cannot act is DISABLED WITH ITS REASON) · BR-SHL-047 (every
//           wizard parks) · B14 rules 3, 4, 5, 10, 11, 18, 21
// Questions: ⛔ OQ-249 (Work is R5) — the *"We schedule it"* mode card is
//           DISABLED, matching `_check_mode`'s `NotImplementedError("OQ-249")` ·
//           ⛔ OQ-370 (which characteristic keys a flat service has) — the
//           wizard collects no characteristic
//           ✔ **OQ-379 IS ANSWERED AND THIS LINE NO LONGER CITES IT AS OPEN.**
//           It read *"the quote is four coded lines and billing's one-time door
//           takes one code with no amount - step 6 renders the quote it is GIVEN
//           and assembles none"*. `CR-109` widened that door
//           (`raise_and_issue_quote_bill`) and the posting is observed on real
//           PostgreSQL. What is open now is `DEF-BIL-5486` — a PREVIEW door, so
//           the screen can show the figure before the button that writes.
// Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.4.10 (all nine
//           steps, captured from the drawing) · §5.4.4 · §5.4.5 · §8.3
// Tests:    07-frontend/src/features/customers/NewConnectWizard.test.tsx
// Impacts:  ⛔ `07-frontend/src/App.tsx` — the route is NOT mounted by this lane
//           (routing is not this lane's file). REPORTED with the exact lines.
//           ⛔ `06-backend/apps/metering/api.py` — `POST /connections/commit`
//           does not exist. REPORTED with the exact view.
//           `src/routing/screenIds.ts` — S87 has no entry. REPORTED.
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · THE WHOLE WIZARD IS A DRAFT, AND THAT IS THE CONTRACT — NOT A SHORTCUT
// ══════════════════════════════════════════════════════════════════════════
// `NCT-03.2`'s footer reads **`Step 2 of 9 · nothing is written until step 8`**,
// and BR-MET-112 makes it a rule. So steps 1–8 issue **no request whatsoever**:
// no draft premise, no draft connection, no reserved connection number. Every
// answer lives in this component's state until one commit.
//
// Two consequences worth stating, because both look like omissions:
//
//   · **There is no autosave and no resume-by-id.** `Save & exit` leaves
//     quietly (B19 §12.2) and `Park` records what the flow is waiting on — and
//     BOTH are blocked with their reason today, because a wizard that has not
//     committed is not yet a row anything can hang a park on. That is
//     `parkStoreBlockedReason`'s existing sentence, reused rather than
//     rewritten (the move-in and move-out wizards say the same thing).
//   · **The step number is URL state** (`?step=`, A9) so a reload keeps the
//     place. The ANSWERS do not survive a reload. Saying so is better than a
//     half-built persistence layer that loses them on a different day.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · WHAT IS DRAWN AND IS NOT BUILT, EACH WITH ITS REASON
// ══════════════════════════════════════════════════════════════════════════
//   * **`↑ Upload a unit schedule`** (step 3). `POST /connections/{id}/units`
//     is in B18 §5.4.6's endpoint table and is not mounted, and BR-MET-112
//     forbids writing units before the commit anyway — so an upload would have
//     nowhere to put the file. Drawn DISABLED with the reason (BR-SHL-025).
//   * **The 26 × 5 per-unit service grid** (step 4). Built as the drawn
//     `Apply to all units` BULK ROW plus a separate common-area set, which is
//     exactly what the drawing's own example does (`Apt 101–106 carry E, W and
//     S; T and D unticked`) and what step 5's warning is about. A per-unit
//     override grid is a real feature and is REPORTED as owed, not faked with a
//     control that writes nothing.
//   * **Step 6's priced lines and its `Quoted` total** — `DEF-BIL-5486`. The
//     step COUNTS what the quote is counted on (per unit · per meter · per
//     premise, from step 4's grid, which is p090's own red sentence) and prices
//     nothing, because no server door prices a build that does not exist yet:
//     `billing.fee_bill.price_quote_bill` wants an `account_id` and
//     `BR-MET-112` says there is no account until step 8. A browser multiply
//     would be the second rounding path `DEF-088` removed.
//     ⚠ **THIS PARAGRAPH READ THE OPPOSITE UNTIL 2026-09-16** — *"the quote
//     came from request SR-26-0043's quote and are not re-priced here … this
//     screen never assembles one"* — and that premise is what the PO rejected:
//     a build RAISED DIRECTLY could then never be charged at all. The drawing
//     does not say the quote arrives; it says the quote is COUNTED.
//   * **The three `Billed to` options are a LIVE radio group again** (p090,
//     `DEF-CUS-5485`). The choice travels as `quote_payer`, which the commit has
//     accepted since `CR-109` and nothing sent. The other two are DISABLED with
//     their real reasons read off `_quote_payer` — not off the drawing, whose
//     stated reason (*"an account must name a unit"*) expired on 2026-09-01.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import { getLookupEntries, getPremisesTypes, getUnits, uploadAccountDocument } from "@/api/endpoints";
import type { AccountDocumentType } from "@/api/endpoints";
import type { ApiClient } from "@/api/client";
import { missingRequiredLabels, useCustomFieldRegistry } from "@/components/CustomFields";
import { PageHeader } from "@/components/PageHeader";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { WizardFrame } from "@/components/WizardFrame";
import type { LeaveDraft } from "@/components/LeaveGuard";
import type {
  WizardCommitOutcome,
  WizardExit,
  WizardNavState,
  WizardStep,
} from "@/components/WizardFrame";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import {
  PossibleDuplicateNotice,
  possibleDuplicateOf,
} from "@/features/payments/PossibleDuplicate";
import type { EarlierPayment } from "@/features/payments/PossibleDuplicate";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { isApiError } from "@/api/client";
import { useTenantPath } from "@/routing/tenantPath";

import { commitNewConnect, getConnection } from "./newConnectEndpoints";
import type { CommitResult } from "./newConnectEndpoints";
import {
  noOneToBillReason,
  coApplicantShortfall,
  draftCoOwners,
  MOVE_IN_EXTRAS_PROBLEM_KEY,
  moveInExtrasProblems,
  ownerDocumentsToFile,
  commitPlanOf,
  commitWorkOrdersOf,
  draftFromRaisedBuild,
  draftManifest,
  draftUnitServices,
  draftFromPark,
  draftUnits,
  emptyDraft,
  parkSubjectRefOf,
} from "./newConnectDraft";
import type { DraftDocument, NewConnectDraft } from "./newConnectDraft";
import {
  NEW_CONNECT_STEPS,
  availabilityBreaches,
  newConnectAddressStep,
  newConnectStoredStep,
  sewerWithoutWater,
} from "./newConnectShared";
import type { Translator } from "./newConnectShared";
import { parkStoreBlockedReason, stepFromParam } from "./moveShared";
// CR-070 wave O — ONE function says where a build lives, and it is Work's.
// CR-070 wave E — and ONE function says which jobs a new build needs. Both are
// HTTP reads: `customers` never queries a Work table (`A7`, the mirror of the
// boundary `G78` enforces from Work's own side).
import { getProposedWorkOrders } from "@/features/work/workEndpoints";
import type { BuildHome, ProposedWorkOrder } from "@/features/work/workEndpoints";
// CR-035 — the park store, its resume handle and the list a park lands on.
import { parkedHomePath, useWizardPark } from "./wizardPark";

// ── The eight steps, one file each (Lane E wave 1) ─────────────────────────
// ⚠ **THE STEP FILES ARE IMPORTED AND RE-EXPORTED, AND THE RE-EXPORT IS THE
// POINT.** `App.tsx`, `wizardPark.dom.test.tsx` and `NewConnectWizard.test.tsx`
// all import from THIS path, and the split changed no import anywhere: this
// file stays the address of the whole wizard while each step is a file a
// separate lane can own. A re-export is invisible to `G104`, which compares
// DECLARATIONS rather than exports, precisely so that composing like this is
// not punished.
import { NewConnectDone } from "./NewConnectDone";
import { coOwnerFormatProblem, coOwnerProblem } from "./CoOwnerCards";
import { customerFormatProblem } from "./customerForm/CustomerWhoPanel";
import { ownerToCustomer } from "./NewConnectCustomerForm";
// `DEF-MET-6110`/`DEF-MET-6111` — the server's refusal, drawn on the step that
// owns it. A COMPONENT, because two steps render it and B14 rule 43 says so.
import { StepRefusal } from "./newConnectStepKit";
import {
  ChargesStep,
  paymentBlocksContinue,
  quoteCannotBePriced,
  useQuotePreview,
} from "./NewConnectChargesStep";
import {
  OwnerScopeStep,
  ownerBirthDateSentence,
  ownerHasABirthDate,
  ownerIdentityShortfall,
  ownerShortfallSentence,
  todayIn,
} from "./NewConnectOwnerStep";
import { PremiseStep, newConnectPremisesTypesQueryKey } from "./NewConnectPremiseStep";
import { ReviewStep } from "./NewConnectReviewStep";
// ⚠ **`PlansStep` AND `ServicesStep` ARE NO LONGER IMPORTED HERE
// (`CR-150-BRC09`).** Both were absorbed into `UnitsStep` when eight steps
// became five, so this file renders neither. `PlansStep` and the old
// `CommunicationStep` wrapper are DELETED with their re-exports
// (`DEF-GOV-10106`): nothing came through this module's door for either.
import { UnitsStep, rowsMissingSize } from "./NewConnectUnitsStep";

export {
  CONNECT_SCOPES,
  OWNER_KINDS,
  OWNER_SUBCATEGORIES,
  applicantPartyKind,
  commitPlanOf,
  draftFromRaisedBuild,
  draftManifest,
  draftUnitServices,
  draftUnits,
  emptyDraft,
} from "./newConnectDraft";
export type { NewConnectDraft, OwnerForm } from "./newConnectDraft";
export { NewConnectDone } from "./NewConnectDone";
export { ChargesStep } from "./NewConnectChargesStep";
export { OwnerScopeStep } from "./NewConnectOwnerStep";
export { PREMISE_TYPES, PremiseStep } from "./NewConnectPremiseStep";
export { OCCUPANCY_COPY, ReviewStep } from "./NewConnectReviewStep";
export { ServicesStep } from "./NewConnectServicesStep";
export { UnitsStep } from "./NewConnectUnitsStep";

/** A1 allocates no id for this screen and **D1 is why** — S61–S90 are gone and
 *  CR-030 needs sixteen. `S87` is what B18 §11 task 6.11 CALLS it and is used
 *  as the DOM handle so a gate and an e2e assertion have one; the ALLOCATION is
 *  the PO's (D1) and is REPORTED, not taken here. */
export const NEW_CONNECT_SCREEN = "S87";

/**
 * The H1 drawn on each of the five screens, in `NEW_CONNECT_STEPS` order.
 *
 * ⚠ **FIVE ROWS SINCE 2026-09-28 (`CR-150-BRC09`), EIGHT BEFORE THAT AND NINE
 * BEFORE 2026-09-16.** Every title below was read off its PNG in
 * `05-prototype/new-connect-redesign-2026-09-28/` with the Read tool, as an
 * IMAGE (B14 rule 42) — *Who is asking, and what for?* · *The premise* · *The
 * units* · *Charges* · *What will be created*. Three of the five are words the
 * blueprint already drew; **`Charges` and `What will be created` now title
 * steps that carry more than they did**, and neither drawing renamed them.
 *
 * ⚠ **THE H1 IS THE DRAWN SENTENCE AND IT IS LONGER THAN B14 RULE 33's
 * THREE-WORD HEADING CAP.** Rule 44 gives our UI standard how a screen is
 * BUILT and the drawing what is ON it; the drawn title is the latter, and
 * reading rule 33's cap onto a page H1 would discard all five. The cap binds
 * the LABELS and section headings below, where it is obeyed.
 *
 * ⚠ Keys are LITERAL on every row so `G18` can see them. A template key
 * (`customers.newConnect.title.${id}`) renders perfectly and is invisible to
 * the gate, so all five would report as dead entries the day they are
 * translated — the same note `NEW_CONNECT_STEPS` and `WIZARD_PARK_REASONS`
 * both carry.
 *
 * ⚠ **THE THREE RETIRED TITLE KEYS ARE NOT DELETED FROM THE CATALOGUES HERE.**
 * `title.services`, `title.plans` and `title.communication` are the TEXT
 * lane's to retire through `10-scripts/i18n_fanin.py`, across eleven files;
 * deleting them from this array is what takes them off the screen, which is
 * this lane's half.
 */
const NEW_CONNECT_STEP_TITLES = [
  { titleKey: "customers.newConnect.title.customer", titleEn: "Who is asking, and what for?" },
  { titleKey: "customers.newConnect.title.premise", titleEn: "The premise" },
  { titleKey: "customers.newConnect.title.units", titleEn: "The units" },
  { titleKey: "customers.newConnect.title.charges", titleEn: "Charges" },
  { titleKey: "customers.newConnect.title.review", titleEn: "What will be created" },
] as const;

const STEP_PARAM = "step";
const PARK_PARAM = "park";
/**
 * **`DEF-CUS-6109` — the DRAFT BUILD this wizard was opened on.**
 *
 * PO ruling 2026-09-21: approving an application into a new connection *"may
 * create a new conenct request - as draft request"*, and the approve modal's
 * own drawn table says what happens next — **p089, `WHAT APPROVING WILL DO`:
 * *"Next · The build's own wizard asks for units, services, plans and
 * charges"***. This is the address that wizard is opened at.
 *
 * ⚠ **IT IS THE BUILD's ID AND NEVER THE APPLICATION's.** From the moment the
 * draft is raised the BUILD is the subject and the application is provenance on
 * it (`BR-MET-1178`) — *"we should not make it dependent on applciation #"*.
 *
 * ⚠ **ABSENT IS THE ORDINARY CASE.** `/connections/new` with no `?build=`
 * behaves exactly as it always has: nothing is read, nothing is prefilled, and
 * the commit creates the row and the address together.
 */
const BUILD_PARAM = "build";

/**
 * **WHICH STEP A SERVER REFUSAL BELONGS TO** — `DEF-MET-6110`/`DEF-MET-6111`,
 * PO ruling 2026-09-21: *"you ahve to show the error at step you mentioned"*.
 *
 * ⚠ **THE SERVER NAMES A STEP ID AND THIS RESOLVES THE POSITION, WHICH IS THE
 * ONLY ORDER THAT SURVIVES A STEP BEING INSERTED.** It has already happened
 * once: `owner` and `scope` merged on 2026-09-16 and every later step moved down
 * a number. A refusal carrying `6` would have landed on `Charges` before that
 * day and on `Communication` after it, silently.
 *
 * ⚠ **AN UNRECOGNISED STEP IS NOT ROUTED, AND THAT IS THE GUARD.** A refusal
 * from some other door, an envelope with no `step`, a step id this wizard does
 * not declare — each returns `null` and takes the ordinary failure card. This
 * function never invents a destination, which is the front-end half of the
 * server's *"anything unrecognised is re-raised untouched"*.
 */
export function stepOwningRefusal(error: unknown): { id: string; position: number } | null {
  if (!isApiError(error)) {
    return null;
  }
  const named = error.params["step"];
  if (typeof named !== "string" || named === "") {
    return null;
  }
  const at = NEW_CONNECT_STEPS.findIndex((step) => step.id === named);
  return at < 0 ? null : { id: named, position: at + 1 };
}

// ══════════════════════════════════════════════════════════════════════════
// THE COMPONENT
// ══════════════════════════════════════════════════════════════════════════

export interface NewConnectWizardProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function NewConnectWizard(props: NewConnectWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const { dateFormat, timeZone } = useRegional(props);

  // BR-SHL-046 — the rail, the `?step=` clamp and anything that ever shows
  // progress read ONE declared list.
  // ⚠ **AN OLD `?step=` IS REMAPPED BEFORE IT IS CLAMPED (`CR-150-BRC09`).**
  // Eight steps became five on 2026-09-28, so every bookmark, every error
  // report and every link a clerk pasted into a ticket carries a number off
  // the OLD list. The clamp alone holds 1-5 unchanged, and `?step=6` — which
  // was *Charges* — clamps to **Review**, one step past the money.
  //
  // ⚠ **THE MAP RUNS BEFORE THE CLAMP, INSIDE `stepFromParam`, AND THE ORDER
  // IS THE WHOLE POINT.** Clamping first turns 6 into 5 and the map then
  // agrees with itself about the wrong number; that is why the mapper is a
  // parameter of the parser rather than a call wrapped around it.
  //
  // ⚠ **AND IT IS `newConnectAddressStep`, NOT `newConnectStoredStep` — THE
  // NARROW MAP, WHICH ONLY TOUCHES 6, 7 AND 8.** The full map here WALLS the
  // wizard: Continue on step 3 writes `?step=4`, the map reads that back as
  // old step 4 and returns 3. That was measured, not reasoned about; the
  // reasoning is in `newConnectAddressStep`'s own docstring.
  //
  // ⚠ **THE ADDRESS IS NOT REWRITTEN AND THAT IS DELIBERATE**, the posture
  // `AssetAddWizard` already takes: this clamps the value it USES. A rewrite
  // needs an effect, and an effect setting search params on mount races the
  // park hydration below, which sets them too.
  const step = stepFromParam(
    searchParams.get(STEP_PARAM),
    NEW_CONNECT_STEPS,
    newConnectAddressStep,
  );
  const nav: WizardNavState = { step, reached: step };
  function setStep(next: WizardNavState): void {
    const query = new URLSearchParams(searchParams);
    query.set(STEP_PARAM, String(next.step));
    setSearchParams(query, { replace: true });
  }
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

  const [draft, setDraft] = useState<NewConnectDraft>(emptyDraft);
  // ── CR-162-BRC10 (Q1) · THE TYPE'S ACCOUNT TYPE RIDES ON THE DRAFT ───────
  // The utility's own premises-type row says whether a premises of that type
  // takes a MASTER or a REGULAR account (`account_kind`), and that — not the
  // number of units typed — decides whether the owner's master account opens
  // (`buildOpensOwnerMaster`). Copied onto the draft whenever the type
  // changes, from the SAME cached read step 2's select already makes, so every
  // reader of the draft (the review step's sentence, the manifest, the commit
  // payload) agrees without a second fetch.
  // ⊕ `DEF-CUS-9242` — the REQUIRED custom fields each step shows, so the step
  // stops where the box is (New Account's own fix, `DEF-CUS-9235`). The SAME
  // registry reads the steps render from — one cache entry each, so what is
  // asked and what is checked cannot disagree. The server's refusal stays the
  // rule underneath; this only says it on the step that can answer it.
  const ownerFieldsReg =
    useCustomFieldRegistry({ entity: "customers", screen: "NEW_CONNECTION_OWNER", mode: "input", client })
      .data ?? [];
  const accountFieldsReg =
    useCustomFieldRegistry({ entity: "accounts", screen: "S18", mode: "input", client }).data ?? [];
  const premiseFieldsReg =
    useCustomFieldRegistry({ entity: "premises", screen: "NEW_CONNECTION_PREMISE", mode: "input", client })
      .data ?? [];
  const fillIn = (missing: string[]): string | null =>
    missing.length === 0 ? null : t("customFields.requiredList", { fields: missing.join(", ") });

  const premisesTypes = useQuery({
    queryKey: newConnectPremisesTypesQueryKey,
    queryFn: () => getPremisesTypes(),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  useEffect(() => {
    // ⊕ **`DEF-CUS-10048` — NO LIST, NO ANSWER, AND NO OVERWRITE.** While the
    // utility's types are not in hand (not read yet, or the cache entry was
    // emptied under a mounted wizard) there is nothing to copy, and copying
    // `""` here quietly turned an owner's regular or master account into
    // NONE — step 4 then refused the clerk's charges for want of an account
    // Create was going to open. Only a LOADED list can say a type has no
    // answer.
    if (premisesTypes.data === undefined) {
      return;
    }
    const row = premisesTypes.data.find((one) => one.code === draft.premise.premiseType);
    const kind = row?.account_kind ?? "";
    if ((draft.premise.accountKind ?? "") !== kind) {
      setDraft((now) => ({ ...now, premise: { ...now.premise, accountKind: kind } }));
    }
  }, [premisesTypes.data, draft.premise.premiseType, draft.premise.accountKind]);
  const [result, setResult] = useState<CommitResult | null>(null);
  // ══════════════════════════════════════════════════════════════════════
  // `DEF-MET-6110` / `DEF-MET-6111` — THE SERVER'S REFUSAL, HELD AGAINST THE
  // STEP THAT OWNS IT
  // ══════════════════════════════════════════════════════════════════════
  //
  // PO ruling 2026-09-21, verbatim: *"this fix is correct - you ahve to show
  // the error at step you mentioned"*.
  //
  // ⚠ **IT IS HELD HERE AND NOT INSIDE A STEP**, for the reason the customer
  // search above already carries: a step's content unmounts the moment the
  // clerk walks away from it, so a refusal stored inside one would vanish on
  // the way back and the screen would look as though nothing had happened.
  //
  // ⚠ **AND IT CLEARS THE MOMENT THE CLERK CHANGES ANYTHING.** A refusal that
  // outlives the thing it refused is a sentence the clerk cannot get rid of,
  // which reads as a screen that is stuck. `patch` is the one door every step
  // edits the draft through, so one line covers all eight.
  const [stepRefusal, setStepRefusal] = useState<{ step: string; message: string } | null>(null);
  // DEF-PAY-9263 · BR-PAY-1199 — step 4's card/ACH payment answered "Looks
  // like a duplicate". Nothing was written; step 4 names the earlier payment
  // and offers *Record anyway*, which re-runs the commit with the flag.
  const [paymentDuplicate, setPaymentDuplicate] = useState<EarlierPayment | null>(null);
  const confirmDuplicateRef = useRef(false);
  function patch(next: Partial<NewConnectDraft>): void {
    setStepRefusal(null);
    setPaymentDuplicate(null);
    setDraft((current) => ({ ...current, ...next }));
  }
  /** The sentence this step owns, or null. Rendered by `StepRefusal`. */
  function refusalOn(step: string): string | null {
    return stepRefusal !== null && stepRefusal.step === step ? stepRefusal.message : null;
  }

  // ══════════════════════════════════════════════════════════════════════
  // `DEF-CUS-6109` — FINISHING A BUILD AN APPROVAL ALREADY RAISED
  // ══════════════════════════════════════════════════════════════════════
  //
  // ⚠ **THE READ IS THE BUILD's, NOT THE APPLICATION's, AND THAT IS THE
  // RULING RATHER THAN A CONVENIENCE** (`BR-MET-1178`, PO 2026-09-21). The
  // build carries the request on its own row and serves what the application
  // already answered as `prefill`; asking the requests API here would make the
  // wizard depend on an application that a directly-raised build does not
  // have, which is the dependency the ruling removes.
  const buildId = searchParams.get(BUILD_PARAM);
  const buildQuery = useQuery({
    queryKey: ["new-connect-draft", buildId],
    queryFn: () => getConnection(buildId as string, client),
    enabled: buildId !== null && buildId !== "",
  });
  // ⚠ **HYDRATE ONCE, AND THE REF IS WHY.** Without it every refetch would
  // overwrite whatever the clerk has typed since — the wizard would silently
  // undo their work on any window focus, which is hard-won law 7's *check that
  // cannot fail* wearing a data face: nothing would ever go red over it.
  const hydrated = useRef<string | null>(null);
  useEffect(() => {
    const build = buildQuery.data;
    if (build === undefined || hydrated.current === build.id) {
      return;
    }
    hydrated.current = build.id;
    setDraft((current) => draftFromRaisedBuild(current, build));
  }, [buildQuery.data]);

  // ⚠ **THE PLANS QUERY LEFT THIS FILE WITH THE PLAN PICKER (`DEF-CUS-5482`).**
  // It read the published plans for step 5's two pickers and the WON'T COVER
  // check computed over them. Both moved to step 2, which runs its OWN query
  // (`newConnectPlansQueryKey`) because the plan and the services it must cover
  // are now asked on one screen. Leaving the read here would have fetched every
  // published plan on every wizard mount for two locals nothing consumed —
  // hard-won law 2 read backwards: not a control with no wiring, but wiring
  // with no control.

  // ⚠ **STEP 1's CUSTOMER SEARCH IS GONE (`CR-164-BRC10` item 11).** The
  // *Search customer ID* box and the term this wizard held for it were removed
  // by the PO on 2026-10-02; step 1 now looks the owner up by itself from what
  // the clerk typed (`NewConnectOwnerMatch`), and what it settles lives on the
  // draft (`owner.matchedCustomerId`, `owner.dismissedMatchIds`), so Back loses
  // nothing.
  // ══════════════════════════════════════════════════════════════════════
  // CR-070 wave E · `US-WRK-017` — WHAT STEP 6 PROPOSES
  //
  // ⚠ **`customers` READS `work` OVER THE API AND NEVER THROUGH THE ORM.**
  // That is the module boundary in the direction `G78` cannot see: Work's own
  // gate stops `apps/work` writing a foreign table, and `A7` stops this module
  // querying `work_order_templates`. The wizard imports a FUNCTION from
  // `features/work/workEndpoints.ts` and the server does the rest.
  //
  // ⚠ **KEYED ON THE SERVICES, SO IT FOLLOWS STEP 4.** Ticking gas at step 4
  // re-asks and the four gas jobs appear; unticking it takes them away. A copy
  // held in the draft would be a second answer that goes stale in between.
  // ══════════════════════════════════════════════════════════════════════
  // ⚠ **READ THE GRID, NOT THE TWO RETIRED SETS (PO 2026-09-16).** Step 4 is
  // one row per unit per service now, so what this build takes is the union of
  // what its UNITS take. `apartmentServices`/`commonAreaServices` no longer
  // decide anything; leaving them here would have proposed work orders for a
  // service nobody selected and none for a service they did.
  const chosenServices = useMemo(() => {
    const codes = new Set<string>(Object.values(draftUnitServices(draft)).flat());
    return [...codes].sort();
  }, [draft]);

  // ══════════════════════════════════════════════════════════════════════
  // `DEF-MET-6111` LAYER 1 — WHAT THIS ADDRESS ALREADY HOLDS, BEFORE A WORD
  // IS TYPED
  // ══════════════════════════════════════════════════════════════════════
  //
  // A unit label is unique within its address. A clerk adding units to an
  // address ALREADY ON FILE could not see what was there, so `Apt 101` met the
  // database rather than the screen — and met it after eight steps, as a 500.
  //
  // ⚠ **THE READ LIVES HERE, NOT IN THE STEP**, for the reason the customer
  // search and the work-order proposal above both carry: a step unmounts when
  // the clerk walks on, and a query inside one re-fetches on every return.
  //
  // ⚠ **ONLY FOR A PICKED ADDRESS.** A build on a NEW address has nothing to
  // collide with — the premises does not exist yet — so the query is disabled
  // rather than asked with an empty id.
  //
  // ⚠⚠ **THIS CAN ONLY UNDER-WARN, AND THAT IS WHY LAYER 2 EXISTS.** The page
  // is server-paginated (`NFR-3`), so a building with more units than one page
  // holds is only partly read; and two clerks can pick the same address in the
  // same second. Neither can make this warn WRONGLY — an absent label is simply
  // not warned about — and the commit still refuses by name on the same step.
  // **The database stays the authority; this is the asking-first half.**
  const pickedPremisesId = draft.premise.premisesId;
  const unitsHereQuery = useQuery({
    queryKey: ["connection-wizard-units-here", pickedPremisesId],
    queryFn: () =>
      getUnits({ per: 500, filters: { premises_id: pickedPremisesId } }, client),
    enabled: pickedPremisesId !== "",
    staleTime: 0,
  });
  // A unit with no label at all cannot collide with one, so it is dropped
  // rather than compared as `""` — which would warn on every unlabelled unit.
  const labelsAlreadyHere = useMemo(
    () =>
      (unitsHereQuery.data?.results ?? [])
        .map((row) => row.label)
        .filter((label): label is string => typeof label === "string" && label !== ""),
    [unitsHereQuery.data],
  );
  const proposalQuery = useQuery({
    queryKey: ["connection-wizard-proposed", chosenServices.join(",")],
    queryFn: () => getProposedWorkOrders(chosenServices, client),
    enabled: chosenServices.length > 0,
  });
  /** The read, minus what the clerk removed. `US-WRK-017` TC-1/TC-2: Electric
   *  and Water propose five; removing one leaves four at commit. */
  //  ⚠ **THE CLERK'S OWN ADDITIONS JOIN THE READ, AND A REMOVAL STILL WINS**
  //  (`DEF-CUS-5482`, PO: *"allow user to add few more work order"*). The
  //  proposal answers only what the CHOSEN SERVICES imply; an addition comes
  //  from the utility's whole template catalogue and is therefore not in that
  //  read at all, which is why the draft stores the WHOLE row for it.
  //  De-duplicated by `template_id` so adding a job the proposal later reaches
  //  for cannot raise it twice.
  const proposedOrders = useMemo(() => {
    const removed = new Set(draft.removedWorkOrderTemplateIds);
    const seen = new Set<string>();
    const kept: ProposedWorkOrder[] = [];
    for (const order of [...(proposalQuery.data?.proposed ?? []), ...draft.addedWorkOrders]) {
      if (removed.has(order.template_id) || seen.has(order.template_id)) continue;
      seen.add(order.template_id);
      kept.push(order);
    }
    return kept;
  }, [proposalQuery.data, draft.removedWorkOrderTemplateIds, draft.addedWorkOrders]);

  const units = draftUnits(draft);
  const unitServices = draftUnitServices(draft);
  const breaches = availabilityBreaches(draft.premiseServices, unitServices);
  const sewerGaps = sewerWithoutWater(unitServices);
  // ⊕ `DEF-CUS-9267` — the two catalogues step 3 sizes its rows from, on the
  // SAME query keys, so this reads the cache step 3 filled rather than a second
  // copy. A size is never assumed; Continue names each row still missing one.
  const sizeCatalogue = useQuery({
    queryKey: ["lookups", "service_size_classes", "new-connect"],
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, client),
  });
  const assetTypeCatalogue = useQuery({
    queryKey: ["lookups", "asset_types", "new-connect"],
    queryFn: () => getLookupEntries("asset_types", { per: 200 }, client),
  });
  const unsized = rowsMissingSize(
    draft,
    units,
    (sizeCatalogue.data?.results ?? []) as { code: string; name: string; service?: unknown }[],
    (assetTypeCatalogue.data?.results ?? []) as { code: string; name: string }[],
  );
  // Same change, and it matters more here: a coverage check reading an empty
  // set reports NO GAPS, which is a check that cannot fail rather than a check
  // that passes (law 7). The dwelling side is the union of every non-common
  // unit; the common area is its own row.

  // ⛔ **NO QUOTE FIGURE IS ASSEMBLED IN THIS BROWSER, AND THAT IS HARD RULE 2
  // RATHER THAN A GAP IN THE SCREEN.** `quote_total` is the ONE money field the
  // commit accepts from a client, and the only honest way to fill it would be to
  // multiply a catalogue price by a count here — which `charge_code_line` names
  // as the defect it was shaped to prevent: *"A caller that multiplied first and
  // handed in a product would be the second rounding path this comment exists to
  // prevent."* So `null` travels and the server prices what it raises.
  //
  // ✔ **THE MISSING PREVIEW DOOR EXISTS SINCE `DEF-CUS-6115`**, and this
  // sentence used to end *"`DEF-BIL-5486` carries the missing preview door"*.
  // `useQuotePreview` asks `POST /connections/quote-preview`, which prices the
  // build's lines through `charge_code_line` — the function the COMMIT prices
  // with — and writes nothing. **It is a READ, so none of the above is
  // weakened:** the figure below came from the server and no arithmetic
  // happened in this browser.
  //
  // ⚠ **IT REACHES THE REVIEW SCREEN AND NOT THE PAYLOAD, DELIBERATELY.**
  // `draftManifest`'s `quoteDisplay` is what step 8 SHOWS; `commitPlanOf`'s
  // `quoteTotal` is what the commit WRITES, and they are two arguments. Sending
  // the preview back as `quote_total` would record a figure that could have
  // gone stale between the preview and the press, and the record's own
  // `quote_total_recorded` exists precisely so a disagreement is visible rather
  // than manufactured. `null` still travels.
  const quotePreview = useQuotePreview(draft, client);
  // ⚠ **`display`, NOT `stored` — `ManifestPreview.oneTimeCharges` is rendered
  // RAW** and its own contract says so: *"the SERVER'S display string or
  // `null`… never summed here"*. `stored` is the 4-decimal figure and would put
  // `315.0000` in front of a clerk, which is `DEF-088` exactly.
  const quoteDisplay: string | null = quotePreview.data?.total.display ?? null;
  const manifest = draftManifest(draft, quoteDisplay);

  // ⚠ **A REF, BECAUSE THE MUTATION IS DECLARED ABOVE THE PARK HOOK AND THE
  // HOOK ORDER IS NOT NEGOTIABLE (`BR-SHL-048 (d)`).** `useWizardPark` sits
  // below every early return's guard, so reading `park.parkedId` here would be
  // a use-before-declare. The effect just under the hook syncs it and the
  // mutation reads it at CLICK time, long after any render has settled. This
  // is `MoveInWizard.parkIdRef`'s shape, copied rather than re-reasoned.
  const parkIdRef = useRef<string | null>(null);

  // ── `DEF-CUS-8021` · CLAUDE.md HARD RULE 6 · ONE BUILD, ONE TOKEN ────────
  //
  // ⚠ **PRESSING *Create connection* TWICE BUILT TWO OF EVERYTHING.** Two
  // connections, two customers, two master accounts, two properties at one
  // address and **two payments of $250.00, each posting its own balanced
  // ledger pair** — `CON-26-0130` and `CON-26-0131`, both answered 200. With a
  // parcel number typed the second press was refused by a UNIQUENESS
  // constraint on `premises.external_ref`, which is not idempotency: it fires
  // only on the builds that type a parcel, and it answers an error where the
  // rule asks for the first result. That is how it stayed hidden.
  //
  // ⚠ **A REF, AND THAT IS THE WHOLE MECHANISM.** The token must name the
  // BUILD, not the press: minted inside `mutationFn` it would be a new string
  // on every click and would protect nothing. A ref is created once per mount
  // of this wizard — which is what a clerk means by *this build* — survives
  // every re-render between step 1 and step 5, and is replaced the next time
  // the wizard is opened. Same shape as `parkIdRef` above, copied rather than
  // re-reasoned.
  //
  // ⚠ **`crypto.randomUUID` IS THE MINTER AND NOT A COUNTER.** Two clerks at
  // two counters must never produce the same token; the tenant is the other
  // column of the server's unique index, so a collision across tenants is
  // impossible either way, but a collision WITHIN one would silently hand the
  // second clerk the first clerk's build.
  const commitTokenRef = useRef<string | null>(null);
  if (commitTokenRef.current === null) {
    commitTokenRef.current = crypto.randomUUID();
  }

  const commit = useMutation({
    mutationFn: () =>
      // ⚠ **`null`, NEVER `quoteDisplay` — see the block above.** What step 8
      // SHOWS and what the commit WRITES are two arguments on purpose.
      commitNewConnect(
        {
          ...commitPlanOf(draft, null, proposedOrders, parkIdRef.current, commitTokenRef.current),
          ...(confirmDuplicateRef.current ? { payment_duplicate_confirmed: true } : {}),
        },
        client,
      ),
  });

  // ══════════════════════════════════════════════════════════════════════
  // THE OWNER'S DOCUMENTS ARE FILED AFTER THE COMMIT — PO ruling 2026-09-21
  // ══════════════════════════════════════════════════════════════════════
  //
  // PO, verbatim: *"Step 1 — Owner & scope (p92) + you ahve to take documents
  // - rest is all good"*, and the decision log of the same day: *"nothing is
  // owned by anybody else, so the owner's documents may be captured at step 1
  // and filed against what the commit creates"*.
  //
  // ⚠ **IT CANNOT BE PART OF THE COMMIT, AND THAT IS `BR-MET-112`.** *Nothing
  // is written until step 8* — and a browser `File` is not JSON, so it cannot
  // ride the commit payload at all. The commit opens the owner's account; this
  // files the papers against it, through the door that already exists.
  //
  // ⚠ **HARD-WON LAW 2, IN BOTH DIRECTIONS.** A capture control whose files
  // reached nothing would be dead UI that renders perfectly and passes every
  // test. So this runs, and when it CANNOT run the clerk is told which files
  // did not land rather than being left to assume they did.
  const [docOutcome, setDocOutcome] = useState<{ filed: number; unfiled: number } | null>(null);
  // ⊕ lane CF-1 — step 1's Continue was pressed (the shared form's refusals).
  const [ownerTried, setOwnerTried] = useState(false);
  // ⊕ lane CF-1 — the charges step's Continue was pressed (Move-in's panels).
  const [chargesTried, setChargesTried] = useState(false);

  async function runCommit(): Promise<WizardCommitOutcome> {
    try {
      const answered = await commit.mutateAsync();
      setResult(answered);
      setDocOutcome(
        await fileOwnerDocuments(ownerDocumentsToFile(draft), answered.home, (accountId, doc) =>
          uploadAccountDocument(
            accountId,
            { file: doc.file, docType: doc.docType as AccountDocumentType, name: doc.name },
            client,
          ),
        ),
      );
      fireToast(
        t("customers.newConnect.toast", {
          defaultValue: "Connection {{connection}} created.",
          connection: answered.connection_no,
        }),
      );
      return { ok: true };
    } catch (error) {
      // BR-SHL-020 — the server's own refusal, in its own words, with every
      // answer still on screen (A18 §4).
      const reason = apiErrorText(error, translate);
      // DEF-PAY-9263 — the warning is not a refusal: step 4 shows the earlier
      // payment and the two buttons instead of a refusal sentence.
      const earlier = possibleDuplicateOf(error);
      if (earlier !== null) {
        const charges = NEW_CONNECT_STEPS.findIndex((one) => one.id === "charges") + 1;
        setPaymentDuplicate(earlier);
        setStep({ step: charges, reached: charges });
        return { ok: false, reason, refusedOnStep: charges };
      }
      // ⛔ **`DEF-MET-6110` / `DEF-MET-6111` — A RULE REFUSAL LANDS ON THE STEP
      // THE CLERK CHOSE IT.** The server names the step, because only the
      // server knows which rule refused; this resolves that name to a position
      // out of the wizard's OWN declared list, so inserting a step moves the
      // number and never this code. An envelope naming no step, or a step this
      // wizard does not have, takes the ordinary failure card on step 8 —
      // **unrecognised is never routed, in either half of this fix.**
      const owner = stepOwningRefusal(error);
      if (owner !== null) {
        setStepRefusal({ step: owner.id, message: reason });
        setStep({ step: owner.position, reached: owner.position });
        return { ok: false, reason, refusedOnStep: owner.position };
      }
      return { ok: false, reason };
    }
  }

  // ══════════════════════════════════════════════════════════════════════════
  // CR-035 — PARK AND RESUME. NINE STEPS, AND IT IS THE FLOW THAT NEEDS THIS
  // MOST: a new connect waits on a permit, an inspection and a crew, and CR-035
  // is the requirement that those waits stop being a reason to abandon a form.
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **WHAT A RESUME PUTS BACK, AND THE CARE IT TAKES, IS `draftFromPark`'s**
  // — moved out of this file on 2026-09-21 so a case can call the thing that
  // broke (`DEF-CUS-6135`). It is not a summary that lives in two places: this
  // comment names the function and the reasoning is there, which is what
  // CLAUDE.md asks for wherever a note restates what code does.
  const park = useWizardPark({
    steps: NEW_CONNECT_STEPS,
    step,
    // ⚠ **THE OTHER DOOR A STORED STEP COMES THROUGH (`CR-150-BRC09`).** A
    // resume reads `wizard_parks.step`, an index into the list as it stood
    // when the clerk parked — eight steps, for every row parked before
    // 2026-09-28. Without this, a draft parked on *Charges* reopens on
    // *Review*, past the money it was waiting for. The FULL map here, and the
    // narrow one on the address: a parked number is unambiguously old-shape
    // in the only way that matters, because landing one step EARLY on a
    // hydrated draft costs a clerk one press and nothing else.
    storedStep: newConnectStoredStep,
    parkOpen,
    context: {
      flow: "new_connect",
      // The address the connection is for, in the clerk's own typing, falling
      // back to the owner while step 2 is still ahead of them. COPIED, never a
      // join (BR-SHL-048 (a)) — and there is nothing to join to anyway: a new
      // connect has no premise id until it commits.
      subjectLabel: draft.premise.address !== "" ? draft.premise.address : draft.owner.name,
      // `BR-SHL-048 (d)` — the build this wizard is finishing, carried as
      // COPIED VALUES (clause (a) used rather than bent). `{}` on a New
      // Connect started from scratch. The reasoning, and why this stopped
      // being `{}` on 2026-09-21, is `parkSubjectRefOf`'s.
      subjectRef: parkSubjectRefOf(draft),
      values: { draft },
    },
    t: translate,
    client,
    // ⚠ **ONE CALL, AND THE BODY LIVES IN `newConnectDraft` ON PURPOSE
    // (`DEF-CUS-6135`).** The whole of this defect was inside this callback —
    // the park carried the build id and the hydrate dropped it one line later
    // — and a callback is reachable only by driving eight steps of a browser,
    // which is why the suite proved the PARK and never the RESUME. As a
    // function it is one call a case can make. See `draftFromPark` for what it
    // restores and why `hydrateForm` cannot do the last three fields.
    onHydrate: (row) => setDraft(draftFromPark(row)),
    // CR-035 · AMENDMENT 1 (PO 2026-08-26) — a parked draft lands on the tab
    // for its OWN kind of work, not on a ninth queue. `parkedHomePath` is the
    // one place those five destinations are named.
    onParked: () => navigate(tenantPath(parkedHomePath("new_connect"))),
  });
  // `DEF-SHL-10001` — the leave-page popup's *Save as draft* writes the
  // same `wizard_parks` row this wizard's Park writes, as a draft.
  const leaveDraft: LeaveDraft = {
    onSave: park.saveDraft,
    savedMessage: t("leaveGuard.saved", { place: t("customers.accounts.tab.newConnects") }),
  };
  // `BR-SHL-048 (d)` — see `parkIdRef` above. `park.parkedId` is `?parked=`,
  // so this is the draft the clerk resumed from, and `null` on a wizard that
  // was never parked.
  useEffect(() => {
    parkIdRef.current = park.parkedId;
  }, [park.parkedId]);

  /** B19 §12.2 — TWO controls, and they stay two. `Save & exit` leaves quietly
   *  and writes nothing; `Park` records what is being waited on, a note and a
   *  reminder, and still writes nothing outside the draft store (BR-SHL-048:
   *  no premise, no units, no plan assignment until this is executed). */
  const exit: WizardExit = {
    onSaveAndExit: () => navigate(tenantPath("/accounts")),
    // ✅ BR-SHL-047 is TRUE rather than merely ruled since CR-035 — the shared
    // sentence went null when `wizardParkPort()` stopped returning one, and
    // that single `return` is what turned all five wizards on.
    parkBlockedReason: parkStoreBlockedReason(translate),
    parkOpen,
    onParkOpenChange: setParkOpen,
    onPark: park.onPark,
    dateFormat,
    parkedAt: park.parkedAt,
  };

  if (result !== null) {
    // ⚠ `DEF-CUS-9175` (PO 2026-10-02: *"on open connection it is going to
    // Account it should go to new connect request link"*) — *Open the
    // connection* lands on the BUILD'S OWN PAGE, NCT-02, which `CR-151-BRC09`
    // restored on 2026-09-28, and `NewConnectDone` now owns that address. This
    // passed `buildHomePath(result.home)` from wave O, when that page had been
    // deleted, and so opened the owner's account.
    return (
      <NewConnectDone
        result={result}
        t={translate}
        // ⚠ **WIRED, OR THE UPLOAD ABOVE IS INVISIBLE (law 2).** A clerk
        // who handed over three deeds and is told nothing assumes all three
        // landed; the count is a fact rather than a reassurance.
        documents={docOutcome}
      />
    );
  }

  // ══════════════════════════════════════════════════════════════════════════
  // THE FIVE — `CR-150-BRC09`, PO ruling 2026-09-28
  // ══════════════════════════════════════════════════════════════════════════
  //
  // ⚠ **THE THREE ABSORBED STEPS ARE GONE FROM THIS LIST AND THEIR FIELDS ARE
  // NOT.** *"we dont want any information to be reduced or lost"*. `services`
  // and `plans` are inside `UnitsStep` (the UNITS lane's six extra props
  // above); `communication` renders inside step 5 until the REVIEW lane draws
  // it into the review's own Messages table.
  //
  // ⚠ **A STEP'S `validate` IS ITS OWN, AND ABSORBING MEANS ABSORBING THE
  // GUARD TOO.** Step 3 now has to refuse what `units` AND what `services`
  // refused; dropping the services guard because its step no longer exists
  // would let a unit take sewer without water — `TC-NCT-6`, a rule with a
  // meter behind it, silently un-enforced by a layout change.
  const steps: WizardStep[] = [
    {
      id: "customer",
      label: t(NEW_CONNECT_STEPS[0].labelKey, { defaultValue: NEW_CONNECT_STEPS[0].en }),
      content: (
        <OwnerScopeStep
          draft={draft}
          onPatch={patch}
          t={translate}
          client={client}
          showErrors={ownerTried}
        />
      ),
      // BR-MET-111 — without a name there is no customer, and without a
      // customer the connection charges have nowhere to go (DEF-650). Plus the
      // two the old step 2 guarded: the scope decides how many units the next
      // steps ask for, so it cannot be left unanswered either.
      //
      // ⚠ **AND THE IDENTITY SHORTFALL BLOCKS THE STEP (`DEF-CUS-5467`).**
      // `BR-CUS-1024` refuses the owner's master account outright without a
      // party kind and an identifier, so letting the clerk walk on means
      // discovering it after eight steps of a build — the PO's words on the
      // accounts wizard were *"never after the account is created"*. An
      // ATTACHED customer clears it, because the commit names them instead.
      //
      // ⚠ **AND IT SAYS SO IN ITS OWN WORDS, HERE, SINCE 2026-09-28 (PO
      // reported bug 1).** The strip that stood under the owner's fields is
      // deleted — it refused an untouched form before anybody had answered —
      // and `WizardStepVerdict` is `boolean | string` precisely so a step can
      // hand the frame its own sentence at the press (`DEF-936`). Returning
      // bare `false` here would have been the deletion losing the message:
      // the frame's generic *check the fields* tells a clerk to look at
      // fields that may all be filled in. **Nothing is let through that was
      // refused before** — the same `ownerIdentityShortfall` decides, and
      // `?? false` falls back to the generic rather than inventing words.
      validate: () => {
        // ⊕ lane CF-1 — from the first press the shared form shows its refusals.
        setOwnerTried(true);
        const shortfall = ownerIdentityShortfall(draft.owner);
        if (shortfall !== null) {
          return ownerShortfallSentence(shortfall, translate) ?? false;
        }
        // ⊕ `DEF-CUS-9193` — PO ruling Q4: a birth date in the future or an
        // owner under 18 is refused, for the co-applicant too.
        const today = todayIn(timeZone);
        for (const person of [draft.owner, draft.coApplicant]) {
          // ⊕ `DEF-CUS-9261` — a company has no birth date to check.
          if (person === null || !ownerHasABirthDate(person)) continue;
          const dob = ownerBirthDateSentence(person.dateOfBirth, today, translate);
          if (dob !== null) return dob;
        }
        // ⊕ `DEF-CUS-9830` — an open co-applicant panel needs her name, and
        // nothing else (PO ruling 2026-10-06); an email only its shape.
        const coShortfall = coApplicantShortfall(draft.coApplicant);
        if (coShortfall !== null) return translate(coShortfall);
        // ⊕ lane CF-1 (2026-10-18) — the shared form's own rules, Move-in's:
        // a typed email or phone must be well formed, and every co-owner card
        // needs a name and well-formed contact details.
        const format = customerFormatProblem(ownerToCustomer(draft.owner));
        if (format !== null) return translate(format);
        const cards = draftCoOwners(draft);
        if (cards.on && draft.coOwners !== undefined) {
          const card = coOwnerProblem(cards.rows) ?? coOwnerFormatProblem(cards.rows);
          if (card !== null) return translate(card);
        }
        // ⊕ `DEF-CUS-9242` — the owner's own fields (drawn only for a NEW
        // customer) and the account's, each as the step shows them.
        const ownFields = fillIn([
          ...(draft.owner.matchedCustomerId !== null
            ? []
            : missingRequiredLabels(ownerFieldsReg, draft.ownerCustomData ?? {})),
          ...missingRequiredLabels(accountFieldsReg, draft.accountCustomData ?? {}),
        ]);
        if (ownFields !== null) return ownFields;
        return draft.owner.name.trim() !== "" && draft.scope !== "" && draft.mode !== "";
      },
    },
    {
      id: "premise",
      label: t(NEW_CONNECT_STEPS[1].labelKey, { defaultValue: NEW_CONNECT_STEPS[1].en }),
      // ⚠ **`DEF-MET-7690` — STEP 2 CAN BE REFUSED BY THE SERVER TOO, AND HAD
      //     NOWHERE TO SAY SO.** `units` and `charges` have carried a
      //     `StepRefusal` since `DEF-MET-6110`; this step did not, so a
      //     refusal about the ADDRESS BLOCK — an unknown read route above all
      //     — landed on the ordinary failure card at step 8 naming neither the
      //     field nor the step. The server names the step now
      //     (`connections._premises_made_for_the_wizard`) and this is where
      //     the sentence lands.
      content: (
        <>
          <StepRefusal step="premise" message={refusalOn("premise")} />
          <PremiseStep draft={draft} onPatch={patch} t={translate} />
        </>
      ),
      // ⛔ **THE WIZARD ASKS FOR THE PLAN — PO ruling 2026-09-21, verbatim:
      // *"ask for plan"*.** The review step used to print `Plan assignments 0`
      // as a plain fact, call the counts *"a contract"* and let the clerk press
      // anyway — and the press then failed at the server, because
      // `_apply_unit_plan` refuses an empty `tariff_id` by name. The clerk had
      // walked six more steps by then. **This is that ask, at the step where
      // the plan is chosen and can be answered.**
      //
      // ⚠ **THE ASK IS ABOUT DWELLINGS AND ONLY DWELLINGS**, which is the other
      // ruling of the same day: *"common area dont need rate plan as of now"*.
      // `planApartments` is the dwellings' plan and `planCommonArea` is asked by
      // nobody and sent by nobody — **a wizard that demanded one for a common
      // area would re-create the refusal the PO has just removed.**
      validate: () => {
        if (draft.premise.address.trim() === "") {
          return false;
        }
        // ⊕ `DEF-CUS-9242` — a NEW property's required fields hold this step
        // (Add Premises does the same); a property on file shows them read-only.
        if (draft.premise.premisesId === "") {
          const ownFields = fillIn(missingRequiredLabels(premiseFieldsReg, draft.premise.customData ?? {}));
          if (ownFields !== null) return ownFields;
        }
        if (draft.planApartments === "") {
          return t("customers.newConnect.step3.planRequired", {
            defaultValue: "Choose a plan for the units.",
          });
        }
        return true;
      },
    },
    {
      id: "units",
      label: t(NEW_CONNECT_STEPS[2].labelKey, { defaultValue: NEW_CONNECT_STEPS[2].en }),
      content: (
        <>
          <StepRefusal step="units" message={refusalOn("units")} />
          {/* ⚠ **STEP 3 ABSORBS *Map services* AND *Work orders*** —
              `CR-150-BRC09`, PO: *"we dont want any information to be reduced
              or lost - 8 steps → 5"*. The six props below are the two absorbed
              steps' own, unchanged and already in scope here; the audit of
              what moved where is beside the drawings. The `services` and
              `plans` entries under this one are the MODEL lane's to drop. */}
          <UnitsStep
            draft={draft}
            units={units}
            labelsAlreadyHere={labelsAlreadyHere}
            breaches={breaches}
            sewerGaps={sewerGaps}
            proposed={proposedOrders}
            proposalsUnavailable={proposalQuery.isError}
            onPatch={patch}
            client={client}
            t={translate}
            dateFormat={dateFormat}
          />
        </>
      ),
      // ⛔ **A BUILD NEEDS A DWELLING, NOT MERELY A UNIT (`BR-MET-1179`'s other
      // half).** This read `units.length > 0`, and with *Include a common-area
      // unit* ticked by default that was TRUE for a build with no dwelling at
      // all — which is exactly what the acceptance walk got when a clerk built
      // a house and left the unit boxes empty. The tick is now absent for the
      // four single-occupier types, so for them the old check would simply
      // block with the frame's generic sentence; this says what is missing.
      //
      // ⚠ **AND THE OLD STEP 4's GUARD IS HERE TOO, BECAUSE ITS FIELDS ARE
      // (`CR-150-BRC09`).** `TC-NCT-6` — sewer derives from water, so a unit
      // taking sewer without it is REFUSED, not warned — and a unit may never
      // take a service the street cannot deliver. Both were the `services`
      // step's `validate`, and a merged step that kept the fields and dropped
      // the guard would enforce neither while looking complete. Old step 5
      // (work orders) validated `true` and contributes nothing.
      validate: () => {
        if (!units.some((unit) => !unit.isCommonArea)) {
          return t("customers.newConnect.step4.dwellingRequired", {
            defaultValue: "Add at least one unit.",
          });
        }
        if (unsized.length > 0) {
          const named = unsized
            .slice(0, 3)
            .map((row) => `${row.unit.label} · ${t(`rating.service.${row.service}`, { defaultValue: row.service })}`);
          const more = unsized.length - named.length;
          return t("customers.newConnect.units.sizeRequired", {
            defaultValue: "Choose a size: {{rows}}.",
            rows: more > 0 ? `${named.join(", ")} +${more}` : named.join(", "),
          });
        }
        return breaches.length === 0 && sewerGaps.length === 0;
      },
    },
    {
      id: "charges",
      label: t(NEW_CONNECT_STEPS[3].labelKey, { defaultValue: NEW_CONNECT_STEPS[3].en }),
      content: (
        <>
          <StepRefusal step="charges" message={refusalOn("charges")} />
          {paymentDuplicate !== null && (
            <PossibleDuplicateNotice
              earlier={paymentDuplicate}
              working={commit.isPending}
              onGoBack={() => setPaymentDuplicate(null)}
              onRecordAnyway={() => {
                confirmDuplicateRef.current = true;
                setPaymentDuplicate(null);
                void runCommit().then((outcome) => {
                  confirmDuplicateRef.current = false;
                  if (!outcome.ok && outcome.refusedOnStep === undefined) {
                    setStepRefusal({ step: "charges", message: outcome.reason });
                  }
                });
              }}
            />
          )}
          <ChargesStep
            draft={draft}
            onPatch={patch}
            t={translate}
            dateFormat={dateFormat}
            tried={chargesTried}
          // ⚠ **WIRED, NOT OPTIONAL-AND-UNPASSED (hard-won law 2).** Step 6
            // reads the tenant's charge catalogue through this client; a prop
            // nothing passes is dead UI that renders nothing and passes every
            // test. Four defects in one day taught that.
            client={client}
          />
        </>
      ),
      // ══════════════════════════════════════════════════════════════════
      // TWO THINGS STEP 6 NOW REFUSES, AND BOTH WERE FOUND AFTER THE PRESS
      // ══════════════════════════════════════════════════════════════════
      // ⚠ **`DEF-CUS-6112` — A CHARGE WITH NO PAYMENT TERMS COMMITTED AND
      // RAISED NOTHING.** The done panel then said so, after the build existed,
      // with no way back into the wizard: `quote_total` NULL, no invoice, no
      // audit row, on a build the clerk believed was priced. `BR-BIL-024` is
      // right that the terms are captured and never guessed — the screen was
      // wrong to let the one field that decides whether any money exists be
      // skipped in silence.
      //
      // ⚠ **NO CHARGE ON THE LIST MEANS NO TERMS ARE NEEDED**, which is why
      // this is a condition. A build that charges nothing is a real and lawful
      // build; the server reports that absence rather than refusing, and so
      // does this.
      //
      // ⚠ **`DEF-MET-6110` — A CODE THE CATALOGUE CANNOT PRICE LOST THE WHOLE
      // BUILD.** `TAP`, `IMPACT` and `DAMAGE` are live charge codes with no
      // amount at all; picking one committed eight steps of work and answered
      // **500**, and nothing was written. The preview asks the pricing engine
      // the same question the commit will ask, so the refusal lands where the
      // code was PICKED. It blocks only on a DEFINITE server answer — a dropped
      // request says nothing about the charge code (see `quoteCannotBePriced`).
      validate: () => {
        if (quoteCannotBePriced(quotePreview.data) !== null) {
          return t("customers.newConnect.step6.cannotBePriced", {
            defaultValue: "This charge has no price. Choose another.",
          });
        }
        // ⊕ `DEF-CUS-9212` — a charge needs somebody to bill, or the press
        // answers 422 after all five steps. ⊕ **`DEF-CUS-9228` (PO 2026-10-02,
        // item 1: *"The owner asked for the work, so the owner pays"*)** — a
        // single-family home now opens the OWNER's own account, so this fires
        // only on a build that opens no owner's account at all.
        // ⊕ `DEF-CUS-10048` — the sentence names the thing actually missing
        // (owner, type, one home, or the master account), never *master* over
        // a single-family home. Same condition as before: `noOneToBill`.
        const noPayer = noOneToBillReason(draft);
        if (noPayer !== null) {
          return t(noPayer);
        }
        if (draft.quoteLines.length > 0 && draft.quoteDueDays.trim() === "") {
          return t("customers.newConnect.step6.dueDaysRequired", {
            defaultValue: "Say when this charge is due.",
          });
        }
        // ⚠ **`BR-MET-1187` — AN AMOUNT WITH NO TENDER, OR A TENDER WITH NO
        // AMOUNT, IS REFUSED BY THE SERVER BY NAME.** Asked here so the
        // refusal reaches the clerk on the step that chose it rather than as a
        // 500 after thirty-three acts (`DEF-MET-6110`'s ruling). The rule
        // itself lives with the fields, in `paymentBlocksContinue`.
        const payment = paymentBlocksContinue(draft);
        if (payment !== null) {
          return t(payment);
        }
        // ⊕ lane CF-1 — Move-in's Tax and Discounts panels hold the step by
        // Move-in's own rules (a type, a number, an expiry and the file for
        // an exemption; a discount on every row).
        const extras = moveInExtrasProblems(draft);
        if (extras.length > 0) {
          setChargesTried(true);
          return t(MOVE_IN_EXTRAS_PROBLEM_KEY[extras[0]]);
        }
        return true;
      },
    },
    {
      id: "review",
      label: t(NEW_CONNECT_STEPS[4].labelKey, { defaultValue: NEW_CONNECT_STEPS[4].en }),
      content: (
        <>
        <ReviewStep
          draft={draft}
          manifest={manifest}
          /* ⚠ **THE 4-DECIMAL `stored` FIGURE AND ITS `CHAR(3)`, SO THE
              REVIEW TILE CAN GO THROUGH `MoneyCell` (`BR-SHL-023`, hard rule
              2).** The manifest's own `oneTimeCharges` is the server's
              `display` string and step 8 printed it RAW — `1035.00` where a
              clerk expects `$1,035.00` (PO 2026-09-28, reported bug 1's
              drawing: *"1035.00 is shown as $1,035.00"*). Both are REQUIRED
              props rather than optional ones, so a host cannot mount this
              step without answering the currency question (hard-won law 2).
              Neither is arithmetic: the server priced and rounded once. */
          quoteTotal={quotePreview.data?.total.stored ?? null}
          quoteCurrency={quotePreview.data?.currency ?? null}
          workOrderCount={commitWorkOrdersOf(draft, proposedOrders).length}
          client={client}
          onPatch={patch}
          t={translate}
        />
          {/* ⚠ **THE ABSORB BRIDGE THAT STOOD HERE IS GONE — `DEF-CUS-7910`.**
              It rendered the `CommunicationStep` panel beneath the review and said
              why, honestly: *"until the REVIEW lane draws it there, the step's
              own panel renders here so no message, channel or template is
              lost."* **The Review lane drew it there in `2.401.0`** —
              `NewConnectReviewStep.tsx` mounts `WhoWeAreTelling` and
              `MessagesFold` itself — and from that commit this screen showed
              *Who we are telling* and *Messages* **TWICE**, including two
              copies of every template `<select>`, so the same `id` appeared
              twice in one document.

              ⚠ **THIS IS HARD-WON LAW 2'S MIRROR, THE HOLD WITH A CLOCK IN
              IT.** The comment was correct the day it was written and rotted
              the day its condition was met, because landing the screen and
              releasing the thing that was standing in for it are two acts and
              only the first feels like the work. CLAUDE.md says it outright:
              *when you land a screen, grep for the control that was holding
              it.* This lane landed the screen and did not, for one build.

              ⚠ **NOTHING MECHANICAL COULD HAVE CAUGHT IT.** Every presence
              check — `page.$(sel)`, `toContain` — finds the FIRST copy and
              stops; a duplicate passes them all. It was found by looking at a
              full-height screenshot, which is law 6 doing the only job no
              gate in this repo does. */}
        </>
      ),
      validate: () => true,
    },
  ];

  // The step the head is naming. Indexed by the CURRENT step and clamped, so a
  // stale `?step=` from a bookmark cannot render an empty title.
  const currentStepDef = {
    ...NEW_CONNECT_STEPS[Math.min(Math.max(step, 1), NEW_CONNECT_STEPS.length) - 1],
    ...NEW_CONNECT_STEP_TITLES[Math.min(Math.max(step, 1), NEW_CONNECT_STEPS.length) - 1],
  };

  return (
    <div data-screen={NEW_CONNECT_SCREEN}>
      {/* ⚠ **THE TITLE CHANGES PER STEP AND THE `rollup` IS GONE
          (`DEF-CUS-5187`).** The blueprint draws a different H1 on every one of
          the eight screens — *Who is asking, and what for?* · *The premise* ·
          *The units* · … — under one unchanging `NEW CONNECT` kicker. The
          rollup read *"Nine steps · who is asking, the address, its units, its
          services and its pricing"*: a step count written out in English prose,
          which is the exact shape that told every move-in clerk there were five
          steps over a rail drawing six. The count now appears once, in the step
          line below, derived from the step list. */}
      <PageHeader
        kicker={t("customers.newConnect.kicker", { defaultValue: "New connect" })}
        title={t(currentStepDef.titleKey, { defaultValue: currentStepDef.titleEn })}
        backTo={{ to: tenantPath("/accounts"), label: t("customers.accounts.title") }}
      />
      {/* ⚠ **THE STEP LINE — DRAWN UNDER THE TITLE OF ALL EIGHT SCREENS, AND
          THE PRODUCT PUT A TWENTY-WORD INSTRUCTION WHERE THE STEP'S NAME GOES.**
          Same shared key the move-in, move-out and new-account wizards render,
          so the four cannot say it four ways, and both halves come off
          `NEW_CONNECT_STEPS` rather than a typed number. */}
      <Note>
        {t("customers.wizard.stepOfNamed", {
          step,
          of: NEW_CONNECT_STEPS.length,
          name: t(currentStepDef.labelKey, { defaultValue: currentStepDef.en }),
          defaultValue: "Step {{step}} of {{of}} · {{name}}",
        })}
      </Note>
      {/* ⚠ **BR-MET-112 IS STILL THE CONTRACT AND IT IS NO LONGER A SENTENCE
          ON EVERY STEP** (PO 2026-09-28, reported bug 1: *"To Much text on
          every step reduce it"*; the redesign drawings list it under *Removed
          from this step* on all five). *"Nothing is written until step 8.
          Create connection writes it."* is RATIONALE — why the product works
          this way — which B14 rule 33 gives **zero words on screen**, and
          rationale is REMOVED rather than shortened. The BEHAVIOUR is
          untouched: nothing is written until `runCommit`, and the commit
          button below still says what it does. */}
      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setStep}
        commitLabel={t("customers.newConnect.commit", { defaultValue: "Create connection ✓" })}
        commitFailedTitle={t("customers.newConnect.commitFailed", {
          defaultValue: "The connection was not created.",
        })}
        onCommit={runCommit}
        onCommitted={() => undefined}
        exit={exit}
        saveDraft={leaveDraft}
      />
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-030 W6 task 6.11 (S87 `NCT-03.1`–`NCT-03.9`) · B18 §5.4.10 (the
//         nine steps as drawn 2026-08-25) · §5.4.4 · §5.4.5 · §8.3 ·
//         BR-MET-111 · BR-MET-112 · BR-MET-113 · BR-MET-115 · BR-SHL-018/019/
//         025/047 · OQ-249 · OQ-370 · OQ-379
// generated: 2026-08-25 by lane W6-SCREENS
// checklist: A=n/a(no backend half in this lane) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions:
//   E1 ⛔ **THE COMMIT DOOR DOES NOT EXIST.** `POST /connections/commit` is not
//      mounted; `apps/metering/api.py` serves `GET /connections` and nothing
//      else on this resource. The wizard CALLS it and renders the failure in
//      the server's own words. REPORTED with the view code — this lane does not
//      own `api.py`.
//   E1 ⛔ **THE ROUTE IS NOT MOUNTED.** `App.tsx` is not this lane's file, so
//      `/connections/new` reaches nothing until the reported two lines land.
//      Stated plainly rather than left to be discovered (hard-won law 2).
//   E3 **TASK 6.4 IS REFRAMED AND STEP 6 SHOWS THE REFRAME.** The PO ruled
//      2026-08-25: *"We are making it flexible; utility users can issue as many
//      work order they want … they will develope these templats in work order
//      section"*. So batching is NOT a system rule — `25 units → 7 orders` is
//      an OUTCOME of that tenant's templates. The wizard therefore proposes no
//      orders and says why, and the *"Split into individual orders"* affordance
//      lives on the connection's Work orders tab where the orders are.
//   E3 the per-unit service grid is a BULK ROW plus a common-area set, which is
//      what the drawing's own example does; a per-unit override is owed.
//   E3 no quote is assembled and none is printed — the wizard has no request,
//      and the drawn `$14,435.00` belongs to `SR-26-0043`, not to every build.
//   E3 the drawn `$150.00` deposit policy and the `$762.50` monthly total are
//      NOT rendered: neither is served to this screen and both are money.
//   E3 `Park` is offered and blocked with the shared sentence (BR-SHL-047) —
//      a wizard that has written nothing is not a row a park can hang on.
//   E3 S87 is B18's own name for this screen; the ID ALLOCATION is D1 and is
//      the PO's. `screenIds.ts` has no entry and this lane does not own it.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

/**
 * **FILE THE OWNER'S STEP-1 DOCUMENTS AGAINST WHAT THE COMMIT CREATED — PO
 * ruling 2026-09-21.**
 *
 * Decision log of the same day, verbatim: *"nothing is owned by anybody else,
 * so the owner's documents may be captured at step 1 and filed against what
 * the commit creates"*.
 *
 * ⚠ **IT IS A FUNCTION WITH AN INJECTED DOOR BECAUSE THAT IS THE ONLY WAY LAW
 * 2 CAN BE ASSERTED.** *Built is not wired* — a capture control whose files
 * reached nothing would render perfectly, pass `tsc` and pass every test. The
 * upload is handed in, so a test can watch it happen; written inline in the
 * component it could only be watched by driving eight wizard steps, which is
 * exactly the assertion nobody writes.
 *
 * ⚠ **THE COMMIT'S OWN ANSWER DECIDES, NEVER A GUESS.** `home` is
 * `{kind: "account"}` exactly when the build opened the owner's account, and
 * `create_owner_account` is OPT-IN (`BR-MET-1024`) — so a clerk who unticked
 * it has nowhere to hang these, and the COUNT says so rather than the files
 * disappearing.
 *
 * ⚠ **ONE REFUSAL DOES NOT STOP THE REST AND NONE OF THEM UNDOES THE BUILD.**
 * The build is committed and immutable by the time this runs; a 415 on the
 * third file must not lose the two that landed, nor leave a clerk thinking the
 * whole press failed.
 */
export async function fileOwnerDocuments(
  held: readonly DraftDocument[],
  home: BuildHome | null,
  upload: (accountId: string, doc: DraftDocument) => Promise<unknown>,
): Promise<{ filed: number; unfiled: number } | null> {
  if (held.length === 0) {
    return null;
  }
  const account = home?.kind === "account" ? home.id : null;
  if (account === null) {
    return { filed: 0, unfiled: held.length };
  }
  let filed = 0;
  for (const doc of held) {
    try {
      await upload(account, doc);
      filed += 1;
    } catch {
      // Counted as unfiled below. The clerk is told the number.
    }
  }
  return { filed, unfiled: held.length - filed };
}
