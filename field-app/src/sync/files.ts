/** The handset's file store for photographs and documents (expo-file-system). */
import * as FileSystem from 'expo-file-system';

import type { FileStore } from './photos';
import { TRANSFER_TIME_LIMIT_MS, TransportError, withTimeLimit } from './transport';

/**
 * Fetching a job's help document into the phone's own store, AT SYNC
 * (BR-WRK-038, DEF-FLD-10581): the bytes are what the phone keeps and opens
 * offline. Resolves where the file landed and its size; rejects when it did
 * not land — with the HTTP status when there was one (a `TransportError`), so
 * a refused or expired link sends the job's bundle to be fetched again.
 *
 * FB-031 (DEF-FLD-10805): `headers` — our own route (`…/help/{id}/content`)
 * is fetched with the technician's credential and the build's headers
 * (`FieldApi.fileRequest`); a storage link is fetched bare, as before.
 */
export interface HelpDownloads {
  download(url: string, name: string, headers?: Record<string, string>): Promise<{ path: string; bytes: number }>;
}

export const expoFileStore: FileStore & HelpDownloads = {
  async exists(path: string): Promise<boolean> {
    return (await FileSystem.getInfoAsync(path)).exists;
  },
  async delete(path: string): Promise<void> {
    // idempotent: a file already gone is the state we wanted
    await FileSystem.deleteAsync(path, { idempotent: true });
  },
  async download(url: string, name: string, headers?: Record<string, string>): Promise<{ path: string; bytes: number }> {
    const dir = `${FileSystem.documentDirectory ?? ''}help/`;
    await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
    const to = `${dir}${name}`;
    // A time limit like every server call (DEF-FLD-10608): a stalled link is
    // cancelled and the row waits for the next sync's fresh link.
    const task = FileSystem.createDownloadResumable(url, to, headers ? { headers } : {});
    const answer = await withTimeLimit(() => task.downloadAsync(), TRANSFER_TIME_LIMIT_MS, () => {
      void task.cancelAsync().then(() => FileSystem.deleteAsync(to, { idempotent: true })).catch(() => undefined);
    });
    if (!answer) throw new Error('help document: cancelled');
    if (answer.status < 200 || answer.status >= 300) {
      await FileSystem.deleteAsync(to, { idempotent: true });
      throw new TransportError('http', `help document: HTTP ${answer.status}`, answer.status);
    }
    const info = await FileSystem.getInfoAsync(to);
    return { path: to, bytes: info.exists ? info.size : 0 };
  },
};
