// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-053 (EP-CWP-10) · Screen: CWP-063
// Rules:    BR-CWP-065 (a plan activates on the CUSTOMER's signature alone) ·
//           BR-CWP-063 (new bills still arrive and still have to be paid) ·
//           BR-CWP-001 (a signature is not one of the six portal writes) ·
//           BR-CWP-056 (held WITH its reason) · BR-CUS-043 (late-fee
//           suspension is a PER-PLAN election) · B14 rule 31 · rule 33
// Open:     OQ-CWP-1720 — the panel must NOT say a plan ends after two misses
// Defect:   DEF-CWP-4137 — it DID, and this file is why. The two sibling
//           screens each assert `not.toMatch(/plan ends/i)`
//           (AskForPlan.dom.test.tsx:149, YourPlan.dom.test.tsx:158); this one
//           had no such assertion and instead SUPPLIED `miss_two_ends_it` in
//           its own fixture, so the one test that rendered the forbidden
//           sentence treated it as expected input.
// Cases:    TC-1 the offer with its figures · TC-9 the consequence panel, read
//           from THIS plan's elections · the three controls in order, all held
//           (TC-2/5/6 are refused at the edge until OQ-CWP-1568) · the two
//           facts the record does not hold, stated rather than guessed ·
//           OQ-CWP-1720's absence
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalFront } from "../api/guestClient";
import { PortalRegionalProvider } from "../components/regional";
import type { PortalPlanOffer } from "../api/portalClient";

let readOffer: () => Promise<{ offer: PortalPlanOffer | null }> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getPlanOffer: () => readOffer() };
});

const { PlanOfferView } = await import("./PlanOffer");

/** `US-CWP-053` §4's own figures: `$172.20` covered, `$40.00` up front, five
 *  at `$22.03` and a final `$22.05` — `40.00 + 5 × 22.03 + 22.05 = 172.20`. */
