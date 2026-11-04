// ── Trace ──────────────────────────────────────────────
// Change:   `CR-137-BRC07` `P3.9` + `P3.10` + `P3.11` — screen **2·2, the
//           payment detail**, of `05-prototype/06 Payments Page Blueprint.pdf`.
//           **p035 and p036 read AS IMAGES at scale 2.0** (B14 rule 42; PO,
//           twice: *"i want you to use drawing images exactly to build screen;
//           dont use text"*).
// Story:    US-PAY-004 (`TC-7` names this URL) · Screens: S33 · S21
// Rules:    B14 rule 1 (the `←` names where it EXITS to) · rule 2 (one page
//           header) · rule 4 (`+ Noun` creates) · rule 6 (danger tier on the
//           destructive commit) · rule 11 · rule 21 (Tailwind only; this file
//           is on `route-b-migrated.txt`) · rule 31 (no database id is a
//           visible value) · rule 32 (one sentence per section) · rule 33 ·
//           rule 40 (the page-head title is 32px) · rule 43 (components) ·
//           BR-SHL-025 (a refused control says WHY)
// Tests:    src/features/payments/paymentDetailPage.dom.test.tsx
// ───────────────────────────────────────────────────────
// **A PAYMENT HAS A HOME.**
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHAT THIS REPLACES, AND WHY IT HAD TO BE ONE COMMIT
// ══════════════════════════════════════════════════════════════════════════
// Until now a payment opened as an EXPANSION INSIDE THE LIST ROW
// (`paymentDetail.tsx`'s `PaymentDetailPanel`, through the shared table's
// `renderExpanded`). p036 states the cost: *"It has no address, so it cannot be
// linked, bookmarked or returned to after a refresh — which is also why the row
// actions have no View icon."*
//
// `P3.10`'s instruction is explicit about the timing and both halves of it
// matter: ***"Not before"*** — removing the panel first would take away the
// only way to see what a payment paid off — and ***"not later"*** — leaving
// both would give the product **two answers to one question, which is how a
// figure starts to drift**. So: *one commit — the page arrives, the panel goes,
// the 👁 appears.*
//
// **And the eleven facts and the two-column bill table are KEPT EXACTLY**
// (p036). They moved into `paymentDetailShared.tsx` with their markup and their
// reasoning intact, so no clerk loses a fact in the swap.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE FOUR HEADER CONTROLS ARE LIVE ON THE DAY THIS LANDS — ALL FOUR
// ══════════════════════════════════════════════════════════════════════════
// Hard-won law 2's mirror is *"a live screen behind a dead control"*, and it
// cost the customer portal two working doors out of eight. A payment detail
// that shipped with `+ Correction`, `Cancel` and `↓ Receipt` greyed out over
// *"opens with the next release"* would be exactly that failure, on a money
// screen. So `P3.11`'s three modals land in this same commit and every control
// in the head either OPENS something or SAYS WHY IT CANNOT.
//
// **And the why is the SERVER's.** `actions` comes off `GET /payments/{id}`,
// where `cancel.refusal_for` — the same pure function the write path calls —
// decides it. A screen that worked the status rules out for itself would be a
// second copy of them, free to drift (BR-SHL-025).
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE ADDRESS CARRIES THE `PMT-` NUMBER, NOT THE uuid
// ══════════════════════════════════════════════════════════════════════════
// `/:tenant/payments/PMT-2609-000418`. **B14 rule 31 — an address a clerk
// pastes into a message is about as visible as a value gets**, and the drawing
// agrees. The server resolves either spelling, so a link built from an id still
// opens; this screen only ever BUILDS the number.
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ IT SAYS NOTHING ABOUT HOW LONG THE HISTORY SURVIVES (`P3.18`)
// ══════════════════════════════════════════════════════════════════════════
// `audit_log` is pruned and a correction's row is pruned with everything else
// (PO, 2026-09-23). The server carries that as the `unavailable[]` CODE
// `history_is_pruned_like_every_audit_row`, **for a caller to reason about and
// never to render**: B14 rule 33 puts RATIONALE at ZERO WORDS ON SCREEN, so a
// panel explaining the retention policy in order to be honest would break rule
// 33 while trying to obey the ruling. **The honest build is silence — never
// claim permanence.** This page claims nothing.
import { useState } from "react";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getPayments } from "@/api/endpoints";
import { getPaymentDetail, getPaymentHistory } from "@/api/paymentDetailEndpoints";
import { Button } from "@/components/Button";
import { formatMoney } from "@/components/MoneyCell";
import { CustomFieldsView } from "@/components/CustomFields";
import { formatDate } from "@/components/DateCell";
import type { RegionalDateFormat } from "@/components/DateCell";
import { PageHeader } from "@/components/PageHeader";
import { Panel } from "@/components/Panel";
import { FailedWithRetry, LoadingSkeleton, PermissionDenied } from "@/components/StateFrame";
import { useToast } from "@/components/Toast";
import { useCrumbLeaf } from "@/components/crumbLeaf";
import { billDetailPath } from "@/features/billing/billingShared";
import { accountDetailPath } from "@/features/customers/customersShared";
import {
  ROLE_BILLING_CLERK,
  ROLE_SYSTEM_ADMIN,
  useRegional,
  useTenantRole,
} from "@/features/metering/meteringShared";
import { isPermissionDenied } from "@/features/tenancy/settingsShared";
import { useTenantPath } from "@/routing/tenantPath";

