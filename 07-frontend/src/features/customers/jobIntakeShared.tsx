// ── Trace ──────────────────────────────────────────────
// Change:   CR-094-BRC01 step 2 wave G — **Complaints and Services.** PO
//           ruling 2026-09-12, verbatim: *"in the main tab list, add
//           complaints and services. These two tabs. build their ad form and
//           detail view. and tables."*; then *"A complaint form should be of a
//           staple form and on new page it should open up. Same for the
//           services"*, confirmed ***"Yes that is correct"***; folded into this
//           CR by ***"(a) Fold into this CR as build items."***
// Design:   `05-prototype/02 Accounts Menu Blueprint.pdf` screens 18 and 19,
//           pages 39–54, read as IMAGES (`DEF-GOV-5006`: its text layer
//           renders every digit as `&`).
// Rules:    BR-WRK-006 (a job stands on an anchor — an account is one) ·
//           BR-WRK-018 (the promise is stamped at the raise from the type's
//           priority) · BR-WRK-026 (the dispatcher list has exactly six
//           filters — NOT moved by this wave) · BR-WRK-058 (`work_order_types`
//           is a two-level catalogue: a row with a parent IS a sub-type) ·
//           BR-TEN-030 (a lookup's `code` freezes once used) · BR-SHL-010 ·
//           BR-SHL-013 (`screenId` keys the column preference) · B14 rules 19,
//           20, 21, 31, 32, 33
// Tests:    src/features/customers/JobIntake.test.tsx
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// 1 · A COMPLAINT IS A WORK ORDER, AND SO IS A SERVICE — NO NEW TABLE
// ══════════════════════════════════════════════════════════════════════════
// The blueprint states it in its own words on page 39: *"This tab does not
// exist, and everything behind it does. There is no complaints list, no
// complaint form and no complaint record anywhere in the front end — but a
// complaint is already a **work order**: `Consumer Complaint` is one of the
// nine job types the Product Owner listed themselves, it carries fifteen kinds
// beneath it, and a job can already stand on an account. **What is missing is
// the screen, not the record.**"*
//
// Measured against the running code before a line was written:
//
//   * `work.models.SEED_TYPE_SPINE` seeds **`COMPLAINT` / Consumer Complaint**
//     (default priority High) and **`CONSUMER_SVC` / Consumer Services**
//     (Normal) for every tenant.
//   * `work_orders.account_id` is `BR-WRK-006`'s third anchor, with
//     `ck_work_orders_has_anchor` refusing a job that stands on nothing.
//   * `BR-WRK-018`'s promise — `priority` → `due_at` — is stamped by
//     `metering.connections.create_work_order` at the raise, from the TYPE's
//     own default, read live from `work_priorities.sla_hours`.
//   * `POST /work-orders` is already *"the ONE raise every door uses"*
//     (`07-endpoints.md` §1 row 14), and `GET /work-orders` already filters by
//     type.
//
// ⚠ **THIS SUPERSEDES THIS SESSION'S OWN EARLIER RECOMMENDATION**, recorded in
// the decision log of 2026-09-12 as *"one record, one table, one detail page;
// Complaints and Services become two FILTERED TABS over [`ServiceRequest`],
// each with its own full-page capture form … what must stay distinct is a
// **class** column"*. That was written before the blueprint's §10 drawings were
// read, it was never put to the PO as a decision, and it would have built a
// `class` column, a second intake write path and a second queue over a table
// whose vocabulary is a MOVE (`move_in`/`move_out`/`disconnect`) — beside a
// work-order model that already carries the type, the priority, the due time
// and the account. The reasoning is recorded in `02-decision-log.md` under the
// heading of this wave; `CLAUDE.md` law 13 makes the judgment ours to make and
// to write down.
//
// ══════════════════════════════════════════════════════════════════════════
// 2 · TWO TABS RATHER THAN ONE FILTER, AND THAT IS THE DRAWING'S REASON
// ══════════════════════════════════════════════════════════════════════════
// Page 46: *"`Consumer Services` is what a customer ASKED FOR; `Consumer
// Complaint` is what went wrong. A container swap answered in three days is a
// good service and a missed collection answered in three days is not, which is
// why they carry different response times and why they are two tabs rather
// than one filter."* The two headings carry different seeded SLAs — High (8 h)
// against Normal (72 h) — so the queues answer different questions about
// lateness and cannot share one list.
//
// ══════════════════════════════════════════════════════════════════════════
// 3 · THE QUEUE FILTERS BY THE HEADING'S ID, AND THE HEADING'S KINDS COUNT
// ══════════════════════════════════════════════════════════════════════════
// ⚠ **EVERY ROW THE BLUEPRINT DRAWS IS A SUB-TYPE** — `Billing Issues`,
// `Odour complaint`, `Low Pressure`, `Missed collection`. So a queue that
// filtered on the heading row alone would be EMPTY on a utility doing exactly
// what the drawing shows, with `tsc` and every test green.
//
// `dispatch._apply_filters` matched `type_ref_id` and the free-typed words and
// **not the parent**, which predates `BR-WRK-058` making this catalogue
// hierarchical on 2026-09-07. That is `DEF-WRK-5106`, fixed in the same commit
// as this file: filtering by a HEADING now includes its kinds, on the
// dispatcher's own Orders tab as well as here. **No seventh filter is added
// and `BR-WRK-026` does not move.**
//
// The id is resolved from the CODE through `GET /lookups/work_order_types`,
// never hard-coded: `code` freezes once used (`BR-TEN-030`) while `name` does
// not, so a utility that renames *Consumer Complaint* to *Customer complaints*
// keeps working. Hard-won law 12 of the UI skill — never hand-type a list.
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "@/api/client";
import { getLookupEntries } from "@/api/endpoints";
import type { LookupEntry } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import type { TableConfig, TableFilterConfig, TableRequestState } from "@/components/tableTypes";
import { WORK_ORDER_DISPATCH_STATES } from "@/features/work/workEndpoints";
import type { WorkOrderDispatchRow } from "@/features/work/workEndpoints";
import type { Translator } from "@/features/tenancy/settingsShared";

