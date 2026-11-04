/**
 * The *waiting to send* strip as FF-10 and FF-63 draw it, fed from the
 * handset: items and photographs counted from the outbox and the photo
 * queue, and the last time the server answered one of this technician's
 * items. The words open Sync (FF-50, R103); *Send now* runs the sync
 * engine's push when the app has wired one (`FieldData.sendNow`), and is not
 * drawn when it has not.
 *
 * With no store on the handset it says the count is not known — never "0",
 * which would read as "all sent" on a phone holding a day of work.
 */
import { useNavigation } from '@react-navigation/native';
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { SyncStrip } from '../../components';
import { waitingToSend } from '../../db/queries/day';
import { clock } from './format';
import { useFieldData, useScoped } from './fieldData';
import { openScreen } from './go';

export function DaySyncStrip(props: { refreshKey?: number; onSent?: () => void }) {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const { sendNow } = useFieldData();
  const s = useScoped();
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(0);
  // `refreshKey` and `sent` re-read the counts after a send or a pull.
  void props.refreshKey;
  void sent;
  const waiting = s ? waitingToSend(s) : null;

  const send = useCallback(async () => {
    if (!sendNow) return;
    setSending(true);
    try {
      await sendNow();
    } catch {
      // A failed send is the engine's to record (FF-50 shows it); the strip
      // simply keeps counting what is still waiting.
    } finally {
      setSending(false);
      setSent((n) => n + 1);
      props.onSent?.();
    }
  }, [sendNow, props]);

  const title = waiting ? t('field.sync.waiting', { count: waiting.items }) : t('field.status.sync.unknown');
  const last = waiting ? clock(waiting.lastSentAt) : null;
  const detail = waiting
    ? [t('field.sync.photos', { count: waiting.photos }), last ? t('field.sync.lastSent', { time: last }) : null]
        .filter(Boolean)
        .join(' · ')
    : undefined;

  return (
    <SyncStrip
      title={title}
      detail={detail}
      pending={(waiting?.items ?? 0) + (waiting?.photos ?? 0) > 0}
      onOpen={() => openScreen(navigation, 'FF-50')}
      openHint={t('field.sync.openHint')}
      sendLabel={t('field.sync.sendNow')}
      onSend={sendNow && waiting ? () => void send() : undefined}
      sending={sending}
      testID="sync-strip"
    />
  );
}
