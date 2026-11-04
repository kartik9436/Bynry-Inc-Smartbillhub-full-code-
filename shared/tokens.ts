/**
 * THE SHARED TOKEN MODULE — one source of colours, spacing, type, radius and
 * touch, imported by the native field app (`field-app/`) and, once it reads
 * this file, by the web app (`07-frontend/`). CR-187-BRC10, field-app task T-06.
 *
 * A plain TypeScript object: no React, no CSS, no platform import. Both
 * renderers turn it into what they draw with.
 *
 * WHERE EVERY VALUE COMES FROM — PORTED, NEVER INVENTED
 *   1. The web's tokens: `07-frontend/src/styles/tokens.css` (`:root`) and its
 *      mirror in `07-frontend/src/styles/tailwind.css` (`@theme`). Every value
 *      that mirrors a CSS variable is listed in `WEB_CSS_MIRROR` at the foot of
 *      this file, and `field-app/tests/tokens/drift.test.ts` fails when one of
 *      them differs from `tokens.css` (decision log 2026-10-21, "twelve
 *      conflicts", #2: *"until the web reads it, a test fails when its values
 *      drift from tokens.css. The web tokens are not rewritten in the same
 *      change."*).
 *   2. B14 rule 45 (ratified 2026-10-20/21): the native type ramp
 *      22 / 17 / 15 / 13 / 12 and the touch standard 56 / 48 / 48 / 8.
 *   3. B14 rule 39 (ratified 2026-09-11/12): field anatomy 5 / 6 / 20.
 *   4. The field-app design (*SMART360 Next Field App*, Stack page, "The
 *      orange, and the one adjustment"), ruled by the PO as field-app rule
 *      R100: the primary-button fill `#e12e13`. Plus `#ffffff`, which the
 *      design names as the card colour and the web has no variable for.
 *   Anything in groups 2–4 has NO CSS variable and is therefore NOT in the
 *   mirror list — the drift test cannot and does not check it. Its source is
 *   written beside it instead.
 */

/** Colours. Names follow the CSS variables they mirror (`--color-neutral-300`
 *  → `color.neutral[300]`). */
export const color = {
  // ── Core surface & ink (tokens.css top block) ─────────────────────────────
  bg: '#f3f2f2',
  surface: '#eae9e9',
  text: '#201e1d',
  accent: '#ec3013',
  accent2: '#e15b47',
  // portal a11y Group A F-09 (PO/QA 2026-10-23): input/select/textarea borders only.
  fieldBorder: '#8c8888',
  // portal a11y Group A decision 6 (PO/QA 2026-10-23): staff input/select/textarea fill.
  fieldFill: '#ffffff',

  neutral: {
    100: '#f8f4f4',
    200: '#eae7e7',
    300: '#d7d3d3',
    400: '#bab6b6',
    500: '#9b9797',
    600: '#6b6767', // portal a11y Group A F-01 (PO/QA 2026-10-23); was #7d7979
    700: '#605d5d',
    800: '#444141',
    900: '#2d2b2b',
  },
  accentRamp: {
    100: '#fff2ef',
    200: '#ffe0d9',
    300: '#ffc4b8',
    400: '#ff9783',
    500: '#ff563c',
    600: '#dd2b0f',
    700: '#ae1800',
    800: '#7c1405',
    900: '#4d170e',
  },
  accent2Ramp: {
    100: '#fff2ef',
    200: '#ffe0da',
    300: '#ffc4b9',
    400: '#ff9784',
    500: '#ef6853',
    600: '#c94b39',
    700: '#9e3526',
    800: '#71261b',
    900: '#471d16',
  },

  // ── Semantic status colours — status meaning only, never decoration ──────
  success: { 100: '#e6f4ec', 500: '#1f9d57', 700: '#0f6e3a' },
  warning: { 100: '#fdf0d8', 500: '#e08a1e', 700: '#a65d0a' },
  danger: { 100: '#fde4df', 500: '#e0341a', 700: '#a81600' },
  /** No `500`, deliberately — tokens.css explains why. */
  info: { 100: '#e6eefb', 700: '#1d4ea8' },

  /** Eleven services, in seed order. Keys are the service CODES. */
  service: {
    electric: '#ec3013',
    water: '#1e6b8f',
    gas: '#c47a1d',
    sewer: '#5a5555',
    trash: '#3a6b3d',
    storm_water: '#2f4a7a',
    solar: '#7a9a2a',
    broadband: '#6b3d8a',
    thermal_heat: '#a8256b',
    battery: '#3aa39b',
    fire: '#8f1f14',
  },

  // ── NOT on the web — sourced from the field-app design ────────────────────
  /**
   * The primary-button fill. White on the brand orange `#ec3013` measures
   * 4.20:1 against a 4.5:1 bar, so a filled primary button uses this, 5%
   * darker, at 4.56:1. `#ec3013` (`accent`) stays the brand colour for marks,
   * active indicators and section labels.
   * Source: field-app design, Stack page, "The orange, and the one
   * adjustment"; PO ruled as field-app rule R100 (decision log 2026-10-21,
   * "Field app Phase 0 (T-05)").
   */
  brandAction: '#e12e13',
  /** The card colour. Source: field-app design, Stack page, token table
   *  (*"card / border | #ffffff #d7d3d3 | Every card. White on #f3f2f2"*).
   *  The web draws `#fff` in places but declares no variable for it. */
  white: '#ffffff',
  /** Pure black — the sunlight theme's ink. Source: field-app design, the
   *  Sunlight board (FF-55) and AD-09 (*"pure white, black text"*). */
  black: '#000000',
} as const;

