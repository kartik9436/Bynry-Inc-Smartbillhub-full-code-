// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-003 (EP-CWP-02) · US-CWP-002 · Screen: CWP-002
//           wireframes/CWP-002.png
// Rules:    BR-CWP-019/020 (the amount owing and a MASKED name, nothing else) ·
//           BR-CWP-023 (five wrong tries, and the screen says so BEFORE the
//           tries are spent) · BR-CWP-056 / CR-068 R3 (the Pay control is
//           visible, disabled and carries its reason) · B14 rule 31 (no
//           database id is a visible value) · rule 33 (a refusal is five or
//           six words) · rule 36 (compose the kit — no raw <button>)
// Cases:    the two fields and the two rail panels before anything is typed ·
//           TC-1 (the pair opens the found state with $142.18) · TC-2/TC-3
//           (ONE refusal sentence, whatever the miss was) · TC-4 (a paid bill
//           offers no Pay control) · TC-5 (cancelled) · TC-7 (replaced, and it
//           names the replacement) · the Pay control is HELD, never hidden ·
//           the screen renders no name, no address, no account, no uuid
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { BillLookupView } from "../api/guestClient";

// A plain function rather than `vi.fn()` — a recording stand-in reaches a
// rejected promise before the screen's own `catch` does (the reasoning
// `MyDetails.dom.test.tsx` records one directory over).
let answer: () => Promise<BillLookupView> = async () => {
  throw new Error("no behaviour set");
};
let asked: Array<[string, string]> = [];
vi.mock("../api/guestClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/guestClient");
  return {
    ...actual,
    lookUpBill: (billNumber: string, postcode: string) => {
      asked.push([billNumber, postcode]);
      return answer();
    },
  };
});

const { QuickPayFindBill } = await import("./QuickPay");

const PAYABLE: BillLookupView = {
  number: "BL-2608-0141",
  amount: { kind: "amount", amount: "142.1800", display: "$142.18", currency: "USD" },
  status: "payable",
  due_on: "2026-09-14",
  masked_name: "M. A••••••",
  replaced_by: null,
};

/** Where the screen navigated to, and what it handed on in router state.
 *
 * ⚠ **RECORDED FROM A REAL ROUTE RATHER THAN FROM A MOCKED `useNavigate`**
 * (`DEF-CWP-3925`). A bare `MemoryRouter` with no `/:tenant/portal` pattern
 * leaves `useParams().tenant` undefined, so every address the page builds comes
 * out `//portal/…` — a protocol-relative URL to another host, which reads as a
 * perfectly good string to `toContain`. Mounting under the real pattern is what
 * makes *"the door points at the right place"* an assertion anybody can write. */
let wentTo: string[] = [];
let handedOn: unknown = null;

function Landed() {
  const location = useLocation();
  wentTo.push(location.pathname);
  handedOn = location.state;
  return <p>landed</p>;
}

function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/pay"]}>
      <Routes>
        <Route path="/:tenant/portal/pay" element={<QuickPayFindBill />} />
        <Route path="/:tenant/portal/pay/check" element={<Landed />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function lookUp(number = "BL-2608-0141", postcode = "78702") {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText(/bill number/i), number);
  // ⚠ `zip code`, and this read `postcode` until `DEF-CWP-4855` (2026-09-11).
  // `portal.quickPay.postcode` is the LABEL a North American customer reads and
  // it said the British word; only `en.json` moved, because the ten other
  // catalogues already carry their own language's (B14 rule 35). The field id
  // is untouched — `#quickpay-postcode` is internal and names nothing on screen.
  await user.type(screen.getByLabelText(/zip code/i), postcode);
  await user.click(screen.getByRole("button", { name: /continue/i }));
}

beforeEach(() => {
  asked = [];
  wentTo = [];
  handedOn = null;
});
afterEach(cleanup);

