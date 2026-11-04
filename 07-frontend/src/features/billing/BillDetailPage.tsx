// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-026 (S30 bill detail: the pinned document, the A19 summary
//           box, every stamped line with its GL, the run/correction linkage,
//           delivery history and audit) ·
//           US-BIL-007 (bill anatomy — the line table this screen renders) ·
//           US-BIL-027 (void: state-gated, consequence-messaged, server-side)
//           Screens: S30 (entered from the All-bills row and from `/billing/bills/{id}`)
// Rules:    BR-BIL-004 (the detail is READ-ONLY on an issued bill — mutation is
//           correction or void, each its own gated flow) · BR-BIL-009 (a void
//           shows its plain-language consequence BEFORE confirm, computed by
//           the server from the reversal preview) · BR-BIL-010 (a line shows
//           the STAMPED GL — issue-time truth, never re-resolved against
//           today's mapping) · BR-BIL-063 (every bill carries a number, drafts included) ·
//           BR-BIL-024 (the due date is derived at issue) · BR-BIL-026 (the
//           document panel renders the PINNED template version, forever) ·
//           BR-BIL-030 (the bill is LOCKED at issue — a complete document
//           instance is stamped and the reprint renders that instance) ·
//           BR-BIL-031 (payload_version and template_version are two axes) ·
//           BR-BIL-016 (delivery is a QUEUE — per channel, per bill) ·
//           BR-CUS-040 (a reprint re-renders the ISSUED document; it never
//           recomputes) · BR-SHL-020 (plain-language absence) · BR-SHL-023 (one
//           money path) · BR-SHL-025 (a forbidden control renders disabled WITH
//           its reason) · BR-SHL-034 (one date formatter) · BR-SHL-044 (one
//           page header, exactly one primary action)
// ───────────────────────────────────────────────────────
// S30 detail — a bill's two truths on one screen: the CUSTOMER DOCUMENT and the
// RECORD.
//
// THE DOCUMENT IS NOT RENDERED HERE, AND THAT IS THE RULE, NOT A SHORTCUT.
// BR-BIL-030: at issue the run stamps a complete document instance into
// `invoices.bill_payload` — tenant identity, customer name, service address,
// premises/unit, account number, every meter with its prior and current read,
// every line grouped by service, taxes, totals and messages. BR-CUS-040 and
// BR-BIL-026 then say a reprint renders THAT instance through THAT pinned
// template version, forever: a bill reprinted in December shows the name and
// the address as they stood in July, not as they stand today. Sarah marries;
// the apartment is renumbered; the plan is edited — every one of those is a
// legitimate change to live data and every one of them silently rewrites
// history if the reprint re-joins today's rows.
//
// So the render belongs to the server (`GET /invoices/{id}/document`, 11b §2.8)
// and this screen embeds it. There is no `bill_payload` parser in this module:
// no signed document names that payload's JSON keys, stage 6
// (assemble-document, BR-BIL-037) is being authored in `apps/billing/` right
// now, and a second guess at one schema from a second lane is how two copies of
// a generated artifact drifted in a day (hard-won law 5).
//
// WHAT THIS SCREEN DOES RENDER, from `GET /invoices/{id}`: every
// `invoice_lines` row with its quantity, explicit unit, unit price, amount,
// taxable flag, STAMPED GL and tariff version; the A19 summary box; the run and
// correction linkage; and the three gated actions. Everything the endpoint
// cannot answer is named where its value would be, never drawn as an empty
// table (which asserts "none") or a zero (which asserts "nothing").
//
// ⚠ **THIS PARAGRAPH SAID "AND THE ENDPOINT IS NOT SERVED YET" UNTIL
// 2026-09-14, AND IT HAD STOPPED BEING TRUE LONG BEFORE THAT.** `GET
// /invoices/{id}` answers **200** — measured over real HTTP on this branch for
// `BL-2608-000058`, with `customer_name`, `cycle_label`, `charges_by_service`,
// `taxes_by_authority` and the delivery queue on it — and every screenshot in
// `CR-101-BRC03`'s walk is of a bill this route served. A comment claiming a
// state of the product that is no longer true is hard-won law 1 in its purest
// form, running backwards, and it is the second one found in this module in a
// week (`BillsListPage.tsx:42` is the other).
//
// **WHAT STANDS IS THE 404's SHAPE, WHICH IS WHY THE REST IS KEPT.** A 404 here
// is genuinely AMBIGUOUS — HR-1 makes an unknown id and a cross-tenant id one
// answer (US-BIL-026 TC-6 requires exactly that) — so the failure names both
// causes instead of picking one. It no longer names a third, because the route
// is mounted. That is still why the LIST, whose 404 on a COLLECTION route is
// unambiguous, is the screen allowed to say "this API serves no bills list".
import { Fragment, useState } from "react";
import type { ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";

import { apiHref } from "@/api/apiHref";
import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getAccountDetail, getAccountOpenBills, getInvoice } from "@/api/endpoints";
import type {
  AccountDetail,
  InvoiceAdjustmentRef,
  InvoiceChargesByService,
  InvoiceCreditNoteRef,
  InvoiceDetail,
  InvoiceLineRow,
  OpenBillPosition,
} from "@/api/endpoints";
import { getBillDocument } from "@/api/billingOpsEndpoints";
import type { RenderedBillDocument } from "@/api/billingOpsEndpoints";
import { ButtonAnchor, ButtonLink } from "@/components/Button";
import { DateCell } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { MoneyCell, formatMoney, formatRate } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { DayShareNote } from "@/components/DayShareNote";
import { SizeBreakdown } from "@/components/SizeBreakdown";
import type { PageHeaderTab } from "@/components/PageHeader";
import { Kicker } from "@/components/TextBits";
import { RowActionsMore, RowMenuAction, RowMenuAnchor } from "@/components/RowActions";
import { CopyIcon, PrinterIcon, TrashIcon } from "@/components/icons";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { StatusPill } from "@/components/StatusPill";
import { UnitCell } from "@/components/UnitCell";
import { InlineLinkTo, PlainTable } from "@/components/Surfaces";
import { assetDetailPath } from "@/features/assets/assetsShared";
import { Panel } from "@/components/Panel";
import { AuditTab } from "@/features/metering/PremisesDetailPage";
import {
  AwaitsCell,
  NotRecorded,
  accountDetailPath,
  primaryContact,
} from "@/features/customers/customersShared";
// US-PAY-016 — the returned-mail rule, imported rather than re-implemented.
// The single mark lives on THIS screen (S30's delivery rows) and the bulk mark
// on payments' summary (S35); a rule written in two places is a rule enforced
// in one.
import {
  MarkReturnedModal,
  ReturnedMailOutcome,
  markReturnedRefusal,
} from "@/features/payments/returnedMail";
import type { MarkReturnedOutcome } from "@/features/payments/returnedMail";
import {
  CELL_FULL,
  Dash,
  Fact,
  FactList,
  GuardedButton,
  detailTabFrom,
  isDenied,
  useRegional,
  useAccessCell,
} from "@/features/metering/meteringShared";
// `DetailTab` was imported here and used by nothing — an eslint error already
// standing at `cab896fa`, in a file this lane owns. Removed rather than left,
// because a red a lane walks past is how a true one acquires the colouring of a
// known one (hard-won law 7, habit 1).
import type { RegionalProps } from "@/features/metering/meteringShared";
import { ArrivesWith, apiErrorText, isPermissionDenied } from "@/features/tenancy/settingsShared";
import type { Translator } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import {
  BILLING_PERMISSION,
  BILLING_ROUTE,
  BillNumber,
  DASHBOARD_ROUTE,
  LINE_GROUP_DISCOUNTS,
  LINE_GROUP_OTHER,
  billDetailPath,
  billStatusLabel,
  billStatusTone,
  billTypeLabel,
  detailNotFound,
  groupLinesByService,
  isLockedBill,
} from "./billingShared";
import { billDocumentPath, fixABillPath } from "./billingOpsShared";
// DEF-2716 — the run row is a LINK now, and the route it needs is defined once,
// beside `BILL_RUN_ROUTE` and `RUN_PARAM` in the wizard's own shared module.
// The run's NUMBER comes from the run itself, through the wizard's own query
// key so the two screens share one cached answer.
import { billRunPath } from "./billRunShared";
import { billRunDetailKey, getBillRun } from "./billRunEndpoints";
import { billChainKey, getInvoiceChain } from "./billChainEndpoints";
import type { ChainActor, InvoiceChain } from "./billChainEndpoints";
import { billDocumentKey } from "./BillDocumentPage";
import { DraftDecision } from "./oneTimeBill/DraftDecision";
import { useToast } from "@/components/Toast";
// `CR-105-BRC03` — the Usage group reads the ACC-01 Usage tab's own endpoint
// through its OWN key and its OWN types. Re-typing the payload here would be a
// second contract for one route (hard-won law 5), and re-keying it would make
// the account screen pay for a read this one just made.
import {
  accountUsageKey,
  getAccountUsage,
} from "@/features/customers/AccountUsageTab";
import type { UsagePayload, UsageSeries } from "@/features/customers/AccountUsageTab";

/** The window the Usage group's AVERAGE is taken over. See the query. */
const USAGE_MONTHS = 12;

// ── Pure pieces (provable without a browser or a network) ──────────────────

export const billDetailQueryKey = (id: string) => ["invoices", "detail", id] as const;

/**
 * US-BIL-026 §1: the document, the record, the chain, and who touched it.
 *
 * ⚠ **`sent` IS THE THIRD OF FIVE SINCE 2026-09-14 (`CR-101-BRC03`), AND THE
 * POSITION IS THE DRAWING'S.** The Billing blueprint's entry 02.5 splits
 * *Delivery* — until now the last panel of the FIRST tab, below four panels of
 * provenance — into a tab of its own, and draws it between *Charges* and
 * *Corrections*: *"did they get it"* is a top-three question and it was four
 * scrolls down. `…?tab=sent` used to fall back to Document, which was
 * `detailTabFrom`'s correct behaviour for an address that did not exist.
 */
export const BILL_TAB_IDS = ["document", "lines", "sent", "chain", "audit"] as const;
export const TAB_PARAM = "tab";

/**
 * The counts beside two of the five tab words (`PageHeaderTab.count`).
 *
 * The blueprint's legend 7 gives the reason in one line — a count so *"a clerk
 * never clicks to find nothing"* — and the two tabs that carry one are the two
 * a clerk clicks speculatively.
 */
export interface BillTabCounts {
  /**
   * How many rows the delivery queue holds. **`null`, never `0`, while the
   * queue itself is not served**: BR-BIL-016's `deliveries` is nullable for
   * exactly this reason, and a `0` would claim the bill was never sent.
   */
  sent: number | null;
  /**
   * How many correction DOCUMENTS stand against this bill — its credit notes,
   * plus the replacement if one was issued. **`0` is a real answer here and is
   * drawn as one** (`Corrections ₀`): an uncorrected bill has nothing against
   * it, and saying so is the point of the count.
   */
  chain: number;
}

export function billTabs(t: Translator, counts?: BillTabCounts): PageHeaderTab[] {
  return BILL_TAB_IDS.map((id) => {
    const label = t(`billing.bill.tab.${id}`);
    if (counts === undefined) {
      return { id, label };
    }
    if (id === "sent") {
      return counts.sent === null ? { id, label } : { id, label, count: counts.sent };
    }
    if (id === "chain") {
      return { id, label, count: counts.chain };
    }
    return { id, label };
  });
}

/**
 * How many correction documents stand against this bill — the `chain` count
 * above, and the same question the Corrections tab answers.
 *
 * Read off the DETAIL rather than off `GET /invoices/{id}/chain`, deliberately:
 * the tab strip renders before that second read resolves, and a count that
 * appeared a moment after the word would be worse than none. Both sides read
 * the same column (`invoices.corrects_invoice_id`, PO 2026-08-12), so they
 * cannot disagree — one is simply richer.
 */
export function correctionDocumentCount(detail: InvoiceDetail): number {
  return detail.credit_notes.length + (detail.corrected_by_invoice_id !== null ? 1 : 0);
}

/**
 * The H1. A bill's name IS its number, and every bill has one from the moment
 * it is drafted (BR-BIL-063, PO 2026-08-11). The fallback stays for the served
 * null: it names the period rather than printing an empty heading or inventing
 * "Bill —".
 */
export function billHeadline(detail: InvoiceDetail, t: Translator): string {
  if (detail.invoice_no !== null && detail.invoice_no !== "") {
    return detail.invoice_no;
  }
  return t("billing.bill.draftHeadline");
}

// ── The screen ─────────────────────────────────────────────────────────────

export interface BillDetailPageProps extends RegionalProps {
  client?: ApiClient; // test seam — screens never build their own transport
}

