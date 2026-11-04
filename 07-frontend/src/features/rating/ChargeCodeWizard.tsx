// ── Trace ──────────────────────────────────────────────
// Change:   CR-156-BRC10 wave B — CHG-02, the Add and Edit wizard for a charge
//           code, REBUILT FROM THE IMAGES (B14 rules 41, 42; rule 44 for
//           spacing, sizes and components; rule 37 — every drawn figure is an
//           illustration). Screen: CHG-02.
// Images:   05-prototype/charge-codes-2026-10-01/images
//             Add  step 1 43–50 · step 2 51–64 · step 3 65–72
//             Edit 73–83 (BASE-T, LATE, APP-FEE; reason error; saved)
// Rulings:  decision log 2026-10-01 (last column "charge-code redesign"):
//           steps Details · Pricing · Review · "What is it?" Base / Plan /
//           Other · the code is a searchable dropdown of FREE Settings codes ·
//           the bill line fills in and stays editable (option A) · How it bills
//           on step 1, every setting a dropdown, a base's two signed ones fixed
//           (B4.3 cut down by days; on every bill) · GL in the side panel ·
//           step 2 is the shared TableArray, sizes a dropdown, one price column ·
//           Effective from (required, "Pick a date.") / Effective to (blank = no
//           end) on Add AND Edit · a reason on Edit.
// Defects:  DEF-RAT-8713 · 8714 · 8715 · 8716 · 8717 · 8719 (closed by this
//           rebuild — each has a DOM test that fails on the old screen).
// ───────────────────────────────────────────────────────
/**
 * ⚠ **ADD CONFIGURES A CODE SETTINGS ALREADY MINTED.** The picker lists the
 * tenant's `charges` rows not yet in use (`GET /charges/picker`), so the commit
 * for *Create charge code* is a `PATCH` of the picked row; a `POST` would be
 * refused as a duplicate of the code Settings holds.
 *
 * ⚠ **NOTHING SAVED IS EVER DELETED.** The server closes a changed price the day
 * before *Effective from* and marks it killed; this screen only states the new
 * prices and the date (`CR-156-BRC10` §7).
 *
 * ⚠ **THE TWO PRICINGS WAVE B SHOWED DISABLED ARE OFFERED SINCE WAVE C
 * (`DEF-RAT-8753`)** — a penalty's percent and minimum BY CLASS (stored as
 * dated terms rows, `class_terms`) and an Other code's amount *entered when
 * used* (`amount_rule = per_case`, CR-010 A2).
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api, isApiError, refusalParams } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  CUSTOMER_CLASSES,
  getCharge,
  getChargePickerAnswer,
  getLookupEntries,
  getMyPermissions,
  getTenantServices,
  updateCharge,
} from "@/api/endpoints";
import type { ChargeKind, ChargeRow, LookupEntry } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import type { RegionalDateFormat } from "@/components/DateCell";
import { formatDate } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import type { Fact } from "@/components/FactBlock";
import { DatePickerField, SearchSelectField, SelectField, TextField } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { WarningBox } from "@/components/WarningBox";
import { Panel } from "@/components/Panel";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { CellSelect, CellStatic, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import { WizardFrame, initialWizardNav } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { useRegional } from "@/features/metering/meteringShared";
import { RefusalNotice, isPermissionDenied, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  ALL_SIZES,
  KIND_TYPES,
  STORED_CLASSES,
  assetKeyFor,
  chargePayload,
  chargedKey,
  draftChanges,
  draftFromCharge,
  emptyDraft,
  emptyRow,
  fixedFor,
  floorText,
  graceDaysValid,
  graceShown,
  hasFloors,
  isPercentPenalty,
  penaltyChargesNothing,
  pricedByWords,
  pricedCount,
  rangeText,
  sizeLabel,
  sizeListedTwice,
  sizeRowKey,
  sizesFor,
  withKindDefaults,
} from "./chargeCodeModel";
import type { ChargeCodeDraft, PriceDraftRow, PricedBy } from "./chargeCodeModel";
import { ChargeNote, ChargeSummaryAside, FactsPanel, GlValue, PricesReadTable, dollars, graceText } from "./chargeCodeParts";
import type { AsideStatus, PriceReadRow } from "./chargeCodeParts";
import { typeWords } from "./ChargeCodeDetailPage";
import { DEFINITION_ROUTES, definitionPath } from "./definitionDetail";
import { ACCOUNT_TYPES_LIST, GuardedButton, isDecimalShape, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "./ratingShared";
import type { Translator } from "./ratingShared";

export const CHARGE_WIZARD_STEPS = ["details", "pricing", "review"] as const;

/** The charge-codes landing tab — what Cancel returns to. */
export const CHARGE_LIST_ROUTE = DEFINITION_ROUTES.charge.listRoute;

/** `apps/rating/constants.py` `PRICE_HISTORY_EPOCH` — the backfill's start,
 *  not a date anyone chose (2.433.4); never shown as a real date. */
const PRICE_HISTORY_EPOCH = "2000-01-01";

const SIZE_PAGE = 200;
const CLASS_PAGE = 100;

/** The page grid: the wizard on the left, the summary aside on the right — the
 *  One-time bill's layout, which the PO named as this redesign's reference.
 *
 *  ⚠ **THE FOOTER SPANS BOTH COLUMNS — `DEF-RAT-9104`**, exactly as the
 *  rate-schedule wizard's does since `DEF-RAT-8824` (2.436.6). PO 2026-10-02:
 *  *"button in details view of chrage code ar all over the place"*. It was
 *  `col-start-1`, so `Save change` ended at the right edge of the LEFT column
 *  with the summary hanging beside it. */
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

export interface ChargeCodeWizardProps {
  client?: ApiClient;
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
}

/** Every customer class the tenant can pick, in the drawn order. */
function classCodes(served: readonly LookupEntry[]): string[] {
  const live = served.filter((row) => row.active).map((row) => row.code);
  const codes = live.length > 0 ? live : [...CUSTOMER_CLASSES];
  const drawn: string[] = [...CUSTOMER_CLASSES];
  const rank = (code: string) => (drawn.includes(code) ? drawn.indexOf(code) : drawn.length);
  return [...codes].sort((a, b) => rank(a) - rank(b));
}

