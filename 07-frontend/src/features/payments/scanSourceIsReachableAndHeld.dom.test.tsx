// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-139-BRC07 — the payments blueprint's phase 5, task `P5.15`
//           *"a scan with no barcode fails visibly rather than silently keying
//           nothing"*. The PARSE half is backend and is asserted in
//           `06-backend/tests/test_cr139_p5_remittance.py`; **this is the half
//           a clerk actually meets**, and it is the half `P5.8` will release.
// Screens:  S35 / 4·3a — the ETL runner's Extract stage on the payments
//           target, mounted at `/{tenant}/payments/imports/new`
// Rules:    BR-SHL-025 (a control that cannot be honoured is DISABLED WITH ITS
//           REASON, never hidden) · B14 rule 33 (an instruction ≤ 6 words per
//           sentence) · CLAUDE.md hard-won law 2's mirror (a hold with no test
//           that fires when it expires is a promise nobody is keeping) ·
//           hard-won law 7 *looking at the wrong thing*
// Tests:    this file. The backend end of the same hold is
//           `06-backend/tests/test_cr139_p5_12_to_p5_15.py::test_cr139_p5_15_the_scan_card_stays_held_while_our_own_bills_carry_no_bars`
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY A THIRD FILE ABOUT THIS CARD, WHEN TWO ALREADY ASSERT IT.**
// `paymentsSourceAndWriteMode.test.tsx` renders `<SourceCards choices={…}>`
// with props it hands in itself, and `paymentsRunnerIsReady.dom.test.tsx`
// mounts the runner inside a `<MemoryRouter>` with **a `<Route>` that file
// wrote**. Both are correct about what they assert and **neither can tell a
// working address from a broken one** — which is precisely the fixture flaw
// CLAUDE.md records under hard-won law 2: the customer portal's front page
// tested green for days while every link it built pointed at another host,
// because its test mounted the component bare.
//
// **So every case below goes through `APP_ROUTES`**, the application's own
// route table, at the address `App.tsx` really mounts. Delete that route line
// and these go red on *"there is nothing at this address"* — which is the
// failure a clerk meets and the one no existing case can see.
//
// ⚠⚠ **THIS FILE WAS THE HOLD, AND ON 2026-09-23 THE HOLD EXPIRED. IT IS
// UPDATED DELIBERATELY, WHICH IS WHAT IT WAS WRITTEN FOR.**
//
// It asserted `data-available="false"`, with a failure message that named the
// condition in terms: *"the Scan paper card went live. If `documents.py` now
// draws the bars this hold has expired — release it deliberately, with P5.8's
// input behind it."* **`documents.py` now draws them** (`DEF-BIL-6325`, after
// the PO's *"please enable it and also start putting bar code on bills - we are
// still in beta and uat - we ahve to make these changes now"*), so the sibling
// lane's question was answered rather than argued with, and this file now
// asserts the card is LIVE.
//
// ⚠ **EVERY REACHABILITY ASSERTION IS KEPT, AND THAT IS THE POINT OF NOT
// DELETING IT.** The three cases around the middle one — the runner really is
// at this address, the same assertion at a WRONG address finds nothing, and the
// other seven targets do not draw the card — are what make the middle one worth
// anything. They are the fixture flaw CLAUDE.md records under hard-won law 2:
// the portal's front page tested green for days while every link it built
// pointed at another host.
//
// ⚠ **AND THE PAIRING IS STILL A PAIRING.** The property is not *the card is
// on*; it is **the card is on if and only if our own paper can be scanned**.
// The half that watches the paper is
// `06-backend/tests/test_cr139_p5_12_to_p5_15.py::test_cr139_p5_15_the_scan_card_is_live_now_that_our_own_bills_carry_bars`,
// which reads `kinds.ts` and `documents.py` together, and the half that proves
// the paper actually scans is
// `06-backend/tests/test_def_bil_6325_barcode_round_trip.py`, which decodes a
// rendered bill back to characters. This file is the half a CLERK meets.

import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render } from "@testing-library/react";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { APP_ROUTES } from "@/App";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import { shellBootSeed } from "@/components/shellBootSeed";
import { SEEDED_REGIONAL } from "@/components/tenantRegionalFixture";
import { workflowSourcesFor } from "@/components/workflow";

// ⚠ **THE FILENAME STILL SAYS `AndHeld` AND THE CARD IS NO LONGER HELD.** It is
// NOT renamed: four registers, two backend cases and `kinds.ts` cite this path
// by name, and renaming it moves every one of those citations at once for a
// word — the same reasoning that leaves `OQ-291` as `OQ-291`. What the file
// asserts is stated in its cases, which is where a reader looks.
const TEST_TENANT = "brazosbend";

/** The address `App.tsx` mounts `<ImportWorkflowPage target="payments" />` at.
 *
 *  ⚠ **SPELLED OUT AS A LITERAL, NOT BUILT FROM `PAYMENTS_ROUTE`.** A test that
 *  composes the address from the same constant the router composes it from
 *  agrees with the router by construction and would follow a typo anywhere.
 *  This is the address a clerk's browser holds. */
const EXTRACT_ADDRESS = `/${TEST_TENANT}/payments/imports/new`;

