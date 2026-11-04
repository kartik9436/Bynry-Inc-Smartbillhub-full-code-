/**
 * FF-58 Hand it back — requirement 71, US-FLD-071. R106 (PO ruled): *"Handing
 * a job back returns it to Queued, unassigned, with the technician's name and
 * reason on it. No eighth dispatch state is invented."* R107: *"An emergency
 * cannot be handed back from the app. It takes a call to dispatch, so a
 * person knows nobody is going."*
 *
 * A reason from a short list, one tap (R38); *Say a bit more* opens a box the
 * phone's own keyboard microphone can dictate into (no speech package is
 * installed, and none is needed for that). The hand-back is captured as a
 * `hand_back` item — unrouted until the server has the door — with the
 * reason and a stamped status line on the job's activity (R10). The handset
 * invents no state for the order: the SERVER moves it to Queued.
 *
 * For an emergency the button is not offered and the screen says to ring
 * dispatch. ⚠ Today nothing on the handset marks an emergency (`jobModel.ts`
 * `isEmergency`), which is reported as a server gap.
 *
 * Built from `phone/FF-58-hand-it-back.png`. Doors: back and *Keep it* →
 * FF-15, *Hand it back* → FF-10 (the job has left the day).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, CheckRow, Field, Kicker, Notice } from '../../components';
import { useTheme } from '../../theme';
import { handBack } from './actions';
import { hhmm } from './format';
import { JobScreen, useDoor } from './JobScreen';
import { useOpenJob } from './useJob';

/** The short list (requirement 71), in the board's order. The words are the catalogue's. */
export const HAND_BACK_REASONS = ['skills', 'parts', 'reach', 'twoPeople', 'alreadyDone', 'other'] as const;
export type HandBackReason = (typeof HAND_BACK_REASONS)[number];

const REASON_KEY: Record<HandBackReason, string> = {
  skills: 'field.ff58.reason.skills',
  parts: 'field.ff58.reason.parts',
  reach: 'field.ff58.reason.reach',
  twoPeople: 'field.ff58.reason.twoPeople',
  alreadyDone: 'field.ff58.reason.alreadyDone',
  other: 'field.ff58.reason.other',
};

export function HandBack() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-58');
  const { port, view } = useOpenJob();
  const [reason, setReason] = useState<HandBackReason | null>(null);
  const [more, setMore] = useState(false);
  const [note, setNote] = useState('');
  const order = view?.order ?? null;
  const emergency = view?.emergency ?? false;
  const address = view?.premise?.address_line ?? null;

  const submit = () => {
    if (!port || !view) {
      go('FF-10');
      return;
    }
    if (!reason || emergency) return;
    handBack(port, view.order.id, { reason, note, emergency });
    port.setOpenJobId(null);
    port.changed();
    go('FF-10');
  };

  return (
    <JobScreen
      id="FF-58"
      title={t('field.screen.ff58')}
      back={{ to: 'FF-15', label: t('field.job.backToJob') }}
      footer={
        <>
          <Button grow onPress={() => go('FF-15')} testID="hand-back-keep">
            {t('field.ff58.keep')}
          </Button>
          <Button
            grow
            variant="primary"
            disabled={view !== null && (reason === null || emergency)}
            onPress={submit}
            testID="door-FF-10"
          >
            {view === null ? t('field.ff58.backToToday') : t('field.ff58.handBack')}
          </Button>
        </>
      }
    >
      {order ? (
        <View testID="hand-back-order">
          <AppText variant="body" weight="heavy">
            {[order.number, order.type].filter(Boolean).join(' · ')}
          </AppText>
          <AppText variant="label" tone="muted">
            {[address, order.window_start ? `${hhmm(order.window_start)}–${hhmm(order.window_end)}` : null].filter(Boolean).join(' · ')}
          </AppText>
        </View>
      ) : (
        <Notice tone="info">{t('field.job.noJob')}</Notice>
      )}
      {emergency ? (
        <Notice tone="danger" testID="hand-back-emergency">
          {t('field.ff58.emergency')}
        </Notice>
      ) : (
        <>
          <Kicker>{t('field.ff58.why')}</Kicker>
          <View accessibilityRole="radiogroup" accessibilityLabel={t('field.ff58.why')} style={{ gap: theme.space[2] }}>
            {HAND_BACK_REASONS.map((id) => (
              <CheckRow
                key={id}
                kind="radio"
                label={t(REASON_KEY[id])}
                checked={reason === id}
                disabled={view === null}
                onPress={() => setReason(id)}
                testID={`hand-back-${id}`}
              />
            ))}
          </View>
          {more ? (
            <Field label={t('field.ff58.more')} value={note} onChangeText={setNote} multiline testID="hand-back-note" />
          ) : (
            <Button onPress={() => setMore(true)} disabled={view === null} testID="hand-back-say-more">
              {t('field.ff58.sayMore')}
            </Button>
          )}
          <Notice tone="info">{t('field.ff58.goesBack')}</Notice>
        </>
      )}
    </JobScreen>
  );
}
