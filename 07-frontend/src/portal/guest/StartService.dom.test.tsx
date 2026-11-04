// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:  DEF-CWP-3941 — CWP-008's PRICED ANSWER, the whole point of the
//          screen, had no test. `StartService.test.tsx` held this fixture and
//          nothing used it; its five cases all assert the screen BEFORE
//          anything is typed, and one of them asserts `not.toContain
//          ("data-minitable")` — that no priced table is drawn YET.
// Story:   US-CWP-012 (EP-CWP-04) · Screen: CWP-008 · wireframes/CWP-008.png
// Rules:   US-CWP-012 TC-1 (the four rows and their figures) · TC-4 (a service
//          that is not carried says NOT HERE and NEVER $0.00) · BR-CWP-021 (a
//          guest sees an amount and a status, never a person) · hard rule 2
//          (the screen renders `display`, never `amount`) · B14 rule 36
// Cases:   TC-1 the four rows arrive with their signed figures · TC-2 included
//          is not zero and zero is not nothing · TC-3 the unavailable row is
//          greyed and quotes NO money · TC-4 IF YOU APPLY carries $185.00 and
//          $150.00 · TC-5 nothing is priced until Check is pressed · TC-6 the
//          address the customer typed is what is asked
//
// ⚠ **WHY THIS FILE EXISTS SEPARATELY FROM `StartService.test.tsx`.** That file
// renders with `renderToStaticMarkup` and seeds the react-query cache — the
// shape every static portal test uses — but the availability read is a
// `useMutation` driven by local `useState`, so THERE IS NO QUERY KEY TO SEED.
// The priced rows are reachable only by typing an address and pressing a
// button, which needs the DOM harness this file has and that one does not.
// The gap was not an oversight a reviewer would spot: the other file looks
// complete for what it can do.
//
// ⚠ **AND THE DEMO FIXTURE HID IT TWICE OVER** — `DEF-CWP-3927` and
// `DEF-CWP-3928` were both `31 Palm Ct`'s prices failing to seed, and neither
// was caught by a test either. This screen's priced half had been broken twice
// in two days with nothing red.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { AddressParts, Availability, MoneyCell } from "../api/guestClient";

// Plain functions rather than `vi.fn()`, for the reason `QuickPayCheck.dom
// .test.tsx` records next door: a recording stand-in reaches a rejected promise
// before the screen's own `catch` does.
let asked: AddressParts[] = [];
let answer: () => Promise<Availability> = async () => {
  throw new Error("no behaviour set");
};

vi.mock("../api/guestClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/guestClient");
  return {
    ...actual,
    getAvailability: (parts: AddressParts) => {
      asked.push(parts);
      return answer();
    },
    // CR-200-BRC10 — the street box now suggests; nothing to offer here.
    getAddressSuggestions: async () => [],
  };
});

const { StartServiceBody } = await import("./StartService");

const money = (amount: string, display: string): MoneyCell => ({
  kind: "amount",
  amount,
  display,
  currency: "USD",
});
const included: MoneyCell = { kind: "included", amount: null, display: null, currency: null };
const nothing: MoneyCell = { kind: "none", amount: null, display: null, currency: null };

/**
 * `US-CWP-012`'s own signed figures, moved here from `StartService.test.tsx`
 * where it sat unused behind an `eslint-disable` naming `DEF-CWP-3941`.
 * **$185.00 to connect · $150.00 on the first bill · sewer included · trash
 * $0.00 · electric unavailable.**
 */
const PALM_CT: Availability = {
  matched: true,
  address: "31 Palm Ct, Austin, TX 78702",
  job: "new_connection",
  rows: [
    { service_code: "water", service_name: "Water", available: true, to_connect: money("185.0000", "$185.00"), deposit: money("150.0000", "$150.00") },
    { service_code: "sewer", service_name: "Sewer", available: true, to_connect: included, deposit: nothing },
    { service_code: "trash", service_name: "Trash", available: true, to_connect: money("0.0000", "$0.00"), deposit: nothing },
    { service_code: "electric", service_name: "Electric", available: false, to_connect: nothing, deposit: nothing },
  ],
  if_you_apply: {
    before_we_start: money("185.0000", "$185.00"),
    on_first_bill: money("150.0000", "$150.00"),
    working_days: 3,
  },
};

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE.** Hard-won law 2 records
 * what a bare `MemoryRouter` costs on this surface: `useParams().tenant` comes
 * back undefined and every address the page builds comes out `//portal/…`, a
 * protocol-relative URL to another host that reads as a perfectly good string
 * to `toContain`.
 */
