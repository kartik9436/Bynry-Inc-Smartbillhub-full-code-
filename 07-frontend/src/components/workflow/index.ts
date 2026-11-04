// ── Trace ──────────────────────────────────────────────
// Change:   CR-023 — the reusable ETL workflow kit, one import path
// Rules:    B14 rule 21 (new UI is Tailwind)
// Impacts:  the screens that mount the runner import from here.
// ───────────────────────────────────────────────────────
//
// ONE IMPORT PATH FOR THE WHOLE KIT, so a screen that needs the runner cannot
// reach half of it and hand-roll the other half — which is how
// `ImportAccountsWizard.tsx` ended up drawing a customers screen out of
// metering's stylesheet.

export { StageBar } from "./StageBar";
export type { StageBarProps } from "./StageBar";
export { SourceCards } from "./SourceCards";
export type { SourceCardsProps } from "./SourceCards";
export { DropZone } from "./DropZone";
export type { DropZoneProps } from "./DropZone";
export { MappingTable } from "./MappingTable";
export type { MappingTableProps } from "./MappingTable";
export { RowHandlingOptions } from "./RowHandlingOptions";
export type { RowHandlingOptionsProps } from "./RowHandlingOptions";
export { ReconcileStrip } from "./ReconcileStrip";
export type { ReconcileStripProps } from "./ReconcileStrip";
export { RuleResultsTable } from "./RuleResultsTable";
export type { RuleResultsTableProps } from "./RuleResultsTable";
export { RejectList } from "./RejectList";
export type { RejectListProps } from "./RejectList";
export { DryRunPanel } from "./DryRunPanel";
export type { DryRunPanelProps } from "./DryRunPanel";
export { Receipt } from "./Receipt";
export type { ReceiptProps } from "./Receipt";
export { RollbackNotice } from "./RollbackNotice";
export type { RollbackNoticeProps } from "./RollbackNotice";
// `P1.5` — THE RUN HISTORY, which the kit did not own until 2026-09-22. It was
// instantiated three times in three screen files while the RUNNER it lists was
// shared; the payments blueprint asked for the extraction in terms (*"Payments
// is a fourth caller, not a fourth implementation"*), so it comes through this
// one import path like every other piece of the kit.
export { ImportRunsList } from "./ImportRunsList";
export type { ImportRunsKpiCopy, ImportRunsListProps } from "./ImportRunsList";
export { WorkflowRunner } from "./WorkflowRunner";
export type { WorkflowRunnerProps } from "./WorkflowRunner";
// CR-042 / BR-MET-210 — ONE write-mode control for every import in the product.
export {
  DEFAULT_WRITE_MODE,
  WRITE_MODES,
  WriteModeField,
  WriteModeStated,
  writeModeOptions,
} from "./WriteModeChoice";
export type {
  WriteModeFieldProps,
  WriteModeId,
  WriteModeOption,
  WriteModeStatedProps,
} from "./WriteModeChoice";

export {
  ABSENT,
  WORKFLOW_COPY_KEYS,
  WORKFLOW_KINDS,
  WORKFLOW_SOURCES,
  WORKFLOW_STAGES,
  WRITING_STAGE,
  // `P1.22` — whether a target offers a rollback control at all. Exported
  // through the barrel because the PAGE asks it, and a rule a page reaches
  // into a module for is a rule two files can disagree about.
  rollbackControlIsOffered,
  // `P1.18` / `P1.19` — the same shape, for the same reason: which write modes
  // this target REFUSES, and which source cards it draws.
  workflowSourcesFor,
  writeModeIsRefused,
  writeModeRefusals,
  // `DEF-PAY-10772` — what the Transform ticks start as, per target.
  rowHandlingDefaultsFor,
} from "./kinds";
export type {
  WorkflowCopy,
  WorkflowKind,
  // `P1.18` — the per-kind rules take this, so a caller outside the kit needs
  // it to name a target at all.
  WorkflowKindId,
  WorkflowStage,
  WorkflowStageId,
} from "./kinds";

export type {
  ApprovalNote,
  DryRunFigure,
  LoadOptions,
  MappingRow,
  MappingStatus,
  ReceivedFile,
  ReconcileFigure,
  Receipt as ReceiptData,
  RejectedRow,
  RollbackPoint,
  RowHandling,
  RuleResult,
  RuleSeverity,
  SourceChoice,
  TargetColumn,
} from "./contract";
