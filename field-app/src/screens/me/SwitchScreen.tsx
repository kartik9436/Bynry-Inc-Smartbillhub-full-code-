/**
 * The Switch technician sheet (`SWITCH`; T-25; image `phone/Switch.png`).
 *
 * The phone changes hands. What the drawing says first is the guarantee:
 * *Your 3 jobs stay on this phone. They send under your name.* (R64,
 * E2E-21). Then who is handing over, and who is next — everyone this handset
 * has seen sign in, and *Someone else*.
 *
 * A PASSWORD, ALWAYS (Security §3; `SessionManager.switchTo`): biometric only
 * ever returns you to your own session, so this sheet asks for the next
 * person's password whoever they are, and *Hand over* is disabled until one
 * is typed. Someone new also types their technician ID — the one place the
 * sheet types, because a person cannot be chosen from a list they are not on.
 *
 * Nothing the current technician captured is touched: `switchTo` and
 * `signIn` never reach the outbox.
 */
import { useNavigation } from '@react-navigation/native';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, View } from 'react-native';

import { AppText, Avatar, Button, Field, FieldGroup, Kicker, Notice } from '../../components';
import { useOptionalSession } from '../../session/SessionProvider';
import type { UnsentSummary } from '../../session/sessionManager';
import { useTheme } from '../../theme';
import { MeSheetScreen } from './MeScreen';

const SOMEONE_ELSE = '__someone_else__';

function Person(props: { name: string; detail?: string; selected: boolean; onPress: () => void; literal?: boolean; testID: string }) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityLabel={props.detail ? `${props.name}, ${props.detail}` : props.name}
      accessibilityState={{ checked: props.selected }}
      onPress={props.onPress}
      testID={props.testID}
      style={{
        minHeight: theme.touch.primary,
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[3],
        padding: theme.space[3],
        borderWidth: props.selected ? theme.borderWidth.emphasis : theme.borderWidth.control,
        borderColor: props.selected ? c.text : c.controlBorder,
        borderRadius: theme.radius.md,
        backgroundColor: props.selected ? c.surface : c.card,
      }}
    >
      <Avatar name={props.literal ? '+' : props.name} literal={props.literal} />
      <View style={{ flexShrink: 1 }}>
        <AppText variant="body" weight={props.selected ? 'heavy' : 'regular'}>
          {props.name}
        </AppText>
        {props.detail ? (
          <AppText variant="label" tone="muted">
            {props.detail}
          </AppText>
        ) : null}
      </View>
    </Pressable>
  );
}

export function SwitchScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNavigation();
  const session = useOptionalSession();
  const [next, setNext] = useState<string | null>(null);
  const [login, setLogin] = useState('');
  const [password, setPassword] = useState('');
  const [problem, setProblem] = useState(false);
  const [busy, setBusy] = useState(false);
  const [unsent, setUnsent] = useState<UnsentSummary | null>(null);

  const snap = session?.snapshot;
  const active = snap?.active ?? null;
  const others = (snap?.known ?? []).filter((k) => k.technicianId !== active?.technicianId);

  useEffect(() => {
    let live = true;
    session?.manager.unsentSummary().then(
      (s) => live && setUnsent(s),
      () => live && setUnsent(null),
    );
    return () => {
      live = false;
    };
  }, [session]);

  async function handOver() {
    if (!session || !active || !next || password === '') return;
    setBusy(true);
    setProblem(false);
    try {
      if (next === SOMEONE_ELSE) {
        await session.manager.signIn({ tenant: active.tenant, login: login.trim(), password });
      } else {
        await session.manager.switchTo(next, password);
      }
      setPassword('');
      navigation.goBack();
    } catch {
      setProblem(true);
    } finally {
      setBusy(false);
    }
  }

  const mine = unsent?.mine ?? null;
  const canHand = next != null && password !== '' && (next !== SOMEONE_ELSE || login.trim() !== '');

  return (
    <MeSheetScreen
      id="SWITCH"
      title={t('field.screen.switch')}
      footer={
        <View style={{ flexDirection: 'row', gap: theme.touch.clear }}>
          <Button grow onPress={() => navigation.goBack()} testID="switch-cancel">
            {t('field.me.cancel')}
          </Button>
          <Button grow variant="primary" onPress={handOver} disabled={!canHand} busy={busy} testID="switch-hand-over">
            {t('field.switch.handOver')}
          </Button>
        </View>
      }
    >
      {mine && (mine.items > 0 || mine.photos > 0) ? (
        <Notice tone="success" testID="switch-stays">
          {`${t('field.switch.stays', { items: mine.items, photos: mine.photos })} ${t('field.ff53.underYourName')}`}
        </Notice>
      ) : null}
      {active ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }} testID="switch-current">
          <Avatar name={active.displayName} />
          <View style={{ flexShrink: 1 }}>
            <AppText variant="body" weight="heavy">
              {active.displayName}
            </AppText>
            {mine ? (
              <AppText variant="label" tone="muted">
                {t('field.ff53.toSend', { items: mine.items, photos: mine.photos })}
              </AppText>
            ) : null}
          </View>
        </View>
      ) : null}
      <Kicker>{t('field.switch.next')}</Kicker>
      <View accessibilityRole="radiogroup" accessibilityLabel={t('field.switch.next')} style={{ gap: theme.touch.clear }}>
        {others.map((k) => (
          <Person
            key={k.technicianId}
            name={k.displayName}
            selected={next === k.technicianId}
            onPress={() => setNext(k.technicianId)}
            testID={`switch-to-${k.technicianId}`}
          />
        ))}
        <Person
          name={t('field.switch.someoneElse')}
          literal
          selected={next === SOMEONE_ELSE}
          onPress={() => setNext(SOMEONE_ELSE)}
          testID="switch-someone-else"
        />
      </View>
      {next ? (
        <FieldGroup>
          {next === SOMEONE_ELSE ? (
            <Field label={t('field.signIn.login')} value={login} onChangeText={setLogin} keyboardType="email-address" autoCapitalize="none" autoCorrect={false} testID="switch-login" />
          ) : null}
          <Field label={t('field.switch.password')} value={password} onChangeText={setPassword} secure testID="switch-password" />
        </FieldGroup>
      ) : null}
      {problem ? (
        <Notice tone="danger" testID="switch-problem">
          {t('field.switch.wrong')}
        </Notice>
      ) : null}
    </MeSheetScreen>
  );
}
