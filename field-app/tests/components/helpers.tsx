import { render, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { StyleSheet } from 'react-native';

import { ThemeProvider, THEMES } from '../../src/theme';
import type { Theme, ThemeName } from '../../src/theme';

/** A host element as RNTL returns it (react-test-renderer ships no types). */
export type ReactTestInstance = ReturnType<typeof screen.getByText>;

export const THEME_NAMES: ThemeName[] = ['light', 'dark', 'sunlight'];

/** Render inside a real ThemeProvider pinned to one theme. */
export function renderIn(name: ThemeName, ui: ReactElement) {
  return render(<ThemeProvider initialMode={name}>{ui}</ThemeProvider>);
}

export function themeOf(name: ThemeName): Theme {
  return THEMES[name];
}

/** The flattened style of a host element. */
export function styleOf(el: ReactTestInstance): Record<string, unknown> {
  return (StyleSheet.flatten(el.props.style) ?? {}) as Record<string, unknown>;
}

/** The touch height of a host element: its minHeight or height. */
export function touchHeight(el: ReactTestInstance): number {
  const s = styleOf(el);
  return Number(s.minHeight ?? s.height ?? 0);
}
