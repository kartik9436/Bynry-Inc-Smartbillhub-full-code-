/**
 * FF-46 Shifts (T-24; US-FLD-006; image `phone/FF-46-shifts.png`).
 *
 * The shift in progress (how long, of what window, and *End shift*), then the
 * week: each day a shift with its window and route, approved time off in
 * blue, a utility holiday in grey (TC-4). *Request time off* at the foot.
 *
 * WIRED (`CR-193-BRC10`, MQ-040 step 1, decision log 2026-10-26): the week
 * is the one the day's sync downloaded and kept (`sync/shifts.ts`) — the
 * office's working days, its one-day exceptions and the utility's holidays —
 * and *End shift* is captured through the outbox at the press and sent when
 * there is signal (`shiftsPorts.ts`). With no week kept yet the screen still
 * says it is not on this phone — never an invented rota.
 *
 * ⚠ *Request time off* is STEP 2 and is NOT approved: it still says it was
 * not sent (`ME-shifts`).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, EmptyState, Kicker, Notice } from '../../components';
import { Pickable } from '../../tablet/Pickable';
import { useTheme } from '../../theme';
import { formatClock, formatDuration } from './format';
import { useActiveTechnician, useCaptor, useHandsetPrefs, usePortRead } from './hooks';
import { MeScreen } from './MeScreen';
import { type ShiftDay, useMeServices } from './services';

export const DAY_KEYS = [
  'field.ff46.day.sun',
  'field.ff46.day.mon',
  'field.ff46.day.tue',
  'field.ff46.day.wed',
  'field.ff46.day.thu',
  'field.ff46.day.fri',
  'field.ff46.day.sat',
] as const;

function DayRow({ day, clock, today }: { day: ShiftDay; clock: 'h24' | 'h12'; today: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const d = new Date(day.date);
  const tone = day.kind === 'timeOff' ? 'info' : day.kind === 'holiday' ? 'neutral' : null;
  const off = day.kind === 'off';
  const pair = tone ? theme.colors.status[tone] : null;
  const ink = pair ? pair.fg : theme.colors.text;
  const title =
    day.kind === 'shift' && day.start && day.end
      ? `${formatClock(day.start, clock)} – ${formatClock(day.end, clock)}`
      : day.kind === 'shift'
        ? t('field.ff46.workDay')
        : day.kind === 'timeOff'
          ? t('field.ff46.timeOff')
          : off
            ? t('field.ff46.off')
            : (day.name ?? '');
  const detail = day.kind === 'shift' ? [day.name, day.note].filter(Boolean).join(' · ') : (day.note ?? '');
  return (
    <View
      accessible
      accessibilityLabel={`${t(DAY_KEYS[d.getDay()] ?? DAY_KEYS[0])} ${d.getDate()}, ${title}${detail ? `, ${detail}` : ''}`}
      testID={`ff46-day-${day.date.slice(0, 10)}`}
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[4],
        padding: theme.space[3],
        borderWidth: theme.borderWidth.card,
        borderColor: pair ? pair.rule : theme.colors.border,
        borderRadius: theme.radius.lg,
        backgroundColor: pair ? pair.bg : theme.colors.card,
      }}
    >
      <View style={{ alignItems: 'center', minWidth: theme.touch.control }}>
        <AppText variant="micro" weight="heavy" tone={today && !pair ? 'brand' : 'default'} style={pair ? { color: ink } : undefined}>
          {t(DAY_KEYS[d.getDay()] ?? DAY_KEYS[0]).toUpperCase()}
        </AppText>
        <AppText variant="section" style={pair ? { color: ink } : undefined}>
          {String(d.getDate())}
        </AppText>
      </View>
      <View style={{ flexShrink: 1 }}>
        <AppText variant="body" weight="heavy" tone={off ? 'muted' : 'default'} style={pair ? { color: ink } : undefined}>
          {title}
        </AppText>
        {detail ? (
          <AppText variant="label" tone={pair ? 'default' : 'muted'} style={pair ? { color: ink } : undefined}>
            {detail}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

export function ShiftsScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const tech = useActiveTechnician();
  const captor = useCaptor();
  const [prefs] = useHandsetPrefs();
  const [notice, setNotice] = useState<{ tone: 'warning' | 'info'; text: string } | null>(null);
  const now = services.now();
  const [loaded, reload] = usePortRead(
    () => (tech ? services.shifts.week(tech.technicianId, now) : Promise.resolve(null)),
    [services, tech?.technicianId],
  );
  const week = loaded.state === 'ready' ? loaded.value : null;

  async function act(fn: () => Promise<void>, done?: string) {
    setNotice(null);
    try {
      await fn();
      if (done) setNotice({ tone: 'info', text: done });
    } catch {
      setNotice({ tone: 'warning', text: t('field.me.notSent') });
    }
  }

  async function endShift() {
    if (!tech) return;
    const at = services.now();
    await act(
      () => services.shifts.endShift(captor(), at),
      t('field.ff46.shiftEnded', { time: formatClock(at.toISOString(), prefs.clock) }),
    );
    reload();
  }

  const current = week?.current ?? null;
  const todayKey = now.toISOString().slice(0, 10);

  return (
    <MeScreen
      id="FF-46"
      title={t('field.screen.ff46')}
      leading={{ back: 'FF-44' }}
      footer={
        <Button
          grow
          onPress={() => tech && act(() => services.shifts.requestTimeOff(tech.technicianId))}
          testID="ff46-request-time-off"
        >
          {t('field.ff46.requestTimeOff')}
        </Button>
      }
    >
      {notice ? <Notice tone={notice.tone}>{notice.text}</Notice> : null}
      {current ? (
        <Card tone="plain" testID="ff46-current" style={{ backgroundColor: theme.colors.status.success.bg, borderColor: theme.colors.status.success.rule }}>
          <AppText variant="micro" weight="heavy" style={{ color: theme.colors.status.success.fg }}>
            {t('field.ff46.onShift').toUpperCase()}
          </AppText>
          <AppText variant="title" style={{ color: theme.colors.status.success.fg }}>
            {formatDuration((now.getTime() - Date.parse(current.startedAt)) / 60_000)}
          </AppText>
          <AppText variant="body" style={{ color: theme.colors.status.success.fg }}>
            {t('field.ff46.ofWindow', {
              start: formatClock(current.start, prefs.clock),
              end: formatClock(current.end, prefs.clock),
            })}
          </AppText>
          <Button size="sm" onPress={() => void endShift()} testID="ff46-end-shift">
            {t('field.ff46.endShift')}
          </Button>
        </Card>
      ) : null}
      <Kicker>{t('field.ff46.thisWeek')}</Kicker>
      {week ? (
        week.days.map((day) => (
          // FF-46 T: beside the day, a day picks it.
          <Pickable key={day.date} id={day.date} label={day.date.slice(0, 10)} testID={`ff46-day-${day.date.slice(0, 10)}-pick`}>
            <DayRow day={day} clock={prefs.clock} today={day.date.slice(0, 10) === todayKey} />
          </Pickable>
        ))
      ) : loaded.state === 'loading' ? null : (
        <EmptyState title={t('field.me.notHereYet')} helper={t('field.ff46.emptyHelper')} testID="ff46-not-wired" />
      )}
    </MeScreen>
  );
}
