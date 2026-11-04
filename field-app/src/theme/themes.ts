/**
 * The three themes — light, dark, sunlight — as TOKEN SETS (task T-08,
 * AD-09: *"Three themes from one token set … Dark and sunlight are not
 * inverses of each other. Dark lowers light output; sunlight raises
 * contrast"*). A screen never overrides a colour for a theme; it reads
 * `useTheme()` and gets one of these three values.
 *
 * SOURCES, value by value:
 *   LIGHT — the web's own tokens, through `shared/tokens.ts`, as the design's
 *     Stack page assigns them (page #f3f2f2, card #ffffff, border #d7d3d3,
 *     text #201e1d, muted #605d5d, statuses at 700 on 100) and the primary
 *     fill `brandAction` (#e12e13, rule R100).
 *   DARK — the design's Night board, FF-54 (`wireframes/phone/FF-54-dark-
 *     theme.png`; source `Night.dc.html`). Most of it is the web's own neutral
 *     ramp (card #2d2b2b = neutral-900, border #605d5d = neutral-700, text
 *     #f8f4f4 = neutral-100, muted #bab6b6 = neutral-400). SEVEN values exist
 *     only on that board and are written below with that source: the page
 *     #1a1918, the brand #ff7a5e, and the four status inks #7fd99f / #f0c060 /
 *     #ff9a85 / #9ec0ff with the success tint #14301f. The primary button is
 *     drawn as a LIGHT fill with dark text (#f8f4f4 / #201e1d), not orange.
 *   SUNLIGHT — the design's Sunlight board, FF-55 (`Sunlight.dc.html`) and
 *     AD-09: pure white, pure black text, 3px structural lines, solid status
 *     chips with white text (#0a5c31 / #8a4a00 / #8f0f00 — on that board
 *     only), the primary button black. Info is not drawn there; it takes the
 *     web's info-700, which passes on white at 7:1.
 *
 * WHAT THE DRAWINGS SAY THAT THIS FILE DOES NOT DO, and why (B14 rule 44 —
 * the drawing says what is on the screen, our standard says how it is built):
 *   - radius: drawn 4/6/8/22 and BUILT so (PO 2026-10-21, rounded on the
 *     phone) from `shared/tokens.ts` `nativeRadius`; the web's stays 0.
 *   - padding 14, heights 52/58/60: off the spacing scale; built 16 and the
 *     touch standard's 56/48.
 *   - sunlight type 25/19/17/15/14 (+2 per step, 19 and 14 off-ramp): built as
 *     "one size up" ON the declared ramps — each native step takes the next
 *     step up (micro 12→13, label 13→15, body 15→17, section 17→22) and the
 *     title takes the web's h3, 25. Body, label and title match the drawing;
 *     section is 22 rather than 19 and micro 13 rather than 14.
 *   - light warning ink: drawn #a65d0a on #fdf0d8 (the web's pill), which
 *     measures 4.45:1; built #8a4a00, the Sunlight board's amber, at 6.1:1.
 *   - light disabled text: drawn #605d5d on #d7d3d3, which measures 4.4:1;
 *     built #444141 (neutral-800) so every text pair passes 4.5:1, which
 *     `tests/theme/contrast.test.ts` asserts.
 */
import { color, field, letterSpacing, lineHeight, nativeRadius, space, touch, type } from '../tokens';
import type { Theme, ThemeColors, ThemeFonts, ThemeName, ThemeType } from './types';

/** The three Archivo weights the web loads (400 / 600 / 800), by the family
 *  names `useArchivoFonts()` registers them under. */
export const ARCHIVO: ThemeFonts = {
  regular: 'Archivo_400Regular',
  semibold: 'Archivo_600SemiBold',
  heavy: 'Archivo_800ExtraBold',
};

/** `#rrggbb` + alpha → `rgba()`. The scrim is the ink at 40%, the same mix
 *  the web's `--color-divider` uses. */
export function withAlpha(hex: string, alpha: number): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

const NATIVE: ThemeType = { ...type.native };

/** One size up, on the declared ramps (see the header). */
const NATIVE_ONE_UP: ThemeType = {
  title: type.web.h3,
  section: type.native.title,
  body: type.native.section,
  label: type.native.body,
  micro: type.native.label,
};

const shared = {
  fonts: ARCHIVO,
  space: { ...space },
  // PO 2026-10-21: rounded on the phone (the web stays square — `shared/tokens.ts`).
  radius: { ...nativeRadius },
  touch: { ...touch },
  field: { ...field },
  lineHeight: { body: lineHeight.body, heading: lineHeight.heading },
  tracking: { kicker: parseFloat(letterSpacing.kicker) },
};

/** The Sunlight board's amber (FF-55), also the light theme's warning ink. */
const SUNLIGHT_WARNING = '#8a4a00';

