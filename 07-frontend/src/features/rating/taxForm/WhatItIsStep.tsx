// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — step 1 *What it is*, built from images 04–08
//           of `05-prototype/taxes-fees-2026-10-03/images/` (B14 rule 42).
// Defects:  DEF-RAT-9277 P1 (only switched-on services) · P2/P3 (one dropdown,
//           not a line plus an add box) · P4 (the class list opens below its
//           box, over nothing) · P5 (no red capital headings) · P6/P7 (the
//           reach is a count and a table, not a sentence and a run-on list)
// ───────────────────────────────────────────────────────
//
// Two sections: *Name and authority*, and *Who it reaches* with the reach of
// the boundary as it stands. Every list is the server's.
import { CheckDropdown } from "@/components/CheckDropdown";
import { SelectField, TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { StatusPill } from "@/components/StatusPill";
import { PlainTable } from "@/components/Surfaces";

import { PAIR, SECTION_HEADING, isLocked } from "./taxFormShared";
import type { StepProps, Translator } from "./taxFormShared";
import type { MatchedPremises } from "@/api/endpoints";

export function WhatItIsStep(props: StepProps) {
  const { draft, lists, t } = props;
  const needsPlace = lists.placeBoundaries.includes(draft.boundary);
  return (
    <div className="flex flex-col gap-5" data-tax-step="what">
      <Panel as="section" aria-labelledby="tax-sec-name">
        <h2 id="tax-sec-name" className={SECTION_HEADING}>
          {t("rating.taxForm.section.nameAuthority")}
        </h2>
        <div className={PAIR}>
          <TextField
            id="tax-name"
            label={t("rating.taxForm.field.name")}
            required
            value={draft.name}
            placeholder={t("rating.taxForm.placeholder.name")}
            help={t("rating.taxForm.help.name")}
            disabled={isLocked(props, "name")}
            onChange={(name) => props.onChange({ name })}
          />
          <SelectField
            id="tax-authority"
            label={t("rating.taxForm.field.authority")}
            required
            value={draft.jurisdiction}
            placeholder={t("rating.taxForm.placeholder.authority")}
            options={lists.authorities}
            disabled={isLocked(props, "jurisdiction")}
            onChange={(jurisdiction) => props.onChange({ jurisdiction })}
          />
        </div>
      </Panel>

      <Panel as="section" aria-labelledby="tax-sec-reach">
        <h2 id="tax-sec-reach" className={SECTION_HEADING}>
          {t("rating.taxForm.section.reach")}
        </h2>
        <div className="flex flex-col gap-5">
          <div className={needsPlace ? PAIR : ""}>
            <SelectField
              id="tax-boundary"
              label={t("rating.taxForm.field.boundary")}
              value={draft.boundary}
              options={lists.boundaries}
              disabled={isLocked(props, "boundary")}
              onChange={(boundary) => props.onChange({ boundary })}
            />
            {needsPlace && (
              <TextField
                id="tax-place"
                label={t("rating.taxForm.field.place")}
                required
                value={draft.place_name}
                placeholder={t("rating.taxForm.placeholder.place")}
                help={t("rating.taxForm.help.place")}
                disabled={isLocked(props, "place_name")}
                onChange={(place_name) => props.onChange({ place_name })}
              />
            )}
          </div>
          <div className={PAIR}>
            <CheckDropdown
              id="tax-services"
              label={t("rating.taxForm.field.services")}
              allLabel={t("rating.taxForm.allServices")}
              options={lists.services}
              selected={draft.services}
              help={t("rating.taxForm.help.services")}
              disabled={isLocked(props, "services")}
              onChange={(services) => props.onChange({ services })}
            />
            <CheckDropdown
              id="tax-classes"
              label={t("rating.taxForm.field.classes")}
              allLabel={t("rating.taxForm.allClasses")}
              options={lists.classes}
              selected={draft.customer_classes}
              disabled={isLocked(props, "customer_classes")}
              onChange={(customer_classes) => props.onChange({ customer_classes })}
            />
          </div>
          <ReachPreview reach={lists.reach} t={t} />
        </div>
      </Panel>
    </div>
  );
}

/**
 * P6/P7 — the reach as a COUNT and a TABLE: *78 of 84 premises*, a pill for
 * who it misses, and the first rows the server sampled. Rule 33: no sentence
 * explaining how the count was reached; the figure and the rows are the fact.
 */
export function ReachPreview(props: { reach: MatchedPremises | null; t: Translator }) {
  const { reach, t } = props;
  if (reach === null) {
    return (
      <div className="bg-neutral-100 p-4 text-base text-neutral-700" data-tax-reach="counting">
        {t("rating.taxForm.reach.counting")}
      </div>
    );
  }
  const missed = reach.total - reach.count;
  return (
    <div className="border border-divider bg-neutral-100 p-4" data-tax-reach={String(reach.count)}>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="m-0 text-lead text-neutral-700">
          <span className="font-heading text-h4 text-text">{reach.count}</span>{" "}
          {t("rating.taxForm.reach.ofTotal", { total: reach.total })}
        </p>
        {!reach.resolvable ? (
          <StatusPill tone="danger">{t("rating.taxForm.reach.unresolvable")}</StatusPill>
        ) : missed === 0 ? (
          <StatusPill tone="success">{t("rating.taxForm.reach.every")}</StatusPill>
        ) : (
          <StatusPill tone="warning">{t("rating.taxForm.reach.notReached", { count: missed })}</StatusPill>
        )}
      </div>
      {reach.sample.length > 0 && (
        <div className="border border-divider bg-surface">
          <PlainTable>
            <thead>
              <tr>
                <th scope="col">{t("rating.taxForm.reach.col.premises")}</th>
                <th scope="col">{t("rating.taxForm.reach.col.address")}</th>
                <th scope="col">{t("rating.taxForm.reach.col.city")}</th>
              </tr>
            </thead>
            <tbody>
              {reach.sample.map((row) => (
                <tr key={row.id}>
                  <td>{row.premise_no ?? "—"}</td>
                  <td>{row.address_line ?? "—"}</td>
                  <td>{row.city ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        </div>
      )}
    </div>
  );
}
