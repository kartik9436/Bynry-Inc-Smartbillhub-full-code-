/**
 * FB-031 (DEF-FLD-10805) — the real document opener: the phone's own copy is
 * handed to the operating system's *Open with…* (PO ruling B, 2026-10-31).
 * Android: a content URI, ACTION_VIEW, the read grant and the file's type.
 * iOS: the system sheet. No app for the file is `NoAppError`, which FF-28
 * says as *No app can open this.*
 *
 * Proved RED (law 7) before `src/device/native/documents.ts` existed: the
 * suite failed on `Cannot find module '../../../src/device/native/documents'`.
 */
import * as IntentLauncher from 'expo-intent-launcher';
import * as Sharing from 'expo-sharing';

import { NoAppError } from '../../../src/device';
import { ACTION_VIEW, FLAG_GRANT_READ_URI_PERMISSION, osDocumentOpener } from '../../../src/device/native/documents';

jest.mock('expo-file-system', () => ({
  documentDirectory: 'file:///data/user/0/app/files/',
  getContentUriAsync: jest.fn(async (uri: string) => uri.replace('file:///data/user/0/app/files/', 'content://app.fileprovider/files/')),
}));

const IL = IntentLauncher as jest.Mocked<typeof IntentLauncher>;
const SH = Sharing as jest.Mocked<typeof Sharing>;

beforeEach(() => jest.clearAllMocks());

test('Android: the file goes to the installed viewer as a content URI with the read grant and its type', async () => {
  await osDocumentOpener('android').open('file:///data/user/0/app/files/help/wo-1-h1.pdf', 'application/pdf');
  expect(IL.startActivityAsync).toHaveBeenCalledWith(ACTION_VIEW, {
    data: 'content://app.fileprovider/files/help/wo-1-h1.pdf',
    flags: FLAG_GRANT_READ_URI_PERMISSION,
    type: 'application/pdf',
  });
  expect(FLAG_GRANT_READ_URI_PERMISSION).toBe(1);
});

test('Android with no app for the file: NoAppError, never a silent nothing', async () => {
  IL.startActivityAsync.mockRejectedValueOnce(
    Object.assign(new Error('No Activity found to handle Intent { act=android.intent.action.VIEW }'), { code: 'ERR_UNEXPECTED' }),
  );
  await expect(osDocumentOpener('android').open('help/wo-1-h1.pdf', 'application/pdf')).rejects.toBeInstanceOf(NoAppError);
});

test('Android: any other failure is not dressed up as "no app"', async () => {
  IL.startActivityAsync.mockRejectedValueOnce(new Error('permission denied'));
  await expect(osDocumentOpener('android').open('help/wo-1-h1.pdf')).rejects.not.toBeInstanceOf(NoAppError);
});

test('iOS: the system sheet, told what the file is; no sheet at all is NoAppError', async () => {
  await osDocumentOpener('ios').open('help/wo-1-h1.pdf', 'application/pdf');
  expect(SH.shareAsync).toHaveBeenCalledWith('file:///data/user/0/app/files/help/wo-1-h1.pdf', {
    mimeType: 'application/pdf',
    UTI: 'com.adobe.pdf',
  });
  SH.isAvailableAsync.mockResolvedValueOnce(false);
  await expect(osDocumentOpener('ios').open('help/wo-1-h1.pdf')).rejects.toBeInstanceOf(NoAppError);
});
