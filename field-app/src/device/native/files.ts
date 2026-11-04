/**
 * The REAL file picker behind `FilePickerPort` (`../photo.ts`): `expo-document-picker`,
 * for FF-60's *A file* (R108). One file; copied into the app's cache so the
 * outbox holds a path the app owns. Backing out is `null`, never an error.
 */
import * as DocumentPicker from 'expo-document-picker';

import { withSystemInteraction } from '../../session/systemInteraction';
import type { FilePickerPort, PickedFile } from '../photo';

export function expoFilePicker(): FilePickerPort {
  return {
    async pick(): Promise<PickedFile | null> {
      // The platform's picker is the app's own system screen; never "leaving" (MQ-019).
      const result = await withSystemInteraction(() =>
        DocumentPicker.getDocumentAsync({ multiple: false, copyToCacheDirectory: true }),
      );
      if (result.canceled) return null;
      const asset = result.assets?.[0];
      if (!asset) return null;
      return { uri: asset.uri, name: asset.name, bytes: asset.size ?? 0, mimeType: asset.mimeType ?? null };
    },
  };
}
