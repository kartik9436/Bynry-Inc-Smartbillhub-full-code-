// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the Units tab (images 31–33): *Search
//           unit or premises*, *All · Occupied · Vacant*, ⤓ CSV, and every name a
//           link (ruling 13). Units, not Accounts — a plan attaches to a UNIT
//           (ruling 2).
// Defects:  DEF-RAT-9353 (premises and account open) · DEF-RAT-9334 (no search,
//           no filter, no CSV)
// Rules:    NFR-3 (searched, filtered and paged by the SERVER; the CSV is the
//           whole filtered set, streamed) · BR-SHL-011 (the list's state is URL
//           state, beside `?tab=`) · B14 rule 31 (labels and numbers, never ids)
//           · ruling 15 (*Move units to another plan* is NOT here: no selection
//           column, no Move button)
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import type { ApiClient } from "@/api/client";
import { PLAN_UNIT_OCCUPANCY, getPlanUnitPage, getPlanUnitsCsv } from "@/api/planDetailEndpoints";
import type { PlanUnitRow } from "@/api/planDetailEndpoints";
import { ChipRow, ChipToggle } from "@/components/Chip";
import { DataTable } from "@/components/DataTable";
import { DownloadButton } from "@/components/DownloadButton";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { InlineLinkTo } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { setFilter } from "@/components/FilterBar";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { accountDetailPath } from "@/features/customers/customersShared";
import { premisesDetailPath, unitDetailPath } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { SECTION_HEADING } from "../planForm/planFormShared";
import { ServiceTags } from "../ratingShared";
import { DASH, dayShown } from "./planDetailModel";
import type { PlanRegional, Translator } from "./planDetailModel";
import { saveCsv } from "./saveCsv";

/** The tab's list state lives in the URL beside `?tab=` (BR-SHL-011). */
export const UNITS_PARAM_PREFIX = "u.";

const OCCUPANCY_KEYS: Readonly<Record<string, string>> = {
  occupied: "rating.planDetail.units.occupied",
  vacant: "rating.planDetail.units.vacant",
};

export function planUnitsConfig(t: Translator, cells: TableConfig<PlanUnitRow>["columns"]): TableConfig<PlanUnitRow> {
  return {
    screenId: "S10.plan.units",
    columns: cells,
    getRowId: (row) => row.unit_id,
    searchFields: ["unit", "premises"],
    searchPlaceholder: "rating.planDetail.units.search",
    filters: [
      {
        name: "occupancy",
        label: t("rating.planDetail.units.col.occupancy"),
        options: PLAN_UNIT_OCCUPANCY.map((value) => ({ value, label: t(OCCUPANCY_KEYS[value]) })),
      },
    ],
    defaultSort: { sort: "premises", dir: "asc" },
  };
}

