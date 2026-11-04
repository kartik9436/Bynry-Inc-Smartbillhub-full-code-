// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.09 — the Unit & reads tab (image 24): the *Unit*
//           grid (unit · address · building / owner · area · parcel · route ·
//           cycle) and the *Opening reads* tree — meter, then its sub-meter and
//           behind-the-meter device nested under it (BR-AST-003).
// Rules:    hard rule 8 (the address is WALKED from the premises by the server)
//           · hard rule 3 (a reading carries its unit) · B14 rule 31
// Data:     `GET /units/{id}/move-in-facts` and `GET /units/{id}/move-in-meters`
//           (§9.FLOW, step 1's reads, reused), and the move's own
//           `opening_reads` rows (§9.LIST) matched to each meter by number.
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { LoadingSkeleton } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";
import { UnitCell } from "@/components/UnitCell";

import { readFirst } from "../meterTreeOrder";
import type { MoveReadRow } from "../MoveRecordPage";
import { getUnitMoveInFacts, getUnitMoveInMeters } from "./moveDetailEndpoints";
import type { UnitMeterRow } from "./moveDetailEndpoints";
import { Day, DetailGroup, EmptyLine, FactGrid, Stated, registerMeter } from "./moveDetailParts";
import type { Regional } from "./moveDetailParts";

interface TreeLine {
  row: UnitMeterRow;
  depth: number;
}

/** The meter tree flattened in drawn order: each meter, then its children —
 *  the sub-meter before the device behind the meter (image 24, `DEF-CUS-9765`),
 *  by the ONE helper step 1 uses. */
export function meterTree(services: readonly { meters: readonly UnitMeterRow[] }[]): TreeLine[] {
  const out: TreeLine[] = [];
  const walk = (row: UnitMeterRow, depth: number) => {
    out.push({ row, depth });
    for (const child of readFirst(row.children ?? [])) walk(child, depth + 1);
  };
  for (const service of services) for (const meter of service.meters) walk(meter, 0);
  return out;
}

