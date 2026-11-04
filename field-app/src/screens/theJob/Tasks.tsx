/**
 * FF-17 Tasks — the steps, worked in order, photographs taken on the step
 * (R6, R110), steps added in the field marked as such (R7). Built from
 * `phone/FF-17-tasks.png` / `tablet/FF-17-T-tasks.png`.
 *
 * Under the title: how far through the steps, the two clocks (R9) and the
 * template's estimate. Doors: back → FF-15, *Add a step* → FF-18, *Materials*
 * → FF-23, *Readings* → FF-20.
 *
 * Tasks stay locked until every safety row is ticked (R3): opened before then,
 * this screen says so and sends the technician to the job, where Continue
 * leads to Safety. (FF-17 has no door to FF-16 on the board.)
 */
import { useTranslation } from 'react-i18next';

import { AppText, Button, DashedButton, Glyph, Notice, ProgressBar } from '../../components';
import { shortDuration } from './format';
import { JobScreen, useDoor } from './JobScreen';
import { safetyPassed } from './jobModel';
import { TaskList } from './TaskList';
import { useOpenJob } from './useJob';

export function Tasks() {
  const { t } = useTranslation();
  const go = useDoor('FF-17');
  const { port, view } = useOpenJob();
  const units = { h: t('field.job.unit.h'), m: t('field.job.unit.m') };
  const done = view?.tasks.done ?? 0;
  const total = view?.tasks.total ?? 0;
  const locked = !safetyPassed(view);

  return (
    <JobScreen
      id="FF-17"
      title={t('field.screen.ff17')}
      back={{ to: 'FF-15', label: t('field.job.backToJob') }}
      trailing={
        <AppText variant="body" weight="heavy" testID="tasks-count">
          {t('field.job.nOfM', { done, total })}
        </AppText>
      }
      footer={
        <>
          <Button grow onPress={() => go('FF-23')} testID="door-FF-23">
            {t('field.ff17.materials')}
          </Button>
          <Button grow variant="primary" onPress={() => go('FF-20')} testID="door-FF-20">
            {t('field.ff17.readings')}
          </Button>
        </>
      }
    >
      <ProgressBar
        done={done}
        total={total}
        label={t('field.screen.ff17')}
        left={
          view
            ? t('field.ff17.clocks', {
                travel: shortDuration(view.travel.minutes, units),
                onSite: shortDuration(view.labour.minutes, units),
              })
            : undefined
        }
        right={view && view.tasks.estMinutes > 0 ? t('field.ff17.estimate', { count: view.tasks.estMinutes }) : undefined}
        testID="tasks-progress"
      />
      {view === null ? <Notice tone="info">{t('field.job.noJob')}</Notice> : null}
      {view !== null && locked ? (
        <Notice tone="warning" icon={<Glyph name="warning" />} testID="tasks-locked">
          {t('field.ff17.locked')}
        </Notice>
      ) : null}
      {view !== null && !locked ? <TaskList port={port} view={view} /> : null}
      <DashedButton
        icon={<Glyph name="more" />}
        label={t('field.ff17.addStep')}
        onPress={() => go('FF-18')}
        testID="door-FF-18"
      />
    </JobScreen>
  );
}
