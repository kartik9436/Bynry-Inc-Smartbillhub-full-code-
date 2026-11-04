// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 2 task 5 — step 2 *Services*, built from images
//           08–12 of `05-prototype/plans-2026-10-03/images/` (B14 rule 42).
// Rules:    ruling 6 (full-size controls in the row, a red × to remove, *+ Add
//           service* under the table, disabled with *All added.* when nothing
//           is left; an empty row refused by name) · ruling 7 (the row shows
//           the base — $ and base code — and the minimum from the picked
//           schedule, with the monthly base total under the table; no base
//           section on Charges) · ruling 8 (version pill and *from* date on the
//           schedule and the base code) · ruling 12 (*Base charges*, *Monthly
//           base charges*)
// ───────────────────────────────────────────────────────
//
// ⚠ **THE BASE IN THE ROW IS THE CODE THE BILL CHARGES (`DEF-RAT-9336`).** It
// is the schedule option's `base` as the server resolved it — the schedule's
// named code, else the class-narrowed base code — never every base code of the
// service in the catalogue.
import { AffixField } from "@/components/AffixField";
import { SelectField, useFieldError } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { CellSelect, CellStatic, CellTick, TableArray } from "@/components/TableArray";
import type { TableArrayColumn } from "@/components/TableArray";

import { RefVersion, moneyShown } from "../planSections/PlanSections";
import { sortBySize } from "../sizeOrder";
import {
  allAdded,
  monthlyBaseShown,
  newServiceRow,
  scheduleOf,
  schedulesFor,
  stillOffered,
} from "./planFormModel";
import type { PlanServiceRow } from "./planFormModel";
import { PAIR, SECTION_HEADING, isLocked } from "./planFormShared";
import type { PlanStepProps } from "./planFormShared";

export function ServicesStep(props: PlanStepProps) {
  return (
    <div className="flex flex-col gap-5" data-plan-step="services">
      <ServicesTable {...props} />
      <OutsideCitySection {...props} />
    </div>
  );
}

