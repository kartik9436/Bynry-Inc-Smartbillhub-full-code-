// ── Trace ──────────────────────────────────────────────
// Screen:   S30 · the One-time bill tab's door (`/billing/one-time`)
// Design:   04-docs/05-modules/07-billing/11-one-time-bill-redesign.md (PO-confirmed 2026-09-30)
// Contract: 04-docs/05-modules/07-billing/13-one-time-bill-api-contract.md §1–§5
// Drawing:  05-prototype/one-time-bill-2026-09-30/*.png + inventory.md
// Plan:     12-one-time-bill-build-plan.md F1–F18
// Rules:    B14 rules 21, 31, 33, 36, 38, 40, 42, 43, 44 · BR-SHL-018/019 (the
//           wizard frame) · CLAUDE.md rules 2, 3 · hard-won law 2 (the door)
// ───────────────────────────────────────────────────────
/**
 * THE ONE-TIME BILL — ONE PAGE, FOUR STEPS: Account · Services · Review · Send.
 *
 * It replaces the live `OneTimeBillTab` (an in-tab form) and the unfinished
 * three-step `OneTimeWizardShell`. The PO's words for the shape: *"i need 1
 * word step name not 2 - and workflow should not be more than 3 or 4 steps"*.
 *
 * ## Where each fact comes from
 *
 *   * **The account** — `GET /accounts?q=` behind the searchable dropdown
 *     (contract §1), unchanged.
 *   * **Everything else** — ONE read, `POST /billing/one-time/preview`, which
 *     writes nothing and is re-asked whenever the clerk's entries change.
 *     Services, rates, readings, periods, the bill itself, its warnings and the
 *     already-billed fact are all the server's rows; this page groups and
 *     formats them and never decides a figure.
 *   * **Readings** — saved through Meter Reads' own `/read-batches`
 *     (stage → validate → post) on step 2's Continue, never by billing
 *     (contract §3), then the preview is asked again.
 *   * **The draft** — `POST /billing/one-time` on step 3's Continue or Save
 *     draft; **the send** — `POST /billing/one-time/{run_id}/send`, the frame's
 *     one transactional commit (BR-SHL-019).
 *
 * ## Problems: all at once, each on its field
 *
 * The screen checks what it can see (an empty field, a period that ends before
 * it starts) with the SAME catalogue keys the server answers with, and merges
 * the server's `field_errors` in, one problem per field. Nothing shows red
 * until the clerk has pressed Continue once — an empty form does not open
 * shouting.
 *
 * ## Layout
 *
 * The rail runs the full width and the summary aside sits beside the step's
 * panels. `WizardFrame` draws rail, content and footer as one column, so the
 * wrapper below lays the frame's own parts onto a two-column grid by their
 * `data-wizard` hooks (the frame renders `display: contents`). No stylesheet
 * class is added (B14 rule 21) and the frame itself is not forked (rule 36).
 */
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { api, diagnosticOf, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  getCharges,
  getPaymentReasonCodes,
  getReadBatch,
  getTenantUsers,
  postReadBatch,
  stageReadBatch,
  validateReadBatch,
} from "@/api/endpoints";
import type { AccountRow } from "@/api/endpoints";
import {
  ONE_TIME_BILL_KINDS,
  checkOneTimePeriod,
  draftOneTime,
  getOneTimeAccount,
  previewOneTime,
  sendOneTime,
} from "@/api/billingOpsEndpoints";
import type {
  OneTimeBillAccount,
  OneTimeBillDelivery,
  OneTimeBillDraft,
  OneTimeBillDuplicate,
  OneTimeBillKind,
  OneTimeBillPreview,
  OneTimeBillSent,
} from "@/api/billingOpsEndpoints";
import { Button } from "@/components/Button";
import { todayInZone } from "@/components/DateCell";
import { startingAmount } from "@/components/moneyMath";
import type { Translator } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { WizardFrame, initialWizardNav } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { CELL_FULL, useAccessCell, useRegional } from "@/features/metering/meteringShared";
import { READS_ROUTE } from "@/features/metering/readsShared";
import { useAccountSearch } from "@/features/payments/paymentsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { BILLING_PERMISSION, billDetailPath } from "../billingShared";
import { discardBillRun } from "../billRunEndpoints";
import { emptyGateState, releaseConfirmations } from "../billRunShared";
import type { GateState } from "../billRunShared";

import { AccountPanel, DatesPanel, PeriodPanel, ProblemsBanner } from "./AccountStep";
import type { CodeOption } from "./AccountStep";
import { KindCards } from "./KindCards";
import {
  accountProblems,
  clientProblems,
  derivedDueDate,
  draftExtras,
  emptyForm,
  hasServiceSections,
  lineCount,
  mergeProblems,
  postedKey,
  readingsReady,
  requestBody,
  takesPeriodList,
  typedReadings,
  unpostedReadings,
} from "./oneTimeBillModel";
import type { OneTimeBillForm, Problem } from "./oneTimeBillModel";
import { RolloverAccept, rolloverHoldFrom } from "./RolloverAccept";
import type { RolloverHold } from "./RolloverAccept";
import { AlreadyBilledBanner, ClosedMonthNote, OneTimeSummary } from "./OneTimeSummary";
import type { SummaryFootnote } from "./OneTimeSummary";
import { BillPreview, DeliveryPanel } from "./ReviewStep";
import { allConfirmed } from "./SendConfirmations";
import { SendCard, SentCard } from "./SendStep";
import {
  ChargePanel,
  EvidencePanel,
  WaitingReadingsNote,
  approvedBy,
  MoveInChargesPanel,
  PeriodsTable,
  RatesTable,
  ReadingsPanel,
  ServicesTable,
  SettlementPanel,
} from "./ServicesStep";
import type { ApproverChoice } from "./ServicesStep";
import { money } from "./oneTimeBillShared";
import type { OtbFormat } from "./oneTimeBillShared";

