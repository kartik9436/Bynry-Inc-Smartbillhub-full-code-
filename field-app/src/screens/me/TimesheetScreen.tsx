/**
 * FF-47 Timesheet (T-24; US-FLD-017; image `phone/FF-47-timesheet.png`).
 *
 * Where the hours went, per person (R8): the total recorded, split into jobs ·
 * travel · admin on one bar, then every clock in order — admin tasks, travel
 * to a job, labour on a job, and the one RUNNING now in amber (TC-1). Today or
 * the week.
 *
 * R9 (PO ruled): *"Travel and labour are separate clocks — depart, arrive,
 * start. Both correctable by the technician."* Tapping an entry opens its
 * correction: start and end move in five- and fifteen-minute taps (R38: taps,
 * never types), and the correction is captured through the outbox like any
 * other act (`dbData.ts`).
 *
 * *Submit the day* sends the day to the office per person per order (TC-3) —
 * WIRED (`CR-193-BRC10`, MQ-040 step 1): captured through the outbox at the
 * press and sent when there is signal; the server snapshots that day's labour
 * per job and travel (`shifts.submit_day`). A running clock is shown as
 * running at submit and is never silently stopped (TC-4).
 *
 * ⚠ **A SUBMITTED DAY IS READ-ONLY ON THE PHONE** (decision log 2026-10-26,
 * *"a submitted timesheet day is not editable on the phone (the office
 * corrects it)"*): once today is submitted the button reads *Submitted*, and
 * today's entries no longer open their correction.
 */
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, View } from 'react-native';

import { AppText, Button, ChoiceChips, Dot, EmptyState, Meter, Notice, Sheet } from '../../components';
import { useTheme } from '../../theme';
import type { StatusTone } from '../../theme';
import { formatClock, formatDuration } from './format';
import { useActiveTechnician, useCaptor, useHandsetPrefs } from './hooks';
import { MeScreen } from './MeScreen';
import { type AdminTask, type TimeEntry, useMeServices } from './services';

export const ADMIN_TASK_KEY: Record<AdminTask, string> = {
  vehicleCheck: 'field.ff48.task.vehicleCheck',
  training: 'field.ff48.task.training',
  depot: 'field.ff48.task.depot',
  crewMeeting: 'field.ff48.task.crewMeeting',
  other: 'field.ff48.task.other',
};

const KIND_TONE: Record<TimeEntry['kind'], StatusTone> = { labour: 'success', travel: 'info', admin: 'neutral' };

export function minutesOf(e: TimeEntry, now: Date): number {
  const end = e.endedAt ? Date.parse(e.endedAt) : now.getTime();
  return Math.max(0, Math.round((end - Date.parse(e.startedAt)) / 60_000));
}

export function totals(entries: readonly TimeEntry[], now: Date) {
  const sum = { labour: 0, travel: 0, admin: 0 };
  for (const e of entries) sum[e.kind] += minutesOf(e, now);
  return { ...sum, all: sum.labour + sum.travel + sum.admin };
}

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

