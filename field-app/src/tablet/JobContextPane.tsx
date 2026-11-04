/**
 * The job context pane (T-29) — ONE pane, beside every T3 screen of a job
 * (FF-14, FF-16…FF-19, FF-22…FF-27, FF-30, FF-32…FF-34, FF-36, FF-37,
 * FF-58…FF-61). Built from the boards FF-16 T, FF-25 T, FF-22 T and FF-33 T,
 * which draw it the same every time:
 *
 *   WORK ORDER · *WO-4821* · *Meter exchange · P2*
 *   WHERE      — the street, then the unit and the town
 *   CUSTOMER   — the name and the account
 *   CLOCKS     — *Travel 14m · on site 1h 12m*
 *   *The whole job* — back to FF-15
 *
 * and, between the heading and *Where*, THE JOB'S OWN STEPS — Safety, Tasks,
 * Materials, Readings, Photos, each with its count — which FF-20 T and FF-21 T
 * draw down the left edge while a step is open. The step you are on is marked
 * the way the sidebar marks its screen (the brand rule down the left edge).
 * ⚠ Putting the steps HERE rather than in the sidebar is our judgment: the
 * sidebar is the app's menu on every other board, and swapping its contents
 * while a job is open is a navigation change the brief did not ask for.
 * Reported.
 *
 * Which job: the route's `workOrderId` (the param every job door carries),
 * else `jobId` (what FF-10 and FF-14 carry), else the job already open. The
 * pane reads the store through the job services (`theJob/JobPort`) and
 * re-reads after every capture, so a tick on FF-16 shows in the pane at once.
 * No job → it says so, in one line, and draws nothing else (never a made-up
 * order).
 *
 * The customer's MONEY is never here (R16, R26): a name and an account number
 * only.
 */
import { type NavigationProp, type ParamListBase, useIsFocused, useNavigation, useRoute } from '@react-navigation/native';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { AppText, Button, Card, Glyph, Kicker, Notice } from '../components';
import { textStyle } from '../components/AppText';
import { type ScreenId } from '../navigation/screens';
import { openScreen } from '../screens/theDay/go';
import { shortDuration } from '../screens/theJob/format';
import { useJobPort } from '../screens/theJob/JobPort';
import { type JobView, loadJob } from '../screens/theJob/jobModel';
import { useTheme } from '../theme';

/** The job a pane is about: `workOrderId`, then `jobId`, then the job already open. */
export function useContextJob(): { workOrderId: string | null; view: JobView | null } {
  const port = useJobPort();
  const route = useRoute();
  const focused = useIsFocused();
  const params = (route.params ?? {}) as Record<string, unknown>;
  const fromRoute =
    typeof params.workOrderId === 'string' ? params.workOrderId : typeof params.jobId === 'string' ? params.jobId : null;
  const workOrderId = fromRoute ?? port?.openJobId ?? null;
  const version = port?.version ?? 0;
  const view = useMemo(
    () => (port && workOrderId ? loadJob(port, workOrderId) : null),
    // `version` and `focused` are re-read triggers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [port, workOrderId, version, focused],
  );
  return { workOrderId, view };
}

interface Step {
  id: ScreenId;
  labelKey: string;
  done: number;
  total: number;
  /** Shown instead of "n of m" (Materials: "1 short"). */
  note?: string;
}

export function jobSteps(view: JobView): Step[] {
  return [
    { id: 'FF-16', labelKey: 'field.ff15.safety', done: view.safety.done, total: view.safety.total },
    { id: 'FF-17', labelKey: 'field.ff15.tasks', done: view.tasks.done, total: view.tasks.total },
    { id: 'FF-23', labelKey: 'field.ff15.materials', done: view.materials.satisfied, total: view.materials.planned.length },
    { id: 'FF-20', labelKey: 'field.ff15.readings', done: view.readings.taken, total: view.readings.total },
    { id: 'FF-21', labelKey: 'field.screen.ff21', done: view.photos.length, total: -1 },
  ];
}

