// ── Trace ──────────────────────────────────────────────
// Change:   CR-177-BRC10 round B — Add a premise (S16 / PRM-07), redesigned.
//           PO GO 2026-10-09 (decision log *"PO GO — BUILD THE ADD-A-PREMISE
//           REDESIGN"*), in the format of the Discounts redesign.
// Defect:   DEF-MET-10034 — search on every keystroke at a utility with no City
//           map; parcel, point and *Checked against GIS* at a utility with no
//           City map; `3721 S Village Dr,, Avenel`; a required custom field
//           skipped on Review.
// Rules:    BR-MET-1190–1195 (new, 2026-10-09) · BR-MET-001 (the number comes
//           from the series at the save) · BR-SHL-018/019 (wizard navigation,
//           ONE transactional commit) · B14 rules 21, 31, 32, 33, 37, 42, 43, 44
// Drawing:  05-prototype/add-premise-2026-10-09/images/01–14
// Reads:    GET /premises/types · GET /settings/services · GET /routes ·
//           GET /lookups/areas · the custom-field registry (premises, S16) ·
//           GET /premises/number-preview · GET /premises/same-address ·
//           GET /premises/owner-search · POST /integrations/gis_esri/check-address
// Writes:   POST /premises, or POST /integrations/gis_esri/premises after
//           *Use these details* (the City is asked again at the save)
// ───────────────────────────────────────────────────────
//
// THREE STEPS — Property · Units · Review. The old step 1, *How many?*, is gone:
// bulk adds go through Import (PO 2026-10-09: *"there is seperate improt
// fucntion for premsies bulk import so step 1 how many not required"*).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import {
  checkCityAddress,
  createPremises,
  createPremisesFromCity,
  getLookupEntries,
  getPremiseNumberPreview,
  getPremisesTypes,
  getRoutes,
  getSameAddressPremise,
  getTenantServices,
} from "@/api/endpoints";
import { customFieldErrors, useCustomFieldRegistry } from "@/components/CustomFields";
import { formatDate as formatRegionalDate } from "@/components/DateCell";
import { FieldErrorsScope } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { apiErrorText } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  GuardedButton,
  PREMISES_ROUTE,
  areaLookupQueryKey,
  premisesDetailPath,
  useRegional,
} from "../meteringShared";
import { routesQueryKey } from "../RoutesCyclesPage";
import { enabledServiceRows } from "../ServicesAvailableField";
import {
  addPremisePayload,
  addressParts,
  addressReadyToCompare,
  checkFromAnswer,
  emptyAddPremiseForm,
  linkedOwner,
  sameAddressFromParams,
  withCityAddress,
} from "./addPremiseModel";
import type { AddPremiseForm, AddressCheck, OwnerState, SameAddressState } from "./addPremiseModel";
import { ADD_PREMISE_LAYOUT } from "./addPremiseShared";
import type { Translator } from "./addPremiseShared";
import { CUSTOM_FIELDS_SETTINGS_ROUTE, PropertyStep, missingRequiredKeys } from "./PropertyStep";
import type { OpenSections } from "./PropertyStep";
import { PremiseSummaryCard, ReviewStep } from "./ReviewStep";
import type { ReviewContext } from "./ReviewStep";
import { UnitsStep } from "./UnitsStep";

export interface AddPremisePageProps {
  client?: ApiClient;
}

const ADDRESS_KEYS = ["address_line", "city", "state", "postal_code"] as const;

function addressMoved(before: AddPremiseForm, after: AddPremiseForm): boolean {
  return ADDRESS_KEYS.some((key) => before[key] !== after[key]);
}

