/* ══════════════════════════════════════════════════════════════════════════
 * CR-075 wave C · C1c — hard rule 2's percentage half
 * ══════════════════════════════════════════════════════════════════════════
 *
 * Every assertion here is what a READER sees, never that a prop was passed
 * (hard-won law 2). The two that matter most were both proved RED before this
 * file went green, and the file says which they are so the next lane can
 * re-break them in one edit:
 *
 *   1. `PERCENT_DISPLAY_DECIMALS = 6` — the storage precision leaking to the
 *      screen. `"0.062500"` reads `6.250000%` instead of `6.25%`.
 *   2. `pointsToFraction` replaced by `Number(points) / 100` — the float path.
 *      `"0.175"` points reads `0.17%` instead of `0.18%`.
 *
 * Both were run, both went red, and the failure text is quoted in the lane
 * report. A guard nobody has watched fail is a claim, not a check.
 * ══════════════════════════════════════════════════════════════════════════ */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  PERCENT_DISPLAY_DECIMALS,
  PercentCell,
  formatPercent,
} from "./PercentCell";
import { MoneyAmountAbsent } from "./MoneyCell";

describe("formatPercent — CLAUDE.md hard rule 2: stored 6, DISPLAY 2", () => {
  it("the display precision is TWO, and it is the number the rule names", () => {
    expect(PERCENT_DISPLAY_DECIMALS).toBe(2);
  });

  it("a tax rate stored as a fraction reads as a percentage a clerk recognises", () => {
    // `taxes.rate` holds 0.062500 and CR-013 part 4 calls it "6.2500%".
    // A clerk reads 6.25%.
    expect(formatPercent("0.062500", "fraction")).toBe("6.25%");
  });

  it("THE RED-FIRST CASE: six stored decimals do not reach the screen", () => {
    // With PERCENT_DISPLAY_DECIMALS = 6 this reads "6.250000%" and fails.
    // That is the whole of hard rule 2's percentage half, asserted once.
    const drawn = formatPercent("0.062500", "fraction");
    expect(drawn).toBe("6.25%");
    expect(drawn).not.toContain("6.250000");
    // and the digits after the point are exactly two, whatever was stored
    expect(drawn.replace("%", "").split(".")[1]).toHaveLength(2);
  });

  it("pads as well as trims — one setting, both directions", () => {
    expect(formatPercent("0.047", "fraction")).toBe("4.70%"); // pads
    expect(formatPercent("0.0625374", "fraction")).toBe("6.25%"); // trims
    expect(formatPercent("0", "fraction")).toBe("0.00%");
  });

  it("rounds HALF-UP, the direction B4.4 signed", () => {
    // 0.06255 as a fraction is 6.255% — half-up goes to 6.26%, not 6.25%.
    expect(formatPercent("0.06255", "fraction")).toBe("6.26%");
    // and away from zero on the negative side, which is what halfExpand means
    expect(formatPercent("-0.06255", "fraction")).toBe("-6.26%");
  });
});

