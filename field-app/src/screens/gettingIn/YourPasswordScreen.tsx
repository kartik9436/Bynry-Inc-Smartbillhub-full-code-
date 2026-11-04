/**
 * FF-57 Your password (T-15; US-FLD-070). Built from `wireframes/phone/
 * FF-57-your-password.png` and `tablet/FF-57-T-your-password.png`.
 *
 * As drawn: the green *Code accepted.* note with who the account is for
 * (*Dana Ortiz · Field Technician · Lone Star Water*); CHOOSE A PASSWORD with
 * three checks under it — *At least ten characters*, *Not a password you have
 * used before*, *Type it once more*; ONCE MORE; THIS DEVICE (*Registered as
 * Van 14 tablet.*); and *Save and sign in*, grey until it can be pressed.
 *
 * THE CHECKS, and whose each one is:
 *  - the length is the UTILITY's minimum, from the server's answer on FF-56
 *    (`passwordMinLength`: 8 · 10 · 12), never a number in this file;
 *  - *Type it once more* is the handset's (`checkNewPassword`);
 *  - *Not a password you have used before* is the SERVER's — the handset
 *    cannot know your old passwords — so it is drawn as the server's check,
 *    never ticked here; a refusal comes back on save.
 *
 * THE DEVICE NAME is what the office sees in its list and signs out by (R105,
 * R115). Read from the device register; when the handset has none yet, the
 * technician types it here (the board shows it already named).
 *
 * ON SAVE: `completeActivation` (the server sets the password, registers the
 * device by name — `activation-complete`, a `ServerGapError` today), then a
 * normal sign-in with the new password through the session, so the handset
 * holds its session exactly as after FF-05. ⚠ The session manager cannot take
 * the activation's own sign-in answer (it has no "adopt" call), so this signs
 * in a second time with the WORK EMAIL as the login — whether a technician's
 * login is their email is the server's to confirm when it builds the route;
 * reported.
 *
 * ⚠ **THE UTILITY COMES FROM FF-56, NOT FROM THE HANDSET (`DEF-FLD-10580`).**
 * FF-56 looked the code up and passes the utility it names (`tenant`,
 * `utilityName`); this screen completes against THAT utility and, once the
 * password is set, REMEMBERS it on the handset (`security/handsetUtility.ts`)
 * with the email as the last login, so FF-05 signs in there from then on. A
 * handset that used to sign in somewhere else is simply moved — each utility's
 * work stays in its own database file (R131).
 */
import { useNavigation, useRoute } from '@react-navigation/native';
import { useEffect, useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Text } from 'react-native';

import { Button, Card, CheckRow, Field, Notice, Page } from '../../components';
import { textStyle } from '../../components/AppText';
import type { ActivationCheck } from '../../security/authApi';
import { checkNewPassword, completeActivation, PasswordNotAcceptedError } from '../../security/activation';
import { useOptionalSession } from '../../session/SessionProvider';
import { useTheme } from '../../theme';
import { openScreen } from '../theDay/go';
import { ScreenBoundary } from '../theDay/ScreenBoundary';
import { useGettingIn } from './gettingInServices';
import { failureKey } from './signInErrors';

