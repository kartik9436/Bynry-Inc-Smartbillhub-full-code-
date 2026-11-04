// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-015 (capture custom fields on input screens) · US-SHL-016
//           (display them, and include them in exports)
//           Screens: S14 · S15 · S16 · S18 · S21 · S23 · S49 · S50 · S51 —
//           every eligible slot in the US-TEN-016 allow-list
// Rules:    BR-SHL-036 (one control per data type; required binds INPUT
//           placements only) · BR-SHL-037 (the EXISTING error envelope,
//           `field_errors[]` keyed `custom_data.<key>`) · BR-SHL-038 (custom
//           columns are AVAILABLE, never default; unsorted in R2) ·
//           BR-SHL-039 (one CSV column per active field, IS-11 formats) ·
//           BR-TEN-048 (never a money input) · BR-TEN-050 (a deactivated field
//           is gone from every surface; its values survive)
// ───────────────────────────────────────────────────────
// THE ONE COMPONENT THAT TURNS A DEFINITION INTO PIXELS.
//
// A screen drops `<CustomFields entity="assets" screen="S51" mode="input" … />`
// into a cleared slot ONCE, and every field the tenant defines afterwards
// appears there with no further code and no deploy. B8 LAW 0 says an
// abstraction earns its place on the third use; this one has eight entities and
// nine screens before a line is written, and the alternative is the same
// rendering logic pasted into four modules.
//
// **THE HAZARD THIS FILE IS MOST EXPOSED TO IS G13 / hard-won law 2.** A
// renderer with an optional prop nothing passes is dead UI: it renders nothing,
// every test passes, and the feature does not exist. Four defects in one day
// came from exactly that. So: every prop here is REQUIRED except `client`
// (the injectable test seam every page takes) — there is no optional
// "customFields" prop for a caller to forget, and the callers are listed in the
// Lifecycle trailer by file.
//
// US-SHL-015 TC-4: **a tenant with no fields renders NOTHING AT ALL** — no
// heading, no empty section, no layout shift. `null`, not an empty <section>.
import { useQueries, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCustomFieldRegistry } from "@/api/endpoints";
import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";

import { CheckboxField, SelectField, TextField, useFieldError } from "./FormModal";
import type { TableColumnConfig } from "./tableTypes";


export type CustomFieldValues = Record<string, unknown>;

/**
 * BR-SHL-037: the server keys its refusals `custom_data.<key>`, so the control
 * asks for its error under exactly that id and FormModal's existing context
 * highlights it. No second error path is invented for custom fields.
 */
export function fieldErrorId(key: string): string {
  return `custom_data.${key}`;
}

/**
 * Never `null`, never `undefined`, never the string "None" — US-SHL-016 TC-4.
 * A missing value renders as an EMPTY string in every surface: the detail page,
 * the list column and the CSV cell.
 */
export function displayValue(
  field: CustomFieldRegistryEntry,
  values: CustomFieldValues,
  formatDate: (iso: string) => string,
  t: (key: string) => string,
): string {
  const raw = values[field.key];
  if (raw === null || raw === undefined || raw === "") {
    return "";
  }
  switch (field.data_type) {
    case "boolean":
      // ⚠ UNRATIFIED, AND FLAGGED RATHER THAN CHOSEN. BR-TEN-082 records that a
      // boolean custom field prints `Yes`/`No` in ENGLISH on a bill that may be
      // Spanish, and names it as the weakest part of the format grant — the one
      // to put back to the PO. On SCREEN we render the catalogue's own yes/no,
      // so a Spanish user reads Sí/No here while the BILL says Yes/No. That
      // divergence is deliberate and is ROUTED as OQ-212, not resolved here.
      return t(raw === true || raw === "true" ? "settings.customFields.yes" : "settings.customFields.no");
    case "date":
      // ⚠ ALSO UNRATIFIED. The screen renders the tenant's IS-8 regional format
      // via the caller's formatter; the BILL deliberately prints ISO 8601
      // (`2026-03-04`, never `03/04/2026`) and a CSV export uses ISO per IS-11.
      // Three surfaces, two formats, one stored value — OQ-211, not chosen here.
      return formatDate(String(raw));
    case "multi_select":
      return Array.isArray(raw) ? raw.join(", ") : String(raw);
    default:
      // `number` included: it is stored as the string the operator typed and is
      // rendered verbatim. It is NOT money — no MoneyCell, no grouping, no
      // 2-decimal rounding — because BR-TEN-048 keeps it out of every money
      // path and a grouped identifier (`10,432` for `10432`) would be wrong.
      return String(raw);
  }
}

