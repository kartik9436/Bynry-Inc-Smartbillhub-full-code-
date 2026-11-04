// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-014 (the card + management view) · US-TEN-015 (define a
//           field) · US-TEN-016 (placement) · US-TEN-017 (deactivate only)
//           Screens: S8 (Settings → Reference data → Custom fields)
// Rules:    BR-TEN-046 (tenant DATA, never schema) · BR-TEN-047 (inside the
//           Reference-data framework — card → table → FormModal, no new screen
//           ID) · BR-TEN-048 (never a money input) · BR-TEN-049 (`key`
//           immutable after create) · BR-TEN-050 (deactivate only — no delete
//           control exists) · BR-TEN-051 (cap 10 active per entity) ·
//           BR-TEN-052 (placement bounded by the platform) · BR-SHL-035 (one
//           shell for every Reference-data item) · BR-SHL-025 (a control the
//           user may not use renders disabled WITH its reason) · IS-3/IS-4
// ───────────────────────────────────────────────────────
// S8 → Reference data → Custom fields. BR-TEN-047 is the whole reason this file
// looks the way it does: a custom field is a configurable vocabulary exactly
// like a lookup list, so it is one more card in the S8 grid with the same
// card → table → Add-modal shape, inside the SAME SettingsFrame. No new screen
// ID is minted and A1 is not renumbered.
//
// WHAT IS DELIBERATELY ABSENT, AND WHY YOU SHOULD NOT ADD IT
// -----------------------------------------------------------
// **There is no Delete control anywhere in this file.** BR-TEN-050 (CONFIRMED,
// PO 2026-08-10 — *"Deactivate only"*). Not a disabled one, not a hidden one:
// the API has no delete route, the service layer has no delete function, and
// offering the verb here would be offering something the product cannot do.
// Deactivate retires a field and every value recorded against it survives.
//
// The `key` is rendered READ-ONLY after create rather than omitted, because the
// operator needs to see the identifier their exports and (later) their bill
// templates will carry — BR-SHL-025's shape: visible, not editable, with the
// reason on the help line.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  createCustomField,
  getCustomFieldSlots,
  getCustomFields,
  saveCustomFieldPlacement,
  setCustomFieldActive,
  updateCustomField,
} from "@/api/endpoints";
import type {
  CustomFieldDefinition,
  CustomFieldEntitySlots,
  CustomFieldSlot,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { Button } from "@/components/Button";
import { LayoutIcon, PencilIcon, PowerIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import { DataTable } from "@/components/DataTable";
import { FilterBar, offerableFilters } from "@/components/FilterBar";
import { CheckboxField, FormModal, SelectField, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { FailedWithRetry } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";

import { RefusalNotice, SettingsDenied, apiErrorText, isPermissionDenied, refusalOf } from "./settingsShared";
import type { Refusal, Translator } from "./settingsShared";

// ⚠ **THERE IS NO CLIENT LIST OF RECORD TYPES OR SCREENS (`CR-161-BRC10` W1,
// `DEF-TEN-9153`).** This file carried `CUSTOM_FIELD_ENTITIES`, a hand copy of
// the server's eight, and offered every screen the server's R2 allow-list
// named — nine screens, of which two drew anything. Both now come from
// `GET /settings/custom-fields/slots` (`apps/tenancy/custom_fields.SLOTS`),
// which says per screen whether it is rendered. Hard-won law 5: one source.

/** B2 r17.1's six signed data types. The client invents none. */
export const CUSTOM_FIELD_DATA_TYPES = [
  "text",
  "number",
  "date",
  "boolean",
  "select",
  "multi_select",
] as const;

export const SELECT_DATA_TYPES = ["select", "multi_select"];

/** BR-TEN-051 — mirrored here only to render the headroom line; the SERVER refuses. */
export const ACTIVE_CAP_PER_ENTITY = 10;

export type PlacementMode = "input" | "view" | "not_shown";

/**
 * "Feeder Number" → `feeder_number`. The same derivation the server performs,
 * run client-side ONLY so the Add modal can PREVIEW the key before the row
 * exists. The server's value is authoritative and is what the row shows after
 * save — this never becomes the source of truth for something BR-TEN-049 makes
 * permanent.
 */
export function previewKey(label: string): string {
  const slug = label
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
  const prefixed = slug !== "" && !/^[a-z]/.test(slug) ? `f_${slug}` : slug;
  return prefixed.slice(0, 40).replace(/_+$/, "");
}

/** BR-TEN-052: `input` implies `view`, so a view query includes input slots. */
export function screensFor(
  placement: Record<string, string>,
  mode: "input" | "view",
): string[] {
  return Object.entries(placement)
    .filter(([, value]) => (mode === "view" ? value === "view" || value === "input" : value === mode))
    .map(([screen]) => screen)
    .sort();
}

/** The mode currently chosen for one slot — absent from the map means Not shown. */
export function modeForSlot(
  placement: Record<string, string>,
  screen: string,
): PlacementMode {
  const stored = placement[screen];
  return stored === "input" || stored === "view" ? stored : "not_shown";
}

/** The PO's three groups, in their order (`CR-161-BRC10` R6, Part 2). */
export const PLACEMENT_ROUTES = ["portal", "clerk_input", "read_only"] as const;

/** One choice on one screen: the stored mode and the catalogue key it reads as. */
export interface PlacementChoice {
  mode: PlacementMode;
  labelKey: string;
}

/**
 * The words a screen's choices read as, from how the screen PRESENTS the field
 * — the Roof Material table, verbatim: the portal form offers *Ask the customer
 * / Don't ask*, a list *Show as column / Not shown*, every other screen *Input
 * / View / Not shown* as its modes allow. The STORED value is still only
 * `input` or `view`.
 */
export function choicesFor(slot: CustomFieldSlot): PlacementChoice[] {
  if (slot.presentation === "portal") {
    return [
      { mode: "input", labelKey: "settings.customFields.mode.ask" },
      { mode: "not_shown", labelKey: "settings.customFields.mode.dont_ask" },
    ];
  }
  if (slot.presentation === "list") {
    return [
      { mode: "view", labelKey: "settings.customFields.mode.column" },
      { mode: "not_shown", labelKey: "settings.customFields.mode.not_shown" },
    ];
  }
  return [
    ...slot.modes.map((mode) => ({ mode, labelKey: `settings.customFields.mode.${mode}` })),
    { mode: "not_shown" as PlacementMode, labelKey: "settings.customFields.mode.not_shown" },
  ];
}

/**
 * Which screens the editor offers for a field, grouped *Customer (portal) ·
 * Clerk input · Read-only view*. The list is the SERVER's `slots` on the
 * definition — RENDERED screens only — never a copy here, so a screen that
 * draws nothing cannot be offered (`DEF-TEN-9153`).
 */
export function slotGroups(
  field: CustomFieldDefinition,
): { route: (typeof PLACEMENT_ROUTES)[number]; slots: CustomFieldSlot[] }[] {
  return PLACEMENT_ROUTES.map((route) => ({
    route,
    slots: field.slots.filter((slot) => slot.rendered && slot.route === route),
  })).filter((group) => group.slots.length > 0);
}

/** The record types *Applies to* offers for a NEW field: something collects
 *  each one today (a rendered input screen or its import). The field being
 *  edited keeps its own type in the list even when it is not offered. */
export function offeredEntities(
  catalogue: readonly CustomFieldEntitySlots[],
  keep?: string,
): string[] {
  return catalogue
    .filter((row) => row.offered || row.entity === keep)
    .map((row) => row.entity);
}

/** How many ACTIVE fields this entity already holds (BR-TEN-051's headroom). */
export function activeCountFor(rows: readonly CustomFieldDefinition[], entity: string): number {
  return rows.filter((row) => row.is_active && row.entity === entity).length;
}

export function definitionSchema(t: Translator, dataType: string) {
  return z.object({
    label: z
      .string()
      .trim()
      .min(1, t("settings.customFields.labelRequired"))
      .max(60, t("settings.reference.tooLong", { max: 60 })),
    entity: z.string().min(1, t("settings.customFields.entityRequired")),
    data_type: z.string().min(1, t("settings.customFields.typeRequired")),
    // ≥2 options for the select types, ignored otherwise (US-TEN-015 §5).
    options: SELECT_DATA_TYPES.includes(dataType)
      ? z
          .string()
          .refine(
            (value) => value.split("\n").map((line) => line.trim()).filter(Boolean).length >= 2,
            t("settings.customFields.optionsMin", { min: 2 }),
          )
      : z.string(),
    help_text: z.string().max(200, t("settings.reference.tooLong", { max: 200 })),
  });
}

export function parseOptions(text: string): string[] {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line !== "");
}

interface DefinitionForm {
  label: string;
  entity: string;
  data_type: string;
  options: string;
  help_text: string;
  is_required: boolean;
  /** `DEF-TEN-9234` — *"Prints on a bill only when switched on"*. Edit only:
   *  the server refuses it at create, so the unsafe choice is always a second,
   *  deliberate act (OQ-076, hard-won law 3). */
  is_document_safe: boolean;
}

function emptyForm(): DefinitionForm {
  return {
    label: "",
    entity: "accounts",
    data_type: "text",
    options: "",
    help_text: "",
    is_required: false,
    is_document_safe: false,
  };
}

type CustomFieldRow = CustomFieldDefinition & { _rowKey: string };

// ── The management view ────────────────────────────────────────────────────

export function CustomFieldsView(props: { readOnly: boolean; client?: ApiClient }) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const state: TableRequestState = {
    q: searchParams.get("q") ?? "",
    sort: "entity",
    dir: "asc",
    page: 1,
    per: DEFAULT_PAGE_SIZE,
    // Only filters actually SET travel in the state object: DataTable reads a
    // non-empty `filters` map as "the user is filtering" and shows the
    // no-results state instead of the A18 empty state (US-TEN-014 TC-1). An
    // unset filter is an absent key, not an empty string.
    filters: Object.fromEntries(
      (
        [
          ["entity", searchParams.get("f.entity") ?? ""],
          ["status", searchParams.get("f.status") ?? ""],
        ] as const
      ).filter(([, value]) => value !== ""),
    ),
  };

  function setState(next: TableRequestState): void {
    const params = new URLSearchParams(searchParams);
    for (const [key, value] of [
      ["q", next.q],
      ["f.entity", next.filters.entity ?? ""],
      ["f.status", next.filters.status ?? ""],
    ] as const) {
      if (value === "") {
        params.delete(key);
      } else {
        params.set(key, value);
      }
    }
    setSearchParams(params, { replace: true });
  }

  const slotsQuery = useQuery({
    queryKey: queryKeys.customFieldSlots(),
    queryFn: () => getCustomFieldSlots(client),
  });
  const catalogue = slotsQuery.data ?? [];

  const queryString = `${state.q}|${state.filters.entity ?? ""}|${state.filters.status ?? ""}`;
  const fieldsQuery = useQuery({
    queryKey: queryKeys.customFields(queryString),
    queryFn: () =>
      getCustomFields(
        { q: state.q, entity: state.filters.entity, status: state.filters.status },
        client,
      ),
  });

  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<CustomFieldDefinition | null>(null);
  const [placing, setPlacing] = useState<CustomFieldDefinition | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  function refresh(): void {
    // Both resources move on a definition write: the management table AND the
    // per-screen registry every placed screen reads (BR-TEN-053).
    void queryClient.invalidateQueries({ queryKey: ["custom-fields"] });
    void queryClient.invalidateQueries({ queryKey: ["lookups"] });
  }

  const toggleActive = useMutation({
    mutationFn: (input: { field: CustomFieldDefinition; active: boolean }) =>
      setCustomFieldActive(input.field.id, input.active, client),
    onSuccess: (_saved, input) => {
      refresh();
      setRefusal(null);
      fireToast(
        t(
          input.active
            ? "settings.customFields.reactivated"
            : "settings.customFields.deactivated",
          { label: input.field.label },
        ),
      );
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, t)),
  });

  const rows: CustomFieldRow[] = useMemo(
    () => (fieldsQuery.data ?? []).map((row) => ({ ...row, _rowKey: row.id })),
    [fieldsQuery.data],
  );
  // Every record type the server knows, for the filter — falling back to the
  // types the rows already carry while the list loads, never to a typed copy.
  const filterEntities =
    catalogue.length > 0
      ? catalogue.map((row) => row.entity)
      : [...new Set(rows.map((row) => row.entity))];

  if (fieldsQuery.data === undefined && fieldsQuery.isError) {
    if (isPermissionDenied(fieldsQuery.error)) {
      // US-TEN-014 TC-5: Settings is System Admin-only (A4).
      return <SettingsDenied helper={t("settings.denied.tab")} />;
    }
    return (
      <FailedWithRetry
        title={t("settings.customFields.failedTitle")}
        reason={apiErrorText(fieldsQuery.error, t)}
        onRetry={() => void fieldsQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => void fieldsQuery.refetch()}
      />
    );
  }

  const config: TableConfig<CustomFieldRow> = {
    screenId: "S8",
    getRowId: (row) => row.id,
    defaultSort: { sort: "entity", dir: "asc" },
    searchFields: ["label", "key"], // US-TEN-014 capability row
    // B14 rule 19 (DEF-510). `tenancy/selectors.py` filters `Q(label) | Q(key)`
    // and its docstring says so: *"Search covers Label and Key (US-TEN-014
    // TC-3)"*. Both are columns on this table, so the prompt uses their exact
    // headers — "Label" and "Key".
    //
    // ⚠ **DEF-510's ROW SAID THIS SCREEN STAYS ON THE DEFAULT DELIBERATELY, AND
    // CR-041 REVERSES THAT.** The reason recorded there was that r10 draws
    // `Search this list` on the reference-data toolbar (line 7193) — true, and
    // it is r10 being inconsistent with itself, since the same prototype gives
    // eleven other lists a sentence naming their fields. Rule 19 is RATIFIED
    // and says a placeholder names its entities; B14's rule-20 amendment
    // already set the precedent that **where an r10 value and a ratified B14
    // rule disagree, B14 wins and the divergence is stamped**. This is that
    // stamp. Leaving two of twenty-four lists saying "Search this list" is the
    // exact "different in many places" the PO reported CR-041 about.
    searchPlaceholder: "settings.customFields.searchPlaceholder",
    filters: [
      {
        name: "entity",
        label: t("settings.customFields.col.entity"),
        options: [
          { value: "", label: t("settings.customFields.filter.allEntities") },
          ...filterEntities.map((entity) => ({
            value: entity,
            label: t(`settings.customFields.entity.${entity}`),
          })),
        ],
      },
      {
        name: "status",
        label: t("settings.customFields.col.status"),
        options: [
          { value: "", label: t("settings.customFields.filter.allStatuses") },
          { value: "active", label: t("settings.customFields.status.active") },
          { value: "inactive", label: t("settings.customFields.status.inactive") },
        ],
      },
    ],
    columns: [
      { key: "label", label: t("settings.customFields.col.label"), identity: true },
      { key: "key", label: t("settings.customFields.col.key") },
      {
        key: "entity",
        label: t("settings.customFields.col.entity"),
        cell: (row) => t(`settings.customFields.entity.${row.entity}`),
      },
      {
        key: "data_type",
        label: t("settings.customFields.col.type"),
        cell: (row) => t(`settings.customFields.type.${row.data_type}`),
      },
      {
        key: "is_required",
        label: t("settings.customFields.col.required"),
        cell: (row) => (row.is_required ? t("settings.customFields.yes") : t("settings.customFields.no")),
      },
      {
        key: "placement_count",
        label: t("settings.customFields.col.placements"),
        numeric: true,
        cell: (row) => String(row.placement_count),
      },
      {
        key: "is_active",
        label: t("settings.customFields.col.status"),
        cell: (row) => (
          <StatusPill tone={row.is_active ? "success" : "neutral"}>
            {t(
              row.is_active
                ? "settings.customFields.status.active"
                : "settings.customFields.status.inactive",
            )}
          </StatusPill>
        ),
      },
      {
        key: "actions",
        label: t("settings.customFields.col.actions"),
        cell: (row) => (
          <RowActions>
            <RowAction
              label={t("settings.customFields.edit")}
              icon={<PencilIcon />}
              reason={props.readOnly ? t("settings.readOnlyReason") : null}
              onClick={() => setEditing(row)}
            />
            {/* "Placement" is WHERE the field appears on a form, so the glyph is
                a form frame rather than a verb. One of the five with no r10
                precedent — see the table in components/icons.tsx. */}
            <RowAction
              label={t("settings.customFields.placement")}
              icon={<LayoutIcon />}
              reason={props.readOnly ? t("settings.readOnlyReason") : null}
              onClick={() => setPlacing(row)}
            />
            {/* BR-TEN-050: deactivate/reactivate, and NO delete. */}
            <RowAction
              label={t(
                row.is_active
                  ? "settings.customFields.deactivate"
                  : "settings.customFields.reactivate",
              )}
              icon={<PowerIcon />}
              reason={props.readOnly ? t("settings.readOnlyReason") : null}
              working={toggleActive.isPending}
              onClick={() => toggleActive.mutate({ field: row, active: !row.is_active })}
            />
          </RowActions>
        ),
      },
    ],
  };

  return (
    <div className="settings-custom-fields">
      {refusal !== null && <RefusalNotice refusal={refusal} />}
      <DataTable
        config={config}
        state={state}
        onStateChange={setState}
        rows={rows}
        totalRows={rows.length}
        loading={fieldsQuery.isLoading}
        empty={{
          // US-TEN-014 TC-1: the A18 empty state with a primary Add action —
          // and TC-4: an entity filter with no matches lands HERE, not on an
          // error, with the Add action still available.
          title: t("settings.customFields.emptyTitle"),
          helper: t("settings.customFields.emptyHelper"),
          ctaLabel: t("settings.customFields.add"),
          ctaReason: props.readOnly ? t("settings.readOnlyReason") : null,
          onCta: () => setAdding(true),
        }}
        // ⚠ **THIS SLOT WAS NOT PASSED, AND THE FILTERS HAVE BEEN DECLARED ALL
        //    ALONG (DEF-1701).** `filters: [entity, status]` sat in this config
        //    with nothing reading it, so US-TEN-014 TC-4's "an entity filter
        //    with no matches lands on the empty state" described a filter no
        //    user could set. PO 2026-08-27, naming the sibling screen: *"on
        //    assets - tookkit dont have filters; same is the case with sub
        //    meters, devices, investory"* — `AssetRegistryPage` had the
        //    identical shape and this file was found by the sweep.
        //
        //    `offerableFilters` strips each group's leading
        //    `{ value: "", label: "All …" }` cell, which is a `<select>`-era
        //    leftover: FilterBar's own `All` chip IS that control, and a
        //    checkbox valued `""` could never read as checked. The catalogue
        //    keys keep their call sites in the config above.
        filterBarSlot={
          <FilterBar
            filters={offerableFilters(config.filters ?? [])}
            state={state}
            onStateChange={setState}
          />
        }
        downloadSlot={
          <Button
            variant="primary"
            disabled={props.readOnly}
            title={props.readOnly ? t("settings.readOnlyReason") : undefined}
            onClick={() => setAdding(true)}
          >
            {t("settings.customFields.add")}
          </Button>
        }
      />
      {adding && (
        <DefinitionModal
          client={client}
          existing={null}
          catalogue={catalogue}
          rows={fieldsQuery.data ?? []}
          onClose={() => setAdding(false)}
          onSaved={(field) => {
            refresh();
            setAdding(false);
            fireToast(t("settings.customFields.created", { label: field.label }));
          }}
        />
      )}
      {editing !== null && (
        <DefinitionModal
          client={client}
          existing={editing}
          catalogue={catalogue}
          rows={fieldsQuery.data ?? []}
          onClose={() => setEditing(null)}
          onSaved={(field) => {
            refresh();
            setEditing(null);
            fireToast(t("settings.customFields.saved", { label: field.label }));
          }}
        />
      )}
      {placing !== null && (
        <PlacementModal
          client={client}
          field={placing}
          onClose={() => setPlacing(null)}
          onSaved={(field) => {
            refresh();
            setPlacing(null);
            fireToast(t("settings.customFields.placementSaved", { label: field.label }));
          }}
        />
      )}
    </div>
  );
}

