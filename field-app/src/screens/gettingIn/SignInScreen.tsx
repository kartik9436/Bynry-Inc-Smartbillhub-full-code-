/**
 * FF-05 Sign in (T-15; US-FLD-003, -032, -080). Built from `wireframes/
 * phone/FF-05-sign-in.png` and `tablet/FF-05-T-sign-in.png`.
 *
 * As drawn: the brand tile, *Field app* and the utility's name; ONE sign-in
 * field, drawn *Technician ID* and labelled *Email or phone* — ⚠ PO ruling
 * 2026-10-21 (`CR-187-BRC10`): there is NO Technician ID; a technician signs
 * in with their work email OR their phone number, in this one field, and the
 * server tells them apart (`@` → email, else the number in E.164 — see
 * `06-backend/apps/identity/phones.py`). The drawing's SHAPE stands (one field
 * above *Password*); only its words moved. Sent as `identifier`. The keyboard
 * is the email one, which can type digits too; *Password* with *Ask the office to reset it* under it; *Sign in*;
 * *Forgot your password?* (FF-06); *First time here? Activate your account*
 * (FF-56 — R105, the only way in for a new person: there is no sign-up);
 * the banner when someone else's work is waiting on the handset (*R. Patel
 * has 2 to send. They send under their name.* — R25, R64); and at the foot
 * *Staff portal is a different app* and the version (R40).
 *
 * SIGNING IN is `SessionManager.signIn` and nothing else — a password,
 * always. On success the session flips to signed in, the gate unmounts, and
 * the app opens on FF-07 Permissions then FF-08 First sync
 * (`navigation/AppNavigator.tsx`, *after a sign-in from the gate*).
 *
 * THE FAILURE STATES are said in one short line under the form
 * (`signInErrors.ts`): wrong email, phone or password · no signal and never signed in
 * here · the BUILD has no server address (`release/serverAddress.ts`): *No
 * server set*, shown before anything is typed and with *Sign in* off, because
 * no answer can come.
 *
 * ⚠ **WHICH UTILITY — `DEF-FLD-10580` (beta MQ-006), PO 2026-10-24: *"A. The
 * code from the office sets the utility"*.** The app is one build for every
 * utility; the handset remembers the utility its office's code named on FF-56
 * (`security/handsetUtility.ts`). Under the title, where the drawing puts
 * *Silver Creek Water*, this screen says *Signing in to City of Houston ·
 * Change* — *Change* goes back to FF-56 for another utility's code — and the
 * sign-in field starts with the email or phone last used at THAT utility on
 * this handset. A handset with no utility yet says *Activate this phone
 * first.* in that place and *Sign in* stays off: the only way forward is
 * *First time here? Activate*. Nothing is ever guessed and nothing comes from
 * the build (`EXPO_PUBLIC_TENANT` is gone).
 *
 * WHAT IS DRAWN AND NOT BUILT: *Use fingerprint*. Biometrics only ever return
 * a technician to their OWN locked session (Security §3: *"a thumb on a shared
 * tablet is not an identity claim"*); on this screen nobody is signed in, so
 * there is no session for a thumb to return to. It is on the lock cover
 * instead (`LockCover.tsx`).
 */
import { useNavigation } from '@react-navigation/native';
import { useEffect, useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, Text, View } from 'react-native';

import { AppText, Button, Field, FieldGroup, Glyph, Notice } from '../../components';
import { textStyle } from '../../components/AppText';
import { versionLabel } from '../../release/build';
import { useOptionalSession } from '../../session/SessionProvider';
import type { UnsentSummary } from '../../session/sessionManager';
import { useTheme } from '../../theme';
import { openScreen } from '../theDay/go';
import { ScreenBoundary } from '../theDay/ScreenBoundary';
import { BrandMark } from './BrandMark';
import { useGettingIn, useHandsetUtility } from './gettingInServices';
import { failureKey, failureParams } from './signInErrors';

function TextLink(props: { label: string; onPress: () => void; testID: string }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={props.label}
      onPress={props.onPress}
      testID={props.testID}
      style={{ minHeight: theme.touch.control, alignItems: 'center', justifyContent: 'center' }}
    >
      <Text style={textStyle(theme, 'body', 'semibold')}>{props.label}</Text>
    </Pressable>
  );
}

/** *Change* beside the utility's name: a link in the line, still a full-height touch target. */
function InlineLink(props: { label: string; onPress: () => void; testID: string }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={props.label}
      onPress={props.onPress}
      testID={props.testID}
      hitSlop={theme.space[2]}
      style={{ minHeight: theme.touch.control, justifyContent: 'center' }}
    >
      <Text style={textStyle(theme, 'body', 'semibold')}>{props.label}</Text>
    </Pressable>
  );
}