export function PlanUnitsTab(props: { planId: string; client: ApiClient; regional: PlanRegional; t: Translator }) {
  const { t, regional } = props;
  const tenantPath = useTenantPath();
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();

  const config = planUnitsConfig(t, [
    {
      key: "unit",
      label: t("rating.planDetail.units.col.unit"),
      identity: true,
      cell: (row) => (
        <InlineLinkTo to={tenantPath(unitDetailPath(row.unit_id))} className="font-semibold">
          {row.unit_label ?? row.unit_no ?? DASH}
        </InlineLinkTo>
      ),
    },
    {
      key: "premises",
      label: t("rating.planDetail.units.col.premises"),
      cell: (row) =>
        row.premises_id === null ? (
          <span>{row.premises_address ?? DASH}</span>
        ) : (
          <InlineLinkTo to={tenantPath(premisesDetailPath(row.premises_id))} className="font-semibold">
            {row.premises_address ?? DASH}
          </InlineLinkTo>
        ),
    },
    {
      key: "services",
      label: t("rating.planDetail.units.col.services"),
      cell: (row) =>
        row.services.length === 0 ? (
          <span className="text-neutral-700">{t("rating.planDetail.units.noServicePoint")}</span>
        ) : (
          <ServiceTags services={row.services} />
        ),
    },
    {
      key: "account",
      label: t("rating.planDetail.units.col.account"),
      cell: (row) =>
        row.account_no === null ? (
          <span>{DASH}</span>
        ) : row.account_id === null ? (
          <span>{row.account_no}</span>
        ) : (
          <InlineLinkTo to={tenantPath(accountDetailPath(row.account_id))} className="font-semibold">
            {row.account_no}
          </InlineLinkTo>
        ),
    },
    {
      key: "occupancy",
      label: t("rating.planDetail.units.col.occupancy"),
      cell: (row) =>
        row.vacant ? (
          <StatusPill tone="neutral">{t("rating.planDetail.units.vacant")}</StatusPill>
        ) : (
          <StatusPill tone="success">{t("rating.planDetail.units.occupied")}</StatusPill>
        ),
    },
    {
      key: "since",
      label: t("rating.planDetail.units.col.since"),
      cell: (row) => <span className="tabular-nums">{dayShown(row.assigned_from, regional)}</span>,
    },
  ]);

  const state = parseTableParams(searchParams, config, UNITS_PARAM_PREFIX);
  const occupancy = state.filters.occupancy ?? "";
  const query = useQuery({
    queryKey: ["plans", props.planId, "units", serializeTableParams(state, config).toString()],
    queryFn: () =>
      getPlanUnitPage(props.planId, { q: state.q, occupancy, page: state.page, per: state.per }, props.client),
    enabled: props.planId !== "",
    placeholderData: (previous) => previous,
  });

  function setState(next: TableRequestState): void {
    const merged = new URLSearchParams(searchParams);
    for (const key of [...merged.keys()]) {
      if (key.startsWith(UNITS_PARAM_PREFIX)) merged.delete(key);
    }
    serializeTableParams(next, config, UNITS_PARAM_PREFIX).forEach((value, key) => merged.set(key, value));
    setSearchParams(merged, { replace: true });
  }

  async function download(): Promise<void> {
    try {
      saveCsv(await getPlanUnitsCsv(props.planId, { q: state.q, occupancy }, props.client), "plan-units.csv");
    } catch {
      toast(t("rating.planDetail.csvFailed"));
    }
  }

  const choices: { value: string; label: string }[] = [
    { value: "", label: t("table.filters.all") },
    ...PLAN_UNIT_OCCUPANCY.map((value) => ({ value, label: t(OCCUPANCY_KEYS[value]) })),
  ];

  return (
    <Panel as="section" aria-labelledby="plan-detail-units" data-plan-units="">
      <h2 id="plan-detail-units" className={SECTION_HEADING}>
        {t("rating.planDetail.tab.units")}
      </h2>
      <DataTable<PlanUnitRow>
        config={config}
        state={state}
        onStateChange={setState}
        rows={query.data?.rows ?? []}
        totalRows={query.data?.total ?? null}
        loading={query.isPending}
        error={
          query.isError && query.data === undefined
            ? { reason: t("rating.planDetail.units.failed"), onRetry: () => void query.refetch() }
            : undefined
        }
        filterBarSlot={
          // Image 31's three choices, drawn as the kit's chips — ONE dimension,
          // declared in `config.filters`, writing the same `u.f.occupancy`.
          <ChipRow data-plan-occupancy="">
            {choices.map((choice) => (
              <ChipToggle
                key={choice.value || "all"}
                selected={occupancy === choice.value}
                onClick={() => setState(setFilter(state, "occupancy", choice.value))}
                data-occupancy={choice.value || "all"}
              >
                {choice.label}
              </ChipToggle>
            ))}
          </ChipRow>
        }
        downloadSlot={<DownloadButton onDownload={() => void download()} />}
        empty={{ title: t("rating.planDetail.units.empty"), helper: "" }}
      />
    </Panel>
  );
}