/** Which of the two queues — the ONE word every helper here is keyed by. */
export type JobIntakeKind = "complaint" | "service";

/** The seeded `work_order_types` heading each queue stands on. CODES, because
 *  `BR-TEN-030` freezes a code once used and leaves the name editable. */
export type JobHeadingCode = "COMPLAINT" | "CONSUMER_SVC";

/**
 * Everything that differs between the two tabs and the two forms.
 *
 * ⚠ **ONE COMPONENT EACH, TWO CONFIGURATIONS — the PO's standing instruction
 * of 2026-09-12, verbatim: *"Do all changes bsed on actual code - also dont
 * create duplcate code"*.** The queue and the form differ in their heading,
 * their address, their four step names and their words; they share the anchor
 * search, the kind picker, the promise step, the review and the single write.
 * Two copies would be two sets of filters, two review steps and two places for
 * the same defect — which is the deposit lesson the PO themselves gave on the
 * same day: *"building it four times would give four behaviours"*.
 */
export interface JobIntakeSpec {
  kind: JobIntakeKind;
  /** The heading whose kinds this queue holds. */
  headingCode: JobHeadingCode;
  /** `?tab=` on the accounts register. */
  tab: "complaints" | "services";
  /**
   * The form's own address, TENANT-RELATIVE.
   *
   * ⚠ **NO `/:tenant` PREFIX** — `App.tsx` registers each as `route.slice(1)`
   * under a `:tenant` parent, so a constant carrying the prefix matches
   * nothing at all (`DEF-WRK-4051`).
   */
  route: string;
  /** `BR-SHL-013` — keys the saved column set. The two queues get their own,
   *  because two lists sharing a `screenId` share one stored set. */
  screenId: string;
  tabLabelKey: string;
  kickerKey: string;
  titleKey: string;
  newActionKey: string;
  /** The four step labels, in order, as catalogue KEYS. */
  steps: readonly string[];
  commitKey: string;
  commitFailedKey: string;
  toastKey: string;
  emptyTitleKey: string;
  emptyHelperKey: string;
  searchPlaceholderKey: string;
}

/**
 * The complaint queue and its four-step form.
 *
 * Page 39 draws `/:tenant/accounts?tab=complaints` and
 * `/brazosbend/complaints/new?step=1..4` with the rail
 * *Who is complaining · What happened · How fast we answer · Review & log*.
 */
export const COMPLAINT_INTAKE: JobIntakeSpec = {
  kind: "complaint",
  headingCode: "COMPLAINT",
  tab: "complaints",
  route: "/complaints/new",
  screenId: "S17.complaints",
  tabLabelKey: "customers.accounts.tab.complaints",
  kickerKey: "customers.complaints.kicker",
  titleKey: "customers.complaints.title",
  newActionKey: "customers.complaints.action.new",
  steps: [
    "customers.complaints.step.who",
    "customers.complaints.step.what",
    "customers.complaints.step.fast",
    "customers.complaints.step.review",
  ],
  commitKey: "customers.complaints.commit",
  commitFailedKey: "customers.complaints.commitFailed",
  toastKey: "customers.complaints.toast",
  emptyTitleKey: "customers.complaints.empty.title",
  emptyHelperKey: "customers.complaints.empty.helper",
  searchPlaceholderKey: "customers.complaints.search",
};

