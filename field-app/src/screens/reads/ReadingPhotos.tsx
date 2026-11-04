/**
 * A reading's photographs — the thumbnail row and the full-size viewer
 * (DEF-FLD-10630, FB-002; B14 rule 43: built as components, used by RW-09 and
 * RW-13).
 *
 * FB-002: a photo, once taken, was shown nowhere — RW-09's button became a
 * count, and the count opened the camera again. Now every photo of the
 * reading is a thumbnail, and a thumbnail opens the photo full size.
 *
 * PO 2026-10-27 (*"go with recommendation"*): what the viewer offers depends on
 * whether the reading is SAVED.
 *   - Before saving, the photos are a draft: **Retake** and **Remove**, freely.
 *     Pass `onRetake` and `onRemove`.
 *   - After saving, the reading and its photos are the evidence: the viewer
 *     shows the photo and nothing else. Pass neither — the screen offers
 *     *Add photo* beside the row instead.
 *
 * A photograph whose file has gone to the server (R61) has no path; its
 * thumbnail is the plain panel `PhotoThumb` draws, so it still shows it was
 * taken. Sizes are the field app's (rule 45): a thumbnail is 56pt tall, every
 * control 48pt or more, 8pt clear between.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, View } from 'react-native';

import { Button, PhotoThumb, Sheet } from '../../components';
import { useTheme } from '../../theme';
import type { CameraShot } from './ports';
import { useGo } from './ReadsScreen';
import { useReads } from './services';

export interface ShownPhoto {
  /** Stable for the row (a photo id, or a draft file's path). */
  key: string;
  /** The file on the phone; null once it has gone to the server. */
  path: string | null;
  /** One short line under the thumbnail — its time. */
  caption?: string;
}

/** The row of thumbnails. Renders nothing when there are none. */
export function PhotoStrip(props: { photos: readonly ShownPhoto[]; onOpen: (index: number) => void; testID?: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  if (props.photos.length === 0) return null;
  const id = props.testID ?? 'reading-photos';
  return (
    <View testID={id} style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.touch.clear }}>
      {props.photos.map((p, i) => (
        <Pressable
          key={p.key}
          accessibilityRole="button"
          accessibilityLabel={t('field.reads.photos.open', { n: i + 1 })}
          onPress={() => props.onOpen(i)}
          testID={`reading-photo-${i}`}
          style={{ minHeight: theme.touch.control, minWidth: theme.touch.control }}
        >
          <PhotoThumb path={p.path} label={t('field.reads.photos.open', { n: i + 1 })} caption={p.caption} />
        </Pressable>
      ))}
    </View>
  );
}

/**
 * One photo full size, in a sheet. With `onRetake`/`onRemove` (a reading not
 * yet saved) it offers both; without them it only shows the photo.
 */
export function PhotoViewer(props: {
  photos: readonly ShownPhoto[];
  /** The photo open, or null when the viewer is shut. */
  index: number | null;
  onClose: () => void;
  onRetake?: (index: number) => void;
  onRemove?: (index: number) => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const i = props.index;
  const shown = i !== null ? props.photos[i] : undefined;
  return (
    <Sheet
      visible={shown !== undefined}
      onClose={props.onClose}
      title={i !== null ? t('field.reads.photos.nOfM', { n: i + 1, m: props.photos.length }) : ''}
      closeLabel={t('field.reads.common.close')}
      testID="photo-viewer"
      footer={
        <Button grow onPress={props.onClose} testID="photo-viewer-close">
          {t('field.reads.common.close')}
        </Button>
      }
    >
      {shown && i !== null ? (
        <View style={{ gap: theme.touch.clear }}>
          <PhotoThumb path={shown.path} size="large" label={t('field.reads.photos.open', { n: i + 1 })} testID="photo-viewer-image" />
          {props.onRetake || props.onRemove ? (
            <View style={{ flexDirection: 'row', gap: theme.touch.clear }}>
              {props.onRetake ? (
                <Button grow onPress={() => props.onRetake?.(i)} testID="photo-retake">
                  {t('field.reads.photos.retake')}
                </Button>
              ) : null}
              {props.onRemove ? (
                <Button grow variant="danger" onPress={() => props.onRemove?.(i)} testID="photo-remove">
                  {t('field.reads.photos.remove')}
                </Button>
              ) : null}
            </View>
          ) : null}
        </View>
      ) : null}
    </Sheet>
  );
}

/**
 * The photos of a reading NOT YET SAVED — the row and its viewer, with Retake
 * and Remove (PO 2026-10-27). Used by every screen that holds a draft's
 * photos: RW-09, RW-15 and RW-17. Retake opens RW-14 with the photo's place in
 * the address; Remove hands the new list to `onChange` and deletes the file,
 * which was never declared, so nothing travels.
 */
export function DraftPhotos(props: { readId: string; photos: readonly CameraShot[]; onChange: (next: CameraShot[]) => void }) {
  const go = useGo();
  const { services } = useReads();
  const viewer = useViewer();
  const shown: ShownPhoto[] = props.photos.map((p) => ({ key: p.localPath, path: p.localPath }));
  return (
    <>
      <PhotoStrip photos={shown} onOpen={viewer.open} />
      <PhotoViewer
        photos={shown}
        index={viewer.index}
        onClose={viewer.close}
        onRetake={(i) => {
          viewer.close();
          go('RW-14', { readId: props.readId, photo: String(i) });
        }}
        onRemove={(i) => {
          const gone = props.photos[i];
          viewer.close();
          props.onChange(props.photos.filter((_, j) => j !== i));
          if (gone) void services.camera.discard?.(gone.localPath);
        }}
      />
    </>
  );
}

/** The open/close state of one viewer, for the screen that holds the row. */
export function useViewer(): { index: number | null; open: (i: number) => void; close: () => void } {
  const [index, setIndex] = useState<number | null>(null);
  return { index, open: setIndex, close: () => setIndex(null) };
}
