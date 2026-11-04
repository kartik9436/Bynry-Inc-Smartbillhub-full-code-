/**
 * RecordPhoto — one photograph in a RECORD (FF-35's job record, RW-28's
 * reading), whether its file is still on the phone or not (FB-030, PO
 * 2026-10-31, *"keep photos only for 3 days"*; B14 rule 43 — a component, not
 * code inside a page).
 *
 *   - FILE ON THE PHONE (the first 3 days after the close or the turn-in):
 *     drawn from the file, like every other thumbnail (`PhotoThumb`).
 *   - FILE GONE: the row stays, so the record still shows a photograph was
 *     taken. A TAP loads it from the server — own work only, the request
 *     carries this sign-in's credential and the server answers `no-store` —
 *     and it is SHOWN, NEVER STORED. With no signal the tile says
 *     *Needs signal* and nothing is asked.
 *
 * Nothing is fetched until the tap (BR-WRK-042's posture: no network on a
 * screen opening). The port is provided once by the runtime
 * (`RemotePhotoProvider`); with no port (a preview, a test without a server)
 * a gone file reads *Needs signal*, which is the truth.
 */
import { createContext, type ReactNode, useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Image, Pressable, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';
import { PhotoThumb } from './PhotoThumb';

export type RemotePhotoKind = 'job' | 'route';

/** Where a gone photograph loads from, and whether there is a signal to ask. */
export interface RemotePhotoPort {
  online(): boolean;
  source(kind: RemotePhotoKind, photoId: string): { uri: string; headers: Record<string, string> } | null;
}

const RemotePhotoContext = createContext<RemotePhotoPort | null>(null);

export function RemotePhotoProvider(props: { value: RemotePhotoPort | null; children: ReactNode }) {
  return <RemotePhotoContext.Provider value={props.value}>{props.children}</RemotePhotoContext.Provider>;
}

export function useRemotePhoto(): RemotePhotoPort | null {
  return useContext(RemotePhotoContext);
}

export interface RecordPhotoProps {
  /** The phone's own photo id — the server's link is keyed on it. */
  photoId: string;
  kind: RemotePhotoKind;
  /** The file on the phone, or null once it is gone. */
  path: string | null;
  label: string;
  caption?: string;
  testID?: string;
}

export function RecordPhoto({ photoId, kind, path, label, caption, testID }: RecordPhotoProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const port = useRemotePhoto();
  const [loaded, setLoaded] = useState<{ uri: string; headers: Record<string, string> } | null>(null);
  const [noSignal, setNoSignal] = useState(false);
  if (path) return <PhotoThumb path={path} label={label} caption={caption} testID={testID} />;

  const open = () => {
    const src = port && port.online() ? port.source(kind, photoId) : null;
    if (!src) {
      setNoSignal(true);
      return;
    }
    setNoSignal(false);
    setLoaded(src);
  };

  return (
    <Pressable
      accessibilityRole="imagebutton"
      accessibilityLabel={label}
      onPress={open}
      style={{ minHeight: theme.touch.control }}
      testID={testID}
    >
      <View
        style={{
          width: theme.touch.primary + theme.space[6],
          height: theme.touch.primary,
          backgroundColor: theme.colors.surface,
          borderWidth: theme.borderWidth.card,
          borderColor: theme.colors.border,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {loaded ? (
          // `cache: 'reload'` — fetched for this view, not kept (FB-030: never stored).
          <Image
            source={{ uri: loaded.uri, headers: loaded.headers, cache: 'reload' }}
            style={{ width: '100%', height: '100%' }}
            resizeMode="cover"
            onError={() => {
              setLoaded(null);
              setNoSignal(true);
            }}
            testID={testID ? `${testID}-remote` : undefined}
          />
        ) : (
          <AppText variant="micro" tone="muted" style={{ textAlign: 'center' }} testID={testID ? `${testID}-state` : undefined}>
            {noSignal ? t('field.record.needsSignal') : t('field.record.tapToLoad')}
          </AppText>
        )}
      </View>
      {caption ? (
        <AppText variant="micro" tone="muted">
          {caption}
        </AppText>
      ) : null}
    </Pressable>
  );
}
