// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-041 (EP-CWP-08) · Screen: CWP-034
// Rules:    BR-CWP-071 (the method as prominent as the number) · BR-CWP-072
//           (the correction's reason AND its size) · BR-CWP-069 (never charged
//           twice) · CLAUDE.md hard rule 3 (the unit on every quantity) ·
//           B14 rule 31 (no database id on screen)
// Defects:  DEF-CWP-3990 (every meter in one list, nothing saying which) ·
//           DEF-CWP-3925 (a hold with no test that fires when it expires)
// Cases:    the method in words · the corrected row and both figures · the
//           self-read row · the EMPTY bill cell · the empty state · the unit ·
//           the METER column · the held Send a reading AND the test that goes
//           red the day CWP-035 lands · the chip as the exception
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

// ⚠ **SUPPLIED BY HAND FOR THE ONE CASE THAT NEEDS A TENANT FORMAT**
// (`DEF-CWP-4172`). `usePortalDate` returns the server's string unchanged when
// no format is in context — the honest answer for a utility that has stated
// none — so a test without this provider cannot tell a formatted date from a
// raw one, which is how the defect survived every case in this file.
import { TenantRegionalProvider } from "@/components/TenantRegional";

import type {
  PortalListRequest,
  PortalNextRead,
  PortalReading,
  PortalReadings,
} from "../api/portalClient";

let readReadings: () => Promise<PortalReadings> = async () => {
  throw new Error("no behaviour set");
};
/**
 * ⚠ **EVERY REQUEST THIS SCREEN MAKES, RECORDED — `DEF-CWP-5747`.** The list
 * takes its page, its search and its sort from the SERVER now, and the ONLY
 * assertion that can tell that apart from a browser holding every row is
 * *what went out on the wire*. A case counting rendered rows passes either way
 * and would have been green through the whole life of the defect.
 */
let asked: PortalListRequest[] = [];
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getAccountReadings: (_accountId: string, request: PortalListRequest = {}) => {
      asked.push(request);
      return readReadings();
    },
  };
});

/**
 * One payload, with the three whole-set facts the server now serves.
 *
 * ⚠ **`services` IS NOT DERIVED FROM `readings` HERE, AND THAT IS THE POINT.**
 * The screen's meter tabs used to be folded out of the rows; over a page that
 * would read *the services in the newest fifty readings*, so the server answers
 * the set question separately. A fixture that folded them from the rows would
 * assert the bug rather than the fix.
 */
function answer(
  readings: PortalReading[],
  over: Partial<PortalReadings> = {},
): PortalReadings {
  return {
    readings,
    services: readings.length === 0 ? [] : [{ code: "water", name: "Water", meters: ["88-40219"] }],
    next_read: null,
    count: readings.length,
    page: 1,
    per: 50,
    ...over,
  };
}

const { ReadingsView, SEND_A_READING_PATH, SEND_A_READING_SCREEN } = await import("./Readings");

/** `CPB-09` — the same mount, with a next-read window on the payload. */
function drawWithNextRead(nextRead: PortalNextRead | null) {
  readReadings = async () => answer([BASE], { next_read: nextRead });
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
      <Routes>
        <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}
const { PORTAL_ROUTES } = await import("../routing/portalRoutes");
const { PORTAL_SCREENS } = await import("../routing/screenIds");

const BASE: PortalReading = {
  taken_on: "2026-08-31",
  meter_serial: "88-40219",
  meter_no: "M-88402",
  meter_service: "water",
  meter_service_name: "Water",
  reading: "153040.000000",
  reading_display: "153040",
  used_since: "4820.000000",
  used_since_display: "4820 gal",
  unit: "gal",
  how: "reader",
  read_method: "walk_by",
  read_method_origin: "recorded",
  estimated: false,
  correction: null,
  channel: "total",
  on_bill: "BL-2608-0141",
};

/** `US-CWP-041` §4's June row — estimated `144,600`, corrected to `144,130`. */
const CORRECTED: PortalReading = {
  ...BASE,
  taken_on: "2026-06-30",
  reading: "144130.000000",
  reading_display: "144130",
  used_since: "3760.000000",
  used_since_display: "3760 gal",
  how: "estimated_corrected",
  read_method: null,
  read_method_origin: "not_stated",
  on_bill: "BL-2606-0147",
  correction: {
    estimated_reading: "144600.000000",
    estimated_reading_display: "144600",
    estimated_used: "4230 gal",
    corrected_to: "144130.000000",
    corrected_to_display: "144130",
    corrected_on: "2026-07-03",
    reason: "Meter read on 3 July",
  },
};

const SELF_READ: PortalReading = {
  ...BASE,
  taken_on: "2026-09-02",
  reading_display: "153300",
  used_since_display: "260 gal",
  how: "self_read",
  read_method: "self_read",
  // ⚠ **NO ISSUED BILL COVERS IT** — the cell is EMPTY, not a guess (TC-4).
  on_bill: null,
};

