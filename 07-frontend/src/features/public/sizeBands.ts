// ── Trace ──────────────────────────────────────────────
// Change:  DEF-TEN-4222 (reopened 2026-10-02) — decision log 2026-10-02,
//          "THE PUBLIC PRICING PAGE STOPS SHOWING PRICES" and "THE PUBLIC HOME /
//          PRICING PAGE IS REBUILT FROM THE APPROVED DRAFT, AS IMAGES".
// Rules:   BR-TEN-002 (sizes guide setup, never cap billing) · NFR-5 (no caps)
//          · B14 rule 43 (one list, two callers)
// Callers: PricingPage (the Sizes section) · SignupWizard (the size step)
// ───────────────────────────────────────────────────────
//
// THE THREE SIZE BANDS, IN ONE PLACE. The home page shows them and the sign-up
// wizard asks a prospect to pick one, so they are written once: two copies of a
// band label is exactly the rot this repo records most.
//
// ⚠ NO PRICE LIVES HERE, ON PURPOSE. The PO took the prices off display
// pending a new pricing model (*"I dont want to display the pricing - we are
// going to revamp the procing"*). The server still needs a plan CODE at commit
// (`POST /tenants` reads `plan`, `apps/tenancy/services.py`), so each band maps
// to the existing code in size ORDER — smallest band, smallest plan. The
// server's own rows still carry the old ranges (0–300 / 300–1,000 /
// 1,000–3,000) and prices; re-cutting those is the pricing-model work, not this
// page's, and nothing here reads them.
//
// ⚠ AND THE TOP BAND IS NOT A CEILING. 40,000 is the top of the ICP (T5), not a
// cap: the page says "No account cap" beside these, and NFR-5 forbids one.
export interface SizeBand {
  /** Catalogue segment: `public.home.sizes.<key>.*`. */
  key: "small" | "mid" | "large";
  /** The existing subscription plan code the server requires at commit. */
  plan: "starter" | "growth" | "scale";
  /** Account counts. `min` is absent for the bottom band ("Up to 3,000"). */
  min?: number;
  max: number;
}

export const SIZE_BANDS: readonly SizeBand[] = [
  { key: "small", plan: "starter", max: 3000 },
  { key: "mid", plan: "growth", min: 3000, max: 10000 },
  { key: "large", plan: "scale", min: 10000, max: 40000 },
];

type Translate = (key: string, params?: Record<string, unknown>) => string;

/** "Up to 3,000" · "3,000–10,000" · "10,000–40,000", in the reader's own digit
 *  grouping (`3.000` in German, `3 000` in French).
 *
 *  ⚠ THE TWO RANGES ARE COMPOSED HERE AND NOT WRITTEN IN A CATALOGUE, AND G15
 *  IS WHY. "3,000–10,000" is not a word of any language, so in Hindi, Japanese,
 *  Korean and Mexican Spanish it is byte-identical to English and G15 reads it
 *  as an untranslated paste-in. The honest fix is that it never was copy: the
 *  numbers are data and the dash is punctuation. Only "Up to" is a word. */
export function sizeBandRange(t: Translate, band: SizeBand, locale: string): string {
  const count = new Intl.NumberFormat(locale);
  if (band.min === undefined) {
    return t("public.home.sizes.small.range", { max: count.format(band.max) });
  }
  return `${count.format(band.min)}–${count.format(band.max)}`;
}

export function sizeBandBodyKey(band: SizeBand): string {
  return `public.home.sizes.${band.key}.body`;
}

/** The band a stored plan code stands for, or undefined for a code no band
 *  maps to (a restored draft from before the bands, say). */
export function sizeBandForPlan(plan: string): SizeBand | undefined {
  return SIZE_BANDS.find((band) => band.plan === plan);
}
