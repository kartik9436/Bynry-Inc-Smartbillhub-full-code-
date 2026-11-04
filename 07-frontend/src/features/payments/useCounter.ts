// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.6` — §03 frame 3·2 *My counter*,
//           `05-prototype/06 Payments Page Blueprint.pdf` p052–p053.
// Rules:    B14 rule 43 (one piece, one component — three callers) ·
//           rule 31 (the CODE is the key, never the id)
// ───────────────────────────────────────────────────────
// One till, read by its code.
//
// ⚠ **THREE CALLERS, WHICH IS WHY IT IS A HOOK AND NOT A `useQuery` TYPED OUT
// THREE TIMES.** 3·2 reads it to draw the screen; 3·1 reads it to open 3·3d
// over a row that carries no per-method split; and `P2.7`'s *Start counter →*
// will read it to know whether this clerk already has one open. Three spellings
// of one cache key is three chances for a stale till to survive an act on it.
import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";
import type { ApiClient } from "@/api/client";
import { getCounter, getCounters } from "@/api/counterEndpoints";
import type { CounterDetail, CounterRow } from "@/api/counterEndpoints";

import { getMe } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";

import { counterQueryKey, myOpenCounterQueryKey } from "./counterQueries";
import { COUNTER_STATE_FILTER, OPEN_FILTER_VALUE } from "./counterShared";

export function useCounter(code: string, client: ApiClient = api) {
  return useQuery<CounterDetail>({
    queryKey: counterQueryKey(code),
    queryFn: () => getCounter(client, code),
    enabled: code !== "",
  });
}

/**
 * **THE TILL THIS CLERK HAS OPEN, OR NOTHING** — the one read `P2.7`'s page-head
 * slot and `P2.9`'s record banner both need.
 *
 * ⚠ **AT MOST ONE ROW, AND THE DATABASE IS WHY.**
 * `uq_counter_sessions_open_owner` is a partial unique index on
 * `(tenant, owner) WHERE closed_at IS NULL`, so *"my open till"* is a question
 * with one answer or none. Nothing here picks a winner from a list, because
 * there cannot be a list.
 *
 * ⚠ **`f.mine` IS A FILTER ON THE LIST THE DRAWING ALREADY GIVES, NOT A NEW
 * ROUTE.** 3·1's `GET /counters` is the supervisor's list of EVERYONE's tills;
 * narrowing it to the caller is the smallest thing that answers *"is my
 * counter open?"*, and it stays inside BR-SHL-011's `f.<name>` grammar. It is
 * the second contract this lane needs and cannot write — the first is that a
 * counter resolves by its CODE — and both are stated in `P2.6`'s row on the CR
 * so `P2.1`–`P2.3` read them rather than being told in a chat that does not
 * survive (hard-won law 10).
 *
 * ⚠ **A FAILED READ IS NOT *NO TILL*.** The hook hands back the query, so a
 * caller can tell *"you have no counter open"* from *"we could not ask"* — the
 * `DEF-127` shape, where an absence and a failure render identically and the
 * screen states the more alarming one as fact.
 */
// ⛔ **`DEF-PAY-6235` — `f.mine` IS A FILTER `P2.3` HAS NOT BUILT, AND `BE-05`
// DROPS AN UNDECLARED FILTER *SILENTLY* RATHER THAN REFUSING IT.** The version
// of this hook that shipped with `P2.7` asked for `f.mine=1`, capped the page
// at `per: 1` and took `rows[0]`. The docstring above is right that there can
// be at most one row *for one person* — but `GET /counters` is the
// SUPERVISOR'S list of EVERYONE'S tills, so the moment `P2.3` serves it
// WITHOUT `f.mine`, `rows[0]` is *whichever open till the server sorted first*
// and the page head announces a colleague's drawer as **Your counter**, beside
// a button that takes money. Nothing goes red: both states render correctly,
// the read succeeds, and `per: 1` makes the wrong row arrive faster.
//
// **So the caller is matched HERE as well, and that is not belt and braces —
// it is what makes the answer safe under BOTH contracts.** If `P2.3` builds
// `f.mine`, this filter is a no-op over a one-row page. If it does not, this
// IS the filter. The failure direction is now *offer to open one*, never *here
// is a till that might not be yours*.
//
// ⚠ **MATCHED ON `owner_name`, BECAUSE THAT IS WHAT THE ROW CARRIES.** `P2.6`
// serves `owner_name` and no owner id, deliberately — B14 rule 31 keeps ids off
// a screen — so the name is the only join available to a client. `per` is
// dropped with it: capping the page at one row is exactly what stops the right
// row being in it.
export function useMyOpenCounter(client: ApiClient = api) {
  const me = useQuery({ queryKey: queryKeys.me, queryFn: () => getMe(client), retry: false });
  const myName = me.data?.full_name ?? null;
  const counter = useQuery({
    queryKey: myOpenCounterQueryKey(),
    queryFn: () =>
      getCounters(client, {
        [`f.${COUNTER_STATE_FILTER}`]: OPEN_FILTER_VALUE,
        "f.mine": "1",
      }),
    select: (body): CounterRow | null =>
      body.rows.find((row) => row.owner_name === myName) ?? null,
    // Asking before we know who is looking would cache an answer selected
    // against `null` and never re-ask it.
    enabled: myName !== null,
  });
  // ⚠ **`isLoading` COVERS BOTH READS, AND THE `/me` HALF IS THE ONE THAT
  // MATTERS.** A DISABLED React Query is `pending` with `fetchStatus: idle`, so
  // `counter.isLoading` is **false** while the session read is still going.
  // Reading it alone draws `Start counter →` for as long as `/me` takes and
  // then swaps it for `Your counter · … · open` — a control moving under a
  // clerk's cursor in a head whose neighbour is `Record payment`. Both states
  // render correctly, so nothing goes red; found by reading the code.
  //
  // `me.isError` is NOT loading: a session read that failed will not succeed on
  // the next render either, and holding the slot empty for ever over it would
  // take the door off every payments screen. It renders `Start counter →`,
  // which is the safe direction.
  return {
    ...counter,
    isLoading: me.isLoading || (myName !== null && counter.isLoading),
  };
}

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §4 row `P2.6` · blueprint p052–p053 as images at 2.0
// generated: 2026-09-23 by LANE P2-SCREENS
// checklist: A✔ B=n/a(`GET /counters/{ref}` is `P2.3`, LANE P2-API's) C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: tsc --noEmit · vitest src/features/payments/counterScreens.dom.test.tsx
// exceptions: E3 the endpoint is NOT SERVED at this commit
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