export function ServicesTable(props: PlanStepProps) {
  const { draft, lists, t } = props;
  const options = lists.options;
  const error = useFieldError("plan-services");
  const picked = draft.services.map((row) => row.service);
  const surchargeOn = draft.outside_city === "yes";
  const monthly = monthlyBaseShown(draft, options);

  function setRow(index: number, patch: Partial<PlanServiceRow>): void {
    props.onChange({ services: draft.services.map((row, i) => (i === index ? { ...row, ...patch } : row)) });
  }

  const columns: TableArrayColumn<PlanServiceRow>[] = [
    {
      key: "service",
      label: t("rating.planForm.col.service"),
      cell: (row, index) => {
        const service = options.services.find((option) => option.value === row.service);
        return (
          <span className="flex flex-col gap-1">
            <CellSelect
              name="service"
              label={t("rating.planForm.col.service")}
              value={row.service}
              placeholder={t("rating.planForm.placeholder.service")}
              options={stillOffered(options.services, picked, row.service)}
              onChange={(service) => setRow(index, { service, schedule: "" })}
            />
            {service?.gl !== null && service?.gl !== undefined && (
              <span className="text-sm text-neutral-700" data-service-gl="">
                {t("rating.planSections.service.gl", { code: service.gl.code })}
              </span>
            )}
          </span>
        );
      },
    },
    {
      key: "schedule",
      label: t("rating.planForm.col.schedule"),
      cell: (row, index) => {
        const chosen = scheduleOf(options, row.schedule);
        return (
          <span className="flex flex-col">
            <CellSelect
              name="schedule"
              label={t("rating.planForm.col.schedule")}
              value={row.schedule}
              placeholder={
                row.service === "" ? t("rating.planForm.placeholder.serviceFirst") : t("rating.planForm.placeholder.schedule")
              }
              blockedReason={row.service === "" ? t("rating.planForm.placeholder.serviceFirst") : undefined}
              options={schedulesFor(options, row.service).map((schedule) => ({
                value: schedule.ref.id,
                // DEF-RAT-9502 — the model in the catalogue's word (`rating.model.*`).
                label:
                  schedule.ref.model_label === null
                    ? schedule.ref.name
                    : `${schedule.ref.name} · ${t(`rating.model.${schedule.ref.model}`, { defaultValue: schedule.ref.model_label })}`,
              }))}
              onChange={(schedule) => setRow(index, { schedule })}
            />
            {chosen !== undefined && (
              <RefVersion item={chosen.ref} t={t} dateFormat={lists.dateFormat} timeZone={lists.timeZone} />
            )}
          </span>
        );
      },
    },
    {
      key: "base",
      label: t("rating.planForm.col.baseCharges"),
      cell: (row) => {
        const base = scheduleOf(options, row.schedule)?.base;
        if (base === undefined) return <CellStatic name="base">—</CellStatic>;
        if (base.state !== "ok" || base.code === null) {
          // `DEF-RAT-9351` — a base the plan's classes do not settle is NAMED
          // (its codes, as the shared sections name them), never a silent $0.00.
          return (
            <span className="flex flex-col" data-cell="base">
              <span className="font-semibold">
                {base.state === "ambiguous" || base.state === "not_named"
                  ? t("rating.planSections.service.baseChooseCode")
                  : t("rating.planSections.none")}
              </span>
              {/* `DEF-RAT-9832` — the schedule names none, so the bill charges $0.00. */}
              {base.state === "not_named" && base.flat_display !== null && (
                <span className="text-sm text-neutral-700">{moneyShown(base.flat_display, lists.currency)}</span>
              )}
              {base.codes.length > 0 && <span className="text-sm text-neutral-700">{base.codes.join(", ")}</span>}
            </span>
          );
        }
        return (
          <span className="flex flex-col" data-cell="base">
            <span className="font-semibold">{moneyShown(base.flat_display ?? sortBySize(base.by_size, (size) => size.size_label)[0]?.amount_display ?? null, lists.currency)}</span>
            <span className="text-sm text-neutral-700">{base.code.code}</span>
            <RefVersion item={base.code} t={t} dateFormat={lists.dateFormat} timeZone={lists.timeZone} />
          </span>
        );
      },
    },
    {
      key: "minimum",
      label: t("rating.planForm.col.minimum"),
      numeric: true,
      cell: (row) => {
        const schedule = scheduleOf(options, row.schedule);
        if (schedule === undefined) return <CellStatic name="minimum">—</CellStatic>;
        const minimum =
          schedule.minimum.flat_display ??
          sortBySize(schedule.minimum.by_size, (size) => size.size_label)[0]?.amount_display ??
          null;
        return (
          <CellStatic name="minimum">
            {minimum === null ? t("rating.planSections.none") : moneyShown(minimum, lists.currency)}
          </CellStatic>
        );
      },
    },
    {
      key: "surcharge",
      label: t("rating.planForm.field.surcharge"),
      cell: (row, index) => (
        <CellTick
          name="surcharge"
          label={t("rating.planForm.field.surcharge")}
          checked={surchargeOn && row.surcharged}
          blockedReason={!surchargeOn || row.service === "" ? t("rating.planForm.reason.surchargeOff") : undefined}
          onChange={(surcharged) => setRow(index, { surcharged })}
        />
      ),
    },
  ];

  const full = allAdded(options.services.length, draft.services.length);
  return (
    <TableArray<PlanServiceRow>
      title={t("rating.planForm.section.services")}
      fact={t("rating.planForm.fact.switchedOn", { count: draft.services.filter((row) => row.service !== "").length, total: options.services.length })}
      collection="plan-services"
      columns={columns}
      rows={draft.services}
      rowKey={(row) => row.key}
      emptyText={t("rating.planForm.empty.services")}
      note={error}
      onChange={(services) => props.onChange({ services })}
      removeLabel={t("rating.planForm.remove")}
      actions={
        isLocked(props, "services")
          ? []
          : [
              {
                key: "add-service",
                label: t("rating.planForm.add.service"),
                onClick: () => props.onChange({ services: [...draft.services, newServiceRow()] }),
                blockedReason: full ? t("rating.planForm.allAdded") : undefined,
                showReason: true,
              },
            ]
      }
      footerTrailing={
        <span className="flex flex-col items-end gap-1">
          <span className="flex gap-6 text-base" data-plan-monthly="">
            <span className="font-semibold text-neutral-700">{t("rating.planForm.monthlyBase")}</span>
            <span className="font-semibold tabular-nums">{moneyShown(monthly, lists.currency)}</span>
          </span>
          <a
            className="font-semibold text-accent underline"
            href={lists.servicesSettingsHref}
            target="_blank"
            rel="noopener noreferrer"
          >
            {t("rating.planForm.link.moreServices")}
          </a>
        </span>
      }
    />
  );
}

export function OutsideCitySection(props: PlanStepProps) {
  const { draft, t } = props;
  return (
    <Panel as="section" aria-labelledby="plan-sec-outside">
      <h2 id="plan-sec-outside" className={SECTION_HEADING}>
        {t("rating.planForm.section.outside")}
      </h2>
      <div className={PAIR}>
        <SelectField
          id="plan-outside"
          label={t("rating.planForm.field.outside")}
          value={draft.outside_city}
          options={[
            { value: "no", label: t("rating.planForm.outside.no") },
            { value: "yes", label: t("rating.planForm.outside.yes") },
          ]}
          disabled={isLocked(props, "outside_city")}
          onChange={(value) => props.onChange({ outside_city: value === "yes" ? "yes" : "no" })}
        />
        {draft.outside_city === "yes" && (
          <AffixField
            id="plan-surcharge"
            label={t("rating.planForm.field.surcharge")}
            required
            value={draft.outside_city_percent}
            affix="%"
            side="end"
            help={t("rating.planForm.help.surcharge")}
            disabled={isLocked(props, "outside_city_percent")}
            onChange={(outside_city_percent) => props.onChange({ outside_city_percent })}
          />
        )}
      </div>
    </Panel>
  );
}
