// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-057 (EP-CWP-10) · Screen: CWP-057
// Rules:    BR-CWP-092 (an unmapped tier renders as an ABSENCE, never rounded)
//           · BR-CWP-091 (a hold stops a disconnection, not the debt) ·
//           BR-CWP-051 (a write-off shows amount and date, never its reason) ·
//           BR-CWP-093 · B14 rule 31 · rule 32
// Open:     OQ-CWP-1600 — nothing prices a reconnection deposit, so the panel
//           states the requirement in words and the closing row is a SUBTOTAL
// Cases:    the headline and the timeline · the absence where a deposit would
//           be · the unmapped rung drawn as an absence · a future step reads
//           *no earlier than* · a hold names itself and the debt stands · a
//           write-off shows amount and date and no reason · nothing overdue
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalArrears } from "../api/portalClient";

let readArrears: () => Promise<PortalArrears> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getArrears: () => readArrears() };
});

const { OverdueView } = await import("./Overdue");

/** `US-CWP-057` §4 — `22 Palm Ct`, `$412.60` overdue by 19 days on 2 Sep 2026.
 *
 * ⚠ **THE DEPOSIT IS `null` AND THE CLOSING FIGURE IS `$507.60`.** The story
 * works `$657.60` on a `$150.00` deposit; no read in this product answers that
 * figure (`OQ-CWP-1600`), so the server sends the two parts it has and names
 * the one it does not. */
