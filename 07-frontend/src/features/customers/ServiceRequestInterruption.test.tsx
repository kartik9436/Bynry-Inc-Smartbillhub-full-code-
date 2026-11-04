// ── Trace ────────────────────────────────────────────────────────────────
// Change:   CR-072 (2026-09-04) — a report no longer opens an interruption; a
//           CLERK does. Screens: the Interruption section of REQ-02.
// Defect:   DEF-CWP-3743 — `ServiceRequestInterruption.tsx` has cited this file
//           by name since it was written and the file did not exist. It does
//           now, and it asserts the thing that citation was for.
// Rules:    BR-CWP-101 (a person judges the reports real) · B14 rule 36 (the
//           shared kit is how you comply — nothing hand-rolled) · r10 rule 4
//           (`Verb ✓` commits) · rule 6 (opening one is not the danger tier) ·
//           rule 17 (an absence says what is missing) · B14 rule 31 (no
//           database id is a visible value) · rule 32 (one sentence)
// Cases:    the two faces of the section — a report nobody has judged, and the
//           record once somebody has; the suggestion is offered, never taken.
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { InterruptionSection } from "./serviceRequestEndpoints";
import { ServiceRequestInterruption, houseNumber, interruptionKey } from "./ServiceRequestInterruption";

const REQUEST_ID = "0198f0a1-2b3c-7d4e-8f90-1a2b3c4d5e6f";
const INTERRUPTION_ID = "0198f0a1-9999-7d4e-8f90-1a2b3c4d5e6f";

const NOT_YET: InterruptionSection = {
  report: {
    kind: "leak_or_burst",
    location_text: "1408 Elm St, Austin TX 78702",
    reported_at: "2026-09-04T14:52:00Z",
  },
  interruption: null,
  already_open_nearby: null,
  statuses: ["looking_into_it", "crew_on_site", "resolved"],
};

const NEARBY: InterruptionSection = {
  ...NOT_YET,
  already_open_nearby: {
    id: INTERRUPTION_ID,
    reference: "RP-26-0412",
    location_text: "Elm St",
    status: "crew_on_site",
  },
};

const OPENED: InterruptionSection = {
  ...NOT_YET,
  interruption: {
    id: INTERRUPTION_ID,
    reference: "RP-26-0412",
    kind: "leak_or_burst",
    status: "crew_on_site",
    location_text: "1408 Elm St, Austin TX 78702",
    affected_area: { street: "Elm St", from: 1400, to: 1500 },
    expected_back_on: null,
    reported_at: "2026-09-04T14:52:00Z",
    resolved_at: null,
    affected_premises: [],
    affected_premises_count: 0,
    affected_unit_count: 0,
  },
};

/** The section reads its own query, so the answer is seeded into the cache
 *  rather than faked with a prop — a prop nothing passes is dead UI (law 2). */
function render(section: InterruptionSection): string {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(interruptionKey(REQUEST_ID), section);
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <ServiceRequestInterruption requestId={REQUEST_ID} />
    </QueryClientProvider>,
  );
}

const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/;

describe("the Interruption section · a report nobody has judged yet (CR-072)", () => {
  const html = render(NOT_YET);

  it("says what the absence MEANS, rather than rendering an empty frame", () => {
    expect(html).toContain("Nobody has opened an interruption");
    expect(html).toContain("A leak or a burst");
    expect(html).toContain("1408 Elm St, Austin TX 78702");
  });

  it("offers the commit that judges it, and it is not the danger tier", () => {
    expect(html).toContain("Open an interruption ✓");
    expect(html).not.toContain('data-variant="danger"');
  });

  it("offers no status control, because there is nothing yet to move", () => {
    expect(html).not.toContain("data-move-to=");
  });

  it("puts no database id on screen (B14 rule 31)", () => {
    expect(html).not.toMatch(UUID);
  });
});

describe("the Interruption section · somebody has already reported this street", () => {
  const html = render(NEARBY);

  it("offers the record already open BY ITS NUMBER, which is a clerk's word", () => {
    expect(html).toContain("Add to RP-26-0412 ✓");
  });

  it("still offers a NEW one — the suggestion is offered, never taken", () => {
    // ⚠ `street_words` is a deliberately small rule and its own docstring
    // limits it to one sentence on a screen. Two bursts on one long street are
    // two interruptions, and only the clerk can tell.
    expect(html).toContain("Open an interruption ✓");
  });
});

describe("the Interruption section · once a clerk has opened one", () => {
  const html = render(OPENED);

  it("shows the utility's own reference and the state it is in", () => {
    expect(html).toContain("RP-26-0412");
    expect(html).toContain("Crew on site");
  });

  it("offers the states it is NOT in, and never the one it is", () => {
    expect(html).toContain('data-move-to="looking_into_it"');
    expect(html).toContain('data-move-to="resolved"');
    expect(html).not.toContain('data-move-to="crew_on_site"');
  });

  it("stops offering to open one", () => {
    expect(html).not.toContain("data-open-interruption");
  });

  it("says the empty affected set is a STATE, not a gap (r10 rule 17)", () => {
    expect(html).toContain("an interruption can exist before we know who it touches");
  });
});

describe("the house-number rule", () => {
  it("reads a number a clerk typed, and refuses everything else", () => {
    expect(houseNumber("1400")).toBe(1400);
    expect(houseNumber(" 1400 ")).toBe(1400);
    expect(houseNumber("")).toBeNull();
    expect(houseNumber("fourteen hundred")).toBeNull();
  });
});
