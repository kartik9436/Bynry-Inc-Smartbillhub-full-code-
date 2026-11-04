// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-060 (EP-CWP-11) · Screen: CWP-046
// Rules:    BR-CWP-075 · BR-CWP-076 · BR-CWP-080 (moving out and stopping
//           service are DIFFERENT, and the cards say which) · BR-CWP-093
//           (nothing empty ever appears) · BR-CWP-056 (held WITH its reason) ·
//           B14 rule 31 (no database id on screen) · rule 33 · rule 35
// Cases:    TC-1 six cards + open requests · TC-4 SR-26-0056 · Move out ·
//           17 Sep · WE NEED TWO DOCUMENTS · TC-6 an empty state naming what
//           fills it · TC-8 a renamed category shows its new label
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalRequestHub } from "../api/portalClient";

let readHub: () => Promise<PortalRequestHub> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getRequestHub: () => readHub() };
});

const { RequestsView } = await import("./Requests");

/** `US-CWP-060` §4's own fixture: six cards for Pine Hill, and `SR-26-0056`. */
const HUB: PortalRequestHub = {
  errands: [
    { code: "move_out", label: "portal.errand.move_out.title", hint: "portal.errand.move_out.hint", to: null, held_reason: "not_online_yet" },
    { code: "move_home", label: "portal.errand.move_home.title", hint: "portal.errand.move_home.hint", to: null, held_reason: "not_online_yet" },
    { code: "add_service", label: "portal.errand.add_service.title", hint: "portal.errand.add_service.hint", to: null, held_reason: "not_online_yet" },
    { code: "stop_for_a_while", label: "portal.errand.stop_for_a_while.title", hint: "portal.errand.stop_for_a_while.hint", to: "/stop-or-restart", held_reason: null },
    { code: "report_problem", label: "portal.errand.report_problem.title", hint: "portal.errand.report_problem.hint", to: "/report", held_reason: null },
    // ⚠ **LIVE SINCE 2026-09-05, AND IT WAS `to: null` HERE FOR A DAY WHILE
    // `CWP-054` ANSWERED AT `/ask-a-question`.** A fixture is a picture of the
    // product, so a stale one keeps a shut door looking correct in every
    // assertion below it.
    { code: "something_else", label: "portal.errand.something_else.title", hint: "portal.errand.something_else.hint", to: "/ask-a-question", held_reason: null },
  ],
  open_requests: [
    {
      reference: "SR-26-0056",
      // ⚠ **`null` IS THE CUSTOMER'S OWN WORDS BEING THE ANSWER**, which is
      // what a move-out request raised through the card writes. The bill query
      // below is the other branch, and it is the one `DEF-CWP-4198` is about.
      title: null,
      what: "Move out",
      raised_on: "2026-09-02",
      status: "more_info",
      documents_wanted: 2,
    },
  ],
  closed_requests: [],
  lists_only_portal_requests: true,
};

/**
 * ⚠ **THE SENTENCE A CLERK READS, WORD FOR WORD OFF THE LIVE DEMO**
 * (2026-09-08, Ana's own requests list). 271 characters, two ISO dates, a
 * doubled full stop, and the customer described to herself in the third
 * person. It is the fixture rather than a paraphrase because the assertion
 * that matters is that **none of it reaches the screen**.
 */
const CLERK_SENTENCE =
  "Queried through the customer portal bill BL-2608-000044 (2026-07-01 to 2026-07-31, " +
  "843.36 USD): The bill is higher than usual. Their reason: We were away for three weeks " +
  "in July and the house was empty.. They read the meter themselves today: 41988.";

const A_BILL_QUERY = {
  reference: "SR-26-0009",
  title: { kind: "bill_query", number: "BL-2608-000044" },
  what: CLERK_SENTENCE,
  raised_on: "2026-09-08",
  status: "submitted",
  documents_wanted: 0,
};

/** The same query after the customer called it off — `CPB-11`'s whole subject. */
const WITHDRAWN = { ...A_BILL_QUERY, status: "withdrawn" };

/**
 * ⚠ **THE `:tenant` ROUTE IS DECLARED AND THAT IS LOAD-BEARING.**
 * `usePortalPath` reads the tenant off the ADDRESS THE BROWSER IS ON
 * (`BR-CWP-005`), which means `useParams().tenant` — and a `MemoryRouter` with
 * an `initialEntries` but no matching `<Route>` binds no params at all. Every
 * card's href would then be `//portal/…`, which is exactly the defect
 * `PortalShell.test.tsx` records finding on the six shell tabs. Declaring the
 * route is what makes the href assertions below able to fail.
 */
