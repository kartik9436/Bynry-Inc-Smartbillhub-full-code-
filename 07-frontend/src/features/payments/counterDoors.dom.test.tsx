// ── Trace ──────────────────────────────────────────────
// Change:   `CR-136-BRC07` `P2.16` — *"`Start counter →` asserted BY ADDRESS on
//           every payments screen"*, blueprint p018. Its own outcome line:
//           *"The test that would have caught the control being missing at
//           all."*
// Screens:  2·1 Payments · 3·1 Counter · 4·1 Imports · 5·1 Settlements ·
//           7·1 Debtors · S32 Summary · 7·3a the collections ladder
// Rules:    B14 rule 4 (`Verb →` navigates) · rule 31 (the CODE, never an id) ·
//           CLAUDE.md hard-won law 2 and its MIRROR (`DEF-CWP-3925`) ·
//           hard-won law 7 (a count beats a loop; a fixture that cannot tell a
//           working link from a broken one)
// Tests:    this file. `CounterDoors.tsx` has NAMED it in its own Trace header
//           since `f77dca804` and **it did not exist** (`DEF-PAY-6263`) — a
//           comment claiming a guarantee is not the guarantee (law 1).
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY THIS FILE, WHEN `sevenTabs.dom.test.tsx` ALREADY ASSERTS A COUNTER DOOR
// ══════════════════════════════════════════════════════════════════════════
// That file asserts the door **on the Counter tab**, where it is 3·1's own
// primary action. `P2.7` is the task that put the same control on the OTHER
// six screens, and `P2.16` is the task that asks whether it is still there.
// Nothing asked that. The whole of `DEF-CWP-3925` is that question belonging
// to nobody: on 2026-09-05 the customer portal had **two working doors out of
// eight** while 42 test files and 391 cases passed, because each wave tested
// ITS OWN screen at ITS OWN address.
//
// ══════════════════════════════════════════════════════════════════════════
// THE SLOT HAS TWO STATES AND BOTH ARE ADDRESSES
// ══════════════════════════════════════════════════════════════════════════
// 2·1 note ①, verbatim: *"when your counter is already open this same slot
// reads **`Your counter · CTR-260921-DW · open`** and is the door back to it"*.
//
// A file that asserted only the first state would be green over a product that
// **offers an act the database refuses**: `uq_counter_sessions_open_owner`
// permits one open till per person, so `Start counter →` shown to a clerk who
// already has one is a button whose only outcome is a refusal. So every screen
// is rendered twice, and the SECOND state is asserted at the same strength as
// the first — by address, and by the code in that address.
//
// ══════════════════════════════════════════════════════════════════════════
// TWO THINGS THAT WOULD MAKE THIS WHOLE FILE PASS WRONGLY
// ══════════════════════════════════════════════════════════════════════════
// **1 · A FIXTURE THAT CANNOT TELL A WORKING LINK FROM A BROKEN ONE.** Mounted
// in a bare `MemoryRouter` with no `/:tenant/…` route, `useParams().tenant` is
// undefined and every address the page builds comes out `//payments/counter` —
// a protocol-relative URL to ANOTHER HOST, which reads as a perfectly good
// string to `toContain`. That fixture is exactly how the eight dead doors hid.
// Every render below goes through the real path pattern and every assertion
// carries `/${TENANT}` inside the quoted `href=`.
//
// **2 · A HAND-WRITTEN LIST OF SCREENS.** A list typed out here would be
// complete on the day it was written and silently short the day an eighth tab
// arrives — and the failure would be an ABSENCE, which is invisible to every
// check this repository has. So the scope is DERIVED from `PAYMENTS_TABS`, the
// same constant the strip itself renders from, and the one exclusion is named
// with its reason and asserted rather than assumed.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { queryKeys } from "@/api/queryClient";
import type { CounterRow } from "@/api/counterEndpoints";
import { ToastProvider } from "@/components/Toast";

import { CollectionsPage } from "./CollectionsPage";
import { RefundsPage } from "./RefundsPage";
import { myOpenCounterQueryKey } from "./counterQueries";
import { COUNTERS_ROUTE, COUNTER_START_ROUTE, counterRoute } from "./counterShared";
import { PaymentsPage } from "./PaymentsPage";
import {
  COLLECTIONS_LADDER_ROUTE,
  PAYMENTS_TABS,
  PAYMENTS_TAB_REFUNDS,
  paymentsTabPath,
} from "./paymentsShared";

const TENANT = "brazosbend";
const OWNER = "D. Whitfield";
const CODE = "CTR-260921-DW";

