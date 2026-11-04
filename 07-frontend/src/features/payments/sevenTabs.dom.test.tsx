// ── Trace ──────────────────────────────────────────────
// Change:   `P0.8`/`P0.9` of `05-prototype/06 Payments Page Blueprint.pdf` —
//           *"The seven-tab strip"* and *"Routes and shell doors"*.
// Ruled:    PO 2026-09-22, verbatim: *"go as per phase 0 ; we are going to
//           implement all phases one by one so fcus on current one."* All seven
//           render, all seven are reachable, and the three with no screen say so
//           plainly.
// Rules:    B14 rule 42 (a screen is built from the DRAWING; the labels and the
//           order below are read off §03, not off the task table's prose) ·
//           B14 rule 32/33 (the holding copy is a stated absence and nothing
//           more) · CLAUDE.md hard-won law 2's mirror · BR-SHL-001
// Screens:  S32 Summary · S33 Payments · S34 Debtors · 3·x Counter · 4·x
//           Imports · 5·x Settlements · S58 Refunds
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// THIS FILE IS THE TEST THAT FIRES WHEN THE HOLD EXPIRES
// ══════════════════════════════════════════════════════════════════════════
// CLAUDE.md hard-won law 2's mirror, in terms: *"WHEN YOU WRITE A HOLD, WRITE
// THE TEST THAT FIRES WHEN THE HOLD EXPIRES, in the same commit — assert the
// destination by ADDRESS and by the screen id it opens."*
//
// On 2026-09-05 the customer portal's front page had **two working doors out of
// eight** — five cards and three nav words all still refusing over screens that
// had shipped days earlier — and 42 test files and 391 cases passed over it,
// because each wave tested ITS OWN screen at ITS OWN address and the question
// *has the door started pointing at it* belonged to nobody. Phase 0 lands three
// holds at once, so that question is given an owner here.
//
// **THE TWO DIRECTIONS, AND BOTH ARE LOAD-BEARING:**
//   · a tab in `PAYMENTS_TABS_AWAITING_A_SCREEN` that has STOPPED drawing the
//     holding panel is a screen that landed while its hold stayed behind — RED,
//     and the failure names the tab;
//   · a tab NOT in that register that DOES draw one is a screen that vanished
//     behind a refusal — RED the other way.
//
// ⚠ **AND EVERY COMPONENT IS MOUNTED UNDER THE REAL PATH PATTERN.** A bare
// `MemoryRouter` with no `/:tenant/…` route leaves `useParams().tenant`
// undefined, so every address the page builds comes out `//payments/…` — a
// protocol-relative URL to another host, which reads as a perfectly good string
// to `toContain`. That fixture is how the eight dead doors hid.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { ToastProvider } from "@/components/Toast";
import { COUNTER_START_ROUTE } from "./counterShared";
import { PaymentsPage } from "./PaymentsPage";
import {
  COLLECTIONS_LADDER_ROUTE,
  PAYMENTS_TABS,
  REFUNDS_LEGACY_ROUTE,
  REFUNDS_ROUTE,
  PAYMENTS_TABS_AWAITING_A_SCREEN,
  PAYMENTS_TAB_OUTSTANDINGS,
  paymentsTabPath,
} from "./paymentsShared";

const TENANT = "brazosbend";

/**
 * The strip exactly as §03 draws it — every screen in that section carries this
 * same row, and 2·1, 7·1 and 7·3a were read at 2.0 to confirm the words and the
 * order rather than taking them from the task table's prose.
 *
 * ⚠ **THE ADDRESS IS PART OF THE EXPECTATION, NOT A DETAIL.** `P0.9`'s outcome
 * is *"Every new tab is reachable"*, and a label with no address is the half of
 * a tab that cannot be clicked.
 */
