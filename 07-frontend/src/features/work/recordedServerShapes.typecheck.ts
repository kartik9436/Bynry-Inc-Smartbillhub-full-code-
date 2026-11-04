// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 lane SHAPE-SWEEP — every Work read the back office
//           draws, checked by `tsc` against the type the screen reads through.
// Defects:  DEF-WRK-9600 · DEF-WRK-9601 (and the sweep's own, in CR-168 §15)
// Rules:    CLAUDE.md hard-won law 2's mirror · law 7 (*looking at the wrong
//           thing*) · CR-168 §7 *"Fixtures come from the server"*
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY JSON FILE IMPORTED HERE IS A RECORDING, NOT A FIXTURE SOMEBODY
// WROTE.** `10-scripts/cr168_capture_work_shapes.py` signs in to
// `manage.py runserver` on PostgreSQL 16 and saves what each read answered.
// This file assigns each recording to the TypeScript type the screen reads it
// through, so **`tsc --noEmit` goes red the day the server and the screen stop
// agreeing** — a unit sent as `{id, label}` where the screen declares a string
// (`DEF-WRK-9600`), a field the screen REQUIRES and the server never sends
// (`DEF-WRK-9601`'s `active`), a money string where the screen declares a
// number. Before this file the only description of the wire was the screen's
// own interface and each side's hand-typed fixture, which agreed with itself.
//
// `Wire<T>` widens literal unions to their base type, because a JSON module's
// `"state": "planned"` is typed `string` and could never satisfy
// `"planned" | "completed"`; every OTHER difference — object for string, null
// where the type says never-null, a missing required key, a number for a
// string — still fails. What it CANNOT see: a key the type marks optional
// that the server never sends (that is a contract question, and the sweep's
// report lists them), and an enum value outside its union.
//
// **Never edit a recording to make this file compile.** Fix the side the
// contract (CR-168 §7.3) says is wrong, then re-record.
import type { Paginated } from "@/api/paginated";
import type { NotificationRuleRow, RolesMatrix, TenantServiceRow } from "@/api/endpoints";

import type { HoldReason, OrderHistoryRow, OrderPageFields } from "./orderPage/orderPageEndpoints";
import type { RuleAuditRow, RuleProcesses, WorkRule, WorkRuleDetail } from "./rules/ruleEndpoints";
import type { BulkRaiseOutcome, RaiseAssetRow } from "./raise/raiseEndpoints";
import type { AtRiskPage, SlaSettings } from "./performance/performanceEndpoints";
import type {
  AssetTemplatesPayload,
  AwaitingApprovalList,
  CandidatePage,
  CertificationWatch,
  CloseReadiness,
  CrewList,
  CrewMember,
  LabourRateRow,
  OrderAttachment,
  OrderChecklist,
  OrderEditForm,
  OrderSignature,
  PartIssueRow,
  PartList,
  PerformancePayload,
  RaiseOptions,
  TechnicianDetail,
  TemplateAudit,
  TemplateDetail,
  TemplateList,
  TemplatePack,
  TemplateUsage,
  TemplateVersions,
  WorkArea,
  WorkKpis,
  WorkOrderDispatchRow,
  WorkOrderList,
  WorkOrderMap,
  WorkOrderState,
  WorkRuleRow,
  getWorkOrder,
} from "./workEndpoints";