/**
 * The service queue and its form.
 *
 * ⚠ **FOUR STEPS, NOT THE DRAWING'S FIVE, AND THE MISSING ONE IS *SERVICE
 * FEES*.** Page 219 is explicit that the fees step is *"a proposal"* built on
 * *"a model that already exists rather than a new one"* — the SERVICE
 * REQUEST's fee model — because *"a work order carries no price today"*. That
 * is true of the table as it stands: `work_orders` has no quoted, collected or
 * outstanding column anywhere, and `work.costing` computes what a finished job
 * COST from labour and parts, which is a different fact from what a customer
 * was quoted. **A step that collects money with nowhere to store it is dead
 * UI** (hard-won law 2 — four defects in one day), so it is not drawn and its
 * absence is recorded as a build item instead of faked. Nothing on either
 * screen mentions a fee.
 */
export const SERVICE_INTAKE: JobIntakeSpec = {
  kind: "service",
  headingCode: "CONSUMER_SVC",
  tab: "services",
  route: "/services/new",
  screenId: "S17.services",
  tabLabelKey: "customers.accounts.tab.services",
  kickerKey: "customers.services.kicker",
  titleKey: "customers.services.title",
  newActionKey: "customers.services.action.new",
  steps: [
    "customers.services.step.who",
    "customers.services.step.what",
    "customers.services.step.when",
    "customers.services.step.review",
  ],
  commitKey: "customers.services.commit",
  commitFailedKey: "customers.services.commitFailed",
  toastKey: "customers.services.toast",
  emptyTitleKey: "customers.services.empty.title",
  emptyHelperKey: "customers.services.empty.helper",
  searchPlaceholderKey: "customers.services.search",
};

/** Both, in the order the register draws them. Walked by the suite so a third
 *  queue cannot be added without meeting every case the two meet. */
export const JOB_INTAKE_KINDS: readonly JobIntakeSpec[] = [COMPLAINT_INTAKE, SERVICE_INTAKE];

export function jobIntakeSpecFor(tab: string): JobIntakeSpec | null {
  return JOB_INTAKE_KINDS.find((spec) => spec.tab === tab) ?? null;
}

/** The form's address WITH the tenant, for a `navigate()` or an `href`. */
export function jobIntakePath(tenant: string, spec: JobIntakeSpec): string {
  return `/${tenant}${spec.route}`;
}

/**
 * The queue's cache key. The HEADING ID is part of it, deliberately: two
 * tenants' `COMPLAINT` rows are different ids, and a key that held only the
 * word would serve one utility's queue to the next one in the same session.
 */
export function jobQueueQueryKey(
  kind: JobIntakeKind,
  headingId: string | null,
  state: TableRequestState,
) {
  return ["customers", "jobQueue", kind, headingId ?? "unresolved", state] as const;
}

/**
 * The two headings and their kinds, read from the utility's OWN catalogue.
 *
 * Returns the heading row (matched on `code`) and every row whose
 * `parent_code` is that code — `BR-WRK-058`'s sub-types, which is what a clerk
 * actually picks from. `null` heading is a real answer: a tenant may have
 * retired the row, and the caller renders that rather than guessing an id.
 *
 * ⚠ **RETIRED ROWS ARE KEPT OUT OF THE PICKER AND NOT OUT OF THE QUEUE.** The
 * blueprint's own rule is *"retire, never delete: a retired kind stays
 * readable on every job filed under it"* — so `active` gates what may be
 * CHOSEN, and the queue filters by the heading and shows every job whatever
 * its kind's state.
 */
export interface JobKinds {
  heading: LookupEntry | null;
  kinds: readonly LookupEntry[];
  loading: boolean;
  failed: boolean;
}

export function useJobKinds(spec: JobIntakeSpec, client: ApiClient): JobKinds {
  const query = useQuery({
    queryKey: queryKeys.workLookup("work_order_types"),
    queryFn: () => getLookupEntries("work_order_types", { per: 200 }, client),
  });
  const rows = query.data?.results ?? [];
  const heading = rows.find((row) => row.code === spec.headingCode) ?? null;
  return {
    heading,
    kinds: rows.filter((row) => row.parent_code === spec.headingCode && row.active),
    loading: query.isPending,
    failed: query.isError,
  };
}

