// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   `CR-137-BRC07` `P3.16` (the REVERSAL commit carries the danger
//           class) · `P3.17` (the swap cannot half-land — the panel is gone
//           AND the page is present, in ONE test) · `P3.21` (`J12-nsf-life`
//           regression: the bounce path the tier change touches)
// Screens:  2·2 (`S33`) · 2·3e Reverse (`S35`) · 2·1 the list
// Rules:    B14 rule 6 (danger tier on the destructive commit) · rule 31 (no
//           database id is a visible value) · CLAUDE.md hard-won law 2 (built
//           is not wired, BOTH directions) · law 7 (looking at the wrong thing)
// ───────────────────────────────────────────────────────
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHY THIS IS A NEW FILE AND NOT THREE MORE CASES IN A SIBLING
// ══════════════════════════════════════════════════════════════════════════
// `paymentDetailPage.dom.test.tsx` belongs to lane P3-PAGE and
// `reversePayment.test.tsx` to `CR-059` CS-5; phase 2 is running in parallel on
// this branch with six lanes. A whole-file write to either is how a sibling's
// hunks get reverted invisibly (CLAUDE.md law 11), and neither file's subject
// is *the tier*. So these three live together, because they are one subject:
// **what `P3.12` changed, and what must not half-land around it.**
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHAT `P3.16` FOUND, AND IT IS WHY THE TASK EXISTED
// ══════════════════════════════════════════════════════════════════════════
// The task board says *"B14's own record names a `FormModal` commit as the
// unchecked case"*. Measured on 2026-09-23, across the whole of
// `07-frontend/src`: **`border-danger-500` was asserted on a rendered commit in
// eleven files, and on NO `ReversePaymentModal` anywhere.** `reversePayment
// .test.tsx` — 33 cases, the file that owns this modal — contains the string
// `danger` zero times. `paymentDetailPage.dom.test.tsx` asserts the class on
// the **Cancel** modal's commit, which is a different component built by a
// different task (`P3.11`). So `P3.12`'s one-line change had no test at all,
// and `PaymentsPage.tsx` says so in its own words beside it: *"`P3.16` is the
// test that closes it."*
//
// ══════════════════════════════════════════════════════════════════════════
// ⚠ WHAT WOULD MAKE EACH CASE HERE PASS WRONGLY (law 7, habit 2)
// ══════════════════════════════════════════════════════════════════════════
//   * **A build that reddened every commit in the product.** `border-danger-500`
//     on Reverse is satisfied by a stylesheet change that danger-tiers the
//     shared `WorkingButton`. So the SAME case asserts a neighbour commit is
//     NOT danger — `Save correction`, which `P3.12` names as its own control
//     because the drawing rules it *"not danger tier — it moves no money by
//     construction"*.
//   * **Asserting the PROP instead of the rendered class.** `submitVariant`
//     reaching the component proves nothing about what a clerk sees; the class
//     is read off the DOM node, as `P3.11`'s sibling case already does.
//   * **`P3.17` proving the page exists by IMPORTING it.** A test file that
//     imports `PaymentDetailPage` and mounts it under a hand-written `<Route>`
//     proves the component compiles. It does **not** prove the app routes
//     anybody to it — that is law 7's *looking at the wrong thing*, recorded in
//     CLAUDE.md as a hold-expiry test asserting a screen was registered at an
//     address while the router mounted it somewhere else. So `P3.17` reads the
//     REAL `APP_ROUTES` table.
//   * **`P3.21` asserting the bounce form renders.** Rendering is not
//     submitting, and the tier change touched the SUBMIT button. So the case
//     drives the form and reads the POST body off the client.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { RouteObject } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { APP_ROUTES } from "@/App";
import type { ApiClient } from "@/api/client";
import type { PaymentRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import {
  CorrectReferenceModal,
  ReversePaymentModal,
  paymentsCells,
  paymentsTableConfig,
} from "./PaymentsPage";
import { PaymentsSegmentRoute, segmentIsPaymentRef } from "./PaymentDetailPage";
import type { Translator } from "@/features/tenancy/settingsShared";

const t: Translator = (key, params) => i18n.t(key, params);
const TENANT = "brazosbend";

afterEach(() => cleanup());

/** PE-7's payment, the figure `J12-nsf-life` is written against. */
const BOUNCED = {
  id: "pay-1042",
  payment_no: "PMT-2607-001042",
  account_id: "acc-1042",
  account_no: "ACC-1042",
  customer_name: "Ana Alvarez",
  amount: "292.8700",
  currency: "USD",
  status: "cleared",
  type: "payment",
  method: "check",
  confirmation: "8842",
  memo: null,
  purpose: "bill",
  posted_at: "2026-07-18",
  cleared_at: "2026-07-21",
  applied_to: [],
  deposit_batch_id: null,
  receipt_no: null,
} as unknown as PaymentRow;

const METHODS = [
  { id: "m-check", code: "check", name: "Cheque" },
  { id: "m-cash", code: "cash", name: "Cash" },
] as never;

function client(): ApiClient {
  return {
    get: vi.fn(async () => ({ status: 200, data: { results: [] }, headers: new Headers() })),
    post: vi.fn(async () => ({
      status: 201,
      data: {
        payment_id: "pay-1042",
        reversing_payment_no: "PMT-2608-001199",
        amount: "-292.8700",
        reopened: [],
        nsf_count: 1,
        bank_fee: "30.0000",
      },
      headers: new Headers(),
    })),
  } as unknown as ApiClient;
}

/**
 * ⚠ **THE REAL PATH PATTERN, INCLUDING `:tenant`.**
 *
 * A bare `MemoryRouter` leaves `useParams().tenant` undefined, so every address
 * the component builds comes out `//payments/…` — a protocol-relative URL to
 * another host, which `toContain` reads as a perfectly good string. That is how
 * eight dead doors hid on the customer portal (CLAUDE.md law 2).
 */
function mount(node: JSX.Element, at = `/${TENANT}/payments/record`) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={[at]}>
          <Routes>
            <Route path="/:tenant/payments/:tab" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// P3.16 — the REVERSAL commit carries the danger class
// ══════════════════════════════════════════════════════════════════════════

describe("P3.16 — B14 rule 6 on a `FormModal` commit, the row B14 calls unchecked", () => {
  it("the Reverse commit is danger-tiered, and Save correction is NOT", async () => {
    // ⚠ **ONE CASE, TWO MODALS, AND THAT IS THE DESIGN.** Split across two
    // cases, a build that danger-tiered every commit in the product would show
    // one green and one red and a reader would fix the wrong one. Together they
    // say what rule 6 actually requires: the tier is a CHOICE, applied to the
    // commit that destroys and withheld from the commit that does not.
    const reverse = mount(
      <ReversePaymentModal
        client={client()}
        payment={BOUNCED}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onReversed={() => undefined}
      />,
    );
    const commit = await screen.findByRole("button", { name: t("payments.reverse.submit") });
    // THE RENDERED CLASS, never the prop — `submitVariant` reaching the
    // component says nothing about what a clerk sees.
    expect(commit.getAttribute("class")).toContain("border-danger-500");
    expect(commit.getAttribute("class")).toContain("text-danger-700");
    reverse.unmount();

    // THE CONTROL — `P3.12`'s own, named in the blueprint at §03 frame 2·3e:
    // *"Not danger tier — it moves no money by construction."*
    mount(
      <CorrectReferenceModal
        client={client()}
        payment={BOUNCED}
        methods={METHODS}
        onClose={() => undefined}
        onCorrected={() => undefined}
      />,
    );
    const save = await screen.findByRole("button", {
      name: t("payments.correct.submit"),
    });
    expect(save.getAttribute("class")).not.toContain("border-danger-500");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// P3.17 — the swap cannot half-land
// ══════════════════════════════════════════════════════════════════════════

/** Every `path` in the real route table, flattened, as `screenIds.test.tsx` does. */
function flatten(routes: readonly RouteObject[], parent = ""): string[] {
  const out: string[] = [];
  for (const route of routes) {
    const here = [parent, route.path ?? ""].filter(Boolean).join("/");
    if (route.path !== undefined) out.push(here);
    if (route.children) out.push(...flatten(route.children, here));
  }
  return out;
}

function routeAt(routes: readonly RouteObject[], want: string): RouteObject | null {
  for (const route of routes) {
    if (route.path === want) return route;
    if (route.children) {
      const found = routeAt(route.children, want);
      if (found) return found;
    }
  }
  return null;
}

describe("P3.17 — the panel is GONE and the page is PRESENT, in one test", () => {
  it("both halves at once: no expander in the table, and the real router opens the page", () => {
    // ⚠ **WHY BOTH HALVES MUST BE ONE CASE.** `P3.10`'s own sentence is *"not
    // before — no way to see what a payment paid off; not later — two answers
    // to one question"*. Each half alone is green in exactly the state the
    // other half forbids: a build that deleted the panel and never routed the
    // page passes *"the panel is gone"*, and a clerk who clicks the 👁 lands
    // on the Summary tab with nothing saying so. One assertion cannot be
    // satisfied by the broken state the other names.
    //
    // ⚠ **AND THE ASSERTION BELOW IS WEAKER THAN ITS NAME, WHICH IS WORTH
    // SAYING RATHER THAN HIDING — `DEF-PAY-6261`.** `P3.10` removed the
    // expander from the CALLER's extras and left the seam standing:
    // `PaymentsTableExtras.renderExpanded` is still declared, and
    // `paymentsTableConfig` still threads `renderExpanded: extras
    // .renderExpanded`. So the config resolves to `undefined` only because no
    // caller passes one, and re-adding the row panel is a one-line change
    // nothing would refuse. **The RED PROOF of this case is what found it:**
    // declaring `renderExpanded` at the TOP of the returned object left every
    // case green, because the pass-through further down overrides it. Filed;
    // not removed here, because `PaymentsPage.tsx` is a 4,000-line file six
    // lanes are editing and a whole-file write there reverts a sibling (law 11).
    //
    // ⚠ **AND THIS IS WHY IT IS NOT ALREADY COVERED.**
    // `paymentDetailPage.dom.test.tsx` has a describe block titled *"P3.10 —
    // the swap cannot half-land"*, and its three cases are the panel half, the
    // link half and the icon cap — each in its OWN case, and the page half is
    // proved by mounting `PaymentDetailPage` inside a hand-written `<Route
    // path="/:tenant/payments/:paymentRef">` that **the application does not
    // have**. `App.tsx` mounts `PaymentsSegmentRoute` at `payments/:tab`. A
    // test that declares its own route pattern is testing its own fixture.

    // ── HALF ONE: the row panel is gone ──────────────────────────────────
    const cells = paymentsCells(t, (path) => `/${TENANT}${path}`, "UTC", "MM/DD/YYYY");
    expect(paymentsTableConfig(t, cells).renderExpanded).toBeUndefined();

    // ── HALF TWO: the REAL router opens the page at the address the 👁 builds ─
    const address = cells.detailTo({ payment_no: "PMT-2609-000418", id: "x" } as never);
    expect(address).toBe(`/${TENANT}/payments/PMT-2609-000418`);
    // NOT `//payments/…` — a missing tenant segment produces a protocol-relative
    // URL to another host and every `toContain` in the suite reads it as fine.
    expect(address.startsWith("//")).toBe(false);

    // The address the 👁 builds has THREE segments after the tenant's, so the
    // route that must catch it is `payments/:tab` — and it must be mounted.
    // ⚠ **THE FULL PATTERN, `:tenant` INCLUDED.** The raw `path` on the route
    // object is `payments/:tab` and it is mounted under a `:tenant` parent; a
    // check that only read the raw segment would stay green on the day
    // somebody re-parented payments outside the tenant, which is the one
    // change that would break every address on this screen at once.
    const paths = flatten(APP_ROUTES);
    expect(paths).toContain("/:tenant/payments/:tab");
    const segment = routeAt(APP_ROUTES, "payments/:tab");
    expect(segment).not.toBeNull();
    // ⚠ **IDENTITY, NOT A NAME.** `resolve(path).func.__name__` is `"view"` for
    // every `@api_view` in the backend and a route element's `type.name` is
    // minified in a production build; comparing the function object itself is
    // the only form that cannot pass on the wrong component.
    const element = segment?.element as { type?: unknown } | undefined;
    expect(element?.type).toBe(PaymentsSegmentRoute);

    // And that component genuinely answers a `PMT-` segment with the detail —
    // the one named function the route delegates the decision to.
    expect(segmentIsPaymentRef("PMT-2609-000418")).toBe(true);
    expect(segmentIsPaymentRef("summary")).toBe(false);
  });

  it("mounted through the REAL segment route, a PMT- address draws the page", async () => {
    // The end of the same walk: not *"is it registered"* but *"does the thing
    // that is registered render the screen"*. Mounted at `payments/:tab`
    // because that is the pattern `App.tsx` uses — the page reads `:tab` here,
    // not `:paymentRef`, and a fixture declaring `:paymentRef` would hide a
    // rename of that param forever.
    const detailClient = {
      get: vi.fn(async (path: string) => {
        if (path.includes("/history")) {
          return {
            status: 200,
            data: { results: [], count: 0, next: null, previous: null },
            headers: new Headers(),
          };
        }
        if (path.startsWith("/payments/")) {
          return {
            status: 200,
            data: {
              id: "8f14e45f-ea5c-4f31-9c1b-0c2c0a1a7d11",
              payment_no: "PMT-2609-000418",
              account_id: "acc-1",
              account_no: "AC-2026-00001",
              customer_name: "Ana Alvarez",
              type: "payment",
              method: "check",
              method_name: "Cheque",
              confirmation: "4471",
              memo: null,
              amount: "158.100000",
              currency: "USD",
              status: "processing",
              purpose: "bill",
              posted_at: "2026-09-21",
              cleared_at: null,
              applied_to: [],
              origin: "entry",
              batch_ref: null,
              source: {
                origin: "entry",
                origin_is_derived: false,
                taken_by: null,
                counter_session_ref: null,
              },
              reconciled: null,
              actions: {
                edit: { allowed: true, reason: null, tender_locked: false },
                correction: { allowed: true, reason: null },
                cancel: { allowed: true, reason: null },
                receipt: { allowed: true, reason: null },
              },
              receipts: [],
              next_copy_no: 2,
              unavailable: [],
            },
            headers: new Headers(),
          };
        }
        return { status: 200, data: { results: [], methods: [] }, headers: new Headers() };
      }),
      post: vi.fn(async () => ({ status: 201, data: {}, headers: new Headers() })),
    } as unknown as ApiClient;

    mount(
      <PaymentsSegmentRoute client={detailClient} />,
      `/${TENANT}/payments/PMT-2609-000418`,
    );
    // B14 rule 31 — the NUMBER is the title, and no uuid reaches the screen.
    expect(
      await screen.findByRole("heading", { name: "PMT-2609-000418" }),
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("8f14e45f");
  });
});

// ══════════════════════════════════════════════════════════════════════════
// P3.21 — `J12-nsf-life` regression: the bounce path the tier change touches
// ══════════════════════════════════════════════════════════════════════════

describe("P3.21 — J12's step 2 still walks after the commit changed tier", () => {
  it("a bounce submits with the bank's date, and the reason is still NSF by default", async () => {
    // ⚠ **THE REGRESSION `P3.12` COULD HAVE CAUSED IS A DEAD COMMIT, NOT AN
    // UGLY ONE.** `submitVariant` reaches `WorkingButton`, which is the
    // component that owns `type="submit"`; a tier that swapped it for a plain
    // `<Button>` would render perfectly and submit nothing. Every case in
    // `reversePayment.test.tsx` renders this modal and reads it — none of them
    // presses the commit — so *"the form still works"* was assumed, not
    // asserted, on the exact button that changed.
    const spy = client();
    mount(
      <ReversePaymentModal
        client={spy}
        payment={BOUNCED}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onReversed={() => undefined}
      />,
    );

    // J12 step 2: *Aug 3 — the bank returns the cheque.* The reason a clerk
    // gets by touching nothing is the bounce (CS-31), which is what makes the
    // walk below the one a clerk actually performs.
    const reason = document.querySelector<HTMLSelectElement>("#reason");
    expect(reason?.value).toBe("nsf");

    // BR-PAY-021 — the BANK's return date, required and never pre-filled.
    const returned = document.querySelector<HTMLInputElement>("#returned_on");
    expect(returned?.value).toBe("");
    fireEvent.change(returned as HTMLInputElement, { target: { value: "2026-08-03" } });

    fireEvent.click(await screen.findByRole("button", { name: t("payments.reverse.submit") }));

    await waitFor(() => {
      expect(spy.post).toHaveBeenCalledWith(
        "/payments/pay-1042/reverse",
        expect.objectContaining({ reason: "nsf", returned_on: "2026-08-03" }),
      );
    });
  });

  it("without the bank's date the commit refuses, so the tier did not disable the schema", async () => {
    // ⚠ **THE CONTROL FOR THE CASE ABOVE, AND IT IS THE HALF THAT USUALLY
    // ROTS.** A commit that posted whatever it was given would pass the happy
    // path exactly as well. `J12`'s whole premise is that a bounce is dated by
    // the BANK — an undated reversal reinstates AR against the wrong day and
    // the late-fee clock (BR-BIL-071) reads from a date nobody supplied.
    const spy = client();
    mount(
      <ReversePaymentModal
        client={spy}
        payment={BOUNCED}
        dateFormat="MM/DD/YYYY"
        onClose={() => undefined}
        onReversed={() => undefined}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: t("payments.reverse.submit") }));
    await waitFor(() => {
      expect(document.body.textContent).toContain(t("payments.reverse.returnedOnRequired"));
    });
    expect(spy.post).not.toHaveBeenCalled();
  });
});
