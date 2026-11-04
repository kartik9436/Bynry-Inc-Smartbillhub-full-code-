/**
 * FF-15 T *The job with its tasks beside it* (T-28; image
 * `tablet/FF-15-T-job.png`).
 *
 *   CONTEXT — the job itself, under its own bar (back to Today, *WO-4822*):
 *             what the phone's FF-15 shows above its footer (`JobDetails`),
 *             with *Hand it back* at its foot.
 *   CONTENT — the steps, under *Tasks · 3 of 8*: the same task list FF-17
 *             draws (`TaskList`), so a step is ticked, photographed and added
 *             to right here, beside the job — or, while safety is not done,
 *             the line that says so (R3).
 *
 * FF-15 is the one T3 screen that does NOT get the shared job pane: on its
 * board the job IS the context. The content carries `screen-FF-15`, the
 * address a job test finds this screen by.
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, DashedButton, Glyph, Notice } from '../../components';
import { useHistoryBack } from '../../navigation/back';
import { JobDetails } from '../../screens/theJob/JobOverview';
import { useDoor } from '../../screens/theJob/JobScreen';
import { safetyPassed } from '../../screens/theJob/jobModel';
import { TaskList } from '../../screens/theJob/TaskList';
import { useOpenJob } from '../../screens/theJob/useJob';
import { useTheme } from '../../theme';
import { PaneScreen } from './parts';

export function JobContext() {
  const { t } = useTranslation();
  const go = useDoor('FF-15');
  const { view } = useOpenJob();
  // DEF-FLD-10607: back through history; Today (the drawn door) only without it.
  const back = useHistoryBack({ label: t('field.ff15.backToToday'), follow: () => go('FF-10') });
  return (
    <PaneScreen
      title={view?.order.number ?? t('field.screen.ff15')}
      onBack={back.onBack}
      backLabel={back.label}
      backTestID="door-FF-10"
      testID="job-pane"
      footer={
        <Button grow onPress={() => go('FF-58')} testID="door-FF-58">
          {t('field.ff15.handBack')}
        </Button>
      }
    >
      <JobDetails />
    </PaneScreen>
  );
}

export function JobTasks() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { port, view } = useOpenJob();
  const done = view?.tasks.done ?? 0;
  const total = view?.tasks.total ?? 0;
  const locked = !safetyPassed(view);
  return (
    <View style={{ flex: 1 }} testID="screen-FF-15">
      <PaneScreen
        title={t('field.screen.ff17')}
        trailing={
          <AppText variant="body" weight="heavy" testID="tasks-count">
            {t('field.job.nOfM', { done, total })}
          </AppText>
        }
        testID="job-tasks-pane"
      >
        {view === null ? <Notice tone="info">{t('field.job.noJob')}</Notice> : null}
        {view !== null && locked ? (
          <Notice tone="warning" icon={<Glyph name="warning" />} testID="tasks-locked">
            {t('field.ff17.locked')}
          </Notice>
        ) : null}
        {view !== null && !locked ? <TaskList port={port} view={view} /> : null}
        <View style={{ paddingTop: theme.space[1] }}>
          <AddStepButton />
        </View>
      </PaneScreen>
    </View>
  );
}

/** *Add a step* — FF-17's door to FF-18, drawn under the tasks on FF-15 T. */
function AddStepButton() {
  const { t } = useTranslation();
  const go = useDoor('FF-17');
  return <DashedButton icon={<Glyph name="more" />} label={t('field.ff17.addStep')} onPress={() => go('FF-18')} testID="pane-FF-18" />;
}