/**
 * The queue's table, as the blueprint's own header row draws it.
 *
 * Page 39/47: `REF · ACCOUNT · CUSTOMER · ADDRESS · WHAT ABOUT · SERVICE ·
 * PRIORITY · LOGGED · RESPOND BY · STATE`.
 *
 * ⚠ **`CUSTOMER` IS NOT DECLARED AND THAT IS A SERVED-FIELD FACT, NOT A
 * CHOICE.** `dispatch._dispatch_row` serves `account` as `{id, account_no}`
 * and nothing else — there is no customer name on the row and no filter that
 * would fetch one per row without a query per line. Drawing the column with a
 * dash in every cell would assert *"this job has no customer"* on every row of
 * both queues, which is worse than the column being absent (`DEF-127`'s rule:
 * an absence must not look like a value). It is REPORTED as owed.
 *
 * ⚠ **AND NO KPI STRIP.** The drawing carries four tiles — *Open · Past due ·
 * Urgent · Logged this month* — and each is a figure over the WHOLE queue
 * rather than over the page in hand. `GET /work-orders`' envelope is A11's
 * four keys and carries no aggregate, and computing one from `results` would
 * put a number on screen that changes as a clerk pages. `GET /work/kpis` is
 * where an aggregate belongs and it answers for the dispatcher, not per type.
 * REPORTED as owed.
 */
export function jobQueueTableConfig(
  t: Translator,
  spec: JobIntakeSpec,
  cells: {
    ref: (row: WorkOrderDispatchRow) => JSX.Element;
    account: (row: WorkOrderDispatchRow) => JSX.Element;
    address: (row: WorkOrderDispatchRow) => JSX.Element;
    about: (row: WorkOrderDispatchRow) => JSX.Element;
    service: (row: WorkOrderDispatchRow) => JSX.Element;
    priority: (row: WorkOrderDispatchRow) => JSX.Element;
    logged: (row: WorkOrderDispatchRow) => JSX.Element;
    respondBy: (row: WorkOrderDispatchRow) => JSX.Element;
    state: (row: WorkOrderDispatchRow) => JSX.Element;
    actions: (row: WorkOrderDispatchRow) => JSX.Element;
  },
  options: {
    priorities?: readonly LookupEntry[];
  } = {},
): TableConfig<WorkOrderDispatchRow> {
  // ⚠ **ONLY FILTERS `GET /work-orders` CAN ANSWER.** It reads its six as BARE
  // parameters and answers `400` to a seventh (`BR-WRK-026`), and this queue
  // spends `type` on its own heading — so it declares the remaining four and
  // invents none. `q` is the search box rather than a chip.
  const filters: TableFilterConfig[] = [
    {
      name: "status",
      label: t("work.orders.filter.status"),
      options: WORK_ORDER_DISPATCH_STATES.map((state) => ({
        value: state,
        label: t(`work.orders.dispatch.${state}`),
      })),
    },
    {
      name: "priority",
      label: t("work.orders.filter.priority"),
      options: (options.priorities ?? []).map((row) => ({ value: row.id, label: row.name })),
    },
  ];
  return {
    screenId: spec.screenId,
    // B14 rule 19 — THIS list's own prompt, naming what the server really
    // matches: `_search` ORs the order number, the type and three addresses.
    searchPlaceholder: spec.searchPlaceholderKey,
    searchFields: ["order_no", "type", "address"],
    filters,
    // ⚠ **NO `defaultSort` CONTROL IS OFFERED BY THE ROUTE.** `dispatch_page`
    // fixes the order — priority rank, then due time — and takes no `sort`
    // param, so declaring a sortable column here would offer an ordering the
    // request cannot ask for. The declared default names what the server
    // actually does, and no column below sets `sortable`.
    defaultSort: { sort: "priority", dir: "asc" },
    getRowId: (row) => row.id,
    columns: [
      { key: "ref", label: t("customers.jobIntake.column.ref"), cell: cells.ref },
      { key: "account", label: t("customers.accounts.col.account"), cell: cells.account },
      { key: "address", label: t("customers.accounts.col.premise"), cell: cells.address },
      { key: "about", label: t("customers.jobIntake.column.about"), cell: cells.about },
      { key: "service", label: t("work.orders.col.service"), cell: cells.service },
      { key: "priority", label: t("work.orders.col.priority"), cell: cells.priority },
      { key: "logged", label: t("customers.jobIntake.column.logged"), cell: cells.logged },
      {
        key: "respond_by",
        label: t("customers.jobIntake.column.respondBy"),
        cell: cells.respondBy,
      },
      { key: "state", label: t("work.orders.col.state"), cell: cells.state },
      { key: "actions", label: t("work.orders.col.actions"), cell: cells.actions },
    ],
  };
}
