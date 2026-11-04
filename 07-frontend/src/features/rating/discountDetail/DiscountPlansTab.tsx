// ── Trace ──────────────────────────────────────────────
// Change:   CR-166-BRC10 round 3 task 6 — the discount details PLANS tab
//           (image 21): Plan · Services · Customer classes · Accounts · Since.
//           CR-166 follow-up (§18, 2026-10-03): *+ Add to a plan* and × are LIVE.
// Defect:   DEF-RAT-9291 D29 (Plans tab said the read did not exist) ·
//           DEF-478 (add / remove a plan from the discount page)
// Rules:    BR-RAT-069 (a plan OFFERS; an enrollment GRANTS) · ruling 2
//           (2026-10-03: only accounts whose plan carries it can get it, and
//           taking it off a plan stops it from the next bill) · BR-RAT-037 (a
//           reason) · NFR-3 (paged by the server) · B14 rules 6, 31, 33
// ───────────────────────────────────────────────────────
//
// ⚠ **BOTH ACTS GO THROUGH THE PLAN'S OWN WRITE (`DEF-478`).** `POST
// /discounts/{id}/plans` and `DELETE …/plans/{plan}` restate the plan's
// discounts through `update_plan`, so a published plan takes its reason and its
// version, and a removal ENDS the binding and the enrollments of accounts on
// that plan from yesterday (ruling 2) — never a second, weaker write path. A
// reason is asked for on both, and it is the reason the discount's Audit shows.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { addDiscountToPlan, getDiscountPlanPage, removeDiscountFromPlan } from "@/api/discountDetailEndpoints";
import type { DiscountPlanRow } from "@/api/discountDetailEndpoints";
import { getPlans } from "@/api/endpoints";
import { Button } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { ListPager } from "@/components/ListPager";
import { Panel } from "@/components/Panel";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import { RowAction, RowActions } from "@/components/RowActions";
import { LoadingSkeleton } from "@/components/StateFrame";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { useToast } from "@/components/Toast";
import { PAGE_SIZES } from "@/components/tableTypes";
import type { PageSize } from "@/components/tableTypes";
import { useTenantPath } from "@/routing/tenantPath";

import { planDetailRoute } from "../planDetail/planDetailModel";
import { SECTION_HEADING } from "../discountForm/discountFormShared";
import { DASH } from "./discountDetailModel";
import type { DiscountRegional, Translator } from "./discountDetailModel";

export function planServicesText(row: DiscountPlanRow, t: Translator): string {
  const codes = row.services ?? [];
  return codes.length === 0 ? DASH : codes.map((code) => t(`rating.service.${code}`, { defaultValue: code })).join(", ");
}

export function planClassesText(row: DiscountPlanRow, t: Translator): string {
  if (row.customer_classes === undefined) return DASH;
  return row.customer_classes.length === 0 ? t("rating.taxes.list.everyClass") : row.customer_classes.join(", ");
}

const PLAN_SEARCH_PER = 20;

async function submitted(run: () => Promise<void>): Promise<FormSubmitOutcome> {
  try {
    await run();
    return { ok: true };
  } catch (error) {
    if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
    return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
  }
}

/** *+ Add to a plan* — the plan is found by typing its name; the server
 *  searches (NFR-3), the screen never lists every plan. */
export function AddDiscountToPlanDialog(props: {
  discountId: string;
  client: ApiClient;
  onClose: () => void;
  onAdded: (plan: string) => void;
  t: Translator;
}) {
  const { t } = props;
  const [term, setTerm] = useState("");
  const [planId, setPlanId] = useState("");
  const [reason, setReason] = useState("");
  const query = useQuery({
    queryKey: ["plans", "search", term],
    queryFn: () => getPlans({ q: term, page: 1, per: PLAN_SEARCH_PER }, props.client),
    enabled: term.trim().length >= 1,
    retry: false,
  });
  const options = (query.data?.results ?? []).map((plan) => ({ value: plan.id, label: plan.name }));
  const planName = options.find((option) => option.value === planId)?.label ?? "";
  return (
    <FormModal
      title={t("rating.taxDetail.plans.addTitle")}
      schema={z.object({
        plan: z.string().min(1, t("rating.taxDetail.plans.planRequired")),
        reason: z.string().trim().min(1, t("rating.discountDetail.plans.reasonRequired")),
      })}
      values={{ plan: planId, reason }}
      submitLabel={t("rating.taxDetail.plans.addSubmit")}
      onSubmit={() =>
        submitted(async () => {
          await addDiscountToPlan(props.discountId, { plan: planId, reason: reason.trim() }, props.client);
          props.onAdded(planName);
        })
      }
      onClose={props.onClose}
    >
      <RemoteSearchSelectField
        id="plan"
        label={t("rating.taxDetail.plans.plan")}
        term={term}
        onTermChange={(next) => {
          setTerm(next);
          setPlanId("");
        }}
        status={{
          idle: term.trim().length < 1,
          searching: query.isFetching,
          searched: query.isSuccess,
          failed: query.isError,
        }}
        options={options}
        value={planId}
        onChange={setPlanId}
        words={{
          tooShort: t("rating.taxDetail.plans.search.tooShort"),
          searching: t("rating.taxDetail.plans.search.searching"),
          failed: t("rating.taxDetail.plans.search.failed"),
          noMatch: t("rating.taxDetail.plans.search.noMatch"),
        }}
        required
      />
      <TextField id="reason" label={t("rating.taxDetail.plans.reason")} value={reason} onChange={setReason} required />
    </FormModal>
  );
}

/** × on a row — ruling 2: it stops from the next bill, and the enrollments of
 *  accounts on that plan end with it. Danger tier (B14 rule 6). */
