// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — §03 frame **3·2 My counter**,
//           `05-prototype/06 Payments Page Blueprint.pdf` p052–p053, read as
//           an IMAGE at scale 2.0 (B14 rule 42).
// Screens:  `PAY-07` — `/:tenant/payments/counter/<code>`
// Rules:    B14 rule 2 (ONE page header — kicker, title, rollup, actions) ·
//           rule 6 (the danger tier on `Close batch`) · rules 12–17 (the
//           payments list underneath keeps the toolbar and the footer) ·
//           rule 31 · rule 33 · rule 40 (the head title is 32px, which
//           `PageHeader` now owns) · rule 43 · rule 21 · BR-SHL-023 (ONE money
//           formatting path) · `CR-136-BRC07` §3.3
// Tests:    src/features/payments/counterScreens.dom.test.tsx
// ───────────────────────────────────────────────────────
// *"What have I taken this shift, and does the drawer match?"* — for the clerk
// on the till, during their shift.
//
// ══════════════════════════════════════════════════════════════════════════
// THE ONE SCREEN WITH NOTHING BEHIND IT AT ALL — p053's own GAP box
// ══════════════════════════════════════════════════════════════════════════
// *"`CounterReceipt` records who took a payment and when — but only for
// application fees on service requests, one source type, and **no screen opens
// it**. There is no session object: nothing opens, nothing closes, nothing
// holds a float."*
//
// ══════════════════════════════════════════════════════════════════════════
// ④ — WHEN THE ID ATTACHES, SAID PLAINLY, BECAUSE A CLERK MUST NEVER WONDER
// ══════════════════════════════════════════════════════════════════════════
// p053's note ④ is one line of screen copy and it carries the ruling of
// 2026-09-21: the batch exists from the moment the till opens, so **every
// payment carries its id from the first one** and closing only seals it.
// *"Every payment carries CTR-260921-DW. Closing counts the drawer."* — two
// sentences, four words and four (B14 rule 33).
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ THE TILES ARE THE SERVER'S SPLIT, NOT A FIXED FOUR
// ══════════════════════════════════════════════════════════════════════════
// p053 draws `Cash · Cheques · Tap and pay · Taken this session`. B14 rule 37
// makes those an illustration of the shape rather than the shape itself: the
// methods a tenant takes are the tenant's, and a utility that takes money
// orders at the window would lose a tile to a hand-typed list. So this renders
// ONE TILE PER METHOD THE SERVER SENDS, then the session total — which is the
// drawing exactly for a tenant taking those three.
//
// The cash tile carries the float as its detail line, which is p053's own
// *"plus $200.00 float"*, and the float is INSIDE the cash figure on the close
// screen rather than netted out (p056's GAP box). One quantity, said twice, in
// the two places a clerk needs it.
import { useState } from "react";

