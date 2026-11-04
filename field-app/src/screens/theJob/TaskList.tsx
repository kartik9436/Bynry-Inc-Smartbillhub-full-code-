/**
 * The job's steps, in the template's order with the field's additions among
 * them (FF-17, and the right-hand pane of FF-15 on a tablet).
 *
 * The step being worked is open: its photographs are TAKEN HERE, on the step
 * (R6 — the gallery is a review, never the place of capture), as many as the
 * template asks for (R110), in a strip with the camera tile beside them. Short
 * of an EXPECTED count is a WARNING and *Mark done* stays pressable (R110:
 * *"Short of the count warns and never blocks"*). A step added in the field
 * says so, with who and when (R7).
 *
 * ⚠ **A REQUIRED PHOTO BLOCKS — PO 2026-10-24 (MQ-017, CR-187-BRC10):** *"B.
 * Block on a required photo - but show warning message to field technician"*.
 * A step whose template marks its photo REQUIRED (`photo_required`) cannot be
 * marked done until its photographs are taken; in place of a silent grey
 * button it says *"Take 1 photo to finish this step."*, and the same sentence
 * is the button's accessibility hint. The server still accepts a tick and
 * records the gap (`photos_missing`), because a refusal there would arrive
 * after the technician has left — the block lives where the tap happens.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, Text, View } from 'react-native';

import { AppText, Button, Card, DashedButton, Glyph, Kicker, Notice, PhotoThumb, textStyle } from '../../components';
import { useTheme } from '../../theme';
import { capturePhoto, tickTask } from './actions';
import { hhmm } from './format';
import type { JobPortValue } from './JobPort';
import type { JobView, TaskView } from './jobModel';
import { pathOf } from './photoStamp';
import { usePhotoTaker } from './usePhotoTaker';

function NumberBox({ n, strong }: { n: number; strong: boolean }) {
  const theme = useTheme();
  const side = theme.touch.control / 2 + theme.space[2];
  return (
    <View
      accessible={false}
      style={{
        width: side,
        height: side,
        alignItems: 'center',
        justifyContent: 'center',
        borderWidth: strong ? theme.borderWidth.emphasis : theme.borderWidth.control,
        borderColor: strong ? theme.colors.text : theme.colors.controlBorder,
      }}
    >
      <AppText variant="label" weight="heavy" accessibilityRole="none">
        {String(n)}
      </AppText>
    </View>
  );
}

function DoneMark() {
  const theme = useTheme();
  const side = theme.touch.control / 2 + theme.space[2];
  return (
    <View
      accessible={false}
      style={{ width: side, height: side, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.colors.status.success.rule }}
    >
      <Glyph name="check" colour={theme.colors.card} />
    </View>
  );
}

/** Photographs a REQUIRED step still lacks before it may be marked done; 0 when it only warns (R110). */
export function requiredPhotosShort(task: TaskView): number {
  return task.row.photo_required ? Math.max(0, task.photoMin - task.photos.length) : 0;
}