// ⚠ AMENDED 2026-10-02 (`CR-161-BRC10` W3): the LIST-COLUMN half IS built now —
// `useCustomFieldColumns` below, called by the premises list, the assets list and
// the Premise page's Units tab, whose rows now carry `custom_data`. The CSV half
// is still not built, and the note below remains true for it.
// ── US-SHL-016's LIST-COLUMN and CSV halves are NOT BUILT, and this is where
// they would live. Read this before adding them.
//
// BR-SHL-038 (IS-5 column chooser: available, never default) and BR-SHL-039
// (one CSV column per active field, headed with the LABEL, IS-11 formats) each
// need a CONSUMER, and in R2 there is no consumer this lane could reach:
//
//   · The CSV is written SERVER-side (`apps/tenancy/exports.py` →
//     `ExportResource`, whose `columns` tuple is frozen per resource). The four
//     resources registered today — premises, units, assets, reads — are
//     registered by `apps/assets/exports.py` and `apps/metering/exports.py`,
//     and there is NO `accounts` export resource at all. Appending custom
//     columns means making `ExportResource.header` tenant-dependent AND having
//     each owning module serialize `custom_data` onto its rows.
//   · The list screens with a column chooser (S49 · S14 · S15) read those same
//     modules' list payloads, none of which carries `custom_data`.
//
// Client-side helpers for both were WRITTEN AND THEN DELETED rather than left
// here green and uncalled: a tested function nothing calls is exactly the dead
// UI hard-won law 2 was written about, and it would have read in the lane
// report as "exports done". The gap is reported instead, with the one change
// each half needs. `displayValue` above is the piece a column cell would use
// when that day comes.

/**
 * `CR-161-BRC10` W4 — the LABELS of the required fields left unanswered on one
 * slot. A WIZARD step has no FormModal error context to highlight a server
 * refusal in, so it asks this before Continue and names what is missing; the
 * server's refusal (`custom_data.<key>`) stays the rule underneath it.
 * Empty, `null`, `undefined`, `[]` and `false`-for-a-checkbox count as
 * unanswered only where the server agrees: a Yes/No answered "No" is an answer.
 */
export function missingRequiredLabels(
  fields: CustomFieldRegistryEntry[],
  values: CustomFieldValues,
): string[] {
  return fields
    .filter((field) => field.is_required)
    .filter((field) => {
      const value = values[field.key];
      if (field.data_type === "boolean") return value === undefined || value === null;
      if (Array.isArray(value)) return value.length === 0;
      return value === undefined || value === null || String(value).trim() === "";
    })
    .map((field) => field.label);
}

/**
 * `DEF-CUS-9158` — what an EDIT sends: only the keys whose answer changed, a
 * cleared answer as `null` (the server clears it). Empty, `null`, `undefined`
 * and `[]` are one state, as they are in the stored blob and the CSV cell.
 */
export function customDataChanges(
  before: CustomFieldValues,
  after: CustomFieldValues,
): CustomFieldValues {
  const norm = (value: unknown): string => {
    if (value === undefined || value === null || value === "") return "";
    if (Array.isArray(value)) return value.length === 0 ? "" : JSON.stringify(value);
    return JSON.stringify(value);
  };
  const out: CustomFieldValues = {};
  for (const key of Object.keys(after)) {
    if (norm(after[key]) === norm(before[key])) continue;
    out[key] = norm(after[key]) === "" ? null : after[key];
  }
  return out;
}

/** The registry for one slot — exported so a form that renders
 *  `CustomFieldsInput` can name the same fields in its recap from the SAME
 *  cached read, rather than asking the server twice. */
export function useCustomFieldRegistry(params: {
  entity: string;
  screen: string;
  mode: "input" | "view";
  client?: ApiClient;
}) {
  return useRegistry({ ...params, client: params.client ?? api });
}

