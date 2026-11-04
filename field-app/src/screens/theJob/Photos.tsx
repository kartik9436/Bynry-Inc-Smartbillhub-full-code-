/**
 * FF-21 Photos — a REVIEW of every photograph on the job, under the step or
 * reading it proves (R6: *"The gallery is a review, never the place of
 * capture"*; US-FLD-027). Each shows its stamp — date, time, position ±
 * accuracy, who, which order (R94) — and one still on the handset says it is
 * waiting to upload and how big it is (TC-4: the declaration already went with
 * the data, R123).
 *
 * ⚠ THE BOARD DRAWS *Take photo* ON A MISSING REQUIRED PHOTOGRAPH, AND R6 (PO
 * ruled) SAYS THIS SCREEN NEVER CAPTURES. The signed rule wins: the missing
 * one is shown as missing, marked REQUIRED, and is taken on its step. No
 * gallery is offered anywhere (R93, TC-3).
 *
 * A required photograph never taken blocks the close (`REQUIRED_PHOTO_BLOCKS_
 * CLOSE`, `BR-WRK-040`); one short of the count only warns (R110).
 *
 * Built from `phone/FF-21-photos.png`. Doors: back → FF-15, *Close job* →
 * FF-34, *Before and after* / *Compare* → FF-22.
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, Glyph, Kicker, Notice, PhotoThumb, StatusChip } from '../../components';
import type { OrderPhotoRow } from '../../db/queries/jobScreens';
import { COLUMN_GAP, rowsOf, usePaneColumns } from '../../tablet/columns';
import { useTheme } from '../../theme';
import { fileSize, hhmm } from './format';
import { JobScreen, useDoor } from './JobScreen';
import { REQUIRED_PHOTO_BLOCKS_CLOSE, requiredPhotosMissing } from './jobModel';
import { pathOf, stampOfRow } from './photoStamp';
import { useOpenJob } from './useJob';

interface Proof {
  id: string;
  title: string;
  required: boolean;
  labels: string[];
  photos: OrderPhotoRow[];
  kind: 'task' | 'reading';
}

export function Photos() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-21');
  const { port, view } = useOpenJob();
  const order = view?.order.number ?? '';
  const who = (p: OrderPhotoRow) => (p.captured_by === port?.captor().capturedBy ? port.displayName : p.captured_by);

  const proofs: Proof[] = view
    ? [
        ...view.tasks.items
          .filter((x) => x.photoMin > 0 || x.photos.length > 0)
          .map((x) => ({
            id: x.row.id,
            title: x.row.label,
            required: x.row.photo_required === 1,
            labels: x.detail.photo_labels ?? [],
            photos: x.photos,
            kind: 'task' as const,
          })),
        ...view.readings.items
          .filter((r) => r.row.photo_required === 1 || r.photos.length > 0)
          .map((r) => ({ id: r.row.id, title: r.row.prompt, required: r.row.photo_required === 1, labels: [], photos: r.photos, kind: 'reading' as const })),
      ]
    : [];
  const withPhotos = proofs.filter((p) => p.photos.length > 0).length;
  const missing = view ? requiredPhotosMissing(view).length : 0;

  // FF-21 T *The photo gallery, grouped by what it proves*: on a tablet the
  // proofs sit under FROM THE TASKS / FROM THE READINGS as a wall, as many
  // across as the pane holds at 260 or more (R121, R122 — `fitColumns`). The
  // board draws four narrower tiles; the 260 rule wins, so the wide pane
  // holds two. A phone keeps the one column it always had.
  const columns = usePaneColumns(4);
  const groups = [
    { kind: 'task' as const, titleKey: 'field.tablet.ff21.fromTasks', proofs: proofs.filter((p) => p.kind === 'task') },
    { kind: 'reading' as const, titleKey: 'field.tablet.ff21.fromReadings', proofs: proofs.filter((p) => p.kind === 'reading') },
  ].filter((g) => g.proofs.length > 0);
  const card = (proof: Proof) => (
    <Card
      key={proof.id}
      title={proof.title}
      trailing={proof.required && proof.photos.length === 0 ? <StatusChip tone="danger">{t('field.ff21.required')}</StatusChip> : undefined}
      testID={`proof-${proof.id}`}
    >
      {proof.photos.length === 0 ? (
        <View
          accessible
          accessibilityLabel={t('field.ff21.notTaken')}
          style={{
            minHeight: theme.touch.primary * 2,
            alignItems: 'center',
            justifyContent: 'center',
            borderWidth: theme.borderWidth.emphasis,
            borderStyle: 'dashed',
            borderColor: theme.colors.controlBorder,
            backgroundColor: theme.colors.surface,
          }}
          testID={`proof-${proof.id}-missing`}
        >
          <AppText variant="body" tone="muted">
            {t('field.ff21.notTaken')}
          </AppText>
        </View>
      ) : (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space[3] }}>
          {proof.photos.map((p, k) => (
            <View key={p.id} style={{ flexGrow: 1, flexBasis: '45%', gap: theme.space[1] }}>
              <PhotoThumb
                size="large"
                path={pathOf(p)}
                label={proof.labels[k] ?? t('field.job.photoAt', { time: hhmm(p.captured_at) })}
                stamp={stampOfRow(t, p, who(p), order, port?.tenantName ?? '')}
                testID={`photo-${p.id}`}
              />
              {proof.labels[k] ? <AppText variant="label">{proof.labels[k]}</AppText> : null}
              {p.state !== 'uploaded' ? (
                <AppText variant="label" tone="muted" testID={`photo-${p.id}-waiting`}>
                  {t('field.ff21.waiting', { size: fileSize(p.bytes, { kb: t('field.job.unit.kb'), mb: t('field.job.unit.mb') }) })}
                </AppText>
              ) : null}
            </View>
          ))}
        </View>
      )}
      {proof.photos.length >= 2 ? (
        <Button size="sm" onPress={() => go('FF-22', { proofId: proof.id })} testID={`compare-${proof.id}`}>
          {t('field.ff21.compare')}
        </Button>
      ) : null}
    </Card>
  );

  return (
    <JobScreen
      id="FF-21"
      title={t('field.screen.ff21')}
      back={{ to: 'FF-15', label: t('field.job.backToJob') }}
      trailing={
        <AppText variant="body" weight="heavy" testID="photos-count">
          {t('field.job.nOfM', { done: withPhotos, total: proofs.length })}
        </AppText>
      }
      footer={
        <View style={{ flexGrow: 1, gap: theme.touch.clear }}>
          <Button variant="primary" onPress={() => go('FF-34')} testID="door-FF-34">
            {t('field.ff21.closeJob')}
          </Button>
          <Button onPress={() => go('FF-22')} testID="door-FF-22">
            {t('field.ff21.beforeAfter')}
          </Button>
        </View>
      }
    >
      {view === null ? <Notice tone="info">{t('field.job.noJob')}</Notice> : null}
      {missing > 0 ? (
        // PO 2026-10-21: a missing required photo warns, never blocks (`REQUIRED_PHOTO_BLOCKS_CLOSE`).
        <Notice tone={REQUIRED_PHOTO_BLOCKS_CLOSE ? 'danger' : 'warning'} icon={<Glyph name="warning" />} testID="photos-missing">
          {t('field.ff21.missing', { count: missing })}
        </Notice>
      ) : null}
      {columns > 1
        ? groups.map((g) => (
            <View key={g.kind} style={{ gap: theme.space[2] }} testID={`photos-group-${g.kind}`}>
              <Kicker>{t(g.titleKey)}</Kicker>
              {rowsOf(g.proofs, columns).map((row) => (
                <View key={row.map((p) => p.id).join()} style={{ flexDirection: 'row', gap: COLUMN_GAP }} testID="photos-row">
                  {row.map((proof) => (
                    <View key={proof.id} style={{ flex: 1 }} testID="photos-cell">
                      {card(proof)}
                    </View>
                  ))}
                  {row.length < columns ? <View style={{ flex: columns - row.length }} /> : null}
                </View>
              ))}
            </View>
          ))
        : proofs.map((proof) => card(proof))}
    </JobScreen>
  );
}
