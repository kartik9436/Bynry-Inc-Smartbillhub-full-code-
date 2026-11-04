// ── Trace ──────────────────────────────────────────────
// Change:   CR-167-BRC10 round 3 task 7 — the plan DETAILS page (S10, PLN-02),
//           rebuilt from images 24–37 of 05-prototype/plans-2026-10-03 (B14
//           rule 42: the images are the specification; our kit decides how it
//           is built, rule 44). Six tabs — Overview · Services · Charges ·
//           Billing · Units · Audit (ruling 2) — and ruling 13's improvements.
// Defects:  DEF-RAT-9334 · DEF-RAT-9331 · DEF-RAT-9288 · DEF-RAT-9286 ·
//           DEF-RAT-9285 (details half) · DEF-RAT-9352 (Duplicate held) ·
//           DEF-RAT-9353 (Units links)
// Rules:    README rulings 2, 8, 11, 12, 13, 15 · BR-SHL-011 (the open tab and
//           *Priced as of* are URL state) · BR-SHL-012 (A18 states) ·
//           BR-SHL-025 · BR-RAT-030 (a plan ever billed is never deleted) ·
//           B14 rules 6, 21, 31, 33, 37, 43, 44
// Tests:    src/features/rating/planDetail/planDetail.dom.test.tsx
// Impacts:  App.tsx mounts this at `plans-rates/plans/:planId` (it replaced
//           `PlanDetail.tsx`, whose eight-then-three-tab page is retired)
// ───────────────────────────────────────────────────────
//
// ⚠ **REMOVED FROM THE PAGE AS TEXT, NOT DATA** (README, *"Removed from the
// details page"*): the Revenue and Exceptions tiles, *Not recorded on a plan
// yet* (7), *How a plan works*, *Sample bill*, *Splitting by city limits…*, the
// draft-schedule note, the softer-state note and *Why units and not accounts*.
// Every FACT the old page showed has a home (CR-167 §5.4).
//
// ⚠ **NOT BUILT, BY RULING 15:** *Move units to another plan* — no selection
// column and no Move button on Units.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { archivePlan, deletePlan, getMyPermissions } from "@/api/endpoints";
import { getPlanDetailRead, publishPlanVersion } from "@/api/planDetailEndpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import type { RegionalDateFormat } from "@/components/DateCell";
import { todayInZone } from "@/components/DateCell";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { useRegional } from "@/features/metering/meteringShared";
import { RefusalNotice, apiErrorText, isPermissionDenied, refusalOf } from "@/features/tenancy/settingsShared";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { DASHBOARD_ROUTE, GuardedButton, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "../ratingShared";
import { PlanAuditTab } from "./PlanAuditTab";
import { DuplicatePlanDialog } from "./DuplicatePlanDialog";
import { PlanDetailHeader, PlanHeaderFacts } from "./PlanDetailHeader";
import { PlanDraftVersionBanner } from "./PlanDraftVersionBanner";
import { PlanMoreMenu } from "./PlanMoreMenu";
import { PlanOverviewTab } from "./PlanOverviewTab";
import { PlanPricedTab } from "./PlanPricedTab";
import { PlanUnitsTab } from "./PlanUnitsTab";
import { PlanUpcomingBanner } from "./PlanUpcomingBanner";
import { dayBefore } from "../planForm/planEditModel";
import {
  PLANS_LIST_ROUTE,
  PLAN_AS_OF_PARAM,
  PLAN_DETAIL_TABS,
  PLAN_TAB_PARAM,
  PRICED_TABS,
  classesText,
  dayShown,
  draftVersion,
  planDetailRoute,
  planDetailTabFrom,
  planEditDoor,
  planSectionEditDoor,
  planTabAddress,
  versionEndedBy,
  windowText,
} from "./planDetailModel";
import type { PlanDetailTab, Translator } from "./planDetailModel";

/** Literal keys, so G18 sees each one used. */
const TAB_KEYS: Readonly<Record<PlanDetailTab, string>> = {
  overview: "rating.planDetail.tab.overview",
  services: "rating.planDetail.tab.services",
  charges: "rating.planDetail.tab.charges",
  billing: "rating.planDetail.tab.billing",
  units: "rating.planDetail.tab.units",
  audit: "rating.planDetail.tab.audit",
};

type Dialog = "retire" | "deleteDraft" | "duplicate" | "publishVersion" | null;

export function PlanDetailPage(props: { client?: ApiClient; timeZone?: string; dateFormat?: RegionalDateFormat }) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params) as string;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const client = props.client ?? api;
  const regional = useRegional(props);
  const toast = useToast();
  const queryClient = useQueryClient();
  const planId = params.planId ?? "";
  const active = planDetailTabFrom(searchParams.get(PLAN_TAB_PARAM));
  const today = todayInZone(regional.timeZone);
  const asOfParam = searchParams.get(PLAN_AS_OF_PARAM) ?? "";
  const asOf = asOfParam === "" ? today : asOfParam;
  const [dialog, setDialog] = useState<Dialog>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  // The page as of TODAY — the header, the tiles, the banner, Units and Audit.
  const detailQuery = useQuery({
    queryKey: ["plans", planId, "detail", null],
    queryFn: () => getPlanDetailRead(planId, null, client),
    enabled: planId !== "",
    retry: false,
  });
  // *Priced as of* another date reads the page again on that date (image 28).
  const pricedQuery = useQuery({
    queryKey: ["plans", planId, "detail", asOfParam],
    queryFn: () => getPlanDetailRead(planId, asOfParam, client),
    enabled: planId !== "" && asOfParam !== "" && PRICED_TABS.includes(active),
    retry: false,
  });

  function refresh(): void {
    void queryClient.invalidateQueries({ queryKey: ["plans"] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.plan(planId) });
  }
  const retire = useMutation({
    mutationFn: () => archivePlan(planId, client),
    onSuccess: (saved) => {
      setDialog(null);
      setRefusal(null);
      toast(t("rating.planDetail.toast.retired", { name: saved.name }));
      refresh();
    },
    onError: (error: unknown) => {
      setDialog(null);
      setRefusal(refusalOf(error, translate));
    },
  });
  // CR-167 §5.5 L13 — a DRAFT's delete, in More ▾ (it was a header button
  // while the drawn menu was unbuilt). The server refuses a plan ever billed.
  const removeDraft = useMutation({
    mutationFn: () => deletePlan(planId, client),
    onSuccess: () => {
      setDialog(null);
      setRefusal(null);
      toast(t("rating.plans.toast.delete", { name: detailQuery.data?.name ?? "" }));
      refresh();
      navigate(tenantPath(PLANS_LIST_ROUTE));
    },
    onError: (error: unknown) => {
      setDialog(null);
      setRefusal(refusalOf(error, translate));
    },
  });

  // `DEF-RAT-9364` — publish the version *Save new version* left unpublished.
  const publishVersion = useMutation({
    mutationFn: (version: number) => publishPlanVersion(planId, version, client),
    onSuccess: (_saved, version) => {
      setDialog(null);
      setRefusal(null);
      toast(t("rating.planDetail.toast.versionPublished", { n: version }));
      refresh();
    },
    onError: (error: unknown) => {
      setDialog(null);
      setRefusal(refusalOf(error, translate));
    },
  });

  if (permissionsQuery.isPending) return <LoadingSkeleton variant="card" />;
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access)) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
  }
  const readOnly = ratingIsReadOnly(access);
  if (detailQuery.isPending) return <LoadingSkeleton variant="card" />;
  const read = detailQuery.data;
  if (read === undefined) {
    if (isPermissionDenied(detailQuery.error)) {
      return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
    }
    return (
      <FailedWithRetry
        title={t("rating.planDetail.failedTitle")}
        reason={apiErrorText(detailQuery.error, translate)}
        onRetry={() => void detailQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(PLANS_LIST_ROUTE))}
      />
    );
  }

  const tabTo = (tab: PlanDetailTab, date?: string | null) => tenantPath(planTabAddress(planId, tab, date));
  function selectTab(id: PlanDetailTab): void {
    const next = new URLSearchParams(searchParams);
    next.set(PLAN_TAB_PARAM, id);
    setSearchParams(next, { replace: true });
  }
  function setAsOf(value: string): void {
    const next = new URLSearchParams(searchParams);
    if (value === "" || value === today) next.delete(PLAN_AS_OF_PARAM);
    else next.set(PLAN_AS_OF_PARAM, value);
    setSearchParams(next, { replace: true });
  }

  const tabs = PLAN_DETAIL_TABS.map((id) => ({
    id,
    label: t(TAB_KEYS[id]),
    count: id === "services" ? read.sections.services.length : id === "units" ? (read.units ?? undefined) : undefined,
  }));

  const window = read.plan_version;
  const place = [
    read.sections.details.customer_classes.length === 0 ? "" : classesText(read.sections, translate),
    window === null ? "" : windowText(window.effective_from, window.effective_to, regional, t("rating.taxes.list.noEnd")),
  ]
    .filter((part) => part !== "" && part !== "—")
    .join(" · ");

  const actions = [
    <GuardedButton
      key="edit"
      readOnly={readOnly}
      readOnlyReason={t("rating.readOnlyReason")}
      variant="primary"
      onClick={() => navigate(tenantPath(planEditDoor(planId, "info")))}
    >
      {t("rating.planDetail.action.edit")}
    </GuardedButton>,
    <PlanMoreMenu
      key="more"
      status={read.status}
      readOnly={readOnly}
      onDeleteDraft={() => {
        setRefusal(null);
        setDialog("deleteDraft");
      }}
      onDuplicate={() => {
        setRefusal(null);
        setDialog("duplicate");
      }}
      onRetire={() => {
        setRefusal(null);
        setDialog("retire");
      }}
      t={translate}
    />,
  ];

  const priced = PRICED_TABS.includes(active);
  const pricedRead = asOfParam === "" ? read : pricedQuery.data;
  // The banner answers for the date being read: on a priced tab with a later
  // date chosen, a version that has started by then is no longer *upcoming*.
  // `DEF-RAT-9515` — ONE LINE PER UPCOMING ITEM, earliest first (the server's
  // order). Showing only the first hid a schedule's new rates behind the
  // plan's own later start (a plan from 11/01/2026 never named its water v2
  // from 01/01/2027) — this replaces CR-167 §13 judgment 3.
  const upcoming = (priced ? pricedRead?.upcoming : read.upcoming) ?? [];
  // `DEF-RAT-9506` — only a PUBLISHED plan has a saved NEW version; a draft
  // plan's own v1 is published by Edit's *Publish plan*.
  const draft = read.status === "published" ? draftVersion(read.versions) : null;
  const ended = draft === null ? null : versionEndedBy(read.versions, draft);

  return (
    <div className="pt-6 px-4 pb-8" data-plan-detail="">
      <PlanDetailHeader
        name={read.name}
        code={read.code}
        facts={<PlanHeaderFacts status={read.status} version={window?.version ?? null} place={place} />}
        backTo={tenantPath(PLANS_LIST_ROUTE)}
        actions={actions}
        tabs={tabs}
        activeTab={active}
        onTab={selectTab}
        t={translate}
      />
      <div className="flex flex-col gap-4">
        <RefusalNotice refusal={refusal} />
        {draft !== null && (
          <PlanDraftVersionBanner
            draft={draft}
            readOnly={readOnly}
            onPublish={() => {
              setRefusal(null);
              setDialog("publishVersion");
            }}
            regional={regional}
            t={translate}
          />
        )}
        {upcoming.map((item) => (
          <PlanUpcomingBanner
            key={`${item.kind}-${item.code}-${item.name}-${item.version}`}
            planId={planId}
            item={item}
            sections={read.sections}
            seeIt={tabTo("services", item.effective_from)}
            client={client}
            regional={regional}
            t={translate}
          />
        ))}
        {active === "overview" && <PlanOverviewTab read={read} tabTo={(tab) => tabTo(tab)} regional={regional} t={translate} />}
        {priced &&
          (pricedRead === undefined ? (
            pricedQuery.isError ? (
              <FailedWithRetry
                title={t("rating.planDetail.failedTitle")}
                reason={apiErrorText(pricedQuery.error, translate)}
                onRetry={() => void pricedQuery.refetch()}
                onDownloadReport={() => undefined}
                onCancel={() => setAsOf("")}
              />
            ) : (
              <LoadingSkeleton variant="card" />
            )
          ) : (
            <PlanPricedTab
              tab={active as "services" | "charges" | "billing"}
              sections={pricedRead.sections}
              asOf={asOf}
              today={today}
              onAsOf={setAsOf}
              onEdit={
                readOnly || read.status === "archived"
                  ? null
                  : (section) => navigate(tenantPath(planSectionEditDoor(planId, read.status, section)))
              }
              regional={regional}
              t={translate}
            />
          ))}
        {active === "units" && <PlanUnitsTab planId={planId} client={client} regional={regional} t={translate} />}
        {active === "audit" && <PlanAuditTab planId={planId} client={client} regional={regional} t={translate} />}
      </div>

      {dialog === "retire" && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("rating.planDetail.confirm.retire.title", { name: read.name })}
          consequence={t("rating.planDetail.retire.consequence")}
          confirmLabel={t("rating.planDetail.confirm.retire.verb")}
          working={retire.isPending}
          onConfirm={() => retire.mutate()}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog === "duplicate" && (
        <DuplicatePlanDialog
          planId={planId}
          planName={read.name}
          client={client}
          onClose={() => setDialog(null)}
          onCopied={(copy) => {
            setDialog(null);
            toast(t("rating.planDetail.toast.duplicated", { name: copy.name }));
            refresh();
            navigate(tenantPath(planDetailRoute(copy.id)));
          }}
          t={translate}
        />
      )}
      {dialog === "publishVersion" && draft !== null && (
        <ConfirmDialog
          title={t("rating.planDetail.confirm.publishVersion.title", { n: draft.version, name: read.name })}
          consequence={
            ended === null || draft.effective_from === null
              ? t("rating.planDetail.confirm.publishVersion.starts", { date: dayShown(draft.effective_from, regional) })
              : t("rating.planDetail.confirm.publishVersion.ends", {
                  n: ended.version,
                  date: dayShown(dayBefore(draft.effective_from), regional),
                })
          }
          confirmLabel={t("rating.planDetail.draftVersion.publish", { n: draft.version })}
          working={publishVersion.isPending}
          onConfirm={() => publishVersion.mutate(draft.version)}
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog === "deleteDraft" && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("rating.plans.confirm.delete.title", { name: read.name })}
          consequence={t("rating.planDetail.confirm.deleteDraft.body")}
          confirmLabel={t("rating.planDetail.action.deleteDraft")}
          working={removeDraft.isPending}
          onConfirm={() => removeDraft.mutate()}
          onCancel={() => setDialog(null)}
        />
      )}
    </div>
  );
}

export default PlanDetailPage;
