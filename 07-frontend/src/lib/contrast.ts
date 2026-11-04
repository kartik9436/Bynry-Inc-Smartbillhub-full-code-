/**
 * WCAG 2.x contrast, and the ink the portal writes on a utility's own colour.
 *
 * ONE HELPER, THREE READERS (decision log 2026-10-23, Group A):
 *   * `styles/tokenContrast.test.ts` measures every text token and the field
 *     border against every background token;
 *   * `portal/shell/GuestFrame.tsx` picks the text colour on a brand-filled
 *     surface (ruling 3(a));
 *   * `features/tenancy/BrandMark.tsx` re-exports the ratio for the S8 live
 *     letterhead preview.
 * The server mirror is `06-backend/apps/tenancy/brand.py` (`contrast_ratio`,
 * `brand_ink`, `brand_colour_refusal`), which Company → Profile uses to refuse
 * a colour (ruling 3(b)). The two are pinned on the same worked figures by
 * `contrast.test.ts` and `tests/test_a11y_group_a_brand.py`.
 *
 * THE RULE, as ruled: white text when white reaches 4.5:1 on the colour;
 * otherwise the dark ink. The dark ink is black `#000000`, the ink the brand
 * mark already uses (OQ-800(a)). Worked: `#EC3013` scores 4.20 with white and
 * 5.00 with black, so it takes black. Why black and not the product's text ink
 * `#201e1d` (3.95 on that colour) is the decision log's 2026-10-23 entry
 * "Group A colour build: four judgments".
 */

export const INK_LIGHT = "#FFFFFF";
export const INK_DARK = "#000000";

/** WCAG AA, normal text. */
export const AA_TEXT = 4.5;
/** WCAG 2.1 SC 1.4.11, a form control's boundary. */
export const AA_NON_TEXT = 3;

export function parseHex(value: string | null | undefined): [number, number, number] | null {
  if (value == null) return null;
  const text = value.trim();
  const six = /^#([0-9a-fA-F]{6})$/.exec(text);
  if (six) {
    const d = six[1];
    return [
      Number.parseInt(d.slice(0, 2), 16),
      Number.parseInt(d.slice(2, 4), 16),
      Number.parseInt(d.slice(4, 6), 16),
    ];
  }
  const three = /^#([0-9a-fA-F]{3})$/.exec(text);
  if (three) {
    const d = three[1];
    return [
      Number.parseInt(d[0] + d[0], 16),
      Number.parseInt(d[1] + d[1], 16),
      Number.parseInt(d[2] + d[2], 16),
    ];
  }
  return null;
}

function channel(value: number): number {
  const srgb = value / 255;
  return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
}

