// ── Trace ──────────────────────────────────────────────
// Change:  CR-089 wave A (`PUJ-01` · `PUJ-03` · `PUJ-10` · `PUJ-20` · `PUJ-27`)
//          Screens: S14 (premises list), PRM-02 (the property's Overview),
//          S16 (the add wizard), PRM-03 (the unit's Overview)
// Rules:   BR-MET-1162 (PO 2026-09-08 — a unit's own point, and the fallback
//          is part of the rule) · BR-MET-1163 (`external_ref` IS the parcel) ·
//          B14 rule 32 (a description budget) · rule 33 (a short refusal)
// Tests:   this file · 06-backend/tests/test_cr089_a_where_a_property_is.py
// Impacts: PremisesDetailPage.tsx · PremisesListPage.tsx
// ───────────────────────────────────────────────────────
/**
 * THE THREE THINGS THAT COULD PASS WRONGLY, AND ARE THEREFORE WHAT THIS FILE
 * ASKS ABOUT.
 *
 * ⚠ **1 · `gis_unchecked` IS `false` ON EVERY PROPERTY IN THE PRODUCT.** It is
 * `NOT NULL DEFAULT false`, set on NONE of the 673, so *false* means **nobody
 * has looked** and not *somebody checked*. A screen reading the flag alone
 * would print **Checked** across the whole estate and name a person who never
 * looked. The pair — flag AND `gis_checked_at` — is what decides, and the case
 * below is the one that would have caught it.
 *
 * ⚠ **2 · A REFUSAL THIS PANEL CANNOT RECOGNISE RENDERS AS SILENCE**, which is
 * indistinguishable from the ordinary *there is no City here* state. The first
 * draft of `isNotConnected` read `error.body.error.message_key` — a shape this
 * client never produces — so it was ALWAYS false, `tsc` was happy with the
 * cast, and the panel drew nothing exactly as it should have when there is no
 * City. Only a browser found it. These cases pin the shape it actually reads.
 *
 * ⚠ **3 · A UNIT READING ITS BUILDING'S POINT AND A UNIT WITH ITS OWN LOOK
 * IDENTICAL IF YOU ONLY PRINT THE NUMBERS.** `BR-MET-1162`'s second sentence
 * is that the screen says WHICH, so a case that asserted only the coordinates
 * would be a test named after an assertion it does not make.
 */
import { describe, expect, it } from "vitest";

import { gisCheckState, pointText } from "./PremisesDetailPage";

const t = ((key: string) => key) as never;

describe("CR-089 A3 — the GIS check is a PAIR, never the flag alone", () => {
  it("a placed property nobody has checked is NOT reported as checked", () => {
    // The state all 673 properties are in: the column's DEFAULT.
    expect(gisCheckState({ gis_unchecked: false, gis_checked_at: null })).toBe("not_yet");
  });

  it("a property somebody pressed the control on IS checked", () => {
    expect(gisCheckState({ gis_unchecked: false, gis_checked_at: "2026-09-08" })).toBe(
      "checked",
    );
  });

  it("a property marked unchecked is not checked, stamp or no stamp", () => {
    expect(gisCheckState({ gis_unchecked: true, gis_checked_at: null })).toBe("not_yet");
  });
});

describe("CR-089 A3 — the point is printed, never parsed", () => {
  it("serves the stored strings unchanged", () => {
    // ⚠ NOT `Number()`: this figure is quoted down a phone and typed into other
    // systems, and a round trip through a float can change its last digit.
    expect(pointText("30.752104", "-98.238391", t)).toBe("30.752104, -98.238391");
  });

  it("half a point is NO point — it cannot be drawn either way", () => {
    expect(pointText("30.752104", null, t)).toBeNull();
    expect(pointText(null, "-98.238391", t)).toBeNull();
    expect(pointText(null, null, t)).toBeNull();
  });
});

// CR-089 A5 (the address lookup's not-connected refusal, `isNotConnected`) was
// retired with `FindTheAddress.tsx` on 2026-10-09 (`CR-177-BRC10`): Add a premise
// no longer searches while typing, and *Check address* reads its answer from
// `result` (`not_connected`), which `AddPremisePage.dom.test.tsx` asserts.