describe("formatPercent — the convention is required, because the product uses both", () => {
  it("the SAME stored string means two different things, and both are drawn correctly", () => {
    // `06-backend/core/money_fields.py`: a percent is stored "either as a
    // fraction (0.062500) or as percent points (40)". 0.5 is an ordinary value
    // under both readings, which is why no heuristic can decide it.
    expect(formatPercent("0.5", "fraction")).toBe("50.00%");
    expect(formatPercent("0.5", "points")).toBe("0.50%");
  });

  it("percent points read as themselves", () => {
    expect(formatPercent("40", "points")).toBe("40.00%");
    expect(formatPercent("4.7", "points")).toBe("4.70%"); // RBS-006-R16's +4.7%
    expect(formatPercent("38", "points")).toBe("38.00%"); // RBS-006-R4's +38%
    expect(formatPercent("0.05", "points")).toBe("0.05%"); // RBS-006-R2's limit
  });

  it("THE FLOAT DETECTOR: points are shifted, never divided", () => {
    // 0.175 / 100 is 0.0017499999999999998 as a double, which reads 0.17%.
    // The exact value reads 0.18%. Measured to diverge on 0.175, 0.205, 0.235,
    // 0.285, 0.305, 0.355 — every tie, always reading LOWER.
    expect(formatPercent("0.175", "points")).toBe("0.18%");
    expect(formatPercent("0.205", "points")).toBe("0.21%");
    expect(formatPercent("0.305", "points")).toBe("0.31%");
  });

  it("precision beyond IEEE-754 survives — a NUMERIC(18,6) percent can exceed a double", () => {
    // 2^53 + 1 is the first integer a double cannot represent; a float path
    // renders ...099,200.00% and loses the last digit.
    expect(formatPercent("9007199254740993", "fraction")).toContain("099,300.00%");
  });

  it("a negative points value keeps its sign through the shift", () => {
    expect(formatPercent("-12.25", "points")).toBe("-12.25%");
    expect(formatPercent("-0.5", "points")).toBe("-0.50%");
  });
});

describe("formatPercent — the locale places the sign, and the absent case refuses", () => {
  it("the per-cent sign is the locale's, never appended", () => {
    // A template literal would put it on the wrong side in Turkish.
    // ⚠ The German separator is U+00A0, a NO-BREAK space, and it is written as
    // an escape here on purpose: with a plain space this assertion fails while
    // its own failure message reads `expected '6,25 %' to be '6,25 %'` — two
    // strings that look identical on the terminal. A check whose output cannot
    // distinguish pass from fail to a reader is the shape hard-won law 7 warns
    // about; this one cost ten minutes to see and would cost the next lane the
    // same.
    expect(formatPercent("0.0625", "fraction", "de-DE")).toBe("6,25\u00a0%");
    expect(formatPercent("0.0625", "fraction", "tr-TR")).toBe("%6,25");
  });

  it("a malformed value renders verbatim, never NaN", () => {
    expect(formatPercent("12.3.4", "fraction")).toBe("12.3.4%");
    expect(formatPercent("", "fraction")).toBe("%");
  });

  it("an ABSENT value throws rather than inventing a dash (DEF-151's reasoning)", () => {
    expect(() =>
      formatPercent(null as unknown as string, "fraction"),
    ).toThrow(MoneyAmountAbsent);
  });
});

describe("PercentCell — what a reader sees on the screen", () => {
  it("draws the figure a clerk reads, not the one the column stores", () => {
    const html = renderToStaticMarkup(<PercentCell value="0.062500" basis="fraction" />);
    expect(html).toContain("6.25%");
    expect(html).not.toContain("6.250000");
  });

  it("a change carries its plus, and a negative keeps the locale's minus", () => {
    expect(
      renderToStaticMarkup(<PercentCell value="4.7" basis="points" signed />),
    ).toContain("+4.70%");
    // Intl writes the minus itself; `signed` must not add a second sign.
    const down = renderToStaticMarkup(<PercentCell value="-4.7" basis="points" signed />);
    expect(down).toContain("-4.70%");
    expect(down).not.toContain("+-");
  });

  it("aligns in a column — a percentage is a numeric cell", () => {
    expect(renderToStaticMarkup(<PercentCell value="40" basis="points" />)).toContain(
      "tabular-nums",
    );
  });

  it("colour is meaning: no direction, no colour", () => {
    const plain = renderToStaticMarkup(<PercentCell value="40" basis="points" />);
    expect(plain).not.toContain("text-danger-700");
    expect(plain).not.toContain("text-success-700");
    expect(plain).toContain('data-percent-direction="none"');
  });

  it("a direction colours the figure, up is the finding and down is the relief", () => {
    expect(
      renderToStaticMarkup(<PercentCell value="38" basis="points" direction="up" />),
    ).toContain("text-danger-700");
    expect(
      renderToStaticMarkup(<PercentCell value="38" basis="points" direction="down" />),
    ).toContain("text-success-700");
  });
});
