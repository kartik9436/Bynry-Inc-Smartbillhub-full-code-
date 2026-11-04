// ── Trace ──────────────────────────────────────────────
// Change:   CR-092-BRC01 step 2 wave C lane 1 — `AST-B-25` (a pencil per
//           Overview panel) and `AST-B-27` (the sub-meter's allocation share).
//           Screens: 16 `Edit · What's due` · 17 `Edit · Measurement` ·
//           18 `Edit · Measurement · confirm` · 19 `Edit · Device` ·
//           20 `Edit · Cost & value` · 21 `Edit · Lifecycle`.
//           Drawing: 04-docs/05-modules/05-assets/08-screen-layouts.md and
//           wireframes/CR-092-assets-screens.html#screen-16 … #screen-21.
// Rules:    BR-AST-012 (billing-affecting fields apply FORWARD ONLY once reads
//           exist; every edit audited before/after) · BR-AST-015 (register
//           digits default 9) · BR-AST-020 (a retired asset takes no edit) ·
//           BR-AST-026 (three identifiers; the uuid is none of them) ·
//           BR-AST-044 (`meter_type` is NOT billing-affecting, documented) ·
//           BR-AST-047 + §10-D3 (cost is CAPTURED and posted NOWHERE) ·
//           BR-AST-500 (a null connection size is a real state) ·
//           hard rule 2 (money 4 dp stored, 2 displayed; percentages 6) ·
//           hard rule 4 (an issued invoice takes no update, ever) ·
//           hard rule 8 (an address lives on the premises — this is a NOTE) ·
//           B14 rule 33 (what a string is FOR caps its length) · B14 rule 38
//           (the UI rules decide how a form is built) · B14 rule 39 (field
//           anatomy: label → input → helper, 5 / 6 / 20).
// ───────────────────────────────────────────────────────
//
// FIVE DIALOGS AND ONE SECOND STEP — AND THE SERVER NEEDED NOTHING.
//
// `PATCH /assets/{id}` has validated a PARTIAL payload since the module
// shipped (`_validate_asset(data, partial=True, current=asset)` accepts 39
// field names), already audits before and after, already refuses a retired
// asset before it validates anything, and already returns the
// `forward_only_change` warning. **The one edit door in the product sent
// seven of those 39 fields and was reachable only from a table row.** So a
// clerk reading a wrong multiplier on the asset had to leave the asset, find
// its row in a paginated registry, and press a pencil there.
//
// ⚠ **PAGE OR DIALOG IS A RULE HERE, NOT TASTE.** A PAGE when you are creating
// something, or when the change moves where the thing lives — add an asset,
// reassign, retire. A MODAL when you are correcting a value on something you
// are already looking at. Twenty-three fields in one form is why nobody edits
// (screen 14 stays a page, and the PO ruled it: *"this should be form and not
// modal"*); two to nine fields on the panel you are reading is a dialog.
//
// ⚠ **EXACTLY ONE PENCIL ON THIS SCREEN CAN RESTATE WHAT A READING MEANS.**
// All five of `BILLING_AFFECTING_FIELDS` — `multiplier`, `unit`,
// `net_metering`, `service`, `size_class` — sit in the Measurement panel, so
// one form carries the warning and one confirmation covers it. `meter_type` is
// explicitly NOT on that list, documented in `update_asset`'s own docstring,
// which is why the Device dialog needs no confirmation at all.
//
// ⚠ **THE DRAWING NUMBERS ITS FIELDS 1, 2, 3 … AND THIS DOES NOT.** B14 rule
// 38: where a drawing and our UI rules disagree about how a FORM IS BUILT, the
// UI rules win — a numbered label is form construction, the kit's five
// help-bearing field variants carry no such affordance, and adding one would
// change every dialog in the product on one screen's authority. Recorded in
// the conformance file rather than built.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import { getLookupEntries, updateAsset } from "@/api/endpoints";
import type { AssetDetail, LookupEntry } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { ConsequenceBox } from "@/components/ConsequenceBox";
import {
  DatePickerField,
  FormModal,
  SelectField,
  TextField,
} from "@/components/FormModal";
import type { FormSubmitOutcome, ServerErrorEnvelope } from "@/components/FormModal";
import { StatusPill } from "@/components/StatusPill";
import { useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { z } from "zod";

import {
  assetTypesQueryKey,
  meterTypesQueryKey,
  readMethodsQueryKey,
  sizeClassesQueryKey,
} from "./AssetRegistryPage";
import {
  isMeasuringCategory,
  offersConnectionSize,
  sizeOptionsForService,
  trimDecimalZeros,
} from "./assetsShared";
import type { AssetOverviewPanel } from "./AssetDetailPage";

/**
 * `AST-B-27` — the four ratified words for `allocation_rule`.
 *
 * ⚠ **THESE ARE THE FIRST CUSTOMER-FACING WORDS THESE VALUES HAVE EVER HAD.**
 * `allocation_rule` is a plain `TextField` on the model with a code comment
 * reading `# rubs | sqft | equal | absorb` — no `choices`, no lookup, no
 * constraint, no catalogue key, and no UI anywhere in the product. The PO
 * ratified the four on 2026-09-12: *"this is correct - build it"*.
 *
 * ⚠ **THE LIST IS DECLARED ONCE AND BOTH WRITE DOORS READ IT** (hard-won law
 * 12's shape for a hand-typed list): this dialog and the add wizard. A fifth
 * rule added to the model without a word here would render as a blank option,
 * which is why the select falls back to the stored CODE only through
 * `defaultValue` and never silently.
 */
export const ALLOCATION_RULES = ["rubs", "sqft", "equal", "absorb"] as const;

/** The methods `asset_book_value` can actually work out a present value from.
 *  `NONE · NO LIST EXISTS` on the drawing: nothing in Settings owns these. */
export const DEPRECIATION_METHODS = ["straight_line", "none"] as const;

const EMPTY_SCHEMA = z.object({});

function lookupOptions(rows: readonly LookupEntry[]): { value: string; label: string }[] {
  return rows.map((row) => ({ value: row.code, label: row.name }));
}

/** A `PATCH` that renders its refusal where the field is (B12 §3). */
async function patch(
  assetId: string,
  body: Record<string, unknown>,
  client: ApiClient,
): Promise<FormSubmitOutcome> {
  try {
    await updateAsset(assetId, body, client);
    return { ok: true };
  } catch (error) {
    const envelope = (error as { body?: ServerErrorEnvelope }).body;
    if (envelope !== undefined && typeof envelope.message_key === "string") {
      return { ok: false, error: envelope };
    }
    return {
      ok: false,
      error: { code: "UNKNOWN", message_key: "api.error.unexpected" },
    };
  }
}

/**
 * Screens 16, 20 and 21 — **the facts this form does NOT type**, named rather
 * than left to be wondered about. A person who came to change the next-due date
 * learns here that it is computed, which is the whole point of splitting
 * twenty-three fields into five panels.
 *
 * ⚠ **THE DRAWING GIVES EACH LINE ITS REASON AND B14 RULE 33 FORBIDS IT, SO
 * THE REASONS ARE NOT BUILT.** Screen 16 draws *"Next due — computed from the
 * last test and the interval"*, and rule 33 is explicit: **RATIONALE — why the
 * product works this way, WHY A CONTROL IS ABSENT — is ZERO WORDS ON SCREEN**.
 * What survives is the ABSENCE itself, which is content the drawing decides
 * (rule 38's own last clause) and which each line states as a LABEL of at most
 * three words. The reasons live here, in the code, and in the conformance file
 * — which is where rule 33 says to put them. Divergence filed, not followed.
 */
function NotOnThisForm(props: { t: Translator; keys: readonly string[] }) {
  return (
    <div className="mt-5 border-t border-t-divider pt-3">
      <p className="m-0 mb-2 text-sm font-semibold">{props.t("assets.panel.notTyped")}</p>
      <ul className="m-0 list-disc pl-5 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
        {props.keys.map((key) => (
          <li key={key}>{props.t(`assets.panel.derived.${key}`)}</li>
        ))}
      </ul>
    </div>
  );
}

export function AssetPanelEditDialog(props: {
  asset: AssetDetail;
  panel: AssetOverviewPanel;
  client: ApiClient;
  regional: RegionalProps;
  t: Translator;
  onClose: () => void;
  onSaved: () => void;
}) {
  const kicker = [props.asset.asset_no, props.asset.classifications.asset_type.name]
    .filter((part) => part)
    .join(" · ");
  const shared = { ...props, kicker };
  switch (props.panel) {
    case "due":
      return <EditWhatsDue {...shared} />;
    case "measurement":
      return <EditMeasurement {...shared} />;
    case "device":
      return <EditDevice {...shared} />;
    case "cost":
      return <EditCostValue {...shared} />;
    case "lifecycle":
      return <EditLifecycle {...shared} />;
    default:
      // Assignment has no pencil on any kind — the panel says so and offers
      // `Reassign` instead. Reaching here would be a bug, not a state.
      return null;
  }
}

interface DialogProps {
  asset: AssetDetail;
  client: ApiClient;
  regional: RegionalProps;
  t: Translator;
  kicker: string;
  onClose: () => void;
  onSaved: () => void;
}

// ── 16 · Edit · What's due ─────────────────────────────────────────────────
//
// Two typed fields, and the four derived ones named on the form as absent.

function EditWhatsDue(props: DialogProps) {
  const { t } = props;
  const { dateFormat } = useRegional(props.regional);
  const [values, setValues] = useState({
    test_interval_months:
      props.asset.specs.test_interval_months === null
        ? ""
        : String(props.asset.specs.test_interval_months),
    // ⚠ **THE EXPLICIT COLUMN IS NOT SERVED SEPARATELY, AND THAT IS WHY THIS
    // SEEDS FROM THE DERIVED VALUE.** `next_test_date()` returns the explicit
    // `certification_due` when it is captured and the `BR-AST-007` derivation
    // otherwise, and BOTH payload keys are that one call — so the screen
    // cannot tell a captured date from a computed one. Saving what is shown
    // therefore PINS the date, which is what a person editing this field
    // means; blanking it restores the derivation. Filed as `DEF-MET-5001`
    // because the distinction should be on the wire.
    certification_due: props.asset.lifecycle.certification_due ?? "",
  });
  return (
    <FormModal
      kicker={props.kicker}
      title={t("assets.panel.title.due")}
      schema={EMPTY_SCHEMA}
      values={values}
      submitLabel={t("assets.panel.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await patch(
          props.asset.id,
          {
            test_interval_months:
              values.test_interval_months === "" ? null : values.test_interval_months,
            certification_due: values.certification_due === "" ? null : values.certification_due,
          },
          props.client,
        );
        if (outcome.ok) {
          props.onSaved();
        }
        return outcome;
      }}
    >
      {/* `Test interval` in MONTHS, never `cadence` or `frequency` — the
          product has one word and eleven catalogues carry it. */}
      <TextField
        id="test_interval_months"
        label={t("assets.spec.testInterval")}
        help={t("assets.panel.help.testInterval")}
        numeric
        value={values.test_interval_months}
        onChange={(value) => setValues({ ...values, test_interval_months: value })}
      />
      <DatePickerField
        id="certification_due"
        label={t("assets.lifecycle.certificationDue")}
        help={t("assets.panel.help.certificationDue")}
        dateFormat={dateFormat}
        value={values.certification_due}
        onChange={(value) => setValues({ ...values, certification_due: value })}
      />
      <NotOnThisForm t={t} keys={["nextDue", "age", "forecast", "warrantyState"]} />
    </FormModal>
  );
}

