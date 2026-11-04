// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — step 1, *Job & location*:
//           image 14 (on units), image 15 (an asset type chosen), image 19
//           (from an account), image 20 (from an asset).
// Rulings:  19 (one job per unit ticked) · 20 (an asset type chosen means the
//           asset must be chosen) · 21 (the premises is a dropdown you type
//           into — BR-SHL-033) · 22 (the assets list has its own search) ·
//           35 (from an account or an asset the form arrives filled).
// Defects:  DEF-WRK-9572 (free-text premises and type) · DEF-WRK-9582 (job
//           type one flat list).
// Rules:    B14 rules 8 (5+ options searchable), 10 (the asterisk on the
//           label), 21, 31, 33, 39 (label → input → helper), 43, 44.
// Tests:    src/features/work/raise/cr168Raise.dom.test.tsx
// ───────────────────────────────────────────────────────
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getLookupEntries, getPremisesTypes } from "@/api/endpoints";
import type { UnitRow } from "@/api/endpoints";
import { CustomFieldsInput } from "@/components/CustomFields";
import { FieldErrorsScope, SelectField, TextField } from "@/components/FormModal";
import { ChipRow, ChipToggle } from "@/components/Chip";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { formatDate } from "@/components/DateCell";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";
import type { PageSize } from "@/components/tableTypes";
import { searchPremisesPicker } from "@/features/customers/serviceRequestEndpoints";
import type { PremisesPickerRow } from "@/features/customers/serviceRequestEndpoints";

import { WORK_TEMPLATE_NEW_ROUTE } from "../TemplateBuilder";
import { getRaiseOptions, getTemplate, listTemplatesForAsset } from "../workEndpoints";
import type { RaiseOptions } from "../workEndpoints";

import { RaisePickTable } from "./RaisePickTable";
import { listRaiseAssets, listRaiseTemplates, listRaiseUnits, listUnitTypeOptions } from "./raiseEndpoints";
import type { RaiseAssetRow } from "./raiseEndpoints";
import type { RaiseForm, RaiseUpdate } from "./raiseForm";
import { chooseOneUnits, jobCount, jobTypeChoices, useDebouncedTerm } from "./raiseModel";
import type { ChosenAsset, RaiseOrigin } from "./raiseModel";

/** What the origin already decided (ruling 35). `null` = the clerk chooses. */
export interface RaiseFixed {
  premisesId: string | null;
  /** The account's unit — the units table is not drawn (image 19). */
  unitIds: string[] | null;
  /** The asset itself — neither asset type nor assets is drawn (image 20). */
  asset: { id: string; assetNo: string; assetTypeId: string | null } | null;
  /** The account's unit, named — the subject of a one-job raise on it. */
  unitLabel: string | null;
}

/** The step-1 refusals, each drawn under its own field after a Continue. */
export interface RaiseJobErrors {
  premises?: string;
  units?: string;
  type?: string;
  template?: string;
  assets?: string;
  /** A required own field left empty, named (CR-161 W4). */
  custom?: string;
}

function premisesLine(row: PremisesPickerRow): string {
  return [row.address_line, row.city].filter((part) => part !== null && part !== "").join(" · ");
}

