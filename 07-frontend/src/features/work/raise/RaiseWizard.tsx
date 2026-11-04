// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 round 3, lane RAISE — THE raise, and its three doors:
//           Work › Orders (images 14–18), an account (image 19) and an asset
//           (image 20). P2.2–P2.4, P2.15, P2.16, P2.18, P2.19.
// Rulings:  19–25 and 35 (the CR's §0 table, the PO's words quoted there).
// Defects:  DEF-WRK-9572 · DEF-WRK-9582 · DEF-WRK-4752.
// Rules:    B14 rules 2/16 (a step flow keeps its footer), 3 (a three-step
//           flow gets the step bar, not a page head), 4, 11, 21 (this folder
//           is on route-b-migrated.txt), 31, 33, 37 (a drawn figure is an
//           illustration), 42 (built from the images), 43, 44 · BR-WRK-006
//           (an anchor is required) · BR-WRK-008 (the template's copy) ·
//           BR-WRK-024 (the source is stamped) · BR-WRK-056 (the asset door is
//           Work's own write — it holds; ruling 35 retires only the one-page
//           FORM, Assets blueprint figure 42).
// Tests:    src/features/work/raise/cr168Raise.dom.test.tsx ·
//           src/features/work/raise/cr168RaiseAccount.dom.test.tsx ·
//           src/features/work/raise/raiseModel.test.ts
// ───────────────────────────────────────────────────────
//
// ⚠ **THREE STEPS, ONE WRITE.** Nothing is written until *Raise N jobs ✓*:
// close the tab on step 2 and no row exists and no `WO-` number is burned.
// The one write is `POST /work-orders/bulk-raise` — one job per unit, or per
// asset once an asset type is chosen (rulings 19, 20) — which the server runs
// with ONE SAVEPOINT PER JOB (law 14) and answers per job (`BR-WRK-027`).
//
// ⚠ **ONE WIZARD, THREE DOORS, AND THE DOOR ONLY DECIDES WHAT ARRIVES FILLED**
// (ruling 35). An account fixes the premises and the unit; an asset fixes the
// premises, the unit and the asset itself. Everything after step 1 is the same
// screen — *"the rest is 1·4b and 1·4c"* in the blueprint's own words.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountDetail, getAsset, getPremisesDetail, getUnit, getUnitAccount } from "@/api/endpoints";
import { customFieldErrors, missingRequiredLabels, useCustomFieldRegistry } from "@/components/CustomFields";
import { isApiError } from "@/api/client";
import { formatDate } from "@/components/DateCell";
import { Kicker } from "@/components/TextBits";
import { useRegional } from "@/features/metering/meteringShared";
import { WizardFrame, clampStepToReached, initialWizardNav } from "@/components/WizardFrame";
import type { WizardCommitOutcome, WizardNavState } from "@/components/WizardFrame";
import { useTenantPath } from "@/routing/tenantPath";
import i18n from "@/i18n";

import { WORK_ORDERS_ROUTE } from "../WorkShell";
import { getRaiseOptions } from "../workEndpoints";
import { windowMoments } from "../visitWindow";

import { RaiseConfirmStep, RaiseResult } from "./RaiseConfirm";
import type { RaiseJobLine } from "./RaiseConfirm";
import type { RaiseFact } from "./RaiseFacts";
import { RaiseFacts } from "./RaiseFacts";
import { RaiseJobStep } from "./RaiseJobStep";
import type { RaiseFixed, RaiseJobErrors } from "./RaiseJobStep";
import { RaiseScheduleStep } from "./RaiseScheduleStep";
import { bulkRaise } from "./raiseEndpoints";
import type { BulkRaiseOutcome } from "./raiseEndpoints";
import { EMPTY_RAISE_FORM } from "./raiseForm";
import type { RaiseForm } from "./raiseForm";
import { assigneeFor, dueFromPriority, newIdempotencyKey, unitsMissingAnAsset } from "./raiseModel";
import type { RaiseOrigin } from "./raiseModel";

