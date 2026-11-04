/**
 * The phone as `session/FieldRuntime.tsx` builds it: the job services
 * (`JobPortProvider`) AND the on-site data (`FieldDataProvider`) both above
 * the REAL navigator, over one handset store — so a door from a job screen to
 * an on-site or closing screen is tested across the seam DEF-FLD-10578 broke.
 * No job is pre-set in the port: a job is opened by address, the way Today's
 * card opens it (`openJob`), and later screens know it only the way the app
 * does.
 */
import { CommonActions, createNavigationContainerRef, NavigationContainer, type ParamListBase } from '@react-navigation/native';
import { act, fireEvent, render, screen, within } from '@testing-library/react-native';
import { type ReactElement } from 'react';

import { createFieldI18n } from '../../../src/i18n/i18n';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AppNavigator } from '../../../src/navigation/AppNavigator';
import { routeTo } from '../../../src/navigation/routing';
import type { ScreenId } from '../../../src/navigation/screens';
import { UNKNOWN_STATUS, ShellStatusProvider } from '../../../src/navigation/ShellStatus';
import { type FieldData, FieldDataProvider } from '../../../src/screens/onSite/fieldData';
import { JobPortProvider, type JobServices } from '../../../src/screens/theJob/JobPort';
import { SessionProvider } from '../../../src/session/SessionProvider';
import { ThemeProvider } from '../../../src/theme';
import { makeHandset, signIn } from '../../session/fakes';

export type NavRef = ReturnType<typeof createNavigationContainerRef<ParamListBase>>;

export async function mountPhone(services: JobServices, data: FieldData): Promise<NavRef> {
  const h = makeHandset();
  await signIn(h.session, 'd.ortiz');
  const ref = createNavigationContainerRef<ParamListBase>();
  const ui: ReactElement = (
    <ThemeProvider initialMode="light">
      <I18nProvider fieldI18n={createFieldI18n({ language: 'en' })} prefs={h.prefs}>
        <SessionProvider manager={h.session}>
          <ShellStatusProvider value={UNKNOWN_STATUS}>
            <JobPortProvider services={services}>
              <FieldDataProvider value={data}>
                <NavigationContainer ref={ref}>
                  <AppNavigator tablet={false} />
                </NavigationContainer>
              </FieldDataProvider>
            </JobPortProvider>
          </ShellStatusProvider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>
  );
  render(ui);
  await screen.findByTestId('screen-FF-63');
  return ref;
}

/** Open a screen by its address, with params when given. */
export async function open(ref: NavRef, id: ScreenId, params?: Record<string, unknown>) {
  const target = routeTo(id);
  const nested = target.params as { screen: string; params: { screen: string } };
  await act(async () => {
    ref.dispatch(CommonActions.navigate(target.name, params ? { ...nested, params: { ...nested.params, params } } : nested));
  });
}

export function onTop(id: ScreenId) {
  const el = screen.getAllByTestId(`screen-${id}`).at(-1);
  if (!el) throw new Error(`${id} is not mounted`);
  return el;
}

/** Press a control drawn on the screen on top. */
export function press(from: ScreenId, testID: string) {
  fireEvent.press(within(onTop(from)).getByTestId(testID));
}
