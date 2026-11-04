// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-059 (EP-CWP-10) · Screen: CWP-064
// Rules:    BR-CWP-090 (three lifetimes, three sentences; never imply a hold is
//           permanent) · BR-CWP-091 (a hold stops a disconnection, not the
//           debt) · BR-CWP-089 · BR-CWP-093
// Cases:    a certificate names its date AND says it is not permanent · ⚠ the
//           plan hold carries NO date and says what ends it · the moratorium
//           has no control · the warning is on the screen · a lifted hold is
//           still listed · no protection at all draws one sentence
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalProtections } from "../api/portalClient";

let readProtections: () => Promise<PortalProtections> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getProtections: () => readProtections() };
});

const { ProtectionsView } = await import("./Protections");

/** `US-CWP-059` §4 — a certificate to 30 Nov, a plan hold with NO end date,
 *  and the regulator's winter window. */
const HELD: PortalProtections = {
  as_of: "2026-09-02",
  any: true,
  protections: [
    {
      kind: "medical_certificate", lifetime: "expires_on_a_date", in_force: true,
      since: "2026-08-14", ends_on: "2026-11-30", lifted_on: null,
    },
    {
      kind: "payment_plan", lifetime: "derived_from_the_plan", in_force: true,
      since: "2026-08-20", ends_on: null, lifted_on: null,
    },
    {
      kind: "weather_moratorium", lifetime: "regulator_date_window", in_force: false,
      since: "2026-12-01", ends_on: "2027-03-01", lifted_on: null,
    },
  ],
  hold_stops_disconnection_not_debt: true,
  problems: [],
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/portal` PATTERN** (CLAUDE.md hard-won
 * law 2). Bare inside a `MemoryRouter` with no matching `<Route>`,
 * `useParams().tenant` is `undefined` and every address this screen builds
 * comes out `//portal/…` — a protocol-relative URL to ANOTHER HOST that reads
 * as a perfectly good string to `toContain`. A door assertion cannot be
 * written truthfully without this.
 */
function draw(body: PortalProtections) {
  readProtections = async () => body;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/protections"]}>
      <Routes>
        <Route path="/:tenant/portal/protections" element={<ProtectionsView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-064 · what is protecting your supply (US-CWP-059)", () => {
  it("TC-1 — the certificate names its end date AND says it is not permanent", async () => {
    const { container } = draw(HELD);
    await screen.findByText("What a hold does not do");
    const card = container.querySelector("[data-protection='medical_certificate']");
    expect(card?.querySelector("[data-ends='medical_certificate']")?.textContent).toBe("2026-11-30");
    const body = container.querySelector(
      "[data-protection-body='medical_certificate']",
    )?.textContent;
    expect(body).toContain("This is not permanent");
    expect(body).toContain("2026-11-30");
    expect(body).toContain("Send a new certificate before then");
  });

  it("TC-2 · negative — ⚠ THE PLAN HOLD CARRIES NO DATE AND NONE IS INVENTED", async () => {
    // ⚠ **THE CARD THAT SAVES MONEY.** A customer who believes a plan hold is
    // permanent stops paying and is cut the week it lapses. An em-dash in the
    // date cell would read as *forever* just as loudly as a wrong date.
    const { container } = draw(HELD);
    await screen.findByText("What a hold does not do");
    const card = container.querySelector("[data-protection='payment_plan']");
    expect(card?.querySelector("[data-ends='no-date']")?.textContent).toBe(
      "no date — see below",
    );
    const body = container.querySelector("[data-protection-body='payment_plan']")?.textContent;
    expect(body).toContain("has no end date");
    expect(body).toContain("lifts the day an installment is missed");
    // ⚠ No date string anywhere in the plan card's own date cell.
    expect(card?.querySelector("[data-ends='payment_plan']")).toBeNull();
  });

  it("TC-3 — the moratorium is read from the record and carries NO control", async () => {
    const { container } = draw(HELD);
    await screen.findByText("What a hold does not do");
    const card = container.querySelector("[data-protection='weather_moratorium']");
    expect(card?.textContent).toContain("2026-12-01");
    expect(card?.querySelector("[data-ends='weather_moratorium']")?.textContent).toBe("2027-03-01");
    expect(card?.querySelector("button")).toBeNull();
    expect(card?.querySelector("a")).toBeNull();
  });

  it("TC-9 · negative — change the record and the sentence changes with it", async () => {
    // ⚠ `P42` states the window in prose and this story fixes that.
    const { container } = draw({
      ...HELD,
      protections: [
        {
          kind: "weather_moratorium", lifetime: "regulator_date_window", in_force: false,
          since: "2026-11-15", ends_on: "2027-04-15", lifted_on: null,
        },
      ],
    });
    await screen.findByText("What a hold does not do");
    expect(container.textContent).toContain("2026-11-15");
    expect(container.textContent).toContain("2027-04-15");
    expect(container.textContent).not.toContain("2026-12-01");
  });

  it("TC-5 — the warning is ON THE SCREEN, not only in help", async () => {
    const { container } = draw(HELD);
    await screen.findByText("What a hold does not do");
    expect(container.querySelector("[data-hold-warning]")?.textContent).toBe(
      "A hold stops a disconnection. It does not stop the debt.",
    );
  });

  it("TC-7 · negative — a lifted protection is shown as lifted, not removed", async () => {
    const { container } = draw({
      ...HELD,
      protections: [
        {
          kind: "medical_certificate", lifetime: "expires_on_a_date", in_force: false,
          since: "2025-01-01", ends_on: "2025-06-30", lifted_on: "2025-05-01",
        },
      ],
    });
    await screen.findByText("Lifted");
    expect(container.querySelector("[data-protection='medical_certificate']")).toBeTruthy();
    expect(container.textContent).toContain("lifted on 2025-05-01");
  });

  it("TC-6 · negative — no protection at all draws ONE SENTENCE, not three empty cards", async () => {
    const { container } = draw({ ...HELD, any: false, protections: [] });
    await screen.findByText("Nothing is holding your supply at the moment.");
    expect(container.querySelectorAll("[data-protection]")).toHaveLength(0);
  });

  it("B14 rule 31 — no database id reaches the screen", async () => {
    const { container } = draw(HELD);
    await screen.findByText("What a hold does not do");
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/);
  });

  it("CR-085 — nothing holding the supply still says what can still be done", async () => {
    // ⚠ The drawing's *not protected* state is *"neutral, not alarming: says
    // which could apply and links each application"*. This branch said only
    // that nothing was holding anything, which a frightened customer reads as
    // a verdict.
    // ⚠ **AND NO PROTECTION IS NAMED HERE.** Which ones exist is tenant
    // configuration; `CWP-056` serves that list. A hard-coded winter or
    // medical row would be one state's rules in every utility's product.
    const { container } = draw({
      as_of: "2026-09-08",
      any: false,
      protections: [],
      hold_stops_disconnection_not_debt: true,
      problems: [],
    });
    await screen.findByText("Nothing is holding your supply at the moment.");
    expect(container.querySelector("[data-protections-what-next]")?.textContent).toContain(
      "there are still things we can do",
    );
    // ⚠ **THE DOOR IS NOW A `waysOut` ON THE SHARED STATE CARD** (`CR-085`
    // step 2, R-10) — same destination, asserted the same way: WHOLE, because
    // a bare `/help-paying` resolves to `//portal/help-paying`, another host,
    // and `toContain` accepts it (`BR-CWP-007`).
    expect(
      container.querySelector('[data-way-out="help-paying"]')?.getAttribute("href"),
    ).toBe("/pine-hill/portal/help-paying");
    // R-10 is *"next to the message"* — the control is INSIDE the card that
    // carries the sentence, not somewhere else on the page.
    expect(
      container.querySelector('[data-portal-state="empty"] [data-way-out="help-paying"]'),
    ).not.toBeNull();
    for (const word of ["Winter", "winter", "military", "moratorium"]) {
      expect(container.textContent).not.toContain(word);
    }
  });


  // ═══════════════════════════════════════════════════════════════════════
  // `CR-085` step 2, lane 7 — `DEF-CWP-4145` and the card headings.
  // ═══════════════════════════════════════════════════════════════════════

  it("DEF-CWP-4145 — every card a customer can act on carries its control", async () => {
    // ⚠ **HARD-WON LAW 2 IN ITS PUREST FORM.** `ProtectionCard` has accepted an
    // `action` since the day it was written and NOTHING has ever passed one:
    // the component rendered, `tsc` was happy, every assertion passed, and the
    // feature did not exist. The drawing marks all three cards.
    const { container } = draw(HELD);
    await screen.findByText("Payment plan");
    // The plan hold opens the plan it is derived FROM — which is where *when
    // does this lift* is actually answered.
    expect(
      container.querySelector("[data-protection='payment_plan'] a")?.getAttribute("href"),
    ).toBe("/pine-hill/portal/plan");
    // The certificate opens the route that takes one, carrying `CWP-056`'s own
    // five-word label.
    expect(
      container.querySelector("[data-protection='medical_certificate'] a")?.getAttribute("href"),
    ).toBe("/pine-hill/portal/help-paying");
  });

  it("DEF-CWP-4145 — the moratorium gets NO control, and that is the decision", async () => {
    // The regulator sets the window; nobody applies for it and nobody can be
    // given it. A control there would invite somebody to ask for a thing they
    // already have and could not be refused.
    const { container } = draw(HELD);
    await screen.findByText("Winter moratorium");
    expect(container.querySelector("[data-protection='weather_moratorium'] a")).toBeNull();
  });

  it("the card TITLES are headings, not the in-sentence noun", async () => {
    // ⚠ `portal.protections.kind.*` is written to be inserted into *"A {{kind}}
    // is holding your supply"* on `CWP-057`, so it is lower-case BY DESIGN —
    // and reusing it as a card title printed *doctor's certificate* as a
    // heading on three cards. Two uses, two spellings, in eleven languages.
    const { container } = draw(HELD);
    await screen.findByText("Doctor's certificate");
    expect(container.textContent).not.toContain("doctor's certificate");
    expect(container.textContent).not.toContain("winter moratorium");
  });

  it("R-10 — a failed read still names the help route and really re-reads", async () => {
    let calls = 0;
    readProtections = async () => {
      calls += 1;
      if (calls === 1) throw new Error("down");
      return HELD;
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/protections"]}>
        <Routes>
          <Route
            path="/:tenant/portal/protections"
            element={<ProtectionsView accountId="acc-1" />}
          />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read this right now. Try again in a moment.");
    expect(
      container
        .querySelector('[data-portal-state="failed"] [data-way-out="help-paying"]')
        ?.getAttribute("href"),
    ).toBe("/pine-hill/portal/help-paying");
    fireEvent.click(container.querySelector('[data-way-out="try-again"]') as HTMLElement);
    expect(await screen.findByText("Payment plan")).toBeInTheDocument();
    expect(calls).toBe(2);
  });

});
