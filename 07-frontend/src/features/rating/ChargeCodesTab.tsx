// ── Trace ──────────────────────────────────────────────
// Story:    US-RAT-008 (the Charge-codes catalog + the New/Edit Charge Code form)
//           Screens: S9 (Charge codes tab), S12
// Rules:    BR-RAT-005 (fees and late charges are NEVER in the tax base — the taxable
//           flag is bounded by B4.2, and the field says so) · BR-RAT-025 (D7: a global
//           tenant catalog; plans attach with per-plan overrides) · BR-RAT-035 (code
//           unique per tenant; service scope Any or one; IS-1 deactivate-first with the
//           audit-lock while referenced; prototype amounts are SEEDS never constants) ·
//           BR-RAT-041 (amount rules v1 = flat / percent / percent-with-minimum;
//           "Formula" is VISIBLE and DISABLED) · BR-SHL-010/011/012/020/025/032
// ───────────────────────────────────────────────────────
// S9's Charge codes tab — the CATALOGUE. The editor behind it is a route.
//
// ⚠ THE S12 FORM LEFT THIS FILE ON 2026-08-21 (CR-013 §18 row 9). It was a
// `FormModal` here, with its three CR-013 steps rendered as labelled sections
// inside one dialog, and exception E2 below had recorded that divergence since
// the day it was written. The PO ruled the shape on 2026-08-20 — *"Wizards for
// each type - no modal"* — so it is now `ChargeCodeWizard.tsx`, a full-page
// three-step wizard on `/plans-rates/charge-codes/new` and `…/{id}/edit`, and
// the modal is DELETED rather than left behind as a second door.
//
// Both of this tab's write doors go there and nowhere else: `+ New charge code`
// (including the empty state's CTA) and the pencil row action. What stayed here
// is what belongs to a list — deactivate, delete with its reference-lock
// confirmation, filters, export, and the code link into the definition detail.
//
// Two laws are still visible in the code below and worth naming:
//
//   · **No amount is a constant.** BR-RAT-035 is explicit that the prototype's
//     "NSF $30 / reconnect $45" are seed DATA, not defaults this screen ships.
//     There is therefore not one amount literal in this file.
//
//   · **No amount is formatted.** Every figure this list renders comes from the
//     server's `*_display` strings (BR-RAT-087 / DEF-364) — the raw stored
//     value and the fraction behind a percent never reach a person.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import {
  CHARGE_AMOUNT_RULES,
  CHARGE_AMOUNT_RULE_FORMULA,
  CHARGE_KINDS,
  CHARGE_TYPES,
  deleteCharge,
  getCharges,
  getLedgerAccounts,
  getTenantServices,
  setChargeActive,
} from "@/api/endpoints";
import type { ChargeRow, GlAccountRef } from "@/api/endpoints";
import { REFERENCE_STALE_MS, queryKeys } from "@/api/queryClient";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { DataTable } from "@/components/DataTable";
import type { RegionalDateFormat } from "@/components/DateCell";
import { FilterBar } from "@/components/FilterBar";
import { FailedWithRetry, PermissionDenied } from "@/components/StateFrame";
import { InlineLinkTo } from "@/components/Surfaces";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";
import type { TableConfig, TableRequestState } from "@/components/tableTypes";
import { useToast } from "@/components/Toast";
import { ListExportButton } from "@/features/exports/ListExportButton";
import {
  RefusalNotice,
  apiErrorText,
  isPermissionDenied,
  refusalOf,
} from "@/features/tenancy/settingsShared";
import { PencilIcon, PowerIcon, TrashIcon } from "@/components/icons";
import { RowAction, RowActions } from "@/components/RowActions";
import type { Refusal } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { listAmount, listPricedBy } from "./chargeCodeModel";
import { GlValue, KindBadge } from "./chargeCodeParts";
import { definitionPath, definitionWizardPath } from "./definitionDetail";
import {
  activatedServiceOptions,
  activeStatusTone,
  DASHBOARD_ROUTE,
  enumLabel,
  GuardedButton,
  isDecimalShape,
  RatingStatusPill,
  useNarrowList,
} from "./ratingShared";
import type { RatingTabRender, Translator } from "./ratingShared";