const lightColors: ThemeColors = {
  page: color.bg,
  surface: color.surface,
  card: color.white,
  border: color.neutral[300],
  controlBorder: color.neutral[300],
  divider: color.neutral[200],
  text: color.text,
  textMuted: color.neutral[700],
  brand: color.accent,
  brandFill: color.brandAction,
  actionFill: color.brandAction,
  actionText: color.white,
  dangerAction: color.danger[700],
  disabledFill: color.neutral[300],
  disabledText: color.neutral[800],
  selectedFill: color.text,
  selectedText: color.white,
  toastFill: color.text,
  toastText: color.bg,
  scrim: withAlpha(color.text, 0.4),
  status: {
    success: { fg: color.success[700], bg: color.success[100], rule: color.success[700] },
    // NOT the web's warning-700: #a65d0a on #fdf0d8 measures 4.45:1 (tokens.css
    // records the same figure for the web pill) and fails 4.5. The ink is the
    // design's own darker amber from the Sunlight board, #8a4a00 — 6.1:1.
    warning: { fg: SUNLIGHT_WARNING, bg: color.warning[100], rule: color.warning[500] },
    danger: { fg: color.danger[700], bg: color.danger[100], rule: color.danger[500] },
    info: { fg: color.info[700], bg: color.info[100], rule: color.info[700] },
    neutral: { fg: color.neutral[700], bg: color.neutral[200], rule: color.neutral[500] },
  },
  statusInk: {
    success: color.success[700],
    warning: SUNLIGHT_WARNING,
    danger: color.danger[700],
    info: color.info[700],
    neutral: color.neutral[700],
  },
};

/** Values that exist only on the Night board (FF-54). */
const NIGHT = {
  page: '#1a1918',
  brand: '#ff7a5e',
  successInk: '#7fd99f',
  successTint: '#14301f',
  warningInk: '#f0c060',
  dangerInk: '#ff9a85',
  infoInk: '#9ec0ff',
} as const;

const darkColors: ThemeColors = {
  page: NIGHT.page,
  surface: color.neutral[800],
  card: color.neutral[900],
  border: color.neutral[700],
  controlBorder: color.neutral[600],
  divider: color.neutral[800],
  text: color.neutral[100],
  textMuted: color.neutral[400],
  brand: NIGHT.brand,
  brandFill: NIGHT.brand,
  actionFill: color.neutral[100],
  actionText: color.text,
  dangerAction: NIGHT.dangerInk,
  disabledFill: color.neutral[800],
  disabledText: color.neutral[400],
  selectedFill: color.neutral[100],
  selectedText: color.text,
  toastFill: color.neutral[100],
  toastText: color.text,
  scrim: withAlpha(color.black, 0.6),
  status: {
    success: { fg: NIGHT.successInk, bg: NIGHT.successTint, rule: NIGHT.successInk },
    warning: { fg: NIGHT.warningInk, bg: color.neutral[900], rule: NIGHT.warningInk },
    danger: { fg: NIGHT.dangerInk, bg: color.neutral[900], rule: NIGHT.dangerInk },
    info: { fg: NIGHT.infoInk, bg: color.neutral[900], rule: NIGHT.infoInk },
    neutral: { fg: color.neutral[300], bg: color.neutral[800], rule: color.neutral[600] },
  },
  statusInk: {
    success: NIGHT.successInk,
    warning: NIGHT.warningInk,
    danger: NIGHT.dangerInk,
    info: NIGHT.infoInk,
    neutral: color.neutral[300],
  },
};

/** Values that exist only on the Sunlight board (FF-55). */
const SUN = {
  success: '#0a5c31',
  warning: SUNLIGHT_WARNING,
  danger: '#8f0f00',
} as const;

const sunlightColors: ThemeColors = {
  page: color.white,
  surface: color.white,
  card: color.white,
  border: color.black,
  controlBorder: color.black,
  divider: color.black,
  text: color.black,
  textMuted: color.black,
  brand: color.black,
  brandFill: color.black,
  actionFill: color.black,
  actionText: color.white,
  dangerAction: SUN.danger,
  disabledFill: color.neutral[300],
  disabledText: color.black,
  selectedFill: color.black,
  selectedText: color.white,
  toastFill: color.black,
  toastText: color.white,
  scrim: withAlpha(color.black, 0.6),
  status: {
    success: { fg: color.white, bg: SUN.success, rule: SUN.success },
    warning: { fg: color.white, bg: SUN.warning, rule: SUN.warning },
    danger: { fg: color.white, bg: SUN.danger, rule: SUN.danger },
    info: { fg: color.white, bg: color.info[700], rule: color.info[700] },
    neutral: { fg: color.white, bg: color.black, rule: color.black },
  },
  // DEF-FLD-10360: on the white card a tone is its own dark colour, never `fg`'s white.
  statusInk: {
    success: SUN.success,
    warning: SUN.warning,
    danger: SUN.danger,
    info: color.info[700],
    neutral: color.black,
  },
};

export const lightTheme: Theme = {
  name: 'light',
  colors: lightColors,
  type: NATIVE,
  borderWidth: { card: 1, control: 1, emphasis: 2, divider: 1, rule: 3 },
  iconSize: space[5],
  ...shared,
};

export const darkTheme: Theme = {
  name: 'dark',
  colors: darkColors,
  type: NATIVE,
  borderWidth: { card: 1, control: 1, emphasis: 2, divider: 1, rule: 3 },
  iconSize: space[5],
  ...shared,
};

export const sunlightTheme: Theme = {
  name: 'sunlight',
  colors: sunlightColors,
  type: NATIVE_ONE_UP,
  borderWidth: { card: 3, control: 3, emphasis: 3, divider: 3, rule: 3 },
  iconSize: space[6],
  ...shared,
};

export const THEMES: Record<ThemeName, Theme> = {
  light: lightTheme,
  dark: darkTheme,
  sunlight: sunlightTheme,
};