export function BillDetailPage(props: BillDetailPageProps) {
  const { t } = useTranslation();
  const translate: Translator = (key, params) => t(key, params);
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const { timeZone, dateFormat } = useRegional(props);

  const invoiceId = params.invoiceId ?? "";

  const cell = useAccessCell(BILLING_PERMISSION, client);
  const writeBlockedReason =
    cell === CELL_FULL || cell === null ? null : t("billing.rbac.readOnly");
  const queryClient = useQueryClient();
  const toast = useToast();

  const detailQuery = useQuery({
    queryKey: billDetailQueryKey(invoiceId),
    queryFn: () => getInvoice(invoiceId, client),
    enabled: invoiceId !== "",
    // A missing route is not a flaky network — retrying only delays the answer.
    retry: false,
  });

  // ⚠ **CR-053 tasks 1 and 3 — THE BILL ITSELF, FETCHED ONCE FOR TWO CONSUMERS.**
  //
  // The header's *Print bill* control and the Document tab's body are the same
  // fact asked twice: does this bill have a printable page, and where is it?
  // `GET /invoices/{id}/document` answers both — it carries `pdf_url`, which is
  // the route the print control opens and the frame below embeds — so it is
  // read HERE and passed down, rather than fetched in the tab and guessed at in
  // the header.
  //
  // **IT IS NOT ENABLED ON A BILL THAT CANNOT HAVE ONE.** `document_url` is
  // null exactly while no template version is pinned (a draft), and the route
  // answers 422 for that bill with the renderer's own sentence. Asking anyway
  // would spend a request to be told what the row already said.
  const documentUrl = detailQuery.data?.document_url ?? null;
  const documentQuery = useQuery({
    queryKey: billDocumentKey(invoiceId),
    queryFn: () => getBillDocument(invoiceId, client),
    enabled: invoiceId !== "" && documentUrl !== null,
    retry: false,
  });

  // ⚠ **THE ACCOUNT, FOR THE TWO THINGS THE INVOICE DOES NOT CARRY AND CANNOT
  // (`CR-101-BRC03`).** The blueprint's header names the customer AND the
  // SERVICE ADDRESS, and its Sent tab names how this customer hears from us.
  // `customer_name` is on the invoice; the address is not and must not be —
  // **hard rule 8: an address is stored on `premises` and nowhere else**, and
  // every other entity DERIVES it by walking there. `GET /accounts/{id}` is
  // that walk, already done, and it carries `premise_address`,
  // `premise_locality`, `unit_label`, `paperless` and the contacts in one read.
  //
  // The key is the one `AccountDetailPage` uses, so the two screens share one
  // cached answer rather than asking twice — the same choice the document read
  // above makes for the same reason.
  const accountQuery = useQuery({
    queryKey: ["accounts", "detail", detailQuery.data?.account_id ?? ""],
    queryFn: () => getAccountDetail(detailQuery.data?.account_id ?? "", client),
    enabled: detailQuery.data !== undefined,
    retry: false,
  });

  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **THE TWO LIVE READS THE BLUEPRINT ADDS, AND THEY ARE THE ONLY TWO
  // (`CR-105-BRC03`).** §09 of the Billing document counts them itself: *"Only
  // 'Owed today', the usage AVERAGE and the paperless election need a read this
  // module does not have today"* — and the paperless election is the Sent tab's,
  // already read off `GET /accounts/{id}` above.
  // ══════════════════════════════════════════════════════════════════════════
  //
  // **NEITHER IS A NEW ENDPOINT.** `GET /accounts/{id}/open-bills` has served
  // the account's whole open position since 2026-09-01 (CR-059 CS-4) and the
  // payments picker reads it; `GET /accounts/{id}/usage` is the ACC-01 Usage
  // tab's own read. Both are asked through THE SAME query keys those screens
  // use, so a clerk who opens the account afterwards pays for neither again.
  //
  // ⚠ **EVERY OTHER FIGURE ON THIS SCREEN IS AS-AT-ISSUE AND THESE TWO ARE
  // NOT**, which is the whole reason they are worth a request: BR-BIL-030
  // freezes the bill at issue, so nothing on it could answer *what do they owe
  // now* or *is this month unusual*. The screen says which is which in words
  // rather than leaving a reader to infer it from two figures that disagree.
  const openBillsQuery = useQuery({
    queryKey: ["accounts", "open-bills", detailQuery.data?.account_id ?? ""],
    queryFn: () => getAccountOpenBills(detailQuery.data?.account_id ?? "", client),
    enabled: detailQuery.data !== undefined,
    retry: false,
  });
  // TWELVE months, not the endpoint's 24-month default: the drawn column is
  // *AVERAGE* against *THIS PERIOD*, and a two-year mean answers a different
  // question than the one a clerk holding this bill is asking.
  const usageQuery = useQuery({
    queryKey: accountUsageKey(detailQuery.data?.account_id ?? "", USAGE_MONTHS),
    queryFn: () => getAccountUsage(detailQuery.data?.account_id ?? "", USAGE_MONTHS, client),
    enabled: detailQuery.data !== undefined,
    retry: false,
  });

  function selectTab(id: string): void {
    const next = new URLSearchParams(searchParams);
    next.set(TAB_PARAM, id);
    setSearchParams(next, { replace: true });
  }

  if (isDenied(cell)) {
    // BR-SHL-003 / A18 §6: a surface this role cannot reach is not drawn.
    return (
      <PermissionDenied
        helper={t("billing.denied")}
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
          helper={t("billing.denied")}
          onBack={() => navigate(tenantPath(DASHBOARD_ROUTE))}
        />
      );
    }
    // A18 §4. A 404 here has THREE possible causes and the message names all of
    // them rather than choosing: the bill does not exist, it belongs to another
    // utility (HR-1 collapses those two server-side, and US-BIL-026 TC-6
    // requires it), or `GET /invoices/{id}` is not registered. Claiming only
    // the last would mislabel an RLS refusal as a build gap.
    return (
      <FailedWithRetry
        title={t("billing.bill.failedTitle")}
        reason={
          detailNotFound(detailQuery.error)
            ? t("billing.bill.notFound")
            : apiErrorText(detailQuery.error, translate)
        }
        onRetry={() => void detailQuery.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(BILLING_ROUTE))}
      />
    );
  }

  const detail = detailQuery.data;
  const locked = isLockedBill(detail.status);
  // DEF-BIL-10068 — a ONE-TIME draft decides on this page (Approve / Cancel
  // draft). DEF-BIL-10067 (after-walk 2026-10-12, c): the old disabled
  // "Cancel this bill" is then hidden, because its reason (*"A draft is not
  // canceled — it is simply not issued"*) contradicts the button beside it.
  const decidesHere = !locked && detail.one_time === true && detail.bill_run_id !== null;
  // Computed HERE and not at the top of the component because the counts are
  // facts about the bill. `detailTabFrom` is a plain function, not a hook, so
  // nothing about the rules of hooks moves with it.
  const tabs = billTabs(translate, {
    sent: detail.deliveries === null ? null : detail.deliveries.length,
    chain: correctionDocumentCount(detail),
  });
  const active = detailTabFrom(searchParams.get(TAB_PARAM), tabs);

  // BR-BIL-004 / US-BIL-027: the three gated actions the capability row names.
  // None has an endpoint, and each carries the reason that is TRUE about it
  // rather than one generic "not built" — the reason changes with the fact
  // (hard-won law 1).
  //
  // Reprint needs the pinned render (`GET /invoices/{id}/document`), and it is
  // meaningless on a draft: BR-BIL-030 stamps the document instance AT ISSUE,
  // so a draft has nothing to reprint.
  //
  // ⚠ **DEF-116 — TWO CONTROLS ON THIS SCREEN ASSERTED OPPOSITE FACTS ABOUT ONE
  // ROW, AND THIS BRANCH WAS THE ONE THAT WAS WRONG.** The Document panel read
  // `has_payload` and said *"Locked copy saved: Yes — the saved copy exists but
  // cannot be opened yet"*; this button read `document_url === null` and said
  // *"No saved copy was recorded for this bill, so there is nothing to print."*
  // Both about the same bill, and a user could not tell which to believe.
  //
  // **THE PANEL WAS TELLING THE TRUTH.** `has_payload` is a fact about the ROW —
  // `invoices.bill_payload`, the BR-BIL-030 instance stamped at issue and frozen
  // with the money. `document_url` is a fact about the SERVER: it is null
  // because `GET /invoices/{id}/document` is not mounted (`apps/billing/api.py`
  // says so in as many words), which says nothing whatever about whether a copy
  // was saved. Reading a missing ROUTE as a missing RECORD is the bug, and it is
  // the kind that matters — it told a clerk a customer's bill was never
  // recorded, which on an immutable financial record is alarming and false.
  //
  // So both controls now branch on the SAME fact in the same order: does the row
  // carry its locked copy? If it does, the only thing missing is the endpoint
  // that renders it, and that is what the reason says.
  //
  // ══════════════════════════════════════════════════════════════════════════
  // ⚠ **CR-053 TASK 1 · DEF-2451 — THE ENDPOINT DEF-116's REASON NAMED HAS BEEN
  // MOUNTED SINCE 2026-08-16, AND THIS BUTTON WENT ON SAYING IT WAS NOT.**
  // ══════════════════════════════════════════════════════════════════════════
  // `billing.bill.action.reprintBlocked` read *"Re-printing the saved copy needs
  // the endpoint that renders it, which has not been built."* It has. Both
  // halves were verified on this branch before a line of this was written:
  //
  //   · `config/urls.py` includes `apps.billing.documents_api`, and
  //     `resolve("/api/{tenant}/invoices/{id}/document.pdf")` lands on
  //     `apps.billing.documents_api.view`;
  //   · over real HTTP the route answered **`200 application/pdf`, 4,110 bytes,
  //     `%PDF-1.4`, `Content-Disposition: inline`,
  //     `X-Document-Provenance: original`** for `BL-2608-000094`.
  //
  // A disabled control whose reason is a claim about the product that stopped
  // being true is hard-won law 1 in its purest form — *"a comment claiming a
  // guarantee is not the guarantee"*, running backwards. The key is RETIRED
  // rather than reworded, because nothing is left for it to say.
  //
  // **WHAT REPLACES IT IS THE SERVER'S OWN ANSWER, NOT A NEW CLAIM.** The four
  // states below are the four the route really has, and only one of them is a
  // sentence this screen writes:
  //
  //   · a DRAFT — nothing is stamped until issue (BR-BIL-030), so there is
  //     nothing to print and the row itself says so;
  //   · issued with NO locked copy — the row's own fact, unchanged (DEF-116);
  //   · the document read is still in flight — disabled while we do not yet
  //     know, which is honest for the half-second it lasts and is why it is not
  //     rendered as a live link that might 409;
  //   · the document read FAILED — the SERVER's sentence, verbatim. The
  //     development store answered `BIZ-STATE billing.document.bytesMissing`
  //     when its bytes were not on disk, and a clerk needs to read exactly
  //     that, not a generic refusal this file invented.
  //
  // Otherwise it is a LINK to `pdf_url`, opened in the browser's own viewer —
  // the same choice `BillDocumentPage` records: the route answers `application/
  // pdf` inline, so print and save belong to the browser and not to us.
  const printReason = !locked
    ? t("billing.bill.action.reprintDraft")
    : !detail.has_payload
      ? t("billing.bill.action.reprintNoDocument")
      : documentQuery.isPending
        ? t("billing.bill.action.reprintChecking")
        : documentQuery.data === undefined
          ? apiErrorText(documentQuery.error, translate)
          : null;
  const printHref =
    documentQuery.data === undefined ? null : apiHref(tenantPath(documentQuery.data.pdf_url));
  // Correcting is EP-BIL-04, and it only ever applies to a bill that WAS issued.
  //
  // ⚠ 2026-08-16: THIS STOPPED BEING A DISABLED BUTTON. `correctBlocked` said
  // the correction workflow did not exist; S30's Fix-a-bill tab exists now, so
  // an issued bill LINKS to it with this bill already chosen and only a DRAFT
  // still refuses (a draft is re-priced, never corrected). Leaving the disabled
  // control up would be a comment claiming a state of the product — the exact
  // thing hard-won law 1 is about, one release later.
  const correctReason =
    writeBlockedReason ?? (!locked ? t("billing.bill.action.correctDraft") : null);
  // BR-BIL-009 / OQ-012: the void's consequence message and its window
  // evaluation (paid? same open period? approval?) are computed SERVER-side.
  // Offering a confirm dialog written here would be inventing the consequence
  // it is required to state.
  const voidReason =
    writeBlockedReason ??
    (detail.status === "void"
      ? t("billing.bill.action.voidAlready")
      : !locked
        ? t("billing.bill.action.voidDraft")
        : t("billing.bill.action.voidBlocked"));

  return (
    <div className="px-4 pt-6 pb-8">
      <PageHeader
        backTo={{ to: tenantPath(BILLING_ROUTE), label: t("billing.title") }}
        // DEF-BIL-10068 (PO 2026-10-12) — an interim bill is typed `cycle` on
        // purpose, so a bill from a ONE-TIME run reads *One-time bill*, never
        // *Cycle bill*. Every other type keeps its own word.
        kicker={t("billing.bill.kicker", {
          type:
            detail.one_time === true && detail.bill_type === "cycle"
              ? t("billing.bills.type.oneTime")
              : billTypeLabel(detail.bill_type, translate),
        })}
        title={billHeadline(detail, translate)}
        titleAfter={<CopyBillNumber value={detail.invoice_no} t={translate} />}
        rollup={
          <BillIdentityLine
            detail={detail}
            account={accountQuery.data}
            t={translate}
            timeZone={timeZone}
            dateFormat={dateFormat}
          />
        }
        status={
          // ⚠ **ONE PILL, NOT TWO (`CR-101-BRC03`, blueprint legend 5).** A
          // second pill reading *Past-due unknown* stood beside `Issued` on
          // every issued bill in this deployment, and the blueprint's answer is
          // that the fact lives ONCE, as a row — it is still on the Charges
          // tab's *When this is due* panel, spelled out in a sentence, which is
          // where a clerk asking "is this late" is already looking. A heading
          // is for what this record IS; "we did not work that out" is not that.
          <StatusPill tone={billStatusTone(detail.status, detail.past_due)}>
            {billStatusLabel(detail, translate)}
          </StatusPill>
        }
        // ══════════════════════════════════════════════════════════════════
        // ⚠ **THE EMPHASIS IS THE ANNOTATION'S, NOT THE BOX'S — `DEF-BIL-5244`
        // REVERSED (`CR-105-BRC03`, 2026-09-14).**
        // ══════════════════════════════════════════════════════════════════
        // This slot shipped INVERTED, defended by a comment that named six
        // pages: *"on p015, p018, p021, p022, p024 and p027 — every §02 frame
        // — `Fix this bill` is the boxed control and `View the bill as sent` is
        // unboxed grey."* Every word of that is a true reading of the PIXELS
        // and it is the wrong instrument. **B14 rule 37: a figure drawn in a
        // wireframe is an ILLUSTRATION, never a fact to build to** — and the
        // annotation printed under those same frames says, verbatim (p016,
        // legend 6): *"One primary, and an overflow · View the bill as sent
        // FILLED; Fix this bill secondary; Print bill and Cancel this bill into
        // `…`, Cancel keeping its reason · UI-RULES 4–6 · CHANGED"*. Neither
        // control is drawn FILLED anywhere in the document, so the drawing
        // could not have settled this in either direction; the words could and
        // did.
        //
        // It is also the only reading that makes the row's ORDER mean
        // something: the drawing puts `View the bill as sent` LEFTMOST, which
        // is where `leadingAction` exists to put a primary (US-SHL-020), and
        // BR-SHL-044's *exactly one primary* then lands on the thing a clerk
        // opens this screen to see.
        //
        // ⚠ **AND IT NO LONGER VANISHES — `p014`'s OWN FINDING, CLOSED.** The
        // as-built pair refused in two different ways side by side: *"Print
        // disables with a reason; View vanishes. A clerk cannot learn one rule
        // from the pair."* Both disable with the reason now, and it is the same
        // reason, read off the same fact in the same order (DEF-116).
        leadingAction={
          detail.document_url !== null ? (
            <ButtonLink variant="primary" to={tenantPath(billDocumentPath(detail.id))}>
              {t("billing.bill.action.viewDocument")}
            </ButtonLink>
          ) : (
            <GuardedButton
              label={t("billing.bill.action.viewDocument")}
              reason={printReason ?? t("billing.bill.action.reprintNoDocument")}
              variant="primary"
              onClick={() => undefined}
            />
          )
        }
        secondaryActions={
          <>
            {/* DEF-BIL-10068 (PO 2026-10-12, *"a draft gets Approve and
                Cancel"*) — a ONE-TIME draft decides here, through the
                one-time Send and the existing discard. */}
            {decidesHere && detail.bill_run_id !== null && (
              <DraftDecision
                runId={detail.bill_run_id}
                blockedReason={writeBlockedReason}
                client={client}
                onMessage={toast}
                onDone={(outcome) => {
                  if (outcome === "cancelled") {
                    navigate(tenantPath(BILLING_ROUTE));
                    return;
                  }
                  void queryClient.invalidateQueries({ queryKey: billDetailQueryKey(invoiceId) });
                }}
                refusalOf={(error) => apiErrorText(error, translate)}
                t={translate}
              />
            )}
            {correctReason === null ? (
              // Legend 6: *"Fix this bill secondary"*. It is still the thing a
              // clerk comes here to DO; it is no longer the thing they came
              // here to SEE, and the drawing's own order says which is which.
              <ButtonLink variant="secondary" to={tenantPath(fixABillPath(detail.id))}>
                {t("billing.bill.action.correct")}
              </ButtonLink>
            ) : (
              <GuardedButton
                label={t("billing.bill.action.correct")}
                reason={correctReason}
                onClick={() => undefined}
              />
            )}
            <RowActionsMore label={t("billing.bill.moreActions")}>
              {/* B14 rule 4: print HANDS SOMETHING OVER, and an anchor is what
                  lets middle-click and "open in new tab" work on it — which is
                  why this line of the menu is `RowMenuAnchor` and not
                  `RowMenuAction` with a `window.open`. */}
              <RowMenuAnchor
                label={t("billing.bill.action.reprint")}
                icon={<PrinterIcon />}
                href={printHref ?? ""}
                reason={printReason}
                testId="bil-print-bill"
              />
              {/* BR-BIL-009 / OQ-012: the void's consequence message and its
                  window evaluation are computed SERVER-side, so this stays
                  disabled WITH its reason — the drawing keeps that reason in as
                  many words (legend 6, *"Cancel keeping its reason"*). */}
              {!decidesHere && (
                <RowMenuAction
                  label={t("billing.bill.action.void")}
                  icon={<TrashIcon />}
                  reason={voidReason}
                  danger
                  onClick={() => undefined}
                  testId="bil-cancel-bill"
                />
              )}
            </RowActionsMore>
          </>
        }
        tabs={tabs}
        activeTabId={active}
        tabsLabel={t("billing.bill.tabsLabel")}
        onTabSelect={(tab) => selectTab(tab.id)}
      />

      {/* ⚠ THIS USED TO RENDER ON ALL FOUR TABS AND THE PRODUCT OWNER SAW WHY
          THAT WAS WRONG (CR-043 finding 9, 2026-08-27). The comment here read
          *"the A19 summary box sits outside the tab strip because it belongs to
          the bill, not to one view of it"* — which is true of the FACT and does
          not follow for the LAYOUT. Document, Charges, Corrections and Audit
          each opened with the identical Amount-due panel before their own
          content, and on Corrections and Audit it pushed the tab's actual
          subject below the fold: a clerk who clicked *Corrections* to see
          whether a credit note exists was shown the bill's total first, again.

          **So it renders where the money IS the subject and not where it is
          background.** Document is the bill; Charges is what the total is made
          of, and the panel foots the table below it. Corrections is about
          credit notes and replacement bills, Audit is a log of who touched what
          — neither is a view of the total, and both carry the bill's identity,
          status and dates in the page header two inches above.

          The bill's own numbers are never further than one click away, which is
          the only thing "it belongs to the bill" actually required. */}
      {/* ⚠ **AND `Owed today` IS THE DOCUMENT'S ALONE (`CR-105-BRC03`).** The
          blueprint draws AMOUNT on both tabs and draws the live balance under
          it only on Document (p015 legend 9 against p018, which ends at *Total
          due*). Charges is *what the total is made of*; what they owe NOW is a
          different question and belongs where the bill is the subject. */}
      {(active === "document" || active === "lines") && (
        <SummaryPanel
          detail={detail}
          t={translate}
          owedToday={active === "document" ? (openBillsQuery.data ?? null) : undefined}
        />
      )}

      {active === "document" && (
        <DocumentTab
          detail={detail}
          account={accountQuery.data}
          usage={usageQuery.data}
          usagePending={usageQuery.isPending}
          document={documentQuery.data}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          client={client}
          printHref={printHref}
          printBlockedReason={printReason}
        />
      )}
      {/* ⚠ **DELIVERY MOVED OFF THIS TAB AND ONTO ITS OWN (`CR-101-BRC03`,
          blueprint entry 02.5).** It was the LAST panel of the FIRST tab, below
          four panels of provenance, and *did they get it* is a top-three
          question. It is the same panel and the same rows — a MOVE, not a
          rebuild — with the channel and status names turned into words and the
          customer's own delivery preferences beside them. */}
      {active === "sent" && (
        <SentTab
          detail={detail}
          account={accountQuery.data}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          writeBlockedReason={writeBlockedReason}
          client={client}
          // US-PAY-016: the mark changes THIS bill's delivery rows, so the
          // detail is re-read rather than patched in the browser — the panel
          // must show the server's own `returned_at`, not this screen's guess
          // at what it will be.
          onMarkedReturned={() => {
            void queryClient.invalidateQueries({ queryKey: billDetailQueryKey(invoiceId) });
          }}
        />
      )}
      {active === "lines" && (
        // CR-053 task 6 — the due-date panel renders a DATE, so this tab
        // takes the tenant's zone and format like every other one. A date
        // formatted anywhere but `DateCell` is BR-SHL-034's defect.
        <LinesTab
          detail={detail}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
        />
      )}
      {active === "chain" && (
        <ChainTab
          detail={detail}
          t={translate}
          timeZone={timeZone}
          dateFormat={dateFormat}
          client={client}
        />
      )}
      {/* BR-CUS-034 / US-AUD-005: the audit tab is the S61 viewer filtered to
          this entity — the SAME component every other detail uses, so one audit
          surface keeps one set of masking and window rules. */}
      {active === "audit" && (
        <AuditTab entityType="invoice" entityId={detail.id} t={translate} regional={props} />
      )}
    </div>
  );
}

export default BillDetailPage;

// ── The identity line under the H1, and the glyph beside it ───────────────

/**
 * COPY THE BILL NUMBER. Blueprint legend 8: *"it gets read aloud and pasted
 * into Fix-a-bill all day"*.
 *
 * ⚠ **IT IS THE ONE THING ON THIS HEADER THAT CAN FAIL SILENTLY, SO IT SAYS SO.**
 * `navigator.clipboard` is absent over plain HTTP and refused when the document
 * is not focused, and both reject rather than throw synchronously. A glyph that
 * looks pressed and copied nothing is worse than no glyph, so the label changes
 * to the outcome for a moment and reverts.
 *
 * A `<button>`, never a clickable `<span>`: it acts, so a keyboard must reach it.
 */
function CopyBillNumber(props: { value: string | null; t: Translator }) {
  const [state, setState] = useState<"idle" | "copied" | "failed">("idle");
  if (props.value === null || props.value === "") {
    // A draft has no number to copy (BR-BIL-022 mints it at issue).
    return null;
  }
  const value = props.value;
  const label =
    state === "copied"
      ? props.t("billing.bill.copied")
      : state === "failed"
        ? props.t("billing.bill.copyFailed")
        : props.t("billing.bill.copyNumber");
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      data-bil="copy-bill-no"
      data-copy-state={state}
      onClick={() => {
        void (async () => {
          try {
            await navigator.clipboard.writeText(value);
            setState("copied");
          } catch {
            setState("failed");
          }
          window.setTimeout(() => setState("idle"), 2000);
        })();
      }}
      className={
        "ms-2 inline-flex h-6 w-6 cursor-pointer items-center justify-center align-middle " +
        "rounded-md border-none bg-transparent p-0 text-accent " +
        "hover:bg-[color-mix(in_srgb,var(--color-accent)_10%,transparent)]"
      }
    >
      <CopyIcon />
    </button>
  );
}

/**
 * WHO THIS IS, and WHAT IS OWED — the two lines the blueprint draws under the
 * bill number, in that order.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT CHANGED, AND WHY EACH HALF MOVED (`CR-101-BRC03`)
 * ══════════════════════════════════════════════════════════════════════════
 * This was one line of four labelled pairs — *Account · Service period · Due
 * date* — and the blueprint replaces it with two lines that answer the two
 * questions a clerk on the phone actually asks:
 *
 *   1. **whose bill is this** — the customer's NAME, the SERVICE ADDRESS and
 *      the account number, the last two as links;
 *   2. **what does it say** — the total and its due date in bold, then the
 *      issue date, the period and the cycle in a quieter voice.
 *
 * ⚠ **THE ACCOUNT NUMBER LOSES ITS LABEL AND THAT IS DELIBERATE.** It read
 * *"Account AC-2026-00011"*; the drawing puts it bare, third in a `·` list
 * after a name and an address, where nothing else it could be. B14 rule 33
 * caps a LABEL at three words and this line has three facts — spending a word
 * on *Account* in front of a string that begins `AC-` is the description
 * budget rule 32 exists for.
 *
 * ⚠ **THE ADDRESS IS DERIVED, NEVER STORED HERE (hard rule 8).** It comes off
 * `GET /accounts/{id}`, which walked to `premises` for it. The invoice carries
 * no address column and must not grow one. When the account read has not
 * landed — or answered — the line simply omits the address rather than drawing
 * a placeholder: an address is either a real place or it is nothing.
 */
