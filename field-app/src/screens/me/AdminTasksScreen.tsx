/**
 * FF-48 Admin tasks (T-24; US-FLD-017; image `phone/FF-48-admin-tasks.png`).
 *
 * Work that is not a job, on a clock: vehicle check, training, depot time,
 * crew meeting, something else. The card at the top says what is running (or
 * that nothing is, and how much admin time today holds); tapping a task
 * starts its clock and stops whatever was running — one clock at a time,
 * because a person is in one place (R8: labour is per person).
 *
 * Each start and stop is captured through the outbox as `crew_time`
 * (`dbData.ts`), which waits for its server door (`N17`). The drawing's
 * *Something else · Name it* would need typing; the app taps and never types
 * (R38), so it starts an unnamed "other" clock — naming it by voice is
 * reported, not invented.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, ListRow, Notice } from '../../components';
import { Pickable } from '../../tablet/Pickable';
import { usePick } from '../../tablet/selection';
import { useTheme } from '../../theme';
import { formatClock, formatDuration } from './format';
import { useActiveTechnician, useCaptor, useHandsetPrefs } from './hooks';
import { MeScreen, useDoor } from './MeScreen';
import { ADMIN_TASKS, type AdminTask, useMeServices } from './services';
import { ADMIN_TASK_KEY, totals } from './TimesheetScreen';

const HELP_KEY: Record<AdminTask, string> = {
  vehicleCheck: 'field.ff48.help.vehicleCheck',
  training: 'field.ff48.help.training',
  depot: 'field.ff48.help.depot',
  crewMeeting: 'field.ff48.help.crewMeeting',
  other: 'field.ff48.help.other',
};

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

export function AdminTasksScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const door = useDoor('FF-48');
  const tech = useActiveTechnician();
  const captor = useCaptor();
  const [prefs] = useHandsetPrefs();
  const [, setVersion] = useState(0);
  const [problem, setProblem] = useState(false);
  const pick = usePick();
  const now = services.now();

  const from = startOfDay(now);
  const to = new Date(from);
  to.setDate(to.getDate() + 1);
  const today = tech ? services.data.timesheet(tech.technicianId, from, to) : null;
  const running = tech ? services.data.runningClock(tech.technicianId) : null;
  const adminToday = today ? totals(today.filter((e) => e.kind === 'admin'), now).all : null;

  function act(fn: () => void) {
    setProblem(false);
    try {
      fn();
      setVersion((v) => v + 1);
    } catch {
      setProblem(true);
    }
  }

  function lastDone(task: AdminTask) {
    const done = (today ?? []).filter((e) => e.kind === 'admin' && e.adminTask === task && e.endedAt);
    const last = done.at(-1);
    if (!last || !last.endedAt) return null;
    const minutes = Math.round((Date.parse(last.endedAt) - Date.parse(last.startedAt)) / 60_000);
    return t('field.ff48.doneAt', { time: formatClock(last.startedAt, prefs.clock), duration: formatDuration(minutes) });
  }

  const runningTitle = running
    ? running.kind === 'admin'
      ? t(running.adminTask ? ADMIN_TASK_KEY[running.adminTask] : 'field.ff47.admin')
      : (running.workOrderNumber ?? t('field.ff47.labour'))
    : null;

  return (
    <MeScreen
      id="FF-48"
      title={t('field.screen.ff48')}
      leading="drawer"
      footer={
        <Button grow onPress={() => door('FF-47')} testID="door-FF-47">
          {t('field.nav.item.timesheet')}
        </Button>
      }
    >
      {problem ? <Notice tone="warning">{t('field.me.notSaved')}</Notice> : null}
      <Card title={running ? t('field.ff48.running') : t('field.ff48.notRunning')} testID="ff48-state">
        {running ? (
          <View style={{ gap: theme.space[2] }}>
            <AppText variant="section">{runningTitle ?? ''}</AppText>
            <AppText variant="body" tone="muted">
              {t('field.ff47.since', { time: formatClock(running.startedAt, prefs.clock) })}
            </AppText>
            <Button size="sm" onPress={() => tech && act(() => services.data.stopClock(captor(), services.now()))} testID="ff48-stop">
              {t('field.ff48.stop')}
            </Button>
          </View>
        ) : (
          <AppText variant="body" tone="muted" testID="ff48-recorded">
            {adminToday == null ? t('field.me.notHereYet') : t('field.ff48.recordedToday', { duration: formatDuration(adminToday) })}
          </AppText>
        )}
      </Card>
      <AppText variant="micro" weight="heavy" tone="muted">
        {t('field.ff48.startSomething').toUpperCase()}
      </AppText>
      {ADMIN_TASKS.map((task) =>
        // FF-48 T: beside the task, a row picks it and the task starts from there.
        pick.active ? (
          <Pickable key={task} id={task} label={t(ADMIN_TASK_KEY[task])} testID={`ff48-task-${task}-pick`}>
            <Card>
              <ListRow label={t(ADMIN_TASK_KEY[task])} detail={lastDone(task) ?? t(HELP_KEY[task])} />
            </Card>
          </Pickable>
        ) : (
          <Card key={task}>
            <ListRow
              label={t(ADMIN_TASK_KEY[task])}
              detail={lastDone(task) ?? t(HELP_KEY[task])}
              onPress={() => tech && act(() => services.data.startAdmin(captor(), task, services.now()))}
              disabled={!services.data.wired || (running?.kind === 'admin' && running.adminTask === task)}
              testID={`ff48-start-${task}`}
            />
          </Card>
        ),
      )}
    </MeScreen>
  );
}