// ── Pure pieces ────────────────────────────────────────────────────────────

export const CHARGE_STATUSES = ["active", "inactive"] as const;

/**
 * The S12 amount-rule option set. `formula` IS in the list (US-RAT-008 TC-8:
 * "the option renders") and is marked `disabled`, because BR-RAT-041 keeps it
 * out of v1 and the server refuses it outright. Rendering it as a live choice
 * would offer a rule with no storage behind it.
 */
export function amountRuleOptions(
  t: Translator,
): { value: string; label: string; disabled?: boolean }[] {
  return [
    ...CHARGE_AMOUNT_RULES.map((rule) => ({
      value: rule,
      label: t(`rating.charges.amountRule.${rule}`),
    })),
    {
      value: CHARGE_AMOUNT_RULE_FORMULA,
      label: t("rating.charges.amountRule.formula"),
      disabled: true,
    },
  ];
}

/** Which money inputs an amount rule uses. The server enforces requiredness. */
export function amountFieldsFor(rule: string): {
  amount: boolean;
  percent: boolean;
  minimum: boolean;
} {
  return {
    amount: rule === "flat",
    percent: rule === "percent" || rule === "percent_with_minimum",
    minimum: rule === "percent_with_minimum",
  };
}

/**
 * US-RAT-008 TC-1: LATE renders as "1.5% or $5 min". The percent arrives as a
 * FRACTION string (0.015) and the minimum as an amount string — so this returns
 * the i18n KEY and the raw strings as params, and lets the catalog assemble the
 * sentence. It does NOT multiply 0.015 by 100: that would be client-side money
 * arithmetic, and the value on screen would stop being the value in the row.
 */
export function chargeAmountDisplay(row: ChargeRow): {
  key: string;
  params: Record<string, unknown>;
} {
  // BR-RAT-087 / DEF-364: render the SERVER'S display string, never the stored
  // value. `percent` holds the fraction 0.015000 and a customer was reading
  // exactly that. The `*_display` fields carry "1.50%" and "18.50", formatted
  // server-side for the reason the note at the foot of this file already gives:
  // scaling here would be client-side money arithmetic on a value the server
  // owns. The fix is not to scale here — it is to stop rendering the raw value.
  if (row.amount_rule === "percent_with_minimum") {
    return {
      key: "rating.charges.amount.percentWithMin",
      params: {
        percent: row.percent_display ?? "—",
        min: row.min_amount_display ?? "—",
      },
    };
  }
  if (row.amount_rule === "percent") {
    return {
      key: "rating.charges.amount.percent",
      params: { percent: row.percent_display ?? "—" },
    };
  }
  return { key: "rating.charges.amount.flat", params: { amount: row.amount_display ?? "—" } };
}

/** BR-RAT-035 IS-1: hard delete is offered only at zero references. */
export function chargeIsLocked(row: ChargeRow): boolean {
  return row.used_by_plans > 0 || row.used_by_invoice_lines > 0;
}

