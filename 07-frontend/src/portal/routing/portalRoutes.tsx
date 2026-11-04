// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-001 (EP-CWP-01) — the front page at `/{tenant}/portal`.
// Rules:    BR-CWP-007 · CR-068 §11c (`portalRoutes.tsx` — every CWP screen,
//           one route each) · CR-068 §13 (every route here has a row in
//           screenIds.ts — G82)
// Tests:    src/portal/routing/screenIds.test.ts (the two tables agree)
// ───────────────────────────────────────────────────────
import type { RouteObject } from "react-router-dom";

import { CentrePage, CentresPage } from "../guest/CentresPage";
import { ApplyForServicePage } from "../guest/ApplyForService";
import { FrontPage } from "../guest/FrontPage";
import { ReportPage } from "../guest/ReportPage";
import { TrackPage } from "../guest/TrackPage";
import { QuickServicePage } from "../guest/QuickService";
import { QuickPayPage } from "../guest/QuickPayPage";
import { QuickPayCheckPage } from "../guest/QuickPayCheck";
import { QuickPayDonePage } from "../guest/QuickPayDone";
import { MethodsPage } from "../methods/MethodsPage";
import { AutopayPage } from "../methods/AutopayPage";
import { PayNowCheckPage } from "../payments/PayNowCheck";
import { PayNowDonePage } from "../payments/PayNowDone";
import { PayNowPage } from "../payments/PayNowPage";
import { FeesPage } from "../payments/FeesPage";
import { StartServicePage } from "../guest/StartService";
import { AnswerPage, HelpPage } from "../guest/HelpPage";
import {
  EnrolPage,
  ForgotPasswordPage,
  HomePage,
  SignInPage,
} from "../signin/SignInPages";
import { UpdateEmailPage } from "../signin/UpdateEmail";
import { MyAccountsPage } from "../accounts/MyAccountsPage";
import { YourAccountPage } from "../accounts/YourAccountPage";
import { PremisesStatementPage } from "../premises/PremisesStatementPage";
import { BillsPage } from "../bills/BillsPage";
import { FinalBillPage } from "../bills/FinalBillPage";
import { BillComparisonPage, BillDetailPage, PrintedBillPage } from "../bills/BillPages";
import { AddAccountPage } from "../details/AddAccountPage";
import { MyDetailsPage } from "../details/MyDetailsPage";
import { PreferencesPage } from "../details/PreferencesPage";
import { DocumentsPage } from "../documents/DocumentsPage";
import { LevelPayPage } from "../plans/LevelPayPage";
import { LevelPayStandingPage } from "../plans/LevelPayStandingPage";
import { PlanOfferPage } from "../plans/PlanOfferPage";
import { AskForPlanPage } from "../plans/AskForPlanPage";
import { YourPlanPage } from "../plans/YourPlanPage";
import {
  HelpPayingPage,
  MoneyBackPage,
  OverduePage,
  ProtectionsPage,
} from "../arrears/ArrearsPages";
import { PaymentsPage } from "../payments/PaymentsPage";
import {
  AskAQuestionPage,
  DisputeBillPage,
  TrackRequestPage,
} from "../requests/RequestPages";
import { RequestsPage } from "../requests/RequestsPage";
import { StopOrRestartPage } from "../requests/StopOrRestartPage";
import { EquipmentPage, ReadingsPage, SendReadingPage, UsagePage } from "../usage/UsagePages";