// ── The definition's TYPE half, as a component (B14 rule 43) ───────────────

/** The four values the type half edits — a subset of any definition form. */
export interface DefinitionTypeValues {
  data_type: string;
  /** One option per line; `parseOptions` turns it into the list sent. */
  options: string;
  help_text: string;
  is_required: boolean;
}

/**
 * Type · Options · Help text · Required — the part of a custom-field definition
 * that is about WHAT is asked, as one component.
 *
 * ⚠ **EXTRACTED 2026-10-24 FOR `CR-192-BRC10` (MQ-033 task 11), NOT COPIED.**
 * The PO ruled a read-format question is *"similar to custom fields"* — the same
 * types, options and required flag — so the question editor in Settings → Reads
 * IMPORTS this rather than drawing its own four fields (B14 rule 43). The field
 * ids stay the server's field names, so a refusal from either endpoint lands
 * under the right input. `extraTypes` is how a caller offers a type custom
 * fields do not have (a read format's *Photo*); absent = the six signed types,
 * which is exactly what `DefinitionModal` drew before the extraction.
 */
export function DefinitionTypeFields(props: {
  values: DefinitionTypeValues;
  onChange: <K extends keyof DefinitionTypeValues>(key: K, value: DefinitionTypeValues[K]) => void;
  /** The checkbox's words — where the answer is required differs by caller. */
  requiredLabel: string;
  extraTypes?: readonly { value: string; label: string }[];
}) {
  const { t } = useTranslation();
  const { values } = props;
  return (
    <>
      <SelectField
        id="data_type"
        label={t("settings.customFields.field.type")}
        value={values.data_type}
        onChange={(value) => props.onChange("data_type", value)}
        required
        options={[
          ...CUSTOM_FIELD_DATA_TYPES.map((type) => ({
            value: type,
            label: t(`settings.customFields.type.${type}`),
          })),
          ...(props.extraTypes ?? []),
        ]}
        // BR-TEN-048, said on the screen for the ONE type it is about.
        // `DEF-TEN-9156`: this read *"A number here is recorded and shown…"*
        // under every type — Text, Date and Yes/No included. Only a number can
        // be mistaken for something to add up, so only a number says it is not.
        help={values.data_type === "number" ? t("settings.customFields.typeHelp.number") : undefined}
      />
      {SELECT_DATA_TYPES.includes(values.data_type) && (
        <TextField
          id="options"
          label={t("settings.customFields.field.options")}
          value={values.options}
          onChange={(value) => props.onChange("options", value)}
          multiline
          required
          help={t("settings.customFields.optionsHelp")}
        />
      )}
      <TextField
        id="help_text"
        label={t("settings.customFields.field.helpText")}
        value={values.help_text}
        onChange={(value) => props.onChange("help_text", value)}
      />
      <CheckboxField
        id="is_required"
        label={props.requiredLabel}
        checked={values.is_required}
        onChange={(checked) => props.onChange("is_required", checked)}
      />
    </>
  );
}

