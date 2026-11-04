// DEF-TEN-8754 — Settings › Configure › Asset types printed the stored category
// code ("behind_the_meter", "meters") where a person should read a name.
import { describe, expect, it } from "vitest";

import en from "../../i18n/locales/en.json";
import { detailLabel } from "./SettingsReferenceData";
import { REFERENCE_CARDS } from "./referenceDataConfig";

const t = (key: string): string => (en as Record<string, string>)[key] ?? key;
const assetTypes = REFERENCE_CARDS.find((card) => card.code === "asset_types");

describe("DEF-TEN-8754 asset type category reads as a name", () => {
  it("names the three stored categories", () => {
    const column = assetTypes?.detailField;
    expect(column).toBeDefined();
    if (column === undefined) return;
    const cell = (category: string) =>
      detailLabel({ category } as never, column, t);
    expect(cell("behind_the_meter")).toBe("Behind the meter");
    expect(cell("meters")).toBe("Meters");
    expect(cell("sub_meters")).toBe("Sub-meters");
  });

  it("falls back to the stored value for a code with no label, and blank stays blank", () => {
    const column = { field: "category", valueLabelKeyPrefix: "assets.tab." };
    expect(detailLabel({ category: "new_kind" } as never, column, t)).toBe("new_kind");
    expect(detailLabel({ category: null } as never, column, t)).toBe("");
  });

  it("leaves a card without a prefix exactly as stored", () => {
    expect(detailLabel({ level: "district" } as never, { field: "level" }, t)).toBe("district");
  });
});
