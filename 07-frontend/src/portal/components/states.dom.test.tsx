// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:  DEF-CWP-4926 — ten signed-in screens declared `if (failed) return …`
//          BEFORE their page head, so a failed or slow read threw the heading,
//          the `data-screen` mark and the whole top row of controls away with
//          the data. Walked in a browser at 390 and 1280 on 2026-09-11: 13 of
//          the 34 signed-in addresses rendered no `<h1>`, and ten of the
//          thirteen were this one cause.
// Rules:   R-22 (PO 2026-09-11: *"differntiate it using text message"*) ·
//          R-10 (PO 2026-09-11: *"the thing they can do about it must be on
//          that same screen, next to the message"*) · B14 rule 2
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS IS A RENDERED CHECK AND THAT IS THE WHOLE POINT (hard-won law 6).**
// `pageHeadCensus.test.ts` next door proves COMPOSITION — that a screen file
// imports the shared head — and says so about itself: *"a file could import
// `PageHeader` and render it behind a condition."* That is exactly what these
// ten files did, for weeks, with the census green. Composition cannot see a
// branch; only mounting the component can.
//
// ⚠ **AND IT MOUNTS EACH VIEW WITH ITS READ REJECTING, not with a fixture** —
// the failure branch is the thing under test, so a passing read would exercise
// the one branch that was never broken.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

/** Every read the nine screens make, refused. */
const refuse = () => Promise.reject(new Error("refused for this test"));

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getAccountBalance: refuse,
    getAccountSummary: refuse,
    getMyDetails: refuse,
    getPreferences: refuse,
    getAccountEquipment: refuse,
    getAccountReadings: refuse,
    getMoneyList: refuse,
    getBillDetail: refuse,
    getPrintedBill: refuse,
    getPaymentMethods: refuse,
  };
});

