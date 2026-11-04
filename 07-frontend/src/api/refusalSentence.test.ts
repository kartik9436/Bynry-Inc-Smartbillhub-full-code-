// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-7991 — four database uuids on the One-time bill screen.
// Rules:   B14 rule 31 · rule 32 · rule 33 · BR-SHL-020 r2
// Gates:   G139 holds the SERVER half (it runs the chain and reads the
//          payload). This file is the CLIENT half the gate's own output says
//          it does not cover — a check that names its blind spot and leaves it
//          unheld is law 7's fifth shape.
// ───────────────────────────────────────────────────────
import { describe, expect, it } from "vitest";

import { REFUSAL_FALLBACK_KEY, refusalSentence } from "./refusalSentence";

/** A translator that shows its work, so an assertion reads the KEY and PARAMS. */
const t = ((key: string, params?: Record<string, unknown>) => {
  if (key === "rating.service.sewer") return "Sewer";
  if (key === REFUSAL_FALLBACK_KEY) return "This bill cannot be priced. Ask an administrator to check setup.";
  if (key === "rating.refusal.schedulesAmbiguous") {
    return `${params?.schedules} schedules price ${params?.service} on ${params?.date}. Ask an administrator to retire one.`;
  }
  return key;
}) as never;

const PHOTOGRAPHED =
  "R2: 4 versions of schedule '01a0b366-61fa-7f50-8cc4-25fa070287cc' are in force for " +
  "'sewer' on 2026-10-29 (01a0b366-6200-75a1-b0ca-a47e7ba7f490, " +
  "01a0b388-86ba-726e-91c9-1ad57e082b3b). Exactly one prices a service.";

describe("refusalSentence", () => {
  it("renders the catalogue sentence, with the service in the clerk's own word", () => {
    expect(
      refusalSentence(
        {
          message_key: "rating.refusal.schedulesAmbiguous",
          message_params: { schedules: 4, service: "sewer", date: "29 Oct 2026" },
          detail: PHOTOGRAPHED,
        },
        t,
      ),
    ).toBe("4 schedules price Sewer on 29 Oct 2026. Ask an administrator to retire one.");
  });

  it("never shows the engine's sentence when a uuid is in it", () => {
    // The 2026-09-29 payload EXACTLY: no key, and the engineer's `detail`.
    const shown = refusalSentence({ detail: PHOTOGRAPHED }, t);
    expect(shown).toBe("This bill cannot be priced. Ask an administrator to check setup.");
    expect(shown).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}/i);
  });

  it("still shows a clean server sentence verbatim — DEF-CUS-6464 is not undone", () => {
    const clean = "BASE-E has no price for E-200. Price it on the charge code.";
    expect(refusalSentence({ detail: clean }, t)).toBe(clean);
  });

  it("says nothing when the server says nothing", () => {
    expect(refusalSentence(null, t)).toBeNull();
    expect(refusalSentence({ detail: "   " }, t)).toBeNull();
  });

  it("does not mistake an ordinary hex-looking word for an id", () => {
    // `deadbeef` is eight hex characters and is NOT uuid-shaped; the pattern
    // is anchored on the dashed form and the bare 32. Measured, not assumed.
    const sentence = "The deadbeef meter has no reading. Record one.";
    expect(refusalSentence({ detail: sentence }, t)).toBe(sentence);
  });
});
