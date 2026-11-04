import { QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, Navigate, Outlet, RouterProvider } from "react-router-dom";
import type { RouteObject } from "react-router-dom";

import { createQueryClient } from "@/api/queryClient";
import { NotBuiltYetPage } from "@/components/NotBuiltYet";
import { ScreenIdTag } from "@/components/ScreenIdTag";
import { ToastProvider } from "@/components/Toast";
import { AssetAddWizard } from "@/features/assets/AssetAddWizard";
import { AssetDetailPage } from "@/features/assets/AssetDetailPage";
import { AssetEditPage } from "@/features/assets/AssetEditPage";
import { AssetLogMaintenancePage, AssetReassignPage } from "@/features/assets/AssetFlowPages";
import { AccountImportWorkflowPage } from "@/features/customers/AccountImportWorkflow";
import { AssetImportWorkflowPage } from "@/features/assets/AssetImportWorkflow";
import { AssetRegistryPage } from "@/features/assets/AssetRegistryPage";
import { AssetRetireWizard } from "@/features/assets/AssetRetireWizard";
import { AUDIT_ROUTE, AuditLogPage, RETENTION_ROUTE } from "@/features/audit/AuditLogPage";
import { RetentionRunsPage } from "@/features/audit/RetentionRunsPage";
import { BillDetailPage } from "@/features/billing/BillDetailPage";
import { BillDocumentPage } from "@/features/billing/BillDocumentPage";
import { PendingQueuePage } from "@/features/billing/PendingQueuePage";
import { PrintBillsPage, BILLING_PRINT_ROUTE } from "@/features/billing/PrintBillsPage";
import { BILLING_PENDING_ROUTE } from "@/features/billing/billingOpsShared";
import { BulkRunPage } from "@/features/billing/bulkRun/BulkRunPage";
import { OneTimeBillPage, ONE_TIME_BILL_ROUTE } from "@/features/billing/oneTimeBill/OneTimeBillPage";
import { BillsListPage } from "@/features/billing/BillsListPage";
import { BudgetAsksPage } from "@/features/billing/BudgetAsksPage";
import { BudgetEnrolPage } from "@/features/billing/BudgetEnrolPage";
import { SettleUpForecastPage } from "@/features/billing/SettleUpForecastPage";
// `CR-094-BRC01` wave L — the correction workflow mounted OVER the account
// (`BR-CUS-1051`). The TAB, not `BillsListPage`: a clerk who pressed *Issue
// credit* on one account did not ask for every bill in the utility.
import { FixABillTab } from "@/features/billing/FixABillTab";
import { BILL_RUN_ROUTE } from "@/features/billing/billRunShared";
import {
  BILLING_ROUTE,
  BUDGET_ASKS_ROUTE,
  BUDGET_ENROL_ROUTE,
  BUDGET_FORECAST_ROUTE,
} from "@/features/billing/billingShared";
import { AnalyticsPageViews } from "@/analytics";
import { ShellWithSession } from "@/components/ShellWithSession";
import { MobileApp } from "@/features/work/mobile/MobileApp";
import { PortalApp } from "@/portal/PortalApp";
import { AGREEMENT_ROUTE, AgreementPage } from "@/portal/agreements/AgreementPage";
import { BILL_LINK_ROUTE, BillLinkPage } from "@/portal/bill-link/BillLinkPage";
import { AccountDetailPage } from "@/features/customers/AccountDetailPage";
import { AccountsListPage } from "@/features/customers/AccountsListPage";
import { CustomersListPage, CUSTOMERS_ROUTE } from "@/features/customers/CustomersListPage";
import { ChangePlanWizard } from "@/features/customers/ChangePlanWizard";
import { PaymentPlanWizard } from "@/features/customers/PaymentPlanWizard";
import { MoveInWizard } from "@/features/customers/MoveInWizard";
import { MoveOutWizard } from "@/features/customers/MoveOutWizard";
import { CloseOutPage } from "@/features/customers/CloseOutPage";
import {
  MoveRecordPage,
  MOVE_RECORD_ROUTE,
} from "@/features/customers/MoveRecordPage";
import {
  MOVE_IN_WIZARD_ROUTE,
  MOVE_OUT_WIZARD_ROUTE,
} from "@/features/customers/moveShared";
import { NewAccountWizard } from "@/features/customers/NewAccountWizard";
import {
  ACCOUNTS_ROUTE,
  ACCOUNT_IMPORT_ROUTE,
  ACCOUNT_NEW_ROUTE,
} from "@/features/customers/customersShared";
// CR-030 W4 — the SERVICE REQUEST surface (S83 · S84 · S85 + the BR-CUS-095
// checklist). `service_request_api.py` mounted 23 routes on 2026-08-24 and
// NOTHING rendered any of them, which is hard-won law 2 for the seventh time in
// this product. These four lines are the whole of the wiring.
import { ServiceRequestsListPage } from "@/features/customers/ServiceRequestsListPage";
import { BuildDetailPage } from "@/features/customers/BuildDetailPage";
import { NewConnectWizard } from "@/features/customers/NewConnectWizard";
import { ServiceRequestDetailPage } from "@/features/customers/ServiceRequestDetailPage";
import { ServiceRequestCapturePage } from "@/features/customers/ServiceRequestCapturePage";
// CR-094-BRC01 wave G — the complaint form and the service form, one component
// with two configurations.
import { JobIntakeWizard } from "@/features/customers/JobIntakeWizard";
import {
  COMPLAINT_INTAKE,
  SERVICE_INTAKE,
} from "@/features/customers/jobIntakeShared";
import { ServiceRequestDocumentSettingsPage } from "@/features/customers/ServiceRequestDocumentSettingsPage";
import {
  SERVICE_REQUESTS_ROUTE,
  SERVICE_REQUEST_DOC_SETTINGS_ROUTE,
  SERVICE_REQUEST_NEW_ROUTE,
} from "@/features/customers/serviceRequestShared";
import { CONNECTIONS_ROUTE, NEW_CONNECT_ROUTE } from "@/features/customers/newConnectShared";
import { DisconnectWizard } from "@/features/customers/DisconnectWizard";
import {
  DisconnectRecordPage,
  DISCONNECT_RECORD_ROUTE,
} from "@/features/customers/disconnect/record/DisconnectRecordPage";
import { ReconnectPage } from "@/features/customers/disconnect/reconnect/ReconnectPage";
import { RECONNECT_ROUTE } from "@/features/customers/disconnect/reconnect/reconnectEndpoints";
import { TransferWizard } from "@/features/customers/TransferWizard";
import {
  TransferRecordPage,
  TRANSFER_RECORD_ROUTE,
} from "@/features/customers/TransferRecordPage";
import {
  DISCONNECT_WIZARD_ROUTE,
  TRANSFER_WIZARD_ROUTE,
} from "@/features/customers/transferDisconnectShared";
import { SignInHelpPage } from "@/features/identity/SignInHelpPage";
import { ChangePasswordPage } from "@/features/identity/ChangePasswordPage";
import { ForgotPasswordPage } from "@/features/identity/ForgotPasswordPage";
import { SetPasswordPage } from "@/features/identity/SetPasswordPage";
import {
  FORCED_PASSWORD_CHANGE_ROUTE,
  FORGOT_PASSWORD_ROUTE,
  SET_PASSWORD_ROUTE,
  SignInPage,
} from "@/features/identity/SignInPage";
import { RevenueArPage } from "@/features/ledger/RevenueArPage";
import { CloseExportPage } from "@/features/ledger/CloseExportPage";
import { GeneralLedgerPage } from "@/features/ledger/GeneralLedgerPage";
import { RemittancePage } from "@/features/ledger/RemittancePage";
import { CostOfServicePage, COST_OF_SERVICE_ROUTE } from "@/features/ledger/CostOfServicePage";
import { FINANCE_ROUTE } from "@/features/ledger/financeShared";
import {
  JOURNAL_ENTRY_DETAIL_ROUTE,
  JournalEntryDetailPage,
} from "@/features/ledger/JournalEntryDetailPage";
import { REFUND_DETAIL_ROUTE, RefundDetailPage } from "@/features/ledger/RefundDetailPage";
import { JournalBatchPage } from "@/features/ledger/JournalBatchPage";
import { AccountLedgerReportPage } from "@/features/reports/AccountLedgerReportPage";
import { ByPremisesReportPage } from "@/features/reports/ByPremisesReportPage";
import {
  CUSTOMER_STATEMENT_ROUTE,
  CustomerStatementPage,
} from "@/features/reports/CustomerStatementPage";
import { DASHBOARD_ROUTE, DashboardPage } from "@/features/reports/DashboardPage";
import { ReportLibraryPage } from "@/features/reports/ReportLibraryPage";
import { ReportsDashboardPage } from "@/features/reports/ReportsDashboardPage";
import { RESERVED_REPORT_SEGMENTS, ReportsTabRoute } from "@/features/reports/ReportsTabRoute";
import { ReportEditorPage } from "@/features/reports/ReportEditorPage";
import { ReportViewerPage } from "@/features/reports/ReportViewerPage";
// ⚠ **NOT `RunHistoryPage` — THAT NAME IS TAKEN, BY RUNBOOKS, IN THIS FILE.**
// `@/features/runbooks/history/RunHistoryPage` is imported 133 lines below and
// mounts at `runbooks/runs`. Two identically-named default exports in one
// routing table is a bug that compiles: the second import shadows the first and
// `/reports/history` quietly serves the runbook run list. Found by grepping the
// symbol after wiring the route, which is the only thing that would have.
import { ReportRunsPage } from "@/features/reports/ReportRunsPage";
import { ScheduledTab } from "@/features/reports/ScheduledTab";
import {
  ACCOUNT_LEDGER_ROUTE,
  BY_PREMISES_ROUTE,
  REPORTS_ROUTE,
  REPORT_BUILDER_NEW_ROUTE,
  REPORT_EDITOR_ROUTE_PATTERN,
} from "@/features/reports/reportsShared";
// CR-070 wave A (2026-09-03) — the Work module is its own module (PO: "it will
// become the module itself") and `/work` is a real screen: the shell with its
// Orders tab. The templates page (CR-030 W6 task 6.14, the PO's 2026-08-25
// "keep it blank" ruling) keeps its route and now renders under the shell's
// strip until wave D replaces it.
import {
  AwaitingApprovalPage,
  WORK_AWAITING_APPROVAL_ROUTE,
} from "@/features/work/AwaitingApprovalPage";
import { OrderEditPage } from "@/features/work/OrderEditPage";
import { OrdersPage } from "@/features/work/OrdersPage";
import { WorkMapPage } from "@/features/work/WorkMapPage";
import {
  OrderDetailPage,
  WORK_ORDER_DETAIL_ROUTE,
} from "@/features/work/OrderDetailPage";
import {
  NEW_ORDER_WIZARD_ROUTE,
  NewOrderWizard,
} from "@/features/work/NewOrderWizard";
import { ACCOUNT_RAISE_ROUTE, AccountRaisePage } from "@/features/work/raise/AccountRaisePage";
import { CrewsPage } from "@/features/work/CrewsPage";
import { PartsPage } from "@/features/work/PartsPage";
import { TechnicianDetailPage } from "@/features/work/TechnicianDetailPage";
import {
  WORK_AT_RISK_ROUTE,
  WORK_MAP_ROUTE,
  WORK_ORDERS_ROUTE,
  WORK_ORDER_EDIT_ROUTE,
  WORK_CREWS_ROUTE,
  WORK_PARTS_ROUTE,
  WORK_PERFORMANCE_ROUTE,
  WORK_RULES_ROUTE,
  WORK_ROUTE,
  WorkShell,
} from "@/features/work/WorkShell";
import { PerformancePage } from "@/features/work/PerformancePage";
import { AtRiskPage } from "@/features/work/AtRiskPage";
// CR-187-BRC10 (EP-WRK-11) — `Work-034`, the office side of the field app.
import {
  FieldDeskPage,
  WORK_FIELD_ALERTS_ROUTE,
  WORK_FIELD_FINDINGS_ROUTE,
  WORK_FIELD_RAISED_ROUTE,
  WORK_FIELD_REFUSED_ROUTE,
  WORK_FIELD_ROUTE,
} from "@/features/work/field/FieldDeskPage";
// CR-070 wave M — `Work-026` and its five-step builder, plus the Assets door.
import { RulesPage } from "@/features/work/RulesPage";
import { RuleBuilder, WORK_RULE_EDIT_ROUTE } from "@/features/work/RuleBuilder";
import { RuleDetailPage, WORK_RULE_DETAIL_ROUTE } from "@/features/work/RuleDetailPage";
import {
  RAISE_WORK_ORDER_ROUTE,
  RaiseWorkOrderPage,
} from "@/features/assets/RaiseWorkOrderPage";
import { WORK_RULE_BUILDER_ROUTE } from "@/features/work/RulesPage";
import {
  LabourRatesPage,
  WORK_LABOUR_RATES_ROUTE,
} from "@/features/work/LabourRatesPage";
import {
  READ_FORMATS_ROUTE,
  READ_FORMAT_DETAIL_ROUTE,
  ReadFormatsPage,
} from "@/features/metering/ReadFormatsPage";
import { ReadFormatDetailPage } from "@/features/metering/ReadFormatDetailPage";
import { CANT_READ_REASONS_ROUTE, CantReadReasonsPage } from "@/features/metering/CantReadReasonsPage";
import {
  WORK_ORDER_TEMPLATES_ROUTE,
  TemplatesPage,
} from "@/features/work/TemplatesPage";
import {
  WORK_TEMPLATE_DETAIL_ROUTE,
  TemplateDetailPage,
} from "@/features/work/TemplateDetailPage";
// CR-070 wave E — the eight-step builder (`US-WRK-016`, `Work-014`–`017`). It
// mounts at TWO addresses: `…/templates/new` writes a template that does not
// exist yet, and `…/templates/{id}/edit` opens one that does. One component,
// because the eight steps are identical and a second copy would drift.
import {
  TemplateBuilder,
  WORK_TEMPLATE_NEW_ROUTE,
  templateEditPath,
} from "@/features/work/TemplateBuilder";
import { AddPremisesWizard } from "@/features/metering/AddPremisesWizard";
import { AddUnitsWizard } from "@/features/metering/AddUnitsWizard";
import { PremisesDetailPage } from "@/features/metering/PremisesDetailPage";
import { PremisesTabsPage } from "@/features/metering/PremisesTabsPage";
import { ReadDetailPage } from "@/features/metering/ReadDetailPage";
import { ReadsListPage } from "@/features/metering/ReadsListPage";
import { ImportWorkflowPage } from "@/features/metering/ImportWorkflowPage";
import { RouteReadsPage } from "@/features/metering/RouteReadsPage";
import { ReadCycleDetailPage } from "@/features/metering/ReadCycleDetailPage";
import { RedirectToReadCycles } from "@/features/metering/ReadCyclesTab";
import { UnitDetailPage } from "@/features/metering/UnitDetailPage";
import { UploadReadsWizard } from "@/features/metering/UploadReadsWizard";
import { READS_ROUTE, READS_UPLOAD_ROUTE } from "@/features/metering/readsShared";
import { BankImportWizard } from "@/features/payments/BankImportWizard";
import { CollectionsPage } from "@/features/payments/CollectionsPage";
import { DepositBatchPage } from "@/features/payments/DepositBatchPage";
import { DepositsPage } from "@/features/payments/DepositsPage";
import { MyCounterPage } from "@/features/payments/MyCounterPage";
import { DebtorPage } from "@/features/payments/DebtorPage";
import { PaymentsPage } from "@/features/payments/PaymentsPage";
import { PaymentsSegmentRoute } from "@/features/payments/PaymentDetailPage";
import { RecordPaymentPage } from "@/features/payments/RecordPaymentPage";
import { ReconciliationStatementPage } from "@/features/payments/ReconciliationStatementPage";
import { SettlementPage } from "@/features/payments/SettlementPage";
import { RefundsLegacyRedirect, RefundsPage } from "@/features/payments/RefundsPage";
import { SEND_NOTICE_ROUTE, SendNoticeWizard } from "@/features/payments/SendNoticeWizard";
import {
  DEPOSITS_IMPORT_ROUTE,
  DEPOSITS_ROUTE,
  DEPOSITS_STATEMENT_ROUTE,
} from "@/features/payments/depositsShared";
import { COLLECTIONS_ROUTE } from "@/features/payments/CollectionsPage";
import {
  PAYMENTS_ROUTE,
  REFUNDS_LEGACY_ROUTE,
  REFUNDS_ROUTE,
} from "@/features/payments/paymentsShared";
import { PricingPage } from "@/features/public/PricingPage";
import { ChargeCodeDetailPage } from "@/features/rating/ChargeCodeDetailPage";
import { ChargeCodeWizard } from "@/features/rating/ChargeCodeWizard";
import { DefinitionDetailPage } from "@/features/rating/DefinitionDetailPage";
import { PlanDetailPage } from "@/features/rating/planDetail/PlanDetailPage";
import { PlansRatesPage } from "@/features/rating/PlansRatesPage";
import { RateScheduleDetail } from "@/features/rating/RateScheduleDetail";
import { RateScheduleWizard } from "@/features/rating/RateScheduleWizard";
import { EditTaxForm } from "@/features/rating/taxForm/EditTaxForm";
import { NewTaxWizard } from "@/features/rating/taxForm/NewTaxWizard";
import { EditDiscountForm } from "@/features/rating/discountForm/EditDiscountForm";
import { NewDiscountWizard } from "@/features/rating/discountForm/NewDiscountWizard";
import { EditPlanForm } from "@/features/rating/planForm/EditPlanForm";
import { NewPlanForm } from "@/features/rating/planForm/NewPlanForm";
import {
  TAX_WIZARD_EDIT_PATTERN,
  TAX_WIZARD_NEW_ROUTE,
} from "@/features/rating/definitionDetail";
import { ChecklistPage } from "@/features/tenancy/ChecklistPage";
import { RunbookSetupPage } from "@/features/runbooks/RunbookSetupPage";
import { RunResultPage } from "@/features/runbooks/RunResultPage";
import { RunWizardPage } from "@/features/runbooks/run/RunWizardPage";
import { WorkListPage } from "@/features/runbooks/work/WorkListPage";
// ⚠ **NAMED `Runbook…` RATHER THAN ALIASED HERE.** `features/work/
// TemplateDetailPage` already exports `TemplateDetailPage`, and `tsc` refused
// the collision by name at this line. An alias would have compiled and would
// have left two different `TemplateDetailPage`s in one file — the shape the
// `ConnectionDetailPage` note below records outliving its own clash. The
// runbooks components carry the longer name at their own definition instead.
import {
  RunbookTemplateDetailPage,
  RunbookTemplateLibraryPage,
} from "@/features/runbooks/library/TemplateLibraryPage";
import { MyRunbooksPage } from "@/features/runbooks/library/MyRunbooksPage";
import { RunbooksHomePage } from "@/features/runbooks/home/RunbooksHomePage";
import { RunHistoryPage } from "@/features/runbooks/history/RunHistoryPage";
import { CycleDetailPage } from "@/features/tenancy/CycleDetailPage";
import { RouteDetailPage } from "@/features/tenancy/RouteDetailPage";
// ⚠ ALIASED, AND THE ALIAS OUTLIVED THE CLASH IT WAS WRITTEN FOR. Until
// 2026-09-04 `features/customers/ConnectionDetailPage` (S88 · NCT-02, a
// customer's service connection) held this name one directory away; CR-070
// wave O deleted that file, so nothing collides today. The alias STAYS because
// it is the honest name: the integrations one is a PROVIDER connection — a
// mail server, a bank file — and that is what every route around it calls it.
import { ConnectionDetailPage as IntegrationDetailPage } from "@/features/integrations/ConnectionDetailPage";
import { ValueMappingPage } from "@/features/integrations/ValueMappingPage";
import { MachineKeysPage } from "@/features/integrations/MachineKeysPage";
import { ConnectorSetupPage } from "@/features/integrations/ConnectorSetupPage";
import { CycleWizardPage, RouteWizardPage } from "@/features/tenancy/RoutesCyclesWizardPages";
import {
  LEGACY_SETTINGS_TAB_PATHS,
  LegacyNotificationsRedirect,
  LegacySettingsTabRedirect,
  SettingsPage,
} from "@/features/tenancy/SettingsPage";
import { SignupWizard } from "@/features/tenancy/SignupWizard";
import {
  HOME_ROUTE,
  PRICING_ROUTE,
  SIGNIN_HELP_ROUTE,
  SIGNIN_SEGMENT,
  SIGNUP_ROUTE,
  TENANT_PARAM,
} from "@/routing/tenantPath";

