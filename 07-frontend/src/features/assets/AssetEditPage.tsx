// ── Trace ──────────────────────────────────────────────
// Story:    US-AST-002 (S49 edit one asset — the specification correction)
//           Screen:  AST-09 · /:tenant/assets/{assetId}/edit
// Change:   CR-092-BRC01 `AST-B-12` (PO ✅ APPROVED 2026-09-12) — "A clerk can
//           correct an asset from the asset, at an address they can come back
//           to." Drawn as screen 14 of
//           04-docs/05-modules/05-assets/wireframes/CR-092-assets-screens.html
//           PO instruction 2026-09-11, verbatim: "this should be form and not
//           modal."
// Rules:    BR-AST-012 (multiplier · unit · net metering · service are
//           FORWARD-ONLY once reads exist — the server applies it) ·
//           BR-AST-026 (three identifiers; the uuid is never displayed) ·
//           BR-AST-033 (a duplicate asset # is a hard block, a duplicate
//           serial warns and saves) · BR-AST-044 (the three classifications,
//           and meter_type ONLY on a measuring type) · BR-AST-500/530 (the
//           connection size, blank lawful, on-the-connection only) ·
//           B14 rules 10, 11, 12, 38, 39/R12 (label→input→helper, 20px
//           between fields) and 40 (the page head at 32px) · hard rule 3
//           (a quantity never travels without its unit)
// Tests:    AssetEditPayload.dom.test.tsx (the PATCH body, key for key) ·
//           AssetSizeDoors.dom.test.tsx (BR-AST-530's two doors) ·
//           AssetEditAddress.dom.test.tsx (the route, both doors into it)
// ───────────────────────────────────────────────────────
// AST-09 — the one surface every specification correction in the product
// passes through.
//
// ⚠ **IT WAS A DIALOG UNTIL THIS FILE EXISTED, AND WHAT CHANGED IS THE
// CONTAINER — NOT ONE FIELD, NOT THE SCHEMA AND NOT THE WRITE.** The form
// below is `AssetFormModal` MOVED out of `AssetRegistryPage.tsx` with its
// `FormModal` frame removed; the drawing says so in its own words ("the dialog
// frame itself — REMOVED … it is the container, not a field") and that is why
// there is no second copy of this form anywhere. The registry pencil and the
// asset header now both NAVIGATE here, which is the same conversion CR-028
// AST-W4 made for reassign, log-repair and retire on 2026-08-22.
//
// ⚠ **WHAT A PAGE BUYS THAT THE DIALOG COULD NOT, because it is the point of
// the change rather than a side effect:** an ADDRESS — a correction can be
// linked to, sent to a colleague, bookmarked and returned to, and it survives
// a refresh. A dialog was reachable from a table row and nowhere else, so a
// clerk reading a wrong multiplier ON THE ASSET had to leave it, find the row
// in a paginated registry and press a pencil.
//
// ⚠ **THE FIELD SET IS THE AS-BUILT NINE AND THE DRAWING NAMES A TENTH
// (`DEF-AST-5107`).** Screen 14's field table lists `location_note` where the
// built form carries `manufacturer_model`, and its own note says the field set
// "is read from AssetRegistryPage.tsx's AssetFormModal" — so the drawing is
// wrong about one field rather than asking for a change. `location_note` IS
// editable, on the Lifecycle panel dialog (`AssetPanelEdits.tsx`), so adding
// it here would be a second way to write one field rather than a new
// capability. The difference is FILED, not silently followed either way (the
// UI skill's rule for a drawing that disagrees with the code).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getLookupEntries, updateAsset } from "@/api/endpoints";
import type { AssetRow, AssetTab } from "@/api/endpoints";
import { Button } from "@/components/Button";
import {
  FieldErrorsScope,
  SelectField,
  TextField,
  collectFormErrors,
  envelopeErrors,
} from "@/components/FormModal";
import { WorkingButton } from "@/components/StateFrame";
import { CustomFieldsInput, customDataChanges } from "@/components/CustomFields";
import type { CustomFieldValues } from "@/components/CustomFields";
import { RefusalStrip } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { toEnvelope } from "@/features/metering/PremisesListPage";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { AssetFlowShell } from "./AssetFlowPages";
import type { AssetFlowPageProps } from "./AssetFlowPages";
import {
  assetTypesQueryKey,
  meterTypesQueryKey,
  readMethodsQueryKey,
  sizeClassesQueryKey,
  typesForTab,
} from "./AssetRegistryPage";
import {
  assetDetailPath,
  isMeasuringCategory,
  offersConnectionSize,
  useTranslator,
} from "./assetsShared";