/** The one spacing scale (B14 rule 39). 6, 10, 14, 18 and 22 do not exist. */
export const space = {
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  8: 32,
} as const;

/**
 * Radii — TWO sets, because the two renderers are ruled differently.
 *
 * `radius` is the WEB's: the Modernist theme is SQUARE, every radius 0, and
 * the web's CSS mirrors these (`WEB_CSS_MIRROR`, the drift test holds them).
 *
 * `nativeRadius` is the PHONE's: PO 2026-10-21 (decision log "Field app: ten
 * PO answers") — *corners are rounded on the phone* — at the design's Stack
 * page figures, 4 / 6 / 8 / 22: a chip, a button, a card, and a pill or the
 * top of a sheet. The field app's theme reads `nativeRadius`; nothing on the
 * web reads it, so the web stays square.
 */
export const radius = {
  sm: 0,
  md: 0,
  lg: 0,
} as const;

export const nativeRadius = {
  /** A chip, a tag, a small mark. */
  sm: 4,
  /** A button, a field. */
  md: 6,
  /** A card, a panel. */
  lg: 8,
  /** A pill, and the top corners of a sheet. */
  pill: 22,
} as const;

/** Font families and weights. Archivo is ratified (OQ-272 (a), PO 2026-10-20). */
export const font = {
  /** The CSS stack, as the web declares it. */
  headingStack: '"Archivo", system-ui, sans-serif',
  bodyStack: '"Archivo", system-ui, sans-serif',
  headingWeight: 800,
  /** The three weights the web loads (`Archivo:wght@400;600;800`). */
  weights: [400, 600, 800] as const,
} as const;

/** BOTH type ramps, side by side (B14 rule 45: one standard, two ramps). */
export const type = {
  /** The web ramp, as in tokens.css. Pixels. */
  web: {
    display: 56,
    h1: 40,
    h2: 32,
    h3: 25,
    h4: 20,
    h5: 16,
    xs: 11,
    sm: 12,
    base: 13,
    md: 14,
    body: 15,
    metricSm: 22,
    metric: 26,
    metricLg: 32,
    btn: 14,
    btnSm: 12,
    table: 13.5,
    tableHeader: 12,
  },
  /** The native ramp — B14 rule 45. Points. */
  native: {
    title: 22,
    section: 17,
    body: 15,
    label: 13,
    micro: 12,
  },
} as const;

export const lineHeight = {
  body: 1.55,
  heading: 1.12,
  metricSm: 1.15,
  metric: 1.1,
} as const;

export const letterSpacing = {
  /** tokens.css `--letter-spacing-heading`. */
  heading: '-0.015em',
  /** tailwind.css `--tracking-kicker` — an uppercase section label. */
  kicker: '0.1em',
} as const;

/** The touch standard — B14 rule 45 / field-app R39 / AD-11. Points. */
export const touch = {
  /** The one thing the screen is for. */
  primary: 56,
  /** Any interactive control — nothing smaller ships. */
  control: 48,
  /** An icon-only button. */
  iconButton: 48,
  /** The most-tapped control (a quantity stepper). Stack page. */
  mostTapped: 56,
  /** Clear space between two adjacent targets. */
  clear: 8,
} as const;

/** Field anatomy — B14 rule 39 (ratified 2026-09-11/12). Pixels. The ratio
 *  1 : 1 : 4 is the point; the figures stand as ratified. */
export const field = {
  labelToInput: 5,
  inputToHelp: 6,
  fieldToField: 20,
} as const;

export const tokens = {
  color,
  space,
  radius,
  nativeRadius,
  font,
  type,
  lineHeight,
  letterSpacing,
  touch,
  field,
} as const;

export type Tokens = typeof tokens;