// THE CATCH-ALL. Module screens arrive with their own story packets as children
// of the shell route; until one lands, its address renders `NotBuiltYetPage`.
//
// It used to render `<p>{t("w0.scaffold")}</p>` — the literal developer string
// "SMARTBillHub — W0 scaffold" — and that string reached a real user TWICE:
// DEF-129 on `/{tenant}/dashboard`, the first screen after every sign-in, and
// DEF-152 on `/{tenant}/reports`, a sidebar item one click from anywhere. The
// distinction neither instance drew is the whole fix: *"this screen is not
// built yet" is a legitimate state; "SMARTBillHub — W0 scaffold" is not a way
// to say it.* See `components/NotBuiltYet.tsx` for what is rendered instead and
// for the register of sidebar destinations that knowingly land here.
//
// Do not grow this file ahead of those packets — but DO NOT reach for a
// placeholder string either: an unrouted path is a user-facing state and gets
// the product's own voice, through the catalogues, like everything else.

// FI-02: one QueryClient with the ratified defaults (no retry layer on top of
// the transport's, no optimistic money writes).
const queryClient = createQueryClient();

// PO ruling 2026-08-10 — TENANCY IS PATH-BASED, so the route table has three
// groups instead of two:
//   · PUBLIC (root, no tenant) — pricing, signup (POST /api/tenants) and the
//     tenant-less `/signin-help` landing. The shell chrome must not frame them:
//     there is no tenant, and no session, behind them.
//   · PER-TENANT, OUTSIDE the shell — `/{tenant}/signin` (S3). It is inside the
//     tenant segment because the tenant is what the sign-in resolves against
//     (BR-IDN-001, source now the path), and outside the shell because there is
//     no session to frame yet.
//   · PER-TENANT, INSIDE the shell — every authenticated screen, as children of
//     FE-01 AppShell's <Outlet/>, with the S62 checklist at
//     `/{tenant}/checklist`. That IS where the S114 commit now lands: with one
//     origin the backend signs the owner in at provisioning, so BR-TEN-045's
//     cross-host success screen is obsolete (PO 2026-08-10).
// The child paths below stay written TENANT-RELATIVE — the `/:tenant` parent
// supplies the segment once, exactly as `tenantPath()` does for every link.
// Route-level RBAC/auth guards are FI-04 / EP-SHL-06 — not invented here.
// /change-password (BR-IDN-022's forced-change screen, US-IDN-002's packet) IS
// BUILT AND IS MOUNTED BELOW, as a sibling of `signin` — outside the shell,
// which is what the paragraph this replaces asked for and what `DEF-IDN-5653`
// cost while nothing did it.
//
// ⚠ **THE OLD PARAGRAPH WAS RIGHT AND STILL LET EVERY INVITED USER BE LOCKED
// OUT**, which is worth a sentence because it is hard-won law 1 exactly: it
// said the address *"currently falls through to the catch-all, which now tells
// the user in plain English that the screen is not built"*, and *"When that
// screen lands it must render OUTSIDE the shell, since it gates every app
// screen."* Both halves were true when written. The FIRST stopped being the
// whole truth the moment the catch-all moved inside the shell: `SignInPage`
// sends a temp-password holder here, the shell tries to boot, and every read it
// makes is refused 403 while a change is owed (`identity/auth.py`
// `_FORCED_CHANGE_EXEMPT`) — so the user got neither the screen nor the plain
// English, but *"We couldn't load your regional settings."* and a Retry button
// that could never work. A comment describing a destination is not the
// destination; the route below is.
// Exported so the route table itself is testable (a deep link must render its
// screen with the tenant in scope) without a browser history.
export const APP_ROUTES: RouteObject[] = [
  { path: HOME_ROUTE, element: <PricingPage /> },
  { path: PRICING_ROUTE, element: <Navigate to={HOME_ROUTE} replace /> },
  { path: SIGNUP_ROUTE, element: <SignupWizard /> },
  // The ruling names this public path; A1 has no screen for it (S2's "First
  // time / Sign in" fork is the nearest), and none is invented — no ID is
  // claimed here. (The first sentence of this comment used to say the route
  // "renders the W0 marker"; it has not since 2026-08-10 and the correction is
  // US-IDN-011's — hard-won law 1.)
  // Was <ModulePlaceholder/> until 2026-08-10, which rendered the literal
  // "SMARTBillHub — W0 scaffold" on a PUBLIC page — found by the PO on the first
  // real deployment. It now builds a `/{tenant}/signin` URL from the address the
  // utility chose at signup, and deliberately performs no lookup: see the file
  // header for why every lookup here is a membership oracle. OQ-078 owns the
  // "I don't remember our address" path.
  { path: SIGNIN_HELP_ROUTE, element: <SignInHelpPage /> },
  {
    path: `/:${TENANT_PARAM}`,
    children: [
      { path: SIGNIN_SEGMENT.slice(1), element: <SignInPage /> },
      // DEF-IDN-5653 — the forced password change, a SIBLING of `signin` and
      // deliberately NOT a child of `ShellWithSession` below. BR-IDN-022 gates
      // every app screen behind this one, so the shell must not be the thing
      // that renders it: while the flag is set the server refuses every read
      // the shell boots on, and the frame dies before the form inside it can
      // appear. It is inside `/:tenant` for the same reason sign-in is — the
      // session, and the password policy it will be judged against, belong to
      // THIS tenant.
      // ⚠ THE PATH IS `SignInPage`'S OWN CONSTANT — the one the redirect reads —
      // rather than a second spelling of the same address. That is the whole
      // defect made impossible: a door and its destination that are two
      // separate strings can disagree, and for eight days they did.
      { path: FORCED_PASSWORD_CHANGE_ROUTE.slice(1), element: <ChangePasswordPage /> },
      // CR-170-BRC10 (BR-IDN-023 as amended 2026-10-05) — the forgot-password
      // page, PUBLIC and signed out, so a sibling of `signin` like the forced
      // change and for the same reason: there is no session to frame it. The
      // path is `SignInPage`'s own constant, the one its link reads.
      { path: FORGOT_PASSWORD_ROUTE.slice(1), element: <ForgotPasswordPage /> },
      // CR-188-BRC10 (PO 2026-10-22) — where an emailed one-time sign-in link
      // lands. Public and signed out, so a sibling of `signin` for the same
      // reason as the two above.
      { path: SET_PASSWORD_ROUTE.slice(1), element: <SetPasswordPage /> },
      // CR-068 wave A (2026-09-03): THE CUSTOMER PORTAL — a second application
      // root at `/{tenant}/portal/*` (PO ruling R11: *"/{utility-name}/portal/…
      // - we will use this"*), a SIBLING of the staff shell and never inside
      // it: it shares no session, no role model and no navigation with the
      // staff app (BR-CWP-011). The bare `/{tenant}` stays the staff app's
      // dashboard redirect (CR-068 §0 row 3). Its own routes and its own
      // screen register live under src/portal/; the staff map below records
      // this address as `noScreen: "own-register"`.
      // CR-190-BRC10 (2026-10-22) — the agreement link's page, BESIDE the
      // portal and never inside it (PO answer 4: *"No"* to accepting in the
      // signed-in portal). More specific than `portal/*`, so it is matched
      // first; it wears the guest frame and opens whether or not the portal is
      // live.
      { path: AGREEMENT_ROUTE, element: <AgreementPage /> },
      // DEF-BIL-10531 (2026-10-22) — the bill email's direct PDF link, beside
      // the portal for the agreement page's reason: no sign-in, guest frame.
      { path: BILL_LINK_ROUTE, element: <BillLinkPage /> },
      { path: "portal/*", element: <PortalApp /> },
      // CR-070 wave J (2026-09-05): THE TECHNICIAN'S PHONE — a THIRD
      // application root at `/{tenant}/work/mobile/*` (`BR-WRK-045`, the
      // decision-log row of 2026-09-03: *a manifest, a service worker and an
      // offline store served by the staff app's own build*).
      //
      // ⚠ A SIBLING OF THE STAFF SHELL, LIKE THE PORTAL, AND FOR THE SAME
      // REASON: it has no sidebar, no global search and no page header, and a
      // phone in a meter pit must not download or render any of them.
      // ⚠ BUT UNLIKE THE PORTAL IT SHARES THE SESSION. `OQ-WRK-1494` closed
      // 2026-09-04 with one `users` table and a `surface_scope` column — the
      // surface a login may use is a property of the login, never a reason for
      // a second identity. A field technician's WEB sign-in is refused at
      // sign-in; the phone is what their login is for.
      //
      // It must sit ABOVE the `ShellWithSession` layout route below, or
      // `work/mobile` is matched by the staff app's `/work` family and a
      // technician gets the dispatcher.
      { path: "work/mobile/*", element: <MobileApp /> },
      {
        // A layout route: no path of its own, so every child below hangs
        // directly off `/{tenant}/`.
        // ShellWithSession, not AppShell directly: the shell needs a session
        // to show who you are and to let you leave. Rendering <AppShell/> bare
        // is why there was no sign-out anywhere until 2026-08-10 (US-SHL-005).
        element: <ShellWithSession />,
        children: [
          // `/{tenant}` alone is the tenant's home — BR-SHL-001's first nav
          // item, the Dashboard. Relative, so the tenant rides along.
          //
          // S7 (US-REP-019), added 2026-08-16. **THIS REDIRECT POINTED AT
          // NOTHING** until this commit: there was no route with path
          // `dashboard`, so `/{tenant}` and the sidebar's first item both fell
          // through `path: "*"` below to `ModulePlaceholder` and rendered the
          // literal string "SMARTBillHub — W0 scaffold" — the first screen after
          // every single sign-in (DEF-129). It survived every E2E journey
          // because `bootApp()` waited for the SIDEBAR, which renders perfectly.
          // Hard-won law 8 for the second time: a screen named in the inventory
          // that no story owned, so it was nobody's to build and nobody's to
          // notice. `10-scripts/gates/g25_screen_coverage.py` is the check that
          // now goes red on the third one.
          { index: true, element: <Navigate to="dashboard" replace /> },
          { path: DASHBOARD_ROUTE.slice(1), element: <DashboardPage /> }, // S7
          { path: "checklist", element: <ChecklistPage /> },
          // RBS-001 · S147 — the Runbooks home, and the screen the PO's nav
          // item opens. CR-075 wave D task `D2`.
          //
          // ⚠ **THIS LINE RELEASED A HOLD, AND THE HOLD LEFT IN THE SAME
          // COMMIT.** Until it existed, `/{tenant}/runbooks` fell through to
          // the catch-all and `UNBUILT_SIDEBAR_DESTINATIONS` carried a dated
          // `/runbooks` row saying so — this comment block said so too, in the
          // present tense, until D2 landed. Releasing the pointer and landing
          // the screen are two acts and only the first feels like the work,
          // which is `DEF-CWP-3925` exactly (the customer portal shipped a
          // front page with two working doors out of eight).
          // `features/runbooks/navHoldExpiry.test.tsx` is the clock that fired
          // on this; its assertions were TURNED AROUND rather than deleted and
          // now assert `RBS-001` DOES render here, by address and by screen id.
          //
          // ⚠ **AN ORDINARY PATH, NOT `index: true`.** React Router does not
          // match `/runbooks` against `/runbooks/:key`, so the home needs its
          // own entry; an index route on this level would claim `/{tenant}`,
          // which the dashboard redirect above already owns.
          { path: "runbooks", element: <RunbooksHomePage /> }, // RBS-001 · S147
          // RBS-004 · S150 — one runbook's definition, seven tabs. CR-075 wave
          // C task C3.
          // ── CR-075 wave D tasks D3 and D4 — the library and the list ──────
          //
          // ⚠ **THE SHEETS WRITE THESE ROUTES WITH AN `operations` SEGMENT AND
          // THE PRODUCT'S WORD IS `runbooks`.** `08-screen-layouts.md` gives
          // `silvercreek / operations / templates` and `… / operations /
          // runbooks`, and the same file records why that word is not the
          // address: *"The routes and the seam names in the source say
          // `operations`; … the product word is **Runbooks** (PO 2026-09-06:
          // *we coin the word Runbooks*)."* Wave C already read it that way when
          // it mounted `RBS-004` at `runbooks/:key` rather than at
          // `operations/runbooks/:key`. So `operations` → `runbooks`, once, for
          // every screen in the module. The decision log of 2026-09-06 carries
          // the reasoning.
          //
          // ⚠ **AND `runbooks` ITSELF IS LEFT ALONE BY THESE THREE, WHICH IS
          // WHY THEY AND `D2` COULD LAND WITHIN THE HOUR OF EACH OTHER.** It is
          // the rail's destination and `RBS-001`'s address; `D2` mounts it a
          // few lines above. This note read *"held over the not-built-yet
          // screen"* until that landed. `My runbooks` is therefore
          // `runbooks/mine`, which is also the screen's own title.
          //
          // ⚠ **STATIC SEGMENTS BEAT `:key`, AND THE BACKEND HAS THIS EXACT
          // COLLISION.** `apps/runbooks/api.py` registers `runbooks/templates`
          // BEFORE `runbooks/<str:key>` and says why in a header of its own:
          // `integrations/subprocessors` shipped read as a provider key and
          // answering 405 under a comment that had asserted the collision away.
          // React Router v6 ranks by specificity rather than array position, so
          // these win wherever they sit — they are written above `:key` so a
          // reader sees the three together, and the tests ask the ROUTER rather
          // than trusting this paragraph.
          { path: "runbooks/templates", element: <RunbookTemplateLibraryPage /> }, // RBS-002.1 · S148
          { path: "runbooks/templates/:key", element: <RunbookTemplateDetailPage /> }, // RBS-002.2
          { path: "runbooks/mine", element: <MyRunbooksPage /> }, // RBS-003 · S149
          // RBS-008 · S154 — run history across every runbook. CR-075 wave I
          // task I6. ⚠ **THE SHEET'S ROUTE IS `silvercreek / operations / runs`
          // AND THE PRODUCT'S WORD IS `runbooks`** — the same `operations` →
          // `runbooks` translation the three routes above carry, recorded once
          // in `08-screen-layouts.md` and applied here rather than re-argued.
          // ⚠ **AND `runs` IS STATIC, SO IT BEATS `:key` WHEREVER IT SITS** —
          // React Router v6 ranks by specificity, not by array position, which
          // is the same reason `runbooks/mine` and `runbooks/templates` are
          // safe. It is written above `:key` so a reader sees the four
          // together, and the test asks the ROUTER rather than trusting this
          // paragraph.
          { path: "runbooks/runs", element: <RunHistoryPage /> }, // RBS-008 · S154
          // ── CR-075 wave H task H3 — the work list ────────────────────────
          //
          // ⚠ **THE SHEET'S ROUTE IS `silvercreek / operations / work` AND
          // `/{tenant}/work` IS TAKEN.** It belongs to the WORK MODULE — crews,
          // work orders, parts — which is a different thing with a confusingly
          // similar name, and `models.py`'s own docstring says so: *"`work_items`
          // is not the `work` module's table, and the names are not a
          // coincidence."* So `operations` → `runbooks`, exactly as the three
          // routes above resolved the same clash, and the address is
          // `runbooks/work`.
          //
          // ⚠ **A TENANT COULD NAME A RUNBOOK *Work*, AND THIS ROUTE WOULD WIN
          // — STATED RATHER THAN ASSUMED AWAY.** `services._slug` would mint
          // the key `work`, and React Router v6 ranks a static segment above
          // `:key` wherever either sits, so that runbook's setup screen would
          // be unreachable at its own address while every other one worked.
          // Nothing in the product reserves the word today. It is written down
          // here because the failure is silent, and `screenIds.test.tsx` asks
          // the ROUTER which pattern wins rather than trusting this paragraph.
          { path: "runbooks/work", element: <WorkListPage /> }, // RBS-007 · S153
          { path: "runbooks/:key", element: <RunbookSetupPage /> }, // RBS-004 · S150
          // RBS-004.run — the Check wizard, and the ONE way a run starts
          // (`OQ-WRK-12792` → A, PO 2026-10-13; `DEF-WRK-10123`). Built in
          // CR-075 wave C task C4 and unrouted until this line; the setup
          // page's pop-up that started runs instead was deleted in the same
          // change. A dotted sub-id of the runbook it runs, never an A1 number.
          { path: "runbooks/:key/run", element: <RunWizardPage /> }, // RBS-004.run
          // ⚠ **MORE SPECIFIC, AND ORDER DOES NOT SAVE IT.** React Router v6
          // ranks by specificity rather than by array position, so
          // `runbooks/:key/runs/:runId` wins over `runbooks/:key` wherever it
          // sits — but it is written after it anyway so a reader sees the two
          // together. `RunResult.dom.test.tsx` mounts this exact pattern,
          // because a component mounted bare gets `undefined` from
          // `useParams()` and builds every address as `//host/…` (DEF-CWP-3925).
          { path: "runbooks/:key/runs/:runId", element: <RunResultPage /> }, // RBS-006 · S152
          // S8 Settings. `:tab?` keeps every tab linkable and `:sub?` does the
          // same for Company's second-level strip ("Company profile" /
          // "Regional, formats & fiscal calendar"), which the prototype nests
          // inside the Company tab body.
          //
          // The S62 checklist's deep-link targets are SERVER data
          // (apps/tenancy/selectors.py CHECKLIST_TARGETS): "settings/company",
          // "settings/regional", "settings/services", "settings/number-series",
          // "settings/users". Four still name a tab; `settings/regional` names
          // a tab that MOVED, so it gets a redirect to its new home rather than
          // being dropped — a moved tab that breaks a live checklist link is a
          // worse defect than the divergence it fixed. The redirects are
          // generated from LEGACY_SETTINGS_TAB_PATHS so the map and the route
          // table cannot drift; each is an all-static path, which React Router
          // ranks above `settings/:tab`.
          ...Object.keys(LEGACY_SETTINGS_TAB_PATHS).map((tab) => ({
            path: `settings/${tab}`,
            element: <LegacySettingsTabRedirect tab={tab} />,
          })),
          // ── CR-029 RC-W3 · Routes & Cycles, addressable ────────────────
          // ⚠ **ALL SIX ARE ALL-STATIC-PLUS-ONE-ID AND SIT ABOVE
          // `settings/:tab/:sub`**, which they cannot collide with anyway —
          // React Router matches path SEGMENT COUNT, and these are four and
          // five deep against that route's three. They are declared here
          // rather than inside `SettingsPage` for the reason W3-T5 exists:
          // SET-06/07 were `useState` inside the landing tab, so a refresh
          // three steps into a wizard lost 140 picked premises (BR-SHL-011
          // requires a URL for every other stateful surface in this product),
          // and SET-06D/SET-07D are whole screens rather than tab bodies.
          //
          // ⚠ AND `new` IS DECLARED BEFORE `:routeId`. React Router ranks a
          // static segment above a dynamic one, so the order is belt and
          // braces — but the premises runner routes learned this the hard way
          // (DEF-520) and writing it down costs nothing.
          // ── CR-030 W4 · BR-CUS-095's document checklist ────────────────
          // *"Settings grows a checklist — for each request type, tick which
          // documents are required. We ship with nothing ticked, and a utility
          // that configures nothing blocks nothing."* System Admin only,
          // server-side. THREE segments and all-static up to the last, so React
          // Router ranks it above `settings/:tab/:sub` — the same ranking the
          // routes-cycles block below relies on. It is a route rather than a
          // tab body because `SettingsPage.tsx` owns the Configure strip and
          // belongs to another lane in this shared tree today (SET-06D's own
          // precedent); folding it in is one line and is OWED.
          {
            path: SERVICE_REQUEST_DOC_SETTINGS_ROUTE.slice(1),
            element: <ServiceRequestDocumentSettingsPage />,
          },
          // CR-070 wave N — `Work-030`, `US-WRK-051`. A Settings reference-data
          // card, because a labour rate is configuration a supervisor sets once
          // rather than a list a dispatcher works from.
          {
            path: WORK_LABOUR_RATES_ROUTE.slice(1),
            element: <LabourRatesPage />,
          }, // WRK-17
          // CR-192-BRC10 (MQ-033 task 11) — Settings → Reads → Read formats, a
          // READS reference-data card that opens a screen of its own (the
          // labour-rates precedent above). Three segments + a static word, so
          // React Router ranks both above `settings/:tab/:sub`.
          {
            path: READ_FORMATS_ROUTE.slice(1),
            element: <ReadFormatsPage />,
          }, // SET-04.readFormats
          {
            path: READ_FORMAT_DETAIL_ROUTE.slice(1),
            element: <ReadFormatDetailPage />,
          }, // SET-04.readFormatDetail
          // DEF-MET-10609 (decision log 2026-10-26) — the one can't-read reason
          // list, the READS card beside Read formats.
          {
            path: CANT_READ_REASONS_ROUTE.slice(1),
            element: <CantReadReasonsPage />,
          }, // SET-04.cantReadReasons
          {
            path: "settings/reference-data/routes-cycles/routes/new",
            element: <RouteWizardPage />, // SET-06.1–4, create
          },
          {
            path: "settings/reference-data/routes-cycles/routes/:routeId/edit",
            element: <RouteWizardPage />, // SET-06.1–4, edit — PRE-FILLED
          },
          {
            path: "settings/reference-data/routes-cycles/routes/:routeId",
            element: <RouteDetailPage />, // SET-06D
          },
          {
            path: "settings/reference-data/routes-cycles/cycles/new",
            element: <CycleWizardPage />, // SET-07.1–4, create
          },
          {
            path: "settings/reference-data/routes-cycles/cycles/:cycleId/edit",
            element: <CycleWizardPage />, // SET-07.1–4, edit — PRE-FILLED
          },
          {
            path: "settings/reference-data/routes-cycles/cycles/:cycleId",
            element: <CycleDetailPage />, // SET-07D
          },
          // ── CR-110-BRC04 wave A · S147, the connector SET-UP screen ──────
          // FOUR segments, so React Router ranks it above `settings/:tab/:sub`
          // on specificity — the same fact the mappings and access routes
          // above rely on.
          //
          // ⚠ **`connectors`, NOT `integrations`, AND THE TWO WORDS COEXIST ON
          // PURPOSE.** The 16 Sep route ruling keeps `settings/integrations`
          // and `…/:key` where they are, because changing a shipped address
          // breaks every bookmark to buy a word in a place nobody reads for
          // meaning. This screen has no shipped address to protect — it did not
          // exist — so it takes the word the PO ruled visible everywhere and
          // the blueprint draws on all 28 frames.
          //
          // ⚠ **THE PARAM IS `:providerKey` AND NOT `:key`**, which is the name
          // the blueprint's own address bar uses. It is also the name
          // `ConnectorSetupRoute.test.tsx` asserts through, so a lane renaming
          // it here without renaming it there goes red rather than silently
          // handing the screen an undefined provider.
          {
            path: "settings/connectors/:providerKey/configure",
            element: <ConnectorSetupPage />, // INT-07 · S147
          },
          // ── CR-069 wave R · S144, the keys we issue ──────────────────────
          // Four segments, so React Router ranks it above `settings/:tab/:sub`
          // for the same reason the mappings route below does. `INT-04` was
          // ALLOCATED against this exact path in g29_allocated_badges.txt by
          // wave D, months before the screen existed; this is the wave that
          // mounts it, and the address is taken from that file rather than
          // chosen here.
          {
            path: "settings/integrations/:key/access",
            element: <MachineKeysPage />, // INT-04 · S144
          },
          // ── CR-069 wave D · S143, their words for our things ─────────────
          // Four segments, so React Router ranks it above `settings/:tab/:sub`
          // on segment count alone (the routes-cycles block above relies on the
          // same fact). A route rather than a tab body for BR-SHL-011's reason:
          // a mapping editor a clerk returns to needs a URL of its own.
          {
            path: "settings/integrations/:key/mappings",
            element: <ValueMappingPage />, // INT-03 · S143
          },
          // ── CR-069 wave C · S142, the connection detail ──────────────────
          // THREE segments, and it is written AFTER the four-segment mappings
          // route above for readability only: React Router ranks by
          // specificity and not by order, so `…/:key/mappings` wins over
          // `…/:key` wherever the two are written. Asserted in
          // ConnectionDetailPage.test.tsx rather than left to that reading.
          {
            path: "settings/integrations/:key",
            element: <IntegrationDetailPage />, // INT-02 · S142
          },
          // CR-068 wave A (2026-09-03): Settings → Configure → Customer portal's
          // OWN strip — Overview · Branding (CWP-069 · CWP-070). Four segments,
          // all-static plus one id, so React Router ranks it above
          // `settings/:tab/:sub`; SettingsPage reads `segment` back into
          // tab/sub, so one frame serves a third level rather than a second frame.
          {
            path: "settings/reference-data/customer-portal/:segment",
            element: <SettingsPage configureSub="customer-portal" />,
          },
          // 2026-10-22 — Settings → Configure → Notifications, next to
          // Templates (PO: *"Settings → Configure → Notifications, sitting next
          // to Templates - this is correct understanding"*). Its own strip
          // (`messages`, `blocked`) and every rule page (`<event key>`) are the
          // fourth segment, the same shape as the portal segment above.
          {
            path: "settings/reference-data/notifications/:segment",
            element: <SettingsPage configureSub="notifications" />,
          },
          // …and every old `/settings/notifications/<sub>` lands on its new
          // home. Three segments, all-static up to the last, so React Router
          // ranks it above `settings/:tab/:sub`. The two-segment
          // `/settings/notifications` redirects through
          // LEGACY_SETTINGS_TAB_PATHS above.
          {
            path: "settings/notifications/:sub",
            element: <LegacyNotificationsRedirect />,
          },
          { path: "settings", element: <SettingsPage /> },
          { path: "settings/:tab", element: <SettingsPage /> },
          { path: "settings/:tab/:sub", element: <SettingsPage /> },
          // S61 audit log (OQ-029 CLOSED). This is the exact path S8 Security's
          // "View audit log →" already navigates to — the button stops landing
          // on the placeholder. Role gating is the SERVER's (BR-AUD-009: System
          // Admin + Executive); the screen renders A18 §6 on its own 403.
          { path: AUDIT_ROUTE.slice(1), element: <AuditLogPage /> },
          // US-MET-020 / US-AUD-007 — "has data retention ever run?". Its
          // `archive_job_runs` ledger existed in a migration, a command and
          // core/archival.py and in no api.py anywhere, so an operator under a
          // 7-year obligation could not answer the question. A ROUTE rather
          // than a tab: a compliance answer gets sent as a link into a ticket.
          // Declared BEFORE nothing else — `/audit-log/{id}` is a drawer on the
          // list's own URL, so there is no id segment this can collide with.
          { path: RETENTION_ROUTE.slice(1), element: <RetentionRunsPage /> },
          // S9–S13 Plans & Rates. The four tab paths are exactly SHELL_NAV's
          // `plans-rates` children (BR-SHL-001), so the sidebar sub-items land
          // on the right tab; `history` is the fifth tab, reachable from the S9
          // tab strip only (the ratified sidebar lists four — reported).
          // The two wizards are their own routes so a half-built plan or
          // schedule is linkable and a browser Back leaves the wizard.
          // ⚠ CR-167-BRC10 round 2 task 5: the NEW door opens the redrawn
          // five-step form (`planForm/NewPlanForm.tsx`, images 04–23). Round 3
          // task 8: the EDIT door below opens the SAME steps with *What to
          // change* on top (`planForm/EditPlanForm.tsx`, images 37–44), and
          // `PlanWizard.tsx` is retired.
          { path: "plans-rates/plans/new", element: <NewPlanForm /> },
          // PLN-02 is what a plan's NAME opens (CR-013 part 5, and r10's
          // `prView: 'plan'`), so the detail owns `…/plans/:planId` and the
          // PLN-03 builder moves one segment down into `/edit` — the same
          // move RAT-02 made below, for the same reason. `PlansTab`'s row
          // pencil already points at `planEditRoute`, so neither door is left
          // pointing at a route that no longer exists (hard-won law 2).
          // ⚠ CR-167-BRC10 round 3 task 7: the details page redrawn from images
          // 24–37 — six tabs (`planDetail/PlanDetailPage.tsx`); the old
          // `PlanDetail.tsx` is retired.
          { path: "plans-rates/plans/:planId", element: <PlanDetailPage /> },
          { path: "plans-rates/plans/:planId/edit", element: <EditPlanForm /> },
          { path: "plans-rates/rates/new", element: <RateScheduleWizard /> },
          // RAT-02 is what a schedule's NAME opens (CR-013 part 1, and r10's
          // `prView: 'rate'`), so the detail owns `…/rates/:tariffId` and the
          // RAT-03 wizard moves one segment down into `/edit`. The wizard used
          // to own the bare id; nothing outside `RateSchedulesTab` linked to it
          // (`e2e/T4-07.spec.ts` reads the version chain, which is now this
          // screen's Versions & filings tab).
          { path: "plans-rates/rates/:tariffId", element: <RateScheduleDetail /> },
          { path: "plans-rates/rates/:tariffId/edit", element: <RateScheduleWizard /> },
          // CR-013 rows 8 · 11 · 14 — the shared definition detail. BR-RAT-084
          // (PO ruling 2026-08-20): ONE component behind THREE routes with
          // THREE screen ids, *"so a walkthrough can evidence each and a deep
          // link resolves"*. The kind is a PROP, not a URL guess — the route
          // is the kind. Ranked above `plans-rates/:tab` by segment count, so
          // `/plans-rates/charge-codes` is still the landing tab.
          // CR-013 row 9 — CHG-02, the New/Edit CHARGE CODE wizard. PO ruling
          // 2026-08-20: *"Wizards for each type - no modal"*, so this is a
          // ROUTE and not a dialog, and a half-filled charge code is linkable
          // and a browser Back leaves it. `new` and `…/edit` are STATIC
          // segments, so React Router ranks them above `:definitionId` exactly
          // as it does for `rates/new` — the detail below still owns the bare
          // id.
          { path: "plans-rates/charge-codes/new", element: <ChargeCodeWizard /> },
          { path: "plans-rates/charge-codes/:definitionId/edit", element: <ChargeCodeWizard /> },
          {
            path: "plans-rates/charge-codes/:definitionId",
            // CR-156-BRC10 wave B — CHG-01 rebuilt from its images: View
            // details varies by KIND (PO 2026-10-01), so the charge route has
            // its own page; discounts and taxes keep the shared one below.
            element: <ChargeCodeDetailPage />,
          },
          // CR-013 row 12 — DIS-02, the New/Edit DISCOUNT wizard. Same ranking
          // argument as the charge-code pair above: `new` and `…/edit` are
          // STATIC segments, so React Router puts them ahead of `:definitionId`
          // and the bare id still resolves to the detail.
          // CR-166-BRC10 round 2 task 4 (2026-10-03): the NEW door opens the
          // redrawn three-step form (`discountForm/NewDiscountWizard.tsx`,
          // images 05–18). CR-166-BRC10 round 3 task 7: the EDIT door opens the
          // same form with *What to change* on top (`discountForm/
          // EditDiscountForm.tsx`, images 27–36, `?change=info|change|correct`);
          // `DiscountWizard.tsx` is retired.
          { path: "plans-rates/discounts/new", element: <NewDiscountWizard /> },
          { path: "plans-rates/discounts/:definitionId/edit", element: <EditDiscountForm /> },
          {
            path: "plans-rates/discounts/:definitionId",
            element: <DefinitionDetailPage kind="discount" />,
          },
          // CR-013 P4 — TAX-02, the New/Edit tax or fee wizard (inventory §18
          // row 15). PO 2026-08-20: *"Wizards for each type - no modal;"*, so
          // this is a ROUTE and not a dialog, and a half-entered tax is
          // linkable with its step in the URL. Both paths are declared once in
          // `definitionDetail.tsx`, so the tab's two doors cannot drift from them.
          // React Router ranks the static `new` segment above `:definitionId`,
          // so the detail route below still owns a real id.
          // CR-165-BRC10 task 4 (2026-10-03): the NEW door opens the redrawn
          // four-step form (`taxForm/NewTaxWizard.tsx`, images 04–17).
          // CR-165-BRC10 task 7: the EDIT door opens the SAME form with a
          // variation (`taxForm/EditTaxForm.tsx`, images 24–33) — PO, *"We dont
          // use side panel for edit … You can use add form with variation"*.
          // `?change=info|change|correct` picks the flow; `TaxWizard.tsx` is gone.
          { path: TAX_WIZARD_NEW_ROUTE.slice(1), element: <NewTaxWizard /> },
          { path: TAX_WIZARD_EDIT_PATTERN.slice(1), element: <EditTaxForm /> },
          {
            path: "plans-rates/taxes-fees/:definitionId",
            element: <DefinitionDetailPage kind="tax" />,
          },
          { path: "plans-rates", element: <PlansRatesPage /> },
          { path: "plans-rates/:tab", element: <PlansRatesPage /> },
          // S14–S16 Premises & Units. The two list paths are exactly SHELL_NAV's
          // `premises` children (BR-SHL-001) — `/premises` and `/premises/units`
          // — so the sidebar sub-items land on the right screen and the
          // breadcrumb resolves. React Router ranks the static `units`/`new`
          // segments above `:premisesId`, so a unit list is never mistaken for
          // a premises id.
          //
          // ⚠ **CR-023 P0 — THREE ROUTES, ONE PAGE, AND `/premises/units` MUST
          // KEEP RESOLVING.** r10 draws Premises · Units · Imports as ONE page
          // with a tab strip, and the obvious implementation — one route plus
          // `?tab=` — would have broken every existing deep link and every
          // `f.premises_id=`-scoped URL into the units list. So the TAB IS THE
          // ROUTE: all three mount `PremisesTabsPage` (the one head, the roll-up
          // and the strip) and differ only in which body it renders. TC-24 is
          // the assertion, and `/premises/units` is byte-identical to what it
          // was. `PremisesListPage` and `UnitsListPage` are no longer routed
          // directly — they are tab BODIES and draw no page head of their own.
          { path: "premises/new", element: <AddPremisesWizard /> }, // S16
          // ⚠ **DEF-520 — THE TWO ROUTES THAT MOUNT THE FIVE-STAGE RUNNER.**
          // They must sit ABOVE `premises/units/:unitId` and `premises/:premisesId`
          // or `import` is read as an id and the runner never renders. ONE page
          // serves both: `target` is the only thing that differs, because
          // BR-MET-096 rules one workflow for premises and units and puts the
          // whole of the difference in the Transform stage.
          { path: "premises/import", element: <ImportWorkflowPage target="premises" /> }, // WFL-01
          { path: "premises/units/import", element: <ImportWorkflowPage target="units" /> }, // WFL-01
          // ⚠ CR-089 wave E — MUST sit above `premises/units/:unitId` or `new`
          // is read as a unit id and the wizard never renders. Same trap
          // DEF-520 records one line up for the two import routes.
          { path: "premises/units/new", element: <AddUnitsWizard /> }, // S16 (units half)
          { path: "premises/units", element: <PremisesTabsPage tab="units" /> }, // S15 · PRM-01U
          { path: "premises/units/:unitId", element: <UnitDetailPage /> },
          { path: "premises/imports", element: <PremisesTabsPage tab="imports" /> }, // PRM-04
          { path: "premises", element: <PremisesTabsPage tab="premises" /> }, // S14 · PRM-01
          { path: "premises/:premisesId", element: <PremisesDetailPage /> },
          // S25–S27 — SHELL_NAV's `reads` parent and its two children
          // (BR-SHL-001), so every sidebar item under Reads lands on a screen.
          //
          // S25 joins them 2026-08-11. The reads ENGINE — validation, flagging,
          // estimation, supersession and the whole import pipeline — shipped
          // served and unreachable: eleven endpoints under /reads and
          // /read-batches with not one screen calling them, which is hard-won
          // law 2 at feature scale. `reads` is the sidebar's own parent path,
          // so this is the item that used to land on the W0 placeholder.
          //
          // S29 is a FULL PAGE as of CR-038 W5 (PO 2026-08-26: "i want page to
          // be open for consitency - we dont open side panel") at
          // `reads/:readId` — declared BELOW the four static siblings so the
          // reading order shows the ranking, though React Router ranks static
          // segments above the id converter regardless (the DEF-520 habit).
          // The old `?read=<id>` drawer links still resolve: S25 forwards them
          // to the page (the LEGACY_SETTINGS_TAB_PATHS posture).
          //
          // The static `routes`/`cycles` segments are declared first, exactly as
          // React Router ranks them, so neither is ever read as a read id.
          // ⚖️ **ENTRY 14's HOLD HAS EXPIRED, AND THESE TWO ADDRESSES NOW
          //    REDIRECT (`ReadCyclesTab.test.tsx`'s pairing case).** Entry 14
          //    retires Routes *"as a screen"* and says in the same breath where
          //    its contents go — *"Every column survives, inside the cycle it
          //    belongs to — see entry 20"* — so the forward is only lawful once
          //    entry 20 exists. It does, one line below, and the pairing test
          //    asserts the two as ONE state: both absent, or both present.
          //
          //    The addresses are KEPT because *"there are tickets with these
          //    URLs in them"*; they land on the Read cycles tab.
          { path: "reads/routes", element: <RedirectToReadCycles /> },
          // Meter Reads blueprint entry 21 — **A ROUTE, THE DETAIL**, and the
          // reason it has an address of its own is PO ruling 2026-09-13, option
          // A: a route can be walked on more than one cycle, so *"0 of 11
          // collected"* has no denominator until a window is named, and the
          // window rides in the address (`?window=YYYY-MM`) where a ticket can
          // link straight at it. Nesting it under the cycle page would have put
          // the figures back inside one cycle's frame.
          //
          // Declared BELOW the static `reads/routes` sibling in reading order,
          // the DEF-520 habit — React Router ranks the static segment above the
          // id converter regardless, so `reads/routes` is never read as a route
          // id and `reads/routes/<uuid>` is never read as the list.
          { path: "reads/routes/:routeId", element: <RouteReadsPage /> },
          { path: "reads/cycles", element: <RedirectToReadCycles /> },
          // Meter Reads blueprint entry 20 — **A CYCLE, THE DETAIL**. The
          // second half of the PO's ruling *"within that we should show Routes
          // and their completion"*: retiring entry 14 moved nine columns with
          // nowhere to go, and this is where they went. Opened by a row on the
          // cycles list above, and addressable on its own because a ticket that
          // says *"CY-001 is short"* needs a link to paste — the open tab rides
          // in `?tab=` (BR-SHL-011), so the shortfall itself is linkable.
          //
          // Declared BELOW the static `reads/cycles` sibling in reading order,
          // the DEF-520 habit — React Router ranks the static segment above the
          // id converter regardless.
          { path: "reads/cycles/:cycleId", element: <ReadCycleDetailPage /> },
          // ⚠ **`reads/estimate` IS NOT A ROUTE ANY MORE (DEF-897).** PO, on
          // the live app at v2.61.1: *"this can be modal - instead of page"*.
          // "Estimate a missing read" is a three-field form that returns to the
          // list it was launched from, and its three siblings on S25 (Add
          // reading, Route sheet, Upload reads) were already dialogs — so it is
          // `EstimateReadModal`, mounted from `ReadsListPage`'s header.
          //
          // The engine it reaches is unchanged and so is the reason it exists:
          // `POST /reads/estimate` shipped 2026-08-11 with NO screen calling it,
          // so a clerk with an unreadable meter could not fill the gap and that
          // customer could not be billed at all (hard-won law 2).
          // S28 — Upload reads (DEF-115). The read-import pipeline shipped on
          // 2026-08-10 complete and unit-tested with NO screen, so `meter_reads`
          // held 0 rows on a fully seeded stack and no bill this product has
          // ever produced came from a meter reading. Hard-won law 2 at the
          // largest scale the register carries: the first step of a
          // meter-to-cash system could not be performed by a human at all.
          // The S25 header's "↑ Upload reads" button lands here — it was a
          // disabled control saying the screen did not exist until today.
          { path: READS_UPLOAD_ROUTE.slice(1), element: <UploadReadsWizard /> }, // S28
          { path: `${READS_ROUTE.slice(1)}/:readId`, element: <ReadDetailPage /> }, // S29
          { path: READS_ROUTE.slice(1), element: <ReadsListPage /> }, // S25
          // S17 Accounts. Exactly SHELL_NAV's `accounts` path (BR-SHL-001), so
          // the sidebar item stops landing on the W0 placeholder — the
          // `customers` API shipped the same day with no screen reading it,
          // which is hard-won law 2 ("built is not wired") in its purest form.
          //
          // S18 (the guided New account page) and S21 (account detail) join it
          // 2026-08-11: `POST /accounts` and `GET /accounts/{id}` were served
          // with nothing calling them, which is the same law again. React
          // Router ranks the static `new` segment above `:accountId`, so the
          // wizard is never mistaken for an account id.
          //
          // S19/S20 (move-in, move-out) join them the same day the backend
          // slice that serves them landed. Both are ACCOUNT-SCOPED, because
          // their endpoints are (11b §S19/§S20): move-out closes the account in
          // the path, and move-in creates the next occupant of THAT account's
          // unit — so each hangs off `:accountId`, and the static
          // `move-in`/`move-out` segments rank above nothing else that could
          // swallow them.
          //
          // ⚠ **AMENDED 2026-08-26 — "rather than getting a top-level route" IS
          // NO LONGER TRUE.** Both now ALSO have one (`/move-ins/new`,
          // `/move-outs/new`, below), because the PO ruled the Accounts header's
          // disabled Move-in / Move-out open. The ENDPOINTS are unchanged and
          // still account-scoped; what changed is that each wizard's first step
          // can find its own subject when the URL did not carry one.
          { path: ACCOUNT_NEW_ROUTE.slice(1), element: <NewAccountWizard /> }, // S18
          // S68 — the brownfield account import (US-CUS-019). Static like
          // `new`, so it outranks `:accountId` and cannot be read as an id.
          // CR-030 W1 — S68 on the ONE runner (BR-MET-096). The three-step
          // modal that stood here never had the value-map step A1 has
          // specified since 2026-08-08 (DEF-611).
          { path: ACCOUNT_IMPORT_ROUTE.slice(1), element: <AccountImportWorkflowPage /> }, // S68
          { path: ACCOUNTS_ROUTE.slice(1), element: <AccountsListPage /> },
          // ── CR-056 W5 task 25 — THE CUSTOMERS LIST ───────────────────────
          // There was no way to browse people at all: you reached a person
          // only backwards, through one of their accounts. Declared BEFORE
          // `accounts/:accountId` in file order for readability only — the
          // paths do not overlap, since this one is not under `accounts/`.
          { path: CUSTOMERS_ROUTE.slice(1), element: <CustomersListPage /> },
          // ── `CR-094-BRC01` wave L · `BR-CUS-1051` — THE EIGHT ARE CHILDREN ─
          //
          // PO 2026-09-13, verbatim: *"Yes move the eight quick actions over the
          // account"*. **Every path below is the string it already was** — this
          // is a nesting, not a re-addressing — plus three NEW account-scoped
          // addresses for the three screens that never had one.
          //
          // ⚠ **THE NESTING *IS* THE FEATURE, AND NOTHING WAS RE-TYPED.**
          // `AccountDetailPage` renders `AccountActionOverlay`, which puts
          // `<Outlet/>` inside the shared `ModalShell`. So the account — its
          // balance, its status, its tabs — stays on screen behind whichever of
          // the eight is open, which is `ACC-S14`'s own acceptance sentence
          // (*"without losing sight of the balance behind it"*). What it buys
          // that a `useState` dialog could not: `:accountId` still resolves for
          // the five screens that read `useParams()`, `?step=` still survives a
          // reload for the three that park there, and each screen's existing
          // `navigate(accountDetailPath(accountId))` exit UN-MATCHES the child
          // and closes the dialog — so not one exit was rewired.
          //
          // ⚠ **THE OTHER DOOR IS UNTOUCHED IN ALL THREE CASES THAT HAVE ONE:**
          // `/billing/bills/:invoiceId/document`, `/billing/fix?bill=` and
          // `/disconnects/new?account=` are all still declared, still mounted,
          // still the addresses every other screen links to.
          {
            path: `${ACCOUNTS_ROUTE.slice(1)}/:accountId`,
            element: <AccountDetailPage />, // S21
            children: [
              { path: "move-out", element: <MoveOutWizard /> }, // S20
              { path: "move-in", element: <MoveInWizard /> }, // S19
              // ── DEF-724 · THE CLOSE-OUT — a SEPARATE door, on purpose ────
              // PO 2026-08-27: *"A disconnected customer can never be closed -
              // Add a separate close-out act — Cleaner in the record"*. It is
              // its own path rather than a mode of `/move-out` because routing a
              // cut customer through the move-out screen is how a disconnection
              // ends up filed as a move-out, and to a regulator those are not
              // the same event (BR-CUS-430).
              { path: "close-out", element: <CloseOutPage /> },
              // ⚠ **BILL-SCOPED, WHICH IS WHY IT CARRIES A PARAMETER.**
              // `BillDocumentPage` reads `useParams().invoiceId` and there is
              // nothing account-shaped for it to read; the rail resolves WHICH
              // bill (the newest ISSUED one) exactly as it did when this glyph
              // navigated to billing, and that derivation did not move.
              { path: "bills/:invoiceId/document", element: <BillDocumentPage /> },
              // The credit is raised ON A BILL, inside the correction workflow —
              // `FixABillTab` reads `?bill=<id>` and this route hands it the same
              // query the billing address does. The TAB is mounted rather than
              // `BillsListPage`, because a list of every bill in the utility is
              // not what a clerk pressed *Issue credit* to see.
              { path: "issue-credit", element: <FixABillTab /> },
              { path: "change-plan", element: <ChangePlanWizard /> }, // S23
              // `DisconnectWizard` took its subject from `?account=` alone; it
              // now falls back to `:accountId`, so this address needs no query
              // to be complete and cannot silently open the finder step.
              { path: "disconnect", element: <DisconnectWizard /> }, // DSC-02
              { path: "payment-plan", element: <PaymentPlanWizard /> }, // S24
            ],
          },
          // ── THE STANDALONE ENTRY POINTS — PO ruling 2026-08-26 ──────────
          // ⚠ **THE TWO ACCOUNT-SCOPED ROUTES ABOVE ARE UNTOUCHED AND STILL
          // WORK.** These are a second door onto the SAME two components, not a
          // replacement: `MoveOutWizard` reads `params.accountId ?? ""` and
          // `MoveInWizard` reads it the same way, so an absent param is what
          // switches each wizard's FIRST STEP from confirming to finding. Every
          // step after the first is the same code either way.
          //
          // The PO's own sentence is why they differ: *"a move-in creates the
          // next occupant of a particular account's unit"*. So move-out finds an
          // ACCOUNT (the shared `AccountFinder`, DEF-732 — the same step
          // `/transfers/new` and `/disconnects/new` open on) and move-in finds
          // the UNIT, deriving the outgoing account from it.
          //
          // ⚠ **TOP-LEVEL, AND THE STATIC SEGMENT IS DECLARED FIRST**, exactly
          // as `/connections/new`, `/transfers/new` and `/disconnects/new`.
          // Neither path has a sibling `:id` route today, so the ordering buys
          // nothing yet — it is written this way because the day a move-in or
          // move-out DETAIL screen lands, a route added after these would make
          // `/move-ins/new` a move-in whose id is the word "new". That is the
          // trap `apps/customers/api.py` carries a comment about on
          // `accounts/master`, and DEF-520 is the premises runner learning it
          // the hard way.
          // CR-168-BRC10 image 19 (ruling 35) — the raise opened from an
          // account, FULL PAGE beside the account route rather than one of its
          // dialog children (`BR-CUS-1051`), because the drawing draws a page.
          { path: ACCOUNT_RAISE_ROUTE.slice(1), element: <AccountRaisePage /> }, // WRK-12
          { path: MOVE_IN_WIZARD_ROUTE.slice(1), element: <MoveInWizard /> }, // S19 standalone
          { path: MOVE_OUT_WIZARD_ROUTE.slice(1), element: <MoveOutWizard /> }, // S20 standalone
          // ── THE MOVE RECORD (blueprint p074) — the detail screen the note
          // above predicted, and it does NOT create the trap it warns about.
          //
          // ⚠ **`/moves/:ref`, A SEGMENT OF ITS OWN — NOT `/move-ins/:id`.**
          // The blueprint's own URL is `/brazosbend/moves/mvi-26-0114`, and a
          // move-OUT record answers here too (`MVO-26-0001`), so one address
          // serves both flows.
          //
          // ⚠⚠ **THAT SENTENCE WAS HALF FALSE UNTIL 2026-09-19, AND THE HALF
          // THAT WAS FALSE IS THE HALF A READER USES (`DEF-CUS-5889`).** The
          // ADDRESS served both flows from the day it was declared — measured,
          // not assumed: `GET /moves/MVO-26-0001` answers **200** with
          // `kind: "move_out"`. The PAGE did not. `MoveRecordPage` had no
          // move-out branch at all, so a real move-out rendered *"Account
          // opened"* and *"Moved in on"* about somebody who had LEFT, and the
          // deposit box where p118 draws the settlement. **That is worse than a
          // 404, because it looks like a page.** Hard-won law 1 — a comment
          // claiming a guarantee is not the guarantee — inside the comment that
          // claimed it. The branch exists now and
          // `MoveRecordPage.test.tsx` asserts it by `kind`.
          //
          // Because the segment differs from `move-ins`,
          // `/move-ins/new` cannot be read as a record whose reference is the
          // word "new" — the ordering hazard the note above names is avoided by
          // the address rather than by the declaration order.
          //
          // ⚠ **NOT UNDER `accounts/`, AND THAT IS THE DESIGN.** *"A move-in is
          // a record OF an act, and the thing it produced is an account"*
          // (p073). It is also the only placement that WORKS: an in-flight move
          // has no account at all, and half of what p073 draws is in flight.
          //
          // `:ref` is the move NUMBER and never a uuid (B14 rule 31).
          { path: MOVE_RECORD_ROUTE.slice(1), element: <MoveRecordPage /> },
          // ⚠ **S23 (Change plan) AND S24 (Payment plan) MOVED UP INTO THE
          // ACCOUNT'S `children` BLOCK** (`CR-094-BRC01` wave L, `BR-CUS-1051`).
          // Their addresses are unchanged — `/accounts/:accountId/change-plan`
          // and `/accounts/:accountId/payment-plan` — and both are still
          // account-scoped for the reason they always were: their endpoints are
          // (`POST /accounts/{id}/plan-changes` and its preview, 11b §2.6;
          // `GET|POST /accounts/{id}/payment-plans`, 11b §S24), so the account
          // whose plan moves or whose arrears are spread is the one in the URL.
          // ── CR-030 W4 · THE SERVICE REQUEST (REQ-01 · REQ-02 · REQ-03) ───
          // `new` is declared BEFORE `:requestId` — React Router ranks a static
          // segment above a dynamic one, so the order is belt and braces, but
          // the premises runner learned this the hard way (DEF-520) and writing
          // it down costs nothing.
          //
          // ⚠ **B19 §12.1 DRAWS THE LIST AS A TAB OF THE ACCOUNTS PAGE** —
          // `Accounts · Requests⁴² · New Connect⁷ · …` — and `AccountsListPage
          // .tsx` renders that strip. Its Requests tab currently draws an
          // "arrives with" note that is FALSE from this commit, and correcting
          // it is one line in a file another lane holds today (hard-won law 11:
          // a pathspec commit takes the whole file). REPORTED and OWED. Until
          // it lands these are the addresses, and every link in the feature
          // points here.
          // ── CR-094-BRC01 wave G (2026-09-12) · THE TWO FULL-PAGE FORMS ──
          //
          // PO ruling, verbatim: *"A complaint form should be of a staple form
          // and on new page it should open up. Same for the services"*,
          // confirmed **"Yes that is correct"**. Both addresses are the
          // blueprint's own (`/brazosbend/complaints/new?step=1`,
          // `/brazosbend/services/new?step=1`).
          //
          // ⚠ **A PAGE, NOT A DIALOG** — B14 rule 30 was DECLINED and the PO
          // ruled this instance; `JobIntakeWizard.tsx`'s header records both.
          //
          // ⚠ **`new` IS THE WHOLE PATH HERE, so there is no `:id` sibling for
          // it to be mistaken for** — the record's detail is the work order's
          // own page (`/work/wo/:orderId`), which already exists. A second
          // detail would be `CR-070` wave O's duplicate destination again.
          {
            path: COMPLAINT_INTAKE.route.slice(1),
            element: <JobIntakeWizard spec={COMPLAINT_INTAKE} />,
          },
          {
            path: SERVICE_INTAKE.route.slice(1),
            element: <JobIntakeWizard spec={SERVICE_INTAKE} />,
          },
          { path: SERVICE_REQUEST_NEW_ROUTE.slice(1), element: <ServiceRequestCapturePage /> }, // S85 · REQ-03.1–6 + REQ-03.sent
          { path: SERVICE_REQUESTS_ROUTE.slice(1), element: <ServiceRequestsListPage /> }, // S83 · REQ-01
          {
            path: `${SERVICE_REQUESTS_ROUTE.slice(1)}/:requestId`,
            element: <ServiceRequestDetailPage />, // S84 · REQ-02
          },
          // ── CR-030 W6 · New Connect (tasks 6.11 / 6.13). ──
          // ⚠ THE STATIC SEGMENT IS DECLARED FIRST, or `/connections/new` is
          // read as a connection whose id is the word "new" — the same trap
          // `accounts/master` carries a comment about in apps/customers/api.py.
          { path: NEW_CONNECT_ROUTE.slice(1), element: <NewConnectWizard /> }, // S87 · NCT-01
          // ── CR-151-BRC09 §6a (2026-09-28) · THE BUILD GETS ITS OWN PAGE
          //    BACK, AT THE SAME ADDRESS ──────────────────────────────────
          //
          // ⚠ **THIS REVERSES THE FIRST CLAUSE OF CR-070 WAVE O AND NOTHING
          // ELSE.** That wave read the PO's *"you are duplicating this — there
          // is nothing called as conenctions; Connection = Account only - you
          // cannot have two differnt screen"* as *the build has no page*, so
          // `ConnectionDetailPage` was deleted and this address became a
          // doorway that resolved where the build lived and sent the reader
          // away. The 2026-09-28 ruling puts the page back: a build IS a thing
          // a clerk opens, and the duplication the PO objected to was two
          // screens for one fact, not one screen for the build.
          //
          // ⚠ **THE ADDRESS DID NOT MOVE, AND THAT IS THE POINT OF FLIPPING
          // THE ELEMENT RATHER THAN THE ROUTE.** Every bookmark and every
          // *Open this connection* link the wizard handed out since wave O
          // resolves here and goes on resolving here.
          //
          // ⚠ **`BuildRedirect` IS DELETED IN THIS COMMIT, NOT LEFT BEHIND**
          // — a doorway nothing mounts is dead code that still looks wired
          // (hard-won law 2), and `buildAddress.route.test.tsx` is the test
          // written at the hold that fires on exactly this day and names the
          // three things the flip owes: the screen-id row, G29's badge list
          // and this deletion.
          {
            path: `${CONNECTIONS_ROUTE.slice(1)}/:connectionId`,
            element: <BuildDetailPage />, // NCT-02
          },
          // ── CR-030 W7 · the two enforcement wizards (B18 §5.7.7 / §5.8.7). ──
          // The LIST half of each id shipped 2026-08-25 as an embedded tab of
          // the Accounts page (`TransfersTab` / `DisconnectsTab`, DEF-664); the
          // WIZARD half had no route in this application at all, which is
          // hard-won law 2 in its purest form — five steps of engine in
          // `transfers.py` and `disconnects.py` with nothing anywhere to click.
          //
          // ⚠ **THE STATIC SEGMENT IS DECLARED FIRST**, exactly as the New
          // Connect pair above it. Neither path has a sibling `:id` route TODAY,
          // so the ordering buys nothing yet — and it is written this way
          // because the day a transfer or disconnect DETAIL screen lands, a
          // route added after these would make `/transfers/new` a transfer
          // whose id is the word "new". That is the trap `apps/customers/api.py`
          // carries a comment about on `accounts/master`, and DEF-520 is the
          // premises runner learning it the hard way.
          //
          // ⚠ **TOP-LEVEL, NOT ACCOUNT-SCOPED**, unlike move-in and move-out.
          // Those hang off `:accountId` because their endpoints do; these two
          // FIND the account as step 1 of the flow (`transfers.start_transfer`
          // takes `from_account_id` in its payload, and `DSC-02.1` is a search
          // box), so an account in the path would be a prerequisite the drawing
          // does not have.
          { path: TRANSFER_WIZARD_ROUTE.slice(1), element: <TransferWizard /> }, // S89 · TRF-02
          // ── THE TRANSFER RECORD (blueprint p132) — the detail screen the
          // note above predicted, landing AFTER the static segment exactly as
          // that note instructs.
          //
          // ⚠ **`new` CANNOT BE READ AS A REFERENCE, AND BOTH HALVES OF THAT
          // ARE TRUE HERE.** React Router ranks a static segment above a
          // dynamic one, and this route is ALSO declared second — belt and
          // braces, because the comment above is the only place the reasoning
          // is written and DEF-520 is the premises runner learning it the hard
          // way. `/transfers/new` stays the wizard.
          //
          // ⚠ **`:ref` IS THE TRANSFER NUMBER AND NEVER A UUID** (B14 rule
          // 31). `OQ-426` closed on 2026-08-27 — PO verbatim, *"Transfer
          // TRF-26-0001 … follow same logic that we are following for other
          // numbers we have did in settings"* — so `core/numbering.py` carries
          // the series and `start_transfer` allocates inside its own
          // transaction. p132's dashed panel saying no series exists describes
          // the world of the day before that ruling.
          //
          // ⛔ **NO DOOR POINTS HERE YET, AND THAT IS REPORTED RATHER THAN
          // QUIETLY TRUE** (hard-won law 2's mirror). `TransfersTab.tsx` states
          // in its own §4 that it draws no row action because *"There is no
          // transfer detail screen, so a 👁 icon would link onto nothing"* —
          // a refusal that stops being true at this commit. That file is held
          // by another lane today, so the door is OWED and filed
          // (`DEF-CUS-5982`), never silently left: a screen nobody can reach
          // is the other half of the defect this law names.
          //
          // ⚠ **`GET /transfers/{ref}` IS NOT MOUNTED YET EITHER.** Until it
          // is, this address renders the page's not-found sentence. That is
          // deliberate: a screen that draws its own furniture over no data
          // looks like a working page, which is worse than a 404.
          { path: TRANSFER_RECORD_ROUTE.slice(1), element: <TransferRecordPage /> }, // S89 · p132
          { path: DISCONNECT_WIZARD_ROUTE.slice(1), element: <DisconnectWizard /> }, // S90 · DSC-02
          // ── THE DISCONNECT CASE RECORD (blueprint p143) — the detail screen
          // the note above predicted for the second of the two wizards,
          // landing AFTER the static segment exactly as that note instructs.
          //
          // ⚠ **`new` CANNOT BE READ AS A CASE NUMBER, AND BOTH HALVES OF THAT
          // ARE TRUE HERE.** React Router ranks a static segment above a
          // dynamic one, and this route is ALSO declared second — belt and
          // braces, because the reasoning lives only in the comment above and
          // DEF-520 is the premises runner learning it the hard way.
          // `/disconnects/new` stays the wizard.
          //
          // ⚠ **`:ref` IS THE CASE NUMBER AND NEVER A UUID** (B14 rule 31).
          // `OQ-427` closed on 2026-08-27 — PO verbatim, *"it needs its own
          // series"* — so `core/numbering.py` carries the `disconnect_case`
          // series and `/disconnects/dsc-26-0003` is the blueprint's own
          // address.
          //
          // ⛔ **THE DOOR IS OWED AND IS REPORTED RATHER THAN QUIETLY TRUE**
          // (hard-won law 2's mirror). `DisconnectsTab.tsx` draws no row action
          // today because there was nowhere to go — a refusal that stops being
          // true at this commit. That file is held by another lane, so the door
          // is handed over rather than taken.
          { path: DISCONNECT_RECORD_ROUTE.slice(1), element: <DisconnectRecordPage /> }, // S90 · p143
          // ── `S148` · PUT SERVICE BACK ON (PO drawings 2026-09-25) ───────
          // **The case record's address plus one segment**, which is 4.8's
          // whole answer: a clerk arrives from `/disconnects/dsc-26-0005`, so
          // this is where they go and the back link writes itself. Declared
          // AFTER the record for the same belt-and-braces reason the record is
          // declared after `transfer_disconnect_api` — `disconnects/:ref`
          // cannot match two segments, so ranking is not load-bearing here,
          // but a lane reordering these has to think about it either way.
          //
          // ⚠ **THE DOOR FROM THE CASE IS OWED AND IS REPORTED RATHER THAN
          // QUIETLY TRUE** (hard-won law 2's mirror). `DisconnectRecordPage`
          // and `ReconnectDialog` belong to lane CUTPATH today, so the record
          // still opens the DIALOG; replacing that control with a link here is
          // handed over, not taken. `ReconnectPage.dom.test.tsx` asserts this
          // address and the screen id it opens, so the day that control moves
          // the suite already names the destination it must point at.
          { path: RECONNECT_ROUTE.slice(1), element: <ReconnectPage /> }, // S148
          // S30 Billing. Exactly SHELL_NAV's `billing` path (BR-SHL-001), which
          // has NO submenu because the prototype's Billing page is a tabbed one
          // — so `:tab` carries the six-tab strip (All bills · Run bills ·
          // One-time bill · Budget Bills · Fix a bill · Past billing runs) and
          // only "All bills" has a story shipping today.
          //
          // The billing TABLES landed 2026-08-11 with no read endpoint and no
          // screen, which is hard-won law 2 read from the other end: a bill that
          // exists is invisible. `GET /invoices` and `GET /invoices/{id}` are
          // CONTRACTED (11b §2.8) and not served yet — these screens call them
          // and render the A18 §4 failure with a plain-language reason derived
          // from the response, so nothing here has to be edited when the route
          // lands.
          //
          // `bills/:invoiceId` is three segments and all-static up to the id, so
          // React Router ranks it above `billing/:tab` — a bill id can never be
          // read as a tab name.
          //
          // S31 joins them 2026-08-11 at `billing/run`, which is the Billing
          // page's own "Run bills" TAB id. Two consequences, both deliberate:
          // the tab strip on S30 already navigates to `/billing/run`, so the tab
          // lands on the wizard with nothing in `BillsListPage` edited; and the
          // segment is all-static, so React Router ranks it above `billing/:tab`
          // and the wizard wins over the list's tab handler. The run engine
          // (`apps/billing/runs.py` — prepare, calculate, retry, mark-for-later)
          // shipped on 2026-08-11 with no screen able to reach a line of it,
          // which is hard-won law 2 at feature scale: a clerk could not run
          // billing at all. ⚠ **`POST /billing/runs` AND ITS SIBLINGS ARE
          // REGISTERED NOW AND THIS SENTENCE SAID THEY WERE "REGISTERED
          // NOWHERE" UNTIL 2026-09-01 (DEF-2421)** — `apps/billing/api.py`
          // mounts `path("billing/runs", bill_runs)` under
          // `@api_view(["GET", "POST"])`. The claim was true when written and
          // rotted in place, and the copy of it in `BillsListPage` was holding
          // the Billing screen's primary action disabled. Hard-won law 1: the
          // sentence is CORRECTED rather than deleted, because this is where a
          // regression would show first. What still holds: the wizard derives
          // an absent route from the RESPONSE, so nothing here needs editing
          // either way.
          // ORDER IS LOAD-BEARING: `bills/:invoiceId/document` is four segments
          // and must be declared ABOVE `bills/:invoiceId`, or React Router
          // matches the shorter pattern first and the document renders the
          // detail screen. Added 2026-08-16 with the route that serves it —
          // `documents.py` had rendered every bill twice since the day it
          // landed and `issue.py` threw the result away, its own
          // DOCUMENT_UNAVAILABLE recording that no human could open one.
          {
            path: `${BILLING_ROUTE.slice(1)}/bills/:invoiceId/document`,
            element: <BillDocumentPage />,
          },
          { path: `${BILLING_ROUTE.slice(1)}/bills/:invoiceId`, element: <BillDetailPage /> },
          // US-BIL-006 — the pending-billing QUEUE, *"hold ≠ forget"*.
          // `GET /billing/pending` has been served since the queue landed and
          // `pending.py`'s own trailer recorded `E=deferred(no-frontend-half —
          // S30's KPI chip and queue list are not built; REPORTED)`. An account
          // a run declined to bill was invisible: the run said "21 excluded"
          // and nothing in the product could name them. All-static, and
          // declared above `billing/:tab` so `pending` is never read as a tab.
          { path: BILLING_PENDING_ROUTE.slice(1), element: <PendingQueuePage /> },
          // CR-053 task 13 — Print bills. The PDF set plus its manifest, which
          // is what a print vendor receives. All-static and declared above
          // `billing/:tab` for the same reason `pending` is: otherwise `print`
          // is read as a seventh tab, and the Billing strip has six labels that
          // G14 compares against the prototype.
          { path: BILLING_PRINT_ROUTE.slice(1), element: <PrintBillsPage /> },
          // ⚠ **THE ONE-TIME BILL, REDRAWN — ONE PAGE, FOUR STEPS (PO-confirmed
          // design 2026-09-30, `11-one-time-bill-redesign.md`).** It takes the
          // Bills page's `One-time bill` tab address, so the tab IS the door:
          // pressing it opens this page. It replaces both the in-tab
          // `OneTimeBillTab` and the unfinished three-step `OneTimeWizardShell`
          // that lived one segment deeper — both deleted in the same change.
          //
          // Two STATIC segments, declared ABOVE `billing/:tab` for the reason
          // `pending` and `print` are: otherwise `one-time` is read as a tab
          // name and the tab handler wins. Asserted by ADDRESS in
          // `OneTimeBillDoor.dom.test.tsx` (`DEF-CWP-3925`).
          { path: ONE_TIME_BILL_ROUTE.slice(1), element: <OneTimeBillPage /> },
          // ⚠ **THE BILL RUN — ONE PAGE, FOUR STEPS (bulk bill run redesign,
          // 2026-09-30, plan task F2; `DEF-BIL-8200`).** Bills → Run opens it.
          // It replaces the six-step `BillRunWizard` AND the four-step
          // `RunWizardShell` that answered one segment deeper at
          // `billing/run/:step` — both deleted in the same change, so there is
          // one bill-run screen. Asserted by ADDRESS in
          // `bulkRun/BulkRunDoor.dom.test.tsx` (hard-won law 2).
          { path: BILL_RUN_ROUTE.slice(1), element: <BulkRunPage /> }, // S31
          // §05 entry 25.1 `Enrol` — the Budget Bills tab's one-at-a-time
          // enrolment form, drawn on p122-p124 of the Billing blueprint.
          //
          // THREE STATIC SEGMENTS, declared ABOVE `billing/:tab`, for exactly
          // the reason `pending` and `print` are: otherwise `budget` matches
          // `:tab` and the tab handler wins over this screen. The order is
          // load-bearing and its test asserts the screen by ADDRESS, because
          // `DEF-CWP-3925`'s hold-expiry test asserted a screen was registered
          // at one address while the router mounted it at another, and every
          // check passed over both.
          //
          // It replaces the free-text `Paste the account's id` panel that stood
          // inside the tab (`DEF-BIL-5232` - a database id as a field's visible
          // value, which B14 rule 31 forbids by name).
          { path: BUDGET_ENROL_ROUTE.slice(1), element: <BudgetEnrolPage /> },
          // §05 entry 25.2 `Settle-up forecast` — READ ONLY, drawn on
          // p124-p126. Three static segments, declared above `billing/:tab`
          // for the same reason the enrol form is: otherwise `budget` matches
          // `:tab` and the tab handler wins over this screen. The order is
          // load-bearing and its test asserts the screen by ADDRESS.
          { path: BUDGET_FORECAST_ROUTE.slice(1), element: <SettleUpForecastPage /> },
          // §05 entry 25.3 — the queue a customer's portal ask lands on. Three
          // static segments, declared beside `enrol` and ABOVE `billing/:tab`
          // for the same reason: `budget` must never be read as a tab name.
          //
          // ⚠ ASSERTED BY ADDRESS in `budgetAsksPage.dom.test.tsx`, because
          // `DEF-CWP-3925`'s hold-expiry test asserted a screen was registered
          // at one address while the router mounted it at another, and every
          // check passed over both.
          { path: BUDGET_ASKS_ROUTE.slice(1), element: <BudgetAsksPage /> },
          { path: BILLING_ROUTE.slice(1), element: <BillsListPage /> },
          { path: `${BILLING_ROUTE.slice(1)}/:tab`, element: <BillsListPage /> },
          // S33 Payments. Exactly SHELL_NAV's `payments` path and its three
          // children (BR-SHL-001), so every sidebar item under Payments lands on
          // a screen instead of the W0 placeholder.
          //
          // The payments WRITE PATH landed 2026-08-11 — a payment could be
          // recorded, allocated across the customer's open bills and posted to
          // the books, under nineteen passing tests — with `apps/payments/api.py`
          // a one-line docstring in front of it, so NO HUMAN COULD RECORD A
          // PAYMENT. Hard-won law 2 at feature scale. Both endpoints
          // (`POST /accounts/{id}/payments`, `GET /payments`) landed with this
          // lane and this screen is their first caller.
          //
          // `:tab` carries the prototype's three-tab strip (Summary · Record
          // payments · Outstandings) and only "Record payments" has a story
          // shipping today: S32 is US-PAY-005 and S34 is US-PAY-013, and each
          // tab says what it is waiting for rather than drawing invented KPIs.
          //
          // `payments/collections` is a FOURTH tab (2026-08-16, payments SURFACE
          // lane). `apps/payments/ladder.py` could only be DRIVEN — `POST
          // /collections/run` sends the notice, advances the tier and records a
          // skip row on every path — and nothing could LOOK at the ladder first.
          // A clerk drove a five-stop-condition engine over a selection they
          // could not inspect. The static segment is declared BEFORE `:tab` so
          // the board wins over the tab handler.
          { path: COLLECTIONS_ROUTE.slice(1), element: <CollectionsPage /> },
          // S35 / 4·3a (`CR-135` `P1.5`) — the ONE ETL runner on the eighth
          // target. `P1.1` made `payments` an `ImportTarget` and `P1.17` proved
          // the runner already renders for it; this is the address its one door
          // opens, and it is declared ABOVE `:tab` so the literal `imports`
          // segment is never read as a tab id (the DEF-520 lesson).
          //
          // ⚠ **NO `?target=` QUERY, UNLIKE assets.** `AssetImportWorkflowPage`
          // reads one because THREE targets share its route; payments has
          // exactly one, and a target read off the address would let a typed
          // URL run the premises loader from the payments door.
          {
            path: `${PAYMENTS_ROUTE.slice(1)}/imports/new`,
            element: <ImportWorkflowPage target="payments" />,
          },
          // `PAY-04` / 3·2 *Your counter* (`CR-136-BRC07` `P2.6`) — one
          // clerk's till, its running split by method and the payments it has
          // taken. Declared ABOVE `:tab` so the literal `counter` segment is
          // never read as a tab id (the DEF-520 lesson), and the list at
          // `/payments/counter` stays the Counter TAB rather than a separate
          // screen.
          //
          // ⚠ **THE PARAM IS THE COUNTER'S CODE** — `CTR-260921-DW`, which is
          // what the blueprint draws in the address on p052 and what B14 rule
          // 31 requires: an address bar is the most visible field a screen
          // has, so a primary key may not ride in it.
          {
            path: `${PAYMENTS_ROUTE.slice(1)}/counter/:counterCode`,
            element: <MyCounterPage />,
          },
          // **7·2 Debtor** (`CR-138-BRC07` `P4.8`) — the drill-down the debtor
          // list has never had. Blueprint p083: *"Doors: a row on 7·1. 1 door
          // — there is none today."* This is that door's destination.
          //
          // ⚠ **DECLARED ABOVE `:tab` FOR THE SAME REASON `counter` IS**: the
          // literal `debtors` segment must never be read as a tab id
          // (DEF-520's lesson), and `paymentsTabFrom` deliberately falls back
          // to Summary for an unknown tab rather than 404-ing — so a
          // mis-ordered route here would open the Summary tab silently.
          //
          // ⚠ **AND THE PARAM IS THE ACCOUNT NUMBER**, `AC-2026-00001`, which
          // is what the blueprint draws in the address bar and what B14 rule
          // 31 requires. `debtor_api._resolve_account_id` is the server half;
          // a pk still resolves, so callers that hold one are not broken.
          {
            path: `${PAYMENTS_ROUTE.slice(1)}/debtors/:accountNo`,
            element: <DebtorPage />,
          },
          // **5·2 Settlement** (`CR-139-BRC07` `P5.7`) — the payout a row on
          // 5·1 opens. Blueprint p071: *"Doors: a row on 5·1. 1 door."* This
          // is that door's destination, and `settlementScreens.dom.test.tsx`
          // asserts it BY ADDRESS against `APP_ROUTES` itself, because
          // `DEF-CWP-3925`'s hold-expiry test asserted a screen was registered
          // at one address while the router mounted it at another and every
          // check passed over both.
          //
          // ⚠ **DECLARED ABOVE `:tab` FOR THE SAME REASON `counter` AND
          // `debtors` ARE**: the literal `settlements` segment must never be
          // read as a tab id (DEF-520's lesson), and `paymentsTabFrom`
          // deliberately falls back to Summary for an unknown tab rather than
          // 404-ing — so a mis-ordered route here would open the Summary tab
          // silently. The three-segment pattern cannot eat the two-segment tab
          // route `/payments/settlements`, which is the TAB and stays.
          //
          // ⚠ **AND THE PARAM IS THE PROVIDER'S OWN REFERENCE**,
          // `STL-260921-CARD`, which is what p071 draws in the address bar and
          // what B14 rule 31 requires.
          {
            path: `${PAYMENTS_ROUTE.slice(1)}/settlements/:settlementRef`,
            element: <SettlementPage />,
          },
          // ⚠ **6·1 Refunds — `CR-138-BRC07` `P4.10`, THE MOVE ITSELF.** Static
          // and declared ABOVE `:tab`, exactly as `payments/collections` is
          // three lines up: `refunds` IS a known tab id, so without this line
          // `PaymentsSegmentRoute` would render `PaymentsPage` and the strip
          // would fall through to Debtors — a live screen behind a door that
          // opens somewhere else (hard-won law 2's mirror). React Router ranks
          // a static segment above a dynamic sibling, which is what makes the
          // pair safe; the DEF-520 lesson is the same one.
          { path: REFUNDS_ROUTE.slice(1), element: <RefundsPage /> },
          // **2·3a Record a payment** — `DEF-PAY-6317`, the deferred half of
          // `CR-136-BRC07` `P2.9`. Blueprint p037 writes the address in the
          // frame header itself: *"today: a modal · agreed:
          // `/:tenant/payments/record/new` — a page, not a modal"*, over
          // *"DESKTOP · 1440 · A PAGE, FULL WIDTH"*. p038 says why it is the
          // one act of eight that gets a page: *"nine fields, an open-bill
          // picker and an allocation table … A modal cannot be linked,
          // bookmarked or returned to after a refresh"*.
          //
          // ⚠ **`/payments/record` IS NOT REDIRECTED HERE AND MUST NOT BE.**
          // p030 draws it as the payments LIST — `/:tenant/payments/record →
          // PaymentsPage → PaymentsTable` — because `record` is the TAB's id.
          // It is `AppShell`'s sidebar entry and a `sidebarDestinations` row,
          // so sending it to this form would delete the list of every payment
          // from an address a clerk may well have bookmarked. The two are
          // siblings; the list's page head is what carries the door.
          //
          // THREE SEGMENTS, so it can collide with neither `:tab` nor the
          // counter — and declared ABOVE `:tab` with the rest of them anyway,
          // which is the `DEF-520` lesson stated once for the whole block.
          {
            path: `${PAYMENTS_ROUTE.slice(1)}/record/new`,
            element: <RecordPaymentPage />,
          },
          // 7·3d Send a notice — `P4.14` + `P4.27`. A WIZARD AND NOT A MODAL,
          // *"because the letter has to be seen before it is sent, and a modal
          // had nowhere to put it"*, so it needs an address of its own. Three
          // segments, so it can collide with neither `:tab` nor the counter.
          { path: SEND_NOTICE_ROUTE.slice(1), element: <SendNoticeWizard /> },
          { path: PAYMENTS_ROUTE.slice(1), element: <PaymentsPage /> },
          // ⚠ **ONE DYNAMIC ROUTE, TWO SCREENS — `CR-137-BRC07` `P3.9`.**
          // Screen 2·2's agreed address is `/:tenant/payments/PMT-2609-000418`,
          // a SIBLING of the seven tab addresses. **React Router scores two
          // dynamic siblings at one level identically**, so a second
          // `:paymentRef` route here would either eat `payments/summary` or
          // never be reached, depending only on which line came first.
          //
          // `PaymentsSegmentRoute` decides it in one named, testable function:
          // a known tab (or `collections`) renders `PaymentsPage` exactly as
          // before, and only a segment shaped like a payment reference opens
          // the detail. **Nothing that works today changes** — including
          // `paymentsTabFrom`'s deliberate *an unknown tab falls back to
          // Summary, never 404s*.
          { path: `${PAYMENTS_ROUTE.slice(1)}/:tab`, element: <PaymentsSegmentRoute /> },
          // S49–S55 Assets. The registry is the sidebar's `assets` target.
          // CR-028 AST-W4 (PO 2026-08-22, B16 §5.2 as amended: "as per r10 -
          // it is not modal"): the four lifecycle flows are FULL-PAGE routes —
          // AST-05 add wizard · AST-06 reassign · AST-07 log repair/test ·
          // AST-08 retire. Only edit / delete / bulk-assign stay modal.
          //
          // ⚠ `assets/import` and `assets/new` must sit ABOVE `assets/:assetId`
          // (the DEF-520 lesson from the premises runner routes) or the literal
          // segment is read as an asset id. BR-AST-046 (CR-028): the three
          // tab-named import buttons land on the ONE workflow runner with
          // `?target=assets_*` (see AssetImportWorkflow.tsx).
          { path: "assets/import", element: <AssetImportWorkflowPage /> }, // WFL-01 (assets targets)
          { path: "assets/new", element: <AssetAddWizard /> }, // S51 / AST-05
          { path: "assets", element: <AssetRegistryPage /> },
          // ⚠ **`DEF-MET-4991` — THESE THREE MOUNTS PASS NO PROPS, AND THAT IS
          // WHY THREE DATE FIELDS PROPOSED NO DATE.** `today` reaches each page
          // through a prop nothing here supplies, so `prefill` was `undefined`
          // and all three rendered `value=""` against `BR-PAY-033` — and the
          // same absence silently voided a `max` bound whose unit test was
          // green, because the TEST passes `today` and the ROUTER does not.
          // Fixed in the pages (`todayInZone(timeZone)`), not here: a screen
          // should not depend on its mount site remembering to say what day it
          // is. Passing props here would work and would rot the same way.
          { path: "assets/:assetId/reassign", element: <AssetReassignPage /> }, // S55 / AST-06
          { path: "assets/:assetId/maintenance/new", element: <AssetLogMaintenancePage /> }, // S53 / AST-07
          // CR-070 wave M — the Assets door (`Work-028`, `US-WRK-038`,
          // `BR-WRK-056`), a SIBLING of the line above, which is the rule's own
          // word for it. ABOVE `assets/:assetId` for the same reason every
          // other static child here is.
          //
          // ⚠ **MOUNTING THIS ADDRESS RELEASES SEVEN CONTROLS THAT WERE
          // REFUSING OVER IT**, and the tests that name them fail until it is
          // here — hard-won law 2's mirror clause, the same machinery wave G
          // built for `ORDERS_HELD_CONTROLS`.
          // `DEF-MET-4978` — this comment read `WRK-19` until 2026-09-12, a badge
          // RETIRED in wave D, while `routing/screenIds.ts` minted this route
          // `WRK-24` and said why. The screen always rendered the right one, so
          // no user ever saw the wrong id and nothing went red for a week.
          { path: RAISE_WORK_ORDER_ROUTE.slice(1), element: <RaiseWorkOrderPage /> }, // WRK-24
          { path: "assets/:assetId/retire", element: <AssetRetireWizard /> }, // S54 / AST-08
          // `AST-B-12` (CR-092, PO 2026-09-11: "this should be form and not
          // modal") — the fifth asset surface stops being a dialog. STATIC
          // child above `assets/:assetId`, like every other one here.
          //
          // ⚠ **MOUNTING THIS ADDRESS IS THE HALF THAT MAKES THE PENCIL AND THE
          // HEADER'S Edit BUTTON REAL** (hard-won law 2): both navigate here,
          // and until this line existed both would have landed on the catch-all
          // with the form built, tested and unreachable.
          { path: "assets/:assetId/edit", element: <AssetEditPage /> }, // AST-09
          { path: "assets/:assetId", element: <AssetDetailPage /> },
          // S36 Finance and the two ledger-owned report viewers (S59 · S60).
          //
          // `apps/ledger/reporting.py` shipped on 2026-08-11 with every finance
          // figure in the product derived and tested — the trial balance foots
          // 598.69 = 598.69, LE-2's service slice reproduces verbatim — and its
          // own Lifecycle trailer records `E=deferred(no-frontend-half)`. Nobody
          // could see a number. Hard-won law 2 at feature scale again.
          //
          // `:tab` carries the prototype's five-tab Finance strip; only Revenue
          // & AR has a story shipping today (US-LED-007), and the other four
          // name what they are waiting for. `/finance/deposits`, `/finance/taxes`
          // and `/finance/export` are SHELL_NAV's own children (BR-SHL-001), so
          // every sidebar item under Finance lands on this page rather than on
          // the W0 placeholder.
          // ⚠ **CR-060 T10 — THE BARE `/finance` LANDS ON THE TRIAL BALANCE.**
          // The CR's reason, verbatim: *"The books are the one surface every
          // other tab feeds, so opening on the trial balance means the first
          // thing anyone sees is whether the month balances."* The sidebar path
          // is UNCHANGED and still ratified (BR-SHL-001) — what changed is what
          // it renders — and `AppShell`'s breadcrumb row for `/finance` moved
          // with it in the same commit, or the crumb would name the old screen.
          { path: FINANCE_ROUTE.slice(1), element: <GeneralLedgerPage /> }, // S56
          // Revenue & AR keeps its screen and takes a segment of its own.
          { path: `${FINANCE_ROUTE.slice(1)}/revenue`, element: <RevenueArPage /> }, // S36
          // DEF-112 (2026-08-15) — THREE OF THE FIVE FINANCE TABS NOW HAVE A
          // SCREEN. Until this commit `/finance/:tab` sent every tab to
          // RevenueArPage, which rendered "arrives with …" for four of them:
          // the month-close journey booted a real browser, went to Finance →
          // Export to accounting, and found ZERO of the five checklist items
          // and nothing to click — while `close_checklist`, `close_period`,
          // `reopen_period` and the export batch with its four gates were all
          // built, unit-tested and correct.
          //
          // The static segments are declared BEFORE `:tab` deliberately: React
          // Router ranks a static segment above a dynamic one either way, but
          // reading them in this order is how the next lane sees which tabs are
          // real. `/finance/deposits` is still the catch-all's — S37-S40 are
          // payments' (EP-PAY-06) and unbuilt, so that tab keeps saying so.
          // S37 · S38 · S39 · S40 — the deposits and bank-reconciliation family
          // (2026-08-16, payments SURFACE lane). `/finance/deposits` is a
          // RATIFIED sidebar child and has landed on RevenueArPage's "arrives
          // with …" panel since the Finance screens shipped, while
          // `apps/payments/reconciliation.py` could cut a day's batches, import
          // a statement, auto-match it, explain a difference with a reason and
          // a GL, reconcile, LOCK and unreconcile — 2,700 tested lines its own
          // docstring called "reachable only from a test or a shell today".
          //
          // ORDER IS LOAD-BEARING: `deposits/import` is all-static and MUST be
          // declared above `deposits/:batchId`, or the word "import" resolves as
          // a batch id and the wizard 404s on a batch that never existed.
          { path: `${DEPOSITS_IMPORT_ROUTE.slice(1)}`, element: <BankImportWizard /> }, // S38
          // CR-059 W8 · P8 — the period reconciliation statement (task 48).
          // FOUR finished backends sat behind this one route: the statement
          // itself, an explanation hung off a bank LINE, the many-to-one match
          // SET and the differences report. `apps/payments/api.py` said so in
          // its own words above them — hard-won law 2, stated by the lane that
          // built them. STATIC, so it is declared above `:batchId` for the same
          // reason `import` is: "statement" would otherwise resolve as a batch
          // id and 404 on a batch that never existed.
          { path: `${DEPOSITS_STATEMENT_ROUTE.slice(1)}`, element: <ReconciliationStatementPage /> },
          { path: `${DEPOSITS_ROUTE.slice(1)}/:batchId`, element: <DepositBatchPage /> }, // S39·S40
          { path: DEPOSITS_ROUTE.slice(1), element: <DepositsPage /> }, // S37
          // ⛔ `/finance/write-offs` IS GONE (`CR-135` P1.10, 2026-09-22). The
          // approval queue lives as `WriteOffQueuePanel` inside Revenue & AR —
          // `CR-060` §8b folded it there *"where the receivable it gives up
          // already lives"* — and the standalone page stayed mounted beside it,
          // so the product carried TWO implementations of one queue. This was
          // never a missing door: nothing linked to this address, and adding a
          // link would have made the duplication permanent. `writeOffOneQueue.
          // test.tsx` is the guard that keeps it gone.
          // ⚠ **S58 LEFT THIS AREA ON 2026-09-23 (`CR-138-BRC07` `P4.10`) AND
          // THIS LINE IS NOW A REDIRECT, NOT A DELETION.** It read
          // `{ path: REFUNDS_ROUTE.slice(1), element: <RefundsPage /> }` while
          // `REFUNDS_ROUTE` was `/finance/refunds`. The screen is mounted in
          // the PAYMENTS block below; the supersedes chain for the move is on
          // `paymentsShared.REFUNDS_ROUTE`.
          //
          // The old address stays mounted because it is in saved links, in
          // tickets and in this repo's own journeys — the same reason
          // `CR-060`'s ruling kept `/finance/gl` and `/finance/write-offs`
          // routed when their tabs went. `P4.21`: *"The old refunds address
          // 404s or redirects **deliberately**. No silent dead link."*
          { path: REFUNDS_LEGACY_ROUTE.slice(1), element: <RefundsLegacyRedirect /> },
          // ⚠ **`P3.3` — 2·5d REFUND DETAIL, AND THE ORDER IS LOAD-BEARING.**
          // It is declared AFTER the static `/finance/refunds` redirect above
          // deliberately: React Router ranks a static segment over a dynamic
          // one either way, and reading them in this order is how the next lane
          // sees that `refunds` alone still redirects while `refunds/<id>`
          // opens the detail (the `deposits/import` shape this file already
          // records twice).
          //
          // **A `/finance` ADDRESS FOR A PAYMENTS RECORD, DELIBERATELY** —
          // Finance blueprint `P3.9`: *"Refund detail is payments' — Finance
          // draws it at a `/finance` address; the seam is declared, not
          // assumed."* The LIST moved to `/payments/refunds` on 2026-09-23 and
          // that is not reversed; what a Finance approver opens is the one
          // refund they are about to agree to.
          { path: REFUND_DETAIL_ROUTE.slice(1), element: <RefundDetailPage /> }, // S58 detail
          // `P1.21` — the batch composer. TWO segments, so it can never be
          // read as the `/:tab` catch-all below, and it is registered ABOVE it
          // anyway (the DEF-520 route-ordering shape).
          {
            path: `${FINANCE_ROUTE.slice(1)}/journal-entries/new`,
            element: <JournalBatchPage />,
          },
          {
            path: `${FINANCE_ROUTE.slice(1)}/journal-entries/:entryId/edit`,
            element: <JournalBatchPage />,
          },
          // ⚠ **`DEF-LED-6723` — S56's DETAIL, AND THE ORDER IS LOAD-BEARING.**
          // Declared AFTER the static `/new` and after `/:entryId/edit`
          // deliberately, the `REFUND_DETAIL_ROUTE` shape three blocks up:
          // React Router ranks a static segment over a dynamic one either way,
          // and reading them in this order is how the next lane sees that
          // `journal-entries/new` composes, `journal-entries/<id>/edit` edits a
          // DRAFT, and `journal-entries/<id>` OPENS a posted entry read-only.
          //
          // The Product Owner reported it on v2.351.84: *"on this screen user
          // is unable to see detail screen of Journal entry - we cannot click
          // on eye."* The eye was correctly disabled — the path was registered
          // DELETE-only and there was nothing to open.
          {
            path: JOURNAL_ENTRY_DETAIL_ROUTE.slice(1),
            element: <JournalEntryDetailPage />,
          }, // S56 detail
          { path: `${FINANCE_ROUTE.slice(1)}/taxes`, element: <RemittancePage /> }, // S41
          { path: `${FINANCE_ROUTE.slice(1)}/gl`, element: <GeneralLedgerPage /> }, // S56
          { path: `${FINANCE_ROUTE.slice(1)}/export`, element: <CloseExportPage /> }, // S42·S43
          // S73 · S74 — the captured payable side (2026-08-16, surface-debt
          // tails lane). `apps/ledger/cost_capture.py` and
          // `cost_reconciliation.py` shipped on 2026-08-15 as 1,700 tested,
          // LE-11/LE-12/LE-13-verified lines with `D=deferred(no-API-half)` in
          // their own trailers, so a utility could capture no supplier invoice,
          // see no register, and never learn what fraction of the water it
          // bought it had failed to bill — the ONE figure the Product Owner
          // said an accounting package cannot produce and this product can.
          // Hard-won law 2, for the fifth time in this module.
          //
          // Static and declared with its Finance siblings ABOVE `:tab`, so
          // React Router can never read `cost-of-service` as a tab name.
          { path: COST_OF_SERVICE_ROUTE.slice(1), element: <CostOfServicePage /> }, // S73·S74
          // BR-SHL-011 — an unknown `:tab` falls back to the LANDING tab and
          // never 404s. That is `gl` from CR-060 T10 onward, so this element
          // moves with `financeTabFrom`'s fallback: leaving it on
          // `RevenueArPage` would highlight General ledger in the strip while
          // rendering Revenue & AR's body, which is a screen lying about where
          // the reader is.
          { path: `${FINANCE_ROUTE.slice(1)}/:tab`, element: <GeneralLedgerPage /> },
          // S59 · S60. `/reports` itself is S44, the report LIBRARY, and belongs
          // to US-REP-001 — it is not minted here, so the parent path falls
          // through to the catch-all below and these two are reached from S36's
          // panels and from the breadcrumb.
          //
          // ⚠ THAT SENTENCE WAS TRUE AND STILL SHIPPED A DEVELOPER STRING TO A
          // PRODUCTION USER (DEF-152, 2026-08-16). Being right about the gap in
          // a comment is not a state a user can read — hard-won law 1. What
          // changed today is the catch-all: `/reports` is now a REGISTERED
          // unbuilt destination (`UNBUILT_SIDEBAR_DESTINATIONS` in
          // components/NotBuiltYet.tsx), so it says in plain English what the
          // report library will do, what it is waiting on, and links the two
          // viewers that ARE finished — which also answers the old "thinner
          // wiring than they deserve" note below. The library is still what
          // properly fixes it, and it is still US-REP-001's.
          { path: ACCOUNT_LEDGER_ROUTE.slice(1), element: <AccountLedgerReportPage /> }, // S59
          { path: BY_PREMISES_ROUTE.slice(1), element: <ByPremisesReportPage /> }, // S60
          // CR-060 C16 / T17 — the customer statement. NO A1 SCREEN ID and
          // none is minted: the report was designed after A1 was extracted
          // from a prototype that has since been deleted, so an id here
          // would be a citation resolving to nothing (hard-won law 8 asks
          // for the gap to be REPORTED, which its Lifecycle trailer does).
          // The customer rides in `?customer=`, so this path is static and
          // nothing can be swallowed by a wildcard segment.
          {
            path: CUSTOMER_STATEMENT_ROUTE.slice(1),
            element: <CustomerStatementPage />,
          },
          // S44 — the report LIBRARY, which the comment above spent a paragraph
          // explaining the absence of. US-REP-001 landed it on 2026-08-16, so
          // `/reports` is a screen and its register entry in
          // `UNBUILT_SIDEBAR_DESTINATIONS` is removed in the same commit (the
          // register's own rule: an entry outlives its gap or it becomes the
          // stale comment hard-won law 1 is about).
          { path: REPORTS_ROUTE.slice(1), element: <ReportLibraryPage /> }, // S44
          // ── CR-142-BRC07 `P0.8` (2026-09-26) · THE FOUR RESERVED SEGMENTS ──
          //
          // ⚠ **THESE MUST RANK ABOVE `:reportKey` AND THE HAZARD IS NOT
          // ROUTER PRECEDENCE — IT IS THE VOCABULARY.** `:reportKey` is a
          // catch-all over a name a TENANT chooses, and *custom*, *dashboard*,
          // *scheduled* and *history* are four ordinary English words a utility
          // could each name a report. Without these four lines a user asking
          // for History reaches the viewer with `reportKey = "history"`, which
          // the server refuses with VAL-005 — the brief's own sentence:
          // *"a user asking for History gets a report named 'history'"*.
          //
          // Generated from `RESERVED_REPORT_SEGMENTS` rather than typed out
          // four times, so the routing table and the test that pins it read
          // ONE list. Typing an eleventh service by hand in two places is how
          // `fire` failed silently (CLAUDE.md, B14 rule 2's worked case), and
          // four segments in three files is the same shape one size down.
          // ── `CR-142-BRC07` `P3.2` (2026-09-27) · `history` STOPS BEING A
          // PLACEHOLDER ──
          //
          // ⚠ **THE OTHER THREE SEGMENTS STAY EXACTLY AS THEY WERE.** `custom`,
          // `dashboard` and `scheduled` are still Phase 0's held addresses;
          // only `history` has a screen behind it now. The list they are
          // generated from is still ONE list, so the router and
          // `reportsReservedSegments.test.tsx` still read the same source —
          // `history` is simply filtered out of it here rather than being
          // deleted from it, because the SEGMENT is still reserved (a tenant
          // may still name a report *History*) even though it now resolves to a
          // real screen.
          // ── `CR-142-BRC07` `P4.5` (2026-09-27) · `scheduled` STOPS BEING A
          // PLACEHOLDER TOO ──
          //
          // ⚠ **`custom` AND `dashboard` STAY EXACTLY AS THEY WERE.** `custom`
          // is Phase 5's and `dashboard` is `P4.11`'s, which this lane did not
          // reach. The list is still ONE list, so the router and
          // `reportsReservedSegments.test.tsx` still read the same source —
          // the two live segments are FILTERED OUT here rather than deleted
          // from it, because the SEGMENTS are still reserved (a tenant may
          // still name a report *History* or *Scheduled*) even though they now
          // resolve to real screens.
          // ── `CR-142-BRC07` `P5.10` (2026-09-27) · `custom` JOINS THEM ──
          //
          // ⚠ **ONLY `dashboard` IS STILL A PLACEHOLDER**, and `custom` is
          // filtered out here rather than deleted from the list for exactly
          // the reason the two notes above give: the SEGMENT is still
          // reserved. A tenant may still try to name a report *Custom*, and
          // `apps/reports/definitions.RESERVED_KEYS` refuses it by name —
          // `test_rep_p5_definition_crud.py` asserts the two lists equal
          // because they live in different languages and cannot import each
          // other, which is the `fire` defect four segments down.
          // ── `CR-142-BRC07` `P4.11` (2026-09-27) · `dashboard` IS THE LAST ──
          //
          // ⚠ **EVERY ONE OF THE FOUR RESERVED SEGMENTS NOW RESOLVES TO A REAL
          // SCREEN, SO THIS `filter` NOW REMOVES ALL OF THEM AND THE SPREAD IS
          // EMPTY.** It is kept rather than deleted for the reason the three
          // notes above each give: the SEGMENTS are still reserved. A tenant may
          // still try to name a report *Dashboard*, `apps/reports/definitions
          // .RESERVED_KEYS` refuses it by name, and `test_rep_p5_definition_crud
          // .py` asserts the two lists equal because they live in different
          // languages and cannot import each other. Deleting the list here would
          // leave that assertion comparing the server's four against nothing.
          ...RESERVED_REPORT_SEGMENTS.filter(
            (segment) =>
              segment !== "history" &&
              segment !== "scheduled" &&
              segment !== "custom" &&
              segment !== "dashboard",
          ).map((segment) => ({
            path: `${REPORTS_ROUTE.slice(1)}/${segment}`,
            element: <ReportsTabRoute segment={segment} />,
          })),
          // 1·2 — the Custom sub-tab. ONE screen with `/reports`, opened on its
          // second sub-tab, rather than a second catalogue to keep in step:
          // p23 calls the strip *"the whole argument for a sub-tab over a
          // filter"*.
          {
            path: `${REPORTS_ROUTE.slice(1)}/custom`,
            element: <ReportLibraryPage initialOrigin="custom" />,
          },
          // ── `DEF-REP-7640` (2026-09-28) · 2·2 ON A BLANK DEFINITION ──────
          //
          // Where `+ Build your own` goes. PO ruling 2026-09-28, verbatim:
          // *"Opens the editor on a blank definition, then Save as"*.
          //
          // ⚠ **UNDER `custom/`, SO THE SIGNED RESERVED LIST STAYS AT FOUR.**
          // `/reports/new/edit` would have needed `new` added to
          // `RESERVED_REPORT_SEGMENTS` and to `apps/reports/definitions
          // .RESERVED_KEYS`, because `:reportKey` is a catch-all over a name a
          // TENANT chooses and *New* is an ordinary English word a utility
          // could name a report. `custom` is already on both lists and the
          // server already refuses it BY NAME, so nothing under this prefix
          // can ever collide with a report. The whole argument is on
          // `REPORT_BUILDER_NEW_ROUTE` itself.
          //
          // ⚠ **THREE SEGMENTS, SO `:reportKey` (two) CANNOT SWALLOW IT** and
          // `:reportKey/edit` cannot either — that one needs a literal `edit`
          // in the second position. Written above both anyway, because the
          // ORDER is what a reader checks.
          {
            path: REPORT_BUILDER_NEW_ROUTE.slice(1),
            element: <ReportEditorPage blank />,
          }, // S47
          // 3·1 — the Reports DASHBOARD tab. `CR-142-BRC07` `P4.11`–`P4.13`.
          //
          // ⚠ **THIS IS NOT `/dashboard`, AND THE TWO MUST NEVER BE MERGED.**
          // The shell's dashboard at `/:tenant/dashboard` is rail item 1 and is
          // fenced by PO ruling (p36: *"no i dont want to update existing
          // dashboard … you can create a tab - dont replace existing one"*).
          // This is an owner's monthly read at a different address, and it is
          // reached from the Reports tab strip and from nowhere else — p37
          // DOORS rules out a link from the shell dashboard by name, because
          // adding one is touching a fenced screen.
          { path: `${REPORTS_ROUTE.slice(1)}/dashboard`, element: <ReportsDashboardPage /> },
          // 4·1 — the Scheduled tab. `CR-142-BRC07` `P4.5`.
          { path: `${REPORTS_ROUTE.slice(1)}/scheduled`, element: <ScheduledTab /> },
          // 5·1 — the run history, and 5·2 as a child of it: the dialog is an
          // ADDRESS, so a row a clerk sends a colleague opens the same run.
          { path: `${REPORTS_ROUTE.slice(1)}/history`, element: <ReportRunsPage /> },
          { path: `${REPORTS_ROUTE.slice(1)}/history/:runId`, element: <ReportRunsPage /> },
          // ── PO ruling 2026-09-28 · 2·2, THE BUILDER, AT ITS OWN ADDRESS ──
          //
          // ⚠ **A CHILD SEGMENT, SO THE SIGNED RESERVED LIST DOES NOT MOVE.**
          // `custom`, `dashboard`, `scheduled` and `history` each had to be
          // reserved because `:reportKey` is a catch-all over a name a TENANT
          // chooses. `edit` is not a fifth of those: a report key is
          // `[a-z0-9_]` and never holds a slash, so `/reports/edit` is still a
          // report a utility may call *Edit* and `/reports/edit/edit` is that
          // report's builder. The path is built by `editorRouteFor` — ONE
          // source, shared with the `Edit` door, the legacy redirect and the
          // tests (the skill's §12: never hand-type a list, or a path).
          //
          // ⚠ **IT IS THREE SEGMENTS AND THE VIEWER IS TWO**, so neither can
          // swallow the other whatever the order. It is written ABOVE the
          // viewer anyway, because the ORDER is what a reader checks.
          {
            path: `${REPORT_EDITOR_ROUTE_PATTERN.slice(1)}`,
            element: <ReportEditorPage />,
          }, // S47
          // S46 — the viewer, LAST among the /reports paths so the two static
          // segments above can never be swallowed by `:reportKey`. React Router
          // ranks static over dynamic, so this is belt and braces; the ORDER is
          // what a reader checks, and it reads correctly.
          { path: `${REPORTS_ROUTE.slice(1)}/:reportKey`, element: <ReportViewerPage /> }, // S46
          // ── CR-070 wave A (2026-09-03) · the Work shell — Work-006 · 007 · 005 ──
          // `/work` was the registered not-built-yet destination while the module
          // behind it was an open question; the PO ruled the module on 2026-09-03
          // and its register entry left `UNBUILT_SIDEBAR_DESTINATIONS` in this
          // commit (the register's own rule: an entry outlives its gap or it
          // becomes the stale comment hard-won law 1 is about).
          //
          // THREE FLAT ROUTES, ONE SHELL, ON PURPOSE. `WorkShell` takes the active
          // tab and the screen as children rather than nesting an `<Outlet/>`
          // under an `index` child — the `PremisesTabsPage` shape — so the
          // screen-id table stays one row per route (`screenIds.test.tsx`
          // flattens an index child onto its parent's path and would see `/work`
          // twice). `/work` and `/work/orders` are the same screen, WRK-01.
          // Every segment is static; no `:id` converter sits above these paths.
          {
            path: WORK_ROUTE.slice(1),
            element: (
              <WorkShell tab="orders">
                <OrdersPage />
              </WorkShell>
            ),
          }, // WRK-01
          {
            path: WORK_ORDERS_ROUTE.slice(1),
            element: (
              <WorkShell tab="orders">
                <OrdersPage />
              </WorkShell>
            ),
          }, // WRK-01
          // ── CR-070 wave I — Work-021, the edit screen (US-WRK-031) ──────
          //
          // ⚠ **MOUNTED IN THE SAME COMMIT AS THE COMPONENT AND THE ROW ACTION
          // THAT OPENS IT.** Hard-won law 2 and its mirror: a screen with no
          // route is dead UI, and a route no door points at is a screen nobody
          // can reach. Both halves land together.
          //
          // The `:orderId` is a uuid in the ADDRESS and never on the page —
          // B14 rule 31. What a dispatcher reads and quotes is `WO-4821`.
          {
            path: WORK_ORDER_EDIT_ROUTE.slice(1),
            element: (
              <WorkShell tab="orders">
                <OrderEditPage />
              </WorkShell>
            ),
          }, // WRK-03
          // ── CR-070 wave I — the map (US-WRK-029), a sub-screen of Work-007 ─
          //
          // Its own address so a dispatcher can bookmark the day's pins, and so
          // the Map tab is a REAL LINK rather than local state that vanishes on
          // reload.
          {
            path: WORK_MAP_ROUTE.slice(1),
            element: (
              <WorkShell tab="map">
                <WorkMapPage />
              </WorkShell>
            ),
          }, // WRK-09
          // CR-070 wave B — the approval queue (Work-009, US-WRK-003). MOUNTED
          // HERE AND NOWHERE ELSE: the page component exists, the tab links to
          // it and the endpoint answers, and without this row all three are a
          // control onto nothing (hard-won law 2 — built is not wired).
          {
            path: WORK_AWAITING_APPROVAL_ROUTE.slice(1),
            element: (
              <WorkShell tab="approvals">
                <AwaitingApprovalPage />
              </WorkShell>
            ),
          }, // WRK-20
          // CR-187-BRC10 (EP-WRK-11) — `Work-034`, *From the field*: ONE screen,
          // three panes, three addresses, all under the one Work tab. Mounted
          // in the same commit as the tab that links here (hard-won law 2).
          // ⚠ The bare `/work/field` is declared FIRST and the two sub-panes
          // after; they are different lengths, so neither can swallow the
          // other, and the screen-id table reads them in this order.
          {
            path: WORK_FIELD_ROUTE.slice(1),
            element: (
              <WorkShell tab="field">
                <FieldDeskPage view="results" />
              </WorkShell>
            ),
          }, // WRK-26
          {
            path: WORK_FIELD_RAISED_ROUTE.slice(1),
            element: (
              <WorkShell tab="field">
                <FieldDeskPage view="raised" />
              </WorkShell>
            ),
          }, // WRK-26
          {
            path: WORK_FIELD_ALERTS_ROUTE.slice(1),
            element: (
              <WorkShell tab="field">
                <FieldDeskPage view="alerts" />
              </WorkShell>
            ),
          }, // WRK-26
          {
            // BR-WRK-067 (PO 2026-10-22) — route findings, the fourth pane.
            path: WORK_FIELD_FINDINGS_ROUTE.slice(1),
            element: (
              <WorkShell tab="field">
                <FieldDeskPage view="findings" />
              </WorkShell>
            ),
          }, // WRK-26
          {
            // CR-194-BRC10 (PO 2026-10-26, "store on both") — refused field work, the fifth pane.
            path: WORK_FIELD_REFUSED_ROUTE.slice(1),
            element: (
              <WorkShell tab="field">
                <FieldDeskPage view="refused" />
              </WorkShell>
            ),
          }, // WRK-26
          // CR-070 wave C — the parts register (Work-025). The register is the
          // ONE parts screen: the Settings → Reference data card for it is a
          // `kind: "link"` that navigates here (BR-TEN-033), rather than a
          // second, weaker list inside a Settings modal.
          // CR-070 wave F — `Work-023`, the crews list, and `Work-024`, one
          // technician. The DETAIL sits UNDER the list's own address, which is
          // the address `WS-24` draws: `/brazosbend/work/crews/r-patel`.
          //
          // ⚠ THE LIST PATH IS DECLARED BEFORE THE `:slug` ONE, for the reason
          // written against the templates pair below: React Router matches
          // neither against the other today, but a later sibling literal
          // WOULD be swallowed by the slug route — so the ordering is written
          // now, while it costs nothing, rather than found then.
          {
            path: WORK_CREWS_ROUTE.slice(1),
            element: (
              <WorkShell tab="crews">
                <CrewsPage />
              </WorkShell>
            ),
          }, // WRK-07
          // NOT inside `WorkShell`: the tab strip is a strip of LISTS, and a
          // record detail sits under its own `← Crews` instead — the same
          // shape every other detail screen takes (`DEF-WRK-3724`).
          {
            path: `${WORK_CREWS_ROUTE.slice(1)}/:slug`,
            element: <TechnicianDetailPage />,
          }, // WRK-08
          {
            path: WORK_PARTS_ROUTE.slice(1),
            element: (
              <WorkShell tab="parts">
                <PartsPage />
              </WorkShell>
            ),
          }, // WRK-10
          // CR-077 — the parts upload. The SAME five-stage runner every other
          // target uses (`BR-MET-096`: one process, the target is a
          // parameter), so there is no second page and no second wizard.
          //
          // ⚠ **NOT INSIDE `WorkShell`, and the reason is `DEF-WRK-3724`'s:**
          // the strip is a strip of LISTS, and a wizard sits under its own ←,
          // which is what `workflow.parts.return` names.
          //
          // ⚠ **DECLARED BEFORE ANY `:slug` UNDER `work/parts`** — there is
          // none today, and this is where it would have to stay if one is ever
          // added, or `import` would be read as a part's own id.
          {
            path: `${WORK_PARTS_ROUTE.slice(1)}/import`,
            element: <ImportWorkflowPage target="parts" />,
          }, // WFL-01 (parts)
          // CR-070 wave M — `Work-026`, `US-WRK-037`. The rules LIST is a tab;
          // the five-step builder is NOT inside `WorkShell`, because the strip
          // is a strip of LISTS and a wizard sits under its own ←
          // (`DEF-WRK-3724`).
          //
          // ⚠ **THE STATIC `new` IS DECLARED BEFORE THE LIST'S OWN PATH IS
          // EXTENDED** — `/work/rules/new` and `/work/rules` are different
          // lengths so neither can swallow the other, but the ordering stays
          // belt-and-braces the day somebody adds `/work/rules/:ruleId`.
          {
            path: WORK_RULE_BUILDER_ROUTE.slice(1),
            element: <RuleBuilder />,
          }, // WRK-13
          // CR-168-BRC10 round 5, lane RULES — the SAME builder re-opened on a
          // rule (P3.17), and one rule's own page (P3.62, images 62–64). Both
          // sit AFTER the static `new`, or `new` is read as a rule's id; the
          // page sits under its own ← like every Work record (`DEF-WRK-3724`).
          {
            path: WORK_RULE_EDIT_ROUTE.slice(1),
            element: <RuleBuilder />,
          }, // WRK-13
          {
            path: WORK_RULE_DETAIL_ROUTE.slice(1),
            element: <RuleDetailPage />,
          }, // WRK-06.rule
          {
            path: WORK_RULES_ROUTE.slice(1),
            element: (
              <WorkShell tab="rules">
                <RulesPage />
              </WorkShell>
            ),
          }, // WRK-06
          // CR-168-BRC10 §30 — At risk, its own tab next to Orders (PO answer
          // (1), 2026-10-05). `.slice(1)` for the reason below.
          {
            path: WORK_AT_RISK_ROUTE.slice(1),
            element: (
              <WorkShell tab="at-risk">
                <AtRiskPage />
              </WorkShell>
            ),
          }, // WRK-25
          // CR-070 wave N — `Work-027`, `US-WRK-054`. ⚠ `.slice(1)` because
          // this branch is already mounted under `:tenant`; the constant is
          // tenant-less for exactly that reason (`DEF-WRK-4051`).
          {
            path: WORK_PERFORMANCE_ROUTE.slice(1),
            element: (
              <WorkShell tab="performance">
                <PerformancePage />
              </WorkShell>
            ),
          }, // WRK-16
          // CR-070 wave D — `Work-013`, the templates LIST. It replaces the
          // blank page the PO ruled on 2026-08-25 (*"Just keep it black - and
          // show note that Work orders not yet build"*), whose own header
          // recorded, measured, the three facts that made the absence honest:
          // there was no writer for `work_order_templates`, `sample_data.py`
          // said so in as many words, and nothing read the 24 seeded starter
          // rows. All three are false now, so the stated absence goes in the
          // commit that makes it untrue.
          //
          // ⚠ THE STATIC LIST PATH IS DECLARED BEFORE THE `:templateId` ONE.
          // React Router would match `/work/templates` against neither, but a
          // later sibling literal (`/work/templates/new`, which wave E adds for
          // the builder) WOULD be swallowed by the id route — so the ordering
          // is written now, while it costs nothing, rather than found then.
          {
            path: WORK_ORDER_TEMPLATES_ROUTE.slice(1),
            element: (
              <WorkShell tab="templates">
                <TemplatesPage />
              </WorkShell>
            ),
          }, // WRK-04
          // CR-070 wave E — `Work-014`…`017`, the eight-step builder.
          //
          // ⚠ **THE STATIC `new` IS DECLARED BEFORE `:templateId`, AND THIS IS
          // THE SIBLING WAVE D SAID WOULD ARRIVE.** Wave D wrote, in this file:
          // *"a later sibling literal (`/work/templates/new`, which wave E adds
          // for the builder) WOULD be swallowed by the id route — so the
          // ordering is written now, while it costs nothing, rather than found
          // then."* It cost nothing, and here is the literal it was written
          // for. React Router ranks a static segment above a dynamic one, so
          // the order is belt and braces rather than the only guard — which is
          // exactly the posture `/connections/new` takes one module over.
          //
          // NOT inside `WorkShell`: the tab strip is a strip of LISTS, and a
          // wizard sits under its own `← Work order templates` (the same shape
          // `Work-022` takes, `DEF-WRK-3724`).
          {
            path: WORK_TEMPLATE_NEW_ROUTE.slice(1),
            element: <TemplateBuilder />,
          }, // WRK-05.n
          {
            path: templateEditPath(":templateId").slice(1),
            element: <TemplateBuilder />,
          }, // WRK-05.n
          // CR-070 wave H — `Work-008` (the order detail) and the three-step
          // new-order wizard, `WM-20`'s sub-screen of `Work-007`.
          //
          // ⚠ **THE STATIC `new` IS DECLARED BEFORE `:orderNo`, AND THIS IS THE
          // THIRD TIME THIS FILE HAS MADE THAT NOTE PAY.** Wave D wrote it for
          // `/work/templates/new`, wave E collected it, and the same pair
          // arrives here: `/work/orders/new` would be swallowed by the id route
          // if the ordering ever stopped being belt and braces.
          //
          // ⚠ **MOUNTING THESE TWO ADDRESSES RELEASES WAVE G's TWO HELD
          // CONTROLS, AND `OrdersPage.test.tsx` FAILS UNTIL THEY ARE.** That is
          // hard-won law 2's mirror clause working exactly as it was written:
          // wave G declared `ORDERS_HELD_CONTROLS` with the address that
          // releases each, so landing the screens turns the suite red and NAMES
          // the button rather than leaving a live screen behind a dead door
          // (`DEF-CWP-3925`, where five of eight portal doors refused over
          // screens that had shipped days earlier).
          //
          // NOT inside `WorkShell`: the tab strip is a strip of LISTS, and both
          // a record detail and a wizard sit under their own ← instead
          // (`DEF-WRK-3724`).
          {
            path: NEW_ORDER_WIZARD_ROUTE.slice(1),
            element: <NewOrderWizard />,
          }, // WRK-12
          {
            path: WORK_ORDER_DETAIL_ROUTE.slice(1),
            element: <OrderDetailPage />,
          }, // WRK-02
          // `Work-022`, the template DETAIL. NOT inside `WorkShell`: the tab
          // strip is a strip of LISTS, and a record detail sits under its own
          // `← Templates` instead — the same shape every other detail screen in
          // this product takes (r10 rule 1, `DEF-WRK-3724`).
          {
            path: WORK_TEMPLATE_DETAIL_ROUTE.slice(1),
            element: <TemplateDetailPage />,
          }, // WRK-15
          // Every address with no screen. NEVER a developer string — see above.
          { path: "*", element: <NotBuiltYetPage /> },
        ],
      },
    ],
  },
];

