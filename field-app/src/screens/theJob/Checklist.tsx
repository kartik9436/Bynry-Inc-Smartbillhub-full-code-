/**
 * FF-19 Checklist — questions that branch on the answer (requirement 18,
 * US-FLD-018). A question with `show_if` is asked only when the question it
 * depends on was answered that way, and says *Because you said yes* (TC-1);
 * answered otherwise, it does not appear (TC-3). Answers are taps (R38) —
 * Yes / No — except a figure, which carries its unit (R12).
 *
 * The line under an answer ("No opens a tamper report") is the TEMPLATE's own
 * words, read from the question's detail, never this app's.
 *
 * *Save and exit* keeps what is answered (TC-4: FF-15 then shows *3 of 5*);
 * *Submit* is available once every question still asked is answered.
 *
 * ⚠ An answer is held on the handset (`wo_item.state`) and has no outbox kind
 * to travel in — the server has no checklist-answer item and the unrouted
 * list has none either (`actions.ts`). Reported; nothing pretends it was sent.
 *
 * Built from `phone/FF-19-checklist.png`. Doors: back and *Save and exit* →
 * FF-17 (the board links nothing else).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, ChoiceChips, Field, Kicker, Notice, ProgressBar, StatusChip } from '../../components';
import { useTheme } from '../../theme';
import { saveChecklistAnswer } from './actions';
import { JobScreen, useDoor } from './JobScreen';
import { parseTyped } from './readingCheck';
import { useOpenJob } from './useJob';

export function Checklist() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-19');
  const { port, view } = useOpenJob();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const items = view?.checklist.items ?? [];
  const shown = items.filter((q) => q.visible);
  const answered = view?.checklist.answered ?? 0;
  const total = view?.checklist.total ?? 0;
  const complete = total > 0 && answered === total;

  const answer = (id: string, value: string | null) => {
    if (!port) return;
    saveChecklistAnswer(port, id, value);
    port.changed();
  };

  return (
    <JobScreen
      id="FF-19"
      title={t('field.screen.ff19')}
      back={{ to: 'FF-17', label: t('field.ff19.backToTasks') }}
      trailing={
        total > 0 ? (
          <StatusChip tone={complete ? 'success' : 'warning'}>
            {complete ? t('field.ff15.state.done') : t('field.ff15.state.inProgress')}
          </StatusChip>
        ) : null
      }
      footer={
        <>
          <Button grow onPress={() => go('FF-17')} testID="checklist-save-exit">
            {t('field.ff19.saveExit')}
          </Button>
          <Button grow variant="primary" disabled={!complete} onPress={() => go('FF-17')} testID="checklist-submit">
            {t('field.ff19.submit')}
          </Button>
        </>
      }
    >
      <ProgressBar
        done={answered}
        total={total}
        label={t('field.screen.ff19')}
        left={t('field.ff19.answered', { done: answered, total })}
        testID="checklist-progress"
      />
      {view === null ? <Notice tone="info">{t('field.job.noJob')}</Notice> : null}
      {shown.map((q, i) => {
        const n = i + 1;
        const value = q.row.state && q.row.state !== '' ? q.row.state : null;
        const hint = value ? q.detail.hints?.[value] : undefined;
        return (
          <Card key={q.row.id} tone={q.because ? 'info' : 'plain'} testID={`question-${q.row.id}`}>
            {q.because ? (
              <Kicker tone="default" testID={`because-${q.row.id}`}>
                {t('field.ff19.because', { answer: q.detail.show_if?.answer === 'yes' ? t('field.ff19.yes') : t('field.ff19.no') })}
              </Kicker>
            ) : null}
            <AppText variant="body" weight="semibold">{`${n}  ${q.row.label}`}</AppText>
            {q.detail.answer_type === 'number' ? (
              <Field
                label={q.row.label}
                value={drafts[q.row.id] ?? value ?? ''}
                onChangeText={(text) => setDrafts((d) => ({ ...d, [q.row.id]: text }))}
                keyboardType="decimal-pad"
                unit={q.detail.unit}
                testID={`answer-${q.row.id}`}
              />
            ) : (
              <ChoiceChips
                label={q.row.label}
                fill
                active={value}
                onSelect={(id) => answer(q.row.id, id)}
                segments={[
                  { id: 'yes', label: t('field.ff19.yes') },
                  { id: 'no', label: t('field.ff19.no') },
                ]}
                testID={`answer-${q.row.id}`}
              />
            )}
            {q.detail.answer_type === 'number' && drafts[q.row.id] !== undefined ? (
              <Button
                size="sm"
                onPress={() => {
                  const parsed = parseTyped(drafts[q.row.id] ?? '');
                  answer(q.row.id, parsed);
                  setDrafts(({ [q.row.id]: _gone, ...rest }) => rest);
                }}
                testID={`answer-${q.row.id}-save`}
              >
                {t('field.job.save')}
              </Button>
            ) : null}
            {hint ? (
              <AppText variant="label" tone="muted" testID={`hint-${q.row.id}`}>
                {hint}
              </AppText>
            ) : null}
          </Card>
        );
      })}
      <View style={{ height: theme.space[2] }} />
    </JobScreen>
  );
}
