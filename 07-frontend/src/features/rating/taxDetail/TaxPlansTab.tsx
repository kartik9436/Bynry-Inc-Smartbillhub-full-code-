// ── Trace ──────────────────────────────────────────────
// Change:   CR-165-BRC10 round 3 task 6 — the tax details PLANS tab (image 19).
// Defect:   DEF-RAT-9272 P38 (Plans tab — counted units where the drawing
//           says accounts)
// Rules:    BR-RAT-113 (a plan carries a tax through its bound AUTHORITY or an
//           explicit ATTACHMENT; a mandated tax cannot be detached) ·
//           BR-RAT-037 (a published plan needs a reason for a change) ·
//           CR-165 §7 item 5 (accounts beside units) · B14 rule 31 · rule 37
// ───────────────────────────────────────────────────────
//
// ⚠ **ACCOUNTS, AND UNITS BESIDE THEM — §7 item 5, decided rather than asked
// (law 13).** The drawing's column is ACCOUNTS; blueprint p35 ruled UNITS and
// `GET /taxes/{id}/plans` has served units since CR-087. Task 3 serves both
// (decision log 2026-10-03). They differ only by vacant units: a vacant unit is
// on the plan and has no open account. This tab shows Accounts, as drawn, and
// keeps Units beside it, because a plan whose units are all vacant would
// otherwise read *0* and look like a plan nobody is on.
//
// ⚠ **NFR-3 — ONE ROW PER PLAN.** This list is bounded by the plans a utility
// authors by hand; it never grows a row per account (task 3's docstring on
// `tax_plans` says the same). The drawn table has no pager and none is drawn.
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { z } from "zod";

import { formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPlans } from "@/api/endpoints";
import { attachTaxToPlan, detachTaxFromPlan, getTaxPlanRows } from "@/api/taxDetailEndpoints";
import type { TaxPlanRow } from "@/api/taxDetailEndpoints";
import { Button } from "@/components/Button";
import { FormModal, TextField } from "@/components/FormModal";
import type { FormSubmitOutcome } from "@/components/FormModal";
import { Panel } from "@/components/Panel";
import { RemoteSearchSelectField } from "@/components/RemoteSearchSelectField";
import { RowAction, RowActions } from "@/components/RowActions";
import { LoadingSkeleton } from "@/components/StateFrame";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { Note } from "@/components/TextBits";
import { useTenantPath } from "@/routing/tenantPath";

import { planDetailRoute } from "../planDetail/planDetailModel";
import { SECTION_HEADING } from "../taxForm/taxFormShared";
import { DASH } from "./taxDetailModel";
import type { Translator } from "./taxDetailModel";

export function taxPlansQueryKey(taxId: string) {
  return ["taxes", taxId, "plans"] as const;
}

/** The footer's sums. A dash where the server could not count accounts. */
export function planTotals(rows: readonly TaxPlanRow[]): { accounts: number | null; units: number } {
  let accounts: number | null = 0;
  let units = 0;
  for (const row of rows) {
    units += row.units;
    accounts = accounts === null || row.accounts === null || row.accounts === undefined ? null : accounts + row.accounts;
  }
  return { accounts, units };
}

const PLAN_SEARCH_PER = 20;

/** HOW the plan gets this tax (BR-RAT-113) — literal keys, so G18 sees both. */
const REACH_KEYS: Readonly<Record<TaxPlanRow["reached_by"], string>> = {
  jurisdiction: "rating.definition.tax.plans.reach.jurisdiction",
  attached: "rating.definition.tax.plans.reach.attached",
};

/**
 * *+ Add to a plan* — attach this tax to one plan (BR-RAT-113, PLN-03 step 5's
 * own write, `POST /plans/{id}/taxes`). The plan is found by typing its name;
 * the server searches (NFR-3), the screen never lists every plan.
 */
