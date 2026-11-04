/**
 * FF-16 Safety — the gate before work. R3 (repo `BR-WRK-037`): *"All safety
 * checks or none. Two of four ticked is locked, not half unlocked. The server
 * re-derives the lock and refuses a completion carrying an unticked row,
 * naming it."* So: each row is one tap and one captured `safety_tick`; the
 * tasks below stay LOCKED, and *Open tasks* stays unavailable with its reason
 * on the button, until every row is ticked. The screen's lock is a courtesy —
 * the server's is the guarantee.
 *
 * A tick is an act, captured with its key; it is not taken back by a second
 * tap (the server has no un-tick item), so a ticked row is shown done.
 *
 * Built from `phone/FF-16-safety.png` / `tablet/FF-16-T-safety.png`. Doors:
 * back → FF-15, *Open tasks* → FF-17.
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, CheckRow, Glyph, Notice } from '../../components';
import { useTheme } from '../../theme';
import { tickSafety } from './actions';
import { JobScreen, useDoor } from './JobScreen';
import { safetyPassed } from './jobModel';
import { useOpenJob } from './useJob';

/** How many locked steps the preview lists before "+ N more". */
export const LOCKED_PREVIEW = 3;

export function Safety() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-16');
  const { port, view } = useOpenJob();
  const done = view?.safety.done ?? 0;
  const total = view?.safety.total ?? 0;
  // No job open → nothing is locked (and FF-17 says there is no job).
  const open = safetyPassed(view);
  const tasks = view?.tasks.items ?? [];

  return (
    <JobScreen
      id="FF-16"
      title={t('field.screen.ff16')}
      back={{ to: 'FF-15', label: t('field.job.backToJob') }}
      trailing={
        <AppText variant="body" weight="heavy" testID="safety-count">
          {t('field.job.nOfM', { done, total })}
        </AppText>
      }
      footer={
        <Button
          grow
          variant="primary"
          disabled={!open}
          onPress={() => go('FF-17')}
          testID="door-FF-17"
        >
          {open ? t('field.ff16.openTasks') : t('field.ff16.tasksLocked')}
        </Button>
      }
    >
      {view === null ? <Notice tone="info">{t('field.job.noJob')}</Notice> : null}
      {view !== null && !open ? (
        <Notice tone="warning" icon={<Glyph name="warning" />} testID="safety-locked">
          {t('field.ff16.lockedNotice', { count: total })}
        </Notice>
      ) : null}
      <View style={{ gap: theme.space[2] }}>
        {(view?.safety.items ?? []).map((row) => (
          <CheckRow
            key={row.id}
            label={row.label}
            checked={row.state === 'ticked'}
            disabled={row.state === 'ticked' || !port}
            onPress={() => {
              if (!port || !view) return;
              tickSafety(port, view.order.id, row.id);
              port.changed();
            }}
            testID={`safety-${row.id}`}
          />
        ))}
      </View>
      {!open && tasks.length > 0 ? (
        <Card title={t('field.ff16.locked')} testID="safety-locked-tasks">
          {tasks.slice(0, LOCKED_PREVIEW).map((task, i) => (
            <AppText key={task.row.id} variant="body" tone="muted">
              {`${i + 1} · ${task.row.label}`}
            </AppText>
          ))}
          {tasks.length > LOCKED_PREVIEW ? (
            <AppText variant="label" tone="muted">
              {t('field.ff16.more', { count: tasks.length - LOCKED_PREVIEW })}
            </AppText>
          ) : null}
        </Card>
      ) : null}
    </JobScreen>
  );
}