export function chargeTableConfig(
  t: Translator,
  serviceOptions: { value: string; label: string }[],
  cells: {
    code: (row: ChargeRow) => JSX.Element;
    /** CR-156-BRC10 — Base / Plan / Other (images 01–04). */
    kind: (row: ChargeRow) => JSX.Element;
    /** CR-156-BRC10 — *3 meter sizes · One amount · By customer class …* */
    pricedBy: (row: ChargeRow) => string;
    type: (row: ChargeRow) => string;
    service: (row: ChargeRow) => string;
    amount: (row: ChargeRow) => string;
    /** DEF-RAT-5821 — the second narrowing rule, which the list did not draw. */
    customerClass: (row: ChargeRow) => string;
    gl: (row: ChargeRow) => JSX.Element;
    taxable: (row: ChargeRow) => string;
    status: (row: ChargeRow) => JSX.Element;
    actions: (row: ChargeRow) => JSX.Element;
  },
  /** `DEF-RAT-9112` — below 1440, Priced by and GL account start behind the
   *  Columns picker so the list fits the 1280 laptop's 960px; the full set
   *  stays one click away. Decision log 2026-10-02. */
  narrow = false,
): TableConfig<ChargeRow> {
  const hideWhenNarrow = narrow ? { defaultVisible: false } : {};
  return {
    screenId: "S9.charges",
    columns: [
      {
        key: "code",
        label: t("rating.charges.col.code"),
        sortable: true,
        identity: true,
        cell: cells.code,
      },
      { key: "name", label: t("rating.charges.col.description"), sortable: true },
      // CR-156-BRC10 — the PO kept today's columns and added TWO: Kind, after
      // the description, and Priced by, before the amount (decision log
      // 2026-10-01, *"THE LIST KEEPS TODAY'S COLUMNS AND ADDS KIND AND PRICED BY"*).
      { key: "kind", label: t("rating.chargeCode.col.kind"), sortable: true, cell: cells.kind },
      { key: "charge_type", label: t("rating.charges.col.type"), sortable: true, cell: cells.type },
      { key: "service", label: t("rating.filter.service"), cell: cells.service },
      // ── DEF-RAT-5821 · THE OTHER NARROWING RULE, BESIDE THE FIRST ────────
      // The PO's charge-code walk named TWO rules — *"based on services, based
      // on customer class"* — and only one of them was on this list. A clerk
      // looking at 29 codes could not tell which were class-scoped from any
      // screen in the product, so the column sits immediately beside `SERVICE`
      // because the two answer the same question about the same code.
      //
      // ⚠ NOT `defaultVisible: false`. The two optional columns below are
      // extra detail a clerk may want; this one is the fact the defect is
      // about, and a column nobody turns on is the absence again with a
      // chooser in front of it.
      //
      // ⚠ **THERE IS NO CLASS FILTER BESIDE IT, DELIBERATELY** — the server
      // filters `charges` in SQL (`NFR-3`, `charge_list_queryset`) and
      // `applies_to_customer_classes` is a JSON column whose `__contains`
      // lookup PostgreSQL supports and SQLite does not, which is the database
      // the whole test suite runs on (hard-won law 14). Filed rather than
      // half-built; this column is what answers *which codes are class-scoped*.
      {
        key: "applies_to_customer_classes",
        label: t("rating.plan.customerClassLabel"),
        cell: cells.customerClass,
      },
      { key: "priced_by", label: t("rating.chargeCode.col.pricedBy"), cell: cells.pricedBy, ...hideWhenNarrow },
      { key: "amount", label: t("rating.charges.col.amount"), sortable: true, cell: cells.amount },
      { key: "gl_account_id", label: t("rating.charges.col.gl"), cell: cells.gl, ...hideWhenNarrow },
      // The two additional available columns (IS-5 chooser).
      {
        key: "taxable_default",
        label: t("rating.charges.col.taxable"),
        defaultVisible: false,
        cell: cells.taxable,
      },
      {
        key: "used_by_plans",
        label: t("rating.charges.col.usedBy"),
        defaultVisible: false,
        numeric: true,
      },
      { key: "status", label: t("rating.col.status"), cell: cells.status },
      { key: "actions", label: t("rating.col.actions"), cell: cells.actions },
    ],
    getRowId: (row) => row.id,
    searchFields: ["code", "name"],
    // ⚠ **B14 rule 19, AND THE COPY SAYS `description`, NOT `name`.**
    // `charge_list` filters `Q(code) | Q(name)`; the `name` column's header on
    // THIS table is `rating.charges.col.description` → **"Description"**. The
    // prompt names what the screen shows, not what the column is called in the
    // database — a user cannot match a prompt against a field they never see.
    searchPlaceholder: "rating.charges.searchPlaceholder",
    filters: [
      {
        name: "type",
        label: t("rating.charges.filter.type"),
        options: CHARGE_TYPES.map((value) => ({
          value,
          label: t(`rating.charges.type.${value}`),
        })),
      },
      { name: "service", label: t("rating.filter.service"), options: serviceOptions },
      {
        name: "status",
        label: t("rating.col.status"),
        options: CHARGE_STATUSES.map((value) => ({ value, label: t(`rating.status.${value}`) })),
      },
      // DEF-RAT-9803 — Kind is an ordinary `+ Filter` dimension (B14 rule 12;
      // PO 2026-10-06: *"on list view filter options are showing outside it
      // should be in the filter dropdown"*), applied as a removable
      // `Kind: Base` chip; `f.kind` keeps its URL spelling so links still
      // work. The panel shows each option's count (`counts`, filled by the
      // tab from the server's `kind_counts`). It was a chip row beside the
      // search box (CR-156-BRC10, images 01–04) until then.
      {
        name: "kind",
        label: t("rating.chargeCode.col.kind"),
        options: CHARGE_KINDS.map((value) => ({ value, label: t(`rating.chargeCode.kindChip.${value}`) })),
      },
    ],
    defaultSort: { sort: "code", dir: "asc" },
  };
}