import ORDERS from "./__fixtures__/server/work-orders.list.json";
import ORDERS_DONE from "./__fixtures__/server/work-orders.list.complete.json";
import AWAITING from "./__fixtures__/server/work-orders.awaiting-approval.json";
import MAP from "./__fixtures__/server/work-orders.map.json";
import HOLD_REASONS from "./__fixtures__/server/work.hold-reasons.json";
import RAISE_OPTIONS from "./__fixtures__/server/work.raise-options.json";
import KPIS from "./__fixtures__/server/work.kpis.json";
import AREAS from "./__fixtures__/server/work.areas.json";
import OPEN from "./__fixtures__/server/work-order.open.json";
import OPEN_AUDIT from "./__fixtures__/server/work-order.open.audit.json";
import OPEN_CHECKLIST from "./__fixtures__/server/work-order.open.checklist.json";
import OPEN_ATTACHMENTS from "./__fixtures__/server/work-order.open.attachments.json";
import OPEN_READINESS from "./__fixtures__/server/work-order.open.close-readiness.json";
import OPEN_EDIT from "./__fixtures__/server/work-order.open.edit.json";
import OPEN_CANDIDATES from "./__fixtures__/server/work-order.open.candidates.json";
import HELD from "./__fixtures__/server/work-order.held.json";
import HELD_AUDIT from "./__fixtures__/server/work-order.held.audit.json";
import HELD_CHECKLIST from "./__fixtures__/server/work-order.held.checklist.json";
import ACCEPTED from "./__fixtures__/server/work-order.accepted.json";
import ACCEPTED_AUDIT from "./__fixtures__/server/work-order.accepted.audit.json";
import ACCEPTED_CHECKLIST from "./__fixtures__/server/work-order.accepted.checklist.json";
import ACCEPTED_ATTACHMENTS from "./__fixtures__/server/work-order.accepted.attachments.json";
import ACCEPTED_READINESS from "./__fixtures__/server/work-order.accepted.close-readiness.json";
import DONE from "./__fixtures__/server/work-order.completed.json";
import DONE_AUDIT from "./__fixtures__/server/work-order.completed.audit.json";
import DONE_CHECKLIST from "./__fixtures__/server/work-order.completed.checklist.json";
import DONE_ATTACHMENTS from "./__fixtures__/server/work-order.completed.attachments.json";
import DONE_READINESS from "./__fixtures__/server/work-order.completed.close-readiness.json";
import DONE_SIGNATURE from "./__fixtures__/server/work-order.completed.signature.json";
import CREWS from "./__fixtures__/server/work.crews.technicians.json";
import CREW_DIRECTORY from "./__fixtures__/server/work.crew-directory.json";
import CERT_WATCH from "./__fixtures__/server/work.certification-watch.json";
import TECHNICIAN from "./__fixtures__/server/work.technician.json";
import PARTS from "./__fixtures__/server/work.parts.json";
import PART_ISSUES from "./__fixtures__/server/work.parts.issues.json";
import TEMPLATES from "./__fixtures__/server/work.templates.json";
import TEMPLATE_PACKS from "./__fixtures__/server/work.template-packs.json";
import TEMPLATE from "./__fixtures__/server/work.template.json";
import TEMPLATE_VERSIONS from "./__fixtures__/server/work.template.versions.json";
import TEMPLATE_USAGE from "./__fixtures__/server/work.template.usage.json";
import TEMPLATE_AUDIT from "./__fixtures__/server/work.template.audit.json";
import RULES from "./__fixtures__/server/work.rules.json";
// Lane RULES (CR-168 round 5) — the reads the rules list, the builder and one
// rule's page are typed against (`rules/ruleEndpoints.ts`), recorded by lane
// SRV-4 and (`work.rules.processes`) re-recorded by lane RULES.
import RULE_PROCESSES from "./__fixtures__/server/work.rules.processes.json";
import RULE from "./__fixtures__/server/work.rule.json";
import RULE_JOBS from "./__fixtures__/server/work.rule.jobs.json";
import RULE_AUDIT from "./__fixtures__/server/work.rule.audit.json";
import RULE_LOOKUP_MESSAGES from "./__fixtures__/server/work.rules.lookup.notification-rules.json";
import RULE_LOOKUP_SERVICES from "./__fixtures__/server/work.rules.lookup.services.json";
import RULE_LOOKUP_ROLES from "./__fixtures__/server/work.rules.lookup.roles.json";
import LABOUR_RATES from "./__fixtures__/server/work.labour-rates.json";
import PERFORMANCE from "./__fixtures__/server/work.performance.json";
// CR-168 round 5, lane PERFORMANCE — the paged table (P5.6), the at-risk
// board's read (P5.3) and the default target (P5.1), recorded by SRV-4.
import PERFORMANCE_PAGED from "./__fixtures__/server/work.performance.paged.json";
import AT_RISK from "./__fixtures__/server/work.at-risk.json";
import SETTINGS_SLA from "./__fixtures__/server/work.settings.sla.json";
// Lane SRV-2's recordings (`10-scripts/cr168_srv2_record_shapes.py`), checked
// here against the screens that already read them.
import SRV2_CANDIDATES from "./__fixtures__/work-order-candidates.recorded.json";
import SRV2_ASSET_TEMPLATES from "./__fixtures__/asset-work-order-templates.recorded.json";
import SRV2_RAISE_TEMPLATES from "./__fixtures__/work-templates-for-the-raise.recorded.json";
import SRV2_RAISE_ASSETS from "./__fixtures__/work-raise-assets.recorded.json";
import SRV2_BULK_RAISE from "./__fixtures__/work-orders-bulk-raise.recorded.json";

