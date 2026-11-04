// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Change:  CR-200-BRC10 lane B — F1 (the suggestion drop-down), F2 (Start
//          service: a pick fills street/town/ZIP and runs the check; *Which
//          apartment?* after a building with several units), F4 (Ask us for
//          something: same suggestions; the pick's PARTS are sent)
// Defects: DEF-CWP-10682 · DEF-CWP-10680 · DEF-CWP-10681
// Rules:   PO 2026-10-29 1A / 2A / Ask us A · BR-CWP-021 · B14 rule 31
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`/:tenant/portal/…`, hard-won
// law 2) — a bare router builds `//portal/…` and every link reads as fine.
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a list asserted
// only by its text would pass a `<div>` nobody can reach by keyboard, so the
// ROLES and `aria-activedescendant` are asserted; a pick asserted only by the
// street box would pass a screen that never ran the check, so the check's
// arguments are asserted.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { AddressParts, AddressSuggestion, Availability } from "../api/guestClient";

let suggestCalls: string[] = [];
let suggestions: AddressSuggestion[] = [];
let checked: AddressParts[] = [];
let availability: (parts: AddressParts) => Availability = () => ELM;
let asked: Record<string, unknown>[] = [];

vi.mock("../api/guestClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/guestClient");
  return {
    ...actual,
    getAddressSuggestions: async (typed: string) => {
      suggestCalls.push(typed);
      return suggestions;
    },
    getAvailability: async (parts: AddressParts) => {
      checked.push(parts);
      return availability(parts);
    },
    getQuickServices: async () => ({
      categories: [{ code: "re_read", label: "Re-read", hint: null, needs_bill_number: false }],
    }),
    askForQuickService: async (body: Record<string, unknown>) => {
      asked.push(body);
      return { reference: "SR-26-0101" };
    },
  };
});

const { StartServiceBody } = await import("../guest/StartService");
const { QuickServiceBody } = await import("../guest/QuickService");
const { PortalAnnouncer } = await import("./a11y");

const ELM_ROW: AddressSuggestion = {
  street: "1408 Elm St",
  city: "Austin",
  state: "TX",
  postal_code: "78702",
};
const ELM: Availability = {
  matched: true,
  address: "1408 Elm St, Austin, TX 78702",
  job: null,
  units: ["A", "B"],
  unit: null,
  rows: [],
  if_you_apply: null,
};

function draw(path: string, element: JSX.Element) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false }, queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <PortalAnnouncer>
        <MemoryRouter initialEntries={[`/pine-hill/portal/${path}`]}>
          <Routes>
            <Route path={`/:tenant/portal/${path}`} element={element} />
          </Routes>
        </MemoryRouter>
      </PortalAnnouncer>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  suggestCalls = [];
  suggestions = [ELM_ROW, { ...ELM_ROW, street: "1412 Elm St" }];
  checked = [];
  asked = [];
  availability = (parts) =>
    parts.unit === "B"
      ? { ...ELM, unit: "B", job: "move_in" } // PO ruling A (DEF-CWP-10690): empty B is a move-in
      : ELM;
});
afterEach(cleanup);

async function typeStreet(container: HTMLElement, text: string) {
  const user = userEvent.setup();
  const box = container.querySelector("#availability-address") as HTMLInputElement;
  await user.type(box, text);
  return { user, box };
}