// ── The page (AST-09) ──────────────────────────────────────────────────────

export function AssetEditPage(props: AssetFlowPageProps) {
  const client = props.client ?? api;
  const t = useTranslator();
  return (
    <AssetFlowShell
      client={client}
      // The drawing's kicker is the SECTION and the KIND — "ASSETS · METER" —
      // which is the asset detail header's own grammar one segment shorter.
      // `type_name` is the tenant's own label for the kind, never a hardcoded
      // enum, and it is never null on a served row.
      kicker={(asset) => [t("assets.kicker"), asset.type_name].join(" · ")}
      title={(asset) => t("assets.form.editTitle", { asset: asset.asset_no })}
    >
      {(asset) => <AssetEditForm asset={asset} client={client} />}
    </AssetFlowShell>
  );
}

// ── The form — MOVED from AssetRegistryPage.AssetFormModal ─────────────────

/**
 * ⚠ **EXPORTED FOR ITS TESTS, AND THE REASON SURVIVED THE MOVE.** This form is
 * the only asset-wide caller of `updateAsset`: every specification correction a
 * utility makes from the registry or the asset header goes through it. The
 * five panel dialogs (`AssetPanelEdits.tsx`, `AST-B-25`) write the same
 * endpoint one panel at a time, so the comment this file inherited — "the ONLY
 * caller of `updateAsset` in the whole frontend" — **stopped being true when
 * those landed** and is corrected here rather than carried over (hard-won law
 * 1: a comment claiming a guarantee is not the guarantee).
 */