/** SHAPE only — the sort order of "which field is required" is the server's. */
export function chargeSchema(t: Translator) {
  const decimal = z
    .string()
    .refine((value) => value.trim() === "" || isDecimalShape(value), t("rating.error.notDecimal"));
  return z.object({
    code: z
      .string()
      .trim()
      .min(1, t("rating.error.required"))
      .max(20, t("rating.error.tooLong", { max: 20 })),
    name: z
      .string()
      .trim()
      .min(1, t("rating.error.required"))
      .max(120, t("rating.error.tooLong", { max: 120 })),
    // BR-RAT-041: the disabled option can still be reached by keyboard on some
    // platforms, so it is refused here too — with the rule's own wording.
    amount_rule: z
      .string()
      .refine((value) => value !== CHARGE_AMOUNT_RULE_FORMULA, t("rating.charges.formulaDisabled")),
    amount: decimal,
    percent: decimal,
    min_amount: decimal,
    max_amount: decimal,
  });
}

// ── The tab ────────────────────────────────────────────────────────────────

export interface ChargeCodesTabProps {
  readOnly: boolean;
  client?: ApiClient;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /**
   * US-SHL-020 addendum r2. The frame draws the page header, so the tab hands
   * its primary button up rather than rendering it itself. It now NAVIGATES —
   * `+ New charge code` opens the CHG-02 full-page wizard (PO 2026-08-20,
   * *"Wizards for each type - no modal"*), and the modal it used to open is
   * deleted rather than left as a second door.
   */
  render: RatingTabRender;
}

