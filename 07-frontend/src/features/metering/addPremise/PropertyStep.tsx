// ── Trace ──────────────────────────────────────────────
// Change:   CR-177-BRC10 tasks 7–10 — step 1, *Property*: one Address section
//           (street; City · State · ZIP on one line; Check address; property
//           type and City limits; Services), then Map (only after a match),
//           Owner, Area & sub-area and Custom fields as closed sections.
// Rulings:  PO 2026-10-09, verbatim: *"keep thme in same section"* · *"instead
//           of premises - call it address"* · *"keep in in 1 line ineatsd of
//           2"* · *"City limits - make this drop down; Services - also multi
//           seelct drop down - active services for that utility; Reading &
//           billing - headline should change to area and sub area; Your own
//           fields - call it custom field - and make it collasable; and also
//           proide link for custom field in settings"*
// Rules:    BR-MET-1190 (the same address) · BR-MET-1191 (Check address, never
//           search while typing) · BR-MET-1192 (Use these details) ·
//           BR-MET-1193 (active services, none ticked) · BR-MET-1194 (required
//           custom fields) · BR-MET-071 (area and sub-area, one column) ·
//           BR-MET-073 (the cycle follows the route) · BR-MET-076 (only ACTIVE
//           routes are offered) · B14 rules 21, 31, 32, 33, 43, 44
// Drawing:  05-prototype/add-premise-2026-10-09/images/01–08, 13, 14
// ───────────────────────────────────────────────────────
import type { ApiClient } from "@/api/client";
import type { LookupEntry, PremisesType, RouteRow, TenantServiceRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { CheckDropdown } from "@/components/CheckDropdown";
import { CustomFieldControl } from "@/components/CustomFields";
import type { CustomFieldRegistryEntry } from "@/api/endpoints";
import { SelectField, TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { InlineLinkTo } from "@/components/Surfaces";
import { subAreasOf, topLevelAreas } from "@/features/metering/meteringShared";

import { pointText } from "./addPremiseModel";
import type { AddPremiseForm, AddressCheck, OwnerState, SameAddressState } from "./addPremiseModel";
import { CITY_LINE, FoldPanel, PAIR, ResultBox, SECTION_HEADING } from "./addPremiseShared";
import type { Translator } from "./addPremiseShared";
import { CityAddressCheck } from "./CityAddressCheck";
import { OwnerSection } from "./OwnerSection";

/** The settings page that manages a tenant's own fields (the reference-data
 *  card `custom_fields`). Tenant-relative; the caller puts it through
 *  `tenantPath`. */
export const CUSTOM_FIELDS_SETTINGS_ROUTE = "/settings/reference-data/reference-data?list=custom_fields";

/** Which closed sections are open. */
export interface OpenSections {
  map: boolean;
  owner: boolean;
  area: boolean;
  custom: boolean;
}

export interface PropertyStepProps {
  form: AddPremiseForm;
  onForm: (next: AddPremiseForm) => void;
  /** Called when the address loses focus — the same-address check runs then. */
  onAddressDone: () => void;
  types: readonly PremisesType[];
  services: readonly TenantServiceRow[];
  routes: readonly RouteRow[];
  /** Why the route list is the length it is (`DEF-MET-4758`): an empty box
   *  that is loading, failed or truly empty says which. */
  routesState: "loading" | "failed" | "ready";
  areas: readonly LookupEntry[];
  customFields: readonly CustomFieldRegistryEntry[];
  check: AddressCheck;
  onCheck: () => void;
  onUseDetails: () => void;
  onKeepMine: () => void;
  same: SameAddressState | null;
  onOpenSame: () => void;
  onAddAnyway: () => void;
  owner: OwnerState;
  onOwner: (next: OwnerState) => void;
  open: OpenSections;
  onToggle: (section: keyof OpenSections) => void;
  /** The tenant path of the custom-fields settings page. */
  customFieldsSettingsTo: string;
  formatDate: (iso: string) => string;
  t: Translator;
  client?: ApiClient;
}

const CITY_LIMITS: { value: string; key: string }[] = [
  { value: "", key: "metering.addPremise.cityLimits.notRecorded" },
  { value: "inside", key: "metering.addPremise.cityLimits.inside" },
  { value: "outside", key: "metering.addPremise.cityLimits.outside" },
];

/** A premise's status in the clerk's words — LITERAL keys, so a gate can see
 *  each one is used; an unknown status is shown as the server sent it. */
const PREMISE_STATUS_KEYS: Record<string, string> = {
  draft: "metering.premises.status.draft",
  pending: "metering.premises.status.pending",
  active: "metering.premises.status.active",
  inactive: "metering.premises.status.inactive",
};

export function premiseStatusWord(status: string, t: Translator): string {
  const key = PREMISE_STATUS_KEYS[status];
  return key === undefined ? status : t(key);
}

export function cityLimitsValue(flag: boolean | null): string {
  return flag === null ? "" : flag ? "inside" : "outside";
}

export function cityLimitsWord(flag: boolean | null, t: Translator): string {
  return t(CITY_LIMITS.find((row) => row.value === cityLimitsValue(flag))?.key ?? CITY_LIMITS[0].key);
}

export function PropertyStep(props: PropertyStepProps) {
  return (
    <div className="flex flex-col gap-5" data-add-premise-step="property">
      <AddressSection {...props} />
      {props.check.kind === "match" && <MapSection {...props} />}
      <OwnerSection
        owner={props.owner}
        onOwner={props.onOwner}
        open={props.open.owner}
        onToggle={() => props.onToggle("owner")}
        t={props.t}
        client={props.client}
      />
      <AreaSection {...props} />
      <CustomFieldsSection {...props} />
    </div>
  );
}

function AddressSection(props: PropertyStepProps) {
  const { form, t } = props;
  const set = (patch: Partial<AddPremiseForm>) => props.onForm({ ...form, ...patch });
  const blocked = props.same !== null && props.same.choice === null;
  return (
    <Panel as="section" aria-labelledby="add-premise-address">
      <h2 id="add-premise-address" className={SECTION_HEADING}>
        {t("metering.addPremise.section.address")}
      </h2>
      <div className="flex flex-col gap-5" onBlur={(event) => {
        // Only when focus LEAVES the four address boxes, not when it moves
        // between them — the check is about the whole address.
        const next = event.relatedTarget as Node | null;
        if (next === null || !event.currentTarget.querySelector("[data-address-parts]")?.contains(next)) {
          props.onAddressDone();
        }
      }}>
        <div className="flex flex-col gap-5" data-address-parts="">
          <TextField
            id="address_line"
            label={t("metering.premises.field.address")}
            required
            value={form.address_line}
            onChange={(address_line) => set({ address_line })}
          />
          <div className={CITY_LINE}>
            <TextField id="city" label={t("metering.premises.field.city")} value={form.city} onChange={(city) => set({ city })} />
            <TextField id="state" label={t("metering.premises.field.state")} value={form.state} onChange={(state) => set({ state })} />
            <TextField
              id="postal_code"
              label={t("metering.addPremise.field.zip")}
              value={form.postal_code}
              onChange={(postal_code) => set({ postal_code })}
            />
          </div>
        </div>
      </div>

      <CityAddressCheck
        check={props.check}
        onCheck={props.onCheck}
        onUseDetails={props.onUseDetails}
        onKeepMine={props.onKeepMine}
        t={t}
      />

      {props.same !== null && (
        <div className="mt-5">
          <ResultBox
            tone="warn"
            role={blocked ? "alert" : "status"}
            data-result="same-address"
            title={
              props.same.choice === "anyway"
                ? t("metering.addPremise.dup.adding", { premise: props.same.premise.premise_no })
                : t("metering.premises.same_address_exists")
            }
            facts={[
              { id: "premise", label: t("metering.addPremise.dup.premise"), value: props.same.premise.premise_no },
              { id: "address", label: t("metering.addPremise.dup.address"), value: props.same.premise.address },
              {
                id: "units",
                label: t("metering.addPremise.dup.unitsStatus"),
                value: `${props.same.premise.units} · ${premiseStatusWord(props.same.premise.status, t)}`,
              },
            ]}
            actions={
              props.same.choice === null ? (
                <>
                  <Button variant="primary" onClick={props.onOpenSame}>
                    {t("metering.addPremise.dup.open", { premise: props.same.premise.premise_no })}
                  </Button>
                  <Button onClick={props.onAddAnyway}>{t("metering.addPremise.dup.anyway")}</Button>
                </>
              ) : undefined
            }
          />
        </div>
      )}

      <div className={`mt-5 ${PAIR}`}>
        <SelectField
          id="premises_type"
          label={t("metering.premises.field.type")}
          value={form.premises_type}
          placeholder={t("metering.premises.field.typePlaceholder")}
          options={props.types.filter((type) => type.active).map((type) => ({ value: type.code, label: type.name }))}
          onChange={(premises_type) => set({ premises_type })}
        />
        <SelectField
          id="inside_city_limits"
          label={t("metering.premises.field.jurisdiction")}
          value={cityLimitsValue(form.inside_city_limits)}
          options={CITY_LIMITS.map((row) => ({ value: row.value, label: t(row.key) }))}
          help={t("metering.addPremise.cityLimits.help")}
          onChange={(value) => set({ inside_city_limits: value === "" ? null : value === "inside" })}
        />
      </div>
      <div className="mt-5">
        <CheckDropdown
          id="services_available"
          label={t("metering.addPremise.field.services")}
          mode="every"
          allLabel={t("metering.addPremise.services.all")}
          placeholder={t("metering.addPremise.services.choose")}
          options={props.services.map((row) => ({ value: row.service, label: row.name }))}
          selected={form.services}
          help={t("metering.addPremise.services.help")}
          onChange={(services) => set({ services })}
        />
      </div>
    </Panel>
  );
}

/** Map — shown only after the City matched (PO 2026-10-09; amended rule 7: map
 *  fields only for a utility with a City map). Read-only: the City's figures,
 *  written at the save only when *Use these details* was pressed. */
function MapSection(props: PropertyStepProps) {
  const { check, t } = props;
  if (check.kind !== "match") return null;
  const used = check.used;
  return (
    <FoldPanel
      id="add-premise-map"
      title={t("metering.addPremise.map.title")}
      state={used ? t("metering.premises.gis.checked") : t("metering.addPremise.check.notChecked")}
      open={props.open.map}
      onToggle={() => props.onToggle("map")}
    >
      <dl className="m-0 grid grid-cols-3 gap-x-4" data-add-premise-map="">
        {[
          ["parcel", t("metering.addPremise.check.parcel"), used ? check.match.parcel : "—"],
          ["point", t("metering.addPremise.check.point"), used ? pointText(check.match.lat, check.match.lng) || "—" : "—"],
          [
            "checked",
            t("metering.premises.gis.label"),
            used
              ? t("metering.addPremise.map.checkedOn", { date: props.formatDate(check.checkedOn) })
              : t("metering.addPremise.check.notChecked"),
          ],
        ].map(([id, label, value]) => (
          <div key={id} data-map-fact={id}>
            <dt className="text-sm text-neutral-700">{label}</dt>
            <dd className="m-0 font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
    </FoldPanel>
  );
}

/** The area's NAME, never its code (B14 rule 31). */
export function areaName(areas: readonly LookupEntry[], code: string): string {
  if (code === "") return "";
  return areas.find((entry) => entry.code === code)?.name ?? code;
}

/**
 * **WHICH EMPTY THE ROUTE BOX IS (`DEF-MET-4758`, PO 2026-09-10).** Loading,
 * failed and *this utility has no active route* are three facts, and the old
 * screen drew all three as one empty box the PO read as a missing dropdown.
 * Kept through the redesign as the box's own words — facts, not explanation.
 */
export function routePlaceholder(state: "loading" | "failed" | "ready", count: number, t: Translator): string {
  if (state === "loading") return t("metering.premises.route.loadingPlaceholder");
  if (state === "failed") return t("metering.premises.route.failedPlaceholder");
  if (count === 0) return t("metering.premises.route.nonePlaceholder");
  return t("metering.premises.field.routePlaceholder");
}

/** `Route 12 — North Silver Creek`, never a bare id. */
export function routeWord(row: RouteRow, t: Translator): string {
  return t("metering.premises.route.named", {
    route: row.code,
    name: row.name === null || row.name.trim() === "" ? row.code : row.name,
  });
}

function AreaSection(props: PropertyStepProps) {
  const { form, t } = props;
  const set = (patch: Partial<AddPremiseForm>) => props.onForm({ ...form, ...patch });
  const tops = topLevelAreas(props.areas);
  const subs = subAreasOf(props.areas, form.area.top);
  const cycle = props.routes.find((row) => row.code === form.route)?.cycle_code ?? null;
  return (
    <FoldPanel
      id="add-premise-area"
      title={t("metering.addPremise.area.title")}
      state={areaName(props.areas, form.area.sub || form.area.top) || t("metering.addPremise.area.none")}
      open={props.open.area}
      onToggle={() => props.onToggle("area")}
    >
      <div className={PAIR}>
        <SelectField
          id="area_code"
          label={t("metering.premises.field.area")}
          value={form.area.top}
          placeholder={t("metering.addPremise.area.none")}
          options={tops.map((area) => ({ value: area.code, label: area.name }))}
          onChange={(top) => set({ area: { top, sub: "" } })}
        />
        <SelectField
          id="sub_area_code"
          label={t("metering.premises.field.subArea")}
          value={form.area.sub}
          placeholder={form.area.top === "" ? t("metering.addPremise.area.areaFirst") : t("metering.addPremise.area.noSub")}
          options={subs.map((area) => ({ value: area.code, label: area.name }))}
          disabled={form.area.top === ""}
          onChange={(sub) => set({ area: { ...form.area, sub } })}
        />
        <SelectField
          id="route"
          label={t("metering.premises.field.readRoute")}
          value={form.route}
          placeholder={routePlaceholder(props.routesState, props.routes.length, t)}
          options={props.routes.map((row) => ({ value: row.code, label: routeWord(row, t) }))}
          onChange={(route) => set({ route })}
        />
        <TextField
          id="billing_cycle"
          label={t("metering.premises.field.billingCycle")}
          readOnly
          value={form.route === "" || cycle === null ? "" : t("metering.premises.cycle.named", { cycle })}
          placeholder={t("metering.premises.cycle.followsRoute")}
          onChange={() => undefined}
        />
      </div>
    </FoldPanel>
  );
}

/** How many REQUIRED fields on this screen are still empty. */
export function missingRequiredKeys(
  fields: readonly CustomFieldRegistryEntry[],
  values: Record<string, unknown>,
): string[] {
  return fields
    .filter((field) => field.is_required)
    .filter((field) => {
      const value = values[field.key];
      if (field.data_type === "boolean") return value === undefined || value === null;
      if (Array.isArray(value)) return value.length === 0;
      return value === undefined || value === null || String(value).trim() === "";
    })
    .map((field) => field.key);
}

function CustomFieldsSection(props: PropertyStepProps) {
  const { form, t } = props;
  const missing = missingRequiredKeys(props.customFields, form.custom_data).length;
  const state =
    props.customFields.length === 0
      ? t("metering.addPremise.custom.none")
      : missing > 0
        ? t("metering.addPremise.custom.required", { count: missing })
        : t("metering.addPremise.custom.done");
  return (
    <FoldPanel
      id="add-premise-custom"
      title={t("metering.addPremise.custom.title")}
      state={state}
      open={props.open.custom}
      onToggle={() => props.onToggle("custom")}
    >
      {props.customFields.length > 0 && (
        <div className={PAIR}>
          {props.customFields.map((field) => (
            <CustomFieldControl
              key={field.key}
              field={field}
              value={form.custom_data[field.key]}
              onChange={(value) => props.onForm({ ...form, custom_data: { ...form.custom_data, [field.key]: value } })}
            />
          ))}
        </div>
      )}
      <p className="m-0">
        <InlineLinkTo to={props.customFieldsSettingsTo} data-manage-custom-fields="">
          {t("metering.addPremise.custom.manage")} <span aria-hidden="true">→</span>
        </InlineLinkTo>
      </p>
    </FoldPanel>
  );
}