const OVERDUE: PortalArrears = {
  as_of: "2026-09-02",
  overdue: true,
  //: `CWP-060`'s second placement. `null` is the normal case — the slot closes
  //: up entirely (`BR-CWP-093`) and the cases below assert BOTH directions.
  attached_answer: null,
  owed: "412.6000",
  currency: "USD",
  due_on: "2026-08-14",
  days_overdue: 19,
  tier: "tier_2_10_day",
  tier_unmapped: false,
  chips: ["tier_2_10_day"],
  tier_reached_on: "2026-09-01",
  case_open: true,
  timeline: [
    { step: "due", tier: null, unmapped: false, on: "2026-08-14", is_floor: false, state: "done" },
    {
      step: "notice_sent", tier: "tier_1_reminder", unmapped: false, on: "2026-08-21",
      is_floor: false, state: "done", served_channel: null, served_on: null,
    },
    {
      step: "notice_sent", tier: "tier_2_10_day", unmapped: false, on: "2026-09-01",
      is_floor: false, state: "done", served_channel: null, served_on: null,
    },
    {
      step: "notice_next", tier: "tier_3_48_hour", unmapped: false, on: "2026-09-15",
      is_floor: true, state: "current",
    },
    { step: "cut", tier: null, unmapped: false, on: "2026-09-25", is_floor: true, state: "future" },
  ],
  services_at_risk: ["WATER"],
  ladder_running: true,
  halt_code: null,
  held_by: [],
  cost: {
    parts: [
      { part: "owed", amount: "412.6000", already_owed: false },
      { part: "reconnection_fee", amount: "95.0000", already_owed: false },
      { part: "new_deposit", amount: null, already_owed: false },
    ],
    parts_missing: ["new_deposit"],
    subtotal: "507.6000",
    currency: "USD",
    // ⚠ Before the cut, so the fee is a QUOTE and the sum adds it
    // (`DEF-CWP-6072`). `TC-FEE-ISSUED` below is the other side.
    basis: { code: "arrears_plus_the_quoted_fee", fee_in_arrears: false },
    // ⚠ `detail` is on the WIRE and off the client type (`PortalProblem`,
    //    `DEF-CWP-3926`). The fixture keeps it so this stays a picture of what
    //    the server actually sends.
    problems: [
      { code: "reconnection_deposit_not_priced", oq_ref: "OQ-CWP-1600", detail: "…" },
    ] as unknown as PortalArrears["cost"]["problems"],
  },
  reconnection_fee_absence: null,
  new_deposit_required: true,
  write_offs: [],
  scheduler: { advances_on_a_schedule: false },
  problems: [],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant` PATTERN** (CLAUDE.md hard-won law 2).
 * With an `initialEntries` and no matching `<Route>`, `useParams().tenant` is
 * `undefined` and every address this screen builds comes out `//portal/…` — a
 * protocol-relative URL to another host, which reads as a perfectly good
 * string to `toContain`. The door assertion below could not fail without it.
 */
function draw(body: PortalArrears) {
  readArrears = async () => body;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/overdue"]}>
      <Routes>
        <Route path="/:tenant/portal/overdue" element={<OverdueView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-057 · what happens if this is not paid (US-CWP-057)", () => {
  it("DEF-CWP-3954 — three doors, and two of them opened NOTHING until today", async () => {
    // ⚠ `to="ask-for-a-plan"` and `to="help-paying"` had no leading slash, and
    // `usePortalPath` CONCATENATES — so they resolved to
    // `/pine-hill/portalask-for-a-plan`, an address no route serves. The
    // string was in the DOM, so `tsc` and every `toContain` passed on it.
    // Asserted WHOLE here, which is the only form that can tell them apart.
    // The third door is `CWP-064`, which nothing in the product pointed at.
    const { container } = draw(OVERDUE);
    await screen.findByText("You can stop this");
    // ⚠ **EVERY ANCHOR ON THE SCREEN, NOT A LIST OF BOXES TO LOOK IN**
    // (`CR-085` task (c)). The previous form named three CSS selectors — the
    // page head and two shapes of sibling `div` beside `[data-stop-it]` — so
    // it was a claim about where links SIT rather than about which doors
    // exist. Moving *Your protections* into its own panel took that door out
    // of the selector's reach and the case went on passing over three of the
    // four: hard-won law 7's *looking at the wrong thing*, in a case written
    // to catch exactly this. Selecting all anchors cannot drift that way — a
    // door that moves is still counted, and a door that stops being drawn
    // fails here. Order matters: it is what caught
    // `/pine-hill/portalask-for-a-plan`.
    const doors = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(doors).toEqual([
      // The FILLED one, and the one that was missing altogether until today:
      // the drawing's *three ways out* named two.
      "/pine-hill/portal/pay-now",
      "/pine-hill/portal/ask-for-a-plan",
      "/pine-hill/portal/help-paying",
      "/pine-hill/portal/protections",
    ]);
  });

  it("CR-085 — the three ways out are one group, and paying is the filled one", async () => {
    // ⚠ **THE FIGURE ON THE PAY CONTROL IS THE SERVER'S `owed`.** A label that
    // named a different number from the headline one line above it would be
    // this screen's worst possible defect, and nothing else here checks it.
    const { container } = draw(OVERDUE);
    await screen.findByText("You can stop this");
    const ways = container.querySelector("[data-stop-it]")?.parentElement;
    const labels = [...(ways?.querySelectorAll("a") ?? [])].map((a) => a.textContent);
    expect(labels).toEqual([
      "Pay $412.60",
      "Ask for a payment plan",
      "See what help there is",
    ]);
  });

  it("CR-085 — the protections door asks a question instead of claiming a hold", async () => {
    // ⚠ **THE LINK USED TO BE LABELLED *Something is holding this*** — the
    // heading of the panel that appears when one does — so on an account with
    // no hold at all the screen asserted the opposite of its own answer.
    const { container } = draw(OVERDUE);
    await screen.findByText("You can stop this");
    expect(container.querySelector("[data-medical]")?.textContent).toContain(
      "depends on a machine",
    );
    expect(container.textContent).not.toContain("Something is holding this");
  });

  it("TC-1 — the headline names the amount and the days, and the timeline is the case's", async () => {
    const { container } = draw(OVERDUE);
    await screen.findByText(/412\.60 is overdue by 19 days/);
    const steps = container.querySelectorAll("[data-timeline-step]");
    expect(steps).toHaveLength(5);
    expect(container.textContent).toContain("2026-08-14");
    expect(container.textContent).toContain("2026-08-21");
    expect(container.textContent).toContain("2026-09-01");
  });

  it("TC-2 — the deposit is an ABSENCE IN WORDS and the closing row is a subtotal", async () => {
    // ⚠ **THE CASE THIS SCREEN EXISTS TO GET RIGHT.** A `$0.00` here would tell
    // a frightened customer that getting reconnected costs nothing beyond the
    // fee — and it would have passed every other check in this repo.
    const { container } = draw(OVERDUE);
    await screen.findByText(/412\.60 is overdue by 19 days/);
    expect(container.querySelector("[data-part='owed']")?.textContent).toBe("$412.60");
    expect(container.querySelector("[data-part='reconnection_fee']")?.textContent).toBe("$95.00");
    // No figure at all where the deposit would be — and no `$0.00`, no dash.
    expect(container.querySelector("[data-part='new_deposit']")).toBeNull();
    expect(container.querySelector("[data-part-absent='new_deposit']")?.textContent).toBe(
      "required, ask us the amount",
    );
    expect(container.querySelector("[data-total='if-it-goes-that-far']")?.textContent).toContain(
      "$507.60",
    );
    expect(container.textContent).not.toContain("$0.00");
    expect(container.textContent).not.toContain("$657.60");
    // ⚠ **THE NEGATIVE HALF OF `DEF-CWP-6072`.** Before the cut the fee IS
    // added, so the *already in what you owe* line must not appear — a note
    // drawn unconditionally would pass the post-cut case exactly as a correct
    // one does (law 7: ask what would make this check pass wrongly).
    expect(container.querySelector("[data-part-included='reconnection_fee']")).toBeNull();
    // …and the panel says out loud that something is missing from the sum.
    expect(container.querySelector("[data-subtotal-note]")?.textContent).toContain(
      "A new deposit would be on top of this",
    );
  });

  it("DEF-CWP-6072 — after the cut the fee is SHOWN, said to be inside the figure, and NOT added", async () => {
    // ⚠ **THE SAME $95.00 WAS QUOTED TWICE.** `commit_cut` ISSUES the
    // reconnection fee, so from that instant it is an open bill and is already
    // inside what the customer owes — and this panel went on adding it. The
    // server now says so on the row (`already_owed`) and the subtotal stops
    // adding. Measured on `A-11340` after the first real cut: owed $75.00 +
    // fee $75.00 = $150.00, over a single $75.00 fee.
    const { container } = draw({
      ...OVERDUE,
      cost: {
        ...OVERDUE.cost,
        parts: [
          { part: "owed", amount: "95.0000", already_owed: false },
          { part: "reconnection_fee", amount: "95.0000", already_owed: true },
          { part: "new_deposit", amount: null, already_owed: false },
        ],
        subtotal: "95.0000",
        basis: { code: "the_position_the_cut_left_behind", fee_in_arrears: true },
      },
    });
    await screen.findByText(/412\.60 is overdue by 19 days/);
    // The fee is still on screen — a customer must see what they are charged.
    expect(container.querySelector("[data-part='reconnection_fee']")?.textContent).toContain(
      "$95.00",
    );
    // …and the row says, in five words, why the sum does not add it.
    expect(container.querySelector("[data-part-included='reconnection_fee']")?.textContent).toBe(
      "already in what you owe",
    );
    expect(container.querySelector("[data-total='if-it-goes-that-far']")?.textContent).toContain(
      "$95.00",
    );
    // The pre-fix figure, and it must never come back.
    expect(container.textContent).not.toContain("$190.00");
  });

  it("TC-3 · negative — an unmapped rung draws an ABSENCE, never a neighbour's chip", async () => {
    // ⚠ Showing somebody at the five-day notice as though they were at the
    // ten-day one MOVES THE DATE THEY THINK THEY HAVE.
    const { container } = draw({
      ...OVERDUE,
      tier: null,
      tier_unmapped: true,
      chips: [],
      timeline: [OVERDUE.timeline[0]!],
    });
    await screen.findByText(/412\.60 is overdue by 19 days/);
    expect(container.querySelector("[data-tier='absent']")?.textContent).toContain(
      "We cannot name the stage you are at",
    );
    expect(container.textContent).not.toContain("Ten-day notice");
    expect(container.textContent).not.toContain("Final notice");
    expect(container.querySelector("[data-chip='tier']")).toBeNull();
  });

  it("a future step reads NO EARLIER THAN and never a bare date", async () => {
    // ⚠ Nothing in this product advances a tier on a date, so the stored date
    // is a floor. A bare date would be a promise the product cannot keep.
    const { container } = draw(OVERDUE);
    await screen.findByText(/412\.60 is overdue by 19 days/);
    expect(container.textContent).toContain("no earlier than 2026-09-15");
    expect(container.textContent).toContain("no earlier than 2026-09-25");
  });

  it("TC-5 — the services that would be cut are named from the case", async () => {
    const { container } = draw(OVERDUE);
    await screen.findByText(/412\.60 is overdue by 19 days/);
    expect(container.querySelector("[data-services-at-risk]")?.textContent).toContain("WATER");
  });

  it("TC-6 · negative — a hold names itself AND the debt is said to stand", async () => {
    const { container } = draw({
      ...OVERDUE,
      ladder_running: false,
      halt_code: "protected",
      held_by: [{ kind: "medical_certificate", lifetime: "expires_on_a_date" }],
    });
    await screen.findByText(/412\.60 is overdue by 19 days/);
    const held = container.querySelector("[data-held-by]")?.textContent ?? "";
    expect(held).toContain("doctor's certificate");
    expect(held).toContain("The money is still owed");
    // ⚠ `BR-CWP-091` — the hold did not change the figure.
    expect(container.textContent).toContain("$412.60");
  });

  it("TC-9 · negative — a write-off shows its amount and date and no reason", async () => {
    const { container } = draw({
      ...OVERDUE,
      write_offs: [
        { amount: "87.4000", currency: "USD", date: "2026-06-02", state: "written_off" },
      ],
    });
    await screen.findByText(/412\.60 is overdue by 19 days/);
    const panel = container.querySelector("[data-write-offs]")?.textContent ?? "";
    expect(panel).toContain("$87.40");
    expect(panel).toContain("2026-06-02");
    expect(container.textContent?.toLowerCase()).not.toContain("bankrupt");
  });

  it("TC-10 · negative — an account that is not overdue draws no ladder at all", async () => {
    // ⚠ `BR-CWP-093` — an empty ladder reads as *we have already sent
    // everything* to the person least able to check.
    const { container } = draw({
      ...OVERDUE, overdue: false, days_overdue: null, case_open: false, timeline: [],
    });
    await screen.findByText("Nothing is overdue on this account.");
    expect(container.querySelector("[data-timeline]")).toBeNull();
    expect(container.querySelector("[data-total='if-it-goes-that-far']")).toBeNull();
  });

  it("DEF-CWP-3945 — an answer pinned to this screen IS DRAWN, with a routed link", async () => {
    // ⚠ **THE WHOLE POINT OF THE DEFECT.** The column, the staff field, the
    // published read and `AttachedAnswerCard` all existed; nothing joined
    // them, so a clerk ticked *also show this on the overdue screen*, the tick
    // saved, and the answer appeared nowhere.
    const { container } = draw({
      ...OVERDUE,
      attached_answer: {
        slug: "why-is-my-bill-higher",
        question: "Why is my bill higher?",
        topic: "billing",
        body: "A hot month usually means more water on the garden.",
        asked_for: "en",
        shown_in: "en",
        is_fallback: false,
        updated_on: "2026-08-30",
        also_written_in: ["en"],
        related: [],
      },
    });
    await screen.findByText("Why is my bill higher?");
    const card = container.querySelector("[data-attached-answer]");
    expect(card).not.toBeNull();
    expect(card?.textContent).toContain("more water on the garden");
    // ⚠ **THE ADDRESS, UNDER THE REAL `/:tenant/portal` PATTERN.** A bare
    // `/help/…` would come out `//portal/help/…` — a protocol-relative URL to
    // ANOTHER HOST that `toContain` accepts as a perfectly good string, which
    // is how a whole class of broken doors hid (`BR-CWP-007`).
    expect(card?.querySelector("a")?.getAttribute("href")).toBe(
      "/pine-hill/portal/help/why-is-my-bill-higher",
    );
  });

  it("DEF-CWP-3945 · negative — no answer pinned draws NO card at all", async () => {
    // `BR-CWP-093`. An empty card headed with a question is worse than no card.
    const { container } = draw(OVERDUE);
    await screen.findByText(/412\.60 is overdue by 19 days/);
    expect(container.querySelector("[data-attached-answer]")).toBeNull();
  });

  it("B14 rule 31 — no database id reaches the screen", async () => {
    const { container } = draw(OVERDUE);
    await screen.findByText(/412\.60 is overdue by 19 days/);
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
  });

  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` step 2, lane 7 — R-10 and the due date.
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-4919 — the screen says WHICH DAY it is counting from", async () => {
    // ⚠ `due_on` has been on the wire since `CR-068` wave H and not one line
    // of this screen read it: it said *overdue by 19 days* and never named the
    // date. A relative count is the one form a customer cannot check against
    // the letter in their hand, and the blueprint states the date in BOTH
    // frames and names it under TONE.
    const { container } = draw(OVERDUE);
    await screen.findByText(/is overdue by/);
    const line = container.querySelector("[data-due-on]");
    expect(line).not.toBeNull();
    expect(line?.textContent).toContain("It was due on");
  });

  it("DEF-CWP-4919 — a due date nobody recorded draws NOTHING, not an em-dash", async () => {
    // `BR-CWP-093`. An absence is stated or omitted; it is never punctuation.
    const { container } = draw({ ...OVERDUE, due_on: null });
    await screen.findByText(/is overdue by/);
    expect(container.querySelector("[data-due-on]")).toBeNull();
    expect(container.textContent).not.toContain("It was due on");
  });

  it("R-10 — a failed read still names the plan and the help route", async () => {
    // ⚠ **THE MOST FRIGHTENING ADDRESS IN THE PORTAL**, and a failed read left
    // it saying only that the read failed. The two doors are the two that need
    // no figure — *Pay $412.60* cannot be offered when the balance is what
    // could not be read.
    let calls = 0;
    readArrears = async () => {
      calls += 1;
      if (calls === 1) throw new Error("down");
      return OVERDUE;
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/overdue"]}>
        <Routes>
          <Route path="/:tenant/portal/overdue" element={<OverdueView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read this right now. Try again in a moment.");
    const card = container.querySelector('[data-portal-state="failed"]');
    expect(card?.querySelector('[data-way-out="ask-for-a-plan"]')?.getAttribute("href")).toBe(
      "/pine-hill/portal/ask-for-a-plan",
    );
    expect(card?.querySelector('[data-way-out="help-paying"]')?.getAttribute("href")).toBe(
      "/pine-hill/portal/help-paying",
    );
    // ⚠ And the control REALLY re-reads — a presence assertion would pass on a
    // button wired to nothing (`DEF-MET-4764`).
    fireEvent.click(container.querySelector('[data-way-out="try-again"]') as HTMLElement);
    expect(await screen.findByText(/is overdue by/)).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("R-22 — nothing overdue is an EMPTY state, not a failure", async () => {
    const { container } = draw({ ...OVERDUE, overdue: false });
    await screen.findByText("Nothing is overdue on this account.");
    expect(container.querySelector("[data-portal-state]")?.getAttribute("data-portal-state")).toBe(
      "empty",
    );
    // ⚠ **AND IT CARRIES NO WAYS OUT, DELIBERATELY.** R-10 is about bad news;
    // a row of buttons under *nothing is overdue* invites somebody in good
    // standing to ask for a payment plan they do not need.
    expect(container.querySelector("[data-ways-out]")).toBeNull();
  });

});
