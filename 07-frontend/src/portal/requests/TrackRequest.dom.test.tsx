// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-063 (EP-CWP-11) · Screen: CWP-051
// Rules:    BR-CWP-078 (never an internal routing comment) · BR-CWP-079
//           (withdrawable until approved; the account carries on) ·
//           BR-CWP-077 (a refusal always carries its reason) · B14 rule 31
//           (the `SR-` number is the identity) · rule 33
// Cases:    six steps with the dates the server sent · the routing note is
//           ABSENT · a customer-visible note is present · withdraw is offered
//           only when the server says so · a refusal shows its reason · the
//           customer can answer · *open for* is the server's number
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalRequestDetail } from "../api/portalClient";

let read: () => Promise<PortalRequestDetail> = async () => {
  throw new Error("no behaviour set");
};
const noted = vi.fn(async (note: string) => ({
  at: "2026-09-03T09:00:00Z",
  customer_visible: note.trim() !== "",
}));

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getRequest: () => read(),
    // ⚠ **NO `withdrawRequest` KEY — THE WRAPPER IS GONE (2026-09-19).** A mock
    // for an export that no longer exists is a fixture describing a world the
    // product left, and it is exactly how a deleted door goes on looking wired.
    addRequestNote: (_reference: string, note: string) => noted(note),
  };
});

const { TrackRequestView } = await import("./TrackRequest");

/** `US-CWP-063` §4 — the story's own fixture, as the SERVER serves it.
 *
 *  ⚠ **THERE IS NO `internal` FLAG AND NO `actor` ON THIS TYPE**, because there
 *  is none on the wire: the projection lives on the server and drops them by
 *  name. This fixture is the contract, so a screen cannot render a field it is
 *  never sent. */