describe("CWP-002 · find your bill (US-CWP-003)", () => {
  it("draws the two fields and both rail panels before anything is typed", () => {
    const { container } = draw();
    expect(container.querySelector('[data-screen="CWP-002"]')).not.toBeNull();
    expect(screen.getByLabelText(/bill number/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/zip code/i)).toBeInTheDocument();
    expect(screen.getByText(/top right of your bill/i)).toBeInTheDocument();
    // ⚠ **THE LOCKOUT IS STATED BEFORE THE TRIES ARE SPENT** (`BR-CWP-023`).
    // A form that only mentions it in the refusal has told somebody after it
    // is too late to matter.
    expect(container.querySelector("[data-five-tries]")?.textContent).toMatch(/fifteen minutes/i);
  });

  it("posts nothing until both boxes are filled in", async () => {
    draw();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/bill number/i), "BL-2608-0141");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(asked).toHaveLength(0);
  });

  it("TC-1 — the pair opens the found state at $142.18, owing", async () => {
    answer = async () => PAYABLE;
    const { container } = draw();
    await lookUp();
    await waitFor(() => expect(container.querySelector("[data-bill-found]")).not.toBeNull());
    expect(asked).toEqual([["BL-2608-0141", "78702"]]);
    // Hard rule 2 — the screen renders the SERVER's two-decimal sentence and
    // carries the four-decimal figure in the DOM beside it.
    const money = container.querySelector("[data-money]");
    expect(money?.textContent).toBe("$142.18");
    expect(money?.getAttribute("data-money")).toBe("142.1800");
    expect(container.querySelector("[data-bill-status]")?.getAttribute("data-bill-status")).toBe(
      "payable",
    );
  });

  // ⚠ **THE OTHER HALF OF THE ONE PAIR THIS SCREEN IS ALLOWED TO SHOW**
  // (`CR-085`, 2026-09-08). The drawing: *"What you can see here — only the
  // amount due and the due date."* The server has sent `due_on` since wave B,
  // `CWP-003` one step along draws it with this exact catalogue key, and step 1
  // threw it away — so the person holding the paper could read WHAT they owed
  // and not BY WHEN, on the screen where they decide whether to pay today.
  it("draws the due date beside the amount, which is the pair the drawing allows (CR-085)", async () => {
    answer = async () => PAYABLE;
    const { container } = draw();
    await lookUp();
    await waitFor(() => expect(container.querySelector("[data-bill-found]")).not.toBeNull());
    const due = container.querySelector("[data-due-on]");
    expect(due).not.toBeNull();
    // The ATTRIBUTE is the server's own string; the visible value is the
    // tenant's format, which outside a frame publishes none and hands the
    // string back unchanged (`DEF-SHL-3964` — a default here would be a
    // plausible wrong answer, which is the defect and not the cure).
    expect(due?.getAttribute("data-due-on")).toBe("2026-09-14");
    expect(due?.textContent).not.toBe("");
    // The catalogue's word, never the key (B14 rule 35).
    expect(container.textContent).toContain("Due");
    expect(container.textContent).not.toContain("portal.quickPay.due");
  });

  it("draws NO due row at all when the server sent no date (BR-CWP-093)", async () => {
    // ⚠ An em dash beside *Due* reads as a date that exists and is being
    // withheld. No row says the true thing.
    answer = async () => ({ ...PAYABLE, due_on: null });
    const { container } = draw();
    await lookUp();
    await waitFor(() => expect(container.querySelector("[data-bill-found]")).not.toBeNull());
    expect(container.querySelector("[data-due-on]")).toBeNull();
  });

  it("TC-1 — *Billed to* is the server's mask, rendered verbatim (BR-CWP-020)", async () => {
    answer = async () => PAYABLE;
    const { container } = draw();
    await lookUp();
    await waitFor(() => expect(container.querySelector("[data-masked-name]")).not.toBeNull());
    expect(container.querySelector("[data-masked-name]")?.textContent).toBe("M. A••••••");
    // ⚠ THE FULL NAME NEVER REACHES THE PAGE, so it cannot be in the markup.
    expect(container.innerHTML).not.toMatch(/alvarez/i);
  });

  it("the Pay control is LIVE and opens CWP-003 at /pine-hill/portal/pay/check", async () => {
    // ⚠ **THIS CASE WAS THE HOLD AND IS NOW THE HOLD'S EXPIRY TEST.** It read
    // *"CR-068 R3 — the Pay control is VISIBLE, DISABLED and carries its
    // reason"* and asserted `[data-held]` plus the sentence *"Card payments are
    // not open yet"*, which was correct while no gateway existed. `CWP-003`
    // landed on 2026-09-05 (`US-CWP-004`) and a refusal that outlives its
    // reason is `DEF-CWP-3925` — eight shut doors over live screens, every
    // check passing, because landing a screen and releasing the control that
    // pointed at it are two acts.
    //
    // ⚠ **AND IT ASSERTS THE DESTINATION BY ADDRESS**, which is the other half
    // of that defect: the front page's own fixture could not tell a working
    // link from a broken one because it mounted the component with no
    // `/:tenant/portal` route, so every address it built came out
    // `//portal/…` — a perfectly good string to `toContain`.
    answer = async () => PAYABLE;
    const { container } = draw();
    await lookUp();
    await waitFor(() => expect(container.querySelector("[data-bill-found]")).not.toBeNull());
    const pay = screen.getByRole("button", { name: /pay \$142\.18/i });
    expect(pay).toBeEnabled();
    expect(container.querySelector("[data-held]")).toBeNull();
    await userEvent.setup().click(pay);
    await waitFor(() => expect(wentTo).toEqual(["/pine-hill/portal/pay/check"]));
    // Step 2 needs the PAIR, and it travels in router state rather than in the
    // address — a postcode in a URL reaches access logs and browser history.
    expect(handedOn).toEqual({ billNumber: "BL-2608-0141", postcode: "78702" });
  });

  it("TC-2 · TC-3 — ONE refusal sentence, whatever the miss was", async () => {
    // The server already answers identically for a wrong postcode and an
    // unknown number; this asserts the SCREEN does not add a second sentence.
    answer = async () => {
      throw new Error("refused");
    };
    const { container } = draw();
    await lookUp("BL-2608-0141", "78704");
    await waitFor(() =>
      expect(container.querySelector("[data-quick-pay-refused]")).not.toBeNull(),
    );
    const first = container.querySelector("[data-quick-pay-refused]")?.textContent;
    cleanup();
    const second = draw();
    await lookUp("BL-9999-9999", "78702");
    await waitFor(() =>
      expect(second.container.querySelector("[data-quick-pay-refused]")).not.toBeNull(),
    );
    expect(second.container.querySelector("[data-quick-pay-refused]")?.textContent).toBe(first);
    // And nothing is drawn about a bill that was not found.
    expect(second.container.querySelector("[data-bill-found]")).toBeNull();
  });

  it("TC-4 — a paid bill opens at $0.00 with no Pay control at all", async () => {
    answer = async () => ({
      ...PAYABLE,
      number: "BL-2607-0139",
      status: "settled",
      amount: { kind: "amount", amount: "0.0000", display: "$0.00", currency: "USD" },
    });
    const { container } = draw();
    await lookUp("BL-2607-0139");
    await waitFor(() => expect(container.querySelector("[data-bill-found]")).not.toBeNull());
    expect(container.querySelector("[data-nothing-to-pay]")).not.toBeNull();
    expect(container.querySelector("[data-held]")).toBeNull();
    expect(screen.queryByRole("button", { name: /pay \$/i })).toBeNull();
  });

  it("TC-5 — a voided bill reads *cancelled* and offers no payment", async () => {
    answer = async () => ({
      ...PAYABLE,
      status: "cancelled",
      amount: { kind: "amount", amount: "0.0000", display: "$0.00", currency: "USD" },
    });
    const { container } = draw();
    await lookUp();
    await waitFor(() => expect(container.querySelector("[data-bill-status]")).not.toBeNull());
    expect(screen.getByText(/canceled/i)).toBeInTheDocument();
    expect(container.querySelector("[data-held]")).toBeNull();
  });

  it("TC-7 — a corrected bill names the bill that replaced it", async () => {
    answer = async () => ({
      ...PAYABLE,
      number: "BL-2606-0137",
      status: "replaced",
      replaced_by: "BL-2606-0147",
      amount: { kind: "amount", amount: "0.0000", display: "$0.00", currency: "USD" },
    });
    const { container } = draw();
    await lookUp("BL-2606-0137");
    await waitFor(() => expect(container.querySelector("[data-replaced-by]")).not.toBeNull());
    expect(screen.getByText(/BL-2606-0147/)).toBeInTheDocument();
    expect(container.querySelector("[data-held]")).toBeNull();
  });

  it("B14 rule 31 — nothing on the screen is a database id", async () => {
    answer = async () => PAYABLE;
    const { container } = draw();
    await lookUp();
    await waitFor(() => expect(container.querySelector("[data-bill-found]")).not.toBeNull());
    expect(container.innerHTML).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
    );
  });

  it("B14 rule 36 — every control comes from the kit, and none is danger tier", () => {
    const { container } = draw();
    // r10 rule 6: danger is for DESTRUCTIVE commits. Looking up a bill is not
    // one, so nothing here may wear it.
    expect(container.innerHTML).not.toMatch(/danger/);
  });
});
