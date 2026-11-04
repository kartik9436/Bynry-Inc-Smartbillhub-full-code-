// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave F · F6 (`PUJ-44`, `PUJ-45`) — a unit has an edit screen
//          of its own, and its plan is applied or changed from that same form.
// Story:   US-MET-002 (S15 unit detail)
// Rules:   BR-MET-095 (a unit MAY move, on its own dated screen —
//          SUPERSEDES-REFINES BR-MET-046, and this form no longer says
//          otherwise: `DEF-MET-4762`) ·
//          BR-MET-118 (a unit's services ARE its premises', inherited LIVE —
//          PO 2026-09-10) · BR-MET-1162 (a unit may carry its own point) ·
//          BR-MET-036 (occupancy is DERIVED — stated, never editable) ·
//          BR-MET-101 (a common area IS a unit with a flag) ·
//          BR-MET-007 / BR-CUS-014 (a unit's default plan) ·
//          BR-MET-040 (the plan lock) · BR-MET-042 (a direct plan edit on an
//          OCCUPIED unit is an error-correction OVERRIDE the SERVER warns
//          about — this form shows the warning it is given and decides nothing) ·
//          BR-RAT-030 (an unpublished plan is not assignable) ·
//          BR-SHL-033 (a long list is the searchable control; a date is a
//          picker) · B14 rule 32 (one sentence per section) · B14 rule 31 (no
//          database id is ever the visible value of a field) · B14 rule 37 (a
//          drawn figure is an illustration) · B14 rule 38 (where a drawing and
//          our UI rules disagree about how a FORM IS BUILT, the rules win).
// Drawn:   04-docs/05-modules/04-metering/conformance/CR-089-p087-edit-a-unit.md
// Defects: DEF-MET-4731 (two edit forms) · DEF-MET-4762 (a retired rule still
//          on screen) · DEF-MET-4763 (the frame was never diffed)
// ───────────────────────────────────────────────────────
//
// ── WHY THIS FILE EXISTS AT ALL ─────────────────────────────────────────────
//
// PO 2026-09-08, verbatim: *"youa re not allowing to add plan here from drop
// down - we shuld attached plans and it should be options, when I edit it later
// you should allow to change the plan ot apply the plan"*.
//
// **A unit had no edit screen.** The pencil lived on the units LIST, so a label,
// a floor and a floor area could be changed from a table and not from the unit
// itself — which is where a person is standing when they notice the label is
// wrong. And the plan lived on a third surface again, the Plan tab's own modal.
// So *rename this flat and put it on the right plan* was a list, a row action
// and a tab.
//
// ── ONE WRITE, NOT TWO BEHIND ONE BUTTON ───────────────────────────────────
//
// The obvious build is two calls on Save: `PATCH /units/{id}` for the fields and
// `POST /units/{id}/plan` for the plan. It is wrong for a reason that only shows
// up on the bad day: when the second call is refused — an unpublished plan, a
// locked unit — the clerk is left with a RENAMED unit, an error message about a
// plan, and no way to tell which half landed.
//
// So the plan rides the PATCH as a nested `plan` block, applied inside the same
// transaction by the same `services._apply_unit_plan` the create and the plan
// modal call. A refusal takes the label change back with it.
//
// ⚠ **`plan` WAS ALREADY ACCEPTED ON THAT ENDPOINT AND WAS SILENTLY DROPPED.**
// `_validate_unit`'s `ignored` set has carried `"plan"` since S16 so the CREATE
// payload could be handed to it whole; on a PATCH nothing read it. A PATCH
// carrying a plan answered **200**, changed the label, left the plan exactly as
// it was and said nothing — `DEF-836`'s silent-drop shape, on a money path.
// That is fixed in `services.update_unit`, and this form is its only caller.
//
// ── WHAT THIS DELIBERATELY DOES NOT DO ─────────────────────────────────────
//
// ⛔ **IT DOES NOT OFFER A UNIT-LEVEL SERVICES CONTROL, AND THE ABSENCE IS
// STATED RATHER THAN LEFT AS A GAP.** `BR-MET-118`, re-confirmed by the PO on
// 2026-09-10, verbatim: *"no they will do it on Premises - if it is change on
// premises all units will inherit it."* The `U10` frame draws removable per-unit
// service chips, which presume a unit-level list a clerk can subtract from;
// there is no such column and there is no override. So the building's list is
// drawn READ-ONLY with one sentence saying where it comes from (B14 rule 32's
// stated absence), and the drawing is amended rather than followed.
//
// ⚠ **THAT SENTENCE IS A PROMISE, SO THE READ-THROUGH IS VERIFIED AND NOT
// ASSUMED (hard-won law 1).** `selectors.unit_detail_dict` reads
// `unit.premises.services_available` at READ TIME — there is no `services`
// column on `units` in the model or in any migration, and `_validate_unit`
// never writes one — so a change on the building reaches every unit under it on
// the next read. `UnitEditForm.dom.test.tsx` asserts the screen renders the
// premises' list rather than anything of the unit's own.
//
// ── WHAT IT NOW DOES THAT IT DID NOT ───────────────────────────────────────
//
// ⚠ **IT IS THE ONLY EDIT FORM A UNIT HAS (`DEF-MET-4731` CLOSED).**
// `UnitsListPage.tsx` declared a SECOND, private `UnitEditModal` — same
// endpoint, five of the same fields, `is_common_area` which this form did not
// have, and no plan block, which this form did. The blueprint says the units
// list pencil *"opens the same form"*; it did not, and two forms writing one
// endpoint is the shape that drifts. The list now imports this one, and
// `is_common_area` moved here with it.
//
// ⚠ **AND THE POINT OFFER RIDES THE SAME PATCH.** `BR-MET-1162` lets a unit
// carry its own `lat`/`lng`, and the `U10` frame draws that as an OFFER inside
// `WHERE IT IS` rather than as two empty boxes on every unit — *"almost none
// should"*. The coordinates go out in the SAME `PATCH /units/{id}` as the label
// and the plan, for the reason the plan block is there: two writes behind one
// Save leaves a clerk with half an edit and an error about the other half.