/** The page's address, tenant-relative. It is the Bills page's `One-time bill`
 *  tab address, so the tab IS the door — declared above `billing/:tab`. */
export const ONE_TIME_BILL_ROUTE = "/billing/one-time";

/** How long the page waits after the last keystroke before re-asking the
 *  preview — long enough not to ask per character. */
const PREVIEW_DEBOUNCE_MS = 350;

function kindFrom(raw: string | null): OneTimeBillKind {
  return ONE_TIME_BILL_KINDS.find((kind) => kind === raw) ?? "interim";
}

/** An API refusal's field errors as problems; `null` fields are dropped here
 *  and rendered by the failure path instead. */
function problemsFrom(error: unknown): Problem[] | null {
  if (!isApiError(error) || error.status !== 422) return null;
  return error.fieldErrors
    .filter((fe) => fe.field !== null)
    .map((fe) => ({ field: fe.field as string, messageKey: fe.message_key, params: fe.params }));
}

/** A `409 BIZ-IDEMPOTENT` from the draft carries who billed the period. */
function duplicateFrom(error: unknown): OneTimeBillDuplicate | null {
  if (!isApiError(error) || error.status !== 409) return null;
  const params = error.params;
  return {
    invoice_no: typeof params.invoice_no === "string" ? params.invoice_no : null,
    run_id: typeof params.run_id === "string" ? params.run_id : "",
    invoice_id: typeof params.invoice_id === "string" ? params.invoice_id : null,
    ran_by_name: typeof params.ran_by_name === "string" ? params.ran_by_name : null,
    ran_at: typeof params.ran_at === "string" ? params.ran_at : null,
  };
}

/**
 * A refusal as ONE specific sentence — never the frame's bare "This step isn't
 * finished" (DEF-BIL-8321). A known key reads its own catalogue sentence; an
 * unknown key or an unexpected error reads the generic sentence WITH the
 * support line (`HTTP 500 · Ref 5F2B-9C1D`), so the clerk always has something
 * to act on or to quote.
 */
export function refusalOf(error: unknown, t: Translator): string {
  const generic = t("billing.oneTimeBill.problem.generic");
  const sentence = isApiError(error)
    ? t(error.messageKey, { ...error.params, defaultValue: generic })
    : generic;
  if (sentence !== generic) return sentence;
  const reference = diagnosticOf(error);
  return reference === null ? generic : `${generic} (${reference})`;
}

/** A preview refusal whose every problem stands on a field (and in the list
 *  above it) — the one case the frame's own line is not alone. */
const ON_THEIR_FIELDS = "\u0000on-their-fields";

/** The refusal a Continue gives the frame when the preview did not answer: the
 *  problems banner names fields; anything else names itself (DEF-BIL-8321). */
function continueRefusal(
  problems: readonly Problem[],
  previewError: string | null,
  t: Translator,
): string {
  if (problems.length > 0) return t("billing.oneTimeBill.problem.summary", { count: problems.length });
  return previewError ?? t("billing.oneTimeBill.problem.generic");
}

/**
 * The grid the frame's parts are laid onto. Each selector names a hook the
 * frame already renders (`data-wizard="rail"` etc.), so nothing about the
 * frame changes for the 23 other wizards that mount it.
 */
const LAYOUT =
  "grid grid-cols-[minmax(0,1fr)_320px] gap-x-5 items-start " +
  "[&_[data-wizard=frame]]:contents " +
  "[&_[data-wizard=rail]]:col-span-2 [&_[data-wizard=rail]]:row-start-1 " +
  "[&_[data-wizard=content]]:col-start-1 [&_[data-wizard=content]]:row-start-3 " +
  "[&_[data-wizard=actions]]:col-start-1 [&_[data-wizard=actions]]:row-start-4 " +
  "[&_[data-wizard=actions]]:mt-0 [&_[data-wizard=actions]]:border-t " +
  "[&_[data-wizard=actions]]:border-divider [&_[data-wizard=actions]]:pt-4 " +
  "[&_[data-wizard=blocked]]:col-start-1 [&_[data-wizard=blocked]]:row-start-5";

export interface OneTimeBillPageProps {
  client?: ApiClient;
  timeZone?: string;
  dateFormat?: OtbFormat["dateFormat"];
}