export function AssetEditForm(props: {
  /**
   * ⚠ **`AssetRow`, NOT `AssetDetail`, AND THAT IS DELIBERATE.** Every field
   * this form reads and writes is on the registry row — the detail payload's
   * panels, rollups and chain are not among them — so the narrower type keeps
   * the form mountable from a row fixture and keeps its two DOM suites from
   * having to build a whole detail payload to assert a payload key.
   * `AssetFlowShell` hands it an `AssetDetail`, which IS one.
   */
  asset: AssetRow;
  client: ApiClient;
}) {
  const { asset, client } = props;
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const fireToast = useToast();
  const queryClient = useQueryClient();

  // BR-AST-004: the asset's OWN tab decides which types it may move between
  // and whether a connection size is offered — on the registry that came from
  // the tab the clerk was standing on, and here it comes off the asset.
  const tab = asset.tab as AssetTab;

  const [values, setValues] = useState({
    // BR-AST-026: the three identifiers. The internal uuid is not among them —
    // it is never displayed and never entered.
    asset_no: asset.asset_no,
    serial_no: asset.serial_no ?? "",
    type: asset.type,
    meter_type: asset.meter_type ?? "",
    // BR-AST-500: `null` on the row means "no size recorded", which is a REAL
    // state and the one every meter loaded before 2026-08-28 is in. It maps to
    // the empty option, never to a default — defaulting here would invent a
    // connection size for 1,847 meters at once.
    size_class: asset.size_class ?? "",
    read_method: asset.read_method ?? "",
    unit: asset.unit ?? "",
    multiplier: asset.multiplier ?? "1",
    manufacturer_model: [asset.manufacturer, asset.model]
      .filter((part) => part !== null && part !== undefined && part !== "")
      .join(" · "),
  });
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  // `CR-161-BRC10` W3 · `DEF-AST-9171` — the tenant's own fields, re-opened on
  // what the server stored; the save sends only what changed.
  const openedCustom = asset.custom_data ?? {};
  const [customData, setCustomData] = useState<CustomFieldValues>(openedCustom);

  // The three catalogues the controls read. The registry passed `types` and
  // `meterTypes` down as props because it had already fetched them for its own
  // filters; a page has no such parent, so it asks — on the SAME query keys,
  // which means arriving from the registry costs no second request.
  const typesQuery = useQuery({
    queryKey: assetTypesQueryKey,
    queryFn: () => getLookupEntries("asset_types", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const meterTypesQuery = useQuery({
    queryKey: meterTypesQueryKey,
    queryFn: () => getLookupEntries("meter_types", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  const readMethodsQuery = useQuery({
    queryKey: readMethodsQueryKey,
    queryFn: () => getLookupEntries("read_methods", { per: 100 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // BR-AST-530 — the tenant's own ratified sizes. `per: 200` clears BR-TEN-171's
  // forty rows with room, as `RateScheduleWizard` reads the same list; UNSCOPED
  // by BR-TEN-078, so never filtered by the asset's service.
  const sizeClassesQuery = useQuery({
    queryKey: sizeClassesQueryKey,
    queryFn: () => getLookupEntries("service_size_classes", { per: 200 }, client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const allTypes = typesQuery.data?.results ?? [];
  const tabTypes = typesForTab(allTypes, tab);
  const selectedType = allTypes.find((entry) => entry.code === values.type);
  // While the catalogue is still in flight nothing is resolvable, so the
  // asset's own tab answers: a meter is measuring whatever the lookup says
  // later, and the measuring-only controls must not flicker out from under a
  // clerk who has started typing in them.
  const measuring = isMeasuringCategory(String(selectedType?.category ?? tab));

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {
        serial_no: values.serial_no,
        // ⛔ **BR-AST-044 CLASSIFICATION 1 — AND IT WAS MISSING FOR THE WHOLE
        // LIFE OF THE FORM (`DEF-MET-4971`, CR-092 step 2 lane 3).** The
        // control below is `required` and fully interactive, `assetSchema`
        // marks `type` required, and the frame validated the value and then
        // handed it to a submit that dropped it — so a clerk changed the type,
        // pressed Save, **got the success toast**, and the asset was
        // unchanged. Proved in a browser on brazosbend at 1280 and 1440: chose
        // `backflow`, toast said saved, `GET /assets/{id}` still read `pv`. The
        // server was never the problem — `_validate_asset` lists `type` among
        // its 39 known fields and `update_asset` resolves it through
        // `type_by_code` — so this one line is the whole fix.
        //
        // ⚠ **DO NOT "SIMPLIFY" IT BACK OUT BECAUSE `values.type` IS ALREADY
        // READ ABOVE.** It is read to decide `measuring`, which is exactly why
        // `tsc` and eslint were happy while the field was dead. The assertion
        // that keeps it honest is `AssetEditPayload.dom.test.tsx` TC-E1/TC-E2,
        // which submits this form and reads the body key for key.
        //
        // `type` is NOT one of BR-AST-012's billing-affecting four (multiplier,
        // unit, net_metering, service), so it raises no forward-only warning of
        // its own; BR-AST-010 still applies server-side, and a move to
        // `net_meter` locks net metering ON there rather than here.
        type: values.type,
        read_method: values.read_method === "" ? null : values.read_method,
        manufacturer_model: values.manufacturer_model,
        // ALWAYS sent, even empty, so a required field placed Input on Edit
        // asset can refuse a save that leaves it blank (`CR-161-BRC10` W3).
        custom_data: customDataChanges(openedCustom, customData),
      };
      // BR-AST-044: meter_type travels ONLY for a measuring type. On anything
      // else the server refuses it as a field error — and the control below is
      // not even rendered, so the only way to hit that refusal is a stale form.
      if (measuring) {
        payload.meter_type = values.meter_type === "" ? null : values.meter_type;
        payload.unit = values.unit;
        payload.multiplier = values.multiplier;
      }
      // BR-AST-530 as AMENDED 2026-09-01 (DEF-2414) — the size travels for an
      // asset that stands ON a service connection: a meter, or a non-measuring
      // asset that declares a service (a trash cart IS its connection). A
      // sub-meter is still excluded, which is judgment 4's own reason kept.
      // `offersConnectionSize` is the single predicate and the control below
      // renders on it too, so the two halves of the rule cannot drift.
      //
      // ⚠ **EMPTY SENDS `null`, AND THAT IS AN EXPLICIT CLEAR, NOT AN OMISSION**
      // — the `meter_type` line above does the same for the same reason. On an
      // EDIT the operator is looking at a stored value, so blanking the field is
      // a statement: *"we no longer claim to know this connection's size"*.
      // BR-AST-500 makes that lawful and `assets.services` accepts it.
      //
      // ⚠ BR-AST-501: the size is BILLING-AFFECTING, so changing it on a meter
      // that already has reads raises the server's forward-only warning. The
      // form shows what the server says; it does not re-implement the rule.
      if (offersConnectionSize(tab, asset.service)) {
        payload.size_class = values.size_class === "" ? null : values.size_class;
      }
      // BR-AST-012: multiplier / unit / net_metering / service are FORWARD-ONLY
      // once reads exist — the server applies that, and issued invoices are
      // never restated. The form says so; it does not re-implement the rule.
      return updateAsset(asset.id, payload, client);
    },
    onSuccess: () => {
      // One key covers both the registry lists and this asset's own detail
      // read — `["assets", "detail", id]` sits under it.
      void queryClient.invalidateQueries({ queryKey: ["assets"] });
      fireToast(t("assets.toast.saved", { asset: asset.asset_no }));
      // The correction is saved; the clerk goes back to the asset they were
      // reading, which is the screen that shows them the corrected value.
      navigate(tenantPath(assetDetailPath(asset.id)));
    },
    onError: (error: unknown) => {
      // BR-AST-033: a duplicate asset # is a HARD BLOCK and arrives as a field
      // error under its own field; anything else renders as the strip above the
      // footer. A page has room to show both, which a 640px dialog did not.
      const mapped = envelopeErrors(toEnvelope(error), translate);
      setFieldErrors(mapped.fields);
      setRefusal(mapped.message);
    },
  });

  function submit(): void {
    const validation = collectFormErrors(assetSchema(translate, measuring), values);
    setFieldErrors(validation.errors);
    setRefusal(null);
    if (validation.count > 0) {
      return;
    }
    save.mutate();
  }

  return (
    <>
      {/* B14 rule 32's one sentence: what this screen is for, in the drawing's
          own words. */}
      <Note>{t("assets.edit.lead")}</Note>
      {/* B14 rule 39 / R12–R13: TWO FIELDS TO A ROW, 20px between fields in
          both directions, and the label→input→helper anatomy inside each field
          is the shared `field` block's own. The long field and every Note span
          the pair, which is what "the location note breaks the run because it
          is the long one" means in the drawing — here that field is
          `Manufacturer / model` (see the header note on `DEF-AST-5107`).
          One grid rather than hand-paired rows, so a control the rules hide —
          `meter_type` off a device, `size_class` off a sub-meter — closes its
          gap instead of leaving a hole beside its neighbour. */}
      <div className="grid grid-cols-2 gap-5 max-md:grid-cols-1" data-asset-edit-form="">
        {/* Identifier 1 of 3 (BR-AST-026): the user asset number. It identifies
            the record everywhere and is NOT edited here — `readOnly` rather
            than `disabled`, so it stays selectable and copyable (BR-SHL-025). */}
        <TextField
          id="asset_no"
          label={t("assets.form.assetNo")}
          value={values.asset_no}
          readOnly
          onChange={(value) => setValues({ ...values, asset_no: value })}
          help={t("assets.form.assetNoEditHelp")}
          error={fieldErrors.asset_no}
        />
        {/* Identifier 2 of 3: the physical serial. BR-AST-033: a duplicate here
            WARNS and still saves — the server returns the warning, we show it. */}
        <TextField
          id="serial_no"
          label={t("assets.form.serial")}
          value={values.serial_no}
          onChange={(value) => setValues({ ...values, serial_no: value })}
          help={t("assets.form.serialHelp")}
          error={fieldErrors.serial_no}
        />
        {/* BR-AST-044 classification 1: the asset TYPE. */}
        <SelectField
          id="type"
          label={t("assets.col.assetType")}
          required
          value={values.type}
          options={tabTypes.map((entry) => ({ value: entry.code, label: entry.name }))}
          onChange={(value) => setValues({ ...values, type: value })}
          help={t("assets.form.typeEditHelp")}
          error={fieldErrors.type}
        />
        {/* BR-AST-044 classification 2 — measuring assets ONLY. On a battery or a
            PV panel this control is ABSENT and the server refuses the field, so
            the two halves of the rule agree. */}
        {measuring ? (
          <SelectField
            id="meter_type"
            label={t("assets.col.meterType")}
            value={values.meter_type}
            placeholder={t("assets.form.meterTypePlaceholder")}
            options={meterTypesQuery.data?.results
              .filter((entry) => entry.active)
              .map((entry) => ({ value: entry.code, label: entry.name })) ?? []}
            onChange={(value) => setValues({ ...values, meter_type: value })}
            help={t("assets.form.meterTypeHelp")}
            error={fieldErrors.meter_type}
          />
        ) : (
          <Note className="col-span-2 max-md:col-span-1">
            {t("assets.form.meterTypeUnavailable")}
          </Note>
        )}
        {/* ⛔ BR-AST-530 — THE CONNECTION SIZE ON AN EXISTING METER (AST-02).
            This is the half of the PO's 2026-08-28 ruling that repairs what is
            already loaded: a utility that imported 1,847 meters before the size
            column existed fixes one here, from the sizes on its own list.

            ⚠ ON-THE-CONNECTION ONLY, and the payload above holds the same
            boundary through the same predicate (BR-AST-530 as amended
            2026-09-01, DEF-2414): a meter, or a device that declares a service
            — which is how a trash cart's size became recordable at all.
            ⚠ NOT REQUIRED — blank is lawful and clearing it back to blank is a
            real answer (BR-AST-500). */}
        {offersConnectionSize(tab, asset.service) && (
          <SelectField
            id="size_class"
            label={t("assets.col.sizeClass")}
            value={values.size_class}
            placeholder={t("assets.form.sizeClassPlaceholder")}
            options={(sizeClassesQuery.data?.results ?? [])
              .filter((entry) => entry.active)
              .map((entry) => ({ value: entry.code, label: entry.name }))}
            onChange={(value) => setValues({ ...values, size_class: value })}
            help={t("assets.form.sizeClassHelp")}
            error={fieldErrors.size_class}
          />
        )}
        {/* BR-AST-044 classification 3: how the read is COLLECTED. */}
        <SelectField
          id="read_method"
          label={t("assets.col.readMethod")}
          value={values.read_method}
          placeholder={t("assets.form.readMethodPlaceholder")}
          options={(readMethodsQuery.data?.results ?? [])
            .filter((entry) => entry.active)
            .map((entry) => ({ value: entry.code, label: entry.name }))}
          onChange={(value) => setValues({ ...values, read_method: value })}
          error={fieldErrors.read_method}
        />
        {measuring && (
          <>
            {/* BR-AST-009 / CLAUDE.md #3: a measuring asset carries an EXPLICIT
                unit of measure — never assumed from the service. */}
            <TextField
              id="unit"
              label={t("assets.form.uom")}
              required
              value={values.unit}
              onChange={(value) => setValues({ ...values, unit: value })}
              help={t("assets.form.uomHelp")}
              error={fieldErrors.unit}
            />
            <TextField
              id="multiplier"
              label={t("assets.form.multiplier")}
              numeric
              required
              value={values.multiplier}
              onChange={(value) => setValues({ ...values, multiplier: value })}
              help={t("assets.form.forwardOnly")}
              error={fieldErrors.multiplier}
            />
          </>
        )}
        {/* The long one — it takes the whole row, which is the drawing's own
            treatment of the field that breaks the two-to-a-row run. */}
        <div className="col-span-2 max-md:col-span-1">
          <TextField
            id="manufacturer_model"
            label={t("assets.form.manufacturerModel")}
            value={values.manufacturer_model}
            onChange={(value) => setValues({ ...values, manufacturer_model: value })}
            help={t("assets.form.manufacturerModelHelp")}
            error={fieldErrors.manufacturer_model}
          />
        </div>
      </div>
      {/* `CR-161-BRC10` W3 — Edit asset's slot; nothing for a tenant with none.
          The page's own field errors reach the controls through the scope. */}
      <FieldErrorsScope errors={fieldErrors}>
        <CustomFieldsInput
          entity="assets"
          screen="ASSET_EDIT"
          values={customData}
          onChange={setCustomData}
          client={client}
        />
      </FieldErrorsScope>
      {/* The forward-only consequence, below the fields and above the buttons —
          the drawing's "UNCHANGED: same words, same place". */}
      <Note>{t("assets.form.forwardOnlyNote")}</Note>
      {refusal !== null && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
      {/* Cancel · Save ✓ — moved from a dialog footer to a page footer, same
          words, same order, same primary (B14 rule 12). */}
      <div className="mt-2 flex gap-2 border-t-2 border-divider pt-4">
        <Button variant="ghost" onClick={() => navigate(tenantPath(assetDetailPath(asset.id)))}>
          {t("assets.flow.cancel")}
        </Button>
        <WorkingButton working={save.isPending} onClick={submit}>
          {t("assets.form.save")}
        </WorkingButton>
      </div>
    </>
  );
}

/**
 * The edit form's schema — MOVED from `AssetRegistryPage.tsx` with the form it
 * belongs to. Nothing else ever imported it, and the add wizard has its own
 * per-step schemas (`AssetAddWizard.tsx`).
 */
export function assetSchema(t: Translator, measuring: boolean) {
  return z
    .object({
      asset_no: z.string(),
      serial_no: z.string(),
      type: z.string().trim().min(1, t("assets.form.typeRequired")),
      meter_type: z.string(),
      // BR-AST-530 — free-form only in the SCHEMA's eyes; the control is a
      // SELECT over the tenant's ratified list, and blank is lawful
      // (BR-AST-500), so there is nothing here to require.
      size_class: z.string(),
      read_method: z.string(),
      unit: z.string(),
      multiplier: z.string(),
      manufacturer_model: z.string(),
    })
    .superRefine((values, ctx) => {
      if (!measuring) {
        return;
      }
      // CLAUDE.md #3: a measuring asset never travels without its unit.
      if (values.unit.trim() === "") {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["unit"],
          message: t("assets.form.uomRequired"),
        });
      }
      if (values.multiplier.trim() === "") {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["multiplier"],
          message: t("assets.form.multiplierRequired"),
        });
      }
    });
}
