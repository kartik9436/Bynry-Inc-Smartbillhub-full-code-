/**
 * FF-06 Forgot password — *Locked out?* (T-15; US-FLD-032 TC-2). Built from
 * `wireframes/phone/FF-06-forgot-password.png` and its tablet board.
 *
 * ⚠ THERE IS NO INPUT BOX ON THIS SCREEN, ON PURPOSE (R38: a technician taps,
 * never types). It is a call-or-ask screen: three choices drawn as cards —
 * *Text me a code* (*(512) 555-••42*), *Call the office* (*(512) 555-0100*),
 * *Ask the office to reset* (*They text you a new one*) — the *Signing in
 * as D. Ortiz · Silver Creek Water* card, and one button whose words follow
 * the choice (*Send the code* · *Call the office* · *Ask the office*).
 *
 * The technician's ID comes from what they typed on FF-05 (route param
 * `login`); nothing is typed here. The numbers are the SERVER's — the masked
 * one is masked by the server and never unmasked on the handset — and no
 * route answers them yet (`passwordReset.ts`, `ResetGapError`). So each
 * choice says what it can do: *Call the office* rings the number when it is
 * known; the other two say plainly that they are not ready, in place of a
 * success that did not happen.
 */
import { useNavigation, useRoute } from '@react-navigation/native';
import { useEffect, useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, Pressable, Text, View } from 'react-native';

import { AppText, Button, IconCircle, Notice, Page } from '../../components';
import type { GlyphName } from '../../components';
import { textStyle } from '../../components/AppText';
import type { StatusTone } from '../../theme';
import { useTheme } from '../../theme';
import { ScreenBoundary } from '../theDay/ScreenBoundary';
import { useGettingIn, useHandsetTenant } from './gettingInServices';
import { type ResetContacts, ResetGapError, type ResetWay } from './passwordReset';

interface Way {
  id: ResetWay;
  glyph: GlyphName;
  tone: StatusTone;
  titleKey: string;
  actionKey: string;
}

const WAYS: readonly Way[] = [
  { id: 'text', glyph: 'mail', tone: 'info', titleKey: 'field.forgot.text', actionKey: 'field.forgot.sendCode' },
  { id: 'call', glyph: 'phone', tone: 'success', titleKey: 'field.forgot.call', actionKey: 'field.forgot.call' },
  { id: 'ask', glyph: 'message', tone: 'neutral', titleKey: 'field.forgot.ask', actionKey: 'field.forgot.askAction' },
];

type Result = null | 'sent' | 'asked' | 'notReady' | 'noNumber' | 'failed';

/** Every key written out, so the catalogue test can see each one. */
const RESULT_KEY: Record<Exclude<Result, null>, string> = {
  sent: 'field.forgot.result.sent',
  asked: 'field.forgot.result.asked',
  notReady: 'field.forgot.result.notReady',
  noNumber: 'field.forgot.result.noNumber',
  failed: 'field.forgot.result.failed',
};

function WayCard(props: { way: Way; detail: string | null; selected: boolean; onPress: () => void }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const c = theme.colors;
  const title = t(props.way.titleKey);
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityLabel={[title, props.detail].filter(Boolean).join(', ')}
      accessibilityState={{ checked: props.selected }}
      onPress={props.onPress}
      testID={`forgot-${props.way.id}`}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[4],
        minHeight: theme.touch.primary,
        padding: theme.space[4],
        backgroundColor: props.selected ? c.surface : c.card,
        borderColor: props.selected ? c.text : c.border,
        borderWidth: props.selected ? theme.borderWidth.emphasis : theme.borderWidth.card,
        borderRadius: theme.radius.lg,
      }}
    >
      <IconCircle glyph={props.way.glyph} tone={props.way.tone} />
      <View style={{ flexShrink: 1 }}>
        <Text style={textStyle(theme, 'body', 'heavy')}>{title}</Text>
        {props.detail ? <Text style={textStyle(theme, 'label', 'regular', 'muted')}>{props.detail}</Text> : null}
      </View>
    </Pressable>
  );
}

