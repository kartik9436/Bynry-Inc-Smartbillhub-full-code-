// ── Trace ──────────────────────────────────────────────
// Change:   CR-171-BRC10 P2.04–P2.12 — the pieces every tab of the move-in
//           details view repeats: a titled group (`Panel`), a three-across fact
//           grid (`FactBlock` strip), a value-or-reason cell, a link value, a
//           service list and a date.
// Rules:    B14 rule 43 (a repeated piece is a component, not a copy) · rule 36
//           (the kit is how a screen complies) · rule 31 (ids ride in hrefs) ·
//           rule 33 (a stated absence is ≤ 6 words; the WHY is `title` only)
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FactBlock } from "@/components/FactBlock";
import type { Fact } from "@/components/FactBlock";
import { Panel } from "@/components/Panel";
import { InlineLinkTo } from "@/components/Surfaces";

import type { MoveAbsence } from "../MoveRecordPage";

export interface Regional {
  timeZone: string;
  dateFormat: RegionalDateFormat;
}

/** One titled information group — `Panel`, the detail screen's group (rule 36). */
export function DetailGroup(props: {
  title: string;
  name: string;
  trailing?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Panel title={props.title} trailing={props.trailing} data-move-group={props.name}>
      <div className="mt-3">{props.children}</div>
    </Panel>
  );
}

/** The drawn three-across grid of labelled facts (images 03, 09, 24–26). */
export function FactGrid(props: { name: string; facts: readonly Fact[] }) {
  return <FactBlock name={props.name} facts={props.facts} variant="strip" columns={3} />;
}

/** A value, or the reason there is none — never a dash over nothing. */
export function Stated(props: { absence?: MoveAbsence | null; label: string }) {
  return (
    <span className="font-normal text-neutral-600" title={props.absence?.detail} data-stated="">
      {props.label}
    </span>
  );
}

/** `P-00063 · Kestrel Park ph. 2` — the number links, the words follow. */
export function LinkedValue(props: { to: string | null; label: string | null; rest?: ReactNode }) {
  return (
    <span>
      {props.to !== null && props.label ? (
        <InlineLinkTo to={props.to}>{props.label}</InlineLinkTo>
      ) : (
        props.label
      )}
      {props.rest ? <> · {props.rest}</> : null}
    </span>
  );
}

/**
 * `DEF-CUS-9763` — a unit as images 03–17 draw it: its NUMBER, linked to the
 * unit, then its label (`SCW-U-311 · Unit 4A`) — step 1's form. A unit with no
 * number is named by its label alone, still linked.
 */
export function UnitValue(props: { to: string | null; unit: { unit_no?: string | null; label: string | null } }) {
  const number = props.unit.unit_no ?? null;
  return number ? (
    <LinkedValue to={props.to} label={number} rest={props.unit.label ?? undefined} />
  ) : (
    <LinkedValue to={props.to} label={props.unit.label} />
  );
}

/** A date in the tenant's zone and format (IS-8). */
export function Day(props: { value: string | null | undefined; regional: Regional; withTime?: boolean }) {
  if (!props.value) return null;
  return (
    <DateCell
      value={props.value}
      timeZone={props.regional.timeZone}
      dateFormat={props.regional.dateFormat}
      withTime={props.withTime}
    />
  );
}

/** `Water · Sewer` from codes — the ONE service-name catalogue (`rating.service.*`). */
export function useServiceNames(): (codes: readonly (string | null | undefined)[]) => string {
  const { t } = useTranslation();
  return (codes) =>
    codes
      .filter((code): code is string => typeof code === "string" && code !== "")
      .map((code) => t(`rating.service.${code}`, { defaultValue: code }))
      .join(" · ");
}

/** An empty table's one sentence — never column heads over nothing. */
export function EmptyLine(props: { children: ReactNode }) {
  return <p className="m-0 text-base text-neutral-600">{props.children}</p>;
}

/** `E-5041 · total` → `E-5041`: a read row names the register as meter ·
 *  channel; the opening-reads door and the meter tree speak the METER number. */
export function registerMeter(register: string): string {
  return register.split(" · ")[0] ?? register;
}
