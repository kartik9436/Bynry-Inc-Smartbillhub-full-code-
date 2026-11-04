/**
 * FF-53 Sign out (T-25; US-FLD-048; image `phone/FF-53-sign-out.png`).
 *
 * R64 (PO ruled): *"A sign-out deletes nothing. The next technician's handover
 * leaves the previous one's unsent work intact, and it sends under their name
 * when the handset next has a signal."* So the sheet says what is still to
 * send and whose name it sends under, and offers three ways on:
 *   *Hand to the next technician* — the Switch sheet (a password, always);
 *   *Sign out anyway* — `SessionManager.signOut()`, which ends the session
 *     and touches no captured row (`session/outboxPort.ts` has no delete);
 *   *Stay signed in* — back to where the technician was.
 *
 * The count comes from the session's view of the outbox. When that cannot
 * answer (the outbox port refuses rather than answering zero), the sheet says
 * the work was not counted — never "nothing to send".
 *
 * The drawing's two ticks — *Your shift is still open*, *Emergency alerts
 * still reach you* — are not shown: the handset does not know the shift
 * (`ME-shifts`) and push is not wired (T-41), so neither can be stated as a
 * fact yet (reported).
 */
import { useNavigation } from '@react-navigation/native';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Notice } from '../../components';
import { useOptionalSession } from '../../session/SessionProvider';
import type { UnsentSummary } from '../../session/sessionManager';
import { MeSheetScreen, useDoor } from './MeScreen';

type Count = { state: 'loading' } | { state: 'known'; value: UnsentSummary } | { state: 'unknown' };

export function SignOutScreen() {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const door = useDoor('FF-53');
  const session = useOptionalSession();
  const [count, setCount] = useState<Count>({ state: 'loading' });
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    if (!session) {
      setCount({ state: 'unknown' });
      return;
    }
    session.manager.unsentSummary().then(
      (value) => live && setCount({ state: 'known', value }),
      () => live && setCount({ state: 'unknown' }),
    );
    return () => {
      live = false;
    };
  }, [session]);

  async function signOut() {
    if (!session) return;
    setBusy(true);
    try {
      // Ends the session. Deletes nothing (R64). The tree swaps to the gate.
      await session.manager.signOut();
    } finally {
      setBusy(false);
    }
  }

  const mine = count.state === 'known' ? count.value.mine : null;
  const waiting = mine != null && (mine.items > 0 || mine.photos > 0);

  return (
    <MeSheetScreen
      id="FF-53"
      title={t('field.ff53.title')}
      footer={
        <>
          <Button variant="primary" onPress={() => door('SWITCH')} testID="door-SWITCH">
            {t('field.ff53.handOver')}
          </Button>
          <Button variant="danger" onPress={signOut} busy={busy} testID="door-FF-05">
            {t('field.ff53.signOutAnyway')}
          </Button>
          <Button onPress={() => navigation.goBack()} testID="door-FF-09">
            {t('field.ff53.stay')}
          </Button>
        </>
      }
    >
      {waiting && mine ? (
        <Notice tone="warning" testID="ff53-waiting">
          {`${t('field.ff53.toSend', { items: mine.items, photos: mine.photos })} ${t('field.ff53.underYourName')}`}
        </Notice>
      ) : null}
      {count.state === 'unknown' ? (
        <Notice tone="warning" testID="ff53-not-counted">
          {`${t('field.ff53.notCounted')} ${t('field.ff53.underYourName')}`}
        </Notice>
      ) : null}
      {count.state === 'known' && !waiting ? (
        <Notice tone="success" testID="ff53-all-sent">
          {t('field.ff50.allSent')}
        </Notice>
      ) : null}
    </MeSheetScreen>
  );
}
