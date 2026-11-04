/**
 * Mounting a day screen the way the app mounts it: the real navigation tree
 * (`tests/navigation/harness.tsx` — never a bare component, hard-won law 2's
 * fixture lesson), Dana signed in, her day in a real store, and the screen
 * opened by its ADDRESS through the same `openScreen` the app's buttons use.
 */
import { act, screen } from '@testing-library/react-native';
import { StyleSheet } from 'react-native';

import { focusedLeaf } from '../../../src/navigation/routing';
import { type ScreenId } from '../../../src/navigation/screens';
import { type FieldData } from '../../../src/screens/theDay/fieldData';
import { openScreen } from '../../../src/screens/theDay/go';
import type { ThemeName } from '../../../src/theme';
import { mountApp, type MountOptions } from '../../navigation/harness';
import { NOW, seedDay } from './dayFixture';

export type App = Awaited<ReturnType<typeof mountApp>>;

export async function mountDay(
  options: Omit<MountOptions, 'fieldData'> & { fieldData?: Partial<FieldData>; noStore?: boolean; theme?: ThemeName } = {},
): Promise<App & { db: ReturnType<typeof seedDay> | null }> {
  const db = options.noStore ? null : seedDay();
  const app = await mountApp({ ...options, fieldData: { db, now: () => NOW, ...options.fieldData } });
  await screen.findByTestId('screen-FF-63');
  return Object.assign(app, { db });
}

export async function open(app: App, id: ScreenId, params?: object): Promise<void> {
  await act(async () => {
    openScreen(app.ref, id, params);
  });
}

/** The screen on show, by its route name. */
export function current(app: App): string | undefined {
  return app.ref.getCurrentRoute()?.name;
}

/** The params the screen on show was opened with. */
export function currentParams(app: App): Record<string, unknown> | undefined {
  return app.ref.getCurrentRoute()?.params as Record<string, unknown> | undefined;
}

/** Is the drawer (FF-09) open, from the navigation state itself. */
export function drawerOpen(app: App): boolean {
  return JSON.stringify(app.ref.getRootState()).includes('"status":"open"');
}

export { focusedLeaf };

/** Every button in `root` is named and at least 48pt (B14 rule 45, R39). Returns how many were checked. */
export function assertTouchTargets(nodes: ReturnType<typeof screen.getAllByRole>): number {
  let checked = 0;
  for (const el of nodes) {
    const style = (StyleSheet.flatten(el.props.style) ?? {}) as Record<string, unknown>;
    const h = Number(style.minHeight ?? style.height ?? 0);
    const label = String(el.props.accessibilityLabel ?? '');
    if (label === '' || h < 48) {
      throw new Error(`control "${label}" (${el.props.testID ?? 'no testID'}) is ${h}pt or unnamed`);
    }
    checked += 1;
  }
  return checked;
}