export function ChargeCodeWizard(props: ChargeCodeWizardProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const client = props.client ?? api;
  const queryClient = useQueryClient();
  const { timeZone, dateFormat } = useRegional(props);
  const editId = params.definitionId ?? null;
  const editing = editId !== null;

  const [draft, setDraft] = useState<ChargeCodeDraft | null>(null);
  const [nav, setNav] = useState<WizardNavState>(initialWizardNav());
  const [refusal, setRefusal] = useState<Refusal | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState<ChargeRow | null>(null);

  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const sizesQuery = useQuery({
    queryKey: queryKeys.lookupEntries("service_size_classes", "", 1, SIZE_PAGE),
    queryFn: () => getLookupEntries("service_size_classes", { per: SIZE_PAGE }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const classesQuery = useQuery({
    queryKey: queryKeys.lookupEntries(ACCOUNT_TYPES_LIST, "", 1, CLASS_PAGE),
    queryFn: () => getLookupEntries(ACCOUNT_TYPES_LIST, { page: 1, per: CLASS_PAGE }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const storedQuery = useQuery({
    queryKey: queryKeys.charge(editId ?? "new"),
    queryFn: () => getCharge(editId as string, client),
    enabled: editing,
  });
  const entries: readonly LookupEntry[] = sizesQuery.data?.results ?? [];
  const stored = storedQuery.data ?? null;
  const original = stored === null ? null : draftFromCharge(stored, entries);
  const current: ChargeCodeDraft = draft ?? original ?? emptyDraft();

  // DEF-RAT-10026 (PO 2026-10-09) — the step-1 base-code clash warning
  // (DEF-RAT-9799) is retired with the save-time refusal it mirrored: a service
  // may hold two or more base codes for one customer class, and each rate
  // schedule names the one it bills.
  const pickerQuery = useQuery({
    queryKey: ["charges", "picker", current.kind, current.kind === "base" ? current.service : ""],
    queryFn: () =>
      getChargePickerAnswer(current.kind as ChargeKind, current.kind === "base" ? current.service : null, client),
    enabled: !editing && current.kind !== "" && (current.kind !== "base" || current.service !== ""),
    retry: false,
  });
  // The picked code's own row — its GL account for the side panel (DEF-RAT-8719:
  // the GL is the code's, on every step), and its name for the bill line.
  const pickedQuery = useQuery({
    queryKey: queryKeys.charge(current.chargeId === "" ? "none" : current.chargeId),
    queryFn: () => getCharge(current.chargeId, client),
    enabled: !editing && current.chargeId !== "",
  });
  const codeRow: ChargeRow | null = editing ? stored : (pickedQuery.data ?? null);
  // DEF-RAT-8752 — the service's schedule minimum per size (image 51): from
  // the picker's answer on Add, from the code's own read on Edit.
  const sizeMinimums = editing ? stored?.size_minimums : pickerQuery.data?.size_minimums;

  const commit = useMutation({
    mutationFn: (payload: Record<string, unknown>) => updateCharge(current.chargeId, payload, client),
  });

  function patch(next: Partial<ChargeCodeDraft>): void {
    setDraft(withKindDefaults({ ...current, ...next }));
  }

  if (permissionsQuery.isPending || (editing && storedQuery.isPending)) {
    return <LoadingSkeleton variant="card" />;
  }
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access) || ratingIsReadOnly(access) || (editing && isPermissionDenied(storedQuery.error))) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(CHARGE_LIST_ROUTE))} />;
  }
  if (editing && stored === null) {
    return (
      <FailedWithRetry
        title={t("rating.chargeWizard.loadFailed")}
        reason={t("rating.chargeCode.view.loadFailed")}
        onRetry={() => void storedQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(CHARGE_LIST_ROUTE))}
      />
    );
  }

  const services = (servicesQuery.data ?? []).filter((row) => row.enabled);
  const sizes = sizesFor(entries, current.service);
  const hasSizes = sizes.length > 0;
  const assetKey = assetKeyFor(current.service, current.pricedBy === "size" || (current.kind === "base" && hasSizes));
  const asset = assetKey === null ? null : t(assetKey);
  const serviceWord =
    current.service === "" ? t("rating.charges.anyService") : t(`rating.service.${current.service}`, { defaultValue: current.service });
  const classes = classCodes(classesQuery.data?.results ?? []);
  const className = (code: string | null) =>
    code === null ? t("rating.chargeCode.everyClass") : t(`rating.customerClass.${code}`, { defaultValue: code });
  // DEF-RAT-9176 — a stored scope of two or more classes, in the class words.
  const storedScope = current.storedClasses.length > 1 ? current.storedClasses.map(className).join(", ") : null;
  const words = pricedByWords(current, asset);
  const pricedByText = t(words.key, words.params);
  const counted = pricedCount(current);
  const day = (value: string) => (value === "" ? "—" : formatDate(value, timeZone, dateFormat));

  /** Step 1 → a kind picked: a base prices by size when its service has sizes. */
  function chooseKind(kind: string): void {
    const next = withKindDefaults({
      ...current,
      kind: kind as ChargeKind,
      chargeId: "",
      code: "",
      name: "",
      service: kind === "base" ? "" : current.kind === "base" ? "" : current.service,
      pricedBy: "one",
      flatPenalty: false,
      rows: [emptyRow(ALL_SIZES)],
    });
    setDraft(next);
  }

  function chooseService(service: string): void {
    const scoped = sizesFor(entries, service);
    const pricedBy: PricedBy = current.kind === "base" ? (scoped.length > 0 ? "size" : "one") : current.pricedBy;
    patch({
      service,
      chargeId: editing ? current.chargeId : "",
      code: editing ? current.code : "",
      pricedBy,
      // One row per size of the service, in size order — the clerk removes
      // what the utility does not serve (images 43, 51, 53 count every size).
      rows: pricedBy === "size" ? scoped.map((entry) => emptyRow(entry.code)) : [emptyRow(ALL_SIZES)],
    });
  }

  function choosePricedBy(pricedBy: PricedBy, extra: Partial<ChargeCodeDraft> = {}): void {
    patch({
      ...extra,
      pricedBy,
      rows:
        pricedBy === "entered"
          ? // DEF-RAT-9807 — one row holds the optional default, blank to start.
            [emptyRow(ALL_SIZES)]
          : pricedBy === "class"
            ? classes.slice(0, 2).map((code) => emptyRow(ALL_SIZES, code))
            : pricedBy === "size"
              ? [emptyRow()]
              : [emptyRow(ALL_SIZES)],
    });
  }

  function pickCode(chargeId: string): void {
    const row = (pickerQuery.data?.results ?? []).find((option) => option.id === chargeId);
    if (row === undefined) return;
    patch({ chargeId: row.id, code: row.code, name: row.name });
  }

  const fixed = fixedFor(current);
  // PO 2026-10-06 11 (a) — a penalty's late-fee grace; Billing defaults' grace
  // is the starting value (served on the code's detail read).
  const graceDefault = codeRow?.grace_default ?? null;
  const penalty = current.chargeType === "penalty";
  const grace = graceShown(current, graceDefault);
  const graceProblem = penalty && !graceDaysValid(grace.days) ? t("rating.plans.grace_days_range", { max: 30 }) : null;
  const yesNo = [
    { value: "yes", label: t("rating.yes") },
    { value: "no", label: t("rating.no") },
  ];
  const asYes = (value: boolean) => (value ? "yes" : "no");
  const fixedHelp = t("rating.chargeCode.fixed");

  // ── step 1 · Details ────────────────────────────────────────────────────
  // DEF-RAT-9811 — an Other charge can never be a late fee (BR-BIL-001 reads a
  // plan's PENALTY code), and Ann Arbor built one as Other because nothing
  // said so. The hint shows while the kind can still be changed: on Edit the
  // kind is locked and the hint would name a choice the clerk does not have.
  const kindHelp =
    current.kind === ""
      ? undefined
      : current.kind === "other" && !editing
        ? `${t("rating.chargeCode.kindHelp.other")} ${t("rating.chargeCode.lateFeeKindHint")}`
        : t(`rating.chargeCode.kindHelp.${current.kind}`);
  // DEF-RAT-9813 — recurring AND automatic puts the code on every account's
  // every bill (BR-RAT-117). Legitimate for a monthly fee, so a WARNING and
  // never a refusal; a base code is that by design and is not warned about.
  const billsEveryone = current.kind !== "base" && current.kind !== "" && current.chargeType === "recurring" && current.autoApply;
  const serviceOptions =
    current.kind === "base"
      ? services.map((row) => ({ value: row.service, label: row.name }))
      : [{ value: "", label: t("rating.charges.anyService") }, ...services.map((row) => ({ value: row.service, label: row.name }))];
  const typeOptions = (current.kind === "" ? [] : KIND_TYPES[current.kind]).map((type) => ({
    value: type,
    label: typeWords(type, translate),
  }));
  const chargedOptions = (current.kind === "" ? [] : KIND_TYPES[current.kind]).map((type) => ({
    value: type,
    label: t(chargedKey(type)),
  }));

  const stepDetails = (
    <div className="flex flex-col gap-5" data-step="details">
      <Panel as="section" title={t("rating.chargeCode.charge")}>
        <div className={FIELDS}>
          <SelectField
            id="cc-kind"
            label={t("rating.chargeCode.field.whatIsIt")}
            value={current.kind}
            onChange={chooseKind}
            required
            // DEF-RAT-9804 — a saved value to READ, not a control to look past.
            locked={editing}
            placeholder={t("rating.chargeCode.choose")}
            options={(["base", "plan", "other"] as const).map((kind) => ({ value: kind, label: t(`rating.chargeCode.kind.${kind}`) }))}
            help={kindHelp}
          />
          <SelectField
            id="cc-service"
            label={t("rating.chargeCode.field.service")}
            value={current.service}
            onChange={chooseService}
            required
            locked={editing}
            disabled={!editing && current.kind === ""}
            placeholder={current.kind === "base" ? t("rating.chargeCode.choose") : undefined}
            options={serviceOptions}
            help={editing ? fixedHelp : undefined}
          />
          {editing ? (
            // DEF-RAT-9806 — the Add form's searchable dropdown (PO: "code field
            // should be dropdown ; as per add form"), LOCKED: the code is on
            // sent bills (hard rule 4) and cannot change. Its one option is the
            // code itself, in the picker's own `CODE · name` words.
            <SearchSelectField
              id="cc-code"
              label={t("rating.chargeCode.field.code")}
              value={current.chargeId}
              onChange={() => undefined}
              required
              dropdown
              locked
              options={[
                {
                  value: current.chargeId,
                  label: stored?.name ? `${current.code} · ${stored.name}` : current.code,
                },
              ]}
              help={t("rating.chargeCode.codeLocked")}
            />
          ) : (
            <SearchSelectField
              id="cc-code"
              label={t("rating.chargeCode.field.code")}
              value={current.chargeId}
              onChange={pickCode}
              required
              dropdown
              disabled={current.kind === "" || (current.kind === "base" && current.service === "")}
              placeholder={t("rating.chargeCode.searchCodes")}
              options={(pickerQuery.data?.results ?? []).map((row) => ({
                value: row.id,
                label: `${row.code} · ${row.name}`,
                search: row.code,
              }))}
              emptyText={t("rating.chargeCode.pickerEmpty")}
              noMatchText={t("rating.chargeCode.pickerNoMatch")}
              help={t("rating.chargeCode.fromSettings")}
            />
          )}
          <TextField
            id="cc-name"
            label={t("rating.chargeCode.field.billLine")}
            value={current.name}
            onChange={(name) => patch({ name })}
            required
            help={t("rating.chargeCode.billLineHelp")}
            error={errors.name}
          />
          {current.kind === "base" && (
            <>
              <SelectField
                id="cc-class"
                label={t("rating.chargeCode.field.customerClass")}
                value={current.customerClass}
                onChange={(customerClass) => patch({ customerClass })}
                required
                options={[
                  { value: "", label: t("rating.chargeCode.allClasses") },
                  // DEF-RAT-9176 — the code's own two-or-more classes, kept as
                  // stored unless the clerk picks all or one instead.
                  ...(storedScope === null ? [] : [{ value: STORED_CLASSES, label: storedScope }]),
                  ...classes.map((code) => ({ value: code, label: className(code) })),
                ]}
                help={t("rating.chargeCode.classHelp")}
              />
              <SelectField
                id="cc-asset"
                label={t("rating.chargeCode.field.asset")}
                value={asset === null ? "" : "asset"}
                onChange={() => undefined}
                required
                disabled={asset === null}
                options={asset === null ? [{ value: "", label: "—" }] : [{ value: "asset", label: asset }]}
                help={asset === null ? undefined : t("rating.chargeCode.assetHelp")}
              />
              {hasSizes && (
                <SelectField
                  id="cc-priced-by"
                  label={t("rating.chargeCode.field.pricedBy")}
                  value={current.pricedBy === "size" ? "size" : "one"}
                  onChange={(value) =>
                    // DEF-RAT-8844 — one amount for every size is ONE *All sizes* row
                    // (PO 2026-10-01, "Flat amount as an All sizes row", BASE-W $8.00).
                    patch(
                      value === "size"
                        ? { pricedBy: "size", rows: sizes.map((entry) => emptyRow(entry.code)) }
                        : { pricedBy: "one", rows: [emptyRow(ALL_SIZES)] },
                    )
                  }
                  required
                  disabled={editing}
                  options={[
                    { value: "size", label: t("rating.chargeCode.col.size") },
                    { value: "one", label: t("rating.rs.allSizes") },
                  ]}
                />
              )}
            </>
          )}
          {current.kind === "plan" && (
            <>
              <SelectField
                id="cc-type"
                label={t("rating.chargeCode.field.type")}
                value={current.chargeType}
                onChange={(chargeType) => patch({ chargeType })}
                required
                options={typeOptions}
                // DEF-RAT-9812 — percent pricing (with a minimum) is offered
                // only for a Penalty; under Recurring it is silently absent.
                help={t("rating.chargeCode.lateFeeTypeHint")}
              />
              <SelectField
                id="cc-priced-by"
                label={t("rating.chargeCode.field.pricedBy")}
                value={current.chargeType === "penalty" && current.flatPenalty ? "amount" : current.pricedBy}
                onChange={(value) => {
                  // DEF-RAT-8843 — a penalty is a percent and minimum, OR one flat
                  // amount (NSF $30.00, TAMPER $250.00), stored as Edit stores it.
                  if (value === "amount") {
                    patch({ flatPenalty: true, pricedBy: "one", rows: [emptyRow(ALL_SIZES)] });
                    return;
                  }
                  choosePricedBy(value as PricedBy, { flatPenalty: false });
                }}
                required
                options={
                  current.chargeType === "penalty"
                    ? [
                        { value: "class", label: t("rating.chargeCode.pricedByOption.class") },
                        { value: "one", label: t("rating.chargeCode.pricedBy.percent") },
                        { value: "amount", label: t("rating.chargeCode.pricedByOption.one") },
                      ]
                    : [
                        { value: "class", label: t("rating.chargeCode.pricedByOption.class") },
                        { value: "size", label: t("rating.chargeCode.pricedByOption.size") },
                        { value: "one", label: t("rating.chargeCode.pricedByOption.one") },
                      ]
                }
              />
              {penalty && (
                // PO 2026-10-06 11 (a) — "When Type is Penalty, the form asks
                // Grace days (default 5) and Calendar / Business days".
                <>
                  <TextField
                    id="cc-grace-days"
                    label={t("rating.chargeCode.field.graceDays")}
                    value={grace.days}
                    onChange={(graceDays) => patch({ graceDays })}
                    required
                    numeric
                    error={graceProblem ?? (errors.grace_days || undefined)}
                  />
                  <SelectField
                    id="cc-grace-mode"
                    label={t("rating.chargeCode.field.graceMode")}
                    value={grace.mode}
                    onChange={(graceMode) => patch({ graceMode })}
                    required
                    options={[
                      { value: "calendar", label: t("rating.chargeCode.graceMode.calendar") },
                      { value: "business", label: t("rating.chargeCode.graceMode.business") },
                    ]}
                  />
                </>
              )}
            </>
          )}
          {current.kind === "other" && (
            <SelectField
              id="cc-amount-mode"
              label={t("rating.chargeCode.field.amount")}
              value={current.pricedBy === "entered" ? "entered" : "one"}
              onChange={(value) => choosePricedBy(value as PricedBy)}
              required
              options={[
                { value: "one", label: t("rating.chargeCode.amountMode.now") },
                { value: "entered", label: t("rating.chargeCode.pricedBy.entered") },
              ]}
            />
          )}
        </div>
      </Panel>
      <Panel as="section" title={t("rating.chargeCode.howItBills")}>
        <div className={FIELDS}>
          <SelectField
            id="cc-part-month"
            label={t("rating.chargeCode.field.partMonth")}
            value="fixed"
            onChange={() => undefined}
            required
            // DEF-RAT-9804 — every value fixed for the kind is drawn LOCKED
            // (full-strength, read-only), never dimmed like a dead control.
            locked
            options={[
              {
                value: "fixed",
                label: t(current.kind === "base" ? "rating.chargeCode.partMonth.days" : "rating.chargeCode.partMonth.full"),
              },
            ]}
            help={fixedHelp}
          />
          <SelectField
            id="cc-charged"
            label={t("rating.chargeCode.field.charged")}
            value={current.chargeType}
            onChange={(chargeType) => patch({ chargeType })}
            required
            locked={fixed.charged && current.kind !== ""}
            disabled={current.kind === ""}
            options={chargedOptions.length > 0 ? chargedOptions : [{ value: "", label: "—" }]}
            help={fixed.charged ? fixedHelp : undefined}
          />
          <SelectField
            id="cc-taxed"
            label={t("rating.chargeCode.field.taxed")}
            value={asYes(current.taxable)}
            onChange={(value) => patch({ taxable: value === "yes" })}
            required
            locked={fixed.taxable}
            options={yesNo}
            help={fixed.taxable ? fixedHelp : undefined}
          />
          <SelectField
            id="cc-auto"
            label={t("rating.chargeCode.field.auto")}
            value={asYes(current.autoApply)}
            onChange={(value) => patch({ autoApply: value === "yes" })}
            required
            // DEF-RAT-9805 — a one-time code shows No, locked: nothing reads
            // the flag beside `one_time`, and the server refuses Yes.
            locked={fixed.autoApply}
            options={yesNo}
            help={
              fixed.autoApply
                ? current.kind !== "base" && current.chargeType === "one_time"
                  ? t("rating.chargeCode.autoOneTimeHelp")
                  : fixedHelp
                : undefined
            }
          />
          <SelectField
            id="cc-waive"
            label={t("rating.chargeCode.field.waive")}
            value={asYes(current.waivable)}
            onChange={(value) => patch({ waivable: value === "yes" })}
            required
            options={yesNo}
          />
          <SelectField
            id="cc-own-line"
            label={t("rating.chargeCode.field.ownLine")}
            value={asYes(current.separateLine)}
            onChange={(value) => patch({ separateLine: value === "yes" })}
            required
            options={yesNo}
          />
          {/* DEF-CUS-9819 (PO 2026-10-06) — the utility's application fee:
              every new request gets this code's line automatically. Asked of
              a one-time code only; the server refuses it on any other. */}
          {current.chargeType === "one_time" && (
            <SelectField
              id="cc-application-fee"
              label={t("rating.chargeCode.field.applicationFee")}
              value={asYes(current.applicationFee)}
              onChange={(value) => patch({ applicationFee: value === "yes" })}
              required
              options={yesNo}
            />
          )}
          {/* DEF-RAT-10739 (PO 2026-10-31 P7 = A) — the utility's own NSF fee,
              whatever its code: a bounce charges the marked code its plan
              lists. Asked of a penalty code only; the server refuses it on any
              other, and refuses a second one on the same plan by name. */}
          {current.chargeType === "penalty" && (
            <SelectField
              id="cc-nsf-fee"
              label={t("rating.chargeCode.field.nsfFee")}
              value={asYes(current.nsfFee)}
              onChange={(value) => patch({ nsfFee: value === "yes" })}
              required
              options={yesNo}
            />
          )}
        </div>
        {billsEveryone && (
          // DEF-RAT-9813 — the kit's warning box (B14 rule 43), a warning and
          // never a refusal: a monthly fee on every account is legitimate.
          <div className="mt-5">
            <WarningBox tone="soon" data-warning="bills-everyone" sentence={t("rating.chargeCode.billsEveryone")} />
          </div>
        )}
      </Panel>
    </div>
  );

  // ── step 2 · Pricing ────────────────────────────────────────────────────
  const priceColumnLabel =
    current.kind === "base"
      ? current.customerClass === ""
        ? t("rating.chargeCode.everyClass")
        : current.customerClass === STORED_CLASSES && storedScope !== null
          ? storedScope
          : className(current.customerClass)
      : t("rating.chargeCode.col.amount");
  const factLine = [
    pricedByText,
    current.pricedBy === "entered" ? null : t("rating.chargeCode.pricedOf", { n: counted.priced, total: counted.cells }),
  ]
    .filter((part) => part !== null)
    .join(" · ");
  const fact = <span className="font-heading text-xs font-semibold uppercase tracking-kicker">{factLine}</span>;

  function setRow(index: number, next: Partial<PriceDraftRow>): void {
    patch({ rows: current.rows.map((row, at) => (at === index ? { ...row, ...next } : row)) });
  }
  const moneyCell = (row: PriceDraftRow, index: number, field: "amount" | "percent" | "minimum", label: string) => (
    <input
      type="text"
      inputMode="decimal"
      className="input input-num"
      aria-label={`${label} ${index + 1}`}
      placeholder={field === "amount" ? t("rating.chargeCode.notPriced") : undefined}
      value={row[field]}
      data-cell={`${field}-${index}`}
      onChange={(event) => setRow(index, { [field]: event.target.value })}
    />
  );
  const number: TableArrayColumn<PriceDraftRow> = {
    key: "n",
    label: "#",
    cell: (_row, index) => <span className="text-neutral-600">{index + 1}</span>,
  };
  // DEF-RAT-9322 — "used" is the (size, class) PAIR, the server's own key.
  const usedSizes = new Set(current.rows.map(sizeRowKey));
  const isUsed = (size: string, customerClass: string | null) => usedSizes.has(sizeRowKey({ size, customerClass }));
  // A sized code holding a class row shows WHICH class each row prices, or
  // W-1 every class and W-1 Commercial read as one size twice (DEF-RAT-9322).
  const sizedByClass = current.pricedBy === "size" && current.rows.some((row) => row.customerClass !== null);
  const usedClasses = new Set(current.rows.map((row) => row.customerClass));
  const missing = counted.cells - counted.priced;
  const notPricedNote =
    missing > 0 && current.chargeType !== "penalty" && current.pricedBy === "size" ? (
      <ChargeNote tone="warning" name="not-priced" lead={t("rating.chargeCode.notPricedLead", { n: missing, total: counted.cells })}>
        {t("rating.chargeCode.notPricedBilled")}
      </ChargeNote>
    ) : null;
  const depositNote =
    current.chargeType === "refundable" ? (
      <ChargeNote tone="info" name="deposit">
        {t("rating.chargeCode.depositNote")}
      </ChargeNote>
    ) : null;

  let pricingTable: ReactNode;
  if (current.pricedBy === "entered") {
    // DEF-RAT-9807 — `BR-RAT-1054` AMENDED 2026-10-06 (PO option (a)): an
    // optional default the clerk's amount box starts at. Blank is allowed and
    // is exactly the old behaviour.
    const defaultRow = current.rows[0] ?? emptyRow(ALL_SIZES);
    pricingTable = (
      <Panel as="section" title={t("rating.chargeCode.prices")} trailing={fact}>
        <div className="flex flex-col gap-5">
          <ChargeNote tone="info" name="entered">
            {t("rating.chargeCode.enteredNote")}
          </ChargeNote>
          <div className={FIELDS}>
            <TextField
              id="cc-default-amount"
              label={t("rating.chargeCode.field.defaultAmount")}
              value={defaultRow.amount}
              onChange={(amount) => patch({ rows: [{ ...defaultRow, amount }] })}
              numeric
              placeholder={t("rating.chargeCode.defaultAmountPlaceholder")}
              help={t("rating.chargeCode.defaultAmountHelp")}
            />
          </div>
        </div>
      </Panel>
    );
  } else if (current.chargeType === "penalty" && current.pricedBy === "class") {
    // DEF-RAT-8753 — a percent and a minimum PER CUSTOMER CLASS (image 61).
    pricingTable = (
      <TableArray<PriceDraftRow>
        collection="charge-price-rows"
        title={t("rating.chargeCode.prices")}
        fact={fact}
        rows={current.rows}
        rowKey={(_row, index) => `penalty-class-${index}`}
        emptyText={t("rating.chargeCode.noPrices")}
        removeLabel={t("rating.chargeCode.removeRow")}
        onChange={(rows) => patch({ rows })}
        actions={[
          {
            key: "add-row",
            label: t("rating.chargeCode.addRow"),
            onClick: () => patch({ rows: [...current.rows, emptyRow(ALL_SIZES, "")] }),
            blockedReason: classes.every((code) => usedClasses.has(code)) ? t("rating.chargeCode.everyClassUsed") : undefined,
          },
        ]}
        columns={[
          number,
          {
            key: "class",
            label: t("rating.chargeCode.col.customerClass"),
            cell: (row, index) => (
              <CellSelect
                name={`class-${index}`}
                label={t("rating.chargeCode.col.customerClass")}
                value={row.customerClass ?? ""}
                placeholder={t("rating.chargeCode.choose")}
                options={classes
                  .filter((code) => code === row.customerClass || !usedClasses.has(code))
                  .map((code) => ({ value: code, label: className(code) }))}
                onChange={(customerClass) => setRow(index, { customerClass })}
              />
            ),
          },
          { key: "percent", label: t("rating.chargeCode.col.percent"), numeric: true, cell: (row, index) => moneyCell(row, index, "percent", t("rating.chargeCode.col.percent")) },
          { key: "minimum", label: t("rating.chargeCode.col.minimum"), numeric: true, cell: (row, index) => moneyCell(row, index, "minimum", t("rating.chargeCode.col.minimum")) },
        ]}
      />
    );
  } else if (isPercentPenalty(current)) {
    pricingTable = (
      <TableArray<PriceDraftRow>
        collection="charge-price-rows"
        title={t("rating.chargeCode.prices")}
        fact={fact}
        rows={current.rows.slice(0, 1)}
        rowKey={(_row, index) => `penalty-${index}`}
        emptyText={t("rating.chargeCode.noPrices")}
        removeLabel={t("rating.chargeCode.removeRow")}
        rowRemoveBlocked={() => t("rating.chargeCode.oneRow")}
        onChange={(rows) => patch({ rows })}
        columns={[
          number,
          { key: "class", label: t("rating.chargeCode.col.customerClass"), cell: () => <CellStatic name="class">{t("rating.chargeCode.everyClass")}</CellStatic> },
          { key: "percent", label: t("rating.chargeCode.col.percent"), numeric: true, cell: (row, index) => moneyCell(row, index, "percent", t("rating.chargeCode.col.percent")) },
          { key: "minimum", label: t("rating.chargeCode.col.minimum"), numeric: true, cell: (row, index) => moneyCell(row, index, "minimum", t("rating.chargeCode.col.minimum")) },
        ]}
      />
    );
  } else if (current.pricedBy === "class") {
    pricingTable = (
      <TableArray<PriceDraftRow>
        collection="charge-price-rows"
        title={t("rating.chargeCode.prices")}
        fact={fact}
        rows={current.rows}
        rowKey={(_row, index) => `class-${index}`}
        emptyText={t("rating.chargeCode.noPrices")}
        removeLabel={t("rating.chargeCode.removeRow")}
        onChange={(rows) => patch({ rows })}
        actions={[
          {
            key: "add-row",
            label: t("rating.chargeCode.addRow"),
            onClick: () => patch({ rows: [...current.rows, emptyRow(ALL_SIZES, "")] }),
            blockedReason: classes.every((code) => usedClasses.has(code)) ? t("rating.chargeCode.everyClassUsed") : undefined,
          },
        ]}
        columns={[
          number,
          {
            key: "class",
            label: t("rating.chargeCode.col.customerClass"),
            cell: (row, index) => (
              <CellSelect
                name={`class-${index}`}
                label={t("rating.chargeCode.col.customerClass")}
                value={row.customerClass ?? ""}
                placeholder={t("rating.chargeCode.choose")}
                options={classes
                  .filter((code) => code === row.customerClass || !usedClasses.has(code))
                  .map((code) => ({ value: code, label: className(code) }))}
                onChange={(customerClass) => setRow(index, { customerClass })}
              />
            ),
          },
          { key: "amount", label: t("rating.chargeCode.col.amount"), numeric: true, cell: (row, index) => moneyCell(row, index, "amount", t("rating.chargeCode.col.amount")) },
        ]}
      >
        {depositNote}
      </TableArray>
    );
  } else if (current.pricedBy === "size") {
    // + Add row adds an every-class row, so a size is spent when every class holds it.
    const offered = sizes.filter((size) => !isUsed(size.code, null));
    pricingTable = (
      <TableArray<PriceDraftRow>
        collection="charge-price-rows"
        title={t("rating.chargeCode.prices")}
        fact={fact}
        rows={current.rows}
        rowKey={(_row, index) => `size-${index}`}
        emptyText={t("rating.chargeCode.noPrices")}
        removeLabel={t("rating.chargeCode.removeRow")}
        onChange={(rows) => patch({ rows })}
        actions={[
          {
            key: "add-row",
            label: t("rating.chargeCode.addRow"),
            onClick: () => patch({ rows: [...current.rows, emptyRow()] }),
            blockedReason: offered.length === 0 ? t("rating.chargeCode.everySizeUsed") : undefined,
          },
        ]}
        footerTrailing={offered.length === 0 ? <span className="text-base text-neutral-700">{t("rating.chargeCode.everySizeUsed")}</span> : undefined}
        columns={[
          number,
          { key: "service", label: t("rating.chargeCode.col.service"), cell: () => <CellStatic name="service">{serviceWord}</CellStatic> },
          { key: "asset", label: t("rating.chargeCode.col.asset"), cell: () => <CellStatic name="asset">{asset ?? "—"}</CellStatic> },
          {
            key: "size",
            label: t("rating.chargeCode.col.size"),
            cell: (row, index) => (
              <CellSelect
                name={`size-${index}`}
                label={t("rating.chargeCode.col.size")}
                // The name is longer than the code it replaced (`Water 1½"`), so
                // the cell takes its widest option's width (DEF-CUS-9093).
                fit
                value={row.size}
                placeholder={t("rating.chargeCode.choose")}
                // DEF-RAT-8717 — SIZE order, and a size another row holds is not offered.
                options={sizes
                  .filter((size) => size.code === row.size || !isUsed(size.code, row.customerClass))
                  // DEF-RAT-9321 — the size's NAME (`Water 5/8"`), never its code.
                  .map((size) => ({ value: size.code, label: size.name }))}
                onChange={(size) => setRow(index, { size })}
              />
            ),
          },
          ...(sizedByClass
            ? [
                {
                  key: "class",
                  label: t("rating.chargeCode.col.customerClass"),
                  cell: (row: PriceDraftRow) => <CellStatic name="class">{className(row.customerClass)}</CellStatic>,
                },
              ]
            : []),
          { key: "amount", label: priceColumnLabel, numeric: true, cell: (row, index) => moneyCell(row, index, "amount", priceColumnLabel) },
          // DEF-RAT-8752 — image 51: a BASE size's minimum, read-only, from
          // the rate schedules on its service (never typed here).
          ...(current.kind === "base" && hasFloors(sizeMinimums)
            ? [
                {
                  key: "floor",
                  label: t("rating.chargeCode.col.minimum"),
                  numeric: true,
                  cell: (row: PriceDraftRow) => (
                    <CellStatic name="floor">{floorText(sizeMinimums, row.size) ?? "—"}</CellStatic>
                  ),
                },
              ]
            : []),
        ]}
      >
        {notPricedNote}
        {depositNote}
      </TableArray>
    );
  } else {
    const baseOne = current.kind === "base";
    pricingTable = (
      <TableArray<PriceDraftRow>
        collection="charge-price-rows"
        title={t("rating.chargeCode.prices")}
        fact={fact}
        rows={current.rows.slice(0, 1)}
        rowKey={() => "one"}
        emptyText={t("rating.chargeCode.noPrices")}
        removeLabel={t("rating.chargeCode.removeRow")}
        rowRemoveBlocked={() => t("rating.chargeCode.oneRow")}
        onChange={(rows) => patch({ rows })}
        columns={[
          number,
          ...(baseOne
            ? [
                { key: "service", label: t("rating.chargeCode.col.service"), cell: () => <CellStatic name="service">{serviceWord}</CellStatic> },
                // DEF-RAT-8836 — the service's asset, and the one amount is its *All sizes* row
                // (PO 2026-10-01, "Flat amount as an All sizes row"); sewer has no sizes and keeps "—".
                { key: "asset", label: t("rating.chargeCode.col.asset"), cell: () => <CellStatic name="asset">{asset ?? "—"}</CellStatic> },
                ...(asset === null
                  ? []
                  : [{ key: "size", label: t("rating.chargeCode.col.size"), cell: () => <CellStatic name="size">{t("rating.rs.allSizes")}</CellStatic> }]),
              ]
            : []),
          { key: "amount", label: priceColumnLabel, numeric: true, cell: (row: PriceDraftRow, index: number) => moneyCell(row, index, "amount", priceColumnLabel) },
        ]}
      >
        {/* Image 52 — a base on a service billed as a SHARE of another (sewer
            as a % of water) says where the share is set. Read off the
            service's own basis, never its name. */}
        {baseOne && services.find((row) => row.service === current.service)?.billing_basis === "share" ? (
          <ChargeNote tone="info" name="share">
            {t("rating.chargeCode.shareNote")}
          </ChargeNote>
        ) : null}
        {depositNote}
      </TableArray>
    );
  }
  const stepPricing = (
    <div className="flex flex-col gap-5" data-step="pricing">
      {pricingTable}
    </div>
  );

  // ── step 3 · Review ─────────────────────────────────────────────────────
  const yesNoWord = (value: boolean) => t(value ? "rating.yes" : "rating.no");
  const reviewFacts: Fact[] = [
    { id: "code", label: t("rating.chargeCode.field.code"), value: current.code || "—" },
    { id: "billLine", label: t("rating.chargeCode.field.billLine"), value: current.name || "—" },
    { id: "kind", label: t("rating.chargeCode.field.kind"), value: current.kind === "" ? "—" : t(`rating.chargeCode.kind.${current.kind}`) },
    { id: "type", label: t("rating.chargeCode.field.type"), value: typeWords(current.chargeType || null, translate) },
    { id: "service", label: t("rating.chargeCode.field.service"), value: serviceWord },
    { id: "pricedBy", label: t("rating.chargeCode.field.pricedBy"), value: pricedByText },
    { id: "partMonth", label: t("rating.chargeCode.field.partMonth"), value: t(current.kind === "base" ? "rating.chargeCode.partMonth.days" : "rating.chargeCode.partMonth.full") },
    { id: "charged", label: t("rating.chargeCode.field.charged"), value: t(chargedKey(current.chargeType)) },
    { id: "taxed", label: t("rating.chargeCode.field.taxed"), value: yesNoWord(current.taxable) },
    { id: "auto", label: t("rating.chargeCode.field.auto"), value: yesNoWord(current.autoApply) },
    { id: "waive", label: t("rating.chargeCode.field.waive"), value: yesNoWord(current.waivable) },
    { id: "ownLine", label: t("rating.chargeCode.field.ownLine"), value: yesNoWord(current.separateLine) },
    ...(current.chargeType === "one_time"
      ? [{ id: "applicationFee", label: t("rating.chargeCode.field.applicationFee"), value: yesNoWord(current.applicationFee) }]
      : []),
    ...(penalty ? [{ id: "nsfFee", label: t("rating.chargeCode.field.nsfFee"), value: yesNoWord(current.nsfFee) }] : []),
    ...(penalty ? [{ id: "grace", label: t("rating.chargeCode.field.grace"), value: graceText(translate, grace.days, grace.mode) }] : []),
  ];
  const fig =(value: string) => (value.trim() === "" ? null : dollars(value.trim()));
  let reviewPrices: ReactNode;
  if (current.pricedBy === "entered") {
    const fallback = current.rows[0]?.amount.trim() ?? "";
    reviewPrices = (
      <Panel as="section" title={t("rating.chargeCode.prices")}>
        <div className="flex flex-col gap-4">
          <ChargeNote tone="info" name="entered">
            {t("rating.chargeCode.enteredNote")}
          </ChargeNote>
          {/* DEF-RAT-9807 — the default read back, or that there is none. */}
          <FactBlock
            name="default-amount"
            columns={4}
            facts={[
              {
                id: "defaultAmount",
                label: t("rating.chargeCode.field.defaultAmount"),
                value: fallback === "" ? t("rating.chargeCode.noDefault") : (fig(fallback) ?? "—"),
              },
            ]}
          />
        </div>
      </Panel>
    );
  } else if (current.chargeType === "penalty" && current.pricedBy === "class") {
    // DEF-RAT-8753 — image 67: one row per class, its percent and minimum.
    reviewPrices = (
      <PricesReadTable
        t={translate}
        columns={["customerClass", "percent", "minimum"]}
        amountLabel={t("rating.chargeCode.col.amount")}
        rows={current.rows
          .filter((row) => row.customerClass)
          .map((row, index) => ({
            key: `${row.customerClass ?? ""}|${index}`,
            customerClass: className(row.customerClass),
            percent: row.percent.trim() === "" ? null : `${row.percent.trim()}%`,
            minimum: fig(row.minimum),
          }))}
      />
    );
  } else if (isPercentPenalty(current)) {
    const row = current.rows[0] ?? emptyRow(ALL_SIZES);
    reviewPrices = (
      <PricesReadTable
        t={translate}
        columns={["customerClass", "percent", "minimum"]}
        amountLabel={t("rating.chargeCode.col.amount")}
        rows={[{ key: "every", customerClass: t("rating.chargeCode.everyClass"), percent: row.percent.trim() === "" ? null : `${row.percent.trim()}%`, minimum: fig(row.minimum) }]}
      />
    );
  } else {
    const readRows: PriceReadRow[] = current.rows
      .filter((row) => current.pricedBy !== "size" || row.size !== "")
      .map((row, index) => ({
        key: `${row.size}|${row.customerClass ?? ""}|${index}`,
        service: serviceWord,
        asset: current.pricedBy === "size" || current.kind === "base" ? (asset ?? "—") : "—",
        size: row.size === ALL_SIZES ? t("rating.rs.allSizes") : sizeLabel(row.size, entries),
        customerClass: className(row.customerClass),
        amount: fig(row.amount),
      }));
    const columns: ("service" | "asset" | "size" | "customerClass" | "amount")[] =
      current.pricedBy === "size"
        ? sizedByClass
          ? ["service", "asset", "size", "customerClass", "amount"]
          : ["service", "asset", "size", "amount"]
        : current.pricedBy === "class"
          ? ["customerClass", "amount"]
          : current.kind === "base"
            ? asset === null
              ? ["service", "asset", "amount"]
              : ["service", "asset", "size", "amount"]
            : ["amount"];
    reviewPrices = (
      <PricesReadTable t={translate} columns={columns} amountLabel={priceColumnLabel} rows={readRows}>
        {notPricedNote}
        {depositNote}
      </PricesReadTable>
    );
  }
  const changes =
    original === null
      ? []
      : draftChanges(original, current, {
          field: (key) => t(`rating.chargeCode.field.${key}`),
          yesNo: yesNoWord,
          type: (value) => typeWords(value || null, translate),
          money: (value) => dollars(value) ?? value,
          notPriced: t("rating.chargeCode.notPriced"),
          priceItem: (row) =>
            `${row.size === ALL_SIZES ? t("rating.chargeCode.col.amount") : sizeLabel(row.size, entries)} · ${className(row.customerClass)}`,
          // DEF-RAT-9209 — a scope change, in class names.
          classes: (codes) => (codes.length === 0 ? t("rating.chargeCode.allClasses") : codes.map(className).join(", ")),
          grace: (days, mode) => graceText(translate, days, mode),
        }, graceDefault);
  // DEF-RAT-9104: on Edit, before a new date is typed, the summary reads the
  // price in force today (its own window), never "— · no end". A price
  // backfilled from 2000-01-01 is not a date anyone set (2.433.4), so it is
  // not shown; the typed date replaces all of this the moment it exists.
  const inForce =
    editing && current.effectiveFrom === ""
      ? (stored?.versions ?? []).find(
          (version) => version.state === "in_force" && version.effective_from !== PRICE_HISTORY_EPOCH,
        )
      : undefined;
  const effectiveText =
    inForce !== undefined
      ? inForce.effective_to === null
        ? t("rating.chargeCode.aside.from", { from: day(inForce.effective_from) })
        : rangeText(day(inForce.effective_from), day(inForce.effective_to))
      : current.effectiveTo === ""
        ? t("rating.chargeCode.aside.from", { from: day(current.effectiveFrom) })
        : rangeText(day(current.effectiveFrom), day(current.effectiveTo));
  const stepReview = (
    <div className="flex flex-col gap-5" data-step="review">
      <FactsPanel title={t("rating.chargeCode.charge")} name="review-charge" facts={reviewFacts} />
      {reviewPrices}
      {editing && (
        <TableArray<{ item: string; now: string | null; next: string | null }>
          readOnly
          collection="charge-changes"
          title={t("rating.chargeCode.whatChanges")}
          fact={
            <span className="font-heading text-xs font-semibold uppercase tracking-kicker">
              {t("rating.chargeCode.changesCount", { count: changes.length })}
            </span>
          }
          columns={[
            { key: "item", label: t("rating.chargeCode.col.item"), cell: (row) => row.item },
            { key: "now", label: t("rating.chargeCode.col.now"), cell: (row) => row.now ?? "—" },
            {
              key: "next",
              label: t("rating.chargeCode.col.new"),
              cell: (row) => <strong className="text-danger-700">{row.next ?? t("rating.chargeCode.removed")}</strong>,
            },
          ]}
          rows={changes}
          rowKey={(row, index) => `${row.item}-${index}`}
          emptyText={t("rating.chargeCode.noChanges")}
        />
      )}
      <Panel as="section" title={t(editing ? "rating.chargeCode.whenAndWhy" : "rating.chargeCode.when")}>
        <div className="grid grid-cols-2 gap-x-4 gap-y-4">
          <DatePickerField
            id="cc-effective-from"
            label={t("rating.chargeCode.field.effectiveFrom")}
            value={current.effectiveFrom}
            onChange={(effectiveFrom) => {
              setErrors((was) => ({ ...was, effective_from: "" }));
              patch({ effectiveFrom });
            }}
            dateFormat={dateFormat}
            required
            help={t("rating.chargeCode.fromHelp")}
            error={errors.effective_from || undefined}
          />
          <DatePickerField
            id="cc-effective-to"
            label={t("rating.chargeCode.field.effectiveTo")}
            value={current.effectiveTo}
            onChange={(effectiveTo) => patch({ effectiveTo })}
            dateFormat={dateFormat}
            min={current.effectiveFrom === "" ? undefined : current.effectiveFrom}
            help={t("rating.chargeCode.toHelp")}
            error={errors.effective_to || undefined}
          />
        </div>
        {editing && (
          <div className="mt-4">
            <TextField
              id="cc-reason"
              label={t("rating.chargeCode.field.reason")}
              value={current.reason}
              onChange={(reason) => {
                setErrors((was) => ({ ...was, reason: "" }));
                patch({ reason });
              }}
              required
              multiline
              placeholder={t("rating.chargeCode.reasonPlaceholder")}
              error={errors.reason || undefined}
            />
            <ChargeNote tone="info" name="sent-bills">
              {t("rating.chargeCode.sentBills")}
            </ChargeNote>
          </div>
        )}
      </Panel>
      {saved !== null && (
        <ChargeNote
          tone="success"
          name="saved"
          lead={t(editing ? "rating.chargeCode.savedLead" : "rating.chargeCode.createdLead", { code: saved.code })}
        >
          {current.effectiveTo === ""
            ? t("rating.chargeCode.savedFrom", { from: day(current.effectiveFrom) })
            : t("rating.chargeCode.savedWindow", { from: day(current.effectiveFrom), to: day(current.effectiveTo) })}
        </ChargeNote>
      )}
    </div>
  );

  /** Client-side checks the drawing shows BEFORE the server is asked. */
  function reviewProblems(): Record<string, string> {
    const found: Record<string, string> = {};
    if (current.effectiveFrom === "") found.effective_from = t("rating.chargeCode.pickDate");
    if (editing && current.reason.trim() === "") found.reason = t("rating.chargeCode.addReason");
    return found;
  }

  async function submit(): Promise<WizardCommitOutcome> {
    setRefusal(null);
    const problems = reviewProblems();
    setErrors(problems);
    if (Object.keys(problems).length > 0) {
      // ROUTED to this step: the field says why, and the footer stays as drawn
      // (image 71) instead of being replaced by the failure card.
      return { ok: false, reason: Object.values(problems)[0], refusedOnStep: 3 };
    }
    try {
      const row = await commit.mutateAsync(chargePayload(current, editing, graceDefault));
      setSaved(row);
      void queryClient.invalidateQueries({ queryKey: ["charges"] });
      return { ok: true };
    } catch (error) {
      const rendered = refusalOf(error, translate);
      setRefusal(rendered);
      if (isApiError(error)) {
        const mapped: Record<string, string> = {};
        for (const fieldError of error.fieldErrors) {
          if (fieldError.field !== null) {
            mapped[fieldError.field] =
              fieldError.field === "effective_from" && fieldError.message_key === "rating.required"
                ? t("rating.chargeCode.pickDate")
                : t(fieldError.message_key, refusalParams(fieldError.params, error.traceId));
          }
        }
        setErrors(mapped);
        const onThisStep = ["effective_from", "effective_to", "reason"];
        if (Object.keys(mapped).some((key) => onThisStep.includes(key))) {
          return { ok: false, reason: rendered.message, refusedOnStep: 3 };
        }
      }
      return { ok: false, reason: rendered.message };
    }
  }

  const detailsReady =
    current.kind !== "" &&
    current.chargeId !== "" &&
    current.name.trim() !== "" &&
    (current.kind !== "base" || current.service !== "") &&
    graceProblem === null;
  const pricingProblem = (): string | true => {
    if (current.pricedBy === "entered") {
      // DEF-RAT-9807 — the optional default is checked only when typed.
      const fallback = current.rows[0]?.amount.trim() ?? "";
      return fallback === "" || isDecimalShape(fallback) ? true : t("rating.error.notDecimal");
    }
    for (const row of current.rows) {
      for (const value of [row.amount, row.percent, row.minimum]) {
        if (value.trim() !== "" && !isDecimalShape(value)) return t("rating.error.notDecimal");
      }
    }
    if (current.pricedBy === "size" && current.rows.some((row) => row.size === "")) return t("rating.chargeCode.pickSize");
    // DEF-RAT-9322 — one size twice for the same class is refused here, by name.
    const twice = current.pricedBy === "size" ? sizeListedTwice(current.rows) : null;
    if (twice !== null) return t("rating.chargeCode.sizeTwice", { size: sizeLabel(twice.size, entries) });
    if (current.pricedBy === "class" && current.rows.some((row) => !row.customerClass)) return t("rating.chargeCode.pickClass");
    // DEF-BIL-10201 — a percent penalty at 0% with no minimum charges nothing
    // on every bill; the server refuses it by the same sentence.
    if (isPercentPenalty(current) && current.pricedBy !== "class" && penaltyChargesNothing(current.rows[0])) {
      return t("rating.charges.penalty_needs_percent_or_minimum");
    }
    return true;
  };

  const steps: WizardStep[] = [
    {
      id: CHARGE_WIZARD_STEPS[0],
      label: t("rating.chargeCode.step.details"),
      content: stepDetails,
      continueDisabled: !detailsReady,
      validate: () => detailsReady,
    },
    { id: CHARGE_WIZARD_STEPS[1], label: t("rating.chargeCode.step.pricing"), content: stepPricing, validate: pricingProblem },
    { id: CHARGE_WIZARD_STEPS[2], label: t("rating.chargeCode.step.review"), content: stepReview },
  ];

  const status: AsideStatus | null =
    current.pricedBy === "entered"
      ? { kind: "entered" }
      : counted.cells === 0
        ? null
        : counted.priced < counted.cells
          ? { kind: "missing", count: counted.cells - counted.priced }
          : { kind: "all" };

  return (
    <div className="flex flex-col gap-5 pt-6 px-4 pb-8" data-screen="CHG-02" data-charge-mode={editing ? "edit" : "add"}>
      <PageHeader
        backTo={
          editing && stored !== null
            ? { to: tenantPath(definitionPath("charge", stored.id)), label: t("rating.chargeCode.crumbCode", { code: stored.code }) }
            : { to: tenantPath(CHARGE_LIST_ROUTE), label: t("rating.chargeCode.crumb") }
        }
        title={editing ? t("rating.chargeCode.editTitle", { code: stored?.code ?? "" }) : t("rating.chargeCode.newTitle")}
      />
      <RefusalNotice refusal={refusal} />
      <div className={LAYOUT} data-charge-layout="">
        <WizardFrame
          steps={steps}
          nav={nav}
          onNavChange={setNav}
          // DEF-RAT-9104: NO `backAtStart` — beside `cancel` it gave the row two
          // `mr-auto` items and floated `Back` mid-row (DEF-RAT-8824's cause).
          doneMark="tick"
          commitLabel={t(editing ? "rating.chargeCode.saveChange" : "rating.chargeCode.create")}
          commitDisabled={saved !== null}
          commitFailedTitle={t("rating.chargeWizard.saveFailed")}
          onCommit={submit}
          onCommitted={() => undefined}
          cancel={{ label: t("rating.plan.cancel"), onCancel: () => navigate(tenantPath(CHARGE_LIST_ROUTE)) }}
          secondaryActions={
            nav.step === 3 ? (
              <GuardedButton readOnly readOnlyReason={t("rating.chargeWizard.saveDraftReason")} onClick={() => undefined}>
                {t("rating.rate.saveDraft")}
              </GuardedButton>
            ) : undefined
          }
        />
        <div className="col-start-2 row-start-2 self-start sticky top-4">
          <ChargeSummaryAside
            editing={editing}
            code={current.code}
            billLine={current.name}
            kind={current.kind === "" ? "" : t(`rating.chargeCode.kind.${current.kind}`)}
            service={current.kind === "" ? "" : serviceWord}
            gl={codeRow === null ? "—" : <GlValue code={codeRow.gl_account_code} name={codeRow.gl_account_name} t={translate} />}
            effective={effectiveText}
            pricedBy={current.kind === "" ? "—" : pricedByText}
            rows={current.pricedBy === "entered" ? "—" : String(counted.rows)}
            priced={current.pricedBy === "entered" ? null : t("rating.chargeCode.ofCount", { n: counted.priced, total: counted.cells })}
            status={status}
            saved={saved !== null}
            t={translate}
          />
        </div>
      </div>
    </div>
  );
}