/**
 * **THE SCREENS `P2.16` MEANS BY *every payments screen*, DERIVED.**
 *
 * `PAYMENTS_TABS` is the strip's own source of truth, so an eighth tab is in
 * scope here the day it is declared rather than the day somebody remembers.
 *
 * ⚠ **REFUNDS WAS THE ONE EXCLUSION UNTIL 2026-09-23 AND IS NOW IN SCOPE —
 * THIS FILE SAID EXACTLY WHAT WOULD MAKE THAT HAPPEN, AND IT HAPPENED.** The
 * comment here read: *"Its path is `/finance/refunds`: S58 is payments-owned
 * and lives in the FINANCE area by ruling, and `RefundsPage` draws the FINANCE
 * tab strip, not this one. It is a door OUT of payments to a screen that
 * already exists…"* — and the case below added *"If it is ever re-homed into
 * this strip — the blueprint's 6·1–6·3c work — this goes RED and this file has
 * to say what it now means by *every*."*
 *
 * `CR-138-BRC07` `P4.10` is that work. `REFUNDS_ROUTE` is `/payments/refunds`,
 * `RefundsPage` draws THIS strip with **Refunds** selected, and a clerk
 * standing on it IS standing on a payments screen. **So *every* now means all
 * seven tabs plus the ladder, and the screen carries `CounterHeadSlot` like
 * its siblings.** The exclusion is gone rather than re-justified, which is what
 * the case asked for.
 */
const TAB_SCREENS = PAYMENTS_TABS.map((tab) => tab.id);

/** 7·3a — a static route of its own, and `DEF-PAY-6237` is that it was missed.
 *  Its tab left the strip with the drawing and its screen did not. */
const LADDER = "collections";

const SCREENS: readonly string[] = [...TAB_SCREENS, LADDER];

function openTill(over: Partial<CounterRow> = {}): CounterRow {
  return {
    code: CODE,
    owner_name: OWNER,
    service_centre_name: "Main counter",
    opened_at: "2026-09-21T08:55:00Z",
    closed_at: null,
    close_kind: null,
    declared_at: null,
    declared_by_name: null,
    payment_count: 17,
    taken_total: "1996.7500",
    counted_total: null,
    difference: null,
    currency: "USD",
    ...over,
  };
}

/**
 * Render one payments screen at its real address, with the world stated.
 *
 * `mine` is the body `GET /counters` would have returned. `useMyOpenCounter`
 * runs its own `select` over whatever is in the cache, so seeding the BODY (not
 * the selected row) is what exercises the hook's own matching — the clause
 * `DEF-PAY-6235` added, where `rows[0]` off the supervisor's list of everyone's
 * tills was being announced as *Your counter*.
 */
function render(screen: string, mine: CounterRow[] | null): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.me, {
    id: "u-dana",
    full_name: OWNER,
    email: "dana@brazosbendutilities.com",
    phone: null,
    role: "system_admin",
    role_name: "System Admin",
    must_change_password: false,
  });
  if (mine !== null) {
    queryClient.setQueryData(myOpenCounterQueryKey(), {
      rows: mine,
      count: mine.length,
      totals: {
        open_now: mine.length,
        open_owner_names: mine.map((one) => one.owner_name ?? ""),
        taken_today: "1996.7500",
        taken_today_payment_count: 17,
        not_counted: 0,
        not_counted_oldest: null,
        difference_this_week: "0.0000",
        currency: "USD",
      },
    });
  }
  const at =
    screen === LADDER
      ? `/${TENANT}${COLLECTIONS_LADDER_ROUTE}`
      : `/${TENANT}${paymentsTabPath(screen)}`;
  // ⚠ **THREE SCREENS, NOT TWO, SINCE `P4.10` (2026-09-23).** Refunds is a
  // payments screen now and it is its OWN static route — `RefundsPage`, not a
  // `:tab` of `PaymentsPage` — exactly as the ladder is. Rendering
  // `PaymentsPage` for it would mount the wrong component at the right address
  // and the door would be asserted on a screen nobody opens.
  const node =
    screen === LADDER ? (
      <CollectionsPage today="2026-09-21" />
    ) : screen === PAYMENTS_TAB_REFUNDS ? (
      <RefundsPage />
    ) : (
      <PaymentsPage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />
    );
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[at]}>
          <Routes>
            {/* ⚠ **THE REAL PATTERNS.** Without `:tenant`, `useTenantPath`
                builds `//payments/counter?start=1` — a protocol-relative URL to
                another host that satisfies a naive `toContain`. */}
            <Route path="/:tenant/payments" element={node} />
            <Route path="/:tenant/payments/:tab" element={node} />
            <Route path="/:tenant/payments/collections" element={node} />
            {/* The static sibling `P4.10` added — declared here because
                `/:tenant/payments/:tab` would otherwise swallow it, which is
                the DEF-520 lesson the app's own router obeys too. */}
            <Route path="/:tenant/payments/refunds" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * ⚠ **THE WHOLE ASSERTION IS THIS STRING, AND EVERY PART OF IT IS LOAD-BEARING.**
 * `href="` pins it to a real anchor rather than to any text that happens to
 * contain the route; `/${TENANT}` is what a fixture with no `/:tenant/…` route
 * cannot produce; and the closing quote stops `/payments/counter?start=1`
 * matching some longer address that merely begins the same way.
 */
const START_HREF = `href="/${TENANT}${COUNTER_START_ROUTE}"`;
const YOURS_HREF = `href="/${TENANT}${counterRoute(CODE)}"`;

