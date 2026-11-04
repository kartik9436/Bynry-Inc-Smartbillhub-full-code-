/**
 * FF-15 TIME: the two clocks, travel and on site, kept apart (R9 — *"Travel
 * and labour are separate clocks — depart, arrive, start. Both correctable by
 * the technician"*), for this technician (R8 — labour is per person).
 *
 * *Pause* stops the labour clock; the button then reads *Resume* and starts a
 * new segment, so a close after a pause records the paused total (US-FLD-029
 * TC-4). *Correct time* moves an end of either clock, by taps (R38): a
 * stepper of minutes, never a typed time. Every correction is captured and
 * stamped who and when on the job's activity (R10).
 *
 * Depart / Arrive / Start work are drawn on FF-14 (Stop), not here; they use
 * `startClock` / `stopClock` from `actions.ts`.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, ChoiceChips, Sheet, Stepper } from '../../components';
import { useTheme } from '../../theme';
import { correctClock, startClock, stopClock } from './actions';
import { hhmm, shortDuration } from './format';
import type { JobPortValue } from './JobPort';
import type { ClockSummary, JobView } from './jobModel';

const MINUTE = 60 * 1000;

function Tile({ label, figure, line, live }: { label: string; figure: string; line: string; live: boolean }) {
  const theme = useTheme();
  const pair = live ? theme.colors.status.success : null;
  return (
    <View
      accessible
      accessibilityLabel={`${label}, ${figure}, ${line}`}
      style={{ flexGrow: 1, flexBasis: 0, padding: theme.space[3], backgroundColor: pair ? pair.bg : theme.colors.surface }}
    >
      <AppText variant="label" style={pair ? { color: pair.fg } : undefined}>
        {label}
      </AppText>
      <AppText variant="title" style={pair ? { color: pair.fg } : undefined}>
        {figure}
      </AppText>
      {/* On the live tile's fill the line takes the fill's own ink (DEF-FLD-10360:
          muted black on sunlight's dark green measured 2.59:1). */}
      <AppText variant="micro" tone={pair ? undefined : 'muted'} style={pair ? { color: pair.fg } : undefined}>
        {line}
      </AppText>
    </View>
  );
}

export function TimeCard({ port, view }: { port: JobPortValue | null; view: JobView }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [, tick] = useState(0);
  const [correcting, setCorrecting] = useState(false);
  const [which, setWhich] = useState<'travel' | 'labour'>('travel');
  const [end, setEnd] = useState<'start' | 'end'>('start');
  const [offset, setOffset] = useState(0);

  // A running clock is redrawn every half minute.
  useEffect(() => {
    const id = setInterval(() => tick((n) => n + 1), MINUTE / 2);
    return () => clearInterval(id);
  }, []);

  const units = { h: t('field.job.unit.h'), m: t('field.job.unit.m') };
  const travelLine =
    view.travel.firstStart === null
      ? t('field.ff15.notStarted')
      : view.travel.running
        ? t('field.ff15.runningSince', { time: hhmm(view.travel.runningSince) })
        : `${hhmm(view.travel.firstStart)} → ${hhmm(view.travel.lastEnd)}`;
  const labourLine =
    view.labour.firstStart === null
      ? t('field.ff15.notStarted')
      : view.labour.running
        ? t('field.ff15.runningSince', { time: hhmm(view.labour.runningSince) })
        : t('field.ff15.paused');

  const pauseOrResume = () => {
    if (!port) return;
    if (view.labour.openId) stopClock(port, view.order.id, view.labour.openId);
    else startClock(port, view.order.id, 'labour');
    port.changed();
  };

  const clock: ClockSummary = which === 'travel' ? view.travel : view.labour;
  const segment = end === 'start' ? clock.segments[0] : clock.segments[clock.segments.length - 1];
  const original = segment ? (end === 'start' ? segment.started_at : segment.ended_at) : null;
  const corrected = original ? new Date(Date.parse(original) + offset * MINUTE).toISOString() : null;

  const saveCorrection = () => {
    if (!port || !segment || !corrected) return;
    correctClock(port, view.order.id, segment, {
      startedAt: end === 'start' ? corrected : segment.started_at,
      endedAt: end === 'end' ? corrected : segment.ended_at,
    });
    setCorrecting(false);
    setOffset(0);
    port.changed();
  };

  return (
    <Card title={t('field.ff15.time')} testID="job-time">
      <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
        <Tile label={t('field.ff15.travel')} figure={shortDuration(view.travel.minutes, units)} line={travelLine} live={view.travel.running} />
        <Tile label={t('field.ff15.onSite')} figure={shortDuration(view.labour.minutes, units)} line={labourLine} live={view.labour.running} />
      </View>
      <View style={{ flexDirection: 'row', gap: theme.touch.clear }}>
        <Button grow size="sm" onPress={pauseOrResume} disabled={!port || view.labour.firstStart === null} testID="job-pause">
          {view.labour.running || view.labour.firstStart === null ? t('field.ff15.pause') : t('field.ff15.resume')}
        </Button>
        <Button
          grow
          size="sm"
          onPress={() => setCorrecting(true)}
          disabled={!port || (view.travel.segments.length === 0 && view.labour.segments.length === 0)}
          testID="job-correct-time"
        >
          {t('field.ff15.correctTime')}
        </Button>
      </View>
      <Sheet
        visible={correcting}
        onClose={() => setCorrecting(false)}
        title={t('field.ff15.correctTime')}
        closeLabel={t('field.job.close')}
        testID="correct-time-sheet"
        footer={
          <>
            <Button grow onPress={() => setCorrecting(false)}>
              {t('field.job.cancel')}
            </Button>
            <Button grow variant="primary" onPress={saveCorrection} disabled={!corrected || offset === 0} testID="correct-time-save">
              {t('field.job.save')}
            </Button>
          </>
        }
      >
        <View style={{ gap: theme.space[4] }}>
          <ChoiceChips
            label={t('field.ff15.whichClock')}
            fill
            active={which}
            onSelect={(id) => {
              setWhich(id as 'travel' | 'labour');
              setOffset(0);
            }}
            segments={[
              { id: 'travel', label: t('field.ff15.travel'), disabled: view.travel.segments.length === 0 },
              { id: 'labour', label: t('field.ff15.onSite'), disabled: view.labour.segments.length === 0 },
            ]}
            testID="correct-which"
          />
          <ChoiceChips
            label={t('field.ff15.whichEnd')}
            fill
            active={end}
            onSelect={(id) => {
              setEnd(id as 'start' | 'end');
              setOffset(0);
            }}
            segments={[
              { id: 'start', label: t('field.ff15.start') },
              { id: 'end', label: t('field.ff15.end'), disabled: !segment?.ended_at },
            ]}
            testID="correct-end"
          />
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: theme.space[3] }}>
            <AppText variant="title" testID="correct-time-value">
              {corrected ? hhmm(corrected) : '–'}
            </AppText>
            <Stepper
              value={offset}
              onChange={setOffset}
              min={-120}
              max={120}
              label={t('field.ff15.minutesMoved')}
              decreaseLabel={t('field.ff15.earlier')}
              increaseLabel={t('field.ff15.later')}
              testID="correct-time-stepper"
            />
          </View>
        </View>
      </Sheet>
    </Card>
  );
}