afterEach(cleanup);

function mount(url: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  // The real shell renders no routed screen until it knows the tenant's date
  // format and time zone (DEF-SHL-3964 / DEF-SHL-4272). Without these two
  // seeds every address renders a loading skeleton and every case below would
  // be red for a reason that has nothing to do with the Scan card.
  client.setQueryData(queryKeys.shellDisplay, shellBootSeed(SEEDED_REGIONAL));
  client.setQueryData(queryKeys.regionalSettings, SEEDED_REGIONAL);
  const router = createMemoryRouter(APP_ROUTES, { initialEntries: [url] });
  const view = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return view;
}

describe("P5.15 · the Scan source, at the address a clerk reaches it", () => {
  it("the runner's Extract stage is really at /{tenant}/payments/imports/new", async () => {
    // The precondition every other case here rests on, asserted on its own so
    // that a routing change fails with the right sentence rather than making
    // four cases fail about a card.
    const { container } = mount(EXTRACT_ADDRESS);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(
      container.querySelector('[data-workflow="source-cards"]'),
      `there is no import runner at ${EXTRACT_ADDRESS} — the route App.tsx declares for ` +
        "the payments target has moved or gone, and every Scan-card assertion below is " +
        "about a screen nobody can open",
    ).not.toBeNull();
  });

  it("✅ RELEASED: the Scan paper card is drawn there, LIVE, and refuses nothing", async () => {
    // ⚠ **THE FOUR THINGS THIS CASE NAMED HAVE ALL MOVED, IN THIS ORDER.**
    // 1 · the bars are drawn in `apps/billing/documents.py` — `PageFill`, the
    // filled-rectangle primitive the PDF writer lacked, and `_barcode_rows`
    // drawing `remittance.bars()` on the stub; 2 · `SCAN_PAPER_CARD` is
    // `available: true`; 3 · `workflow.source.scan.notYet` is retired from all
    // eleven catalogues; 4 · `P5.8`'s focused input was already behind the
    // card and is what it opens onto.
    //
    // ⚠ **ORDER, NOT LIST.** The PO's sentence reads *"enable it and also start
    // putting bar code on bills"* — card first. Done that way round, this case
    // would have gone green over a clerk scanning a blank stub. The bars landed
    // first and were proved by DECODING a rendered bill, not by looking at it.
    const { container } = mount(EXTRACT_ADDRESS);
    await new Promise((resolve) => setTimeout(resolve, 0));
    const scan = container.querySelector('[data-workflow-source="scan"]');
    expect(scan, "the Scan paper card is not on the Extract stage at all").not.toBeNull();
    expect(
      scan?.getAttribute("data-available"),
      "the Scan paper card is refused again. Our bills have carried scannable bars since " +
        "DEF-BIL-6325, so a clerk is being told to key what a scanner could read. If the " +
        "BARS were taken off the bill, put the hold back with them — the two move together.",
    ).toBe("true");
    // The retired sentence must not be on the page. i18next answers a missing
    // key with the key itself, so this also catches a catalogue that still
    // carries it (BR-SHL-025 governs a control that CANNOT be honoured; this
    // one can, and B14 rule 33 puts rationale at zero words on screen).
    expect(
      container.textContent,
      "the retired hold sentence is on screen over a LIVE card — a refusal whose stated " +
        "reason has stopped being true (DEF-PAY-6274's shape, hard-won law 2's mirror)",
    ).not.toContain("no barcode bars");
    expect(container.textContent).not.toContain("workflow.source.scan.notYet");
  });

  it("⚠ CONTROL — the same assertion at a WRONG address finds nothing", async () => {
    // ⚠ **THE CASE ABOVE IS ONLY WORTH ANYTHING IF IT CAN FAIL ON THE ADDRESS.**
    // A test that writes its own `<Route>` passes at every URL, which is how a
    // screen can be asserted for days while its door points somewhere else
    // (hard-won law 7's *looking at the wrong thing*, twice on this feature).
    // `/payments/import` is the spelling seven other targets use and the one a
    // reader would guess; nothing is mounted there, and the Scan card must be
    // absent to prove these cases read the router rather than the component.
    const { container } = mount(`/${TEST_TENANT}/payments/import`);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(
      container.querySelector('[data-workflow-source="scan"]'),
      "the Scan paper card rendered at an address App.tsx does not mount the runner at, so " +
        "these cases are not measuring the address at all",
    ).toBeNull();
  });

  it("the payments target is the ONLY one that draws it — the other seven do not", async () => {
    // The regression half, through the router rather than through the kit's
    // own function: a per-target rule goes wrong by leaking onto the others,
    // and `workflowSourcesFor` being right says nothing about what is mounted.
    const { container } = mount(`/${TEST_TENANT}/premises/import`);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(container.querySelector('[data-workflow="source-cards"]')).not.toBeNull();
    expect(
      container.querySelector('[data-workflow-source="scan"]'),
      "the premises runner grew a Scan paper card. Nobody scans a sack of premises, and a " +
        "permanently-refused control on a screen with no paper is B14 rule 32's noise.",
    ).toBeNull();
    expect(workflowSourcesFor("premises").some((card) => card.id === "scan")).toBe(false);
  });
});
