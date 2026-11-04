// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-066 (EP-CWP-11) · Screen: CWP-054
// Rules:    BR-CWP-093 (*might answer it now* is ABSENT when nothing is
//           published, never empty) · BR-CWP-056 (a held control carries its
//           reason) · B14 rule 31 · rule 33 · CR-068 §2b (consumer upload is a
//           SIGNED DEFERRAL — no file input anywhere)
// Cases:    the bill travels with the question · a question with NO bill is
//           accepted · three published answers appear · NONE published and the
//           panel is absent · the photo box is held and there is NO file input
//           · the office and emergency numbers are two different lines
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { HelpAnswerSummary, PortalFront } from "../api/guestClient";
import type { PortalBill } from "../api/portalClient";

const OFFICE = "(512) 555-0148";
const EMERGENCY = "(512) 555-0100";

const ANSWERS: HelpAnswerSummary[] = [
  { slug: "why-higher", question: "Why is my bill higher than last month?", topic: "billing" },
  { slug: "estimated", question: 'What does "estimated" mean on a reading?', topic: "readings" },
  { slug: "leak", question: "How do I check for a leak?", topic: "water" },
];

const BILLS: PortalBill[] = [
  {
    number: "BL-2608-0141",
    issued_on: "2026-08-26",
    due_on: "2026-09-15",
    total: "142.1800",
    owing: "142.1800",
    currency: "USD",
    state: "due",
  } as PortalBill,
];

let answers: HelpAnswerSummary[] = ANSWERS;
let centres: { phone: string | null }[] = [{ phone: OFFICE }];
// ⚠ **THE SPY IS TYPED ON ITS ARGUMENT, NOT ONLY ON ITS ANSWER.** The case
// this file exists for is *what did the screen SEND* — `bill_number` — and an
// untyped `vi.fn` records the call at `never`, so `mock.calls[0][0]` is a `tsc`
// error rather than an assertion.
type Question = { topic: string; what: string; bill_number?: string };
const asked = vi.fn(
  async (body: Question) => ({
    reference: "SR-26-0091",
    bill_number: body.bill_number ?? null,
  }),
);

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getBills: async () => ({ bills: BILLS }),
    askAQuestion: (body: Question) => asked(body),
  };
});

vi.mock("../api/guestClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/guestClient");
  return {
    ...actual,
    getPortalHelp: async () => ({ answers, topics: [], visit_link: true }),
    getPortalCentres: async () => centres,
    getPortalFront: async () =>
      ({ emergency_phone: EMERGENCY, tenant: { slug: "pine-hill" } }) as unknown as PortalFront,
  };
});

const { AskAQuestionView } = await import("./AskAQuestion");

function draw(billNumber: string | null = null) {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/ask-a-question"]}>
      <Routes>
        <Route
          path="/:tenant/portal/*"
          element={<AskAQuestionView billNumber={billNumber} />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  asked.mockClear();
  answers = ANSWERS;
  centres = [{ phone: OFFICE }];
});