// ── US-TEN-015 — the Add / Edit modal ──────────────────────────────────────

export function DefinitionModal(props: {
  client: ApiClient;
  existing: CustomFieldDefinition | null;
  /** The served slot list — *Applies to* offers only types something collects. */
  catalogue: readonly CustomFieldEntitySlots[];
  rows: readonly CustomFieldDefinition[];
  onClose: () => void;
  onSaved: (field: CustomFieldDefinition) => void;
}) {
  const { t } = useTranslation();
  const creating = props.existing === null;
  const [form, setForm] = useState<DefinitionForm>(() =>
    props.existing === null
      ? emptyForm()
      : {
          label: props.existing.label,
          entity: props.existing.entity,
          data_type: props.existing.data_type,
          options: props.existing.options.join("\n"),
          help_text: props.existing.help_text,
          is_required: props.existing.is_required,
          is_document_safe: props.existing.is_document_safe === true,
        },
  );

  function set<K extends keyof DefinitionForm>(key: K, value: DefinitionForm[K]): void {
    setForm((current) => ({ ...current, [key]: value }));
  }

  // US-TEN-015 TC-1: the key is derived from the label and shown READ-ONLY.
  // After create it is the server's stored value, and BR-TEN-049 makes it
  // permanent — the help line says so rather than the field simply not moving.
  const existing = props.existing;
  const keyText = existing === null ? previewKey(form.label) : existing.key;
  const headroom = ACTIVE_CAP_PER_ENTITY - activeCountFor(props.rows, form.entity);

  async function submit(): Promise<FormSubmitOutcome> {
    const body: Record<string, unknown> = {
      label: form.label.trim(),
      help_text: form.help_text.trim(),
      is_required: form.is_required,
    };
    if (SELECT_DATA_TYPES.includes(form.data_type)) {
      body.options = parseOptions(form.options);
    }
    if (creating) {
      body.entity = form.entity;
      body.data_type = form.data_type;
    } else {
      body.is_document_safe = form.is_document_safe;
    }
    try {
      const saved =
        existing === null
          ? await createCustomField(body, props.client)
          : await updateCustomField(existing.id, body, props.client);
      props.onSaved(saved);
      return { ok: true };
    } catch (error) {
      // BR-SHL-037: the SERVER's envelope, unchanged — including the BR-TEN-051
      // cap refusal, which names the entity, the count and the cap.
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t(creating ? "settings.customFields.addTitle" : "settings.customFields.editTitle")}
      kicker={t("settings.reference.card.custom_fields")}
      schema={definitionSchema(t, form.data_type)}
      values={form}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t(creating ? "settings.customFields.add" : "settings.customFields.save")}
    >
      <TextField
        id="label"
        label={t("settings.customFields.field.label")}
        value={form.label}
        onChange={(value) => set("label", value)}
        required
      />
      <TextField
        id="key"
        label={t("settings.customFields.field.key")}
        value={keyText}
        onChange={() => undefined}
        readOnly
        help={t("settings.customFields.keyLockedReason")}
      />
      <SelectField
        id="entity"
        label={t("settings.customFields.field.entity")}
        value={form.entity}
        onChange={(value) => set("entity", value)}
        required
        options={offeredEntities(props.catalogue, form.entity).map((entity) => ({
          value: entity,
          label: t(`settings.customFields.entity.${entity}`),
        }))}
        help={
          creating
            ? t("settings.customFields.headroom", {
                remaining: Math.max(0, headroom),
                cap: ACTIVE_CAP_PER_ENTITY,
              })
            : t("settings.customFields.entityLockedReason")
        }
      />
      <DefinitionTypeFields
        values={form}
        onChange={(key, value) => setForm((current) => ({ ...current, [key]: value }))}
        requiredLabel={t("settings.customFields.field.required")}
      />
      {/* `DEF-TEN-9234` — the PO's Rules table: *"Prints on a bill only when
          switched on · 'Safe to print' is off by default"*. The flag existed
          (OQ-076) and the bill's stamp reads it, but no screen could set it,
          so every field stayed off every bill. EDIT only: the server refuses
          it at create, so a new field is never printable by accident. */}
      {!creating && (
        <CheckboxField
          id="is_document_safe"
          label={t("settings.customFields.field.documentSafe")}
          checked={form.is_document_safe}
          onChange={(checked) => set("is_document_safe", checked)}
        />
      )}
    </FormModal>
  );
}

