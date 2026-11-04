// ── Trace ──────────────────────────────────────────────
// Screen:   S9 / PLN-01 (Plans landing) and every rating table with a SERVICES
//           INCLUDED column.
// Defect:   DEF-439 — the column drew FULL-NAME chips where r10 draws a
//           coloured letter badge, so three services wrapped to two lines and
//           every row grew taller than the reference.
// Rule:     r10 is THE reference (PO ruling 2026-08-16). Its own markup:
//           `.svc-tag{width:20px;height:20px;background:var(--dot);
//           color:var(--color-bg);font-size:10px;font-weight:800}`.
// Load-     THE LETTER IS DECLARED, NOT DERIVED. `name[0]` collides on six of
// bearing:  our ten services, and a badge that collides is worse than a chip
//           that wraps — it says two different services are the same one.
// ───────────────────────────────────────────────────────
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { ServiceTags, serviceBadge } from "./ratingShared";

// The ELEVEN, in the platform seed order (CLAUDE.md, BR-RAT-024 as amended
// 2026-09-02). ⚠ `fire` was APPENDED by CR-063 and the list is widened rather
// than left at ten: these cases assert DISTINCTNESS, and a subset can never
// fail on the member it does not contain — the same reasoning
// `SignupWizard.test.tsx` records against its own six-year-old `toContain`.
// A fire badge sharing another service's letter or falling through to the
// neutral grey would have been invisible here.
const ELEVEN = [
  "electric",
  "water",
  "gas",
  "sewer",
  "trash",
  "storm_water",
  "solar",
  "broadband",
  "thermal_heat",
  "battery",
  "fire",
] as const;

describe("SERVICES INCLUDED — r10's badge", () => {
  it("DEF-439 / CR-063: every one of the ELEVEN services has a DISTINCT letter", () => {
    const letters = ELEVEN.map((code) => serviceBadge(code).letter);
    expect(new Set(letters).size).toBe(ELEVEN.length);
  });

  it("DEF-439 / CR-063: every one of the ELEVEN has a distinct COLOUR token", () => {
    const tokens = ELEVEN.map((code) => serviceBadge(code).token);
    expect(new Set(tokens).size).toBe(ELEVEN.length);
    // And none of them falls through to the neutral, which is the bug the
    // service palette was introduced to fix (OQ-273) — and the one fire would
    // have hit, since `serviceBadge` answers the neutral for any code its map
    // does not carry.
    expect(tokens).not.toContain("--color-neutral-500");
  });

  it("DEF-439: the six r10 actually draws carry r10's own letters", () => {
    expect(serviceBadge("electric").letter).toBe("E");
    expect(serviceBadge("water").letter).toBe("W");
    expect(serviceBadge("gas").letter).toBe("G");
    expect(serviceBadge("sewer").letter).toBe("S");
    expect(serviceBadge("trash").letter).toBe("T");
    expect(serviceBadge("broadband").letter).toBe("B");
  });

  it("DEF-439: the naive implementation would collide — this is why the map exists", () => {
    // `name[0]` on these six gives S,S,S / T,T / B,B. If a later change
    // "simplifies" the map away, this states what breaks.
    const naive = ["sewer", "solar", "storm_water", "trash", "thermal_heat", "battery"].map(
      (code) => code[0].toUpperCase(),
    );
    expect(new Set(naive).size).toBe(3); // S, T, B — six services, three letters
    const declared = ["sewer", "solar", "storm_water", "trash", "thermal_heat", "battery"].map(
      (code) => serviceBadge(code).letter,
    );
    expect(new Set(declared).size).toBe(6);
  });

  it("DEF-439: the full name is not dropped — it is the accessible name", () => {
    const html = renderToStaticMarkup(<ServiceTags services={["water", "sewer", "trash"]} />);
    // A letter alone is not something a screen reader can announce usefully.
    expect(html).toContain('aria-label="Water"');
    expect(html).toContain('aria-label="Sewer"');
    expect(html).toContain('aria-label="Trash"');
    // And the badge itself is the letter, not the name — the visual fix.
    expect(html).toContain(">W<");
    expect(html).toContain(">S<");
    expect(html).toContain(">T<");
    expect(html).not.toContain(">Water<");
  });

  it("DEF-439: a tenant-added service still renders, visibly, rather than blank", () => {
    const badge = serviceBadge("reclaimed_water");
    expect(badge.letter).toBe("Re");
    expect(badge.token).toBe("--color-neutral-500");
  });
});
