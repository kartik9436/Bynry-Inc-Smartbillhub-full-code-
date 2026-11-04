/**
 * FF-20 Readings — every reading the job asks for, each with its unit beside
 * the figure (R12), its expected range and last value, and the photograph
 * the prompt asks for taken ON the reading (R6, R97).
 *
 * R11, the rule this screen exists for: out of range is FLAGGED, never
 * refused. The first out-of-range figure is not saved — *"Outside expected
 * range. Enter it again."* — and the same figure a second time is saved and
 * marked for the office; a different second figure was a typo and is judged
 * on its own, with no flag (`readingCheck.ts`, US-FLD-009 TC-1…TC-3). Nothing
 * on this screen blocks completion.
 *
 * ⚠ **A READING IS A NUMBER OR WORDS (DEF-FLD-10585, beta MQ-022).** The
 * template says which (`wo_reading.kind`). A TEXT reading — a serial, a seal
 * number — opens the ordinary keyboard, is saved exactly as typed (trimmed
 * only), shown verbatim (no digit grouping: *20260042*, never *20,260,042*),
 * sent as `value_text`, and has no range. A NUMBER reading given anything but
 * a number says *"Numbers only."* at the field rather than silently not
 * saving. A range reads as plain figures: *Expected 0–99,999*, not the
 * server's four places.
 *
 * *Unable to read* is an answer AT THE READING (R13), not an outcome of the
 * job: the job can still pass with one meter unread (TC-4). ⚠ **IT ASKS WHY
 * (DEF-MET-10609, decision log 2026-10-26, PO *"yes do it"*):** the button
 * opens the SAME reason picker the route reading uses (RW-17's, now
 * `reads/CantReadReasonPicker`) from the utility's one list, plus an optional
 * note; *Record* needs a reason when the phone holds a list. A phone with no
 * list yet says so and records without one — never blocks the answer.
 *
 * ⚠ **A REQUIRED DIAL PHOTO BLOCKS THE SAVE — PO 2026-10-24 (MQ-017/MQ-020,
 * CR-187-BRC10):** a prompt whose template marks its photo Required
 * (`wo_reading.photo_required`, carried from the bundle) cannot be saved until
 * a dial photo is taken or held; Save is off and the card says *"Take 1 photo
 * to save this reading."*, which is also Save's accessibility hint. A figure
 * already saved without its required photo (before this rule, or from the
 * office) is not counted in *x of 3* (`jobModel.ts`) until the photo exists.
 * *Unable to read* is not blocked: it is the answer that there is no figure,
 * and the ruling blocks a reading SAVED AS DONE. Once a figure is saved the
 * button goes (it would contradict the figure); the field still edits it.
 *
 * A photograph taken before the figure is saved travels WITH the reading — the
 * reading, its photo rows and its key in one transaction (`recordReading`);
 * one taken after is its own declaration.
 *
 * Built from `phone/FF-20-readings.png` / `tablet/FF-20-T-readings.png`; on a
 * tablet the cards sit two to a row. ⚠ The meter line (MASTER W-4471) is not
 * drawn: `wo_reading` carries no meter (`jobModel.ts`). Doors: back → FF-15,
 * *Add a reading* → FF-59, *All photos* → FF-21, *Debrief* → FF-32.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import {
  AppText,
  Button,
  Card,
  DashedButton,
  Field,
  Glyph,
  IconButton,
  Notice,
  PhotoThumb,
  StatusChip,
} from '../../components';
import { CantReadReasonPicker, cantReadReasons } from '../reads/CantReadReasonPicker';
import { COLUMN_GAP, rowsOf, usePaneColumns } from '../../tablet/columns';
import { useTheme } from '../../theme';
import { capturePhoto, recordReading, recordTextReading } from './actions';
import type { ReadyPhoto } from './camera';
import { groupDigits, hhmm } from './format';
import type { JobPortValue } from './JobPort';
import type { JobView, ReadingView } from './jobModel';
import { JobScreen, useDoor } from './JobScreen';
import { pathOf } from './photoStamp';
import { judgeReading, parseTyped } from './readingCheck';
import { useOpenJob } from './useJob';
import { usePhotoTaker } from './usePhotoTaker';

/** A decimal as a person reads it: grouped, with trailing zero decimals dropped (`99999.0000` → `99,999`, `0.50` → `0.5`). */
export function plainFigure(decimal: string | null | undefined): string {
  if (decimal === null || decimal === undefined || decimal === '') return '';
  const trimmed = decimal.includes('.') ? decimal.replace(/0+$/, '').replace(/\.$/, '') : decimal;
  return groupDigits(trimmed);
}