function SignInBody() {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const session = useOptionalSession();
  const { serverSet, utility } = useGettingIn();
  const remembered = useHandsetUtility();
  const tenant = remembered?.tenant ?? null;
  const [login, setLogin] = useState(() => (tenant ? (utility.lastLogin(tenant) ?? '') : ''));
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorParams, setErrorParams] = useState<Record<string, number>>({});
  const [others, setOthers] = useState<UnsentSummary['others']>([]);

  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  // Another utility chosen (FF-56 → FF-57 → back here): its own last login.
  useEffect(() => {
    if (tenant) setLogin(utility.lastLogin(tenant) ?? '');
  }, [tenant, utility]);

  useEffect(() => {
    let live = true;
    session?.manager
      .unsentSummary()
      .then((s) => {
        if (live) setOthers(s.others);
      })
      .catch(() => {
        // Not known (the outbox is not wired yet): say nothing, never "nothing waiting".
      });
    return () => {
      live = false;
    };
  }, [session?.manager]);

  const ready = serverSet && tenant !== null && login.trim() !== '' && password !== '' && !busy;

  const signIn = async () => {
    if (!session) return;
    if (!serverSet) {
      setError('field.signIn.noServer');
      return;
    }
    if (!tenant) {
      setError('field.signIn.error.noUtility');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await session.manager.signIn({ tenant, login: login.trim(), password });
      utility.rememberLogin(tenant, login.trim());
      // The session flips to signed in and the gate unmounts; nothing more to do here.
    } catch (err) {
      setError(failureKey(err));
      setErrorParams(failureParams(err)); // DEF-IDN-10620 — the lock's minutes
      setBusy(false);
    }
  };

  const waiting = others[0];

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.card }} testID="screen-FF-05">
      <View style={{ flex: 1, padding: theme.space[6], gap: theme.space[4] }}>
        <View style={{ gap: theme.space[3] }}>
          <BrandMark size="sm" />
          <View>
            <AppText variant="title">{t('field.signIn.title')}</AppText>
            {tenant ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' }}>
                <AppText variant="body" tone="muted" testID="signin-utility">
                  {t('field.signIn.signingInTo', { utility: remembered?.utilityName || tenant })}
                </AppText>
                <AppText variant="body" tone="muted">
                  {' · '}
                </AppText>
                <InlineLink
                  label={t('field.signIn.change')}
                  onPress={() => openScreen(navigation, 'FF-56')}
                  testID="signin-change-utility"
                />
              </View>
            ) : (
              <AppText variant="body" tone="muted" testID="signin-no-utility">
                {t('field.signIn.activateFirst')}
              </AppText>
            )}
          </View>
        </View>
        <FieldGroup>
          <Field
            label={t('field.signIn.login')}
            value={login}
            onChangeText={setLogin}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            textContentType="username"
            testID="signin-login"
          />
          <Field
            label={t('field.signIn.password')}
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            textContentType="password"
            help={t('field.signIn.passwordHelp')}
            onSubmitEditing={() => {
              if (ready) void signIn();
            }}
            testID="signin-password"
          />
        </FieldGroup>
        <Button variant="primary" disabled={!ready} busy={busy} onPress={() => void signIn()} testID="door-FF-07">
          {t('field.signIn.signIn')}
        </Button>
        {!serverSet ? (
          <Notice tone="danger" testID="signin-no-server">
            {t('field.signIn.noServer')}
          </Notice>
        ) : null}
        {error && !(error === 'field.signIn.noServer' && !serverSet) ? (
          <Notice tone="danger" testID="signin-error">
            {t(error, errorParams)}
          </Notice>
        ) : null}
        <View>
          <TextLink
            label={t('field.signIn.forgot')}
            onPress={() => openScreen(navigation, 'FF-06', { login: login.trim() })}
            testID="door-FF-06"
          />
          <TextLink label={t('field.signIn.activate')} onPress={() => openScreen(navigation, 'FF-56')} testID="door-FF-56" />
        </View>
      </View>
      <View style={{ paddingHorizontal: theme.space[6], paddingBottom: theme.space[4], gap: theme.space[3] }}>
        {waiting ? (
          <Notice tone="warning" icon={<Glyph name="sync" colour={theme.colors.status.warning.fg} />} testID="signin-others">
            {t('field.signIn.othersWaiting', {
              name: waiting.displayName || t('field.signIn.anotherTechnician'),
              count: waiting.items + waiting.photos,
            })}
          </Notice>
        ) : null}
        <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
          <AppText variant="label" tone="muted">
            {t('field.signIn.staffPortal')}
          </AppText>
          <AppText variant="label" weight="semibold" testID="signin-version">
            {versionLabel(t)}
          </AppText>
        </View>
      </View>
    </View>
  );
}

export function SignInScreen() {
  return (
    <ScreenBoundary screen="FF-05">
      <SignInBody />
    </ScreenBoundary>
  );
}
