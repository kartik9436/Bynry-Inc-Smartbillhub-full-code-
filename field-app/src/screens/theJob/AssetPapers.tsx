/**
 * FF-60 Asset papers — documents for an asset fitted on this job: a permit, a
 * serial plate, a seal number. R108 (PO ruled): *"A document may come from
 * anywhere; where it came from is recorded. Camera, file or typed, stamped on
 * each one. This does not weaken R93 — a photograph proving a task is evidence
 * and stays camera-only."* So each paper carries its SOURCE, shown on it, and
 * this screen is the one place a FILE is accepted — never for a task's proof.
 *
 * Each paper is captured as a `document` item (unrouted until the server has
 * the door) with its `document` row, in one transaction. A typed paper's words
 * travel in the item; a photographed one is a file on disk like any photo.
 *
 * *A file* uses `expo-document-picker` (`device/native/files.ts`, wired
 * 2026-10-21); where a build has no picker it says so in words when pressed.
 *
 * The board's two paragraphs of explanation are rationale and are not drawn
 * (B14 rule 33: rationale is zero words on screen); they live here.
 *
 * Built from `phone/FF-60-asset-papers.png`. Doors: back and *Done* → FF-15.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, Field, FieldGroup, Glyph, Kicker, Notice, PhotoThumb, Sheet, StatusChip, type StatusTone } from '../../components';
import { fromJson } from '../../db/json';
import * as jobQ from '../../db/queries/jobScreens';
import type { DocumentRow } from '../../db/queries/document';
import { scoped } from '../../db/scoped';
import { useTheme } from '../../theme';
import { addPaper } from './actions';
import { type PickedFile, type ReadyPhoto, FilePickerUnavailableError } from './camera';
import { fileSize } from './format';
import { JobScreen, useDoor } from './JobScreen';
import { useOpenJob } from './useJob';
import { usePhotoTaker } from './usePhotoTaker';

const SOURCE: Record<DocumentRow['source'], { tone: StatusTone; key: string }> = {
  camera: { tone: 'success', key: 'field.ff60.source.camera' },
  file: { tone: 'info', key: 'field.ff60.source.file' },
  typed: { tone: 'neutral', key: 'field.ff60.source.typed' },
  server: { tone: 'neutral', key: 'field.ff60.source.server' },
};

type Draft =
  | { source: 'camera'; photo: ReadyPhoto }
  | { source: 'file'; file: PickedFile }
  | { source: 'typed' };

export function AssetPapers() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-60');
  const { port, view } = useOpenJob();
  const camera = usePhotoTaker(port, view?.order.number ?? '');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [fileError, setFileError] = useState<string | null>(null);
  const asset = view?.asset ?? null;
  const papers = view?.papers ?? [];
  const units = { kb: t('field.job.unit.kb'), mb: t('field.job.unit.mb') };

  const typedWords = new Map<string, string>();
  if (port && view) {
    for (const item of jobQ.capturedOfKind(scoped(port.db, port.captor().technicianId), view.order.id, 'document')) {
      const payload = fromJson<{ document_id?: string; text?: string | null }>(item.payload);
      if (payload?.document_id && payload.text) typedWords.set(payload.document_id, payload.text);
    }
  }

  const open = (d: Draft, name: string) => {
    setDraft(d);
    setTitle(name);
    setText('');
  };

  const photograph = async () => {
    const photo = await camera.take();
    if (photo) open({ source: 'camera', photo }, '');
  };

  const pickFile = async () => {
    if (!port) return;
    setFileError(null);
    try {
      const file = await port.files.pick();
      if (file) open({ source: 'file', file }, file.name);
    } catch (err) {
      setFileError(err instanceof FilePickerUnavailableError ? t('field.ff60.fileUnavailable') : t('field.job.camera.failed'));
    }
  };

  const save = () => {
    if (!port || !view || !asset || !draft || !title.trim()) return;
    if (draft.source === 'camera') addPaper(port, view.order.id, asset.id, { source: 'camera', title, photo: draft.photo });
    else if (draft.source === 'file')
      addPaper(port, view.order.id, asset.id, { source: 'file', title, localPath: draft.file.uri, bytes: draft.file.bytes, kind: draft.file.mimeType });
    else addPaper(port, view.order.id, asset.id, { source: 'typed', title, text });
    port.changed();
    setDraft(null);
  };

  const ready = title.trim() !== '' && (draft?.source !== 'typed' || text.trim() !== '');

  return (
    <JobScreen
      id="FF-60"
      title={t('field.screen.ff60')}
      back={{ to: 'FF-15', label: t('field.job.backToJob') }}
      trailing={
        <AppText variant="body" weight="heavy" testID="papers-count">
          {String(papers.length)}
        </AppText>
      }
      footer={
        <Button grow variant="primary" onPress={() => go('FF-15')} testID="papers-done">
          {t('field.ff60.done', { count: papers.length })}
        </Button>
      }
    >
      {asset ? (
        <View testID="papers-asset">
          <AppText variant="section">{[asset.serial ?? asset.badge ?? asset.id, asset.size, asset.model].filter(Boolean).join(' · ')}</AppText>
          {view?.premise?.address_line ? (
            <AppText variant="label" tone="muted">
              {view.premise.address_line}
            </AppText>
          ) : null}
        </View>
      ) : (
        <Notice tone="info" testID="papers-no-asset">
          {view ? t('field.ff60.noAsset') : t('field.job.noJob')}
        </Notice>
      )}
      {papers.map((p) => {
        const src = SOURCE[p.source];
        const detail =
          p.source === 'typed'
            ? (typedWords.get(p.id) ?? '')
            : [p.kind === 'application/pdf' ? t('field.ff60.pdf') : null, p.bytes > 0 ? fileSize(p.bytes, units) : null].filter(Boolean).join(' · ');
        return (
          <Card key={p.id} testID={`paper-${p.id}`}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
              {p.source === 'camera' ? (
                <PhotoThumb path={p.local_path} label={p.title} />
              ) : (
                <View style={{ width: theme.touch.primary, height: theme.touch.primary, alignItems: 'center', justifyContent: 'center', backgroundColor: theme.colors.surface }}>
                  <Glyph name={p.source === 'typed' ? 'menu' : 'forward'} colour={theme.colors.textMuted} />
                </View>
              )}
              <View style={{ flexGrow: 1, flexShrink: 1 }}>
                <AppText variant="body" weight="heavy">
                  {p.title}
                </AppText>
                {detail ? (
                  <AppText variant="label" tone="muted">
                    {detail}
                  </AppText>
                ) : null}
              </View>
              <StatusChip tone={src.tone} testID={`paper-${p.id}-source`}>
                {t(src.key)}
              </StatusChip>
            </View>
          </Card>
        );
      })}
      <Kicker>{t('field.ff60.addOne')}</Kicker>
      <View style={{ flexDirection: 'row', gap: theme.touch.clear }}>
        <Button grow size="sm" icon={<Glyph name="camera" />} disabled={!asset} onPress={() => void photograph()} testID="papers-photograph">
          {t('field.ff60.photograph')}
        </Button>
        <Button grow size="sm" disabled={!asset} onPress={() => void pickFile()} testID="papers-file">
          {t('field.ff60.file')}
        </Button>
        <Button grow size="sm" disabled={!asset} onPress={() => open({ source: 'typed' }, '')} testID="papers-typed">
          {t('field.ff60.type')}
        </Button>
      </View>
      {camera.error ? <Notice tone="danger">{camera.error}</Notice> : null}
      {fileError ? (
        <Notice tone="danger" testID="papers-file-error">
          {fileError}
        </Notice>
      ) : null}
      <Sheet
        visible={draft !== null}
        onClose={() => setDraft(null)}
        title={draft?.source === 'typed' ? t('field.ff60.type') : t('field.ff60.name')}
        closeLabel={t('field.job.close')}
        testID="paper-sheet"
        footer={
          <>
            <Button grow onPress={() => setDraft(null)}>
              {t('field.job.cancel')}
            </Button>
            <Button grow variant="primary" disabled={!ready} onPress={save} testID="paper-save">
              {t('field.job.save')}
            </Button>
          </>
        }
      >
        <FieldGroup>
          <Field label={t('field.ff60.name')} value={title} onChangeText={setTitle} testID="paper-title" />
          {draft?.source === 'typed' ? <Field label={t('field.ff60.words')} value={text} onChangeText={setText} testID="paper-text" /> : null}
        </FieldGroup>
      </Sheet>
    </JobScreen>
  );
}