function ReadingCard({ port, view, reading }: { port: JobPortValue | null; view: JobView; reading: ReadingView }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const r = reading.row;
  const [draft, setDraft] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [said, setSaid] = useState<'again' | 'marked' | 'numbersOnly' | null>(null);
  const [held, setHeld] = useState<ReadyPhoto[]>([]);
  // DEF-MET-10609 — *Unable to read* asks WHY first: one reason from the
  // utility's list (the RW-17 picker, shared) and an optional note.
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState<string | null>(null);
  const [note, setNote] = useState('');
  const camera = usePhotoTaker(port, view.order.number ?? '');
  const reasons = asking && port ? cantReadReasons(port.db) : null;
  const hasList = reasons !== null && reasons.length > 0;

  const isText = r.kind === 'text';
  const range =
    !isText && (r.min_value !== null || r.max_value !== null)
      ? t('field.ff20.expected', { min: plainFigure(r.min_value) || '…', max: plainFigure(r.max_value) || '…' })
      : null;
  const last = !isText && r.previous_value !== null ? t('field.ff20.last', { value: plainFigure(r.previous_value) }) : null;
  const help = [range, last].filter(Boolean).join(' · ') || undefined;

  const photoCount = reading.photos.length + held.length;
  const photoMissing = r.photo_required === 1 && photoCount === 0;
  const photoWords = photoMissing ? t('field.ff20.photoToSave', { count: 1 }) : undefined;

  const commit = () => {
    if (!port || draft === null || photoMissing) return;
    if (isText) {
      if (draft.trim() === '') return;
      recordTextReading(port, view.order.id, r.id, draft, held);
      setHeld([]);
      setDraft(null);
      setSaid(null);
      port.changed();
      return;
    }
    const value = parseTyped(draft);
    if (value === null) {
      if (draft.trim() !== '') setSaid('numbersOnly');
      return;
    }
    const verdict = judgeReading(value, { min: r.min_value, max: r.max_value }, pending);
    if (verdict.kind === 'again') {
      setPending(verdict.value);
      setSaid('again');
      return;
    }
    recordReading(port, view.order.id, { id: r.id, unit: r.unit }, { value: verdict.value, flagged: verdict.flagged, unableToRead: false }, held);
    setHeld([]);
    setPending(null);
    setDraft(null);
    setSaid(verdict.flagged ? 'marked' : null);
    port.changed();
  };

  const unable = () => {
    if (!port || (hasList && reason === null)) return;
    recordReading(
      port,
      view.order.id,
      { id: r.id, unit: r.unit },
      { value: null, flagged: false, unableToRead: true, unableReason: reason, note },
      held,
    );
    setHeld([]);
    setAsking(false);
    setReason(null);
    setNote('');
    setDraft(null);
    setPending(null);
    setSaid(null);
    port.changed();
  };

  const photo = async () => {
    const p = await camera.take();
    if (!p || !port) return;
    if (reading.taken) {
      capturePhoto(port, view.order.id, p, { reading_id: r.id });
      port.changed();
    } else {
      setHeld((h) => [...h, p]);
    }
  };

  const saved = isText ? r.value_text : r.value;
  const shown = draft ?? (saved === null ? '' : isText ? saved : groupDigits(saved));
  const tone = said === 'again' ? 'warning' : r.flagged ? 'warning' : saved !== null && draft === null ? 'success' : 'default';

  return (
    <Card testID={`reading-${r.id}`} style={{ flexGrow: 1, flexBasis: 0 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
        <View style={{ flexGrow: 1 }} />
        {photoCount > 0 ? <StatusChip tone="danger">{t('field.ff20.photos', { count: photoCount })}</StatusChip> : null}
        {r.unable_to_read ? <StatusChip tone="neutral">{t('field.ff20.unable')}</StatusChip> : null}
      </View>
      <Field
        label={r.prompt}
        value={shown}
        onChangeText={(text) => {
          setDraft(text);
          if (said === 'marked' || said === 'numbersOnly') setSaid(null);
        }}
        onSubmitEditing={commit}
        keyboardType={isText ? 'default' : 'decimal-pad'}
        autoCapitalize={isText ? 'characters' : undefined}
        autoCorrect={isText ? false : undefined}
        unit={r.unit || undefined}
        help={help}
        error={said === 'numbersOnly' ? t('field.ff20.numbersOnly') : undefined}
        tone={tone}
        placeholder={t('field.ff20.notTaken')}
        testID={`reading-${r.id}-field`}
      />
      {draft !== null && draft !== '' ? (
        <Button size="sm" onPress={commit} disabled={photoMissing} accessibilityHint={photoWords} testID={`reading-${r.id}-save`}>
          {t('field.job.save')}
        </Button>
      ) : null}
      {photoWords && r.unable_to_read !== 1 ? (
        <Notice tone="warning" icon={<Glyph name="camera" />} testID={`reading-${r.id}-photo-required`}>
          {photoWords}
        </Notice>
      ) : null}
      {said === 'again' ? (
        <Notice
          tone="warning"
          icon={<Glyph name="warning" />}
          testID={`reading-${r.id}-again`}
          action={
            <Button size="sm" onPress={() => setDraft('')} testID={`reading-${r.id}-enter-again`}>
              {t('field.ff20.enterAgain')}
            </Button>
          }
        >
          {t('field.ff20.outside')}
        </Notice>
      ) : null}
      {said === 'marked' || (r.flagged === 1 && draft === null && said !== 'again') ? (
        <Notice tone="success" testID={`reading-${r.id}-marked`}>
          {t('field.ff20.marked')}
        </Notice>
      ) : null}
      {r.photo_required || photoCount > 0 ? (
        <View style={{ gap: theme.space[2] }}>
          <AppText variant="label" weight="semibold">
            {t('field.ff20.photoOfDial')}
          </AppText>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: theme.space[2] }}>
            {reading.photos.map((p) => (
              <PhotoThumb key={p.id} path={pathOf(p)} label={t('field.job.photoAt', { time: hhmm(p.captured_at) })} caption={hhmm(p.captured_at)} />
            ))}
            {held.map((p) => (
              <PhotoThumb key={p.localPath} path={p.localPath} label={t('field.ff20.heldPhoto')} />
            ))}
            <IconButton outlined label={t('field.ff20.takeDial')} onPress={() => void photo()} testID={`reading-${r.id}-photo`}>
              <Glyph name="camera" />
            </IconButton>
          </View>
          {camera.error ? <Notice tone="danger">{camera.error}</Notice> : null}
        </View>
      ) : null}
      {!reading.taken && asking ? (
        <View style={{ gap: theme.space[2] }} testID={`reading-${r.id}-why`}>
          <CantReadReasonPicker reasons={reasons} selected={reason} onSelect={setReason} testID={`reading-${r.id}-reasons`} />
          <Field label={t('field.ff20.note')} value={note} onChangeText={setNote} testID={`reading-${r.id}-note`} />
          <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
            <Button size="sm" onPress={() => setAsking(false)} testID={`reading-${r.id}-unable-cancel`}>
              {t('field.job.cancel')}
            </Button>
            <Button
              size="sm"
              variant="primary"
              onPress={unable}
              disabled={!port || (hasList && reason === null)}
              testID={`reading-${r.id}-unable-record`}
            >
              {t('field.ff20.recordUnable')}
            </Button>
          </View>
        </View>
      ) : null}
      {!reading.taken && !asking ? (
        <Button size="sm" onPress={() => setAsking(true)} disabled={!port} testID={`reading-${r.id}-unable`}>
          {t('field.ff20.unable')}
        </Button>
      ) : null}
    </Card>
  );
}