/** Every portal route, relative to `/:tenant/portal`. One row per CWP screen. */
export const PORTAL_ROUTES: RouteObject[] = [
  { path: "/", element: <FrontPage /> },
  // CR-068 wave C — the journey that begins before identity exists.
  // ⚠ `start-service/:draft` IS THE DRAFT LINK and the `:draft` is a
  // CAPABILITY, not a reference: it is what makes *"close the tab and come
  // back"* work (US-CWP-013 TC-1). `SR-26-nnnn` is allocated at submit and
  // never appears in an address bar.
  { path: "/start-service", element: <StartServicePage /> },
  { path: "/start-service/:draft", element: <ApplyForServicePage /> },
  { path: "/ask", element: <QuickServicePage /> },
  // CR-068 wave P (screen half) — CWP-002. ⚠ The LOOKUP ships and the
  // payment does not: no gateway exists (CR-068 R2), so the Pay control
  // renders in its normal place, disabled, carrying its reason (R3).
  { path: "/pay", element: <QuickPayPage /> },
  // ⚠ CR-068 phase 5 — SIX ROUTES REGISTERED ONCE, BEFORE FOUR LANES START.
  // This file and `screenIds.ts` are one file each, and hard-won law 11 is
  // unambiguous about two lanes committing one file: the second silently
  // reverts the first, with a correct file count and its own hunks present.
  // So the addresses are declared here and NO LANE TOUCHES THIS FILE — each
  // owns only the component behind its own route. Every one answers with a
  // holding screen until its lane replaces it, and the walkthrough fails on
  // any `data-holding-screen` left in the DOM.
  { path: "/pay/check", element: <QuickPayCheckPage /> },
  { path: "/pay/done", element: <QuickPayDonePage /> },
  { path: "/pay-now", element: <PayNowPage /> },
  { path: "/pay-now/check", element: <PayNowCheckPage /> },
  { path: "/pay-now/done", element: <PayNowDonePage /> },
  { path: "/payment-methods", element: <MethodsPage /> },
  { path: "/autopay", element: <AutopayPage /> },
  { path: "/fees", element: <FeesPage /> },
  // CR-068 wave D. ⚠ These four routes exist whether or not the utility has
  // published anything — the ABSENCE BR-CWP-093 asks for is the LINK and the
  // page's content, and the server is what refuses: `/help` answers an empty
  // list a screen renders as no rows, and `/visit` 404s outright when no
  // centre is shown, which is why the visit page cannot exist empty.
  { path: "/help", element: <HelpPage /> },
  { path: "/help/:slug", element: <AnswerPage /> },
  { path: "/visit", element: <CentresPage /> },
  { path: "/visit/:slug", element: <CentrePage /> },
  // CR-068 wave B — the two guest doors a stranger uses without an account.
  // CR-068 wave E — getting in. ⚠ `/enrol` IS ONE ROUTE FOR THREE DRAWINGS
  // (`CWP-016` find, `CWP-017` prove, `CWP-018` choose). They are three STEPS
  // of one form and each carries its own `data-screen`; giving each an
  // address would let somebody bookmark *choose a password* for an account
  // they have not proved they hold. The server refuses that anyway
  // (`enrol/set-password` needs a consumed code) — there is simply no reason
  // to draw a door the server then has to close.
  { path: "/sign-in", element: <SignInPage /> },
  { path: "/enrol", element: <EnrolPage /> },
  { path: "/forgot-password", element: <ForgotPasswordPage /> },
  // CR-189-BRC10 — the locked-out customer's email change (CWP-079).
  // ⚠ A literal, not `UPDATE_EMAIL_PATH`: G82 reads this table's `path:`
  // strings. `UpdateEmail.test.tsx` asserts the two agree.
  { path: "/update-email", element: <UpdateEmailPage /> },
  { path: "/home", element: <HomePage /> },
  // CR-068 wave F — CWP-023. ⚠ Its own address, unlike the three enrolment
  // drawings that share `/enrol`: this is a place a landlord comes back to
  // and bookmarks, not a step of a form.
  { path: "/accounts", element: <MyAccountsPage /> },
  // CR-068 wave F — CWP-065. ⚠ No account id in the address: the switcher
  // knows which account is being read, and a database id in a URL is a
  // database id on screen (B14 rule 31).
  { path: "/account", element: <YourAccountPage /> },
  // CR-142-BRC07 `P4.15` — CWP-078, the property statement. ⚠ NO id in the
  // address, for `/account`'s reason and one more of its own: the subject is
  // an ACCOUNT the switcher already holds, and the server walks it to the
  // property (hard rule 8). A premises has no human reference a customer
  // could quote the way `BL-2608-0141` is printed on their bill, so an
  // addressable version of this screen could only have carried a uuid.
  { path: "/property", element: <PremisesStatementPage /> },
  // CR-068 wave G — CWP-027.
  { path: "/bills", element: <BillsPage /> },
  // CR-068 wave H — CWP-028 · CWP-029 · CWP-030. ⚠ **`:number` IS THE BILL
  // NUMBER AND NOT AN ID** (B14 rule 31, PO 2026-08-30: *"no Databse ID on
  // screen - that is a rule"*): `BL-2608-0141` is printed on the paper the
  // customer is holding and is what they would read out on the telephone. A
  // truncated id was never an option either — `accountDetailTabs.tsx` records
  // that eight characters of a uuid used as link text is the same breach.
  //
  // ⚠ The two DEEPER paths are declared BEFORE `/bills/:number`, for a
  // reader's sake rather than the matcher's: `matchPath` is exact and
  // `:number` cannot swallow a second segment, but the order that reads
  // correctly is the order that stays correct if either ever gains a wildcard.
  { path: "/bills/:number/document", element: <PrintedBillPage /> },
  { path: "/bills/:number/comparison", element: <BillComparisonPage /> },
  { path: "/bills/:number", element: <BillDetailPage /> },
  // CR-068 wave G — CWP-024. ⚠ NO account id: a contact detail is edited once
  // and written to every account this login holds (US-CWP-028 TC-10), so an
  // id in the address would promise a per-account edit the product does not do.
  { path: "/my-details", element: <MyDetailsPage /> },
  // CR-068 wave G — CWP-025. ⚠ NO account id, for the same reason
  // `/my-details` has none: one save reaches every account this login
  // holds, so an id in the address would promise a per-account choice
  // the product does not make.
  { path: "/my-details/preferences", element: <PreferencesPage /> },
  // CR-068 wave G — CWP-020, the form that grows the account set.
  { path: "/accounts/add", element: <AddAccountPage /> },
  // CR-068 wave H — CWP-031. ⚠ A read of what was SENT, never of what
  // arrived: post and email remain the delivery record (BR-CWP-083, and
  // OQ-1399 closed 2026-09-04 with the portal as a convenience copy).
  { path: "/documents", element: <DocumentsPage /> },
  // CR-068 wave H — CWP-063. The one plan state where the customer has
  // something to do, and all three of its controls are HELD until OQ-CWP-1568
  // is ruled: a signature is not one of the six writes BR-CWP-001 allows.
  { path: "/plan-offer", element: <PlanOfferPage /> },
  // CR-068 wave H — CWP-044.
  // CR-068 — CWP-066 (US-CWP-055), declared before `/level-pay` so the deeper
  // path stays first if either ever gains a wildcard.
  { path: "/level-pay/standing", element: <LevelPayStandingPage /> },
  { path: "/level-pay", element: <LevelPayPage /> },
  // CR-068 — CWP-032 (US-CWP-037), the closing bill and where the deposit goes.
  { path: "/final-bill", element: <FinalBillPage /> },
  // CR-068 wave H — CWP-033, CWP-034, CWP-037. The shell's `Usage` tab already
  // pointed at `/usage`; until this wave it pointed at nothing, which is the
  // mirror of hard-won law 2 (a link with no screen behind it).
  { path: "/usage", element: <UsagePage /> },
  { path: "/readings", element: <ReadingsPage /> },
  // US-CWP-042 · DEF-CWP-10175 — CWP-035, *Send us your reading*.
  { path: "/usage/submit", element: <SendReadingPage /> },
  { path: "/equipment", element: <EquipmentPage /> },
  // CR-068 wave G — CWP-041. ⚠ NO account id: the money list is one
  // person reconciling one bank statement across every account they hold —
  // the same scope `/bills` and `/documents` take, and BR-CWP-010 does the
  // filtering in the server's query.
  { path: "/payments", element: <PaymentsPage /> },
  // CR-068 wave M — CWP-042 and CWP-043. ⚠ NO account id here either, and
  // it is the SWITCHER that names the account rather than the address: a
  // plan belongs to ONE account, and a database id in a URL is a database
  // id on screen (B14 rule 31) — `/account`'s own reading.
  { path: "/ask-for-a-plan", element: <AskForPlanPage /> },
  { path: "/plan", element: <YourPlanPage /> },
  // CR-068 — CWP-046 (US-CWP-060). ⚠ The shell's `Requests` tab has pointed
  // at `/requests` since wave E and there was no screen behind it: hard-won
  // law 2 in its plainest form, and this route is what closes it.
  { path: "/requests", element: <RequestsPage /> },
  // CR-068 — CWP-052 (US-CWP-062). The one card on the hub that leads
  // somewhere today, besides *Report a problem*.
  { path: "/stop-or-restart", element: <StopOrRestartPage /> },
  // CR-068 wave L1 — CWP-057 · CWP-056 · CWP-064 · CWP-045. ⚠ NO account id in
  // any of the four addresses: each reads ONE account and the switcher names
  // it, exactly as `/plan` and `/account` do (B14 rule 31).
  //
  // ⚠ **THREE OF THE FOUR ARE REACHABLE ONLY WHEN THEY HAVE SOMETHING TO SAY,
  // AND THE SERVER IS WHAT DECIDES** (`BR-CWP-093`): `/overdue` answers
  // `overdue: false` on an account in good standing, `/protections` answers
  // `any: false` where no hold exists, and `/money-back` answers `any: false`
  // where there is neither a credit nor a refund. Each screen then states one
  // sentence rather than drawing an empty ladder, three empty cards or two
  // empty tables — an empty ladder reads as *we have already sent everything*
  // to the person least able to check.
  { path: "/overdue", element: <OverduePage /> },
  { path: "/help-paying", element: <HelpPayingPage /> },
  { path: "/protections", element: <ProtectionsPage /> },
  { path: "/money-back", element: <MoneyBackPage /> },
  // CR-068 wave R — CWP-051, CWP-055, CWP-054.
  //
  // ⚠ **`/bills/:number/dispute` IS DECLARED AFTER THE THREE `/bills/:number`
  // ROUTES ABOVE, FOR A READER RATHER THAN FOR THE MATCHER** — `matchPath` is
  // exact and `:number` cannot swallow a second segment, which is the reading
  // the wave-H block already records for `/document` and `/comparison`.
  //
  // ⚠ **NEITHER `/requests/:reference` NOR `/ask-a-question` CARRIES AN ACCOUNT
  // ID.** A service request belongs to a person rather than to one account, and
  // a uuid in an address is a database id on screen (B14 rule 31).
  { path: "/requests/:reference", element: <TrackRequestPage /> },
  { path: "/bills/:number/dispute", element: <DisputeBillPage /> },
  { path: "/ask-a-question", element: <AskAQuestionPage /> },
  { path: "/report", element: <ReportPage /> },
  { path: "/track", element: <TrackPage /> },
];
