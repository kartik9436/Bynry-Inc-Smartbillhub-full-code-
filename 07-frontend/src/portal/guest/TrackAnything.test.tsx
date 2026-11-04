// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-010 (EP-CWP-03) · Screens: CWP-012 · wireframes/CWP-012.png
// Rules:    BR-CWP-024 (progress and never data) · BR-CWP-025 (two fields) ·
//           B14 rule 36 (compose the kit; no danger tier) · rule 31
// Cases:    US-CWP-010 TC-1 (the found panel) · TC-4 (nothing about a customer
//           reaches the page either) · the status vocabulary of both series
// ─────────────────────────────────────────────────────────────────────────
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { TrackView } from "../api/guestClient";

import { TrackAnything, statusKey, statusTone } from "./TrackAnything";

function render(): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/pine-hill/portal/track"]}>
      <TrackAnything />
    </MemoryRouter>,
  );
}

describe("CWP-012 · track anything (US-CWP-010)", () => {
  const html = render();

  it("asks for the reference AND a second fact (BR-CWP-025)", () => {
    expect(html).toContain('id="cwp012-reference"');
    expect(html).toContain('id="cwp012-second-fact"');
    // ⚠ **`ZIP code`, AND THIS READ `Postcode` UNTIL `DEF-CWP-4855`.** The
    // blueprint's conventions block C lists the words a North American utility
    // customer knows and names this one: *ZIP code*. Only `en.json` moved —
    // the ten other catalogues already said *código postal*, *CAP*, *CEP*,
    // *Postleitzahl*, *पिन कोड*, *郵便番号*, each right in its own language,
    // and pushing an English acronym into them would break B14 rule 35 to fix
    // a defect that exists in one catalogue.
    expect(html).toContain("ZIP code, or the phone number you gave us");
  });

  it("states the limit before anything is looked up (BR-CWP-024)", () => {
    expect(html).toContain("a reference is not a login");
  });

  it("advances with `Verb →` and never in the danger tier (r10 rules 4 and 6)", () => {
    expect(html).toContain("Look it up →");
    expect(html).not.toContain('data-variant="danger"');
  });

  it("holds the commit until both boxes are filled, WITH its reason", () => {
    expect(html).toContain("Fill in both boxes.");
    expect(html).toContain("disabled");
  });
});

describe("the status vocabulary of both series", () => {
  // ⚠ **A REPORT ANSWERS `series: "report"` AND CARRIES AN `SR-` REFERENCE
  // SINCE `CR-072`, AND THE PAIR IS NOT A CONTRADICTION.** `series` tells this
  // screen which vocabulary to speak — a kind, a place and one of three plain
  // words — and BOTH shapes now come out of `service_requests`. What changed is
  // the number the person types in, not what they read back.
  const report: TrackView = {
    series: "report",
    reference: "SR-26-0049",
    status: "crew_on_site",
    reported_at: "2026-09-02T14:52:00Z",
    kind: "leak_or_burst",
    location_text: "near 1412 Elm St",
  };
  const request: TrackView = {
    series: "request",
    reference: "SR-26-0056",
    status: "submitted",
    reported_at: "2026-09-02T14:52:00Z",
  };

  it("a report's statuses carry the kit's tones, and CREW ON SITE is not danger", () => {
    expect(statusKey(report)).toBe("portal.status.crew_on_site");
    // ⚠ THE INVENTORY PUTS *CREW ON SITE* IN THE BRAND TONE BESIDE OVERDUE AND
    // BOUNCED; r10 rule 6 keeps the loudest colour for a DESTRUCTIVE COMMIT,
    // and a crew arriving to fix your water is the best news on the screen.
    expect(statusTone(report)).toBe("warning");
    expect(statusTone({ ...report, status: "resolved" })).toBe("success");
  });

  it("a request REUSES the staff lifecycle catalogue rather than a second one", () => {
    // ⚠ Eleven states × eleven languages already exist and already say
    // *Submitted*. A second vocabulary for one lifecycle is two answers to one
    // question.
    expect(statusKey(request)).toBe("customers.serviceRequest.state.submitted");
    expect(statusTone(request)).toBe("neutral");
  });
});
