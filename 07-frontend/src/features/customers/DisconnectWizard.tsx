// ── Trace ──────────────────────────────────────────────
// Change:   **THE DISCONNECT WIZARD GOES FROM FIVE STEPS TO FOUR** —
//           `Choose · Check · Schedule · Confirm`, 2026-09-25. MAINTENANCE
//           (`12-governance/22-product-maintenance-process.md`): a live screen
//           redrawn end to end is maintenance, borrowing exactly one thing from
//           Build — the drawing step. Defects: `DEF-CUS-6750`, `DEF-CUS-6751`,
//           `DEF-CUS-6752`, `DEF-CUS-6753`.
// Rules:    **BR-CUS-1096** (a protection WARNS the clerk; it never stops them)
//           · **BR-CUS-1097** (the balance need not be clear to reconnect —
//           SUPERSEDES `BR-CUS-104`'s gate clause) · **BR-CUS-1098** (a master
//           account's cut is a building's cut) · **BR-CUS-1099** (no recorded
//           proof of certified service WARNS) · **BR-CUS-1100** (the block
//           marks the ACCOUNT and the CUSTOMER, never the address) ·
//           BR-CUS-103 · BR-CUS-105 · BR-CUS-100 · BR-BIL-007 · BR-SHL-019 ·
//           BR-SHL-025 · B14 rules 6, 20, 21, 31, 32, 33, 41, 42, 43, 44
// Tests:    07-frontend/src/features/customers/DisconnectWizard.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · ⚠ THE SUPERSEDED SENTENCE THIS FILE CARRIED — `DEF-CUS-6751`
// ══════════════════════════════════════════════════════════════════════════
// **Until this commit §2 of this header read:** *"A customer must clear the
// arrears PLUS the fee before `mark_reconnecting` will accept them."*
//
// **THAT CLAUSE WAS SUPERSEDED ON 2026-09-25 BY `BR-CUS-1097`** — PO, verbatim,
// choosing option (a) of two: *"Show what's still owed and let the clerk
// proceed"*. A clerk may restore service on an account that still owes money;
// **`$8,315.00` is now what the clerk is SHOWN, not what they must collect
// first.** Option (b), requiring the balance to be clear, is what the code does
// today and is what the PO declined.
//
// ⚠ **`BR-CUS-104` IS AMENDED, NOT WITHDRAWN.** The fee's TIMING is untouched:
// it still lands **at the cut**, it is still a real receivable, and step 4
// still shows it there. Only the GATE is gone.
//
// ⚠ **AND THE SAME SENTENCE IS STILL IN
// `04-docs/05-modules/03-customers/06-epics/EP-CUS-10-transfer-disconnect-wizards.md`.**
// Amended by this lane in the same commit, because closing a ruling is a
// FAN-OUT and not a status edit — and because a justification by reference
// outlives the justification.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · WHY FOUR, AND WHY NOT r10's STEPPER
// ══════════════════════════════════════════════════════════════════════════
// B18 §5.8.7 and blueprint p136–p141 both draw FIVE. The rebuild draws four —
// **four words, each naming an ACT** — and the carry-over is written out in
// `DISCONNECT_STEPS`' own docstring so nothing is lost by subtraction.
//
// ⚠ **THE STEPPER IS NOT INHERITED FROM THE PROTOTYPE, AND THAT IS A LESSON
// RATHER THAN A PREFERENCE.** `billRunShared.tsx` was built to r10's SIX-step
// stepper — its own docstring says so — while the Billing blueprint draws four,
// argues for them in prose and carries a whole carry-over map on p86–p88. **A
// lane obeying `CLAUDE.md`'s pointer built the wrong shape and passed every
// check**, and four further lanes then built onto it. The four here come from
// the rebuild's own drawings, read AS IMAGES (B14 rule 42).
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · THE RAIL IS NOT NAVIGATION, AND IT IS NO LONGER DRAWN AS IF IT WERE
// ══════════════════════════════════════════════════════════════════════════
// `nav.reached` never runs ahead of `nav.step` in this wizard, so under
// `BR-SHL-018` every rail cell was a `<button disabled>` — **four controls that
// do nothing, announced to a screen reader as four buttons and tabbed through
// by a keyboard.** Item 3.16: Back and Continue only is fine; then do not draw
// them as buttons. `railNavigable={false}` is the kit's new opt-in for that,
// absent everywhere else so the other twenty-two wizards are byte-identical.
//
// ══════════════════════════════════════════════════════════════════════════
// 4 · ONE ACTION, AND IT IS STILL TWO CALLS
// ══════════════════════════════════════════════════════════════════════════
// PO 2026-09-21: *"we need to keep only park, complete - two action only"*. The
// proof of service is draft data and `Complete` writes it.
//
// ⛔ **`POST /disconnects/schedule` DOES NOT ACCEPT A PROOF**, so one clerk
// action is two HTTP calls, and if the proof lands and the schedule then fails
// a proof row is left behind — `DEF-CUS-6035`, FILED rather than worked around.
// Retrying is safe: the proof's second write is refused by name as
// `proof_already_recorded`, which is the server holding the line.
//
// ⚠ **AND THE `whatHappened` NOTE HAS NOWHERE TO GO YET — ITEM 3.13, HALF
// KEPT.** The five-step wizard threw the clerk's note away entirely: nothing on
// the draft held it and nothing sent it. It is draft data now, it survives a
// park and a resume, and it is on the payload this wizard assembles — but
// `schedule_cut`'s keyword arguments are `account_id`, `cut_on`, `reason`,
// `services` and `deposit`, and **there is no field for a note.** So the note
// is KEPT on the draft and is NOT yet written to the case: `DEF-CUS-6764`, and
// the server half is lane CUTPATH's. **Stated rather than quietly dropped** —
// a screen that took the note and silently discarded it is exactly the defect
// being fixed.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountDetail } from "@/api/endpoints";
import type { AccountDetail } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { WizardFrame } from "@/components/WizardFrame";
import type { LeaveDraft } from "@/components/LeaveGuard";
import type { WizardCommitOutcome, WizardExit, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { useAccountSearch } from "./accountFinder";
import type { AccountSearchState } from "./accountFinder";
import { parkStoreBlockedReason, stepFromParam } from "./moveShared";
import { accountHeadline } from "./customersShared";
import { parkedHomePath, parkedString, useWizardPark } from "./wizardPark";
import type { Translator } from "./newConnectShared";
import { getLadderState, getProtectionCheck, scheduleCut } from "./transferDisconnectEndpoints";
import type {
  DisconnectCaseRecord,
  DisconnectPreflightBlocker,
  ProtectionCheckResult,
} from "./transferDisconnectEndpoints";
import {
  DISCONNECTS_TAB_PATH,
  DISCONNECT_ACCOUNT_PARAM,
  DISCONNECT_STEPS,
} from "./transferDisconnectShared";

import { ChooseStep } from "./disconnect/steps/ChooseStep";
import { CheckStep } from "./disconnect/steps/CheckStep";
import { ScheduleStep } from "./disconnect/steps/ScheduleStep";
import { ConfirmStep } from "./disconnect/steps/ConfirmStep";
import {
  AUDIENCE_OCCUPANTS,
  AUDIENCE_OWNER,
  emptyDisconnectDraft,
  hydrateDraft,
  proofIsComplete,
  proofIsStarted,
  scheduleCutPlanOf,
  seededChecks,
  servicesCut,
} from "./disconnect/disconnectDraft";
import type { DisconnectDraft, DisconnectProof } from "./disconnect/disconnectDraft";
import { getAccountNotices, postProofOfService } from "./disconnect/disconnectNotices";
import { getDisconnectTerms } from "./disconnect/disconnectTerms";
import {
  disconnectRefusalText,
  disconnectRefusalTextForCode,
} from "./disconnect/disconnectRefusal";

// ⚠ **RE-EXPORTED, NOT RE-DECLARED.** Suites and one page import the draft
// helpers from this module by name. A lane that later removes one of these
// lines is making a breaking change and should say so.
export {
  emptyDisconnectDraft,
  emptyDisconnectProof,
  hydrateDraft,
  proofIsComplete,
  proofIsStarted,
  scheduleCutPlanOf,
  servicesCut,
  treatmentsOf,
} from "./disconnect/disconnectDraft";
export type { DisconnectDraft, DisconnectProof } from "./disconnect/disconnectDraft";
export { ChooseStep } from "./disconnect/steps/ChooseStep";
export { CheckStep } from "./disconnect/steps/CheckStep";
export { ScheduleStep } from "./disconnect/steps/ScheduleStep";
export { ConfirmStep } from "./disconnect/steps/ConfirmStep";

/** B18 §3 maps S90 as *"Disconnects tab — list + ladder + wizard"*, so the
 *  wizard is the second half of S90 rather than a new number. */
export const DISCONNECT_WIZARD_SCREEN = "S90";

const STEP_PARAM = "step";
const PARK_PARAM = "park";

export interface DisconnectWizardProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function DisconnectWizard(props: DisconnectWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const routeParams = useParams();
  const { dateFormat } = useRegional(props);

  const step = stepFromParam(searchParams.get(STEP_PARAM), DISCONNECT_STEPS);
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

  // `?account=` / `/accounts/:accountId/disconnect` — step 1 arrives ALREADY
  // CHOSEN when the caller knows which account. A LAZY initialiser and not an
  // effect: seeding after the first paint would draw the empty picker for a
  // frame. A PARKED draft still beats a URL prefill, because `useWizardPark`'s
  // hydrate runs after this.
  const [draft, setDraft] = useState<DisconnectDraft>(() => {
    const prefill = (
      searchParams.get(DISCONNECT_ACCOUNT_PARAM) ??
      routeParams.accountId ??
      ""
    ).trim();
    return prefill === ""
      ? emptyDisconnectDraft()
      : { ...emptyDisconnectDraft(), accountId: prefill };
  });
  const [accountTerm, setAccountTerm] = useState("");
  const [result, setResult] = useState<DisconnectCaseRecord | null>(null);
  function patch(next: Partial<DisconnectDraft>): void {
    setDraft((current) => ({ ...current, ...next }));
  }
  function patchProof(next: Partial<DisconnectProof>): void {
    setDraft((current) => ({ ...current, proof: { ...current.proof, ...next } }));
  }

  const accountId = draft.accountId.trim();
  const accountSearch: AccountSearchState = useAccountSearch(accountTerm, client);
  const accountQuery = useQuery({
    queryKey: ["disconnect-wizard-account", accountId],
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
  });
  const account: AccountDetail | null = accountQuery.data ?? null;

  // ⚠ **`master` IS DERIVED FROM THE ACCOUNT AND IS NEVER TYPED OR CHOSEN.**
  // `BR-CUS-068` makes `kind` `regular | master`, and `BR-CUS-1010` lets a
  // master name a premises and no unit. A clerk does not declare which kind of
  // cut this is; the account already knows.
  const master = account?.kind === "master";

  // ⛔ **THE OCCUPANT COUNT IS `null` UNTIL A READ SERVES IT.**
  // `GET /accounts/{id}/units` answers a master's units and their occupancy,
  // and the disconnect path does not call it today. `null` renders as a stated
  // absence on the banner rather than as `0 occupying accounts`, which on this
  // screen would say a building is empty (`DEF-127`'s shape on a fact about
  // people). The read is owed and is named in this file's exceptions.
  const occupants: number | null = null;

  const protections = useQuery({
    queryKey: ["disconnect-protections", accountId],
    queryFn: () => getProtectionCheck(accountId, client),
    enabled: accountId !== "",
  });
  const protectionAnswers: ProtectionCheckResult | null = protections.data ?? null;
  const inForce = protectionAnswers?.protections_in_force ?? [];

  // ╔══════════════════════════════════════════════════════════════════════╗
  // ║  `DEF-CUS-7680` — STEP 1 ASKS WHETHER THIS CASE CAN BE SCHEDULED AT  ║
  // ║  ALL, INSTEAD OF COSTING A CLERK FOUR STEPS TO FIND OUT              ║
  // ╚══════════════════════════════════════════════════════════════════════╝
  // Four of the reasons `POST /disconnects/schedule` refuses for are decided
  // by the CASE — no open case · the cut is already recorded · a COLLECTIONS
  // sequence or a closed account · the case is below TIER 3 — and the case is
  // chosen HERE and does not change while the clerk types.
  //
  // ⚠ **THE RULE IS NOT DUPLICATED AND THIS SCREEN DECIDES NOTHING.** The
  // server answers, through `disconnect_reads.schedule_readiness`, which calls
  // the same predicates and guards `schedule_cut` calls; the screen renders
  // the CODE it is handed. A wizard comparing a tier to a string would be the
  // second implementation of a rule, and the two disagree the day one of them
  // is amended.
  //
  // ⚠ **IT RIDES ON THE LADDER READ** — the resource that owns the case, and
  // where `cut_floor` already rides for the same reason. One call, not two.
  const ladder = useQuery({
    queryKey: ["disconnect-ladder", accountId],
    queryFn: () => getLadderState(accountId, client),
    enabled: accountId !== "",
  });
  // ⚠ **AN UNANSWERED READ LETS THE CLERK THROUGH, AND THAT IS HARD-WON LAW 3
  // POINTING THE OTHER WAY.** Here the unsafe option is REFUSING: a tenant on
  // an older build serves no `schedule_readiness`, and a screen that read a
  // missing key as *not ready* would block every disconnection in the product
  // on an absent field. The commit is the guard and it always runs.
  const preflight: DisconnectPreflightBlocker | null =
    ladder.data?.schedule_readiness?.refusal ?? null;

  const notices = useQuery({
    queryKey: ["disconnect-notices", accountId],
    queryFn: () => getAccountNotices(accountId, client),
    enabled: accountId !== "",
  });
  // WHICH letter the proof is about is READ here, not typed and not stored: the
  // most recent notice nobody has attested to. A notice already proved needs no
  // second record and the server refuses one by name.
  const unprovedNoticeId = (notices.data ?? []).find((row) => !row.recorded)?.notice_id ?? "";

  const terms = useQuery({
    queryKey: ["disconnect-terms", accountId],
    queryFn: () => getDisconnectTerms(accountId, client),
    // Step 4's figures only. Asked for from step 1 so the clerk does not watch
    // a spinner on the step that commits.
    enabled: accountId !== "",
  });

  const proofMissing =
    draft.proof.channel === "" && draft.proof.reference.trim() === "" && unprovedNoticeId !== "";

  const commit = useMutation({
    mutationFn: async () => {
      if (unprovedNoticeId !== "" && proofIsComplete(draft.proof)) {
        await postProofOfService(
          unprovedNoticeId,
          {
            channel: draft.proof.channel,
            reference: draft.proof.reference,
            served_on: draft.proof.servedOn,
            // BR-CUS-100: nullable even on a fully recorded proof — a certified
            // item can be posted today and signed for on Thursday. An empty box
            // is sent as null and never as the served date, which would put a
            // signature in the record nobody wrote.
            signed_for_on: draft.proof.signedForOn === "" ? null : draft.proof.signedForOn,
          },
          client,
        );
      }
      return scheduleCut(scheduleCutPlanOf(draft), client);
    },
  });

  async function runCommit(): Promise<WizardCommitOutcome> {
    // ⚠ **A HALF-TYPED PROOF FAILS THE COMMIT AND IS NEVER DROPPED.** This is
    // NOT `BR-CUS-1099`'s case: that ruling made an EMPTY proof warn and
    // proceed, and this is a proof the clerk started and did not finish, which
    // the server would refuse field by field. Silently scheduling without it
    // would turn an incomplete legal attestation into no attestation at all.
    if (proofIsStarted(draft.proof) && !proofIsComplete(draft.proof)) {
      return {
        ok: false,
        reason: t("customers.disconnect.proofIncomplete", {
          defaultValue: "Finish the proof on step 3. Nothing was scheduled.",
        }),
      };
    }
    try {
      const answered = await commit.mutateAsync();
      setResult(answered);
      fireToast(
        t("customers.disconnect.toast", {
          defaultValue: "The disconnection is scheduled. Nothing is cut until that date.",
        }),
      );
      return { ok: true };
    } catch (error) {
      // ⛔ **`DEF-CUS-7680` — THE SERVER SAYS EXACTLY WHY AND THIS LINE USED TO
      // THROW IT AWAY.** `apiErrorText` renders the catalogue value for the
      // envelope's `message_key`, and `_as_catalog_refusal` folds EIGHTEEN
      // distinct refusals onto one key — so a clerk who had filled all four
      // steps read *"This disconnect step can't be done as asked. Check the
      // case."* whether the case was closed, already cut, below tier 3 or
      // simply never opened. The Product Owner hit it on `v2.352.0`.
      //
      // ⚠ **IT BRANCHES ON `params.code` AND NOT ON THE ENGLISH**, which is
      // the route's own docstring — *"so a screen can branch without parsing
      // English"* — and an unmapped code still renders the generic line rather
      // than a blank. `disconnect/disconnectRefusal.ts` is the one place that
      // maps it, so this wizard and step 1 cannot say two different things.
      return { ok: false, reason: disconnectRefusalText(translate, error) };
    }
  }

  const park = useWizardPark({
    steps: DISCONNECT_STEPS,
    step,
    parkOpen,
    context: {
      flow: "disconnect",
      subjectLabel: account === null ? accountTerm : accountHeadline(account, translate),
      subjectRef: { account_id: accountId === "" ? null : accountId },
      values: { account_term: accountTerm, draft },
    },
    t: translate,
    client,
    onHydrate: (row) => {
      setAccountTerm(parkedString(row.values, "account_term"));
      // ⚠ `hydrateDraft` and NOT the shared `hydrateForm` — every collection on
      // this wizard is an ARRAY now, and `typeof [] === typeof {}`, so the
      // shared hydrator would put a parked `{}` into a field the screen then
      // calls `.map` on. See `disconnectDraft.hydrateDraft`.
      setDraft(hydrateDraft(row.values.draft));
    },
    onParked: () => navigate(tenantPath(parkedHomePath("disconnect"))),
  });
  // `DEF-SHL-10001` — the leave-page popup's *Save as draft* writes the
  // same `wizard_parks` row this wizard's Park writes, as a draft.
  const leaveDraft: LeaveDraft = {
    onSave: park.saveDraft,
    savedMessage: t("leaveGuard.saved", { place: t("customers.accounts.tab.disconnects") }),
  };

  /** ⚠ **PARK IS THE ONLY WAY OUT — PO ruling 2026-09-21**, verbatim: *"we need
   *  to keep only park, complete - two action only"*. `onSaveAndExit` is
   *  `null`, stated rather than omitted so the decision is visible here. */
  const exit: WizardExit = {
    onSaveAndExit: null,
    parkBlockedReason: parkStoreBlockedReason(translate),
    parkOpen,
    onParkOpenChange: setParkOpen,
    onPark: park.onPark,
    dateFormat,
    parkedAt: park.parkedAt,
  };

  // ⚠ **THE VISIT ROWS AND THE NOTICE RECIPIENTS ARE SEEDED FROM WHAT THE CLERK
  // CHOSE ON STEP 1**, once, and then belong to the clerk. Re-deriving them on
  // every render would erase a row they removed, which is the whole point of a
  // table array — the same reasoning `EditableTable` hands its owner the WHOLE
  // new list rather than a "moved from 3 to 5" event.
  const seeded = useMemo(() => {
    const cut = servicesCut(draft);
    return { cut };
  }, [draft]);

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ STEP 2 ARRIVES WITH ITS SIX ROWS — AND IT ARRIVED WITH NONE
  // ══════════════════════════════════════════════════════════════════════════
  // Measured in Chromium on 2026-09-25: step 2 drew its heading, its add button
  // and NO ROWS. Every unit case passed, because each one handed the step its
  // own rows; **only the browser saw it** (hard-won law 6).
  //
  // ⚠ **AN EFFECT AND NOT STEP 1's `validate`, AND THAT IS THE FIX FOR THE
  // WHOLE CLASS RATHER THAN FOR THE PATH I HAPPENED TO WALK.** Seeding on the
  // way out of step 1 covers a clerk who presses Continue and nobody else — not
  // `?step=2` in the address bar, not a parked draft resumed on step 2, not the
  // account rail's shortcut. Those are real clerk paths and each one would have
  // drawn the empty table again.
  //
  // ⚠ **`seededFor` IS WHY A REMOVED ROW STAYS REMOVED.** Without it, a clerk
  // who cleared the table would watch six rows reappear — the table array's own
  // meaning undone by its seed. It re-arms when the ACCOUNT changes, because
  // then it is a different household being checked.
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ THE FINDER ARRIVES SHOWING A DATABASE ID, AND THIS IS THE HALF THIS LANE
  //   CAN FIX WITHOUT REACHING INTO A FILE THREE WIZARDS SHARE — `DEF-CUS-6765`
  // ══════════════════════════════════════════════════════════════════════════
  // Measured in Chromium on 2026-09-25, arriving at
  // `/disconnects/new?account=<id>`: the search box read
  // `01a0d23a-4bed-7688-a5d5-9a9816c56ed9` and an open listbox holding the SAME
  // string sat over the fact strip. **B14 rule 31 — no database id is ever the
  // visible value of a field — and it is the first thing a clerk sees on the
  // screen that cuts somebody's water.** It is also the path the account rail's
  // shortcut and `/accounts/:id/disconnect` both take, so it is the common
  // arrival rather than an edge one.
  //
  // **THE CAUSE IS IN `AccountFinder`** (the kit's `RemoteSearchSelectField`
  // underneath it): with a value and no term it displays the value, which is
  // the id. That file is shared by three wizards and is filed rather than
  // edited here.
  //
  // **WHAT THIS DOES INSTEAD, AND IT IS A FIX RATHER THAN A HIDE:** once the
  // account has actually loaded, the wizard seeds the clerk's SEARCH TERM with
  // the account's own number — the string their lists and their bills carry
  // (`BR-CUS-053`). The finder then shows a number, resolves it, and the id is
  // nowhere on screen. It runs ONCE per account and never over something the
  // clerk has typed, so it cannot fight them.
  const termSeededFor = useRef("");
  useEffect(() => {
    if (account === null || account.account_no === null) return;
    if (accountTerm !== "" || termSeededFor.current === account.id) return;
    termSeededFor.current = account.id;
    setAccountTerm(account.account_no);
  }, [account, accountTerm]);

  const seededFor = useRef("");
  useEffect(() => {
    if (accountId === "" || seededFor.current === accountId) {
      return;
    }
    seededFor.current = accountId;
    if (draft.checks.length === 0) {
      patch({ checks: seededChecks() });
    }
  }, [accountId, draft.checks.length]);

  function seedSchedule(): void {
    if (draft.visits.length === 0 && seeded.cut.length > 0) {
      patch({
        visits: seeded.cut.map((code) => ({
          point: code,
          label:
            account?.premise == null
              ? t(`rating.service.${code}`, { defaultValue: code })
              : `${t(`rating.service.${code}`, { defaultValue: code })} · ${account.premise}`,
          meter: "",
          visit: "",
          instruction: "",
          workOrder: "",
        })),
      });
    }
    if (master && draft.recipients.length === 0) {
      patch({
        recipients: [
          { audience: AUDIENCE_OWNER, count: 1, channel: "", reference: "" },
          { audience: AUDIENCE_OCCUPANTS, count: occupants ?? 0, channel: "", reference: "" },
        ],
      });
    }
  }

  if (result !== null) {
    return (
      <DisconnectScheduled
        record={result}
        t={translate}
        onDone={() => navigate(tenantPath(DISCONNECTS_TAB_PATH))}
      />
    );
  }

  const steps: WizardStep[] = [
    {
      id: DISCONNECT_STEPS[0].id,
      label: t(DISCONNECT_STEPS[0].labelKey, { defaultValue: DISCONNECT_STEPS[0].en }),
      content: (
        <ChooseStep
          draft={draft}
          account={account}
          failed={accountQuery.isError}
          onPatch={patch}
          term={accountTerm}
          onTermChange={setAccountTerm}
          search={accountSearch}
          t={translate}
          master={master}
          occupants={occupants}
          preflight={preflight}
        />
      ),
      // ⚠ **THE ACCOUNT IS THE ONLY THING STEP 1 REQUIRES, AND THE REASON IS
      // NOT.** `schedule_cut` accepts a schedule with no reason, and requiring
      // one here would refuse a job the product accepts. ⚠ **AND THE RESTRICTOR
      // NO LONGER NEEDS A GUARD** — the option is not offered at all (item
      // 3.14), so a draft cannot carry one.
      //
      // ⛔ **`DEF-CUS-7680` — AND THE CASE'S OWN REFUSAL STOPS THE CLERK HERE.**
      // The four blockers below are as true on step 1 as they are at the
      // commit, and the Product Owner met one of them (`no_open_case`) after
      // filling every step. **This is the SERVER's answer rendered, never this
      // screen's own** — `disconnect_reads.schedule_readiness` runs
      // `schedule_cut`'s own guards read-only — and the sentence comes from
      // the same map the commit failure uses, so a clerk is told the same
      // thing in both places.
      validate: () => {
        if (accountId === "") {
          return t("customers.disconnect.needAccount", {
            defaultValue: "Choose an account first.",
          });
        }
        if (preflight !== null) {
          return disconnectRefusalTextForCode(translate, preflight.code);
        }
        return true;
      },
    },
    {
      id: DISCONNECT_STEPS[1].id,
      label: t(DISCONNECT_STEPS[1].labelKey, { defaultValue: DISCONNECT_STEPS[1].en }),
      content: (
        <CheckStep
          draft={draft}
          onPatch={patch}
          t={translate}
          answers={protectionAnswers}
          master={master}
          occupants={occupants}
          // ⛔ EMPTY ON EVERY ACCOUNT — see `CheckStep`'s exceptions.
          occupantProtections={[]}
          actor={t("customers.disconnect.check.you", { defaultValue: "You" })}
        />
      ),
      // ⚠ **NOTHING HERE BLOCKS — `BR-CUS-1096`, item 3.11 AND item 3.4.** A
      // protection warns and never refuses, and the checklist is the clerk's
      // own with nothing mandatory on it. `true`, always, and deliberately.
      validate: () => {
        seedSchedule();
        return true;
      },
    },
    {
      id: DISCONNECT_STEPS[2].id,
      label: t(DISCONNECT_STEPS[2].labelKey, { defaultValue: DISCONNECT_STEPS[2].en }),
      content: (
        <ScheduleStep
          draft={draft}
          onPatch={patch}
          onPatchProof={patchProof}
          t={translate}
          dateFormat={dateFormat}
          notices={notices.data ?? []}
          cutFloor={null}
          master={master}
          occupants={occupants}
        />
      ),
      // ⚠ **ITEM 3.6 — THE BUTTON SAYS WHAT IS MISSING.** The old step returned
      // a bare `false` on an empty date, so the frame printed its generic
      // *"fill in what's marked above"* — over a screen with nothing marked,
      // which is `DEF-936` exactly. A STRING blocks and names the field.
      //
      // ⚠ **AND THE MISSING PROOF DOES NOT BLOCK** (`BR-CUS-1099`). Only the
      // date does, because `schedule_cut` cannot store a cut with no date at
      // all — that is a shape the table refuses, not a judgement about the
      // clerk's work.
      validate: () =>
        draft.cutOn !== ""
          ? true
          : t("customers.disconnect.needCutDate", {
              defaultValue: "Set the scheduled cut date.",
            }),
    },
    {
      id: DISCONNECT_STEPS[3].id,
      label: t(DISCONNECT_STEPS[3].labelKey, { defaultValue: DISCONNECT_STEPS[3].en }),
      content: (
        <ConfirmStep
          draft={draft}
          account={account}
          onPatch={patch}
          t={translate}
          terms={terms.data ?? null}
          master={master}
          occupants={occupants}
          protectionsInForce={inForce}
          proofMissing={proofMissing}
          client={client}
        />
      ),
      validate: () => true,
    },
  ];

  return (
    <div data-screen={DISCONNECT_WIZARD_SCREEN} data-r10="DSC-02">
      <PageHeader
        kicker={t("customers.disconnect.kicker", { defaultValue: "Disconnect" })}
        title={t("customers.disconnect.title", { defaultValue: "Cut service at an address" })}
        // ⚠ **NO SUBTITLE AND NO FOOTER SENTENCE — ITEMS 3.7 AND 3.8.** The
        // five-step wizard carried *"Five steps · notices, protections and the
        // date."* under the title AND `Step N of 5 · nothing is cut until the
        // scheduled date` under that, on every step. The rail already says
        // which step this is, and *nothing is cut until the date* is now a
        // fact beside the table it is about (step 3's `Who goes`) rather than
        // a sentence repeated four times.
        backTo={{
          // ⚠ **THE BACK LINK NAMES THE PREVIOUS STEP, AS DRAWN** — `← Disconnects`
          // on step 1 and `← Choose`, `← Check`, `← Schedule` after it. It is
          // the one part of the frame that moves between steps.
          to:
            step === 1
              ? tenantPath(DISCONNECTS_TAB_PATH)
              : `?${new URLSearchParams({ [STEP_PARAM]: String(step - 1) }).toString()}`,
          label:
            step === 1
              ? t("customers.disconnects.title", { defaultValue: "Disconnects" })
              : t(DISCONNECT_STEPS[step - 2].labelKey, {
                  defaultValue: DISCONNECT_STEPS[step - 2].en,
                }),
        }}
      />
      <WizardFrame
        steps={steps}
        nav={nav}
        onNavChange={setStep}
        // §3, item 3.16 — the rail is not navigation here, so it is not drawn
        // as four controls that never act.
        railNavigable={false}
        commitLabel={t("customers.disconnect.commit", {
          defaultValue: "Schedule the disconnection ✓",
        })}
        // B14 rule 6 names `disconnect` as its first destructive commit.
        // ⚠ ASSERTED ON RENDERED OUTPUT, not on the prop (`DEF-712`).
        commitVariant="danger"
        commitFailedTitle={t("customers.disconnect.commitFailed", {
          defaultValue: "The disconnection was not scheduled. Nothing has changed.",
        })}
        onCommit={runCommit}
        onCommitted={() => undefined}
        exit={exit}
        saveDraft={leaveDraft}
      />
    </div>
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE SCHEDULED PANEL
// ══════════════════════════════════════════════════════════════════════════

export function DisconnectScheduled(props: {
  record: DisconnectCaseRecord;
  t: Translator;
  onDone: () => void;
}) {
  return (
    <div data-screen={DISCONNECT_WIZARD_SCREEN} data-disconnect-scheduled="">
      <Panel as="section">
        <h2 className="font-heading text-h4 m-0 mb-2">
          {props.t("customers.disconnect.done.title", {
            defaultValue: "The disconnection is scheduled",
          })}
        </h2>
        <PlainTable>
          <tbody>
            <tr>
              <th scope="row">
                {props.t("customers.disconnect.done.date", { defaultValue: "Cut scheduled for" })}
              </th>
              <td>{props.record.cut_scheduled_for ?? ""}</td>
            </tr>
          </tbody>
        </PlainTable>
        <Note className="mt-2 max-w-measure">
          {props.t("customers.disconnect.done.nothingCutYet", {
            defaultValue: "Nothing has been cut yet.",
          })}
        </Note>
        <div className="mt-4">
          <Button variant="primary" onClick={props.onDone}>
            {props.t("customers.disconnect.done.back", { defaultValue: "Back to disconnects" })}
          </Button>
        </div>
      </Panel>
    </div>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: the disconnect wizard rebuild, 2026-09-25 (MAINTENANCE) ·
//         `Step1Choose.png` `Step2Check.png` `Step3Schedule.png`
//         `Step4Confirm.png` and the four master variants ·
//         `05-prototype/02 Accounts Menu Blueprint.pdf` p136–p141 (the FIVE-step
//         shape, departed from and recorded) · **BR-CUS-1096** ·
//         **BR-CUS-1097** · **BR-CUS-1098** · **BR-CUS-1099** ·
//         **BR-CUS-1100** · BR-CUS-100 · BR-CUS-103 · BR-CUS-105 ·
//         BR-BIL-007 · BR-SHL-019 · BR-SHL-025 · `DEF-CUS-6750`…`DEF-CUS-6764`
// generated: 2026-09-25 by lane WIZARD
// checklist: A=n/a(the backend half is lane CUTPATH's) B✔ C✔ D✔ E✔ F✔ G✔
//         H=deferred(PO 2026-08-09)
// exceptions:
//   E1 ⛔ **THREE CONFIRMED RULINGS ARE UNWIRED IN THE SERVER AND THIS SCREEN
//      DOES NOT HIDE IT.** `BR-CUS-1096` (`halt_reason` → `HALT_PROTECTED`
//      still refuses), `BR-CUS-1099` (`assert_service_proved` →
//      `cut_on_unrecorded_service` still refuses) and `BR-CUS-1097`
//      (`reconnect_blockers` → `not_settled`). The SCREEN no longer blocks,
//      which is this lane's half; a server refusal reaches the clerk through
//      the frame's commit failure carrying the server's own sentence, with
//      every entered value preserved (A18 §4). REPORTED to lane CUTPATH.
//   E1 ⛔ **THE OCCUPANT COUNT IS NOT READ.** `BR-CUS-1098` wants *"Master
//      account · 25 occupying accounts"*, a protections row per occupant, a
//      field-work row per SERVICE POINT and the residue transferred up.
//      `GET /accounts/{id}/units` answers the first and the disconnect path
//      calls nothing; the rest is not on any wire. Every one renders a stated
//      absence rather than a zero — on this screen `0 occupying accounts` would
//      say a building is empty. REPORTED.
//   E1 ⛔ **`whatHappened` IS KEPT ON THE DRAFT AND IS NOT WRITTEN**
//      (`DEF-CUS-6764`): `schedule_cut` has no field for a note. Half of item
//      3.13 — it is no longer thrown away, and it does not yet reach the case.
//   E3 **the rail is drawn as flat segments** (item 3.16, `railNavigable`).
//   E3 **no subtitle and no per-step footer sentence** (items 3.7, 3.8).
//   E3 **`cutFloor` is passed `null`.** `OQ-CUS-1810`'s floor rides on the
//      LADDER payload and this wizard no longer reads the ladder — the ladder
//      panel was step 1's and item 3.2 moved the ladder check to step 2. The
//      field is unbounded either way (*"give a message but allow it"*), so what
//      is lost is the advisory sentence, not a guard. Owed and named.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