describe("CWP-054 · ask a question (US-CWP-066)", () => {
  it("TC-1 — the bill travels with the question", async () => {
    const { container } = draw("BL-2608-0141");
    await screen.findByText("Might answer it now");

    fireEvent.change(container.querySelector("#question-what") as HTMLTextAreaElement, {
      target: { value: "My August water is nearly double July." },
    });
    fireEvent.click(screen.getByText("Send ✓"));

    expect(asked).toHaveBeenCalledTimes(1);
    expect(asked.mock.calls[0]?.[0]).toMatchObject({ bill_number: "BL-2608-0141" });
  });

  it("TC-5 — a question with NO bill is accepted; the first row says so", async () => {
    const { container } = draw(null);
    await screen.findByText("Might answer it now");

    const bill = container.querySelector("#question-bill") as HTMLSelectElement;
    // ⚠ **THE EMPTY ROW IS EXPLICIT AND CARRIES ITS OWN WORDS.** A dropdown
    // whose first row is a real bill has already answered for the customer.
    expect(bill.options[0]?.value).toBe("");
    expect(bill.options[0]?.textContent).toBe("Not about one bill");

    fireEvent.change(container.querySelector("#question-topic") as HTMLSelectElement, {
      target: { value: "something_else" },
    });
    fireEvent.change(container.querySelector("#question-what") as HTMLTextAreaElement, {
      target: { value: "When does the office open?" },
    });
    fireEvent.click(screen.getByText("Send ✓"));

    expect(asked.mock.calls[0]?.[0]).toMatchObject({ bill_number: "" });
  });

  it("TC-4 — three published answers appear, drawn from the answer store", async () => {
    const { container } = draw();
    await screen.findByText("Might answer it now");

    expect(container.querySelector("[data-suggestions]")?.getAttribute("data-suggestions")).toBe(
      "3",
    );
    expect(container.textContent).toContain("Why is my bill higher than last month?");
  });

  it("TC-3 — with NOTHING published the panel is ABSENT, not empty", async () => {
    answers = [];
    const { container } = draw();
    await screen.findByText("Or call");

    // `BR-CWP-093` — the link disappears with the content.
    expect(container.querySelector("[data-suggestions]")).toBeNull();
    expect(container.textContent).not.toContain("Might answer it now");
  });

  it("TC-7 — the photo box is HELD and there is NO file input anywhere", async () => {
    const { container } = draw();
    await screen.findByText("Or call");

    // ⚠ A disabled file input is still a file input.
    expect(container.querySelector("input[type='file']")).toBeNull();
    const picker = container.querySelector("[data-photo-picker='held']");
    expect(picker).not.toBeNull();
    expect(picker?.textContent).toContain("Photos come later this year");
  });

  it("TC-8 — the emergency number is present and DISTINCT from the office one", async () => {
    const { container } = draw();
    await screen.findByText("Or call");

    const office = container.querySelector("[data-phone='office']")?.textContent;
    const emergency = container.querySelector("[data-phone='emergency']")?.textContent;
    expect(office).toContain(OFFICE);
    expect(emergency).toContain(EMERGENCY);
    expect(office).not.toBe(emergency);
  });

  it("a utility with no centre on show draws no office line, rather than a blank one", async () => {
    centres = [];
    const { container } = draw();
    await screen.findByText("Or call");

    expect(container.querySelector("[data-phone='office']")).toBeNull();
    expect(container.querySelector("[data-phone='emergency']")).not.toBeNull();
  });

  it("the send control is HELD until a topic and some words exist (rule 33)", async () => {
    const { container } = draw();
    await screen.findByText("Or call");

    const send = screen.getByText("Send ✓");
    expect(send).toBeDisabled();
    expect(send).toHaveAttribute("title", "Choose a topic and write something.");

    fireEvent.change(container.querySelector("#question-topic") as HTMLSelectElement, {
      target: { value: "a_bill" },
    });
    fireEvent.change(container.querySelector("#question-what") as HTMLTextAreaElement, {
      target: { value: "Why is this so high?" },
    });
    expect(screen.getByText("Send ✓")).not.toBeDisabled();
  });

  it("TC-1's other half — the confirmation opens CWP-051 by reference", async () => {
    const { container } = draw("BL-2608-0141");
    await screen.findByText("Might answer it now");
    fireEvent.change(container.querySelector("#question-what") as HTMLTextAreaElement, {
      target: { value: "Why is this so high?" },
    });
    fireEvent.click(screen.getByText("Send ✓"));
    await screen.findByText("Your question is with us");

    expect(screen.getByText("Track this question →").getAttribute("href")).toBe(
      "/pine-hill/portal/requests/SR-26-0091",
    );
  });

  it("B14 rule 31 — every bill in the dropdown is named by its NUMBER", async () => {
    const { container } = draw();
    await screen.findByText("Or call");

    const bill = container.querySelector("#question-bill") as HTMLSelectElement;
    expect(bill.options[1]?.value).toBe("BL-2608-0141");
    expect(bill.options[1]?.textContent).toContain("BL-2608-0141");
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });
});