function todayIso(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function AddPremisePage(props: AddPremisePageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const regional = useRegional({});
  const formatDate = (iso: string) =>
    formatRegionalDate(iso, regional.timeZone, regional.dateFormat);

  const [form, setForm] = useState<AddPremiseForm>(emptyAddPremiseForm);
  const [nav, setNav] = useState<WizardNavState>({ step: 1, reached: 1 });
  const [check, setCheck] = useState<AddressCheck>({ kind: "none" });
  const [same, setSame] = useState<SameAddressState | null>(null);
  const [owner, setOwner] = useState<OwnerState>({ kind: "none" });
  const [open, setOpen] = useState<OpenSections>({ map: false, owner: false, area: false, custom: false });
  const [commonOpen, setCommonOpen] = useState(false);
  const [marks, setMarks] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<string | null>(null);

  const typesQuery = useQuery({
    queryKey: ["premises", "types"],
    queryFn: () => getPremisesTypes(client),
    staleTime: 5 * 60 * 1000,
    retry: false,
  });
  // BR-MET-1193 — the utility's ACTIVE services, from the one place that says.
  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  // BR-MET-076 — only an ACTIVE route may be offered. The same cache key the
  // routes screen writes, so the two cannot disagree about a route's status.
  const routesQuery = useQuery({
    queryKey: routesQueryKey,
    queryFn: () => getRoutes(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const areasQuery = useQuery({
    queryKey: areaLookupQueryKey,
    queryFn: () => getLookupEntries("areas", { per: 200 }, client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const registry = useCustomFieldRegistry({ entity: "premises", screen: "S16", mode: "input", client });
  // BR-MET-1165 — previewed, never reserved; re-read whenever the step changes.
  const numberQuery = useQuery({
    queryKey: ["premises", "number-preview", nav.step],
    queryFn: () => getPremiseNumberPreview(client),
    staleTime: 0,
    retry: false,
  });

  const services = enabledServiceRows(servicesQuery.data);
  const routes = (routesQuery.data ?? []).filter((row) => row.status === "active");
  const areas = areasQuery.data?.results ?? [];
  const customFields = registry.data ?? [];
  const premiseNumber = numberQuery.data?.number ?? null;

  function onForm(next: AddPremiseForm): void {
    if (addressMoved(form, next)) {
      // An answer about another address is not an answer about this one.
      setCheck({ kind: "none" });
      setSame(null);
    }
    if (Object.keys(marks).length > 0) setMarks({});
    setRefusal(null);
    setForm(next);
  }

  function goto(next: WizardNavState): void {
    setNav(next);
    window.scrollTo?.({ top: 0 });
  }

  /** BR-MET-1190 — asked when the address is complete, and again on Continue. */
  async function compareAddress(of: AddPremiseForm): Promise<SameAddressState | null> {
    if (!addressReadyToCompare(of)) {
      setSame(null);
      return null;
    }
    try {
      const premise = await getSameAddressPremise(addressParts(of), client);
      const next =
        premise === null
          ? null
          : same !== null && same.premise.id === premise.id
            ? same
            : { premise, choice: null };
      setSame(next);
      return next;
    } catch {
      // The save asks again and refuses by name; a failed courtesy blocks nothing.
      return same;
    }
  }

  async function onCheck(): Promise<void> {
    if (form.address_line.trim() === "") {
      setMarks({ address_line: translate("metering.premises.address_required") });
      return;
    }
    setCheck({ kind: "checking" });
    try {
      setCheck(checkFromAnswer(await checkCityAddress(addressParts(form), client), todayIso()));
    } catch {
      setCheck({ kind: "unavailable", messageKey: null });
    }
  }

  function onUseDetails(): void {
    if (check.kind !== "match") return;
    const next = withCityAddress(form, check.match);
    setForm(next);
    setCheck({ ...check, used: true });
    setSame(null);
    void compareAddress(next);
  }

  function validateProperty(): Promise<boolean> | boolean {
    const found: Record<string, string> = {};
    if (form.address_line.trim() === "") {
      found.address_line = translate("metering.premises.address_required");
    }
    const missing = missingRequiredKeys(customFields, form.custom_data);
    for (const key of missing) found[`custom_data.${key}`] = translate("customFields.required");
    if (missing.length > 0) setOpen((was) => ({ ...was, custom: true }));
    setMarks(found);
    if (Object.keys(found).length > 0) return false;
    return compareAddress(form).then((answer) => answer === null || answer.choice !== null);
  }

  function applyRefusal(error: unknown): number {
    setRefusal(apiErrorText(error, translate));
    if (!isApiError(error)) return 1;
    if (error.messageKey === "metering.premises.same_address_exists") {
      const premise = sameAddressFromParams(error.params);
      if (premise !== null) setSame({ premise, choice: null });
      setRefusal(null);
      return 1;
    }
    const custom = customFieldErrors(error.fieldErrors, translate);
    const named: Record<string, string> = { ...custom };
    let step = 1;
    for (const fieldError of error.fieldErrors) {
      if (fieldError.field === null || fieldError.field.startsWith("custom_data.")) continue;
      named[fieldError.field] = translate(fieldError.message_key, fieldError.params ?? {});
      if (fieldError.field === "units" || fieldError.field.startsWith("units")) step = 2;
    }
    if (Object.keys(custom).length > 0) setOpen((was) => ({ ...was, custom: true }));
    setMarks(named);
    return step;
  }

  async function commit(): Promise<WizardCommitOutcome> {
    setRefusal(null);
    const payload = addPremisePayload(form, { owner: linkedOwner(owner), addAnyway: same?.choice === "anyway" });
    try {
      const created =
        check.kind === "match" && check.used
          ? await createPremisesFromCity(
              { parcel: check.match.parcel, point: check.match.point, session: check.session, premises: payload },
              client,
            )
          : await createPremises(payload, client);
      void queryClient.invalidateQueries({ queryKey: ["premises"] });
      toast(translate("metering.wizard.toast.premiseCreated", { premise: created.premise_no ?? created.address_line ?? "" }));
      return { ok: true };
    } catch (error) {
      const step = applyRefusal(error);
      goto({ step, reached: nav.reached });
      return { ok: false, reason: apiErrorText(error, translate), refusedOnStep: step };
    }
  }

  const ctx: ReviewContext = {
    form,
    premiseNumber,
    check,
    owner,
    types: typesQuery.data ?? [],
    services,
    routes,
    areas,
    customFields,
    formatDate,
    t: translate,
  };

  const steps: WizardStep[] = [
    {
      id: "property",
      label: translate("metering.addPremise.step.property"),
      content: (
        <PropertyStep
          form={form}
          onForm={onForm}
          onAddressDone={() => void compareAddress(form)}
          types={typesQuery.data ?? []}
          services={services}
          routes={routes}
          routesState={routesQuery.isError ? "failed" : routesQuery.isPending ? "loading" : "ready"}
          areas={areas}
          customFields={customFields}
          check={check}
          onCheck={() => void onCheck()}
          onUseDetails={onUseDetails}
          onKeepMine={() => setCheck({ kind: "none" })}
          same={same}
          onOpenSame={() => {
            if (same !== null) navigate(tenantPath(premisesDetailPath(same.premise.id)));
          }}
          onAddAnyway={() => setSame((was) => (was === null ? null : { ...was, choice: "anyway" }))}
          owner={owner}
          onOwner={setOwner}
          open={open}
          onToggle={(section) => setOpen((was) => ({ ...was, [section]: !was[section] }))}
          customFieldsSettingsTo={tenantPath(CUSTOM_FIELDS_SETTINGS_ROUTE)}
          formatDate={formatDate}
          t={translate}
          client={client}
        />
      ),
      validate: validateProperty,
    },
    {
      id: "units",
      label: translate("metering.addPremise.step.units"),
      content: (
        <UnitsStep
          form={form}
          onForm={onForm}
          services={services}
          commonOpen={commonOpen}
          onToggleCommon={() => setCommonOpen((was) => !was)}
          t={translate}
          client={client}
        />
      ),
    },
    {
      id: "review",
      label: translate("metering.addPremise.step.review"),
      content: <ReviewStep ctx={ctx} onEdit={(step) => goto({ step, reached: nav.reached })} />,
    },
  ];

  return (
    <div className="flex flex-col gap-5" data-screen="add-premise">
      <PageHeader
        title={translate("metering.addPremise.title")}
        backTo={{ to: tenantPath(PREMISES_ROUTE), label: translate("metering.addPremise.back") }}
        secondaryActions={
          // A premise has no draft state to save into (`premises.status` is
          // written live by `POST /premises`), so the drawn control is shown
          // and refused with its reason (BR-SHL-025) rather than hidden.
          <GuardedButton
            label={translate("metering.wizard.saveDraftExit")}
            reason={translate("metering.wizard.saveDraftHeld")}
            onClick={() => undefined}
          />
        }
      />
      {refusal !== null && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
      <FieldErrorsScope errors={marks}>
        <div className={ADD_PREMISE_LAYOUT} data-add-premise-layout="">
          <WizardFrame
            steps={steps}
            nav={nav}
            onNavChange={goto}
            doneMark="tick"
            backAtStart
            cancel={
              nav.step === 1
                ? { label: translate("metering.addPremise.cancel"), onCancel: () => navigate(tenantPath(PREMISES_ROUTE)) }
                : undefined
            }
            commitLabel={translate("metering.addPremise.commit")}
            commitFailedTitle={translate("metering.wizard.commitFailed")}
            onCommit={commit}
            onCommitted={() => navigate(tenantPath(PREMISES_ROUTE))}
          />
          <div className="col-start-2 row-start-2 row-span-2 self-start">
            <PremiseSummaryCard ctx={ctx} />
          </div>
        </div>
      </FieldErrorsScope>
    </div>
  );
}

export default AddPremisePage;
