// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 §F — lane FIELD-2: the field app's screens move onto
//           the technician API (capture token, acknowledged outbox, photo
//           links created with the record, automatic location).
// Rules:    BR-WRK-059 (the captor rides on the item) · BR-WRK-060 (unsent
//           work stays the captor's) · BR-WRK-061 (location on every item) ·
//           BR-WRK-062 (photo link with the record; bytes in the background) ·
//           BR-WRK-063 (an item leaves the phone only on its ack) ·
//           BR-WRK-042 (captured offline, keyed at capture)
// Tests:    src/features/work/mobile/capture.test.ts
// ───────────────────────────────────────────────────────

/**
 * THE ONE WAY A SCREEN RECORDS SOMETHING THE TECHNICIAN DID.
 *
 * Every tick, reading, photograph and close goes through `capture` (or
 * `capturePhoto`), and each does the same three things in the same order:
 *
 *  1. **Stamp it at capture** — the key, the capture time, the signed-in
 *     technician's capture token, and the best location fix the job has.
 *     Nothing is read again at send time, so an item captured by Patel and
 *     sent while Chen is signed in is still Patel's (`BR-WRK-059`/`060`).
 *  2. **Write it to the phone first** — the outbox in IndexedDB. A request
 *     that dies halfway leaves the work recorded, never lost.
 *  3. **Then try to send it**, if there is a signal. The item leaves the phone
 *     only when the server names it in `acknowledged` (`BR-WRK-063`).
 *
 * One path, two speeds: online and offline are the same code, so the offline
 * path is the one every screen and every test exercises.
 */

import { compressPhoto } from "./compressPhoto";
import { bestFix } from "./location";
import { flushOutbox, type SyncBatchResult } from "./mobileEndpoints";
import {
  captureToken,
  currentUser,
  declarePhoto,
  enqueue,
  nextSeq,
  photoItemKey,
  putPhoto,
  type QueuedItem,
} from "./offlineStore";

function isOffline(): boolean {
  return typeof navigator !== "undefined" && navigator.onLine === false;
}

/** Record one act; send it if there is a signal. Returns the flush's answer
 *  when one was attempted (so a screen can show a refusal), else `null`. */
export async function capture(input: {
  orderId: string;
  kind: QueuedItem["kind"];
  key: string;
  payload: Record<string, unknown>;
  send?: boolean;
}): Promise<{ item: QueuedItem; sent: SyncBatchResult[] | null }> {
  const item: QueuedItem = {
    key: input.key,
    orderId: input.orderId,
    kind: input.kind,
    seq: await nextSeq(input.orderId),
    capturedAt: new Date().toISOString(),
    payload: input.payload,
    captureToken: await captureToken(),
    owner: currentUser(),
    location: await bestFix(input.orderId),
  };
  await enqueue(item);
  if (input.send === false || isOffline()) return { item, sent: null };
  try {
    return { item, sent: await flushOutbox() };
  } catch {
    // A failed send is not an error here, it is *offline*: the item is queued.
    return { item, sent: null };
  }
}

/** The bytes of a blob, in every browser and in jsdom. */
async function bytesOf(blob: Blob): Promise<ArrayBuffer> {
  if (typeof blob.arrayBuffer === "function") return blob.arrayBuffer();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
}

/** Hex sha256 — what the server checks the uploaded bytes against. */
export async function sha256Hex(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await bytesOf(blob));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function newPhotoId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // RFC 4122 v4 from getRandomValues — a phone browser without randomUUID.
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

/**
 * A photograph: compressed (70–100 KB), hashed, its bytes kept on the phone,
 * and its DATA — id, hash, the task or reading — queued like any other item.
 * The server creates the link when it saves the data page; the bytes follow
 * to that link in the background (`BR-WRK-062`). Works with no signal at all.
 */
export async function capturePhoto(input: {
  orderId: string;
  file: File | Blob;
  taskId?: string;
  readingId?: string;
}): Promise<{ photoId: string; sent: SyncBatchResult[] | null }> {
  const small = await compressPhoto(input.file as File);
  const photoId = newPhotoId();
  const sha256 = await sha256Hex(small);
  const takenAt = new Date().toISOString();
  await putPhoto({
    photoId,
    orderId: input.orderId,
    owner: currentUser(),
    sha256,
    blob: small,
    taskId: input.taskId ?? null,
    readingId: input.readingId ?? null,
    takenAt,
  });
  const rowId = input.taskId ?? input.readingId;
  if (rowId) await declarePhoto(input.orderId, rowId, photoId);
  const payload: Record<string, unknown> = { photo_id: photoId, sha256 };
  if (input.taskId) payload.task_id = input.taskId;
  if (input.readingId) payload.reading_id = input.readingId;
  const { sent } = await capture({
    orderId: input.orderId,
    kind: "photo",
    key: photoItemKey(photoId),
    payload,
  });
  return { photoId, sent };
}