/**
 * ⚠ **MOUNTED UNDER THE REAL `/:tenant/portal` PATTERN.** A bare
 * `MemoryRouter` with no matching route leaves `useParams().tenant` UNDEFINED,
 * so every address this screen builds comes out `//portal/…` — a
 * protocol-relative URL to another host that `toContain` happily accepts. The
 * `<Routes>` below is what makes the href assertions below mean anything.
 */
function draw(readings: PortalReading[], services?: PortalReadings["services"]) {
  // ⚠ **`services` IS SUPPLIED, NEVER FOLDED OUT OF `readings`** — see
  // `answer` above. A fixture that derived the tabs from the rows would assert
  // the behaviour `DEF-CWP-5747` removed, and would go on passing over a page.
  readReadings = async () => answer(readings, services === undefined ? {} : { services });
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
      <Routes>
        <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
      </Routes>
    </MemoryRouter>,
  );
}

/**
 * ⚠ **EVERY ROW IS DRAWN TWICE NOW — ONCE AS A TABLE ROW AND ONCE AS A PHONE
 * CARD — AND ONLY ONE OF THEM IS EVER VISIBLE** (`CR-085`; the switch is CSS,
 * `md:hidden` / `max-md:hidden`, and jsdom applies no CSS). So a bare
 * `findByText` now finds two elements and throws. `findAllByText` is the
 * honest wait: it says *this text is on the screen* without claiming which
 * half drew it, and every assertion below reads a `data-` attribute that
 * belongs to exactly one half (the card's are prefixed `card-`, which is
 * `bills/Bills.tsx`'s own convention for the same reason).
 */

