// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-MET-6913 — the premises detail header showed no utility-service
//           chips. Reported by the Product Owner from the live beta
//           (v2.352.0, Ottumwa Water Works, premises `P-00079`, four services).
// Rules:    BR-RAT-024 (the ELEVEN services) · B14 rule 31 (no database id is
//           ever the visible value of a field) · rule 33 (a chip is a LABEL,
//           ≤ 3 words, no sentence; RATIONALE is ZERO words on screen) ·
//           rule 43 (a piece of UI is a COMPONENT).
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT THIS HARNESS CANNOT SEE.** It does no layout and no colour, so it
// cannot tell a chip row that wrapped from one that did not, and it cannot see
// that the swatch is the right red. The rendered proof is a browser —
// `10-scripts/def_met_6913_premises_chips_walkthrough.mjs`, at 1440 and 1280.
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** A component that rendered an
// EMPTY chip strip for a premises with no services would satisfy tc1 and be
// wrong for the case the PO will look at next, so tc3 and tc4 assert the empty
// and absent cases render NOTHING — not a wrapper, not a separator. And a
// component that printed the service CODE would satisfy "four chips" while
// breaking rule 31, so tc2 reads the visible WORDS.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { SERVICE_CODES } from "@/features/rating/ratingShared";

import { ServiceChips } from "./ServiceChips";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function markup(services: readonly string[] | null | undefined): string {
  return renderToStaticMarkup(<ServiceChips services={services} t={t} />);
}

describe("DEF-MET-6913 — the services a record carries, as header chips", () => {
  it("tc1 — draws one chip per service, in the order the record holds them", () => {
    const html = markup(["water", "sewer", "trash", "fire"]);
    expect(html.match(/data-service="/g)).toHaveLength(4);
    for (const code of ["water", "sewer", "trash", "fire"]) {
      expect(html).toContain(`data-service="${code}"`);
    }
  });

  it("tc2 — names the service in words, never its code (B14 rule 31)", () => {
    const html = markup(["storm_water", "thermal_heat", "fire"]);
    expect(html).toContain(i18n.t("rating.service.storm_water"));
    expect(html).toContain(i18n.t("rating.service.thermal_heat"));
    expect(html).toContain(i18n.t("rating.service.fire"));
    // The code survives only as a `data-` hook, never as visible text.
    expect(html).not.toContain(">storm_water<");
    expect(html).not.toContain(">thermal_heat<");
  });

  it("tc3 — a record with NO services renders nothing at all", () => {
    expect(markup([])).toBe("");
  });

  it("tc4 — and so does a record nobody has been asked about", () => {
    // `null` and `[]` are different FACTS (DEF-762 / CR-036 (h)) and the fact
    // row tells them apart in words. A header states what a record IS, so both
    // are blank here — no separator, no empty chip.
    expect(markup(null)).toBe("");
    expect(markup(undefined)).toBe("");
  });

  it("tc5 — every one of the ELEVEN services draws a chip with a real name", () => {
    // ⚠ HARD-WON LAW 2: the front end typed the service list out by hand in two
    // places and an eleventh service failed SILENTLY — the row existed, the API
    // served it, `tsc` and every test passed, and the screen never offered it.
    // This file holds no list of its own; it asserts against `SERVICE_CODES`,
    // so a twelfth service is covered the day it is added there.
    expect(SERVICE_CODES).toHaveLength(11);
    expect(SERVICE_CODES).toContain("fire");
    const html = markup(SERVICE_CODES);
    expect(html.match(/data-service="/g)).toHaveLength(11);
    for (const code of SERVICE_CODES) {
      const name = i18n.t(`rating.service.${code}`);
      expect(name).not.toBe(code);
      expect(html).toContain(name);
      // A LABEL, per B14 rule 33: at most three words and no sentence.
      expect(name.trim().split(/\s+/).length).toBeLessThanOrEqual(3);
      expect(name).not.toMatch(/\.\s|\.$/);
    }
  });
});