export function RaiseJobStep(props: {
  origin: RaiseOrigin;
  fixed: RaiseFixed;
  form: RaiseForm;
  update: RaiseUpdate;
  errors: RaiseJobErrors;
  /** A refused own field, marked on its own control. */
  customErrors?: Record<string, string>;
  /** The *From the account* / *From the asset* panel, drawn first. */
  originPanel?: ReactNode;
  client?: ApiClient;
}) {
  const client = props.client ?? api;
  const { t } = useTranslation();
  const { form, update } = props;
  const { timeZone, dateFormat } = useRegional({});
  const readDate = (iso: string) => formatDate(iso, timeZone, dateFormat);

  const options = useQuery({
    queryKey: ["work", "raise-options"],
    queryFn: () => getRaiseOptions(client),
  });

  // ── Premises (ruling 21) ────────────────────────────────────────────────
  const typed = form.premisesTerm.trim();
  const term = useDebouncedTerm(typed);
  const premisesSearch = useQuery({
    queryKey: ["work", "raise", "premises", term],
    queryFn: () => searchPremisesPicker(term, client),
    enabled: props.fixed.premisesId === null && term.length >= 2 && form.premisesId === "",
  });
  const premisesTypes = useQuery({
    queryKey: ["premises", "types"],
    queryFn: () => getPremisesTypes(client),
    enabled: props.fixed.premisesId === null,
  });
  const typeName = (code: string | null | undefined): string =>
    (premisesTypes.data ?? []).find((row) => row.code === code)?.name ?? "";
  const unitsWord = (count: number): string =>
    count === 0 ? t("work.raise.noUnits") : t("work.raise.unitCount", { count });
  const premisesFact = (row: PremisesPickerRow): string =>
    [typeName(row.premises_type), unitsWord(row.units.length)].filter((s) => s !== "").join(" · ");

  const premisesRows = premisesSearch.data?.results ?? [];
  const premisesOptions = form.premisesId !== ""
    ? [{ value: form.premisesId, label: form.premisesLabel }]
    : premisesRows.map((row) => ({ value: row.id, label: premisesLine(row), aside: premisesFact(row) }));

  // ── Units (ruling 19) ───────────────────────────────────────────────────
  const premisesId = props.fixed.premisesId ?? form.premisesId;
  const [unitQ, setUnitQ] = useState("");
  const unitTerm = useDebouncedTerm(unitQ);
  const [unitType, setUnitType] = useState("");
  const unitTypes = useQuery({
    queryKey: ["units", "unit-types"],
    queryFn: () => listUnitTypeOptions(client),
    enabled: props.fixed.unitIds === null,
  });
  // A common area is not a unit a clerk raises a job "for a flat" on, and the
  // add-units picker leaves it out for the same reason (`unitTypeChoices`).
  const unitTypeChips = (unitTypes.data?.results ?? []).filter((row) => row.code !== "common_area");
  const [unitPage, setUnitPage] = useState(1);
  const [unitPer, setUnitPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  const units = useQuery({
    queryKey: ["work", "raise", "units", premisesId, unitTerm, unitType, unitPage, unitPer],
    queryFn: () =>
      listRaiseUnits({ premisesId, q: unitTerm, unitType, page: unitPage, per: unitPer }, client),
    enabled: premisesId !== "" && props.fixed.unitIds === null,
  });
  const unitRows = (units.data?.results ?? []).map((row) => ({ ...row, name: row.label ?? row.unit_no ?? "" }));
  const unitTotal = units.data?.count ?? 0;
  // A building of exactly one unit has one answer — it arrives ticked.
  useEffect(() => {
    if (units.data !== undefined && units.data.count === 1 && unitQ === "" && unitType === "" && form.units.length === 0) {
      const only = units.data.results[0];
      update({ units: [{ id: only.id, label: only.label ?? only.unit_no ?? "" }] });
    }
  }, [units.data, unitQ, unitType, form.units.length, update]);
  const chosenUnitIds = new Set(form.units.map((unit) => unit.id));
  const unitIds = props.fixed.unitIds ?? form.units.map((unit) => unit.id);

  // ── Job type (DEF-WRK-9582) and template ────────────────────────────────
  const raiseOptions: RaiseOptions | undefined = options.data;
  const choices = useMemo(() => jobTypeChoices(raiseOptions?.types ?? []), [raiseOptions]);
  const assetDoor = props.fixed.asset;
  const templates = useQuery({
    queryKey: ["work", "raise", "templates", form.typeId],
    queryFn: () => listRaiseTemplates({ jobTypeId: form.typeId }, client),
    enabled: assetDoor === null && form.typeId !== "",
  });
  const assetTemplates = useQuery({
    queryKey: ["work", "raise", "asset-templates", assetDoor?.id ?? ""],
    queryFn: () => listTemplatesForAsset(assetDoor?.id ?? "", client),
    enabled: assetDoor !== null,
  });
  const templateOptions = assetDoor !== null
    ? // The house envelope's `results` — SRV-2's one-round `rows` twin is NOT
      // read, so it can go (told to the coordinator).
      ((assetTemplates.data as { results?: { id: string; name: string }[] } | undefined)?.results ?? []).map(
        (row) => ({ value: row.id, label: row.name }),
      )
    : (templates.data?.results ?? [])
        // Published only (`BR-WRK-011`: version 0 IS the draft) — the courtesy;
        // the server's refusal of a draft is the rule.
        .filter((row) => (row.version ?? 0) >= 1)
        .map((row) => ({ value: row.id, label: `${row.name} · v${row.version}` }));

  const noneFitsAsset = assetDoor !== null && assetTemplates.isSuccess && templateOptions.length === 0;
  const tenantPath = useTenantPath();

  // ── Asset type, set by the template where it names one ──────────────────
  const templateDetail = useQuery({
    queryKey: ["work", "templates", "detail", form.templateId],
    queryFn: () => getTemplate(form.templateId, client),
    enabled: assetDoor === null && form.templateId !== "",
  });
  const assetTypes = useQuery({
    queryKey: ["lookups", "asset_types", "raise"],
    queryFn: () => getLookupEntries("asset_types", { per: 200 }, client),
    enabled: assetDoor === null,
  });
  const templateTypeIds = (templateDetail.data?.bundle?.asset_types ?? []).map((row) => row.asset_type_id);
  const setByTemplate = templateTypeIds.length > 0;
  useEffect(() => {
    if (setByTemplate && !templateTypeIds.includes(form.assetTypeId)) {
      update({ assetTypeId: templateTypeIds[0], assets: [], assetUnitKeys: [] });
    }
    // `templateTypeIds` is derived each render; its first id is the dependency.
  }, [setByTemplate, templateTypeIds[0], form.assetTypeId, update]); // eslint-disable-line react-hooks/exhaustive-deps
  const assetTypeRows = (assetTypes.data?.results ?? []).filter(
    (row) => !setByTemplate || templateTypeIds.includes(row.id),
  );
  const assetTypeName = (assetTypes.data?.results ?? []).find((row) => row.id === form.assetTypeId)?.name ?? "";

  // ── Assets on the ticked units (rulings 20, 22) ─────────────────────────
  const [assetQ, setAssetQ] = useState("");
  const assetTerm = useDebouncedTerm(assetQ);
  const [assetPage, setAssetPage] = useState(1);
  const [assetPer, setAssetPer] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  const showAssets = assetDoor === null && form.assetTypeId !== "" && unitIds.length > 0;
  // A water template's job is on a WATER meter: two meters on one flat are
  // one electric and one water, and only one of them is this job's (P2.11).
  const templateService =
    (templates.data?.results ?? []).find((row) => row.id === form.templateId)?.service?.code ?? undefined;
  const assets = useQuery({
    queryKey: ["work", "raise", "assets", unitIds.join(","), form.assetTypeId, templateService, assetTerm, assetPage, assetPer],
    queryFn: () =>
      listRaiseAssets(
        { unitIds, assetType: form.assetTypeId, service: templateService, q: assetTerm, page: assetPage, per: assetPer },
        client,
      ),
    enabled: showAssets,
  });
  const unitKeyOf = (row: RaiseAssetRow): string => row.unit?.id ?? row.unit?.label ?? "";
  const assetRows = (assets.data?.results ?? []).map((row) => ({ ...row, name: row.asset_no }));
  // SRV-2 says whether another asset of the type stands on the same unit
  // (`shares_unit`) across EVERY page; counting the page in hand would miss a
  // second meter on page 2. The page count stays the fallback for a row that
  // predates the field.
  const seen = assetRows.map((row) => ({ id: row.id, unitKey: unitKeyOf(row) }));
  const pageChooseOne = chooseOneUnits(seen, form.assets);
  const coveredUnits = new Set(form.assets.map((row) => row.unitKey));
  const chooseOne = new Set(
    assetRows
      .filter((row) => (row.shares_unit === undefined ? pageChooseOne.has(unitKeyOf(row)) : row.shares_unit))
      .map((row) => unitKeyOf(row))
      .filter((key) => !coveredUnits.has(key)),
  );
  const chosenAssetIds = new Set(form.assets.map((row) => row.id));
  const toChosenAsset = (row: RaiseAssetRow): ChosenAsset => ({
    id: row.id,
    assetNo: row.asset_no,
    unitKey: unitKeyOf(row),
    unitLabel: row.unit?.label ?? "",
    where: row.location ?? null,
    lastRead: lastReadText(row, readDate),
  });

  // Ruling 20's memory: every unit on which an asset of the type was READ, so
  // a ticked unit with one left unchosen is named on Continue.
  const readKeys = assetRows.map((row) => unitKeyOf(row)).filter((key) => key !== "");
  const readKeysJoined = [...new Set(readKeys)].sort().join("|");
  useEffect(() => {
    if (readKeysJoined === "") return;
    const merged = [...new Set([...form.assetUnitKeys, ...readKeysJoined.split("|")])];
    if (merged.length !== form.assetUnitKeys.length) update({ assetUnitKeys: merged });
  }, [readKeysJoined, form.assetUnitKeys, update]);

  // The words of the three choices, carried to the Confirm summary.
  const typeLabel = (raiseOptions?.types ?? []).find((row) => row.id === form.typeId)?.name ?? "";
  const templateLabel = templateOptions.find((row) => row.value === form.templateId)?.label ?? "";
  useEffect(() => {
    const patch: Partial<RaiseForm> = {};
    if (typeLabel !== form.typeLabel) patch.typeLabel = typeLabel;
    if (templateLabel !== "" && templateLabel !== form.templateLabel) patch.templateLabel = templateLabel;
    if (assetTypeName !== form.assetTypeLabel) patch.assetTypeLabel = assetTypeName;
    if (Object.keys(patch).length > 0) update(patch);
  }, [typeLabel, templateLabel, assetTypeName, form.typeLabel, form.templateLabel, form.assetTypeLabel, update]);

  // ── The priority, defaulted from the job type ───────────────────────────
  useEffect(() => {
    if (raiseOptions === undefined || form.priorityId !== "") return;
    const fromType = raiseOptions.types.find((row) => row.id === form.typeId)?.default_priority_id ?? null;
    const normal = raiseOptions.priorities.find((row) => row.code === "NORMAL")?.id ?? null;
    const first = raiseOptions.priorities[0]?.id ?? "";
    update({ priorityId: fromType ?? normal ?? first });
  }, [raiseOptions, form.typeId, form.priorityId, update]);

  // ── The line under the form: what one press raises ──────────────────────
  const assetChosen = assetDoor !== null || form.assetTypeId !== "";
  const count = assetDoor !== null ? 1 : jobCount(assetChosen, unitIds.length, form.assets.length);
  const singleSubject =
    assetDoor !== null
      ? assetDoor.assetNo
      : assetChosen
        ? (form.assets[0]?.assetNo ?? "")
        : (form.units[0]?.label ?? props.fixed.unitLabel ?? "");
  const summary =
    count === 1 && singleSubject !== ""
      ? t("work.raise.summaryOne", { subject: singleSubject })
      : assetChosen
        ? t("work.raise.summaryAssets", { count })
        : t("work.raise.summaryUnits", { count });

  const occupancyPill = (row: UnitRow) => (
    <StatusPill tone={row.occupancy === "occupied" ? "success" : "neutral"}>
      {row.occupancy === "occupied" ? t("work.raise.occupied") : t("work.raise.vacant")}
    </StatusPill>
  );
  const servicesText = (codes: readonly string[] | null) =>
    (codes ?? []).map((code) => t(`work.orders.service.${code}`)).join(" · ");

  return (
    <div className="flex flex-col gap-4" data-raise-step="job">
      {props.originPanel}

      {props.fixed.premisesId === null && (
        <RemoteSearchSelectField
          id="raise-premises"
          label={t("work.raise.premises")}
          required
          term={form.premisesId !== "" ? form.premisesLabel : form.premisesTerm}
          onTermChange={(value) => update({ premisesTerm: value })}
          status={{
            idle: typed.length < 2,
            searching: premisesSearch.isFetching || (typed !== term && typed.length >= 2),
            searched: premisesSearch.isSuccess,
            failed: premisesSearch.isError,
          }}
          options={premisesOptions}
          value={form.premisesId}
          onChange={(value) => {
            if (value === "") {
              update({ premisesId: "", premisesLabel: "", premisesDetail: "", units: [], assets: [] });
              return;
            }
            const row = premisesRows.find((candidate) => candidate.id === value);
            if (row === undefined) return;
            setUnitPage(1);
            update({
              premisesId: row.id,
              premisesLabel: premisesLine(row),
              premisesDetail: premisesFact(row),
              premisesTerm: "",
              units: [],
              assets: [],
            });
          }}
          words={{
            tooShort: t("work.raise.premisesSearch.tooShort"),
            searching: t("work.raise.premisesSearch.searching"),
            failed: t("work.raise.premisesSearch.failed"),
            noMatch: t("work.raise.premisesSearch.noMatch"),
          }}
          placeholder={t("work.raise.premisesPlaceholder")}
          help={form.premisesDetail !== "" ? form.premisesDetail : undefined}
          error={props.errors.premises}
        />
      )}

      {props.fixed.unitIds === null && premisesId !== "" && (
        <RaisePickTable
          title={t("work.raise.units")}
          collection="raise-units"
          rows={unitRows}
          total={unitTotal}
          chosen={chosenUnitIds}
          onToggle={(rows, ticked) => {
            const ids = new Set(rows.map((row) => row.id));
            update({
              units: ticked
                ? [...form.units, ...rows.map((row) => ({ id: row.id, label: row.name }))]
                : form.units.filter((unit) => !ids.has(unit.id)),
              assets: ticked ? form.assets : form.assets.filter((asset) => !ids.has(asset.unitKey)),
            });
          }}
          columns={[
            { key: "unit", label: t("work.raise.col.unit"), cell: (row) => <span className="font-semibold">{row.name}</span> },
            {
              key: "type",
              label: t("work.raise.col.type"),
              // The tenant's own word for the type, never its code (B14 rule 31's
              // spirit — `residential_submetered` is a key, not a word).
              cell: (row) =>
                (unitTypes.data?.results ?? []).find((option) => option.code === row.unit_type)?.name ?? "",
            },
            { key: "status", label: t("work.raise.col.status"), cell: occupancyPill },
            { key: "services", label: t("work.raise.col.services"), cell: (row) => servicesText(row.services) },
          ]}
          chips={
            unitTypeChips.length === 0 ? undefined : (
              <ChipRow data-raise-unit-types="">
                <ChipToggle selected={unitType === ""} onClick={() => { setUnitType(""); setUnitPage(1); }}>
                  {t("work.raise.allUnits")}
                </ChipToggle>
                {unitTypeChips.map((row) => (
                  <ChipToggle
                    key={row.code}
                    selected={unitType === row.code}
                    onClick={() => {
                      setUnitType(row.code);
                      setUnitPage(1);
                    }}
                  >
                    {row.name}
                  </ChipToggle>
                ))}
              </ChipRow>
            )
          }
          search={{
            label: t("work.raise.unitsSearchLabel"),
            placeholder: t("work.raise.unitsSearch"),
            value: unitQ,
            onChange: (value) => {
              setUnitQ(value);
              setUnitPage(1);
            },
          }}
          chosenFact={t("work.raise.chosen", { n: form.units.length, total: unitTotal })}
          tickLabel={(row) => t("work.raise.tick", { unit: row.name })}
          tickAllLabel={t("work.raise.tickAll")}
          emptyText={units.isPending ? t("work.raise.loading") : t("work.raise.unitsEmpty")}
          note={t("work.raise.unitsNote")}
          error={props.errors.units}
          page={unitPage}
          per={unitPer}
          onPage={setUnitPage}
          onPer={(per) => {
            setUnitPer(per);
            setUnitPage(1);
          }}
        />
      )}

      <SelectField
        id="raise-type"
        label={t("work.raise.type")}
        required
        value={form.typeId}
        onChange={(value) => update({ typeId: value, templateId: "", priorityId: "" })}
        placeholder={t("work.raise.typeNone")}
        options={choices.options}
        groups={choices.groups}
        error={props.errors.type}
      />

      <SelectField
        id="raise-template"
        label={t("work.raise.template")}
        required
        value={form.templateId}
        onChange={(value) => update({ templateId: value, templateLabel: "", assetTypeId: "", assets: [], assetUnitKeys: [] })}
        placeholder={t("work.raise.templateNone")}
        options={templateOptions}
        // BR-AST-534 / BR-SHL-025 — no template fits this asset: the picker
        // cannot act, and the line under it says so and what to do next.
        disabled={noneFitsAsset}
        help={
          noneFitsAsset
            ? `${t("assets.raiseWork.noneApply")} ${t("assets.raiseWork.noneApplyNext")}`
            : assetDoor !== null
            ? t("work.raise.templateHelpAsset")
            : props.origin.kind === "account"
              ? t("work.raise.templateHelpAccount")
              : undefined
        }
        error={props.errors.template}
      />
      {/* `DEF-MET-4973` — the refusal above is not a dead end: the next step
          is the template, and this is where one is made. */}
      {noneFitsAsset && (
        <p className="m-0 -mt-2 mb-4 text-sm">
          <InlineLinkTo to={tenantPath(WORK_TEMPLATE_NEW_ROUTE)} data-new-template-link="">
            {t("work.templates.new")}
          </InlineLinkTo>
        </p>
      )}

      {assetDoor === null && (
        <SelectField
          id="raise-asset-type"
          label={t("work.raise.assetType")}
          required={setByTemplate}
          value={form.assetTypeId}
          onChange={(value) => {
            setAssetPage(1);
            update({ assetTypeId: value, assets: [], assetUnitKeys: [] });
          }}
          placeholder={setByTemplate ? undefined : t("work.raise.assetTypeNone")}
          options={assetTypeRows.map((row) => ({ value: row.id, label: row.name }))}
          help={setByTemplate ? t("work.raise.assetTypeSet") : t("work.raise.assetTypeHelp")}
        />
      )}

      {showAssets && (
        <RaisePickTable
          title={t("work.raise.assets")}
          collection="raise-assets"
          rows={assetRows}
          total={assets.data?.count ?? 0}
          chosen={chosenAssetIds}
          onToggle={(rows, ticked) => {
            const ids = new Set(rows.map((row) => row.id));
            update({
              assets: ticked
                ? [...form.assets, ...rows.map(toChosenAsset)]
                : form.assets.filter((asset) => !ids.has(asset.id)),
            });
          }}
          columns={[
            { key: "asset", label: t("work.raise.col.asset"), cell: (row) => <span className="font-semibold">{row.asset_no}</span> },
            ...(props.origin.kind === "account"
              ? []
              : [
                  {
                    key: "unit",
                    label: t("work.raise.col.unit"),
                    cell: (row: (typeof assetRows)[number]) => (
                      <span className="inline-flex items-center gap-2">
                        {row.unit?.label ?? ""}
                        {chooseOne.has(unitKeyOf(row)) && (
                          <StatusPill tone="warning">{t("work.raise.chooseOne")}</StatusPill>
                        )}
                      </span>
                    ),
                  },
                ]),
            { key: "where", label: t("work.raise.col.where"), cell: (row) => row.location ?? "—" },
            { key: "lastRead", label: t("work.raise.col.lastRead"), cell: (row) => lastReadText(row, readDate) ?? t("work.raise.neverRead") },
          ]}
          search={
            props.origin.kind === "account"
              ? undefined
              : {
                  label: t("work.raise.assetsSearchLabel"),
                  placeholder: t("work.raise.assetsSearch"),
                  value: assetQ,
                  onChange: (value) => {
                    setAssetQ(value);
                    setAssetPage(1);
                  },
                }
          }
          chosenFact={t("work.raise.chosen", { n: form.assets.length, total: assets.data?.count ?? 0 })}
          tickLabel={(row) => t("work.raise.tick", { unit: row.asset_no })}
          tickAllLabel={t("work.raise.tickAll")}
          emptyText={assets.isPending ? t("work.raise.loading") : t("work.raise.assetsEmpty", { type: assetTypeName })}
          note={props.origin.kind === "account" ? t("work.raise.assetsNoteAccount") : t("work.raise.assetsNote")}
          error={props.errors.assets}
          page={assetPage}
          per={assetPer}
          onPage={setAssetPage}
          onPer={(per) => {
            setAssetPer(per);
            setAssetPage(1);
          }}
        />
      )}

      <SelectField
        id="raise-priority"
        label={t("work.raise.priority")}
        value={form.priorityId}
        onChange={(value) => update({ priorityId: value })}
        options={(raiseOptions?.priorities ?? []).map((row) => ({
          value: row.id,
          label: t("work.raise.priorityOption", { name: row.name, hours: row.sla_hours }),
        }))}
      />

      <TextField
        id="raise-notes"
        label={t("work.raise.notes")}
        value={form.notes}
        onChange={(value) => update({ notes: value })}
        multiline
      />

      {/* CR-161-BRC10 W4 — the utility's OWN work-order fields; nothing at
          all when none is placed on this screen (CR-168 §5.7, N4). */}
      <FieldErrorsScope errors={props.customErrors ?? {}}>
        <CustomFieldsInput
          entity="work_orders"
          screen="WORK_NEW"
          values={form.customData}
          onChange={(values) => update({ customData: values })}
          client={client}
        />
      </FieldErrorsScope>
      {props.errors.custom !== undefined && (
        <p className="m-0 text-base text-danger-700" role="alert">
          {props.errors.custom}
        </p>
      )}

      <p className="m-0 text-base font-semibold text-neutral-900" data-raise-summary="">
        {summary}
      </p>
    </div>
  );
}

/** A decimal STRING shown with thousands separators and no trailing zeros —
 *  `"1024.000000"` → `1,024`. Never parsed into a float (hard rule 2's
 *  posture for any stored decimal). */
export function readingText(value: string): string {
  const [whole, frac = ""] = value.split(".");
  const negative = whole.startsWith("-");
  const digits = negative ? whole.slice(1) : whole;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/gu, ",");
  const trimmed = frac.replace(/0+$/u, "");
  return `${negative ? "-" : ""}${grouped}${trimmed === "" ? "" : `.${trimmed}`}`;
}

/** *1,024 kgal · 10/04/2026* — the latest ACTUAL reading with its unit (hard
 *  rule 3), or null where nothing was ever read. The date is the tenant's
 *  regional format (IS-8). */
export function lastReadText(row: RaiseAssetRow, date: (iso: string) => string = (iso) => iso): string | null {
  const read = row.last_read;
  if (read === null || read === undefined || read.reading === null) return null;
  const figure = readingText(read.reading);
  return [read.unit === null ? figure : `${figure} ${read.unit}`, read.on === null ? null : date(read.on)]
    .filter((part) => part !== null && part !== "")
    .join(" · ");
}
