/**
 * FF-32 Debrief — my labour and travel, the parts used, what the problem was
 * and what I did, before the close (US-FLD-022; R9, R38, R95).
 *
 *   LABOUR — the signed-in technician's own clocks on this job (R8: per
 *     person), correctable here (R9) with the same sheet as FF-29.
 *   PARTS — the job's materials and how many were used; *Change what was
 *     used* opens FF-24.
 *   PROBLEM FOUND · WHAT I DID — typed or dictated (R38: dictation beside
 *     every note), never required (R95). They go on the close and become the
 *     meter's history.
 *
 * *Close the job* opens FF-33 Signature with the draft (`draft.ts`).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Field } from '../../components/Field';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { ScreenFrame } from '../../components/ScreenFrame';
import { fromJson } from '../../db/json';
import * as crewOrderQ from '../../db/queries/crewTimeOrder';
import * as woItemQ from '../../db/queries/woItem';
import { useTheme } from '../../theme';
import { NotOnPhone, useRefresh, type WaveScreenProps } from '../onSite/common';
import { CorrectTimeSheet } from '../onSite/CorrectTimeSheet';
import { crewLines } from '../onSite/crew';
import { correctTime } from '../onSite/crewActions';
import { goTo, useNav } from '../onSite/fieldData';
import { formatClock, formatMinutes } from '../onSite/format';
import { loadJob } from '../onSite/job';
import { asParams, saveDraft, useCloseDraft } from './draft';

/** How many of a material were used, when the job's item says. */
export function usedCount(detail: string | null): string | null {
  const d = fromJson<Record<string, unknown>>(detail);
  const n = d?.used ?? d?.quantity;
  return typeof n === 'number' || typeof n === 'string' ? String(n) : null;
}

export function DebriefScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const draft = useCloseDraft(w);
  const [, refresh] = useRefresh();
  const [problem, setProblemState] = useState(draft?.debrief?.problem ?? '');
  const [done, setDoneState] = useState(draft?.debrief?.done ?? '');
  // Every keystroke is kept on the handset, so killing the app loses nothing typed.
  const keep = (next: { problem: string; done: string }) => {
    if (draft) saveDraft(w.prefs, w.me, { ...draft, debrief: next });
  };
  const setProblem = (v: string) => {
    setProblemState(v);
    keep({ problem: v, done });
  };
  const setDone = (v: string | ((now: string) => string)) => {
    setDoneState((now) => {
      const next = typeof v === 'function' ? v(now) : v;
      keep({ problem, done: next });
      return next;
    });
  };
  const [correcting, setCorrecting] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const job = loadJob(w, draft?.workOrderId ?? null);
  if (!job || !draft) return <NotOnPhone />;

  const workOrderId = job.order.id;
  const mine = crewLines(crewOrderQ.listForOrder(w.s, workOrderId), w.clock.now()).find((l) => l.personId === w.me) ?? null;
  const parts = woItemQ.listForOrder(w.s, workOrderId, 'material');

  const dictate = () =>
    w.device.dictation.listen().then(
      (heard) => heard && setDone((now) => (now ? `${now} ${heard}` : heard)),
      () => setNote(t('field.site.note.noDictation')),
    );

  return (
    <ScreenFrame
      footer={
        <Button
          variant="primary"
          grow
          onPress={() => goTo(navigation, 'FF-33', asParams({ ...draft, debrief: { problem: problem.trim(), done: done.trim() } }))}
          testID="door-FF-33"
        >
          {t('field.ff32.close')}
        </Button>
      }
    >
      <Card title={t('field.ff32.labour')} testID="labour-card">
        <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: theme.space[2] }}>
          <AppText variant="title" testID="my-labour">
            {formatMinutes(mine?.labourMinutes ?? 0)}
          </AppText>
          {mine?.labourFrom && mine.labourTo ? (
            <AppText variant="label" tone="muted">
              {`${formatClock(mine.labourFrom)} – ${formatClock(mine.labourTo)}`}
            </AppText>
          ) : null}
        </View>
        <ListRow divider label={t('field.ff29.travel')} value={formatMinutes(mine?.travelMinutes ?? 0)} />
        <Button size="sm" onPress={() => setCorrecting(true)} testID="correct-mine">
          {t('field.ff32.correct')}
        </Button>
      </Card>

      <Card title={t('field.ff32.parts')} testID="parts-card">
        {parts.map((p, i) => (
          <ListRow key={p.id} divider={i > 0} label={p.label} value={usedCount(p.detail) ?? undefined} />
        ))}
        <ListRow
          divider={parts.length > 0}
          label={t('field.ff32.changeParts')}
          onPress={() => goTo(navigation, 'FF-24', { workOrderId })}
          testID="door-FF-24"
        />
      </Card>

      <Card title={t('field.ff32.problem')}>
        <Field label={t('field.ff32.problem')} value={problem} onChangeText={setProblem} multiline testID="problem" />
      </Card>

      <Card title={t('field.ff32.whatIDid')}>
        <Field label={t('field.ff32.whatIDid')} value={done} onChangeText={setDone} multiline testID="what-i-did" />
        <Button size="sm" onPress={() => void dictate()} icon={<Mark name="mic" />} testID="dictate">
          {t('field.site.note.dictate')}
        </Button>
        {note ? <Notice tone="warning">{note}</Notice> : null}
      </Card>

      <Notice tone="info" icon={<Mark name="document" colour={theme.colors.status.info.fg} />}>
        {t('field.ff32.becomesHistory')}
      </Notice>

      <CorrectTimeSheet
        visible={correcting}
        name={t('field.ff32.you')}
        travel={mine?.travelMinutes ?? 0}
        labour={mine?.labourMinutes ?? 0}
        onCancel={() => setCorrecting(false)}
        onSave={(m) => {
          correctTime(w, workOrderId, mine ?? { personId: w.me, arrivedAt: null, labourFrom: null }, m);
          setCorrecting(false);
          refresh();
        }}
      />
    </ScreenFrame>
  );
}
