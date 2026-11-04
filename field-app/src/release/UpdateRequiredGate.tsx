/**
 * *Update the app* — the one blocking screen a too-old build shows when the
 * server refuses it (`app_too_old`, DEF-FLD-10355; `appUpdate.ts`).
 *
 * No board draws it (the wireframe index has no such screen), so it is built
 * from the kit alone — B14 rules 44/45: the native type ramp, the theme's
 * spacing and the 56pt primary button — and its words are B14 rule 33's caps:
 * a 3-word title, two 6-word facts, a 3-word button. Why the build is refused
 * is rationale and is NOT on screen.
 *
 * The button opens the store for this platform. While that address is empty
 * (`stores.ts`, the PO's to supply) the screen shows the instruction instead,
 * never a button that opens nothing.
 *
 * It replaces the navigator and is not dismissable. It is mounted INSIDE
 * `FieldRuntime` (App.tsx), so the runtime above it keeps its store and its
 * schedule and captured work goes on draining while the server accepts it
 * (07-endpoints §0 rule 2).
 */
import { type ReactNode, useEffect, useState } from 'react';
import { Linking, Platform, View } from 'react-native';
import { useTranslation } from 'react-i18next';

import { AppText } from '../components/AppText';
import { Button } from '../components/Button';
import { useTheme } from '../theme';
import { appUpdate as defaultSignal, type UpdateSignal, type UpdateState } from './appUpdate';
import { versionLabel } from './build';
import { FIELD_APP_STORE_URLS, type StoreUrls, storeUrlFor } from './stores';

export interface UpdateRequiredScreenProps {
  minimum: string | null;
  storeUrl: string | null;
  openUrl?: (url: string) => void;
}

export function UpdateRequiredScreen({ minimum, storeUrl, openUrl }: UpdateRequiredScreenProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const open = openUrl ?? ((url: string) => void Linking.openURL(url));
  return (
    <View
      testID="update-required"
      accessibilityRole="alert"
      style={{
        flex: 1,
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: theme.colors.page,
        paddingHorizontal: theme.space[6],
        gap: theme.space[3],
      }}
    >
      <AppText variant="title" style={{ textAlign: 'center' }}>
        {t('field.update.title')}
      </AppText>
      <AppText variant="body" style={{ textAlign: 'center' }}>
        {t('field.update.tooOld')}
      </AppText>
      <AppText variant="body" tone="muted" style={{ textAlign: 'center' }}>
        {t('field.update.workKept')}
      </AppText>
      {minimum ? (
        <AppText variant="label" tone="muted" style={{ textAlign: 'center' }} testID="update-required-minimum">
          {t('field.update.needs', { minimum })}
        </AppText>
      ) : null}
      <View style={{ alignSelf: 'stretch', marginTop: theme.space[3] }}>
        {storeUrl ? (
          <Button variant="primary" onPress={() => open(storeUrl)} testID="update-required-store">
            {t('field.update.openStore')}
          </Button>
        ) : (
          <AppText variant="body" style={{ textAlign: 'center' }} testID="update-required-instruction">
            {t('field.update.fromStore')}
          </AppText>
        )}
      </View>
      <AppText variant="micro" tone="muted" style={{ textAlign: 'center' }} testID="update-required-version">
        {versionLabel(t)}
      </AppText>
    </View>
  );
}

export function useUpdateState(signal: UpdateSignal = defaultSignal): UpdateState {
  const [state, setState] = useState<UpdateState>(signal.get());
  useEffect(() => {
    setState(signal.get());
    return signal.subscribe(setState);
  }, [signal]);
  return state;
}

export interface UpdateRequiredGateProps {
  children: ReactNode;
  signal?: UpdateSignal;
  platform?: string;
  urls?: StoreUrls;
  openUrl?: (url: string) => void;
}

/** The app below, or — once a call met `app_too_old` — the *Update the app* screen in its place. */
export function UpdateRequiredGate({ children, signal, platform, urls, openUrl }: UpdateRequiredGateProps) {
  const state = useUpdateState(signal);
  if (!state.required) return <>{children}</>;
  return (
    <UpdateRequiredScreen
      minimum={state.minimum}
      storeUrl={storeUrlFor(platform ?? Platform.OS, urls ?? FIELD_APP_STORE_URLS)}
      openUrl={openUrl}
    />
  );
}