export function TaskList({ port, view }: { port: JobPortValue | null; view: JobView }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [chosen, setChosen] = useState<string | null>(null);
  const camera = usePhotoTaker(port, view.order.number ?? '');
  const tasks = view.tasks.items;
  const open = tasks.find((x) => x.row.id === chosen && !x.done) ?? tasks.find((x) => !x.done) ?? null;

  const minutesLine = (task: TaskView) => {
    const parts: string[] = [];
    if (task.detail.minutes) parts.push(t('field.job.minutes', { count: task.detail.minutes }));
    if (task.row.must_do) parts.push(t('field.ff17.mustDo'));
    if (task.row.added_in_field) parts.push(`${task.detail.added_by ?? ''} ${hhmm(task.detail.added_at)}`.trim());
    return parts.join(' · ');
  };

  const takePhoto = async (task: TaskView) => {
    const photo = await camera.take();
    if (!port || !photo) return;
    capturePhoto(port, view.order.id, photo, { task_id: task.row.id });
    port.changed();
  };

  const markDone = (task: TaskView) => {
    if (!port || requiredPhotosShort(task) > 0) return;
    tickTask(port, view.order.id, task.row.id);
    setChosen(null);
    port.changed();
  };

  return (
    <View style={{ gap: theme.space[2] }} testID="task-list">
      {tasks.map((task, i) => {
        const n = i + 1;
        const label = `${n} · ${task.row.label}`;
        if (task.done) {
          return (
            <View
              key={task.row.id}
              testID={`task-${task.row.id}`}
              accessible
              accessibilityLabel={t('field.ff17.doneA11y', { label })}
              style={{
                minHeight: theme.touch.primary,
                flexDirection: 'row',
                alignItems: 'center',
                gap: theme.space[3],
                padding: theme.space[3],
                backgroundColor: theme.colors.card,
                borderWidth: theme.borderWidth.card,
                borderColor: theme.colors.border,
              }}
            >
              <DoneMark />
              <Text style={[textStyle(theme, 'body', 'regular', 'muted'), { flexGrow: 1, flexShrink: 1, textDecorationLine: 'line-through' }]}>
                {label}
              </Text>
              {task.photos.slice(0, 2).map((p) => (
                <PhotoThumb key={p.id} path={pathOf(p)} label={t('field.job.photoAt', { time: hhmm(p.captured_at) })} caption={hhmm(p.captured_at)} />
              ))}
            </View>
          );
        }
        if (open && task.row.id === open.row.id) {
          const short = Math.max(0, task.photoMin - task.photos.length);
          const blocked = requiredPhotosShort(task);
          const blockedWords = blocked > 0 ? t('field.ff17.photoToFinish', { count: blocked }) : undefined;
          return (
            <Card key={task.row.id} testID={`task-${task.row.id}`} tone={task.row.added_in_field ? 'info' : 'plain'} title={task.row.added_in_field ? t('field.ff17.addedInField') : undefined}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
                <NumberBox n={n} strong />
                <View style={{ flexShrink: 1 }}>
                  <AppText variant="section">{task.row.label}</AppText>
                  {minutesLine(task) ? (
                    <AppText variant="label" tone="muted">
                      {minutesLine(task)}
                    </AppText>
                  ) : null}
                </View>
              </View>
              {task.detail.instruction ? (
                <AppText variant="body" testID="task-instruction">
                  {task.detail.instruction}
                </AppText>
              ) : null}
              {task.photoMin > 0 ? (
                <>
                  <Notice tone={short > 0 ? 'warning' : 'success'} icon={<Glyph name="camera" />} testID="task-photo-count">
                    {t('field.ff17.photoCount', { count: task.photoMin, taken: task.photos.length })}
                  </Notice>
                  <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space[2] }}>
                    {task.photos.map((p, k) => (
                      <PhotoThumb
                        key={p.id}
                        path={pathOf(p)}
                        label={task.detail.photo_labels?.[k] ?? t('field.job.photoAt', { time: hhmm(p.captured_at) })}
                        caption={hhmm(p.captured_at)}
                      />
                    ))}
                    <DashedButton
                      grow
                      icon={<Glyph name="camera" />}
                      label={short > 0 ? t('field.ff17.morePhotos', { count: short }) : t('field.ff17.anotherPhoto')}
                      onPress={() => void takePhoto(task)}
                      disabled={camera.busy}
                      testID="task-take-photo"
                    />
                  </View>
                  {camera.error ? (
                    <Notice tone="danger" testID="task-camera-error">
                      {camera.error}
                    </Notice>
                  ) : null}
                </>
              ) : null}
              {blockedWords ? (
                <Notice tone="warning" icon={<Glyph name="warning" />} testID="task-photo-required">
                  {blockedWords}
                </Notice>
              ) : null}
              <Button onPress={() => markDone(task)} disabled={blocked > 0} accessibilityHint={blockedWords} testID="task-mark-done">
                {t('field.ff17.markDone')}
              </Button>
            </Card>
          );
        }
        return (
          <View key={task.row.id} style={{ gap: theme.space[1] }}>
            {task.row.added_in_field ? <Kicker tone="brand">{t('field.ff17.addedInField')}</Kicker> : null}
            <Pressable
              testID={`task-${task.row.id}`}
              accessibilityRole="button"
              accessibilityLabel={[label, minutesLine(task)].filter(Boolean).join(', ')}
              onPress={() => setChosen(task.row.id)}
              style={{
                minHeight: theme.touch.primary,
                flexDirection: 'row',
                alignItems: 'center',
                gap: theme.space[3],
                padding: theme.space[3],
                backgroundColor: theme.colors.card,
                borderWidth: task.row.added_in_field ? theme.borderWidth.emphasis : theme.borderWidth.card,
                borderColor: task.row.added_in_field ? theme.colors.status.info.rule : theme.colors.border,
              }}
            >
              <NumberBox n={n} strong={false} />
              <AppText variant="body" style={{ flexGrow: 1, flexShrink: 1 }}>
                {task.row.label}
              </AppText>
              <AppText variant="label" tone="muted">
                {task.photoMin > 0
                  ? t('field.ff17.photosAsked', { count: task.photoMin })
                  : task.detail.minutes
                    ? t('field.job.minutesShort', { count: task.detail.minutes })
                    : ''}
              </AppText>
            </Pressable>
          </View>
        );
      })}
    </View>
  );
}
