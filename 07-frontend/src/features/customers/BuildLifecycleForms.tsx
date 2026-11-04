// ── Trace ──────────────────────────────────────────────
// Change:   CR-162-BRC10 items 7 and 8 (T2-7, T2-8) — *Add unit* (with its
//           services) and *Add service* as proper forms, from the build's More
//           menu.
// Ruling:   decision log 2026-10-02 (commit 56eb54ba9): *"7 Add unit. 8 Add
//           service as proper form."*
// Server:   `POST /connections/{id}/units` (`add_unit_to_build`) ·
//           `POST /connections/{id}/services` (`add_connection_service`).
// Rules:    B14 rule 38/44 (a form is built to our UI rules) · rule 33 ·
//           rule 43 (FormModal, the kit's one form shell) · rule 21
// ───────────────────────────────────────────────────────
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getLookupEntries } from "@/api/endpoints";
import {
  CheckboxField,
  FormModal,
  SelectField,
  TextField,
  useFieldError,
} from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import type { AddServiceOption, AddServiceUnit } from "@/features/work/buildRecord/AddServiceChoice";

import { unitTypeChoices } from "./NewConnectUnitsStep";
import type { Translator } from "./newConnectShared";

function refused(error: unknown): FormSubmitOutcome {
  if (isApiError(error)) {
    return { ok: false, error: formErrorEnvelope(error) };
  }
  return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
}

const unitSchema = (t: Translator) =>
  z.object({
    label: z.string().trim().min(1),
    // The server's own sentence for the same refusal, in every catalogue.
    services: z
      .array(z.string())
      .min(1, t("metering.build.unit_needs_a_service", { defaultValue: "Choose at least one service." })),
  });

/**
 * ⊕ **`DEF-MET-9262` — the services *Add unit* may offer: this build's own.**
 * It offered the utility's whole list, so a unit could join a battery-and-solar
 * build taking water. A NEW service for the build is *Add service*'s job, and
 * the server refuses the rest by name (`metering.build.unit_service_not_on_build`).
 * Kept in the utility's order and names; the build's codes only filter.
 */
export function servicesOfThisBuild(
  all: readonly AddServiceOption[],
  buildCodes: readonly string[],
): AddServiceOption[] {
  return all.filter((one) => buildCodes.includes(one.code));
}