/** r10's own badge, carried by every image 14–20 (`WRK-12`). */
export const RAISE_SCREEN = "WRK-12";

export function RaiseWizard(props: { origin: RaiseOrigin; client?: ApiClient }) {
  const client = props.client ?? api;
  const { t } = useTranslation();
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const origin = props.origin;

  // The step is URL state (A9): a reload keeps it, and a pasted ?step=3 clamps
  // to 1 because `reached` is 1 (BR-SHL-018).
  const [params, setParams] = useSearchParams();
  const [nav, setNav] = useState<WizardNavState>(() =>
    clampStepToReached(Number(params.get("step") ?? 1), initialWizardNav(), 3),
  );
  function moveTo(next: WizardNavState) {
    setNav(next);
    const search = new URLSearchParams(params);
    search.set("step", String(next.step));
    setParams(search, { replace: true });
  }

  const [form, setForm] = useState<RaiseForm>(EMPTY_RAISE_FORM);
  const update = useCallback((patch: Partial<RaiseForm>) => setForm((current) => ({ ...current, ...patch })), []);
  const [errors, setErrors] = useState<RaiseJobErrors>({});
  const [customErrors, setCustomErrors] = useState<Record<string, string>>({});
  const customRegistry = useCustomFieldRegistry({ entity: "work_orders", screen: "WORK_NEW", mode: "input", client });
  const [outcome, setOutcome] = useState<BulkRaiseOutcome | null>(null);
  const [complete, setComplete] = useState(false);
  const [idempotencyKey, setIdempotencyKey] = useState(() => newIdempotencyKey());

  // ── What each door brings (ruling 35) ───────────────────────────────────
  const seededPremises = origin.kind === "work" ? (origin.premisesId ?? "") : "";
  const seeded = useQuery({
    queryKey: ["work", "raise", "seed-premises", seededPremises],
    queryFn: () => getPremisesDetail(seededPremises, client),
    enabled: seededPremises !== "",
  });
  const [seedApplied, setSeedApplied] = useState(false);
  useEffect(() => {
    if (seeded.data === undefined || seedApplied) return;
    const row = seeded.data;
    setSeedApplied(true);
    update({
      premisesId: row.id,
      premisesLabel: [row.address_line, row.city].filter((s) => s !== null && s !== "").join(" · "),
      premisesDetail: row.premises_type_name ?? "",
    });
  }, [seeded.data, seedApplied, update]);

  const account = useQuery({
    queryKey: ["work", "raise", "account", origin.kind === "account" ? origin.accountId : ""],
    queryFn: () => getAccountDetail(origin.kind === "account" ? origin.accountId : "", client),
    enabled: origin.kind === "account",
  });
  const asset = useQuery({
    queryKey: ["work", "raise", "asset", origin.kind === "asset" ? origin.assetId : ""],
    queryFn: () => getAsset(origin.kind === "asset" ? origin.assetId : "", client),
    enabled: origin.kind === "asset",
  });
  const fixedUnitId =
    origin.kind === "account" ? (account.data?.unit_id ?? "") : origin.kind === "asset" ? (asset.data?.assigned_unit_id ?? "") : "";
  const unit = useQuery({
    queryKey: ["units", "detail", fixedUnitId],
    queryFn: () => getUnit(fixedUnitId, client),
    enabled: fixedUnitId !== "",
  });
  const assetAccount = useQuery({
    queryKey: ["units", "account", fixedUnitId],
    queryFn: () => getUnitAccount(fixedUnitId, client),
    enabled: origin.kind === "asset" && fixedUnitId !== "",
  });

  const { timeZone, dateFormat } = useRegional({});
  const options = useQuery({ queryKey: ["work", "raise-options"], queryFn: () => getRaiseOptions(client) });
  const priority = options.data?.priorities.find((row) => row.id === form.priorityId) ?? null;

  const fixed: RaiseFixed = useMemo(() => {
    if (origin.kind === "account") {
      const a = account.data;
      return {
        premisesId: a?.premises_id ?? a?.service_premises_id ?? unit.data?.premises_id ?? "",
        unitIds: a?.unit_id ? [a.unit_id] : [],
        asset: null,
        unitLabel: a?.unit_label ?? null,
      };
    }
    if (origin.kind === "asset") {
      const a = asset.data;
      return {
        premisesId: unit.data?.premises_id ?? "",
        unitIds: a?.assigned_unit_id ? [a.assigned_unit_id] : [],
        asset: { id: origin.assetId, assetNo: a?.asset_no ?? "", assetTypeId: null },
        unitLabel: unit.data?.label ?? null,
      };
    }
    return { premisesId: null, unitIds: null, asset: null, unitLabel: null };
  }, [origin, account.data, asset.data, unit.data]);

  const premisesId = fixed.premisesId ?? form.premisesId;
  const unitIds = fixed.unitIds ?? form.units.map((row) => row.id);
  const assetJobs = fixed.asset !== null || form.assetTypeId !== "";

  // ── The origin panel, image 19 / image 20 ───────────────────────────────
  const service = (code: string | null | undefined) => (code ? t(`work.orders.service.${code}`) : "—");
  let originPanel: JSX.Element | undefined;
  let kicker = t("work.newOrder.kicker");
  if (origin.kind === "account") {
    const a = account.data;
    kicker = t("work.raise.kicker.account", { account: a?.account_no ?? "" });
    originPanel = (
      <RaiseFacts
        title={t("work.raise.fromAccount")}
        name="from-account"
        facts={[
          {
            name: "account",
            label: t("work.raise.fact.account"),
            value: (
              <>
                <span className="font-semibold">{a?.account_no ?? ""}</span>
                {a?.name ? ` · ${a.name}` : ""}
              </>
            ),
          },
          {
            name: "where",
            label: t("work.raise.fact.where"),
            value: [a?.premise_address ?? a?.premise, a?.unit_label].filter(Boolean).join(" · ") || "—",
          },
          {
            name: "category",
            label: t("work.raise.fact.category"),
            value:
              [a?.account_type ? t(`customers.accounts.category.${a.account_type}`) : null, a?.account_subtype_name]
                .filter(Boolean)
                .join(" · ") || "—",
          },
          { name: "status", label: t("work.raise.fact.status"), value: a?.status_name ?? "—" },
          {
            name: "services",
            label: t("work.raise.fact.services"),
            value: (a?.services ?? []).map((code) => service(code)).join(" · ") || "—",
          },
        ]}
      />
    );
  } else if (origin.kind === "asset") {
    const a = asset.data;
    const owner = assetAccount.data?.account ?? null;
    kicker = t("work.raise.kicker.asset", { asset: a?.asset_no ?? "" });
    originPanel = (
      <RaiseFacts
        title={t("work.raise.fromAsset")}
        name="from-asset"
        facts={[
          {
            name: "asset",
            label: t("work.raise.fact.asset"),
            value: (
              <>
                <span className="font-semibold">{a?.asset_no ?? ""}</span>
                {[a?.type_name, a?.read_method_name].filter(Boolean).map((part) => ` · ${part}`).join("")}
              </>
            ),
          },
          { name: "service", label: t("work.raise.fact.service"), value: service(a?.service) },
          {
            name: "where",
            label: t("work.raise.fact.where"),
            value: [unit.data?.premise_address ?? a?.assigned_address, unit.data?.label].filter(Boolean).join(" · ") || "—",
          },
          { name: "onSite", label: t("work.raise.fact.onSite"), value: a?.specs?.location_note ?? "—" },
          {
            name: "account",
            label: t("work.raise.fact.account"),
            value:
              owner === null ? (
                "—"
              ) : (
                <>
                  <span className="font-semibold">{owner.account_no ?? ""}</span>
                  {owner.name ? ` · ${owner.name}` : ""}
                </>
              ),
          },
        ]}
      />
    );
  }

  // ── The jobs one press raises (ruling 19) ───────────────────────────────
  const jobs: RaiseJobLine[] = useMemo(() => {
    if (fixed.asset !== null) {
      return [{ key: fixed.asset.id, unit: fixed.unitLabel ?? "", asset: fixed.asset.assetNo, where: asset.data?.specs?.location_note ?? null, lastRead: null }];
    }
    if (form.assetTypeId !== "") {
      return form.assets.map((row) => ({ key: row.id, unit: row.unitLabel, asset: row.assetNo, where: row.where, lastRead: row.lastRead }));
    }
    if (fixed.unitIds !== null) {
      return fixed.unitIds.map((id) => ({ key: id, unit: fixed.unitLabel ?? "", asset: null, where: null, lastRead: null }));
    }
    return form.units.map((row) => ({ key: row.id, unit: row.label, asset: null, where: null, lastRead: null }));
  }, [fixed, form.assetTypeId, form.assets, form.units, asset.data]);

  function validateJob(): boolean {
    const next: RaiseJobErrors = {};
    if (fixed.premisesId === null && form.premisesId === "") next.premises = t("work.raise.need.premises");
    else if (fixed.unitIds === null && form.units.length === 0) next.units = t("work.raise.need.units");
    if (form.typeId === "") next.type = t("work.raise.need.type");
    if (form.templateId === "") next.template = t("work.raise.need.template");
    if (fixed.asset === null && form.assetTypeId !== "") {
      const ticked = fixed.unitIds !== null
        ? fixed.unitIds.map((id) => ({ id, label: fixed.unitLabel ?? "" }))
        : form.units;
      const missing = unitsMissingAnAsset(
        ticked,
        form.assetUnitKeys.map((unitKey) => ({ unitKey })),
        form.assets,
      );
      if (form.assets.length === 0) next.assets = t("work.raise.need.assets");
      else if (missing.length > 0) next.assets = t("work.raise.chooseFor", { unit: missing[0].label });
    }
    const missingOwn = missingRequiredLabels(customRegistry.data ?? [], form.customData);
    if (missingOwn.length > 0) next.custom = t("customFields.requiredList", { fields: missingOwn.join(", ") });
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function commit(): Promise<WizardCommitOutcome> {
    // A visit DAY with *Any time* is still a day the customer is told: it
    // travels as that whole day, never as nothing (decision log, CR-168
    // round 3 RAISE (6)).
    const moments =
      form.visitDay === ""
        ? { window_start: null, window_end: null }
        : form.visitWindow === "any"
          ? { window_start: `${form.visitDay}T00:00:00`, window_end: `${form.visitDay}T23:59:00` }
          : windowMoments(form.visitDay, form.visitWindow);
    try {
      const result = await bulkRaise(
        {
          template_id: form.templateId,
          type_id: form.typeId,
          type: form.typeLabel,
          ...(fixed.asset === null && form.assetTypeId !== "" ? { asset_type_id: form.assetTypeId } : {}),
          premises_id: premisesId,
          ...(assetJobs
            ? { asset_ids: fixed.asset !== null ? [fixed.asset.id] : form.assets.map((row) => row.id) }
            : { unit_ids: unitIds }),
          ...(origin.kind === "account" ? { account_id: origin.accountId } : {}),
          priority_id: form.priorityId || null,
          due_on: form.due || null,
          ...moments,
          technician_notes: form.notes.trim() || null,
          assignee: assigneeFor(form.assignee),
          idempotency_key: idempotencyKey,
          custom_data: form.customData,
          source: origin.kind === "asset" ? ("assets" as const) : ("dispatcher" as const),
        },
        client,
      );
      setOutcome(result);
      return { ok: true };
    } catch (error) {
      setCustomErrors(isApiError(error) ? customFieldErrors(error.fieldErrors, (key, p) => t(key, p)) : {});
      return { ok: false, reason: t("work.raise.failed") };
    }
  }

  function raiseMore() {
    setForm(EMPTY_RAISE_FORM);
    setErrors({});
    setOutcome(null);
    setComplete(false);
    setIdempotencyKey(newIdempotencyKey());
    moveTo(initialWizardNav());
  }

  const assigneeName = form.assignee?.name ?? null;

  const summaryFacts: RaiseFact[] = [
    { name: "job", label: t("work.raise.fact.job"), value: form.typeLabel || "—" },
    { name: "template", label: t("work.raise.fact.template"), value: form.templateLabel || "—" },
    ...(assetJobs && fixed.asset === null
      ? [{ name: "assetType", label: t("work.raise.fact.assetType"), value: form.assetTypeLabel || "—" }]
      : []),
    {
      name: "priority",
      label: t("work.raise.fact.priority"),
      value: priority === null ? "—" : t("work.raise.priorityOption", { name: priority.name, hours: priority.sla_hours }),
    },
    { name: "due", label: t("work.raise.fact.due"), value: form.due === "" ? "—" : formatDate(form.due, timeZone, dateFormat) },
    {
      name: "visit",
      label: t("work.raise.fact.visit"),
      value:
        form.visitDay === ""
          ? "—"
          : `${formatDate(form.visitDay, timeZone, dateFormat)}, ${t(`work.edit.window.${form.visitWindow}`)}`,
    },
    { name: "assigned", label: t("work.raise.fact.assigned"), value: assigneeName ?? t("work.raise.nobodyYet") },
  ];
  const placeLabel =
    origin.kind === "work"
      ? form.premisesLabel.split(" · ")[0]
      : origin.kind === "account"
        ? (account.data?.premise_address ?? account.data?.premise ?? "")
        : (unit.data?.premise_address ?? asset.data?.assigned_address ?? "");

  return (
    <div className="flex max-w-5xl flex-col gap-3" data-screen={RAISE_SCREEN} data-raise-origin={origin.kind}>
      {/* B14 rule 3 — the stepper IS the head of a three-step flow. */}
      <Kicker>{kicker}</Kicker>
      <WizardFrame
        nav={nav}
        onNavChange={moveTo}
        complete={complete}
        steps={[
          {
            id: "job",
            label: t("work.newOrder.step1"),
            content: (
              <RaiseJobStep
                origin={origin}
                fixed={fixed}
                form={form}
                update={update}
                errors={errors}
                customErrors={customErrors}
                originPanel={originPanel}
                client={client}
              />
            ),
            validate: () => {
              const fine = validateJob();
              if (fine && form.due === "" && priority !== null) {
                update({ due: dueFromPriority(priority.sla_hours, new Date()) });
              }
              return fine;
            },
          },
          {
            id: "schedule",
            label: t("work.newOrder.step2"),
            content: (
              <RaiseScheduleStep
                form={form}
                update={update}
                slaHours={priority?.sla_hours ?? null}
                templateId={form.templateId}
                premisesId={premisesId}
                unitIds={unitIds}
                client={client}
              />
            ),
          },
          {
            id: "confirm",
            label: t("work.newOrder.step3"),
            content:
              outcome !== null && complete ? (
                <RaiseResult
                  outcome={outcome}
                  lines={jobs}
                  reasonText={(key) => (i18n.exists(key) ? t(key) : t("work.raise.refusedGeneric"))}
                  onRaiseMore={raiseMore}
                  onOpenOrders={() => navigate(tenantPath(WORK_ORDERS_ROUTE.slice(1)))}
                  orderHref={(orderNo) => tenantPath(`${WORK_ORDERS_ROUTE.slice(1)}/${orderNo}`)}
                />
              ) : (
                <RaiseConfirmStep
                  heading={t("work.raise.confirmHeading", { place: placeLabel, count: jobs.length })}
                  facts={summaryFacts}
                  jobs={jobs}
                  assetJobs={assetJobs}
                  assigneeName={assigneeName}
                />
              ),
          },
        ]}
        commitLabel={t("work.raise.commit", { count: jobs.length })}
        commitFailedTitle={t("work.raise.failedTitle")}
        onCommit={commit}
        onCommitted={() => setComplete(true)}
      />
    </div>
  );
}
