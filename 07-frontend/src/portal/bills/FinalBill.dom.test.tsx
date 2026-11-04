// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-037 (EP-CWP-07) · Screen: CWP-032
// Rules:    BR-CWP-048 (a negative final balance is a REFUND, never a carried
//           credit) · BR-CWP-049 (the deposit and its interest settle here) ·
//           BR-CWP-093 · B14 rule 31 · rule 33 · rule 35
// Cases:    TC-1/TC-2 `$63.40 − $150.00 − $3.20 = −$89.80`, *we owe you
//           $89.80* · TC-3 service EXCEEDS the deposit, so it reads as owed ·
//           TC-4 a refund and not a credit · TC-6 no deposit means no deposit
//           lines · TC-8 the closing reading · TC-8 HOLD EXPIRY the query
//           opens CWP-055 (DEF-CWP-3962) · TC-8b a bill with no number stays
//           held · TC-9 the query route closes
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { resolvePortalScreen } from "../routing/screenIds";

import type { PortalFinalBillView } from "../api/portalClient";

let readFinal: () => Promise<PortalFinalBillView> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getFinalBill: () => readFinal() };
});

const { FinalBillView } = await import("./FinalBill");

/** `US-CWP-037` §4's own figures, exactly as the server composes them. */
const WE_OWE: PortalFinalBillView = {
  bill: {
    number: "BL-2609-0163",
    issued_on: "2026-09-18",
    due_on: "2026-10-02",
    total: "63.4000",
    currency: "USD",
    period_start: "2026-09-01",
    period_end: "2026-09-17",
    service_charges: "63.4000",
    charges: "63.4000",
    deposit: {
      held: "150.0000",
      interest: "3.2000",
      total: "153.2000",
      taken_on: "2021-03-04",
      currency: "USD",
    },
    remainder: "-89.8000",
    path: "refund",
    path_is_automatic: true,
    settled: false,
    settlement_unavailable: null,
  },
  closing_reading: {
    taken_on: "2026-09-17",
    meter_serial: "W-88213",
    reading_display: "154,310",
    used_since_display: "1,270 gal",
    how: "reader",
  },
  query_reading_open: true,
  query_reading_closed_reason: null,
};