// CR-016 addendum (PO 2026-08-19) — *"display that as a tag - right bottom for
// every UI screen so that we know which scren has a problem"*.
//
// A PATHLESS LAYOUT ABOVE EVERYTHING, so the tag mounts ONCE and covers the
// public pages, the sign-in page and every screen inside the shell alike. The
// alternative — mounting it in AppShell — would miss the four screens that
// render outside the shell, which are exactly the screens a signup problem
// gets reported from.
//
// ⚠ `APP_ROUTES` IS DELIBERATELY LEFT UNWRAPPED and this composes ON TOP of
// it. Four existing suites read `APP_ROUTES` directly and one of them indexes
// into it by shape (`APP_ROUTES.find(r => r.path === "/:tenant")?.children?.[1]`
// in BillRunWizard.test.tsx). Wrapping the exported constant would break that
// silently — the `find` returns undefined and the test reads as though the
// route vanished. So the export keeps its shape and the browser router gets
// the chrome.
function RootChrome() {
  return (
    <>
      <Outlet />
      <ScreenIdTag />
      {/* CR-169-BRC10 — one `screen_viewed` per screen, all three apps, from
          the same single mount as the tag and for the same reason. */}
      <AnalyticsPageViews />
    </>
  );
}

/** What the BROWSER runs: every route in `APP_ROUTES`, under the chrome above. */
export const ROOT_ROUTES: RouteObject[] = [{ element: <RootChrome />, children: APP_ROUTES }];

// Built on FIRST RENDER, not at import: `createBrowserRouter` reaches for
// `document`, and the route TABLE above must stay importable without a DOM so
// the routing contract (a deep link renders its screen with the tenant in
// scope) can be tested on a memory history.
let browserRouter: ReturnType<typeof createBrowserRouter> | null = null;

function appRouter(): ReturnType<typeof createBrowserRouter> {
  browserRouter ??= createBrowserRouter(ROOT_ROUTES);
  return browserRouter;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* US-SHL-012 / BR-SHL-021: the ONE global toast surface mounts ABOVE the
          router so an in-flight toast survives a commit → redirect navigation
          (US-SHL-012 TC-6). Modules fire it via useToast(). */}
      <ToastProvider>
        <RouterProvider router={appRouter()} />
      </ToastProvider>
    </QueryClientProvider>
  );
}