describe("F1 · the suggestion drop-down (PO 1A)", () => {
  it("looks nothing up under four characters", async () => {
    const { container } = draw("start-service", <StartServiceBody />);
    await typeStreet(container, "Elm");
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(suggestCalls).toEqual([]);
    expect(container.querySelector("[role='option']")).toBeNull();
  });

  it("from the fourth character shows a listbox of options, street + town + ZIP", async () => {
    const { container } = draw("start-service", <StartServiceBody />);
    const { box } = await typeStreet(container, "1408");
    await waitFor(() => expect(container.querySelectorAll("[role='option']")).toHaveLength(2));
    expect(suggestCalls).toEqual(["1408"]);
    expect(box).toHaveAttribute("role", "combobox");
    expect(box).toHaveAttribute("aria-expanded", "true");
    const list = container.querySelector("[role='listbox']") as HTMLElement;
    expect(box.getAttribute("aria-controls")).toBe(list.id);
    expect(container.querySelector("[role='option']")?.textContent).toBe("1408 Elm St, Austin, TX 78702");
    // The count is spoken, the list is not.
    await waitFor(() =>
      expect(container.querySelector("[data-portal-status]")?.textContent).toBe("2 addresses found."),
    );
  });

  it("arrow keys move, Enter picks: street, town and ZIP filled and the check runs", async () => {
    const { container } = draw("start-service", <StartServiceBody />);
    const { user, box } = await typeStreet(container, "1408");
    await waitFor(() => expect(container.querySelectorAll("[role='option']")).toHaveLength(2));
    await user.keyboard("{ArrowDown}");
    const first = container.querySelector("[role='option']") as HTMLElement;
    expect(box.getAttribute("aria-activedescendant")).toBe(first.id);
    expect(first).toHaveAttribute("aria-selected", "true");
    await user.keyboard("{Enter}");
    expect(box.value).toBe("1408 Elm St");
    expect((container.querySelector("#availability-town") as HTMLInputElement).value).toBe("Austin");
    expect((container.querySelector("#availability-zip") as HTMLInputElement).value).toBe("78702");
    await waitFor(() =>
      expect(checked).toEqual([{ street: "1408 Elm St", city: "Austin", postalCode: "78702" }]),
    );
    expect(box).toHaveAttribute("aria-expanded", "false");
  });

  it("Escape closes the list and keeps what was typed", async () => {
    const { container } = draw("start-service", <StartServiceBody />);
    const { user, box } = await typeStreet(container, "1408");
    await waitFor(() => expect(container.querySelectorAll("[role='option']")).toHaveLength(2));
    await user.keyboard("{Escape}");
    expect(box).toHaveAttribute("aria-expanded", "false");
    expect(box.value).toBe("1408");
    expect(checked).toEqual([]);
  });

  it("carries no id: an option is the four strings and nothing else", async () => {
    suggestions = [ELM_ROW];
    const { container } = draw("start-service", <StartServiceBody />);
    await typeStreet(container, "1408 Elm");
    await waitFor(() => expect(container.querySelectorAll("[role='option']")).toHaveLength(1));
    const option = container.querySelector("[role='option']") as HTMLElement;
    expect(Object.keys(option.dataset)).toEqual(["suggestion"]);
  });
});

