// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 4 — the New tax or fee form, built from images
//           04–17 of `05-prototype/taxes-fees-2026-10-03/images/` (B14 rules
//           42, 44, 37, 43, 21, 33). Replaces the new-tax half of
//           `TaxWizard.tsx` at `TAX_WIZARD_NEW_ROUTE`.
// Defects:  DEF-RAT-9277 (P1–P20) · DEF-RAT-9275 (*Save draft & exit* must
//           send `as_draft: true`)
// Contract: CR-165-BRC10 §9 — `GET /settings/services`, `GET /taxes/form-options`,
//           `GET /settings/authority-accounts`, `POST /taxes` (+ `as_draft`,
//           `authority_account_id`)
// ───────────────────────────────────────────────────────
//
// THE PAGE: it loads the lists, holds the ONE draft, and lays the four step
// components and the summary panel onto the frame. Every step is a component
// in this folder, so round 3's three edit variations mount the same steps with
// fields locked and a different `steps` array.
//
// ⚠ **NOTHING TYPED IS LOST.** The draft lives here, above every step, and is
// never reset by a refusal — a server error marks the box and opens its step;
// Back, Continue and the rail move between steps over the same draft.
//
// ⚠ **A ROUTE THAT IS NOT SERVED YET IS AN EMPTY LIST, NEVER A BROKEN STEP.**
// `form-options` and `authority-accounts` are new in round 2; every read here
// is `retry: false` and falls back to an empty list, so the form renders with
// an empty dropdown (and the account box's own *Add one* door) either way.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { activateTax, createTax, getTax, updateTax } from "@/api/endpoints";
import type { TaxEditRow } from "@/api/taxEditEndpoints";
import { refusalParams } from "@/api/refusalText";
import { Button } from "@/components/Button";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FieldErrorsScope } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { refusalOf } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { DEFINITION_ROUTES, definitionPath } from "../definitionDetail";
import { DASHBOARD_ROUTE, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "../ratingShared";
import { FilingStep } from "./FilingStep";
import { HowMuchStep } from "./HowMuchStep";
import { ReviewStep } from "./ReviewStep";
import { TaxSavedPanel } from "./TaxSavedPanel";
import { TaxSummaryPanel } from "./TaxSummaryPanel";
import { WhatItIsStep } from "./WhatItIsStep";
import {
  NEW_TAX_STEPS,
  SERVER_FIELD_BOXES,
  emptyTaxFormDraft,
  stepGaps,
  stepNumberOf,
  taxFormPayload,
  withListDefaults,
} from "./taxFormModel";
import type { TaxFormDraft, TaxFormStepSpec } from "./taxFormModel";
import { DRAFT_PARAM, DUPLICATE_PARAM, duplicateDraft, taxFormDraftFromRow } from "./taxEditModel";
import { AUTHORITY_ACCOUNTS_SETTINGS_ROUTE, TAX_FORM_LAYOUT, useTaxFormLists } from "./useTaxFormLists";

/** Re-exported for the callers that imported it from here. */
export { AUTHORITY_ACCOUNTS_SETTINGS_ROUTE };

/** The URL param the open step lives in (BR-SHL-011 — a step is linkable). */
const STEP_PARAM = "step";

export interface NewTaxWizardProps {
  client?: ApiClient; // test seam — screens never build their own transport
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
}

export function NewTaxWizard(props: NewTaxWizardProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const steps: readonly TaxFormStepSpec[] = NEW_TAX_STEPS;
  const [draft, setDraft] = useState<TaxFormDraft>(emptyTaxFormDraft);
  const [nav, setNav] = useState<WizardNavState>({ step: 1, reached: 1 });
  /** The step whose empty boxes are marked — set by a refused Continue, so an
   *  empty form does not open shouting. */
  const [shownStep, setShownStep] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  const [saved, setSaved] = useState<{ id: string; name: string } | null>(null);
  const [drafting, setDrafting] = useState(false);

  // Duplicate (image 21, DEF-RAT-9299): `?duplicate=<id>` opens this form
  // filled from that tax, once, before the clerk types anything. The copy is
  // a NEW tax — `POST /taxes`, its own v1, its own code.
  // A DRAFT (DEF-RAT-9305): `?draft=<id>` opens this form filled from a tax
  // saved with *Save draft & exit*, code and all, and saves IN PLACE —
  // `PATCH /taxes/{id}`, then `POST /taxes/{id}/activate` on *Save tax*.
  const duplicateId = searchParams.get(DUPLICATE_PARAM) ?? "";
  const draftId = searchParams.get(DRAFT_PARAM) ?? "";
  const sourceId = draftId !== "" ? draftId : duplicateId;
  const sourceQuery = useQuery({
    queryKey: ["taxes", "item", sourceId],
    queryFn: () => getTax(sourceId, client) as Promise<TaxEditRow>,
    enabled: sourceId !== "",
    retry: false,
  });
  const [filledFrom, setFilledFrom] = useState<string | null>(null);
  useEffect(() => {
    if (sourceQuery.data !== undefined && filledFrom !== sourceId) {
      setDraft(draftId !== "" ? taxFormDraftFromRow(sourceQuery.data) : duplicateDraft(sourceQuery.data));
      setFilledFrom(sourceId);
    }
  }, [sourceQuery.data, sourceId, draftId, filledFrom]);

  // The lists, the reach and the permissions — shared with the edit form.
  const { current, lists, options, placeBoundaries, permissions: permissionsQuery, translate } = useTaxFormLists({
    draft,
    savedRow: undefined,
    client,
    dateFormat: props.dateFormat,
    timeZone: props.timeZone,
  });

  if (permissionsQuery.isPending || (sourceId !== "" && sourceQuery.isPending)) {
    return <LoadingSkeleton variant="card" />;
  }
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access)) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
  }
  const readOnly = ratingIsReadOnly(access);

  function patch(next: Partial<TaxFormDraft>): void {
    setDraft((was) => ({ ...withListDefaults(was, options), ...next }));
    // A box the clerk has just changed no longer carries the server's refusal.
    if (Object.keys(serverErrors).length > 0) setServerErrors({});
  }

  function goto(next: WizardNavState): void {
    setNav(next);
    const params = new URLSearchParams(searchParams);
    params.set(STEP_PARAM, String(next.step));
    setSearchParams(params, { replace: true });
  }

  const stepId = steps[nav.step - 1]?.id ?? "what";
  const ctx = { placeBoundaries };
  const gaps = shownStep === stepId ? stepGaps(stepId, current, ctx) : {};
  const marks: Record<string, string> = {
    ...Object.fromEntries(Object.entries(gaps).map(([box, key]) => [box, translate(key)])),
    ...serverErrors,
  };
  const markCount = Object.keys(marks).length;

  /** A refusal from the server: mark each box, open the first box's step. */
  function applyRefusal(error: unknown): number | undefined {
    setRefusal(refusalOf(error, translate).message);
    if (!isApiError(error)) return undefined;
    const mapped: Record<string, string> = {};
    let first: number | undefined;
    for (const fieldError of error.fieldErrors) {
      const home = fieldError.field === null ? undefined : SERVER_FIELD_BOXES[fieldError.field];
      if (home === undefined) continue;
      mapped[home.box] = translate(fieldError.message_key, refusalParams(fieldError.params, error.traceId));
      const number = stepNumberOf(home.step, steps);
      first = first === undefined ? number : Math.min(first, number);
    }
    setServerErrors(mapped);
    return first;
  }

  async function commit(): Promise<WizardCommitOutcome> {
    setRefusal(null);
    try {
      const payload = taxFormPayload(current, { asDraft: false, placeBoundaries });
      const row =
        draftId !== ""
          ? (await updateTax(draftId, payload, client), await activateTax(draftId, undefined, client))
          : await createTax(payload, client);
      void queryClient.invalidateQueries({ queryKey: ["taxes"] });
      setSaved({ id: row.id, name: row.name });
      toast(translate("rating.taxes.toast.created", { name: row.name }));
      return { ok: true };
    } catch (error) {
      const step = applyRefusal(error);
      if (step !== undefined) {
        goto({ step, reached: Math.max(nav.reached, step) });
        return { ok: false, reason: refusalOf(error, translate).message, refusedOnStep: step };
      }
      return { ok: false, reason: refusalOf(error, translate).message };
    }
  }

  /** DEF-RAT-9275 — a draft does NOT price, so it is asked for by name. The
   *  server needs a name and an authority to keep anything at all, so those
   *  two are checked first and step 1 opens with them marked if missing. */
  async function saveDraftAndExit(): Promise<void> {
    const first = stepGaps("what", current, ctx);
    if (first["tax-name"] !== undefined || first["tax-authority"] !== undefined) {
      setShownStep("what");
      goto({ step: 1, reached: nav.reached });
      return;
    }
    setDrafting(true);
    setRefusal(null);
    try {
      const row =
        draftId !== ""
          ? await updateTax(draftId, taxFormPayload(current, { asDraft: false, placeBoundaries }), client)
          : await createTax(taxFormPayload(current, { asDraft: true, placeBoundaries }), client);
      void queryClient.invalidateQueries({ queryKey: ["taxes"] });
      toast(translate("rating.taxForm.toast.draft", { name: row.name }));
      navigate(tenantPath(DEFINITION_ROUTES.tax.listRoute));
    } catch (error) {
      const step = applyRefusal(error);
      if (step !== undefined) goto({ step, reached: Math.max(nav.reached, step) });
    } finally {
      setDrafting(false);
    }
  }

  function startAgain(): void {
    setDraft(emptyTaxFormDraft());
    setSaved(null);
    setShownStep(null);
    setServerErrors({});
    setRefusal(null);
    goto({ step: 1, reached: 1 });
  }

  const stepProps = { draft: current, onChange: patch, lists, t: translate };
  const wizardSteps: WizardStep[] = steps.map((spec) => ({
    id: spec.id,
    label: translate(spec.labelKey),
    content:
      spec.id === "what" ? (
        <WhatItIsStep {...stepProps} />
      ) : spec.id === "much" ? (
        <HowMuchStep {...stepProps} />
      ) : spec.id === "filing" ? (
        <FilingStep {...stepProps} />
      ) : saved !== null ? (
        <TaxSavedPanel
          draft={current}
          lists={lists}
          savedName={saved.name}
          t={translate}
          onOpen={() => navigate(tenantPath(definitionPath("tax", saved.id)))}
          onAnother={startAgain}
        />
      ) : (
        <ReviewStep
          draft={current}
          lists={lists}
          steps={steps}
          t={translate}
          onEdit={(step) => goto({ step, reached: nav.reached })}
        />
      ),
    validate: () => {
      const found = stepGaps(spec.id, current, ctx);
      if (Object.keys(found).length > 0) {
        setShownStep(spec.id);
        return false;
      }
      setShownStep(null);
      return true;
    },
  }));

  return (
    <div className="flex flex-col gap-5" data-screen="new-tax">
      <PageHeader
        title={translate("rating.taxForm.title")}
        secondaryActions={
          saved === null ? (
            <Button disabled={readOnly || drafting} onClick={() => void saveDraftAndExit()}>
              {translate("rating.taxForm.saveDraft")}
            </Button>
          ) : undefined
        }
      />
      {readOnly && <RefusalStrip role="note">{translate("rating.readOnlyReason")}</RefusalStrip>}
      {refusal !== null && markCount === 0 && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
      <FieldErrorsScope errors={marks}>
        <div className={TAX_FORM_LAYOUT} data-tax-layout="">
          <WizardFrame
            steps={wizardSteps}
            nav={nav}
            onNavChange={goto}
            complete={saved !== null}
            doneMark="tick"
            backAtStart
            cancel={
              nav.step === 1
                ? { label: translate("rating.taxForm.cancel"), onCancel: () => navigate(tenantPath(DEFINITION_ROUTES.tax.listRoute)) }
                : undefined
            }
            actionNote={
              markCount > 0 ? (
                <p className="m-0 text-base font-semibold text-danger-700" role="alert" data-tax-fix-count={markCount}>
                  {translate("rating.taxForm.fixFirst", { count: markCount })}
                </p>
              ) : undefined
            }
            commitLabel={translate("rating.taxForm.saveTax")}
            commitDisabled={readOnly}
            commitFailedTitle={translate("rating.taxForm.saveFailed")}
            onCommit={commit}
            onCommitted={() => undefined}
          />
          <div className="col-start-2 row-start-2 row-span-2 self-start">
            <TaxSummaryPanel draft={current} lists={lists} t={translate} />
          </div>
        </div>
      </FieldErrorsScope>
    </div>
  );
}

export default NewTaxWizard;
