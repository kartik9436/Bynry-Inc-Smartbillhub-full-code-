/**
 * Mounts the real navigation tree, inside the real theme, i18n and session
 * providers, the way `App.tsx` does — under a `NavigationContainer` with a ref
 * so a test can ask which screen is showing.
 *
 * `fieldData` and `gettingIn` are what a screen test passes for the store and
 * the server ports (`screens/theDay/fieldData.tsx`, `screens/gettingIn/
 * gettingInServices.tsx`); left out, the screens see what the app sees today —
 * no store, and every server port refusing with its gap.
 */
import { createNavigationContainerRef, NavigationContainer, type ParamListBase } from '@react-navigation/native';
import { render } from '@testing-library/react-native';
import { type ReactElement } from 'react';

import { createFieldI18n } from '../../src/i18n/i18n';
import { I18nProvider } from '../../src/i18n/I18nProvider';
import { AppNavigator } from '../../src/navigation/AppNavigator';
import { ShellStatusProvider, type ShellStatusValue, UNKNOWN_STATUS } from '../../src/navigation/ShellStatus';
import { type GettingInServices, GettingInProvider } from '../../src/screens/gettingIn/gettingInServices';
import { type FieldData, FieldDataProvider } from '../../src/screens/theDay/fieldData';
import { SessionProvider } from '../../src/session/SessionProvider';
import { ThemeProvider, type ThemeMode } from '../../src/theme';
import { makeHandset, signIn, TENANT } from '../session/fakes';

export interface MountOptions {
  tablet?: boolean;
  signedIn?: boolean;
  status?: ShellStatusValue;
  theme?: ThemeMode;
  fieldData?: Partial<FieldData>;
  gettingIn?: Partial<GettingInServices>;
  handset?: ReturnType<typeof makeHandset>;
  /** Wraps the NavigationContainer (a test's own provider, e.g. a wave's ports). */
  wrap?: (ui: ReactElement) => ReactElement;
}

export async function mountApp(options: MountOptions = {}) {
  const h = options.handset ?? makeHandset();
  if (options.signedIn ?? true) await signIn(h.session, 'd.ortiz');
  const fieldI18n = createFieldI18n({ language: 'en' });
  const ref = createNavigationContainerRef<ParamListBase>();
  const wrap = options.wrap ?? ((ui: ReactElement) => ui);
  // The app mounts a ThemeProvider at its root (App.tsx); a built screen reads
  // `useTheme()`, which throws outside one.
  const ui: ReactElement = (
    <ThemeProvider initialMode={options.theme ?? 'light'}>
      <I18nProvider fieldI18n={fieldI18n} prefs={h.prefs}>
        <SessionProvider manager={h.session}>
          <GettingInProvider value={{ api: h.api, tenant: TENANT, ...options.gettingIn }}>
            <FieldDataProvider value={options.fieldData ?? {}}>
              <ShellStatusProvider value={options.status ?? UNKNOWN_STATUS}>
                {wrap(
                  <NavigationContainer ref={ref}>
                    <AppNavigator tablet={options.tablet ?? false} />
                  </NavigationContainer>,
                )}
              </ShellStatusProvider>
            </FieldDataProvider>
          </GettingInProvider>
        </SessionProvider>
      </I18nProvider>
    </ThemeProvider>
  );
  const utils = render(ui);
  return { ...utils, ref, handset: h, fieldI18n };
}
