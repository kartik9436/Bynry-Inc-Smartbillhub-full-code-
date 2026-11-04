// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-005 (EP-TEN-05 §Stories)  Screens: S8, shell-chrome
// Change:   CR-048 wave D — the utility's own mark.
// Defect:   DEF-195 (ruled 2026-08-16, drawn nowhere)
// Rules:    CR-007 PO ruling 2026-08-16 (*"2 letters"*) · BR-TEN-019 ·
//           OQ-800(a) (the contrast call, decided 2026-08-30)
// ───────────────────────────────────────────────────────
/**
 * THIS FILE'S REAL JOB IS TO STOP TWO IMPLEMENTATIONS DRIFTING.
 *
 * `apps/tenancy/brand.py` owns the mark. This app has a second copy of the
 * same maths for one reason only: BR-TEN-019 requires the S8 letterhead to
 * preview LIVE FROM UNSAVED VALUES, and there is nothing on the server to ask
 * while a utility is typing.
 *
 * Every case below is asserted with the SAME worked figure the backend suite
 * asserts (`06-backend/tests/test_cr048_brand_mark.py`). If either side moves,
 * one of the two goes red and names the value.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { CompanyMark } from "@/api/endpoints";

import {
  BrandMark,
  INK_LUMINANCE_THRESHOLD,
  contrastRatio,
  markLetters,
  previewMark,
  readableInk,
  relativeLuminance,
} from "./BrandMark";

const NO_COLOUR: CompanyMark = {
  letters: "SC",
  background_hex: null,
  ink_hex: null,
  contrast_ratio: null,
};

describe("the two letters (CR-007, PO 2026-08-16: “2 letters”)", () => {
  it.each([
    // The PO's own example — and it resolves the same either way, which is
    // why the row under it exists.
    ["Silver Creek Water", "Silver Creek Water & Sanitation District", "SC"],
    // Trading name wins even when it is not a prefix of the legal name.
    ["Hilltop Power", "Ridgeline Holdings LLC", "HP"],
    ["Brazos Bend Utilities", "Brazos Bend Utility District No. 1", "BB"],
    // No trading name → the legal name.
    ["", "Lone Star Ridge Water Co-op", "LS"],
    // One word → its first two letters, never one letter and a gap.
    ["Aquaflow", "Aquaflow Inc", "AQ"],
    // "&" is punctuation, not a letter.
    ["Water & Power", "Water and Power Co", "WP"],
    ["Q", "Q", "Q"],
    // A name may legitimately begin with a digit.
    ["1st Utility District", "1st Utility District", "1U"],
    ["silver creek water", "silver creek water", "SC"],
  ])("%s / %s -> %s", (dba, legal, expected) => {
    expect(markLetters(dba, legal)).toBe(expected);
  });

  it("has no letters only when there is no name at all", () => {
    expect(markLetters("", "")).toBe("");
    expect(markLetters(null, null)).toBe("");
  });
});

describe("the ink — their colour, our text (OQ-800(a))", () => {
  it("picks white on a dark brand and black on a pale one", () => {
    expect(readableInk("#1B5E9E")).toBe("#FFFFFF"); // a navy
    expect(readableInk("#F5E9A0")).toBe("#000000"); // OQ-800's pale yellow
    expect(readableInk("#000000")).toBe("#FFFFFF");
    expect(readableInk("#FFFFFF")).toBe("#000000");
  });

  it("clears WCAG AA (4.5:1) for every colour a tenant can pick", () => {
    // The whole argument for choosing the ink instead of refusing a colour:
    // the floor over the RGB cube is 4.58:1, above AA's 4.5 for normal text.
    let worst = 21;
    let worstHex = "";
    for (let r = 0; r < 256; r += 15) {
      for (let g = 0; g < 256; g += 15) {
        for (let b = 0; b < 256; b += 15) {
          const hex = `#${[r, g, b].map((c) => c.toString(16).padStart(2, "0")).join("")}`;
          const ratio = contrastRatio(readableInk(hex), hex) ?? 0;
          if (ratio < worst) {
            worst = ratio;
            worstHex = hex;
          }
        }
      }
    }
    expect(worst, `${worstHex} only reaches ${worst.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
    expect(worst).toBeCloseTo(4.58, 1);
  });

  it("uses the crossover luminance, not a taste — and agrees with the server", () => {
    expect(INK_LUMINANCE_THRESHOLD).toBeCloseTo(0.179, 3);
    expect(relativeLuminance("#FFFFFF")).toBeCloseTo(1, 6);
    expect(relativeLuminance("#000000")).toBeCloseTo(0, 6);
    // The figures the backend suite pins, to the decimal it rounds to.
    expect(contrastRatio("#FFFFFF", "#1B5E9E")).toBeCloseTo(6.68, 2);
    expect(contrastRatio("#000000", "#F5E9A0")).toBeCloseTo(17.05, 2);
  });

  it("does not guess at a colour it cannot read", () => {
    expect(readableInk(null)).toBeNull();
    expect(readableInk("")).toBeNull();
    expect(readableInk("teal")).toBeNull();
    expect(readableInk("#12345")).toBeNull();
    expect(readableInk("#111")).toBe("#FFFFFF"); // 3-digit CSS hex is real input
  });
});

describe("previewMark — the live half of BR-TEN-019", () => {
  it("recomputes from UNSAVED values, which is the only reason it exists", () => {
    const typed = previewMark({
      dba_name: "Silver Creek Water",
      legal_name: "Silver Creek Water & Sanitation District",
      brand_primary_hex: "#F5E9A0",
    });
    expect(typed).toEqual({
      letters: "SC",
      background_hex: "#F5E9A0",
      ink_hex: "#000000",
      contrast_ratio: 17.05,
    });
  });

  it("states an absent colour rather than inventing one", () => {
    const half = previewMark({
      dba_name: "Silver Creek Water",
      legal_name: "",
      brand_primary_hex: "",
    });
    expect(half.background_hex).toBeNull();
    expect(half.ink_hex).toBeNull();
    expect(half.contrast_ratio).toBeNull();
    expect(half.letters).toBe("SC");
  });
});

describe("what it renders", () => {
  it("DEF-195: the mark carries LETTERS — the block it replaced carried none", () => {
    const html = renderToStaticMarkup(
      <BrandMark
        mark={{
          letters: "SC",
          background_hex: "#1B5E9E",
          ink_hex: "#FFFFFF",
          contrast_ratio: 6.68,
        }}
        hasLogo={false}
        name="Silver Creek Water"
      />,
    );
    expect(html).toContain(">SC<");
    expect(html).toContain("background-color:#1B5E9E");
    expect(html).toContain("color:#FFFFFF");
    // It is the utility's identity, so it is named rather than hidden.
    expect(html).toContain('aria-label="Silver Creek Water logo"');
    expect(html).toContain('role="img"');
  });

  it("falls back to design TOKENS, never to a hex literal (B8)", () => {
    const html = renderToStaticMarkup(<BrandMark mark={NO_COLOUR} hasLogo={false} />);
    expect(html).toContain("var(--color-neutral-300)");
    expect(html).toContain("var(--color-text)");
    expect(html).toContain('aria-label="Utility logo"');
  });

  it("falls back to the mark when there is no tenant to fetch a logo from", () => {
    // This suite runs in `node` (vitest.config.ts keeps that default), so
    // there is no window and no tenant in any URL. A component that threw
    // here would take the screen with it; it draws the letters instead. The
    // real <img> and its src are asserted in SettingsCompanyLogo.dom.test.tsx.
    const html = renderToStaticMarkup(
      <BrandMark mark={NO_COLOUR} hasLogo name="Silver Creek Water" />,
    );
    expect(html).not.toContain("<img");
    expect(html).toContain(">SC<");
  });

  it("adds NO class of its own — B14 rule 21 in an unmigrated file", () => {
    // A Tailwind utility written here would render as nothing at all (the
    // file is not in styles/route-b-migrated.txt), and a bespoke class would
    // be a stylesheet rule rule 21 forbids. So the only class it ever carries
    // is the one its caller passes.
    const bare = renderToStaticMarkup(<BrandMark mark={NO_COLOUR} hasLogo={false} />);
    expect(bare).not.toContain("class=");
    const passed = renderToStaticMarkup(
      <BrandMark mark={NO_COLOUR} hasLogo={false} className="settings-letterhead-mark" />,
    );
    expect(passed).toContain('class="settings-letterhead-mark"');
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-048 wave D · CR-007 PO ruling 2026-08-16 · OQ-257 · OQ-800(a)
// generated: 2026-08-30 by the CR-048 wave-D lane
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