import { AddCorrectionModal } from "./AddCorrectionModal";
import { CancelPaymentModal } from "./CancelPaymentModal";
import { MarkReturnedModal } from "./MarkReturnedModal";
import { CorrectReferenceModal, PaymentsPage } from "./PaymentsPage";
import { PrintReceiptButton } from "./PrintReceipt";
import { ResendReceiptModal } from "./ResendReceiptModal";
import {
  paymentDetailRoute,
  PaymentFacts,
  PaymentHeaderStrip,
  PaymentHistoryPanel,
} from "./paymentDetailShared";
import { PAYMENTS_TABS, PAYMENTS_ROUTE } from "./paymentsShared";
import { depositBatchRoute } from "./depositsShared";

// The address and its builder live in `paymentDetailShared.tsx` so this page
// and `PaymentsPage.tsx` do not import each other; re-exported here so a reader
// looking for the route beside the screen still finds it.
export { PAYMENT_DETAIL_ROUTE, paymentDetailRoute } from "./paymentDetailShared";

export function paymentDetailQueryKey(ref: string) {
  return ["payments", "detail", ref] as const;
}

/** The server's code for *the trail could not be read* — a DIFFERENT fact from
 *  *nothing has happened*, and only one of them is safe to draw as an empty
 *  table. */
const HISTORY_UNREADABLE = "history_read_unpublished";

type OpenModal = "edit" | "correction" | "cancel" | "receipt" | "returned" | null;

export interface PaymentDetailPageProps {
  client?: ApiClient; // test seam — screens never build their own transport
  /**
   * The payment this page is for, when the ROUTE's param is not `:paymentRef`.
   *
   * ⚠ **`PaymentsSegmentRoute` mounts this at `payments/:tab`**, so the segment
   * arrives under the other name. Passing it explicitly beats declaring both
   * param names and hoping one is filled — `useParams()` returning `undefined`
   * for a name the route does not declare is exactly how eight portal doors
   * came out as `//portal/…` and passed every `toContain` (CLAUDE.md law 2).
   */
  paymentRef?: string;
  timeZone?: string;
  dateFormat?: RegionalDateFormat;
  locale?: string;
}