export function AddToPlanDialog(props: {
  taxId: string;
  client: ApiClient;
  onClose: () => void;
  onAdded: () => void;
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

  async function submit(): Promise<FormSubmitOutcome> {
    try {
      const body: { tax: string; reason?: string } = { tax: props.taxId };
      if (reason.trim() !== "") body.reason = reason.trim();
      await attachTaxToPlan(planId, body, props.client);
      props.onAdded();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }

  return (
    <FormModal
      title={t("rating.taxDetail.plans.addTitle")}
      schema={z.object({ plan: z.string().min(1, t("rating.taxDetail.plans.planRequired")) })}
      values={{ plan: planId }}
      submitLabel={t("rating.taxDetail.plans.addSubmit")}
      onSubmit={submit}
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
      <TextField
        id="reason"
        label={t("rating.taxDetail.plans.reason")}
        help={t("rating.taxDetail.plans.reasonHelp")}
        value={reason}
        onChange={setReason}
      />
    </FormModal>
  );
}

/** × on an ATTACHED row — remove this one attachment. */
export function RemoveFromPlanDialog(props: {
  taxId: string;
  plan: TaxPlanRow;
  client: ApiClient;
  onClose: () => void;
  onRemoved: () => void;
  t: Translator;
}) {
  const { t } = props;
  const [reason, setReason] = useState("");
  async function submit(): Promise<FormSubmitOutcome> {
    try {
      await detachTaxFromPlan(props.plan.id, props.taxId, reason.trim() === "" ? {} : { reason: reason.trim() }, props.client);
      props.onRemoved();
      return { ok: true };
    } catch (error) {
      if (isApiError(error)) return { ok: false, error: formErrorEnvelope(error) };
      return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
    }
  }
  return (
    <FormModal
      title={t("rating.taxDetail.plans.removeTitle", { plan: props.plan.name })}
      schema={z.object({})}
      values={{}}
      submitLabel={t("rating.taxDetail.plans.removeSubmit")}
      submitVariant="danger"
      onSubmit={submit}
      onClose={props.onClose}
    >
      <TextField
        id="reason"
        label={t("rating.taxDetail.plans.reason")}
        help={t("rating.taxDetail.plans.reasonHelp")}
        value={reason}
        onChange={setReason}
      />
    </FormModal>
  );
}

export function TaxPlansTab(props: { taxId: string; client: ApiClient; readOnly: boolean; t: Translator }) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const [adding, setAdding] = useState(false);
  const [removing, setRemoving] = useState<TaxPlanRow | null>(null);
  const query = useQuery({
    queryKey: taxPlansQueryKey(props.taxId),
    queryFn: () => getTaxPlanRows(props.taxId, props.client),
    enabled: props.taxId !== "",
  });
  const rows: readonly TaxPlanRow[] = query.data ?? [];
  const totals = planTotals(rows);
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["taxes"] });
  };

  return (
    <Panel as="section" aria-labelledby="tax-detail-plans" data-tax-plans="">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 id="tax-detail-plans" className={`${SECTION_HEADING} mb-0`}>
          {t("rating.taxDetail.plans.title")}
        </h2>
        <Button
          variant="secondary"
          disabled={props.readOnly}
          title={props.readOnly ? t("rating.readOnlyReason") : undefined}
          onClick={() => setAdding(true)}
          data-tax-add-plan=""
        >
          {t("rating.taxDetail.plans.add")}
        </Button>
      </div>
      {query.isPending ? (
        <LoadingSkeleton variant="table" />
      ) : query.isError ? (
        <Note>{t("rating.definition.tax.plans.failed")}</Note>
      ) : rows.length === 0 ? (
        <Note>{t("rating.definition.tax.plans.empty")}</Note>
      ) : (
        <div className="border border-divider">
          <PlainTable>
            <thead>
              <tr>
                <th scope="col">{t("rating.definition.tax.plans.col.plan")}</th>
                <th scope="col">{t("rating.definition.tax.plans.col.reachedBy")}</th>
                <th scope="col" className="!text-right">
                  {t("rating.taxDetail.plans.accounts")}
                </th>
                <th scope="col" className="!text-right">
                  {t("rating.definition.tax.plans.col.units")}
                </th>
                <th scope="col">
                  <span className="sr-only">{t("rating.taxDetail.plans.actions")}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                // B14 rule 31 — the plan's id is the key and the link target,
                // never a cell.
                <tr key={row.id} data-plan-reach={row.reached_by}>
                  <td>
                    <InlineLinkTo to={tenantPath(planDetailRoute(row.id))} className="font-semibold">
                      {row.name}
                    </InlineLinkTo>
                  </td>
                  <td>{t(REACH_KEYS[row.reached_by])}</td>
                  <td className="!text-right tabular-nums">
                    {row.accounts === null || row.accounts === undefined ? DASH : row.accounts}
                  </td>
                  <td className="!text-right tabular-nums">{row.units}</td>
                  <td className="!text-right">
                    {/* Only an ATTACHMENT comes off. A tax the plan's
                        authority brings has no row to remove (BR-RAT-113),
                        so no control is drawn for it. */}
                    {row.reached_by === "attached" && (
                      <RowActions>
                        <RowAction
                          label={t("rating.taxDetail.plans.remove", { plan: row.name })}
                          icon={<span aria-hidden="true">×</span>}
                          reason={props.readOnly ? t("rating.readOnlyReason") : null}
                          danger
                          onClick={() => setRemoving(row)}
                        />
                      </RowActions>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-neutral-100 font-semibold" data-plan-totals="">
                <td colSpan={2}>{t("rating.taxDetail.plans.count", { count: rows.length })}</td>
                <td className="!text-right tabular-nums">{totals.accounts === null ? DASH : totals.accounts}</td>
                <td className="!text-right tabular-nums">{totals.units}</td>
                <td />
              </tr>
            </tfoot>
          </PlainTable>
        </div>
      )}
      {adding && (
        <AddToPlanDialog
          taxId={props.taxId}
          client={props.client}
          onClose={() => setAdding(false)}
          onAdded={refresh}
          t={t}
        />
      )}
      {removing !== null && (
        <RemoveFromPlanDialog
          taxId={props.taxId}
          plan={removing}
          client={props.client}
          onClose={() => setRemoving(null)}
          onRemoved={refresh}
          t={t}
        />
      )}
    </Panel>
  );
}
