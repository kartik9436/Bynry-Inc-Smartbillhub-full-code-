// ── Trace ──────────────────────────────────────────────
// Story:    RAT-03 — the rate-schedule wizard, Add and Edit. Screens: S11 (A1)
// Change:   CR-157-BRC10 wave B — FIVE steps become THREE, Details · Pricing ·
//           Review (decision log 2026-10-01, *"THE RATE SCHEDULE REDESIGN
//           ARTIFACT IS THE REFERENCE … WHICH ANSWERS THE THREE-STEP
//           QUESTION"*), built from images 40–71 of
//           05-prototype/rate-schedules-2026-10-01 read as IMAGES (B14 rule 42),
//           in the One-time bill / charge-code layout: the rail across the top,
//           the steps on the left, the summary aside on the right.
// Rules:    BR-RAT-031 (save-draft resumable; status derived) · BR-RAT-037 (a
//           live schedule changes by a NEW version with a reason) · BR-RAT-104
//           (a correction restates the SAME window and sends no dates) ·
//           BR-RAT-088 (the base is the charge code's, read-only) · BR-RAT-1025
//           (the schedule NAMES its base code) · BR-RAT-067 + CR-157 wave A (a
//           TOU window's name sets its register) · seasons store month + day ·
//           the MINIMUM is per meter size (PO 2026-10-01, option A — the
//           per-version minimum is not offered and not sent) · BR-SHL-019 (one
//           transactional call per outcome) · B14 rules 21, 31, 33, 37, 41–44
// Tests:    ./rateScheduleWizard3.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  activateRateSchedule,
  correctRateScheduleVersion,
  createRateSchedule,
  createRateScheduleVersion,
  discardRateScheduleDraft,
  getCharges,
  getLookupEntries,
  getMyPermissions,
  getRateSchedule,
  getTenantServices,
  updateRateSchedule,
} from "@/api/endpoints";
import type { ScheduleDetail } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { refusalParams } from "@/api/refusalText";
import { Button } from "@/components/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { formatDate, todayInZone } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import type { Fact } from "@/components/FactBlock";
import {
  CheckboxField,
  DatePickerField,
  SearchSelectField,
  SegmentedField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { TableArray } from "@/components/TableArray";
import { formatQuantity } from "@/components/UnitCell";
import { WizardFrame, initialWizardNav } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { useRegional } from "@/features/metering/meteringShared";
import { RefusalNotice, isPermissionDenied, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { sameUnit } from "@/lib/units";
import { useTenantPath } from "@/routing/tenantPath";

import { boundBaseChargeFor } from "./baseCharge";
import { ChargeNote, FactsPanel } from "./chargeCodeParts";
import {
  PercentEditor,
  activationDates,
  draftFromSchedule,
  draftPayload,
  emptyScheduleDraft,
  BASE_ONLY_MODEL,
  structureOptions,
} from "./RateScheduleWizard";
import type { ScheduleDraft } from "./RateScheduleWizard";
import { versionOrdinal } from "./RateScheduleDetail";
import { UsageChargesTable } from "./rateScheduleViewTabs";
import {
  BaseRatesTable,
  ScheduleAside,
  UsageRatesEditor,
  baseRowsPriced,
  draftChanges,
  draftStructureForView,
} from "./rateScheduleWizardParts";
import {
  ACCOUNT_TYPES_LIST,
  DASHBOARD_ROUTE,
  PLANS_RATES_ROUTE,
  declaredUnitFor,
  isDecimalShape,
  ratingAccess,
  ratingIsDenied,
  ratingIsReadOnly,
  scheduleUomOptions,
  sizeClassesForService,
} from "./ratingShared";
import type { Translator } from "./ratingShared";

/** The three drawn steps, in order. */
export const RATE_WIZARD3_STEPS = ["details", "pricing", "review"] as const;

const REFERENCE_PAGE_SIZE = 200;
const CHARGES_FOR_BASE_KEY = `active:${REFERENCE_PAGE_SIZE}`;
const RATES_LIST = `${PLANS_RATES_ROUTE}/rates`;

/** The rail across the top; steps left; the summary aside right — the same
 *  grid the One-time bill and the charge-code wizard lay their frame onto.
 *
 *  ⚠ **THE FOOTER SPANS BOTH COLUMNS — `DEF-RAT-8824`.** PO 2026-10-01: *"all
 *  buttom position on bottom pf the page - they are all over the place"*. It
 *  was `col-start-1`, so `Continue` ended at the right edge of the LEFT column
 *  with the summary hanging beside it; it is now the page's one bottom bar,
 *  under the steps AND the summary. (View details and the list keep their
 *  actions top-right in the page head — DEF-RAT-9101, decision log 2026-10-02.) */
const LAYOUT =
  "grid grid-cols-[minmax(0,1fr)_320px] gap-x-5 items-start " +
  "[&_[data-wizard=frame]]:contents " +
  "[&_[data-wizard=rail]]:col-span-2 [&_[data-wizard=rail]]:row-start-1 " +
  "[&_[data-wizard=content]]:col-start-1 [&_[data-wizard=content]]:row-start-2 " +
  "[&_[data-wizard=actions]]:col-span-2 [&_[data-wizard=actions]]:row-start-3 " +
  "[&_[data-wizard=actions]]:mt-0 [&_[data-wizard=actions]]:border-t " +
  "[&_[data-wizard=actions]]:border-divider [&_[data-wizard=actions]]:pt-4 " +
  "[&_[data-wizard=blocked]]:col-span-2 [&_[data-wizard=blocked]]:row-start-4";

const FIELDS = "grid grid-cols-3 gap-x-4 gap-y-4";

/** Step 1's own checks, in the drawn words (`43-add-1-errors.png`).
 *
 *  ⚠ **`perClassBase` — `DEF-RAT-9111`.** A saved schedule that names no class
 *  and no single code is priced from EACH class's own base code (billing finds
 *  an account's base by its class, `DEF-RAT-8833`; the server stores no code for
 *  it, `services._validate_base_charge_code`). Editing one must not demand a
 *  single code — the seeded *Residential Water* (BASE-W and BASE-W-COM) could not
 *  leave step 1. So the code is required unless the schedule being edited was
 *  already saved that way and still names no class. A NEW schedule is unchanged. */
export function detailsProblems(
  draft: ScheduleDraft,
  t: Translator,
  perClassBase = false,
): Record<string, string> {
  const found: Record<string, string> = {};
  if (draft.name.trim() === "") found.name = t("rating.rs.wiz.err.name");
  if (draft.service === "") found.service = t("rating.rs.wiz.err.service");
  if (draft.uom.trim() === "") found.uom = t("rating.rs.wiz.err.unit");
  if (draft.model === "") found.model = t("rating.rs.wiz.err.structure");
  const eachClassOwnCode = perClassBase && draft.account_type_id === "";
  if (draft.base_charge_code === "" && !eachClassOwnCode) {
    found.base_charge_code = t("rating.rs.wiz.err.baseCode");
  }
  return found;
}

/** Step 2's own checks: every row has a size, every typed figure is a number. */
export function pricingProblem(draft: ScheduleDraft, t: Translator): string | true {
  if (draft.size_rows.some((row) => row.size_class === "")) {
    return t("rating.rs.wiz.err.chooseEverySize");
  }
  const typed = [
    ...draft.size_rows.map((row) => row.minimum_bill),
    ...draft.tiers.flatMap((tier) => [tier.from_qty, tier.to_qty, tier.unit_price]),
    ...draft.windows.map((window) => window.unit_price),
    ...draft.seasons.map((season) => season.unit_price),
    draft.capacity.rate_per_unit,
    draft.demand.energy_rate_per_kwh,
    draft.demand.demand_rate_per_kw,
    draft.demand.pf_penalty_rate_per_kw,
  ];
  if (typed.some((value) => value.trim() !== "" && !isDecimalShape(value.trim()))) {
    return t("rating.error.notDecimal");
  }
  return true;
}

/** Step 3's own checks (`60`, `65`, `70`). A correction sends no dates. */
export function reviewProblems(
  draft: ScheduleDraft,
  mode: "new" | "change" | "correct",
  t: Translator,
): Record<string, string> {
  const found: Record<string, string> = {};
  if (mode !== "correct" && draft.effective_from === "") {
    found.effective_from = t("rating.rs.wiz.err.pickDate");
  }
  if (mode !== "new" && draft.change_reason.trim() === "") {
    found.change_reason = t(mode === "correct" ? "rating.rs.wiz.err.reason" : "rating.rs.wiz.err.whatChanged");
  }
  return found;
}

/**
 * ⚠ **THE PER-VERSION MINIMUM IS NEVER SENT** (PO 2026-10-01, option A — the
 * minimum is set per meter size). `draftPayload` still carries a version
 * minimum it reads off a stored version; this strips it so no save from this
 * screen writes one. Billing is the other lane's (it will read the per-size
 * minimum and migrate the old version minimums).
 */
export function wizardPayload(draft: ScheduleDraft, includeIdentity: boolean): Record<string, unknown> {
  const payload = draftPayload({ ...draft, minimum_bill: "" }, includeIdentity);
  delete payload.minimum_bill;
  return payload;
}

export interface RateScheduleThreeStepProps {
  client?: ApiClient;
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
  /** The display year a season's date picker shows (a year is never stored).
   *  Defaults to the tenant's current year; a test passes one. */
  displayYear?: number;
}

export function RateScheduleThreeStep(props: RateScheduleThreeStepProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const { timeZone, dateFormat } = useRegional(props);
  const tariffId = params.tariffId ?? null;

  const [draft, setDraft] = useState<ScheduleDraft | null>(null);
  const [nav, setNav] = useState<WizardNavState>(initialWizardNav());
  const [intent, setIntent] = useState<"change" | "correct">("change");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [saved, setSaved] = useState<ScheduleDetail | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState(false);

  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  const detailQuery = useQuery({
    queryKey: queryKeys.rateSchedule(tariffId ?? "new"),
    queryFn: () => getRateSchedule(tariffId as string, client),
    enabled: tariffId !== null,
  });
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const uomsQuery = useQuery({
    queryKey: queryKeys.lookupEntries("uoms", "", 1, REFERENCE_PAGE_SIZE),
    queryFn: () => getLookupEntries("uoms", { per: REFERENCE_PAGE_SIZE }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const accountTypesQuery = useQuery({
    queryKey: queryKeys.lookupEntries(ACCOUNT_TYPES_LIST, "", 1, 100),
    queryFn: () => getLookupEntries(ACCOUNT_TYPES_LIST, { page: 1, per: 100 }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const sizeClassesQuery = useQuery({
    queryKey: queryKeys.lookupEntries("service_size_classes", "", 1, REFERENCE_PAGE_SIZE),
    queryFn: () => getLookupEntries("service_size_classes", { per: REFERENCE_PAGE_SIZE }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const chargesQuery = useQuery({
    queryKey: queryKeys.charges(CHARGES_FOR_BASE_KEY),
    queryFn: () => getCharges({ per: REFERENCE_PAGE_SIZE, filters: { status: "active" } }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });

  const detail = detailQuery.data ?? null;
  // ⚠ A new version or a correction asks for its OWN reason. `draftFromSchedule`
  // carries the stored version's note, which would arrive pre-typed in *What
  // changed* and file last year's reason under this year's price. A parked
  // DRAFT keeps its note — that note is the draft's own.
  //
  // `DEF-RAT-10149` — `today` is the TENANT's day (BR-TEN-043), so a new
  // version from the live one opens with *Effective from* proposed as the first
  // of next month (or the day after the outgoing start). A parked draft ignores
  // it and keeps its own typed date.
  const tenantToday = todayInZone(timeZone);
  const original =
    detail === null
      ? null
      : detail.current_version != null && detail.draft_version == null
        ? { ...draftFromSchedule(detail, tenantToday), change_reason: "" }
        : draftFromSchedule(detail, tenantToday);
  const current = draft ?? original ?? emptyScheduleDraft();

  const activated = detail?.current_version != null;
  const showingParkedDraft = activated && detail?.draft_version != null;
  const mayCorrect = activated && !showingParkedDraft;
  const correcting = mayCorrect && intent === "correct";
  const mode: "new" | "change" | "correct" = !activated ? "new" : correcting ? "correct" : "change";

  const commit = useMutation({ mutationFn: (kind: "draft" | "activate") => run(kind) });
  const discard = useMutation({
    mutationFn: () => discardRateScheduleDraft(tariffId as string, client),
    onSuccess: (next) => {
      queryClient.setQueryData(queryKeys.rateSchedule(tariffId as string), next);
      setConfirmDiscard(false);
      setRefusal(null);
      setDraft(draftFromSchedule(next, todayInZone(timeZone)));
    },
    onError: (error: unknown) => {
      setConfirmDiscard(false);
      setRefusal(refusalOf(error, translate));
    },
  });

  function patch(next: Partial<ScheduleDraft>): void {
    setDraft({ ...current, ...next });
    if (refusal !== null) setRefusal(null);
    if (Object.keys(errors).length > 0) {
      const cleared = { ...errors };
      for (const key of Object.keys(next)) delete cleared[key];
      setErrors(cleared);
    }
  }

  /** One transactional call per outcome (BR-SHL-019). */
  async function run(kind: "draft" | "activate"): Promise<ScheduleDetail> {
    if (kind === "draft") {
      return tariffId === null
        ? await createRateSchedule(wizardPayload(current, true), client)
        : await updateRateSchedule(tariffId, wizardPayload(current, false), client);
    }
    if (tariffId === null) {
      return await createRateSchedule({ ...wizardPayload(current, true), ...activationDates(current) }, client);
    }
    if (correcting) {
      // BR-RAT-104 — a correction restates the SAME window: no dates, ever.
      return await correctRateScheduleVersion(
        tariffId,
        detail?.current_version?.id as string,
        { ...wizardPayload(current, false), reason: current.change_reason.trim() },
        client,
      );
    }
    if (activated) {
      return await createRateScheduleVersion(
        tariffId,
        { ...wizardPayload(current, false), ...activationDates(current), reason: current.change_reason.trim() },
        client,
      );
    }
    return await activateRateSchedule(tariffId, { ...wizardPayload(current, false), ...activationDates(current) }, client);
  }

  /** The server's field errors, each at its own box (`DEF-RAT-5830`). */
  function mapErrors(error: unknown): Record<string, string> {
    const mapped: Record<string, string> = {};
    if (isApiError(error)) {
      for (const fieldError of error.fieldErrors) {
        if (fieldError.field !== null) {
          mapped[fieldError.field] = t(fieldError.message_key, refusalParams(fieldError.params, error.traceId));
        }
      }
    }
    return mapped;
  }

  async function submit(): Promise<WizardCommitOutcome> {
    setRefusal(null);
    const problems = reviewProblems(current, mode, translate);
    setErrors(problems);
    if (Object.keys(problems).length > 0) {
      return { ok: false, reason: Object.values(problems)[0], refusedOnStep: 3 };
    }
    try {
      const next = await commit.mutateAsync("activate");
      setSaved(next);
      void queryClient.invalidateQueries({ queryKey: ["rate-schedules"] });
      return { ok: true };
    } catch (error) {
      const rendered = refusalOf(error, translate);
      setRefusal(rendered);
      setErrors(mapErrors(error));
      return { ok: false, reason: rendered.message };
    }
  }

  async function saveDraft(): Promise<void> {
    setRefusal(null);
    try {
      await commit.mutateAsync("draft");
      void queryClient.invalidateQueries({ queryKey: ["rate-schedules"] });
      navigate(tenantPath(RATES_LIST));
    } catch (error) {
      setRefusal(refusalOf(error, translate));
      setErrors(mapErrors(error));
    }
  }

  if (permissionsQuery.isPending || (tariffId !== null && detailQuery.isPending)) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access) || ratingIsReadOnly(access) || (tariffId !== null && isPermissionDenied(detailQuery.error))) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
  }
  if (tariffId !== null && detail === null) {
    return (
      <PermissionDenied helper={t("rating.rateDetail.failedTitle")} onBack={() => navigate(tenantPath(RATES_LIST))} />
    );
  }

  const services = (servicesQuery.data ?? []).filter((row) => row.enabled);
  const service = services.find((row) => row.service === current.service);
  const serviceName = service?.name ?? "";
  const uomEntries = uomsQuery.data?.results ?? [];
  const declaredUom = declaredUnitFor(services, current.service);
  // DEF-RAT-10220 (PO 2026-10-17) — a FLAT schedule priced per the unit this
  // service's sizes SUM in (kW for solar and battery…) bills the summed
  // capacity, but its natural structure is Capacity; say so, in two short
  // sentences (B14 rule 33). Read off the service's own `capacity_uom` — no
  // service is named here.
  const summingUom = service?.capacity_uom ?? null;
  const flatPerCapacity = current.model === "flat" && summingUom !== null && sameUnit(current.uom, summingUom);
  const uomOptions = scheduleUomOptions(uomEntries, current.service, declaredUom, [current.uom]).map((option) => ({
    value: option.value,
    label: option.label,
    disabled: option.reason !== "offered",
  }));
  const accountTypes = accountTypesQuery.data?.results ?? [];
  const className =
    current.account_type_id === ""
      ? t("rating.rs.everyClass")
      : (accountTypes.find((row) => row.id === current.account_type_id)?.name ?? "—");
  const allCharges = chargesQuery.data?.results ?? [];
  // DEF-RAT-10026 — the classes a base code covers, in the utility's own type
  // names (an empty scope is every class), for the base-code picker below.
  const baseCodeClasses = (codes: readonly string[] | undefined): string =>
    (codes ?? []).length === 0
      ? t("rating.chargeCode.everyClass")
      : (codes ?? [])
          .map(
            (code) =>
              accountTypes.find((row) => row.code === code)?.name ??
              t(`rating.customerClass.${code}`, { defaultValue: code }),
          )
          .join(", ");
  const baseCodes = allCharges.filter(
    (row) => row.is_base && row.service === current.service && row.status !== "inactive",
  );
  const baseCharge = boundBaseChargeFor(allCharges, current.service, current.base_charge_code);
  // DEF-RAT-9111 — a saved schedule priced from each class's own base code.
  const perClassBase =
    detail !== null && (detail.current_version ?? detail.draft_version)?.base_charge_code == null;
  // DEF-RAT-9118 — and while it still names no class and no code, steps 2 and 3
  // show EVERY class code's prices, as View details does (`_base_codes_shown`).
  // They showed the first code alone (BASE-W), so the commercial BASE-W-COM
  // prices the edited schedule bills were nowhere on the screen.
  const classCharges =
    perClassBase && current.account_type_id === "" && current.base_charge_code === "" && baseCodes.length > 1
      ? [...baseCodes].sort((a, b) => a.code.localeCompare(b.code))
      : [];
  const baseCodeText =
    classCharges.length > 1
      ? classCharges.map((row) => row.code).join(" · ")
      : current.base_charge_code === ""
        ? ""
        : (baseCharge?.code ?? "");
  const sizeClasses = sizeClassesForService(
    sizeClassesQuery.data?.results ?? [],
    current.service,
    current.size_rows.map((row) => row.size_class),
  ).filter((entry) => current.service === "" || entry.service?.code === current.service || current.size_rows.some((row) => row.size_class === entry.code));
  const assetKey = sizeClasses.length > 0 ? `rating.chargeCode.asset.${current.service || "meter"}` : null;
  const assetName = assetKey === null ? null : t(assetKey, { defaultValue: t("rating.chargeCode.asset.meter") });
  const counted = baseRowsPriced(current, baseCharge, classCharges);
  const sizesPriced = counted.total === 0 ? t("rating.rs.oneAmount") : t("rating.rs.sizesOf", { priced: counted.priced, total: counted.total });
  const structureWord = current.model === "" ? "" : t(`rating.model.${current.model}`, { defaultValue: current.model });
  // The version this edit makes, counted on the schedule as SAVED once it is —
  // the refetched list already holds the new row, so `+ 1` on it read `v3` for
  // a schedule's second version.
  // `DEF-RAT-8829` — counted the way View details numbers them: every version
  // by its position, a correction included (`15-view-SEWER-audit.png` draws the
  // correction as `v2 · Fixes v1`). This counted only the rows NOT superseded,
  // so after a correction the next change read one lower here than there.
  const versionCount = ((saved ?? detail)?.versions ?? []).filter((row) => row !== null).length;
  // A correction names the version it CORRECTS (image 71: `v3 (corrected)`):
  // the one in force before the save, the one the saved correction points at
  // after it. The count of live rows read `v2 (corrected)` for a correction of
  // v1 once a v2 was scheduled.
  const correctedOrdinal =
    versionOrdinal(
      (saved ?? detail)?.versions ?? [],
      saved !== null ? (saved.current_version?.corrects ?? saved.current_version?.id) : detail?.current_version?.id,
    ) ?? Math.max(versionCount, 1);
  const versionText =
    detail === null
      ? null
      : correcting
        ? t("rating.rs.wiz.versionCorrected", { n: correctedOrdinal })
        : t("rating.rateDetail.kicker.version", { n: saved !== null ? versionCount : versionCount + 1 });
  const reach =
    detail === null
      ? null
      : t("rating.rs.wiz.reach", { units: formatQuantity(String(detail.applied_to_accounts)), count: detail.used_by_plans });
  const day = (value: string) => (value === "" ? "" : formatDate(value, timeZone, dateFormat));
  const displayYear = props.displayYear ?? Number(new Date().getFullYear());

  /** Step 1 → a service picked: its declared unit, its declared base code. */
  function chooseService(next: string): void {
    if (activated) return; // Locked once in force.
    const declared = declaredUnitFor(services, next);
    const offered = scheduleUomOptions(uomEntries, next, declared).filter((option) => option.reason === "offered");
    const codes = allCharges.filter((row) => row.is_base && row.service === next && row.status !== "inactive");
    // DEF-RAT-9015 / DEF-BIL-9014 — a method the new service cannot use
    // (time of use without a meter; a share on a metered service) is not left picked.
    const basis = services.find((row) => row.service === next)?.billing_basis;
    const offeredModel = structureOptions(translate, basis).find((option) => option.value === current.model);
    patch({
      service: next,
      uom: offered.length === 1 ? offered[0].value : "",
      base_charge_code: codes.length === 1 ? codes[0].id : "",
      size_rows: [],
      ...(offeredModel?.disabled === true ? { model: "flat" } : {}),
    });
  }

  // ── step 1 · Details ──────────────────────────────────────────────────────
  const stepDetails = (
    <div className="flex flex-col gap-5" data-step="details">
      {mayCorrect && (
        <Panel as="section" title={t("rating.rate.intent.title")} data-rs-intent={intent}>
          <SegmentedField
            id="rs-intent"
            label={t("rating.rate.intent.title")}
            value={intent}
            onChange={(value) => setIntent(value === "correct" ? "correct" : "change")}
            options={[
              { value: "change", label: t("rating.rate.intent.change") },
              { value: "correct", label: t("rating.rate.intent.correct") },
            ]}
          />
          <p className="m-0 mt-2 text-base text-neutral-700">
            {t(correcting ? "rating.rs.wiz.correctFact" : "rating.rs.wiz.changeFact")}
          </p>
        </Panel>
      )}
      <Panel as="section" title={t("rating.rs.wiz.schedule")}>
        <div className={FIELDS}>
          <TextField
            id="rs-name"
            label={t("rating.rate.nameLabel")}
            value={current.name}
            onChange={(name) => patch({ name })}
            required
            help={t("rating.rs.wiz.nameHelp")}
            error={errors.name}
          />
          <SelectField
            id="rs-service"
            label={t("rating.rs.col.service")}
            value={current.service}
            onChange={chooseService}
            required
            disabled={activated}
            placeholder={t("rating.rs.wiz.choose")}
            options={services.map((row) => ({ value: row.service, label: row.name }))}
            help={activated ? t("rating.rs.wiz.serviceLocked") : undefined}
            error={errors.service}
          />
          <SelectField
            id="rs-unit"
            label={t("rating.rs.fact.unit")}
            value={current.uom}
            onChange={(uom) => patch({ uom })}
            required
            placeholder={t("rating.rs.wiz.choose")}
            options={uomOptions}
            error={errors.uom}
          />
          <SelectField
            id="rs-class"
            label={t("rating.rs.col.customerClass")}
            value={current.account_type_id === "" ? "every" : current.account_type_id}
            onChange={(value) => patch({ account_type_id: value === "every" ? "" : value })}
            required
            options={[
              { value: "every", label: t("rating.rs.everyClass") },
              ...accountTypes.filter((row) => row.active).map((row) => ({ value: row.id, label: row.name })),
            ]}
          />
          <SelectField
            id="rs-structure"
            label={t("rating.rate.modelLabel")}
            value={current.model}
            onChange={(model) => patch({ model })}
            required
            disabled={correcting}
            options={structureOptions(
              translate,
              services.find((row) => row.service === current.service)?.billing_basis,
            ).map((option) =>
              option.value === BASE_ONLY_MODEL ? { ...option, label: t("rating.rs.wiz.baseOnlyLater") } : option,
            )}
            help={flatPerCapacity ? t("rating.rs.wiz.flatPerCapacity", { uom: summingUom }) : undefined}
            error={errors.model}
          />
          <SearchSelectField
            id="rs-base-code"
            label={t("rating.rs.fact.baseChargeCode")}
            value={current.base_charge_code}
            onChange={(base_charge_code) => patch({ base_charge_code })}
            required
            dropdown
            placeholder={t("rating.rs.wiz.searchCodes")}
            // DEF-RAT-10026 (PO 2026-10-09) — a service may hold two base codes
            // for one class (BASE-E and BASE-E-OUT, both Residential), so each
            // option shows its CODE · NAME and, at the right, the classes it
            // covers; the code alone told the two apart only by string.
            options={baseCodes.map((row) => ({
              value: row.id,
              label: `${row.code} · ${row.name}`,
              detail: baseCodeClasses(row.applies_to_customer_classes),
              search: `${row.code} ${row.name}`,
            }))}
            error={errors.base_charge_code}
          />
        </div>
      </Panel>
    </div>
  );

  // ── step 2 · Pricing ──────────────────────────────────────────────────────
  const stepPricing = (
    <div className="flex flex-col gap-5" data-step="pricing">
      <BaseRatesTable
        draft={current}
        sizeClasses={sizeClasses}
        baseCharge={baseCharge}
        classCharges={classCharges}
        serviceName={serviceName}
        assetName={assetName}
        errors={errors}
        onPatch={patch}
      />
      <UsageRatesEditor
        draft={current}
        errors={errors}
        displayYear={displayYear}
        onPatch={patch}
        percentEditor={<PercentEditor draft={current} client={client} fieldErrors={errors} onPatch={patch} />}
      />
    </div>
  );

  // ── step 3 · Review ───────────────────────────────────────────────────────
  const scheduleFacts: Fact[] = [
    { id: "name", label: t("rating.rs.wiz.field.name"), value: current.name || "—" },
    { id: "service", label: t("rating.rs.col.service"), value: serviceName || "—" },
    { id: "unit", label: t("rating.rs.fact.unit"), value: current.uom || "—" },
    { id: "class", label: t("rating.rs.col.customerClass"), value: className },
    { id: "structure", label: t("rating.rates.col.structure"), value: structureWord || "—" },
    { id: "baseCode", label: t("rating.rs.fact.baseChargeCode"), value: baseCodeText || "—" },
  ];
  const changes = draftChanges(
    original === null ? null : wizardPayload(original, false),
    wizardPayload(current, false),
    translate,
  );
  const stepReview = (
    <div className="flex flex-col gap-5" data-step="review">
      <FactsPanel title={t("rating.rs.wiz.schedule")} name="rs-review-schedule" facts={scheduleFacts} />
      <BaseRatesTable
        draft={current}
        sizeClasses={sizeClasses}
        baseCharge={baseCharge}
        classCharges={classCharges}
        serviceName={serviceName}
        assetName={assetName}
        errors={{}}
        onPatch={() => undefined}
        readOnly
      />
      <Panel as="section" data-rs-review-usage="">
        <UsageChargesTable model={current.model} structure={draftStructureForView(current)} uom={current.uom || null} />
      </Panel>
      {detail !== null && (
        <TableArray<{ item: string; now: string; next: string }>
          readOnly
          collection="rs-changes"
          title={t("rating.rs.wiz.whatChanges")}
          fact={
            <span className="font-heading text-xs font-semibold uppercase tracking-kicker">
              {t("rating.rs.wiz.changesCount", { count: changes.length })}
            </span>
          }
          columns={[
            { key: "item", label: t("rating.rs.wiz.col.item"), cell: (row) => row.item },
            { key: "now", label: t("rating.rs.wiz.col.now"), cell: (row) => row.now },
            { key: "next", label: t("rating.rs.wiz.col.new"), cell: (row) => <strong className="text-danger-700">{row.next}</strong> },
          ]}
          rows={changes}
          rowKey={(row) => row.item}
          emptyText={t("rating.rs.wiz.noChanges")}
        />
      )}
      {!correcting && (
        <Panel as="section" title={t("rating.rs.wiz.when")}>
          <div className="grid grid-cols-2 gap-x-4 gap-y-4">
            <DatePickerField
              id="rs-effective-from"
              label={t("rating.rs.fact.effectiveFrom")}
              value={current.effective_from}
              onChange={(effective_from) => patch({ effective_from })}
              dateFormat={dateFormat}
              required
              help={t("rating.rs.wiz.fromHelp")}
              error={errors.effective_from}
            />
            <DatePickerField
              id="rs-effective-to"
              label={t("rating.rs.fact.effectiveTo")}
              value={current.effective_to}
              onChange={(effective_to) => patch({ effective_to })}
              dateFormat={dateFormat}
              min={current.effective_from === "" ? undefined : current.effective_from}
              help={t("rating.rs.wiz.toHelp")}
              error={errors.effective_to}
            />
          </div>
          {mode === "change" && (
            <div className="mt-4">
              <TextField
                id="rs-what-changed"
                label={t("rating.rs.wiz.whatChanged")}
                value={current.change_reason}
                onChange={(change_reason) => patch({ change_reason })}
                required
                multiline
                error={errors.change_reason}
              />
            </div>
          )}
          <div className="mt-4 flex flex-wrap gap-6">
            <CheckboxField
              id="rs-notify"
              label={t("rating.rs.wiz.notify")}
              checked={current.notify_customers}
              onChange={(notify_customers) => patch({ notify_customers })}
            />
            <CheckboxField
              id="rs-publish"
              label={t("rating.rs.wiz.publish")}
              checked={current.publish_public}
              onChange={(publish_public) => patch({ publish_public })}
            />
          </div>
        </Panel>
      )}
      {correcting && (
        <Panel as="section" title={t("rating.rs.wiz.correction")}>
          <TextField
            id="rs-reason"
            label={t("rating.rate.correct.reasonLabel")}
            value={current.change_reason}
            onChange={(change_reason) => patch({ change_reason })}
            required
            multiline
            error={errors.change_reason}
          />
          <ChargeNote tone="info" name="rs-sent-bills">
            {detail?.current_version_issued_bills === null || detail?.current_version_issued_bills === undefined
              ? t("rating.rate.correct.billsUnknown")
              : t("rating.rs.wiz.billsSent", { count: detail.current_version_issued_bills })}
          </ChargeNote>
        </Panel>
      )}
      {!correcting && (
        <Panel
          as="section"
          title={t("rating.rs.wiz.regulatorFiling")}
          trailing={
            <span className="font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
              {t("rating.rs.wiz.optional")}
            </span>
          }
        >
          <div className={FIELDS}>
            <TextField
              id="rs-regulator-ref"
              label={t("rating.rs.wiz.reference")}
              value={current.regulator_ref}
              onChange={(regulator_ref) => patch({ regulator_ref })}
            />
            <TextField
              id="rs-authority"
              label={t("rating.rs.wiz.authority")}
              value={current.filing_authority}
              onChange={(filing_authority) => patch({ filing_authority })}
            />
            <TextField
              id="rs-approver"
              label={t("rating.rs.wiz.approvedBy")}
              value={current.regulator_approver}
              onChange={(regulator_approver) => patch({ regulator_approver })}
            />
            <DatePickerField
              id="rs-filed-on"
              label={t("rating.rs.wiz.submittedOn")}
              value={current.filed_on}
              onChange={(filed_on) => patch({ filed_on })}
              dateFormat={dateFormat}
            />
            <DatePickerField
              id="rs-approved-on"
              label={t("rating.rs.wiz.approvedOn")}
              value={current.regulator_approved_on}
              onChange={(regulator_approved_on) => patch({ regulator_approved_on })}
              dateFormat={dateFormat}
            />
          </div>
        </Panel>
      )}
      {saved !== null && (
        <ChargeNote
          tone="success"
          name="rs-saved"
          lead={t(
            mode === "new" ? "rating.rs.wiz.createdLead" : mode === "correct" ? "rating.rs.wiz.correctedLead" : "rating.rs.wiz.newVersionLead",
            { name: saved.name },
          )}
        >
          {mode === "correct" ? "" : t("rating.rs.wiz.savedFrom", { from: day(current.effective_from) })}
        </ChargeNote>
      )}
    </div>
  );

  const steps: WizardStep[] = [
    {
      id: RATE_WIZARD3_STEPS[0],
      label: t("rating.rs.wiz.step.details"),
      content: stepDetails,
      validate: () => {
        const problems = detailsProblems(current, translate, perClassBase);
        setErrors(problems);
        return Object.keys(problems).length === 0 ? true : Object.values(problems)[0];
      },
    },
    {
      id: RATE_WIZARD3_STEPS[1],
      label: t("rating.rs.wiz.step.pricing"),
      content: stepPricing,
      validate: () => pricingProblem(current, translate),
    },
    { id: RATE_WIZARD3_STEPS[2], label: t("rating.rs.wiz.step.review"), content: stepReview },
  ];

  const title = detail === null ? t("rating.rate.newTitle") : t("rating.rate.editTitle", { name: detail.name });
  return (
    <div className="flex flex-col gap-5 pt-6 px-4 pb-8" data-screen="RAT-03" data-rs-mode={mode}>
      <PageHeader
        backTo={
          detail === null
            ? { to: tenantPath(RATES_LIST), label: t("rating.rs.wiz.crumbList") }
            : { to: tenantPath(`${RATES_LIST}/${detail.id}`), label: detail.name }
        }
        title={title}
      />
      <RefusalNotice refusal={refusal} />
      <div className={LAYOUT} data-rs-layout="">
        <WizardFrame
          steps={steps}
          nav={nav}
          onNavChange={setNav}
          // DEF-RAT-8824: NO `backAtStart`. That is the bulk bill run's opt-in
          // for a footer with no Cancel; beside `cancel` it gave the row two
          // `mr-auto` items, which split the free space and floated `Back` in
          // the middle. Without it the row is the one `PlanWizard`,
          // `DiscountWizard` and `AddUnitsWizard` draw: `Cancel` | `Discard
          // draft` · `Save draft` · `Back` · `Continue`/commit.
          doneMark="tick"
          commitLabel={t(
            mode === "new" ? "rating.rs.wiz.create" : mode === "correct" ? "rating.rs.wiz.saveCorrection" : "rating.rs.wiz.createVersion",
          )}
          commitDisabled={saved !== null}
          commitFailedTitle={t("rating.rate.activateFailed")}
          onCommit={submit}
          onCommitted={() => undefined}
          cancel={{
            label: t("rating.plan.cancel"),
            onCancel: () => navigate(tenantPath(detail === null ? RATES_LIST : `${RATES_LIST}/${detail.id}`)),
          }}
          secondaryActions={
            showingParkedDraft || nav.step === 3 ? (
              <>
                {/* DEF-RAT-8824: out of the page head, into the one bar. */}
                {showingParkedDraft && (
                  <Button disabled={discard.isPending} onClick={() => setConfirmDiscard(true)}>
                    {t("rating.rate.discardDraft")}
                  </Button>
                )}
                {nav.step === 3 && (
                  <Button disabled={commit.isPending || saved !== null} onClick={() => void saveDraft()}>
                    {t("rating.rs.wiz.saveDraft")}
                  </Button>
                )}
              </>
            ) : undefined
          }
        />
        <div className="col-start-2 row-start-2 self-start sticky top-4">
          <ScheduleAside
            editing={detail !== null}
            name={current.name}
            service={serviceName}
            structure={structureWord}
            unit={current.uom}
            customerClass={className}
            baseCode={baseCodeText}
            version={versionText}
            sizesPriced={sizesPriced}
            reach={reach}
            saved={saved !== null}
          />
        </div>
      </div>
      {confirmDiscard && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("rating.rate.confirm.discardDraft.title")}
          consequence={t("rating.rate.confirm.discardDraft.body")}
          confirmLabel={t("rating.rate.confirm.discardDraft.verb")}
          working={discard.isPending}
          onConfirm={() => discard.mutate()}
          onCancel={() => setConfirmDiscard(false)}
        />
      )}
    </div>
  );
}