function draw() {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/pine-hill/portal/start-service"]}>
        <Routes>
          <Route path="/:tenant/portal/start-service" element={<StartServiceBody />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Type an address and press *Check →* — the only way to a priced row. */
async function check(container: HTMLElement, address = "31 Palm Ct", town = "Austin", zip = "78702") {
  const user = userEvent.setup();
  await user.type(container.querySelector("#availability-address") as HTMLInputElement, address);
  // `DEF-CWP-9817` — the town and ZIP the blueprint draws (p31).
  await user.type(container.querySelector("#availability-town") as HTMLInputElement, town);
  await user.type(container.querySelector("#availability-zip") as HTMLInputElement, zip);
  await user.click(container.querySelector("[data-action='check']") as HTMLButtonElement);
  await waitFor(() => {
    expect(container.querySelector("[data-minitable]")).not.toBeNull();
  });
}

/** One cell of one row, by the hooks `MiniTable` emits. */
function cell(container: HTMLElement, row: string, column: string) {
  return container.querySelector(`[data-row='${row}'] [data-cell='${column}']`);
}

beforeEach(() => {
  asked = [];
  answer = async () => PALM_CT;
});
afterEach(cleanup);

describe("CWP-008 · can I get service here (US-CWP-012) — the priced answer", () => {
  it("TC-1 — the four services arrive as four rows, with water's signed figures", async () => {
    const { container } = draw();
    await check(container);

    expect(container.querySelectorAll("[data-minitable] tbody tr")).toHaveLength(4);
    for (const code of ["water", "sewer", "trash", "electric"]) {
      expect(container.querySelector(`[data-row='${code}']`)).not.toBeNull();
    }
    // ⚠ The DISPLAY string, never the stored amount (hard rule 2).
    expect(cell(container, "water", "to_connect")?.textContent).toBe("$185.00");
    expect(cell(container, "water", "deposit")?.textContent).toBe("$150.00");
  });

  it("TC-2 — 'included' is not zero, and zero is not nothing", async () => {
    const { container } = draw();
    await check(container);

    // Sewer costs nothing to connect BECAUSE IT COMES WITH THE WATER, which is
    // a different sentence from "$0.00" and a different one again from a blank.
    expect(
      cell(container, "sewer", "to_connect")?.querySelector("[data-money='included']"),
    ).not.toBeNull();
    // Trash IS quoted, and the quote is zero. `$0.00` is an answer.
    expect(cell(container, "trash", "to_connect")?.textContent).toBe("$0.00");
    expect(
      cell(container, "trash", "to_connect")?.querySelector("[data-money='0.0000']"),
    ).not.toBeNull();
    // Sewer's deposit is not quoted at all — neither zero nor included.
    expect(
      cell(container, "sewer", "deposit")?.querySelector("[data-money='none']"),
    ).not.toBeNull();
  });

  it("TC-3 — the service we do not carry is greyed and quotes NO money (TC-4)", async () => {
    const { container } = draw();
    await check(container);

    const row = container.querySelector("[data-row='electric']");
    expect(row?.getAttribute("data-muted")).toBe("true");
    // ⚠ **NOT $0.00.** Quoting zero to connect a service the utility does not
    // sell reads as *free*, and it is the defect US-CWP-012 TC-4 exists for.
    expect(row?.textContent).not.toContain("$0.00");
    expect(cell(container, "electric", "to_connect")?.querySelector("[data-money='none']")).not.toBeNull();
    expect(cell(container, "electric", "deposit")?.querySelector("[data-money='none']")).not.toBeNull();
    // The three we DO carry are not greyed by the same pass.
    expect(container.querySelector("[data-row='water']")?.getAttribute("data-muted")).toBeNull();
  });

  it("TC-4 — IF YOU APPLY carries the two figures a stranger has to plan for", async () => {
    const { container } = draw();
    await check(container);

    const text = container.textContent ?? "";
    expect(text).toContain("$185.00");
    expect(text).toContain("$150.00");
    // The apply door only exists once an address has matched.
    expect(container.querySelector("[data-action='apply']")).not.toBeNull();
  });

  it("DEF-CWP-10692 — the side panel names the test the product applies (an address we hold), not occupancy", () => {
    // PO ruling A (2026-10-30): an address already in Premises is a move-in
    // whether or not anybody lives there, so the panel may not say it depends
    // on someone living there.
    const { container } = draw();
    const panel = container.textContent ?? "";
    expect(panel).toContain("If we already hold this address, it is a move-in.");
    expect(panel).not.toMatch(/lives there/i);
  });

  it("TC-5 — nothing is priced until Check is pressed", () => {
    const { container } = draw();

    expect(container.querySelector("[data-minitable]")).toBeNull();
    expect(container.querySelector("[data-action='apply']")).toBeNull();
    expect(asked).toEqual([]);
  });

  it("TC-6 — the address the customer typed is the address we ask about", async () => {
    const { container } = draw();
    await check(container, "31 Palm Ct");

    // ⊕ `DEF-CWP-9817` — all three parts are asked about, as typed.
    expect(asked).toEqual([{ street: "31 Palm Ct", city: "Austin", postalCode: "78702" }]);
  });
});
