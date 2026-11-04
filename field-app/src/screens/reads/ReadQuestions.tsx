/**
 * The utility's own questions at a meter — MQ-033 (`CR-192-BRC10` task 12).
 *
 * WHEN: after the figure (or the can't-read reason) is decided and before the
 * reading is saved, because the answers travel INSIDE the reading's own item
 * (PO 2026-10-24: answers *"travel inside the reading's own item (batches of 50
 * unchanged)"*). The figure is taken from the meter exactly as before; every
 * screen that saves a reading (RW-09, RW-10, RW-15, RW-16, RW-17) asks through
 * `useReadForm`, so no save path can skip them.
 *
 * WHICH: `readFormat.askedQuestions` — every reading · out of range · can't
 * read · once per stop — and `visibleQuestions` for follow-ups. A route with no
 * format, or a meter whose service has none, never opens the sheet: the save is
 * exactly today's (US: *"a utility with no template reads exactly as today"*).
 *
 * WORDS: the label, help and list options are the UTILITY'S, shown verbatim and
 * never translated. Only this sheet's own controls are catalogue words.
 *
 * REQUIRED: a required question shown and unanswered blocks *Save* with one
 * warning sentence, the pattern of a required step photo (DEF-FLD-10583,
 * `theJob/TaskList.tsx`): a warning `Notice`, the button disabled, and the
 * sentence as its accessibility hint. Nothing is guessed for the reader.
 *
 * The inputs are the kit's (B14 rule 43, rule 45's touch standard): `Field` for
 * text, number and date; `ChoiceChips` for yes/no; `RadioList` for one of a
 * list; `ToggleRow` per option for several; `PhotoAsk` over the camera port
 * for a photo — the camera only, never a gallery (R93), stamp burned in (R94).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, ChoiceChips, Field, Kicker, Notice, RadioList, Sheet, ToggleRow } from '../../components';
import * as readFormatQ from '../../db/queries/readFormat';
import type * as walkQ from '../../db/queries/readsWalk';
import { fromJson } from '../../db/json';
import { useTheme } from '../../theme';
import type { SaveReading } from './acts';
import { PhotoAsk } from './parts';
import type { CameraShot } from './ports';
import {
  type Answers,
  type AnswerValue,
  askedQuestions,
  captureDay,
  malformed,
  missingRequired,
  type ReaderStatus,
  type ReadQuestion,
  visibleQuestions,
  type WireAnswer,
} from './readFormat';
import { meterName } from './records';
import { useReads } from './services';

type Form = NonNullable<SaveReading['form']>;
type Run = (form: Form | undefined) => Promise<void>;

/** The version this meter's reading is asked under: the route's format for the meter's service. */
function versionFor(s: ReturnType<typeof useReads>['s'], db: ReturnType<typeof useReads>['services']['db'], m: walkQ.MeterRead): readFormatQ.StoredVersion | null {
  const formats = readFormatQ.routeFormats(s, m.route_id);
  if (formats.length === 0) return null;
  const service = (m.asset_service ?? '').toLowerCase();
  const chosen = service ? formats.find((f) => f.service.toLowerCase() === service) : formats.length === 1 ? formats[0] : undefined;
  return chosen ? readFormatQ.getVersion(db, chosen.version_id) : null;
}

/** `once_per_stop` keys another reading at this stop answered on this capture day. */
function answeredAtStop(s: ReturnType<typeof useReads>['s'], m: walkQ.MeterRead, today: string): Set<string> {
  const keys = new Set<string>();
  for (const row of readFormatQ.answersAtStop(s, m.stop_id, m.id)) {
    if (captureDay(row.captured_at) !== today) continue;
    for (const a of fromJson<WireAnswer[]>(row.answers) ?? []) keys.add(a.question_key);
  }
  return keys;
}

/**
 * Ask, then save. `saveWith(status, outOfRange, run)` calls `run(undefined)`
 * at once on a route with no format; otherwise it opens the sheet and calls
 * `run(form)` from *Save*. Render `sheet` on the screen.
 */
export function useReadForm(m: walkQ.MeterRead | null | undefined) {
  const { s, services } = useReads();
  const [pending, setPending] = useState<{ versionId: string; asked: ReadQuestion[]; run: Run } | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [busy, setBusy] = useState(false);

  const saveWith = async (status: ReaderStatus, outOfRange: boolean, run: Run): Promise<void> => {
    const version = m ? versionFor(s, services.db, m) : null;
    if (!m || !version) return run(undefined);
    const today = captureDay(services.clock.now().toISOString());
    const asked = askedQuestions(version.questions as ReadQuestion[], { status, outOfRange, answeredAtStop: answeredAtStop(s, m, today) });
    // Nothing to ask is still a reading taken under this version: stamped, no answers.
    if (asked.length === 0) return run({ versionId: version.id, visible: [], answers: {} });
    setAnswers({});
    setPending({ versionId: version.id, asked, run });
  };

  const finish = async () => {
    if (!pending) return;
    setBusy(true);
    try {
      await pending.run({ versionId: pending.versionId, visible: visibleQuestions(pending.asked, answers), answers });
      setPending(null);
    } finally {
      setBusy(false);
    }
  };

  const sheet =
    m && pending ? (
      <ReadQuestionsSheet
        m={m}
        asked={pending.asked}
        answers={answers}
        onChange={(key, v) => setAnswers((prev) => ({ ...prev, [key]: v }))}
        onClose={() => setPending(null)}
        onSave={() => void finish()}
        busy={busy}
      />
    ) : null;
  return { saveWith, sheet };
}

function two(n: number): string {
  return String(n).padStart(2, '0');
}