const OFFER: PortalPlanOffer = {
  covers: "172.2000",
  paid_up_front: "40.0000",
  spread: "132.2000",
  currency: "USD",
  instalment_count: 6,
  cadence: "monthly",
  offered_on: "2026-09-02",
  first_payment_on: "2026-09-14",
  instalments: [
    { number: 1, due_on: "2026-09-14", amount: "22.0300", currency: "USD" },
    { number: 2, due_on: "2026-10-14", amount: "22.0300", currency: "USD" },
    { number: 3, due_on: "2026-11-14", amount: "22.0300", currency: "USD" },
    { number: 4, due_on: "2026-12-14", amount: "22.0300", currency: "USD" },
    { number: 5, due_on: "2027-01-14", amount: "22.0300", currency: "USD" },
    { number: 6, due_on: "2027-02-14", amount: "22.0500", currency: "USD" },
  ],
  consequences: ["late_fees_stop", "no_disconnect", "new_bills_still_due", "missed_we_get_in_touch"],
  expires_on: null,
  expires_on_unavailable: "OQ-CWP-1566",
  offered_by: null,
  offered_by_unavailable: "OQ-CWP-1567",
  agreement: { available: true, reason: null },
  actions_held: true,
  actions_held_reason: "OQ-CWP-1568",
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/portal` PATTERN** (CLAUDE.md hard-won
 * law 2). Bare inside a `MemoryRouter` with no matching `<Route>`,
 * `useParams().tenant` is `undefined` and every address this screen builds
 * comes out `//portal/…` — a protocol-relative URL to ANOTHER HOST that reads
 * as a perfectly good string to `toContain`. A door assertion cannot be
 * written truthfully without this.
 */
function draw(offer: PortalPlanOffer | null, front?: PortalFront) {
  readOffer = async () => ({ offer });
  const view = <PlanOfferView accountId="acc-1" />;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/plan-offer"]}>
      <Routes>
        <Route
          path="/:tenant/portal/plan-offer"
          element={
            front === undefined ? (
              view
            ) : (
              // The real screen's frame publishes the tenant's Regional
              // settings; the frame is not under test here, only what this
              // screen does with what it publishes.
              <PortalRegionalProvider front={front}>{view}</PortalRegionalProvider>
            )
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

/** A Texas utility: `MM/DD/YYYY`, which is what the real `GET /public/front`
 *  answers for the demo tenant. Used only by the expiry case below, because
 *  every other date on this screen is already asserted through `data-kv`. */
const FRONT = {
  tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: null, brand_accent_hex: null },
  is_live: true,
  regional: { timezone: "America/Chicago", date_format: "MM/DD/YYYY", language: null },
  locales: ["en", "es"],
  cards: [],
  links: { help: true, visit: true },
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: null,
} as unknown as PortalFront;

afterEach(cleanup);

describe("CWP-063 · a plan the utility has offered you (US-CWP-053)", () => {
  it("TC-1 · shows what it covers, what was paid up front, and the first payment", async () => {
    const { container } = draw(OFFER);
    expect(await screen.findByText("$172.20")).toBeInTheDocument();
    expect(screen.getByText("$40.00")).toBeInTheDocument();
    // ⚠ Read through `data-kv` rather than by text: 14 September is BOTH the
    // *First payment* line and instalment 1's due date, so a text query matches
    // two nodes. A test that cannot say WHICH one it found is not asserting the
    // summary line at all.
    expect(container.querySelector('[data-kv="first"]')?.textContent).toContain("2026-09-14");
    // The offer names the utility and the DATE the office set it up.
    expect(screen.getByText(/set this up on 2026-09-02/)).toBeInTheDocument();
  });

  it("the six instalments total what is SPREAD, not what the plan covers", async () => {
    const { container } = draw(OFFER);
    await screen.findByText("$172.20");
    // 5 × 22.03 + 22.05 = 132.20, which is 172.20 less the 40.00 already
    // received. Showing 172.20 here would look like the down payment is owed
    // a second time.
    const total = container.querySelector('[data-total="instalments"]');
    expect(total?.textContent).toContain("$132.20");
    expect(container.querySelectorAll("[data-instalment]")).toHaveLength(6);
    expect(container.querySelector('[data-instalment="6"]')?.textContent).toBe("$22.05");
  });

  it("TC-9 · the consequence panel says new bills still arrive", async () => {
    const { container } = draw(OFFER);
    await screen.findByText("$172.20");
    // BR-CWP-063 — believing the plan replaces the bill IS DEF-061.
    expect(
      screen.getByText(/New bills still arrive and still have to be paid/),
    ).toBeInTheDocument();
    expect(container.querySelector('[data-consequence-code="late_fees_stop"]')).not.toBeNull();
  });

  it("says late fees STILL APPLY when this plan does not suspend them", async () => {
    // BR-CUS-043 — a per-plan election, read from the row rather than promised
    // by the screen (J41 step 4).
    draw({
      ...OFFER,
      consequences: ["late_fees_continue", "new_bills_still_due", "missed_we_get_in_touch"],
    });
    expect(
      await screen.findByText(/Late fees still apply on this balance/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Late fees stop on this balance/)).not.toBeInTheDocument();
  });

  it("OQ-CWP-1720 — the panel does NOT say the plan ends after two misses", async () => {
    // ⚠ **THE SCREEN A CUSTOMER COMMITS ON, AND THE ONE THAT SAID IT.**
    // The blueprint's `P49`, `US-CWP-053` and journey `J42` all end the
    // consequence box with *"miss two and the plan ends, and the whole balance
    // falls due"*. **The Product Owner ruled the opposite on 2026-08-11** —
    // *"nodrop we chase for payments until write off"* — and that is what is
    // built: `record_missed_instalment` returns `active` on the tenth miss
    // exactly as on the first. `OQ-CWP-1720` is OPEN and its row states what
    // ships meanwhile: *the screen says only what the code does*.
    //
    // Asserted over the WHOLE rendered container rather than over one bullet,
    // because the defect was not a wrong bullet — it was a bullet nobody had
    // looked for.
    const { container } = draw(OFFER);
    expect(await screen.findByText(/What accepting this does/i)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/plan ends/i);
    expect(container.textContent).not.toMatch(/whole balance falls due/i);
    expect(container.textContent).toMatch(/we get in touch/i);
  });

  it("draws the three controls IN ORDER and holds all three with their reason", async () => {
    const { container } = draw(OFFER);
    await screen.findByText("$172.20");
    const order = [...container.querySelectorAll("[data-plan-action]")].map((node) =>
      node.getAttribute("data-plan-action"),
    );
    // `US-CWP-053` §1 — accepting is one press and *ask for different terms* is
    // a route rather than a dead end, so the order is part of the design.
    expect(order).toEqual(["accept", "different-terms", "decline"]);
    // BR-CWP-001 — a signature is not one of the six writes. Held, never
    // hidden and never live-but-inert (hard-won law 2 inverted).
    expect(screen.getByRole("button", { name: /Accept this plan/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /^Decline$/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Ask for different terms/ })).toBeDisabled();
    // B14 rule 33 — five or six words, rendered rather than only on `title`.
    // ⚠ **ONCE, UNDER THE GROUP — NOT ONCE PER BUTTON (`DEF-CWP-4920`).** This
    // read `toHaveLength(3)` and it was asserting the defect: three identical
    // refusals stacked under three buttons reads as a stutter and buries the
    // sentence. The three share one cause, so they share one sentence — and
    // every button still carries it on `title`, so a hover and a screen reader
    // still get the reason on the control itself.
    expect(screen.getAllByText("Call us to answer this offer")).toHaveLength(1);
    expect(container.querySelector("[data-plan-actions-held]")?.textContent).toBe(
      "Call us to answer this offer",
    );
    for (const action of ["accept", "different-terms", "decline"]) {
      expect(
        container
          .querySelector(`[data-plan-action='${action}'] button`)
          ?.getAttribute("title"),
      ).toBe("Call us to answer this offer");
    }
  });

  it("states the two facts the record does not hold, and invents neither", async () => {
    draw(OFFER);
    await screen.findByText("$172.20");
    // OQ-CWP-1566 — no column holds an expiry, so no date is computed.
    expect(
      screen.getByText(/have not recorded a closing date for this offer/i),
    ).toBeInTheDocument();
    // OQ-CWP-1567 — the clerk's name lives only on a pruned audit row.
    expect(screen.getByText(/cannot show you who set this up/i)).toBeInTheDocument();
    // ⚠ And no user id leaks in its place (B14 rule 31).
    expect(document.body.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/i);
  });

  it("shows a real expiry date when one is recorded, rather than the absence", async () => {
    // The screen must not hardcode the absence: the day OQ-CWP-1566 is answered
    // and a date arrives, this branch is what renders it.
    // ⚠ **AND IT GOES THROUGH THE TENANT'S OWN FORMAT — `DEF-CWP-4911`.** This
    // assertion used to expect the WIRE date, `2026-09-16`, which is what the
    // screen printed: the one date on `CWP-063` that never reached
    // `usePortalDate`, beside four others on the same screen already reading
    // `MM/DD/YYYY`. It was missed because `expires_on` is `null` on every
    // account today, so the wrong branch is the branch nobody can open.
    // ⚠ **THE PROVIDER IS SUPPLIED HERE ON PURPOSE AND IT PROVES A NARROW
    // THING.** `regional.dom.test.tsx` is where *does the running app put a
    // context there* is proved, by mounting the real frames — and it says in
    // its own words why no case there wraps a provider by hand. The question
    // HERE is different and narrower: does THIS ONE LINE go through
    // `usePortalDate` at all, or straight to the screen. With no provider the
    // formatter hands back the server's string unchanged (fail-closed), so the
    // bug and the fix render identically and the assertion cannot be written.
    draw({ ...OFFER, expires_on: "2026-09-16", expires_on_unavailable: null }, FRONT);
    expect(await screen.findByText(/This offer stands until 09\/16\/2026/)).toBeInTheDocument();
    expect(screen.queryByText(/2026-09-16/)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/have not recorded a closing date/i),
    ).not.toBeInTheDocument();
  });

  it("says nothing happens until the customer accepts", async () => {
    draw(OFFER);
    // BR-CWP-065 — nothing activates on the clerk's action alone, and the
    // screen says so before the customer asks (TC-3's fact, on the page).
    expect(await screen.findByText(/does not change anything on its own|changes nothing on its own/i))
      .toBeInTheDocument();
  });

  it("an account with no offer gets a sentence, not an empty offer", async () => {
    draw(null);
    expect(await screen.findByText(/no plan waiting for you at the moment/i)).toBeInTheDocument();
  });

  it("holds the agreement download and says when no copy was kept", async () => {
    draw({ ...OFFER, agreement: { available: false, reason: "document_not_stored" } });
    await screen.findByText("$172.20");
    // BR-CWP-045 — served, never re-rendered; and BR-CWP-056 — held with the
    // TRUE reason for this row rather than one sentence for both cases.
    expect(screen.getByText("No copy of this was kept")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /The agreement/ })).toBeDisabled();
  });

  it("CR-085 CPB-03 — a KEPT agreement is a download, not a hold", async () => {
    // ⚠ **THE HOLD IT REPLACES WAS A HOLD ON NOTHING.** *Downloads are not
    // ready yet* sat over a document this product had already frozen and could
    // already serve: the bill route has streamed the same kind of bytes, out of
    // the same store, behind the same `download` permission, since
    // `US-CWP-034`. That is hard-won law 2's mirror — a live capability behind
    // a dead control — and nothing could see it, because the control is
    // correctly rendered, correctly disabled and correctly explained.
    const { container } = draw({ ...OFFER, agreement: { available: true, reason: null } });
    await screen.findByText("$172.20");
    const link = container.querySelector("[data-plan-agreement-download]");
    expect(link, "a kept agreement still draws a held button").not.toBeNull();
    // ⚠ **THE WHOLE ADDRESS, TENANT SEGMENT INCLUDED.** A bare
    // `/api/portal/…` reaches nothing and reads as a perfectly good string to
    // `toContain`, which is the fixture fault `DEF-CWP-3925` turned on.
    expect(link?.getAttribute("href")).toBe(
      "/api/pine-hill/portal/accounts/acc-1/plans/offer/agreement",
    );
    // And the hold sentence is gone with it — a promise and a refusal about one
    // document, on one screen, is worse than either.
    expect(screen.queryByText("Downloads are not ready yet")).toBeNull();
  });

  it("D9 — the instalments and the nothing-happens-yet note are a rail (CWP-063)", async () => {
    // ⚠ **UNJUDGEABLE UNTIL NOW** because the demo customer has no offered
    // plan. ⚠ **VERDICT: correct.** The drawing puts THE INSTALMENTS and the
    // `Panel.Info` on the right and the plan, its consequences and the three
    // buttons on the left, and that is what draws.
    const { container } = draw(OFFER);
    await screen.findAllByText(/plan/i);
    const rail = container.querySelector("[data-screen='CWP-063'] [data-twocol-rail]");
    expect(rail, "CWP-063 draws no right-hand column").not.toBeNull();
    expect(rail?.textContent?.length ?? 0).toBeGreaterThan(0);
  });

  it("CR-085 CPB-21 — the offer names the person who set it up", async () => {
    // ⚠ **`OQ-CWP-1567` CLOSED 2026-09-08, option (a): a durable column on the
    // plan rather than an audit read the retention schedule deletes.** The
    // blueprint's done-when is *"The plan reads 'Agreed with Dana Whitfield on
    // Aug 14' rather than an unnamed agreement"*, so the NAME goes in the lead
    // sentence where *the office* used to be — not as a fourth grey line,
    // which would spend the section's whole description budget (B14 rule 32).
    //
    // ⚠ **A NAME AND NEVER AN ID** (B14 rule 31). `payments` resolves the
    // person because `BR-CWP-004` forbids the portal reading `identity` at
    // all, so what arrives here is already a word.
    draw({ ...OFFER, offered_by: "Sarah Kesler", offered_by_unavailable: null });
    expect(await screen.findByText(/Sarah Kesler set this up on 2026-09-02/)).toBeInTheDocument();
    // And the absence line is NOT drawn beside a name that is right there.
    expect(screen.queryByText(/cannot show you who set this up/i)).toBeNull();
  });

  it("CR-085 CPB-21 — a plan nobody recorded still says so, and names no office", async () => {
    // ⚠ **THE NULL IS A REAL ANSWER.** Every plan written before the column
    // existed has nobody to name, and so has one a job wrote. No backfill was
    // done on purpose: the trail is pruned, so a backfill would be right for
    // recent plans and fabricated for the rest.
    const { container } = draw({ ...OFFER, offered_by: null, offered_by_unavailable: "not_recorded" });
    await screen.findByText("$172.20");
    expect(container.querySelector("[data-plan-no-clerk]")).not.toBeNull();
    expect(screen.getByText(/cannot show you who set this up/i)).toBeInTheDocument();
    // ⚠ **AND THE LEAD MUST NOT INVENT A PERSON.** *The office* is the utility,
    // not somebody; a screen that printed a name here would be making one up.
    expect(screen.queryByText(/Sarah Kesler/)).toBeNull();
  });

  it("CR-085 — no offer waiting still names the way to ask for one", async () => {
    // ⚠ **BAD NEWS CARRIES THE WAY OUT WITH IT** (group G's standing rule).
    // The sentence offered a telephone; `CWP-042` is one route along and was
    // not named. The address is asserted WHOLE — a bare `/ask-for-a-plan`
    // resolves to `//portal/ask-for-a-plan`, another host, and `toContain`
    // accepts it.
    const { container } = draw(null);
    await screen.findByText(/There is no plan waiting for you/);
    expect(
      container
        .querySelector('[data-portal-state="empty"] [data-way-out="ask-for-a-plan"]')
        ?.getAttribute("href"),
    ).toBe("/pine-hill/portal/ask-for-a-plan");
  });

  it("DEF-CWP-4183 — the title is printed ONCE, not twice one line apart", async () => {
    // *A plan we have offered you* as the page `<h1>` and again as the card's
    // section title — B14 rule 32's description budget spent saying the
    // screen's own name again.
    const { container } = draw(OFFER);
    await screen.findByText("$172.20");
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(screen.getAllByText("A plan we have offered you")).toHaveLength(1);
  });

  it("DEF-CWP-4720 — the agreement download is the kit's control, not five hand-rolled classes", async () => {
    // ⚠ **`hover:bg-neutral-50` IS A CLASS `tokens.css` DOES NOT DECLARE** —
    // the lightest neutral in this product is `neutral-100` — so the hover
    // state of the only download on the screen did nothing at all. `tsc`,
    // eslint and every `toContain` assertion passed on it because the class IS
    // in the DOM (`DEF-974`). `CWP-043` already serves the same document
    // through `ButtonAnchor`; one shape for one job (B14 rule 36).
    const { container } = draw(OFFER);
    await screen.findByText("$172.20");
    const link = container.querySelector("[data-plan-agreement-download]");
    expect(link).not.toBeNull();
    expect(link?.className ?? "").not.toContain("neutral-50");
    // The kit's own anchor marks itself; a hand-rolled `<a>` does not.
    expect(link?.getAttribute("data-variant")).toBe("secondary");
  });


  it("DEF-CWP-4183 — the title is printed ONCE, not twice one line apart", async () => {
    const { container } = draw(OFFER);
    await screen.findByText("$172.20");
    expect(container.querySelectorAll("h1")).toHaveLength(1);
    expect(screen.getAllByText("A plan we have offered you")).toHaveLength(1);
  });

  it("DEF-CWP-4720 — the agreement download is the kit's control, not five hand-rolled classes", async () => {
    // ⚠ **`hover:bg-neutral-50` IS A CLASS `tokens.css` DOES NOT DECLARE** —
    // the lightest neutral in this product is `neutral-100` — so the hover
    // state of the only download on the screen did nothing at all. `tsc`,
    // eslint and every `toContain` assertion passed on it because the class IS
    // in the DOM (`DEF-974`). `CWP-043` already serves the same document
    // through `ButtonAnchor`; one shape for one job (B14 rule 36).
    const { container } = draw(OFFER);
    await screen.findByText("$172.20");
    const link = container.querySelector("[data-plan-agreement-download]");
    expect(link).not.toBeNull();
    expect(link?.className ?? "").not.toContain("neutral-50");
    // The kit's own anchor marks itself; a hand-rolled `<a>` does not.
    expect(link?.getAttribute("data-variant")).toBe("secondary");
  });

});