export function OneTimeBillPage(props: OneTimeBillPageProps) {
  const { t, i18n } = useTranslation();
  const translate: Translator = useCallback((key, params) => t(key, params) as string, [t]);
  const client = props.client ?? api;
  const regional = useRegional(props);
  const tenantPath = useTenantPath();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const today = todayInZone(regional.timeZone);

  const kind = kindFrom(params.get("kind"));
  const [form, setForm] = useState<OneTimeBillForm>(() => emptyForm(kind, today));
  const [nav, setNav] = useState<WizardNavState>(initialWizardNav);
  const [term, setTerm] = useState("");
  const [chosen, setChosen] = useState<AccountRow | null>(null);
  const [attempted, setAttempted] = useState(false);
  const [preview, setPreview] = useState<OneTimeBillPreview | null>(null);
  const [serverProblems, setServerProblems] = useState<Problem[]>([]);
  const [previewError, setPreviewError] = useState<string | null>(null);
  // DEF-BIL-9077 — a meter that rolled over inside the period, held by the
  // preview until the clerk accepts it (shown at once: it is a decision, not
  // a typing error).
  const [rolloverHold, setRolloverHold] = useState<RolloverHold | null>(null);
  // An acceptance is about THIS account's meter over THIS window: a new account,
  // window or kind forgets it rather than carrying it to a meter nobody looked at.
  useEffect(() => {
    setForm((was) =>
      (was.acceptedRollovers ?? []).length === 0 ? was : { ...was, acceptedRollovers: [] },
    );
  }, [form.accountId, form.periodStart, form.periodEnd, form.kind]);
  const [previewTick, setPreviewTick] = useState(0);
  // DEF-BIL-8289 — the automatic preview's refusal is HELD until the clerk
  // presses Continue. PO: *"why this error message is coming that bill cannot
  // be generated - i have not filled all the details and not press continue"*.
  const [failureShown, setFailureShown] = useState(false);
  const [dueDaysTouched, setDueDaysTouched] = useState(false);
  const [refusedMeters, setRefusedMeters] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<OneTimeBillDraft | null>(null);
  const [duplicate, setDuplicate] = useState<OneTimeBillDuplicate | null>(null);
  const [sent, setSent] = useState<OneTimeBillSent | null>(null);
  // PO 2026-09-30, option B — the five release confirmations (was one tick).
  const [confirmations, setConfirmations] = useState<GateState>(emptyGateState);
  const [delivery, setDelivery] = useState<OneTimeBillDelivery>("email");
  const [settlementPath, setSettlementPath] = useState("collect");
  const [evidence, setEvidence] = useState("");
  const [approver, setApprover] = useState<ApproverChoice>({ userId: "", name: "" });
  const [note, setNote] = useState("");
  // The account id a first bill's move-in date was last pre-filled for — so
  // the account's date fills the field ONCE and never over the clerk's own.
  const [moveInFilledFor, setMoveInFilledFor] = useState("");

  const search = useAccountSearch(term, client, "one-time-bill");
  // BR-SHL-025: a clerk who may not write sees the page and its figures, and
  // every control that would draft or send is refused WITH the reason. The
  // server refuses regardless; this only saves the round trip.
  const cell = useAccessCell(BILLING_PERMISSION, client);
  const readOnlyReason = cell === null || cell === CELL_FULL ? null : translate("billing.rbac.readOnly");

  const reasonsQuery = useQuery({
    queryKey: ["one-time-bill", "reasons"],
    queryFn: () => getPaymentReasonCodes(client),
    enabled: takesPeriodList(form.kind),
    retry: false,
  });
  const chargesQuery = useQuery({
    queryKey: ["one-time-bill", "charges"],
    queryFn: () => getCharges({ filters: { status: "active" }, per: 100 }, client),
    enabled: form.kind === "fee" || form.kind === "penalty",
    retry: false,
  });

  // DEF-BIL-8281 — the account card and the Days-to-pay default come from the
  // ACCOUNT the moment it is chosen, never waiting on a preview (which refuses
  // while any required field is empty). PO: *"even if you dont find the move
  // in date you should pull plan and cycle"*.
  const accountQuery = useQuery({
    queryKey: ["one-time-bill", "account", form.accountId],
    queryFn: () => getOneTimeAccount(form.accountId, client),
    enabled: form.accountId !== "",
    retry: false,
  });
  const accountFacts: OneTimeBillAccount | null = accountQuery.data ?? null;
  // DEF-BIL-8305 — the staff a penalty's approver is picked from.
  const staffQuery = useQuery({
    queryKey: ["one-time-bill", "staff"],
    queryFn: () => getTenantUsers({ page: 1, per: 100, sort: "name", dir: "asc" }, client),
    enabled: form.kind === "penalty",
    retry: false,
  });
  const staff = (staffQuery.data?.results ?? [])
    .filter((user) => user.status === "active" && user.name !== "")
    .map((user) => ({ value: user.id, label: user.name }));

  const reasons: CodeOption[] = (reasonsQuery.data?.reasons ?? []).map((reason) => ({
    value: reason.code,
    label: reason.name,
  }));
  const charges: CodeOption[] = (chargesQuery.data?.results ?? []).map((charge) => ({
    value: charge.code,
    entered: charge.amount_rule === "per_case",
    startAmount: charge.amount_rule === "per_case" ? startingAmount(charge.amount) : undefined,
    label:
      charge.amount === null
        ? charge.name
        : `${charge.name} · ${money(charge.amount, { t: translate, currency: preview?.bill.currency ?? "USD", ...regional })}`,
  }));

  const currency = preview?.bill.currency ?? chosen?.balance_currency ?? chosen?.currency ?? "USD";
  const fmt: OtbFormat = { t: translate, currency, ...regional };

  const update = useCallback((patch: Partial<OneTimeBillForm>) => {
    setForm((was) => ({ ...was, ...patch }));
  }, []);

  // ── The preview: re-asked whenever the entries change ─────────────────────
  const rows = useMemo(() => preview?.readings?.rows ?? [], [preview]);
  const body = useMemo(() => requestBody(form, rows), [form, rows]);
  const bodyKey = JSON.stringify(body);
  const asked = useRef(0);
  // A change to the entries hides a refusal shown for the previous ones; the
  // next Continue shows the new answer's, if it still refuses.
  useEffect(() => setFailureShown(false), [bodyKey]);

  // ── DEF-BIL-10068 / 10069 · step 1 knows, the moment the period is picked ──
  // PO 2026-10-12: a draft for the period (Open / Discard) and a closed month
  // (*"August is closed. Posts to October."*) are said on STEP 1, never met as
  // a refusal at the last step. Keyed on the window alone, so typing a reading
  // on step 2 does not re-ask it.
  const windowKey = JSON.stringify([
    form.accountId,
    form.kind,
    form.periodStart,
    form.periodEnd,
    form.periods,
    form.billDate,
  ]);
  const periodCheck = useQuery({
    queryKey: ["one-time-bill", "period-check", windowKey],
    queryFn: () => checkOneTimePeriod(body, client),
    enabled: form.accountId !== "" && sent === null,
    retry: false,
  });
  const [discarding, setDiscarding] = useState(false);
  // This page's OWN draft is not a duplicate of itself.
  const checked = periodCheck.data?.duplicate ?? null;
  const shownDuplicate =
    duplicate ?? (checked !== null && draft !== null && checked.run_id === draft.run_id ? null : checked);
  async function discardDraft(runId: string): Promise<void> {
    setDiscarding(true);
    try {
      await discardBillRun(runId, client);
      setDuplicate(null);
      setDraft(null);
      toast(translate("billing.oneTimeBill.duplicate.discarded"));
      await periodCheck.refetch();
      setPreviewTick((n) => n + 1);
    } catch (error) {
      toast(refusalOf(error, translate));
    } finally {
      setDiscarding(false);
    }
  }

  // DEF-BIL-8327 — the NEWEST preview request, so a caller whose own request
  // was overtaken waits for the answer that replaced it instead of reading
  // "no answer". Continue pressed inside the debounce window started one
  // request and the timer a second; the first came back stale, read as null,
  // and the frame's generic line stood alone over a complete step 1.
  const newest = useRef<Promise<OneTimeBillPreview | string | null> | null>(null);
  // The debounced preview not yet sent — Continue cancels it and asks itself.
  const pendingPreview = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runPreview = useCallback(async (): Promise<OneTimeBillPreview | string | null> => {
    if (form.accountId === "") return null;
    const ticket = asked.current + 1;
    asked.current = ticket;
    const request = (async (): Promise<OneTimeBillPreview | string | null> => {
      try {
        const answer = await previewOneTime(body, client);
        if (asked.current === ticket) {
          setPreview(answer);
          setServerProblems([]);
          setPreviewError(null);
          setRolloverHold(null);
          setDuplicate(answer.duplicate);
        }
        return answer;
      } catch (error) {
        if (asked.current !== ticket) return null;
        const problems = problemsFrom(error);
        if (problems !== null && problems.length > 0) {
          setServerProblems(problems);
          setPreviewError(null);
          return ON_THEIR_FIELDS;
        }
        // DEF-BIL-8301 / DEF-BIL-8321 — a refusal that names no field (a
        // pricing refusal, an unknown key, a 500) is a REFUSAL with its own
        // sentence, returned so step 1's Continue can hand it to the frame; the
        // frame's generic "This step isn't finished" line never stands alone.
        const sentence = refusalOf(error, translate);
        setServerProblems([]);
        setPreviewError(sentence);
        setRolloverHold(rolloverHoldFrom(error));
        return sentence;
      }
    })();
    newest.current = request;
    const outcome = await request;
    // Overtaken: answer with the request that replaced this one — the one
    // whose answer is now on the screen.
    let latest = newest.current;
    while (asked.current !== ticket && latest !== null && latest !== request) {
      const settled = await latest;
      if (newest.current === latest) return settled;
      latest = newest.current;
    }
    return outcome;
    // `bodyKey` stands for `body` — the object is rebuilt each render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bodyKey, client, form.accountId, translate]);

  useEffect(() => {
    if (form.accountId === "" || sent !== null) return undefined;
    const timer = setTimeout(() => void runPreview(), PREVIEW_DEBOUNCE_MS);
    pendingPreview.current = timer;
    return () => clearTimeout(timer);
  }, [runPreview, form.accountId, sent, previewTick]);

  // The account's own defaults: days to pay from its cycle, and a first
  // bill's move-in date. Applied once, never over a value the clerk typed.
  // DEF-BIL-8281 — read off the ACCOUNT, and off the preview only as a
  // fallback, so neither waits on a bill the preview may refuse.
  const cycleDueDays = accountFacts?.cycle_due_days ?? preview?.defaults.due_days ?? null;
  useEffect(() => {
    if (!dueDaysTouched && form.dueDays === "" && cycleDueDays !== null) {
      update({ dueDays: String(cycleDueDays) });
    }
  }, [cycleDueDays, dueDaysTouched, form.dueDays, update]);
  // PO change 2026-09-30 — a first bill's Move-in date is a date picker,
  // PRE-FILLED from `accounts.opened_at` once per account, then the clerk's.
  // It sets THIS bill's period start only; the account's record never moves.
  const recordedMoveIn = accountFacts?.moved_in_on ?? chosen?.opened_at ?? null;
  useEffect(() => {
    if (form.kind !== "first" || form.accountId === "" || moveInFilledFor === form.accountId) return;
    if (recordedMoveIn === null && accountQuery.isFetching) return;
    setMoveInFilledFor(form.accountId);
    if (recordedMoveIn !== null && form.periodStart === "") update({ periodStart: recordedMoveIn });
  }, [form.kind, form.accountId, form.periodStart, recordedMoveIn, moveInFilledFor, accountQuery.isFetching, update]);

  // ── Problems ──────────────────────────────────────────────────────────────
  // DEF-BIL-8330 — a first bill for an account on no cycle is named the moment
  // the account is picked: it is a fact about the ACCOUNT, which nothing typed
  // on this step can fix, so it is not held until Continue as a typing
  // problem is (DEF-BIL-8289).
  const ownAccountProblems = form.accountId === "" ? [] : accountProblems(form.kind, accountFacts);
  const problems = mergeProblems(ownAccountProblems, clientProblems(form), serverProblems);
  const shownProblems = attempted ? problems : ownAccountProblems;
  // DEF-BIL-8289 (a) — while step 1 is not filled in, the summary says what it
  // is waiting for and never a failure.
  const step1Incomplete =
    sent === null &&
    (form.accountId === "" || clientProblems(form).length > 0 || ownAccountProblems.length > 0);
  const dueDate = problems.some((p) => p.field === "due_days" || p.field === "bill_date")
    ? null
    : (preview?.due_date ?? derivedDueDate(form));

  // ── Reading refusals from Meter Reads override the preview's own status ───
  const displayPreview = useMemo<OneTimeBillPreview | null>(() => {
    if (preview === null || preview.readings === null) return preview;
    if (Object.keys(refusedMeters).length === 0) return preview;
    return {
      ...preview,
      readings: {
        ...preview.readings,
        rows: preview.readings.rows.map((row) =>
          refusedMeters[row.label] === undefined
            ? row
            : { ...row, status: "refused", refusal_key: refusedMeters[row.label] },
        ),
      },
    };
  }, [preview, refusedMeters]);

  // ── Actions ───────────────────────────────────────────────────────────────
  function chooseKind(next: OneTimeBillKind): void {
    if (next === form.kind) return;
    setParams((was) => {
      const copy = new URLSearchParams(was);
      copy.set("kind", next);
      return copy;
    });
    setForm((was) => ({
      ...emptyForm(next, today),
      accountId: was.accountId,
      billDate: was.billDate,
      dueDays: was.dueDays,
      // DEF-BIL-8309 — see `chooseAccount`.
      ...(next === "first" && chosen?.opened_at ? { periodStart: chosen.opened_at } : {}),
    }));
    setNav(initialWizardNav());
    setAttempted(false);
    setServerProblems([]);
    setDraft(null);
    setDuplicate(null);
    setConfirmations(emptyGateState());
    setRefusedMeters({});
    setMoveInFilledFor("");
  }

  function startOver(): void {
    setForm(emptyForm(form.kind, today));
    setNav(initialWizardNav());
    setTerm("");
    setChosen(null);
    setAttempted(false);
    setPreview(null);
    setServerProblems([]);
    setPreviewError(null);
    setDueDaysTouched(false);
    setRefusedMeters({});
    setDraft(null);
    setDuplicate(null);
    setSent(null);
    setConfirmations(emptyGateState());
    setEvidence("");
    setApprover({ userId: "", name: "" });
    setNote("");
    setMoveInFilledFor("");
  }

  function chooseAccount(row: AccountRow | null): void {
    setChosen(row);
    setPreview(null);
    setServerProblems([]);
    setDraft(null);
    setDuplicate(null);
    update({ accountId: row?.id ?? "", readings: {}, posted: {} });
    if (row === null) return;
    // DEF-BIL-8309 / PO change 2026-09-30 — a first bill's Move-in date is
    // pre-filled from the account's own `opened_at` (the list row carries it,
    // so nothing waits on a preview); the clerk may then change it. A new
    // account starts from ITS date, never the last account's.
    if (form.kind === "first") {
      update({ periodStart: row.opened_at ?? "" });
      setMoveInFilledFor(row.opened_at ? row.id : "");
    }
    setTerm("");
  }

  /** Step 2's Continue: every typed reading goes to Meter Reads, the preview
   *  is asked again, and the step passes only when every needed row reads. */
  async function saveReadings(): Promise<true | string> {
    const allTyped = typedReadings(form, rows);
    // DEF-BIL-10067 — post only what Continue has not posted at this value.
    const typed = unpostedReadings(allTyped, form.posted);
    if (typed.length > 0) {
      const labelOf = new Map(rows.map((row) => [row.asset_id, row.label]));
      // DEF-BIL-8325 — the MOVE-IN readings are posted in their own batch
      // FIRST. In one batch with the new reading of the same meter, the new
      // one was validated before the move-in one existed, stored no
      // consumption, and the draft refused "no usable read".
      const batches = [
        typed.filter((reading) => reading.role === "move_in"),
        typed.filter((reading) => reading.role !== "move_in"),
      ].filter((batch) => batch.length > 0);
      try {
        for (const batch of batches) {
          const staged = await stageReadBatch(
            {
              source_kind: "manual",
              period_month: batch[0].read_at,
              write_mode: "insert",
              rows: batch.map((reading) => ({
                meter_id: labelOf.get(reading.asset_id) ?? "",
                read_date: reading.read_at,
                reading: reading.value,
                channel: "total",
              })),
            },
            client,
          );
          await validateReadBatch(staged.id, client);
          const detail = await getReadBatch(staged.id, client);
          const refused: Record<string, string> = {};
          for (const row of detail.rows) {
            if (row.severity === "error" && row.meter_no !== null) {
              refused[row.meter_no] = "billing.oneTimeBill.readings.status.refused";
            }
          }
          setRefusedMeters(refused);
          if (Object.keys(refused).length > 0) {
            return translate("billing.oneTimeBill.readings.blocked");
          }
          await postReadBatch(staged.id, { certified: true }, client);
        }
        // DEF-BIL-10067 (PO 2026-10-12, *"the draft is priced on the reading
        // entered"*) — the typed values STAY on the request. This cleared
        // them, so the preview after Continue and the draft were priced on
        // what Meter Reads counted for that date: a committed 8.0 over the
        // clerk's 4.6 (5.1 kgal for a screen showing 1.7). The server prices
        // the typed reading over a committed one, and the draft on the
        // reading posted just above; `posted` stops a second Continue posting
        // it again (the walk's refused duplicate batch).
        update({
          posted: {
            ...(form.posted ?? {}),
            ...Object.fromEntries(typed.map((reading) => [postedKey(reading), reading.value])),
          },
        });
      } catch (error) {
        return refusalOf(error, translate);
      }
    }
    const answer = await runPreview();
    if (answer === null) return translate("billing.oneTimeBill.problem.generic");
    if (answer === ON_THEIR_FIELDS) return translate("billing.oneTimeBill.problem.generic");
    if (typeof answer === "string") {
      setFailureShown(true);
      return answer;
    }
    // Saved readings are on file now, so the preview carries them; what the
    // clerk typed has been cleared above and must not be counted twice.
    const effective = allTyped.length > 0 ? { ...form, readings: {} } : form;
    return readingsReady(effective, answer) ? true : translate("billing.oneTimeBill.readings.stillNeeded");
  }

  /** The draft, made once. Step 3's Continue, Save draft and Send all come
   *  through here, so one bill is never drafted twice from one page. */
  async function ensureDraft(): Promise<OneTimeBillDraft | string> {
    if (draft !== null) return draft;
    if (readOnlyReason !== null) return readOnlyReason;
    try {
      const made = await draftOneTime(
        {
          ...body,
          ...draftExtras(form.kind, { settlementPath, evidence, note }, preview?.settlement?.paths ?? []),
        },
        client,
      );
      setDraft(made);
      setDuplicate(null);
      return made;
    } catch (error) {
      const dup = duplicateFrom(error);
      if (dup !== null) {
        setDuplicate(dup);
        return translate("billing.oneTimeBill.duplicate.title");
      }
      const problems422 = problemsFrom(error);
      if (problems422 !== null) setServerProblems(problems422);
      return refusalOf(error, translate);
    }
  }

  async function saveDraft(): Promise<void> {
    const outcome = await ensureDraft();
    if (typeof outcome !== "string") toast(translate("billing.oneTimeBill.draftSaved"));
  }

  async function send(): Promise<WizardCommitOutcome> {
    const made = await ensureDraft();
    if (typeof made === "string") return { ok: false, reason: made };
    try {
      // DEF-BIL-8305 — a penalty's approver, RECORDED and never required.
      const approval = form.kind === "penalty" ? approvedBy(approver) : undefined;
      const answer = await sendOneTime(
        made.run_id,
        {
          confirmations: releaseConfirmations(confirmations),
          delivery,
          sent_at: new Date().toISOString(),
          ...(approval === undefined ? {} : { approved_by: approval }),
        },
        client,
      );
      setSent(answer);
      return { ok: true };
    } catch (error) {
      return { ok: false, reason: refusalOf(error, translate) };
    }
  }

  // ── Steps ─────────────────────────────────────────────────────────────────
  const services = displayPreview?.services ?? null;
  const warnings = displayPreview?.warnings ?? [];
  const accountLine = [
    preview?.account.account_no ?? chosen?.account_no ?? null,
    preview?.account.address ?? chosen?.premise ?? null,
  ]
    .filter((part): part is string => part !== null && part !== "")
    .join(" · ");
  const customer = preview?.account.name ?? chosen?.name ?? "";
  const period =
    form.kind === "fee"
      ? null
      : takesPeriodList(form.kind)
        ? {
            start: form.periods[0]?.start ?? null,
            end: form.periods[form.periods.length - 1]?.end ?? null,
          }
        : { start: form.periodStart, end: form.periodEnd };

  const stepAccount = (
    <>
      <ProblemsBanner problems={shownProblems} t={translate} />
      <AccountPanel
        t={translate}
        fmt={fmt}
        term={term}
        onTermChange={setTerm}
        search={search}
        matches={search.matches}
        chosen={chosen}
        onChoose={chooseAccount}
        preview={preview}
        account={accountFacts}
        problems={shownProblems}
      />
      <PeriodPanel
        form={form}
        update={update}
        t={translate}
        fmt={fmt}
        reasons={reasons}
        charges={charges}
        movedInOn={recordedMoveIn}
        problems={shownProblems}
      />
      <DatesPanel
        form={form}
        update={(patch) => {
          if (patch.dueDays !== undefined) setDueDaysTouched(true);
          update(patch);
        }}
        t={translate}
        fmt={fmt}
        problems={shownProblems}
      />
      <WaitingReadingsNote preview={preview} t={translate} />
    </>
  );

  const stepServices =
    displayPreview === null ? (
      <p className="m-0 text-base text-neutral-700" role="status">
        {translate("billing.oneTimeBill.loading")}
      </p>
    ) : (
      <>
        {hasServiceSections(form.kind) && services !== null && services.length === 0 && (
          <p className="m-0 mb-4 bg-surface px-4 py-3 text-base" role="status" data-otb-no-services="">
            {translate("billing.oneTimeBill.services.none")}
          </p>
        )}
        {hasServiceSections(form.kind) && services !== null && services.length > 0 && (
          <ServicesTable services={services} warnings={warnings} t={translate} fmt={fmt} />
        )}
        {hasServiceSections(form.kind) && displayPreview.rates !== null && (
          <RatesTable
            rates={displayPreview.rates}
            plan={displayPreview.account.plan}
            perPeriod={takesPeriodList(form.kind)}
            t={translate}
            fmt={fmt}
          />
        )}
        {displayPreview.move_in_charges !== null && (
          <MoveInChargesPanel charges={displayPreview.move_in_charges} t={translate} fmt={fmt} />
        )}
        <ReadingsPanel
          preview={displayPreview}
          form={form}
          onChange={(key, patch) =>
            setForm((was) => ({
              ...was,
              readings: {
                ...was.readings,
                [key]: { ...(was.readings[key] ?? { value: "", readAt: "" }), ...patch },
              },
            }))
          }
          onEstimate={(assetId, service) =>
            // DEF-BIL-8562 — ask for (or withdraw) a meter's own estimate.
            setForm((was) => {
              const estimates = { ...(was.estimates ?? {}) };
              if (service === null) delete estimates[assetId];
              else estimates[assetId] = service;
              return { ...was, estimates };
            })
          }
          readsHref={tenantPath(READS_ROUTE)}
          client={client}
          t={translate}
          fmt={fmt}
        />
        {displayPreview.periods !== null && takesPeriodList(form.kind) && (
          <PeriodsTable periods={displayPreview.periods} t={translate} fmt={fmt} />
        )}
        {displayPreview.settlement !== null && (
          <SettlementPanel
            settlement={displayPreview.settlement}
            path={settlementPath}
            onPathChange={setSettlementPath}
            t={translate}
            fmt={fmt}
          />
        )}
        {form.kind === "penalty" && (
          <EvidencePanel
            found={evidence}
            onFoundChange={setEvidence}
            approver={approver}
            onApproverChange={setApprover}
            staff={staff}
            t={translate}
          />
        )}
        {displayPreview.charge !== null && (
          <ChargePanel
            charge={displayPreview.charge}
            kind={form.kind}
            taxRate={displayPreview.bill.tax[0]?.rate ?? null}
            note={note}
            onNoteChange={setNote}
            t={translate}
            fmt={fmt}
          />
        )}
      </>
    );

  const stepReview =
    displayPreview === null ? null : (
      <>
        <BillPreview
          kind={form.kind}
          bill={draft?.bill ?? displayPreview.bill}
          customer={customer}
          accountLine={accountLine}
          billDate={form.billDate}
          dueDate={dueDate}
          period={period}
          warnings={draft?.warnings ?? warnings}
          t={translate}
          fmt={fmt}
        />
        <DeliveryPanel value={delivery} onChange={setDelivery} t={translate} />
      </>
    );

  const total = draft?.total ?? displayPreview?.bill.total ?? null;
  const stepSend =
    sent !== null ? (
      <SentCard
        sent={sent}
        deliveryWord={translate(`billing.oneTimeBill.delivery.${delivery}`)}
        viewHref={draft === null ? null : tenantPath(billDetailPath(draft.invoice_id))}
        onNew={startOver}
        t={translate}
        fmt={fmt}
      />
    ) : (
      <SendCard
        kind={form.kind}
        accountNo={preview?.account.account_no ?? chosen?.account_no ?? null}
        customer={customer}
        address={preview?.account.address ?? chosen?.premise ?? null}
        total={total}
        dueDate={draft?.due_date ?? dueDate}
        billDate={form.billDate}
        dueDays={form.dueDays}
        lines={lineCount(displayPreview)}
        delivery={delivery}
        warnings={draft?.warnings ?? warnings}
        confirmations={confirmations}
        onConfirmationChange={(id, checked) => setConfirmations((state) => ({ ...state, [id]: checked }))}
        t={translate}
        fmt={fmt}
      />
    );

  const steps: WizardStep[] = [
    {
      id: "account",
      label: translate("billing.oneTimeBill.step.account"),
      content: stepAccount,
      validate: async () => {
        setAttempted(true);
        let own = clientProblems(form);
        // DEF-BIL-8327 — on a cold server the cycle's Days to pay can still be
        // on its way when Continue is pressed. Refusing then left the frame's
        // line alone once the default arrived and cleared the problem, so
        // Continue waits for the account's answer and uses its default.
        if (
          own.some((problem) => problem.field === "due_days") &&
          form.dueDays === "" &&
          !dueDaysTouched &&
          form.accountId !== ""
        ) {
          const facts = accountFacts ?? (await accountQuery.refetch()).data ?? null;
          const fallback = facts?.cycle_due_days ?? null;
          if (fallback !== null) {
            update({ dueDays: String(fallback) });
            own = clientProblems({ ...form, dueDays: String(fallback) });
          }
        }
        // DEF-BIL-8321 — every refusal names itself: field problems by their
        // count (each stands on its field and in the list above), anything
        // else by its own sentence. Never a bare `false`.
        // Field problems stand in the list above and on their fields, so the
        // frame's line beside them is not alone.
        if (own.length > 0) return false;
        // DEF-BIL-8330 — Continue waits while the account has no cycle; the
        // sentence already stands on the account field and in the list.
        if (ownAccountProblems.length > 0) return false;
        // DEF-BIL-8327 — Continue asks with what is on the screen NOW and
        // waits for that answer; the typing's debounced ask is not needed.
        if (pendingPreview.current !== null) clearTimeout(pendingPreview.current);
        const answer = await runPreview();
        if (answer === ON_THEIR_FIELDS) return false;
        setFailureShown(answer === null || typeof answer === "string");
        if (answer === null) return continueRefusal([], previewError, translate);
        return typeof answer === "string" ? answer : true;
      },
    },
    {
      id: "services",
      label: translate("billing.oneTimeBill.step.services"),
      content: stepServices,
      validate: () => (hasServiceSections(form.kind) ? saveReadings() : true),
    },
    {
      id: "review",
      label: translate("billing.oneTimeBill.step.review"),
      content: stepReview,
      validate: async () => {
        const made = await ensureDraft();
        return typeof made === "string" ? made : true;
      },
    },
    {
      id: "send",
      label: translate("billing.oneTimeBill.step.send"),
      content: stepSend,
    },
  ];

  const footnote: SummaryFootnote = sent !== null ? "sent" : draft !== null ? "draft" : "nothing";
  const onStep = nav.step;

  return (
    <div className="flex flex-col gap-5" data-screen="one-time-bill">
      <PageHeader
        title={translate("billing.tab.oneTime")}
        secondaryActions={
          <Button size="sm" onClick={startOver}>
            {translate("billing.oneTimeBill.startOver")}
          </Button>
        }
      />
      {readOnlyReason !== null && <RefusalStrip role="note">{readOnlyReason}</RefusalStrip>}
      <KindCards value={form.kind} onChange={chooseKind} t={translate} disabled={sent !== null} />
      <div className={LAYOUT} data-otb-layout="">
        {(shownDuplicate !== null || (periodCheck.data?.closed_month ?? null) !== null) && sent === null && (
          <div className="col-span-2 row-start-2">
            {shownDuplicate !== null && (
              <AlreadyBilledBanner
                duplicate={shownDuplicate}
                billHref={
                  shownDuplicate.invoice_id === null || shownDuplicate.invoice_id === undefined
                    ? null
                    : tenantPath(billDetailPath(shownDuplicate.invoice_id))
                }
                onDiscard={
                  readOnlyReason === null && shownDuplicate.run_id !== ""
                    ? () => void discardDraft(shownDuplicate.run_id)
                    : undefined
                }
                discarding={discarding}
                t={translate}
                fmt={fmt}
              />
            )}
            {periodCheck.data?.closed_month != null && (
              <ClosedMonthNote closed={periodCheck.data.closed_month} t={translate} language={i18n.language} />
            )}
          </div>
        )}
        <WizardFrame
          steps={steps}
          nav={nav}
          onNavChange={setNav}
          complete={sent !== null}
          commitLabel={translate("billing.oneTimeBill.send.action", { amount: money(total, fmt) })}
          commitVariant="danger"
          commitDisabled={!allConfirmed(confirmations) || readOnlyReason !== null}
          commitFailedTitle={translate("billing.oneTimeBill.send.failed")}
          onCommit={send}
          onCommitted={() => undefined}
          secondaryActions={
            onStep >= 3 && sent === null ? (
              <Button disabled={readOnlyReason !== null} onClick={() => void saveDraft()}>{translate("billing.oneTimeBill.saveDraft")}</Button>
            ) : undefined
          }
        />
        <div className="col-start-2 row-start-3 row-span-3 flex flex-col gap-4 self-start sticky top-4">
          {rolloverHold !== null && sent === null && (
            <RolloverAccept
              hold={rolloverHold}
              t={translate}
              onAccept={(serviceCode) =>
                setForm((was) => ({
                  ...was,
                  acceptedRollovers: [...new Set([...(was.acceptedRollovers ?? []), serviceCode])],
                }))
              }
            />
          )}
          {previewError !== null && failureShown && (
            <FailedWithRetry
              title={translate("billing.oneTimeBill.previewFailed")}
              reason={previewError}
              onRetry={() => setPreviewTick((n) => n + 1)}
              onCancel={() => setPreviewError(null)}
            />
          )}
          <OneTimeSummary
            kind={form.kind}
            preview={displayPreview}
            billDate={form.billDate}
            dueDate={dueDate}
            footnote={footnote}
            waiting={step1Incomplete}
            t={translate}
            fmt={fmt}
          />
        </div>
      </div>
    </div>
  );
}

export default OneTimeBillPage;