export function UnitReadsTab(props: {
  unitId: string | null;
  readings: readonly MoveReadRow[];
  regional: Regional;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const facts = useQuery({
    queryKey: ["move-detail-unit-facts", props.unitId ?? ""],
    enabled: props.unitId !== null,
    queryFn: () => getUnitMoveInFacts(props.unitId ?? "", client),
  });
  const meters = useQuery({
    queryKey: ["move-detail-unit-meters", props.unitId ?? ""],
    enabled: props.unitId !== null,
    queryFn: () => getUnitMoveInMeters(props.unitId ?? "", client),
  });
  if (props.unitId === null) {
    return (
      <DetailGroup title={t("customers.moveDetail.section.unit")} name="unit">
        <EmptyLine>{t("customers.moveDetail.absent.noUnit")}</EmptyLine>
      </DetailGroup>
    );
  }
  const notRecorded = <Stated label={t("customers.moveDetail.absent.notRecorded")} />;
  const f = facts.data;
  const address = f?.unit.address;
  const route = f?.building.routes[0] ?? null;
  const lines = meters.data ? meterTree([...meters.data.services, { meters: meters.data.unplaced }]) : [];
  const readOf = (assetNo: string) =>
    props.readings.find((row) => registerMeter(row.register) === assetNo) ?? null;

  return (
    <div className="flex flex-col gap-6" data-move-tab="unit">
      <DetailGroup title={t("customers.moveDetail.section.unit")} name="unit">
        {facts.isPending ? (
          <LoadingSkeleton variant="card" />
        ) : !f ? (
          <EmptyLine>{t("customers.moveDetail.absent.notReadable")}</EmptyLine>
        ) : (
          <FactGrid
            name="move-unit"
            facts={[
              {
                id: "unit",
                label: t("customers.moveDetail.fact.unit"),
                value: [f.unit.unit_no, f.unit.label, f.unit.floor_label].filter(Boolean).join(" · "),
              },
              {
                id: "address",
                label: t("customers.moveDetail.fact.address"),
                value: address
                  ? [address.line1, [address.city, [address.state, address.postal_code].filter(Boolean).join(" ")]
                      .filter(Boolean)
                      .join(", ")]
                      .filter(Boolean)
                      .join(", ")
                  : notRecorded,
              },
              {
                id: "building",
                label: t("customers.moveDetail.fact.building"),
                value: [f.building.premise_no, f.building.name].filter(Boolean).join(" · ") || notRecorded,
              },
              {
                id: "owner",
                label: t("customers.moveDetail.fact.owner"),
                value: f.owner
                  ? [f.owner.name, f.owner.account_no].filter(Boolean).join(" · ")
                  : t("customers.moveDetail.absent.noOwner"),
              },
              {
                id: "area",
                label: t("customers.moveDetail.fact.areaParcel"),
                value:
                  [f.building.area_name, f.building.parcel].filter(Boolean).join(" · ") || notRecorded,
              },
              {
                id: "route",
                label: t("customers.moveDetail.fact.routeCycle"),
                value: route ? [route.name ?? route.code, route.cycle_name].filter(Boolean).join(" · ") : notRecorded,
              },
            ]}
          />
        )}
      </DetailGroup>
      <DetailGroup title={t("customers.moveRecord.section.openingReads")} name="opening-reads">
        {meters.isPending ? (
          <LoadingSkeleton variant="table" />
        ) : lines.length === 0 ? (
          <EmptyLine>{t("customers.moveDetail.reads.noMeters")}</EmptyLine>
        ) : (
          <PlainTable data-move-reads="">
            <thead>
              <tr>
                <th>{t("customers.moveDetail.col.id")}</th>
                <th>{t("customers.moveDetail.col.kind")}</th>
                <th>{t("customers.moveDetail.col.size")}</th>
                <th>{t("customers.moveDetail.col.lastRead")}</th>
                <th>{t("customers.moveDetail.col.openingRead")}</th>
                <th>{t("customers.moveDetail.col.source")}</th>
                <th>{t("customers.moveDetail.col.state")}</th>
              </tr>
            </thead>
            <tbody>
              {lines.map(({ row, depth }) => {
                const read = readOf(row.asset_no);
                const recorded = read !== null && read.how === "read" && read.reading !== null;
                return (
                  <tr key={row.asset_no} data-reads-depth={depth}>
                    <td className={depth === 0 ? "" : depth === 1 ? "pl-6" : "pl-10"}>
                      {depth > 0 ? <span aria-hidden="true">└ </span> : null}
                      {row.asset_no}
                    </td>
                    <td>
                      {[t(`customers.moveDetail.meterKind.${row.kind}`), row.location_note].filter(Boolean).join(" · ")}
                    </td>
                    <td>{row.size_name ? row.size_name : "—"}</td>
                    <td>
                      {row.last_read ? (
                        <UnitCell quantity={row.last_read.value} unit={row.last_read.unit ?? row.unit ?? ""} />
                      ) : (
                        "—"
                      )}
                    </td>
                    <td>
                      {recorded && read ? (
                        <span>
                          <UnitCell quantity={read.reading ?? ""} unit={read.unit ?? row.unit ?? ""} />{" "}
                          <span className="text-neutral-600">
                            <Day value={read.read_at} regional={props.regional} />
                          </span>
                        </span>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td data-read-source="">
                      {/* `DEF-CUS-9765` — image 24's SOURCE: the read's own event
                          (`meter_reads.event_context`), served on the row. */}
                      {!recorded
                        ? t("customers.moveDetail.stillOpen.notRead")
                        : read?.event === "move_in"
                          ? t("customers.moveDetail.source.move_in")
                          : t("customers.moveDetail.source.other")}
                    </td>
                    <td>
                      {recorded ? (
                        <StatusPill tone="success">{t("customers.moveDetail.reads.recorded")}</StatusPill>
                      ) : (
                        <StatusPill tone="neutral">{t("customers.moveDetail.stillOpen.notRead")}</StatusPill>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </PlainTable>
        )}
      </DetailGroup>
    </div>
  );
}
