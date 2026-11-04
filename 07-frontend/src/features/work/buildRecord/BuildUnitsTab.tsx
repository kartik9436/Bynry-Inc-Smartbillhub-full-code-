// ── Trace ──────────────────────────────────────────────
// Change:   CR-162-BRC10 items 36 and 38 (T2-3, T2-13) — the Units tab shows
//           what stands on each unit and activates what is ready.
// Ruling:   decision log 2026-10-02 (commit 56eb54ba9): *"Details Units tab:
//           Kind, Asset type, Size, Qty, Work order (and asset ID, unit type)
//           columns empty — show them"* · *"Activation per unit/service: user
//           picks one, several or all of what is ready (WOs complete) … same
//           from Units tab row actions and Approve dialog."*
// Server:   `GET /connections/{id}/activation`
//           (apps/metering/connection_activation.py) — ONE read the table and
//           the Approve dialog both draw from, so they cannot disagree.
// Rules:    B14 rule 15 (row actions are icons) · rule 20 (one table type) ·
//           rule 31 (no database id on screen: asset and order NUMBERS) ·
//           rule 21 (Tailwind utilities; on route-b-migrated.txt)
// ───────────────────────────────────────────────────────
// ⚠ **THE COLUMNS WERE EMPTY BECAUSE THE TABLE JOINED THREE LISTS BY LABEL.**
// It read `detail.unit_rows`, `detail.assets` and `detail.work_orders` and
// matched them on the unit's LABEL and the service — but the connection read
// serves `service: null` and `size: null` on every asset, so Asset type, Size
// and Qty could never fill, and the State column printed the SERVICE's
// aggregate on every unit. The activation read joins on the database's own
// keys (unit × service × service point) and is what this table draws now.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getLookupEntries } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { PowerIcon } from "@/components/icons";
import type { KpiTile } from "@/components/KPIStrip";
import { RowAction, RowActions } from "@/components/RowActions";
import { PlainTable } from "@/components/Surfaces";
import { sizeClassName, useSizeClassNames } from "@/features/assets/assetsShared";
import { connectionStateLabel } from "@/features/customers/NewConnectsTab";
import {
  activationQueryKey,
  getActivation,
} from "@/features/customers/buildLifecycleEndpoints";
import type { ActivationRow } from "@/features/customers/buildLifecycleEndpoints";
import type { Translator } from "@/features/customers/newConnectShared";
import { unitDetailPath } from "@/features/metering/meteringShared";

import { Facts, Section, text } from "./buildTabShell";
import type { BuildTabProps } from "./buildTabShell";

/** ⊕ **`DEF-MET-9244` — a unit's TYPE in the utility's own words.** The tab
 *  printed the stored code (`residential_submetered`). The name comes from the
 *  tenant's `unit_types` lookup — the read, and the cache entry, the Add unit
 *  form already uses — then the catalogue's word for a seeded code, and the
 *  code only where neither knows it (B14 rule 31: a code is never the value a
 *  clerk is meant to read, but a blank would hide the fact). */
export function unitTypeName(
  code: string | null | undefined,
  names: ReadonlyMap<string, string>,
  t: Translator,
): string | null {
  const value = text(code);
  if (value === null) {
    return null;
  }
  return names.get(value) ?? t(`metering.units.type.${value}`, { defaultValue: value });
}

/** **Every size on the row, each with its count — `DEF-CUS-9218`.** The cell
 *  read the FIRST asset's size, so a unit with one 6-inch and two 2-inch fire
 *  lines read *FL-2 · 3* and the 6-inch line vanished from the screen (found by
 *  the New Connection end-to-end walk, `CON-26-0131`). A size held once prints
 *  bare; a size held more than once prints `× n`; sizes keep the order the
 *  assets are served in. `null` when no asset carries a size.
 *  `DEF-RAT-9321` — each size prints as the utility's NAME (`Fire line 2"`),
 *  never its code (`FL-2`); `names` is the size catalogue, code → name. */