export function ReadQuestionsSheet(props: {
  m: walkQ.MeterRead;
  asked: readonly ReadQuestion[];
  answers: Answers;
  onChange: (key: string, value: AnswerValue | undefined) => void;
  onClose: () => void;
  onSave: () => void;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { services, here } = useReads();
  const [cameraFailed, setCameraFailed] = useState(false);
  const visible = visibleQuestions(props.asked, props.answers);
  const missing = missingRequired(visible, props.answers).length;
  const blockedWords = missing > 0 ? t('field.reads.questions.toFinish', { count: missing }) : undefined;

  const takePhoto = async (q: ReadQuestion) => {
    const now = services.clock.now();
    // The same burned-in stamp as RW-14 (R94): when, where, who and which meter.
    const stamp = [
      `${now.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })} · ${two(now.getHours())}:${two(now.getMinutes())}:${two(now.getSeconds())}`,
      here ? `${here.lat.toFixed(6)}, ${here.lng.toFixed(6)} · ±${Math.round(here.accuracy_m)} m` : t('field.reads.rw13.noPosition'),
      [services.readerName, meterName(props.m), q.label].filter(Boolean).join(' · '),
    ];
    try {
      const shot: CameraShot = await services.camera.take(stamp);
      setCameraFailed(false);
      // FB-003: the position at the shutter is the photograph's own.
      props.onChange(q.key, { ...shot, location: here });
    } catch {
      setCameraFailed(true);
    }
  };

  const input = (q: ReadQuestion) => {
    const v = props.answers[q.key];
    const id = `question-${q.key}-answer`;
    if (q.data_type === 'boolean') {
      return (
        <ChoiceChips
          label={q.label}
          segments={[
            { id: 'yes', label: t('field.reads.questions.yes') },
            { id: 'no', label: t('field.reads.questions.no') },
          ]}
          active={v === true ? 'yes' : v === false ? 'no' : null}
          onSelect={(choice) => props.onChange(q.key, choice === 'yes')}
          size="default"
          testID={id}
        />
      );
    }
    if (q.data_type === 'select') {
      return (
        <RadioList
          label={q.label}
          options={(q.options ?? []).map((o) => ({ id: o, label: o }))}
          selected={typeof v === 'string' ? v : null}
          onSelect={(o) => props.onChange(q.key, o)}
          testID={id}
        />
      );
    }
    if (q.data_type === 'multi_select') {
      const picked = Array.isArray(v) ? v : [];
      return (
        <View testID={id}>
          {(q.options ?? []).map((o, i) => (
            <ToggleRow
              key={o}
              label={o}
              value={picked.includes(o)}
              divider={i > 0}
              onChange={(on) => props.onChange(q.key, on ? [...picked, o] : picked.filter((x) => x !== o))}
              testID={`${id}-${o}`}
            />
          ))}
        </View>
      );
    }
    if (q.data_type === 'photo') {
      const taken = typeof v === 'object' && v !== null && !Array.isArray(v) ? 1 : 0;
      return (
        <PhotoAsk
          label={taken ? t('field.reads.questions.photoTaken') : t('field.reads.questions.takePhoto')}
          required={q.is_required}
          taken={taken}
          disabled={!services.camera.available}
          onPress={() => void takePhoto(q)}
          testID={`question-${q.key}-take`}
        />
      );
    }
    // text, number, date — and any custom-field type a later server adds, as text.
    const text = typeof v === 'string' ? v : '';
    const bad = malformed(q, text);
    return (
      <Field
        label={q.label}
        help={q.help_text ?? undefined}
        value={text}
        onChangeText={(next) => props.onChange(q.key, next)}
        keyboardType={q.data_type === 'number' ? 'decimal-pad' : q.data_type === 'date' ? 'numbers-and-punctuation' : 'default'}
        placeholder={q.data_type === 'date' ? t('field.reads.questions.datePattern') : undefined}
        multiline={q.data_type === 'text'}
        error={bad ? t(q.data_type === 'number' ? 'field.reads.questions.notNumber' : 'field.reads.questions.notDate') : undefined}
        testID={id}
      />
    );
  };

  const ownsLabel = (q: ReadQuestion) => !['boolean', 'select', 'multi_select', 'photo'].includes(q.data_type);

  return (
    <Sheet
      visible
      onClose={props.onClose}
      title={t('field.reads.questions.title')}
      closeLabel={t('field.reads.common.close')}
      testID="read-questions"
      footer={
        <>
          <Button grow onPress={props.onClose} testID="questions-back">
            {t('field.reads.common.back')}
          </Button>
          <Button variant="primary" grow busy={props.busy} disabled={missing > 0} accessibilityHint={blockedWords} onPress={props.onSave} testID="questions-done">
            {t('field.reads.questions.done')}
          </Button>
        </>
      }
    >
      <View style={{ gap: theme.space[5] }}>
        {visible.map((q) => (
          <View key={q.key} style={{ gap: theme.space[2] }} testID={`question-${q.key}`}>
            {q.is_required ? <Kicker tone="brand">{t('field.reads.questions.required')}</Kicker> : null}
            {ownsLabel(q) ? null : (
              <>
                <AppText variant="body" weight="semibold">
                  {q.label}
                </AppText>
                {q.help_text ? (
                  <AppText variant="label" tone="muted">
                    {q.help_text}
                  </AppText>
                ) : null}
              </>
            )}
            {input(q)}
          </View>
        ))}
        {cameraFailed || !services.camera.available ? (
          visible.some((q) => q.data_type === 'photo') ? (
            <Notice tone="warning" testID="questions-no-camera">
              {t('field.reads.rw14.noCamera')}
            </Notice>
          ) : null
        ) : null}
        {blockedWords ? (
          <Notice tone="warning" testID="questions-required">
            {blockedWords}
          </Notice>
        ) : null}
      </View>
    </Sheet>
  );
}