function draw(hub: PortalRequestHub) {
  readHub = async () => hub;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/requests"]}>
      <Routes>
        <Route path="/:tenant/portal/requests" element={<RequestsView />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-046 · what do you need (US-CWP-060)", () => {
  it("DEF-CWP-3954 — the reference is the door to CWP-051, and it is the SR number", async () => {
    // ⚠ This table listed a customer's open requests and none of the rows
    // could be opened — the same shape as the bills list one tab away.
    // ⚠ The visible value and the path segment are both the `SR-` number
    // (B14 rule 31): it is what is printed on the paper and what the customer
    // reads out on the telephone, never a row id.
    const { container } = draw(HUB);
    await screen.findByText("SR-26-0056");
    const link = container.querySelector("[data-request-link='SR-26-0056']");
    expect(link?.getAttribute("href")).toBe("/pine-hill/portal/requests/SR-26-0056");
    expect(link?.textContent).toBe("SR-26-0056");
  });

  it("a request with no reference is drawn, and is NOT a link", async () => {
    // `/requests/` with an empty segment opens nothing, so a stated absence
    // stays a stated absence (`BR-CWP-093`).
    const { container } = draw({
      ...HUB,
      open_requests: [{ ...HUB.open_requests[0]!, reference: null }],
    });
    await screen.findByText("No reference yet");
    expect(container.querySelector("[data-request-link]")).toBeNull();
  });

  it("TC-1 · six cards in the customer's language, plus the open requests", async () => {
    const { container } = draw(HUB);
    // ⚠ SCOPED TO THE CARD, because *"Move out"* is deliberately the same
    // words in two places — the card a customer presses and the request they
    // already raised — and a bare text query cannot tell them apart.
    expect(await screen.findByRole("heading", { name: "Move out" })).toBeInTheDocument();
    expect(container.querySelectorAll("[data-errand]")).toHaveLength(6);
    // ⚠ BR-CWP-080 — moving out and stopping service are DIFFERENT things and
    // the two cards say which, in the customer's own words rather than ours.
    expect(screen.getByText("Stop service for a while")).toBeInTheDocument();
    expect(
      screen.getByText("For an empty property. The account stays open."),
    ).toBeInTheDocument();
    expect(screen.getByText("SR-26-0056")).toBeInTheDocument();
  });

  it("TC-1 · a card whose screen exists is a LINK and one that does not is HELD", async () => {
    const { container } = draw(HUB);
    await screen.findByRole("heading", { name: "Move out" });
    // The three built screens carry real hrefs inside this utility's portal.
    const live = container.querySelectorAll('a[href="/pine-hill/portal/stop-or-restart"]');
    expect(live).toHaveLength(1);
    expect(
      container.querySelectorAll('a[href="/pine-hill/portal/report"]'),
    ).toHaveLength(1);
    // ⚠ **THE ADDRESS, NOT THE FACT THAT SOMETHING RENDERED** (hard-won law 2's
    // mirror). This card was grey over `CWP-054` for a day; an assertion that
    // only counted held controls was true throughout. What could have caught it
    // is exactly this line — the destination, spelled out.
    expect(
      container.querySelectorAll('a[href="/pine-hill/portal/ask-a-question"]'),
    ).toHaveLength(1);
    // ⚠ Hard-won law 2 — the three that are not built are DISABLED WITH THEIR
    // REASON, never a link to nowhere and never hidden (BR-CWP-056).
    expect(container.querySelectorAll('[data-held="true"]')).toHaveLength(3);
    expect(screen.getAllByText("Not online yet — call us")).toHaveLength(3);
  });

  it("TC-4 · a request waiting on documents says how many, in words", async () => {
    const { container } = draw(HUB);
    await screen.findByText("SR-26-0056");
    const chip = container.querySelector('[data-chip="documents-wanted"]');
    expect(chip).not.toBeNull();
    // ⚠ `_one` / `_other` does the grammar — the screen assembles no English.
    expect(chip?.textContent).toBe("We need 2 documents");
    // ⚠ B14 rule 31 — the human reference, and no row id anywhere on screen.
    expect(container.innerHTML).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  it("TC-4 · one document reads in the singular", async () => {
    const one = {
      ...HUB,
      open_requests: [{ ...HUB.open_requests[0]!, documents_wanted: 1 }],
    };
    const { container } = draw(one);
    await screen.findByText("SR-26-0056");
    expect(container.querySelector('[data-chip="documents-wanted"]')?.textContent).toBe(
      "We need one document",
    );
  });

  it("TC-4 · a request waiting on nothing shows its state, never a raw code", async () => {
    const plain = {
      ...HUB,
      open_requests: [
        { ...HUB.open_requests[0]!, status: "in_fulfilment", documents_wanted: 0 },
      ],
    };
    const { container } = draw(plain);
    await screen.findByText("SR-26-0056");
    // ⚠ ONE VOCABULARY FOR ELEVEN STATES (`DEF-CWP-4709`): this read *Being
    // done* from `portal.requests.state.*` while `CWP-051` read *In hand* from
    // `portal.request.state.*` for the same request. The complete map wins.
    expect(container.textContent).toContain("In hand");
    // ⚠ An internal state code is an internal code in clerk-facing copy.
    expect(container.textContent).not.toContain("in_fulfilment");
  });

  it("TC-6 · no open requests is a sentence naming what fills it, not a blank list", async () => {
    const { container } = draw({ ...HUB, open_requests: [] });
    await screen.findByRole("heading", { name: "Move out" });
    expect(container.querySelector("[data-requests-empty]")).not.toBeNull();
    expect(screen.getByText("Anything you ask us for will appear here.")).toBeInTheDocument();
    // BR-CWP-093 — no table of dashes behind the sentence.
    expect(container.querySelectorAll("[data-minitable]")).toHaveLength(0);
  });

  it("TC-8 · a tenant that renamed a card shows the NEW label", async () => {
    const renamed = {
      ...HUB,
      errands: [
        { ...HUB.errands[0]!, label: "Leaving the property", hint: "We will close your account" },
        ...HUB.errands.slice(1),
      ],
    };
    draw(renamed);
    // The label is whatever the utility configured — the screen holds no copy
    // of the original and cannot re-impose it.
    expect(await screen.findByText("Leaving the property")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Move out" })).toBeNull();
  });

  it("says what the list holds, because a counter-raised request cannot appear", async () => {
    const { container } = draw(HUB);
    await screen.findByText("SR-26-0056");
    expect(container.querySelector("[data-requests-scope]")?.textContent).toBe(
      "This list is what you have asked for online.",
    );
  });

  // ══ CR-085 wave 4 · CPB-05 — what a request IS, in the customer's words ══

  it("CPB-05 · DEF-CWP-4198 — a bill query reads as a bill query, not as a clerk's note", async () => {
    // ⚠ **THE ASSERTION THAT MATTERS IS THE ABSENCE.** Ana's own list printed
    // the whole 271-character worklist sentence in the column headed WHAT.
    const { container } = draw({ ...HUB, open_requests: [A_BILL_QUERY] });
    await screen.findByText("SR-26-0009");
    // ⚠ **THE ABSENCE IS ASSERTED FIRST, ON PURPOSE.** It is the assertion the
    // defect is about, and an assertion that never RUNS because an earlier one
    // failed is an assertion nobody proved red.
    expect(container.textContent).not.toContain("Queried through the customer portal");
    expect(container.textContent).not.toContain("Their reason");
    // ⚠ Two ISO dates and a money figure travelled inside it too.
    expect(container.textContent).not.toContain("2026-07-01");
    expect(container.textContent).not.toContain("843.36 USD");
    expect(container.querySelector('[data-what="bill_query"]')?.textContent).toBe(
      "A bill you queried — BL-2608-000044",
    );
  });

  it("CPB-05 · a bill query whose number could not be read still says what it is", async () => {
    // The kind survives without the number, so no screen prints
    // *"A bill you queried — "* with nothing after it.
    const { container } = draw({
      ...HUB,
      open_requests: [{ ...A_BILL_QUERY, title: { kind: "bill_query", number: null } }],
    });
    await screen.findByText("SR-26-0009");
    expect(container.querySelector('[data-what="bill_query"]')?.textContent).toBe(
      "A bill you queried",
    );
  });

  it("CPB-05 · a kind this screen has no word for falls back to their words, never the code", async () => {
    // ⚠ `i18next` returns the KEY when it does not know one, so a seventh
    // marker added on the server before this screen learns it would otherwise
    // print `portal.requests.kind.undefined` in a customer's table.
    const { container } = draw({
      ...HUB,
      open_requests: [
        { ...A_BILL_QUERY, title: { kind: "something_new", number: null }, what: "My own words" },
      ],
    });
    await screen.findByText("SR-26-0009");
    expect(container.textContent).toContain("My own words");
    expect(container.textContent).not.toContain("portal.requests.kind");
  });

  it("CPB-05 · a reported problem still shows what the customer typed", async () => {
    const { container } = draw({
      ...HUB,
      open_requests: [
        { ...A_BILL_QUERY, title: null, what: "Water coming out of the pavement." },
      ],
    });
    await screen.findByText("SR-26-0009");
    expect(container.querySelector('[data-what="their-words"]')?.textContent).toBe(
      "Water coming out of the pavement.",
    );
  });

  // ══ CR-085 wave 4 · CPB-11 — a finished request still has a door ══════════

  it("CPB-11 · DEF-CWP-4203 — a withdrawn request is reachable, and is not there by default", async () => {
    // ⚠ **THE RED THIS CLOSES, MEASURED LIVE ON 2026-09-08**: Ana raised a
    // query, withdrew it, and `open_requests` came back EMPTY with the row
    // still on file. The reference we had handed her opened nothing she could
    // find her way back to.
    const { container } = draw({ ...HUB, open_requests: [], closed_requests: [WITHDRAWN] });
    await screen.findByRole("heading", { name: "Move out" });
    // Still open: the sentence, and no sign of the withdrawn one.
    expect(container.querySelector("[data-requests-empty]")).not.toBeNull();
    expect(container.textContent).not.toContain("SR-26-0009");
    // The switch is there BECAUSE something is behind it.
    const scope = container.querySelector('[data-segmented="requests-scope"]');
    expect(scope).not.toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "All of them" }));
    expect(await screen.findByText("SR-26-0009")).toBeInTheDocument();
    expect(container.textContent).toContain("Withdrawn");
  });

  it("CPB-11 · the switch is ABSENT while nothing is finished", async () => {
    // `BR-CWP-093` — a filter over a list with one half is a control that
    // does nothing, and it appears on its own the day a request closes.
    const { container } = draw(HUB);
    await screen.findByText("SR-26-0056");
    expect(container.querySelector('[data-segmented="requests-scope"]')).toBeNull();
  });

  it("CPB-11 · the full list is in one date order, not open-then-closed", async () => {
    // ⚠ Concatenating the server's two lists would print every open request
    // above every closed one whatever the dates said.
    const older = { ...A_BILL_QUERY, reference: "SR-26-0001", raised_on: "2026-01-04" };
    const newest = { ...WITHDRAWN, reference: "SR-26-0099", raised_on: "2026-09-08" };
    const { container } = draw({
      ...HUB,
      open_requests: [{ ...older, status: "submitted" }],
      closed_requests: [newest],
    });
    await screen.findByText("SR-26-0001");
    fireEvent.click(screen.getByRole("radio", { name: "All of them" }));
    await screen.findByText("SR-26-0099");
    const order = [...container.querySelectorAll("[data-reference]")].map(
      (one) => one.textContent,
    );
    expect(order).toEqual(["SR-26-0099", "SR-26-0001"]);
  });

  it("CPB-11 · a finished request keeps its own state word, never the with-us fallback", async () => {
    // ⚠ The list's tone map held SEVEN of the eleven states, so a request the
    // customer had called off would have drawn the fallback chip *With us* —
    // the opposite of the truth (`DEF-CWP-4706`).
    const { container } = draw({ ...HUB, open_requests: [], closed_requests: [WITHDRAWN] });
    await screen.findByRole("heading", { name: "Move out" });
    fireEvent.click(screen.getByRole("radio", { name: "All of them" }));
    await screen.findByText("SR-26-0009");
    const chip = container.querySelector('[data-chip="withdrawn"]');
    expect(chip?.textContent).toBe("Withdrawn");
    expect(container.textContent).not.toContain("With us");
  });

  it("a read that fails says so and draws no cards", async () => {
    readHub = async () => {
      throw new Error("nope");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/requests"]}>
        <Routes>
          <Route path="/:tenant/portal/requests" element={<RequestsView />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(
      await screen.findByText("We could not read this. Please try again."),
    ).toBeInTheDocument();
    expect(container.querySelectorAll("[data-errand]")).toHaveLength(0);
  });
});