export function BillIdentityLine(props: {
  detail: InvoiceDetail;
  /** `undefined` while the account read is in flight or refused. */
  account: AccountDetail | undefined;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { detail, account, t } = props;
  const tenantPath = useTenantPath();
  const locality = account?.premise_locality ?? null;
  const street = account?.premise_address ?? null;
  const unit = account?.unit_label ?? null;
  // ⚠ **THE POSTCODE FOLLOWS THE STATE WITH A SPACE, NOT A COMMA.** The
  // drawing reads `105 Cedar Ridge Way, Unit 1, Silver Creek TX 78611`, and the
  // first build of this line produced `… Silver Creek TX, 78611` — a comma a
  // North American address does not have. Found by looking at the screen beside
  // the drawing, which is the only thing that finds a comma.
  const place =
    locality == null
      ? null
      : [locality.city, locality.state, locality.postal_code]
          .filter((part) => part != null && part !== "")
          .join(" ");
  const address =
    street === null || street === ""
      ? null
      : [unit === null || unit === "" ? street : `${street}, ${unit}`, place]
          .filter((part) => part != null && part !== "")
          .join(", ");
  // GUARDED: a server one deploy behind serves no `cycle_name` at all, and the
  // fallback is the CODE rather than nothing — a bill that names no cycle where
  // one exists is a worse answer than one that names it in the old words.
  const cycleName = firstFilled(detail.cycle_name ?? null, detail.cycle_label);
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5" data-bil="who-line">
        {detail.customer_name !== null && detail.customer_name !== "" && (
          // ⚠ **THE NAME IS A LINK — legend 1, *"both linked"* (`CR-105-BRC03`).**
          // The drawing inks it in the body colour and the address beside it in
          // the accent, so the PICTURE says one is a link and the other is not;
          // the annotation under that picture says both are. B14 rule 37 settles
          // which instrument decides, the same way it settles the action row
          // above. A name a clerk cannot click while the address next to it
          // opens the account is the harder thing to explain, and both go to the
          // same place.
          <span className="font-heading font-bold">
            <InlineLinkTo to={tenantPath(accountDetailPath(detail.account_id))}>
              {detail.customer_name}
            </InlineLinkTo>
          </span>
        )}
        {address !== null && (
          <>
            <IdentityDot />
            <InlineLinkTo to={tenantPath(accountDetailPath(detail.account_id))}>
              {address}
            </InlineLinkTo>
          </>
        )}
        {(detail.customer_name !== null || address !== null) && <IdentityDot />}
        <span className="[font-feature-settings:'tnum']">
          <InlineLinkTo to={tenantPath(accountDetailPath(detail.account_id))}>
            {detail.account_no ?? t("billing.bills.noAccountNo")}
          </InlineLinkTo>
        </span>
      </div>
      <div
        className="flex flex-wrap items-baseline gap-x-1.5 gap-y-0.5 [font-feature-settings:'tnum']"
        data-bil="money-line"
      >
        <span className="font-heading font-bold">
          <MoneyCell amount={detail.total} currency={detail.currency} />
        </span>
        {detail.due_date !== null ? (
          <>
            <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
              {t("billing.bill.dueWord")}
            </span>
            <span className="font-heading font-bold">
              <DateCell
                value={detail.due_date}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />
            </span>
          </>
        ) : (
          <Dash>{t("billing.bills.notIssued")}</Dash>
        )}
        <IdentityDot />
        <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
          {/* THREE DATES MATTER AND ONLY TWO WERE SHOWN — blueprint legend 3.
              The issue date is what a clerk checks a posted payment against and
              it was nowhere on this screen. */}
          {detail.issued_at !== null ? (
            <>
              {t("billing.bill.billedWord")}{" "}
              <DateCell
                value={detail.issued_at}
                timeZone={props.timeZone}
                dateFormat={props.dateFormat}
              />{" "}
            </>
          ) : null}
          {t("billing.bill.forWord")}{" "}
          <DateCell
            value={detail.period_start}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
          {" – "}
          <DateCell
            value={detail.period_end}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        </span>
        {/* ⚠ **THE CYCLE BY NAME, NOT BY CODE (`CR-105-BRC03`, legend 4).**
            This printed `CY-007` — the cycle's code — while the PRINTED BILL
            for the same bill said *Silver Creek — monthly*, because
            `issue._cycle_label_for` has stamped the name into the payload since
            `DEF-2865` and `GET /invoices/{id}` served the code. One cycle, two
            words for it, on two surfaces a clerk reads side by side.
            `cycle_name` is the name with the code as its own fallback; the CODE
            keeps its place under Origin, which is what legend 4 asks for in as
            many words. */}
        {cycleName !== null && (
          <>
            <IdentityDot />
            <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
              {cycleName}
            </span>
          </>
        )}
      </div>
    </div>
  );
}

/** The `·` between two facts on one line. A separator, not content — it is
 *  `aria-hidden` so a screen reader reads the facts and not the punctuation. */
function IdentityDot() {
  return (
    <span
      aria-hidden="true"
      className="text-[color-mix(in_srgb,var(--color-text)_40%,transparent)]"
    >
      ·
    </span>
  );
}

// ── The A19 summary box (US-BIL-026 §7) ────────────────────────────────────

/**
 * `total due = previous balance − payments/credits received + current charges`.
 * WE-1 worked: `45.00 − 0.00 + 247.87 = 292.87`.
 *
 * SERVED, never summed here. Two of the three inputs are positions this lane
 * may not read (B1) — the previous balance is the ledger's and the payments are
 * the payments module's — and BR-BIL-035 stamps all of them into the payload at
 * issue so a reprint shows the arrears as they stood on the bill date. A
 * client-side subtraction would answer today's question on a historical bill.
 */
export function SummaryPanel(props: {
  detail: InvoiceDetail;
  t: Translator;
  /**
   * `CR-105-BRC03`, blueprint legend 9 — *"Owed today · the live account
   * balance, linked · NEW READ — every other figure here is as-at-issue and
   * nothing answered what do they owe now"*.
   *
   * **THREE STATES, THREE SENTENCES, AND `undefined` IS NOT ONE OF THEM.**
   * `undefined` means *this tab does not ask the question* (Charges draws the
   * four frozen figures and stops, which is what p018 draws); `null` means the
   * read was asked and has not answered; a payload is the answer.
   */
  owedToday?: OpenBillPosition | null;
}) {
  const { detail, t } = props;
  const summary = detail.summary;
  const tenantPath = useTenantPath();
  const asksOwedToday = props.owedToday !== undefined;
  return (
    <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.summary")}</Kicker>}>
      {summary === null ? (
        <NotRecorded
          label={t("billing.bill.summaryAbsent")}
          why={t("billing.bill.summaryAbsentWhy")}
          ruleRef="BR-BIL-035"
        />
      ) : (
        <dl
          className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 [font-feature-settings:'tnum'] [&_dt]:text-[color-mix(in_srgb,var(--color-text)_65%,transparent)] [&_dd]:m-0 [&_dd]:text-right"
          data-bil="summary"
        >
          <dt>{t("billing.bill.summary.previousBalance")}</dt>
          <dd>
            {summary.previous_balance !== null ? (
              <MoneyCell amount={summary.previous_balance} currency={detail.currency} />
            ) : (
              <AwaitsCell
                label={t("billing.bill.summary.awaiting")}
                why={t("billing.bill.summary.previousBalanceWhy")}
              />
            )}
          </dd>
          <dt>{t("billing.bill.summary.paymentsCredits")}</dt>
          <dd>
            {summary.payments_credits !== null ? (
              <MoneyCell amount={summary.payments_credits} currency={detail.currency} />
            ) : (
              <AwaitsCell
                label={t("billing.bill.summary.awaiting")}
                why={t("billing.bill.summary.paymentsCreditsWhy")}
              />
            )}
          </dd>
          <dt>{t("billing.bill.summary.currentCharges")}</dt>
          <dd>
            {summary.current_charges !== null ? (
              <MoneyCell amount={summary.current_charges} currency={detail.currency} />
            ) : (
              <Dash />
            )}
          </dd>
          <dt
            className="border-t-2 border-t-text pt-1 font-heading font-extrabold"
            data-bil="summary-total"
          >
            {t("billing.bill.summary.totalDue")}
          </dt>
          <dd
            className="border-t-2 border-t-text pt-1 font-heading font-extrabold"
            data-bil="summary-total"
          >
            {summary.total_due !== null && summary.total_due.trim().startsWith("-") ? (
              // OQ-217 (PO 2026-10-01): an account in credit is told so —
              // *"$48.75 credit, nothing to pay"* — never a negative amount due.
              <span className="flex flex-col items-end gap-1">
                <MoneyCell amount="0" currency={detail.currency} />
                <span className="text-sm font-normal" data-bil="summary-credit">
                  {t("billing.bill.summary.credit")}{" "}
                  <MoneyCell amount={summary.total_due.trim().slice(1)} currency={detail.currency} />
                </span>
              </span>
            ) : summary.total_due !== null ? (
              <MoneyCell amount={summary.total_due} currency={detail.currency} />
            ) : detail.status === "draft" && summary.current_charges !== null ? (
              // DEF-BIL-10068 (PO 2026-10-12) — a DRAFT shows its own total, not
              // a dash. The balance-forward stamp happens at issue, so the
              // previous balance above may stay blank until then.
              <MoneyCell amount={summary.current_charges} currency={detail.currency} />
            ) : (
              <Dash />
            )}
          </dd>
          {/* ⚠ **THE ONE LIVE FIGURE IN A PANEL OF FROZEN ONES**, and it is
              drawn BELOW the rule under `Total due` for that reason — it is not
              a fifth term of the sum above, it is a different question. The
              label carries the link, because *what do they owe now* is answered
              in full on the account and this row is the doorway. */}
          {asksOwedToday && (
            <>
              <dt data-bil="owed-today">
                {t("billing.bill.summary.owedToday")}{" "}
                <InlineLinkTo to={tenantPath(accountDetailPath(detail.account_id))}>
                  {t("billing.bill.summary.owedTodayLink")}
                </InlineLinkTo>
              </dt>
              <dd data-bil="owed-today">
                {props.owedToday == null || props.owedToday.total_open === null ? (
                  <AwaitsCell
                    label={t("billing.bill.summary.awaiting")}
                    why={t("billing.bill.summary.owedTodayWhy")}
                  />
                ) : (
                  <MoneyCell
                    amount={props.owedToday.total_open}
                    currency={props.owedToday.currency ?? detail.currency}
                  />
                )}
              </dd>
            </>
          )}
        </dl>
      )}
      {/* ⚠ **THE CAVEAT RENDERS WHERE THE TWO KINDS OF FIGURE SIT TOGETHER, AND
          NOWHERE ELSE (`CR-105-BRC03`).** It read the same 17-word sentence on
          BOTH tabs; p018 draws no sentence under the Charges AMOUNT at all, and
          B14 rule 32's description budget is why. Where it does render it is
          now two short facts rather than one long one — B14 rule 33, *"two
          sentences of six beat one sentence of twelve"*. */}
      {asksOwedToday && <p className="met-panel-hint">{t("billing.bill.panel.summaryHint")}</p>}
    </Panel>
  );
}

// ── Tabs ───────────────────────────────────────────────────────────────────

/**
 * ══════════════════════════════════════════════════════════════════════════
 * `CR-105-BRC03` — THE DOCUMENT TAB, RESTRUCTURED INTO THE SEVEN DRAWN GROUPS.
 * ══════════════════════════════════════════════════════════════════════════
 * Blueprint 02.1 (`05-prototype/04 Billing, As Built.pdf` p015–p017, read as
 * IMAGES per B14 rule 42), whose own closing line gives the order and the
 * reason for it: *"Seven groups, one word each, in the order a clerk asks them:
 * Amount → Breakdown → Usage → Dates → the document itself → Origin → Record.
 * The first four answer how much, why, why that much water, and when. The last
 * two are reassurance and are closed."*
 *
 * **IT IS A RESTRUCTURE AND THE DOCUMENT SAYS SO**: p011–p012's carry-over map
 * is titled *"Nothing on the bill detail is lost"* and does the arithmetic —
 * 43 as-built elements become 51, as 27 unchanged + 11 moved + 4 relabelled +
 * 1 removed + 9 new. An element it marks MOVED that goes missing is a failed
 * conversion; the one it marks REMOVED surviving is the same failure.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ **THE EMBEDDED PDF VIEWER IS GONE, ON A RULING, AND IT IS THE ONLY THING
 * IN THIS DOCUMENT PERMITTED TO GO.**
 * ══════════════════════════════════════════════════════════════════════════
 * Product Owner, 2026-09-11, verbatim: *"we dont what full view of the document
 * - you give a link to download but full view of document is not requires - it
 * does not add any value to user"*.
 *
 * This tab's body was an `<iframe>` at `h-[760px]` pointed at
 * `/invoices/{id}/document.pdf`, under a banner reading **CR-053 TASK 3 — THE
 * OUTPUT IS THE SCREEN**. That decision is superseded and the banner goes with
 * it: a comment carrying the reasoning for a ruling that has been reversed is
 * hard-won law 1 with the argument still attached, and it is what a later lane
 * would restore the viewer from.
 *
 * **WHAT REPLACES IT IS SMALLER AND ANSWERS MORE.** The two things a clerk
 * actually needed from the viewer — *does a saved copy exist* and *can I send
 * it to someone* — are now STATED rather than inferred from a rendered page:
 * a download control, an open-in-a-new-tab control, and the two facts about the
 * saved copy. p017: *"It makes the tab better than the change suggests."*
 *
 * ⚠ **SCREEN 03 IS NOT TOUCHED, DELIBERATELY.** p017 raises whether the ruling
 * reaches `/billing/bills/:id/document`, whose only purpose is the full view,
 * and answers itself: *"I have not assumed either way."* Neither does this
 * lane. The screen stands and both controls here still reach the bill.
 */
function DocumentTab(props: {
  detail: InvoiceDetail;
  /** `undefined` while the account read is in flight or refused. */
  account: AccountDetail | undefined;
  /** `undefined` while `GET /accounts/{id}/usage` is in flight or refused. */
  usage: UsagePayload | undefined;
  usagePending: boolean;
  /** `undefined` while `GET /invoices/{id}/document` is in flight, refused, or
   *  never asked — it is not asked on a bill with no pinned template. */
  document: RenderedBillDocument | undefined;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
  /** The printable page's own URL, or null while there is none. Resolved ONCE
   *  by the page and passed down, so this tab and the header's controls can
   *  never disagree about one bill. */
  printHref?: string | null;
  /** Why there is no printable page — the row's fact or the SERVER's sentence,
   *  never one this component composes (BR-SHL-025). */
  printBlockedReason?: string | null;
}) {
  const { detail, t } = props;
  return (
    <>
      <BreakdownGroup detail={detail} t={t} />
      <UsageGroup
        detail={detail}
        usage={props.usage}
        usagePending={props.usagePending}
        document={props.document}
        t={t}
      />
      <DatesGroup
        detail={detail}
        t={t}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
      />
      <TheBillGroup
        detail={detail}
        document={props.document}
        t={t}
        printHref={props.printHref ?? null}
        printBlockedReason={props.printBlockedReason ?? null}
      />
      <OriginGroup
        detail={detail}
        t={t}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
        client={props.client}
      />
      <RecordGroup detail={detail} t={t} />
    </>
  );
}

/**
 * GROUP 2 · **BREAKDOWN** — *why it is $251.45*, in one line.
 *
 * Blueprint legend 10: *"`charges_by_service`, already served and already on
 * the Charges tab as a table · MOVED (a one-line summary; the table stays)"*.
 * So this is not a second grouping of the money and must never become one — it
 * is the SAME block the Charges tab foots its table with, drawn as a sentence,
 * and `See every charge →` is the only thing on it that is not a figure.
 *
 * ⚠ **THE BILL-LEVEL BUCKET IS DRAWN AS `Tax` AND THAT IS THE DRAWING'S OWN
 * WORD**, not a relabelling this file invented: p015 ends the line
 * `… · Fire $0.00 · Tax $4.93`. It is honest here in a way it would not be on
 * the Charges tab, where the same bucket can also hold a `minimum_adjustment`
 * (`DEF-2429`) — so the word comes from the bucket's `kinds` when the bucket
 * holds only tax, and from a neutral one when it does not.
 */
/**
 * `DEF-BIL-9346` — the bill-level bucket as two groups: its DISCOUNT lines
 * (named *Discounts*, `null` when there are none) and everything else (taxes,
 * fees, a minimum adjustment). Every figure is the server's own; nothing is
 * added up here (BR-SHL-023). Without the server's split the bucket stays whole.
 */
function billLevelSplit(level: InvoiceChargesByService["bill_level"]): {
  discounts: { lineCount: number; subtotal: string; subtotalDisplay: string } | null;
  lineCount: number;
  kinds: string[];
  subtotal: string;
  subtotalDisplay: string;
} {
  if (level.discounts === undefined || level.others === undefined) {
    return {
      discounts: null,
      lineCount: level.line_count,
      kinds: level.kinds,
      subtotal: level.subtotal,
      subtotalDisplay: level.subtotal_display,
    };
  }
  return {
    discounts:
      level.discounts.line_count > 0
        ? {
            lineCount: level.discounts.line_count,
            subtotal: level.discounts.subtotal,
            subtotalDisplay: level.discounts.subtotal_display,
          }
        : null,
    lineCount: level.others.line_count,
    kinds: level.others.kinds,
    subtotal: level.others.subtotal,
    subtotalDisplay: level.others.subtotal_display,
  };
}

function BreakdownGroup(props: { detail: InvoiceDetail; t: Translator }) {
  const { detail, t } = props;
  const tenantPath = useTenantPath();
  // GUARDED for the reason `IntegrityPanel` records: a server one deploy behind
  // omits the block, and an unguarded read of a new one white-screened this
  // page once already.
  const block = detail.charges_by_service ?? null;
  if (block === null) {
    return (
      <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.breakdown")}</Kicker>}>
        <NotRecorded
          label={t("billing.bill.breakdownAbsent")}
          why={t("billing.bill.breakdownAbsentWhy")}
          ruleRef="BR-BIL-030"
        />
      </Panel>
    );
  }
  // `DEF-BIL-9346` — the bill-level DISCOUNTS are named *Discounts*, as the
  // Charges tab has since `DEF-BIL-9339`, and only what is left keeps *Tax* /
  // *Charged to the bill*. Both figures are the server's (`discounts`,
  // `others`); a server one deploy behind serves neither and the bucket reads
  // whole, as before.
  const split = billLevelSplit(block.bill_level);
  const billLevelOnlyTax = split.kinds.length > 0 && split.kinds.every((kind) => kind === "tax");
  const parts: { key: string; label: string; amount: string }[] = [
    ...block.services.map((row) => ({
      key: row.service,
      label: row.service_name,
      amount: row.subtotal,
    })),
  ];
  if (split.discounts !== null) {
    parts.push({ key: LINE_GROUP_DISCOUNTS, label: t("billing.bill.group.discounts"), amount: split.discounts.subtotal });
  }
  if (split.lineCount > 0) {
    parts.push({
      key: LINE_GROUP_OTHER,
      label: billLevelOnlyTax
        ? t("billing.bill.breakdownTax")
        : t("billing.bill.breakdownBillLevel"),
      amount: split.subtotal,
    });
  }
  return (
    <Panel
      as="section"
      title={
        <span className="flex items-baseline gap-2">
          <Kicker as="span">{t("billing.bill.panel.breakdown")}</Kicker>
          {/* The drawn trailing phrase — *why it is $251.45*. A FACT about the
              group it heads, six words with the figure in it (B14 rule 33). */}
          <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {t("billing.bill.breakdownWhy", {
              amount: formatMoney(detail.total, detail.currency),
            })}
          </span>
        </span>
      }
    >
      <p
        className="flex flex-wrap items-baseline gap-x-1.5 gap-y-1 [font-feature-settings:'tnum']"
        data-bil="breakdown"
      >
        {parts.map((part, index) => (
          <Fragment key={part.key}>
            {index > 0 && <IdentityDot />}
            <span>
              {part.label}{" "}
              <span className="font-heading font-bold">
                <MoneyCell amount={part.amount} currency={block.currency} />
              </span>
            </span>
          </Fragment>
        ))}
        {parts.length > 0 && <IdentityDot />}
        <InlineLinkTo to={`${tenantPath(billDetailPath(detail.id))}?${TAB_PARAM}=lines`}>
          {t("billing.bill.breakdownSeeEvery")}
        </InlineLinkTo>
      </p>
    </Panel>
  );
}