const REQUEST: PortalRequestDetail = {
  reference: "SR-26-0056",
  //: ⚠ `null` — a move-out raised through the card writes the customer's own
  //: words, so there is no clerk sentence to replace and the page keeps its
  //: old title. `A_BILL_QUERY` below is the branch `CPB-12` is about.
  title: null,
  raised_through: "customer_portal",
  status: "more_info",
  is_open: true,
  may_withdraw: true,
  raised_at: "2026-09-02T09:14:00Z",
  open_for_days: 1,
  what_they_said: "Moving out on 17 September.",
  waiting_on: "Proof of address and your landlord's consent",
  refusal_reason: null,
  closed_at: null,
  steps: [
    { key: "sent", state: "done", at: "2026-09-02T09:14:00Z" },
    { key: "picked_up", state: "done", at: "2026-09-02T14:40:00Z" },
    { key: "we_need_something", state: "current", at: "2026-09-03T10:02:00Z" },
    { key: "we_decide", state: "future", at: null },
    { key: "in_hand", state: "future", at: null },
    { key: "finished", state: "future", at: null },
  ],
  timeline: [
    {
      at: "2026-09-03T10:02:00Z",
      kind: "note",
      to_state: null,
      note: "We need proof of address and your landlord's consent.",
      note_type: null,
    },
  ],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/portal` PATTERN, AND IT WAS NOT UNTIL
 * 2026-09-08** (`DEF-CWP-4707`, the shape `DEF-CWP-4698` recorded on the
 * Documents screen a wave earlier). This file rendered the view inside a bare
 * `MemoryRouter` with **no matching `<Route>`**, so `useParams().tenant` was
 * `undefined` and every address `usePortalPath` built came out `//portal/…` —
 * a protocol-relative URL to another host, which reads as a perfectly good
 * string to `toContain`. The finished-request card's *Ask a question* link is
 * built that way, so the one assertion that could have caught it could not
 * even be written here.
 */
function draw(request: PortalRequestDetail = REQUEST) {
  read = async () => request;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/requests/SR-26-0056"]}>
      <Routes>
        <Route
          path="/:tenant/portal/requests/:reference"
          element={<TrackRequestView reference="SR-26-0056" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

/** The same request as a BILL QUERY — the shape four of the six portal writes
 *  take, and the one `DEF-CWP-4198` and `DEF-CWP-4201` are both about. */
const A_BILL_QUERY: PortalRequestDetail = {
  ...REQUEST,
  reference: "SR-26-0009",
  title: { kind: "bill_query", number: "BL-2608-000044" },
  what_they_said:
    "Queried through the customer portal bill BL-2608-000044 (2026-07-01 to 2026-07-31, " +
    "843.36 USD): The bill is higher than usual. Their reason: We were away.",
};

afterEach(() => {
  cleanup();
  noted.mockClear();
});

describe("CWP-051 · track your request (US-CWP-063)", () => {
  it("TC-1 — six steps, two done, one current, and the dates the server sent", async () => {
    const { container } = draw();
    // ⚠ **THE REFERENCE APPEARS TWICE ON PURPOSE** — in the header and in the
    // details list — so the anchor is the progress card, which is unique.
    await screen.findByText("Progress");

    const steps = Array.from(container.querySelectorAll("[data-timeline-step]"));
    expect(steps).toHaveLength(6);
    expect(steps.map((step) => step.getAttribute("data-timeline-step"))).toEqual([
      "done",
      "done",
      "current",
      "future",
      "future",
      "future",
    ]);
    // ⚠ **THIS ASSERTION USED TO READ `toContain("2026-09-02")`, AND IT PASSED
    // WHILE THE SCREEN WAS WRONG** (`DEF-CWP-4204`). The ladder rendered
    // `step.at.slice(0, 10)` — the wire's own `YYYY-MM-DD` — so a test pinned to
    // that string was a test of the PAYLOAD, not of the screen, and it would
    // have gone RED the moment the fault was repaired. Wave L reported the same
    // shape three times in one file (`DEF-CWP-4178`).
    // **So it asks whether the DATE IS NAMED, in whichever format a tenant has
    // chosen**: the year, the day, and the month as a number or a word. That
    // holds for `2026-09-02`, `09/02/2026` and `2 September 2026` alike, and
    // still fails on a step with no date at all.
    const text = container.textContent ?? "";
    expect(text).toContain("2026");
    expect(text).toMatch(/(^|[^\d])0?9([^\d]|$)|Sep/i);
    expect(text).toMatch(/(^|[^\d])0?2([^\d]|$)/);
  });

  it("TC-2 — an internal routing note appears NOWHERE on the screen", async () => {
    // ⚠ The server never sends one; this asserts the screen invents nothing and
    // renders only what it was given.
    const { container } = draw();
    // ⚠ **THE REFERENCE APPEARS TWICE ON PURPOSE** — in the header and in the
    // details list — so the anchor is the progress card, which is unique.
    await screen.findByText("Progress");

    expect(container.textContent).not.toContain("Tuesday crew");
    expect(container.textContent).not.toContain("low priority");
  });

  it("TC-3 — a customer-visible note is shown in the clerk's own words", async () => {
    const { container } = draw();
    // ⚠ **THE REFERENCE APPEARS TWICE ON PURPOSE** — in the header and in the
    // details list — so the anchor is the progress card, which is unique.
    await screen.findByText("Progress");

    expect(container.querySelector("[data-note]")?.textContent).toBe(
      "We need proof of address and your landlord's consent.",
    );
  });

  it("TC-9 — *open for* is the SERVER's number and the screen does no arithmetic", async () => {
    const { container } = draw();
    // ⚠ **THE REFERENCE APPEARS TWICE ON PURPOSE** — in the header and in the
    // details list — so the anchor is the progress card, which is unique.
    await screen.findByText("Progress");

    expect(container.querySelector("[data-detail='open_for']")?.textContent).toBe("1 day");
  });

  it("TC-4 — SUPERSEDED: there is no withdraw control, in any state", async () => {
    // ⚠⚠ **THIS CASE CLICKED A BUTTON AND COUNTED A CALL UNTIL 2026-09-19, AND
    // IT WAS LEFT RED BY THE COMMIT THAT DELETED THE BUTTON.** The PO closed
    // the customer's own withdraw door with the clerk's (`OQ-CUS-12486`): *"if
    // customer dont want it - they will call and clark will refuse it. thats'it
    // . keep it simple"*. `BR-CWP-079` is SUPERSEDED and a withdrawal is a
    // REFUSAL REASON now — `Applicant withdrew`, one of the five the clerk's
    // Refuse dialog draws.
    //
    // ⚠ **IT IS DRAWN WITH `may_withdraw: true` ON PURPOSE.** The server can
    // never send that any more, and a fixture sending `false` would prove only
    // that a hidden control stays hidden — a check that cannot fail. This one
    // asserts that the SCREEN has no such control even when told it may.
    const { container } = draw({ ...REQUEST, may_withdraw: true });
    await screen.findByText("Progress");

    expect(container.querySelector("[data-action='withdraw']")).toBeNull();
    expect(screen.queryByText("Withdraw the request")).toBeNull();
    expect(container.textContent).not.toContain("Your account carries on as normal");
  });

  it("TC-5 — SUPERSEDED: it is absent after approval too, for the same reason", async () => {
    // The old TC-5 asserted the control vanished ONCE THE SERVER SAID SO. With
    // the control gone from the screen entirely, that assertion can no longer
    // fail — so this one keeps the state it was about and asserts the stronger
    // fact: nothing draws it, whatever the server says.
    const { container } = draw({ ...REQUEST, status: "approved", may_withdraw: true });
    await screen.findByText("Progress");

    expect(container.querySelector("[data-action='withdraw']")).toBeNull();
    expect(screen.queryByText("Withdraw the request")).toBeNull();
  });

  it("TC-10 — a refused request shows the refusal AND its reason", async () => {
    const { container } = draw({
      ...REQUEST,
      status: "refused",
      is_open: false,
      may_withdraw: false,
      refusal_reason: "The account at this address is in arrears.",
    });
    // ⚠ **THE REFERENCE APPEARS TWICE ON PURPOSE** — in the header and in the
    // details list — so the anchor is the progress card, which is unique.
    await screen.findByText("Progress");

    expect(container.querySelector("[data-refusal-reason]")?.textContent).toBe(
      "The account at this address is in arrears.",
    );
  });

  it("a refusal with no reason says the office will explain — never an empty panel", async () => {
    // `BR-CWP-093` — nothing empty ever appears.
    const { container } = draw({
      ...REQUEST,
      status: "refused",
      is_open: false,
      may_withdraw: false,
      refusal_reason: null,
    });
    // ⚠ **THE REFERENCE APPEARS TWICE ON PURPOSE** — in the header and in the
    // details list — so the anchor is the progress card, which is unique.
    await screen.findByText("Progress");

    expect(container.querySelector("[data-refusal-reason]")?.textContent).toBe(
      "The office will explain this to you.",
    );
  });

  it("the customer can answer the clerk's question, and the box is held until they write", async () => {
    const { container } = draw();
    // ⚠ **THE REFERENCE APPEARS TWICE ON PURPOSE** — in the header and in the
    // details list — so the anchor is the progress card, which is unique.
    await screen.findByText("Progress");

    const send = screen.getByText("Send ✓");
    expect(send).toBeDisabled();
    fireEvent.change(container.querySelector("#request-note") as HTMLTextAreaElement, {
      target: { value: "I have posted the tenancy agreement today." },
    });
    fireEvent.click(screen.getByText("Send ✓"));
    expect(noted).toHaveBeenCalledTimes(1);
  });

  it("an unknown reference gets ONE short sentence and no detail at all", async () => {
    // B14 rule 33 — five or six words — and BR-CWP-024's own reasoning: an
    // unknown reference, another customer's and another utility's are one answer.
    read = async () => {
      throw new Error("404");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/requests/SR-26-9999"]}>
        <TrackRequestView reference="SR-26-9999" />
      </MemoryRouter>,
    );
    await screen.findByText("We cannot find that reference.");

    expect(container.querySelector("[data-timeline]")).toBeNull();
    expect(container.querySelector("[data-detail='reference']")).toBeNull();
  });

  // ── CR-085 group I · the wireframe's *What has happened* thread ──────────
  //
  // ⚠ **THESE FOUR WERE WRITTEN AGAINST A LIVE FAULT AND EACH WAS SEEN RED
  // BEFORE IT WAS SEEN GREEN** (hard-won law 7). The screen guarded the card on
  // `request.timeline.length` and rendered `timeline.filter(has a note)`, so a
  // request whose whole history is note-less transitions — which is EVERY
  // request this product has ever raised from the portal — drew the heading
  // **WHAT WE HAVE TOLD YOU** over an empty list. Walked on the running
  // product at `SR-26-0022` on 2026-09-08.
  it("the thread card is ABSENT when every row is a note-less transition", async () => {
    // `BR-CWP-093` — nothing empty ever appears. This is the live shape: the
    // server drops a transition's note by name, so `timeline.length` is two
    // and the number of rows worth drawing is nought.
    const { container } = draw({
      ...REQUEST,
      what_they_said: "",
      timeline: [
        { at: "2026-09-02T09:14:30Z", kind: "state", to_state: "submitted", note: null, note_type: null },
        { at: "2026-09-02T09:14:00Z", kind: "state", to_state: "draft", note: null, note_type: null },
      ],
    });
    await screen.findByText("Progress");

    expect(container.querySelector("[data-testid='request-timeline']")).toBeNull();
    expect(container.textContent).not.toContain("What has happened");
  });

  it("the customer's OWN words open the thread, and are attributed to them", async () => {
    // The wireframe's first entry is *Aug 13 · You — the water reading looks…*
    // and it was on the wire as `what_they_said` and drawn NOWHERE: a customer
    // could not read back the sentence they had sent us.
    const { container } = draw();
    await screen.findByText("Progress");

    // ⚠ **THE LAST ENTRY, BECAUSE THE THREAD IS NEWEST FIRST** — the sentence
    // that started it is the oldest thing in it. A first draft of this case
    // read `querySelector` and failed on the clerk's reply, which is the check
    // catching the test rather than the screen.
    const entries = Array.from(container.querySelectorAll("[data-said]"));
    const said = entries[entries.length - 1];
    expect(said?.textContent).toBe("Moving out on 17 September.");
    expect(said?.getAttribute("data-said")).toBe("you");
  });

  it("every entry says WHO said it — us or you", async () => {
    const { container } = draw({
      ...REQUEST,
      timeline: [
        {
          at: "2026-09-03T11:00:00Z",
          kind: "note",
          to_state: null,
          note: "I have posted the tenancy agreement.",
          note_type: "customer_note",
        },
        {
          at: "2026-09-03T10:02:00Z",
          kind: "note",
          to_state: null,
          note: "We need proof of address and your landlord's consent.",
          note_type: null,
        },
      ],
    });
    await screen.findByText("Progress");

    const who = Array.from(container.querySelectorAll("[data-said]")).map((n) =>
      n.getAttribute("data-said"),
    );
    // Newest first, then the customer's opening sentence last.
    expect(who).toEqual(["you", "us", "you"]);
  });

  it("an open request with nothing outstanding SAYS so, rather than saying nothing", async () => {
    // The wireframe: *"Nothing is waiting on you"* is stated explicitly,
    // because uncertainty about whose turn it is drives the follow-up call.
    const { container } = draw({ ...REQUEST, waiting_on: null });
    await screen.findByText("Progress");

    expect(container.querySelector("[data-nothing-waiting]")).not.toBeNull();
    expect(container.querySelector("[data-detail='waiting_on']")).toBeNull();
  });

  it("a closed request offers no reply box", async () => {
    // The wireframe's CLOSED state. A box that posts onto a finished thread is
    // a control nobody reads the far end of.
    const { container } = draw({
      ...REQUEST,
      status: "completed",
      is_open: false,
      may_withdraw: false,
      waiting_on: null,
    });
    await screen.findByText("Progress");

    expect(container.querySelector("#request-note")).toBeNull();
    expect(container.querySelector("[data-nothing-waiting]")).toBeNull();
  });

  // ══ CR-085 wave 4 · CPB-12 — the page says WHAT, WHEN and WHAT WE WANT ══

  it("CPB-12 · DEF-CWP-4201 — the head names the request, not the page", async () => {
    // ⚠ **EVERY REQUEST IN THE PRODUCT WAS HEADED *Track your request*.** A
    // customer with two open could not tell from the head which one they had
    // opened, and the clerk's sentence was the only thing on the page that
    // said — in the third person, in the thread, under **You**.
    const { container } = draw(A_BILL_QUERY);
    await screen.findByText("Progress");
    const h1 = container.querySelector("h1");
    expect(h1?.textContent).toBe("A bill you queried — BL-2608-000044");
    expect(container.textContent).not.toContain("Track your request");
  });

  it("CPB-12 · a request we cannot classify keeps the old title, never a blank head", async () => {
    // A reported problem writes what the customer typed, so a KIND would be an
    // invention. `BR-CWP-093` — a true fallback over a guessed one.
    const { container } = draw();
    await screen.findByText("Progress");
    expect(container.querySelector("h1")?.textContent).toBe("Track your request");
  });

  it("CPB-12 · the head says when it was raised", async () => {
    // The drawing's lead — *Raised 2 September.* — was absent entirely.
    const { container } = draw();
    await screen.findByText("Progress");
    // ⚠ `?.textContent` on a missing node is `undefined`, and `toContain` then
    // fails with *"the given combination of arguments is invalid"* — a failure
    // that reads like a broken test rather than a missing sentence. Assert the
    // node first, then the words (law 7's third habit: a check's output must
    // distinguish pass from fail TO A READER).
    expect(container.querySelector("[data-raised]")).not.toBeNull();
    // ⚠ **THE RAW INSTANT IS THE RIGHT ANSWER HERE AND ONLY HERE.**
    // `usePortalDate` returns the server's string UNCHANGED when a tenant has
    // stated no format — *"declining to say is honest, inventing one for a
    // utility in Berlin is what shipped a five-hour error"* — and this fixture
    // states none. On Pine Hill, whose Regional setting is `MM/DD/YYYY`, the
    // same line reads *Raised 09/02/2026*; that half is proved in the browser
    // walkthrough, because only a real tenant can prove it.
    expect(container.querySelector("[data-raised]")?.textContent).toBe(
      "Raised 2026-09-02T09:14:00Z",
    );
    expect(container.querySelector("[data-detail='raised']")).not.toBeNull();
  });

  it("CPB-12 · the ladder says WHAT happened, not only WHEN", async () => {
    // ⚠ Six rows told a customer that something happened on the 3rd and never
    // what it was (`DEF-CWP-4201` row 51.4).
    const { container } = draw();
    await screen.findByText("Progress");
    const notes = [...container.querySelectorAll("[data-step-note]")].map(
      (one) => one.textContent,
    );
    expect(notes).toContain("through this website");
    expect(notes).toContain(
      "We are waiting for: Proof of address and your landlord's consent",
    );
  });

  it("CPB-12 · a future step says nothing at all", async () => {
    // `BR-CWP-093` — a step that has not happened has nothing true to say, and
    // a sentence there would be a promise about a step nobody has taken.
    const { container } = draw();
    await screen.findByText("Progress");
    const future = [...container.querySelectorAll('[data-timeline-step="future"]')];
    expect(future).toHaveLength(3);
    for (const step of future) expect(step.querySelector("[data-step-note]")).toBeNull();
  });

  it("CPB-12 · the acting clerk is NOT drawn, because the server does not send one", async () => {
    // ⚠ **A RULE AND NOT A GAP.** The drawing's second step reads *Sarah at
    // the office*; `_customer_visible_events` drops the actor BY NAME
    // (`BR-CWP-052`) — *"who inside the utility touched it is the utility's
    // business"*. The absence is asserted so nobody "completes" the ladder by
    // inventing a name.
    const { container } = draw();
    await screen.findByText("Progress");
    const picked = container.querySelector('[data-timeline-step="done"]');
    expect(picked?.textContent).not.toMatch(/at the office/);
  });

  it("CPB-05 · DEF-CWP-4708 — the clerk's sentence is NOT the customer's own words", async () => {
    // ⚠ **`DEF-CWP-4198`'S SECOND SURFACE, WHICH THAT ROW DOES NOT NAME.** The
    // thread printed the composed worklist sentence under **You**, so a
    // customer read, of herself, *"… Their reason: …"*. Found by walking this
    // wave's own fix: the customer note `CPB-05` adds appeared BESIDE it, the
    // same claim twice, once in her words and once in ours.
    const { container } = draw({
      ...A_BILL_QUERY,
      timeline: [
        {
          at: "2026-09-08T15:28:00Z",
          kind: "note",
          to_state: null,
          note: "The amount is higher than I expected. We were away.",
          note_type: "customer_note",
        },
      ],
    });
    await screen.findByText("Progress");
    expect(container.textContent).not.toContain("Queried through the customer portal");
    expect(container.textContent).not.toContain("Their reason");
    // Their own words are still there, once, and attributed to them.
    const said = [...container.querySelectorAll("[data-said='you']")].map((n) => n.textContent);
    expect(said).toEqual(["The amount is higher than I expected. We were away."]);
  });

  it("CPB-05 · a request we did not compose still opens with what the customer typed", async () => {
    // A reported problem writes their words into the same column, so there is
    // nothing to drop and the drawing's first entry stands.
    const { container } = draw();
    await screen.findByText("Progress");
    expect(container.textContent).toContain("Moving out on 17 September.");
  });

  it("CPB-12 · the state chip is drawn ONCE, with the identity, in the page head", async () => {
    // ⚠ **NOTHING ASSERTED THIS CHIP AT ALL** until 2026-09-08, which is why it
    // could sit alone on a line under the roll-up over an empty row and no test
    // minded. `PageHeader`'s `status` slot renders it with the `<h1>` —
    // *"state is not an action"*, `DEF-966` — and this asserts BOTH halves: it
    // is there, and there is only one of it.
    const { container } = draw();
    await screen.findByText("Progress");
    const chips = container.querySelectorAll('[data-chip="request-status"]');
    expect(chips).toHaveLength(1);
    expect(chips[0]?.textContent).toBe("Waiting on you");
    // …and it is inside the page head, not floating above the two columns.
    const head = container.querySelector("h1")?.closest("div, header");
    expect(head?.contains(chips[0] as Node)).toBe(true);
  });

  it("B14 rule 31 — the visible identity is the SR- number and no id is drawn", async () => {
    const { container } = draw();
    // ⚠ **THE REFERENCE APPEARS TWICE ON PURPOSE** — in the header and in the
    // details list — so the anchor is the progress card, which is unique.
    await screen.findByText("Progress");

    // ⚠ **THE HEAD'S KICKER CARRIES IT NOW** (`CPB-12`): it was a bold span
    // under the title, and the title said *"Track your request"* whichever
    // request you had opened. `08-screen-layouts.md` makes the reference the
    // kicker, and the rail draws it a second time as the drawing does.
    expect(screen.getAllByText("SR-26-0056").length).toBeGreaterThanOrEqual(2);
    expect(container.querySelector("[data-detail='reference']")?.textContent).toBe("SR-26-0056");
    // Nothing that looks like a uuid is on the screen.
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });
});