function useRegistry(params: {
  entity: string;
  screen: string;
  mode: "input" | "view";
  client: ApiClient;
}) {
  return useQuery({
    queryKey: queryKeys.customFieldRegistry(params.entity, params.screen, params.mode),
    queryFn: () =>
      getCustomFieldRegistry(
        { entity: params.entity, screen: params.screen, mode: params.mode },
        params.client,
      ),
    // A screen that cannot reach the registry must still render its OWN
    // fields. `[]` on failure is honest here in a way it would not be for a
    // money read: the custom section is additive, and the alternative is a
    // whole page failing because an optional section could not load.
    retry: 1,
  });
}

// ── US-SHL-015 — capture ───────────────────────────────────────────────────

export function CustomFieldsInput(props: {
  entity: string;
  screen: string;
  values: CustomFieldValues;
  onChange: (values: CustomFieldValues) => void;
  tenantName?: string;
  /** `CR-161-BRC10` W3 — a section that is ONE OF SEVERAL on a form names
   *  what it belongs to instead of the tenant: a service point's block reads
   *  *Water*, *Electric*. Omitted, the heading names the tenant as before. */
  heading?: string;
  /**
   * Lane CF-1 (2026-10-18) — the controls ALONE, two across, for a host that
   * draws its own panel and heading: the shared customer form's *More about
   * the customer* (drawing set `customer-forms-2026-10-18`, image 01). An
   * opt-in under B14 rule 36 — absent renders byte-for-byte as before.
   */
  bare?: boolean;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const registry = useRegistry({
    entity: props.entity,
    screen: props.screen,
    mode: "input",
    client,
  });
  const fields = registry.data ?? [];
  if (fields.length === 0) {
    return null; // TC-4: nothing at all — no heading, no empty section
  }

  function set(key: string, value: unknown): void {
    props.onChange({ ...props.values, [key]: value });
  }

  if (props.bare === true) {
    return (
      <div className="grid grid-cols-2 gap-x-6 gap-y-5" data-custom-fields-bare={props.entity}>
        {fields.map((field) => (
          <CustomFieldControl
            key={field.key}
            field={field}
            value={props.values[field.key]}
            onChange={(value) => set(field.key, value)}
          />
        ))}
      </div>
    );
  }

  return (
    // CR-018 Route B: CustomFields.css (deleted) ported value for value — the
    // quiet divider-topped section below the platform's own fields
    // (US-SHL-015 §1). `.custom-fields-input`'s own `gap` declaration was
    // INERT (the section was never a grid or flex container) and is dropped,
    // which renders identically.
    <section className="mt-4 border-t border-divider pt-3">
      {/* The heading names the TENANT, not the platform (US-SHL-015 §1).
          tracking-label is the named 0.04em of this uppercase register. */}
      <h3 className="m-0 mb-3 font-heading text-base font-extrabold uppercase tracking-label text-neutral-600">
        {sectionHeading(props.heading, props.tenantName, t)}
      </h3>
      {fields.map((field) => (
        <CustomFieldControl
          key={field.key}
          field={field}
          value={props.values[field.key]}
          onChange={(value) => set(field.key, value)}
        />
      ))}
    </section>
  );
}

export function CustomFieldControl(props: {
  field: CustomFieldRegistryEntry;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const { t } = useTranslation();
  const { field } = props;
  const id = fieldErrorId(field.key);
  const error = useFieldError(id);
  const help = field.help_text === "" ? undefined : field.help_text;

  // BR-SHL-036, one control per data type and no sixth branch invented.
  // ⚠ `DEF-SHL-9240` (2026-10-03): a Yes/No is a CHOICE — nothing chosen, Yes,
  // No — and never a single tick box. A box has two states for three answers:
  // an untouched box saved nothing, so a clerk could not record "No", the view
  // stayed blank and approval had nothing to copy. The portal already asks it
  // this way; staff screens now match. Picking the empty option clears it.
  if (field.data_type === "boolean") {
    const shown =
      props.value === true || props.value === "true"
        ? "true"
        : props.value === false || props.value === "false"
          ? "false"
          : "";
    return (
      <SelectField
        id={id}
        label={field.label}
        value={shown}
        onChange={(value) => props.onChange(value === "" ? null : value === "true")}
        required={field.is_required}
        help={help}
        placeholder={t("customFields.chooseOne")}
        options={[
          { value: "true", label: t("settings.customFields.yes") },
          { value: "false", label: t("settings.customFields.no") },
        ]}
        error={error}
      />
    );
  }
  if (field.data_type === "select") {
    return (
      <SelectField
        id={id}
        label={field.label}
        value={props.value === undefined || props.value === null ? "" : String(props.value)}
        onChange={(value) => props.onChange(value)}
        required={field.is_required}
        help={help}
        placeholder={t("customFields.chooseOne")}
        options={field.options.map((option) => ({ value: option, label: option }))}
        error={error}
      />
    );
  }
  if (field.data_type === "multi_select") {
    const chosen = Array.isArray(props.value) ? (props.value as string[]) : [];
    return (
      <fieldset className="field m-0 mb-3 border-0 p-0" aria-invalid={error !== undefined}>
        {/* CR-018 Route B: `.custom-field-multi legend` travels onto the
            element — p-0, --text-base, neutral-600. */}
        <legend className="p-0 text-base text-neutral-600">{field.label}</legend>
        {field.options.map((option) => (
          <CheckboxField
            key={option}
            id={`${id}.${option}`}
            label={option}
            checked={chosen.includes(option)}
            onChange={(checked) =>
              props.onChange(
                checked
                  ? // The tenant's OWN option order is preserved, so a screen,
                    // an export and a bill list the choices the same way.
                    field.options.filter((o) => o === option || chosen.includes(o))
                  : chosen.filter((o) => o !== option),
              )
            }
          />
        ))}
        {help !== undefined && <p className="field-help mt-1.5 mb-0">{help}</p>}
        {error !== undefined && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
      </fieldset>
    );
  }
  // text · number · date all use the text control. `date` deliberately does NOT
  // use DatePickerField here: the platform date control needs the tenant's IS-8
  // format, which is a screen-level concern the caller owns, and the STORED
  // value is ISO-8601 either way. Stated rather than left as an oversight.
  return (
    <TextField
      id={id}
      label={field.label}
      value={props.value === undefined || props.value === null ? "" : String(props.value)}
      onChange={(value) => props.onChange(value)}
      required={field.is_required}
      help={help}
      // BR-TEN-048: `numeric` is a KEYPAD hint and tabular numerals, not a
      // money control. Nothing here parses the value into a number.
      numeric={field.data_type === "number"}
      placeholder={field.data_type === "date" ? "YYYY-MM-DD" : undefined}
      error={error}
    />
  );
}

// ── US-SHL-016 — display ───────────────────────────────────────────────────

export function CustomFieldsView(props: {
  entity: string;
  screen: string;
  values: CustomFieldValues;
  formatDate: (iso: string) => string;
  tenantName?: string;
  /** See `CustomFieldsInput`'s `heading`. */
  heading?: string;
  /**
   * `CR-161-BRC10` W6, gap 2 — *"Request detail always shows the request's
   * copy of every intake field"*. Names the INPUT screen whose fields this view
   * shows as well as its own View placements, so a field typed on Staff New
   * Request is read back on Request detail whatever its Request detail choice
   * says. Each field once, in the registry's order.
   */
  //
  // ⊕ `CR-161-BRC10` W7 (`DEF-CUS-9214`) — a LIST as well as one screen. A
  // request has two input screens now: the clerk's New request and the
  // customer portal's new-service form. A field asked only on the portal was
  // on the request's copy and invisible on its page while this took one.
  alsoInputOf?: string | readonly string[];
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const registry = useRegistry({
    entity: props.entity,
    screen: props.screen,
    mode: "view",
    client,
  });
  const intakeScreens =
    props.alsoInputOf === undefined
      ? []
      : typeof props.alsoInputOf === "string"
        ? [props.alsoInputOf]
        : [...props.alsoInputOf];
  const intake = useQueries({
    queries: intakeScreens.map((screen) => ({
      queryKey: queryKeys.customFieldRegistry(props.entity, screen, "input"),
      queryFn: () =>
        getCustomFieldRegistry({ entity: props.entity, screen, mode: "input" }, client),
      retry: 1,
    })),
  });
  const viewFields = registry.data ?? [];
  const seen = new Set(viewFields.map((field) => field.key));
  const fields = [...viewFields];
  for (const answer of intake) {
    for (const field of answer.data ?? []) {
      if (!seen.has(field.key)) {
        seen.add(field.key);
        fields.push(field);
      }
    }
  }
  if (fields.length === 0) {
    return null;
  }
  return (
    // CR-018 Route B: the view mode — same section frame; the old
    // `.custom-fields-view` gap was inert (see the input mode note).
    <section className="mt-4 border-t border-divider pt-3">
      <h3 className="m-0 mb-3 font-heading text-base font-extrabold uppercase tracking-label text-neutral-600">
        {sectionHeading(props.heading, props.tenantName, t)}
      </h3>
      <dl className="m-0 grid gap-2">
        {fields.map((field) => (
          <div key={field.key} className="flex items-baseline gap-3">
            <dt className="min-w-[180px] text-neutral-600">{field.label}</dt>
            {/* US-SHL-016 TC-4: an empty value renders as an EMPTY cell; the
                min-height keeps the row from reflowing as values arrive. */}
            <dd className="m-0 min-h-[1.2em]">{displayValue(field, props.values, props.formatDate, t)}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function sectionHeading(
  heading: string | undefined,
  tenantName: string | undefined,
  t: (key: string, params?: Record<string, unknown>) => string,
): string {
  if (heading !== undefined && heading !== "") return heading;
  return tenantName === undefined || tenantName === ""
    ? t("customFields.sectionHeadingFallback")
    : t("customFields.sectionHeading", { tenant: tenantName });
}

// ── CR-161-BRC10 W3 — the review recap and the table columns ───────────────

/**
 * **A REVIEW STEP LISTS WHAT WAS TYPED, AUTOMATICALLY** (PO Roof Material
 * table: *"Add Premises · Step 2 Details — Input / Not shown (Step 3 Review
 * lists answers automatically)"*). It reads the SAME input-mode registry the
 * form's `CustomFieldsInput` read — one cached answer, so the recap can never
 * name a field the form did not draw — and renders nothing at all when there
 * is none. It is deliberately not a `CustomFieldsView`: that reads the VIEW
 * placements of a screen, and a review step is not a place a field is placed.
 */
export function CustomFieldsAnswers(props: {
  entity: string;
  screen: string;
  values: CustomFieldValues;
  heading?: string;
  tenantName?: string;
  client?: ApiClient;
}) {
  const { t } = useTranslation();
  const registry = useRegistry({
    entity: props.entity,
    screen: props.screen,
    mode: "input",
    client: props.client ?? api,
  });
  const fields = registry.data ?? [];
  if (fields.length === 0) {
    return null;
  }
  return (
    <section className="mt-4 border-t border-divider pt-3" data-custom-answers={props.entity}>
      <h3 className="m-0 mb-3 font-heading text-base font-extrabold uppercase tracking-label text-neutral-600">
        {sectionHeading(props.heading, props.tenantName, t)}
      </h3>
      <dl className="m-0 grid gap-2">
        {fields.map((field) => (
          <div key={field.key} className="flex items-baseline gap-3">
            <dt className="min-w-[180px] text-neutral-600">{field.label}</dt>
            <dd className="m-0 min-h-[1.2em]">
              {displayValue(field, props.values, (iso) => iso, t)}
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

/**
 * The server's custom-field refusals as the sentences the controls show, keyed
 * exactly as `CustomFieldControl` asks (`custom_data.<key>`). For a full-page
 * wizard, which renders the controls inside `FieldErrorsScope` rather than a
 * `FormModal` (`CR-161-BRC10` W3).
 */
export function customFieldErrors(
  fieldErrors: readonly {
    field: string | null;
    message_key: string;
    params?: Record<string, unknown>;
  }[],
  t: (key: string, params?: Record<string, unknown>) => string,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const fieldError of fieldErrors) {
    if (fieldError.field !== null && fieldError.field.startsWith("custom_data.")) {
      out[fieldError.field] = t(fieldError.message_key, fieldError.params ?? {});
    }
  }
  return out;
}

/** One labelled set of answers inside a table cell — a unit's own, or one
 *  service point's (`prefix` names the service). */
export interface CustomFieldCellValues {
  prefix?: string;
  values: CustomFieldValues;
}

/**
 * **A LIST OR TABLE COLUMN PER FIELD PLACED ON THAT SCREEN.** BR-SHL-038's
 * *available, never default* is now the tenant's own choice in Settings: a
 * list slot offers *Show as column / Not shown*, default Not shown, so a field
 * reaches a list only because somebody asked for it — and then it is shown.
 * The registry is the screen's VIEW placements.
 *
 * ⚠ **WRITE THE CALL `useCustomFieldColumns<Row>({ entity: "…", screen: "…",
 * … })` WITH LITERAL STRINGS**, because
 * `tests/test_cr161_w1_custom_field_settings.py` pairs each call with the slot
 * list exactly as it pairs `<CustomFieldsInput …>`. A computed entity would be
 * a column no test could see.
 */
export function useCustomFieldColumns<Row>(params: {
  entity: string;
  screen: string;
  valuesOf: (row: Row) => readonly CustomFieldCellValues[];
  client?: ApiClient;
}): TableColumnConfig<Row>[] {
  const { t } = useTranslation();
  const registry = useRegistry({
    entity: params.entity,
    screen: params.screen,
    mode: "view",
    client: params.client ?? api,
  });
  return (registry.data ?? []).map((field) => ({
    key: `custom.${params.entity}.${field.key}`,
    label: field.label,
    cell: (row: Row) =>
      params
        .valuesOf(row)
        .map((set) => {
          const text = displayValue(field, set.values, (iso) => iso, t);
          if (text === "") return "";
          return set.prefix === undefined ? text : `${set.prefix}: ${text}`;
        })
        .filter((text) => text !== "")
        .join(" · "),
  }));
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-015@a1c9f04 (story+rules snapshot over EP-SHL-07-custom-field-rendering.md +
//         00-platform-shell/02-business-rules.md BR-SHL-036..039 +
//         01-tenancy/02-business-rules.md BR-TEN-046..053 + BR-TEN-082)
// generated: 2026-08-15 by story-coder (tenant custom-fields lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest — see the lane report · G13 unwired-props: every prop except the `client` test seam is REQUIRED, and the live callers are — ⚠ CORRECTED 2026-10-02 (`CR-161-BRC10` W1, `DEF-TEN-9153`): this line named AssetDetailPage (S50), AssetLifecycleModals (S51) and AddPremisesWizard (S16), and none of the three renders this component any more, which is how Settings came to offer three screens that drew nothing (hard-won law 1) — features/customers/NewAccountWizard.tsx (input, S18), NewConnectOwnerStep.tsx (input, S18; its values reach the owner account since 2.459.0, DEF-CUS-9159), AccountDetailPage.tsx (view, S21) and AccountPanelEdits.tsx (input, S21). Do not restate the list from memory: `06-backend/tests/test_cr161_w1_custom_field_settings.py` reads every caller and pairs it with `custom_fields.SLOTS` · AMENDED 2026-10-02 (`CR-161-BRC10` W3): the metering and assets callers are AddPremisesWizard, AddUnitsWizard, UnitEditModal, PremisesListPage (edit + list column), PremisesDetailPage (page + Units-tab columns), NewConnectPremiseStep, AssetAddWizard, AssetEditPage, AssetDetailPage and AssetRegistryPage (column) — and the same test now pairs `useCustomFieldColumns` calls too · AMENDED 2026-10-02 (`CR-161-BRC10` W3, customers lane, 2.459.0): the contacts, addresses and service_agreements callers are AccountPanelEdits (contact and mailing edits), AccountDetailPage (Customer, Mailing address and Services groups), NewAccountWizard (mailing block and unit step) and ChangePlanWizard (confirm step)
// exceptions: (1) the BOOLEAN and DATE display formats diverge from what a BILL prints, and both divergences are UNRATIFIED readings on BR-TEN-082 — FLAGGED here and in the lane report, chosen by nobody in this lane · (2) `date` uses the text control, not DatePickerField: the platform date control needs the tenant's IS-8 format, which the caller owns; the stored value is ISO-8601 either way · (3) sorting and filtering over custom columns are OUT of R2 (BR-SHL-038) so `customColumnConfigs` sets no `sortable` · (4) a registry read that fails renders NO custom section rather than failing the page — honest for an additive section, and it would NOT be honest for a money read
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