/**
 * GROUP 3 · **USAGE** — *why that much water*.
 *
 * Blueprint legend 11: *"`meter_reads` through `GET /accounts/{id}/usage`,
 * which **is mounted** · NEW READ — the second question after how much is why
 * is it higher, and nothing answered it"*.
 *
 * **FOUR COLUMNS, THREE SOURCES, AND THE FOURTH IS AN ABSENCE THE SERVER
 * STATES ITSELF.**
 *
 *   · **SERVICE** — the services this BILL charged, in the order
 *     `charges_by_service` serves them. Never the account's services: a bill
 *     is a period, and a service billed nothing this period has no row here.
 *   · **THIS PERIOD** — Σ of this bill's own `usage` lines for that service,
 *     which is frozen with the bill (BR-BIL-030) and needs no read. Summed
 *     ONLY across lines that agree on their unit — hard rule 3, *consumption
 *     always with an explicit unit, never assume* — because a tiered water
 *     charge is three lines of one quantity and a mixed-unit service is not a
 *     quantity at all.
 *   · **AVERAGE** — `metrics.avg_per_month` over twelve months, from the read
 *     above. It is the account's mean and it is LIVE, which is the one figure
 *     on this screen that legitimately moves after issue.
 *   · **READ** — which meter, and when. ⚠ **NOT SERVED, AND THE DOCUMENT
 *     PAYLOAD SAYS SO IN ITS OWN WORDS**: `GET /invoices/{id}/document` returns
 *     `absent: [{field: "meter_no · prior_read · current_read", why: "…stage 6
 *     keeps only whether the service was measured, so the document can say
 *     WHETHER a meter was read and never WHAT it read"}]`. The column is DRAWN
 *     and is therefore kept; its cell carries the server's own sentence rather
 *     than a meter this file guessed at. Inventing `M-8841 · 08/01` from the
 *     account's meter list — which carries no service — is how a screen tells a
 *     clerk a reading came off the wrong meter.
 */
function UsageGroup(props: {
  detail: InvoiceDetail;
  usage: UsagePayload | undefined;
  usagePending: boolean;
  document: RenderedBillDocument | undefined;
  t: Translator;
}) {
  const { detail, t } = props;
  const rows = billedUsageRows(detail);
  const measuredWhy =
    props.document?.absent.find((gap) => gap.field.includes("meter_no"))?.why ?? null;
  return (
    <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.usage")}</Kicker>}>
      {rows.length === 0 ? (
        // A bill with no metered line is a real bill — a fixed-charge-only
        // bill is most of Trash and all of Fire — so this is a FACT, not a
        // failure, and it says which.
        <NotRecorded
          label={t("billing.bill.usageNone")}
          why={t("billing.bill.usageNoneWhy")}
          ruleRef="BR-MET-106"
        />
      ) : (
        <PlainTable data-bil="bill-usage">
          <thead>
            <tr>
              <th>{t("billing.bill.usage.col.service")}</th>
              <th className="[&&]:text-right">{t("billing.bill.usage.col.thisPeriod")}</th>
              <th className="[&&]:text-right">{t("billing.bill.usage.col.average")}</th>
              <th>{t("billing.bill.usage.col.read")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.service}>
                <td>{row.serviceName}</td>
                <td className="[&&]:text-right [font-feature-settings:'tnum']">
                  {row.quantityDisplay === null ? (
                    <Dash>{t("billing.bill.usage.mixedUnits")}</Dash>
                  ) : (
                    `${row.quantityDisplay} ${row.unit ?? ""}`.trim()
                  )}
                </td>
                <td className="[&&]:text-right [font-feature-settings:'tnum']">
                  <UsageAverageCell
                    series={seriesForService(props.usage, row.service)}
                    pending={props.usagePending}
                    t={t}
                  />
                </td>
                <td>
                  <NotRecorded
                    label={t("billing.bill.usage.readAbsent")}
                    why={measuredWhy ?? t("billing.bill.usage.readAbsentWhy")}
                    ruleRef="A19 §1.4"
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </PlainTable>
      )}
      <p className="met-panel-hint">{t("billing.bill.panel.usageHint")}</p>
    </Panel>
  );
}

/** The AVERAGE cell's three states, and none of them is a zero. */
function UsageAverageCell(props: {
  series: UsageSeries | null;
  pending: boolean;
  t: Translator;
}) {
  const { series, t } = props;
  if (series === null) {
    // Two different absences, two different sentences: the read is still in
    // flight, or it answered and this account has no stated month for this
    // service. Neither is a zero, and a zero here would read as "they used
    // nothing", which is a claim about a customer's meter.
    return (
      <AwaitsCell
        label={t("billing.bill.usage.averageAwaiting")}
        why={
          props.pending
            ? t("billing.bill.usage.averageArrives")
            : t("billing.bill.usage.averageNoHistory")
        }
      />
    );
  }
  const metric = series.metrics.avg_per_month;
  if (metric.display === null) {
    // The server names WHY it could not average — no reads at all, one month,
    // a unit that changed under the account. Its sentence, never ours.
    return (
      <AwaitsCell
        label={t("billing.bill.usage.averageAwaiting")}
        why={metric.absent_reason ?? t("billing.bill.usage.averageNoHistory")}
      />
    );
  }
  return <span>{`${metric.display} ${metric.unit ?? ""}`.trim()}</span>;
}

/**
 * GROUP 4 · **DATES** — *and when*.
 *
 * Two carry-over rows land here and nothing else does. Legend 12: *"absorbs
 * When this is due from the Charges tab and the pill from ⑤"*, and legend 5:
 * *"`Past-due unknown` leaves the heading and lives once, under Dates"*.
 *
 * So this is the single home for three facts that were in three places: the
 * dates were in the header and under Origin, the past-due answer was a second
 * pill beside `Issued` AND a row on the Charges tab, and the late-charge count
 * was on Charges. B14 rule 32 — a fact stated twice is a fact a clerk has to
 * reconcile.
 *
 * ⚠ **`Billed` IS NEW HERE AND WAS THE FINDING** (legend 3, *"three dates
 * matter and only two were shown"*): the issue date is what a clerk checks a
 * posted payment against.
 */