describe("P2.16 — `Start counter →` is on every payments screen, BY ADDRESS", () => {
  it("has EIGHT screens in scope now that Refunds is a payments screen", () => {
    // The count is asserted so that a tab quietly leaving `PAYMENTS_TABS`
    // shrinks this file's scope LOUDLY rather than silently.
    expect(SCREENS).toHaveLength(8);
    expect(SCREENS).toContain("counter");
    expect(SCREENS).toContain(LADDER);
    // ⚠ **THIS ASSERTED THE OPPOSITE UNTIL 2026-09-23 AND WENT RED ON `P4.10`,
    // WHICH IS THIS CASE WORKING.** It read `not.toContain(REFUNDS)` and
    // `paymentsTabPath(REFUNDS).startsWith("/payments")).toBe(false)`, over a
    // tab that pointed at `/finance/refunds`. The screen was re-homed, so the
    // scope grew and the assertion inverts — and what it pins is the same
    // requirement read the other way: a screen inside this strip is a payments
    // screen, and a payments screen carries the till door.
    expect(SCREENS).toContain(PAYMENTS_TAB_REFUNDS);
    expect(paymentsTabPath(PAYMENTS_TAB_REFUNDS).startsWith("/payments")).toBe(true);
  });

  it("every one of the seven offers the door when no till is open", () => {
    // ⚠ **A COUNT, NOT A LOOP.** `for (const s of SCREENS) expect(...)` is green
    // when `SCREENS` silently shrinks to nothing, which is precisely how a
    // derived scope fails. So each screen's verdict is collected and the
    // collection is compared whole — a missing screen is named, and a scope
    // that vanished fails on the length.
    const missing = SCREENS.filter((screen) => !render(screen, []).includes(START_HREF));
    expect(missing).toEqual([]);
    expect(SCREENS.filter((screen) => render(screen, []).includes(START_HREF))).toHaveLength(8);
  });

  it("the door carries the drawn words, and they are written out here", () => {
    // ⚠ **NOT `t("payments.counter.action.start")`.** A case that asks the
    // catalogue for the string it then asserts cannot fail: the screen and the
    // assertion read one value, so deleting the key from both would still pass.
    // These are the words a clerk sees; if they change, this file should have
    // to say so. B14 rule 4 gives the arrow because the control NAVIGATES.
    const html = render("record", []);
    expect(html).toContain("Start counter →");
  });

  it("with a till open, every one of the seven becomes the door BACK to 3·2", () => {
    // 2·1 ①'s second state. The address carries the till's CODE and never its
    // id (B14 rule 31), which is also why this can be asserted at all.
    const rows = [openTill()];
    const missing = SCREENS.filter((screen) => !render(screen, rows).includes(YOURS_HREF));
    expect(missing).toEqual([]);
    // And the way IN is gone from those same screens: a slot that offered both
    // would be offering an act `uq_counter_sessions_open_owner` refuses.
    const stillOffering = SCREENS.filter((screen) => render(screen, rows).includes(START_HREF));
    expect(stillOffering).toEqual([]);
  });

  it("the open state names the counter rather than showing a database id", () => {
    const html = render("record", [openTill()]);
    expect(html).toContain(`Your counter · ${CODE} · open`);
    expect(html).toContain(YOURS_HREF);
  });

  it("a colleague's open till is NOT announced as yours", () => {
    // ⛔ `DEF-PAY-6235`'s shape, kept red-able. `GET /counters` is the
    // SUPERVISOR'S list of everyone's tills; if `f.mine` is ever dropped or
    // silently ignored, the only thing standing between a clerk and a
    // colleague's drawer announced as *Your counter* — beside a button that
    // takes money — is the hook's own match on the caller. This states the
    // world where the server answered with somebody else's row.
    const theirs = [openTill({ code: "CTR-260921-MV", owner_name: "M. Vega" })];
    const html = render("record", theirs);
    expect(html).not.toContain("CTR-260921-MV");
    expect(html).toContain(START_HREF); // offered their own, which is the safe direction
  });

  it("the address is the one the Counter tab itself answers on", () => {
    // ⚠ **THE OTHER HALF OF A DOOR IS THAT SOMETHING OPENS.** An `href` nothing
    // mounts is `DEF-CWP-3925` exactly: a control that looks live and opens the
    // catch-all. `COUNTER_START_ROUTE` is the Counter tab's own path plus the
    // query that opens 3·3a, so this asserts the two have not drifted apart.
    expect(COUNTER_START_ROUTE.startsWith(`${COUNTERS_ROUTE}?`)).toBe(true);
    expect(paymentsTabPath("counter")).toBe(COUNTERS_ROUTE);
    // And the tab really renders 3·1 rather than a holding panel.
    expect(render("counter", [])).toContain("Counters");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-136-BRC07 §4 row `P2.16` · blueprint p018 (the task) and p030 note ① (the two states), read as an image at 2.0
// generated: 2026-09-23 by LANE P2-TESTS
// checklist: A✔ B=n/a(no endpoint) C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: vitest src/features/payments/counterDoors.dom.test.tsx · tsc --noEmit
// exceptions: E3 Refunds is out of scope and the reason is asserted, not assumed — its screen draws the FINANCE strip
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