// ── US-TEN-016 — the placement editor ──────────────────────────────────────

export function PlacementModal(props: {
  client: ApiClient;
  field: CustomFieldDefinition;
  onClose: () => void;
  onSaved: (field: CustomFieldDefinition) => void;
}) {
  const { t } = useTranslation();
  const groups = slotGroups(props.field);
  // Only the screens offered here travel. A stored choice on a screen that
  // draws nothing yet is KEPT by the server through this save
  // (`custom_fields.validate_placement`), so it is neither shown nor sent.
  const [placement, setPlacement] = useState<Record<string, string>>(() => {
    const shown = new Set(groups.flatMap((group) => group.slots.map((slot) => slot.key)));
    return Object.fromEntries(
      Object.entries(props.field.placement).filter(([key]) => shown.has(key)),
    );
  });

  function choose(screen: string, mode: PlacementMode): void {
    setPlacement((current) => {
      const next = { ...current };
      if (mode === "not_shown") {
        // Stored by OMISSION — which is exactly why TC-3 holds: the field
        // leaves the screen and the recorded VALUES are untouched.
        delete next[screen];
      } else {
        next[screen] = mode;
      }
      return next;
    });
  }

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const saved = await saveCustomFieldPlacement(props.field.id, placement, props.client);
      props.onSaved(saved);
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) {
        return { ok: false, error: formErrorEnvelope(error) };
      }
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("settings.customFields.placementTitle", { label: props.field.label })}
      kicker={t("settings.reference.card.custom_fields")}
      schema={z.object({})}
      values={{}}
      onSubmit={submit}
      onClose={props.onClose}
      submitLabel={t("settings.customFields.save")}
    >
      {/* BR-TEN-052 as amended (`CR-161-BRC10`): the tenant chooses among
          screens the PLATFORM cleared AND a screen actually draws — the
          server's `slots`, grouped as the PO drew them. Each screen is named,
          never numbered (B14 rule 31), and offers its own choices. The money
          screens are not offered here because they are not offered anywhere. */}
      <p className="field-help">{t("settings.customFields.placementHelp")}</p>
      {groups.length === 0 && (
        <p className="field-help" data-placement-empty={props.field.input_route}>
          {props.field.input_route === "import"
            ? t("settings.customFields.filledByImport")
            : t("settings.customFields.slot_not_rendered")}
        </p>
      )}
      {groups.map((group) => (
        <section key={group.route} data-placement-route={group.route} className="mt-4">
          <h4 className="m-0 mb-2 font-heading text-base font-extrabold uppercase tracking-label text-neutral-600">
            {t(`settings.customFields.route.${group.route}`)}
          </h4>
          {group.slots.map((slot) => (
            <SelectField
              key={slot.key}
              id={`placement-${slot.key}`}
              label={t(`settings.customFields.screen.${slot.screen}`)}
              value={modeForSlot(placement, slot.key)}
              onChange={(value) => choose(slot.key, value as PlacementMode)}
              options={choicesFor(slot).map((choice) => ({
                value: choice.mode,
                label: t(choice.labelKey),
              }))}
            />
          ))}
        </section>
      ))}
      {groups.length > 0 && props.field.input_route === "import" && (
        <p className="field-help">{t("settings.customFields.filledByImport")}</p>
      )}
    </FormModal>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-014@a1c9f04 (story+rules snapshot over EP-TEN-09-custom-fields.md +
//         01-tenancy/02-business-rules.md BR-TEN-046..053)
// generated: 2026-08-15 by story-coder (tenant custom-fields lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ eslint✔ vitest — see the lane report for counts and for the checks proved RED first · G13 unwired-props: this view is reached from SettingsReferenceData's ReferenceCardBody (kind "custom"), which is the caller
// exceptions: (1) there is NO delete control and no disabled one — BR-TEN-050 means the verb does not exist, and a disabled button would imply a capability the product does not have · (2) `previewKey` duplicates the server's slug derivation for the Add modal's read-only preview ONLY; the stored key is always the server's · (3) the eligible-slot list comes from the SERVER (`eligible_slots`), never from a client copy of the allow-list — a second copy is a second thing to keep true · (4) the S8 capability row lists no Export for this view and none is rendered
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
