// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-010 TC-1 (add `MTR-W58 · Water meter 5/8" · Meters · each ·
//           92.4000` → stored `92.4000`, shown `$92.40`) · TC-3 (a fifth
//           decimal is refused) · TC-4 (a part with no unit is refused).
//           Screen: Work-025 → Add part
// Rules:    BR-WRK-019 (the register's five fields, and no stock) ·
//           CLAUDE.md hard rule 2 (4 decimals stored, 2 displayed — the value
//           NEVER becomes a float on this side) · hard rule 3 (a quantity
//           carries its unit; the field is required) · B14 rule 6 (this is not
//           a destructive commit, so the primary is primary tier) · rule 31
//           (the category picker shows NAMES; no id is a visible value) ·
//           BR-SHL-017 (submit stays enabled and re-validates)
// Tests:    src/features/work/PartsPage.test.tsx
// Impacts:  src/features/work/workEndpoints.ts (`createPart`) ·
//           06-backend/apps/work/services.create_part
// ───────────────────────────────────────────────────────
//
// THE ONE ADD/EDIT MODAL, NOT A ROUTE — and that is a decision rather than a
// shortcut. `10-execution-plan.md` C2 words this as *"Add part as a
// sub-screen"*. Every other reference-data addition in this product happens in
// `FormModal` (`SettingsReferenceData.tsx`'s `LookupEntryModal` is the same
// component), and a route would mint a screen id, a `g29` row and a second
// place for the same five fields to drift. The register is the screen; adding
// a row to it is not a different one. Recorded in the wave's decision-log row.
//
// ⚠ **THE UNIT COST IS A STRING FROM THE KEYBOARD TO THE COLUMN.** It is typed
// as text, validated as text, posted as text and stored as `numeric(18,4)`.
// Nothing here calls `Number()` or `parseFloat`, and `92.40004` is REFUSED by
// the server rather than rounded — a price silently changed by the thing that
// stored it is the defect nobody finds for a year (CLAUDE.md hard rule 2).
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { z } from "zod";

import type { ApiClient } from "@/api/client";
import { FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { formErrorEnvelope, isApiError } from "@/api/client";
import { getLookupEntries } from "@/api/endpoints";

import { createPart, updatePart } from "./workEndpoints";
import type { PartRow } from "./workEndpoints";

/**
 * The client-side mirror of `apps/work/services._clean_part` (B8: the schema
 * mirrors the server's VAL codes; the SERVER is the authority and its refusal
 * is what renders under the field).
 *
 * Four decimals, and the regex is the rule: `\\d{1,4}` after the point, so
 * `92.4000` passes and `92.40004` does not — which is TC-3 caught before the
 * request rather than after it, with the same answer either way.
 *
 * ⚠ **CR-168 · `DEF-WRK-9585` — EVERY MESSAGE IS OURS, IN THE CLERK'S
 * LANGUAGE.** The schema was built with zod's defaults, so an empty form read
 * *"String must contain at least 1 character(s)"* three times and *"Invalid"*
 * under Unit cost, in all eleven languages (image 37 draws *This is
 * required.* and *Unit cost must be a number.*). Built per render from `t`,
 * because `collectFormErrors` shows a schema's message as it is.
 */
export function partSchema(t: (key: string, params?: Record<string, unknown>) => string) {
  const required = t("work.parts.add.required");
  const text = z.string().trim().min(1, required).max(60, t("work.lookups.too_long", { max: 60 }));
  return z.object({
    part_no: text,
    name: text,
    unit_of_measure: text,
    unit_cost: z
      .string()
      .trim()
      .superRefine((value, ctx) => {
        if (/^\d+(\.\d{1,4})?$/.test(value)) return;
        const tooPrecise = /^\d+\.\d{5,}$/.test(value);
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: tooPrecise
            ? t("work.parts.cost_places", { max: 4 })
            : t("work.parts.cost_number"),
        });
      }),
  });
}

/** `"92.4000"` → `"92.40"`, `"8.9375"` → `"8.9375"`: the stored four places
 *  as a person would type them — trailing zeros past the second place go, a
 *  real third or fourth stays. A STRING edit, never a float (hard rule 2). */
export function editableCost(stored: string): string {
  const match = /^(\d+)\.(\d*)$/.exec(stored);
  if (match === null) return stored;
  const fraction = (match[2] ?? "").replace(/0+$/, "").padEnd(2, "0");
  return `${match[1]}.${fraction}`;
}