describe("F2 · Which apartment? (PO 2A)", () => {
  async function pickElm(container: HTMLElement) {
    const { user } = await typeStreet(container, "1408");
    await waitFor(() => expect(container.querySelectorAll("[role='option']")).toHaveLength(2));
    fireEvent.mouseDown(container.querySelector("[role='option']") as HTMLElement);
    await waitFor(() => expect(container.querySelector("[data-apartment-choice]")).not.toBeNull());
    return user;
  }

  it("lists the building's labels plus Mine isn't listed, and holds Apply until one is picked", async () => {
    const { container } = draw("start-service", <StartServiceBody />);
    await pickElm(container);
    const radios = [...container.querySelectorAll("[data-apartment-choice] input[type='radio']")];
    expect(radios.map((one) => one.closest("label")?.textContent)).toEqual(["A", "B", "Mine isn't listed"]);
    expect(container.querySelector("[data-action='apply']")).toBeNull();
  });

  it("picking B re-checks for B and opens Apply", async () => {
    const { container } = draw("start-service", <StartServiceBody />);
    const user = await pickElm(container);
    await user.click(container.querySelector("[data-radio='B'] input") as HTMLInputElement);
    await waitFor(() => expect(checked.at(-1)).toEqual({ street: "1408 Elm St", city: "Austin", postalCode: "78702", unit: "B" }));
    await waitFor(() => expect(container.querySelector("[data-action='apply']")).not.toBeNull());
  });

  it("DEF-CWP-10693 — the arrow keys walk the apartments: focus stays on the radio, and the question sits above the answer", async () => {
    availability = (parts) =>
      parts.unit ? { ...ELM, unit: parts.unit, job: "move_in" } : ELM; // PO ruling A
    const { container } = draw("start-service", <StartServiceBody />);
    const user = await pickElm(container);
    (container.querySelector("[data-radio='A'] input") as HTMLInputElement).focus();
    await user.keyboard(" ");
    await waitFor(() => expect(container.querySelector("[data-action='apply']")).not.toBeNull());
    // The answer to a pick is spoken, not focused: the person is still choosing.
    expect(document.activeElement).toBe(container.querySelector("[data-radio='A'] input"));
    await user.keyboard("{ArrowDown}");
    await waitFor(() => expect(checked.at(-1)?.unit).toBe("B"));
    expect((container.querySelector("[data-radio='B'] input") as HTMLInputElement).checked).toBe(true);
    expect(document.activeElement).toBe(container.querySelector("[data-radio='B'] input"));
    // The question is asked where it was asked; the answer comes under it.
    const question = container.querySelector("[data-apartment-choice]") as HTMLElement;
    const apply = container.querySelector("[data-action='apply']") as HTMLElement;
    expect(question.compareDocumentPosition(apply) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // On to *Mine isn't listed*: its sentence is spoken, the radio keeps focus.
    await user.keyboard("{ArrowDown}");
    await waitFor(() => expect(container.querySelector("[data-availability='unit-not-listed']")).not.toBeNull());
    expect((document.activeElement as HTMLInputElement).closest("label")?.textContent).toBe("Mine isn't listed");
  });

  it("Mine isn't listed is 'a person will look at it', with Apply still open", async () => {
    const { container } = draw("start-service", <StartServiceBody />);
    const user = await pickElm(container);
    const notListed = [...container.querySelectorAll("[data-apartment-choice] label")].find(
      (one) => one.textContent === "Mine isn't listed",
    ) as HTMLElement;
    await user.click(notListed.querySelector("input") as HTMLInputElement);
    await waitFor(() =>
      expect(container.querySelector("[data-availability='unit-not-listed']")?.textContent).toBe(
        "A person will check your apartment. You can still apply.",
      ),
    );
    expect(container.querySelector("[data-action='apply']")).not.toBeNull();
  });
});

describe("F4 · Ask us for something (PO, Ask us A)", () => {
  async function openForm(container: HTMLElement) {
    const user = userEvent.setup();
    await waitFor(() => expect(container.querySelector("[data-action='ask-re_read']")).not.toBeNull());
    await user.click(container.querySelector("[data-action='ask-re_read']") as HTMLButtonElement);
    await user.type(container.querySelector("#quick-name") as HTMLInputElement, "Daniel Okafor");
    await user.type(container.querySelector("#quick-phone") as HTMLInputElement, "(512) 555-7730");
    return user;
  }

  it("a picked address and apartment are sent as PARTS and a label, never an id", async () => {
    const { container } = draw("quick-service", <QuickServiceBody />);
    const user = await openForm(container);
    await user.type(container.querySelector("#quick-address") as HTMLInputElement, "1408");
    await waitFor(() => expect(container.querySelectorAll("[role='option']")).toHaveLength(2));
    fireEvent.mouseDown(container.querySelector("[role='option']") as HTMLElement);
    expect((container.querySelector("#quick-address") as HTMLInputElement).value).toBe(
      "1408 Elm St, Austin, TX 78702",
    );
    await waitFor(() => expect(container.querySelector("[data-apartment-choice]")).not.toBeNull());
    await user.click(container.querySelector("[data-radio='B'] input") as HTMLInputElement);
    await act(async () => {
      await user.click(container.querySelector("[data-action='send-ask']") as HTMLButtonElement);
    });
    await waitFor(() => expect(asked).toHaveLength(1));
    expect(asked[0]).toMatchObject({
      address: "1408 Elm St, Austin, TX 78702",
      street: "1408 Elm St",
      city: "Austin",
      postal_code: "78702",
      unit: "B",
    });
    expect(JSON.stringify(asked[0])).not.toMatch(/premises_id|unit_id/u);
  });

  it("an address typed and not picked is sent as typed, alone", async () => {
    suggestions = [];
    const { container } = draw("quick-service", <QuickServiceBody />);
    const user = await openForm(container);
    await user.type(container.querySelector("#quick-address") as HTMLInputElement, "2155 Hemlok Dr");
    await act(async () => {
      await user.click(container.querySelector("[data-action='send-ask']") as HTMLButtonElement);
    });
    await waitFor(() => expect(asked).toHaveLength(1));
    expect(asked[0]?.address).toBe("2155 Hemlok Dr");
    expect(asked[0]).not.toHaveProperty("street");
  });
});