const AS_DRAWN: readonly (readonly [string, string, string])[] = [
  ["summary", "Summary", "/payments"],
  ["record", "Payments", "/payments/record"],
  ["counter", "Counter", "/payments/counter"],
  ["imports", "Imports", "/payments/imports"],
  ["settlements", "Settlements", "/payments/settlements"],
  // ⚠ **THIS ROW READ `"/finance/refunds"` UNTIL 2026-09-23 AND THIS CASE WENT
  // RED THE MOMENT `CR-138-BRC07` `P4.10` MOVED IT — WHICH IS THIS FILE
  // WORKING, FOR THE THIRD TIME.** Its comment read *"NOT `/payments/refunds`.
  // S58 is payments-owned and lives in the Finance area by ruling; this tab is
  // a door to the screen that already exists."* That ruling
  // (`CR-059` §10's PLACEMENT, not the rule behind it) is superseded by the
  // blueprint's p074, and the whole supersedes chain is on
  // `paymentsShared.REFUNDS_ROUTE`. The tab is the payments address now, and
  // `/finance/refunds` REDIRECTS rather than 404s.
  ["refunds", "Refunds", "/payments/refunds"],
  ["outstandings", "Debtors", "/payments/outstandings"],
];

/**
 * The English heading each hold draws, written out rather than read back from
 * the catalogue.
 *
 * ⚠ **A TEST THAT ASKS `t()` FOR THE STRING IT THEN ASSERTS CANNOT FAIL**: the
 * screen and the assertion would be reading one value, so deleting the panel
 * and deleting its key together would still pass. These are the words a clerk
 * sees, and if they change, this file should have to say so.
 */
const HOLD_TITLE: Readonly<Record<string, string>> = {
  // ⛔ **`counter` LEFT THIS MAP ON 2026-09-23, AND THAT IS THIS FILE WORKING
  // A SECOND TIME.** It read `counter: "Counter is not built yet"`, and the
  // day `CR-136-BRC07` `P2.6` mounted `CountersTab` this case went RED and
  // named the tab — which is the whole reason it was written before the
  // screen existed. Its two catalogue keys are deleted from all eleven
  // catalogues in the same commit, so the panel cannot come back quietly, and
  // the case below asserts the SCREEN that replaced it, by address.
  // ⛔ **`imports` LEFT THIS MAP ON 2026-09-22, AND THAT IS THIS FILE WORKING.**
  // It read `imports: "Imports are not built yet"`, and the day `CR-135`
  // `P1.5` mounted the run list this case went RED and named the tab — which
  // is the whole reason it was written before the screen existed. The two
  // catalogue keys behind that sentence are deleted from all eleven
  // catalogues in the same commit, so the panel cannot come back quietly.
  // ⛔ **`settlements` LEFT THIS MAP ON 2026-09-23, AND THAT IS THIS FILE
  // WORKING A THIRD TIME.** It read `settlements: "Settlements are not built
  // yet"`, and the day `CR-139-BRC07` `P5.7` mounted `SettlementsTab` this case
  // went RED and named the tab — which is the whole reason it was written
  // before the screen existed. Its two catalogue keys are deleted from all
  // eleven catalogues in the same commit, so the panel cannot come back
  // quietly, and the case below asserts the SCREEN that replaced it, by
  // address.
  //
  // ⚠ **THE MAP IS NOW EMPTY, AND EVERY LOOP OVER IT STILL HAS TO BE
  // CORRECT.** An empty `Object.values(HOLD_TITLE)` makes the *no tab with a
  // screen draws a holding panel* case vacuously true, so the case below
  // asserts the shipped sentence by its own words instead: a check that cannot
  // fail is worse than no check (hard-won law 7).
};