const { PortalScreen, PortalState } = await import("./states");
const { YourAccountView } = await import("../accounts/YourAccount");
const { MyDetailsView } = await import("../details/MyDetails");
const { PreferencesView } = await import("../details/Preferences");
const { EquipmentView } = await import("../usage/Equipment");
const { ReadingsView } = await import("../usage/Readings");
const { PaymentsView } = await import("../payments/Payments");
const { BillDetailView } = await import("../bills/BillDetail");
const { PrintedBillView } = await import("../bills/PrintedBill");
const { MethodsView } = await import("../methods/Methods");

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NEVER A BARE `MemoryRouter`**
 * (hard-won law 2's fixture clause). Without a `/:tenant/portal` route
 * `useParams().tenant` is undefined and every address these screens build comes
 * out `//portal/…` — a protocol-relative URL to another host that reads as a
 * perfectly good string to `toContain`.
 */
function mount(node: React.ReactNode, at = "/brazosbend/portal/x") {
  return render(
    <MemoryRouter initialEntries={[at]}>
      <Routes>
        <Route path="/:tenant/portal/*" element={node} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("the screen shell keeps the head on every branch", () => {
  it("PortalScreen renders the head and the screen mark", () => {
    mount(
      <PortalScreen screen="CWP-999" head={<h1>Your account</h1>}>
        <p>body</p>
      </PortalScreen>,
    );
    expect(document.querySelector('[data-screen="CWP-999"]')).not.toBeNull();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Your account");
  });

  // The nine files `DEF-CWP-4926` names, minus `usage/Usage.tsx` — that screen
  // composes NO page head at all and is `pageHeadCensus.test.ts`'s one
  // remaining `AWAITING_ANOTHER_LANE` entry, so it is a different defect with
  // a different owner. Listing it here would make this suite red over work
  // this lane deliberately did not do.
  const FAILING_SCREENS: [string, string, React.ReactNode][] = [
    ["CWP-065", "your account", <YourAccountView accountId="a1" key="a" />],
    ["CWP-024", "my details", <MyDetailsView key="b" />],
    ["CWP-025", "preferences", <PreferencesView key="c" />],
    ["CWP-037", "equipment", <EquipmentView accountId="a1" key="d" />],
    ["CWP-034", "readings", <ReadingsView accountId="a1" key="e" />],
    ["CWP-041", "payments", <PaymentsView accountId="a1" key="f" />],
    ["CWP-028", "bill detail", <BillDetailView number="BL-1" key="g" />],
    ["CWP-029", "printed bill", <PrintedBillView number="BL-1" key="h" />],
    ["CWP-039", "payment methods", <MethodsView key="i" />],
  ];

  for (const [id, name, node] of FAILING_SCREENS) {
    it(`${id} (${name}) still draws its heading when the read fails`, async () => {
      mount(node);
      // ⚠ **THE HEADING IS THE ASSERTION AND THE SCREEN MARK IS THE OTHER
      // HALF.** A screen that renders its title inside a `<div>` with no
      // `data-screen` is still invisible to every rendered check this repo
      // owns, which is how the walk had to be done by hand.
      await waitFor(() => {
        expect(
          document.querySelector(`[data-screen="${id}"]`),
          `${id} lost its data-screen mark on the failed branch`,
        ).not.toBeNull();
      });
      expect(
        document.querySelector("h1"),
        `${id} rendered no <h1> on the failed branch — the head is declared ` +
          "below an early return again (DEF-CWP-4926)",
      ).not.toBeNull();
      // R-22: the card says WHICH state it is, in the DOM, so this is
      // checkable at all.
      expect(document.querySelector('[data-portal-state="failed"]')).not.toBeNull();
    });
  }
});

describe("R-22 — one card, three sentences", () => {
  it("each kind marks itself and renders the sentence it was given", () => {
    for (const kind of ["loading", "empty", "failed"] as const) {
      cleanup();
      mount(<PortalState kind={kind} sentence={`sentence for ${kind}`} />);
      const card = document.querySelector(`[data-portal-state="${kind}"]`);
      expect(card, `${kind} did not mark itself`).not.toBeNull();
      expect(card).toHaveTextContent(`sentence for ${kind}`);
    }
  });

  it("the three cards are the SAME picture — the ruling narrowed the rule to the words", () => {
    // PO 2026-09-11: *"differntiate it using text message"*. Three layouts was
    // the reading this ruling replaced, so a lane forking this component into
    // three is undoing a decision rather than improving it.
    const classes = (["loading", "empty", "failed"] as const).map((kind) => {
      cleanup();
      mount(<PortalState kind={kind} sentence="x" />);
      return document.querySelector(`[data-portal-state="${kind}"]`)?.className;
    });
    expect(new Set(classes).size).toBe(1);
  });

  it("a loading card is busy and a failed card is an alert", () => {
    mount(<PortalState kind="loading" sentence="Still coming…" />);
    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull();
    cleanup();
    mount(<PortalState kind="failed" sentence="We could not load this." />);
    expect(document.querySelector('[role="alert"]')).not.toBeNull();
  });
});

describe("R-10 — the way out is beside the message", () => {
  it("an address draws a real link and an action draws a button, both inside the card", () => {
    const pressed = vi.fn();
    mount(
      <PortalState
        kind="failed"
        sentence="We could not load this."
        waysOut={[
          { label: "Pay a bill", to: "/brazosbend/portal/pay", tone: "primary", testKey: "pay" },
          { label: "Try again", onClick: pressed, testKey: "retry" },
        ]}
      />,
    );
    const card = document.querySelector('[data-portal-state="failed"]');
    // "on that same screen, next to the message. Not a page away." — the
    // assertion is CONTAINMENT, because that is the half of R-10 a check can
    // actually see.
    const link = card?.querySelector('[data-way-out="pay"]');
    expect(link?.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/brazosbend/portal/pay");
    const button = card?.querySelector('[data-way-out="retry"]');
    expect(button?.tagName).toBe("BUTTON");
    (button as HTMLButtonElement).click();
    expect(pressed).toHaveBeenCalledOnce();
  });

  it("no ways out means no row at all — never an empty one", () => {
    mount(<PortalState kind="empty" sentence="Nothing here yet." />);
    expect(document.querySelector("[data-ways-out]")).toBeNull();
  });
});
