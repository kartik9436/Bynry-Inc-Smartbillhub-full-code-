/**
 * The shape every theme fills. A component reads ONLY this — never a hex,
 * never a pixel literal — so light, dark and sunlight are three VALUES of one
 * type rather than three sets of per-screen overrides (task T-08, AD-09).
 */

export type ThemeName = 'light' | 'dark' | 'sunlight';

/** What the technician picks on Settings (FF-51 "Screen"): automatic follows
 *  the phone's own light/dark setting. */
export type ThemeMode = 'automatic' | ThemeName;

/** A status tone. Same names as the web's `StatusPill` tones. */
export type StatusTone = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

export interface TonePair {
  /** Text and icon colour. */
  fg: string;
  /** The fill behind it. */
  bg: string;
  /** A strong accent for borders and the left rule of a notice. */
  rule: string;
}

export interface ThemeColors {
  /** The page behind everything. */
  page: string;
  /** A recessed strip (a locked list, a reason box). */
  surface: string;
  /** Every card, sheet and input. */
  card: string;
  /** A card's border. */
  border: string;
  /** An outlined control's border. */
  controlBorder: string;
  /** A rule between two rows inside a card. */
  divider: string;
  text: string;
  textMuted: string;
  /** The brand mark: active indicators, marks. A MARK colour — held to 3:1,
   *  not 4.5:1 (field-app rule R100). Never body text. */
  brand: string;
  /** The brand as a FILL that carries text or a mark on it (the splash, the
   *  brand mark's tile). R100: white on the true brand orange is 4.20:1, so
   *  in light this is the 5%-darker #e12e13 the primary button uses; the other
   *  themes' brand already carries their text. */
  brandFill: string;
  /** The primary tier's fill and the text on it. */
  actionFill: string;
  actionText: string;
  /** The danger tier: outlined in this colour, text in this colour. */
  dangerAction: string;
  /** A disabled control. */
  disabledFill: string;
  disabledText: string;
  /** A selected choice chip (FF-51, FF-18). */
  selectedFill: string;
  selectedText: string;
  /** A toast (the web's ink chip: text-coloured fill, page-coloured text). */
  toastFill: string;
  toastText: string;
  /** The dimmed page behind a sheet. */
  scrim: string;
  /**
   * `fg` is ink ON the tone's own fill (`bg`) — a notice, a chip, a live tile.
   * In sunlight that fill is the dark tone and `fg` is WHITE.
   */
  status: Record<StatusTone, TonePair>;
  /**
   * A status colour drawn as INK ON THE CARD OR PAGE — a tick, a "0 left", a
   * figure in the tone's colour beside plain text (DEF-FLD-10360). Light and
   * dark: the same as `status[tone].fg`. Sunlight: the tone's dark fill
   * colour, because there `fg` is white and white ink on the white card
   * vanished on eight screens. Never use `status[tone].fg` off its own `bg`.
   */
  statusInk: Record<StatusTone, string>;
}

/** The native type ramp (B14 rule 45) — one size up in sunlight. */
export interface ThemeType {
  title: number;
  section: number;
  body: number;
  label: number;
  micro: number;
}

export interface ThemeFonts {
  regular: string;
  semibold: string;
  heavy: string;
}

export interface Theme {
  name: ThemeName;
  colors: ThemeColors;
  type: ThemeType;
  fonts: ThemeFonts;
  /** Border widths. Sunlight draws every structural line at 3. */
  borderWidth: {
    /** A card or input. */
    card: number;
    /** An outlined button. */
    control: number;
    /** A selected chip, a danger outline, a notice's left rule. */
    emphasis: number;
    /** A rule between rows. */
    divider: number;
    /** The strong left rule of a notice (FF-16, FF-18: 3px in every theme). */
    rule: number;
  };
  space: {
    1: number;
    2: number;
    3: number;
    4: number;
    5: number;
    6: number;
    8: number;
  };
  /** The phone's corners (`nativeRadius`): chip, button, card, pill/sheet. */
  radius: { sm: number; md: number; lg: number; pill: number };
  touch: {
    primary: number;
    control: number;
    iconButton: number;
    mostTapped: number;
    clear: number;
  };
  field: { labelToInput: number; inputToHelp: number; fieldToField: number };
  lineHeight: { body: number; heading: number };
  /** Letter spacing in EM (multiply by the font size for React Native). */
  tracking: { kicker: number };
  /** Icon glyph size inside a control. */
  iconSize: number;
  /**
   * Added to every line height so a font-size change re-measures every label
   * (DEF-FLD-10589, `measureKey.ts`). Absent — 0 — at the scale the app
   * started at; only `ThemeProvider` sets it.
   */
  measureKey?: number;
}
