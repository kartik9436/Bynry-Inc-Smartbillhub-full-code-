/**
 * Mounts a job screen UNDER THE REAL NAVIGATION — the same providers and tree
 * `App.tsx` builds, plus the job services and a theme — and opens it the way
 * the app does, by address, so a door that goes to the wrong route fails here
 * (hard-won law 2's fixture lesson: never mount a routed component bare).
 */
import { CommonActions, createNavigationContainerRef, NavigationContainer, type ParamListBase } from '@react-navigation/native';
import { act, render, screen } from '@testing-library/react-native';
import { type ReactElement } from 'react';

import { createFieldI18n } from '../../../src/i18n/i18n';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AppNavigator } from '../../../src/navigation/AppNavigator';
import { routeTo } from '../../../src/navigation/routing';
import type { ScreenId } from '../../../src/navigation/screens';
import { ShellStatusProvider, UNKNOWN_STATUS } from '../../../src/navigation/ShellStatus';
import { JobPortProvider, type JobServices } from '../../../src/screens/theJob/JobPort';
import { SessionProvider } from '../../../src/session/SessionProvider';
import { ThemeProvider, type ThemeName } from '../../../src/theme';
import { makeHandset, signIn } from '../../session/fakes';
import { setTablet } from './window';

export async function mountJob(
  services: JobServices,
  at: ScreenId,
  options: { theme?: ThemeName; tablet?: boolean; params?: Record<string, unknown>; openJob?: string | null } = {},
) {
  // The window the screens measure (`window.ts`; each test file mocks the hook).
  const tablet = options.tablet ?? false;
  setTablet(tablet);
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  const fieldI18n = createFieldI18n({ language: 'en' });
  const ref = createNavigationContainerRef<ParamListBase>();
  const ui: ReactElement = (
    <I18nProvider fieldI18n={fieldI18n} prefs={h.prefs}>
      <SessionProvider manager={h.session}>
        <ThemeProvider initialMode={options.theme ?? 'light'}>
          <ShellStatusProvider value={{ ...UNKNOWN_STATUS, syncPending: 12 }}>
            <JobPortProvider services={services} initialJobId={options.openJob === undefined ? 'wo-4822' : options.openJob}>
              <NavigationContainer ref={ref}>
                <AppNavigator tablet={tablet} />
              </NavigationContainer>
            </JobPortProvider>
          </ShellStatusProvider>
        </ThemeProvider>
      </SessionProvider>
    </I18nProvider>
  );
  const utils = render(ui);
  await screen.findByTestId('screen-FF-63');
  await go(ref, at, options.params);
  return { ...utils, ref };
}

/** Navigate by address, with params when given, and wait for the screen. */
export async function go(
  ref: ReturnType<typeof createNavigationContainerRef<ParamListBase>>,
  at: ScreenId,
  params?: Record<string, unknown>,
) {
  const target = routeTo(at);
  const nested = target.params as { screen: string; params?: { screen: string } };
  const withParams = params ? { ...nested, params: { ...(nested.params ?? {}), params } } : nested;
  await act(async () => {
    ref.dispatch(CommonActions.navigate(target.name, withParams));
  });
  return screen.getAllByTestId(`screen-${at}`).at(-1);
}

/** The screen on top. */
export function onTop(id: ScreenId) {
  const el = screen.getAllByTestId(`screen-${id}`).at(-1);
  if (!el) throw new Error(`${id} is not mounted`);
  return el;
}
