// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 task 7 — EDIT a tax or fee, built from images 24–33 of
//           `05-prototype/taxes-fees-2026-10-03/images/` (B14 rules 42, 44, 37,
//           43, 21, 33). Replaces `TaxWizard.tsx` at `TAX_WIZARD_EDIT_PATTERN`.
// Defects:  DEF-RAT-9273 (P44–P50)
// Rules:    PO 2026-10-03, verbatim: *"We dont use side panel for edit - you will
//           need to send it back to Edit form - You can use add form with
//           variation"* · README point 6 (the three choices) · CR-008 as amended
//           2026-10-03 (the liability account is Settings' alone on a live tax)
// Contract: CR-165-BRC10 §9/§10 — `GET /taxes/{id}`, `PATCH /taxes/{id}`,
//           `POST /taxes/{id}/new-rate`, `POST /taxes/{id}/corrections`
// ───────────────────────────────────────────────────────
//
// THE SAME FULL-PAGE FORM AS NEW, WITH A VARIATION. *What to change* sits on
// top; the chosen card (`?change=info|change|correct`, the address the details
// page links to) picks the step list and the set of LOCKED fields, and the New
// form's own step components render over a draft read back from the tax.
//
// ⚠ **SWITCHING CARDS STARTS THAT FLOW AGAIN FROM THE TAX AS SAVED.** A name
// typed under *Name and filing* is not something *New rate from a date* can
// send, so carrying it across would show it in the summary and then not save
// it. The draft is reset to the served row; the card says which flow is open.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { correctTax, getTax, updateTax } from "@/api/endpoints";
import { refusalParams } from "@/api/refusalText";
import { newTaxRate } from "@/api/taxEditEndpoints";
import type { TaxEditRow } from "@/api/taxEditEndpoints";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FieldErrorsScope, TextField } from "@/components/FormModal";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { WizardFrame } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState, WizardStep } from "@/components/WizardFrame";
import { refusalOf } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { definitionPath } from "../definitionDetail";
import { DASHBOARD_ROUTE, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "../ratingShared";
import { EditChoiceCards } from "./EditChoiceCards";
import { EditNameStep } from "./EditNameStep";
import { EditReviewStep, changedReviewRows } from "./EditReviewStep";
import { EditSavedPanel } from "./EditSavedPanel";
import { FilingStep } from "./FilingStep";
import { HowMuchStep } from "./HowMuchStep";
import { TaxSummaryPanel } from "./TaxSummaryPanel";
import {
  CHANGE_PARAM,
  EDIT_SERVER_FIELD_BOXES,
  EDIT_STEPS,
  correctionPayload,
  dayBefore,
  editModeOf,
  editStepGaps,
  infoPatchPayload,
  lockedFields,
  newRatePayload,
  taxFormDraftFromRow,
} from "./taxEditModel";
import type { TaxEditMode } from "./taxEditModel";
import { SERVER_FIELD_BOXES, emptyTaxFormDraft, stepNumberOf } from "./taxFormModel";
import type { TaxFormDraft } from "./taxFormModel";
import { SECTION_HEADING } from "./taxFormShared";
import { TAX_FORM_LAYOUT, useTaxFormLists } from "./useTaxFormLists";

/** The URL param the open step lives in (BR-SHL-011 — a step is linkable). */
const STEP_PARAM = "step";

/** Literal keys, so G18 can see each one used. */
const COMMIT_KEYS: Record<TaxEditMode, string> = {
  info: "rating.taxEdit.save.info",
  change: "rating.taxEdit.save.change",
  correct: "rating.taxEdit.save.correct",
};

export interface EditTaxFormProps {
  client?: ApiClient; // test seam — screens never build their own transport
  dateFormat?: RegionalDateFormat;
  timeZone?: string;
}

interface Saved {
  /** The row *Back to tax* opens — the correction, which replaced the one edited. */
  id: string;
  name: string;
  sentence: string;
}

export function EditTaxForm(props: EditTaxFormProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { taxId = "" } = useParams<{ taxId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const mode = editModeOf(searchParams.get(CHANGE_PARAM));
  const steps = EDIT_STEPS[mode];

  const taxQuery = useQuery({
    queryKey: ["taxes", "item", taxId],
    queryFn: () => getTax(taxId, client) as Promise<TaxEditRow>,
    enabled: taxId !== "",
    retry: false,
  });
  const row = taxQuery.data;
  const original = useMemo(() => (row === undefined ? emptyTaxFormDraft() : taxFormDraftFromRow(row)), [row]);

  const [draft, setDraft] = useState<TaxFormDraft | null>(null);
  const [reason, setReason] = useState("");
  const [nav, setNav] = useState<WizardNavState>({ step: 1, reached: 1 });
  const [shownStep, setShownStep] = useState<string | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [refusal, setRefusal] = useState<string | null>(null);
  const [saved, setSaved] = useState<Saved | null>(null);

  const { current, lists, permissions, translate } = useTaxFormLists({
    draft: draft ?? original,
    savedRow: row,
    client,
    dateFormat: props.dateFormat,
    timeZone: props.timeZone,
  });
  const day = (value: string) => (value === "" ? "—" : formatDate(value, lists.timeZone, lists.dateFormat));
  const detailPath = tenantPath(definitionPath("tax", taxId));

  if (permissions.isPending || taxQuery.isPending) {
    return <LoadingSkeleton variant="card" />;
  }
  const access = ratingAccess(permissions.data);
  if (ratingIsDenied(access)) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
  }
  if (row === undefined) {
    return (
      <FailedWithRetry
        title={translate("rating.taxEdit.loadFailed")}
        reason={refusalOf(taxQuery.error, translate).message}
        onRetry={() => void taxQuery.refetch()}
      />
    );
  }
  const readOnly = ratingIsReadOnly(access);
  const version = row.version ?? 1;
  const locked = lockedFields(mode);

  function patch(next: Partial<TaxFormDraft>): void {
    setDraft((was) => ({ ...(was ?? original), ...next }));
    if (Object.keys(serverErrors).length > 0) setServerErrors({});
  }

  function goto(next: WizardNavState): void {
    setNav(next);
    const params = new URLSearchParams(searchParams);
    params.set(STEP_PARAM, String(next.step));
    setSearchParams(params, { replace: true });
  }

  function choose(next: TaxEditMode): void {
    if (next === mode) return;
    setDraft(null);
    setReason("");
    setShownStep(null);
    setServerErrors({});
    setRefusal(null);
    setNav({ step: 1, reached: 1 });
    const params = new URLSearchParams(searchParams);
    params.set(CHANGE_PARAM, next);
    params.set(STEP_PARAM, "1");
    setSearchParams(params, { replace: true });
  }

  const stepId = steps[nav.step - 1]?.id ?? "what";
  const ctx = { placeBoundaries: lists.placeBoundaries, liveFrom: original.effective_from, reason };
  const gaps = shownStep === stepId ? editStepGaps(mode, stepId, current, ctx) : {};
  const marks: Record<string, string> = {
    ...Object.fromEntries(
      Object.entries(gaps).map(([box, gap]) => [
        box,
        translate(gap.key, gap.params?.date === undefined ? gap.params : { ...gap.params, date: day(String(gap.params.date)) }),
      ]),
    ),
    ...serverErrors,
  };
  const markCount = Object.keys(marks).length;
  const nothingChanged = mode !== "change" && changedReviewRows({ original, draft: current, lists, t: translate }).length === 0;

  /** A refusal from the server: mark each box, open the first box's step. */
  function applyRefusal(error: unknown): number | undefined {
    setRefusal(refusalOf(error, translate).message);
    if (!isApiError(error)) return undefined;
    const mapped: Record<string, string> = {};
    let first: number | undefined;
    for (const fieldError of error.fieldErrors) {
      const home =
        fieldError.field === null
          ? undefined
          : (EDIT_SERVER_FIELD_BOXES[fieldError.field] ?? SERVER_FIELD_BOXES[fieldError.field]);
      if (home === undefined) continue;
      const params = refusalParams(fieldError.params, error.traceId);
      if (typeof params.starts === "string") params.starts = day(params.starts);
      mapped[home.box] = translate(fieldError.message_key, params);
      const number = stepNumberOf(home.step, steps);
      first = first === undefined ? number : Math.min(first, number);
    }
    setServerErrors(mapped);
    return first;
  }

  async function save(): Promise<Saved> {
    if (mode === "info") {
      const next = await updateTax(taxId, infoPatchPayload(original, current), client);
      return { id: next.id, name: next.name, sentence: translate("rating.taxEdit.saved.info") };
    }
    if (mode === "change") {
      const next = await newTaxRate(taxId, newRatePayload(current, original), client);
      return {
        id: taxId,
        name: next.name,
        sentence: translate("rating.taxEdit.saved.change", { v: next.version ?? version + 1, date: day(current.effective_from) }),
      };
    }
    const next = (await correctTax(taxId, correctionPayload(original, current, reason), client)) as TaxEditRow;
    return {
      id: next.id,
      name: next.name,
      sentence: translate("rating.taxEdit.saved.correct", { v: next.version ?? version + 1, old: version }),
    };
  }

  async function commit(): Promise<WizardCommitOutcome> {
    setRefusal(null);
    try {
      const done = await save();
      void queryClient.invalidateQueries({ queryKey: ["taxes"] });
      setSaved(done);
      toast(translate("rating.taxForm.saved.title", { name: done.name }));
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

  const stepProps = { draft: current, onChange: patch, lists, locked, t: translate };
  const reasonSection = (
    <Panel as="section" aria-labelledby="tax-sec-reason">
      <h2 id="tax-sec-reason" className={SECTION_HEADING}>
        {translate("rating.taxEdit.section.reason")}
      </h2>
      <TextField
        id="tax-reason"
        label={translate("rating.taxEdit.field.reason")}
        required
        value={reason}
        placeholder={translate("rating.taxEdit.placeholder.reason")}
        help={translate("rating.taxEdit.help.reason")}
        onChange={(next) => {
          setReason(next);
          if (Object.keys(serverErrors).length > 0) setServerErrors({});
        }}
      />
    </Panel>
  );

  const wizardSteps: WizardStep[] = steps.map((spec) => ({
    id: spec.id,
    label: translate(spec.labelKey),
    content:
      spec.id === "what" ? (
        <EditNameStep {...stepProps} />
      ) : spec.id === "filing" ? (
        <FilingStep {...stepProps} />
      ) : spec.id === "much" ? (
        mode === "correct" ? (
          <HowMuchStep
            {...stepProps}
            dates={{ lockedNote: translate("rating.taxEdit.lock.dates") }}
            afterDates={reasonSection}
          />
        ) : (
          <HowMuchStep
            {...stepProps}
            dates={{
              fromLabel: translate("rating.taxEdit.field.newFrom"),
              fromHelp:
                // A start on or before today's start is refused, so "today's
                // rate ends 07/31/2026" would describe a save that cannot happen.
                current.effective_from === "" || current.effective_from <= original.effective_from
                  ? translate("rating.taxEdit.help.newFrom")
                  : translate("rating.taxEdit.help.todayEnds", { date: day(dayBefore(current.effective_from)) }),
            }}
          />
        )
      ) : saved !== null ? (
        <EditSavedPanel
          name={saved.name}
          sentence={saved.sentence}
          t={translate}
          onBack={() => navigate(tenantPath(definitionPath("tax", saved.id)))}
        />
      ) : (
        <EditReviewStep
          mode={mode}
          original={original}
          draft={current}
          version={version}
          reason={reason}
          lists={lists}
          steps={steps}
          t={translate}
          onEdit={(step) => goto({ step, reached: nav.reached })}
        />
      ),
    validate: () => {
      const found = editStepGaps(mode, spec.id, current, ctx);
      if (Object.keys(found).length > 0) {
        setShownStep(spec.id);
        return false;
      }
      setShownStep(null);
      return true;
    },
  }));

  return (
    <div className="flex flex-col gap-5" data-screen="edit-tax" data-tax-edit-mode={mode}>
      <PageHeader
        title={translate("rating.taxEdit.title", { name: row.name })}
        backTo={{ to: detailPath, label: row.name }}
      />
      {readOnly && <RefusalStrip role="note">{translate("rating.readOnlyReason")}</RefusalStrip>}
      {refusal !== null && markCount === 0 && <RefusalStrip role="alert">{refusal}</RefusalStrip>}
      <EditChoiceCards mode={mode} onChoose={choose} disabled={saved !== null} t={translate} />
      <FieldErrorsScope errors={marks}>
        <div className={TAX_FORM_LAYOUT} data-tax-layout="">
          <WizardFrame
            key={mode}
            steps={wizardSteps}
            nav={nav}
            onNavChange={goto}
            complete={saved !== null}
            doneMark="tick"
            backAtStart
            cancel={
              nav.step === 1
                ? { label: translate("rating.taxForm.cancel"), onCancel: () => navigate(detailPath) }
                : undefined
            }
            actionNote={
              markCount > 0 ? (
                <p className="m-0 text-base font-semibold text-danger-700" role="alert" data-tax-fix-count={markCount}>
                  {translate("rating.taxForm.fixFirst", { count: markCount })}
                </p>
              ) : undefined
            }
            commitLabel={translate(COMMIT_KEYS[mode])}
            commitDisabled={readOnly || nothingChanged}
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

export default EditTaxForm;
