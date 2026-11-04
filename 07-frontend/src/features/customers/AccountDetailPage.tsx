// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-025 (the Bills tab embeds billing's own S30 list, scoped by
//           `f.account_id` — 11b §2.6, not a customers read model) ·
//           US-CUS-008 (S21 detail header, status pills & action rails) ·
//           US-CUS-009 (Overview tab — customer / payment / deposit / portal panels) ·
//           US-CUS-010 (financial tabs: Bills · Payments · Adjustments) ·
//           US-CUS-011 (operational tabs: Usage · Meters · Documents · Notes · Audit)
//           Screens: S21 (entered from the S17 row and from `/accounts/{id}`)
//           AMENDED 2026-08-15 (tenant custom-fields lane): US-SHL-016 (EP-SHL-07 — S21 renders the tenant's own fields read-only from
//           the ACCOUNT ROW, never from a live join)
// Rules:    BR-CUS-016 (the stored status is a status; Current / 30d past /
//           60+ past are DERIVED from open invoices and NEVER stored) ·
//           BR-CUS-018 (a draft occupies nothing — activation is its own call) ·
//           BR-CUS-023 (the deposit is a LOOKUP from the plan deposit schedule) ·
//           BR-CUS-028 (portal data is not fabricated in v1) ·
//           BR-CUS-029 (the account plan snapshot has NO table — the unit's
//           plan is never substituted for it) · BR-CUS-030 (closing an account
//           is the Move-Out flow, not a status flip) · BR-CUS-034 (other
//           modules are read through service functions, never copied here) ·
//           BR-CUS-045 (contact PII — the last four of a government id is all
//           the server holds) · BR-CUS-054 (the first-class customer entity —
//           BUILT 2026-08-11, so "all accounts for this customer" IS rendered
//           when the account carries a link; an account with none still shows
//           the primary CONTACT's name) · BR-CUS-055 (the seeded,
//           tenant-extensible statuses and their behaviour classes) ·
//           BR-CUS-057 (deposit interest accrual) · BR-CUS-058 (the credit tier
//           is COMPUTED — there is no input path) · BR-CUS-059 (autopay is
//           capture-only in v1) · BR-SHL-020 (the six A18 states, composed) ·
//           BR-SHL-023 (one money path) · BR-SHL-025 (a forbidden control is
//           disabled WITH its reason) · BR-SHL-034 (one date formatter) ·
//           BR-SHL-044 (one page header, exactly one primary action)
// ───────────────────────────────────────────────────────
// S21 — the account detail. `GET /accounts/{id}` was served with nothing
// reading it; this is the screen that reads it, and it renders WHAT THE
// ENDPOINT ACTUALLY ANSWERS.
//
// The prototype's S21 is a header card, ten actions and nine tabs of
// data.
//
// ⚠ **"A TEN-ACTION RAIL" IS WHAT THIS LINE SAID UNTIL 2026-08-24, AND THE
// MISCOUNT IS WHY B18's D2 EXISTED AT ALL.** r10 draws the ten as TWO controls,
// not one rail: an ACTION STACK of three worded buttons beside the metric
// columns (`Record payment` primary · `Adjust` · `Move-out`, task 3.3) and an
// ICON RAIL of seven glyphs beneath them (task 3.2). B18 read this docstring
// against the screenshot, got ten against seven, and raised D2 —
// *"which three left, and what does each of the seven do?"* Nothing had left.
// BR-SHL-045 (PO 2026-08-24) rules the seven and the answer: ✉ Send statement ·
// 🖨 Print bill · $ Issue credit · ⇄ Change plan · ⚡ Disconnect notice ·
// 🗓 Payment plan · ✎ Add note, in `AccountIconRail.tsx`.
//
// Most of that data belongs to modules that do not exist yet, and this
// screen states each gap instead of drawing an empty table (which asserts
// "none") or a dash in a money column (which asserts "zero"):
//
//   · **No plan block.** The server sends `plan: null` WITH
//     `plan_snapshot_unavailable: "BR-CUS-029"` — the account plan snapshot has
//     no DDL in any signed document. The unit's plan is NOT put in its place:
//     the two are equal only until the first override (BR-CUS-010), and billing
//     prices from the snapshot (BR-CUS-014 sc.6).
//   · ~~**No recent bills.**~~ **AMENDED 2026-08-24 (CR-030 W3 · 3.4).** The
//     Overview's recent-bills panel READS `GET /invoices?f.account_id=` now —
//     the endpoint this file's own Bills tab has used since 2026-08-11, which
//     is exactly what DEF-474 was filed about. **The due date and the ageing
//     state are still absent** and still need an AR position billing publishes
//     for no account. The balance itself IS served — the LEDGER's figure since
//     DEF-127, not the `accounts.balance` cache — so it renders with where it
//     came from attached rather than as an AR position. **The BILLS tab is no longer in this list**
//     (amended 2026-08-11, W3 billing lane): it renders billing's own S30 list
//     scoped by `f.account_id`, which is 11b §2.6's account scoping of
//     `GET /invoices` — NOT a customers read model, because BR-CUS-034 forbids
//     one and a per-tab copy is a second place for BR-BIL-063's "a draft has no
//     number" rule to be got wrong. That endpoint is contracted and unserved,
//     and the embedded table reports that in its own A18 §4 state.
//   · **No deposit figure that means anything.** `deposit_on_file` is served,
//     but every write path to it is refused server-side (BR-CUS-023: it is a
//     lookup from the plan deposit schedule, US-CUS-007, unbuilt). Interest
//     accrued has no column at all (BR-CUS-057) and the credit tier is a
//     COMPUTED cache with no computer yet (BR-CUS-058) — both render as
//     not-recorded with their rule, never as $0.00 or "A".
//   · ~~**No customer chip.**~~ **AMENDED 2026-08-11 (US-CUS-019 lane).** This
//     used to read "BR-CUS-054's `customers`/`customer_accounts` tables do not
//     exist, so 'all accounts for this customer' cannot be listed". They exist
//     now (migration 0005), `GET /accounts/{id}` serves the customer, and the
//     chip is rendered — the landlord with three suites reads as one customer
//     with three linked accounts. What is STILL absent is the BR-CUS-019
//     duplicate check at S18 step 1: a customer arrives here only from the
//     import today, and `customer`/`customer_id` remain refused fields on
//     `POST /accounts`. An account with no link renders no chip and falls back
//     to the primary CONTACT's name, which is what every pre-existing account
//     does (hard-won law 1 — the claim moved with what is true).
//   · **Move-out and Move-in are LINKS now** (amended 2026-08-11, lane 3).
//     S20 and S19 exist, so the two header actions navigate to them instead of
//     rendering disabled: the guided pages collect the move-out date and the
//     move-in start date the endpoints require, which is exactly what a bare
//     header button could not. Each is still GUARDED by state, because the
//     server is: only an OCCUPANT can move out (BR-CUS-030) and only a CLOSED
//     account can hand its unit to the next occupant (BR-CUS-017 — a move-in
//     onto a unit that is still held is refused 409). What has not changed is
//     that a status flip to a terminal status is still refused (BR-CUS-030) —
//     closing is a flow, never an edit.
//
// ⚠ **THE PRIMARY SLOT CARRIES "RECORD PAYMENT" — AMENDED 2026-08-24 (CR-030
// W3 · 3.3), AND THE PARAGRAPH IT REPLACES IS WORTH KEEPING FOR THE SHAPE OF
// THE ARGUMENT.** It read: *"The one thing this screen can genuinely DO is
// BR-CUS-018's other half: activate a draft. That is why the ONE primary slot
// carries 'Activate account' rather than the prototype's 'Record payment' — a
// permanently dead button in the primary slot would teach the wrong thing
// about the page."* That was true and it stopped being true: payments landed,
// `POST /accounts/{id}/payments` is served and the S22 modal is live, so the
// button is no longer dead and r10's own action stack — `Record payment`
// (primary) · `Adjust` · `Move-out` — is honourable. Activate moves to the
// rail, where a control that only a pending-activation account can press
// belongs. **The reason expired; the button followed it** (hard-won law 1).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, formErrorEnvelope, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { ACCOUNT_KIND_MASTER, activateAccount, getAccountDetail } from "@/api/endpoints";
import type {
  AccountAddress,
  AccountDetail,
  AccountServiceAgreement,
  RecordedPayment,
  ServerWarning,
} from "@/api/endpoints";
import { CustomFieldsView } from "@/components/CustomFields";
import { DateCell } from "@/components/DateCell";
import { ExemptionLines } from "./AccountTaxExemption";
import { BalanceToOwnerState } from "./BalanceToOwnerState";
import type { RegionalDateFormat } from "@/components/DateCell";
import { formatDate, todayInZone } from "@/components/DateCell";
import { MoneyCell } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { AgreementStatusChip } from "./AccountAgreementsPanel";
import { useToast } from "@/components/Toast";
import { InlineLinkTo, PlainTable, RefusalStrip } from "@/components/Surfaces";
import { assetDetailPath } from "@/features/assets/assetsShared";
import { Panel } from "@/components/Panel";
import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import type { TableRequestState } from "@/components/tableTypes";
import { AuditTab } from "@/features/metering/PremisesDetailPage";
import type { PayForState } from "@/features/payments/PayForSeveral";
import { PAYMENTS_RECORD_NEW_ROUTE } from "@/features/payments/paymentsShared";
import {
  CELL_FULL,
  Fact,
  FactList,
  GuardedButton,
  detailTabFrom,
  isDenied,
  premisesDetailPath,
  unitDetailPath,
  useTenantRole,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
import type { DetailTab, RegionalProps } from "@/features/metering/meteringShared";
// DEF-CUS-3751 — `ServiceTags` was imported here and used nowhere, so this file
// failed `eslint --max-warnings 0` at the branch tip. Its last consumer went
// when the SERVICES cell was rewritten; the comment further down still explains
// what that cell used to draw, which is why the name still read as live.
// ⚠ `ArrivesWith` left this import with `DEF-CUS-4625`: the LAST holding
// panel on this screen was the portal one, and it was holding over a portal
// that shipped in CR-068. Nothing on the account detail refuses any more.
import { apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
// CR-070 wave O — the work panel is Work's, composed here rather than copied.
// One implementation, two hosts, so the account and the premises cannot
// describe the same job two ways (`CR-070 §W.11`).
import { WorkOrdersTab } from "@/features/work/buildViews";
import { PendingBuildLink } from "@/features/work/buildRecord/PendingBuildLink";
import { accountBuildStatusKey, getAccountBuildStatus } from "./buildLifecycleEndpoints";
import { useTenantPath } from "@/routing/tenantPath";

import {
  AddNoteModal,
  AdjustModal,
  RecordPaymentModal,
  RecordPaymentPanel,
  accountNotesKey,
} from "./AccountActions";
import { TemporaryStopModal, TemporaryStopStrip } from "./TemporaryStopAccount";
import {
  AccountHeaderChips,
  AccountIdentityChain,
  AccountMetricColumns,
  AccountServiceChips,
  premiseLocality,
} from "./accountDetailHeader";
import { AccountCommunicationDialog } from "./AccountCommunicationDialog";
import { AccountIconRail } from "./AccountIconRail";
import { MasterAccountsTab } from "./MasterAccountsTab";
import { MasterUnitsTab } from "./MasterUnitsTab";
import { useAccountRailReadiness } from "./accountRailReadiness";
import { AccountActionOverlay, accountOverlayPath } from "./accountActionOverlays";
import { AccountQuickActionForm } from "./AccountQuickActionForm";
import { quickFormFor } from "./accountQuickActions";
import { AccountUsageTab } from "./AccountUsageTab";
// The Accounts LIST already owns what an ageing band IS, what it is called
// and how it is toned. Mounted here rather than restated, so the two
// screens cannot describe the same band differently (B14 rule 36).
import { AgeingCell, ageingSegmentOf } from "./accountsListCells";
import type { AccountAgeingCells } from "./accountsListCells";
import { AccountAdjustmentsTab } from "./AccountAdjustmentsTab";
import { AccountDocumentsTab } from "./AccountDocumentsTab";
import { AccountMetersTab } from "./AccountMetersTab";
import { AccountNotesTab } from "./AccountNotesTab";
import type { AccountRailAction, AccountRailActionId } from "./AccountIconRail";
import {
  AccountAuditPortalNote,
  MeterServiceCell,
  PaymentMethodPanel,
  RecentBillsPanel,
  UsageTrendPanel,
  meterChipsFrom,
  useAccountMeterViews,
} from "./accountDetailTabs";
// The four money tabs (Bills · Payments · Credits · Payment plan) as the
// blueprint's named groups — B14 rule 41, and one file per lane (law 11).
import {
  AccountBillsGroup,
  AccountCreditsGroup,
  AccountPaymentsGroup,
  AccountPlanGroups,
} from "./AccountMoneyTabs";
import { AccountHeldCreditGroup } from "./AccountHeldCredit";
import {
  AccountGroupPencil,
  accountGroupRoleReason,
  AccountPanelEditDialog,
} from "./AccountPanelEdits";
import type { AccountOverviewGroup } from "./AccountPanelEdits";
import { ReturnedPostBanner } from "./ReturnedPostBanner";
import { AccountPlanName } from "./AccountPlanName";
import {
  ACCOUNTS_PERMISSION,
  ACCOUNTS_ROUTE,
  DASHBOARD_ROUTE,
  AwaitsCell,
  Dash,
  NotRecorded,
  WarningList,
  accountChangePlanPath,
  accountCloseOutPath,
  accountHeadline,
  accountMoveInPath,
  accountMoveOutPath,
  accountPaymentPlanPath,
  accountDetailPath,
  accountStatusLabel,
  accountStatusTone,
  DISCONNECTED_STATUS_CODE,
  isClosedAccount,
  isDraftAccount,
  isOccupyingAccount,
  maskedGovId,
  primaryContact,
  accountCategoryName,
  useAccountCategories,
} from "./customersShared";

import "./customers.css";

// ── Pure pieces (provable without a browser or a network) ──────────────────

/** EP-CUS-03 §Scope: the nine S21 tabs, in the prototype's own order. */
export const ACCOUNT_TAB_IDS = [
  "overview",
  "bills",
  "payments",
  // CR-059 CS-37 · P13 — the TENTH tab, and the first place in this product a
  // person can see every credit note on one account. It sits beside Payments
  // rather than at the end because that is where the question is asked: a
  // customer ringing about a credit they were given is looking at what they
  // paid and what they were let off, in one conversation.
  "credits",
  // CR-059 CS-23 · task 6 — the ELEVENTH tab. It sits after Credits and before
  // Usage because the three money tabs belong together: what the customer paid,
  // what they were let off, and what they agreed to pay in instalments. Until
  // 2026-09-01 no instalment was ever marked paid, so this tab could only have
  // shown a customer paying on time as behind — which is why it did not exist.
  "plan",
  "usage",
  "meters",
  // ── CR-070 wave O (2026-09-04) · THE TWELFTH TAB ────────────────────────
  //
  // PO, scoping their own ruling: *"One screen too many. The objection is the
  // duplicate destination — a person should reach the build's progress, its
  // units, its work orders and its charges from the account, not from a
  // parallel screen. Whatever the tables are called underneath, there is one
  // place to look."* `/connections/<uuid>` is retired as a destination and this
  // is half of where it went; the premises detail is the other half.
  //
  // ⚠ **AFTER `meters` AND BEFORE THE MONEY, DELIBERATELY.** A job is about the
  // thing at the address — a meter to exchange, a main to repair, a final read
  // to take — so it belongs beside the meters rather than beside the bills.
  //
  // ⚠ **CHARGES AND HISTORY ARE ALREADY HERE AND NOTHING NEW IS BUILT FOR
  // EITHER.** The retired screen's Charges tab is this account's `bills` and
  // `adjustments`; its History is `audit`. Building a second copy of either
  // inside a Work tab would be the duplicate destination the ruling is about,
  // one level down (execution plan judgment 2). `08-screen-layouts.md` is
  // stamped to say so.
  "work",
  "adjustments",
  "documents",
  "notes",
  "audit",
] as const;
export const TAB_PARAM = "tab";
/** `?order=<id>` — the work-order drawer, opened over the Work tab (CR-070
 *  wave O). The same convention the retired connection detail used, and the one
 *  S29 uses over the reads list. */
export const ORDER_PARAM = "order";

/** `ACC-T07R` — the meter whose read log is open over the Meters tab. The
 *  drawing's own address is `?tab=meters&meter=e-4417&view=reads`, and
 *  `BR-SHL-011` says every surface is linkable: a clerk can send somebody the
 *  log they are looking at. */
export const METER_PARAM = "meter";

export const accountDetailQueryKey = (id: string) => ["accounts", "detail", id] as const;

/**
 * The Payments tab's table state. LOCAL, not URL-backed, and deliberately: S21
 * already spends its query string on `?tab=` (IS-4's deep link, US-CUS-008
 * TC-3), and serialising a second table's sort/page/filters into the same URL
 * would make an account deep link carry a payments page number. The S33 screen
 * keeps its own URL-backed state, which is where a shareable payments view
 * belongs.
 *
 * The sort matches S33's capability row — posting date, newest first — so the
 * tab cannot show a different default order from the ledger it embeds.
 */
const PAYMENTS_TAB_STATE: TableRequestState = {
  q: "",
  sort: "posted_at",
  dir: "desc",
  page: 1,
  per: DEFAULT_PAGE_SIZE,
  filters: {},
};

/**
 * English fallbacks for tab labels whose catalogue entry has not landed yet.
 *
 * ⚠ **ONE ENTRY, AND IT IS TEMPORARY.** `src/i18n/locales/**` is owned by
 * another lane this week, so `customers.account.tab.credits` is REPORTED with
 * this change rather than written into the eleven catalogues here. Without a
 * fallback the tab would be labelled `customers.account.tab.credits` — an
 * internal code on a clerk's screen, which B14 rule 32 forbids. This map goes
 * when the sentence lands; the nine tabs that came before are not in it,
 * because their entries exist.
 */
const TAB_LABEL_FALLBACK: Partial<Record<(typeof ACCOUNT_TAB_IDS)[number], string>> = {
  credits: "Credits",
  // ⚠ `work` IS DELIBERATELY NOT HERE (CR-070 wave O). Its sentence lands in
  // all eleven catalogues in the commit that adds the tab, so there is nothing
  // to fall back to — which is the posture this map's own header asks for and
  // what `G15` checks.
};

/**
 * ── `CR-094-BRC01` R7 / `ACC-S17` — THE THIRTEENTH TAB, AND IT IS CONDITIONAL
 *
 * PO 2026-09-12, verbatim: *"if the account is of master account, then after
 * the overview tab, it should show the accounts that are connected to that
 * master account"*, confirming the walk: *"this is correct - you can see the
 * premises -> units -> regular accounts assocaited with it"*.
 *
 * ⚠ **IT IS NOT IN `ACCOUNT_TAB_IDS`, AND THAT IS DELIBERATE.** Every other tab
 * on this screen exists for every account, so that constant is the strip. This
 * one exists only where `kind === 'master'` (`BR-CUS-068`), and folding it into
 * the list would mean every consumer of the constant — the URL parser, the tab
 * census, the header's button count — had to remember to subtract it again.
 * `accountTabIds` is the one place the insertion happens.
 */
export const ACCOUNT_MASTER_TAB_ID = "accounts";

/**
 * ── `BR-CUS-1094` (PO 2026-09-23) — THE FOURTEENTH TAB, AND ALSO CONDITIONAL
 *
 * PO verbatim: *"show all units with its status what wil be billed to master
 * account - can we do that?"*
 *
 * ⚠ **IT SITS BESIDE `accounts` AND NOT SOMEWHERE ELSE, BECAUSE IT IS THAT
 * TAB'S OTHER HALF.** `MasterAccountsTab` lists every OCCUPYING account at the
 * address (`BR-CUS-1048`); a vacant unit has no account at all, so it appears
 * on no list anywhere in the product. Reading the two side by side is the whole
 * vacancy picture, which is what the PO asked to see.
 *
 * ⚠ **NEITHER IS IN `ACCOUNT_TAB_IDS`, FOR THE REASON RECORDED ABOVE:** that
 * constant is the strip EVERY account gets, and folding a conditional tab into
 * it would mean every consumer — the URL parser, the tab census, the header's
 * button count — had to remember to subtract it again.
 */
export const ACCOUNT_MASTER_UNITS_TAB_ID = "units";

/** The strip this account actually gets, in order. */
export function accountTabIds(kind: string = "regular"): string[] {
  if (kind !== ACCOUNT_KIND_MASTER) {
    return [...ACCOUNT_TAB_IDS];
  }
  // "after the overview tab" — the PO's own words, so the insertion is at index
  // 1 rather than appended. Overview is `ACCOUNT_TAB_IDS[0]` by construction
  // and is asserted to be, so this cannot quietly land second.
  const [overview, ...rest] = ACCOUNT_TAB_IDS;
  return [overview, ACCOUNT_MASTER_TAB_ID, ACCOUNT_MASTER_UNITS_TAB_ID, ...rest];
}

export function accountTabs(t: Translator, kind: string = "regular"): DetailTab[] {
  return accountTabIds(kind).map((id) => ({
    id,
    label: t(`customers.account.tab.${id}`, {
      defaultValue: TAB_LABEL_FALLBACK[id as (typeof ACCOUNT_TAB_IDS)[number]],
    }),
  }));
}

/**
 * The one-line billing chain under the H1 — service address plus the unit, as
 * the server already assembles it for S17 (`premise` = "1408 Elm St · A").
 * Nothing is re-joined here from parts the payload does not carry.
 */
export function accountRollupLine(detail: AccountDetail): string | null {
  return detail.premise ?? detail.unit_label ?? null;
}

/**
 * BR-CUS-045 / A12: the mailing address block. `kind` is `mailing` | `service`
 * (B2 §2) and the SERVER decides which rows exist — an account with no mailing
 * row means "same as service", which is a different claim from "no address",
 * so the caller renders the distinction rather than this helper guessing it.
 */
export function addressLine(address: AccountAddress): string {
  // `line2` — "Apt, suite or unit" — sits after the street, the order an
  // envelope reads (`DEF-CUS-6460`).
  return [address.line1, address.line2 ?? null, address.city, address.state, address.postal_code]
    .filter((part) => part !== null && part !== "")
    .join(", ");
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface AccountDetailPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function AccountDetailPage(props: AccountDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const fireToast = useToast();
  // `ACC-S15` — which Overview group's pencil is open. One at a time.
  const [editingGroup, setEditingGroup] = useState<AccountOverviewGroup | null>(null);
  const { timeZone, dateFormat } = useRegional(props);

  const accountId = params.accountId ?? "";
  // DEF-684's catalogue, read at the PAGE so the header's category chip can
  // resolve a NAME. `OverviewTab` reads the same query key one level down, so
  // this costs no second request.
  const headerCategories = useAccountCategories(props.client);
  const [warnings, setWarnings] = useState<readonly ServerWarning[]>([]);
  const [refusal, setRefusal] = useState<string | null>(null);
  // The S22 family. ONE slot rather than a boolean per modal: two open modals
  // is not a state this screen has, and two booleans is a state where it is.
  const [openModal, setOpenModal] = useState<
    "payment" | "adjust" | "note" | "activate" | "communication" | "temporaryStop" | null
  >(null);

  // `ACC-S14` — the configuration for this action, read from the ONE place all
  // thirteen are declared. `null` when the action opens no form, which is the
  // other twelve today; the control is guarded on it so a missing declaration
  // cannot render a control that opens nothing (hard-won law 2).
  const activateForm = quickFormFor("activate");
  const [recorded, setRecorded] = useState<RecordedPayment | null>(null);
  const [paymentsState, setPaymentsState] = useState<TableRequestState>(PAYMENTS_TAB_STATE);

  const cell = useAccessCell(ACCOUNTS_PERMISSION, client);
  // BR-SHL-025: "Full" writes; anything else renders the control disabled WITH
  // the reason. The server refuses regardless — this only saves a round trip.
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("customers.accounts.rbac.readOnly");

  const detailQuery = useQuery({
    queryKey: accountDetailQueryKey(accountId),
    queryFn: () => getAccountDetail(accountId, client),
    enabled: accountId !== "",
  });

  // ⚠ **`ACC-S14` / `ACC-Q03` — THIS USED TO COMMIT ON THE CLICK.** The button
  // called `activate.mutate()` directly: no dialog, no date, no recap and no way
  // back, on an act that starts billing and cannot be undone. R4's own caption
  // for this figure is *"the confirmation the product is missing, and it names
  // the partial failure BEFORE the click"*, and the form it draws says the same
  // thing on screen. The mutation is unchanged; what changed is that a form now
  // stands between the clerk and it, and that `opened_at` can be set at all.
  const activate = useMutation({
    mutationFn: (payload: Record<string, string>) => activateAccount(accountId, payload, client),
    onSuccess: (result) => {
      // The server's OWN answer replaces the cached detail — nothing here
      // patches a status locally and hopes the server agreed.
      queryClient.setQueryData(accountDetailQueryKey(accountId), result);
      // BR-CUS-029 / BR-CUS-023: the handoffs it could not perform, shown.
      setWarnings(result.warnings);
      setRefusal(null);
      fireToast(t("customers.account.toast.activated", { account: result.account_no ?? "" }));
    },
    onError: (error: unknown) => {
      setWarnings([]);
      // BR-SHL-020: the server's own message_key through the catalog — this is
      // where BR-MET-040 ("plan required at activation") and BR-CUS-017 ("that
      // unit already has an account") reach the user.
      setRefusal(apiErrorText(error, translate));
    },
  });

  // CR-030 W3 (3.1 / 3.9): the meters on this account's unit, as the ASSETS
  // module holds them. Called HERE, above every early return, because it is a
  // hook — and reading `detailQuery.data?.meters` rather than `detail.meters`
  // is what lets it sit above them. An account whose detail has not arrived
  // asks for nothing.
  const meterViews = useAccountMeterViews(detailQuery.data?.meters ?? [], props.client);

  // DEF-CUS-4631 — the icon rail's four DERIVED actions, for exactly the reason
  // the line above gives: `useAccountRailReadiness` is a hook, so it is called
  // above every early return and reads `detailQuery.data?` rather than `detail`.
  // An account whose detail has not arrived asks for nothing, and the rail it
  // would have wired is not rendered on any of the three paths below.
  //
  // ⚠ **THE FOUR REASONS ARE NO LONGER READ FROM `UNAVAILABLE_ACTIONS`, AND
  // THAT IS THE POINT OF THE CHANGE.** Three of them are now DERIVED from facts
  // about this account — has it an issued bill, is it occupying its unit — so
  // there is no sentence left to go stale. All four of the typed ones were
  // false on 2026-09-07; see `accountRailReadiness.ts` for which and why.
  const derivedRail = useAccountRailReadiness({
    accountId,
    facts: {
      occupying:
        detailQuery.data === undefined ? false : isOccupyingAccount(detailQuery.data),
      writeBlockedReason,
    },
    t: translate,
    client: props.client,
  });

  function selectTab(id: string): void {
    const next = new URLSearchParams(searchParams);
    next.set(TAB_PARAM, id);
    // Leaving the Work tab closes any drawer open over it: a `?order=` left
    // behind would re-open a panel over the WRONG tab next time.
    next.delete(ORDER_PARAM);
    // …and the same for the read log open over the Meters tab, for the same
    // reason: a `?meter=` left behind re-opens a panel over the WRONG tab.
    next.delete(METER_PARAM);
    setSearchParams(next, { replace: true });
  }

  /** Open or close the work-order drawer. URL state, so a supervisor can send
   *  somebody a link to one job (`BR-SHL-011` — every tab is linkable). */
  function selectOrder(id: string | null): void {
    const next = new URLSearchParams(searchParams);
    if (id === null) {
      next.delete(ORDER_PARAM);
    } else {
      next.set(ORDER_PARAM, id);
    }
    setSearchParams(next, { replace: true });
  }

  /** Open or close the read log over the Meters tab — `ACC-T07R`'s own
   *  address, for the reason `selectOrder` above gives. */
  function selectMeter(id: string | null): void {
    const next = new URLSearchParams(searchParams);
    if (id === null) {
      next.delete(METER_PARAM);
    } else {
      next.set(METER_PARAM, id);
    }
    setSearchParams(next, { replace: true });
  }

  if (isDenied(cell)) {
    // BR-SHL-003 / A18 §6: a surface this role cannot reach is not drawn.
    return (
      <PermissionDenied
        helper={t("customers.accounts.denied")}
        onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
      />
    );
  }
  if (detailQuery.isPending) {
    return <LoadingSkeleton variant="card" />; // A18 §3
  }
  if (detailQuery.data === undefined) {
    if (isPermissionDenied(detailQuery.error)) {
      return (
        <PermissionDenied
          helper={t("customers.accounts.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    // A cross-tenant id and an unknown id are ONE answer server-side (HR-1) —
    // A18 §4 with the server's own reason, never a blank detail shell.
    return (
      <FailedWithRetry
        title={t("customers.account.detail.failedTitle")}
        reason={apiErrorText(detailQuery.error, translate)}
        onRetry={() => void detailQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(ACCOUNTS_ROUTE))}
      />
    );
  }

  const detail = detailQuery.data;
  const draft = isDraftAccount(detail);

  // ── `CR-094-BRC01` R7 — THE STRIP IS THE ACCOUNT'S, NOT THE SCREEN'S ──────
  // A master carries the **Accounts** tab (`BR-CUS-068`) and nothing else
  // does, so the strip cannot be derived before the detail has arrived — which
  // is why these two lines sit BELOW the early returns rather than beside the
  // other `useSearchParams` reading. Neither is a hook, so nothing about the
  // hook order moves.
  // `detailTabFrom` then makes `?tab=accounts` on an ordinary account fall back
  // to Overview instead of selecting a tab with no body (BR-SHL-011's fallback
  // law) — which is the case a deep link pasted between two accounts produces.
  const tabs = accountTabs(translate, detail.kind);
  const active = detailTabFrom(searchParams.get(TAB_PARAM), tabs);

  // The ONE primary. Reasons in the order a user can act on them: the ROLE
  // first, then the state. `null` means the control is live — and this is the
  // only live write on the screen (BR-CUS-018).
  const activateReason =
    writeBlockedReason ?? (draft ? null : t("customers.account.action.activateNotDraft"));
  // BR-CUS-030: only an OCCUPANT can move out — a draft never took the unit and
  // a closed account has already left it, and the server refuses both.
  const moveOutReason =
    writeBlockedReason ??
    (isOccupyingAccount(detail) ? null : t("customers.account.action.moveOutBlocked"));
  // BR-CUS-017: the move-in endpoint takes the OUTGOING account's unit, so it
  // is offered on a CLOSED account — while this one still holds its unit, the
  // create would be refused 409 by the same guard the move-out frees.
  const moveInReason =
    writeBlockedReason ??
    (isClosedAccount(detail) ? null : t("customers.account.action.moveInBlocked"));
  // ── DEF-724 · BR-CUS-430 — the terminal path a CUT customer HAS ─────────
  // The mirror of `moveOutReason` above, and deliberately so: an OCCUPANT
  // leaves by moving out, and an account whose service was cut is closed out.
  // Offering both on one account would invite a clerk to file a disconnection
  // as a move-out, which is the falsification the ruling forbids. The SERVER
  // is the authority either way; this reason is the explanation, not a second
  // implementation of the rule.
  //
  // ⚠ **THIS GATE NAMED THE STATES THAT REFUSE AND LET EVERYTHING ELSE THROUGH
  // (`DEF-CUS-5005`, 2026-09-12).** It read
  // `isOccupyingAccount(detail) || isClosedAccount(detail)`, which covers
  // `billable`, `billable_base_only` and `terminal` — and `pending_activation`
  // is `non_billable`, so a DRAFT account fell out of both tests and the
  // control rendered LIVE on it. Blueprint `ACC-A05` draws the whole truth
  // table and captions it: **"the only status that opens this button is the one
  // it was not written for"**.
  //
  // **SO IT NAMES THE ONE STATE IT IS FOR INSTEAD, WHICH IS THE SHAPE THAT
  // CANNOT ROT.** A refusal list has to be re-checked every time BR-CUS-055's
  // tenant-extensible status set grows; an allow list of one does not, and a
  // status a tenant adds tomorrow gets the refusal rather than the button.
  // `close_out.eligibility`'s THIRD blocker is the rule being mirrored here —
  // `not_a_cut_account`: *"a close-out needs a service that was CUT, because
  // BR-CUS-431 writes the CUT DATE into `accounts.closed_at`"* — and the first
  // two (already terminal, still occupying) are subsumed, because neither a
  // terminal nor an occupying status is this one.
  //
  // ⚠ **BY CODE AND NOT BY CLASS, AND THAT IS `isDraftAccount`'S OWN
  // PRECEDENT.** `disconnected` and `pending_activation` are BOTH
  // `non_billable` (BR-CUS-107), so the behaviour class cannot tell a cut
  // account from a draft — which is the very confusion this defect is. The
  // server names the code too (`disconnects.CUT_STATUS_CODE`).
  //
  // ⚠ **AND IT IS A DISPLAY GUARD, NOT THE RULE.** The server re-asks the whole
  // question under a lock and needs a disconnect case in state `cut` WITH a
  // date; a `disconnected` account with no such case still gets
  // `close_out_not_a_cut_account` from `POST /accounts/{id}/close-out`. This
  // stops a clerk being offered a button that cannot succeed on the FIVE
  // statuses where it provably cannot; it does not claim to be the sixth
  // answer.
  const closeOutReason =
    writeBlockedReason ??
    (detail.status === DISCONNECTED_STATUS_CODE
      ? null
      : t("customers.account.action.closeOutBlocked", {
          defaultValue:
            "Only an account whose service has been cut is closed out. An occupant leaves by moving out, and a closed account is already finished.",
        }));
  // BR-PAY-036 (PO 2026-08-11): a payment is ALWAYS accepted, in any account
  // state — accepting money never changes an account's status by itself. So
  // this control is gated on the ROLE alone and on nothing else; gating a
  // closed account out of it would refuse a cheque that settles a final bill.
  // BR-CUS-059: an autopay-enrolled account is recorded here exactly like any
  // other — enrolment neither blocks nor auto-substitutes manual recording.
  const recordPaymentReason = writeBlockedReason;
  // US-CUS-008 TC-5: a CLOSED account cannot change plan — there is no
  // tenancy left to price. The server refuses it too, through the same
  // occupancy rule the move-out guard reads.
  const changePlanReason =
    writeBlockedReason ??
    (isOccupyingAccount(detail) ? null : t("customers.account.action.changePlanBlocked"));
  // BR-CUS-043 / US-CUS-018 TC-6: a plan spreads a debt that EXISTS on a live
  // tenancy. A draft never took the unit and a closed account has settled or
  // been written off, and the server refuses both — this is the explanation.
  const paymentPlanReason =
    writeBlockedReason ??
    (isOccupyingAccount(detail) ? null : t("customers.account.action.paymentPlanBlocked"));

  // ── CR-030 W3 · 3.2 · BR-SHL-045 — the icon rail's seven, WIRED ──────────
  //
  // The rail component draws the glyphs and owns their order and their
  // accessible names; this page owns what each one DOES and whether this
  // deployment can honour it, because that is the half that knows the account's
  // state and the caller's A4 cell. A `Record` over the seven ids means a glyph
  // added to the rail with no behaviour here does not compile — hard-won law 2
  // ("built is not wired"), enforced by the type system rather than by G13.
  //
  // ⚠ **THE FOUR THAT USED TO BE DISABLED ARE NOW DERIVED, NOT TYPED — AND THE
  // THREE THAT WERE ALWAYS LIVE ARE UNTOUCHED.** This block used to read four
  // sentences out of `UNAVAILABLE_ACTIONS` so the rail could not hold a second
  // copy of one (hard-won law 5). That was right about copies and wrong about
  // the thing being copied: **one place holding a false sentence is still a
  // false sentence**, and on 2026-09-07 the PO found all four of them false
  // from the screen. `useAccountRailReadiness` replaces the string with the
  // question it was standing in for — has this account an issued bill, is it
  // occupying its unit — and a fact cannot rot the way a sentence does.
  //
  // `sendStatement` still refuses, because that one is TRUE: nothing in this
  // product renders a statement. It refuses from the same hook so every reason
  // on the rail arrives from one place, and it carries the hold-expiry test the
  // other three never had.
  const railActions: Record<AccountRailActionId, AccountRailAction> = {
    // ⚠ **`ACC-S16` — the eighth glyph, and it is LIVE from its first commit.**
    // Step 1's F11 counted seven icons and six buttons that could not send a
    // word. This one opens the Communication dialog, which queues a real row on
    // the outbound queue through notifications' own writer. It takes the same
    // role gate as the other live glyphs: an Executive may read an account and
    // may not write to its customer. A glyph that opened a *not built yet*
    // panel would be the dead control hard-won law 2's mirror is about.
    communication: { reason: writeBlockedReason, onClick: () => setOpenModal("communication") },
    sendStatement: derivedRail.sendStatement,
    printBill: derivedRail.printBill,
    issueCredit: derivedRail.issueCredit,
    changePlan: {
      reason: changePlanReason,
      onClick: () => navigate(tenantPath(accountChangePlanPath(accountId))),
    },
    disconnectNotice: derivedRail.disconnectNotice,
    // S24 — the wizard's engine shipped complete and frozen as GT-47 on
    // 2026-08-11 with nothing in the product able to reach it; the control it
    // gained on 2026-08-16 is this glyph now. Gated on OCCUPANCY like Change
    // plan: a plan spreads the arrears of a live tenancy, and the server
    // refuses a proposal it cannot read a balance for.
    paymentPlan: {
      reason: paymentPlanReason,
      onClick: () => navigate(tenantPath(accountPaymentPlanPath(accountId))),
    },
    addNote: { reason: writeBlockedReason, onClick: () => setOpenModal("note") },
  };

  return (
    <div className="px-4 pt-6 pb-8">
      {/* US-SHL-020 / BR-SHL-044: back → kicker → H1 + status → roll-up → tab
          strip, from the shared component. The arrow belongs to the component
          (TC-5), so the back LABEL is the destination's own name. */}
      <PageHeader
        backTo={{ to: tenantPath(ACCOUNTS_ROUTE), label: t("customers.accounts.title") }}
        // CR-030 W3 — the customer number joins the kicker, PO ruling
        // 2026-08-24: *"we dont need this column … you can sho it as part of
        // details screen"*. It rides beside the account number rather than in
        // a panel below, because the two are the same KIND of fact — the two
        // identifiers a clerk reads out on the phone — and a clerk who has to
        // scroll for the second one will use the first and get the wrong
        // person. `account_row` already serves `customer_no`, so this reads a
        // field that is present rather than costing a query.
        //
        // An account with no customer number renders the account number alone:
        // appending an empty separator would draw a dangling "·", and a stated
        // absence is not owed here because the number is not a capability the
        // screen is withholding — most accounts simply have one and this one
        // does not.
        kicker={
          detail.customer_no
            ? t("customers.account.detail.kickerWithCustomer", {
                account: detail.account_no ?? t("customers.account.noNumber"),
                customer: detail.customer_no,
              })
            : t("customers.account.detail.kicker", {
                account: detail.account_no ?? t("customers.account.noNumber"),
              })
        }
        title={accountHeadline(detail, translate)}
        rollup={
          // CR-030 W3 · 3.1 — r10's own two lines, in r10's order: the address
          // chain ending `Since Feb 2024`, then the service chips carrying
          // each service's METER NUMBER.
          <>
            <AccountIdentityChain
              detail={detail}
              t={translate}
              timeZone={timeZone}
              dateFormat={dateFormat}
            />
            <AccountServiceChips
              services={detail.services}
              meters={meterChipsFrom(meterViews)}
              t={translate}
            />
            <AccountPendingBuild
              accountId={detail.id}
              pending={detail.status === "pending_activation"}
              t={translate}
              path={tenantPath}
              client={props.client}
            />
          </>
        }
        status={
          <>
            <StatusPill tone={accountStatusTone(detail)}>
              {accountStatusLabel(detail, translate)}
            </StatusPill>
            {/* ⚠ **THE FOUR CHIPS THE BLUEPRINT DRAWS AND THE PRODUCT DREW
                ONE OF** (PO 2026-09-13: *"in header we have billable, account
                type etc - none of them are shown"*). `AccountHeaderChips`
                renders `Billable` · `Commercial · Small commercial` ·
                `Regular account`, each resolved through its catalogue so no
                raw enum reaches a clerk (B14 rule 31), and it SUBSUMES the
                master pill this line used to draw on its own — `Master
                account` and `Regular account` are now one chip from one
                vocabulary rather than a positive-only pill. `BR-CUS-068`'s
                reason for wanting it is unchanged: a master account's payer is
                the OWNER, and that is the one fact that changes who pays. */}
            <AccountHeaderChips detail={detail} categories={headerCategories.all} t={translate} />
            {/* BR-CUS-059: the pill signals ENROLMENT, not drafting — v1
                collects nothing on it, and the Overview panel says so.
                ⚠ CR-030 W3 · TC-ACD-4: it renders ONLY WHEN AUTOPAY IS ON.
                It used to render `Autopay off` in the neutral tone on every
                other account, and B18 §5.2.3 rules that out in one line —
                *"no `Autopay on` pill (absence is not a grey pill)"*. r10
                draws one pill beside the status and never a negative one; a
                grey pill saying a thing is off is a claim taking up the space
                of the claims that are true. */}
            {/* DEF-644 — the pill is TRUE and, alone, MISLEADING. Autopay in
                this version is "a promise recorded, never a charge"
                (`apps/payments/models.py:623`), so a clerk can switch it on and
                reasonably expect the next bill to be taken. It will not be.
                That warning lived in the page-level panel the PO deleted on
                2026-08-24, and had no second home; it now rides on the pill
                itself, which is where the mistake is made. */}
            {detail.autopay && (
              <StatusPill tone="warning" title={t("customers.account.pill.autopayOnWhy")}>
                {t("customers.account.pill.autopayOn")}
              </StatusPill>
            )}
            {/* CR-190-BRC10 — the newest agreement request's status. */}
            <AgreementStatusChip accountId={detail.id} client={props.client} />
          </>
        }
        secondaryActions={
          <>
            {/* CR-030 W3 · 3.3 — r10's ACTION STACK is three buttons and its
                order is `Record payment` (primary) · `Adjust` · `Move-out`.
                Record payment has moved to the primary slot below, so the two
                that follow it lead the secondary rail. */}
            {/* ⚠ AMENDED 2026-08-24 (CR-030 W3 · 3.2 — BR-SHL-045, closing D2).
                SEVEN WORDED BUTTONS LEFT THIS SLOT AND BECAME THE ICON RAIL
                below the metric block: Send statement · Print bill · Issue
                credit · Change plan · Disconnect notice · Payment plan · Add
                note. The paragraph this replaces said the icon rail was *"B18's
                D2 — blocked on the PO, because a picture cannot say what a
                glyph does. Deleting the buttons before their replacement is
                ruled would make four live features unreachable."* The PO ruled
                it on 2026-08-24, so the buttons are REPLACED rather than
                deleted and not one action is lost — three of the seven are live
                (Change plan, Payment plan, Add note) and each keeps the same
                guard it had as a button.
                WHAT STAYS WORDED, and why it is not five: Adjust and Move-out
                are r10's own action stack, and Activate + Move-in are this
                deployment's two extra live writes (BR-CUS-018, BR-CUS-017) —
                r10 has no glyph for either, and BR-SHL-045's seven are r10's
                seven exactly, so inventing an eighth or a ninth glyph would be
                the one thing that ruling forbids. */}
            {/* ⚠ **RELEASED 2026-09-13 — `DEF-CUS-5126`.** This carried
                `customers.account.action.adjustBlocked`, *"Adjustments are
                billing rows, and billing is not built. There is no endpoint to
                post one to."* Every clause of it was false: `POST
                /accounts/{id}/payments` has taken `type: "adjustment"` since
                `CR-059` CS-35 on 2026-09-02, and it was looked for in BILLING,
                where the only thing that exists is a table with no writer
                (`OQ-BIL-12348`). `writeBlockedReason` STAYS — a closed or
                cancelled account still refuses every write, and that half was
                always true. */}
            <GuardedButton
              label={t("customers.account.action.adjust")}
              reason={writeBlockedReason}
              onClick={() => setOpenModal("adjust")}
            />
            {/* CR-183-BRC10 T7 — start, move or end a temporary stop for a
                customer on the phone or at the counter. The same write gate
                as Adjust: a closed or cancelled account refuses every write;
                the server refuses an account that is not active by name. */}
            <GuardedButton
              label={t("customers.temporaryStop.action.open")}
              reason={writeBlockedReason}
              onClick={() => setOpenModal("temporaryStop")}
            />
            <GuardedButton
              label={t("customers.account.action.moveOut")}
              reason={moveOutReason}
              onClick={() => navigate(tenantPath(accountMoveOutPath(accountId)))}
            />
            {/* BR-CUS-018's one live write on a DRAFT. It was the primary slot
                until this lane; r10 gives that slot to Record payment, and a
                control only a pending-activation account can press is not the
                page's primary action on the other four statuses. */}
            <GuardedButton
              label={t("customers.account.action.activate")}
              reason={activateReason}
              working={activate.isPending}
              onClick={() => setOpenModal("activate")}
            />
            <GuardedButton
              label={t("customers.account.action.moveIn")}
              reason={moveInReason}
              onClick={() => navigate(tenantPath(accountMoveInPath(accountId)))}
            />
            {/* DEF-724 — the act the product had no door for until
                2026-08-27. It sits beside Move-out because they are the two
                terminal paths and a reader must be able to see that they are
                DIFFERENT: one ends a tenancy, one finishes a customer whose
                service was cut. */}
            <GuardedButton
              label={t("customers.account.action.closeOut", { defaultValue: "Close out" })}
              reason={closeOutReason}
              onClick={() => navigate(tenantPath(accountCloseOutPath(accountId)))}
            />
            {/* DEF-PAY-10706 (PO Q4 = A, the approved mock-up's piece 6) — a
                MASTER pays its units' bills with one cheque. Opens Record
                payment on *Several accounts* with this master already chosen;
                the master rides in router STATE, never the URL (B14 rule 31).
                Same guard as Record payment beside it. */}
            {detail.kind === ACCOUNT_KIND_MASTER && (
              <GuardedButton
                label={t("customers.account.action.payUnits")}
                reason={recordPaymentReason}
                onClick={() =>
                  navigate(tenantPath(PAYMENTS_RECORD_NEW_ROUTE), {
                    state: {
                      payFor: { id: detail.id, accountNo: detail.account_no, kind: detail.kind },
                    } satisfies PayForState,
                  })
                }
              />
            )}
          </>
        }
        primaryAction={
          // CR-030 W3 · 3.3 / B18 §5.2.1: r10's ONE primary is Record payment,
          // and it is honest now — `POST /accounts/{id}/payments` is served and
          // the S22 modal it opens is live. When this screen was written the
          // slot carried Activate instead, because payments did not exist and a
          // permanently dead primary teaches the wrong thing about a page; that
          // reason expired, so the button moved.
          <GuardedButton
            label={t("customers.account.action.recordPayment")}
            reason={recordPaymentReason}
            variant="primary"
            onClick={() => setOpenModal("payment")}
          />
        }
        tabs={tabs}
        activeTabId={active}
        tabsLabel={t("customers.account.detail.tabsLabel")}
        onTabSelect={(tab) => selectTab(tab.id)}
      />

      {/* CR-183-BRC10 — while a temporary stop is scheduled or on. */}
      <TemporaryStopStrip
        accountId={accountId}
        timeZone={timeZone}
        dateFormat={dateFormat}
        client={props.client}
      />

      {refusal !== null && (
        <RefusalStrip role="alert">
          {refusal}
        </RefusalStrip>
      )}
      <WarningList warnings={warnings} title={t("customers.account.warningsTitle")} t={translate} />
      {/* DEF-PAY-6342 — BR-PAY-018's banner and its clear step. It reads the
          ONE bad-address fact (`accounts.bad_address`), the same field the
          Overview's `Bad address` row prints, so the two cannot disagree. */}
      <ReturnedPostBanner
        detail={detail}
        timeZone={timeZone}
        dateFormat={dateFormat}
        client={props.client}
        t={translate}
        onDone={(message) => {
          void queryClient.invalidateQueries({ queryKey: accountDetailQueryKey(detail.id) });
          fireToast(message);
        }}
      />

      {/* CR-030 W3 · 3.1 — r10's THREE metric columns (`BALANCE` · `PLAN` ·
          `LAST ACTIVITY`), each with the sub-line r10 draws beneath it. This
          was a five-row fact list titled "Balance, plan and activity"; r10's
          header card draws three columns and no title, and the AGEING fact
          that was the fourth row now lives on the S17 row (B18 §5.1.2), which
          is where a clerk scans for it. */}
      {/* DEF-2419 — the PLAN column prints the date the unit came onto its
          plan, so the tenant's own timezone and date format are passed. They
          are REQUIRED props: an optional one nothing passed would render an
          empty box and pass every test (hard-won law 2). */}
      <AccountMetricColumns
        detail={detail}
        t={translate}
        timeZone={timeZone}
        dateFormat={dateFormat}
      />

      {/* CR-030 W3 · 3.2 — r10 draws the ICON RAIL immediately under the metric
          columns, inside the same header card and divided from them by a rule
          (`<hr class="hr">`, ~offset 167k). BR-SHL-045 rules its seven glyphs
          and rules the hover label to be each button's ACCESSIBLE NAME. It sits
          BELOW the metric block here for the same reason the metric block sits
          below the shared PageHeader: `components/PageHeader.tsx` owns that card
          and belongs to another lane. */}
      <AccountIconRail t={translate} actions={railActions} />

      {/* `ACC-S1` / `BR-CUS-1053` — the account's own edit, opened from the
          pencil on the group it belongs to. `PATCH /accounts/{id}` has been
          served, audited and tested since August and had NO CALLER anywhere in
          the front end until this line; a clerk could not correct a misspelt
          name or a wrong telephone number from anywhere in the product. */}
      {editingGroup !== null && (
        <AccountPanelEditDialog
          detail={detail}
          group={editingGroup}
          client={props.client}
          t={translate}
          dateFormat={dateFormat}
          onClose={() => setEditingGroup(null)}
          onSaved={() => {
            setEditingGroup(null);
            void queryClient.invalidateQueries({ queryKey: accountDetailQueryKey(detail.id) });
            fireToast(
              translate("customers.account.edit.saved", { account: detail.account_no ?? "" }),
            );
          }}
        />
      )}

      {active === "overview" && (
        <OverviewTab
          detail={detail}
          accountId={detail.id}
          client={props.client}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onSelectTab={selectTab}
          canWriteReason={writeBlockedReason}
          // ⚠ **`plan` ROUTES; EVERY OTHER GROUP OPENS A DIALOG.** `R5` gives
          // the Plan group *"The Change plan wizard"* and names why in its own
          // words — *"an edit control that routes to a wizard rather than
          // duplicating it"* — and its table puts *"Nothing"* in the waits-on
          // column because `POST /accounts/{id}/plan-changes` is served and the
          // three-step wizard already runs. Since `BR-CUS-1051` that wizard
          // opens OVER this account, so the clerk does not lose the balance
          // they were reading either. A case in the dialog dispatcher would be
          // a second plan form beside a working one.
          onEditGroup={(group) => {
            if (group === "plan") {
              navigate(tenantPath(accountOverlayPath("changePlan", detail.id)));
              return;
            }
            setEditingGroup(group);
          }}
        />
      )}
      {/* ── `CR-094-BRC01` R7 / `ACC-S17` — THE ACCOUNTS AT THIS ADDRESS ─────
          PO 2026-09-12: *"if the account is of master account, then after the
          overview tab, it should show the accounts that are connected to that
          master account"*, and *"this is correct - you can see the premises ->
          units -> regular accounts assocaited with it"*.

          ⚠ **THE `active` GUARD IS NOT ENOUGH ON ITS OWN AND THE `kind` GUARD
          IS NOT REDUNDANT.** `accountTabIds` already keeps the tab off an
          ordinary account's strip, so `active` can never be `accounts` there
          today — but a guard that depends on another function's output is a
          guard one refactor away from being gone, and this tab reads an
          account's whole building. Both, deliberately. */}
      {active === ACCOUNT_MASTER_TAB_ID && detail.kind === ACCOUNT_KIND_MASTER && (
        <MasterAccountsTab
          detail={detail}
          client={props.client}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
        />
      )}

      {/* `BR-CUS-1094` — the same BOTH-GUARDS posture as the tab above, and for
          the same reason: `accountTabIds` already keeps this tab off an
          ordinary account's strip, and a guard that depends on another
          function's output is a guard one refactor away from being gone. */}
      {active === ACCOUNT_MASTER_UNITS_TAB_ID && detail.kind === ACCOUNT_KIND_MASTER && (
        <MasterUnitsTab detail={detail} client={props.client} t={translate} />
      )}
      {/* AMENDED 2026-08-11 (W3 billing lane): the Bills tab is LIVE. It is not
          a customers read-model — BR-CUS-034 forbids one — it is billing's own
          S30 list scoped by `f.account_id`, which is 11b §2.6's account
          scoping of `GET /invoices`. One table, so BR-BIL-063's "a draft has no
          number" rule and the derived past-due state cannot be implemented
          twice and drift. The endpoint itself is contracted and not served yet;
          the table reports that in its own A18 §4 state rather than this page
          claiming it. */}
      {/* ⚠ **THE FOUR MONEY TABS NOW RENDER AS THE BLUEPRINT'S NAMED GROUPS**
          (B14 rule 41, PO 2026-09-13 — *"Product screen should match exactly in
          visual with Drawing in Blueprint"*). `AccountMoneyTabs.tsx` carries all
          four, hooks each group for the browser census, and is a file of its own
          so that three lanes building this screen at once cannot revert one
          another inside `accountDetailTabs.tsx` (hard-won law 11). */}
      {active === "bills" && (
        <AccountBillsGroup
          accountId={detail.id}
          client={props.client}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
        />
      )}
      {/* AMENDED 2026-08-11 (W4 ACTION lane): the Payments tab is LIVE, and it
          is NOT a customers read-model (BR-CUS-034 forbids one) — it is the
          payments module's OWN S33 table scoped by `f.account_id`, exactly as
          the Bills tab embeds billing's. One implementation of BR-PAY-021's
          two-date columns and the "Applied to" join; the "+ Record payment"
          empty-state CTA opens the same S22 modal the rail does. */}
      {/* The deposit note moved INTO the group with the table it is about
          (`AccountMoneyTabs.tsx`), and its 39 words of rationale became a
          five-word fact there — B14 rule 33, PO 2026-09-13. */}
      {active === "payments" && (
        <AccountPaymentsGroup
          accountId={detail.id}
          client={props.client}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          state={paymentsState}
          onStateChange={setPaymentsState}
          emptyCtaReason={recordPaymentReason}
          onEmptyCta={() => setOpenModal("payment")}
        />
      )}
      {/* CR-030 W3 · 3.8 — BR-MET-106's stored monthly usage. The sentence that
          stood here was stale TWICE OVER (hard-won law 1): it blamed a reads
          filter CR-028 had already shipped, and it cited DEF-475, which is
          closed. It is replaced by the tab it was standing in for, not
          rewritten — the string changes with the fact, and here the fact is
          that the feature exists.
          ⚠ THIS ONE LINE IS THE DIFFERENCE BETWEEN BUILT AND SHIPPED. The tab,
          its endpoint, its stored table and 25 tests all landed while nothing
          rendered them; a component nothing mounts is dead UI that passes every
          test in the suite (hard-won law 2 — four defects in one day). G40
          reports it the moment the file is tracked, which is the gate working. */}
      {active === "usage" && (
        <AccountUsageTab accountId={detail.id} client={props.client} t={translate} />
      )}
      {/* B14 rule 41 — `ACC-T07` draws ONE table on this tab: the meters on
          this unit, with `Read log` as a row action.
          ⚠ **`ServiceAgreementsPanel` IS NOT DRAWN HERE AND THE BLUEPRINT SAYS
          WHERE IT WENT:** *"The meters belong to the unit, not to the account
          … The services this account holds are a separate fact and live in the
          Service group on Overview."* Overview draws that group, so nothing is
          lost — the fact stopped being said twice. */}
      {active === "meters" && (
        <AccountMetersTab
          views={meterViews}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          openMeterId={searchParams.get(METER_PARAM)}
          onOpenMeter={selectMeter}
        />
      )}
      {/* CR-030 W3 · 3.6 / 3.7 — both tabs draw r10's COLUMN HEADINGS over a
          single spanning cell carrying the absence. The sentence in each is
          the one this screen already shipped, unchanged: neither endpoint has
          appeared. An empty tbody would assert "never adjusted" / "nothing
          filed", which is a claim about a customer nobody made. */}
      {/* CR-059 CS-37 · P13 — every credit note on this account, with the bill
          each came from. Before this tab the only way to answer "show me every
          credit note on this account" was to open the customer's bills one at a
          time; the database index built for the lookup had never had a query
          run against it. */}
      {active === "credits" && (
        <AccountCreditsGroup
          accountId={detail.id}
          client={props.client}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          heldCredit={
            <AccountHeldCreditGroup
              accountId={detail.id}
              accountNo={detail.account_no ?? ""}
              client={props.client}
              t={translate}
              timeZone={timeZone}
              dateFormat={dateFormat}
            />
          }
        />
      )}
      {/* CR-059 CS-23 · task 6 — every instalment, paid or outstanding, with
          the day it was met. `on_time` is the SERVER's judgment (BR-PAY-021)
          and nothing here recomputes it. */}
      {active === "plan" && (
        <AccountPlanGroups detail={detail} client={props.client} t={translate} />
      )}
      {/* CR-070 wave O — the jobs on this account AND at the address it shares,
          each row saying which (`US-WRK-004`). The panel is Work's, composed
          here: one implementation, two hosts, so the premises and the account
          cannot describe the same job two ways. */}
      {active === "work" && (
        <>
          {/* CR-162-BRC10 — the Build panel that stood here is GONE (PO
              2026-10-02: the New Connection's own page tracks progress and
              takes every action). A Pending account links to that page from
              its header instead (`AccountPendingBuild`). */}
          <WorkOrdersTab
            host="account"
            hostId={detail.id}
            t={translate}
            timeZone={timeZone}
            dateFormat={dateFormat}
            openOrderId={searchParams.get(ORDER_PARAM)}
            onOpenOrder={selectOrder}
            client={props.client}
          />
        </>
      )}
      {/* ⚠ `onNew` IS PASSED, and that is the whole of hard-won law 2: the tab's
          own `+ New adjustment` was a live button with `onClick={() => undefined}`
          behind it for as long as the refusal stood. It opens the same modal
          the header's `Adjust` opens — one action, one door.
          B14 rule 41 — the tab draws `ACC-T09`'s six columns over the rows
          `GET /payments?f.account_id=…&f.type=adjustment` has served all along,
          so it takes the account and the regional pair every dated table on
          this screen already takes (`BR-SHL-034`). */}
      {active === "adjustments" && (
        <AccountAdjustmentsTab
          accountId={detail.id}
          client={props.client}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onNew={() => setOpenModal("adjust")}
        />
      )}
      {/* `ACC-S8` — the tab that drew five column heads over a stated absence
          now draws rows. It takes the account it is about, and the regional
          pair every dated table on this screen already takes (`BR-SHL-034` —
          one date formatter). */}
      {active === "documents" && (
        <AccountDocumentsTab
          accountId={accountId}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          client={props.client}
        />
      )}
      {/* AMENDED 2026-08-11 (W4 ACTION lane): Notes is one of exactly two tabs
          customers OWNS outright (BR-CUS-035), and `account_notes` exists now
          — so the card list is real, pinned first, and the tab carries the same
          Add-note modal the rail does. */}
      {active === "notes" && (
        <AccountNotesTab
          accountId={detail.id}
          client={props.client}
          timeZone={timeZone}
          dateFormat={dateFormat}
          addReason={writeBlockedReason}
          onAdd={() => setOpenModal("note")}
        />
      )}
      {/* BR-CUS-034 / US-AUD-005: the Audit tab is the S61 viewer filtered to
          this entity — the SAME component the premises and unit details use, so
          one audit surface keeps one set of masking and window rules. */}
      {active === "audit" && (
        /* `data-account-overview` + `data-overview-group` are what the BROWSER
           census selects on (`10-scripts/render-checks/acc02-tab-conformance
           .mjs`). One column, because `ACC-T12` gives it one.

           ⚠ **THE TABLE INSIDE IS METERING'S `AuditTab` AND IS NOT REDRAWN
           HERE.** `ACC-T12` draws `▸ · WHEN ▼ · WHO · WHAT HAPPENED`; the
           component draws `WHEN · WHO · WHAT CHANGED · FROM · TO` with no
           disclosure, because a PO ruling of 2026-09-10 on the Premises
           blueprint took the expander out in those words — *"that is the whole
           use of an audit log: seeing what a field used to say"*. It is ONE
           audit surface on eight screens (BR-CUS-034 / US-AUD-005), so the
           account cannot hold a different one without the masking and window
           rules diverging per module. The divergence is declared in
           `drawn/acc02-audit.json` and reported, not resolved here. */
        <div data-account-overview="">
          <div className="flex min-w-0 flex-col">
            <Panel
              as="section"
              tone="group"
              data-overview-group="audit"
              title={t("customers.account.tab.audit")}
            >
              <AuditTab entityType="account" entityId={detail.id} t={translate} regional={props} />
              {/* CR-030 W3 · 3.11 — r10's USER column tells `System` from
                  `Sarah Miller (portal)`. BR-CUS-028 is why ours cannot. */}
              <AccountAuditPortalNote t={translate} />
            </Panel>
          </div>
        </div>
      )}

      {/* BR-CUS-054 — "all accounts for this customer". Rendered only when the
          server SENDS a customer: an account created before the entity existed,
          or an imported row that named neither a reference nor a name, has
          none, and inventing one from the contact would put a customer in the
          master list that nobody created. */}
      {detail.customer !== null && (
        <div className="mt-4 border border-divider px-4 py-3.5 [&_h3]:m-0 [&_h3]:mb-1.5 [&_h3]:font-heading [&_h3]:text-md [&_h3]:font-bold [&_ul]:m-0 [&_ul]:mt-2 [&_ul]:flex [&_ul]:list-none [&_ul]:flex-wrap [&_ul]:gap-2 [&_ul]:p-0" role="note">
          <h3>{t("customers.account.customer.title")}</h3>
          {/* Name and kind as two elements rather than one interpolated
              sentence: a "{{name}} ({{kind}})" string is pure punctuation and
              reads identically in ten languages, which is the G15 defect
              (a value that was never actually translated). */}
          <p>{detail.customer.display_name}</p>
          <p className="m-0 mt-2 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {t(`customers.account.customer.kind.${detail.customer.kind}`)}
          </p>
          <ul>
            {detail.customer.accounts.map((linked) => (
              <li key={linked.id}>
                {linked.id === detail.id ? (
                  <span>{linked.account_no}</span>
                ) : (
                  <Link to={tenantPath(accountDetailPath(linked.id))}>{linked.account_no}</Link>
                )}
              </li>
            ))}
          </ul>
          <p className="m-0 mt-2 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {t("customers.account.customer.count", {
              count: detail.customer.accounts.length,
            })}
          </p>
          {/* `CR-161-BRC10` W4 — the utility's OWN customer fields, read-only.
              The PO's *"Customer page · Account detail header"*: there is no
              customer page, so this header block is where a customer's answers
              are seen. Nothing at all when none is placed here. */}
          <CustomFieldsView
            entity="customers"
            screen="S21"
            values={detail.customer.custom_data ?? {}}
            formatDate={(iso) => formatDate(iso, timeZone, dateFormat)}
            client={client}
          />
        </div>
      )}

      {/* AMENDED 2026-08-11 (W4/W8 ACTION lane). This used to be ONE panel
          naming all seven S22 modals as absent — the right call when none of
          them had a service. Four are live now and five carry their own reason
          on their own disabled control, which is where a reason belongs
          (BR-SHL-025). The stale panel is DELETED rather than left beside the
          buttons it contradicts: a claim that has stopped being true is the one
          a reader trusts without checking (hard-won law 1). The customer panel
          below is a different, still-true absence. */}
      {/* ⚠ "The customer record, and what it still cannot do" IS DELETED — PO
          ruling 2026-08-24, walking the deployed build: *"on account details
          screen - we dont want -"*, quoting the panel back in full.

          It was TRUE — the missing duplicate check on a hand-created account is
          real — and it is the THIRD panel of this kind the PO has removed today
          (both Accounts-tab boxes went in the same session). The pattern is
          worth naming rather than absorbing one deletion at a time: hard-won
          law 2 asks a SCREEN to state what it cannot do, and these panels
          answer that by narrating our build backlog to an operator in a grey
          box. The law's purpose is served where the user is actually confused —
          a dash in a column, a control that does nothing — not in a paragraph
          at the foot of a page.

          The duplicate-check gap is NOT lost with the box: it is a real
          product gap and belongs in the defect register, which is where a
          backlog goes. G38 is unaffected — it checks that a stated absence
          cites the row that will kill it, never that a screen must carry one. */}

      {/* US-PAY-001 §5: what the payment PAID, from the same transaction that
          took it. Rendered on THIS page rather than swallowed, because a clerk
          who has just taken $247.30 has to see where it went — and because the
          panel also states what did NOT happen (no receipt queued, the cached
          balance not updated), which is a fact about this deployment. */}
      {recorded !== null && (
        <RecordPaymentPanel recorded={recorded} onDismiss={() => setRecorded(null)} />
      )}

      {openModal === "payment" && (
        <RecordPaymentModal
          accountId={detail.id}
          accountLabel={accountHeadline(detail, translate)}
          currency={detail.currency}
          balance={detail.balance}
          today={todayInZone(timeZone)}
          dateFormat={dateFormat}
          client={props.client}
          onClose={() => setOpenModal(null)}
          onRecorded={(payment) => {
            setRecorded(payment);
            setOpenModal(null);
            // The SERVER's own answer, re-read: the payments service reports
            // that it did not touch `accounts.balance` (customers' column,
            // B1), so nothing here patches a balance locally and hopes.
            void queryClient.invalidateQueries({ queryKey: accountDetailQueryKey(accountId) });
            fireToast(t("customers.account.toast.paymentRecorded"));
          }}
        />
      )}
      {openModal === "adjust" && (
        <AdjustModal
          accountId={detail.id}
          accountLabel={accountHeadline(detail, translate)}
          currency={detail.currency}
          today={todayInZone(timeZone)}
          dateFormat={dateFormat}
          client={props.client}
          onClose={() => setOpenModal(null)}
          onRecorded={(payment) => {
            // The SAME panel a recorded payment opens: an adjustment allocates
            // exactly as a payment does, so what met bills and what carried as
            // credit are the figures a clerk needs either way.
            setRecorded(payment);
            setOpenModal(null);
            void queryClient.invalidateQueries({ queryKey: accountDetailQueryKey(accountId) });
            fireToast(t("customers.account.toast.adjustmentPosted"));
          }}
        />
      )}
      {/* `ACC-S14` — a quick action opens as a FORM OVER THE ACCOUNT, so the
          balance, the status and the tabs stay readable behind it. That phrase
          is the commitment card's own acceptance sentence and it is why this is
          a dialog rather than a page (conformance file §3). */}
      {openModal === "activate" && activateForm !== null && (
        <AccountQuickActionForm
          form={activateForm}
          kicker={accountHeadline(detail, translate)}
          facts={{
            statusName: detail.status_name,
            // The date the clerk has in the box, echoed in the tenant's format
            // through the ONE formatting path — never a second copy of it.
            openedAt: null,
            // The plan the account will INHERIT (BR-CUS-029 — it belongs to
            // the unit, not to the account). Composed from the same two fields
            // the header's PLAN column draws and through the same version key,
            // so the recap and the tile two inches above it cannot disagree.
            unitPlan:
              detail.unit_plan === null || detail.unit_plan.name === null
                ? null
                : detail.unit_plan.version === null
                  ? detail.unit_plan.name
                  : `${detail.unit_plan.name} · ${t("customers.account.planVersion", {
                      version: detail.unit_plan.version,
                    })}`,
            outcomeSentence: t("customers.account.quick.activate.outcome"),
          }}
          dateFormat={dateFormat}
          today={todayInZone(timeZone)}
          absentText={t("customers.account.quick.absent")}
          onClose={() => setOpenModal(null)}
          onSubmit={async (values) => {
            try {
              // ONLY the fields `services.activate_account` accepts —
              // `_reject_unknown(data, frozenset({"opened_at", "status"}))`
              // raises a field error on anything else, so a form that sent its
              // whole state would 400 on a stranger it drew itself.
              await activate.mutateAsync({ opened_at: values.opened_at ?? "" });
              setOpenModal(null);
              return { ok: true };
            } catch (error) {
              if (isApiError(error)) {
                return { ok: false, error: formErrorEnvelope(error) };
              }
              return { ok: false, error: { code: "", message_key: "api.error.unexpected" } };
            }
          }}
        />
      )}
      {openModal === "communication" && (
        <AccountCommunicationDialog
          accountId={detail.id}
          dateFormat={dateFormat}
          // `BR-TEN-043` — the business date is the PAGE's, never a clock this
          // dialog reads. *Queue it · Now* means today as this utility sees it.
          today={todayInZone(timeZone)}
          onClose={() => setOpenModal(null)}
        />
      )}
      {/* ── `CR-094-BRC01` wave L · `BR-CUS-1051` — THE EIGHT THAT USED TO
          NAVIGATE AWAY ────────────────────────────────────────────────────
          PO 2026-09-13, verbatim: *"Yes move the eight quick actions over the
          account"*. Move-out, Move-in, Close out, Print bill, Issue credit,
          Change plan, Disconnect notice and Payment plan are CHILD ROUTES of
          this page now, and this renders whichever of them the URL names inside
          the shared dialog — so the balance, the status and the tabs stay on
          screen behind it.

          ⚠ **NOT ONE OF THE EIGHT WAS RE-TYPED.** Each is the same component at
          the same address it already had; `App.tsx` nests them and this mounts
          the `<Outlet/>`. It renders NOTHING when no child matches, which is
          this page's ordinary state. */}
      <AccountActionOverlay
        accountId={accountId}
        kicker={accountHeadline(detail, translate)}
        t={translate}
      />
      {openModal === "temporaryStop" && (
        <TemporaryStopModal
          accountId={detail.id}
          accountLabel={accountHeadline(detail, translate)}
          today={todayInZone(timeZone)}
          timeZone={timeZone}
          dateFormat={dateFormat}
          client={props.client}
          onClose={() => setOpenModal(null)}
          onDone={(message) => {
            setOpenModal(null);
            void queryClient.invalidateQueries({ queryKey: accountDetailQueryKey(accountId) });
            fireToast(message);
          }}
        />
      )}
      {openModal === "note" && (
        <AddNoteModal
          accountId={detail.id}
          accountLabel={accountHeadline(detail, translate)}
          client={props.client}
          onClose={() => setOpenModal(null)}
          onSaved={() => {
            setOpenModal(null);
            void queryClient.invalidateQueries({ queryKey: accountNotesKey(detail.id) });
            fireToast(t("customers.account.toast.noteAdded"));
          }}
        />
      )}
    </div>
  );
}

/**
 * `CR-162-BRC10` — the header line that links a Pending account to the New
 * Connection that will activate it. Two cases, one read (`GET
 * /accounts/{id}/build`):
 *
 *   * the build's owner MASTER account, Pending until approval (Q1) — the
 *     request number, its state and *Open request*;
 *   * a regular account opened by a move-in BEFORE approval (ruled B) —
 *     *Billing starts once the unit activates.* and the same link.
 *
 * Renders nothing for every other account.
 */
export function AccountPendingBuild(props: {
  accountId: string;
  pending: boolean;
  t: Translator;
  path: (segment: string) => string;
  client?: ApiClient;
}) {
  const read = useQuery({
    queryKey: accountBuildStatusKey(props.accountId),
    queryFn: () => getAccountBuildStatus(props.accountId, props.client),
    enabled: props.accountId !== "",
    retry: false,
  });
  const waiting = read.data?.awaiting_activation ?? null;
  if (waiting !== null && waiting.connection_id !== null) {
    return (
      <PendingBuildLink
        build={{ id: waiting.connection_id, connection_no: waiting.connection_no }}
        t={props.t}
        path={props.path}
        billingWaits
      />
    );
  }
  const build = read.data?.build ?? null;
  if (props.pending && build !== null) {
    return <PendingBuildLink build={build} t={props.t} path={props.path} />;
  }
  return null;
}

export default AccountDetailPage;

// ── Tabs ───────────────────────────────────────────────────────────────────

function OverviewTab(props: {
  /**
   * ⚠ `& Partial<AccountAgeingCells>` — THE SERVER HAS ALWAYS SERVED THESE AND
   * THE TYPE DID NOT DECLARE THEM, WHICH IS WHY NO SCREEN COULD SHOW THEM.
   * `selectors.account_row` spreads `ageing_cells(...)` into EVERY row, and
   * `account_detail_dict` spreads `account_row(...)` — so `ageing_segment`,
   * `ageing_days_past_due` and `ageing_source` are on the detail payload and
   * have been since 2026-08-24. `AccountRow` never declared them, so the data
   * arrived and TypeScript could not see it: the Accounts LIST works around it
   * with `AccountRowWithAgeing` and the DETAIL simply went without.
   *
   * That is why a clerk could read an Ageing column on the list, drill into the
   * account, and find the words "past due" nowhere on the page — the blueprint
   * proved it on A-11812, where the API answers `d61_90`, 61 days, source
   * `opening_buckets`.
   *
   * The list's own type is REUSED rather than a second one declared here: one
   * owner for what the ageing keys are (`accountsListCells.AccountAgeingCells`),
   * so the two screens cannot drift on the vocabulary.
   */
  detail: AccountDetail & Partial<AccountAgeingCells>;
  /** `BR-SHL-025` — the role/state refusal this clerk carries, if any. It WINS
   *  over a group's own reason: somebody who may not write at all needs to be
   *  told that before being told why one panel is derived. */
  canWriteReason?: string | null;
  /** `ACC-S15` — open the edit for one group. */
  onEditGroup?: (group: AccountOverviewGroup) => void;
  /** The account's id, for the panels that read another module's list. */
  accountId: string;
  client?: ApiClient;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** r10's `All bills →` and `Details →` move the TAB, not the route. */
  onSelectTab?: (id: string) => void;
}) {
  const { detail, t } = props;
  // Record links (PO 2026-10-19): a record shown on this tab opens its own page.
  const tenantPath = useTenantPath();
  /**
   * `ACC-S15` — one pencil per group, built once here so every group asks the
   * SAME function whether it can be edited (`accountGroupBlockedReason`) and no
   * panel can quietly acquire its own answer. `R5` draws a control on every
   * group heading and `BR-SHL-025` says a control that cannot act is DISABLED
   * WITH ITS REASON rather than hidden — so a group with nothing editable still
   * draws one, refusing.
   */
  // ⚠ **ONE GROUP'S REFUSAL IS A ROLE AND NOT THE SURFACE CELL** — `BR-CUS-1047`
  // gives the unit correction to a supervisor (`SYSTEM_ADMIN`/`EXECUTIVE`) while
  // A4 grades the whole Accounts surface `Full` for a Billing Clerk, so
  // `canWriteReason` is null for them and the server still answers 403. The role
  // is read ONCE here, where a `QueryClient` already exists, and the sentence is
  // passed down: `AccountGroupPencil` stays hook-free so a bare render of a
  // pencil needs no provider.
  const role = useTenantRole(props.client);
  const pencilFor = (group: AccountOverviewGroup): ReactNode =>
    props.onEditGroup === undefined ? undefined : (
      <AccountGroupPencil
        group={group}
        t={t}
        roleReason={props.canWriteReason ?? accountGroupRoleReason(group, role, t)}
        onEdit={props.onEditGroup}
      />
    );
  // DEF-684 — the platform category catalogue, so this panel prints a NAME for
  // all seven of BR-CUS-094's codes instead of the four that had i18n keys.
  const categories = useAccountCategories(props.client);
  const contact = primaryContact(detail.contacts);
  // ⊕ T4 — the SECOND person: the first live contact that is not the primary.
  const coApplicant =
    (detail.contacts ?? []).find((row) => !row.is_primary && row !== contact) ?? null;
  const mailing = detail.addresses.filter((address) => address.kind === "mailing");
  const govId = maskedGovId(contact?.gov_id_last4 ?? null);
  // ── THE UNIT GROUP's three derived cells (B14 rule 41 · `ACC-02` R5) ──────
  // ⚠ **`premise_address` IS OPTIONAL ON THE WIRE AND `""` IS NOT AN ADDRESS.**
  // Both absences collapse to `null` here so the dash is drawn once, in one
  // place, rather than three `?? ""` chains that each render a blank cell — an
  // empty cell reads as *failed to load*, a dash reads as *nothing recorded*.
  const premiseAddress =
    detail.premise_address !== null && detail.premise_address !== undefined && detail.premise_address !== ""
      ? detail.premise_address
      : null;
  // The drawing's `142 Bakers Row, Silver Creek, TX 78611` — the building's
  // line, then the locality, joined by a comma. `premiseLocality` is the header's
  // own helper and is imported rather than re-derived, so a map, an envelope and
  // this group cannot disagree (hard rule 8's whole point).
  const localityLine = premiseLocality(detail.premise_locality ?? null);
  const serviceAddress =
    premiseAddress === null
      ? localityLine
      : localityLine === null
        ? premiseAddress
        : `${premiseAddress}, ${localityLine}`;
  // `SCW-RES v1` — the drawing's own summary of the plan the UNIT carries. The
  // PLAN group beside it draws the same plan in four rows; this is the one line
  // the UNIT group draws, because what an account is attached to includes what
  // that attachment prices at. `version` is `BR-CUS-013`'s snapshot integer and
  // is only appended when the server sent one.
  const unitPlanCode = detail.unit_plan?.code ?? null;
  const unitPlanSummary =
    unitPlanCode === null || unitPlanCode === ""
      ? null
      : detail.unit_plan?.version === null || detail.unit_plan?.version === undefined
        ? unitPlanCode
        : `${unitPlanCode} v${detail.unit_plan.version}`;

  return (
    <div
      /* `data-account-overview` and the per-group `data-overview-group` hooks
         are what a BROWSER census selects on: jsdom computes no layout, so no
         test in this repo can say the screen LOOKS like the drawing, and B14
         rule 41's own status cell says so. The hooks are cheap now and
         expensive to retrofit. */
      data-account-overview=""
      // ⚠ **EVEN COLUMNS, MEASURED AGAINST THE DRAWING (PO 2026-09-13).**
      // `.cus-two-col` declared `grid-template-columns: 3fr 2fr` and the
      // migration carried it across faithfully — so at 1440 the columns
      // measured **662px and 442px** while the blueprint draws them even.
      // The PO read it off the running product: *"Money and Customer - not
      // coming in 1 line - it is not align - you may have to adjust the
      // %age"*. A pixel-neutral migration reproduces what was there,
      // including what was wrong; this is the correction, made separately
      // and on a measurement rather than on a guess.
      className="mt-4 grid grid-cols-2 items-start gap-4 max-md:grid-cols-1"
    >
      {/* ── THE LEFT COLUMN, IN THE DRAWN ORDER ───────────────────────────
          MONEY · SERVICE · METERS · PLAN · HISTORY. `UsageTrendPanel` follows
          them: the blueprint's Overview does not draw it on this tab, and
          REMOVING a live block is a decision for the PO rather than for a
          lane, so it is kept and placed after the drawn five so the drawn
          sequence stays contiguous from the top. */}
      <div className="flex min-w-0 flex-col gap-4">
        {/* ⚠ **MONEY — THE GROUP THE PO RULED ON 2026-09-10 AND NOTHING BUILT
            (`DEF-GOV-5006`).** Verbatim: *"we should have all these details
            captured on screen"* and *"when we do information architecture, we
            have to logically group the information, give group a heading so
            that it is easy for user to understand"*. The Accounts blueprint
            measured the cost: the account endpoint serves 69 fields and ELEVEN
            reached no screen at all.

            **Ageing is the one that cost a clerk something.** The accounts LIST
            draws an Ageing column. The DETAIL drew nothing — on `A-11812` the
            server answers `d61_90`, 61 days, source `opening_buckets`, and the
            words *past due* appeared NOWHERE on that account's page. Somebody
            drilled in from the list and lost the single fact that says how
            overdue the account is.

            ⚠ **BALANCE IS DELIBERATELY NOT IN THIS GROUP, AND THAT IS THE
            RULING BEING FOLLOWED RATHER THAN TRIMMED.** The same ruling's note
            records what grouping REMOVED — *"the name appeared three times on
            the old screen, the account number twice, the deposit twice"* —
            so a fact belongs to exactly one place. The figure is the header's
            tile (`accountDetailHeader.tsx`, with `DEF-127`'s whole derivation
            and `DEF-628`'s not-yet-billable cell); repeating it here would
            re-create the duplication the ruling exists to delete. **What is
            here is only what is on NO screen today.**

            One hint at the foot rather than a helper under each row: B14 rule
            32 gives a section ONE sentence, and rule 33 caps a fact at six
            words — the blueprint draws per-row helpers and the UI rules win on
            construction (rule 38). */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="money"
          title={t("customers.account.panel.money")}
          trailing={pencilFor("money")}
        >
          <FactList>
            <Fact label={t("customers.account.field.basis")}>
              {detail.balance_basis === null || detail.balance_basis === undefined ? (
                <Dash />
              ) : (
                t(`cells.basis.${detail.balance_basis}`)
              )}
            </Fact>
            {/* The SOURCE is a code on the wire (`"ledger"`), and B14 rule 31
                forbids a database value being the visible value of a field —
                so it resolves through the catalogue and falls back to a dash,
                NEVER to the raw string. */}
            <Fact label={t("customers.account.field.balanceSource")}>
              {detail.balance_source === "ledger" ? (
                t("customers.account.balanceSource.ledger")
              ) : (
                <Dash />
              )}
            </Fact>
            {/* The list's own cell, mounted. It already owns the band's name,
                its tone and the server's absence sentence. */}
            <Fact label={t("customers.accounts.col.ageing")}>
              <AgeingCell row={detail} t={t} />
            </Fact>
            {/* Only when a band was found: a day count with no band behind it
                is a number with nothing to mean. */}
            <Fact label={t("customers.account.field.daysPastDue")}>
              {ageingSegmentOf(detail) !== null &&
              detail.ageing_days_past_due !== null &&
              detail.ageing_days_past_due !== undefined ? (
                detail.ageing_days_past_due
              ) : (
                <Dash />
              )}
            </Fact>
            <Fact label={t("customers.account.field.ageingSource")}>
              {detail.ageing_source === "opening_buckets" ? (
                t("customers.account.ageingSource.openingBuckets")
              ) : detail.ageing_source === "bills" ? (
                // DEF-CUS-10181 — a band aged by an unpaid bill says so.
                t("customers.account.ageingSource.bills")
              ) : (
                <Dash />
              )}
            </Fact>
                      {/* ⚠ **`Returned payments` CAME FROM ACCOUNT SETUP (B14 rule 41).**
                The blueprint draws it as MONEY's last row; the screen had it
                under ACCOUNT SETUP. MOVED, not copied.
                BR-PAY-013: it is counted by the payments module's bounced-
                payment path. (`BR-PAY-018`'s bad-address flag has a writer
                since `DEF-PAY-6342` — marking post returned — and its banner
                sits under the page head.) */}
            {/* ⚠ **THE FOUR DEPOSIT AND CREDIT ROWS LIVE HERE NOW, AND THE
                SEPARATE `Deposit & credit` GROUP IS GONE (PO 2026-09-13,
                B14 rule 41).** The blueprint draws ELEVEN rows under one
                MONEY heading and the product had them under three: six here,
                four in a group of their own, one under `Account`. The PO's
                own ruling of 2026-09-10 is what settles it — *a fact sits
                under ONE named group* — and its note records that grouping is
                exactly what removed the duplicates (*the deposit twice,
                'Deposit received' twice*).

                **FOUND BY THE BROWSER CENSUS, NOT BY READING** — every vitest
                case was green over the split, because jsdom cannot see which
                heading a row sits under once both are in the DOM.

                Order is the drawing's: credit tier, then the deposit held,
                then when it arrived, then the interest on it. `Balance` is
                drawn in this group and is NOT repeated here — it is the
                header tile by the ruling of 2026-09-03, and printing it twice
                is the duplication this merge exists to end. */}
            <Fact label={t("customers.account.field.creditTier")}>
              {detail.credit_tier !== null && detail.credit_tier !== "" ? (
                detail.credit_tier
              ) : (
                // BR-CUS-058: COMPUTED from payment history, and nothing
                // computes it yet. "A" would be an invented credit judgement.
                <NotRecorded
                  label={t("customers.account.creditTierAbsent")}
                  why={t("customers.account.creditTierWhy")}
                  ruleRef="BR-CUS-058"
                />
              )}
            </Fact>
            <Fact label={t("customers.account.field.depositOnFile")}>
              {detail.deposit_on_file !== null ? (
                <MoneyCell amount={detail.deposit_on_file} currency={detail.currency} />
              ) : (
                <Dash />
              )}
              <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]"> {t("customers.account.depositNoWriter")}</span>
            </Fact>
            <Fact label={t("customers.account.field.depositReceived")}>
              {detail.deposit_received_on !== null ? (
                <DateCell
                  value={detail.deposit_received_on}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              ) : (
                <Dash />
              )}
            </Fact>
            <Fact label={t("customers.account.field.depositInterest")}>
              {/* ⚠ **THIS ROW SAID "No column for it" UNTIL 2026-09-03 AND
                  THAT HAD STOPPED BEING TRUE (`DEF-3486`, hard-won law 1).**
                  BR-CUS-057's accrual is BUILT: `apps/customers/
                  deposit_interest.py` is a whole module and
                  `selectors.deposit_interest_accrued(account_id, as_of)`
                  publishes the figure, both landed with CR-059 W6 task 30 on
                  2026-09-03. What is missing is one step further out —
                  `account_detail_dict` does not put it in the payload — so
                  this screen genuinely cannot show it and $0.00 would still be
                  a money claim. The sentence now says which of the two it is,
                  because "there is no column" sends the next lane to build a
                  column that exists. */}
              <NotRecorded
                label={t("customers.account.depositInterestAbsent")}
                why={t("customers.account.depositInterestWhy")}
                ruleRef="BR-CUS-057"
              />
            </Fact>
            <Fact label={t("customers.account.field.nsfCount")}>{detail.nsf_count}</Fact>
</FactList>
          {/* ⚠ **THE GROUP HINT IS GONE, 2026-09-13 (B14 rule 33 sweep).** It read
            *"Ageing is counted from the opening balance, not from a bill"* — and the
            `Ageing source` row says `Opening buckets`
            — RATIONALE, which is ZERO words on screen, and `ACC-02` draws no hint
            under this heading either. The fact it explained is already a ROW in
            the group above. Why it is so lives here and in the register. */}
        </Panel>

        {/* ── SERVICE ────────────────────────────────────────────────────
            The blueprint draws this group on the OVERVIEW; the product had the
            same table only on the Meters tab, so a clerk answering *what is
            this account signed up for* had to leave the tab they land on.

            ⚠ **THE TABLE IS MOUNTED, NOT COPIED.** `ServiceAgreementsTable`
            below is the one the Meters tab already renders, lifted out of
            `ServiceAgreementsPanel` so both hosts draw one table (B14 rule 36).

            ⚠ **THE DRAWN TOOLBAR — `Filter ▾ · Search services · Columns ▾ ·
            ↓ Export` — IS NOT BUILT, AND THAT IS A REFUSAL RATHER THAN AN
            OMISSION.** `POST /exports` registers no `accounts` resource, so
            Export cannot act at all; the other three would act on the one or
            two rows an account holds. Four controls that cannot do anything is
            hard-won law 2's mirror — a live screen behind a dead control — and
            `BR-SHL-010` says an undeclared capability does not render. Reported
            rather than hand-rolled. */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="service"
          title={t("customers.account.panel.service")}
          trailing={pencilFor("service")}
        >
          <ServiceAgreementsTable
            detail={detail}
            t={t}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            client={props.client}
          />
        </Panel>

        {/* ── METERS ─────────────────────────────────────────────────────
            ⚠ **THE COUNT IN THE ABSENCE SENTENCE IS DERIVED, NEVER TYPED.** The
            blueprint draws *"holds two service agreements"* against `A-11812`,
            and two is that account's figure on the day it was drawn — B14 rule
            37: a figure in a wireframe is an illustration, never a fact to
            build to. It is read off `service_agreements.length` here, so the
            sentence is true on every account.

            `meters` is `{id, asset_no, qualifier}` and nothing more — the rest
            of a meter (service, type, install date, multiplier, last read)
            belongs to the ASSETS module and is drawn by the Meters TAB, which
            reads it through its own endpoint. This group states what the
            account holds; it does not grow a second asset table. */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="meters"
          title={t("customers.account.panel.metersHeld")}
          trailing={pencilFor("meters")}
        >
          {detail.meters.length === 0 ? (
            <>
              <p className="m-0 mb-1 font-heading text-md font-bold uppercase">
                {t("customers.account.noMeterAssigned")}
              </p>
              <p className="m-0 mb-3 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                {t("customers.account.noMeterAssignedWhy", {
                  count: detail.service_agreements.length,
                })}
              </p>
            </>
          ) : (
            /* ⚠ **TWO FAULTS HERE, BOTH READ OFF THE RUNNING SCREEN BY THE
               PRODUCT OWNER ON 2026-09-13** — *"look at this table Meters —
               SM-7045 · sub / SM-7203 · sub / W-5045 · master — not correct"*.

                 1 · **`qualifier` IS A RAW DATABASE VALUE AND IT REACHED A
                     CLERK.** B14 rule 31: *"no Databse ID on screen - that is a
                     rule"* (PO 2026-08-31). `metering.meters.qualifier.master`
                     and `.sub` already existed and are NO BETTER — `(master)`
                     and `(sub)` are the same code in brackets — so this
                     resolves to a clerk's own words instead.
                     **THE FALLBACK IS THE ASSET NUMBER ALONE, NEVER THE CODE.**
                     `accountCategoryName` falls back to the code deliberately,
                     because inventing a category label is how `government`
                     starts reading as "Municipal"; that reasoning does not
                     carry here. This vocabulary is CLOSED — `assets/selectors
                     .py:1890` derives exactly `sub` (has a parent), `master`
                     (has children) or null — so an unresolved value is a value
                     this product does not have, and saying nothing is right.
                 2 · **IT WAS A GREY SCROLLING BOX IN A COLUMN OF FLAT GROUPS.**
                     Every other group on this tab sits under the accent rule
                     with no border and no fill; this one carried its own
                     surface and capped itself at 240px with a scrollbar, so
                     a unit with six meters hid three of them behind a scroll
                     nobody looks for. A plain list, like everything else. */
            <ul className="m-0 list-none p-0 text-base">
              {detail.meters.map((meter) => {
                const qualifier =
                  meter.qualifier === null || meter.qualifier === ""
                    ? ""
                    : t(`customers.account.meter.qualifier.${meter.qualifier}`, {
                        defaultValue: "",
                      });
                return (
                  <li key={meter.id} className="mb-1">
                    {meter.id !== null && meter.id !== "" ? (
                      <InlineLinkTo to={tenantPath(assetDetailPath(meter.id))}>{meter.asset_no}</InlineLinkTo>
                    ) : (
                      meter.asset_no
                    )}
                    {qualifier !== "" && (
                      <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]">
                        {" "}
                        · {qualifier}
                      </span>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Panel>

        {/* ⚠ **PLAN — DRAWN AS A GROUP OF ITS OWN AND BUILT AS NOTHING.** The
            account's plan reached the screen only as the header tile, which
            shows the CODE and nothing else. `unit_plan` has carried the name,
            the code, the version and the date all along.

            The plan is READ FROM THE UNIT and is not stored on the account
            (`BR-CUS-010`) — the heading says so, because a clerk who reads
            *Plan* on an account will otherwise believe the account holds it
            and that changing it here would stick. */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="plan"
          title={t("customers.account.panel.plan")}
          trailing={pencilFor("plan")}
        >
          <FactList>
            <Fact label={t("customers.account.panel.plan")}>
              <AccountPlanName plan={detail.unit_plan} />
            </Fact>
            <Fact label={t("customers.account.field.planCode")}>
              {detail.unit_plan?.code ?? <Dash />}
            </Fact>
            <Fact label={t("customers.account.field.planVersion")}>
              {detail.unit_plan?.version ?? <Dash />}
            </Fact>
            <Fact label={t("customers.account.field.inForceSince")}>
              {detail.unit_plan?.since === null || detail.unit_plan?.since === undefined ? (
                <Dash />
              ) : (
                <DateCell
                  value={detail.unit_plan.since}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              )}
            </Fact>
          </FactList>
          {/* ⚠ **THE GROUP HINT IS GONE, 2026-09-13 (B14 rule 33 sweep).** It read
            *"The plan is read from the unit and is not stored here"* — and the header
            tile is already headed `PLAN FROM UNIT`
            — RATIONALE, which is ZERO words on screen, and `ACC-02` draws no hint
            under this heading either. The fact it explained is already a ROW in
            the group above. Why it is so lives here and in the register. */}
        </Panel>

        {/* ── HISTORY ────────────────────────────────────────────────────
            The blueprint heads this group `HISTORY` with `All bills →` on the
            right of the heading. It was a plain `Recent bills` card; the panel
            itself is unchanged — same query, same rows, same `All bills →` —
            and only its heading, its tone and its empty state move, so no
            second bills reader is written. */}
        <RecentBillsPanel
          accountId={props.accountId}
          client={props.client}
          t={t}
          onSeeAll={() => props.onSelectTab?.("bills")}
          pencil={pencilFor("bills")}
        />

        <UsageTrendPanel
          accountId={detail.id}
          client={props.client}
          t={t}
          onDetails={() => props.onSelectTab?.("usage")}
          pencil={pencilFor("usage")}
        />

      </div>

      {/* ── THE RIGHT COLUMN, IN THE DRAWN ORDER ──────────────────────────
          CUSTOMER · MAILING ADDRESS · CUSTOMER RECORD · BILLING PREFERENCES ·
          ACCOUNT SETUP · PORTAL ACCESS. `PaymentMethodPanel` and DEPOSIT &
          CREDIT follow them, for the reason the usage panel does. */}
      <div className="flex min-w-0 flex-col gap-4">
        {/* BR-CUS-045: the contact the bills go to. Everything here is PII and
            the government id is the last four ONLY — there is no fuller value
            on the server for a reveal control to ask for. */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="customer"
          title={t("customers.account.panel.customer")}
          trailing={pencilFor("customer")}
        >
          {contact === null ? (
            <p className="m-0 mb-3 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t("customers.account.noContact")}</p>
          ) : (
            <FactList>
              {/* `DEF-CUS-9776` — the CUSTOMER's name (a company's legal name),
                  as the drawing's *Full name · Bramble Bakery*; the contact's
                  name only where no customer holds the account. */}
              <Fact label={t("customers.account.field.fullName")}>
                {detail.customer?.display_name || contact.full_name || <Dash />}
              </Fact>
              <Fact label={t("customers.account.field.email")}>{contact.email ?? <Dash />}</Fact>
              <Fact label={t("customers.account.field.phone")}>{contact.phone ?? <Dash />}</Fact>
              <Fact label={t("customers.account.field.dob")}>
                {contact.dob !== null ? (
                  <DateCell
                    value={contact.dob}
                    timeZone={props.timeZone}
                    dateFormat={props.dateFormat}
                  />
                ) : (
                  <Dash />
                )}
              </Fact>
              {/* ⊕ `DEF-CUS-10054` (PO 2026-10-11) — SSN and Driver's license,
                  each masked to the last four, from the CUSTOMER's own record
                  (last four only on the wire). A company shows its Tax ID.
                  The contact's single "Government ID" stays as the fallback
                  where no customer holds the account. */}
              {detail.customer?.kind === "company" ? (
                <Fact label={t("customers.newAccount.field.taxId")}>
                  {maskedGovId(detail.customer?.identity?.tax_id_last4 ?? null) ?? <Dash />}
                </Fact>
              ) : detail.customer ? (
                <>
                  <Fact label={t("customers.serviceRequest.capture.ssn")}>
                    <span data-account-ssn="">
                      {maskedGovId(detail.customer.identity?.ssn_last4 ?? null) ?? <Dash />}
                    </span>
                  </Fact>
                  <Fact label={t("customers.serviceRequest.applicant.driversLicence")}>
                    <span data-account-licence="">
                      {maskedGovId(detail.customer.identity?.driving_licence_last4 ?? null) ?? <Dash />}
                    </span>
                  </Fact>
                </>
              ) : (
                <Fact label={t("customers.account.field.govId")}>
                  {govId ?? <Dash />}
                  {govId !== null && (
                    <span className="text-sm text-[color-mix(in_srgb,var(--color-text)_55%,transparent)]"> {t("customers.account.govIdLastFour")}</span>
                  )}
                </Fact>
              )}
            </FactList>
          )}
          {/* `DEF-CUS-9168` — the utility's OWN contact fields, read-only (slot
              `S21` for `contacts`), from the contact row this group shows.
              Renders NOTHING when the utility placed none here. */}
          {contact === null ? null : (
            <CustomFieldsView
              entity="contacts"
              screen="S21"
              values={contact.custom_data ?? {}}
              formatDate={(iso) => formatDate(iso, props.timeZone, props.dateFormat)}
              client={props.client}
            />
          )}
          {/* ⚠ **TWENTY-FOUR WORDS OF RATIONALE, GONE (B14 rule 33, PO
              2026-09-13).** It read *"This is one contact on one account. When
              the account is linked to a customer record, the customer's other
              accounts are listed further down."* — two sentences explaining the
              data model, over a group the drawing gives no sentence at all. The
              linkage is a FACT one group down, where CUSTOMER RECORD states it
              as `Customer ID` and `Linked accounts`. The key stays in all
              eleven catalogues; only this render goes. */}
        </Panel>

        {/* ⊕ **CO-APPLICANT — T4, PO 2026-09-23 (`DEF-CUS-6391`).** *"Store a
            second person on the account (name, email, phone), shown on the
            account page"*. The account's second `contacts` row (not primary),
            written by a sale and editable here through its own pencil. */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="co-applicant"
          title={t("customers.account.panel.coApplicant")}
          trailing={pencilFor("coApplicant")}
        >
          {/* ⊕ `DEF-CUS-9837` — and every CO-OWNER on the account (move-in's
              record, and New Connect's co-applicant since `DEF-CUS-9830`),
              listed under the contact the pencil edits, with the same three
              facts. Never an identifier — the read serves none. */}
          {coApplicant === null && (detail.co_owners ?? []).length === 0 ? (
            <p className="m-0 mb-3 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
              {t("customers.account.noCoApplicant")}
            </p>
          ) : (
            [
              ...(coApplicant === null
                ? []
                : [{ key: "contact", full_name: coApplicant.full_name, email: coApplicant.email, phone: coApplicant.phone }]),
              ...(detail.co_owners ?? []).map((row, index) => ({
                key: `co-owner-${index}`,
                full_name: row.full_name,
                email: row.email,
                phone: row.phone,
              })),
            ].map((person, index) => (
              <div key={person.key} className={index === 0 ? "" : "mt-4"} data-co-applicant-person={person.key}>
                <FactList>
                  <Fact label={t("customers.account.field.fullName")}>{person.full_name ?? <Dash />}</Fact>
                  <Fact label={t("customers.account.field.email")}>{person.email ?? <Dash />}</Fact>
                  <Fact label={t("customers.account.field.phone")}>{person.phone ?? <Dash />}</Fact>
                </FactList>
              </div>
            ))
          )}
        </Panel>

        {/* ⚠ **MAILING ADDRESS IS ITS OWN GROUP NOW (B14 rule 41).** It was a
            `PanelSubhead` INSIDE Customer; the blueprint draws it as the second
            group of the right column with its own heading and its own control,
            and the count only reconciles at eleven groups if it is one. The
            body below is the one this screen already shipped, moved rather than
            rewritten — including hard rule 8's reason for having no write door.
            ⚠ **`PanelSubhead` WAS THIS SITE'S ONLY CALLER AND NOW HAS NONE.**
            It is left in `accountDetailTabs.tsx` rather than deleted: the
            `.cus-subhead` heading it wraps is still drawn by hand in four other
            files, so the component is the thing that would stop them each
            growing their own — REPORTED rather than removed in a commit about
            this screen. */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="mailing-address"
          title={t("customers.account.field.mailingAddress")}
          trailing={pencilFor("mailing")}
        >
          {/* ⚠ **NO WRITE DOOR, AND THAT IS HARD RULE 8 RATHER THAN AN
              OVERSIGHT.** The mailing address is one of the rule's three named
              exceptions — where the BILL goes, which for a landlord is another
              building — and it has no edit endpoint of any kind. The control on
              the heading row is drawn and refuses, per `BR-SHL-025`. */}
          {mailing.length === 0 ? (
            // B2 §2: no mailing row means the service address IS the mailing
            // address — which is a statement, not an absence.
            <p className="m-0 mb-3 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t("customers.account.mailingSameAsService")}</p>
          ) : (
            /* The same grey scrolling box the METERS group carried, and gone
               for the same reason: this tab's groups are flat, under one accent
               rule each. A mailing address is one or two lines; it never needed
               a scroller. */
            <ul className="m-0 list-none p-0 text-base">
              {mailing.map((address) => (
                <li key={address.id} className="mb-1">
                  {addressLine(address)}
                </li>
              ))}
            </ul>
          )}
          {/* `DEF-CUS-9169` — the utility's OWN mailing-address fields,
              read-only (slot `S21` for `addresses`), from the row the pencil
              edits. Nothing at all when there is no mailing row, or when the
              utility placed no address field here. */}
          {mailing.length === 0 ? null : (
            <CustomFieldsView
              entity="addresses"
              screen="S21"
              values={mailing[0].custom_data ?? {}}
              formatDate={(iso) => formatDate(iso, props.timeZone, props.dateFormat)}
              client={props.client}
            />
          )}
        </Panel>

        {/* ── CUSTOMER RECORD ────────────────────────────────────────────
            ⚠ **`Customer ID` IS `customer_no` AND NEVER `customer.id`** — B14
            rule 31, *"no Databse ID on screen - that is a rule"* (PO
            2026-08-31). `account_row` has served `customer_no` since
            `CR-056` W3; the uuid beside it is a machine handle and stays off
            the screen.

            ONE hint at the foot rather than the two per-row helpers the
            blueprint draws: B14 rule 32 gives a section one sentence, and the
            Money group above already took this shape. The hint is written for
            the drawn case — an account with no customer record — because that
            is what the absence of both values means. */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="customer-record"
          title={t("customers.account.panel.customerRecord")}
          trailing={pencilFor("customerRecord")}
        >
          <FactList>
            <Fact label={t("customers.account.field.customerId")}>
              {detail.customer_no ?? <Dash />}
            </Fact>
            <Fact label={t("customers.account.field.linkedAccounts")}>
              {/* Record links (PO 2026-10-19): each linked account by its
                  number, the one on screen as plain text. `Customer ID` above
                  stays text — there is no customer page to open. */}
              {detail.customer === null || detail.customer === undefined || detail.customer.accounts.length === 0 ? (
                <Dash />
              ) : (
                <ul data-linked-accounts="" className="m-0 flex list-none flex-wrap gap-x-3 gap-y-1 p-0">
                  {detail.customer.accounts.map((linked) => (
                    <li key={linked.id}>
                      {linked.id === detail.id ? (
                        <span aria-current="page">{linked.account_no}</span>
                      ) : (
                        <InlineLinkTo to={tenantPath(accountDetailPath(linked.id))}>{linked.account_no}</InlineLinkTo>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Fact>
          </FactList>
          {detail.customer === null && (
            <p className="m-0 mb-3 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
              {t("customers.account.panel.customerRecordHint")}
            </p>
          )}
        </Panel>

        {/* ── BILLING PREFERENCES ────────────────────────────────────────
            Five drawn rows, and THREE of them are facts that already had a home
            on this screen: `Preferred language` came out of ACCOUNT SETUP and
            `Paperless` / `Text reminders` out of PORTAL ACCESS. All three are
            MOVED and none is copied — the 2026-09-10 grouping ruling's own note
            records what grouping removed, so a fact belongs to exactly one
            group.

            ⚠ **`Notification template` IS NOT ON THE WIRE AND IS DRAWN AS A
            STATED ABSENCE.** `account_detail_dict` serves `template_override_id`
            — a uuid, null on every account, and the BILL template's first leg
            rather than a notification one — and serves no resolved name at all.
            The blueprint draws *"Tenant default"*, which for every account
            today is what `billing.templates_service.resolve_for` would in fact
            answer; printing it from the front end would still be a value this
            screen never received, which is the fabricated-value family the
            negative assertions in this screen's suite exist for. `AwaitsCell`
            and not `NotRecorded`: the server CAN work this out
            (`bill_template_election_for_account`), it simply does not put it on
            this payload — a writer that exists, one step out of reach. */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="billing-preferences"
          title={t("customers.account.panel.billingPrefs")}
          /* ⚠ **THIS GROUP HAD NO CONTROL AT ALL AND ITS ENDPOINT WAS ALREADY
             SERVED** — PO 2026-09-13, driving the live screen: *"I cannot edit
             … Billing preferences"*. All four editable rows are
             `services.PATCH_FIELDS` columns. See `AccountPanelEdits.tsx`. */
          trailing={pencilFor("billingPrefs")}
        >
          <FactList>
            <Fact label={t("customers.accounts.col.autopay")}>
              {t(detail.autopay ? "customers.accounts.autopay.on" : "customers.accounts.autopay.off")}
            </Fact>
            <Fact label={t("customers.account.portal.paperless")}>
              {t(detail.paperless === true ? "customers.account.portal.on" : "customers.account.portal.off")}
            </Fact>
            <Fact label={t("customers.account.portal.sms")}>
              {t(detail.sms_reminders === true ? "customers.account.portal.on" : "customers.account.portal.off")}
            </Fact>
            <Fact label={t("customers.account.field.preferredLanguage")}>
              {detail.preferred_language ?? <Dash />}
            </Fact>
            <Fact label={t("customers.account.field.notificationTemplate")}>
              <AwaitsCell
                label={t("customers.account.notificationTemplateAbsent")}
                why={t("customers.account.notificationTemplateWhy")}
              />
            </Fact>
            {/* DEF-CUS-9788 — the PO recorded at move-in, printed on this
                account's bills; drawn when the account has one,
                LAST: the Accounts blueprint does not draw it, so it moves no drawn row. */}
            {detail.po_number ? (
              <Fact label={t("customers.moveIn.review.po")}>
                <span data-account-po="">{detail.po_number}</span>
              </Fact>
            ) : null}
          </FactList>
          <p className="m-0 mb-3 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {t("customers.account.panel.billingPrefsHint")}
          </p>
        </Panel>

        {/* The attribute set BR-CUS-012 confirms and this endpoint DOES serve. */}
        {/* `ACC-S1` — the one group on this screen whose endpoint exists. */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="account-setup"
          title={t("customers.account.panel.account")}
          trailing={pencilFor("account")}
        >
          <FactList>
            {/* ⚠ **THE ROW ORDER BELOW IS THE DRAWING'S, NOT THE ORDER THESE
                ROWS ARRIVED IN (B14 rule 41, 2026-09-13).** The blueprint draws
                ACCOUNT SETUP as Category · Sub-type · Account kind · Master
                account · Behaviour class · Tax exempt · Exemption reference ·
                Exemption expires · Bad address · Opened · Closed, and the
                screen had grown them in the order successive lanes added them.
                Row order is part of a design rather than a detail — the browser
                census checks it. */}
            {/* ⚠ **THE NAME COMES FROM THE CATALOGUE, NOT FROM A KEY (DEF-684).**
                `customers.accounts.category.*` only ever held BR-CUS-094's
                superseded four, so the three codes it added — and
                `builder_developer` most visibly — fell through to their raw slug.
                The fallback is still the CODE, never an invented label: that is how
                `government` would quietly start reading as "Municipal", which the
                ruling forbids by name. */}
            <Fact label={t("customers.accounts.filter.category")}>
              {accountCategoryName(detail.account_type, categories.all)}
            </Fact>
            {/* ⚠ **THIS PRINTED THE RAW ENUM `small_commercial` AT A CLERK
                (`DEF-CUS-5000`, 2026-09-12)** — B14 rule 31/32, and the
                Category cell one line up resolved its own catalogue correctly
                the whole time, so the two sat side by side saying
                `Commercial` and `small_commercial`.
                The label is the TENANT'S (`account_subtypes` is tenant-defined
                per BR-CUS-067), so it arrives on the wire beside the code —
                never from a front-end catalogue, which is `DEF-684`'s mistake
                for categories. The fallback is the CODE and never a guess, for
                `accountCategoryName`'s reason: inventing a label is how
                `government` quietly starts reading as "Municipal". */}
            <Fact label={t("customers.account.field.subtype")}>
              {detail.account_subtype_name ?? detail.account_subtype ?? <Dash />}
            </Fact>
            {/* ⚠ **SIX ROWS THE SERVER HAS ALWAYS ANSWERED AND THE SCREEN NEVER
                DREW** — part of the eleven the Accounts blueprint counted under
                the PO's ruling of 2026-09-10, *"we should have all these
                details captured on screen"*. Every one is on `AccountRow`, so
                the list has been able to read them all along.

                ⚠ **AND THREE OF THEM ARE RAW DATABASE VALUES ON THE WIRE**, so
                each resolves through the catalogue: B14 rule 31 says no
                database id is ever the visible value of a field, and the
                blueprint's own finding is that this screen already breaks it
                once — `account_subtype` reaches a clerk as `small_commercial`,
                underscore and all. That one is NOT fixed here (it is a
                different field with a different owner and its own row); these
                three do not join it. */}
            <Fact label={t("customers.accounts.filter.kind")}>
              {detail.kind === "master"
                ? t("customers.accounts.kind.master")
                : detail.kind === "regular"
                  ? t("customers.accounts.kind.regular")
                  : <Dash />}
            </Fact>
            {/* ⚠ THE ABSENCE HERE MEANS THREE DIFFERENT THINGS AND THE SENTENCE
                SAYS THE ONE THEY SHARE. `_master_ref` answers null for a
                standalone account, for a master itself, AND for the ambiguous
                two-masters-one-premises case it deliberately refuses to break
                — so this may say *not part of a group* and may never say
                *has no master*. The blueprint draws exactly that sentence. */}
            <Fact label={t("customers.account.field.masterAccount")}>
              {detail.master_account?.account_no ?? <Dash />}
            </Fact>
            <Fact label={t("customers.account.field.behaviourClass")}>
              {t(`customers.account.behaviourClass.${detail.status_behavior_class}`, {
                defaultValue: "",
              }) || <Dash />}
            </Fact>
            {/* `DEF-CUS-9774` — the three drawn rows read the per-tax
                CERTIFICATES as well as the blanket flag: ruling (A) leaves the
                flag false for a move-in's certificate (`AccountTaxExemption`). */}
            {(["exempt", "reference", "expires"] as const).map((part) => (
              <Fact
                key={part}
                label={t(
                  part === "exempt"
                    ? "customers.account.field.taxExempt"
                    : part === "reference"
                      ? "customers.account.field.exemptionRef"
                      : "customers.account.field.taxExemptExpires",
                )}
              >
                <ExemptionLines
                  facts={detail}
                  part={part}
                  none={<Dash />}
                  renderDate={(iso) => (
                    <DateCell value={iso} timeZone={props.timeZone} dateFormat={props.dateFormat} />
                  )}
                />
              </Fact>
            ))}
            {/* ⚠ **`Preferred language` LEFT THIS GROUP FOR BILLING
                PREFERENCES (B14 rule 41, 2026-09-13).** The blueprint draws it
                under BILLING PREFERENCES and draws ACCOUNT SETUP without it.
                MOVED and not copied: a fact rendered in two groups is the
                duplication the 2026-09-10 grouping ruling exists to delete —
                *"the name appeared three times on the old screen, the account
                number twice, the deposit twice"*. */}
            <Fact label={t("customers.account.field.badAddress")}>
              {detail.bad_address ? t("customers.account.yes") : t("customers.account.no")}
            </Fact>
            <Fact label={t("customers.account.field.opened")}>
              {detail.opened_at === null ? (
                <Dash />
              ) : (
                <DateCell
                  value={detail.opened_at}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              )}
            </Fact>
            <Fact label={t("customers.account.field.closed")}>
              {detail.closed_at === null ? (
                <Dash />
              ) : (
                <DateCell
                  value={detail.closed_at}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              )}
            </Fact>
            {/* `CR-185-BRC10` — a closed account's tie-back to the owner:
                pending until its final bill is sent, then posted. Drawn only
                when a clerk tied the balance back. */}
            {detail.balance_to_owner ? (
              <Fact label={t("customers.moveOut.done.balanceToOwner")}>
                <BalanceToOwnerState
                  state={detail.balance_to_owner}
                  currency={detail.currency ?? "USD"}
                  t={t}
                  testId="account-balance-to-owner"
                />
              </Fact>
            ) : null}

          </FactList>
          {/* EP-SHL-07 / US-SHL-016 — the utility's OWN fields, read-only, in
              display order (S21 is a `view` slot for `accounts`). Renders
              NOTHING when the utility has defined none, so the drawing match
              measured on 2026-09-13 is unchanged. ⚠ `DEF-CUS-9121`: this block
              was dropped by that day's regrouping with its imports left behind,
              and for nineteen days a value recorded in the New Account wizard
              was shown nowhere on the account. Values come from the ACCOUNT
              ROW, never a live join. */}
          <CustomFieldsView
            entity="accounts"
            screen="S21"
            values={detail.custom_data}
            formatDate={(iso) => formatDate(iso, props.timeZone, props.dateFormat)}
            client={props.client}
          />
          {/* ⚠ **THE GROUP HINT IS GONE, 2026-09-13 (B14 rule 33 sweep).** It read
            *"Returned payments and the bad-address flag are written by the
            returned-mail workflow, which is not built"*
            — RATIONALE, which is ZERO words on screen, and `ACC-02` draws no hint
            under this heading either. The fact it explained is already a ROW in
            the group above. Why it is so lives here and in the register. */}
        </Panel>

        {/* ── UNIT — WHAT THIS ACCOUNT IS ATTACHED TO (B14 rule 41) ──────
            DRAWN IN THE BLUEPRINT AND RENDERED BY NOTHING UNTIL 2026-09-13.
            `04-docs/05-modules/03-customers/blueprint/02-account-detail.md`
            line 473 heads it `UNIT — WHAT THIS ACCOUNT IS ATTACHED TO` with
            `✎Change unit`, and draws five rows: Unit · Premises ·
            Service address · Unit type · Plan the unit carries. The screen
            rendered thirteen groups and this was not one of them.

            ⚠ **THE DRAWN NOTE UNDER THIS GROUP IS RATIONALE AND IS ZERO WORDS
            ON SCREEN (B14 rule 33).** It reads *"the address is the building's
            and the plan is the unit's — both follow this row, which is why it
            has a control of its own"*. That is WHY the product works this way,
            so it lives here, in the code, and the register — never over a
            clerk's head. The facts it explains are the rows themselves.

            ⚠ **WHERE IT SITS.** The R5 frame draws the right column as
            ACCOUNT · UNIT · CUSTOMER · MAILING ADDRESS; the `ACC-02`
            empty-account frame — which `drawn/acc02-overview.json` transcribes
            and which the whole rest of this column already follows — draws
            CUSTOMER first and ACCOUNT SETUP fifth. Two frames of one blueprint
            disagree about the ORDER, so the shape they agree on is built: UNIT
            follows the ACCOUNT group. Nothing else moves.

            ⚠ **`Premises` AND `Service address` ARE TWO DIFFERENT ROWS AND NOT
            A REPEAT.** Hard rule 8: an address is stored on `premises` and a
            unit refines it by LABEL. `Premises` is the building's street line;
            `Service address` is that line plus the locality — the same pair the
            header composes, from the same two served halves, so an envelope and
            this group cannot disagree.

            ⚠ **NO `unit_id` AND NO `premises_id` IS EVER THE VISIBLE VALUE
            HERE** (B14 rule 31). Every row is a label the server resolved; the
            two ids travel only as LINK KEYS (record links, PO 2026-10-19):
            `unit_id` from `account_row`, and `service_premises_id` from
            `_unit_facts` — the unit's premises on a unit account, the anchor on
            a master one. (This note read "no unit_id and no premises_id reach
            this panel" until then; both were served all along.) */}
        <Panel
          as="section"
          tone="group"
          data-overview-group="unit"
          title={t("customers.account.panel.unit")}
          trailing={pencilFor("unit")}
        >
          <FactList>
            <Fact label={t("customers.account.field.unit")}>
              {detail.unit_label !== null && detail.unit_label !== "" ? (
                detail.unit_id !== null && detail.unit_id !== "" ? (
                  <InlineLinkTo to={tenantPath(unitDetailPath(detail.unit_id))}>{detail.unit_label}</InlineLinkTo>
                ) : (
                  detail.unit_label
                )
              ) : (
                <Dash />
              )}
            </Fact>
            <Fact label={t("customers.account.field.premises")}>
              {premiseAddress === null ? (
                <Dash />
              ) : detail.service_premises_id !== undefined &&
                detail.service_premises_id !== null &&
                detail.service_premises_id !== "" ? (
                <InlineLinkTo to={tenantPath(premisesDetailPath(detail.service_premises_id))}>
                  {premiseAddress}
                </InlineLinkTo>
              ) : (
                premiseAddress
              )}
            </Fact>
            {/* The building's line, then the locality — DATA joined by a comma,
                never a translated sentence assembled either side of a component
                (B8). `AccountIdentityChain` joins the same two halves with `·`
                for the header; this group draws the postal form the drawing
                gives it. */}
            <Fact label={t("customers.account.field.serviceAddress")}>
              {serviceAddress !== null ? serviceAddress : <Dash />}
            </Fact>
            {/* ⚠ **`unit_type` IS A RAW CODE ON THE WIRE** (`residential`,
                `common_area`, …) and B14 rule 32 keeps an internal string out of
                clerk-facing copy. It resolves through `metering.units.type.*` —
                the catalogue `UnitsListPage` and `PremisesDetailPage` already
                read, MOUNTED rather than copied (law 12). The fallback is the
                CODE and never an invented label, which is `DEF-684`'s rule. */}
            <Fact label={t("customers.account.field.unitType")}>
              {detail.unit_type !== null && detail.unit_type !== undefined && detail.unit_type !== "" ? (
                t(`metering.units.type.${detail.unit_type}`, { defaultValue: detail.unit_type })
              ) : (
                <Dash />
              )}
            </Fact>
            {/* ⚠ **THREE DIFFERENT ABSENCES ARRIVE AS ONE `null` HERE** and the
                PLAN group one column over already says which: the account names
                no unit, the unit stands on no plan, or the plan is no longer
                published. This row is the SUMMARY the drawing gives —
                `SCW-RES v1`, code and version — so it draws the dash and does
                not grow a second sentence about it (rule 32's budget). */}
            <Fact label={t("customers.account.field.unitPlan")}>
              {unitPlanSummary !== null ? unitPlanSummary : <Dash />}
            </Fact>
          </FactList>
        </Panel>

        {/* ⚠ **THIS WAS AN `ArrivesWith` SAYING THE PORTAL WAS OUT OF SCOPE,
            OVER AN ACCOUNT THAT HAS A LOGIN** (`DEF-CUS-4625`). PO verbatim:
            *"I have login portal for this account - portal access says…"*.
            The sentence was true the day it was written and rotted when
            CR-068 shipped the portal and CR-082 seeded it — hard-won law 2's
            mirror, a refusal outliving the thing it refused. It also claimed
            paperless and SMS were "columns that were never built"; both
            landed on 2026-08-31.
            **Nothing here is typed. Every line is read** — the Product
            Owner's ruling of the same evening on exactly this shape: derive
            the state, keep the specificity, and where a derivation cannot
            see something, print what it skipped beside what it checked. */}
        {/* ⚠ **`Paperless` AND `Text reminders` LEFT THIS GROUP FOR BILLING
            PREFERENCES, AND `Locked` BECAME A ROW OF ITS OWN (B14 rule 41).**
            The blueprint draws PORTAL ACCESS as exactly three rows — Sign-in,
            Locked, Last sign-in — and draws the two delivery elections under
            BILLING PREFERENCES. MOVED, not copied. */}
        <PortalAccessPanel
          detail={detail}
          t={t}
          timeZone={props.timeZone}
          dateFormat={props.dateFormat}
          pencil={pencilFor("portal")}
        />

        {/* CR-030 W3 · 3.4 — the same sentence, plus r10's `→ Update method`
            control, disabled WITH its reason (BR-SHL-025). */}
        <PaymentMethodPanel t={t} />

        {/* BR-CUS-023/057/058 — the one panel where every row has a different
            kind of absence, so each says which kind it is. */}
      </div>
    </div>
  );
}

// ⚠ **`ServiceAgreementsPanel` LEFT THIS SCREEN ON 2026-09-13 (B14 rule 41).**
//    It drew the account's SERVICE AGREEMENTS — what it is signed up for and
//    since when — at the top of the METERS tab, and `ACC-T07` draws one table
//    on that tab and nothing else. The blueprint says where the fact belongs,
//    in terms: *"The meters belong to the unit, not to the account … The
//    services this account holds are a separate fact and live in the Service
//    group on Overview."*
//
//    **NOTHING IS LOST AND NOTHING IS DUPLICATED.** Overview's own `service`
//    group draws `SERVICE · STARTED · ENDED` off the same `detail.services`
//    (`acc02-overview.json`, slug `service`), which is the PO's 2026-09-10
//    ruling that a fact sits under ONE named group — the ruling whose note
//    records what grouping REMOVED: *"the name appeared three times on the old
//    screen, the account number twice, the deposit twice."* This was the
//    services appearing twice.


/**
 * The three columns the blueprint draws — `SERVICE · STARTED · ENDED`, one row
 * per service agreement.
 *
 * ⚠ **IT IS A COMPONENT AND NOT A COPY BECAUSE IT NOW HAS TWO HOSTS**: the
 * Overview's `SERVICE` group and the Meters tab's `Services on this account`
 * panel. B14 rule 36 — one component, one visual decision — and the concrete
 * risk it removes is the one `DEF-3483` already cost once on this very table:
 * two places drawing a service two different ways, which the PO found by
 * looking at the screen.
 *
 * ⚠ **NO `DataTable`, DELIBERATELY.** The shared table brings a toolbar and a
 * pagination footer, and the blueprint's SERVICE group draws neither a pager
 * nor a row count over a list that is one or two rows long.
 */
function ServiceAgreementsTable(props: {
  detail: AccountDetail;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
}) {
  const { detail, t } = props;
  return (
    <>
        {detail.service_agreements.length === 0 ? (
          <p className="m-0 mb-3 text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">{t("customers.account.serviceAgreementsEmpty")}</p>
        ) : (
          <PlainTable>
            <thead>
              <tr>
                <th>{t("customers.accounts.col.services")}</th>
                <th>{t("customers.account.col.startedOn")}</th>
                <th>{t("customers.account.col.endedOn")}</th>
              </tr>
            </thead>
            <tbody>
              {detail.service_agreements.map((agreement: AccountServiceAgreement) => (
                <tr key={agreement.id}>
                  <td>
                    {/* DEF-3483 (PO 2026-09-03): *"Services on this account - I
                        will show name of the service inform of similar to this
                        - E Electric"*. This cell drew `ServiceTags`, which is
                        the bare coloured square — so this panel showed six
                        letters (W E S T St F) and the Meters table below it
                        showed a square AND the word. The PO pointed at the
                        second one and asked for the first to match, so this
                        reuses that exact cell rather than growing a third way
                        of drawing a service. */}
                    {agreement.service === null ? (
                      <Dash />
                    ) : (
                      <MeterServiceCell code={agreement.service} t={t} />
                    )}
                  </td>
                  <td>
                    {agreement.started_on !== null ? (
                      <DateCell
                        value={agreement.started_on}
                        timeZone={props.timeZone}
                        dateFormat={props.dateFormat}
                      />
                    ) : (
                      <Dash />
                    )}
                  </td>
                  <td>
                    {agreement.ended_on !== null ? (
                      <DateCell
                        value={agreement.ended_on}
                        timeZone={props.timeZone}
                        dateFormat={props.dateFormat}
                      />
                    ) : (
                      <Dash>{t("customers.account.agreementOpen")}</Dash>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
        )}
        {/* `DEF-CUS-9170` — the utility's OWN service-agreement fields,
            read-only (slot `S21` for `service_agreements`): one block per
            agreement, headed by its service, because each agreement keeps its
            own answers. Each block renders NOTHING when the utility placed no
            agreement field here, so the group is unchanged for them. */}
        {detail.service_agreements.map((agreement: AccountServiceAgreement) => (
          <CustomFieldsView
            entity="service_agreements"
            screen="S21"
            key={agreement.id}
            values={agreement.custom_data ?? {}}
            heading={
              agreement.service === null
                ? undefined
                : t("customFields.sectionHeading", {
                    tenant: t(`rating.service.${agreement.service}`, {
                      defaultValue: agreement.service,
                    }),
                  })
            }
            formatDate={(iso) => formatDate(iso, props.timeZone, props.dateFormat)}
            client={props.client}
          />
        ))}
    </>
  );
}

/**
 * S21's *Portal access* panel — DERIVED, never declared (`DEF-CUS-4625`).
 *
 * Four facts, each read rather than written down:
 *
 *   * **whether anybody on this account can sign in** — `portal_credential`
 *     rows reached through `customer_accounts`, because a login belongs to a
 *     CUSTOMER and an account can be jointly held;
 *   * **when the portal was last used** — the latest `portal_session` stamp
 *     across those logins. `null` means NEVER, and the screen says never; the
 *     sentence this replaced said no date was recorded, which was a claim
 *     about the schema and is now false;
 *   * **the delivery election** — `accounts.paperless` and
 *     `accounts.sms_reminders`, both real columns since 2026-08-31;
 *   * **anything that could not be read**, with a number beside it, so a
 *     blind spot never reads as an empty one.
 *
 * ⚠ **PAPERLESS DOES NOT TURN PRINT OFF, AND THE PANEL SAYS SO.** `BR-BIL-036`
 * makes print the floor — every bill is printed whatever else is elected — so
 * a panel that showed *Paperless: on* and stopped would invite a clerk to tell
 * a customer their paper bill had stopped. That is the same ruling as *a
 * message that will not be sent must say so on screen*, one channel over: what
 * DID go, and what did not.
 */
function PortalAccessPanel(props: {
  detail: AccountDetail;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  /** `ACC-S15` — refused here: a customer enrols themselves, and `paperless`
   *  is edited on the Account form instead. */
  pencil?: ReactNode;
}) {
  const { t, detail } = props;
  const portal = detail.portal_access;
  return (
    <Panel
      as="section"
      tone="group"
      data-overview-group="portal-access"
      title={t("customers.account.panel.portal")}
      trailing={props.pencil}
    >
      <FactList>
        <Fact label={t("customers.account.portal.signIn")}>
          {portal === undefined || portal.logins === null ? (
            <Dash>{t("customers.account.portal.unreadable")}</Dash>
          ) : portal.logins === 0 ? (
            <Dash>{t("customers.account.portal.noLogin")}</Dash>
          ) : (
            t("customers.account.portal.logins", { count: portal.logins })
          )}
        </Fact>
        {/* ⚠ **`Locked` WAS A QUALIFIER ON THE SIGN-IN CELL AND IS A ROW OF ITS
            OWN NOW (B14 rule 41).** The blueprint draws PORTAL ACCESS as three
            rows and draws `Locked 0` as the second, so a zero is a real answer
            here rather than a reason to hide the line — which is also what
            makes it readable: a clerk asking *why can they not get in* now has
            a row to look at instead of an absent qualifier. `null` still means
            the walk could not read it, and says so. */}
        <Fact label={t("customers.account.field.locked")}>
          {portal === undefined || portal.locked === null ? (
            <Dash>{t("customers.account.portal.unreadable")}</Dash>
          ) : (
            portal.locked
          )}
        </Fact>
        <Fact label={t("customers.account.portal.lastSignIn")}>
          {portal === undefined || portal.unreadable.includes("last_sign_in") ? (
            <Dash>{t("customers.account.portal.unreadable")}</Dash>
          ) : portal.last_sign_in === null ? (
            <Dash>{t("customers.account.portal.never")}</Dash>
          ) : (
            <DateCell
              value={portal.last_sign_in}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          )}
        </Fact>
      </FactList>
      {/* ⚠ **`Bills are always printed as well.` WAS RENDERED HERE AND IS GONE
          (PO 2026-09-13, B14 rule 33).** Two things were wrong with it. It is
          RATIONALE — why the product behaves as it does — which the rule puts
          at ZERO words on screen. And it had been ORPHANED since the
          eleven-group rework moved `Paperless` and `Text reminders` out of this
          group into BILLING PREFERENCES, so it explained two rows that are no
          longer beside it. The fact it carried is `BR-BIL-036`: print is the
          FLOOR, so a paperless election says what the customer gets IN ADDITION
          and never that paper has stopped. The key stays in all eleven
          catalogues for whoever draws that fact next to the election itself. */}
    </Panel>
  );
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-CUS-008@a2e1d59 (story+rules snapshot — EP-CUS-03 lead story; co-packets US-CUS-009/010/011 same epic · customers 02-business-rules@f125a9c)
// generated: 2026-08-11 by story-coder (W2 customers FRONTEND lane 2 — S21, the screen `GET /accounts/{id}` shipped without) · AMENDED 2026-08-11 by story-coder (W2 customers FRONTEND lane 3 — S19/S20 landed, so Move-out and a new Move-in are LIVE navigations gated by the account's own state) · AMENDED 2026-08-11 by story-coder (W3 billing FRONTEND lane — the Bills tab stops being an arrives-with panel and embeds billing's S30 list scoped by `f.account_id`) · AMENDED 2026-08-15 by story-coder (tenant custom-fields lane)
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 670 passed / 160 todo across 49 files✔ (622 passed / 148 todo across 47 files was the pre-lane baseline — the suite grew by 48 passing + 12 todo and nothing was dropped) · vite build✔ · run_gates 14 PASS · 0 FAIL · 1 SKIP✔ (G13 unwired-props, G14 prototype-conformance and G15 i18n-parity included; 5 locales × 2328 keys, identical sets)
// exceptions: E2 [2026-08-11 W3 billing lane] the BILLS tab is live: it renders `features/billing`'s own S30 table with `f.account_id`, which is 11b §2.6's account scoping of `GET /invoices` — customers keeps no copy of a billing row (BR-CUS-034) and there is only one implementation of BR-BIL-022's draft rule and the derived past-due state. The endpoint is contracted (11b §2.8) and unserved; the embedded table reports THAT in its own A18 §4 state rather than this page asserting it. the superseded string `customers.account.arrives.bills` ("Bills come from issued invoices, which billing owns and has not built…") is DELETED from all five catalogues rather than left behind, and `…arrives.recentBills` is rewritten to say the Bills tab now exists — the string changes with the fact (hard-won law 1) · E3 the ONE primary slot carries "Activate account" (BR-CUS-018), not the prototype's "Record payment": payments do not exist, and a permanently dead button in the primary slot teaches the wrong thing about the page. Record payment moves to the secondary rail, disabled WITH its reason · E3 the prototype's seven-item secondary rail (Send statement · Print bill · Issue credit · Change plan · Disconnect notice · Payment plan · Add note) renders as ONE arrives-with panel naming all seven, not as seven disabled buttons: none has an endpoint, and seven dead controls are seven promises (the premises-detail Accounts-tab precedent the S21 brief points at) · E3 the Plan block renders the SERVER's own refusal and its rule id (`plan_snapshot_unavailable`), and the UNIT's plan is NOT substituted (BR-CUS-010 — the two diverge at the first override) · E3 Balance renders with the "cached, nothing writes it yet" qualifier; its DUE DATE, the aging state and Last activity are awaiting-with-reason, never a dash or a date · E3 deposit interest and the credit tier render as not-recorded with BR-CUS-057/BR-CUS-058, never $0.00 or "A" · E3 five of the nine tabs (Bills · Payments · Usage · Adjustments · Documents · Notes) are the honest arrives-with state — billing/payments own the first four and `account_notes`/`account_documents` are PROPOSED-SCHEMA with no endpoint; an empty table would assert "none" · E3 there is no "all accounts for this customer" chip (BR-CUS-054): `customers`/`customer_accounts` have no tables, so the linked set cannot be listed and is named in the awaiting panel instead · E2 [2026-08-11 lane 3] Move-out is a LIVE navigation to S20 now that the screen exists, and a Move-in action joins it for a CLOSED account (the endpoint takes the OUTGOING account's unit). Both stay GUARDED by state because the SERVER is: only an occupant can move out (BR-CUS-030) and a move-in onto a still-held unit is refused 409 (BR-CUS-017); the stale "is not built" string was rewritten with the fact (hard-won law 1). Superseded, kept for the record: · E3 Move-out is disabled with its reason rather than flipping a status: `POST /accounts/{id}/move-out` landed from the backend lane ON THE DAY this screen was written, so the reason was CORRECTED before shipping — it is now "S20 is its own guided page and the server needs a move-out date, a final read and the BR-CUS-031 handoff a bare button cannot collect", not the stale "no endpoint exists". Hard-won law 1: the string had to change with the fact · E4 the Audit tab reuses metering's `AuditTab`, which links to the S61 viewer filtered by entity — one audit surface for the product (US-AUD-005 TC-3/TC-4), so masking and window rules cannot diverge per module · E4 DOB renders through the shared DateCell: US-CUS-009 TC-2 shows the DOB in full while the BR-CUS-045 row says "DOB and ID render masked" — the government id IS masked (the server stores four digits and nothing more), and the DOB divergence between the story's rule row and its own test case is REPORTED, not resolved here · E4 the tenant TZ + date format arrive as props with the same seed fallbacks every other detail uses, until US-SHL-013's formatting service lands
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
// AMENDED 2026-08-24 by the CR-030 W3 lane (B18 §5.2 · tasks 3.1 · 3.3 · 3.4 ·
// 3.5 · 3.6 · 3.7 · 3.9 · 3.10 · 3.11 — the ACC-01 conformance pass):
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 2251 passed / 189 todo across 132 files✔ (2234 passed / 189 todo across 132 files was the pre-lane baseline — this lane adds 17 passing and drops none) · vite build✔ · routeBUtilities.test.ts 9/9✔ (the two new files are registered in styles/route-b-migrated.txt) · run_gates 26 PASS · 14 FAIL · 1 SKIP — byte-identical to the pre-lane baseline, and every number this lane could move held: G13 PASS, G14 186 (unchanged — every new heading is a string r10's own ACC-01 markup draws), G15 unchanged in all ten catalogues (52 new keys × 11, none left in English), G18 102 orphans (unchanged), G25 6, G28 77, G29/G31/G37/G40 PASS, G38 74 untracked at its baseline
// exceptions: E2 the ONE primary is Record payment, not Activate — see the amended paragraph in the header · E3 the header's metric block draws THREE columns (r10's) and the AGEING fact this screen used to show is gone, with its three catalogue keys; B18 §5.1.2 puts ageing on the S17 row · E3 the metric block renders BELOW the shared PageHeader rather than inside the header card as r10 draws it: `components/PageHeader.tsx` owns that card and belongs to another lane · E2 [2026-08-24 CR-030 W3 · 3.2] the r10 ICON RAIL IS BUILT — `AccountIconRail.tsx`, BR-SHL-045, closing B18's D2. This entry read "is NOT built — B18 D2, blocked on the PO — so the rail this deployment already had is kept whole rather than deleted before its replacement is ruled; deleting it would make four live features unreachable", and that is exactly what happened: the seven worded buttons were REPLACED, not deleted, and all three live ones (Change plan · Payment plan · Add note) keep the guards they had. Remaining divergences, both stated rather than folded away: the rail renders BELOW the metric block instead of inside r10's header card (same reason as the entry before this one), and Activate + Move-in stay as WORDED secondaries because r10 has no glyph for either and BR-SHL-045's seven are r10's seven exactly · E3 the Usage tab is untouched (B18 task 3.8, blocked on D3) and its arrives-with sentence is now STALE — it blames a reads filter that CR-028 shipped, and it cites DEF-475, which is CLOSED. REPORTED rather than edited: re-pointing it needs an id for D3 that no register holds, and 12-governance is outside this lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
