/**
 * FF-07 Permissions — *Three permissions* (T-15). Built from `wireframes/
 * phone/FF-07-permissions.png` and its tablet board: one card per permission,
 * each with what it is used for, and its state — *ALLOWED* in green, or for
 * notifications switched off the card goes red with *Off. You will miss
 * emergencies.* and *Open settings* — then *Continue* at the foot.
 *
 * It is the first screen after a sign-in from the gate, before FF-08
 * (`navigation/AppNavigator.tsx`). *Continue* never waits on a permission:
 * each one only costs the feature it serves, and the card says which.
 *
 * The states come from `permissions.ts`. ⚠ With no platform package
 * installed every state is UNKNOWN, and the card says *Not checked* with
 * *Open settings* — never ALLOWED for a permission nobody read.
 */
import { CommonActions, useNavigation } from '@react-navigation/native';
import { useCallback, useEffect, useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AppState, View } from 'react-native';

import { AppText, Button, IconCircle, Page, StatusChip } from '../../components';
import type { GlyphName } from '../../components';
import { useTheme } from '../../theme';
import { ScreenBoundary } from '../theDay/ScreenBoundary';
import { useGettingIn } from './gettingInServices';
import { PERMISSIONS, type PermissionKind, type PermissionState } from './permissions';

const LOOK: Record<PermissionKind, { glyph: GlyphName; titleKey: string; useKey: string }> = {
  location: { glyph: 'pin', titleKey: 'field.permissions.location', useKey: 'field.permissions.locationUse' },
  camera: { glyph: 'camera', titleKey: 'field.permissions.camera', useKey: 'field.permissions.cameraUse' },
  notifications: { glyph: 'bell', titleKey: 'field.permissions.notifications', useKey: 'field.permissions.notificationsUse' },
};

function PermissionCard(props: {
  kind: PermissionKind;
  state: PermissionState;
  canRequest: boolean;
  onAllow: () => void;
  onSettings: () => void;
}) {
  const theme = useTheme();
  const { t } = useTranslation();
  const c = theme.colors;
  const look = LOOK[props.kind];
  const off = props.state === 'denied';
  const emergency = off && props.kind === 'notifications';
  return (
    <View
      testID={`permission-${props.kind}`}
      style={{
        flexDirection: 'row',
        gap: theme.space[4],
        padding: theme.space[4],
        backgroundColor: c.card,
        borderColor: emergency ? c.status.danger.rule : c.border,
        borderWidth: emergency ? theme.borderWidth.emphasis : theme.borderWidth.card,
        borderRadius: theme.radius.lg,
      }}
    >
      <IconCircle glyph={look.glyph} tone={emergency ? 'danger' : 'success'} />
      <View style={{ flexGrow: 1, flexShrink: 1, gap: theme.space[2] }}>
        <View>
          <AppText variant="section">{t(look.titleKey)}</AppText>
          <AppText variant="body" tone="muted">
            {t(look.useKey)}
          </AppText>
        </View>
        {props.state === 'granted' ? (
          <StatusChip tone="success" testID={`permission-${props.kind}-allowed`}>
            {t('field.permissions.allowed')}
          </StatusChip>
        ) : (
          <>
            {emergency ? (
              <AppText variant="body" weight="heavy" tone="danger" testID="permission-notifications-off">
                {t('field.permissions.missEmergencies')}
              </AppText>
            ) : off ? (
              <StatusChip tone="warning">{t('field.permissions.off')}</StatusChip>
            ) : (
              <StatusChip tone="neutral" testID={`permission-${props.kind}-unknown`}>
                {t('field.permissions.notChecked')}
              </StatusChip>
            )}
            {props.state === 'unknown' && props.canRequest ? (
              <Button size="sm" onPress={props.onAllow} testID={`permission-${props.kind}-allow`}>
                {t('field.permissions.allow')}
              </Button>
            ) : (
              <Button
                size="sm"
                variant={emergency ? 'danger' : 'secondary'}
                onPress={props.onSettings}
                testID={`permission-${props.kind}-settings`}
              >
                {t('field.permissions.openSettings')}
              </Button>
            )}
          </>
        )}
      </View>
    </View>
  );
}

function PermissionsBody() {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const { permissions } = useGettingIn();
  const [states, setStates] = useState<Record<PermissionKind, PermissionState>>({
    location: 'unknown',
    camera: 'unknown',
    notifications: 'unknown',
  });

  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  const read = useCallback(async () => {
    const entries = await Promise.all(PERMISSIONS.map(async (kind) => [kind, await permissions.status(kind)] as const));
    setStates(Object.fromEntries(entries) as Record<PermissionKind, PermissionState>);
  }, [permissions]);

  useEffect(() => {
    void read();
    // Coming back from the phone's settings re-reads every state.
    const sub = AppState.addEventListener('change', (s) => {
      if (s === 'active') void read();
    });
    return () => sub.remove();
  }, [read]);

  const allow = async (kind: PermissionKind) => {
    const state = await permissions.request(kind);
    setStates((prev) => ({ ...prev, [kind]: state }));
  };

  return (
    <Page
      testID="screen-FF-07"
      footer={
        <Button
          variant="primary"
          grow
          onPress={() => navigation.dispatch(CommonActions.navigate('FF-08'))}
          testID="door-FF-08"
        >
          {t('field.permissions.continue')}
        </Button>
      }
    >
      <View style={{ paddingVertical: theme.space[4] }}>
        <AppText variant="title">{t('field.permissions.title')}</AppText>
        <AppText variant="body" tone="muted">
          {t('field.permissions.subtitle')}
        </AppText>
      </View>
      {PERMISSIONS.map((kind) => (
        <PermissionCard
          key={kind}
          kind={kind}
          state={states[kind]}
          canRequest={permissions.canRequest}
          onAllow={() => void allow(kind)}
          onSettings={() => void permissions.openSettings()}
        />
      ))}
    </Page>
  );
}

export function PermissionsScreen() {
  return (
    <ScreenBoundary screen="FF-07">
      <PermissionsBody />
    </ScreenBoundary>
  );
}