import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { ReactNode } from "react";
import { z } from "zod";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { CityGisNote, useCityGis } from "@/features/metering/CityGis";
import { getUnitPlanOptions, updateUnit } from "@/api/endpoints";
import type { UnitRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { Chip } from "@/components/Chip";
import {
  DatePickerField,
  FormModal,
  SearchSelectField,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Note } from "@/components/TextBits";
import { CustomFieldsInput, customDataChanges } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import type { Translator } from "@/features/tenancy/settingsShared";

import { toEnvelope } from "./PremisesListPage";
import {
  UNIT_TYPES,
  planOverrideWarningKey,
  planPickerOptions,
  unitPlanOptionsKey,
} from "./UnitsListPage";
import { ServiceTags, useRegional } from "./meteringShared";
import type { RegionalProps } from "./meteringShared";

/**
 * What a clerk calls this unit on a form that edits it — the LABEL first.
 *
 * B14 rule 31 is about database ids and `unit_no` is not one: it is a printed
 * reference off the tenant's own series. It is still the wrong FIRST choice
 * here, because the frame draws the thing written on the door and that is the
 * label. The series number answers when there is no label at all.
 */
export function unitFormTitle(unit: UnitRow, t: Translator): string {
  return unit.label ?? unit.unit_no ?? t("metering.units.noNumber");
}

/**
 * The `WHERE IT IS` panel's one sentence — which point is in force, and whose.
 *
 * ⚠ **IT READS THE FORM'S STATE AND NOT ONLY THE SERVER'S**, because the offer
 * is part of the same unsaved edit: a clerk who has just pressed *Give this
 * unit its own point* must see the sentence change before they save, or the
 * button looks dead (hard-won law 2's mirror). `unit.point.source` is still the
 * only definition of the FALLBACK; this adds the not-yet-saved case in front of
 * it rather than recomputing it.
 */
export function pointSentence(
  unit: UnitRow,
  own: boolean,
  lat: string,
  lng: string,
  t: Translator,
): string {
  if (own) {
    return t("metering.units.point.usingOwn", { lat: lat || "—", lng: lng || "—" });
  }
  if (unit.point.lat === null || unit.point.lng === null) {
    return t("metering.units.point.noneYet");
  }
  return t("metering.units.point.usingPremises", {
    premise: unit.premise_address ?? unit.premise_no ?? "",
    lat: unit.point.lat,
    lng: unit.point.lng,
  });
}

/**
 * The four group headings the `U10` frame draws, in the drawn order.
 *
 * ⚠ **THE ORDER AND THE PRESENCE ARE THE DELIVERABLE, WHICH IS WHY THIS IS AN
 * ARRAY AND NOT FOUR HEADINGS TYPED INTO THE JSX** — the same reasoning
 * `PREMISES_FORM_SECTIONS` carries one file over, and `UnitEditForm.dom.test
 * .tsx` reads the rendered headings back against it.
 *
 * ⚠ **FOUR, THOUGH THE BLUEPRINT'S OWN `COGNITIVE LOAD` ROW SAYS THREE.** The
 * frame draws four; the PO ruled on 2026-09-10 that the frame wins and the
 * sentence gets corrected. Recorded in the conformance file, not resolved here.
 */
export const UNIT_FORM_SECTIONS = [
  { id: "name", labelKey: "metering.units.section.name", optional: false },
  // `optional`, as drawn: a unit almost never needs a point of its own.
  { id: "where", labelKey: "metering.units.section.where", optional: true },
  { id: "capacity", labelKey: "metering.units.section.capacity", optional: false },
  // `optional`, as drawn — and the section's own sentence says what it costs to
  // skip it: a unit with no plan cannot be billed.
  { id: "charged", labelKey: "metering.units.section.charged", optional: true },
] as const;

/**
 * One heading and the controls under it.
 *
 * ⚠ **NO TAILWIND UTILITY IN THIS FILE, AND THAT IS NOT AN OVERSIGHT.**
 * `UnitEditModal.tsx` is not on `src/styles/route-b-migrated.txt`, and B14 rule
 * 21's migration clause is per FILE: a utility written here would be a class no
 * stylesheet declares — it renders as NOTHING while `tsc`, eslint and every
 * `toContain` assertion pass over it. So the heading is an unclassed `<h4>`,
 * which is what rule 21 is actually asking for, and the `optional` pill is the
 * KIT's `Chip`, whose classes are emitted from a file that IS on the list.
 */
function Section(props: {
  id: string;
  label: string;
  optional?: boolean;
  optionalLabel: string;
  children: ReactNode;
}) {
  return (
    <section data-unit-section={props.id}>
      <h4>
        {props.label} {props.optional === true ? <Chip>{props.optionalLabel}</Chip> : null}
      </h4>
      {props.children}
    </section>
  );
}

/**
 * The shape `PATCH /units/{id}` answers with when a plan block was sent — the
 * server's own `plan_assignment`, forwarded. **Absent when no plan was sent and
 * `null` when one was and the helper had nothing to say**, so a caller can tell
 * *I did not ask* from *I asked and nothing came back*; collapsing the two is
 * how a screen comes to report an override warning it never received.
 */
interface UnitPatchAnswer {
  plan_assignment?: { warning?: { code: string } | null } | null;
}

export function UnitEditModal(props: {
  unit: UnitRow;
  client: ApiClient;
  regional: RegionalProps;
  onClose: () => void;
  /** `warningKey` is `BR-MET-042`'s override sentence, or null. */
  onSaved: (warningKey: string | null) => void;
}) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const { dateFormat } = useRegional(props.regional);
  const [values, setValues] = useState({
    label: props.unit.label ?? "",
    unit_type: props.unit.unit_type ?? "",
    floor_label: props.unit.floor_label ?? "",
    square_feet: props.unit.square_feet === null ? "" : String(props.unit.square_feet),
    // `BR-MET-101` — the flag that separates a common area from a vacant unit
    // billed to the owner. It arrived here with `DEF-MET-4731`: the units
    // list's private copy of this form had it and this one did not.
    is_common_area: props.unit.is_common_area ? "yes" : "no",
    // ⚠ **THE PLAN PICKER STARTS ON THE PLAN THE UNIT IS ALREADY ON**, so
    // Save with nothing touched sends the same plan and changes nothing that
    // matters. Starting it EMPTY would have read as *no plan* to a clerk
    // glancing at a form they opened to fix a floor number.
    tariff_id: props.unit.rate_plan_id ?? "",
    effective_from: "",
    reason: "",
  });

  // ── `BR-MET-1162` — the unit's OWN point, offered rather than assumed ────
  // Three pieces of state and no fourth: whether the boxes are showing, what is
  // in them, and whether the clerk has touched the point at all. The last one is
  // what keeps `lat`/`lng` OUT of the payload on a form opened to fix a floor
  // label — sending them unchanged would write the same numbers back and stamp
  // an audit row for a change nobody made.
  const [pointOwn, setPointOwn] = useState(props.unit.point.source === "unit");
  const [pointTouched, setPointTouched] = useState(false);
  const [lat, setLat] = useState(props.unit.lat ?? "");
  const [lng, setLng] = useState(props.unit.lng ?? "");
  // `CR-161-BRC10` W3 · `DEF-MET-9227` — the unit's own fields, re-opened on
  // what the server stored; the save sends only what changed.
  const openedCustom = props.unit.custom_data ?? {};
  const [customData, setCustomData] = useState<CustomFieldValues>(openedCustom);

  // GIS Lane D (`DEF-MET-10003`) — is a City GIS in use here?
  const city = useCityGis(props.client);
  const plansQuery = useQuery({
    // The SAME key the Plan tab's modal uses, so the two doors share one
    // cached list rather than each fetching 500 plans.
    queryKey: unitPlanOptionsKey,
    queryFn: () => getUnitPlanOptions({ per: 500 }, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const planChanged = values.tariff_id !== "" && values.tariff_id !== (props.unit.rate_plan_id ?? "");

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const answer = (await updateUnit(
        props.unit.id,
        {
          label: values.label,
          unit_type: values.unit_type === "" ? null : values.unit_type,
          floor_label: values.floor_label,
          square_feet: values.square_feet === "" ? null : values.square_feet,
          is_common_area: values.is_common_area === "yes",
          // ALWAYS sent, even empty, so a required field placed Input here can
          // refuse a save that leaves it blank (`CR-161-BRC10` W3).
          custom_data: customDataChanges(openedCustom, customData),
          // ⚠ **BOTH COORDINATES OR NEITHER, AND ONLY WHEN TOUCHED.** The
          // server refuses half a point by name (`metering.unit
          // .point_needs_both`), because half a point is neither placed nor
          // fallen back and the rule has no third state.
          ...(pointTouched
            ? { lat: lat.trim() === "" ? null : lat.trim(), lng: lng.trim() === "" ? null : lng.trim() }
            : {}),
          // ⚠ **THE BLOCK IS OMITTED WHEN THE PLAN DID NOT MOVE**, and that is
          // not a saving — `_apply_unit_plan` writes a `unit_plan_assignments`
          // history row and an audit row on EVERY call (`BR-CUS-013`), so
          // sending the unchanged plan would stamp a plan change every time a
          // clerk fixed a typo in a floor label, and the unit's plan history
          // would fill with changes nobody made.
          ...(planChanged
            ? {
                plan: {
                  tariff_id: values.tariff_id,
                  effective_from:
                    values.effective_from === "" ? undefined : values.effective_from,
                  reason: values.reason === "" ? undefined : values.reason,
                },
              }
            : {}),
        },
        props.client,
      )) as unknown as UnitPatchAnswer;
      const warning = answer.plan_assignment?.warning ?? null;
      props.onSaved(planOverrideWarningKey(warning ?? null));
      return { ok: true };
    } catch (error) {
      return { ok: false, error: toEnvelope(error) };
    }
  }

  return (
    <FormModal
      // ⚠ **THE LABEL, NEVER THE ID (B14 rule 31, `DEF-MET-4763`).** This
      // read `Edit unit U-01145` — the tenant's series number — where the
      // frame draws `Edit Unit 2`, the thing written on the door. `unit_no` is
      // the fallback for a unit that has no label rather than the first
      // choice, because a title with neither is worse than either.
      title={t("metering.units.edit.title", {
        unit: unitFormTitle(props.unit, translate),
      })}
      kicker={t("metering.kicker")}
      schema={z.object({
        label: z.string().trim().min(1, t("metering.units.field.labelRequired")),
        unit_type: z.string(),
        floor_label: z.string(),
        square_feet: z.string(),
        is_common_area: z.string(),
        tariff_id: z.string(),
        effective_from: z.string(),
        reason: z.string(),
      })}
      values={values}
      submitLabel={t("metering.units.edit.save")}
      onSubmit={submit}
      onClose={props.onClose}
    >
      {/* ── 1 · WHAT THIS UNIT IS CALLED ─────────────────────────────────
          ⚠ **THERE IS NO `Premise` FIELD HERE ANY MORE, AND ITS SENTENCE WENT
          WITH IT (`DEF-MET-4762`).** The frame draws no such field, and the
          help it carried — *"A unit never moves between premises. To relocate
          it, deactivate it and create it under the other premise."* — stopped
          being true on 2026-08-21, when `BR-MET-095` superseded `BR-MET-046`
          and `MoveUnitModal` shipped. It was advice for a door the product had
          already built, on two forms at once. The address a clerk needs is in
          `WHERE IT IS` below, which is where the frame puts it. */}
      <Section
        id={UNIT_FORM_SECTIONS[0].id}
        label={t(UNIT_FORM_SECTIONS[0].labelKey)}
        optionalLabel={t("metering.premises.section.optional")}
      >
        <TextField
          id="label"
          label={t("metering.units.field.label")}
          required
          value={values.label}
          onChange={(value) => setValues({ ...values, label: value })}
          help={t("metering.units.field.labelHelp")}
        />
        <SelectField
          id="unit_type"
          label={t("metering.units.field.type")}
          value={values.unit_type}
          placeholder={t("metering.units.field.typePlaceholder")}
          options={UNIT_TYPES.map((type) => ({
            value: type,
            label: t(`metering.units.type.${type}`),
          }))}
          onChange={(value) => setValues({ ...values, unit_type: value })}
        />
        {/* ⚠ **THE FRAME DRAWS A SELECT HERE AND THIS STAYS A TEXT FIELD,
            RECORDED RATHER THAN FOLLOWED.** `units.floor_label` is free text in
            the model and holds whatever tenants have already typed —
            `Ground`, `G`, `Mezzanine`, `PH`. A closed list needs a ratified
            vocabulary nobody has ruled, and shipping one would make every
            existing value unselectable on the form that edits it. The
            divergence is stamped in the conformance file. */}
        <TextField
          id="floor_label"
          label={t("metering.units.field.floor")}
          value={values.floor_label}
          onChange={(value) => setValues({ ...values, floor_label: value })}
        />
        <TextField
          id="square_feet"
          label={t("metering.units.field.floorArea")}
          numeric
          value={values.square_feet}
          onChange={(value) => setValues({ ...values, square_feet: value })}
        />
      </Section>

      {/* ── 2 · WHERE IT IS — an OFFER, not two empty boxes ───────────────
          The frame's own reasoning, kept because it is the decision: *"Two
          empty coordinate boxes on every unit would imply every unit ought to
          have them. Almost none should."* `point.source` is the SERVER's
          answer to which of the two points is in force; recomputing the
          fallback here would be a second definition of it. */}
      {/* GIS Lane D (`DEF-MET-10003`, PO GIS review gap 9) — WHERE IT IS is
          the unit's own City point; a utility with no City GIS is not offered
          it. Hiding it sends nothing: `pointTouched` stays false, so the
          stored point is left exactly as it is. */}
      {city.showCity && (
      <Section
        id={UNIT_FORM_SECTIONS[1].id}
        label={t(UNIT_FORM_SECTIONS[1].labelKey)}
        optional={UNIT_FORM_SECTIONS[1].optional}
        optionalLabel={t("metering.premises.section.optional")}
      >
        <Note>{pointSentence(props.unit, pointOwn, lat, lng, t)}</Note>
        {pointOwn && (
          <>
            <TextField
              id="lat"
              label={t("metering.premises.field.lat")}
              numeric
              value={lat}
              onChange={(value) => {
                setPointTouched(true);
                setLat(value);
              }}
            />
            <TextField
              id="lng"
              label={t("metering.premises.field.lng")}
              numeric
              value={lng}
              onChange={(value) => {
                setPointTouched(true);
                setLng(value);
              }}
            />
          </>
        )}
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            setPointTouched(true);
            if (pointOwn) {
              // Back to the building's: BOTH cleared, which is what the
              // fallback is — not a third state.
              setLat("");
              setLng("");
            }
            setPointOwn(!pointOwn);
          }}
        >
          {pointOwn ? t("metering.unit.point.useBuilding") : t("metering.unit.point.give")}
        </Button>
        <Note>{t("metering.units.point.help")}</Note>
        <CityGisNote messageKey={city.brokenKey} />
      </Section>
      )}

      {/* ── 3 · WHAT IT CAN TAKE ──────────────────────────────────────────
          ⚠ **THE SERVICES ARE READ-ONLY AND THE ABSENCE SPEAKS (`BR-MET-118`,
          PO 2026-09-10).** The frame draws removable per-unit chips; there is
          no unit-level column and no override, so what is drawn here is the
          BUILDING's list with the one sentence that says so. */}
      <Section
        id={UNIT_FORM_SECTIONS[2].id}
        label={t(UNIT_FORM_SECTIONS[2].labelKey)}
        optionalLabel={t("metering.premises.section.optional")}
      >
        <div className="field" data-unit-services="">
          <label htmlFor="unit-services">{t("metering.units.col.services")}</label>
          <p className="field-help" id="unit-services">
            <ServiceTags services={props.unit.services} t={translate} />
          </p>
        </div>
        <Note>{t("metering.units.field.servicesInherited")}</Note>
        {/* ⚠ **A SELECT, NOT A TICK-BOX, AND THE FRAME SAYS SO ON PURPOSE:**
            *"Common area is a question with an answer in words, not a
            tick-box, because it changes who gets billed."* */}
        <SelectField
          id="is_common_area"
          label={t("metering.units.field.commonAreaQuestion")}
          value={values.is_common_area}
          options={[
            { value: "no", label: t("metering.units.field.commonAreaNo") },
            { value: "yes", label: t("metering.units.field.commonAreaYes") },
          ]}
          onChange={(value) => setValues({ ...values, is_common_area: value })}
          help={t("metering.units.field.commonAreaHelp")}
        />
      </Section>

      {/* ── 4 · WHAT IT IS CHARGED ON (`PUJ-45`) ──────────────────────────
          B14 rule 32's budget: ONE sentence for this section, and it is the
          drawn one — what it costs to leave this group empty. */}
      <Section
        id={UNIT_FORM_SECTIONS[3].id}
        label={t(UNIT_FORM_SECTIONS[3].labelKey)}
        optional={UNIT_FORM_SECTIONS[3].optional}
        optionalLabel={t("metering.premises.section.optional")}
      >
        <Note>{t("metering.units.edit.planSection")}</Note>
        {/* BR-SHL-033: the plan list is long → the searchable control.
            ⚠ **THE `key` IS LOAD-BEARING AND IT IS `DEF-MET-4732` — `DEF-442`'s
            MECHANISM FOR THE THIRD TIME.** `SearchSelectField` seeds the text it
            DISPLAYS exactly once, with `useState(selected?.label ?? "")`, and
            these options arrive from a second request that has not landed on
            first render. So this form, opened on a unit that HAS a plan, held the
            right plan id and drew a BLANK picker — *"two controls, one fact, and
            the one a clerk can see says the opposite"* — which on this particular
            control reads as **no plan** on a unit that is on one. Re-keying on
            whether the options have arrived remounts it exactly once, when they
            do; the key changes on the 0 → N transition, before anybody has typed,
            so it cannot interrupt typing.
            ⚠ **NO TEST COULD HAVE FOUND IT AND THAT IS THE POINT.** The VALUE is
            correct throughout, so every assertion about what the form holds, what
            it posts and what the server stores passes. The browser walk caught it
            by reopening the form after a save and reading what was on screen. */}
        <SearchSelectField
          key={plansQuery.data === undefined ? "awaiting-options" : "options"}
          id="tariff_id"
          label={t("metering.units.plan.plan")}
          value={values.tariff_id}
          options={planPickerOptions(plansQuery.data?.results)}
          placeholder={t("metering.units.plan.planPlaceholder")}
          onChange={(value) => setValues({ ...values, tariff_id: value })}
          help={plansQuery.isError ? t("metering.units.plan.planListUnavailable") : undefined}
        />
        {/* The two fields below only mean anything when the plan actually moves,
            so they are DRAWN only then rather than sitting greyed out: a date
            picker on a form where no date will be written is furniture. */}
        {planChanged && (
          <>
            <DatePickerField
              id="effective_from"
              label={t("metering.units.plan.takesEffect")}
              value={values.effective_from}
              dateFormat={dateFormat}
              onChange={(value) => setValues({ ...values, effective_from: value })}
              help={t("metering.units.plan.effectiveFromHelp")}
            />
            <TextField
              id="reason"
              label={t("metering.units.plan.reason")}
              value={values.reason}
              onChange={(value) => setValues({ ...values, reason: value })}
              help={t("metering.units.plan.reasonHelp")}
            />
            {/* BR-MET-042: the OVERRIDE path is stated up front; the SERVER
                decides whether this edit is one and returns the warning this
                form then shows. Nothing here judges it. */}
            <Note>{t("metering.units.plan.overrideNote")}</Note>
          </>
        )}
      </Section>

      {/* `CR-161-BRC10` W3 — Edit unit's slot; nothing for a tenant with none. */}
      <CustomFieldsInput
        entity="units"
        screen="UNIT_EDIT"
        values={customData}
        onChange={setCustomData}
        client={props.client}
      />

      {/* BR-MET-036: occupancy is shown as a FACT and has no control anywhere. */}
      <Note>
        {t("metering.units.field.occupancyDerived", {
          occupancy: t(`metering.occupancy.${props.unit.occupancy}`, {
            defaultValue: props.unit.occupancy,
          }),
        })}
      </Note>
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-089 wave F · F6 (`PUJ-44`, `PUJ-45`)
// generated: 2026-09-09 by the CR-089 wave F build lane
// checklist: A✔ B✔ C✔ D=n/a E✔ F✔ G✔ H=n/a
// exceptions: E3 `is_common_area` is deliberately NOT offered here — the list's
//   modal keeps it; turning an occupied flat into a common area changes who the
//   bill goes to (BR-MET-094) and was not asked for by this ruling · E2 the
//   duplicate form in `UnitsListPage.tsx` is REPORTED as `DEF-MET-4731` rather
//   than removed: that file is wave E's and this wave may not restructure it.
//   This component is exported so the removal is a one-line import
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
