/**
 * Themed text — the native type ramp (B14 rule 45: title 22 · section 17 ·
 * body 15 · label 13 · micro 12, one size up in sunlight) in Archivo.
 *
 * A screen never writes a `fontSize`: it picks a `variant`. `Kicker` is the
 * uppercase section label every card on the boards opens with (TIME, ASSET,
 * CREW, OUTCOME…) — the web kit's `Kicker` (TextBits.tsx), same name.
 */
import { Text } from 'react-native';
import type { TextProps, TextStyle } from 'react-native';

import { useTheme } from '../theme';
import type { Theme } from '../theme';

export type TextVariant = 'title' | 'section' | 'body' | 'label' | 'micro';
export type TextWeight = 'regular' | 'semibold' | 'heavy';
export type TextTone = 'default' | 'muted' | 'brand' | 'danger';

/** The style a variant resolves to in a theme. Used by every component that
 *  draws text, so all of them sit on one ramp. */
export function textStyle(
  theme: Theme,
  variant: TextVariant,
  weight?: TextWeight,
  tone: TextTone = 'default',
): TextStyle {
  const size = theme.type[variant];
  const heading = variant === 'title' || variant === 'section';
  const w: TextWeight = weight ?? (heading ? 'heavy' : 'regular');
  const c = theme.colors;
  const toneColour =
    tone === 'muted' ? c.textMuted : tone === 'brand' ? c.brand : tone === 'danger' ? c.dangerAction : c.text;
  return {
    fontSize: size,
    // + measureKey: a font-size change re-measures the label (DEF-FLD-10589).
    lineHeight: Math.round(size * (heading ? theme.lineHeight.heading : theme.lineHeight.body)) + (theme.measureKey ?? 0),
    fontFamily: theme.fonts[w],
    color: toneColour,
  };
}

export interface AppTextProps extends TextProps {
  variant?: TextVariant;
  weight?: TextWeight;
  tone?: TextTone;
}

export function AppText({ variant = 'body', weight, tone, style, ...rest }: AppTextProps) {
  const theme = useTheme();
  const heading = variant === 'title' || variant === 'section';
  return (
    <Text
      accessibilityRole={heading ? 'header' : undefined}
      style={[textStyle(theme, variant, weight, tone), style]}
      {...rest}
    />
  );
}

/** The uppercase section label. Muted by default; `brand` for the job-type
 *  line above a work order (a MARK, R100 — keep it short and heavy). */
export function Kicker(props: { children: string; tone?: 'muted' | 'brand' | 'default'; testID?: string }) {
  const theme = useTheme();
  const base = textStyle(theme, 'micro', 'heavy', props.tone ?? 'muted');
  return (
    <Text
      accessibilityRole="header"
      testID={props.testID}
      style={[base, { letterSpacing: theme.tracking.kicker * theme.type.micro, textTransform: 'uppercase' }]}
    >
      {props.children}
    </Text>
  );
}
