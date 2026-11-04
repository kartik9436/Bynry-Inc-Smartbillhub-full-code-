/**
 * The three themes are token SETS of one shape (T-08), carry B14 rule 45's
 * ramp and touch figures, and the provider switches between them.
 */
import { act, render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';
import * as RN from 'react-native';

import {
  ThemeProvider,
  THEMES,
  resolveTheme,
  useTheme,
  useThemeMode,
} from '../../src/theme';
import type { ThemeMode } from '../../src/theme';
import { nativeRadius, radius } from '../../src/tokens';

describe('corners (PO 2026-10-21: rounded on the phone, square on the web)', () => {
  test('every theme rounds at the design figures — chip 4, button 6, card 8, pill and sheet 22', () => {
    for (const name of ['light', 'dark', 'sunlight'] as const) {
      expect([name, THEMES[name].radius]).toEqual([name, { sm: 4, md: 6, lg: 8, pill: 22 }]);
    }
  });

  test('the web-mirrored radii stay 0, so the web stays square and the drift test holds', () => {
    expect(radius).toEqual({ sm: 0, md: 0, lg: 0 });
    expect(nativeRadius).toEqual({ sm: 4, md: 6, lg: 8, pill: 22 });
  });
});

describe('the three themes', () => {
  test('light and dark carry the native ramp 22 / 17 / 15 / 13 / 12 (B14 rule 45)', () => {
    for (const t of [THEMES.light, THEMES.dark]) {
      expect(t.type).toEqual({ title: 22, section: 17, body: 15, label: 13, micro: 12 });
    }
  });

  test('sunlight is one size up on every step', () => {
    const s = THEMES.sunlight.type;
    const l = THEMES.light.type;
    for (const k of Object.keys(l) as Array<keyof typeof l>) {
      expect(s[k]).toBeGreaterThan(l[k]);
    }
    expect(s).toEqual({ title: 25, section: 22, body: 17, label: 15, micro: 13 });
  });

  test('sunlight is pure black on pure white with 2–3px lines', () => {
    const c = THEMES.sunlight.colors;
    expect(c.text).toBe('#000000');
    expect(c.page).toBe('#ffffff');
    expect(c.card).toBe('#ffffff');
    for (const w of Object.values(THEMES.sunlight.borderWidth)) {
      expect(w).toBeGreaterThanOrEqual(2);
      expect(w).toBeLessThanOrEqual(3);
    }
  });

  test('the touch standard is 56 / 48 / 48 / 8 in every theme (B14 rule 45)', () => {
    for (const t of Object.values(THEMES)) {
      expect(t.touch).toEqual({ primary: 56, control: 48, iconButton: 48, mostTapped: 56, clear: 8 });
      expect(t.field).toEqual({ labelToInput: 5, inputToHelp: 6, fieldToField: 20 });
    }
  });

  test('the light primary fill is #e12e13, never the brand #ec3013 (R100)', () => {
    expect(THEMES.light.colors.actionFill).toBe('#e12e13');
    expect(THEMES.light.colors.brand).toBe('#ec3013');
  });

  test('every theme fills every key (same shape)', () => {
    const keys = (o: object) => JSON.stringify(Object.keys(o).sort());
    expect(keys(THEMES.dark.colors)).toBe(keys(THEMES.light.colors));
    expect(keys(THEMES.sunlight.colors)).toBe(keys(THEMES.light.colors));
  });
});

describe('resolveTheme', () => {
  test.each<[ThemeMode, string | null, string]>([
    ['automatic', 'dark', 'dark'],
    ['automatic', 'light', 'light'],
    ['automatic', null, 'light'],
    ['sunlight', 'dark', 'sunlight'],
    ['light', 'dark', 'light'],
  ])('%s with the phone on %s → %s', (mode, scheme, expected) => {
    expect(resolveTheme(mode, scheme)).toBe(expected);
  });
});

function Probe() {
  const theme = useTheme();
  const { setMode } = useThemeMode();
  return (
    <>
      <Text testID="name">{theme.name}</Text>
      <Text testID="to-sun" onPress={() => setMode('sunlight')}>
        sun
      </Text>
    </>
  );
}

describe('ThemeProvider', () => {
  test('switches theme when the mode changes, and reports it', () => {
    const seen: ThemeMode[] = [];
    render(
      <ThemeProvider initialMode="light" onModeChange={(m) => seen.push(m)}>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('name').props.children).toBe('light');
    act(() => {
      screen.getByTestId('to-sun').props.onPress();
    });
    expect(screen.getByTestId('name').props.children).toBe('sunlight');
    expect(seen).toEqual(['sunlight']);
  });

  test('automatic follows the phone', () => {
    const spy = jest.spyOn(RN, 'useColorScheme').mockReturnValue('dark');
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    );
    expect(screen.getByTestId('name').props.children).toBe('dark');
    spy.mockRestore();
  });

  test('useTheme outside a provider throws rather than silently going light', () => {
    jest.spyOn(console, 'error').mockImplementation(() => undefined);
    expect(() => render(<Probe />)).toThrow('useTheme must be used inside <ThemeProvider>');
    (console.error as jest.Mock).mockRestore();
  });
});
