// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-045 (EP-CWP-09). Screens: CWP-038 `Pay now` · CWP-076 `Check
//           before you pay` · CWP-077 `Payment made` — blueprint 35 · 36 · 37.
// Change:   CR-085 step 2 lane 6. PO 2026-09-11, verbatim: *"it should be 3
//           screens - confirmed"*, and *"ii). Your ruling was about the shape,
//           not the addresses."* — so the SIGNED-IN flow splits IN PLACE, under
//           the address it already occupies, and no guest address moves.
// Rules:    R-10 (PO 2026-09-11, verbatim: *"when a screen tells a customer
//           something bad, the thing they can do about it must be on that same
//           screen, next to the message. Not a page away. Not in a menu. Right
//           there."*) · R-22 (PO 2026-09-11: *"differntiate it using text
//           message"*) · BR-CWP-056 (a control that may not be used is VISIBLE,
//           DISABLED and carries its reason) · BR-CWP-010 (the account is the
//           switcher's) · B14 rule 31 (no database id in an address) · rule 36
//           (compose the kit) · CLAUDE.md hard rule 6 (idempotency)
// Defects:  DEF-CWP-4866 (a `CommitButton` refusal is a `title=` tooltip and
//           NOTHING else — invisible on the phone, which is where people pay)
// Tests:    src/portal/payments/PayNow.dom.test.tsx ·
//           src/portal/payments/PayNowCheck.dom.test.tsx ·
//           src/portal/payments/PayNowDone.dom.test.tsx
// ───────────────────────────────────────────────────────
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { FailedWithRetry, LoadingSkeleton } from "@/components/StateFrame";
import { queryKeys } from "@/api/queryClient";
import { refusalText } from "@/api/refusalText";

import { getPortalFront } from "../api/guestClient";
import { getSession } from "../api/portalClient";
import { PortalShell } from "../shell/PortalShell";
import { resolveCurrentAccount, useCurrentAccount } from "../shell/currentAccount";
import type { PortalPayResult } from "../api/payNowClient";

/**
 * ══ WHAT THE THREE PAY SCREENS SHARE, AND WHY IT IS ONE FILE ══════════════
 *
 * The signed-in payment journey was ONE screen with a `Stepper` inside it
 * (`PayNow.tsx`, 763 lines) until the PO ruled it three. Splitting it produced
 * four things each of the three needs and none of them owns:
 *
 *   * the SHELL — front page + session + account switcher, which was copied
 *     verbatim in every portal page and would now be copied three more times;
 *   * the HANDOFF — what step one hands step two, and step two hands step
 *     three, in **router state and never in the address**;
 *   * `HeldCommit` — a commit control whose refusal is READABLE, which is its
 *     OWN file (`components/heldCommit.tsx`) because the GUEST pay screens need
 *     it too and must not import a signed-in shell to get it;
 *   * `isAboveZero`, which is money arithmetic done on characters.
 *
 * ⚠ **THE HANDOFF TRAVELS IN ROUTER STATE, NOT IN THE URL** — the reading
 * `QuickPayPage.tsx` already records for the guest flow, and it applies harder
 * here: an amount and an instrument id in a query string end up in access logs,
 * in browser history and in a `Referer` header, and an instrument id in an
 * address is a database id on screen (B14 rule 31).
 *
 * ⚠ **AND WHAT IS HANDED ON IS THE CHOICE, NEVER THE ANSWER.** Step two
 * re-prices with the server before it draws a figure — the same discipline
 * `QuickPayCheck` states for the guest flow (*"what step 1 hands on is the
 * PAIR, not the answer"*). A payment that landed in between therefore changes
 * the total the customer reads, which is the one thing screen 36 exists for.
 */

/* ═══════════════════════════════════════════════════════════════════════════
 * 1 · THE HANDOFF
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * What `CWP-038` hands `CWP-076`.
 *
 * ⚠ **`idempotencyKey` IS CARRIED AND IS NEVER RE-MINTED** (`US-CWP-045`
 * TC-7). The preview mints it, step one keeps it, step two presents it on its
 * own re-price — the seam answers `key or mint()` — and the commit sends the
 * same string. A key minted on the screen that commits could never cover the
 * one case it exists for, and a key re-minted at the step boundary would be
 * idempotency that reads correctly and protects nothing.
 */
export interface PayNowHandoff {
  /** A money STRING, exactly as the server serves it. Never a number. */
  amount: string;
  /** The saved instrument's id. Never rendered (B14 rule 31). */
  instrumentId: string;
  idempotencyKey: string;
}

export function payNowHandoffFrom(state: unknown): PayNowHandoff | null {
  if (typeof state !== "object" || state === null) return null;
  const candidate = state as Partial<PayNowHandoff>;
  if (
    typeof candidate.amount !== "string" ||
    typeof candidate.instrumentId !== "string" ||
    typeof candidate.idempotencyKey !== "string"
  ) {
    return null;
  }
  return {
    amount: candidate.amount,
    instrumentId: candidate.instrumentId,
    idempotencyKey: candidate.idempotencyKey,
  };
}

