/**
 * Group A ruling 3(a) — the ink on a brand-coloured surface, on the worked
 * figures the PO/QA was shown, and the same figures the server pins in
 * `06-backend/tests/test_a11y_group_a_brand.py`.
 */
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import {
  AA_TEXT,
  INK_DARK,
  INK_LIGHT,
  STOCK_ACCENT,
  STOCK_ACCENT_INKS,
  STOCK_ACCENT_TEXT,
  PAGE_BG,
  TEXT_STEP,
  WHITE,
  brandColourTooLight,
  brandInks,
  brandTextShade,
  contrastRatio,
  inkOnBrand,
  mixWithBlack,
} from "./contrast";
import { brandStyle } from "../portal/shell/GuestFrame";
import type { PortalFront } from "../portal/api/guestClient";

const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(path: string, encoding: string): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL): string;
};
const tokensCss = nodeFs.readFileSync(nodeUrl.fileURLToPath(new URL("../styles/tokens.css", import.meta.url)), "utf8");
const token = (name: string) => new RegExp(`${name}:\\s*([^;]+);`).exec(tokensCss)?.[1].trim().toLowerCase();

const r2 = (a: string, b: string) => Math.round((contrastRatio(a, b) as number) * 100) / 100;

describe("Group A · the ink on a brand colour", () => {
  it("the sample #EC3013 reads 4.20 with white, so it switches to the dark ink (5.00)", () => {
    expect(r2(INK_LIGHT, "#EC3013")).toBe(4.2);
    expect(inkOnBrand("#EC3013")).toBe(INK_DARK);
    expect(r2(INK_DARK, "#EC3013")).toBe(5.0);
  });

  it("a dark brand colour keeps white", () => {
    // Silver Creek's #1B5E9E — the server's own worked example (6.68 with white).
    expect(inkOnBrand("#1B5E9E")).toBe(INK_LIGHT);
    expect(r2(INK_LIGHT, "#1B5E9E")).toBe(6.68);
    expect(inkOnBrand("#0B6E4F")).toBe(INK_LIGHT);
  });

  it("each step of the button is judged on its own", () => {
    expect(mixWithBlack("#EC3013", 88)).toBe("#D02A11");
    expect(brandInks("#EC3013")).toEqual({ rest: INK_DARK, hover: INK_LIGHT, pressed: INK_LIGHT });
    expect(r2(INK_LIGHT, "#D02A11")).toBe(5.22);
    // A very light colour keeps the dark ink all the way down.
    expect(brandInks("#FFD400")).toEqual({ rest: INK_DARK, hover: INK_DARK, pressed: INK_DARK });
  });

  it("whatever the colour, the chosen ink reaches 4.5:1 (walked across the cube)", () => {
    const worst: string[] = [];
    for (let r = 0; r < 256; r += 15)
      for (let g = 0; g < 256; g += 15)
        for (let b = 0; b < 256; b += 15) {
          const hex = `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
          const ink = inkOnBrand(hex) as string;
          if ((contrastRatio(ink, hex) as number) < AA_TEXT) worst.push(hex);
        }
    expect(worst).toEqual([]);
  });

  it("not a colour → no ink", () => {
    expect(inkOnBrand("")).toBeNull();
    expect(inkOnBrand(null)).toBeNull();
    expect(brandInks("teal")).toBeNull();
  });

  it("the stock accent the helper assumes is the one tokens.css declares", () => {
    expect(token("--color-accent")).toBe(STOCK_ACCENT.rest);
    expect(token("--color-accent-600")).toBe(STOCK_ACCENT.hover);
    expect(token("--color-accent-700")).toBe(STOCK_ACCENT.pressed);
    expect(STOCK_ACCENT_INKS).toEqual({ rest: INK_DARK, hover: INK_LIGHT, pressed: INK_LIGHT });
  });
});

describe("Group A · the portal frame writes the ink", () => {
  const tenant = (hex: string | null) => ({ brand_primary_hex: hex, brand_accent_hex: null }) as unknown as PortalFront["tenant"];
  const html = (hex: string | null) => renderToStaticMarkup(createElement("div", { style: brandStyle(tenant(hex)) }));

  it("#EC3013 → black text at rest, white on hover and press", () => {
    const out = html("#EC3013");
    expect(out).toContain("--color-on-accent:#000000");
    expect(out).toContain("--color-on-accent-600:#FFFFFF");
    expect(out).toContain("--color-on-accent-700:#FFFFFF");
  });

  it("a dark brand colour → white text", () => {
    expect(html("#0F7B6C")).toContain("--color-on-accent:#FFFFFF");
  });

  it("no colour of its own → our accent, corrected the same way", () => {
    const out = html(null);
    expect(out).not.toContain("--color-accent:");
    expect(out).toContain("--color-on-accent:#000000");
    expect(out).toContain("--color-accent-text:#D02A11");
  });

  it("decision 2: the frame writes the brand's text shade", () => {
    expect(html("#EC3013")).toContain("--color-accent-text:#D02A11");
    expect(html("#E8590C")).toContain("--color-accent-text:#BE490A");
    expect(html("#1D3557")).toContain("--color-accent-text:#1A2F4D");
  });
});

describe("Group A decision 2 · brand-coloured TEXT takes a darker shade", () => {
  it("the worked case: #EC3013 → #D02A11, 5.22 on white, 4.67 on #f3f2f2 (was 4.20 / 3.75)", () => {
    expect(brandTextShade("#EC3013")).toBe("#D02A11");
    expect(r2("#D02A11", WHITE)).toBe(5.22);
    expect(r2("#D02A11", PAGE_BG)).toBe(4.67);
    expect(r2("#EC3013", WHITE)).toBe(4.2);
    expect(STOCK_ACCENT_TEXT).toBe("#D02A11");
  });

  it("a brand still under 4.5 at 88% darkens one point at a time: #E8590C → 82% #BE490A", () => {
    expect(r2(mixWithBlack("#E8590C", 88) as string, PAGE_BG)).toBe(4.03);
    expect(mixWithBlack("#E8590C", 83)).not.toBe(brandTextShade("#E8590C"));
    expect(brandTextShade("#E8590C")).toBe(mixWithBlack("#E8590C", 82));
    expect(brandTextShade("#E8590C")).toBe("#BE490A");
    expect(r2("#BE490A", PAGE_BG)).toBe(4.53);
  });

  it("whatever the colour, the text shade reaches 4.5:1 on #f3f2f2 and on white (walked across the cube)", () => {
    const worst: string[] = [];
    for (let r = 0; r < 256; r += 15)
      for (let g = 0; g < 256; g += 15)
        for (let b = 0; b < 256; b += 15) {
          const hex = `#${[r, g, b].map((v) => v.toString(16).padStart(2, "0")).join("")}`;
          const shade = brandTextShade(hex) as string;
          if ((contrastRatio(shade, PAGE_BG) as number) < AA_TEXT || (contrastRatio(shade, WHITE) as number) < AA_TEXT)
            worst.push(hex);
        }
    expect(worst).toEqual([]);
  });

  it("not a colour → no shade", () => {
    expect(brandTextShade(null)).toBeNull();
    expect(brandTextShade("teal")).toBeNull();
  });
});

describe("Group A decision 3 · a colour too light for text or the focus ring is refused", () => {
  it("the worked case #F5C518 is refused: shade 2.12 on white, ring 1.63 / 1.46", () => {
    expect(r2(mixWithBlack("#F5C518", TEXT_STEP) as string, WHITE)).toBe(2.12);
    expect(r2("#F5C518", WHITE)).toBe(1.63);
    expect(r2("#F5C518", PAGE_BG)).toBe(1.46);
    expect(brandColourTooLight("#F5C518")).toBe(true);
  });

  it("#EC3013, #E8590C and a dark brand are allowed", () => {
    expect(brandColourTooLight("#EC3013")).toBe(false); // 5.22; ring 4.20 / 3.76
    expect(brandColourTooLight("#E8590C")).toBe(false); // 4.50; ring 3.58 / 3.20
    expect(brandColourTooLight("#1D3557")).toBe(false);
  });

  it("the ring alone can refuse: #2A9D8F (shade 4.19, ring 3.32 / 2.97)", () => {
    expect(brandColourTooLight("#2A9D8F")).toBe(true);
    expect(brandColourTooLight("not a colour")).toBe(false);
  });
});