function DatesGroup(props: {
  detail: InvoiceDetail;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { detail, t } = props;
  // A late-payment charge is a `fee` line, and `DEF-2428` means its CODE cannot
  // be read yet — so this counts fee lines rather than matching a code that is
  // null on every bill in the product. Naming a fee "the late fee" from its
  // description would be a guess about money.
  const fees = detail.lines.filter((line) => line.kind === "fee");
  return (
    <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.dates")}</Kicker>}>
      <FactList>
        <Fact label={t("billing.bill.field.billed")}>
          {detail.issued_at !== null ? (
            <DateCell
              value={detail.issued_at}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          ) : (
            <Dash>{t("billing.bills.notIssued")}</Dash>
          )}
        </Fact>
        <Fact label={t("billing.bill.field.servicePeriod")}>
          {/* The drawing puts the DAY COUNT beside the period — *07/01 –
              07/31/2026 · 31 days* — and it is the figure that explains a bill
              a customer says is bigger than last month's. Derived from two
              dates this row already draws, so it cannot disagree with them. */}
          <span>
            <DateCell
              value={detail.period_start}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
            {" – "}
            <DateCell
              value={detail.period_end}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
            {periodDays(detail) !== null && (
              <>
                {" "}
                <IdentityDot />{" "}
                <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                  {t("billing.bill.periodDays", { count: periodDays(detail) ?? 0 })}
                </span>
              </>
            )}
          </span>
        </Fact>
        <Fact label={t("billing.bill.field.due")}>
          {detail.due_date !== null ? (
            <DateCell
              value={detail.due_date}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
            />
          ) : (
            <Dash>{t("billing.bills.notIssued")}</Dash>
          )}
        </Fact>
        <Fact label={t("billing.bill.field.pastDue")}>
          {/* `past_due` is DERIVED SERVER-SIDE (issued ∧ unpaid ∧ due_date <
              today) over two positions this screen may not read and one clock
              it does not own. `null` is *not computed*, never *not past due*,
              and it renders as its own state — which is the pill that used to
              stand beside `Issued` on every bill, saying it in the heading. */}
          {detail.past_due === null ? (
            <NotRecorded
              label={t("billing.bill.pastDueUnknown")}
              why={t("billing.bill.pastDueUnknownWhy")}
              ruleRef="US-BIL-025"
            />
          ) : detail.past_due ? (
            <span data-bil="past-due-yes">{t("billing.bill.pastDueYes")}</span>
          ) : (
            <span data-bil="past-due-no">{t("billing.bill.pastDueNo")}</span>
          )}
        </Fact>
        <Fact label={t("billing.bill.field.feesOnBill")}>
          {fees.length === 0
            ? t("billing.bill.lateChargesNone")
            : t("billing.bill.lateChargesCount", { count: fees.length })}
        </Fact>
      </FactList>
      {/* ⚠ **THIS PANEL DOES NOT COMPOSE LATE-FEE TERMS, AND THAT IS THE
          FINDING RATHER THAN A LIMITATION.** `issue._stamp_bill_copy` states
          it: the terms are the TENANT's words (BR-BIL-021), they are charged
          whether or not they are printed, and *"a platform that wrote a
          customer's disclosure for them would be inventing legal copy in one
          language"*. */}
      <p className="met-panel-hint" data-bil="late-terms">
        {t("billing.bill.dueHint")}
      </p>
    </Panel>
  );
}

/**
 * GROUP 5 · **THE BILL** — what replaced the embedded viewer.
 *
 * Two controls and two facts, exactly as p016 draws them: `↓ Download the bill
 * as sent (PDF)`, `Open it in a new tab ↗`, then *Saved copy* and *Template*.
 *
 * ⚠ **BOTH CONTROLS ARE ANCHORS AT THE SAME URL AND THEY ARE NOT THE SAME
 * CONTROL.** `documents_api` answers `application/pdf` with
 * `Content-Disposition: inline`, so the browser decides: an anchor carrying
 * `download` saves the file, and one carrying `target="_blank"` hands it to the
 * browser's own viewer — which is where print and save live (BR-BIL-036's
 * floor) without this app re-implementing either. B14 rule 4 gives each its
 * glyph: `↓` downloads, `↗` leaves the product.
 *
 * ⚠ **`Saved copy` IS THE ROW'S FACT AND `Kept — N pages` IS THE SERVER'S.**
 * `has_payload` says a BR-BIL-030 instance was stamped at issue;
 * `pdf_page_count` comes off the render and is the thing a clerk posting a
 * cheque actually wants to know before printing. Where the render has not
 * answered, the row says the copy is kept and stops — it never invents a page
 * count, and it never reads a missing ROUTE as a missing RECORD (`DEF-116`).
 */
function TheBillGroup(props: {
  detail: InvoiceDetail;
  document: RenderedBillDocument | undefined;
  t: Translator;
  printHref: string | null;
  printBlockedReason: string | null;
}) {
  const { detail, t } = props;
  const pages = props.document?.pdf_page_count ?? null;
  return (
    <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.theBill")}</Kicker>}>
      <div className="mb-4 flex flex-wrap gap-2" data-bil="the-bill-actions">
        {props.printHref === null ? (
          <>
            {/* BR-SHL-025: a forbidden control renders disabled WITH its
                reason, and the reason is the one the row or the server gave —
                the same fact, in the same order, as the header's controls. */}
            <GuardedButton
              label={t("billing.bill.action.download")}
              reason={props.printBlockedReason ?? t("billing.bill.action.reprintNoDocument")}
              onClick={() => undefined}
            />
            <GuardedButton
              label={t("billing.bill.action.openNewTab")}
              reason={props.printBlockedReason ?? t("billing.bill.action.reprintNoDocument")}
              onClick={() => undefined}
            />
          </>
        ) : (
          <>
            <ButtonAnchor variant="secondary" href={props.printHref} download>
              {t("billing.bill.action.download")}
            </ButtonAnchor>
            <ButtonAnchor
              variant="secondary"
              href={props.printHref}
              target="_blank"
              rel="noreferrer"
            >
              {t("billing.bill.action.openNewTab")}
            </ButtonAnchor>
          </>
        )}
      </div>
      <FactList>
        <Fact label={t("billing.bill.field.savedCopy")}>
          {detail.has_payload ? (
            <span data-bil="saved-copy">
              {pages === null
                ? t("billing.bill.savedCopyKept")
                : t("billing.bill.savedCopyPages", { count: pages })}
            </span>
          ) : (
            <NotRecorded
              label={t("billing.bill.documentNotStamped")}
              why={t("billing.bill.documentNotStampedWhy")}
              ruleRef="BR-BIL-030"
            />
          )}
        </Fact>
        <Fact label={t("billing.bill.field.template")}>
          {detail.template_version !== null ? (
            t("billing.bills.templateVersionValue", { version: detail.template_version })
          ) : (
            <Dash>{t("billing.bills.notIssued")}</Dash>
          )}
        </Fact>
      </FactList>
      <p className="met-panel-hint">{t("billing.bill.panel.documentHint")}</p>
    </Panel>
  );
}

/**
 * GROUP 6 · **Origin**, collapsed — and GROUP 7 · **Record**, below it.
 *
 * Legend 13: *"Where this bill came from and How this bill was produced +
 * Record check, merged and closed by default · B14 32"*. Rule 32 is the reason
 * they are `<details>` rather than panels: *a stated absence is CLOSED by
 * default*, and provenance is what a clerk opens when something looks wrong
 * rather than what they read on the way past.
 *
 * **FIVE ROWS KEPT AND `RUN-0002` STILL LINKED** (p012's carry-over row). The
 * cycle's CODE keeps its place here on legend 4's own instruction — *"the id
 * CY-001 stays under Origin"* — while the header now says the cycle's name.
 */
function OriginGroup(props: {
  detail: InvoiceDetail;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
}) {
  const { detail, t } = props;
  return (
    <ClosedGroup summary={t("billing.bill.panel.originShort")} testId="origin">
      <FactList>
        <Fact label={t("billing.bill.field.billType")}>{billTypeLabel(detail.bill_type, t)}</Fact>
        <Fact label={t("billing.bills.col.cycle")}>{detail.cycle_label ?? <Dash />}</Fact>
        <Fact label={t("billing.bill.field.run")}>
          {/* ⚠ **THIS PRINTED THE RUN'S UUID UNTIL 2026-08-31 (DEF-2716).** A
              run has a HUMAN-FACING number — `bill_runs.run_no`, the `RUN-0001`
              series the PO ruled into existence when OQ-342 closed — and that
              is rule 31's first branch and what this cell shows. It is NULL on
              a run created before that series existed and those are not
              retro-numbered, so the link falls back to naming its destination
              in words. Never to the uuid. */}
          {detail.bill_run_id !== null ? (
            <BillRunLink runId={detail.bill_run_id} t={t} client={props.client} />
          ) : (
            <Dash>{t("billing.bill.noRun")}</Dash>
          )}
        </Fact>
        <Fact label={t("billing.bill.field.serviceDate")}>
          <DateCell
            value={detail.service_date}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        </Fact>
        <Fact label={t("billing.bill.field.issuedAt")}>
          {detail.issued_at !== null ? (
            <DateCell
              value={detail.issued_at}
              timeZone={props.timeZone}
              dateFormat={props.dateFormat}
              withTime
            />
          ) : (
            <Dash>{t("billing.bills.notIssued")}</Dash>
          )}
        </Fact>
      </FactList>
      <p className="met-panel-hint">{t("billing.bill.panel.originHint")}</p>
    </ClosedGroup>
  );
}

/**
 * GROUP 7 · **Record**, collapsed — *How this bill was produced* merged into
 * *Record check*, which is what legend 13 asks for and what p012's carry-over
 * row means by *"merged into one collapsed Record group"*.
 *
 * ⚠ **`Locked copy saved` IS OUT OF ENGINEERING LANGUAGE AND BOTH CHECKS ARE
 * KEPT** (p012, and p017's standing finding: *"'Locked copy saved: Yes' is
 * engineering language for we kept a copy of exactly what they received"*).
 * The fact itself moved UP into `The bill` as *Saved copy*, where a clerk
 * looking for the document will meet it; what stays here is the two version
 * axes and the two integrity verdicts, which are what *Record* is for.
 */
function RecordGroup(props: { detail: InvoiceDetail; t: Translator }) {
  const { detail, t } = props;
  return (
    <ClosedGroup summary={t("billing.bill.panel.record")} testId="record">
      <FactList>
        <Fact label={t("billing.bill.field.templateVersion")}>
          {detail.template_version !== null ? (
            t("billing.bills.templateVersionValue", { version: detail.template_version })
          ) : (
            <Dash>{t("billing.bills.notIssued")}</Dash>
          )}
        </Fact>
        <Fact label={t("billing.bill.field.payloadVersion")}>
          {detail.payload_version !== null ? (
            t("billing.bill.payloadVersionValue", { version: detail.payload_version })
          ) : (
            <Dash>{t("billing.bills.notIssued")}</Dash>
          )}
        </Fact>
      </FactList>
      <p className="met-panel-hint">{t("billing.bill.panel.pinHint")}</p>
      <IntegrityPanel detail={detail} t={t} />
    </ClosedGroup>
  );
}

/**
 * A group a clerk opens rather than reads — B14 rule 32's *closed by default*.
 *
 * A real `<details>`/`<summary>`, not a `useState` toggle: it is keyboard- and
 * screen-reader-operable without a line of script, and the browser's own
 * find-in-page opens it. `RunGap` makes the same choice for the same rule.
 */
function ClosedGroup(props: { summary: string; testId: string; children: ReactNode }) {
  return (
    <details className="mt-4 border-t border-divider pt-3" data-bil={`group-${props.testId}`}>
      <summary className="cursor-pointer font-heading font-bold">{props.summary}</summary>
      <div className="mt-3">{props.children}</div>
    </details>
  );
}

/** One row of the Usage table, derived from the bill and from nothing else. */
interface BilledUsageRow {
  service: string;
  serviceName: string;
  /** `null` when this service's usage lines do not agree on a unit — hard
   *  rule 3. A number with no single unit behind it is not a quantity. */
  quantityDisplay: string | null;
  unit: string | null;
}

/**
 * THIS PERIOD, per service, off the bill's own frozen lines.
 *
 * ⚠ **IT SUMS ONLY `usage` LINES AND ONLY WHERE THE UNIT AGREES.** A tiered
 * water charge is three lines of one quantity in one unit and they sum to the
 * consumption; a base charge carries no quantity at all; and two units inside
 * one service is not a quantity, it is two. Rounding and re-rounding are not
 * this file's business either — `BR-MET-144` trims a QUANTITY's trailing zeros
 * because a quantity's precision is what the meter measured, which is why the
 * sum is formatted through the same rule rather than through `formatMoney`.
 */
function billedUsageRows(detail: InvoiceDetail): BilledUsageRow[] {
  const names = new Map<string, string>(
    (detail.charges_by_service?.services ?? []).map((row) => [row.service, row.service_name]),
  );
  const order: string[] = [];
  const totals = new Map<string, { sum: number; unit: string | null; mixed: boolean }>();
  for (const line of detail.lines) {
    if (line.kind !== "usage") continue;
    const service = line.service;
    if (service === null || service === "") continue;
    if (line.quantity === null || line.unit === null || line.unit === "") continue;
    const quantity = Number(line.quantity);
    if (!Number.isFinite(quantity)) continue;
    const held = totals.get(service);
    if (held === undefined) {
      order.push(service);
      totals.set(service, { sum: quantity, unit: line.unit, mixed: false });
      continue;
    }
    held.sum += quantity;
    if (held.unit !== line.unit) held.mixed = true;
  }
  return order.map((service) => {
    const held = totals.get(service) as { sum: number; unit: string | null; mixed: boolean };
    return {
      service,
      serviceName: names.get(service) ?? service,
      quantityDisplay: held.mixed ? null : trimQuantity(held.sum),
      unit: held.mixed ? null : held.unit,
    };
  });
}

/** BR-MET-144 — a quantity keeps what the meter measured and loses the zeros
 *  the column type added. `8`, never `8.000000`; `17.5`, never `17.500000`. */
function trimQuantity(value: number): string {
  const fixed = value.toFixed(6);
  return fixed.includes(".") ? fixed.replace(/\.?0+$/, "") : fixed;
}

/** This account's usage series for one service code, or `null`. */
function seriesForService(payload: UsagePayload | undefined, service: string): UsageSeries | null {
  if (payload === undefined) return null;
  return payload.series.find((row) => row.service.code === service) ?? null;
}

/** The drawn `· 31 days` beside the service period. Whole days, inclusive of
 *  both ends, which is what `bill_payload["days"]` already prints. `null`
 *  rather than a guess when either date is unreadable. */
function periodDays(detail: InvoiceDetail): number | null {
  const start = Date.parse(`${detail.period_start}T00:00:00Z`);
  const end = Date.parse(`${detail.period_end}T00:00:00Z`);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return null;
  return Math.round((end - start) / 86400000) + 1;
}

/** The first of two served strings that is actually a string. */
function firstFilled(...values: (string | null | undefined)[]): string | null {
  for (const value of values) {
    if (typeof value === "string" && value.trim() !== "") return value;
  }
  return null;
}

/**
 * DEF-2716 — THE RUN THIS BILL CAME FROM, NAMED AND REACHABLE.
 *
 * ⚠ **THIS CELL PRINTED `bill_run_id` AS A BARE UUID UNTIL 2026-08-31**, under
 * a comment that was true when it was written — EP-BIL-01's run screens did not
 * exist, and *"a link onto a placeholder is 'built is not wired' wearing a
 * different hat"*. `CR-051` built them; nothing re-read the sentence, which is
 * hard-won law 1. `B14` rule 31 (PO 2026-08-30, *"no Databse ID on screen -
 * that is a rule"*) then made the leftover a breach as well.
 *
 * **WHY IT FETCHES.** Rule 31's FIRST branch is the one that applies here:
 * *"where the reference is genuinely what a user needs … it has a HUMAN-FACING
 * number and that is what is shown"*. A run has one — `bill_runs.run_no`, the
 * `RUN-0001` series `OQ-342` closed on the PO's own words *"A: a real series
 * (RUN-0001, like RT-001)"* — and `GET /invoices/{id}` carries only the key. So
 * the number is read from the run itself, through the SAME query key the wizard
 * uses, which means opening the run afterwards costs no second request.
 *
 * **AND IT DEGRADES INTO WORDS, NEVER INTO THE KEY.** Three ways this read can
 * answer nothing — the run predates the series and `run_no` is null, the reader
 * lacks permission on runs, the route is unreachable — and all three land on
 * *"Open the run"*, which is true in every one of them. The link is rendered
 * before the answer arrives for the same reason: a clerk should not wait on a
 * label to reach the screen the row is about.
 */
function BillRunLink(props: { runId: string; t: Translator; client?: ApiClient }) {
  const { t } = props;
  const tenantPath = useTenantPath();
  const runQuery = useQuery({
    queryKey: billRunDetailKey(props.runId),
    queryFn: () => getBillRun(props.runId, props.client ?? api),
    // A run this reader cannot open is an answer, not a flaky network.
    retry: false,
  });
  const runNo = runQuery.data?.run_no ?? null;
  return (
    <span data-bil="bill-run">
      <InlineLinkTo to={tenantPath(billRunPath(props.runId))}>
        {runNo !== null && runNo !== "" ? runNo : t("billing.bill.openRun")}
      </InlineLinkTo>
    </span>
  );
}

/**
 * US-BIL-030 — the two guarantees the bill run makes about every bill, asked
 * of THIS bill and answered on the screen a clerk already has open.
 *
 * **WHY IT IS ON A SCREEN AT ALL.** BR-BIL-032 says the stamped copy of the
 * bill ties out to its charge lines and that *"drift can never be silent"*.
 * `pipeline.tie_out_document` and `pipeline.balanced_handoff` compute exactly
 * that, and on 2026-08-16 neither had a caller outside its own test file — so
 * the rule was enforced against fixtures and against no bill this product ever
 * produced. A guarantee nobody asks for is a guarantee nobody has.
 *
 * **NO ID, NO RULE NUMBER, NO JARGON ON THE PAGE.** A clerk reads "the saved
 * bill matches its charge lines", not "BR-BIL-032 tie-out": ids are the ticket
 * vocabulary (CLAUDE.md §Screen IDs) and a utility clerk shown our filing
 * system learns nothing. The rule ids live in this comment and in the server's
 * `br_ref`, which is engineering-facing.
 *
 * **THREE STATES, AND THE MIDDLE ONE IS THE POINT.** `true` says checked and
 * matching; `false` says they do not match, with BOTH figures and their
 * currency so the reader can see the size of it; `null` says NOT CHECKED with
 * the server's own reason beside it — never "no", which would accuse a draft
 * of a fault it cannot have.
 */
function IntegrityPanel(props: { detail: InvoiceDetail; t: Translator }) {
  const { detail, t } = props;
  // ⚠ FOUND BY A BROWSER, NOT BY A TEST (hard-won law 6). The first cut read
  // `detail.integrity.document_ties_out` directly and the whole bill screen
  // white-screened with *"Cannot read properties of undefined"* against a
  // server one version behind — every unit test passed, because every fixture
  // supplied the block. A missing block is server/client skew, which is a
  // deployment fault and not this bill's; the screen must still open, and the
  // one panel that cannot answer must SAY it cannot rather than take the page
  // down or, worse, render a confident verdict off `undefined`.
  const block = detail.integrity ?? null;
  const reasonFor = (field: string) =>
    block?.unavailable.find((gap) => gap.field === field)?.why ?? null;

  function verdict(value: boolean | null, field: string) {
    if (value === null) {
      return (
        <AwaitsCell
          label={t("billing.bill.integrityUnknown")}
          why={reasonFor(field) ?? t("billing.bill.integrityUnknown")}
        />
      );
    }
    return (
      <StatusPill tone={value ? "success" : "danger"}>
        {value ? t("billing.bill.integrityYes") : t("billing.bill.integrityNo")}
      </StatusPill>
    );
  }

  return (
    <Panel as="section">
      <h3>{t("billing.bill.panel.integrity")}</h3>
      <FactList>
        <Fact label={t("billing.bill.field.documentTiesOut")}>
          {verdict(block?.document_ties_out ?? null, "document_ties_out")}
        </Fact>
        <Fact label={t("billing.bill.field.postingBalanced")}>
          {verdict(block?.posting_balanced ?? null, "posting_balanced")}
        </Fact>
      </FactList>
      {/* The FIGURES, only when they disagree. "It does not tie out" sends
          somebody looking; "247.87 USD over 3 lines against 999.99 USD over 1"
          does not. Both amounts carry the bill's own currency — a money figure
          without one is not an amount (CLAUDE.md #2). */}
      {block?.document_ties_out === false && (
        <p className="met-panel-hint" role="alert">
          {t("billing.bill.integrityFigures", {
            // ⚠ DEF-968 (CR-043 finding 2). These two figures used to be
            // interpolated RAW: the wire carries the stored decimal string, so a
            // clerk read *"Saved bill: 64.570000 USD over 0 line(s)"*. Hard rule
            // 2 is money stored 4, percentages 6, **both DISPLAY 2**, and
            // `formatMoney` is the one place that boundary lives (BR-SHL-023 /
            // BR-TEN-080) — it also brings the currency symbol, so the trailing
            // ` {{currency}}` in the sentence is now redundant and the key has
            // been reworded with it.
            //
            // ⚠ **THIS IS NOT DEF-894's ANSWER AND MUST NOT BECOME IT.**
            // `BR-MET-144` trims a QUANTITY's trailing zeros — `8`, never
            // `8.00` — because a quantity's precision is what the meter
            // measured. Money's precision is a property of the currency, so
            // `64.57` keeps both places and `148.6` PADS to `$148.60`. Two
            // rules, two formatters, and reaching for the wrong one is
            // invisible to every gate in this repo.
            payload:
              block.payload_total === null
                ? "—"
                : formatMoney(block.payload_total, block.currency),
            rows: block.rows_total === null ? "—" : formatMoney(block.rows_total, block.currency),
            payloadLines: block.payload_line_count ?? "—",
            rowLines: block.row_line_count ?? "—",
          })}
        </p>
      )}
      <p className="met-panel-hint">{t("billing.bill.panel.integrityHint")}</p>
    </Panel>
  );
}

/**
 * BR-BIL-016's per-channel queue.
 *
 * ⚠ **THIS PANEL WAS BUILT WITH THE SCREEN AND DREW NOTHING FOR FIVE DAYS.**
 * `issue.py` has written a delivery row for every bill it issued since
 * 2026-08-11 and `GET /invoices/{id}` served a hardcoded `deliveries: null`, so
 * every branch below except the absence branch was unreachable — the engine
 * wrote, the screen could read, and nothing asked the question (US-BIL-023/024,
 * landed 2026-08-16). This comment used to explain the null as *"the queue does
 * not exist yet (r10 #8 has no table)"*, which was true when written and had
 * been false since the table landed.
 *
 * **THE THREE STATES ARE THREE DIFFERENT SENTENCES and none of them is a zero:**
 *   · `null` — the delivery queue cannot be asked on this deployment. Nothing
 *     is drawn, because an empty table would claim the bill was never sent.
 *   · `[]` — the queue WAS asked and holds nothing. True of a draft: bills join
 *     the queue at issue, and the panel says exactly that.
 *   · rows — where the bill went, per channel.
 *
 * **AND `queued` IS THE FINAL STATE, WHICH THE PANEL SAYS ON SCREEN.** R2 has
 * no dispatcher (US-NOT-002) and no provider connection (US-NOT-003), both out
 * of the release by PO ruling, so a queued row means the bill is ready to go
 * out — not that a send failed. A clerk reading "Queued" against a bill posted
 * last week would otherwise reasonably conclude something is stuck.
 */
/**
 * ══════════════════════════════════════════════════════════════════════════
 * `CR-101-BRC03` — THE SENT TAB. A MOVE PLUS ONE NEW GROUP, NOT A REBUILD.
 * ══════════════════════════════════════════════════════════════════════════
 * Blueprint entry 02.5, `ENTIRELY NEW`: *"a new tab, split out of Document"*.
 * The table below is the one that was the LAST panel of the FIRST tab, rows and
 * all; what is new is where it lives, that the channel and status read as
 * words, and the group beneath it saying how this customer hears from us.
 *
 * ⚠ **THE SECOND GROUP IS A PROPOSAL AND THE DRAWING SAYS SO** (p028: *"One
 * group here is a proposal, not a redraw … is NEW and needs a customers
 * read"*). The read exists — `GET /accounts/{id}` already carries `paperless`,
 * the contacts and the derived address — so it costs one query this screen
 * already makes for its header.
 */
function SentTab(props: {
  detail: InvoiceDetail;
  /** `undefined` while the account read is in flight or refused — the second
   *  group then states that rather than drawing empty rows. */
  account: AccountDetail | undefined;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  writeBlockedReason?: string | null;
  client?: ApiClient;
  onMarkedReturned?: () => void;
}) {
  return (
    <>
      <DeliveryPanel
        detail={props.detail}
        t={props.t}
        timeZone={props.timeZone}
        dateFormat={props.dateFormat}
        writeBlockedReason={props.writeBlockedReason}
        client={props.client}
        onMarkedReturned={props.onMarkedReturned}
      />
      <HowTheyHearPanel account={props.account} t={props.t} />
    </>
  );
}

/**
 * HOW THEY HEAR FROM US — the paperless election and the two addresses a bill
 * would actually go to.
 *
 * ⚠ **THE POST ROW IS DERIVED, NEVER STORED ON THE ACCOUNT (hard rule 8).** It
 * is `premise_address` + `unit_label`, which the accounts read produced by
 * walking to `premises`. ⚠ **AND IT IS THE SERVICE ADDRESS, WHICH IS NOT
 * ALWAYS WHERE THE BILL GOES** — hard rule 8's first exception is
 * `customers.addresses kind='mailing'`, *"where the BILL goes, which for a
 * landlord is another building"*. That row is not on this payload, so this
 * group names what it IS showing and does not claim to be the envelope.
 */
function HowTheyHearPanel(props: { account: AccountDetail | undefined; t: Translator }) {
  const { account, t } = props;
  const contact = account === undefined ? null : primaryContact(account.contacts);
  return (
    <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.howTheyHear")}</Kicker>}>
      {account === undefined ? (
        <NotRecorded
          label={t("billing.bill.howTheyHearAbsent")}
          why={t("billing.bill.howTheyHearAbsentWhy")}
          ruleRef="BR-CUS-054"
        />
      ) : (
        <FactList>
          <Fact label={t("billing.bill.field.paperless")}>
            {account.paperless === undefined ? (
              <Dash />
            ) : account.paperless ? (
              t("billing.bill.paperlessElected")
            ) : (
              t("billing.bill.paperlessNotElected")
            )}
          </Fact>
          <Fact label={t("billing.bill.field.email")}>
            {contact?.email != null && contact.email !== "" ? contact.email : <Dash />}
          </Fact>
          <Fact label={t("billing.bill.field.post")}>
            {account.premise_address != null && account.premise_address !== "" ? (
              account.unit_label != null && account.unit_label !== ""
                ? `${account.premise_address}, ${account.unit_label}`
                : account.premise_address
            ) : (
              <Dash />
            )}
          </Fact>
        </FactList>
      )}
    </Panel>
  );
}

/**
 * A SERVED CODE, AS A WORD — and a stated absence when no word exists.
 *
 * ⚠ **`DEF-BIL-5237` IS WHAT THIS COMPONENT IS FOR, AND THE MECHANISM MATTERS
 * MORE THAN THE TWO KEYS.** The delivery rows resolved their channel and their
 * status through `t(key, { defaultValue: rawValue })`, and
 * `billing.bill.channel.*` and `billing.bill.delivery.*` held **0 keys in all
 * eleven catalogues** — so the fallback was not a fallback, it was the only
 * path there had ever been, and a clerk read `pdf_print` and `queued` in every
 * language. It is the fourth sighting of one mechanism in this module after
 * `DEF-518`, `DEF-2448` and `DEF-BIL-5233`.
 *
 * **So the default is EMPTY, not the code.** A missing word then renders as a
 * stated absence instead of a machine code (B14 rule 32), and the code rides on
 * `title` where support can reach it and no clerk reads it as the value of the
 * field — which is rule 31's own sentence for exactly this case.
 */
function CodeWord(props: { prefix: string; code: string; t: Translator }) {
  const word = props.t(`${props.prefix}.${props.code}`, { defaultValue: "" });
  if (word !== "") {
    return <>{word}</>;
  }
  // ⚠ **A VALUE WITH NO WORD IS ONLY SUPPRESSED WHEN IT IS A MACHINE CODE, AND
  // THE TEST IS THE SHAPE OF THE STRING.** B14 rule 32 bans an internal code in
  // clerk-facing copy; it does not ban TEXT. `credit_notes.reason` is a free
  // text column that the correction engine happens to fill with an enum, and a
  // tenant's own sentence in it is a reason, not a leak. So `wrong_read` is
  // held back and *"Meter misread"* is printed.
  if (!MACHINE_CODE.test(props.code)) {
    return <>{props.code}</>;
  }
  return (
    <span
      data-bil="code-without-a-word"
      title={props.code}
      className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]"
    >
      {props.t("billing.bill.codeUnreadable")}
    </span>
  );
}

/** `snake_case` or a bare lower-case token — what an enum looks like and what a
 *  sentence does not. */
const MACHINE_CODE = /^[a-z0-9]+(_[a-z0-9]+)*$/;