/**
 * What `CWP-076` hands `CWP-077` — **and it is only ever a payment that was
 * actually taken.**
 *
 * ⚠ **THIS PARSER IS THE TRAP THE RULING NAMED, CLOSED IN CODE.** `/pay`'s own
 * route comment records that the lookup ships and the payment does not: no
 * gateway exists on a tenant with no provider connected, so a screen titled
 * *Payment made* must never be reachable unless the server said `paid`. Every
 * other outcome — `declined`, `no_answer`, `refused` — **stays on `CWP-076`
 * with the amount and the method still selected** (R-10: the thing they can do
 * about it is on the same screen, next to the message), so the only way onto
 * this screen is a commit the server answered `paid`. A result of any other
 * outcome arriving here is read as NO result at all, and the screen draws its
 * wrong-turn card.
 */
export function paidResultFrom(state: unknown): PortalPayResult | null {
  if (typeof state !== "object" || state === null) return null;
  const candidate = (state as { result?: unknown }).result;
  if (typeof candidate !== "object" || candidate === null) return null;
  const result = candidate as Partial<PortalPayResult>;
  if (result.outcome !== "paid") return null;
  if (typeof result.amount !== "string") return null;
  return result as PortalPayResult;
}

/** What `CWP-076` hands `CWP-077` beside the result: the balance the SERVER
 *  worked out for after this payment, so the receipt states a figure it did
 *  not compute. `null` when the re-price did not answer one. */
export interface PaidHandoff {
  result: PortalPayResult;
  balanceAfter: string | null;
}

export function balanceAfterFrom(state: unknown): string | null {
  if (typeof state !== "object" || state === null) return null;
  const candidate = (state as { balanceAfter?: unknown }).balanceAfter;
  return typeof candidate === "string" ? candidate : null;
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 2 · MONEY, AS CHARACTERS
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Is this money string above zero? — **no `parseFloat`, no arithmetic**
 * (CLAUDE.md hard rule 2). Money travels as a string beside its currency, and
 * `Number("0.0000")` is the first step down the road that turns `$292.87` into
 * `292.87000000000003`. A decimal amount is above zero exactly when one of its
 * digits is not `0`, which is a question about characters.
 */
export function isAboveZero(amount: string): boolean {
  return /[1-9]/.test(amount);
}

/* ═══════════════════════════════════════════════════════════════════════════
 * 3 · THE SHELL ALL THREE PAGES STAND IN
 * ═══════════════════════════════════════════════════════════════════════════ */

/**
 * Front page + session + the account switcher, once instead of three times.
 *
 * ⚠ **THE ACCOUNT IS RESOLVED ONCE AND USED TWICE** — as the switcher's value
 * and as the payment's scope — so the header and the money cannot name
 * different accounts (`BR-CWP-010`). **No account id reaches the address**: the
 * id travels in the API path, where the server intersects it with the session's
 * set (B14 rule 31).
 *
 * ⚠ **THE FAILED BRANCH IS STILL THE STAFF PANEL, AND THAT IS RECORDED RATHER
 * THAN QUIETLY KEPT.** `FailedWithRetry` offers a customer a *Download error
 * report* button, which is `CPB-17`/R-22's own example of a staff control on a
 * customer screen. It is identical in ~20 portal pages, so replacing it is the
 * frame lane's single change and not three copies of a different one here.
 */
export function PayNowShell(props: {
  client?: ApiClient;
  children: (accountId: string | null) => ReactNode;
}) {
  const { t } = useTranslation();
  const client = props.client ?? api;
  const frontQuery = useQuery({
    queryKey: queryKeys.portalFront,
    queryFn: () => getPortalFront(client),
  });
  const sessionQuery = useQuery({
    queryKey: ["portal", "session"],
    queryFn: () => getSession(client),
  });
  const [current, setCurrent] = useCurrentAccount();

  if (frontQuery.isPending || sessionQuery.isPending) return <LoadingSkeleton variant="card" />;
  if (frontQuery.data === undefined || sessionQuery.data === undefined) {
    return (
      <FailedWithRetry
        title={t("portal.failedTitle")}
        reason={refusalText(t, frontQuery.error ?? sessionQuery.error)}
        onRetry={() => void sessionQuery.refetch()}
        onDownloadReport={() => undefined}
      />
    );
  }
  const session = sessionQuery.data;
  const accountId = resolveCurrentAccount(session.accounts, current);
  return (
    <PortalShell
      front={frontQuery.data}
      displayName={session.customer.display_name}
      accounts={session.accounts}
      currentAccountId={accountId}
      onAccountChange={setCurrent}
    >
      {props.children(accountId)}
    </PortalShell>
  );
}