export function Readings() {
  const { t } = useTranslation();
  const theme = useTheme();
  // FF-20 T *Readings in two columns*: as many columns as the PANE holds at
  // 260 or more (R121, R122) — two in the tablet's wide pane, one on a phone
  // or in anything narrower. Never decided by the window.
  const columns = usePaneColumns(2);
  const tablet = columns > 1;
  const go = useDoor('FF-20');
  const { port, view } = useOpenJob();
  const items = view?.readings.items ?? [];
  const pairs: ReadingView[][] = tablet ? rowsOf(items, columns) : [];

  return (
    <JobScreen
      id="FF-20"
      title={t('field.screen.ff20')}
      back={{ to: 'FF-15', label: t('field.job.backToJob') }}
      trailing={
        <AppText variant="body" weight="heavy" testID="readings-count">
          {t('field.job.nOfM', { done: view?.readings.taken ?? 0, total: view?.readings.total ?? 0 })}
        </AppText>
      }
      footer={
        <>
          <Button onPress={() => go('FF-21')} testID="door-FF-21">
            {t('field.ff20.allPhotos', { count: view?.photos.length ?? 0 })}
          </Button>
          <Button grow variant="primary" onPress={() => go('FF-32')} testID="door-FF-32">
            {t('field.ff20.debrief')}
          </Button>
        </>
      }
    >
      {view === null ? <Notice tone="info">{t('field.job.noJob')}</Notice> : null}
      {view !== null && tablet
        ? pairs.map((pair) => (
            <View key={pair.map((p) => p.row.id).join()} style={{ flexDirection: 'row', gap: COLUMN_GAP }} testID="readings-row">
              {pair.map((reading) => (
                <View key={reading.row.id} style={{ flex: 1 }} testID="readings-cell">
                  <ReadingCard port={port} view={view} reading={reading} />
                </View>
              ))}
              {pair.length < columns ? <View style={{ flex: columns - pair.length }} /> : null}
            </View>
          ))
        : null}
      {view !== null && !tablet
        ? items.map((reading) => <ReadingCard key={reading.row.id} port={port} view={view} reading={reading} />)
        : null}
      <DashedButton icon={<Glyph name="more" />} label={t('field.ff20.addReading')} onPress={() => go('FF-59')} testID="door-FF-59" />
    </JobScreen>
  );
}