/**
 * Which screen `/{tenant}/payments/{segment}` opens — the TAB or the PAYMENT.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * ⚠ WHY THIS EXISTS RATHER THAN A SECOND ROUTE IN `App.tsx`
 * ══════════════════════════════════════════════════════════════════════════
 * The drawing's agreed address is `/:tenant/payments/PMT-2609-000418` — a
 * SIBLING of the seven tab addresses, not a child of one. `App.tsx` already
 * declares `payments/:tab`, and **React Router scores two dynamic siblings at
 * one level IDENTICALLY**: whichever is listed first wins every time, so
 * `payments/:paymentRef` beside it would eat `payments/summary`, and after it
 * would never be reached at all.
 *
 * ⚠ **AND THE FAILURE WOULD HAVE BEEN SILENT, WHICH IS WHY THIS IS A COMPONENT
 * AND NOT A COMMENT.** `paymentsTabFrom` answers an unknown segment with
 * `summary` and says so in its own docstring — *"an unknown `:tab` falls back
 * to the sidebar's own landing tab, never 404s"*. Correct for a typo; **for a
 * payment reference it means a clerk who pastes a link lands on the SUMMARY
 * TAB, with no error, no empty state and nothing on screen saying they are in
 * the wrong place.** That is hard-won law 7's *looking at the wrong thing*, and
 * a route test asserting *"the page is registered"* would pass over it.
 *
 * **What it does is the narrowest thing that works.** A segment that is one of
 * the known tabs — or `collections`, which `paymentsTabFrom` answers
 * deliberately — goes to `PaymentsPage`, byte for byte as before. Only a
 * segment that LOOKS LIKE A PAYMENT REFERENCE is sent here. **Anything else
 * keeps today's fallback exactly**, so no existing address changes behaviour
 * and a mistyped tab still lands on Summary rather than on a 404 this lane
 * invented.
 */
// ⚠ **THIS TEST READ `/^PMT-[A-Za-z0-9-]+|<uuid>$/` UNTIL 2026-09-23 AND MATCHED
// NOTHING THE PRODUCT HAS EVER MINTED (`DEF-PAY-6316`, PO-reported on v2.344.0:
// *"Payment detail screen is missing. Selecting a payment redirects to the
// Summary tab"*, and *"Add Correction is missing"* and *"Cancel Payment is
// missing"* as its two consequences).** The pattern was derived from the number
// DRAWN on p036 — `PMT-2609-000418`, cited at `apps/payments/cancel.py:102` —
// which **B14 rule 37 forbids in terms**: *"a figure drawn in a wireframe is an
// ILLUSTRATION, never a fact to build to"*. Every real address was rejected,
// fell through to `paymentsTabFrom`, and landed the clerk on Summary with no
// error and no empty state. `tsc`, every test and every gate passed, because a
// regex that matches nothing is still a valid regex.
//
// **WHAT THE PRODUCT ACTUALLY MINTS** is `core/numbering.py`'s
// `SERIES_CATALOG[PAYMENT]`, whose five offered formats render like this
// (`numbering.render(f, 69, date(2026, 9, 21))`, run against the kernel):
//
//     PY-{YY}{MM}{DD}-{0000}  →  PY-260921-0069   ← the SEEDED DEFAULT
//     PAY-{YYYY}-{00000}      →  PAY-2026-00069
//     P-{000000}              →  P-000069
//     PMT-{YY}-{00000}        →  PMT-26-00069
//     {00000000}              →  00000069         ← NO PREFIX AT ALL
//
// ⚠ **SO THE FIX IS NOT A LONGER PREFIX LIST, AND THAT IS THE WHOLE POINT.**
// The fifth format is in the catalog, `CR-005` calls a plain counter mandatory,
// and it mints a BARE NUMBER — `(PY|PAY|P|PMT)-` would be this same defect one
// tenant away. And the format is **tenant-editable free text**:
// `numbering.validate_format` checks a GRAMMAR (balanced braces, known date
// tokens, exactly one sequence token, a length cap) and accepts any literal
// characters around it, so no enumeration of prefixes can ever be complete.
//
// **What IS guaranteed is a digit.** `validate_format` refuses a format with
// `no_sequence_token`, so every number this product can mint — under every
// catalog format and every format a tenant can save — contains at least one
// digit. Every tab id is lowercase letters and nothing else. That is the
// discriminator, and it is the kernel's own invariant rather than a sample.
//
// **Nothing that works today changes.** The drawn `PMT-` shape still resolves,
// so do the legacy `PMT-DEMO-000001` demo seeds; the tab list is still consulted
// FIRST, so a real tab is never read as a payment; and a mistyped tab — which is
// letters — keeps `paymentsTabFrom`'s deliberate fallback to Summary rather than
// a 404 this lane invented.
const PAYMENT_UUID_RE =
  /^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$/;