/** One step of the job, marked when it is the screen on show. */
function StepRow(props: { step: Step; current: boolean; onPress: () => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const c = theme.colors;
  const { step, current } = props;
  const complete = step.total > 0 && step.done >= step.total;
  const count = step.total < 0 ? String(step.done) : step.total === 0 ? '' : t('field.job.nOfM', { done: step.done, total: step.total });
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={[t(step.labelKey), count].filter(Boolean).join(', ')}
      accessibilityState={{ selected: current }}
      onPress={props.onPress}
      testID={`job-pane-step-${step.id}`}
      style={{
        minHeight: theme.touch.control,
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[3],
        paddingHorizontal: theme.space[3],
        borderLeftWidth: theme.space[1],
        borderLeftColor: current ? c.brand : 'transparent',
        backgroundColor: current ? c.surface : 'transparent',
      }}
    >
      {complete ? <Glyph name="check" colour={c.statusInk.success} size={theme.type.section} /> : null}
      <Text style={[textStyle(theme, 'body', current ? 'heavy' : 'regular'), { flexGrow: 1 }]}>{t(step.labelKey)}</Text>
      {count ? <Text style={textStyle(theme, 'label', 'regular', 'muted')}>{count}</Text> : null}
    </Pressable>
  );
}

export function JobContextPane() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  const route = useRoute();
  const port = useJobPort();
  const { workOrderId, view } = useContextJob();
  const units = { h: t('field.job.unit.h'), m: t('field.job.unit.m') };

  const go = (id: ScreenId) => {
    if (!workOrderId) return;
    port?.setOpenJobId(workOrderId);
    openScreen(navigation, id, { workOrderId });
  };

  if (!view) {
    return (
      <View style={{ padding: theme.space[4] }} testID="job-context-pane">
        <Notice tone="info" testID="job-context-none">
          {t('field.job.noJob')}
        </Notice>
      </View>
    );
  }

  const order = view.order;
  const premise = view.premise;
  const place = premise ? [premise.locality, [premise.region, premise.postal_code].filter(Boolean).join(' ')].filter(Boolean).join(', ') : '';
  const kind = [order.type, order.priority_code].filter(Boolean).join(' · ');

  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      style={{ flex: 1 }}
      contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }}
      testID="job-context-pane"
    >
      <View>
        <Kicker>{t('field.tablet.job.kicker')}</Kicker>
        <AppText variant="title" testID="job-context-number">
          {order.number ?? order.id}
        </AppText>
        {kind ? (
          <AppText variant="label" tone="muted">
            {kind}
          </AppText>
        ) : null}
      </View>

      <Card testID="job-context-steps">
        {jobSteps(view).map((step) => (
          <StepRow key={step.id} step={step} current={route.name === step.id} onPress={() => go(step.id)} />
        ))}
      </Card>

      {premise ? (
        <Card testID="job-context-where">
          <Kicker>{t('field.tablet.job.where')}</Kicker>
          <AppText variant="body" weight="heavy">
            {premise.address_line ?? ''}
          </AppText>
          {place ? (
            <AppText variant="label" tone="muted">
              {place}
            </AppText>
          ) : null}
        </Card>
      ) : null}

      {view.customer ? (
        <Card testID="job-context-customer">
          <Kicker>{t('field.tablet.job.customer')}</Kicker>
          <AppText variant="body" weight="heavy">
            {view.customer.name ?? ''}
          </AppText>
          {view.customer.account_number ? (
            <AppText variant="label" tone="muted">
              {view.customer.account_number}
            </AppText>
          ) : null}
        </Card>
      ) : null}

      <Card testID="job-context-clocks">
        <Kicker>{t('field.tablet.job.clocks')}</Kicker>
        <AppText variant="label">
          {t('field.tablet.job.clockLine', {
            travel: shortDuration(view.travel.minutes, units),
            site: shortDuration(view.labour.minutes, units),
          })}
        </AppText>
      </Card>

      <Button onPress={() => go('FF-15')} testID="job-context-whole">
        {t('field.tablet.job.whole')}
      </Button>
    </ScrollView>
  );
}