import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import { api, isApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { refusalText } from "@/api/refusalText";
import type { CounterMethodTotal } from "@/api/counterEndpoints";
import { Button, ButtonLink } from "@/components/Button";
import { formatDate } from "@/components/DateCell";
import { KPIStrip } from "@/components/KPIStrip";
import { formatMoney } from "@/components/MoneyCell";
import { PageHeader } from "@/components/PageHeader";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { useTenantPath } from "@/routing/tenantPath";
import { CELL_FULL, useAccessCell, useRegional } from "@/features/metering/meteringShared";
import type { RegionalProps } from "@/features/metering/meteringShared";

import { CloseCounterModal } from "./CloseCounterModal";
import { CounterNote, COUNTERS_ROUTE, FLOAT_RIDES_ON_METHOD_CODE } from "./counterShared";
import { CounterPaymentsTable } from "./CounterPaymentsTable";
import { PAYMENTS_PERMISSION, PAYMENTS_RECORD_NEW_ROUTE } from "./paymentsShared";
import { useCounter } from "./useCounter";

/**
 * ⚠ **THE REGIONAL PAIR AND THE WRITE PERMISSION ARE RESOLVED HERE, NOT
 * PASSED.** This screen is mounted by the ROUTER, which has no props to hand
 * it — exactly as `PaymentsPage` is. The optional overrides exist so a test
 * can state which tenant it is testing rather than inheriting a seed default
 * (`useRegional`'s own docstring says why that matters).
 */
export interface MyCounterPageProps extends RegionalProps {
  client?: ApiClient;
  locale?: string;
  /** Overrides the permission read, for a test that is not about permissions. */
  writeBlockedReason?: string | null;
}

export function MyCounterPage(props: MyCounterPageProps = {}) {
  const { t } = useTranslation();
  const tenantPath = useTenantPath();
  const navigate = useNavigate();
  // Hooks stay unconditional and above every early return.
  const { timeZone, dateFormat } = useRegional(props);
  const cell = useAccessCell(PAYMENTS_PERMISSION, props.client ?? api);
  // BR-SHL-025: "Full" writes; anything else renders the commit disabled WITH
  // its reason. The server refuses regardless — this only saves a round trip.
  const writeBlockedReason =
    props.writeBlockedReason !== undefined
      ? props.writeBlockedReason
      : cell === CELL_FULL || cell === null
        ? null
        : t("payments.rbac.readOnly");
  // ⚠ **THE PARAM IS THE COUNTER'S CODE** — `CTR-260921-DW`, drawn in the
  // address on p052 and kept there by B14 rule 31.
  const { counterCode } = useParams<{ counterCode: string }>();
  const code = counterCode ?? "";
  const [closing, setClosing] = useState(false);
  const counter = useCounter(code, props.client);

  if (counter.isLoading) {
    return <LoadingSkeleton variant="card" />;
  }
  if (counter.isError || counter.data === undefined) {
    // ⛔ `DEF-PAY-10140` — THE SERVER'S REASON, WHEN IT GAVE ONE. This said
    // *"The counter did not answer."* for every failure, including a server
    // that answered precisely (a 422 naming why), so the PO read *did not
    // answer* over a refusal and had nothing to act on. A real refusal now
    // renders its own catalogue sentence through the one refusal path
    // (`refusalText`, BR-SHL-020 r2: the key, never server prose); only a
    // failure that is not an API answer keeps the generic line.
    const failure = counter.error;
    const reason = isApiError(failure)
      ? refusalText(t, failure)
      : t("payments.counter.detail.failedReason");
    return (
      <FailedWithRetry
        title={t("payments.counter.detail.failedTitle")}
        reason={reason}
        onRetry={() => void counter.refetch()}
        onDownloadReport={() => undefined}
        onCancel={() => navigate(tenantPath(COUNTERS_ROUTE))}
      />
    );
  }

  const till = counter.data;
  const open = till.closed_at === null;

  return (
    <div>
      <PageHeader
        // p053 draws `PAYMENTS › COUNTERS › CTR-260921-DW` over **Your
        // counter**. The kicker is the trail; the title is the same three
        // words for every clerk, because it is THEIR till.
        kicker={t("payments.counter.detail.kicker", { counter: till.code })}
        title={t("payments.counter.detail.title")}
        backTo={{ to: tenantPath(COUNTERS_ROUTE), label: t("payments.counter.detail.back") }}
        // ① — `CTR-260921-DW · open since 09/21/2026 08:55 · Dana Whitfield`.
        // The three the requirement names, and they exist from the first
        // payment (p053 ①).
        rollup={
          <span className="text-base text-neutral-700">
            {till.code} ·{" "}
            {/* `DEF-PAY-10732` — both keys carry `{{when}}` and this passed
                none, so the header read *"open since {{when}}"* with the date
                drawn after it. The moment goes INTO the sentence now, so word
                order is each catalogue's own (*"{{when}} に締め"*). */}
            <time dateTime={open ? till.opened_at : (till.closed_at as string)}>
              {t(open ? "payments.counter.detail.openSince" : "payments.counter.detail.closedAt", {
                when: formatDate(
                  open ? till.opened_at : (till.closed_at as string),
                  timeZone,
                  dateFormat,
                  true,
                ),
              })}
            </time>
            {till.owner_name !== null && <> · {till.owner_name}</>}
          </span>
        }
        secondaryActions={
          open ? (
            // The same form as 2·3a, with the batch already known — p053's own
            // *Primary action* row. An ADDRESS rather than a handler, for
            // `DEF-CWP-3925`'s reason.
            //
            // ⚠ **REPOINTED 2026-09-23 (`DEF-PAY-6317`).** It named
            // `PAYMENTS_RECORD_ROUTE`, which is the payments LIST — so p053's
            // *"record a payment"* door put the clerk on a table and made them
            // find the button again. 2·3a has its own address now, and this is
            // the door the blueprint always meant.
            <ButtonLink variant="secondary" to={tenantPath(PAYMENTS_RECORD_NEW_ROUTE)}>
              {t("payments.counter.detail.record")}
            </ButtonLink>
          ) : undefined
        }
        primaryAction={
          open ? (
            // ② — *"Close batch · danger tier — it seals the session and its
            // count · B14 6 · opens 3·3b"*.
            <Button variant="danger" onClick={() => setClosing(true)}>
              {t("payments.counter.close.commit")}
            </Button>
          ) : undefined
        }
      />
      {/* ③ — the running split by method, *"what a till reconciliation
          actually needs"*. One tile per method the server sends, then the
          session total. */}
      <KPIStrip
        kpis={[
          ...till.methods.map((method: CounterMethodTotal) => ({
            id: method.method_id,
            label: method.method_name,
            money: {
              amount: method.system_total,
              currency: till.currency,
              basis: "posting" as const,
              locale: props.locale,
            },
            detail:
              method.method_code === FLOAT_RIDES_ON_METHOD_CODE
                ? t("payments.counter.detail.plusFloat", {
                    // BR-SHL-023: ONE money formatting path. The tile's own
                    // figure goes through `MoneyCell`; this detail line is a
                    // sentence, so it is interpolated already formatted.
                    amount: formatFloat(till.opening_float, till.currency, props.locale),
                  })
                : t("payments.counter.detail.paymentCount", { count: method.payment_count }),
          })),
          {
            id: "taken-session",
            label: t("payments.counter.detail.takenThisSession"),
            money: {
              amount: till.taken_total,
              currency: till.currency,
              basis: "posting" as const,
              locale: props.locale,
            },
            detail: t("payments.counter.detail.paymentCount", { count: till.payment_count }),
          },
        ]}
      />
      {/* ④ — when the id attaches, said plainly, because a clerk must never
          wonder. Two sentences of four words (B14 rule 33). */}
      <CounterNote tone="plain">
        {t("payments.counter.detail.everyPayment", { counter: till.code })}
      </CounterNote>
      <CounterPaymentsTable
        client={props.client}
        counterCode={till.code}
        timeZone={timeZone}
        dateFormat={dateFormat}
        locale={props.locale}
      />
      {closing && (
        <CloseCounterModal
          client={props.client}
          counter={till}
          locale={props.locale}
          writeBlockedReason={writeBlockedReason}
          onClose={() => setClosing(false)}
          onClosed={() => {
            setClosing(false);
            // p059: *"The batch becomes bankable … it appears on Finance →
            // Deposits ready to be matched"*, and the clerk's shift is over —
            // so the way out is the supervisor's list rather than a sealed
            // till they can do nothing more with.
            navigate(tenantPath(COUNTERS_ROUTE));
          }}
        />
      )}
    </div>
  );
}

/** The float, formatted for a sentence rather than for a money cell. It is the
 *  same formatter `MoneyCell` uses — `formatMoney` — reached through the kit,
 *  so there is still exactly one money formatting path (BR-SHL-023). */
function formatFloat(amount: string, currency: string, locale?: string): string {
  return formatMoney(amount, currency, locale);
}

export default MyCounterPage;

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §3.3 · §4 row `P2.6` · blueprint p052–p053 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(`GET /counters/{ref}` is `P2.3`, LANE P2-API's) C✔ D=n/a E✔(routed in App.tsx above `:tab`, and 3·1's row action opens it) F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/counterScreens.dom.test.tsx · G31 · routeBUtilities.test.ts
// exceptions: E3 `GET /counters/{ref}` is NOT SERVED at this commit · E3 the KPI tiles are ONE PER METHOD THE SERVER SENDS rather than the drawn four, because B14 rule 37 makes the drawn set an illustration and the tenant's method list is the tenant's
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