/** The wire's view of a screen type: literal unions widened to their base. */
export type Wire<T> = T extends string
  ? string
  : T extends number
    ? number
    : T extends boolean
      ? boolean
      : T extends readonly (infer U)[]
        ? Wire<U>[]
        : T extends object
          ? { [K in keyof T]: Wire<T[K]> }
          : T;

/** The order page reads `GET /work-orders/{id}` through this exact type. */
type OrderDetail = Awaited<ReturnType<typeof getWorkOrder>> & OrderPageFields & { state: WorkOrderState };

export const recorded = {
  orders: ORDERS satisfies Wire<WorkOrderList>,
  ordersRow: ORDERS.results[0] satisfies Wire<WorkOrderDispatchRow>,
  ordersDone: ORDERS_DONE satisfies Wire<WorkOrderList>,
  awaiting: AWAITING satisfies Wire<AwaitingApprovalList>,
  map: MAP satisfies Wire<WorkOrderMap>,
  holdReasons: HOLD_REASONS satisfies Wire<HoldReason[] | { results: HoldReason[] }>,
  raiseOptions: RAISE_OPTIONS satisfies Wire<RaiseOptions>,
  kpis: KPIS satisfies Wire<WorkKpis>,
  areas: AREAS satisfies Wire<{ results: WorkArea[] }>,
  open: OPEN satisfies Wire<OrderDetail>,
  openAudit: OPEN_AUDIT satisfies Wire<{ order_no: string | null; results: OrderHistoryRow[] }>,
  openChecklist: OPEN_CHECKLIST satisfies Wire<OrderChecklist>,
  openAttachments: OPEN_ATTACHMENTS satisfies Wire<OrderAttachment[]>,
  openReadiness: OPEN_READINESS satisfies Wire<CloseReadiness>,
  openEdit: OPEN_EDIT satisfies Wire<OrderEditForm>,
  openCandidates: OPEN_CANDIDATES satisfies Wire<CandidatePage>,
  held: HELD satisfies Wire<OrderDetail>,
  heldAudit: HELD_AUDIT satisfies Wire<{ order_no: string | null; results: OrderHistoryRow[] }>,
  heldChecklist: HELD_CHECKLIST satisfies Wire<OrderChecklist>,
  accepted: ACCEPTED satisfies Wire<OrderDetail>,
  acceptedAudit: ACCEPTED_AUDIT satisfies Wire<{ order_no: string | null; results: OrderHistoryRow[] }>,
  acceptedChecklist: ACCEPTED_CHECKLIST satisfies Wire<OrderChecklist>,
  acceptedAttachments: ACCEPTED_ATTACHMENTS satisfies Wire<OrderAttachment[]>,
  acceptedReadiness: ACCEPTED_READINESS satisfies Wire<CloseReadiness>,
  done: DONE satisfies Wire<OrderDetail>,
  doneAudit: DONE_AUDIT satisfies Wire<{ order_no: string | null; results: OrderHistoryRow[] }>,
  doneChecklist: DONE_CHECKLIST satisfies Wire<OrderChecklist>,
  doneAttachments: DONE_ATTACHMENTS satisfies Wire<OrderAttachment[]>,
  doneReadiness: DONE_READINESS satisfies Wire<CloseReadiness>,
  doneSignature: DONE_SIGNATURE satisfies Wire<OrderSignature>,
  crews: CREWS satisfies Wire<CrewList>,
  crewDirectory: CREW_DIRECTORY satisfies Wire<{ results: CrewMember[] }>,
  certificationWatch: CERT_WATCH satisfies Wire<CertificationWatch>,
  technician: TECHNICIAN satisfies Wire<TechnicianDetail>,
  parts: PARTS satisfies Wire<PartList>,
  partIssues: PART_ISSUES satisfies Wire<Paginated<PartIssueRow>>,
  templates: TEMPLATES satisfies Wire<TemplateList>,
  templatePacks: TEMPLATE_PACKS satisfies Wire<{ packs: TemplatePack[] }>,
  template: TEMPLATE satisfies Wire<TemplateDetail>,
  templateVersions: TEMPLATE_VERSIONS satisfies Wire<TemplateVersions>,
  templateUsage: TEMPLATE_USAGE satisfies Wire<TemplateUsage>,
  // CR-168 P3.28 — the template's change history, as the Audit tab reads it.
  templateAudit: TEMPLATE_AUDIT satisfies Wire<TemplateAudit>,
  rules: RULES satisfies Wire<Paginated<WorkRuleRow>>,
  // Lane RULES — the list as the rebuilt screen reads it, one rule (with
  // `tonight`), the processes and vocabularies, its jobs and its audit.
  rulesList: RULES satisfies Wire<Paginated<WorkRule>>,
  rule: RULE satisfies Wire<WorkRuleDetail>,
  ruleProcesses: RULE_PROCESSES satisfies Wire<RuleProcesses>,
  ruleJobs: RULE_JOBS satisfies Wire<Paginated<WorkOrderDispatchRow>>,
  ruleAudit: RULE_AUDIT satisfies Wire<Paginated<RuleAuditRow>>,
  // …and the three reads the rule form offers from outside Work.
  // The three fields the rule form reads of each catalogue row (the matrix's
  // whole row is Notifications' screen's to check; a JSON module widens its
  // per-row `template_classes` maps into a union no index signature accepts).
  ruleLookupMessages: RULE_LOOKUP_MESSAGES satisfies Wire<{
    results: Pick<NotificationRuleRow, "key" | "audience" | "channels">[];
  }>,
  ruleLookupServices: RULE_LOOKUP_SERVICES satisfies Wire<TenantServiceRow[]>,
  ruleLookupRoles: RULE_LOOKUP_ROLES satisfies Wire<RolesMatrix>,
  labourRates: LABOUR_RATES satisfies Wire<Paginated<LabourRateRow>>,
  performance: PERFORMANCE satisfies Wire<PerformancePayload>,
  performancePaged: PERFORMANCE_PAGED satisfies Wire<PerformancePayload>,
  atRisk: AT_RISK satisfies Wire<AtRiskPage>,
  settingsSla: SETTINGS_SLA satisfies Wire<SlaSettings>,
  srv2Candidates: SRV2_CANDIDATES satisfies Wire<CandidatePage>,
  srv2AssetTemplates: SRV2_ASSET_TEMPLATES satisfies Wire<AssetTemplatesPayload>,
  srv2RaiseTemplates: SRV2_RAISE_TEMPLATES satisfies Wire<TemplateList>,
  srv2RaiseAssets: SRV2_RAISE_ASSETS satisfies Wire<Paginated<RaiseAssetRow>>,
  srv2BulkRaise: SRV2_BULK_RAISE satisfies Wire<BulkRaiseOutcome>,
};