export function ChargeCodesTab(props: ChargeCodesTabProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const client = props.client ?? api;
  const fireToast = useToast();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [pendingDelete, setPendingDelete] = useState<ChargeRow | null>(null);
  const [refusal, setRefusal] = useState<Refusal | null>(null);

  const servicesQuery = useQuery({
    queryKey: queryKeys.tenantServices,
    queryFn: () => getTenantServices(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  // DEF-RAT-5691 — the tenant's OWN services, never the platform catalogue.
  // `/settings/services` serves all eleven with an `enabled` flag; this filter
  // is the flag being read (BR-RAT-024, PO ruling 2026-09-17).
  const serviceOptions = activatedServiceOptions(servicesQuery.data);
  // DEF-206: the chart of accounts, so the GL column names an account instead
  // of printing its uuid, and so the form can offer a picker. `retry: false`
  // because a deployment that cannot answer this is a state to render, not a
  // thing to hammer — the cell says "not resolvable yet" and the form's picker
  // stays disabled with its reason (BR-SHL-025).
  const chartQuery = useQuery({
    queryKey: queryKeys.ledgerAccounts,
    queryFn: () => getLedgerAccounts(client),
    staleTime: REFERENCE_STALE_MS,
    retry: false,
  });
  const accounts = chartQuery.data ?? [];

  const narrow = useNarrowList(); // DEF-RAT-9112
  const config = chargeTableConfig(translate, serviceOptions, {
    // CR-013 row 8 / BR-RAT-084: the code opens the DEFINITION DETAIL, which is
    // r10's own behaviour and the only door this screen has (hard-won law 2 —
    // a detail nothing links to is not built). It is a LINK, not a
    // `GuardedButton`: a read-only role may read a definition, and the button
    // here was disabled for them only because it used to open the edit modal.
    // Editing keeps its pencil row action, unchanged.
    code: (row) => (
      <InlineLinkTo to={tenantPath(definitionPath("charge", row.id))}>{row.code}</InlineLinkTo>
    ),
    kind: (row) => <KindBadge kind={row.kind} t={translate} />,
    pricedBy: (row) => {
      const words = listPricedBy(row);
      return t(words.key, words.params);
    },
    // The redesigned screens call `refundable` a *Deposit* (image 01).
    type: (row) =>
      row.charge_type === "refundable"
        ? t("rating.chargeCode.type.refundable")
        : enumLabel(translate, "rating.charges.type", row.charge_type),
    // BR-RAT-035: NULL service = Any, and "Any" is a real answer, not a blank.
    service: (row) =>
      row.service === null
        ? t("rating.charges.anyService")
        : t(`rating.service.${row.service}`, { defaultValue: row.service }),
    // CR-156-BRC10 — a sized code shows its RANGE (*"BASE-T reads $9.00 –
    // $40.00, not 0.00"*); a code with no price at all reads a dash.
    amount: (row) => {
      return listAmount(row, translate) ?? "—";
    },
    // DEF-RAT-5821 — BR-RAT-108's inclusion list, read back in the rate
    // schedule detail's own words so one fact has one name across the two
    // priced objects. `[]` and an absent value both mean EVERY class and are
    // SAID so: a blank cell would read as a restriction nobody can see.
    // ⚠ `?? []` — the field is OPTIONAL on `ChargeRow` (`endpoints.ts:4758`),
    // and an ABSENT value from an older row means exactly what an EMPTY list
    // means: every class. Both therefore read the same sentence.
    customerClass: (row) =>
      (row.applies_to_customer_classes ?? []).length === 0
        ? t("rating.rateDetail.field.customerClassAll")
        : (row.applies_to_customer_classes ?? [])
            .map((code) => t(`rating.customerClass.${code}`, { defaultValue: code }))
            .join(", "),
    // CR-156-BRC10 — a missing GL account is a WARNING (image 01, APP-FEE).
    gl: (row) =>
      row.gl_account_code !== undefined ? (
        <GlValue code={row.gl_account_code} name={row.gl_account_name} t={translate} />
      ) : (
        <GlAccountCell value={row.gl_account_id} accounts={accounts} />
      ),
    taxable: (row) => t(row.taxable_default ? "rating.yes" : "rating.no"),
    status: (row) => (
      <RatingStatusPill
        tone={activeStatusTone(row.status)}
        stem="rating.status"
        value={row.status}
      />
    ),
    actions: (row) => (
      <RowActions>
        <RowAction
          label={t("rating.action.edit")}
          icon={<PencilIcon />}
          reason={props.readOnly ? t("rating.readOnlyReason") : null}
          // The SECOND door to CHG-02, and it is a door to the same screen —
          // `…/{id}/edit` is the wizard opened on a stored code, never a
          // different editor (hard-won law 2: one thing, wired everywhere).
          onClick={() => navigate(tenantPath(definitionWizardPath("charge", row.id)))}
        />
        <RowAction
          label={t(row.status === "active" ? "rating.action.deactivate" : "rating.action.reactivate")}
          icon={<PowerIcon />}
          reason={props.readOnly ? t("rating.readOnlyReason") : null}
          onClick={() => toggleActive.mutate(row)}
        />
        <RowAction
          label={t("rating.action.delete")}
          icon={<TrashIcon />}
          danger
          reason={props.readOnly ? t("rating.readOnlyReason") : null}
          onClick={() => {
            setRefusal(null);
            setPendingDelete(row);
          }}
        />
      </RowActions>
    ),
  }, narrow);

  const state = parseTableParams(searchParams, config);
  const listQuery = useQuery({
    queryKey: queryKeys.charges(serializeTableParams(state, config).toString()),
    queryFn: () =>
      getCharges(
        {
          q: state.q,
          filters: state.filters,
          sort: state.sort,
          dir: state.dir,
          page: state.page,
          per: state.per,
        },
        client,
      ),
  });

  function refresh(): void {
    void queryClient.invalidateQueries({ queryKey: ["charges"] });
  }

  const toggleActive = useMutation({
    mutationFn: (row: ChargeRow) => setChargeActive(row.id, row.status !== "active", client),
    onSuccess: (saved) => {
      setRefusal(null);
      fireToast(
        t(
          saved.status === "active"
            ? "rating.charges.toast.reactivated"
            : "rating.charges.toast.deactivated",
          {
            code: saved.code,
          },
        ),
      );
      refresh();
    },
    onError: (error: unknown) => setRefusal(refusalOf(error, translate)),
  });

  const remove = useMutation({
    mutationFn: (row: ChargeRow) => deleteCharge(row.id, client),
    onSuccess: (_void, row) => {
      setPendingDelete(null);
      setRefusal(null);
      fireToast(t("rating.charges.toast.deleted", { code: row.code }));
      refresh();
    },
    onError: (error: unknown) => {
      // US-RAT-008 TC-7: "attached to N plans" — the count is the SERVER's,
      // recomputed inside its transaction, and rendered verbatim.
      setPendingDelete(null);
      setRefusal(refusalOf(error, translate));
    },
  });

  function setState(next: TableRequestState): void {
    setSearchParams(serializeTableParams(next, config), { replace: true });
  }

  // A failed read still goes back through the render prop, so the page keeps
  // its header and tab strip and the user can move somewhere else. It offers
  // no primary action: there is nothing to add to a list that would not load.
  if (listQuery.data === undefined && listQuery.isError) {
    if (isPermissionDenied(listQuery.error)) {
      return (
        <>
          {props.render({
            body: (
              <PermissionDenied
                helper={t("rating.denied")}
                onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
              />
            ),
          })}
        </>
      );
    }
    return (
      <>
        {props.render({
          body: (
            <FailedWithRetry
              title={t("rating.charges.failedTitle")}
              reason={apiErrorText(listQuery.error, translate)}
              onRetry={() => void listQuery.refetch()}
              onDownloadReport={() => undefined}
              onCancel={() => void listQuery.refetch()}
            />
          ),
        })}
      </>
    );
  }

  return (
    <>
      {props.render({
        // BR-SHL-025 stays HERE, not in the frame: a Clerk gets the button
        // disabled with its reason, and the header renders whatever it is
        // handed rather than knowing anything about roles.
        action: (
          <GuardedButton
            readOnly={props.readOnly}
            readOnlyReason={t("rating.readOnlyReason")}
            variant="primary"
            onClick={() => navigate(tenantPath(definitionWizardPath("charge", null)))}
          >
            {t("rating.charges.new")}
          </GuardedButton>
        ),
        body: (
          <div className="rating-tab">
            <RefusalNotice refusal={refusal} />

            <DataTable<ChargeRow>
              config={config}
              state={state}
              onStateChange={setState}
              rows={listQuery.data?.results ?? []}
              totalRows={listQuery.data?.count ?? null}
              loading={listQuery.isPending}
              filterBarSlot={
                <FilterBar
                  filters={(config.filters ?? []).map((filter) =>
                    filter.name === "kind" && listQuery.data?.kind_counts
                      ? { ...filter, counts: { ...listQuery.data.kind_counts } }
                      : filter,
                  )}
                  state={state}
                  onStateChange={setState}
                />
              }
              downloadSlot={
                // EP-RAT-03's capability row: CSV (IS-9). A money table — the export
                // audits itself server-side (BR-SHL-016).
                <ListExportButton resource="charges" state={state} client={client} />
              }
              empty={{
                title: t("rating.charges.emptyTitle"),
                helper: t("rating.charges.emptyHelper"),
                ctaLabel: t("rating.charges.new"),
                onCta: () =>
                  !props.readOnly && navigate(tenantPath(definitionWizardPath("charge", null))),
              }}
            />

            {pendingDelete !== null && (
              <ConfirmDialog
                // B14 rule 6 (DEF-718): delete a charge code.
                confirmVariant="danger"
                title={t("rating.charges.confirm.delete.title", { code: pendingDelete.code })}
                consequence={t(
                  chargeIsLocked(pendingDelete)
                    ? "rating.charges.confirm.delete.locked"
                    : "rating.charges.confirm.delete.body",
                  {
                    code: pendingDelete.code,
                    plans: pendingDelete.used_by_plans,
                    lines: pendingDelete.used_by_invoice_lines,
                  },
                )}
                confirmLabel={t("rating.charges.confirm.delete.verb", { code: pendingDelete.code })}
                working={remove.isPending}
                onConfirm={() => remove.mutate(pendingDelete)}
                onCancel={() => setPendingDelete(null)}
              />
            )}
          </div>
        ),
      })}
    </>
  );
}

/**
 * The income account this charge posts to.
 *
 * ⚠ **DEF-206.** This component used to print the raw uuid, under a docstring
 * saying *"the ledger module is not built, so no endpoint serves an account
 * list"*. `GET /ledger/accounts` has been served since 2026-08-16
 * (`apps/ledger/chart_api.py`), so the sentence was false and a clerk was
 * being shown `0f3c…-a91b` where their own books say `4200 Late fee revenue`.
 *
 * Three answers, and they are NOT the same: unmapped (BR-BIL-010 refuses the
 * WHOLE bill at issue), mapped-and-named, and mapped-but-not-yet-resolvable
 * because the chart has not loaded. The third one still must not print a uuid
 * at a person, so it says so in words.
 */
function GlAccountCell(props: { value: string | null; accounts: readonly GlAccountRef[] }) {
  const { t } = useTranslation();
  if (props.value === null) {
    return <span className="rating-empty">{t("rating.gl.unset")}</span>;
  }
  const account = props.accounts.find((row) => row.id === props.value);
  if (account === undefined) {
    return <span className="rating-empty">{t("rating.gl.unresolved")}</span>;
  }
  return (
    <span className="rating-gl">
      {account.code} — {account.name}
    </span>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-RAT-008@7d1a8ef (story+rules snapshot hash — EP-RAT-03)
// generated: 2026-08-09 by story-coder v1 (W1 Plans & Rates frontend lane — S9 Charge codes + S12) · AMENDED 2026-08-10 by story-coder v1 (path-tenancy lane — PO ruling 2026-08-10: SPA `/{tenant}/…`, API `/api/{tenant}/…`)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: [list-export lane 2026-08-10] tsc✔ eslint --max-warnings 0✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 was the baseline; this lane adds 14 passing + 2 todo and converted 3 stale negative assertions into positives) · 5 locales × 2066 keys, identical sets · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · trace_lint✔ (227 stories, 459 BR refs, 60 OQs) run_gates✔ (11 PASS · 0 FAIL · 1 SKIP) tsc✔ eslint✔ vitest 487 passed / 130 todo across 42 files✔ (399+111 baseline unchanged and green; this packet adds 88 passing + 19 todo across 5 files — every todo is browser-interaction, server/RLS-isolation or unbuilt-neighbour-module scope) · 2026-08-10 path-tenancy re-run: tsc✔ eslint✔ vitest 529 passed / 134 todo across 44 files✔ (509 passed / 132 todo was the pre-lane baseline — the suite grew, nothing was dropped) · vite build✔ · run_gates 11 PASS · 0 FAIL · 1 SKIP · trace_lint✔
// exceptions: E2 CLOSED (CR-013 §18 row 9, 2026-08-21): US-RAT-008 models S12 as a THREE-STEP guided form, and this file rendered the three steps as labelled sections inside ONE FormModal because the shared kit had no modal wizard shell. The PO ruled the shape on 2026-08-20 — "Wizards for each type - no modal" — so S12 is now the full-page ChargeCodeWizard on `/plans-rates/charge-codes/new` and `…/{id}/edit`, mounted on the shared WizardFrame; the modal is deleted and both doors here navigate to it. The reported divergence became the spec · E3 CLOSED (list-export lane 2026-08-10): EP-RAT-03's CSV export for this tab is WIRED to POST /exports (a MONEY table — the server writes the BR-SHL-016 audit row); the Amount cell exports as its RULE plus each field the rule uses, because IS-9 gives a money column one meaning and this one is sometimes a percent · E3 the GL-account field renders as an ArrivesWith note: `charges.gl_account_id` is a →ledger FK and no endpoint serves a chart of accounts, so the form posts no GL and an existing id is shown verbatim in the list · E4 `percent` is displayed and edited as the stored FRACTION (0.015) with the fact stated on the field — converting to 1.5 on screen would be client-side money arithmetic on a value the server owns
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