/**
 * Add a part (images 36, 37) — and, since `CR-168` P3.8, EDIT one: the same
 * five fields in the same frame, opened from the register's pencil with the
 * part's own values. One form for both, because two would be two places for
 * the same five fields to drift (B14 rule 43).
 */
export function AddPartModal(props: {
  client: ApiClient;
  onClose: () => void;
  onAdded: () => void;
  /** Present = EDIT this part; absent = add a new one. */
  part?: PartRow;
}) {
  const { t } = useTranslation();
  const editing = props.part;
  const [partNo, setPartNo] = useState(editing?.part_no ?? "");
  const [name, setName] = useState(editing?.name ?? "");
  const [unit, setUnit] = useState(editing?.unit_of_measure ?? "");
  // The stored four decimals, shown as typed money: `92.4000` → `92.40`. A
  // STRING trim, never a float (hard rule 2) — and a real fourth place stays.
  const [unitCost, setUnitCost] = useState(
    editing === undefined ? "" : editableCost(editing.unit_cost),
  );
  const [category, setCategory] = useState(editing?.category?.name ?? "");

  // The categories the tenant actually holds, from the reference list that
  // owns them (`US-WRK-009`). Its own fetch, unpaged: the choices must not
  // depend on which page of the register the user was looking at.
  const categoriesQuery = useQuery({
    queryKey: ["lookups", "work_parts_categories", "picker"],
    queryFn: () => getLookupEntries("work_parts_categories", { per: 200 }, props.client),
    retry: false,
  });
  const categoryOptions = (categoriesQuery.data?.results ?? [])
    .filter((row) => row.active || row.name === editing?.category?.name)
    // B14 rule 31 — the NAME is the value a person sees and picks. The server
    // resolves it against this tenant's own rows; no id crosses the screen.
    .map((row) => ({ value: row.name, label: row.name }));

  const values = {
    part_no: partNo,
    name,
    unit_of_measure: unit,
    unit_cost: unitCost,
  };

  async function handleSubmit(): Promise<FormSubmitOutcome> {
    try {
      if (editing === undefined) {
        await createPart(
          { ...values, category: category === "" ? undefined : category },
          props.client,
        );
      } else {
        // An empty category on an edit CLEARS it — `_clean_part` writes null.
        await updatePart(editing.id, { ...values, category }, props.client);
      }
      props.onAdded();
      return { ok: true };
    } catch (error) {
      // BR-TEN-031's shape one module along: the OWNING module's validation
      // comes back as field errors in the B12 §3 envelope and lands under the
      // input that caused it — a fifth decimal under Unit cost, a blank unit
      // under Unit of measure, a part number already on the register.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t(editing === undefined ? "work.parts.add.title" : "work.parts.edit.title")}
      kicker={t("work.parts.add.kicker")}
      schema={partSchema(t)}
      values={values}
      onSubmit={handleSubmit}
      onClose={props.onClose}
      submitLabel={t(editing === undefined ? "work.parts.add.submit" : "work.parts.edit.submit")}
    >
      <TextField
        id="part_no"
        label={t("work.parts.add.partNo")}
        value={partNo}
        onChange={setPartNo}
        required
      />
      {/* ruling 32 (PO 2026-09-24): the part has a NAME — the same field the
          register called Description. */}
      <TextField
        id="name"
        label={t("work.parts.add.name")}
        value={name}
        onChange={setName}
        required
      />
      <SelectField
        id="category"
        label={t("work.parts.add.category")}
        value={category}
        onChange={setCategory}
        options={categoryOptions}
        placeholder={t("work.parts.add.categoryNone")}
      />
      {/* hard rule 3 — required, and the help line says what the word is FOR. */}
      <TextField
        id="unit_of_measure"
        label={t("work.parts.add.unit")}
        value={unit}
        onChange={setUnit}
        required
        help={t("work.parts.add.unitHelp")}
      />
      <TextField
        id="unit_cost"
        label={t("work.parts.add.unitCost")}
        value={unitCost}
        onChange={setUnitCost}
        required
        numeric
        help={t("work.parts.add.unitCostHelp")}
      />
    </FormModal>
  );
}

export default AddPartModal;

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-WRK-010@81bb7e45 (EP-WRK-02) · 08-screen-layouts.md Work-025 · 07-endpoints.md §2 rows 31–34
// generated: 2026-09-04 by the CR-070 wave C build lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
// gates: tsc · eslint · vitest src/features/work · routeBUtilities.test.ts · the cr070-c walkthrough types 96.0000 here and reads $96.00 back off the register
// exceptions: a MODAL rather than a route — the one add/edit modal every reference addition in this product uses; stated in the header and in the wave's decision-log row
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
