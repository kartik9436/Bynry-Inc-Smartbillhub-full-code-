// ── Trace ──────────────────────────────────────────────
// Change:   CR-177-BRC10 tasks 12 and 13 — step 3, *Check before saving*: one
//           table grouped under the form's own headings (Address, Property,
//           Owner, Area & sub-area, Custom fields, Units), an Edit on every row
//           that goes back to its step, "—" for an empty value, and one line
//           saying what will be created; and the *This premise* card beside
//           every step.
// Rules:    B14 rule 31 (names and numbers, never an id or a code) · B14 rules
//           32/33 (one outcome line, no explanation) · BR-MET-1165 (the number
//           is previewed, nothing is reserved)
// Drawing:  05-prototype/add-premise-2026-10-09/images/01, 11, 12
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";

import type { CustomFieldRegistryEntry, LookupEntry, PremisesType, RouteRow, TenantServiceRow } from "@/api/endpoints";
import { displayValue } from "@/components/CustomFields";
import { Panel } from "@/components/Panel";
import { InlineLink, PlainTable } from "@/components/Surfaces";

import { addressCheckKey, composeAddress, commonAreaLabels, linkedOwner, outcomeLine, pointText, unitLabels } from "./addPremiseModel";
import type { AddPremiseForm, AddressCheck, OwnerState } from "./addPremiseModel";
import { SECTION_HEADING } from "./addPremiseShared";
import type { Translator } from "./addPremiseShared";
import { areaName, cityLimitsWord, routeWord } from "./PropertyStep";
import { unitTypeWord } from "./UnitsStep";

const DASH = "—";

export interface ReviewContext {
  form: AddPremiseForm;
  premiseNumber: string | null;
  check: AddressCheck;
  owner: OwnerState;
  types: readonly PremisesType[];
  services: readonly TenantServiceRow[];
  routes: readonly RouteRow[];
  areas: readonly LookupEntry[];
  customFields: readonly CustomFieldRegistryEntry[];
  formatDate: (iso: string) => string;
  t: Translator;
}

export interface ReviewRow {
  id: string;
  label: string;
  value: ReactNode;
  /** The step the Edit link opens; `null` draws no Edit (the premise number). */
  step: 1 | 2 | null;
}

export interface ReviewGroup {
  id: string;
  title: string;
  rows: ReviewRow[];
}

/** The services' NAMES, in the utility's order, joined as the drawing does. */
export function servicesWords(form: AddPremiseForm, services: readonly TenantServiceRow[]): string {
  const names = services.filter((row) => form.services.includes(row.service)).map((row) => row.name);
  return names.length === 0 ? DASH : names.join(" · ");
}

export function typeWord(form: AddPremiseForm, types: readonly PremisesType[]): string {
  if (form.premises_type === "") return DASH;
  return types.find((type) => type.code === form.premises_type)?.name ?? form.premises_type;
}

export function routeLabel(form: AddPremiseForm, routes: readonly RouteRow[], t: Translator): string {
  const row = routes.find((one) => one.code === form.route);
  return row === undefined ? DASH : routeWord(row, t);
}

export function reviewGroups(ctx: ReviewContext): ReviewGroup[] {
  const { form, t, check } = ctx;
  const or = (text: string | null | undefined) => (text === null || text === undefined || text.trim() === "" ? DASH : text);
  const owner = linkedOwner(ctx.owner);
  const cycle = ctx.routes.find((row) => row.code === form.route)?.cycle_code ?? null;
  const units = unitLabels(form.unit_count);
  const areas = commonAreaLabels(form);

  const address: ReviewRow[] = [
    { id: "number", label: t("metering.addPremise.review.premiseNumber"), value: or(ctx.premiseNumber), step: null },
    { id: "address", label: t("metering.addPremise.dup.address"), value: or(composeAddress(form)), step: 1 },
  ];
  if (check.kind === "match" && check.used) {
    address.push(
      { id: "parcel", label: t("metering.addPremise.check.parcel"), value: or(check.match.parcel), step: 1 },
      { id: "point", label: t("metering.addPremise.check.point"), value: or(pointText(check.match.lat, check.match.lng)), step: 1 },
      {
        id: "checked",
        label: t("metering.premises.gis.label"),
        value: t("metering.addPremise.map.checkedOn", { date: ctx.formatDate(check.checkedOn) }),
        step: 1,
      },
    );
  } else {
    address.push({ id: "check", label: t("metering.addPremise.summary.check"), value: t(addressCheckKey(check)), step: 1 });
  }

  const groups: ReviewGroup[] = [
    { id: "address", title: t("metering.addPremise.section.address"), rows: address },
    {
      id: "property",
      title: t("metering.addPremise.step.property"),
      rows: [
        { id: "type", label: t("metering.premises.field.type"), value: typeWord(form, ctx.types), step: 1 },
        {
          id: "limits",
          label: t("metering.premises.field.jurisdiction"),
          value: form.inside_city_limits === null ? DASH : cityLimitsWord(form.inside_city_limits, t),
          step: 1,
        },
        { id: "services", label: t("metering.addPremise.field.services"), value: servicesWords(form, ctx.services), step: 1 },
      ],
    },
    {
      id: "owner",
      title: t("metering.addPremise.owner.title"),
      rows: [
        {
          id: "master",
          label: t("metering.addPremise.owner.field"),
          value:
            owner === null
              ? t("metering.premises.owner.needs_owner")
              : [owner.name, owner.account_no].filter(Boolean).join(" · ") || DASH,
          step: 1,
        },
      ],
    },
    {
      id: "area",
      title: t("metering.addPremise.area.title"),
      rows: [
        { id: "area", label: t("metering.premises.field.area"), value: or(areaName(ctx.areas, form.area.top)), step: 1 },
        { id: "sub", label: t("metering.premises.field.subArea"), value: or(areaName(ctx.areas, form.area.sub)), step: 1 },
        { id: "route", label: t("metering.premises.field.readRoute"), value: routeLabel(form, ctx.routes, t), step: 1 },
        {
          id: "cycle",
          label: t("metering.premises.field.billingCycle"),
          value:
            form.route === "" || cycle === null
              ? t("metering.premises.cycle.followsRoute")
              : t("metering.premises.cycle.named", { cycle }),
          step: 1,
        },
      ],
    },
    {
      id: "custom",
      title: t("metering.addPremise.custom.title"),
      rows: ctx.customFields.map((field) => ({
        id: `cf-${field.key}`,
        label: field.label,
        value: or(displayValue(field, form.custom_data, ctx.formatDate, t)),
        step: 1 as const,
      })),
    },
    {
      id: "units",
      title: t("metering.addPremise.units.title"),
      rows: [
        {
          id: "units",
          label: t("metering.addPremise.units.title"),
          value:
            units.length === 0
              ? "0"
              : form.unit_type === ""
                ? String(units.length)
                : `${units.length} · ${unitTypeWord(form.unit_type, t)}`,
          step: 2,
        },
        {
          id: "common",
          label: t("metering.premises.commonAreas.label"),
          value: areas.length === 0 ? t("metering.addPremise.common.none") : areas.join(" · "),
          step: 2,
        },
      ],
    },
  ];
  return groups.filter((group) => group.rows.length > 0);
}

