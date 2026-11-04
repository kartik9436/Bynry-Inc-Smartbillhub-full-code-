// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — the tax DETAILS page (S13 detail,
//           CHG-01.tax), rebuilt from images 18–23 of
//           05-prototype/taxes-fees-2026-10-03 (B14 rule 42: the images are the
//           specification; our kit decides how it is built, rule 44).
// Defect:   DEF-RAT-9272 (P29–P43)
// Rules:    README points 3, 5, 7, 8 · PO rounds 6 and 7 (2026-10-03) ·
//           BR-SHL-011 (the open tab is URL state) · BR-SHL-012 (A18 states) ·
//           BR-SHL-025 · B14 rules 21, 31, 33, 37, 43, 44
// Tests:    src/features/rating/taxDetail/taxDetail.dom.test.tsx
// Impacts:  src/features/rating/DefinitionDetailPage.tsx (mounts this for the
//           tax kind; the charge and discount kinds are unchanged)
// ───────────────────────────────────────────────────────
//
// ⚠ **FILING IS READ HERE, NOT ENTERED (README point 3, P37).** Until round 2
// the wizard did not ask for filing and this page carried a 13-box form with a
// *Save filing details* button — the fourth button of P35. The New form takes
// filing at creation (step 3) and changing it is the edit form's *Name and
// filing* (`?change=info`), so this page only reads it back.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getMyPermissions, getTax } from "@/api/endpoints";
import type { TaxDetailRow } from "@/api/taxDetailEndpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import { useRegional } from "@/features/metering/meteringShared";
import { useTenantPath } from "@/routing/tenantPath";

import { DEFINITION_ROUTES, definitionPath } from "../definitionDetail";
import { DASHBOARD_ROUTE, GuardedButton, ratingAccess, ratingIsDenied, ratingIsReadOnly } from "../ratingShared";
import { RetireTaxDialog } from "./RetireTaxDialog";
import { TaxAuditTab } from "./TaxAuditTab";
import { TaxDetailHeader } from "./TaxDetailHeader";
import { taxDuplicatePath, taxFinishDraftPath } from "../taxForm/taxEditModel";
import { TaxMoreMenu } from "./TaxMoreMenu";
import { TaxOverviewTab } from "./TaxOverviewTab";
import { TaxPlansTab } from "./TaxPlansTab";
import { TAX_DETAIL_TABS, taxDetailTabFrom, taxEditDoor } from "./taxDetailModel";
import type { TaxDetailTab, Translator } from "./taxDetailModel";

/** Literal keys, so G18 sees each one used. The tab words are the shell's. */
const TAB_KEYS: Readonly<Record<TaxDetailTab, string>> = {
  overview: "rating.definition.tab.overview",
  plans: "rating.definition.tab.plans",
  audit: "rating.definition.tab.audit",
};

/** The URL param the open tab lives in — BR-SHL-011, so a tab is linkable. */
export const TAX_TAB_PARAM = "tab";

export function TaxDetailPage(props: { client?: ApiClient; timeZone?: string; dateFormat?: RegionalDateFormat }) {
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
  const taxId = params.definitionId ?? "";
  const active = taxDetailTabFrom(searchParams.get(TAX_TAB_PARAM));
  const [retiring, setRetiring] = useState(false);

  const permissionsQuery = useQuery({
    queryKey: queryKeys.myPermissions,
    queryFn: async () => (await getMyPermissions(client)).data,
    staleTime: REFERENCE_STALE_MS,
  });
  const taxQuery = useQuery({
    queryKey: queryKeys.tax(taxId),
    queryFn: () => getTax(taxId, client) as Promise<TaxDetailRow>,
    enabled: taxId !== "",
  });

  const listRoute = tenantPath(DEFINITION_ROUTES.tax.listRoute);
  if (permissionsQuery.isPending) return <LoadingSkeleton variant="card" />;
  const access = ratingAccess(permissionsQuery.data);
  if (ratingIsDenied(access)) {
    return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
  }
  const readOnly = ratingIsReadOnly(access);
  if (taxQuery.isPending) return <LoadingSkeleton variant="card" />;
  const row = taxQuery.data;
  if (row === undefined) {
    if (isPermissionDenied(taxQuery.error)) {
      return <PermissionDenied helper={t("rating.denied")} onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))} />;
    }
    return (
      <FailedWithRetry
        title={t("rating.definition.failedTitle")}
        reason={apiErrorText(taxQuery.error, translate)}
        onRetry={() => void taxQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(listRoute)}
      />
    );
  }

  function tabAddress(id: TaxDetailTab): string {
    return `${tenantPath(definitionPath("tax", taxId))}?${TAX_TAB_PARAM}=${id}`;
  }
  function selectTab(id: string): void {
    const next = new URLSearchParams(searchParams);
    next.set(TAX_TAB_PARAM, id);
    setSearchParams(next, { replace: true });
  }

  const tabs = TAX_DETAIL_TABS.map((id) => ({
    id,
    label: t(TAB_KEYS[id]),
    count: id === "plans" ? row.used_by_plans : undefined,
  }));

  const actions = [
    <GuardedButton
      key="edit"
      readOnly={readOnly}
      readOnlyReason={t("rating.readOnlyReason")}
      variant="primary"
      onClick={() =>
        // DEF-RAT-9305 — a draft is still being created, so its Edit is the
        // New form filled from it; a live tax's Edit is the edit door.
        navigate(tenantPath(row.status === "draft" ? taxFinishDraftPath(taxId) : taxEditDoor(taxId, "info")))
      }
    >
      {t("rating.definition.action.edit")}
    </GuardedButton>,
    <TaxMoreMenu
      key="more"
      status={row.status}
      readOnly={readOnly}
      onDuplicate={() => navigate(tenantPath(taxDuplicatePath(taxId)))}
      onRetire={() => setRetiring(true)}
      t={translate}
    />,
  ];

  return (
    <div data-tax-detail="">
      <TaxDetailHeader
        row={row}
        regional={regional}
        backTo={listRoute}
        actions={actions}
        tabs={tabs}
        activeTab={active}
        onTab={selectTab}
        t={translate}
      />
      {active === "overview" && (
        <TaxOverviewTab
          row={row}
          client={client}
          regional={regional}
          fixTo={tenantPath(taxEditDoor(taxId, "correct"))}
          auditTo={tabAddress("audit")}
          t={translate}
        />
      )}
      {active === "plans" && <TaxPlansTab taxId={taxId} client={client} readOnly={readOnly} t={translate} />}
      {active === "audit" && <TaxAuditTab taxId={taxId} client={client} regional={regional} t={translate} />}
      {retiring && (
        <RetireTaxDialog
          taxId={taxId}
          taxName={row.name}
          client={client}
          regional={regional}
          onClose={() => setRetiring(false)}
          onRetired={() => {
            toast(t("rating.taxDetail.retire.done", { name: row.name }));
            void queryClient.invalidateQueries({ queryKey: ["taxes"] });
          }}
          t={translate}
        />
      )}
    </div>
  );
}