export function sizesText(
  assets: ActivationRow["assets"],
  names: ReadonlyMap<string, string> = new Map(),
): string | null {
  const counts = new Map<string, number>();
  for (const asset of assets) {
    const size = sizeClassName(text(asset.size_class), names);
    if (size === null) continue;
    counts.set(size, (counts.get(size) ?? 0) + 1);
  }
  if (counts.size === 0) return null;
  // One size for the whole row: the Qty column already says how many.
  if (counts.size === 1) return [...counts.keys()][0];
  return [...counts.entries()].map(([size, n]) => (n > 1 ? `${size} × ${n}` : size)).join(" · ");
}

/** ⊕ `DEF-CUS-9840` — ` · Solar panel 10 kW` after an asset number when its
 *  row holds several pieces, so each number says which size it is (PO ruling
 *  (a): one asset per panel, tracked). Empty for a one-asset row, whose Size
 *  column already says it, and for an asset with no size. */
export function assetSizeSuffix(
  assets: ActivationRow["assets"],
  asset: ActivationRow["assets"][number],
  names: ReadonlyMap<string, string> = new Map(),
): string {
  if (assets.length < 2) return "";
  const size = sizeClassName(text(asset.size_class), names);
  return size === null ? "" : ` · ${size}`;
}

/** Why ONE row cannot be activated now, in the clerk's words, or `null`. */
export function rowRefusal(row: ActivationRow, t: Translator): string | null {
  if (row.state === "activated") {
    return t("customers.build.units.alreadyActive", { defaultValue: "Already activated." });
  }
  if (row.blocked_by_gate !== null) {
    return t("customers.build.units.gateHolds", {
      order: row.blocked_by_gate,
      defaultValue: `Gate ${row.blocked_by_gate} not passed.`,
    });
  }
  if (!row.ready) {
    return t("customers.build.units.ordersOpen", { defaultValue: "Work orders still open." });
  }
  return null;
}

/** The unit's own words for its state — *Pending*, *Partly activated*, *Activated*. */
function unitStateWord(state: ActivationRow["unit_state"], t: Translator): string {
  if (state === "activated") {
    return t("customers.build.units.unitActive", { defaultValue: "Active" });
  }
  if (state === "partly_activated") {
    return connectionStateLabel("partly_activated", t);
  }
  return t("customers.build.units.unitPending", { defaultValue: "Pending" });
}

/** One service at one unit: *Pending* until activated, then *Activated*. */
export function serviceStateWord(state: string, t: Translator): string {
  if (state === "activated") {
    return t("customers.build.units.serviceActivated", { defaultValue: "Activated" });
  }
  if (state === "cancelled") {
    return connectionStateLabel("cancelled", t);
  }
  return t("customers.build.units.unitPending", { defaultValue: "Pending" });
}