export function RemoveDiscountFromPlanDialog(props: {
  discountId: string;
  plan: DiscountPlanRow;
  client: ApiClient;
  onClose: () => void;
  onRemoved: () => void;
  t: Translator;
}) {
  const { t } = props;
  const [reason, setReason] = useState("");
  return (
    <FormModal
      title={t("rating.taxDetail.plans.removeTitle", { plan: props.plan.plan })}
      schema={z.object({ reason: z.string().trim().min(1, t("rating.discountDetail.plans.reasonRequired")) })}
      values={{ reason }}
      submitLabel={t("rating.taxDetail.plans.removeSubmit")}
      submitVariant="danger"
      onSubmit={() =>
        submitted(async () => {
          await removeDiscountFromPlan(props.discountId, props.plan.plan_id, { reason: reason.trim() }, props.client);
          props.onRemoved();
        })
      }
      onClose={props.onClose}
    >
      <p className="mb-4 text-base" data-discount-remove-consequence="">
        {t("rating.discountDetail.plans.removeConsequence")}
      </p>
      <TextField id="reason" label={t("rating.taxDetail.plans.reason")} value={reason} onChange={setReason} required />
    </FormModal>
  );
}

export function DiscountPlansTab(props: {
  discountId: string;
  client: ApiClient;
  readOnly: boolean;
  regional: DiscountRegional;
  t: Translator;
}) {
  const { t, regional } = props;
  const tenantPath = useTenantPath();
  const [page, setPage] = useState(1);
  const [per, setPer] = useState<PageSize>(PAGE_SIZES[0]);
  const query = useQuery({
    queryKey: ["discounts", props.discountId, "plans", page, per],
    queryFn: () => getDiscountPlanPage(props.discountId, { page, per }, props.client),
    enabled: props.discountId !== "",
    placeholderData: (previous) => previous,
  });
  const rows: readonly DiscountPlanRow[] = query.data?.rows ?? [];
  const readOnlyReason = props.readOnly ? t("rating.readOnlyReason") : null;
  const queryClient = useQueryClient();
  const toast = useToast();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<DiscountPlanRow | null>(null);
  // Counts, the Accounts tab and the Audit all move with a plan link.
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["discounts"] });
  };

  return (
    <Panel as="section" aria-labelledby="discount-detail-plans" data-discount-plans="">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 id="discount-detail-plans" className={`${SECTION_HEADING} mb-0`}>
          {t("rating.definition.tab.plans")}
        </h2>
        <Button
          variant="secondary"
          disabled={props.readOnly}
          title={readOnlyReason ?? undefined}
          onClick={() => setAdding(true)}
          data-discount-add-plan=""
        >
          {t("rating.taxDetail.plans.add")}
        </Button>
      </div>
      {query.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : query.isError ? (
        <Note>{t("rating.definition.tax.plans.failed")}</Note>
      ) : rows.length === 0 ? (
        <Note>{t("rating.discountDetail.plans.empty")}</Note>
      ) : (
        <>
          <div className="border border-divider">
            <PlainTable>
              <thead>
                <tr>
                  <th scope="col">{t("rating.definition.tax.plans.col.plan")}</th>
                  <th scope="col">{t("rating.discountForm.field.services")}</th>
                  <th scope="col">{t("rating.discountDetail.plans.classes")}</th>
                  <th scope="col" className="!text-right">
                    {t("rating.taxDetail.plans.accounts")}
                  </th>
                  <th scope="col">{t("rating.discountDetail.plans.since")}</th>
                  <th scope="col">
                    <span className="sr-only">{t("rating.taxDetail.plans.actions")}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  // B14 rule 31 — the plan's id is the key and the link
                  // target, never a cell.
                  <tr key={row.plan_id}>
                    <td>
                      <InlineLinkTo to={tenantPath(planDetailRoute(row.plan_id))} className="font-semibold">
                        {row.plan}
                      </InlineLinkTo>
                    </td>
                    <td>{planServicesText(row, t)}</td>
                    <td>{planClassesText(row, t)}</td>
                    <td className="!text-right tabular-nums">{row.accounts === null ? DASH : row.accounts}</td>
                    <td className="tabular-nums">
                      {row.available_from === null
                        ? DASH
                        : formatDate(row.available_from, regional.timeZone, regional.dateFormat)}
                    </td>
                    <td className="!text-right">
                      <RowActions>
                        <RowAction
                          label={t("rating.taxDetail.plans.remove", { plan: row.plan })}
                          icon={<span aria-hidden="true">×</span>}
                          reason={readOnlyReason}
                          danger
                          onClick={() => setRemoving(row)}
                        />
                      </RowActions>
                    </td>
                  </tr>
                ))}
              </tbody>
            </PlainTable>
          </div>
          <ListPager
            page={page}
            per={per}
            total={query.data?.total ?? 0}
            onPage={setPage}
            onPer={(next) => {
              setPer(next);
              setPage(1);
            }}
          />
        </>
      )}
      {adding && (
        <AddDiscountToPlanDialog
          discountId={props.discountId}
          client={props.client}
          onClose={() => setAdding(false)}
          onAdded={(plan) => {
            // FormModal leaves closing to its caller (DEF-RAT-9326).
            setAdding(false);
            toast(t("rating.discountDetail.done.addedToPlan", { plan }));
            refresh();
          }}
          t={t}
        />
      )}
      {removing !== null && (
        <RemoveDiscountFromPlanDialog
          discountId={props.discountId}
          plan={removing}
          client={props.client}
          onClose={() => setRemoving(null)}
          onRemoved={() => {
            const plan = removing.plan;
            setRemoving(null);
            toast(t("rating.discountDetail.done.removedFromPlan", { plan }));
            refresh();
          }}
          t={t}
        />
      )}
    </Panel>
  );
}