/** WCAG relative luminance, 0 (black) … 1 (white). Null when not a colour. */
export function relativeLuminance(value: string | null | undefined): number | null {
  const rgb = parseHex(value);
  if (rgb === null) return null;
  const [r, g, b] = rgb.map(channel);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/** WCAG contrast ratio, 1 … 21. Null when either colour is unreadable. */
export function contrastRatio(
  first: string | null | undefined,
  second: string | null | undefined,
): number | null {
  const a = relativeLuminance(first);
  const b = relativeLuminance(second);
  if (a === null || b === null) return null;
  const [lighter, darker] = a >= b ? [a, b] : [b, a];
  return (lighter + 0.05) / (darker + 0.05);
}

/** The text colour on a brand-filled surface: white if it reaches 4.5:1,
 *  otherwise the dark ink. Null when `background` is not a colour. */
export function inkOnBrand(background: string | null | undefined): string | null {
  const white = contrastRatio(INK_LIGHT, background);
  if (white === null) return null;
  return white >= AA_TEXT ? INK_LIGHT : INK_DARK;
}

/** `color-mix(in srgb, <hex> <p>%, black)`, computed — the same arithmetic the
 *  browser does for the primary tier's hover (88%) and pressed (72%) steps. */
export function mixWithBlack(hex: string, percent: number): string | null {
  const rgb = parseHex(hex);
  if (rgb === null) return null;
  const out = rgb.map((v) => Math.round((v * percent) / 100));
  return `#${out.map((v) => v.toString(16).padStart(2, "0")).join("").toUpperCase()}`;
}

/** The darkening of the primary tier's two hover/pressed steps. */
export const HOVER_STEP = 88;
export const PRESSED_STEP = 72;

/** The ink for each of the three fills a brand button can show. Each step is
 *  judged on its own, because darkening can fail an ink the rest state passed
 *  (`#EC3013`: black 5.00 at rest, 4.02 on hover, 2.96 pressed). */
export function brandInks(background: string | null | undefined): {
  rest: string;
  hover: string;
  pressed: string;
} | null {
  if (parseHex(background) === null || background == null) return null;
  const rest = inkOnBrand(background) as string;
  const hover = inkOnBrand(mixWithBlack(background, HOVER_STEP)) as string;
  const pressed = inkOnBrand(mixWithBlack(background, PRESSED_STEP)) as string;
  return { rest, hover, pressed };
}

/** Our own accent and its two stock steps (`tokens.css` `--color-accent`,
 *  `-600`, `-700`), which a utility with no colour of its own shows. Pinned to
 *  the stylesheet by `contrast.test.ts`, so a retuned token cannot leave this
 *  behind. */
export const STOCK_ACCENT = { rest: "#ec3013", hover: "#dd2b0f", pressed: "#ae1800" } as const;

/** The inks for {@link STOCK_ACCENT}: black at rest (5.00; white is 4.20),
 *  white on hover (4.74) and pressed (7.17). */
export const STOCK_ACCENT_INKS = {
  rest: inkOnBrand(STOCK_ACCENT.rest) as string,
  hover: inkOnBrand(STOCK_ACCENT.hover) as string,
  pressed: inkOnBrand(STOCK_ACCENT.pressed) as string,
};

/** The two light surfaces brand-coloured text and the focus ring sit on in
 *  the portal: a white card and the page (`--color-bg`). */
export const WHITE = "#FFFFFF";
export const PAGE_BG = "#F3F2F2";

/** The first darkening step brand-coloured TEXT takes — the hover shade. */
export const TEXT_STEP = HOVER_STEP;

/**
 * The shade brand-coloured TEXT is drawn in — Group A decision 2 (PO/QA
 * 2026-10-23, *"agreed to your recommondation"*): the brand mixed 88% with
 * black, its own hover shade. When that is still under 4.5:1 on the page
 * colour `#f3f2f2`, the share of brand drops one point at a time until it
 * reaches 4.5 (decision log 2026-10-23, "Group A, the eight decisions: how
 * they are built" (2)). Worked: `#EC3013` → `#D02A11` (5.22 on white, 4.67 on
 * `#f3f2f2`); `#E8590C` → `#BE490A` at 82% (5.06 / 4.53). Null when `brand`
 * is not a colour. Black (0%) always passes, so the loop always returns.
 */
export function brandTextShade(brand: string | null | undefined): string | null {
  if (brand == null || parseHex(brand) === null) return null;
  for (let percent = TEXT_STEP; percent >= 0; percent -= 1) {
    const shade = mixWithBlack(brand, percent) as string;
    if ((contrastRatio(shade, PAGE_BG) as number) >= AA_TEXT) return shade;
  }
  return INK_DARK;
}

/**
 * True when Company → Profile must refuse `brand` as the PRIMARY colour —
 * Group A decision 3: its 88% text shade cannot reach 4.5:1 on white, or the
 * colour itself (the focus ring) cannot reach 3:1 on white AND on `#f3f2f2`.
 * Worked: `#F5C518` → shade `#D8AD15` 2.12, ring 1.63 / 1.46 → refused;
 * `#EC3013` → 5.22, ring 4.20 / 3.76 → allowed. Mirrors
 * `apps/tenancy/brand.py` `brand_colour_too_light`, which is the one that
 * refuses; both are pinned on the same figures. False when not a colour.
 */
export function brandColourTooLight(brand: string | null | undefined): boolean {
  if (brand == null || parseHex(brand) === null) return false;
  const shade = mixWithBlack(brand, TEXT_STEP) as string;
  return (
    (contrastRatio(shade, WHITE) as number) < AA_TEXT ||
    (contrastRatio(brand, WHITE) as number) < AA_NON_TEXT ||
    (contrastRatio(brand, PAGE_BG) as number) < AA_NON_TEXT
  );
}

/** The text shade for {@link STOCK_ACCENT}, which a utility with no colour of
 *  its own shows: `#D02A11`. */
export const STOCK_ACCENT_TEXT = brandTextShade(STOCK_ACCENT.rest) as string;