export function ReviewStep(props: { ctx: ReviewContext; onEdit: (step: 1 | 2) => void }) {
  const { ctx, onEdit } = props;
  const { t } = ctx;
  const outcome = outcomeLine(ctx.form);
  return (
    <div className="flex flex-col gap-5" data-add-premise-step="review">
      <Panel as="section" aria-labelledby="add-premise-check">
        <h2 id="add-premise-check" className={SECTION_HEADING}>
          {t("metering.addPremise.review.title")}
        </h2>
        <div className="border border-divider">
          <PlainTable>
            <tbody>
              {reviewGroups(ctx).flatMap((group) => [
                <tr key={`g-${group.id}`} data-review-group={group.id}>
                  <th
                    scope="colgroup"
                    colSpan={2}
                    className="bg-neutral-200 text-left font-heading text-xs font-semibold uppercase tracking-kicker"
                  >
                    {group.title}
                  </th>
                </tr>,
                ...group.rows.map((row) => (
                  <tr key={`${group.id}-${row.id}`} data-review-row={row.id}>
                    <th scope="row" className="w-48 bg-neutral-100 font-normal text-neutral-700">
                      {row.label}
                    </th>
                    <td>
                      <span>{row.value}</span>
                      {row.step !== null && (
                        <>
                          {" "}
                          <InlineLink
                            className="ml-2 text-sm"
                            aria-label={t("metering.addPremise.review.editRow", { field: row.label })}
                            onClick={() => onEdit(row.step as 1 | 2)}
                          >
                            {t("metering.addPremise.review.edit")}
                          </InlineLink>
                        </>
                      )}
                    </td>
                  </tr>
                )),
              ])}
            </tbody>
          </PlainTable>
        </div>
      </Panel>
      <p className="m-0 bg-info-100 px-3 py-3 text-base text-info-700" data-add-premise-outcome={outcome.count}>
        {t(outcome.key, { count: outcome.count })}
      </p>
    </div>
  );
}

/** *This premise* — beside every step (image 01). */
export function PremiseSummaryCard(props: { ctx: ReviewContext }) {
  const { ctx } = props;
  const { t, form } = ctx;
  const owner = linkedOwner(ctx.owner);
  const units = unitsShown(form);
  const facts: [string, string, string][] = [
    ["type", t("metering.addPremise.summary.type"), typeWord(form, ctx.types)],
    ["check", t("metering.addPremise.summary.check"), t(addressCheckKey(ctx.check))],
    ["services", t("metering.addPremise.field.services"), servicesWords(form, ctx.services)],
    ["units", t("metering.addPremise.units.title"), units],
    ["owner", t("metering.addPremise.owner.title"), owner?.name ?? owner?.account_no ?? t("metering.premises.owner.needs_owner")],
    ["route", t("metering.addPremise.summary.route"), form.route === "" ? DASH : routeLabel(form, ctx.routes, t)],
  ];
  const address = composeAddress(form);
  return (
    <Panel as="aside" aria-label={t("metering.addPremise.summary.kicker")} data-add-premise-summary="">
      <p className="m-0 font-heading text-xs font-semibold uppercase tracking-kicker text-neutral-700">
        {t("metering.addPremise.summary.kicker")}
      </p>
      <p className="m-0 mt-3 font-heading text-metric-lg font-semibold" data-add-premise-summary-number="">
        {ctx.premiseNumber ?? DASH}
      </p>
      <p className="m-0 mt-2 text-lead text-neutral-700">{address === "" ? t("metering.addPremise.summary.noAddress") : address}</p>
      <dl className="m-0 mt-4 flex flex-col gap-2 border-t border-divider pt-4">
        {facts.map(([id, label, value]) => (
          <div key={id} className="flex items-baseline justify-between gap-3 text-base" data-add-premise-summary-fact={id}>
            <dt className="text-neutral-700">{label}</dt>
            <dd className="m-0 text-right font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function unitsShown(form: AddPremiseForm): string {
  return String(unitLabels(form.unit_count).length);
}