/** The one thing `numbering.validate_format` guarantees every minted number has:
 *  a sequence token, rendered as digits. A format with none is refused at save. */
const PAYMENT_NUMBER_HAS_A_DIGIT = /[0-9]/;

/** Is this URL segment a payment, rather than one of the seven tabs? */
export function segmentIsPaymentRef(segment: string | undefined): boolean {
  if (segment === undefined || segment === "") {
    return false;
  }
  if (PAYMENTS_TABS.some((tab) => tab.id === segment) || segment === "collections") {
    return false;
  }
  // The uuid branch stays EXPLICIT and is not folded into the digit test: a uuid
  // may legally carry no digit at all (`abcdefab-abcd-…`), and a link built
  // before B14 rule 31 put the number in the address must not break.
  return PAYMENT_UUID_RE.test(segment) || PAYMENT_NUMBER_HAS_A_DIGIT.test(segment);
}

export function PaymentDetailPage(props: PaymentDetailPageProps) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const navigate = useNavigate();
  const tenantPath = useTenantPath();
  const queryClient = useQueryClient();
  const toast = useToast();
  const routeParams = useParams();
  const paymentRef = props.paymentRef ?? routeParams.paymentRef ?? "";
  const [open, setOpen] = useState<OpenModal>(null);
  // CR-175-BRC10 — Mark returned is a billing clerk's or a System Admin's. A
  // null role (the read has not answered) offers it; the server decides.
  const role = useTenantRole(client);

  // DEF-SHL-3964: `useRegional` and no hand-written fallback (DEF-SHL-9122).
  const { timeZone, dateFormat } = useRegional(props);
  const locale = props.locale ?? "en-US";

  const detailQuery = useQuery({
    queryKey: paymentDetailQueryKey(paymentRef),
    queryFn: () => getPaymentDetail(client, paymentRef),
    retry: false,
    enabled: paymentRef !== "",
  });

  // ⑦ **ITS OWN READ, BECAUSE IT IS PAGINATED.** `NFR-3` — no unpaginated list
  // anywhere, at any tier — and the trail on a much-corrected payment is the
  // one member of this screen that has no ceiling. Folding it into the detail
  // body would serve an unbounded array on the read a clerk opens most.
  const historyQuery = useQuery({
    queryKey: [...paymentDetailQueryKey(paymentRef), "history"],
    queryFn: () => getPaymentHistory(client, paymentRef),
    retry: false,
    enabled: paymentRef !== "",
  });

  // ⚠ **THE TENDER VOCABULARY RIDES ON THE LIST RESPONSE AND ON NOTHING ELSE
  // (`BR-PAY-026`).** `Edit` offers the tenant's own methods, and a hardcoded
  // six here would go stale the first time a utility added *Bill-pay portal* —
  // the exact defect `paymentsShared`'s method picker records. There is no
  // standalone methods read and `GET /payments/{id}` does not serve one, so the
  // smallest honest source is one row of the list. **Enabled only while the
  // Edit modal is open**, so an ordinary page view costs nothing.
  //
  // ⚠ **FILED RATHER THAN WORKED AROUND SILENTLY: `DEF-PAY-6251`** — the detail
  // read should carry `methods[]` beside `actions`, exactly as the list does,
  // and then this second call goes away.
  const methodsQuery = useQuery({
    queryKey: ["payments", "detail-methods"],
    // `per`, not `page_size` — `ListRequest`'s own name (BR-SHL-011).
    queryFn: () => getPayments({ per: 1 }, client),
    retry: false,
    enabled: open === "edit",
  });

  const detail = detailQuery.data;
  // The shell's breadcrumb leaf — which is what draws the drawn
  // `PAYMENTS › PMT-2609-000418`. The NUMBER, never the id (B14 rule 31), and
  // it clears itself on unmount so it cannot outlive this screen.
  useCrumbLeaf(detail?.payment_no ?? null);

  if (detailQuery.isError && isPermissionDenied(detailQuery.error)) {
    return (
      <PermissionDenied
        helper={t("payments.detail.denied")}
        onBack={() => navigate(tenantPath(PAYMENTS_ROUTE))}
      />
    );
  }

  const backTo = {
    // B14 rule 1: the `←` names where it EXITS to, not a step back.
    to: tenantPath(PAYMENTS_ROUTE),
    label: t("payments.title"),
    testId: "payment-detail-back",
  };

  if (detailQuery.isError) {
    return (
      <>
        <PageHeader title={t("payments.detail.title")} backTo={backTo} />
        {/* BR-SHL-020: a plain sentence, never a raw error code alone.
            Cancel goes back to the list, the one thing a clerk can do from a
            failed READ. ⚠ **NO `onDownloadReport` — `DEF-PAY-6435`.** This
            used to pass `() => navigate(<the list>)`, written when the button
            downloaded nothing; since `DEF-SHL-6377` (2.350.2) the button
            downloads its own report and THEN runs the handler, so a clerk who
            pressed it was taken off the page they were reporting. */}
        <FailedWithRetry
          title={t("payments.detail.title")}
          reason={t("api.error.unexpected")}
          onRetry={() => void detailQuery.refetch()}
          onCancel={() => navigate(tenantPath(PAYMENTS_ROUTE))}
        />
      </>
    );
  }
  if (detail === undefined) {
    return (
      <>
        <PageHeader title={t("payments.detail.title")} backTo={backTo} />
        <LoadingSkeleton variant="card" />
      </>
    );
  }

  const actions = detail.actions;
  const markReturned = actions.mark_returned;
  const roleMayReturn =
    role === null || role === ROLE_BILLING_CLERK || role === ROLE_SYSTEM_ADMIN;
  const markReturnedRefusal = !roleMayReturn
    ? t("payments.markReturned.roleOnly")
    : markReturned !== undefined && !markReturned.allowed && markReturned.reason !== null
      ? t(`payments.markReturned.refused.${markReturned.reason}`, {
          defaultValue: t("payments.detail.refused"),
        })
      : undefined;
  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: paymentDetailQueryKey(paymentRef) });
    // The LIST too: a cancel changes a row a clerk may have open behind this
    // page, and a stale figure on the screen you came back to is the same
    // defect as a stale one here.
    await queryClient.invalidateQueries({ queryKey: ["payments", "list"] });
  }

  return (
    <>
      <PageHeader
        // The drawn subtitle: the three facts that identify this money at a
        // glance — amount, instrument, and when it was taken and by whom.
        kicker={t("payments.title")}
        title={detail.payment_no ?? t("payments.row.noNumber")}
        backTo={backTo}
        secondaryActions={
          <>
            {/* ② **Edit** — writes IN PLACE, and only the three columns hard
                rule 4 allows. It EXISTS today as `CorrectReferenceModal`; this
                page is its second door, and reusing the component rather than
                re-drawing the form is B14 rule 43. */}
            <Button variant="secondary" onClick={() => setOpen("edit")}>
              {t("payments.correct.action")}
            </Button>

            {/* ③ **+ Correction** — `+ Noun` because it CREATES a row (B14 rule
                4). Two controls, because they are two rules. */}
            <Button variant="secondary" onClick={() => setOpen("correction")}>
              {t("payments.correction.action")}
            </Button>

            {/* ④ **Cancel — DANGER TIER**, and refused with its REASON rather
                than hidden (BR-SHL-025). The reason is a server CODE and the
                sentence is the catalogue's; a cleared payment's names Reverse,
                because that clerk is not stuck, they are on the wrong door
                (`BR-PAY-021`). */}
            {/* ⚠ `DEF-PAY-10733` (L3-01) — NOT DRAWN ONCE CLEARED. CR-186-BRC10
                (PO 2026-10-21): *"cleared payment cannot be cancled"* — that is
                final, not a state a clerk waits out, so a greyed button is a
                door that never opens. The refusal sentence below still names
                the right door (a refund or a credit). */}
            {detail.status !== "cleared" && (
              <Button
                variant="danger"
                disabled={!actions.cancel.allowed}
                title={
                  actions.cancel.allowed
                    ? undefined
                    : t(`payments.cancel.refused.${actions.cancel.reason}`, {
                        defaultValue: t("payments.detail.refused"),
                      })
                }
                onClick={() => setOpen("cancel")}
              >
                {t("payments.cancel.action")}
              </Button>
            )}

            {/* **Mark returned — DANGER TIER** (CR-175-BRC10, PO 2026-10-07).
                Drawn on an ACH payment ONLY — `offered` is the tender, and the
                ruling is about ACH. Refused with its reason, never hidden, once
                it is drawn (BR-SHL-025). */}
            {markReturned?.offered === true && (
              <Button
                variant="danger"
                disabled={markReturnedRefusal !== undefined}
                title={markReturnedRefusal}
                onClick={() => setOpen("returned")}
              >
                {t("payments.markReturned.action")}
              </Button>
            )}

            {/* **↓ Receipt** — `↓` is B14 rule 4's download glyph and the
                drawing's own label. It touches no money, so no tier. */}
            <Button variant="secondary" onClick={() => setOpen("receipt")}>
              {t("payments.resend.action")}
            </Button>
            {/* **Print receipt** — PO 2026-10-30, Q3 = A: one page, in the
                browser, now (`DEF-PAY-10743`). Touches no money, so no tier. */}
            <PrintReceiptButton paymentId={detail.id} client={client} locale={locale} />
          </>
        }
      />

      {/* The drawn subtitle: the three facts that identify this money at a
          glance. ⚠ **`formatMoney`, NOT `detail.amount` — CLAUDE.md HARD RULE
          2.** Money is STORED to four decimals and DISPLAYS to two, and the
          raw string is `158.100000`. The first build of this line interpolated
          it directly and rendered **`158.100000 · Cheque 4471`** at the top of
          a money screen; `tsc` was happy, every suite was green, and it was
          found by opening the page in a browser (hard-won law 6 — the one
          check in this repository with no tool behind it). */}
      <p className="mb-4 text-base text-neutral-700">
        {t("payments.detail.subtitle", {
          amount: formatMoney(detail.amount, detail.currency, locale),
          method: detail.method_name ?? t("payments.row.noMethod"),
          reference: detail.confirmation ?? t("payments.detail.noReference"),
          // `DEF-PAY-10015` — a payment agent's payment names the agent
          // (*USPayments*); the server decides, from the payment's own key.
          who: detail.source.taken_by ?? t("payments.detail.noTakenBy"),
        })}
      </p>

      {/* ⚠ **A CANCELLED PAYMENT'S REASON IS SHOWN, AND IT IS NOT HIDDEN BEHIND
          THE HISTORY.** A clerk opening a cancelled payment is almost always
          asking *why*; making them read the trail for it is the description
          budget spent in the wrong place (B14 rule 32). */}
      {!actions.cancel.allowed && actions.cancel.reason !== null && (
        <p className="mb-4 text-base text-neutral-700" role="note" data-testid="cancel-refusal">
          {t(`payments.cancel.refused.${actions.cancel.reason}`, {
            defaultValue: t("payments.detail.refused"),
          })}
        </p>
      )}

      <PaymentHeaderStrip
        source={detail.source}
        batchRef={detail.batch_ref ?? null}
        batchHref={
          detail.batch_kind === "deposit" && detail.batch_id != null
            ? tenantPath(depositBatchRoute(detail.batch_id))
            : null
        }
        reconciled={detail.reconciled}
        status={detail.status}
        reversedFor={detail.reversed_for ?? null}
        reversal={detail.reversal ?? null}
      />

      <Panel title={t("payments.detail.thisPayment")}>
        <PaymentFacts
          row={detail}
          currency={detail.currency}
          timeZone={timeZone}
          dateFormat={dateFormat}
          accountHref={tenantPath(accountDetailPath(detail.account_id))}
          billHref={(invoiceId) => tenantPath(billDetailPath(invoiceId))}
        />
        {/* CR-161-BRC10 W5 — the answers typed on Record payment, READ-ONLY.
            No control here can change them: the database refuses it. */}
        <CustomFieldsView
          entity="payments"
          screen="S33"
          values={detail.custom_data ?? {}}
          formatDate={(iso) => formatDate(iso, timeZone, dateFormat)}
          client={client}
        />
      </Panel>

      <Panel title={t("payments.detail.history")}>
        <PaymentHistoryPanel
          rows={historyQuery.data?.results ?? []}
          timeZone={timeZone}
          dateFormat={dateFormat}
          unreadable={
            historyQuery.isError || detail.unavailable.includes(HISTORY_UNREADABLE)
          }
        />
      </Panel>

      {open === "edit" && (
        <CorrectReferenceModal
          client={client}
          payment={detail}
          methods={methodsQuery.data?.methods ?? []}
          onClose={() => setOpen(null)}
          onCorrected={() => {
            setOpen(null);
            void refresh();
          }}
        />
      )}
      {open === "correction" && (
        <AddCorrectionModal
          client={client}
          detail={detail}
          timeZone={timeZone}
          locale={locale}
          dateFormat={dateFormat}
          onClose={() => setOpen(null)}
          onAdded={(result) => {
            setOpen(null);
            toast(
              t("payments.correction.added", {
                number: result.payment_no ?? t("payments.row.noNumber"),
              }),
            );
            void refresh();
          }}
        />
      )}
      {open === "cancel" && (
        <CancelPaymentModal
          client={client}
          detail={detail}
          timeZone={timeZone}
          locale={locale}
          onClose={() => setOpen(null)}
          onCancelled={(result) => {
            setOpen(null);
            // ⚠ **`created: false` IS A REPLAY, NOT A FAILURE** — the STATUS is
            // the idempotency key, so a double-click cancels once. Reported as
            // *already cancelled* rather than as an error, because an error
            // here teaches a clerk to try again.
            toast(
              t(result.created ? "payments.cancel.done" : "payments.cancel.alreadyDone", {
                number: result.reversing_payment_no ?? result.payment_no ?? "",
              }),
            );
            void refresh();
          }}
        />
      )}
      {open === "returned" && (
        <MarkReturnedModal
          client={client}
          detail={detail}
          dateFormat={dateFormat}
          locale={locale}
          onClose={() => setOpen(null)}
          onReturned={(result) => {
            setOpen(null);
            toast(
              t(result.created ? "payments.markReturned.done" : "payments.reverse.replay", {
                number: result.payment_no ?? t("payments.row.noNumber"),
              }),
            );
            void refresh();
            // The reversing row, which carries the bank's code, is a payment
            // with its own page — open it, so the clerk sees what was written.
            if (result.payment_no) {
              navigate(tenantPath(paymentDetailRoute(result.payment_no)));
            }
          }}
        />
      )}
      {open === "receipt" && (
        <ResendReceiptModal
          client={client}
          detail={detail}
          timeZone={timeZone}
          dateFormat={dateFormat}
          onClose={() => setOpen(null)}
          onSent={(result) => {
            setOpen(null);
            const fresh = result.queued.filter((one) => one.created).length;
            toast(
              t(fresh > 0 ? "payments.resend.done" : "payments.resend.alreadyDone", {
                count: fresh > 0 ? fresh : result.queued.length,
              }),
            );
            void refresh();
          }}
        />
      )}
    </>
  );
}

/**
 * The element `App.tsx` mounts at `payments/:tab` — one route, two screens.
 *
 * ⚠ **IT IS A COMPONENT AND NOT A BRANCH INSIDE `PaymentsPage` (B14 rule 43).**
 * Putting the choice inside the tab page would make that page responsible for
 * knowing it is sometimes not itself, which is the *"standalone code inside a
 * page is not reuse"* shape rule 43 was ratified on. Here the decision is one
 * named function, testable on its own, and `App.tsx` changes by one word.
 */
export function PaymentsSegmentRoute(props: PaymentDetailPageProps = {}) {
  const routeParams = useParams();
  if (segmentIsPaymentRef(routeParams.tab)) {
    // `PaymentDetailPage` reads `:paymentRef`; this route's param is `:tab`, so
    // the value is handed over explicitly rather than by both names existing.
    return <PaymentDetailPage {...props} paymentRef={routeParams.tab} />;
  }
  return <PaymentsPage />;
}
