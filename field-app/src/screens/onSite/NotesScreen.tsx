/**
 * FF-30 Notes — every remark on the job with who wrote it, where and when,
 * and a note box with dictation beside it (US-FLD-022, US-FLD-030; R10, R38,
 * R95).
 *
 *   A remark is an `activity` row of kind `remark`. Its `status` says where it
 *   was written: `dispatch` (the office's note, drawn with the blue rule) or
 *   `on_site` (written here). That is this screen's convention for the
 *   column, stated so the sync lane writes the office's notes the same way.
 *   Dictation sits beside every note (R38) and appends what was heard; a
 *   remark is never required (R95) — an empty box only means there is
 *   nothing to add.
 *   A photo taken here goes with the note, declared with it (R123).
 *
 * ⚠ Outbox kind `remark` has no server door yet (`07-endpoints.md` N18): it
 * is captured, kept and not sent until it lands.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, View } from 'react-native';

import { AppText, Kicker } from '../../components/AppText';
import { Button, IconButton } from '../../components/Button';
import { Card } from '../../components/Card';
import { Field } from '../../components/Field';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { ScreenFrame } from '../../components/ScreenFrame';
import * as activityQ from '../../db/queries/activity';
import * as evidenceQ from '../../db/queries/woItemEvidence';
import { capture } from '../../sync/outbox';
import { useTheme } from '../../theme';
import { NotOnPhone, useHeader, useRefresh, type WaveScreenProps } from './common';
import { useJobId, type Wave } from './fieldData';
import { formatStamp } from './format';
import { loadJob, myName } from './job';
import type { TakenPhoto } from './ports';

export function addNote(w: Wave, workOrderId: string, text: string, photo: TakenPhoto | null): string {
  const at = w.clock.now().toISOString();
  const author = myName(w);
  return capture(
    w.db,
    w.captor,
    {
      kind: 'remark',
      workOrderId,
      payload: { text, source: 'on_site' },
      photos: photo ? [{ ...photo, target: {} }] : [],
      apply: (s, key) =>
        activityQ.insert(s, { id: w.newId(), workOrderId, kind: 'remark', status: 'on_site', text, author, at, outboxId: key }),
    },
    w.deps,
  ).key;
}

export function NotesScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [, refresh] = useRefresh();
  const [text, setText] = useState('');
  const [photo, setPhoto] = useState<TakenPhoto | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const job = loadJob(w, useJobId());
  useHeader({ chip: job?.order.number ?? null });
  if (!job) return <NotOnPhone />;

  const workOrderId = job.order.id;
  const remarks = activityQ.listForOrder(w.s, workOrderId).filter((a) => a.kind === 'remark');

  const dictate = () =>
    w.device.dictation.listen().then(
      (heard) => heard && setText((now) => (now ? `${now} ${heard}` : heard)),
      () => setNote(t('field.site.note.noDictation')),
    );
  const snap = () =>
    w.device.camera.take().then(
      (p) => p && setPhoto(p),
      () => setNote(t('field.site.note.noCamera')),
    );

  return (
    <ScreenFrame
      footer={
        <View style={{ flex: 1, gap: theme.space[2] }}>
          {note ? <Notice tone="warning">{note}</Notice> : null}
          <Field label={t('field.ff30.write')} value={text} onChangeText={setText} multiline placeholder={t('field.ff30.write')} testID="note-text" />
          {photo ? (
            <AppText variant="label" tone="muted" testID="note-photo">
              {t('field.ff30.photoAttached')}
            </AppText>
          ) : null}
          <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
            <IconButton outlined label={t('field.site.note.dictate')} onPress={() => void dictate()} testID="dictate">
              <Mark name="mic" />
            </IconButton>
            <IconButton outlined label={t('field.ff30.photo')} onPress={() => void snap()} testID="note-camera">
              <Mark name="camera" />
            </IconButton>
            <Button
              variant="primary"
              grow
              disabled={text.trim() === '' && !photo}
              onPress={() => {
                addNote(w, workOrderId, text.trim(), photo);
                setText('');
                setPhoto(null);
                setNote(null);
                refresh();
              }}
              testID="add-note"
            >
              {t('field.ff30.add')}
            </Button>
          </View>
        </View>
      }
    >
      {remarks.map((r) => {
        const dispatch = r.status === 'dispatch';
        const photos = r.outbox_id ? evidenceQ.photosOfAct(w.s, r.outbox_id) : [];
        return (
          <Card
            key={r.id}
            testID={`remark-${r.id}`}
            style={dispatch ? { borderLeftWidth: theme.borderWidth.rule, borderLeftColor: theme.colors.status.info.rule } : undefined}
          >
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: theme.space[2] }}>
              <Kicker tone={dispatch ? 'default' : 'muted'}>{dispatch ? t('field.ff30.dispatch') : t('field.ff30.onSite')}</Kicker>
              <AppText variant="label" tone="muted">
                {formatStamp(r.at)}
              </AppText>
            </View>
            <AppText variant="body">{r.text ?? ''}</AppText>
            {photos.map((p) => (
              <Image
                key={p.id}
                source={{ uri: p.local_path }}
                accessibilityLabel={t('field.ff30.photo')}
                style={{ width: theme.touch.primary * 2, height: theme.touch.primary * 2, backgroundColor: theme.colors.surface }}
              />
            ))}
            <AppText variant="label" tone="muted">
              {r.author ?? ''}
            </AppText>
          </Card>
        );
      })}
      {remarks.length === 0 ? (
        <AppText variant="body" tone="muted">
          {t('field.ff30.none')}
        </AppText>
      ) : null}
    </ScreenFrame>
  );
}
