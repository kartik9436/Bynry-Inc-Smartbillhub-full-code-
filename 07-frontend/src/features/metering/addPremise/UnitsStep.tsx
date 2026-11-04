// ── Trace ──────────────────────────────────────────────
// Change:   CR-177-BRC10 task 11 — step 2, *Units*: how many units and their
//           type, the first unit's own custom fields and its services' (kept
//           from the old screen, `CR-161-BRC10` W3), and Common areas as a
//           closed section.
// Rules:    BR-MET-002 (a unit label is unique per premise) · BR-MET-036 (no
//           occupancy input, anywhere) · B14 rules 21, 32, 33, 43, 44
// Drawing:  05-prototype/add-premise-2026-10-09/images/09, 10
// ───────────────────────────────────────────────────────
import { useState } from "react";

import type { ApiClient } from "@/api/client";
import type { TenantServiceRow } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { CustomFieldsInput } from "@/components/CustomFields";
import { SelectField, TextField } from "@/components/FormModal";
import { Panel } from "@/components/Panel";

import { commonAreaLabels, unitLabels } from "./addPremiseModel";
import type { AddPremiseForm } from "./addPremiseModel";
import { FoldPanel, PAIR, SECTION_HEADING } from "./addPremiseShared";
import type { Translator } from "./addPremiseShared";

/** The unit types a unit may take, as the unit tables carry them. LITERAL keys
 *  so a gate can see each one is used. */
export const UNIT_TYPE_KEYS: Record<string, string> = {
  residential: "metering.units.type.residential",
  residential_submetered: "metering.units.type.residential_submetered",
  commercial: "metering.units.type.commercial",
  commercial_master: "metering.units.type.commercial_master",
  common_area: "metering.units.type.common_area",
};

export function unitTypeWord(code: string, t: Translator): string {
  const key = UNIT_TYPE_KEYS[code];
  return key === undefined ? code : t(key);
}

export function UnitsStep(props: {
  form: AddPremiseForm;
  onForm: (next: AddPremiseForm) => void;
  services: readonly TenantServiceRow[];
  commonOpen: boolean;
  onToggleCommon: () => void;
  t: Translator;
  client?: ApiClient;
}) {
  const { form, t } = props;
  const set = (patch: Partial<AddPremiseForm>) => props.onForm({ ...form, ...patch });
  const [draft, setDraft] = useState("");
  const areas = commonAreaLabels(form);
  const firstLabel = unitLabels(form.unit_count)[0];

  function addArea(): void {
    const label = draft.trim();
    if (label === "") return;
    set({ common_areas: [...form.common_areas, label] });
    setDraft("");
  }

  return (
    <div className="flex flex-col gap-5" data-add-premise-step="units">
      <Panel as="section" aria-labelledby="add-premise-units">
        <h2 id="add-premise-units" className={SECTION_HEADING}>
          {t("metering.addPremise.units.title")}
        </h2>
        <div className={PAIR}>
          <TextField
            id="unit_count"
            label={t("metering.addPremise.units.howMany")}
            numeric
            value={form.unit_count}
            help={t("metering.addPremise.units.howManyHelp")}
            onChange={(unit_count) => set({ unit_count })}
          />
          <SelectField
            id="unit_type"
            label={t("metering.units.field.type")}
            value={form.unit_type}
            placeholder={t("metering.units.field.typePlaceholder")}
            options={Object.keys(UNIT_TYPE_KEYS).map((code) => ({ value: code, label: unitTypeWord(code, t) }))}
            onChange={(unit_type) => set({ unit_type })}
          />
        </div>
        {/* The FIRST unit's own fields, then one block per service it takes —
            each renders nothing at all for a utility with none. */}
        {firstLabel !== undefined && (
          <>
            <CustomFieldsInput
              entity="units"
              screen="S16"
              heading={`${t("metering.units.col.label")} ${firstLabel}`}
              values={form.unit_custom_data}
              onChange={(unit_custom_data) => set({ unit_custom_data })}
              client={props.client}
            />
            {form.services.map((code) => (
              <CustomFieldsInput
                entity="service_points"
                screen="S16"
                key={code}
                heading={props.services.find((row) => row.service === code)?.name ?? code}
                values={form.service_point_custom_data[code] ?? {}}
                onChange={(answers) =>
                  set({ service_point_custom_data: { ...form.service_point_custom_data, [code]: answers } })
                }
                client={props.client}
              />
            ))}
          </>
        )}
      </Panel>

      <FoldPanel
        id="add-premise-common"
        title={t("metering.premises.commonAreas.label")}
        state={areas.length === 0 ? t("metering.addPremise.common.none") : areas.join(" · ")}
        open={props.commonOpen}
        onToggle={props.onToggleCommon}
      >
        <div className={PAIR}>
          <TextField
            id="common_area_draft"
            label={t("metering.addPremise.common.field")}
            value={draft}
            placeholder={t("metering.addPremise.common.placeholder")}
            onChange={setDraft}
          />
        </div>
        <div>
          <Button onClick={addArea} disabled={draft.trim() === ""}>
            {t("metering.premises.commonAreas.add")}
          </Button>
        </div>
        {form.common_areas.length > 0 && (
          <ul className="m-0 flex list-none flex-col gap-2 p-0" data-common-areas="">
            {form.common_areas.map((label, index) => (
              <li key={`${label}-${index}`} className="flex items-center gap-3">
                <span>{label}</span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => set({ common_areas: form.common_areas.filter((_, at) => at !== index) })}
                >
                  {t("metering.premises.commonAreas.remove")}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </FoldPanel>
    </div>
  );
}