// ── 17 + 18 · Edit · Measurement, and its confirm step ─────────────────────
//
// ⚠ **THE ONE EDIT ON THIS SCREEN THAT GOES THROUGH A SECOND STEP, AND THE
// SECOND STEP IS THE SAME MODAL.** `Back` returns the typed values rather than
// discarding them, which a second dialog could not do. The primary action on
// step one is therefore `Continue`, never `Save`.
//
// ⚠ **WHEN NOTHING BILLING-AFFECTING CHANGED, `Continue` BEHAVES AS SAVE AND
// THE SECOND STEP IS SKIPPED** — a confirmation over a change with no
// consequence teaches a clerk to press through the one that has.

const BILLING_AFFECTING = ["size_class", "multiplier", "unit"] as const;

function EditMeasurement(props: DialogProps) {
  const { t } = props;
  const asset = props.asset;
  const measuring = isMeasuringCategory(asset.tab);
  const sub = asset.tab === "sub_meters";
  const [step, setStep] = useState<1 | 2>(1);
  const [values, setValues] = useState({
    read_method: asset.read_method ?? "",
    size_class: asset.size_class ?? "",
    multiplier: asset.multiplier ?? "1",
    unit: asset.unit ?? "",
    register_digits:
      asset.specs.register_digits === null ? "" : String(asset.specs.register_digits),
    allocation_share_pct: asset.specs.allocation_share_pct ?? "",
    allocation_rule: asset.specs.allocation_rule ?? "",
    loss_tolerance_pct: asset.specs.loss_tolerance_pct ?? "",
  });

  const readMethodsQuery = useQuery({
    queryKey: readMethodsQueryKey,
    queryFn: () => getLookupEntries("read_methods", { per: 100 }, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const sizeClassesQuery = useQuery({
    queryKey: sizeClassesQueryKey,
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const before: Record<string, string> = {
    size_class: asset.size_class ?? "",
    multiplier: asset.multiplier ?? "1",
    unit: asset.unit ?? "",
  };
  const changed = BILLING_AFFECTING.filter((field) => values[field] !== before[field]);

  function body(): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      read_method: values.read_method === "" ? null : values.read_method,
    };
    if (measuring) {
      payload.multiplier = values.multiplier;
      payload.unit = values.unit;
      payload.register_digits = values.register_digits === "" ? null : values.register_digits;
    }
    if (offersConnectionSize(asset.tab, asset.service)) {
      // BR-AST-500: EMPTY sends `null` and that is an explicit CLEAR — on an
      // edit the operator is looking at a stored value, so blanking it is a
      // statement rather than an omission.
      payload.size_class = values.size_class === "" ? null : values.size_class;
      if (!measuring) {
        // Plan U10 — a device's unit; blank clears it to "the service's own".
        payload.unit = values.unit === "" ? null : values.unit;
      }
    }
    if (sub) {
      // `AST-R-05` — a null share means METERED, NOT ALLOCATED and is served
      // as null, never as a zero, which would read as *allocated nothing*.
      payload.allocation_share_pct =
        values.allocation_share_pct === "" ? null : values.allocation_share_pct;
      payload.allocation_rule = values.allocation_rule === "" ? null : values.allocation_rule;
      payload.loss_tolerance_pct =
        values.loss_tolerance_pct === "" ? null : values.loss_tolerance_pct;
    }
    return payload;
  }

  async function save(): Promise<FormSubmitOutcome> {
    const outcome = await patch(asset.id, body(), props.client);
    if (outcome.ok) {
      props.onSaved();
    }
    return outcome;
  }

  if (step === 2) {
    return (
      <FormModal
        kicker={props.kicker}
        title={t("assets.panel.title.measurementConfirm")}
        schema={EMPTY_SCHEMA}
        values={values}
        submitLabel={t("assets.panel.save")}
        onClose={props.onClose}
        onSubmit={save}
      >
        {/* B14 rule 33 — a CONSEQUENCE before an irreversible act is at most
            two sentences of six words, and never cut below clarity. The
            drawing's own paragraph is longer; this says the same thing in the
            rule's shape, and the RATIONALE (why forward-only exists) is zero
            words on screen by the same rule. */}
        <ConsequenceBox
          tone="check"
          data-consequence="forward-only"
          title={t("assets.panel.forwardOnly.one")}
          tag={t("assets.panel.affectsBilling")}
          body={<strong>{t("assets.panel.forwardOnly.two")}</strong>}
        />
        <dl className="m-0 mt-4 grid grid-cols-[minmax(120px,auto)_1fr] gap-x-3 gap-y-2 text-base [&_dd]:m-0 [&_dt]:font-semibold">
          <dt>{t("assets.panel.confirm.changes")}</dt>
          <dd>
            {changed.map((field) => t(`assets.panel.field.${field}`)).join(" · ")}
          </dd>
          <dt>{t("assets.panel.confirm.unchanged")}</dt>
          <dd>{t("assets.panel.confirm.unchangedValue")}</dd>
        </dl>
        <div className="mt-4">
          {/* `Back` returns to the form with everything still typed — the
              reason this is one modal in two steps and not two modals. */}
          {/* ⚠ THIS WAS A RAW `<button>` CARRYING TWO CLASS NAMES, AND THE
              SECOND ONE HAD NOT EXISTED SINCE CR-018 PHASE 4A DELETED THE SIX
              VARIANT RULES — so it drew as unstyled text (DEF-SHL-5088). The
              kit is the contract now and the contract is a TYPE: a misspelt
              variant fails `tsc`, which is why the rules were deleted rather
              than renamed. The dead name is not written here, for the reason
              `components/Button.tsx` gives in capitals: a class name quoted in
              a comment is reported as a class this file asks for. */}
          <Button variant="ghost" onClick={() => setStep(1)}>
            {t("assets.panel.back")}
          </Button>
        </div>
      </FormModal>
    );
  }

  return (
    <FormModal
      kicker={props.kicker}
      title={t("assets.panel.title.measurement")}
      schema={EMPTY_SCHEMA}
      values={values}
      submitLabel={changed.length > 0 ? t("assets.panel.continue") : t("assets.panel.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        if (changed.length > 0) {
          setStep(2);
          return { ok: true } as FormSubmitOutcome;
        }
        return save();
      }}
    >
      {measuring && (
        <SelectField
          id="read_method"
          label={t("assets.col.readMethod")}
          help={t("assets.panel.help.readMethod")}
          placeholder={t("assets.form.unset")}
          value={values.read_method}
          options={lookupOptions(readMethodsQuery.data?.results ?? [])}
          onChange={(value) => setValues({ ...values, read_method: value })}
        />
      )}
      {offersConnectionSize(asset.tab, asset.service) && (
        <>
          <AffectsBilling t={t} />
          <SelectField
            id="size_class"
            label={t("assets.col.sizeClass")}
            help={t("assets.panel.help.sizeClass")}
            placeholder={t("assets.form.unset")}
            value={values.size_class}
            // Plan U10 — THIS asset's service's sizes only (`AST.SIZE_FOR_SERVICE`).
            options={sizeOptionsForService(sizeClassesQuery.data?.results ?? [], asset.service)}
            onChange={(value) => setValues({ ...values, size_class: value })}
          />
          {/* Plan U10 — a DEVICE on a service carries its own unit too (the
              upload's devices sheet has it); a meter's is further down. */}
          {!measuring && (
            <TextField
              id="unit"
              label={t("assets.form.uom")}
              help={t("assets.add.capacityUnitHelp")}
              value={values.unit}
              onChange={(value) => setValues({ ...values, unit: value })}
            />
          )}
        </>
      )}
      {measuring && (
        <>
          <AffectsBilling t={t} />
          <TextField
            id="multiplier"
            label={t("assets.form.multiplier")}
            help={t("assets.panel.help.multiplier")}
            numeric
            value={values.multiplier}
            onChange={(value) => setValues({ ...values, multiplier: value })}
          />
          <AffectsBilling t={t} />
          <TextField
            id="unit"
            label={t("assets.form.uom")}
            help={t("assets.panel.help.uom")}
            value={values.unit}
            onChange={(value) => setValues({ ...values, unit: value })}
          />
          <TextField
            id="register_digits"
            label={t("assets.spec.registerDigits")}
            help={t("assets.panel.help.registerDigits")}
            numeric
            value={values.register_digits}
            onChange={(value) => setValues({ ...values, register_digits: value })}
          />
        </>
      )}
      {sub && (
        <>
          {/* `AST-B-27` — three rows no other kind has, editable HERE and
              read-only on a meter. The share is a percentage at its stored 6
              dp (hard rule 2); empty means metered, not allocated. */}
          <TextField
            id="allocation_share_pct"
            label={t("assets.spec.allocationShare")}
            help={t("assets.panel.help.allocationShare")}
            numeric
            value={values.allocation_share_pct}
            onChange={(value) => setValues({ ...values, allocation_share_pct: value })}
          />
          <SelectField
            id="allocation_rule"
            label={t("assets.spec.allocationRule")}
            help={t("assets.panel.help.allocationRule")}
            placeholder={t("assets.form.unset")}
            value={values.allocation_rule}
            options={ALLOCATION_RULES.map((code) => ({
              value: code,
              label: t(`assets.allocationRule.${code}`),
            }))}
            onChange={(value) => setValues({ ...values, allocation_rule: value })}
          />
          <TextField
            id="loss_tolerance_pct"
            label={t("assets.spec.lossTolerance")}
            help={t("assets.panel.help.lossTolerance")}
            numeric
            value={values.loss_tolerance_pct}
            onChange={(value) => setValues({ ...values, loss_tolerance_pct: value })}
          />
        </>
      )}
      {asset.export_capacity_kw != null && !measuring && (
        <TextField
          id="export_capacity_kw"
          label={t("assets.col.exportCapacity")}
          help={t("assets.panel.help.exportCapacity")}
          readOnly
          numeric
          value={trimDecimalZeros(asset.export_capacity_kw)}
          onChange={() => undefined}
        />
      )}
    </FormModal>
  );
}

/** `Affects billing`, not `warning` or `caution`: it says what the consequence
 *  IS rather than how worried to be. Two words — B14 rule 33's label cap. */
function AffectsBilling(props: { t: Translator }) {
  return (
    <p className="m-0 -mb-2">
      <StatusPill tone="warning">{props.t("assets.panel.affectsBilling")}</StatusPill>
    </p>
  );
}

// ── 19 · Edit · Device ─────────────────────────────────────────────────────
//
// Everything here is descriptive and none of it restates anything, so there is
// no confirmation and no pill — which is itself information: a person learns
// that this panel is the safe one.

function EditDevice(props: DialogProps) {
  const { t } = props;
  const asset = props.asset;
  const [values, setValues] = useState({
    type: asset.type ?? "",
    meter_type: asset.meter_type ?? "",
    manufacturer: asset.manufacturer ?? "",
    model: asset.model ?? "",
    serial_no: asset.serial_no ?? "",
    external_ref: asset.external_ref ?? "",
    form_class: asset.specs.form_class ?? "",
    firmware_version: asset.specs.firmware_version ?? "",
    seal_no: asset.specs.seal_no ?? "",
  });
  const typesQuery = useQuery({
    queryKey: assetTypesQueryKey,
    queryFn: () => getLookupEntries("asset_types", { per: 100 }, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const meterTypesQuery = useQuery({
    queryKey: meterTypesQueryKey,
    queryFn: () => getLookupEntries("meter_types", { per: 100 }, props.client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const types: readonly LookupEntry[] = typesQuery.data?.results ?? [];
  const selected = types.find((row) => row.code === values.type);
  const measuring = isMeasuringCategory(String(selected?.category ?? asset.tab));
  return (
    <FormModal
      kicker={props.kicker}
      title={t("assets.panel.title.device")}
      schema={EMPTY_SCHEMA}
      values={values}
      submitLabel={t("assets.panel.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        const payload: Record<string, unknown> = {
          type: values.type,
          // `AST-R-15`: two columns are two FIELDS on the form. The server's
          // one edit door takes them joined on a middle dot, which is the only
          // field in the module that asks a human to do a parser's job — this
          // dialog joins them itself so nobody has to type a delimiter.
          manufacturer_model: [values.manufacturer, values.model]
            .filter((part) => part !== "")
            .join(" · "),
          serial_no: values.serial_no,
          external_ref: values.external_ref === "" ? null : values.external_ref,
          form_class: values.form_class === "" ? null : values.form_class,
          firmware_version: values.firmware_version === "" ? null : values.firmware_version,
          seal_no: values.seal_no === "" ? null : values.seal_no,
        };
        // BR-AST-044: `meter_type` travels ONLY for a measuring type; on
        // anything else the server refuses it as a field error.
        if (measuring) {
          payload.meter_type = values.meter_type === "" ? null : values.meter_type;
        }
        const outcome = await patch(asset.id, payload, props.client);
        if (outcome.ok) {
          props.onSaved();
        }
        return outcome;
      }}
    >
      <SelectField
        id="type"
        label={t("assets.col.assetType")}
        help={t("assets.panel.help.assetType")}
        required
        value={values.type}
        options={lookupOptions(types)}
        onChange={(value) => setValues({ ...values, type: value })}
      />
      {measuring && (
        <SelectField
          id="meter_type"
          label={t("assets.col.meterType")}
          help={t("assets.panel.help.meterType")}
          placeholder={t("assets.form.unset")}
          value={values.meter_type}
          options={lookupOptions(meterTypesQuery.data?.results ?? [])}
          onChange={(value) => setValues({ ...values, meter_type: value })}
        />
      )}
      <TextField
        id="manufacturer"
        label={t("assets.form.manufacturer")}
        value={values.manufacturer}
        onChange={(value) => setValues({ ...values, manufacturer: value })}
      />
      <TextField
        id="model"
        label={t("assets.form.model")}
        value={values.model}
        onChange={(value) => setValues({ ...values, model: value })}
      />
      <TextField
        id="serial_no"
        label={t("assets.col.serial")}
        help={t("assets.panel.help.serial")}
        value={values.serial_no}
        onChange={(value) => setValues({ ...values, serial_no: value })}
      />
      {/* Served on every row since the module shipped and written by the asset
          IMPORT alone — typable from a screen here for the first time. */}
      <TextField
        id="external_ref"
        label={t("assets.spec.externalRef")}
        help={t("assets.panel.help.externalRef")}
        value={values.external_ref}
        onChange={(value) => setValues({ ...values, external_ref: value })}
      />
      <TextField
        id="form_class"
        label={t("assets.spec.formClass")}
        value={values.form_class}
        onChange={(value) => setValues({ ...values, form_class: value })}
      />
      <TextField
        id="firmware_version"
        label={t("assets.spec.firmware")}
        value={values.firmware_version}
        onChange={(value) => setValues({ ...values, firmware_version: value })}
      />
      <TextField
        id="seal_no"
        label={t("assets.spec.seal")}
        value={values.seal_no}
        onChange={(value) => setValues({ ...values, seal_no: value })}
      />
    </FormModal>
  );
}

// ── 20 · Edit · Cost & value ───────────────────────────────────────────────
//
// ⚠ **`DEF-MET-4972`'s REMAINING HALF.** The purchase date renders on the
// Overview since wave B lane 3 and could not be CORRECTED from any screen: the
// one edit door sends eight keys and `purchase_date` is not one of them, while
// age, accumulated depreciation and present value are all computed from it and
// all three are shown. A wrong date was visible in its consequences and
// invisible in itself. It is typable here.
//
// ⚠ **NOTHING POSTS, IN ANY STATE** (§10-D3: *"cost is CAPTURED — stored 4 dp,
// totalled on the tab, and posted NOWHERE"*).

function EditCostValue(props: DialogProps) {
  const { t } = props;
  const asset = props.asset;
  const { dateFormat } = useRegional(props.regional);
  const [values, setValues] = useState({
    supplier: asset.valuation.supplier ?? "",
    purchase_cost: asset.valuation.purchase_cost ?? "",
    purchase_date: asset.valuation.purchase_date ?? "",
    depreciation_method: asset.valuation.depreciation_method ?? "",
    expected_life_years:
      asset.lifecycle.expected_life_years === null
        ? ""
        : String(asset.lifecycle.expected_life_years),
  });
  return (
    <FormModal
      kicker={props.kicker}
      title={t("assets.panel.title.cost")}
      schema={EMPTY_SCHEMA}
      values={values}
      submitLabel={t("assets.panel.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await patch(
          asset.id,
          {
            supplier: values.supplier === "" ? null : values.supplier,
            // Money travels as a raw STRING end to end; the server owns
            // parsing and stores at 4 dp (hard rule 2).
            purchase_cost: values.purchase_cost === "" ? null : values.purchase_cost,
            purchase_date: values.purchase_date === "" ? null : values.purchase_date,
            depreciation_method:
              values.depreciation_method === "" ? null : values.depreciation_method,
            expected_life_years:
              values.expected_life_years === "" ? null : values.expected_life_years,
          },
          props.client,
        );
        if (outcome.ok) {
          props.onSaved();
        }
        return outcome;
      }}
    >
      <TextField
        id="supplier"
        label={t("assets.supplier")}
        value={values.supplier}
        onChange={(value) => setValues({ ...values, supplier: value })}
      />
      <TextField
        id="purchase_cost"
        label={t("assets.valuation.purchaseCost")}
        help={t("assets.panel.help.purchaseCost")}
        numeric
        value={values.purchase_cost}
        onChange={(value) => setValues({ ...values, purchase_cost: value })}
      />
      <DatePickerField
        id="purchase_date"
        label={t("assets.valuation.purchaseDate")}
        help={t("assets.panel.help.purchaseDate")}
        dateFormat={dateFormat}
        value={values.purchase_date}
        onChange={(value) => setValues({ ...values, purchase_date: value })}
      />
      <SelectField
        id="depreciation_method"
        label={t("assets.valuation.depreciationMethod")}
        help={t("assets.panel.help.depreciationMethod")}
        placeholder={t("assets.form.unset")}
        value={values.depreciation_method}
        options={DEPRECIATION_METHODS.map((code) => ({
          value: code,
          label: t(`assets.depreciation.${code}`),
        }))}
        onChange={(value) => setValues({ ...values, depreciation_method: value })}
      />
      <TextField
        id="expected_life_years"
        label={t("assets.lifecycle.expectedLife")}
        help={t("assets.panel.help.expectedLife")}
        numeric
        value={values.expected_life_years}
        onChange={(value) => setValues({ ...values, expected_life_years: value })}
      />
      {/* ⚠ **`Warranty term` IS DRAWN ON THIS FORM AND NO COLUMN STORES ONE.**
          `assets` holds `warranty_end` (a date) and no term, and deriving a
          term from two dates nobody signed would be worse than the absence.
          Filed as `DEF-MET-5002` rather than invented here (prime directive).
          The three computed figures are named below for the same reason the
          absent ones are: so nobody hunts for an editable present value. */}
      <NotOnThisForm t={t} keys={["presentValue", "bookValue"]} />
    </FormModal>
  );
}

// ── 21 · Edit · Lifecycle ──────────────────────────────────────────────────
//
// Two fields out of six, and the four that are NOT here are the four a person
// would most expect to be: status, retired on, reason and replaced by. Naming
// them as written-by-something-else is what stops somebody looking for a way to
// retire an asset by typing a date (`BR-AST-020`: status moves by legal
// transition, never by typing).

function EditLifecycle(props: DialogProps) {
  const { t } = props;
  const asset = props.asset;
  const { dateFormat } = useRegional(props.regional);
  const [values, setValues] = useState({
    install_date: asset.install_date ?? "",
    location_note: asset.specs.location_note ?? "",
  });
  return (
    <FormModal
      kicker={props.kicker}
      title={t("assets.panel.title.lifecycle")}
      schema={EMPTY_SCHEMA}
      values={values}
      submitLabel={t("assets.panel.save")}
      onClose={props.onClose}
      onSubmit={async () => {
        const outcome = await patch(
          asset.id,
          {
            install_date: values.install_date === "" ? null : values.install_date,
            location_note: values.location_note === "" ? null : values.location_note,
          },
          props.client,
        );
        if (outcome.ok) {
          props.onSaved();
        }
        return outcome;
      }}
    >
      <DatePickerField
        id="install_date"
        label={t("assets.col.installed")}
        help={t("assets.panel.help.installDate")}
        dateFormat={dateFormat}
        value={values.install_date}
        onChange={(value) => setValues({ ...values, install_date: value })}
      />
      {/* `Location note`, never `address` — hard rule 8 puts an address on the
          premises and NOWHERE else, and a unit refines a premises by LABEL.
          This is where a technician will actually find the thing in the yard,
          which is a different fact from where the post goes. */}
      <TextField
        id="location_note"
        label={t("assets.spec.locationNote")}
        help={t("assets.panel.help.locationNote")}
        multiline
        value={values.location_note}
        onChange={(value) => setValues({ ...values, location_note: value })}
      />
      <NotOnThisForm t={t} keys={["status", "age", "retirement"]} />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-092-BRC01 step 2 wave C lane 1 (AST-B-25, AST-B-27)
// generated: 2026-09-12
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
