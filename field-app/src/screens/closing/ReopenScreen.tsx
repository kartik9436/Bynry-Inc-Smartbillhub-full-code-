/**
 * FF-36 Reopen — undo my own close before the office accepts it, with a
 * reason (US-FLD-024 TC-1; R22). The board draws it as a sheet over FF-35:
 * the job, *Reopen WO-4822?*, what happens (*The close is undone. The office
 * is told.*), WHY, when it was closed, Cancel · Reopen.
 *
 *   After acceptance it is a correction and the office owns it (R22): the
 *     screen says so and Reopen is greyed.
 *   A reconnect is never a reopen (R21) — that is FF-35's *Raise follow-on*.
 *
 * THE REOPEN IS THE SERVER'S ACT, ONLINE (`POST work/mobile/jobs/{id}/reopen`,
 * N21 — released by lane INTEGRATE-2 when the door landed). The handset sends
 * it with a key minted here (a replay changes nothing) and undoes the close on
 * the phone ONLY once the server has: a reopen that cannot be sent — no
 * signal, accepted by the office meanwhile, a close still waiting to be sent —
 * leaves the close as it is and says so, rather than a phone and a server that
 * disagree about whether the job is closed. The three reasons are the board's,
 * mapped to the server's words (`session/fieldDoors.REOPEN_REASON_WIRE`).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { RadioList } from '../../components/RadioList';
import { GroupLabel, ScreenFrame } from '../../components/ScreenFrame';
import { useTheme } from '../../theme';
import { NotOnPhone, type WaveScreenProps } from '../onSite/common';
import { goTo, useNav, useJobId, type Wave } from '../onSite/fieldData';
import { addressLines, formatClock } from '../onSite/format';
import * as workOrderQ from '../../db/queries/workOrder';
import { FieldGapError } from '../onSite/money';
import { acceptedAt, loadJob } from '../onSite/job';

export const REOPEN_REASONS = ['wrongOutcome', 'missedStep', 'evidenceMissing'] as const;

/** Reopen through the server, then on the phone. Rejects — and changes nothing here — when the server did not. */
export async function reopen(w: Wave, workOrderId: string, reason: string): Promise<void> {
  if (!w.reopen) throw new FieldGapError('N21', 'no server on this build');
  await w.reopen.reopen(workOrderId, reason, w.newId());
  w.db.transaction(() => workOrderQ.markReopened(w.s, workOrderId));
}

export function ReopenScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const [reason, setReason] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const job = loadJob(w, useJobId());
  if (!job) return <NotOnPhone />;

  const { order, customer, premise } = job;
  const accepted = acceptedAt(job);

  return (
    <ScreenFrame
      footer={
        <View style={{ flex: 1, flexDirection: 'row', gap: theme.space[2] }}>
          <Button grow onPress={() => goTo(navigation, 'FF-35')} testID="door-FF-35">
            {t('field.site.cancel')}
          </Button>
          <Button
            grow
            variant="danger"
            disabled={!reason || accepted !== null}
            busy={busy}
            onPress={() => {
              setBusy(true);
              setFailed(false);
              reopen(w, order.id, reason ?? '').then(
                () => {
                  setBusy(false);
                  goTo(navigation, 'FF-15', { workOrderId: order.id });
                },
                () => {
                  setBusy(false);
                  setFailed(true);
                },
              );
            }}
            testID="reopen"
          >
            {t('field.ff36.reopen')}
          </Button>
        </View>
      }
    >
      <Card>
        <AppText variant="section">{customer?.name ?? ''}</AppText>
        <AppText variant="body">{addressLines(premise).line1}</AppText>
        <AppText variant="label" tone="muted">
          {[order.number, order.type].filter(Boolean).join(' · ')}
        </AppText>
      </Card>

      <AppText variant="title" testID="reopen-title">
        {t('field.ff36.title', { number: order.number ?? '' })}
      </AppText>
      {accepted ? (
        <Notice tone="info" testID="office-owns">
          {t('field.ff36.officeOwns')}
        </Notice>
      ) : (
        <Notice tone="warning" icon={<Mark name="warning" colour={theme.colors.status.warning.fg} />}>
          {t('field.ff36.undone')}
        </Notice>
      )}
      {failed ? (
        <Notice tone="danger" testID="reopen-failed">
          {t('field.ff36.notSent')}
        </Notice>
      ) : null}

      <GroupLabel>{t('field.ff36.why')}</GroupLabel>
      <RadioList
        label={t('field.ff36.why')}
        options={REOPEN_REASONS.map((id) => ({ id, label: t(`field.ff36.reason.${id}`) }))}
        value={reason}
        onChange={setReason}
        testID="reopen-reason"
      />
      {order.closed_at ? (
        <AppText variant="label" tone="muted" testID="closed-stamp">
          {accepted
            ? t('field.ff36.closedAccepted', { time: formatClock(order.closed_at) })
            : t('field.ff36.closedNotAccepted', { time: formatClock(order.closed_at) })}
        </AppText>
      ) : null}
    </ScreenFrame>
  );
}
