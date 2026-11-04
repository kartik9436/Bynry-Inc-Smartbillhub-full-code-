/**
 * FF-56 Activate — *First time here* (T-15; US-FLD-070, R105). Built from
 * `wireframes/phone/FF-56-activate.png` and `tablet/FF-56-T-activate.png`.
 *
 * As drawn: *The office set up your account* and *They gave you a six-
 * character code. It lasts seven days.*; YOUR CODE (the code box); YOUR WORK
 * EMAIL; NO CODE? *Ring dispatch for a new one.*; then *Check the code* and
 * *I already have a password* (back to FF-05).
 *
 * ⚠ **THE CODE NAMES THE UTILITY (`DEF-FLD-10580`, beta MQ-006; PO
 * 2026-10-24: *"A. The code from the office sets the utility"*).** The app is
 * one build for every utility, so this screen is how a handset learns where
 * its technician works. The moment six characters are typed the phone asks
 * the utility-free door, `POST /api/auth/activation/lookup`, which utility
 * holds the code, and shows its name under the code box — *For City of
 * Houston* — so a technician holding the wrong utility's code sees it before
 * going on. *Check the code* then runs the existing check against THAT
 * utility, and FF-57 carries it forward and remembers it on the handset once
 * the password is set. The line sits under YOUR CODE because it is what the
 * code just told us; the drawing has no utility line (it predates the ruling)
 * and the shape it does draw is unchanged.
 *
 * The board's blue note (*"Technicians are not self-registered. Only the
 * office creates an account; this screen claims one that already exists."*)
 * is RATIONALE and is zero words on screen (B14 rule 33). It is what this
 * screen IS: nothing here creates an account — the lookup and the check only
 * ask the server about a code the office issued.
 *
 * The client checks only the code's SHAPE (six letters or digits) before
 * spending a request; whether it is real, unexpired (seven days) and unused
 * is the server's answer, and every way a code can be wrong is one refusal.
 */
import { useNavigation } from '@react-navigation/native';
import { useEffect, useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { AppText, Button, Card, Field, FieldGroup, Notice, Page } from '../../components';
import { checkActivationCode, isActivationCodeShaped, lookupActivationCode, normaliseActivationCode } from '../../security/activation';
import type { ActivationLookup } from '../../security/authApi';
import { ScreenBoundary } from '../theDay/ScreenBoundary';
import { CodeField } from './CodeField';
import { useGettingIn } from './gettingInServices';
import { failureKey } from './signInErrors';
import { openScreen } from '../theDay/go';

/** The refusal for a code, whatever the reason — said once, the server's posture. */
function codeFailureKey(err: unknown): string {
  return failureKey(err) === 'field.signIn.error.invalid' ? 'field.activate.error.refused' : failureKey(err);
}

function ActivateBody() {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const { api, deviceId } = useGettingIn();
  const [code, setCode] = useState('');
  const [email, setEmail] = useState('');
  const [found, setFound] = useState<(ActivationLookup & { code: string }) | null>(null);
  const [looking, setLooking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useLayoutEffect(() => {
    navigation.setOptions({ title: t('field.activate.title') });
  }, [navigation, t]);

  // Six characters typed → which utility holds them. A new code forgets the old answer.
  const shaped = isActivationCodeShaped(code) ? normaliseActivationCode(code) : null;
  useEffect(() => {
    setFound(null);
    setError(null);
    if (!shaped) return;
    let live = true;
    setLooking(true);
    (async () => {
      try {
        const answer = await lookupActivationCode(api, { code: shaped, deviceId: await deviceId() });
        if (live) setFound({ ...answer, code: shaped });
      } catch (err) {
        if (live) setError(codeFailureKey(err));
      } finally {
        if (live) setLooking(false);
      }
    })();
    return () => {
      live = false;
    };
  }, [shaped, api, deviceId]);

  const utility = found && found.code === shaped ? found : null;
  const ready = utility !== null && email.trim() !== '' && !busy && !looking;

  const check = async () => {
    if (!utility) return;
    setBusy(true);
    setError(null);
    try {
      const answer = await checkActivationCode(api, { tenant: utility.tenant, code, email });
      openScreen(navigation, 'FF-57', {
        check: answer,
        email: email.trim(),
        tenant: utility.tenant,
        utilityName: utility.utilityName || answer.utilityName,
      });
    } catch (err) {
      setError(codeFailureKey(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page
      testID="screen-FF-56"
      footer={
        <>
          <Button grow onPress={() => openScreen(navigation, 'FF-05')} testID="door-FF-05">
            {t('field.activate.havePassword')}
          </Button>
          <Button variant="primary" grow disabled={!ready} busy={busy} onPress={() => void check()} testID="door-FF-57">
            {t('field.activate.check')}
          </Button>
        </>
      }
    >
      <Card>
        <AppText variant="section">{t('field.activate.heading')}</AppText>
        <AppText variant="body" tone="muted">
          {t('field.activate.lead')}
        </AppText>
        <FieldGroup>
          <CodeField label={t('field.activate.code')} value={code} onChange={setCode} testID="activate-code" />
          {utility ? (
            <AppText variant="body" weight="semibold" testID="activate-utility">
              {t('field.activate.forUtility', { utility: utility.utilityName || utility.tenant })}
            </AppText>
          ) : null}
          <Field
            label={t('field.activate.email')}
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="emailAddress"
            testID="activate-email"
          />
        </FieldGroup>
      </Card>
      {error ? (
        <Notice tone="danger" testID="activate-error">
          {t(error)}
        </Notice>
      ) : null}
      <Card title={t('field.activate.noCode')}>
        <AppText variant="body">{t('field.activate.ringDispatch')}</AppText>
      </Card>
    </Page>
  );
}

export function ActivateScreen() {
  return (
    <ScreenBoundary screen="FF-56">
      <ActivateBody />
    </ScreenBoundary>
  );
}