function DeliveryPanel(props: {
  detail: InvoiceDetail;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  writeBlockedReason?: string | null;
  client?: ApiClient;
  onMarkedReturned?: () => void;
}) {
  const { detail, t } = props;
  // US-PAY-016 — which envelope is being marked, and what the last mark did.
  const [marking, setMarking] = useState<string | null>(null);
  const [outcome, setOutcome] = useState<MarkReturnedOutcome | null>(null);
  if (detail.deliveries === null) {
    return (
      <ArrivesWith
        title={t("billing.bill.panel.delivery")}
        message={t("billing.bill.arrives.delivery")}
      />
    );
  }
  return (
    <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.delivery")}</Kicker>}>
      {detail.deliveries.length === 0 ? (
        <p className="met-panel-hint">{t("billing.bill.deliveryEmpty")}</p>
      ) : (
        <>
          <PlainTable>
            <thead>
              <tr>
                <th>{t("billing.bill.col.channel")}</th>
                <th>{t("billing.bills.col.status")}</th>
                {/* "Queued", not "When": the column is the time the row JOINED
                  the queue. Nothing sends, so a sent time does not exist and a
                  vaguer heading would invite it to be read as one. */}
                <th>{t("billing.bill.col.queuedAt")}</th>
                {/* US-PAY-016 — the post office's answer, and the action that
                  records it. BR-PAY-018 marks a DELIVERY RECORD returned, so
                  this is the row that owns it. */}
                <th>{t("billing.bill.col.returned")}</th>
                <th>{t("billing.bill.col.action")}</th>
              </tr>
            </thead>
            <tbody>
              {detail.deliveries.map((row) => (
                <tr key={row.id}>
                  <td>
                    <CodeWord prefix="billing.bill.channel" code={row.channel} t={t} />
                  </td>
                  <td>
                    <CodeWord prefix="billing.bill.delivery" code={row.status} t={t} />
                  </td>
                  <td>
                    {row.at !== null ? (
                      <DateCell
                        value={row.at}
                        timeZone={props.timeZone}
                        dateFormat={props.dateFormat}
                        withTime
                      />
                    ) : (
                      <Dash />
                    )}
                  </td>
                  <td>
                    {/* A DATE or nothing — never "No", which would claim the
                      carrier delivered it. Nobody has reported success on any
                      channel in this release. */}
                    {row.returned_at !== null ? (
                      <DateCell
                        value={row.returned_at}
                        timeZone={props.timeZone}
                        dateFormat={props.dateFormat}
                      />
                    ) : (
                      <Dash />
                    )}
                  </td>
                  <td>
                    <GuardedButton
                      label={t("payments.returnedMail.single.action")}
                      // BR-SHL-025: the reason travels with the refusal. Three
                      // different reasons, and each is the TRUE one for that row:
                      // this role may not write · an email bounce is a provider
                      // fact, not a clerk's observation · it is already marked.
                      reason={props.writeBlockedReason ?? markReturnedRefusal(row, t)}
                      onClick={() => {
                        setOutcome(null);
                        setMarking(row.id);
                      }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </PlainTable>
          {/* Said ONCE, BELOW the rows. ⚠ `DEF-NOT-10537`, 2026-10-22: it read
            *"Nothing on this deployment sends bills — there is no dispatcher"*,
            false once email sends; each row's own status says what happened,
            and this is the blueprint's one sentence — *"Printing is the
            channel every bill has."* (BR-BIL-036). */}
          <p className="met-panel-hint">{t("billing.bill.deliveryQueuedOnly")}</p>
        </>
      )}
      {outcome !== null && <ReturnedMailOutcome outcome={outcome} />}
      {marking !== null && (
        <MarkReturnedModal
          messageId={marking}
          // BR-TEN-043: the field is REQUIRED and this screen proposes the
          // bill's own service date rather than reading a clock — a stack
          // worked on Wednesday is still Tuesday's stack, and the clerk types
          // over it either way.
          proposedDate={detail.service_date ?? ""}
          dateFormat={props.dateFormat}
          client={props.client}
          onClose={() => setMarking(null)}
          onMarked={(result) => {
            setOutcome(result);
            setMarking(null);
            props.onMarkedReturned?.();
          }}
        />
      )}
    </Panel>
  );
}

/**
 * The record: every `invoice_lines` row, grouped by service the way the bill
 * prints them, with the quantity's EXPLICIT unit (CLAUDE.md #3), the taxable
 * flag and — the point of the tab — the STAMPED GL account (BR-BIL-010). The
 * stamp is issue-time truth: after the mapping is edited from 4100 to 4101, an
 * already-issued line still shows 4100, and US-BIL-026 TC-2 is exactly that.
 */
/**
 * ══════════════════════════════════════════════════════════════════════════
 * CR-053 TASK 6 — EVERY SCENARIO ON ONE SCREEN
 * ══════════════════════════════════════════════════════════════════════════
 * The Product Owner's sentence, verbatim, is the whole specification of this
 * tab: *"on this screen you will ahve to cosndier all scenarios - utilty
 * services charges, charge code raletd, discount related, taxes related,
 * previosu due, later payment date etc"*.
 *
 * **"CONSIDER ALL SCENARIOS" IS NOT "DRAW SIX PANELS ALWAYS".** A bill that
 * carries no discount must not grow an empty Discounts box, and a bill that
 * carries one must not hide it inside a group called *Taxes & fees*. So each
 * scenario is drawn WHERE IT OCCURS, and every scenario the reader might
 * reasonably expect and that this bill does not have SAYS SO (G38 — a stated
 * absence, never a silent one). Six things a clerk can be asked about, in the
 * order the question usually arrives:
 *
 *   1  what did each SERVICE cost           → `ChargesByServicePanel`
 *   2  what is every LINE, in full          → the lines table (task 8)
 *   3  whose TAX is on this bill            → `TaxesByAuthorityPanel`
 *   4  what did the customer already owe    → `SummaryPanel`, above the tab
 *   5  when is it DUE, and what if it is late → `DatesGroup`, on Document
 *   6  what was CORRECTED after issue       → `AdjustmentsPanel`
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE ARITHMETIC RULE, AND IT IS A PROHIBITION
 * ══════════════════════════════════════════════════════════════════════════
 * PO 2026-08-30: *"when you build billing logic ensue you use r1 to r7 that we
 * build and wire it"*. For a document that is a prohibition — **the screen
 * displays what the server resolved.** Nothing in this file computes,
 * re-derives or re-sums a money figure:
 *
 *   * per-service subtotals come from `charges_by_service`, where the server
 *     sums Σ of the ROUNDED lines (B4.4 + B4's 2026-08-11 ruling, so a
 *     customer adding the printed column down gets the printed subtotal);
 *   * the tie-out is the SERVER's verdict, rendered as it is given. A
 *     disagreement is REPORTED — never reconciled, never hidden — because a
 *     screen that balanced the books would destroy the evidence BR-BIL-032
 *     exists to surface;
 *   * the tax total is `invoices.tax_total`, and the per-AUTHORITY subtotal is
 *     stated as not served rather than added up here (`OQ-1190`).
 */
function LinesTab(props: { detail: InvoiceDetail; t: Translator; timeZone: string; dateFormat: RegionalDateFormat }) {
  const { detail, t } = props;
  const tenantPath = useTenantPath();
  if (detail.lines.length === 0) {
    // An empty line table on a bill is not a normal state — a bill with no
    // lines has no charges — so it says so rather than rendering a bare header.
    return <p className="met-panel-hint">{t("billing.bill.linesEmpty")}</p>;
  }
  const groups = groupLinesByService(detail.lines);
  return (
    <>
      <ChargesByServicePanel detail={detail} t={t} />
      <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.lines")}</Kicker>}>
        {/* A handle of its own, so a test can slice THIS table rather than
            slicing from a heading it does not own — the heading moved once
            already in this change and took a test helper with it. */}
        <PlainTable data-bil="bill-lines">
          <thead>
            <tr>
              {/* ⚠ **FIVE COLUMNS SINCE 2026-09-14 (`CR-101-BRC03`), AND NOT
                  ONE FIELD IS LOST** — blueprint 02.2 legend ①: *"Accounting
                  code and Rate version come out of their own columns and ride
                  UNDER THE DESCRIPTION, the way the accounting code already
                  shares one cell today."* `Rate version` was the WIDEST column
                  in the table (324 px of 1,086, measured) and the least-used
                  thing on the screen, and it wrapped to two lines on most rows.
                  `Taxable` is KEPT even though it reads `Yes` on every row of a
                  typical bill: it is a dash on a tax line because B4.2 makes
                  the question inapplicable, and that distinction is worth a
                  column. */}
              <th>{t("billing.bill.col.description")}</th>
              <th>{t("billing.bill.col.quantity")}</th>
              <th className="[&&]:text-right">{t("billing.bill.col.unitPrice")}</th>
              <th className="[&&]:text-right">{t("billing.bill.col.amount")}</th>
              <th>{t("billing.bill.col.taxable")}</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((group) => (
              <BillLineGroup
                key={group.service}
                service={group.service}
                lines={group.lines}
                currency={detail.currency}
                t={t}
                assetHref={(assetId) => tenantPath(assetDetailPath(assetId))}
              />
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={3}>{t("billing.bills.col.subtotal")}</td>
              <td className="[&&]:text-right">
                <MoneyCell amount={detail.subtotal} currency={detail.currency} />
              </td>
              <td />
            </tr>
            <tr>
              <td colSpan={3}>{t("billing.bills.col.tax")}</td>
              <td className="[&&]:text-right">
                <MoneyCell amount={detail.tax_total} currency={detail.currency} />
              </td>
              <td />
            </tr>
            {/* ⚠ **THE TOTAL IS BOLD NOW, AND IT IS NOT A PREFERENCE.** It
                rendered at weight 400 / 13.5px while the Amount panel's
                *Total due* — the same figure, six inches up — rendered at
                800 / 15px, which is p020's alignment finding 4, measured in a
                browser on this branch and confirmed. The last row of a money
                column is the one a reader's eye stops on. */}
            <tr className="[&_td]:font-heading [&_td]:font-extrabold" data-bil="lines-total">
              <td colSpan={3}>{t("billing.bills.col.total")}</td>
              <td className="[&&]:text-right">
                <MoneyCell amount={detail.total} currency={detail.currency} />
              </td>
              <td />
            </tr>
          </tfoot>
        </PlainTable>
        <p className="met-panel-hint">{t("billing.bill.panel.linesHint")}</p>
      </Panel>
      <TaxesByAuthorityPanel detail={detail} t={t} />
      {/* ⚠ **`When this is due` LEFT THIS TAB (`CR-105-BRC03`, p012's carry-over
          map — MOVED, not removed).** *"From Charges into Dates on Document,
          where the other dates already are."* Its three rows and its late-terms
          sentence are `DatesGroup`, unchanged; what it leaves behind is the
          answer to *why was the due date on a tab about charges*. */}
      <AdjustmentsPanel adjustments={detail.adjustments} currency={detail.currency} t={t} />
    </>
  );
}

/**
 * CR-053 task 6, first question — WHAT DID EACH SERVICE COST.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * THE BILL-LEVEL BUCKET IS THE INTERESTING HALF, NOT THE SERVICE ROWS
 * ══════════════════════════════════════════════════════════════════════════
 * `charges_by_service` groups on `invoice_lines.service_id`, which
 * `stages/assemble_document._service_id_for` writes for `usage` and `base`
 * lines and for nothing else. Everything else lands in one stated bucket, and
 * WHY a figure is outside every service heading is the question a clerk
 * actually has. Two different answers live in that one bucket:
 *
 *   · **A tax is bill-level BY RULING** — PO 2026-08-11, *"Tax rates are for
 *     bill not for service"* — and nothing in the database records which
 *     service a tax line belongs to. It is not split here and must not be.
 *   · **A `minimum_adjustment` is bill-level BY DEFECT (`DEF-2429`).**
 *     `BR-RAT-028` computes the per-service minimum PER SERVICE, and the line
 *     stores `service_id = NULL`, so money that belongs under a service
 *     heading sits outside every one of them. The bill's TOTAL is unaffected,
 *     which is exactly why nothing was ever red about it.
 *
 * **THE SECOND ONE IS RENDERED TRUTHFULLY AND IS NOT REPAIRED IN THE
 * BROWSER.** Reassigning the line to a service on screen would produce a
 * per-service subtotal that no server, no GL posting and no printed bill
 * agrees with — a screen and an engine disagreeing about a customer's money,
 * which is the exact failure `_charges_by_service` refuses by name. So the
 * bucket names its kinds in plain words and, when the minimum adjustment is
 * among them, says where the money belongs and where it is.
 */
function ChargesByServicePanel(props: { detail: InvoiceDetail; t: Translator }) {
  const { detail, t } = props;
  // ⚠ GUARDED, for `IntegrityPanel`'s reason two panels down: a server one
  // deploy behind omits the block, and an unguarded read of a new block is
  // what white-screened this page once already (found in a browser, not by a
  // test — every fixture supplied it).
  const block = detail.charges_by_service ?? null;
  if (block === null) {
    return (
      <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.byService")}</Kicker>}>
        <NotRecorded
          label={t("billing.bill.byServiceAbsent")}
          why={t("billing.bill.byServiceAbsentWhy")}
          ruleRef="BR-BIL-032"
        />
      </Panel>
    );
  }
  const hasMinimum = block.bill_level.kinds.includes("minimum_adjustment");
  const split = billLevelSplit(block.bill_level);
  return (
    <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.byService")}</Kicker>}>
      <PlainTable data-bil="charges-by-service">
        <thead>
          <tr>
            <th>{t("billing.bill.col.service")}</th>
            <th className="[&&]:text-right">{t("billing.bill.col.lineCount")}</th>
            <th className="[&&]:text-right">{t("billing.bill.col.amount")}</th>
          </tr>
        </thead>
        <tbody>
          {block.services.length === 0 && (
            // A bill with no service-bearing line answers `services: []`, and
            // the server refuses to write a zero-valued row for a service it
            // never touched. The screen keeps that distinction.
            <tr>
              <td colSpan={3}>{t("billing.bill.byServiceNone")}</td>
            </tr>
          )}
          {block.services.map((row) => (
            <tr key={row.service} data-bil="service-subtotal" data-service={row.service}>
              <td>{t(`rating.service.${row.service}`, { defaultValue: row.service_name })}</td>
              <td className="[&&]:text-right tabular-nums">{row.line_count}</td>
              <td className="[&&]:text-right">
                {/* THE SERVER'S OWN 2dp FIGURE, rounded once, by it. Handing
                    `subtotal` (the 4dp stored scale) to `MoneyCell` would
                    round a second time in a second place — one money path
                    (BR-SHL-023). */}
                <MoneyCell amount={row.subtotal_display} currency={block.currency} />
              </td>
            </tr>
          ))}
          {/* DEF-BIL-9346 — the bill's discounts are a row of their own,
              named as the Charges tab names them (DEF-BIL-9339), never
              *Charged to the bill*. Both figures are the server's. */}
          {split.discounts !== null && (
            <tr data-bil="bill-level-discounts">
              <td>{t("billing.bill.group.discounts")}</td>
              <td className="[&&]:text-right tabular-nums">{split.discounts.lineCount}</td>
              <td className="[&&]:text-right">
                <MoneyCell amount={split.discounts.subtotalDisplay} currency={block.currency} />
              </td>
            </tr>
          )}
          {(split.discounts === null || split.lineCount > 0) && (
            <tr data-bil="bill-level-subtotal">
              <td>
                {t("billing.bill.byServiceBillLevel")}
                <span className="mt-1 block text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                  {split.kinds.length === 0
                    ? t("billing.bill.byServiceBillLevelNone")
                    : split.kinds
                        .map((kind) => t(`billing.bill.kind.${kind}`, { defaultValue: kind }))
                        .join(" · ")}
                </span>
              </td>
              <td className="[&&]:text-right tabular-nums">{split.lineCount}</td>
              <td className="[&&]:text-right">
                <MoneyCell amount={split.subtotalDisplay} currency={block.currency} />
              </td>
            </tr>
          )}
        </tbody>
      </PlainTable>
      {hasMinimum && (
        // DEF-2429, said in the words a clerk can act on and with the rule id
        // only on the element for support (DEF-1931's test).
        <p
          className="mt-2 border-l-2 border-l-warning-500 bg-warning-100 px-3 py-2 text-base leading-prose"
          role="note"
          data-bil="minimum-misfiled"
          data-br-ref="BR-RAT-028 · DEF-2429"
        >
          {t("billing.bill.byServiceMinimumMisfiled")}
        </p>
      )}
      {/* THE TIE-OUT, AS THE SERVER GIVES IT. `ties_out` false is not an error
          state of this screen — it is a fact about this bill, and the two
          figures and their difference are shown so the size of it is visible.
          Nothing here adjusts either side. */}
      <p
        className={
          block.tie_out.ties_out
            ? "met-panel-hint"
            : "mt-2 border-l-2 border-l-danger-500 bg-danger-100 px-3 py-2 text-base leading-prose"
        }
        role={block.tie_out.ties_out ? undefined : "alert"}
        data-bil="charges-tie-out"
        data-ties-out={String(block.tie_out.ties_out)}
      >
        {block.tie_out.ties_out
          ? t("billing.bill.byServiceTiesOut")
          : t("billing.bill.byServiceDoesNotTieOut", {
              lines: formatMoney(block.tie_out.lines_total, block.currency),
              bill: formatMoney(block.tie_out.invoice_total, block.currency),
            })}
      </p>
    </Panel>
  );
}

/**
 * CR-053 task 6, third question — WHOSE TAX IS ON THIS BILL.
 *
 * `BR-BIL-069` and the PO's OQ-116 closure — *"For each atheority have
 * separate account and tagging"* — make the authority a fact about the LINE,
 * and CR-053 task 7 began serving it on 2026-08-30. Before that the Charges
 * tab printed *"Tax Local"* and a clerk answering *"who is this paid to?"* had
 * nowhere to look.
 *
 * ⚠ **THE PER-AUTHORITY SUBTOTAL IS SERVED NOW, AND IT IS STILL NOT ADDED UP
 * HERE — `OQ-1190` CLOSED, PO ruling 2026-08-31.** Verbatim: *"(a) Add a
 * per-authority subtotal to the bill and the finance screens"*. Until that
 * ruling this panel GROUPED by authority and stated in plain words that a
 * total per authority did not exist, because none did.
 *
 * **What changed is the SERVER, not this file's posture.**
 * `apps/billing/selectors._taxes_by_authority` publishes one bucket per
 * `invoice_lines.tax_id` — the authority's name, its line count, Σ of the
 * ROUNDED lines (B4.4 + B4's 2026-08-11 ruling) and its own tie-out against
 * `invoices.tax_total`. This panel DISPLAYS those figures and derives none of
 * them, which is the R1–R7 prohibition the PO stated on 2026-08-30: summing a
 * money column in the browser would be a second implementation of a signed
 * rounding rule, living where no golden test can reach it.
 *
 * ⚠ **AND WE ARGUED FOR LESS THAN THIS AND WERE OVERRULED.** The
 * recommendation put to the PO was the finance screens ONLY — a customer does
 * not act on a figure they cannot change. The answer was BOTH surfaces. It is
 * recorded here so a later tidy-up does not read the bill half as scope creep
 * and quietly delete it.
 *
 * **The order is the server's**, alphabetical by the authority's own name with
 * an unreadable one last, so two reads of an unchanged bill draw the same
 * table.
 *
 * **AND TAXES ARE NOT SPLIT ACROSS SERVICES.** PO ruling 2026-08-11, *"Tax
 * rates are for bill not for service"*; `invoice_lines` records no service on
 * a tax row, so any split would be this screen inventing an attribution the
 * database refuses to store.
 */
/**
 * The row key for tax lines carrying no `tax_id` — real on bills issued before
 * `BR-BIL-069`'s column existed. It is a RENDER key and never a displayed
 * value; the cell for such a row states the absence (B14 rule 31).
 */
const UNSTAMPED_TAX = "__unstamped__";

function TaxesByAuthorityPanel(props: { detail: InvoiceDetail; t: Translator }) {
  const { detail, t } = props;
  const taxes = detail.lines.filter((line) => line.kind === "tax");
  if (taxes.length === 0) {
    // A stated absence, not a hidden panel: "this bill charges no tax" is an
    // answer, and a missing panel is not (G38).
    return (
      <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.taxes")}</Kicker>}>
        <p className="met-panel-hint">{t("billing.bill.taxesNone")}</p>
      </Panel>
    );
  }
  // ⚠ GUARDED, for `ChargesByServicePanel`'s reason: a server one deploy behind
  // omits the block, and an unguarded read of a new block is what white-screened
  // this page once already (found in a browser, not by a test — every fixture
  // supplied it). Without the block the panel falls back to what it drew before
  // 2026-08-31 — the lines, grouped, and the absence STATED.
  const block = detail.taxes_by_authority ?? null;

  // ⚠ THE KEY IS THE `tax_id`, NEVER THE NAME. Two authorities can share a
  // display name across tenants and one authority can be renamed; the stamp is
  // the id (BR-BIL-069). `null` is its own bucket — a tax line whose authority
  // could not be resolved is a fact, not a member of the first group.
  const linesFor = new Map<string, InvoiceLineRow[]>();
  for (const line of taxes) {
    const key = line.tax_id ?? UNSTAMPED_TAX;
    linesFor.set(key, [...(linesFor.get(key) ?? []), line]);
  }
  // THE ORDER IS THE SERVER'S when it sent one, so the table a clerk reads and
  // the figures they file from are in one order. Without the block, insertion
  // order, which is what this panel always used.
  const keys =
    block === null
      ? [...linesFor.keys()]
      : [
          ...block.authorities.map((row) => row.tax_id),
          ...(linesFor.has(UNSTAMPED_TAX) ? [UNSTAMPED_TAX] : []),
        ];
  const subtotalOf = new Map<string, { subtotal_display: string; authority?: string | null }>(
    block?.authorities.map((row) => [row.tax_id, row]) ?? [],
  );
  if (block !== null && block.unstamped.line_count > 0) {
    // The unstamped bucket gets its subtotal row too. Its money is on the bill
    // and in the tie-out, so leaving it without one would make the column stop
    // adding up in front of the reader.
    subtotalOf.set(UNSTAMPED_TAX, block.unstamped);
  }
  const authorityOf = (key: string) =>
    subtotalOf.get(key)?.authority ?? linesFor.get(key)?.[0]?.tax_authority ?? null;

  return (
    <Panel as="section" title={<Kicker as="span">{t("billing.bill.panel.taxes")}</Kicker>}>
      <PlainTable data-bil="taxes-by-authority">
        <thead>
          <tr>
            <th>{t("billing.bill.col.authority")}</th>
            <th>{t("billing.bill.col.description")}</th>
            <th className="[&&]:text-right">{t("billing.bill.col.amount")}</th>
          </tr>
        </thead>
        <tbody>
          {keys.map((key) => {
            const authority = authorityOf(key);
            const bucketLines = linesFor.get(key) ?? [];
            const subtotal = subtotalOf.get(key) ?? null;
            return (
              <Fragment key={key}>
                {bucketLines.map((line, index) => (
                  <tr key={line.id} data-bil="tax-line" data-tax-id={key}>
                    <td>
                      {index > 0 ? null : authority !== null ? (
                        <span data-bil="tax-authority">{authority}</span>
                      ) : (
                        // The id is the stamp and the LABEL is resolved live, so
                        // a null here means the authority row could not be read
                        // — not that the tax has none. Never the raw id
                        // (DEF-2432 / B14 rule 31).
                        <NotRecorded
                          label={t("billing.bill.authorityAbsent")}
                          why={t("billing.bill.authorityAbsentWhy")}
                          ruleRef="BR-BIL-069"
                        />
                      )}
                    </td>
                    <td>{line.description}</td>
                    <td className="[&&]:text-right">
                      <MoneyCell amount={line.amount} currency={detail.currency} />
                    </td>
                  </tr>
                ))}
                {subtotal !== null && keys.length > 1 && (
                  // OQ-1190 — WHAT THIS AUTHORITY IS OWED. The server's own 2dp
                  // string; handing `subtotal` (the stored 4dp scale) to
                  // `MoneyCell` would round a second time in a second place
                  // (BR-SHL-023, one money path).
                  /* ⚠ **SUPPRESSED WHEN THERE IS ONLY ONE AUTHORITY
                     (`CR-101-BRC03`).** OQ-1190's ruling is *"add a
                     per-authority subtotal"* and it stands — with two or more
                     buckets each needs its own line. With ONE, that line and
                     the `Total tax` below it are the same figure printed twice
                     six pixels apart, which is what the blueprint's single
                     `Total tax` row says instead. Nothing is lost: the one
                     authority's subtotal IS the bill's tax. */
                  <tr data-bil="authority-subtotal" data-tax-id={key}>
                    <td colSpan={2}>{t("billing.bill.taxAuthoritySubtotal")}</td>
                    <td className="[&&]:text-right">
                      <MoneyCell
                        amount={subtotal.subtotal_display}
                        currency={block?.currency ?? detail.currency}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
        <tfoot>
          {/* `Total tax`, bold — the drawn last row of the drawn last table.
              It read `Tax` and sat under an `Authority subtotal` row carrying
              the identical figure. */}
          <tr className="[&_td]:font-heading [&_td]:font-extrabold" data-bil="tax-total">
            <td colSpan={2}>{t("billing.bill.taxTotal")}</td>
            <td className="[&&]:text-right">
              <MoneyCell amount={detail.tax_total} currency={detail.currency} />
            </td>
          </tr>
        </tfoot>
      </PlainTable>
      {block === null ? (
        // The pre-2026-08-31 sentence, kept for exactly the case it is still
        // true of: a server that does not serve the block.
        <p className="met-panel-hint" data-bil="no-authority-subtotal">
          {t("billing.bill.taxesNoAuthoritySubtotal")}
        </p>
      ) : (
        // THE TIE-OUT, AS THE SERVER GIVES IT — `ChargesByServicePanel`'s
        // posture and for its reason. `ties_out` false is a fact about this
        // bill, not an error state of this screen, and nothing here adjusts
        // either side.
        <p
          className={
            block.tie_out.ties_out
              ? "met-panel-hint"
              : "mt-2 border-l-2 border-l-danger-500 bg-danger-100 px-3 py-2 text-base leading-prose"
          }
          role={block.tie_out.ties_out ? undefined : "alert"}
          data-bil="taxes-tie-out"
          data-ties-out={String(block.tie_out.ties_out)}
        >
          {block.tie_out.ties_out
            ? t("billing.bill.taxesTieOut")
            : t("billing.bill.taxesDoNotTieOut", {
                authorities: formatMoney(block.tie_out.authorities_total, block.currency),
                bill: formatMoney(block.tie_out.tax_total, block.currency),
              })}
        </p>
      )}
      <p className="met-panel-hint">{t("billing.bill.panel.taxesHint")}</p>
    </Panel>
  );
}

/**
 * ⚠ **THE SEVEN FIELDS ARE REQUIRED AND STAY REQUIRED — CR-053 TASK 8.**
 * `US-BIL-026` §1 names them: *"every `invoice_line` with quantity/unit/unit-
 * price/amount/taxable flag/GL stamp/tariff version"*. **Accounting code** and
 * **Rate version** are the two a redesign drops first — they are the widest,
 * the least glanced at, and the only two a clerk cannot reconstruct from the
 * printed bill. They are what a finance query is actually about, and
 * `BillChargesTab.test.tsx` asserts all seven by header so a later tidy-up
 * goes red instead of quiet.
 *
 * WHAT CR-053 TASK 6 ADDED TO EACH ROW, AND WHY IT IS NOT A COLUMN. Three
 * facts had no home: whose tax a tax line is, which charge code a fee line
 * carries, and that a line is a discount or a minimum adjustment at all. Two
 * more columns would take this table to nine and B14 rule 20 holds one table
 * type product-wide, so they ride UNDER the description — the shape
 * `gl_account_code — gl_account_name` already uses one cell over.
 */
function BillLineGroup(props: {
  service: string;
  lines: readonly InvoiceLineRow[];
  currency: string;
  t: Translator;
  /** Record links (PO 2026-10-19): where a line's meter number opens. */
  assetHref?: (assetId: string) => string;
}) {
  const { t } = props;
  const label =
    props.service === LINE_GROUP_OTHER
      ? t("billing.bill.group.taxesAndFees")
      : props.service === LINE_GROUP_DISCOUNTS
        ? t("billing.bill.group.discounts")
        : // DEF-763 — `rating.service.*` holds all ten platform services;
        // `metering.service.*` held six, so a bill grouped by Storm water,
        // Solar, Thermal/Heat or Battery headed that group with a raw slug on a
        // document a customer may be shown.
        t(`rating.service.${props.service}`, { defaultValue: props.service });
  return (
    <>
      <tr className="[&_th]:font-heading [&_th]:text-table-header [&_th]:tracking-table-header [&_th]:uppercase [&_th]:text-accent">
        <th colSpan={5}>{label}</th>
      </tr>
      {props.lines.map((line) => (
        <tr key={line.id} data-bil="bill-line" data-kind={line.kind}>
          <td>
            {line.description}
            {/* DEF-BIL-8315 — WHICH METER this line was priced for, so two
                water meters' lines say whose is whose. */}
            {/* Record links (PO 2026-10-19): the meter number opens the meter. */}
            {line.asset_label ? (
              <span data-line-meter="">
                {" · "}
                {line.asset_id && props.assetHref !== undefined ? (
                  <InlineLinkTo to={props.assetHref(line.asset_id)}>{line.asset_label}</InlineLinkTo>
                ) : (
                  line.asset_label
                )}
              </span>
            ) : null}
            <LineKindNote line={line} t={t} />
            {/* PO 2026-10-01 — the size × count × base this capacity line was
                priced from, as stored on the line (`billing/0039`). */}
            <SizeBreakdown
              rows={line.pricing_trace?.sizes}
              formatAmount={(amount) => formatMoney(amount, props.currency)}
              t={t}
            />
          </td>
          <td>
            {/* CLAUDE.md #3: a quantity NEVER renders without its unit. A line
                with a quantity and no unit is a server bug, and the cell says
                so rather than printing a bare number that reads as kWh. */}
            {line.quantity === null ? (
              <Dash />
            ) : line.unit !== null ? (
              <UnitCell quantity={line.quantity} unit={line.unit} />
            ) : (
              <NotRecorded
                label={t("billing.bill.unitMissing")}
                why={t("billing.bill.unitMissingWhy")}
                ruleRef="CLAUDE.md #3"
              />
            )}
          </td>
          <td className="[&&]:text-right">
            {/* ⚠ **A UNIT PRICE IS A RATE, NOT MONEY (OQ-620(a), DEF-1121).**
                `MoneyCell` gave `$0.14` for a rate stored as `0.142000`, which
                is a well-formed currency string two places short of the
                precision the line was priced at — multiply it back by the
                quantity and it does not reproduce the amount in the next
                column. The PO ruled four places on 2026-08-27 (*"A rate is not
                money and not a quantity"*) and on 2026-10-02 up to four, zeros
                past the second dropped. The
                AMOUNT beside it is money and keeps `MoneyCell`. */}
            {line.unit_price !== null ? (
              <span className="cell-money">
                <span className="cell-money-amount">
                  {formatRate(line.unit_price, props.currency)}
                </span>
              </span>
            ) : (
              <Dash />
            )}
            {/* DEF-BIL-8744 — `19/30 days` under a rate whose amount was cut
                down by days, read off the line's stored pricing trace. */}
            <DayShareNote share={line.day_share} t={t} />
          </td>
          <td className="[&&]:text-right">
            <MoneyCell amount={line.amount} currency={props.currency} />
          </td>
          <td>
            {/* B4.2: tax rows are neither taxable nor not-taxable — the question
                does not apply to them, so they get a dash and not a "No". */}
            {line.kind === "tax" ? (
              <Dash />
            ) : line.taxable ? (
              t("billing.bill.taxableYes")
            ) : (
              t("billing.bill.taxableNo")
            )}
          </td>
        </tr>
      ))}
    </>
  );
}

/**
 * CR-053 task 6 — WHAT KIND OF LINE THIS IS, under its description.
 *
 * A `usage` or `base` line needs no note: it sits under its service heading
 * and its description says what it is. **Every other kind needed one and had
 * none.** A discount and a minimum-bill adjustment both landed in a group
 * headed *Taxes & fees* looking exactly like a usage line, and the three
 * scenarios the PO listed by name — *"charge code raletd, discount related,
 * taxes related"* — were indistinguishable from one another on the screen
 * whose whole job is to take a bill apart.
 *
 * ⚠ **THE CHARGE CODE IS NULL ON EVERY BILL IN THE PRODUCT (`DEF-2428`), AND
 * THE ID BESIDE IT IS NOT PRINTED INSTEAD.** Rating publishes no charge-id →
 * code read, so the label half cannot resolve. The `gl_account_id` fallback in
 * the column two cells over is the opposite choice and is right THERE for its
 * own reason — that id is the BR-BIL-010 stamp, and a blank in a column headed
 * ACCOUNTING CODE would read as *"this line did not post"*. Here the id
 * carries no such meaning to a clerk: it is an internal key, printing it is
 * the `BR-BIL-015` leak filed as `DEF-2432`, and *"this bill's charge code
 * cannot be read yet"* is both true and actionable where a uuid is neither.
 *
 * ⚠ **AND THE TAX AUTHORITY IS DELIBERATELY SHOWN TWICE** — here and in the
 * panel below. The panel answers *"whose tax is on this bill"* for a
 * remittance question; this answers *"what is this line"* for someone reading
 * down the table. One fact, one source, two readers.
 */
function LineKindNote(props: { line: InvoiceLineRow; t: Translator }) {
  const { line, t } = props;
  // ⚠ **EVERY LINE CARRIES A SUB-LINE NOW, NOT ONLY THE ODD KINDS
  // (`CR-101-BRC03`).** This used to return null for `usage` and `base` —
  // correct while the note's only job was to say WHAT KIND a line was, and a
  // usage line sitting under its service heading needs no such note. It now
  // also carries the two folded columns, which every line has, so the early
  // return went with them.
  const parts: ReactNode[] = [];
  if (line.kind !== "usage" && line.kind !== "base") {
    parts.push(
      <span key="kind" data-bil="line-kind">
        {t(`billing.bill.kind.${line.kind}`, { defaultValue: line.kind })}
      </span>,
    );
  }
  if (line.kind === "tax" && line.tax_authority !== null) {
    parts.push(
      <span key="authority" data-bil="line-authority">
        {line.tax_authority}
      </span>,
    );
  }
  // ── the folded ACCOUNTING CODE — blueprint 02.2 legend ① ─────────────────
  //
  // BR-BIL-010: the STAMP, issue-time truth, never re-resolved against today's
  // mapping. ⚠ **THIS PRINTED A RAW UUID ON EVERY LINE OF EVERY BILL UNTIL
  // 2026-08-27 (`DEF-937`)** and the uuid fallback went on 2026-08-31
  // (`DEF-2716`, B14 rule 31 — *"no Databse ID on screen - that is a rule"*).
  // Neither ruling is undone by moving the value under the description: CODE
  // then NAME as before, a stated absence when it cannot be read, and the
  // internal key on `title` where support can reach it and no clerk reads it as
  // the value of a field — which is rule 31's own sentence.
  if (line.gl_account_code !== null) {
    parts.push(
      <span key="gl" data-bil="line-gl">
        {line.gl_account_name !== null
          ? `${line.gl_account_code} — ${line.gl_account_name}`
          : line.gl_account_code}
      </span>,
    );
  } else if (line.gl_account_id !== null) {
    parts.push(
      <span key="gl" data-bil="line-gl-unreadable" title={line.gl_account_id}>
        {t("billing.bill.glCodeUnreadable")}
      </span>,
    );
  } else {
    // ⚠ **A LINE WITH NO ACCOUNTING CODE AT ALL STILL SAYS SO (G38).** When
    // this was a COLUMN the reason was that a blank cell under a header reading
    // ACCOUNTING CODE asserts *"this line did not post"*. Folded under the
    // description the blank is quieter and the fact is the same one BR-BIL-010
    // cares about, so it is stated rather than dropped — which is what the fold
    // did on its first draft, and `US-BIL-026 TC-2` caught it.
    parts.push(
      <span key="gl" data-bil="line-gl-absent" data-br-ref="BR-BIL-010">
        {t("billing.bill.glAbsent")}
      </span>,
    );
  }
  // ── the folded RATE VERSION — the widest column in the table, measured at
  //    324 px of 1,086, and the least-used thing on the screen.
  //
  // The label is the SCHEDULE plus the date it took effect, which is how
  // BR-RAT-007 identifies the version that priced this line. No ordinal —
  // rating stores no "v3" and inventing one would be a number a clerk could not
  // find anywhere else.
  if (line.tariff_version_label !== null) {
    parts.push(
      <span key="rate" data-bil="line-rate-version">
        {line.tariff_version_label}
      </span>,
    );
  } else if (line.tariff_version_id !== null) {
    parts.push(
      <span key="rate" data-bil="line-rate-version-unreadable" title={line.tariff_version_id}>
        {t("billing.bill.rateVersionUnreadable")}
      </span>,
    );
  }
  if (line.charge_code !== null) {
    parts.push(
      <span key="charge" data-bil="line-charge-code">
        {line.charge_name !== null ? `${line.charge_code} — ${line.charge_name}` : line.charge_code}
      </span>,
    );
  } else if (line.charge_id !== null) {
    parts.push(
      <span key="charge" data-bil="line-charge-code-absent" data-br-ref="DEF-2428">
        {t("billing.bill.chargeCodeAwaiting")}
      </span>,
    );
  }
  if (parts.length === 0) {
    return null;
  }
  return (
    <span className="mt-1 block text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
      {parts.map((part, index) => (
        <Fragment key={index}>
          {index > 0 ? " · " : null}
          {part}
        </Fragment>
      ))}
    </span>
  );
}

/** `adjustments` rows on this bill — correction ROWS, never an edit (rule 4). */
function AdjustmentsPanel(props: {
  adjustments: readonly InvoiceAdjustmentRef[];
  currency: string;
  t: Translator;
}) {
  const { t } = props;
  if (props.adjustments.length === 0) {
    return null;
  }
  return (
    <Panel as="section">
      <h3>{t("billing.bill.panel.adjustments")}</h3>
      <PlainTable>
        <thead>
          <tr>
            <th>{t("billing.bill.col.direction")}</th>
            <th>{t("billing.bill.col.reasonCode")}</th>
            <th>{t("billing.bill.col.amount")}</th>
          </tr>
        </thead>
        <tbody>
          {props.adjustments.map((row) => (
            <tr key={row.id}>
              <td>
                {t(`billing.bill.direction.${row.direction}`, { defaultValue: row.direction })}
              </td>
              <td>{row.reason_code}</td>
              <td>
                <MoneyCell amount={row.amount} currency={row.currency} />
              </td>
            </tr>
          ))}
        </tbody>
      </PlainTable>
      <p className="met-panel-hint">{t("billing.bill.panel.adjustmentsHint")}</p>
    </Panel>
  );
}

/**
 * The correction chain, navigable BOTH ways (BR-BIL-004/014): the credit notes
 * raised against this bill, the bill this one re-bills, and the bill that
 * corrected this one. Nothing here is inferred from a status — each link is a
 * served id, and a bill with no chain renders the fact rather than an empty
 * table that would read as "this bill has never been corrected" when the truth
 * is that the chain was not served.
 */
/**
 * ══════════════════════════════════════════════════════════════════════════
 * `CR-101-BRC03` — CORRECTIONS, REBUILT TO THE BLUEPRINT'S TWO STATES.
 * ══════════════════════════════════════════════════════════════════════════
 * Blueprint entry 02.3 draws this tab twice, and the step-1 diff found the
 * drawn frame and the built screen agreeing *"on almost nothing"*: three
 * stacked sentences and a four-column credit-note table against two labelled
 * groups, an event table, a net figure and a way out.
 *
 * **EMPTY** — `STANDING` (a green pill, then one sentence) · `HISTORY`
 * (*Nothing to report.*, then the rule about why nothing ever overwrites) ·
 * and `Fix this bill` **on the tab**, which is the whole point of the redraw:
 * a clerk who clicks *Corrections* and finds none is exactly the person who
 * wants to start one, and until now the only route was the header button.
 *
 * **POPULATED** — `STANDING` (the `Replaced` pill and the link to the bill
 * that counts now) · `WHAT HAPPENED`, one row per event in order · the net
 * effect · `CREDIT NOTES` kept as its own table because a credit note is a
 * document in its own right · and `Fix this bill again` with the truth beside
 * it.
 *
 * ⚠ **NOTHING HERE COMPUTES MONEY.** The net effect is the SERVER's
 * `net_effect`; every other figure is a total off a row. This file's own
 * standing rule (PO 2026-08-30) is that the screen displays what the server
 * resolved, and a browser-side sum of a customer's correction would be a
 * second implementation of an arithmetic no golden test can reach.
 *
 * ⚠ **AND HARD RULE 4 IS WHAT THE TAB IS ABOUT.** An issued bill takes no
 * UPDATE and no DELETE; a correction is new rows. Every row of the table below
 * is a separate document, which is why the sentence under it survives the
 * redraw word for word.
 */
function ChainTab(props: {
  detail: InvoiceDetail;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  client?: ApiClient;
}) {
  const { detail, t } = props;
  const tenantPath = useTenantPath();
  const chainQuery = useQuery({
    queryKey: billChainKey(detail.id),
    queryFn: () => getInvoiceChain(detail.id, props.client ?? api),
    // A refusal here is a state, not a flaky network — retrying delays it.
    retry: false,
  });
  const chain: InvoiceChain | undefined = chainQuery.data;
  // The chain's own legs when the route answered; the detail's fields when it
  // did not. `replaces` / `replaced_by` are the SAME column read in the two
  // directions, so the two sources cannot disagree — one is simply richer.
  const replacesId = chain?.replaces?.invoice_id ?? detail.rebill_of_invoice_id;
  const replacedById = chain?.replaced_by?.invoice_id ?? detail.corrected_by_invoice_id;
  const hasChain =
    detail.credit_notes.length > 0 ||
    replacesId !== null ||
    replacedById !== null ||
    (chain !== undefined && chain.credit_notes.length > 0);
  return (
    <>
      <Panel as="section" title={<Kicker as="span">{t("billing.bill.group.standing")}</Kicker>}>
        <ChainStanding
          detail={detail}
          chain={chain}
          query={chainQuery}
          t={t}
          tenantPath={tenantPath}
        />
        {/* The bill this one REPLACES is a standing fact too, and the drawing
            has no state for it — a bill that IS a replacement is a third
            standing beside *current* and *replaced*. It is recorded as a gap in
            the drawing rather than invented: the product's answer is truthful,
            so it keeps saying it, one line under the standing it belongs to. */}
        {replacesId !== null && replacesId !== undefined && (
          <p className="met-panel-hint" data-bil="chain-replaces">
            {t("billing.bill.field.rebillOf")}{" "}
            <InlineLinkTo to={tenantPath(billDetailPath(replacesId))}>
              {chain?.replaces?.invoice_no ?? t("billing.bill.openOriginal")}
            </InlineLinkTo>
          </p>
        )}
      </Panel>

      <Panel as="section" title={<Kicker as="span">{t("billing.bill.group.history")}</Kicker>}>
        {!hasChain ? (
          <p className="met-panel-hint" data-bil="chain-none">
            {t("billing.bill.chainNone")}
          </p>
        ) : (
          <WhatHappenedTable
            detail={detail}
            chain={chain}
            t={t}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
            tenantPath={tenantPath}
          />
        )}
        <p className="met-panel-hint">{t("billing.bill.panel.chainHint")}</p>
      </Panel>

      {hasChain && (
        <Panel
          as="section"
          title={<Kicker as="span">{t("billing.bill.group.creditNotes")}</Kicker>}
        >
          <CreditNoteList
            creditNotes={detail.credit_notes}
            t={t}
            timeZone={props.timeZone}
            dateFormat={props.dateFormat}
          />
        </Panel>
      )}

      {/* ⚠ **THE WAY OUT — AND IT IS `NEW` IN THE DRAWING'S OWN WORDS.**
          `Fix this bill` appears *"on the tab about corrections, which it
          currently does not: today the only route is the header button"*. On a
          bill that has ALREADY been replaced the label and the truth both
          change: a further correction applies to the REPLACEMENT, not to this
          one (BR-BIL-048 — only the latest in a chain is correctable), and the
          blueprint draws that sentence beside the button rather than leaving a
          clerk to discover it at preview time. */}
      <div className="mt-4 flex flex-wrap items-center gap-3" data-bil="chain-way-out">
        {chain !== undefined && !chain.is_latest ? (
          <>
            <ButtonLink variant="secondary" to={tenantPath(fixABillPath(chain.head.invoice_id))}>
              {t("billing.bill.action.correctAgain")}
            </ButtonLink>
            <span className="text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
              {t("billing.bill.correctAgainNote")}
            </span>
          </>
        ) : (
          <ButtonLink variant="secondary" to={tenantPath(fixABillPath(detail.id))}>
            {t("billing.bill.action.correct")}
          </ButtonLink>
        )}
      </div>
    </>
  );
}

/**
 * ONE ROW PER EVENT, IN ORDER — issued → correction opened → approved → credit
 * note → replacement, with the net effect footing the column.
 *
 * ⚠ **THE ROWS ARE BUILT FROM SERVED FACTS AND FROM NOTHING ELSE, WHICH IS WHY
 * A ROW CAN BE ABSENT.** The two middle rows exist only where a correction
 * CASE was recorded: a chain written by an older build, or by an import, has
 * the documents and no case, and the table then shows three rows rather than
 * inventing an opener and an approver. Every drawn row that this deployment
 * can produce is produced.
 *
 * ⚠ **`EFFECT` IS THE MONEY COLUMN AND IT IS RIGHT-ALIGNED; `REASON` IS NOT.**
 * A dash under `EFFECT` sits on the money's right edge and a dash under
 * `REASON` sits at the column's left, which is what the drawing shows and what
 * `USAGE` on the Charges tab deliberately does not.
 */
function WhatHappenedTable(props: {
  detail: InvoiceDetail;
  chain: InvoiceChain | undefined;
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
  tenantPath: (path: string) => string;
}) {
  const { detail, chain, t } = props;
  const when = (value: string | null | undefined) =>
    value == null ? (
      <Dash />
    ) : (
      <DateCell value={value} timeZone={props.timeZone} dateFormat={props.dateFormat} />
    );
  const who = (actor: ChainActor | null | undefined) =>
    actor == null || actor.name === null ? (
      <Dash />
    ) : (
      <>
        {actor.name}
        {actor.role !== null && (
          <span className="mt-1 block text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {actor.role}
          </span>
        )}
      </>
    );
  const reasonWords = (code: string | null | undefined) =>
    code == null || code === "" ? (
      <Dash />
    ) : (
      <CodeWord prefix="billing.fix.reason" code={code} t={t} />
    );
  const money = (amount: string | null | undefined, currency: string) =>
    amount == null ? <Dash /> : <MoneyCell amount={amount} currency={currency} />;

  const rows: {
    key: string;
    when: string | null | undefined;
    what: ReactNode;
    detail?: ReactNode;
    reason: ReactNode;
    who: ReactNode;
    effect: ReactNode;
  }[] = [];

  rows.push({
    key: "issued",
    when: chain?.issued_at ?? detail.issued_at,
    what: <span className="font-heading font-bold">{detail.invoice_no ?? <Dash />}</span>,
    detail: t("billing.bill.event.thisBill"),
    reason: <Dash />,
    who: <Dash />,
    effect: money(chain?.total ?? detail.total, chain?.currency ?? detail.currency),
  });

  if (chain?.case != null) {
    const kase = chain.case;
    rows.push({
      key: "opened",
      when: kase.opened_at,
      what: t("billing.bill.event.correctionOpened"),
      detail:
        kase.case_no === null
          ? t("billing.fix.noCaseNo")
          : t("billing.bill.event.caseNo", { caseNo: kase.case_no }),
      reason: reasonWords(kase.reason_codes[0]),
      who: who(kase.opened_by),
      effect: <Dash />,
    });
    if (kase.approved_on !== null || kase.approved_by !== null) {
      rows.push({
        key: "approved",
        when: kase.approved_on,
        what: t("billing.bill.event.approved"),
        reason: <Dash />,
        who: who(kase.approved_by),
        effect: <Dash />,
      });
    }
  }

  // ⚠ **THE CREDIT NOTES COME OFF THE DETAIL, NOT THE CHAIN, AND THAT IS THE
  // FALLBACK THIS TAB HAS ALWAYS HAD.** `GET /invoices/{id}` carries them with
  // their reason and their date and it has already resolved before this tab
  // renders; the chain route is a SECOND request that can fail. A tab that went
  // blank because its second request failed would be worse than the one this
  // replaces — so the richer source is the one that is always there.
  for (const note of detail.credit_notes) {
    rows.push({
      key: `cn-${note.id}`,
      when: note.issued_at,
      what:
        note.credit_note_no === null ? (
          <Dash>{t("billing.bill.creditNoteNoNumber")}</Dash>
        ) : (
          <>
            <span className="text-accent">{note.credit_note_no}</span>{" "}
            {t("billing.bill.event.creditNote")}
          </>
        ),
      detail: t("billing.bill.event.cancelsThisBill"),
      reason: reasonWords(note.reason),
      who: <Dash />,
      effect: money(note.amount, note.currency),
    });
  }

  // The same fallback in the other direction: the chain's leg when the route
  // answered, the detail's column when it did not. Both read
  // `invoices.corrects_invoice_id`, so they cannot disagree — one is richer.
  const replacementId = chain?.replaced_by?.invoice_id ?? detail.corrected_by_invoice_id;
  if (replacementId !== null) {
    const leg = chain?.replaced_by ?? null;
    rows.push({
      key: "replacement",
      when: leg?.issued_at,
      what: (
        <>
          <InlineLinkTo to={props.tenantPath(billDetailPath(replacementId))}>
            {leg?.invoice_no ?? t("billing.bill.openRebill")}
          </InlineLinkTo>{" "}
          {t("billing.bill.event.replacementBill")}
        </>
      ),
      detail: t("billing.bill.event.countsNow"),
      reason: <Dash />,
      who: <Dash />,
      effect: money(leg?.total, leg?.currency ?? detail.currency),
    });
  }

  return (
    <>
      <PlainTable data-bil="what-happened">
        <thead>
          <tr>
            <th>{t("billing.bill.col.when")}</th>
            <th>{t("billing.bill.col.what")}</th>
            <th>{t("billing.bill.col.reason")}</th>
            <th>{t("billing.bill.col.who")}</th>
            <th className="[&&]:text-right">{t("billing.bill.col.direction")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} data-bil="chain-event" data-event={row.key}>
              <td>{when(row.when)}</td>
              <td>
                {row.what}
                {row.detail !== undefined && (
                  <span className="mt-1 block text-sm text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
                    {row.detail}
                  </span>
                )}
              </td>
              <td>{row.reason}</td>
              <td>{row.who}</td>
              <td className="[&&]:text-right">{row.effect}</td>
            </tr>
          ))}
        </tbody>
        {chain?.net_effect != null && (
          <tfoot>
            {/* ⚠ **THE ONE FIGURE A CALLER ACTUALLY ASKS FOR, AND THE SERVER
                COMPUTES IT.** "Is my customer better or worse off, and by how
                much" took a clerk reading three rows and doing the sum. It is
                accented because a correction's net is the answer this whole tab
                exists to give. */}
            <tr
              className="[&_td]:font-heading [&_td]:font-extrabold"
              data-bil="chain-net-effect"
            >
              <td colSpan={4}>{t("billing.bill.netEffect")}</td>
              <td className="[&&]:text-right text-accent">
                <MoneyCell
                  amount={chain.net_effect}
                  currency={chain.currency ?? detail.currency}
                />
              </td>
            </tr>
          </tfoot>
        )}
      </PlainTable>
    </>
  );
}

/**
 * `is_latest`, as a sentence a person can act on.
 *
 * THREE STATES AND THEY ARE NOT INTERCHANGEABLE:
 *
 *   · **this bill is the current one** — said plainly, because on an
 *     uncorrected bill it is the reassuring answer and on a REPLACEMENT it is
 *     the load-bearing one (BR-BIL-048 lets a correction be opened on it);
 *   · **this bill has been superseded** — and the replacement is NAMED and
 *     LINKED, so nobody has to find it. A superseded bill quoted to a customer
 *     is the failure this line exists to prevent;
 *   · **we could not ask** — the route failed, and the SERVER's sentence says
 *     why. Never "current", which would be a claim about a customer's money
 *     made from a network error.
 */
function ChainStanding(props: {
  detail: InvoiceDetail;
  chain: InvoiceChain | undefined;
  query: { isPending: boolean; error: unknown };
  t: Translator;
  tenantPath: (path: string) => string;
}) {
  const { chain, t } = props;
  if (chain === undefined) {
    if (props.query.isPending) {
      // ⚠ **WHILE THE SECOND READ IS IN FLIGHT, THE BILL'S OWN COLUMN ANSWERS
      // HALF THE QUESTION — AND ONLY HALF (`CR-101-BRC03`).** This returned
      // `null`, which was right when the standing shared a panel with the rest
      // of the tab and is wrong now that `STANDING` is a panel of its own: an
      // empty bordered box is a visual defect, and on a slow network it is the
      // first thing a clerk sees.
      //
      // **READING MY OWN COLUMN IS NOT WALKING THE CHAIN.** This file's rule
      // stands — deriving `head` here would be a second implementation of
      // BR-BIL-048 and would get A→B→C wrong. `corrected_by_invoice_id` is not
      // that: it is one column of THIS row saying whether anything replaced
      // THIS bill, which is a fact the detail already carries. So a bill with
      // nothing in it is stated as current; a bill with something in it says
      // *Replaced* and waits for the chain to NAME the replacement, because
      // naming it is the walk.
      if (props.detail.corrected_by_invoice_id === null) {
        return (
          <div role="note" data-bil="chain-latest">
            <StatusPill tone="success">{t("billing.bill.chain.isCurrentPill")}</StatusPill>
            <p className="met-panel-hint">{t("billing.bill.chain.isLatest")}</p>
          </div>
        );
      }
      return (
        <div role="note" data-bil="chain-superseded">
          <StatusPill tone="warning">{t("billing.bill.chain.superseded")}</StatusPill>
          <p className="met-panel-hint">{t("billing.bill.chain.supersededWhy")}</p>
        </div>
      );
    }
    return (
      <NotRecorded
        label={t("billing.bill.chain.standingUnknown")}
        why={apiErrorText(props.query.error, t)}
        ruleRef="BR-BIL-048"
      />
    );
  }
  // ⚠ **A PILL AND THEN A SENTENCE, WHICH IS THE REDRAW (`CR-101-BRC03`).**
  // The blueprint's own line: *"Standing answers the question the tab exists
  // for, AS A PILL rather than a sentence."* Three stacked sentences became one
  // pill and one sentence, and *"every sentence on the live tab survives"* — one
  // is promoted to the pill, one is merged into the standing line.
  if (chain.is_latest) {
    return (
      <div role="note" data-bil="chain-latest">
        <StatusPill tone="success">{t("billing.bill.chain.isCurrentPill")}</StatusPill>
        <p className="met-panel-hint">{t("billing.bill.chain.isLatest")}</p>
      </div>
    );
  }
  return (
    <div role="note" data-bil="chain-superseded">
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill tone="warning">{t("billing.bill.chain.superseded")}</StatusPill>
        <InlineLinkTo to={props.tenantPath(billDetailPath(chain.head.invoice_id))}>
          {t("billing.bill.chain.openCurrent", {
            billNo: chain.head.invoice_no ?? t("billing.bills.noNumber"),
          })}
        </InlineLinkTo>
      </div>
      {/* ⚠ **THE DRAWN SENTENCE CARRIES THE REPLACEMENT'S DATE AND THIS ONE
          DOES NOT, DELIBERATELY.** BR-SHL-034 is one date formatter, and a date
          interpolated into a translated string is formatted by whoever built
          the string — which is the defect that rule exists for. The date is one
          row below, in the `WHAT HAPPENED` table's replacement row, through
          `DateCell` like every other date on this screen. */}
      <p className="met-panel-hint">{t("billing.bill.chain.supersededWhy")}</p>
    </div>
  );
}

function CreditNoteList(props: {
  creditNotes: readonly InvoiceCreditNoteRef[];
  t: Translator;
  timeZone: string;
  dateFormat: RegionalDateFormat;
}) {
  const { t } = props;
  if (props.creditNotes.length === 0) {
    return <p className="met-panel-hint">{t("billing.bill.creditNotesNone")}</p>;
  }
  return (
    <PlainTable data-bil="credit-notes">
      <thead>
        {/* ⚠ **THE COLUMN ORDER IS THE DRAWING'S AND `AMOUNT` IS LAST AND
            RIGHT-ALIGNED (`CR-101-BRC03`).** It ran number → amount → reason →
            date, which put a money column in the middle of three text ones. The
            drawn order reads as a sentence — *this note, issued then, for this
            reason, worth this much* — and the money column ends the row where
            every other money column in this product ends it. */}
        <tr>
          <th>{t("billing.bill.col.creditNote")}</th>
          <th>{t("billing.bill.col.issued")}</th>
          <th>{t("billing.bill.col.reason")}</th>
          <th className="[&&]:text-right">{t("billing.bill.col.amount")}</th>
        </tr>
      </thead>
      <tbody>
        {props.creditNotes.map((note) => (
          <tr key={note.id}>
            <td>{note.credit_note_no ?? <Dash>{t("billing.bill.creditNoteNoNumber")}</Dash>}</td>
            <td>
              {note.issued_at !== null ? (
                <DateCell
                  value={note.issued_at}
                  timeZone={props.timeZone}
                  dateFormat={props.dateFormat}
                />
              ) : (
                <Dash>{t("billing.bills.notIssued")}</Dash>
              )}
            </td>
            <td>
              {/* ⚠ **`DEF-2448`, CLOSED HERE.** This cell printed the raw
                  machine code — `wrong_read` — on a real corrected invoice, in
                  all eleven languages, because `billing.fix.reason.*` held zero
                  keys anywhere (`DEF-BIL-5233`, counted). The words exist now;
                  a code without one still states the absence rather than
                  printing itself (B14 rule 32). */}
              {note.reason === null || note.reason === "" ? (
                <Dash />
              ) : (
                <CodeWord prefix="billing.fix.reason" code={note.reason} t={t} />
              )}
            </td>
            <td className="[&&]:text-right">
              <MoneyCell amount={note.amount} currency={note.currency} />
            </td>
          </tr>
        ))}
      </tbody>
    </PlainTable>
  );
}

// Re-exported so the list and the detail agree on how a number is rendered.
export { BillNumber };

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-BIL-026@f4c9d21 (story+rules snapshot — EP-BIL-07; co-packets US-BIL-025/027 same epic · US-BIL-007 EP-BIL-02 · billing 03-field-map §2)
// generated: 2026-08-11 by story-coder (W3 billing FRONTEND lane — the S30 bill detail, the screen the `invoices`/`invoice_lines` tables landed without)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — GET /invoices/{id} is contracted at 11b §2.8 and unserved; 06-backend is another lane's and this packet is frontend-only) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · eslint --max-warnings 0✔ · vitest 738 passed / 174 todo across 53 files✔ (702 passed / 168 todo across 51 files was the pre-lane baseline — this lane adds 36 passing + 6 todo across 2 new files and dropped nothing) · vite build✔ · run_gates 15 PASS · 0 FAIL · 1 SKIP✔ (G13 unwired-props, G14 prototype-conformance and G15 i18n-parity included; 5 locales × 2628 keys, identical sets)
// exceptions: E3 the DOCUMENT is not rendered client-side and there is no `bill_payload` parser anywhere in this module: BR-BIL-030 freezes the instance at issue, BR-CUS-040/BR-BIL-026 make the reprint render THAT instance through the PINNED template version, and 11b §2.8 puts that render on the server (`GET /invoices/{id}/document`). No signed document names the payload's JSON keys and stage 6 is being authored in another lane — a second guess at one schema is hard-won law 5 · E3 `GET /invoices/{id}` IS NOT SERVED; its 404 has three possible causes (unknown id · cross-tenant — HR-1 collapses those two and US-BIL-026 TC-6 requires it — · unregistered route) so the failure names all three rather than picking one. Only the LIST, whose 404 on a collection route is unambiguous, states the route-absent case outright · E3 all three row actions render DISABLED WITH THEIR REASON and each reason is the TRUE one for that bill: Reprint is meaningless on a draft (nothing is stamped until issue), Correct only applies to a bill that was issued, and Void additionally states that its consequence message and OQ-012 window evaluation are SERVER-computed (BR-BIL-009) — a confirm dialog written here would invent the consequence it is required to state · E3 a line with a quantity and NO unit renders as a stated refusal, never as a bare number (CLAUDE.md #3); a tax line's taxable cell is a dash, not "No", because B4.2 makes the question inapplicable to it · E3 the stamped GL renders as the uuid when `gl_account_code` is null: the readable code needs `ledger_accounts` (W5), and a blank would suggest the line did not post · E3 `deliveries: null` renders as arrives-with, never as an empty table — BR-BIL-016's queue has no table (r10 #8) and "no rows" would claim the bill was never sent · E3 the run is SHOWN as its id and not linked: EP-BIL-01's run screens do not exist and a link onto a placeholder is "built is not wired" · E4 the Audit tab reuses metering's `AuditTab` (the S61 viewer filtered by entity) so one audit surface keeps one set of masking and window rules · E4 the tenant TZ + date format arrive as props with the same seed fallbacks every other detail uses
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
