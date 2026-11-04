// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-10051 — move-out step 2 listed METERS only; sewer, trash
//           and fire lines were invisible on the screen that closes them.
// Ruling:   PO 2026-10-11, verbatim on the three tables put to them: *"this is
//           correct"* (decision log, *"MOVE-OUT STEP 2 — EVERY SERVICE ON THE
//           UNIT, GROUPED BY HOW IT IS BILLED"*).
// Rules:    BR-TEN-1180 (metered · share · capacity — the tenant's own
//           declaration) · BR-CUS-021 (final reads) · OQ-394 (the move-out box
//           opens with the last reading) · hard rule 2 (a percentage DISPLAYS
//           2 decimals) · hard rule 3 · B14 rules 21 (Tailwind; on
//           route-b-migrated.txt), 31 (no database id on screen), 33, 43
// Tests:    MoveOutServicesTable.dom.test.tsx · MoveOutWizard.test.tsx
// Hosts:    MoveOutWizard.tsx (step 2, *Date & reads*)
// ───────────────────────────────────────────────────────
//
// THREE GROUPS, ONE PER BILLING BASIS:
//
//   METERED   the nine reading columns `MoveInReadingsTable` draws (the ONE
//             builder, `readingColumns`), plus a last cell — the FETCH SLOT.
//   SHARE     Service · Based on · Comes from. Nothing to enter.
//   CAPACITY  Asset # · Type · Service · Size · Count · Billed through.
//             Nothing to enter.
//
// ⚠ **THE METERED ROWS ARE STILL `GET /units/{id}/assets`'s**, the same query
// the wizard's reads draft is keyed on, so the boxes on screen and the payload
// are one set of registers. `GET /units/{id}/move-out-services` decides only
// which GROUP a row lands in: an asset standing on a capacity service (a cart, a
// fire line) leaves the metered table for the capacity one.
//
// ⚠ **THE FETCH SLOT — `renderFetch`.** The shared *Fetch reading* control
// (`DEF-CUS-10050`) is built elsewhere; this table gives every READABLE metered
// row a cell carrying `data-fetch-slot="<asset no>"` and calls
// `renderFetch(row)` inside it. The row carries the asset id, its number, its
// unit of measure and the MOVE-OUT DATE, because the PO ruled the fetch is
// asked AS OF that date. A non-readable row gets no slot.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { formatPercent } from "@/components/PercentCell";
import { LoadingSkeleton } from "@/components/StateFrame";
import { CellStatic, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";
import { Note } from "@/components/TextBits";
import { serviceLabel } from "@/features/assets/assetsShared";
import type { Translator } from "@/features/tenancy/settingsShared";

import { moveInReadingRows, readingColumns } from "./MoveInReadingsTable";
import type { MoveInReadingRow } from "./MoveInReadingsTable";
import { readableAssets } from "./moveReadsCapture";
import type { ReadsDraft } from "./moveReadsCapture";
import { getUnitAssets, unitAssetsQueryKey } from "./UnitAssetsPanel";
import type { UnitAssets } from "./UnitAssetsPanel";

// ── The read ───────────────────────────────────────────────────────────────

export type BillingBasis = "metered" | "share" | "capacity";

export interface MoveOutShareRow {
  service: string;
  /** Rating's stored figure, in POINTS (`"80.000000"` is 80%). */
  percent: string | null;
  percent_basis: "usage" | "charge" | null;
  basis_service: string | null;
  source_asset_nos: string[];
  /** Why no percent could be read; `null` when one was. */
  terms_absent: string | null;
}

export interface MoveOutCapacityRow {
  service: string;
  type_name: string | null;
  size_class: string | null;
  /** The tenant's NAME for the size, or `null` — never the code (rule 31). */
  size_name: string | null;
  asset_nos: (string | null)[];
  count: number;
}

export interface MoveOutServices {
  unit_id: string;
  as_of: string;
  services: { service: string; billing_basis: BillingBasis }[];
  metered: { service: string; asset_nos: string[] }[];
  share: MoveOutShareRow[];
  capacity: MoveOutCapacityRow[];
}

/** The ONE place this route is spelled. */
export function moveOutServicesPath(unitId: string, asOf: string): string {
  const base = `/units/${encodeURIComponent(unitId)}/move-out-services`;
  return asOf === "" ? base : `${base}?as_of=${encodeURIComponent(asOf)}`;
}

export const moveOutServicesQueryKey = (unitId: string, asOf: string) =>
  ["customers", "unit", unitId, "move-out-services", asOf] as const;

export async function getMoveOutServices(
  unitId: string,
  asOf: string,
  client: ApiClient = api,
): Promise<MoveOutServices> {
  const response = await client.get<MoveOutServices>(moveOutServicesPath(unitId, asOf));
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

// ── Pure derivations ───────────────────────────────────────────────────────

/** One METERED row, with everything the fetch slot needs to ask AS OF the
 *  move-out date. `assetId` is a lookup key and is never drawn (rule 31). */
export interface MoveOutMeteredRow extends MoveInReadingRow {
  assetId: string;
  assetNo: string | null;
  /** The register's unit of measure (hard rule 3), `null` when unknown. */
  uom: string | null;
  service: string | null;
  /** The move-out date (ISO), or `""` before one is chosen. */
  moveOutDate: string;
}

/**
 * The metered group: every installed asset EXCEPT a non-readable one standing
 * on a share or capacity service (a cart, a fire line — those are counted in
 * the capacity group). A readable meter always stays here, whatever its
 * service, because the reads draft holds it and it is sent.
 */
export function meteredRows(
  assets: UnitAssets | undefined,
  services: MoveOutServices | undefined,
  moveOutDate: string,
): MoveOutMeteredRow[] {
  const basis = new Map((services?.services ?? []).map((row) => [row.service, row.billing_basis]));
  return moveInReadingRows(assets)
    .filter(({ asset, readable }) => {
      if (readable || asset.service === null) return true;
      return (basis.get(asset.service) ?? "metered") === "metered";
    })
    .map((row) => ({
      ...row,
      assetId: row.asset.id,
      assetNo: row.asset.asset_no,
      uom: row.asset.last_read?.unit ?? null,
      service: row.asset.service,
      moveOutDate,
    }));
}

/**
 * ⚠ **THE STEP-2 GATE, PURE: the readable registers with neither a reading
 * nor Estimate.** Share and capacity rows have no register and are never in
 * this list. The draft is the wizard's EFFECTIVE draft (`OQ-394`'s prefill
 * already under it), so only a register never read, or one a clerk cleared,
 * can stop Continue.
 */
export function missingFinalReads(assets: UnitAssets | undefined, draft: ReadsDraft): string[] {
  return readableAssets(assets)
    .filter((asset) => {
      const row = draft[asset.id];
      return row === undefined || (!row.estimate && row.value.trim() === "");
    })
    .map((asset) => asset.id);
}

/** *"80.00% of Water usage"* — `null` when rating stated no percent. */
export function shareBasedOnText(row: MoveOutShareRow, t: Translator): string | null {
  if (row.percent === null || row.basis_service === null) return null;
  const params = {
    percent: formatPercent(row.percent, "points"),
    service: serviceLabel(row.basis_service, t),
  };
  return row.percent_basis === "charge"
    ? t("customers.moveOut.services.shareOfCharge", params)
    : t("customers.moveOut.services.shareOfUsage", params);
}

/** *"W-5042 final reading"* — `null` when the basis service has no meter here. */
export function shareComesFromText(row: MoveOutShareRow, t: Translator): string | null {
  if (row.source_asset_nos.length === 0) return null;
  return t("customers.moveOut.services.finalReadingOf", { meter: row.source_asset_nos.join(", ") });
}

// ── The component ──────────────────────────────────────────────────────────

const DASH = "—";

export function MoveOutServicesTable(props: {
  unitId: string;
  /** The wizard's EFFECTIVE reads draft. */
  draft: ReadsDraft;
  onChange: (draft: ReadsDraft) => void;
  /** The move-out date (ISO), or `""` — Read date opens on it, the capacity
   *  rows are billed through it, and the fetch is asked as of it. */
  moveOutDate: string;
  /** Continue was pressed — only then is a missing reading red. */
  showErrors: boolean;
  /** The metered group's heading; a master's common areas pass their own. */
  titleText?: string;
  /** What fills each readable metered row's last cell. */
  renderFetch: (row: MoveOutMeteredRow) => ReactNode;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
}) {
  const { t } = props;
  const client = props.client ?? api;
  const assetsQuery = useQuery({
    queryKey: unitAssetsQueryKey(props.unitId),
    queryFn: () => getUnitAssets(props.unitId, client),
    enabled: props.unitId !== "",
  });
  const servicesQuery = useQuery({
    queryKey: moveOutServicesQueryKey(props.unitId, props.moveOutDate),
    queryFn: () => getMoveOutServices(props.unitId, props.moveOutDate, client),
    enabled: props.unitId !== "",
    // A deployment without the route still draws the meters, ungrouped.
    retry: false,
  });

  const title = props.titleText ?? t("customers.moveOut.date.metersTitle");
  if (props.unitId === "") {
    return null;
  }
  if (assetsQuery.isPending) {
    return (
      <section className="flex flex-col gap-3" data-move-out-services="loading">
        <h4 className="m-0 font-heading text-base font-semibold">{title}</h4>
        <LoadingSkeleton variant="card" />
      </section>
    );
  }
  if (assetsQuery.data === undefined) {
    return (
      <section className="flex flex-col gap-3" data-move-out-services="failed">
        <h4 className="m-0 font-heading text-base font-semibold">{title}</h4>
        <Note role="alert">{t("customers.moveIn.reads.failed")}</Note>
      </section>
    );
  }

  const services = servicesQuery.data;
  const metered = meteredRows(assetsQuery.data, services, props.moveOutDate);
  const missing = new Set(props.showErrors ? missingFinalReads(assetsQuery.data, props.draft) : []);
  const reading = readingColumns({
    draft: props.draft,
    onChange: props.onChange,
    moveInDate: props.moveOutDate,
    t,
    timeZone: props.timeZone,
    dateFormat: props.dateFormat,
    idPrefix: "moveOut",
    readingLabel: t("customers.moveOut.reads.col.reading", { defaultValue: "Reading" }),
    unlinkedServiceText: t("customers.moveOut.services.notLinked"),
    // `DEF-BIL-10129` — the fetch slot shows the server's estimate answer
    // for a ticked row; the column's inferred hint would say it a second time.
    noHistoryHint: false,
  }) as TableArrayColumn<MoveOutMeteredRow>[];
  const meteredColumns: TableArrayColumn<MoveOutMeteredRow>[] = [
    ...reading,
    {
      key: "fetch",
      label: "",
      cell: (row) =>
        row.readable ? (
          <span data-fetch-slot={row.assetNo ?? ""}>{props.renderFetch(row)}</span>
        ) : null,
    },
  ];

  const share = services?.share ?? [];
  const shareColumns: TableArrayColumn<MoveOutShareRow>[] = [
    {
      key: "service",
      label: t("customers.moveIn.reads.col.service"),
      cell: (row) => <CellStatic name="share-service">{serviceLabel(row.service, t)}</CellStatic>,
    },
    {
      key: "basedOn",
      label: t("customers.moveOut.services.col.basedOn"),
      cell: (row) => <CellStatic name="share-based-on">{shareBasedOnText(row, t) ?? DASH}</CellStatic>,
    },
    {
      key: "comesFrom",
      label: t("customers.moveOut.services.col.comesFrom"),
      cell: (row) => (
        <CellStatic name="share-comes-from">{shareComesFromText(row, t) ?? DASH}</CellStatic>
      ),
    },
  ];

  const capacity = services?.capacity ?? [];
  const capacityColumns: TableArrayColumn<MoveOutCapacityRow>[] = [
    {
      key: "asset",
      label: t("customers.moveIn.reads.col.assetNo"),
      cell: (row) => (
        <CellStatic name="capacity-asset">
          {row.asset_nos.filter((no) => no !== null && no !== "").join(", ") || DASH}
        </CellStatic>
      ),
    },
    {
      key: "type",
      label: t("customers.moveIn.reads.col.type"),
      cell: (row) => <CellStatic name="capacity-type">{row.type_name ?? DASH}</CellStatic>,
    },
    {
      key: "service",
      label: t("customers.moveIn.reads.col.service"),
      cell: (row) => <CellStatic name="capacity-service">{serviceLabel(row.service, t)}</CellStatic>,
    },
    {
      key: "size",
      label: t("customers.moveOut.services.col.size"),
      cell: (row) => <CellStatic name="capacity-size">{row.size_name ?? DASH}</CellStatic>,
    },
    {
      key: "count",
      label: t("customers.moveOut.services.col.count"),
      numeric: true,
      cell: (row) => <CellStatic name="capacity-count">{row.count}</CellStatic>,
    },
    {
      key: "billedThrough",
      label: t("customers.moveOut.services.col.billedThrough"),
      cell: () =>
        props.moveOutDate === "" ? (
          DASH
        ) : (
          <DateCell value={props.moveOutDate} timeZone={props.timeZone} dateFormat={props.dateFormat} />
        ),
    },
  ];

  return (
    // No bottom margin: the host's `WizardSectionStack` spaces sections.
    <section className="flex flex-col gap-4" data-move-out-services="ready">
      <TableArray<MoveOutMeteredRow>
        readOnly
        title={title}
        columns={meteredColumns}
        rows={metered}
        rowKey={(row) => row.assetId}
        emptyText={t("customers.moveIn.reads.none")}
        collection="move-out-metered"
        cellError={(row, _index, column) =>
          column === "reading" && missing.has(row.assetId)
            ? t("customers.moveOut.services.readingRequired")
            : undefined
        }
      />
      {share.length === 0 ? null : (
        <TableArray<MoveOutShareRow>
          readOnly
          title={t("customers.moveOut.services.shareTitle")}
          columns={shareColumns}
          rows={share}
          rowKey={(row) => row.service}
          emptyText=""
          collection="move-out-share"
        />
      )}
      {capacity.length === 0 ? null : (
        <TableArray<MoveOutCapacityRow>
          readOnly
          title={t("customers.moveOut.services.capacityTitle")}
          columns={capacityColumns}
          rows={capacity}
          rowKey={(row) => `${row.service}:${row.type_name ?? ""}:${row.size_class ?? ""}`}
          emptyText=""
          collection="move-out-capacity"
        />
      )}
    </section>
  );
}