/** *Add unit* — the unit's label, its type, and the services it takes. */
export function BuildAddUnitForm(props: {
  t: Translator;
  services: readonly AddServiceOption[];
  onClose: () => void;
  onSave: (body: { label: string; unit_type: string | null; services: string[] }) => Promise<unknown>;
  /** The page's client; absent means the app's. */
  client?: ApiClient;
}) {
  const { t } = props;
  const [label, setLabel] = useState("");
  const [unitType, setUnitType] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const unitTypesQuery = useQuery({
    queryKey: ["lookups", "unit_types", "new-connect"],
    queryFn: () => getLookupEntries("unit_types", { per: 200 }, props.client),
    retry: false,
  });
  const unitTypeOptions = unitTypeChoices(
    (unitTypesQuery.data?.results ?? []) as { code: string; name: string; active?: boolean }[],
    t,
  );
  return (
    <FormModal
      title={t("customers.build.act.addUnit", { defaultValue: "Add unit" })}
      schema={unitSchema(t)}
      values={{ label, services: picked }}
      submitLabel={t("customers.build.act.addUnit", { defaultValue: "Add unit" })}
      onClose={props.onClose}
      onSubmit={async () => {
        try {
          await props.onSave({
            label: label.trim(),
            unit_type: unitType.trim() === "" ? null : unitType.trim(),
            services: picked,
          });
          return { ok: true };
        } catch (error) {
          return refused(error);
        }
      }}
    >
      <TextField
        id="label"
        label={t("customers.newConnect.step4.unit", { defaultValue: "Unit" })}
        required
        value={label}
        onChange={setLabel}
        autoComplete="off"
      />
      {/* ⊕ `DEF-CUS-9219` — the utility's own unit types, the list step 3
          offers (`/lookups/unit_types`, `unitTypeChoices`), not a free-text
          box: a typed "Residential" beside step 3's `residential` was two
          spellings of one type on one building. */}
      <SelectField
        id="unit_type"
        label={t("customers.build.units.col.unitType", { defaultValue: "Unit type" })}
        value={unitType}
        onChange={setUnitType}
        placeholder={t("customers.newConnect.units.chooseUnitType", {
          defaultValue: "Choose a unit type",
        })}
        options={unitTypeOptions}
      />
      <fieldset className="m-0 border-0 p-0" data-field="services">
        <legend className="mb-1 font-semibold">
          {t("customers.newConnect.step5.service", { defaultValue: "Utility service" })}
        </legend>
        {/* ⊕ `DEF-CUS-9219` — one box per cell of a grid, so each tick sits
            with its own word (the boxes ran inline and every mark landed
            after the previous service's name), and the refusal for an empty
            pick is drawn here: the schema's `services` path names no input,
            so it had nowhere to show and the press did nothing visibly. */}
        <ServicesError>
          {(error) =>
            error === undefined ? null : (
              <p className="m-0 mb-2 text-sm text-danger-700" role="alert" data-services-error="">
                {error}
              </p>
            )
          }
        </ServicesError>
        <div className="grid grid-cols-3 gap-x-6 gap-y-2 max-sm:grid-cols-2">
        {props.services.map((service) => (
          <CheckboxField
            key={service.code}
            id={`service-${service.code}`}
            label={service.name}
            checked={picked.includes(service.code)}
            onChange={(on) =>
              setPicked((now) =>
                on ? [...now, service.code] : now.filter((code) => code !== service.code),
              )
            }
          />
        ))}
        </div>
      </fieldset>
    </FormModal>
  );
}

/** The refusal under the services boxes — read from the form's own errors,
 *  which only a child of `FormModal` can see. */
function ServicesError(props: { children: (error: string | undefined) => ReactNode }) {
  return <>{props.children(useFieldError("services"))}</>;
}

const SERVICE_SCHEMA = z.object({ service: z.string().min(1), unit: z.string() });

/** *Add service* — which service, and at which unit (or the whole build). */
export function BuildAddServiceForm(props: {
  t: Translator;
  services: readonly AddServiceOption[];
  units: readonly AddServiceUnit[];
  onClose: () => void;
  onSave: (body: { service: string; unit_id: string | null }) => Promise<unknown>;
}) {
  const { t } = props;
  const [service, setService] = useState("");
  const [unit, setUnit] = useState("");
  return (
    <FormModal
      title={t("customers.build.act.addService", { defaultValue: "Add service" })}
      schema={SERVICE_SCHEMA}
      values={{ service, unit }}
      submitLabel={t("customers.build.act.addService", { defaultValue: "Add service" })}
      onClose={props.onClose}
      onSubmit={async () => {
        try {
          await props.onSave({ service, unit_id: unit === "" ? null : unit });
          return { ok: true };
        } catch (error) {
          return refused(error);
        }
      }}
    >
      <SelectField
        id="service"
        label={t("customers.newConnect.step5.service", { defaultValue: "Utility service" })}
        required
        value={service}
        placeholder={t("customers.build.addService.pick", { defaultValue: "Choose a service" })}
        options={props.services.map((one) => ({ value: one.code, label: one.name }))}
        onChange={setService}
      />
      <SelectField
        id="unit"
        label={t("customers.newConnect.step4.unit", { defaultValue: "Unit" })}
        value={unit}
        placeholder={t("customers.build.addService.wholeBuild", { defaultValue: "Whole build" })}
        options={props.units.map((one) => ({ value: one.id, label: one.label }))}
        onChange={setUnit}
      />
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-162-BRC10 (items 7, 8)
// generated: 2026-10-02 by lane NC-A
// gates: G31 (route-b-migrated.txt) · G13 (mounted by BuildDetailPage)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