/**
 * Every value in this module that CLAIMS to mirror a CSS variable in
 * `07-frontend/src/styles/tokens.css`, as `[css variable, value as CSS writes
 * it]`. The drift test reads this list and nothing else, so a value is only
 * protected if it is listed here. Numbers are pixels unless noted.
 *
 * ⚠ WRITTEN WITH PLAIN LOOPS ON PURPOSE — no array spread, no destructuring,
 * no for-of. This file lives OUTSIDE both apps' folders, so it has no
 * `node_modules` of its own; Babel turns a spread or a destructure into a
 * `require("@babel/runtime/helpers/…")`, which cannot be resolved from here
 * and fails the import. `field-app/tests/tokens/helperFree.test.ts` compiles
 * this file the way the app does and fails if any `require(` appears.
 */
function px(n: number): string {
  return String(n) + 'px';
}

function buildMirror(): Array<readonly [string, string]> {
  const out: Array<readonly [string, string]> = [
    ['--color-bg', color.bg],
    ['--color-surface', color.surface],
    ['--color-text', color.text],
    ['--color-accent', color.accent],
    ['--color-accent-2', color.accent2],
    ['--color-field-border', color.fieldBorder],
    ['--color-field-fill', color.fieldFill],
  ];
  const steps = [100, 200, 300, 400, 500, 600, 700, 800, 900] as const;
  for (let i = 0; i < steps.length; i += 1) {
    const s = steps[i] as (typeof steps)[number];
    out.push(['--color-neutral-' + s, color.neutral[s]]);
    out.push(['--color-accent-' + s, color.accentRamp[s]]);
    out.push(['--color-accent-2-' + s, color.accent2Ramp[s]]);
  }
  out.push(
    ['--color-success-100', color.success[100]],
    ['--color-success-500', color.success[500]],
    ['--color-success-700', color.success[700]],
    ['--color-warning-100', color.warning[100]],
    ['--color-warning-500', color.warning[500]],
    ['--color-warning-700', color.warning[700]],
    ['--color-danger-100', color.danger[100]],
    ['--color-danger-500', color.danger[500]],
    ['--color-danger-700', color.danger[700]],
    ['--color-info-100', color.info[100]],
    ['--color-info-700', color.info[700]],
  );
  const services = Object.keys(color.service) as Array<keyof typeof color.service>;
  for (let i = 0; i < services.length; i += 1) {
    const code = services[i] as keyof typeof color.service;
    // The CSS token hyphenates the code's underscore (tokens.css explains why).
    out.push(['--color-service-' + code.replace(/_/g, '-'), color.service[code]]);
  }
  out.push(
    ['--font-heading', font.headingStack],
    ['--font-heading-weight', String(font.headingWeight)],
    ['--font-body', font.bodyStack],
    ['--text-display', px(type.web.display)],
    ['--text-h1', px(type.web.h1)],
    ['--text-h2', px(type.web.h2)],
    ['--text-h3', px(type.web.h3)],
    ['--text-h4', px(type.web.h4)],
    ['--text-h5', px(type.web.h5)],
    ['--text-xs', px(type.web.xs)],
    ['--text-sm', px(type.web.sm)],
    ['--text-base', px(type.web.base)],
    ['--text-md', px(type.web.md)],
    ['--text-body', px(type.web.body)],
    ['--text-metric-sm', px(type.web.metricSm)],
    ['--text-metric', px(type.web.metric)],
    ['--text-metric-lg', px(type.web.metricLg)],
    ['--text-btn', px(type.web.btn)],
    ['--text-btn-sm', px(type.web.btnSm)],
    ['--table-font-size', px(type.web.table)],
    ['--table-header-font-size', px(type.web.tableHeader)],
    ['--line-height-body', String(lineHeight.body)],
    ['--line-height-heading', String(lineHeight.heading)],
    ['--line-height-metric-sm', String(lineHeight.metricSm)],
    ['--line-height-metric', String(lineHeight.metric)],
    ['--letter-spacing-heading', letterSpacing.heading],
  );
  const spaceSteps = [1, 2, 3, 4, 5, 6, 8] as const;
  for (let i = 0; i < spaceSteps.length; i += 1) {
    const k = spaceSteps[i] as keyof typeof space;
    out.push(['--space-' + k, px(space[k])]);
  }
  out.push(
    ['--radius-sm', px(radius.sm)],
    ['--radius-md', px(radius.md)],
    ['--radius-lg', px(radius.lg)],
  );
  return out;
}

export const WEB_CSS_MIRROR: ReadonlyArray<readonly [string, string]> = buildMirror();

/** Values mirroring a key that exists ONLY in `tailwind.css`'s `@theme` block
 *  (not in tokens.css). The drift test checks these against tailwind.css. */
export const WEB_TAILWIND_MIRROR: ReadonlyArray<readonly [string, string]> = [
  ['--tracking-kicker', letterSpacing.kicker],
];
