// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the discount DETAILS page (S14,
//           CHG-01.discount), rebuilt from images 19–26 of
//           05-prototype/discounts-2026-10-03 (B14 rule 42: the images are the
//           specification; our kit decides how it is built, rule 44).
// Defect:   DEF-RAT-9291 (D19–D34) · DEF-RAT-9310 (Duplicate, live since the
//           CR-166 follow-up of 2026-10-03)
// Rules:    PO lifecycle rulings 2026-10-03 (1)–(4) · README points 6, 8 ·
//           BR-SHL-011 (the open tab is URL state) · BR-SHL-012 (A18 states) ·
//           BR-SHL-025 · B14 rules 21, 31, 33, 37, 43, 44
// Tests:    src/features/rating/discountDetail/discountDetail.dom.test.tsx
// Impacts:  src/features/rating/DefinitionDetailPage.tsx (mounts this for the
//           discount kind, as it mounts `TaxDetailPage` for the tax kind)
// ───────────────────────────────────────────────────────
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  approveDiscount,
  getDiscountDetail,
  getDiscountVersionLines,
  submitDiscount,
} from "@/api/discountDetailEndpoints";
import { discardDiscountVersion, getMyPermissions } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import type { RegionalDateFormat } from "@/components/DateCell";
import { formatDate } from "@/components/DateCell";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { RefusalStrip } from "@/components/Surfaces";
import { useToast } from "@/components/Toast";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { DEFINITION_ROUTES, definitionPath } from "../definitionDetail";
import { DASHBOARD_ROUTE, GuardedButton, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "../ratingShared";
import { DiscountAccountsTab } from "./DiscountAccountsTab";
import { DiscountAuditTab } from "./DiscountAuditTab";
import { DiscountDetailHeader } from "./DiscountDetailHeader";
import { RetireDiscountDialog, SendBackDialog } from "./DiscountLifecycleDialogs";
import { DiscountMoreMenu } from "./DiscountMoreMenu";
import { DiscountOverviewTab, discountVersionsQueryKey } from "./DiscountOverviewTab";
import { DiscountPlansTab } from "./DiscountPlansTab";
import { DuplicateDiscountDialog } from "./DuplicateDiscountDialog";
import {
  DISCOUNT_DETAIL_TABS,
  discountDetailTabFrom,
  discountEditDoor,
  draftVersion,
  headerActs,
} from "./discountDetailModel";
import type { DiscountDetailTab, HeaderAct, Translator } from "./discountDetailModel";

/** Literal keys, so G18 sees each one used. */
const TAB_KEYS: Readonly<Record<DiscountDetailTab, string>> = {
  overview: "rating.definition.tab.overview",
  accounts: "rating.discountDetail.tab.accounts",
  plans: "rating.definition.tab.plans",
  audit: "rating.definition.tab.audit",
};

const ACT_KEYS: Readonly<Record<HeaderAct, string>> = {
  edit: "rating.definition.action.edit",
  submit: "rating.discountDetail.act.submit",
  approve: "rating.discountDetail.act.approve",
  sendBack: "rating.discountDetail.act.sendBack",
};

/** The URL param the open tab lives in — BR-SHL-011, so a tab is linkable. */
export const DISCOUNT_TAB_PARAM = "tab";

type Dialog = "approve" | "sendBack" | "retire" | "deleteDraft" | "duplicate" | null;

export function DiscountDetailPage(props: { client?: ApiClient; timeZone?: string; dateFormat?: RegionalDateFormat }) {
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
  const discountId = params.definitionId ?? "";
  const active = discountDetailTabFrom(searchParams.get(DISCOUNT_TAB_PARAM));
  const [dialog, setDialog] = useState<Dialog>(null);
  const [working, setWorking] = useState(false);
  const [refusal, setRefusal] = useState<string | null>(null);

  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  const discountQuery = useQuery({
    queryKey: queryKeys.discount(discountId),
    queryFn: () => getDiscountDetail(discountId, client),
    enabled: discountId !== "",
  });
  const versionsQuery = useQuery({
    queryKey: discountVersionsQueryKey(discountId),
    queryFn: () => getDiscountVersionLines(discountId, client),
    enabled: discountId !== "",
    staleTime: REFERENCE_STALE_MS,
  });

  const listRoute = tenantPath(DEFINITION_ROUTES.discount.listRoute);
  if (permissionsQuery.isPending) return <LoadingSkeleton variant="card" />;
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access)) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
  }
  const readOnly = ratingIsReadOnly(access);
  if (discountQuery.isPending) return <LoadingSkeleton variant="card" />;
  const row = discountQuery.data;
  if (row === undefined) {
    if (isPermissionDenied(discountQuery.error)) {
      return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
    }
    return (
      <FailedWithRetry
        title={t("rating.definition.failedTitle")}
        reason={apiErrorText(discountQuery.error, translate)}
        onRetry={() => void discountQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(listRoute)}
      />
    );
  }
  const draft = draftVersion(versionsQuery.data ?? []);

  function tabAddress(id: DiscountDetailTab): string {
    return `${tenantPath(definitionPath("discount", discountId))}?${DISCOUNT_TAB_PARAM}=${id}`;
  }
  function selectTab(id: string): void {
    const next = new URLSearchParams(searchParams);
    next.set(DISCOUNT_TAB_PARAM, id);
    setSearchParams(next, { replace: true });
  }
  function refresh(): void {
    void queryClient.invalidateQueries({ queryKey: ["discounts"] });
    void queryClient.invalidateQueries({ queryKey: queryKeys.discount(discountId) });
  }
  async function act(run: () => Promise<unknown>, done: string): Promise<void> {
    setWorking(true);
    setRefusal(null);
    try {
      await run();
      toast(done);
      setDialog(null);
      refresh();
    } catch (error) {
      setDialog(null);
      setRefusal(isApiError(error) ? apiErrorText(error, translate) : t("api.error.unexpected"));
    } finally {
      setWorking(false);
    }
  }

  const tabs = DISCOUNT_DETAIL_TABS.map((id) => ({
    id,
    label: t(TAB_KEYS[id]),
    count:
      id === "accounts"
        ? (row.receiving ?? row.enrolled)
        : id === "plans"
          ? row.plans
          : undefined,
  }));

  const acts = headerActs(row.status, row.type);
  const onAct: Readonly<Record<HeaderAct, () => void>> = {
    edit: () => navigate(tenantPath(discountEditDoor(discountId, "info"))),
    submit: () => void act(() => submitDiscount(discountId, client), t("rating.discountDetail.done.submitted", { name: row.name })),
    approve: () => setDialog("approve"),
    sendBack: () => setDialog("sendBack"),
  };
  const actions = [
    ...acts.map((id, index) => (
      <GuardedButton
        key={id}
        readOnly={readOnly}
        readOnlyReason={t("rating.readOnlyReason")}
        variant={index === acts.length - 1 ? "primary" : "secondary"}
        onClick={onAct[id]}
      >
        {t(ACT_KEYS[id])}
      </GuardedButton>
    )),
    <DiscountMoreMenu
      key="more"
      status={row.status}
      readOnly={readOnly}
      hasDraft={draft !== null}
      onDuplicate={() => setDialog("duplicate")}
      onDeleteDraft={() => setDialog("deleteDraft")}
      onRetire={() => setDialog("retire")}
      t={translate}
    />,
  ];

  const startsOn =
    row.effective_from === null ? "—" : formatDate(row.effective_from, regional.timeZone, regional.dateFormat);

  return (
    <div data-discount-detail="">
      <DiscountDetailHeader
        row={row}
        regional={regional}
        backTo={listRoute}
        actions={actions}
        tabs={tabs}
        activeTab={active}
        onTab={selectTab}
        t={translate}
      />
      {refusal !== null && <RefusalStrip className="mb-4">{refusal}</RefusalStrip>}
      {active === "overview" && (
        <DiscountOverviewTab row={row} client={client} regional={regional} auditTo={tabAddress("audit")} t={translate} />
      )}
      {active === "accounts" && (
        <DiscountAccountsTab
          discountId={discountId}
          client={client}
          readOnly={readOnly}
          // DEF-RAT-9833 (PO D2 (b)): Autopay and Paperless are added by hand
          // again; only an Automatic discount no person may add hides Enroll.
          handEnrolmentRefused={row.hand_enrolment_refused === true}
          regional={regional}
          t={translate}
        />
      )}
      {active === "plans" && (
        <DiscountPlansTab discountId={discountId} client={client} readOnly={readOnly} regional={regional} t={translate} />
      )}
      {active === "audit" && <DiscountAuditTab discountId={discountId} client={client} regional={regional} t={translate} />}

      {dialog === "approve" && (
        <ConfirmDialog
          confirmVariant="primary"
          title={t("rating.discountDetail.approve.title", { name: row.name })}
          consequence={t("rating.discountDetail.approve.consequence", { date: startsOn })}
          confirmLabel={t("rating.discountDetail.act.approve")}
          working={working}
          onConfirm={() =>
            void act(() => approveDiscount(discountId, client), t("rating.discountDetail.done.approved", { name: row.name }))
          }
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog === "deleteDraft" && draft !== null && (
        <ConfirmDialog
          confirmVariant="danger"
          title={t("rating.discountDetail.deleteDraft.title", { n: draft.version_no })}
          consequence={t("rating.definition.discount.versions.discardBody")}
          confirmLabel={t("rating.discountDetail.more.deleteDraft")}
          working={working}
          onConfirm={() =>
            void act(
              () => discardDiscountVersion(discountId, draft.id, client),
              t("rating.discountDetail.done.draftDeleted"),
            )
          }
          onCancel={() => setDialog(null)}
        />
      )}
      {dialog === "duplicate" && (
        <DuplicateDiscountDialog
          discountId={discountId}
          name={row.name}
          client={client}
          onClose={() => setDialog(null)}
          onDone={(copy) => {
            setDialog(null);
            toast(t("rating.discountDetail.done.duplicated", { name: copy.name }));
            void queryClient.invalidateQueries({ queryKey: ["discounts"] });
            navigate(tenantPath(definitionPath("discount", copy.id)));
          }}
          t={translate}
        />
      )}
      {dialog === "sendBack" && (
        <SendBackDialog
          discountId={discountId}
          name={row.name}
          client={client}
          onClose={() => setDialog(null)}
          onDone={() => {
            // FormModal leaves closing to its caller (DEF-RAT-9340, as DEF-RAT-9326)
            setDialog(null);
            toast(t("rating.discountDetail.done.sentBack", { name: row.name }));
            refresh();
          }}
          t={translate}
        />
      )}
      {dialog === "retire" && (
        <RetireDiscountDialog
          discountId={discountId}
          name={row.name}
          client={client}
          regional={regional}
          onClose={() => setDialog(null)}
          onDone={() => {
            setDialog(null);
            toast(t("rating.taxDetail.retire.done", { name: row.name }));
            refresh();
          }}
          t={translate}
        />
      )}
    </div>
  );
}
