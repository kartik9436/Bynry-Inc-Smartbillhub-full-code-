/**
 * *Decline* — turning a job down before starting it (DEF-FLD-10579; the PO's
 * ruling of 2026-10-24, decision log *"MQ-026: STARTING A JOB ACCEPTS IT …"*).
 * One component, opened from FF-10's card and from FF-15 (B14 rule 43).
 *
 * As FF-58 (Hand it back) draws its reason list: a short list, one tap (R38),
 * *Other* with a note, and the act button greyed until a reason is given —
 * the server refuses a decline with no reason (`work.mobile.decline_reason_required`).
 * Built from the kit's `Sheet`, `CheckRow` and `Field` (rules 43–45).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Button, CheckRow, Field, Kicker, Notice, Sheet } from '../../components';
import { useTheme } from '../../theme';
import { canDecline, DECLINE_REASONS, type DeclineReason } from './acceptance';

export interface DeclineSheetProps {
  /** The job being declined, or null when the sheet is closed. */
  job: { id: string; number: string | null } | null;
  onClose: () => void;
  /** Send it. Returns false when it was refused. */
  onDecline: (jobId: string, answer: { reason: DeclineReason; note: string }) => boolean;
}

export function DeclineSheet({ job, onClose, onDecline }: DeclineSheetProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [reason, setReason] = useState<DeclineReason | null>(null);
  const [note, setNote] = useState('');
  const close = () => {
    setReason(null);
    setNote('');
    onClose();
  };
  const ready = canDecline(reason, note);
  const confirm = () => {
    if (!job || !reason || !ready) return;
    if (onDecline(job.id, { reason, note })) close();
  };

  return (
    <Sheet
      visible={job !== null}
      onClose={close}
      title={job?.number ? `${t('field.accept.title')} · ${job.number}` : t('field.accept.title')}
      closeLabel={t('field.common.close')}
      testID="decline-sheet"
      footer={
        <>
          <Button grow onPress={close} testID="decline-keep">
            {t('field.accept.keep')}
          </Button>
          <Button grow variant="danger" disabled={!ready} onPress={confirm} testID="decline-confirm">
            {t('field.accept.decline')}
          </Button>
        </>
      }
    >
      <View style={{ gap: theme.space[3] }}>
        <Kicker>{t('field.accept.why')}</Kicker>
        <View accessibilityRole="radiogroup" accessibilityLabel={t('field.accept.why')} style={{ gap: theme.space[2] }}>
          {DECLINE_REASONS.map((id) => (
            <CheckRow
              key={id}
              kind="radio"
              label={t(`field.accept.reason.${id}`)}
              checked={reason === id}
              onPress={() => setReason(id)}
              testID={`decline-reason-${id}`}
            />
          ))}
        </View>
        {reason === 'other' ? (
          <Field label={t('field.accept.note')} value={note} onChangeText={setNote} multiline testID="decline-note" />
        ) : null}
        <Notice tone="info">{t('field.accept.goesBack')}</Notice>
      </View>
    </Sheet>
  );
}