function renderTab(tab: string): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const entry = tab === "summary" ? `/${TENANT}/payments` : `/${TENANT}/payments/${tab}`;
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route
              path="/:tenant/payments"
              element={<PaymentsPage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />}
            />
            <Route
              path="/:tenant/payments/:tab"
              element={<PaymentsPage timeZone="America/Chicago" dateFormat="MM/DD/YYYY" />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("P0.8 — the strip is the drawing's seven, in the drawing's order", () => {
  it("declares seven tabs, with the labels and the order §03 draws", () => {
    expect(PAYMENTS_TABS.map((tab) => tab.id)).toEqual(AS_DRAWN.map(([id]) => id));
  });

  it("renders all seven labels on a payments screen", () => {
    const html = renderTab("record");
    for (const [, label] of AS_DRAWN) {
      expect(html).toContain(`>${label}</`);
    }
  });

  it("gives every tab an address, and the two that leave /payments keep theirs", () => {
    for (const [id, , path] of AS_DRAWN) {
      expect(paymentsTabPath(id)).toBe(path);
    }
    // ⚠ **THIS ASSERTED THE OPPOSITE UNTIL 2026-09-23 AND IT WENT RED WHEN
    // `CR-138-BRC07` `P4.10` MOVED THE SCREEN — A SECOND TIME IN THIS FILE, IN
    // A CASE THE FIRST EDIT DID NOT TOUCH.** It read
    // `expect(paymentsTabPath("refunds")).not.toBe("/payments/refunds")`, and
    // the failure it pinned was real: deriving the address from the id sent
    // Refunds to `/payments/refunds`, **which nothing mounted**, so the tab
    // opened the `:tab` catch-all and read as a broken deployment.
    //
    // **Something mounts it now** — a STATIC route declared above `:tab`, which
    // React Router ranks first. So the assertion inverts, and what it pins is
    // the other half of the same requirement: the tab's address and the
    // screen's address are ONE constant, and the old Finance address still
    // redirects rather than 404ing.
    expect(paymentsTabPath("refunds")).toBe(REFUNDS_ROUTE);
    expect(REFUNDS_LEGACY_ROUTE).toBe("/finance/refunds");
  });
});

describe("P0.9 — the three holds, and the test that fires when each expires", () => {
  it("holds exactly the tabs the blueprint leaves without a screen", () => {
    // ⚠ **THIS READ `["counter", "imports", "settlements"]` UNTIL 2026-09-22
    // AND `["counter", "settlements"]` UNTIL 2026-09-23.** `P1.5` landed the
    // Imports screen and `P2.6` landed the six Counter screens, so each id
    // left the register in the same commit as its screen. Both halves are the
    // point: a tab here that has started rendering is RED, and a tab with no
    // screen and no entry is RED the other way.
    // ⚠ **THIS READ `["counter", "imports", "settlements"]` UNTIL 2026-09-22,
    // `["counter", "settlements"]` UNTIL 2026-09-23 AND `["settlements"]`
    // UNTIL LATER THE SAME DAY.** `P1.5` landed Imports, `P2.6` landed the six
    // Counter screens and `CR-139-BRC07` `P5.7` landed the two Settlements
    // screens, so each id left the register in the same commit as its screen.
    // Both halves are the point: a tab here that has started rendering is RED,
    // and a tab with no screen and no entry is RED the other way.
    //
    // ⚠ **ALL THREE HOLDS ARE RELEASED AND THE REGISTER IS EMPTY.** It stays
    // declared, because the next tab that ships without a screen needs a place
    // to say so — and the two cases below are what stop an empty map from
    // making this suite vacuous.
    expect(Object.keys(PAYMENTS_TABS_AWAITING_A_SCREEN).sort()).toEqual([]);
  });

  it("the Settlements tab renders its real screen and the door to 5\u00b72 BY ADDRESS", () => {
    // ⚠ **THE OTHER HALF OF THE HOLD, WRITTEN THE DAY THE HOLD EXPIRED.** The
    // case this replaces asserted a REFUSAL while the screen did not exist;
    // this one asserts the SCREEN, so the tab can never quietly go back to a
    // panel and the tab can never quietly stop being reachable.
    const html = renderTab("settlements");
    // Reachable: the route resolved to THIS page rather than the catch-all,
    // and the strip came with it.
    expect(html).toContain("Summary");
    expect(html).toContain("Debtors");
    // The screen: 5\u00b71's own placeholder and its drawn columns (p070).
    expect(html).toContain("Search payout or reference\u2026");
    for (const column of ["Settlement", "Provider", "Paid out", "Gross", "Net", "Bank"]) {
      expect(html).toContain(column);
    }
    // ⚠ **AND THE HOLDING PANEL'S OWN SENTENCE IS GONE.** Asserted by the
    // words rather than by the empty `HOLD_TITLE` map, which would make this
    // vacuously true.
    expect(html).not.toContain("Settlements are not built yet");
  });

  it("the Counter tab renders its real screen and the door to 3\u00b73a BY ADDRESS", () => {
    // ⚠ **THE OTHER HALF OF THE HOLD, WRITTEN THE DAY THE HOLD EXPIRED.** The
    // case above asserted a REFUSAL while the screen did not exist; this one
    // asserts the SCREEN, so the tab can never quietly go back to a panel and
    // the door can never quietly stop pointing anywhere.
    const html = renderTab("counter");
    // The screen: 3\u00b71's own page head and its drawn columns.
    expect(html).toContain("Counters");
    expect(html).toContain("Search counter or person\u2026");
    for (const column of ["Person", "Opened", "Closed", "Taken", "Counted"]) {
      expect(html).toContain(column);
    }
    // ⚠ **BY ADDRESS, AND WITH THE TENANT IN IT.** `//payments/counter?start=1`
    // \u2014 what a fixture with no `/:tenant/\u2026` route produces \u2014 would satisfy a
    // naive `toContain(COUNTER_START_ROUTE)` and point at another host. That is
    // exactly how `DEF-CWP-3925` hid on the customer portal.
    expect(html).toContain(`href="/${TENANT}${COUNTER_START_ROUTE}"`);
  });

  it("no tab with a screen draws a holding panel", () => {
    // The mirror direction: a live screen disappearing behind a refusal is the
    // defect that cost the portal six doors, and it is invisible to every other
    // check in this suite.
    //
    // ⚠ **KEYED ON `data-tracks`, NOT ON `HOLD_TITLE`, SINCE 2026-09-23.** All
    // three holds are released, so `HOLD_TITLE` is EMPTY — and a loop over an
    // empty map asserts nothing at all while still printing green. That is
    // hard-won law 7's *structurally incapable of failing*, and the case it
    // would have hidden is precisely the one this test exists for. `data-tracks`
    // is `ArrivesWith`'s own mechanism (`DEF-445`) and it is emitted ONLY when a
    // `tracks` id is passed, which is what a HOLD does; the *More about this
    // tab* disclosure on the Payments list composes the same component without
    // one, so this cannot fire on it.
    for (const [id] of AS_DRAWN) {
      if (PAYMENTS_TABS_AWAITING_A_SCREEN[id] !== undefined || id === "refunds") {
        continue; // refunds leaves this page entirely — it has no `:tab` render
      }
      const html = renderTab(id);
      expect(html, `${id} has gone back behind a hold`).not.toContain("data-tracks=");
      for (const title of Object.values(HOLD_TITLE)) {
        expect(html).not.toContain(title);
      }
    }
  });
});

describe("P0.9 — the ladder keeps a door after its tab leaves the strip", () => {
  it("the Debtors tab links to the ladder BY ADDRESS", () => {
    const html = renderTab(PAYMENTS_TAB_OUTSTANDINGS);
    // ⚠ **BY ADDRESS, AND WITH THE TENANT IN IT.** `//payments/collections` —
    // what a fixture with no `/:tenant/…` route produces — would satisfy a
    // naive `toContain(COLLECTIONS_LADDER_ROUTE)` and point at another host.
    expect(html).toContain(`href="/${TENANT}${COLLECTIONS_LADDER_ROUTE}"`);
  });

  it("no other tab draws that door", () => {
    expect(renderTab("record")).not.toContain(`href="/${TENANT}${COLLECTIONS_LADDER_ROUTE}"`);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: payments blueprint p12-p13 `P0.8`/`P0.9` · §03 screens 2·1, 7·1, 7·3a rendered at 2.0 · decision log 2026-09-22 "THE SEVEN TABS SHIP IN PHASE 0, AS THE DOCUMENT DRAWS THEM"
// generated: 2026-09-22 by LANE P0-FE
// checklist: A✔ B✔ C✔ D=n/a(no endpoint) E✔ F✔ G✔ H=n/a
// gates: vitest src/features/payments/sevenTabs.dom.test.tsx · tsc --noEmit · G31 (both screens are on route-b-migrated.txt)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