function draw(view: PortalFinalBillView) {
  readFinal = async () => view;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/final-bill"]}>
      <Routes>
        <Route
          path="/:tenant/portal/final-bill"
          element={<FinalBillView accountId="acc-1" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("CWP-032 · your final bill (US-CWP-037)", () => {
  it("TC-1/TC-2 · $63.40 − $150.00 − $3.20 = −$89.80, read as WE OWE YOU", async () => {
    const { container } = draw(WE_OWE);
    expect(await screen.findByText("$63.40")).toBeInTheDocument();
    // ⚠ THE DEPOSIT AND ITS INTEREST COME OFF, so they are drawn negative —
    // the three lines add to the total below them and a customer can check it.
    expect(screen.getByText("-$150.00")).toBeInTheDocument();
    expect(screen.getByText("-$3.20")).toBeInTheDocument();
    const total = container.querySelector('[data-total="settlement"]');
    expect(total?.textContent).toContain("We owe you");
    // ⚠ THE SIGN THE SERVER SENT. No `Math.abs` anywhere on this screen.
    expect(total?.textContent).toContain("-$89.80");
  });

  /**
   * ⚠ **`DEF-CWP-4190` — THE HEADING WAS MISSING ON THIS BRANCH AND ONLY ON
   * THIS BRANCH, AND NO CASE IN THIS FILE ASKED.**
   *
   * `{head}` was rendered in the could-not-read, still-reading and
   * no-final-bill returns and left out of the success return, so `CWP-032`
   * drew *MOVING OUT / Your final bill* on every state where there is nothing
   * to read and nothing at all the moment there was a bill. A browser found it
   * (`document.querySelectorAll("h1").length === 0`); every check in this repo
   * passed over it, because `{head}` is a live const used three times and
   * `tsc`, eslint and `G13` have no question to ask about the fourth.
   *
   * **So the case is written on the branch WITH DATA, deliberately.** The three
   * empty states are what a fixture reaches by accident — they draw with no
   * payload at all — and asserting the heading on one of those would have
   * passed throughout the defect.
   */
  it("DEF-CWP-4190 · the page head is on the branch that HAS a final bill", async () => {
    const { container } = draw(WE_OWE);
    expect(await screen.findByText("$63.40")).toBeInTheDocument();
    const heading = container.querySelector("h1");
    expect(heading).not.toBeNull();
    expect(heading?.textContent).toBe("Your final bill");
    // The kicker is the SITUATION, not the document (drawing P18).
    expect(container.querySelector(".page-header")?.textContent).toContain("MOVING OUT");
  });

  it("TC-5 · the deposit is quoted with the date CWP-065 shows", async () => {
    draw(WE_OWE);
    // Both screens read `accounts.deposit_on_file` and one implementation of
    // the interest, so the sentence is the same by construction.
    expect(
      await screen.findByText("Deposit held since 2021-03-04"),
    ).toBeInTheDocument();
  });

  it("TC-4 · it is a REFUND and the screen says it is not a credit", async () => {
    const { container } = draw(WE_OWE);
    await screen.findByText("$63.40");
    expect(container.querySelector('[data-consequence-code="refund"]')).not.toBeNull();
    expect(
      container.querySelector('[data-consequence-code="not_a_credit"]')?.textContent,
    ).toBe(
      "This is money sent back, not a credit — there is no next bill to put it on.",
    );
  });

  it("TC-3 · negative · service EXCEEDING the deposit reads as an amount OWED", async () => {
    const { container } = draw({
      ...WE_OWE,
      bill: {
        ...WE_OWE.bill!,
        service_charges: "289.1000",
        charges: "289.1000",
        remainder: "135.9000",
        path: null,
        path_is_automatic: false,
      },
    });
    // ⚠ **TWICE, AND THE SECOND ONE IS THE HEADLINE** (`CR-085` task (c),
    // wireframe s24: *"the refund is the headline … because that is what they
    // came for"*). It is the SAME string as the total below it, rendered out of
    // one figure, so the two cannot disagree.
    expect(await screen.findAllByText("$135.90")).toHaveLength(2);
    expect(container.querySelector('[data-kpi-value="settlement-headline"]')?.textContent).toBe(
      "$135.90",
    );
    expect(container.querySelector('[data-total="settlement"]')?.textContent).toContain(
      "You owe us",
    );
    // ⚠ NOT *we owe you* with a minus in front of it, which is the shape TC-3
    // exists to forbid.
    expect(container.textContent).not.toContain("We owe you");
  });

  it("TC-6 · negative · an account with NO deposit has no deposit lines at all", async () => {
    const { container } = draw({
      ...WE_OWE,
      bill: { ...WE_OWE.bill!, deposit: null, remainder: "63.4000", path: null },
    });
    // ⚠ THREE `$63.40`s HERE AND THAT IS CORRECT: with no deposit to apply, the
    // service line, the total and the headline ARE the same figure.
    // `findAllByText` says so rather than the test pretending only one exists.
    // (It was two until `CR-085` task (c) put the figure at the top as well —
    // wireframe s24 draws the money first, because that is what a leaving
    // customer opened the screen for.)
    expect(await screen.findAllByText("$63.40")).toHaveLength(3);
    // ⚠ ABSENT, NOT `$0.00` — which would read as *we took nothing from you*.
    expect(container.querySelector('[data-kv="held"]')).toBeNull();
    expect(container.querySelector('[data-kv="interest"]')).toBeNull();
    expect(container.textContent).not.toContain("$0.00");
  });

  it("TC-8 · the closing reading, with how it was taken", async () => {
    const { container } = draw(WE_OWE);
    expect(await screen.findByText("154,310")).toBeInTheDocument();
    expect(screen.getByText("1,270 gal")).toBeInTheDocument();
    expect(screen.getByText("2026-09-17")).toBeInTheDocument();
    // The METHOD is a code and the catalogue writes the words (B14 rule 35) —
    // the same vocabulary `CWP-034` uses.
    expect(container.querySelector("[data-closing-how]")?.textContent).toBe(
      "Read by a meter reader",
    );
  });

  /**
   * ⚠ **THIS CASE USED TO PIN THE HOLD AND NOW EXPIRES IT** (`DEF-CWP-3962`).
   * It read *"It is HELD with its reason rather than live — the query itself is
   * `US-CWP-065`'s screen and this wave does not build it"*, and it went on
   * passing for every day after that screen landed. A hold with a test that
   * pins it and no test that expires it is a promise nobody is keeping.
   *
   * **Asserted by ADDRESS and by the SCREEN ID it opens**, resolved through the
   * front end's own register — so the day this door closes again, or points
   * somewhere else, the suite says which screen stopped being reachable.
   */
  it("TC-8 · HOLD EXPIRY: the query opens CWP-055 while the account is unsettled", async () => {
    const { container } = draw(WE_OWE);
    await screen.findByText("154,310");
    const open = container.querySelector('[data-query-reading="open"]');
    expect(open).not.toBeNull();
    const link = open?.querySelector("a");
    expect(link?.getAttribute("href")).toBe(
      "/pine-hill/portal/bills/BL-2609-0163/dispute",
    );
    expect(resolvePortalScreen("/bills/BL-2609-0163/dispute")?.id).toBe("CWP-055");
    expect(open?.querySelector("button[disabled]")).toBeNull();
    expect(screen.queryByText("Call us to query this")).toBeNull();
  });

  /**
   * The reason that is LEFT, and why it cannot rot: it is about a missing bill
   * NUMBER, not a missing screen. `/bills//dispute` opens nothing, so *ring us*
   * is the true answer — and the data answers it every time the screen draws.
   */
  it("TC-8b · a final bill with no number stays held, and ring us is then true", async () => {
    const { container } = draw({ ...WE_OWE, bill: { ...WE_OWE.bill!, number: null } });
    await screen.findByText("154,310");
    const open = container.querySelector('[data-query-reading="open"]');
    expect(open?.querySelector("a")).toBeNull();
    expect(open?.querySelector("button[disabled]")).not.toBeNull();
    expect(screen.getByText("Call us to query this")).toBeInTheDocument();
  });

  it("TC-9 · negative · once settled the route is gone AND the screen says why", async () => {
    const { container } = draw({
      ...WE_OWE,
      bill: { ...WE_OWE.bill!, settled: true },
      query_reading_open: false,
      query_reading_closed_reason: "settled_correction_is_slower",
    });
    await screen.findByText("154,310");
    expect(container.querySelector('[data-query-reading="closed"]')).not.toBeNull();
    expect(container.querySelector('[data-query-reading="open"]')).toBeNull();
    expect(
      screen.getByText(
        "This account has settled, so a correction now takes longer. Please call us.",
      ),
    ).toBeInTheDocument();
  });

  it("an account that is not leaving gets a sentence, not an empty settlement", async () => {
    const { container } = draw({
      bill: null,
      closing_reading: null,
      query_reading_open: false,
      query_reading_closed_reason: null,
    });
    expect(
      await screen.findByText("When your service ends, your last bill will be here."),
    ).toBeInTheDocument();
    expect(container.querySelector('[data-total="settlement"]')).toBeNull();
  });

  it("a settlement the engine refuses says so instead of showing figures", async () => {
    const { container } = draw({
      ...WE_OWE,
      bill: {
        ...WE_OWE.bill!,
        deposit: null,
        remainder: undefined,
        path: null,
        settlement_unavailable: "deposit_interest_not_accrued",
      },
    });
    await screen.findByText("We cannot settle this yet. The office will be in touch.");
    // ⚠ NO TOTAL AT ALL — a principal-only figure here is exactly what the
    // engine refuses to produce, and a screen must not invent one.
    expect(container.querySelector('[data-total="settlement"]')).toBeNull();
  });

  it("D9 — the two panels are EQUAL width, which is what T4 means (CWP-032)", async () => {
    // ⚠ **UNJUDGEABLE UNTIL 2026-09-05** because the demo customer is not
    // moving out. The fixture here has a final bill, so the shape can be read
    // off the DOM.
    //
    // ⚠ **`DEF-CWP-4006` IS FIXED HERE AND THE EARLIER VERDICT IS REVERSED.**
    // This case used to assert `data-twocol-main` / `data-twocol-rail` and
    // record the 62/35 split as a deliberate divergence. What changed is
    // evidence, not taste: `08-screen-layouts.md` draws this screen as
    // `Panel` **SETTLING UP** · `Panel` **CLOSING READING** — two peer panels,
    // with none of the *left `Card` · right `Panel`* main-and-rail language
    // the other T4 screens carry — and `TwoEqual` exists in the kit for
    // exactly this template. A rail slot for a peer panel was the wrong
    // container, not merely the wrong width.
    //
    // The selectors are the point: `data-twocol-rail` must be ABSENT, or the
    // screen has quietly moved back.
    const { container } = draw(WE_OWE);
    await screen.findByText(/Settling up|SETTLING UP/i);
    const left = container.querySelector("[data-screen='CWP-032'] [data-two-equal-left]");
    const right = container.querySelector("[data-screen='CWP-032'] [data-two-equal-right]");
    expect(left?.textContent?.length ?? 0).toBeGreaterThan(0);
    expect(right?.textContent?.length ?? 0).toBeGreaterThan(0);
    expect(container.querySelector("[data-screen='CWP-032'] [data-twocol-rail]")).toBeNull();
  });
  /**
   * ⚠ **THE DOCUMENT DOOR, WHICH THE SCREEN DID NOT HAVE — `CR-085` task (c).**
   * Wireframe s24 ends on *"↓ Download the final bill"*. A final bill carries a
   * number like any other bill, `/bills/{number}/document` is the route two
   * other portal screens already open, and this one offered no way to it at
   * all. Watched fail on the real screen before it was written green.
   */
  it("offers the printed final bill, by the address the other bill screens use", async () => {
    const { container } = draw(WE_OWE);
    const link = await waitFor(() => {
      const found = container.querySelector('a[href*="/document"]');
      expect(found).not.toBeNull();
      return found as HTMLAnchorElement;
    });
    // ⚠ **BY ADDRESS, AND UNDER THE REAL PATH PATTERN** — hard-won law 2's last
    // clause: a component mounted outside `/:tenant/portal/…` builds
    // `//portal/…`, a protocol-relative URL to another host, which reads as a
    // perfectly good string to `toContain`.
    expect(link.getAttribute("href")).toBe("/pine-hill/portal/bills/BL-2609-0163/document");
  });

  it("a final bill with NO number offers no document link rather than a dead one", async () => {
    const { container } = draw({
      ...WE_OWE,
      bill: { ...WE_OWE.bill!, number: null },
    });
    await screen.findByText("$63.40");
    // `/bills//document` opens nothing; hard-won law 2 — absent beats dead.
    expect(container.querySelector('a[href*="/document"]')).toBeNull();
  });
});