export function BuildUnitsTab(
  props: BuildTabProps & {
    /** Opens the ONE Approve dialog with these rows chosen. */
    onActivate?: (ids: string[]) => void;
  },
) {
  const { t, detail, record, path } = props;
  const read = useQuery({
    queryKey: activationQueryKey(detail.id),
    queryFn: () => getActivation(detail.id, props.client),
    retry: false,
  });
  const unitTypes = useQuery({
    queryKey: ["lookups", "unit_types", "new-connect"],
    queryFn: () => getLookupEntries("unit_types", { per: 200 }, props.client),
    retry: false,
  });
  const typeNames = new Map(
    ((unitTypes.data?.results ?? []) as { code: string; name: string }[]).map(
      (row) => [row.code, row.name] as const,
    ),
  );
  const sizeNames = useSizeClassNames(props.client);
  const [chosen, setChosen] = useState<string[]>([]);
  const rows = read.data?.rows ?? [];
  const canActivate = read.data?.can_activate === true && props.onActivate !== undefined;
  const refusal =
    read.data?.refusal === null || read.data?.refusal === undefined
      ? null
      : t(read.data.refusal, { defaultValue: read.data.refusal });

  const tiles: KpiTile[] = [
    {
      id: "units",
      label: t("customers.build.fact.units", { defaultValue: "Units" }),
      value: <span className="tabular-nums">{detail.units}</span>,
    },
  ];
  if (record !== null) {
    tiles.push({
      id: "points",
      label: t("customers.build.fact.servicePoints", { defaultValue: "Service points" }),
      value: <span className="tabular-nums">{record.tiles.service_points.total}</span>,
    });
  }

  function toggle(id: string): void {
    setChosen((now) => (now.includes(id) ? now.filter((one) => one !== id) : [...now, id]));
  }

  const units = Array.from(
    new Map(rows.map((row) => [row.unit_id ?? "", row] as const)).values(),
  );

  return (
    <>
      <Facts id="units" tiles={tiles} />
      <Section
        id="units"
        title={t("customers.build.units.title", { defaultValue: "Units and service points" })}
      >
        {canActivate && (
          <div className="mb-3 flex flex-wrap gap-2" data-units-activate="">
            <Button
              variant="secondary"
              data-act="activateSelected"
              disabled={chosen.length === 0 || Boolean(props.readOnlyReason)}
              title={props.readOnlyReason ?? undefined}
              data-blocked-reason={props.readOnlyReason ?? undefined}
              onClick={() => props.onActivate?.(chosen)}
            >
              {t("customers.build.units.activateSelected", { defaultValue: "Activate selected" })}
            </Button>
            <Button
              variant="secondary"
              data-act="activateAllReady"
              disabled={(read.data?.ready_ids.length ?? 0) === 0 || Boolean(props.readOnlyReason)}
              title={props.readOnlyReason ?? undefined}
              data-blocked-reason={props.readOnlyReason ?? undefined}
              onClick={() => props.onActivate?.(read.data?.ready_ids ?? [])}
            >
              {t("customers.build.units.activateAllReady", { defaultValue: "Activate all ready" })}
            </Button>
          </div>
        )}
        {refusal !== null && (
          <p className="m-0 mb-3 text-sm text-neutral-700" data-units-refusal="">
            {refusal}
          </p>
        )}
        {read.isPending ? (
          <p className="text-sm text-neutral-700">
            {t("customers.build.units.loading", { defaultValue: "Loading…" })}
          </p>
        ) : rows.length === 0 ? (
          <p className="text-sm text-neutral-700" data-build-empty="units">
            {t("customers.build.units.none", { defaultValue: "No service points yet." })}
          </p>
        ) : (
          <PlainTable data-table="build-units">
            <thead>
              <tr>
                <th aria-label={t("customers.build.units.col.choose", { defaultValue: "Choose" })} />
                <th>{t("customers.newConnect.step4.unit", { defaultValue: "Unit" })}</th>
                <th>{t("customers.build.units.col.unitType", { defaultValue: "Unit type" })}</th>
                <th>{t("customers.newConnect.step5.service", { defaultValue: "Utility service" })}</th>
                <th>{t("customers.newConnect.step5.assetType", { defaultValue: "Asset type" })}</th>
                <th>{t("customers.newConnect.step5.size", { defaultValue: "Size" })}</th>
                <th>{t("customers.build.units.col.qty", { defaultValue: "Qty" })}</th>
                <th>{t("customers.build.units.col.assetId", { defaultValue: "Asset ID" })}</th>
                <th>{t("customers.newConnect.step5.workOrder", { defaultValue: "Work order" })}</th>
                <th>{t("customers.build.units.col.state", { defaultValue: "State" })}</th>
                <th>{t("customers.build.units.col.actions", { defaultValue: "Actions" })}</th>
              </tr>
            </thead>
            <tbody>
              {units.map((unit) => (
                <UnitGroup
                  key={unit.unit_id ?? ""}
                  unit={unit}
                  rows={rows.filter((row) => row.unit_id === unit.unit_id)}
                  t={t}
                  typeNames={typeNames}
                  sizeNames={sizeNames}
                  path={path}
                  chosen={chosen}
                  onToggle={toggle}
                  onActivate={canActivate ? props.onActivate : undefined}
                />
              ))}
            </tbody>
          </PlainTable>
        )}
      </Section>
    </>
  );
}