function ForgotBody() {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const route = useRoute();
  const login = ((route.params as { login?: string } | undefined)?.login ?? '').trim();
  const { reset, utilityName } = useGettingIn();
  const tenant = useHandsetTenant();
  const [way, setWay] = useState<ResetWay>('text');
  const [contacts, setContacts] = useState<ResetContacts>({ maskedPhone: null, officePhone: null });
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result>(null);

  useLayoutEffect(() => {
    navigation.setOptions({ title: '' });
  }, [navigation]);

  useEffect(() => {
    if (!tenant || !login) return;
    let live = true;
    reset
      .contacts({ tenant, login })
      .then((c) => {
        if (live) setContacts(c);
      })
      .catch(() => {
        // Not answered yet (`reset-contacts`): the cards show no number.
      });
    return () => {
      live = false;
    };
  }, [reset, tenant, login]);

  const detail = (w: ResetWay): string | null =>
    w === 'text' ? contacts.maskedPhone : w === 'call' ? contacts.officePhone : t('field.forgot.askDetail');

  const act = async () => {
    setResult(null);
    if (way === 'call') {
      if (!contacts.officePhone) {
        setResult('noNumber');
        return;
      }
      void Linking.openURL(`tel:${contacts.officePhone.replace(/[^\d+]/g, '')}`);
      return;
    }
    if (!tenant || !login) {
      setResult('notReady');
      return;
    }
    setBusy(true);
    try {
      if (way === 'text') await reset.textCode({ tenant, login });
      else await reset.askOffice({ tenant, login });
      setResult(way === 'text' ? 'sent' : 'asked');
    } catch (err) {
      setResult(err instanceof ResetGapError ? 'notReady' : 'failed');
    } finally {
      setBusy(false);
    }
  };

  const chosen = WAYS.find((w) => w.id === way) ?? (WAYS[0] as Way);

  return (
    <Page
      surface="card"
      testID="screen-FF-06"
      footer={
        <Button variant="primary" grow busy={busy} onPress={() => void act()} testID="forgot-act">
          {t(chosen.actionKey)}
        </Button>
      }
    >
      <View>
        <AppText variant="title">{t('field.forgot.title')}</AppText>
        <AppText variant="body" tone="muted">
          {t('field.forgot.pick')}
        </AppText>
      </View>
      <View accessibilityRole="radiogroup" accessibilityLabel={t('field.forgot.pick')} style={{ gap: theme.space[3] }}>
        {WAYS.map((w) => (
          <WayCard key={w.id} way={w} detail={detail(w.id)} selected={w.id === way} onPress={() => setWay(w.id)} />
        ))}
      </View>
      {result ? (
        <Notice
          tone={result === 'sent' || result === 'asked' ? 'success' : 'danger'}
          testID={`forgot-result-${result}`}
        >
          {t(RESULT_KEY[result])}
        </Notice>
      ) : null}
      {login ? (
        <View
          style={{ backgroundColor: theme.colors.surface, padding: theme.space[4], borderRadius: theme.radius.lg }}
          testID="forgot-who"
        >
          <AppText variant="label" weight="semibold">
            {t('field.forgot.signingInAs')}
          </AppText>
          <AppText variant="section">{login}</AppText>
          {utilityName ? (
            <AppText variant="label" tone="muted">
              {utilityName}
            </AppText>
          ) : null}
        </View>
      ) : null}
      <Button size="sm" onPress={() => navigation.goBack()} testID="door-FF-05">
        {t('field.forgot.back')}
      </Button>
    </Page>
  );
}

export function ForgotPasswordScreen() {
  return (
    <ScreenBoundary screen="FF-06">
      <ForgotBody />
    </ScreenBoundary>
  );
}