function YourPasswordBody() {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const route = useRoute();
  const params = (route.params ?? {}) as {
    check?: ActivationCheck;
    email?: string;
    tenant?: string;
    utilityName?: string;
  };
  const check = params.check ?? null;
  const session = useOptionalSession();
  const { api, deviceName, deviceId, utility } = useGettingIn();
  const tenant = params.tenant ?? null;
  const [password, setPassword] = useState('');
  const [again, setAgain] = useState('');
  const [name, setName] = useState<string | null>(null);
  const [typedName, setTypedName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useLayoutEffect(() => {
    navigation.setOptions({ title: t('field.yourPassword.title') });
  }, [navigation, t]);

  useEffect(() => {
    let live = true;
    deviceName()
      .then((n) => {
        if (live) setName(n);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [deviceName]);

  if (!check) {
    return (
      <Page testID="screen-FF-57">
        <Notice tone="warning" testID="your-password-no-code">
          {t('field.yourPassword.noCode')}
        </Notice>
        <Button onPress={() => openScreen(navigation, 'FF-56')} testID="door-FF-56">
          {t('field.yourPassword.backToCode')}
        </Button>
      </Page>
    );
  }

  const rules = checkNewPassword(password, again, check.passwordMinLength);
  const device = name ?? typedName.trim();
  const ready = rules.ok && device !== '' && !busy;

  const save = async () => {
    if (!tenant || !session) {
      setError('field.signIn.error.noUtility');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await completeActivation(api, {
        tenant,
        check,
        password,
        again,
        deviceId: await deviceId(),
        deviceName: device,
      });
      // The utility is this handset's from now on — before the sign-in, so the
      // gate already names it if the sign-in itself is refused.
      utility.remember({ tenant, utilityName: params.utilityName || check.utilityName || null });
      if (params.email) utility.rememberLogin(tenant, params.email);
      await session.manager.signIn({ tenant, login: params.email ?? '', password });
      // Signed in: the gate unmounts and the app opens on FF-07 → FF-08.
    } catch (err) {
      setError(err instanceof PasswordNotAcceptedError ? 'field.yourPassword.error.rules' : failureKey(err));
      setBusy(false);
    }
  };

  return (
    <Page
      testID="screen-FF-57"
      footer={
        <Button variant="primary" grow disabled={!ready} busy={busy} onPress={() => void save()} testID="door-FF-07">
          {t('field.yourPassword.save')}
        </Button>
      }
    >
      <Notice tone="success" testID="your-password-accepted">
        {t('field.yourPassword.accepted', { name: check.displayName, role: check.roleLabel, utility: check.utilityName })}
      </Notice>
      <Card title={t('field.yourPassword.choose')}>
        <Field
          label={t('field.yourPassword.password')}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          textContentType="newPassword"
          testID="your-password-new"
        />
        <CheckRow
          state={rules.longEnough ? 'done' : 'waiting'}
          stateLabel={t(rules.longEnough ? 'field.yourPassword.met' : 'field.yourPassword.notYet')}
          label={t('field.yourPassword.minLength', { n: check.passwordMinLength })}
          testID="your-password-rule-length"
        />
        <CheckRow
          state="waiting"
          stateLabel={t('field.yourPassword.serverChecks')}
          label={t('field.yourPassword.notReused')}
          testID="your-password-rule-reuse"
        />
        <CheckRow
          state={rules.matches ? 'done' : 'waiting'}
          stateLabel={t(rules.matches ? 'field.yourPassword.met' : 'field.yourPassword.notYet')}
          label={t('field.yourPassword.typeAgain')}
          testID="your-password-rule-match"
        />
        <Field
          label={t('field.yourPassword.onceMore')}
          value={again}
          onChangeText={setAgain}
          secureTextEntry
          autoCapitalize="none"
          autoCorrect={false}
          textContentType="newPassword"
          error={again !== '' && !rules.matches ? t('field.yourPassword.mismatch') : undefined}
          testID="your-password-again"
        />
      </Card>
      <Card title={t('field.yourPassword.thisDevice')}>
        {name ? (
          <Text style={textStyle(theme, 'body')} testID="your-password-device">
            {t('field.yourPassword.registeredAs')} <Text style={textStyle(theme, 'body', 'heavy')}>{name}</Text>
          </Text>
        ) : (
          <Field
            label={t('field.yourPassword.deviceName')}
            value={typedName}
            onChangeText={setTypedName}
            help={t('field.yourPassword.deviceHelp')}
            testID="your-password-device-name"
          />
        )}
      </Card>
      {error ? (
        <Notice tone="danger" testID="your-password-error">
          {t(error)}
        </Notice>
      ) : null}
    </Page>
  );
}

export function YourPasswordScreen() {
  return (
    <ScreenBoundary screen="FF-57">
      <YourPasswordBody />
    </ScreenBoundary>
  );
}