export function EntryRow(props: { entry: TimeEntry; now: Date; clock: 'h24' | 'h12'; onPress: () => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const e = props.entry;
  const running = e.endedAt === null;
  const tone: StatusTone = running ? 'warning' : KIND_TONE[e.kind];
  const order = [e.workOrderNumber, e.workOrderType].filter(Boolean).join(' · ');
  const title = running
    ? t('field.ff47.runningNow')
    : e.kind === 'admin'
      ? t(e.adminTask ? ADMIN_TASK_KEY[e.adminTask] : 'field.ff47.admin')
      : e.kind === 'travel'
        ? e.workOrderNumber
          ? t('field.ff47.travelTo', { order: e.workOrderNumber })
          : t('field.ff47.travel')
        : order || t('field.ff47.labour');
  const span = running
    ? t('field.ff47.since', { time: formatClock(e.startedAt, props.clock) })
    : `${formatClock(e.startedAt, props.clock)} – ${formatClock(e.endedAt ?? e.startedAt, props.clock)}`;
  const detail = running && order ? `${order} · ${span}` : e.kind === 'admin' && !running ? `${span} · ${t('field.ff47.admin')}` : span;
  const ink = running ? theme.colors.statusInk.warning : undefined;
  const inkOnCard = running && theme.name !== 'sunlight' ? ink : undefined;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${title}, ${detail}, ${formatDuration(minutesOf(e, props.now))}`}
      accessibilityHint={t('field.ff47.correctHint')}
      onPress={props.onPress}
      testID={`ff47-entry-${e.id}`}
      style={{
        minHeight: theme.touch.primary,
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[3],
        padding: theme.space[3],
        borderWidth: theme.borderWidth.card,
        borderColor: theme.colors.border,
        borderLeftWidth: theme.borderWidth.rule,
        borderLeftColor: theme.colors.status[tone].rule,
        borderRadius: theme.radius.lg,
        backgroundColor: theme.colors.card,
      }}
    >
      <View style={{ flexGrow: 1, flexShrink: 1 }}>
        <AppText variant="body" weight="heavy">
          {title}
        </AppText>
        <AppText variant="label" tone={inkOnCard ? 'default' : 'muted'} style={inkOnCard ? { color: inkOnCard } : undefined}>
          {detail}
        </AppText>
      </View>
      <AppText variant="section" style={inkOnCard ? { color: inkOnCard } : undefined} testID={`ff47-minutes-${e.id}`}>
        {formatDuration(minutesOf(e, props.now))}
      </AppText>
    </Pressable>
  );
}

const SHIFTS = [-15, -5, 5, 15] as const;

function shift(iso: string, minutes: number): string {
  return new Date(Date.parse(iso) + minutes * 60_000).toISOString();
}

export function Correction(props: { entry: TimeEntry | null; clock: 'h24' | 'h12'; onClose: () => void; onSave: (start: string, end: string | null) => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const e = props.entry;
  const [start, setStart] = useState<string | null>(null);
  const [end, setEnd] = useState<string | null>(null);
  const s = start ?? e?.startedAt ?? '';
  const en = end ?? e?.endedAt ?? null;
  const invalid = en !== null && Date.parse(en) < Date.parse(s);
  const segments = SHIFTS.map((m) => ({ id: String(m), label: m > 0 ? `+${m}` : `−${-m}` }));
  const close = () => {
    setStart(null);
    setEnd(null);
    props.onClose();
  };
  return (
    <Sheet
      visible={e != null}
      onClose={close}
      title={t('field.ff47.correct')}
      closeLabel={t('field.me.close')}
      testID="ff47-correction"
      footer={
        <>
          <Button grow onPress={close} testID="ff47-correction-cancel">
            {t('field.me.cancel')}
          </Button>
          <Button
            grow
            variant="primary"
            disabled={invalid}
            onPress={() => {
              props.onSave(s, en);
              setStart(null);
              setEnd(null);
            }}
            testID="ff47-correction-save"
          >
            {t('field.me.save')}
          </Button>
        </>
      }
    >
      {e ? (
        <View style={{ gap: theme.space[4] }}>
          <View style={{ gap: theme.space[2] }}>
            <AppText variant="body" weight="heavy" testID="ff47-correction-start">
              {t('field.ff47.start', { time: formatClock(s, props.clock) })}
            </AppText>
            <ChoiceChips
              label={t('field.ff47.moveStart')}
              segments={segments}
              active={null}
              fill
              onSelect={(id) => setStart(shift(s, Number(id)))}
              testID="ff47-start"
            />
          </View>
          {en !== null ? (
            <View style={{ gap: theme.space[2] }}>
              <AppText variant="body" weight="heavy" testID="ff47-correction-end">
                {t('field.ff47.end', { time: formatClock(en, props.clock) })}
              </AppText>
              <ChoiceChips
                label={t('field.ff47.moveEnd')}
                segments={segments}
                active={null}
                fill
                onSelect={(id) => setEnd(shift(en, Number(id)))}
                testID="ff47-end"
              />
            </View>
          ) : null}
          {invalid ? <Notice tone="danger">{t('field.ff47.endBeforeStart')}</Notice> : null}
        </View>
      ) : null}
    </Sheet>
  );
}

export function TimesheetScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const tech = useActiveTechnician();
  const captor = useCaptor();
  const [prefs] = useHandsetPrefs();
  const [range, setRange] = useState<'today' | 'week'>('today');
  const [editing, setEditing] = useState<TimeEntry | null>(null);
  const [notice, setNotice] = useState<{ tone: 'warning' | 'info'; text: string } | null>(null);
  const [version, setVersion] = useState(0);
  const now = services.now();
  const submittedToday = tech ? services.timesheet.submitted?.(tech.technicianId, now) === true : false;
  const sameDay = (iso: string) => startOfDay(new Date(iso)).getTime() === startOfDay(now).getTime();

  const entries = useMemo(() => {
    if (!tech) return null;
    const to = startOfDay(now);
    to.setDate(to.getDate() + 1);
    const from = startOfDay(now);
    if (range === 'week') from.setDate(from.getDate() - 6);
    return services.data.timesheet(tech.technicianId, from, to);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [services, tech?.technicianId, range, version]);

  const sum = totals(entries ?? [], now);

  async function submit() {
    if (!tech) return;
    setNotice(null);
    try {
      await services.timesheet.submitDay(captor(), now);
      setNotice({ tone: 'info', text: t(services.timesheet.submitted ? 'field.ff47.queued' : 'field.ff47.submitted') });
      setVersion((v) => v + 1);
    } catch {
      setNotice({ tone: 'warning', text: t('field.me.notSent') });
    }
  }

  function save(start: string, end: string | null) {
    if (!editing) return;
    try {
      services.data.correct(captor(), editing.id, start, end, services.now());
      setEditing(null);
      setVersion((v) => v + 1);
    } catch {
      setEditing(null);
      setNotice({ tone: 'warning', text: t('field.me.notSaved') });
    }
  }

  return (
    <MeScreen
      id="FF-47"
      title={t('field.screen.ff47')}
      leading={{ back: 'FF-44' }}
      header={
        <View style={{ paddingHorizontal: theme.space[4], paddingTop: theme.space[3], backgroundColor: theme.colors.page }}>
          <ChoiceChips
            label={t('field.ff47.range')}
            fill
            segments={[
              { id: 'today', label: t('field.ff47.today') },
              { id: 'week', label: t('field.ff47.week') },
            ]}
            active={range}
            onSelect={(id) => setRange(id === 'week' ? 'week' : 'today')}
            testID="ff47-range"
          />
        </View>
      }
      footer={
        <Button grow variant="primary" onPress={submit} disabled={submittedToday || !entries || entries.length === 0} testID="ff47-submit">
          {t(submittedToday ? 'field.ff47.submittedLabel' : 'field.ff47.submit')}
        </Button>
      }
    >
      {notice ? <Notice tone={notice.tone}>{notice.text}</Notice> : null}
      {entries === null ? (
        <EmptyState title={t('field.me.notHereYet')} helper={t('field.ff47.emptyHelper')} testID="ff47-not-wired" />
      ) : (
        <>
          <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: theme.space[2] }}>
            <AppText variant="title" testID="ff47-total">
              {formatDuration(sum.all)}
            </AppText>
            <AppText variant="body" tone="muted">
              {t('field.ff47.recorded')}
            </AppText>
          </View>
          <Meter
            label={t('field.ff47.split', {
              jobs: formatDuration(sum.labour),
              travel: formatDuration(sum.travel),
              admin: formatDuration(sum.admin),
            })}
            parts={[
              { value: sum.labour, tone: 'success' },
              { value: sum.travel, tone: 'info' },
              { value: sum.admin, tone: 'neutral' },
            ]}
            testID="ff47-split"
          />
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space[3] }}>
            {(
              [
                ['success', 'field.ff47.jobs', sum.labour],
                ['info', 'field.ff47.travel', sum.travel],
                ['neutral', 'field.ff47.admin', sum.admin],
              ] as const
            ).map(([tone, key, minutes]) => (
              <View key={key} style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[1] }}>
                <Dot tone={tone} />
                <AppText variant="label" testID={`ff47-legend-${tone}`}>
                  {`${t(key)} ${formatDuration(minutes)}`}
                </AppText>
              </View>
            ))}
          </View>
          {entries.length === 0 ? <EmptyState title={t('field.ff47.none')} helper={t('field.ff47.emptyHelper')} /> : null}
          {entries.map((e) => (
            <EntryRow
              key={e.id}
              entry={e}
              now={now}
              clock={prefs.clock}
              onPress={() => {
                // A submitted day is the office's to correct now.
                if (!(submittedToday && sameDay(e.startedAt))) setEditing(e);
              }}
            />
          ))}
        </>
      )}
      <Correction entry={editing} clock={prefs.clock} onClose={() => setEditing(null)} onSave={save} />
    </MeScreen>
  );
}