afterEach(() => {
  cleanup();
  asked = [];
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-5747` — THE PAGE, THE SEARCH AND THE SORT COME FROM THE SERVER
//
// ⚠ **THESE ASSERT THE REQUEST, NEVER THE ROWS.** The screen used to hold
// every reading an account had ever taken and search, sort and slice them in
// the browser; the rows it draws look identical either way. What changed is
// what goes out on the wire, and that is the only thing a case can look at
// which cannot be green on both sides of the fix.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CWP-5747 · the readings list asks the server for its page", () => {
  afterEach(() => {
    cleanup();
    asked = [];
  });

  it("asks for page 1 of fifty on the first render", async () => {
    draw([BASE]);
    expect((await screen.findAllByText("153,040")).length).toBeGreaterThan(0);
    expect(asked).toHaveLength(1);
    expect(asked[0].page).toBe(1);
    expect(asked[0].per).toBe(50);
  });

  it("sends what was typed as `q` and goes back to page 1", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      draw([BASE]);
      const box = await screen.findByPlaceholderText(/search/i);
      fireEvent.change(box, { target: { value: "88-402" } });
      // IS-3's debounce: one settled burst is one request, and the box shows
      // the keystroke immediately while the wire waits.
      expect((box as HTMLInputElement).value).toBe("88-402");
      await vi.advanceTimersByTimeAsync(400);
      const last = asked[asked.length - 1];
      expect(last.q).toBe("88-402");
      expect(last.page).toBe(1);
    } finally {
      vi.useRealTimers();
    }
  });

  it("sends the column and the direction when a heading is pressed", async () => {
    draw([BASE]);
    const heading = await screen.findByRole("button", { name: /taken|date/i });
    fireEvent.click(heading);
    const last = asked[asked.length - 1];
    expect(last.sort).toBe("taken");
    expect(last.dir).toBe("asc");
  });

  it("turning a page is a REQUEST and not a slice", async () => {
    readReadings = async () => answer([BASE], { count: 120 });
    render(
      <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
        <Routes>
          <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    expect((await screen.findAllByText("153,040")).length).toBeGreaterThan(0);
    const before = asked.length;
    // The shared footer's next arrow, on both the table's copy and the phone
    // stack's — pressing either must ask the server.
    const next = screen.getAllByRole("button", { name: /next/i })[0];
    fireEvent.click(next);
    expect(asked.length).toBeGreaterThan(before);
    expect(asked[asked.length - 1].page).toBe(2);
  });

  it("the footer counts the SERVER's total and not the rows on screen", async () => {
    readReadings = async () => answer([BASE], { count: 120 });
    render(
      <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
        <Routes>
          <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    // ⚠ `DEF-NOT-5746`'s exact fault one screen over: a footer that counted
    // its own page read *1–50 of 50* over four thousand rows and its next
    // arrow reached nothing.
    expect(await screen.findAllByText(/of 120/)).not.toHaveLength(0);
  });

  it("the meter tabs come from the payload's `services`, not from its rows", async () => {
    readReadings = async () =>
      answer([BASE], {
        services: [
          { code: "water", name: "Water", meters: ["88-40219"] },
          // A service with NO row on this page — the quarterly-read meter the
          // old fold would have dropped.
          { code: "electric", name: "Electric", meters: ["8841-C"] },
        ],
      });
    render(
      <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
        <Routes>
          <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findAllByText("Read by a meter reader");
    expect(
      document.querySelector("[data-service-picker='meter'] [data-segment='electric']"),
    ).not.toBeNull();
  });

  it("choosing a meter tab narrows on the SERVER", async () => {
    readReadings = async () =>
      answer([BASE], {
        services: [
          { code: "water", name: "Water", meters: ["88-40219"] },
          { code: "electric", name: "Electric", meters: ["8841-C"] },
        ],
      });
    render(
      <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
        <Routes>
          <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findAllByText("Read by a meter reader");
    const tab = document.querySelector(
      "[data-service-picker='meter'] [data-segment='electric']",
    ) as Element;
    fireEvent.click(tab);
    const last = asked[asked.length - 1];
    expect(last.filters?.service).toBe("electric");
  });
});


describe("CWP-034 · every reading (US-CWP-041)", () => {
  it("TC-1 — each row states its method IN WORDS and the bill it went on", async () => {
    const { container } = draw([BASE, CORRECTED]);
    await screen.findAllByText("Read by a meter reader");
    expect(container.querySelector("[data-bill='2026-08-31']")?.textContent).toBe(
      "BL-2608-0141",
    );
    // ⚠ **AMENDED 2026-09-05: THE ORDINARY ROW IS PLAIN TEXT, NOT A CHIP.**
    // This used to assert `[data-chip='how-2026-08-31']` on a meter-reader row.
    // `CWP-034.png` writes *Read by a meter reader* as plain text in its own
    // column and reserves the chip for the one row that differs, and
    // `13-wireframe-delta.md` 34.4 names what the old behaviour cost: a grey
    // chip on every row spends the emphasis that was meant to mark the
    // exception. `BR-CWP-071` asks for the method to be as prominent AS THE
    // NUMBER — a full column of body text beside the figure is exactly that,
    // and the rule never asked for a chip. The method is still asserted, in
    // its own cell.
    expect(container.querySelector("[data-how='2026-08-31']")?.textContent).toBe(
      "Read by a meter reader",
    );
    expect(container.querySelector("[data-chip='how-2026-08-31']")).toBeNull();
  });

  it("TC-2 — the corrected row opens to BOTH figures, the date and the assurance", async () => {
    const { container } = draw([CORRECTED]);
    // ⚠ **TWO SPANS, NOT ONE STRING (amended 2026-09-05).** The drawing gives
    // the corrected row an `ESTIMATED` chip followed by a plain *then
    // corrected*, so the emphasis is on the first half only.
    await screen.findAllByText("then corrected");
    expect(container.querySelector("[data-chip='how-2026-06-30']")?.textContent).toBe(
      "Estimated",
    );

    fireEvent.click(container.querySelector("[data-open-correction='2026-06-30']")!);
    const said = container.querySelector("[data-correction='2026-06-30']")?.textContent ?? "";
    // ⚠ **GROUPED, AND THIS ASSERTION IS WHY IT WAS NOT (`DEF-CWP-4009`).**
    // It read `toContain("144600")`, which PINS the ungrouped form: `144,600`
    // does not contain `144600`. So the first sweep grouped the Reading column
    // and stopped, and the screen printed the same kind of figure two ways.
    // A dial figure is grouped everywhere it is printed, caption included.
    expect(said).toContain("144,600");
    expect(said).toContain("144,130");
    // ⚠ Stated as the ABSENCE of the old strings rather than as "no long run
    // of digits" — the caption also carries the date `2026-07-03`, and a
    // `/\d{4,}/` negative fires on `2026`. A check that cannot pass is the
    // mirror of one that cannot fail (`DEF-182`).
    expect(said).not.toContain("144600");
    expect(said).not.toContain("144130");
    expect(said).toContain("2026-07-03");
    // `BR-CWP-069`, said out loud.
    expect(said).toContain("not charged twice");
  });

  it("TC-3 — a customer-submitted row reads *You sent it in*", async () => {
    const { container } = draw([SELF_READ]);
    await screen.findAllByText("You sent it in");
    // Plain text, and no chip: a self-read is ordinary, not an exception.
    expect(container.querySelector("[data-chip='how-2026-09-02']")).toBeNull();
  });

  it("TC-4 · negative — a reading no bill covers leaves the cell EMPTY", async () => {
    // ⚠ Not a dash and not the nearest bill: nothing at all, because naming one
    // would say the customer was charged for it.
    const { container } = draw([SELF_READ]);
    await screen.findAllByText("You sent it in");
    expect(container.querySelector("[data-bill='2026-09-02']")?.textContent).toBe("");
  });

  it("TC-6 · negative — no readings is a SENTENCE, never a table of dashes", async () => {
    const { container } = draw([]);
    await screen.findByText("Your first reading will appear here.");
    expect(container.querySelector("[data-minitable]")).toBeNull();
    expect(container.querySelector("[data-readings-empty]")).not.toBeNull();
  });

  it("TC-9 — every used-since cell carries its unit, and a unitless one dashes", async () => {
    const noUnit: PortalReading = { ...BASE, taken_on: "2026-07-31", used_since_display: null };
    const { container } = draw([BASE, noUnit]);
    await screen.findAllByText("Read by a meter reader");
    // ⚠ **GROUPED, AND IT WAS NOT (`DEF-CWP-4168`).** `used_since_display` is
    // the server's `quantity_with_unit`, which rounds and trims and does NOT
    // group, while the dial figure one column left goes through the kit's
    // `formatDialFigure` — so a heavy month printed `8402 kWh` beside
    // `41,208`, the same kind of number written two ways on one row. The kit's
    // `formatQuantity` applies the server's OWN rounding rule before grouping,
    // so no digit moves. This assertion pinned the ungrouped form and is
    // amended with the fix, exactly as `DEF-CWP-4009`'s did one column over.
    expect(container.querySelector("[data-used='2026-08-31']")?.textContent).toBe("4,820 gal");
    // Hard rule 3: a bare `4820` is never printed — the cell dashes instead.
    // ⚠ **AND THE GUARD SURVIVES THE GROUPING.** `formatQuantity` returns
    // `null` when the unit is missing, so the fallback chain ends at the
    // server's own `null` and the cell dashes; rebuilding the pair from
    // `used_since` alone would have printed a bare number here.
    expect(container.querySelector("[data-used='2026-07-31']")?.textContent).toBe("—");
  });

  it("the estimate note is on the screen, not only in the row that needs it", async () => {
    // `BR-CWP-071`'s second half — the sentence that stops the phone call.
    const { container } = draw([CORRECTED]);
    await screen.findAllByText("then corrected");
    expect(container.textContent).toContain("best guess");
  });

  it("B14 rule 31 — no database id appears anywhere on the screen", async () => {
    const { container } = draw([BASE, CORRECTED, SELF_READ]);
    await screen.findAllByText("Read by a meter reader");
    expect(container.textContent ?? "").not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i,
    );
  });

  // ══════════════════════════════════════════════════════════════════════
  // 2026-09-05 — the wireframe pass (`13-wireframe-delta.md` §CWP-034),
  // read off `wireframes/CWP-034.png` rather than off the delta's notes.
  // ══════════════════════════════════════════════════════════════════════

  it("CR-085 s51 — two meters on one date are told apart, by the TAB they sit under", async () => {
    // ⚠ **`DEF-CWP-3990` IS STILL ANSWERED — BY THE PICKER RATHER THAN BY A
    // COLUMN.** The defect was two rows sharing a date with nothing on screen
    // saying which box each came off. The signed-off drawing puts that fact in
    // the tab — `⚡ Electric · 8841-C` — and shows one meter's readings at a
    // time; the column repeated the same seven characters down every row.
    const electric: PortalReading = {
      ...BASE,
      meter_serial: "6462",
      meter_no: "E-5026",
      meter_service: "electric",
      meter_service_name: "Electric",
      used_since_display: "1400 kWh",
      unit: "kWh",
    };
    const water: PortalReading = {
      ...BASE,
      meter_serial: "2007",
      meter_no: "W-5026",
      meter_service: "water",
      meter_service_name: "Water",
    };
    const services = [
      { code: "electric", name: "Electric", meters: ["6462"] },
      { code: "water", name: "Water", meters: ["2007"] },
    ];
    // ⚠ **THE SERVICE IS A SERVER FILTER NOW (`DEF-CWP-5747`), SO THE STAND-IN
    // HAS TO HONOUR IT.** It reads the `f.service` the screen sent and answers
    // that meter's rows — which is the behaviour under test. A stand-in that
    // returned both rows whatever was asked would make the assertion below
    // pass over a screen that had stopped narrowing at all, which is law 7's
    // *incapable of failing* shape.
    readReadings = async () => {
      const chosen = asked[asked.length - 1]?.filters?.service ?? "electric";
      const rows = chosen === "water" ? [water] : [electric];
      return answer(rows, { services });
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
        <Routes>
          <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findAllByText("Read by a meter reader");
    const tabs = [...container.querySelectorAll("[data-service-picker='meter'] [data-segment]")].map(
      (tab) => tab.textContent,
    );
    expect(tabs).toEqual(["Electric · 6462", "Water · 2007"]);

    // ⚠ **AND ONLY ONE METER'S ROWS ARE ON SCREEN**, which is what makes the
    // tab the answer rather than a decoration: the electric read is drawn in
    // kWh and the water one is not drawn at all until its tab is chosen.
    expect(container.querySelectorAll("tbody tr")).toHaveLength(1);
    expect(container.querySelector("[data-used='2026-08-31']")?.textContent).toBe("1400 kWh");
    fireEvent.click(container.querySelector("[data-segment='water']") as Element);
    // ⚠ **AWAITED, BECAUSE CHOOSING A TAB IS A ROUND TRIP NOW** — it was a
    // `rows.filter` and the next line could read the DOM immediately. It is
    // `?f.service=water` since `DEF-CWP-5747`, so the rows arrive a tick later
    // and an assertion taken straight after the click would read the PREVIOUS
    // meter's figures and pass or fail for the wrong reason.
    await waitFor(() =>
      expect(container.querySelector("[data-used='2026-08-31']")?.textContent).toBe("4,820 gal"),
    );
    // ⚠ **THE SERVER COMPOSED THIS PAIR (hard rule 3) AND THE SCREEN ONLY ADDS
    // ITS SEPARATORS** (`DEF-CWP-4168`). The figure is the server's; the commas
    // are the reader's locale. Where the two could not be reconciled the
    // server's own string is printed untouched — see `usedText`.
    // With one meter on the chosen service the tab already names it, so the
    // column is not drawn twice.
    expect(container.querySelector("[data-meter='2026-08-31']")).toBeNull();
  });

  it("CR-085 s51 — TWO meters on ONE service bring the meter column back", async () => {
    // ⚠ **THE ONE CASE A TAB CANNOT STATE.** A service answering from two
    // boxes has no single reference to put in its label, so the tab reads
    // `Water` alone and `DEF-CWP-3990`'s column returns — which is the whole
    // reason the column is conditional rather than deleted.
    const front: PortalReading = { ...BASE, meter_serial: "2007", meter_no: "W-5026" };
    const back: PortalReading = { ...BASE, meter_serial: "2008", meter_no: "W-5027" };
    const { container } = draw([front, back], [
      { code: "water", name: "Water", meters: ["2007", "2008"] },
    ]);
    await screen.findAllByText("Read by a meter reader");
    const said = [...container.querySelectorAll("[data-meter='2026-08-31']")].map(
      (n) => n.textContent,
    );
    expect(said).toEqual(["Water · 2007", "Water · 2008"]);
    // One service, so no picker at all — a chooser with one option is
    // furniture, and the column is doing the work.
    expect(container.querySelector("[data-service-picker]")).toBeNull();
  });

  it("34.1 · negative — a meter on no service falls back to its serial alone", async () => {
    // No stray separator with nothing in front of it.
    const orphan: PortalReading = { ...BASE, meter_service: null, meter_service_name: null };
    const water: PortalReading = { ...BASE, meter_service: "water", meter_service_name: "Water" };
    const { container } = draw([orphan, water], [
      { code: "unassigned", name: null, meters: ["88-40219"] },
      { code: "water", name: "Water", meters: ["88-40219"] },
    ]);
    await screen.findAllByText("Read by a meter reader");
    // ⚠ **A METER ON NO SERVICE POINT IS ITS OWN TAB, NOT A DROPPED ROW.** A
    // reading a customer cannot reach at all is worse than a tab with an odd
    // name on it, and there is no stray separator with nothing in front of it.
    const tabs = [...container.querySelectorAll("[data-service-picker='meter'] [data-segment]")].map(
      (tab) => tab.textContent,
    );
    expect(tabs).toEqual(["88-40219", "Water · 88-40219"]);
  });

  it("34.1 · negative — no serial falls back to the utility's own meter number", async () => {
    // `BR-AST-049` — two different columns, and neither is a database id.
    const noSerial: PortalReading = { ...BASE, meter_serial: null };
    const electric: PortalReading = {
      ...BASE,
      meter_serial: null,
      meter_no: "E-5026",
      meter_service: "electric",
      meter_service_name: "Electric",
    };
    const { container } = draw([noSerial, electric], [
      { code: "water", name: "Water", meters: ["M-88402"] },
      { code: "electric", name: "Electric", meters: ["E-5026"] },
    ]);
    await screen.findAllByText("Read by a meter reader");
    const tabs = [...container.querySelectorAll("[data-service-picker='meter'] [data-segment]")].map(
      (tab) => tab.textContent,
    );
    expect(tabs).toEqual(["Water · M-88402", "Electric · E-5026"]);
  });

  it("CR-085 s51 — the phone frame is a stack of cards, and it cannot disagree with the table", async () => {
    // ⚠ **A SIX-COLUMN TABLE ON A 390px PHONE WANTED 559px, MEASURED IN THE
    // BROWSER.** `overflow-x-auto` stops the PAGE moving and leaves the
    // figures unreadable, which is exactly the finding `bills/Bills.tsx`
    // records. The drawing's phone frame is a stack of cards.
    const { container } = draw([BASE]);
    await screen.findAllByText("Read by a meter reader");
    expect(container.querySelectorAll("[data-reading-cards] [data-reading-card]")).toHaveLength(1);
    // ⚠ **THE DIAL FIGURE IS GROUPED AND CARRIES NO UNIT; THE CONSUMPTION
    // CARRIES ITS UNIT AND IS THE SERVER'S OWN PAIR** (hard rule 3, and
    // `formatDialFigure`'s note — `gal` after a register index would claim the
    // meter has measured 153,040 gallons since it was made).
    expect(container.querySelector("[data-card-reading='2026-08-31']")?.textContent).toBe(
      "153,040",
    );
    expect(container.querySelector("[data-card-used='2026-08-31']")?.textContent).toBe("4,820 gal");
    // ⚠ **ONE SOURCE FOR BOTH HALVES.** The table row and the card are fed the
    // same array, so a figure cannot be true at one width and not the other.
    expect(container.querySelector("[data-used='2026-08-31']")?.textContent).toBe("4,820 gal");
    expect(container.querySelector("[data-reading='2026-08-31']")?.textContent).toBe("153,040");
    // The bill is a live door on the card too, with the tenant in the address.
    expect(container.querySelector("[data-card-bill='2026-08-31']")?.getAttribute("href")).toBe(
      "/pine-hill/portal/bills/BL-2608-0141",
    );
  });

  it("CR-085 s51 · negative — a reading on no bill draws no link on the card either", async () => {
    // `US-CWP-041` TC-4, at the other width: naming the nearest bill would
    // tell a customer they were charged for a reading nobody has billed.
    const { container } = draw([{ ...BASE, on_bill: null }]);
    await screen.findAllByText("Read by a meter reader");
    expect(container.querySelector("[data-card-bill='2026-08-31']")).toBeNull();
  });

  // ══════════════════════════════════════════════════════════════════════
  // ⚠ THE HOLD EXPIRED 2026-10-17 EXACTLY AS IT WAS WRITTEN TO (`DEF-CWP-3925`
  // → `DEF-CWP-10175`). These three cases replaced *"Send a reading is HELD"*
  // and the two *"the hold is honest"* cases, which went red the moment
  // `CWP-035` got its address and its register row — the release the comment
  // above them promised. The head action is now a LINK, asserted by ADDRESS,
  // and it is ABSENT, never greyed, when the utility has self-read off.
  // ══════════════════════════════════════════════════════════════════════
  it("34.2 — Send a reading opens CWP-035 at the drawing's own address when self-read is on", async () => {
    readReadings = async () => answer([BASE], { self_read_enabled: true });
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
        <Routes>
          <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findAllByText("Read by a meter reader");
    const link = container.querySelector("a[data-send-reading]");
    expect(link).not.toBeNull();
    expect(link?.textContent).toBe("Send a reading");
    // Only holds because the mount is under `/:tenant/portal` — a bare router
    // would build `//portal/usage/submit` and still read as a string.
    expect(link?.getAttribute("href")).toBe("/pine-hill/portal/usage/submit");
    expect(container.querySelector("[data-held='true']")).toBeNull();
  });

  it("34.2b — with self-read off the action is ABSENT, not held (US-CWP-042 TC-7)", async () => {
    const { container } = draw([BASE]);
    await screen.findAllByText("Read by a meter reader");
    expect(container.querySelector("a[data-send-reading]")).toBeNull();
    expect(container.querySelector("[data-held='true']")).toBeNull();
    expect(container.textContent).not.toContain("Send a reading");
  });

  it("CWP-035 has its address in the router and its row in the screen register", () => {
    expect(SEND_A_READING_PATH).toBe("/usage/submit");
    expect(PORTAL_ROUTES.map((route) => route.path)).toContain(SEND_A_READING_PATH);
    const row = PORTAL_SCREENS.find((screen_) => screen_.id === SEND_A_READING_SCREEN);
    expect(row?.path).toBe(SEND_A_READING_PATH);
  });

  it("34.7 — the bold span is the word being defined, not the sentence after it", async () => {
    // The notice exists to explain *estimated*; bolding the assurance instead
    // emphasises something the reader was not asking about.
    const { container } = draw([CORRECTED]);
    await screen.findAllByText("then corrected");
    const bold = Array.from(container.querySelectorAll("span.font-bold")).map(
      (n) => n.textContent,
    );
    expect(bold).toContain("estimated");
    expect(container.textContent).toContain("never charged twice for the same water");
  });

  it("34.9 — the way out is a link to Usage, with the tenant in the address", async () => {
    // Only holds because `draw` mounts under the real `/:tenant/portal`
    // pattern; a bare MemoryRouter would build `//portal/usage` and pass.
    const { container } = draw([BASE]);
    await screen.findAllByText("Read by a meter reader");
    const back = Array.from(container.querySelectorAll("a")).find((a) =>
      (a.textContent ?? "").includes("Usage"),
    );
    expect(back?.getAttribute("href")).toBe("/pine-hill/portal/usage");
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// CR-085 blueprint · CPB-09 — *"Readings say when the next read is due"*.
// Done is *"The Readings screen reads 'Next read: Sep 30 · in 22 days' above
// the list."* ⚠ The source it was supposed to read COULD NEVER ANSWER —
// `DEF-MET-4684`: an OPEN read window is unreachable by construction, so the
// figure now comes from the route's CYCLE SCHEDULE, which stores nothing.
// ═══════════════════════════════════════════════════════════════════════════

describe("CPB-09 — when the next read is due", () => {
  afterEach(cleanup);

  it("reads the blueprint's own sentence above the list", async () => {
    const { container } = drawWithNextRead({
      from: "2026-09-30",
      to: "2026-10-02",
      open_now: false,
      days_until: 22,
    });
    await screen.findAllByText("Read by a meter reader");
    // The date is written by `Intl` in the reader's own language and the
    // COUNT comes from the server (B14 rule 35 — Hindi and Japanese put the
    // number elsewhere in the sentence).
    expect(container.querySelector("[data-next-read]")?.textContent).toBe(
      "Next read: Sep 30 · in 22 days",
    );
  });

  it("says a window is open NOW rather than counting to it", async () => {
    // *"Your reading is due between 2 and 6 September"* and *"your next
    // reading window opens on 2 September"* are two different sentences, and
    // `open_now` is which one a customer gets. A crew already on the route is
    // not *"in 0 days"*.
    const { container } = drawWithNextRead({
      from: "2026-09-05",
      to: "2026-09-12",
      open_now: true,
      days_until: 0,
    });
    await screen.findAllByText("Read by a meter reader");
    expect(container.querySelector("[data-next-read]")?.textContent).toBe(
      "We are reading meters now — until Sep 12",
    );
  });

  it("says TOMORROW rather than in 1 days", async () => {
    // The off-by-one that reads as broken English is the one a customer
    // notices. Its own catalogue key, in eleven languages.
    const { container } = drawWithNextRead({
      from: "2026-09-09",
      to: "2026-09-09",
      open_now: false,
      days_until: 1,
    });
    await screen.findAllByText("Read by a meter reader");
    expect(container.querySelector("[data-next-read]")?.textContent).toBe(
      "Next read: Sep 9 · tomorrow",
    );
  });

  it("draws nothing at all when no read is scheduled", async () => {
    // `BR-CWP-093`. A dash above a list of readings reads as a date we lost.
    const { container } = drawWithNextRead(null);
    await screen.findAllByText("Read by a meter reader");
    expect(container.querySelector("[data-next-read]")).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// CR-085 step 2 lane 8 — the three states that were short of the drawing, the
// figure that was written two ways, and the ISO date that reached a customer.
// ═══════════════════════════════════════════════════════════════════════════

describe("CWP-034 — the states, the figures and the dates", () => {
  afterEach(cleanup);

  it("DEF-CWP-4849 — with no reads at all the screen says WHEN the first one is due", async () => {
    // ⚠ **THE DRAWING'S OWN SENTENCE, AND THE BUILD SAID SOMETHING ELSE.**
    // Screen 51's `NO READS YET` state is *"Your first read is due around Sep
    // 30."* — the build said *"Your first reading will appear here."*, which is
    // true and gives a customer nothing to act on, and then printed the date
    // separately in the line above it: two sentences about one fact, neither
    // of them the drawing's.
    readReadings = async () =>
      answer([], {
        next_read: { from: "2026-09-30", to: "2026-10-02", open_now: false, days_until: 19 },
      });
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
        <Routes>
          <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("Your first read is due around Sep 30.");
    // ⚠ **AND THE LINE ABOVE IS GONE, NOT DUPLICATED.** One derivation, one
    // sentence — the two cannot disagree about one date.
    expect(container.querySelector("[data-next-read]")).toBeNull();
  });

  it("DEF-CWP-4849 · negative — no schedule keeps the plain sentence, never an invented month", async () => {
    // `BR-CWP-093`. A cycle with no schedule answers `null` and the screen
    // states the absence rather than guessing a date.
    const { container } = draw([]);
    await screen.findByText("Your first reading will appear here.");
    expect(container.querySelector("[data-readings-empty]")).not.toBeNull();
  });

  it("DEF-CWP-4849 — an estimated row carries the drawing's THIRD signal", async () => {
    // ⚠ **THREE SIGNALS, AND THE BUILD HAD TWO.** Screen 51: *"Flagged with
    // colour AND the word 'Estimated' AND a row tint — three signals, because
    // this is the fact most likely to be disputed."* Measured at 1280 on
    // 2026-09-11, every `<tr>` returned `background-color: rgba(0, 0, 0, 0)`,
    // the estimated row included.
    //
    // ⚠ **THE TABLE ROW AT 1280 IS STILL SHORT ONE SIGNAL AND IT IS NOT THIS
    // LANE'S FILE.** `MiniTable` owns the `<tr>` and offers `muted` alone —
    // grey TEXT, the wrong signal for a row that matters MORE. The phone card
    // is this screen's own markup and carries the tint; the register row says
    // the rest out loud rather than leaving it to be re-derived.
    const estimated: PortalReading = { ...CORRECTED, estimated: true };
    const { container } = draw([estimated]);
    await screen.findAllByText("then corrected");
    const card = container.querySelector("[data-reading-card='2026-06-30']");
    expect(card?.getAttribute("data-estimated")).toBe("true");
    expect(card?.className).toContain("bg-warning-100");
    // …and an ordinary row is NOT tinted, or the signal says nothing.
    cleanup();
    const plain = draw([BASE]);
    await screen.findAllByText("Read by a meter reader");
    const ordinary = plain.container.querySelector("[data-reading-card='2026-08-31']");
    expect(ordinary?.getAttribute("data-estimated")).toBeNull();
    expect(ordinary?.className).not.toContain("bg-warning-100");
  });

  it("DEF-CWP-4172 — the correction sentence prints the TENANT's date, not the wire's", async () => {
    // ⚠ **THE ONE SCREEN A CUSTOMER OPENS TO DISPUTE A BILL PRINTED THE SAME
    // DATE TWO WAYS.** `correction.corrected_on` was interpolated raw while
    // every other date on the screen went through `usePortalDate`, so a
    // customer on a `MM/DD/YYYY` utility read *"…when the meter was read on
    // **2026-07-03**"* two lines under a `TAKEN` column reading `06/30/2026`.
    //
    // ⚠ **AND IT NEEDED THE PROVIDER TO BE SEEN AT ALL.** `usePortalDate`
    // returns the server's string UNCHANGED when no tenant format is in
    // context — which is the honest answer for a utility that has stated none,
    // and is also why every existing case in this file passed over the defect.
    // A test that does not supply a format cannot tell the fix from the bug.
    readReadings = async () => answer([CORRECTED]);
    const { container } = render(
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
          <Routes>
            <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
          </Routes>
        </MemoryRouter>
      </TenantRegionalProvider>,
    );
    await screen.findAllByText("then corrected");
    fireEvent.click(container.querySelector("[data-open-correction='2026-06-30']")!);
    const said = container.querySelector("[data-correction='2026-06-30']")?.textContent ?? "";
    expect(said).toContain("07/03/2026");
    expect(said).not.toContain("2026-07-03");
  });

  it("DEF-CWP-4168 · the guard — where the two halves disagree the SERVER wins", async () => {
    // ⚠ **THIS ONE WAS FOUND BY A FIXTURE AND IT IS WORTH A CASE OF ITS OWN.**
    // The first draft of the fix re-derived the pair from `used_since` and
    // `unit` and preferred it. A fixture that set `used_since_display` and left
    // `used_since` at the row it was spread from made the screen print
    // **`4,820 kWh` where the server had said `1400 kWh`** — a rendering change
    // that had quietly become a second answer to a question the server already
    // answered. The two cannot diverge in the product (one field, one
    // function), and NOTHING IN THE TYPES SAYS SO, which is exactly when a
    // guard earns its place.
    const disagreeing: PortalReading = {
      ...BASE,
      used_since: "4820.000000",
      used_since_display: "1400 kWh",
    };
    const { container } = draw([disagreeing]);
    await screen.findAllByText("Read by a meter reader");
    expect(container.querySelector("[data-used='2026-08-31']")?.textContent).toBe("1400 kWh");
  });

  it("DEF-CWP-4846 — a failed read keeps the title, the screen id and a way out", async () => {
    // ⚠ **THE BACK LINK IS THIS SCREEN'S ONLY DOOR**, and it went with the
    // data: the failure branch returned above `<PageHeader>`, so a customer
    // whose read failed was left on a page with one sentence and no way off
    // it. Asserted BY ADDRESS, which is what the defect's own `prevention`
    // asks for — a sentence assertion cannot see what disappeared.
    readReadings = async () => {
      throw new Error("500");
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/readings"]}>
        <Routes>
          <Route path="/:tenant/portal/readings" element={<ReadingsView accountId="acc-1" />} />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read your meter history.");
    expect(container.querySelector("[data-screen='CWP-034']")).not.toBeNull();
    expect(container.querySelector("h1")?.textContent).toBe("Readings on your meters");
    const hrefs = [...container.querySelectorAll("a")].map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/pine-hill/portal/usage");
    // R-22 and R-10 — which state this is, and what to do about it.
    expect(container.querySelector("[data-portal-state='failed']")).not.toBeNull();
    expect(container.querySelector("[data-way-out='retry']")).not.toBeNull();
  });
});
