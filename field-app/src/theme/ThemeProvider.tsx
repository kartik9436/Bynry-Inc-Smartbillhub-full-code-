/**
 * ThemeProvider + useTheme() — task T-08.
 *
 * The technician picks a SCREEN mode on Settings (FF-51: Automatic · Light ·
 * Dark · Sunlight). Automatic follows the phone's own light/dark setting;
 * sunlight is only ever chosen, because no phone reports "it is bright out".
 *
 * Where the choice is REMEMBERED is not this file's job: the provider takes an
 * `initialMode` and reports changes through `onModeChange`, so the settings
 * lane can store it (MMKV) without this file knowing how.
 *
 * `useTheme()` THROWS outside a provider rather than quietly returning the
 * light theme. A silent default would render every screen correctly in light
 * and never switch — a live screen behind a dead control (hard-won law 2's
 * mirror), which no test of a single screen could see.
 */
import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useColorScheme, useWindowDimensions } from 'react-native';

import { measureKey } from './measureKey';
import { THEMES } from './themes';
import type { Theme, ThemeMode, ThemeName } from './types';

interface ThemeContextValue {
  theme: Theme;
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  biggerText: boolean;
  setBiggerText: (on: boolean) => void;
}

/**
 * FF-51 *Bigger text · Easier with gloves on*: the type ramp one size up —
 * the SAME ramp sunlight uses (themes.ts, `NATIVE_ONE_UP`), so it adds no
 * size that is not already declared. Sunlight is already one up and stays as
 * it is; there is no second step on the ramp to take.
 */
export function withBiggerText(theme: Theme, on: boolean): Theme {
  if (!on || theme.name === 'sunlight') return theme;
  return { ...theme, type: THEMES.sunlight.type };
}

/** The theme with `measureKey` set — left untouched (same object) when the key is 0. */
function withMeasureKey(theme: Theme, key: number): Theme {
  return key === 0 ? theme : { ...theme, measureKey: key };
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

/** Which theme a mode resolves to, given the phone's scheme. */
export function resolveTheme(mode: ThemeMode, scheme: string | null | undefined): ThemeName {
  if (mode === 'automatic') return scheme === 'dark' ? 'dark' : 'light';
  return mode;
}

export function ThemeProvider(props: {
  children: ReactNode;
  initialMode?: ThemeMode;
  onModeChange?: (mode: ThemeMode) => void;
  initialBiggerText?: boolean;
  onBiggerTextChange?: (on: boolean) => void;
}) {
  const { onModeChange, onBiggerTextChange } = props;
  const [mode, setModeState] = useState<ThemeMode>(props.initialMode ?? 'automatic');
  const [biggerText, setBiggerState] = useState<boolean>(props.initialBiggerText ?? false);
  const setBiggerText = useCallback(
    (on: boolean) => {
      setBiggerState(on);
      onBiggerTextChange?.(on);
    },
    [onBiggerTextChange],
  );
  const scheme = useColorScheme();
  // DEF-FLD-10589: the phone's font scale goes into every line height, so a
  // font-size change re-measures every label (measureKey.ts says why).
  const key = measureKey(useWindowDimensions().fontScale);
  const setMode = useCallback(
    (next: ThemeMode) => {
      setModeState(next);
      onModeChange?.(next);
    },
    [onModeChange],
  );
  const value = useMemo<ThemeContextValue>(
    () => ({
      theme: withMeasureKey(withBiggerText(THEMES[resolveTheme(mode, scheme)], biggerText), key),
      mode,
      setMode,
      biggerText,
      setBiggerText,
    }),
    [mode, scheme, setMode, biggerText, setBiggerText, key],
  );
  return <ThemeContext.Provider value={value}>{props.children}</ThemeContext.Provider>;
}

function useThemeContext(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (ctx === null) {
    throw new Error('useTheme must be used inside <ThemeProvider>');
  }
  return ctx;
}

/** The active theme. Every component reads its colours and sizes here. */
export function useTheme(): Theme {
  return useThemeContext().theme;
}

/** The technician's chosen mode and the setter — for the Settings screen. */
export function useThemeMode(): { mode: ThemeMode; setMode: (mode: ThemeMode) => void } {
  const { mode, setMode } = useThemeContext();
  return { mode, setMode };
}

/** FF-51 *Bigger text* — on or off, and the setter. */
export function useBiggerText(): { biggerText: boolean; setBiggerText: (on: boolean) => void } {
  const { biggerText, setBiggerText } = useThemeContext();
  return { biggerText, setBiggerText };
}