function UnitGroup(props: {
  unit: ActivationRow;
  rows: ActivationRow[];
  t: Translator;
  typeNames: ReadonlyMap<string, string>;
  sizeNames: ReadonlyMap<string, string>;
  path: (segment: string) => string;
  chosen: string[];
  onToggle: (id: string) => void;
  onActivate?: (ids: string[]) => void;
}) {
  const { t, unit } = props;
  return (
    <>
      <tr data-unit-group={unit.unit_label ?? ""} className="bg-neutral-100">
        <th colSpan={11} scope="colgroup" className="text-left">
          <span className="font-semibold">{unit.unit_label}</span>
          {text(unit.unit_type) !== null && (
            <span> · {unitTypeName(unit.unit_type, props.typeNames, t)}</span>
          )}
          <span data-unit-state={unit.unit_state}> · {unitStateWord(unit.unit_state, t)}</span>
          <span> · </span>
          {/* A unit is changed where it lives, so this NAVIGATES. */}
          {unit.unit_id !== null && (
            <Link to={props.path(unitDetailPath(unit.unit_id))} data-open-unit={unit.unit_label ?? ""}>
              {t("customers.build.units.openUnit", { defaultValue: "Open unit" })}
            </Link>
          )}
        </th>
      </tr>
      {props.rows.map((row) => {
        const refusal = rowRefusal(row, t);
        const first = row.assets[0] ?? null;
        const order = row.work_orders.find((one) => one.unit_label !== null) ?? null;
        return (
          <tr key={row.id} data-service-point={row.id} data-ready={row.ready ? "true" : "false"}>
            <td>
              {props.onActivate !== undefined && row.ready && (
                <input
                  type="checkbox"
                  aria-label={t("customers.build.units.choose", {
                    unit: row.unit_label ?? "",
                    defaultValue: `Choose ${row.unit_label ?? ""}`,
                  })}
                  checked={props.chosen.includes(row.id)}
                  onChange={() => props.onToggle(row.id)}
                  data-choose={row.id}
                />
              )}
            </td>
            <td>{row.unit_label}</td>
            <td>{unitTypeName(row.unit_type, props.typeNames, t)}</td>
            <td>{t(`rating.service.${row.service}`, { defaultValue: row.service })}</td>
            <td>{first === null ? null : first.type_name}</td>
            <td data-sizes="">{sizesText(row.assets, props.sizeNames)}</td>
            <td className="tabular-nums">{row.qty === 0 ? null : row.qty}</td>
            <td>
              {row.assets.map((asset) => (
                <span key={asset.id} className="block" data-asset-no={asset.asset_no ?? ""}>
                  {asset.asset_no}
                  {/* ⊕ `DEF-CUS-9840` — several pieces on one row: each number
                      says which size it is (*S-00041 · Solar panel 10 kW*). */}
                  {assetSizeSuffix(row.assets, asset, props.sizeNames)}
                  <span className="text-neutral-700"> · {asset.status_name}</span>
                </span>
              ))}
            </td>
            <td>
              {order === null || order.order_no === null ? null : (
                <Link to={props.path(`/work/orders/${order.id}`)} data-order-no={order.order_no}>
                  {order.order_no}
                </Link>
              )}
            </td>
            <td data-point-state={row.state}>{serviceStateWord(row.state, t)}</td>
            <td>
              {props.onActivate !== undefined && (
                <RowActions>
                  <RowAction
                    label={t("customers.build.units.activate", { defaultValue: "Activate" })}
                    icon={<PowerIcon />}
                    reason={refusal}
                    testId={`activate-${row.id}`}
                    onClick={() => props.onActivate?.([row.id])}
                  />
                </RowActions>
              )}
            </td>
          </tr>
        );
      })}
    </>
  );
}
