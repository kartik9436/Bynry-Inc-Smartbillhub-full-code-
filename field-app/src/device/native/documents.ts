/**
 * THE REAL DOCUMENT OPENER behind `DocumentOpener` (`../ports.ts`) — FB-031,
 * PO ruling B (decision log 2026-10-31): *"Hand it to the phone's own PDF app
 * ("Open with…")"*. The file is already on the phone (fetched at sync and kept
 * for offline use); this only hands that copy to the operating system.
 *
 *   Android  a `content://` URI for the file (`FileSystem.getContentUriAsync`,
 *            which grants nothing by itself) and an `ACTION_VIEW` intent
 *            carrying FLAG_GRANT_READ_URI_PERMISSION and the file's type, so
 *            the installed viewer may read it. No activity for that type is
 *            `NoAppError` — *No app can open this.*
 *   iOS      the system share / *Open in…* sheet (`expo-sharing`), which lists
 *            the apps that take the file and offers Quick Look.
 *
 * It leaves our app, which the PO accepted in the same sentence; a phone with
 * no app for the file says so rather than opening nothing.
 */
import * as FileSystem from 'expo-file-system';
import * as IntentLauncher from 'expo-intent-launcher';
import * as Sharing from 'expo-sharing';
import { Platform } from 'react-native';

import { withSystemInteraction } from '../../session/systemInteraction';
import { type DocumentOpener, NoAppError } from '../ports';

/** `Intent.FLAG_GRANT_READ_URI_PERMISSION`. */
export const FLAG_GRANT_READ_URI_PERMISSION = 1;
export const ACTION_VIEW = 'android.intent.action.VIEW';

/** An Android "no activity found" in whatever words the platform used. */
function isNoActivity(err: unknown): boolean {
  const text = err instanceof Error ? `${err.message} ${(err as { code?: string }).code ?? ''}` : String(err);
  return /ActivityNotFound|No Activity found|no activity|ERR_INTENT|unable to resolve/i.test(text);
}

/** A path the phone keeps (`help/…`) as the absolute file URI the platform wants. */
export function fileUri(localPath: string): string {
  if (/^[a-z][a-z0-9+.-]*:/i.test(localPath)) return localPath;
  return `${FileSystem.documentDirectory ?? ''}${localPath.replace(/^\/+/, '')}`;
}

export function osDocumentOpener(platform: string = Platform.OS): DocumentOpener {
  return {
    async open(localPath: string, contentType?: string): Promise<void> {
      const uri = fileUri(localPath);
      if (platform === 'android') {
        const data = await FileSystem.getContentUriAsync(uri);
        try {
          // The viewer is another app: the platform's own screen, never "leaving" (MQ-019).
          await withSystemInteraction(() =>
            IntentLauncher.startActivityAsync(ACTION_VIEW, {
              data,
              flags: FLAG_GRANT_READ_URI_PERMISSION,
              ...(contentType ? { type: contentType } : {}),
            }),
          );
        } catch (err) {
          if (isNoActivity(err)) throw new NoAppError(localPath);
          throw err;
        }
        return;
      }
      if (!(await Sharing.isAvailableAsync())) throw new NoAppError(localPath);
      await withSystemInteraction(() =>
        Sharing.shareAsync(uri, { ...(contentType ? { mimeType: contentType, UTI: utiOf(contentType) } : {}) }),
      );
    },
  };
}

/** iOS wants a Uniform Type Identifier for the sheet to offer the right apps. */
function utiOf(contentType: string): string | undefined {
  return contentType === 'application/pdf' ? 'com.adobe.pdf' : contentType === 'image/png' ? 'public.png' : contentType === 'image/jpeg' ? 'public.jpeg' : undefined;
}
