// ── Trace ──────────────────────────────────────────────
// Story:    US-CWP-023 (EP-CWP-06) — the account switcher re-scopes EVERY tab.
//           Screens: CWP-022 and every signed-in screen after it
// Defects:  DEF-CWP-3900 — the switcher's choice was a `useState` INSIDE each
//           page, so choosing `22 Palm Ct` on Usage and then pressing Bills
//           silently put the customer back on `1408 Elm St · A`
// Rules:    BR-CWP-010 (changing the switcher re-scopes every tab, and the
//           scope is applied in the QUERY) · BR-CWP-013 (the set is FLAT) ·
//           B14 rule 31 (no database id is ever the visible value of a field —
//           which is why this id lives in memory and NOT in the address bar)
// Tests:    src/portal/shell/currentAccount.test.tsx
// Impacts:  src/portal/PortalApp.tsx (the provider) · every signed-in
//           `*Page.tsx` (the hook, in place of its own useState)
// ───────────────────────────────────────────────────────
//
// WHY A CONTEXT AND NOT A URL PARAMETER
// -------------------------------------
// `?account=<uuid>` would survive a reload and would be the obvious answer.
// It is refused for the reason `screenIds.ts` already gives twice: *"a uuid in
// a URL is a database id on screen"* (B14 rule 31). The address bar is
// somewhere a person reads and copies. So the choice lives above the router,
// in memory, for the life of the tab.
//
// WHY IT IS MOUNTED ABOVE `useRoutes` AND NOT INSIDE `PortalShell`
// ----------------------------------------------------------------
// `PortalShell` is re-mounted by every page — that is the bug this file
// fixes. `PortalApp` is mounted once for the whole portal and survives every
// tab change, so state held there is the only place a choice can outlive a
// navigation.

import { createContext, useContext, useState, type ReactNode } from "react";

import type { PortalAccount } from "../api/portalClient";

interface Held {
  readonly value: string | null;
  readonly set: (accountId: string | null) => void;
}

const CurrentAccount = createContext<Held | null>(null);

/** Holds the chosen account for the whole portal, above the router. */
export function CurrentAccountProvider(props: { children: ReactNode }) {
  const [value, set] = useState<string | null>(null);
  return <CurrentAccount.Provider value={{ value, set }}>{props.children}</CurrentAccount.Provider>;
}

/**
 * The chosen account and how to change it — the same pair a `useState` gave,
 * so a page swaps one line and nothing else.
 *
 * ⚠ **IT WORKS WITHOUT A PROVIDER, DELIBERATELY.** Every `*Page.tsx` is also
 * rendered on its own by its `.dom.test.tsx`, and a hook that threw there
 * would make thirty-one green tests red for a reason that has nothing to do
 * with what they assert. Without a provider the state is the page's own —
 * which is exactly the behaviour that shipped before this file existed.
 */
export function useCurrentAccount(): [string | null, (accountId: string | null) => void] {
  const held = useContext(CurrentAccount);
  // ⚠ Called UNCONDITIONALLY. React counts hooks, so this must run whether or
  // not a provider is above; only the return value is chosen.
  const [own, setOwn] = useState<string | null>(null);
  return held ? [held.value, held.set] : [own, setOwn];
}

/**
 * Which account a screen is actually reading — the choice when it is still in
 * the set, and the first entry otherwise.
 *
 * ⚠ **THE FALLBACK IS NOT COSMETIC.** A session's set can shrink between two
 * page loads: a delegate's access ends, a landlord's account is closed. The
 * held id then names an account this login may no longer read, and every
 * account-scoped call would answer 404 — a portal that looks broken rather
 * than one that moved the customer to an account they hold. The server is
 * still the guard (`BR-CWP-010`, `_account_in_set`); this only decides what to
 * ASK for.
 */
export function resolveCurrentAccount(
  accounts: readonly PortalAccount[],
  current: string | null,
): string | null {
  if (current !== null && accounts.some((account) => account.id === current)) return current;
  return accounts[0]?.id ?? null;
}
