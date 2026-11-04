/**
 * The lock cover, with its unlock form (T-12/T-15; Security §3).
 *
 * The session locks after five minutes untouched and at once when the app
 * goes to the background. The navigation tree stays mounted under this
 * cover, so unlocking returns the technician to exactly where they were.
 *
 * TWO WAYS BACK, and only for the technician whose session it is:
 *  - their PASSWORD (works with no signal — the handset checks it against
 *    the verifier it kept at sign-in);
 *  - their FINGERPRINT, which only ever returns them to their OWN session
 *    (*"a thumb on a shared tablet is not an identity claim"*). Somebody else
 *    taking the phone over is a switch, and a switch is always a password —
 *    the Switch technician sheet, not this cover. The session manager
 *    enforces that; this form only offers it.
 *
 * Fingerprint is offered while it has not been refused: no biometric package
 * is installed yet (`security/biometric.ts`), so pressing it today answers
 * *Use your password* and the button goes — it is never pretended.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Field, Notice } from '../../components';
import { useOptionalSession } from '../../session/SessionProvider';
import { BiometricNotAllowedError } from '../../session/sessionManager';
import { useTheme } from '../../theme';
import { BrandMark } from './BrandMark';
import { failureKey } from './signInErrors';

export function LockCover() {
  const theme = useTheme();
  const { t } = useTranslation();
  const session = useOptionalSession();
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [biometricRefused, setBiometricRefused] = useState(false);
  const active = session?.snapshot.active ?? null;

  const unlock = async () => {
    if (!session) return;
    setBusy(true);
    setError(null);
    try {
      await session.manager.unlockWithPassword(password);
      setPassword('');
    } catch (err) {
      setError(failureKey(err));
    } finally {
      setBusy(false);
    }
  };

  const thumb = async () => {
    if (!session || !active) return;
    setError(null);
    try {
      await session.manager.unlockWithBiometric(active.technicianId, t('field.lock.biometricPrompt'));
    } catch (err) {
      if (err instanceof BiometricNotAllowedError) setBiometricRefused(true);
      setError(failureKey(err));
    }
  };

  return (
    <View
      testID="lock-cover"
      accessibilityViewIsModal
      style={{
        position: 'absolute',
        top: 0,
        bottom: 0,
        left: 0,
        right: 0,
        backgroundColor: theme.colors.page,
        justifyContent: 'center',
        padding: theme.space[6],
        gap: theme.space[4],
      }}
    >
      <View style={{ alignItems: 'center', gap: theme.space[3] }}>
        <BrandMark size="sm" />
        <AppText variant="title">{t('field.lock.title')}</AppText>
        {active ? (
          <AppText variant="body" tone="muted" testID="lock-name">
            {active.displayName}
          </AppText>
        ) : null}
      </View>
      <Field
        label={t('field.signIn.password')}
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        autoCapitalize="none"
        autoCorrect={false}
        textContentType="password"
        onSubmitEditing={() => {
          if (password !== '') void unlock();
        }}
        testID="lock-password"
      />
      <Button variant="primary" disabled={password === ''} busy={busy} onPress={() => void unlock()} testID="lock-unlock">
        {t('field.lock.unlock')}
      </Button>
      {biometricRefused ? null : (
        <Button onPress={() => void thumb()} testID="lock-biometric">
          {t('field.lock.fingerprint')}
        </Button>
      )}
      {error ? (
        <Notice tone="danger" testID="lock-error">
          {t(error)}
        </Notice>
      ) : null}
    </View>
  );
}
