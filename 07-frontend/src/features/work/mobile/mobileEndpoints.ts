// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-041 (today's jobs) · US-WRK-042 (the job) · US-WRK-030
//           (the device token).  Screens: Work-010, Work-011
// Rules:    BR-WRK-035 (ordered by appointment time — the SERVER orders it) ·
//           BR-WRK-042 (the bundle is fetched at sync, never on tap) ·
//           BR-WRK-036 (the marker is the phone's own fact)
// Tests:    src/features/work/mobile/TodayPage.test.tsx ·
//           src/features/work/mobile/JobPage.test.tsx
// Impacts:  06-backend/apps/work/api.py (#88, #89, #90, #91)
// ───────────────────────────────────────────────────────
import { api } from "@/api/client";
import type { ApiClient, ApiResponse } from "@/api/client";

import {
  acknowledge,
  currentUser,
  dropJob,
  dropPhoto,
  feedCursor,
  markSynced,
  pendingPhotos,
  queuedItems,
  readDay,
  readJob,
  setFeedCursor,
  writeDay,
  writeJob,
  type PendingPhoto,
  type QueuedItem,
} from "./offlineStore";

function requireData<T>(response: ApiResponse<T>): T {
  if (response.data === null) {
    throw new Error(`empty ${response.status} body where the contract promises one`);
  }
  return response.data;
}

/** One card of `Work-010`. Every field is a VALUE — nothing here is prose. */
export type MobileJobCard = {
  id: string;
  order_no: string;
  type: string;
  premise: { address_line?: string | null } | null;
  window_start: string | null;
  window_end: string | null;
  due_at: string | null;
  /** `DEF-WRK-9688` — the booked day and clock times in the UTILITY's zone. */
  appointment?: { date: string; start: string | null; end: string | null; time_zone: string } | null;
  /** `DEF-WRK-9693` — no visit booked; drawn last, under *Unscheduled*. */
  unscheduled?: boolean;
  est_minutes: number | null;
  priority: { code?: string; name?: string; colour?: string } | null;
  state: string;
  dispatch_state: string;
  access_notes: string;
  hazards: string;
  gate_code: string;
};

export type MobileDay = {
  technician: { name: string; van: string; status: string } | null;
  jobs: MobileJobCard[];
  count: number;
  done: number;
  /**
   * A TOKEN, never a sentence. The screen renders its own catalogue's words
   * from it — B14 rule 32 keeps internal codes out of clerk-facing copy, and a
   * JSON body carrying English is a string eleven catalogues cannot translate.
   */
  empty_reason: string | null;
};

export type MobileHelpRow = {
  id: string;
  seq: number;
  /** `link` is ruling 6's (CR-168 P3.25): its https address is `ref`. */
  kind: "document" | "phone" | "link" | "note";
  label: string;
  ref: string | null;
  /** A four-hour pre-signed link, or null. The phone stores the BYTES at sync. */
  url: string | null;
};

export type MobileSafetyRow = {
  id: string;
  seq: number;
  text: string;
  is_mandatory: boolean;
  ticked_at: string | null;
};

export type MobileTaskRow = {
  id: string;
  seq: number;
  title: string;
  est_minutes: number | null;
  photo_required: boolean;
  /**
   * THE FILE beside THE RULE (`US-WRK-049`) — the server has always sent it
   * (`checklist.checklist()`); this type did not declare it until
   * `DEF-WRK-9619`, which is when a task row first had a camera to fill it.
   */
  photo_attachment_id: string | null;
  ticked_at: string | null;
  /** FB-013 / R18 — the step's payment check as the job copied it from its
   *  template (`checklist.checklist()`): how fresh the money must be, in
   *  minutes (null = no check), and a fee's charge code. */
  money_fresh_minutes?: number | null;
  money_charge_code?: string | null;
};

export type MobileBundle = {
  order_id: string;
  order_no: string;
  safety: MobileSafetyRow[];
  safety_lock: {
    locked: boolean;
    remaining: number;
    first_outstanding: string | null;
    ticked: number;
    total: number;
    mandatory_total: number;
  };
  tasks: MobileTaskRow[];
  tasks_total: number;
  tasks_ticked: number;
  tasks_est_minutes: number;
  readings: unknown[];
  materials: unknown[];
  help: MobileHelpRow[];
  details: { access_notes: string; hazards: string; gate_code: string } | null;
  customer: { name: string | null; phone: string | null; account_no: string | null } | null;
  card: MobileJobCard;
  /** CR-168-BRC10 §F — has THIS technician taken the job? (`BR-WRK-059`) */
  technician_acceptance?: { state: "pending" | "accepted" | "declined"; at: string | null; reason: string | null } | null;
};

/** `POST /work/mobile/jobs/{id}/accept` — idempotent (technician-api.md #6). */
export async function acceptJob(
  orderId: string,
  client: ApiClient = api,
): Promise<{ technician_acceptance: NonNullable<MobileBundle["technician_acceptance"]> }> {
  return requireData(await client.post(`/work/mobile/jobs/${orderId}/accept`, {}));
}

/**
 * `GET /work/mobile/today` — and then WRITE IT TO THE STORE.
 *
 * ⚠ **THE SYNC IS STAMPED ONLY WHEN A RESPONSE ACTUALLY ARRIVED.** That is the
 * whole value of `BR-WRK-036`'s marker: *synced 08:12* has to be true. A
 * `finally` block here, or a stamp before the await, would make a phone that
 * has been in a basement for three hours claim it synced this minute.
 */
export async function syncToday(
  query: { days?: number } = {},
  client: ApiClient = api,
): Promise<MobileDay> {
  const day = requireData(
    await client.get<MobileDay>("/work/mobile/today", { query: { days: query.days } }),
  );
  await writeDay(dayKey(query.days ?? 1), day);
  await markSynced();
  return day;
}

/** The cache key for a window. Today and Week are two lists, two rows. */
export function dayKey(days: number): string {
  return days > 1 ? "week" : "today";
}

/**
 * The day as the screen should show it: the network when there is one, the
 * store when there is not.
 *
 * ⚠ **A FAILED FETCH IS NOT AN ERROR HERE, IT IS *OFFLINE*.** `US-WRK-041`
 * TC-3's whole scenario is a technician who has had no signal since 08:12, and
 * an error screen would be a working product telling them it is broken.
 */
export async function loadDay(
  query: { days?: number } = {},
  client: ApiClient = api,
): Promise<{ day: MobileDay | null; fromStore: boolean }> {
  try {
    return { day: await syncToday(query, client), fromStore: false };
  } catch {
    const cached = (await readDay(dayKey(query.days ?? 1))) as MobileDay | null;
    return { day: cached, fromStore: true };
  }
}

/**
 * `GET /work/mobile/jobs/{id}` — and store it.
 *
 * ⚠ **CALLED AT SYNC, NOT ON TAP** (`BR-WRK-042`). `loadJob` below is what a
 * tap calls, and it reads the store FIRST. `US-WRK-042` TC-1 asks for *zero
 * network requests during the tap*, and a read that falls back to the network
 * on a miss would pass every test with a signal and fail the only case that
 * matters — a meter pit with none.
 */
export async function syncJob(orderId: string, client: ApiClient = api): Promise<MobileBundle> {
  const bundle = requireData(await client.get<MobileBundle>(`/work/mobile/jobs/${orderId}`));
  await writeJob(orderId, bundle);
  return bundle;
}

/** A figure as `payments/field_money.money` sends it: 4 places, 2 to show. */
export type MobileMoneyFigure = { amount: string; display: string; currency: string | null };

/** `GET /work/mobile/jobs/{id}/money` — `apps/work/money.money_read` (N13). */
export type MobileJobMoney = {
  as_at: string;
  fresh_minutes: number;
  withheld: string | null;
  owing: MobileMoneyFigure | null;
  balance: MobileMoneyFigure | null;
  currency: string | null;
  latest_payment: (MobileMoneyFigure & { posted_at?: string | null; cleared_at?: string | null }) | null;
};

/**
 * The job's money, read LIVE (R16: a read; never stored on the handset).
 * `DEF-WRK-10644` — the close asks it only when the next step declares a
 * payment check; with no signal it rejects, and the paid close is not offered.
 */
export async function loadJobMoney(orderId: string, client: ApiClient = api): Promise<MobileJobMoney> {
  return requireData(await client.get<MobileJobMoney>(`/work/mobile/jobs/${orderId}/money`));
}

/** What a TAP calls: the store, and nothing else. */
export async function loadJob(orderId: string): Promise<MobileBundle | null> {
  return (await readJob(orderId)) as MobileBundle | null;
}

/**
 * Merge one reading row into the STORED bundle — `DEF-WRK-4113`.
 *
 * ⚠ **WITHOUT THIS THE SCREEN CONTRADICTS ITSELF, AND IT DID.** `Work-012`
 * renders its rows from the offline bundle (`readJob`) and that bundle is
 * written by `syncJob` and by nothing else. So a technician typed 1,204, the
 * server stored it and flagged it, and `refresh()` re-read the bundle from
 * before the visit: **no out-of-range line ever appeared**, and a required
 * photograph that HAD been taken went on saying *Photo needed to close.*
 * Meanwhile the footer — which is live, from `close-readiness` — cheerfully
 * read *2 of 3 required photographs*. One screen, two answers.
 *
 * ⚠ **IT MERGES, IT DOES NOT FETCH.** `BR-WRK-042` and `US-WRK-042` TC-1: the
 * bundle is fetched at SYNC and opening a job reads and never fetches. The
 * fix therefore writes the row the server just handed back into the bundle we
 * already hold, which is correct with no signal — a re-fetch here would be the
 * offline design undone to repair a rendering bug.
 */
export async function mergeReadingIntoJob(
  orderId: string,
  reading: { id: string } & Record<string, unknown>,
): Promise<void> {
  const bundle = (await readJob(orderId)) as MobileBundle | null;
  if (bundle === null) return;
  const rows = (bundle as { readings?: { id: string }[] }).readings;
  if (!Array.isArray(rows)) return;
  await writeJob(orderId, {
    ...bundle,
    readings: rows.map((row) => (row.id === reading.id ? { ...row, ...reading } : row)),
  });
}

/** `POST /work/mobile/devices`. The answer never carries the token. */
export async function registerDevice(
  body: { token: string; platform?: string; label?: string },
  client: ApiClient = api,
): Promise<{ device_id: string; platform: string; last_four: string; created: boolean }> {
  return requireData(await client.post("/work/mobile/devices", body));
}

// ══════════════════════════════════════════════════════════════════════════
// CR-070 wave L · `POST /work/mobile/jobs/{id}/sync` (#90) — the offline day
// ══════════════════════════════════════════════════════════════════════════

/** What the server says about ONE queued item. Three answers, never a boolean. */
export type SyncItemResult = {
  key: string;
  kind: string;
  seq: number | null;
  /** `accepted` is new work · `duplicate` is the queue behaving correctly ·
   *  `refused` is something the technician has to see and re-do. */
  result: "accepted" | "duplicate" | "refused" | "held_for_review";
  ack?: boolean;
  detail?: { message?: string; message_key?: string; params?: Record<string, unknown> } | null;
};

export type SyncBatchResult = {
  work_order_id: string;
  accepted: number;
  duplicate: number;
  refused: number;
  /** Stored as received and flagged for the office — acknowledged, never dropped. */
  held_for_review?: number;
  /** The keys the server has; only these leave the device's outbox. */
  acknowledged?: string[];
  items: SyncItemResult[];
  synced_at: string;
};

/**
 * Send one job's queue, in CAPTURE order, and forget what the server has.
 *
 * ⚠ **`accepted` AND `duplicate` ARE BOTH ACKNOWLEDGEMENTS; `refused` IS NOT.**
 * *Duplicate* means the server already has it, so keeping it would re-send it
 * for ever. *Refused* means it did not happen — a close that arrived before its
 * safety ticks, a photograph whose bytes never landed — so it STAYS QUEUED for
 * the technician to fix. Dropping the whole queue on a 200 would discard exactly
 * the items a person needs to see.
 *
 * ⚠ **AND THE QUEUE IS NOT EMPTIED BEFORE THE ANSWER ARRIVES.** A phone that
 * cleared its queue optimistically and then lost signal mid-request has thrown
 * away a day's work with nothing to re-send.
 */
export async function syncJobQueue(
  orderId: string,
  client: ApiClient = api,
): Promise<SyncBatchResult | null> {
  const items = await queuedItems(orderId);
  if (items.length === 0) return null;
  // ⚠ **PAGED, NEVER ONE PAYLOAD** (PO 2026-10-04: *"use pagination to send and
  // receive data"*). At most `SYNC_PAGE` items a request, in capture order, so
  // a thousand readings are five pages and a dropped connection costs one page,
  // which is re-sent whole and answered *duplicate* for what already landed.
  let last: SyncBatchResult | null = null;
  const merged: SyncItemResult[] = [];
  for (let start = 0; start < items.length; start += SYNC_PAGE) {
    const page = items.slice(start, start + SYNC_PAGE);
    const result = requireData(
      await client.post<SyncBatchResult>(`/work/mobile/jobs/${orderId}/sync`, {
        items: page.map(wireItem),
      }),
    );
    // TECHNICIAN SYNC DESIGN (1): an item leaves this device ONLY when the
    // server names it in `acknowledged`. A server that predates the list falls
    // back to "everything but refused", which is what it meant then.
    await acknowledge(
      result.acknowledged ?? result.items.filter((r) => r.result !== "refused").map((r) => r.key),
    );
    merged.push(...result.items);
    last = result;
  }
  return last === null ? null : { ...last, items: merged };
}

/** Pages of at most this many items — the server's `sync.MAX_ITEMS`. */
export const SYNC_PAGE = 200;

/**
 * One queued item as the technician API reads it (`technician-api.md` #8).
 * The capture token and the location were stamped AT CAPTURE; nothing here
 * reads who is signed in now (`BR-WRK-059`).
 */
export function wireItem(item: QueuedItem): Record<string, unknown> {
  const wire: Record<string, unknown> = {
    key: item.key,
    kind: item.kind,
    seq: item.seq,
    captured_at: item.capturedAt,
    payload: item.payload,
  };
  if (item.captureToken) wire.capture_token = item.captureToken;
  if (item.location) wire.location = item.location;
  return wire;
}

/** `POST /work/mobile/capture-token` — asked right after sign-in. */
export async function issueCaptureToken(
  body: { device_label?: string } = {},
  client: ApiClient = api,
): Promise<{ capture_token: string; technician: { name: string } | null; max_age_seconds: number }> {
  return requireData(await client.post("/work/mobile/capture-token", body));
}

/**
 * `PUT /work/mobile/photos/{photo_id}` — one photograph's bytes, to the link
 * its data page created. Idempotent on the photo id: a link that already has
 * its bytes answers `duplicate`, and both answers let the bytes go.
 *
 * ⚠ **THE PATH IS BUILT FROM THE PHOTO ID, NOT FROM `upload_url`.** The link IS
 * the photo id (`photo_links._upload_url`), and building the path here keeps
 * the tenant and the API origin the client's business — an absolute
 * `/api/brazosbend/…` from the server would be prefixed a second time.
 */
export async function uploadPhoto(
  photo: PendingPhoto,
  client: ApiClient = api,
): Promise<{ state: string; duplicate?: boolean; attachment_id: string | null }> {
  const form = new FormData();
  form.append("file", photo.blob, `${photo.photoId}.jpg`);
  return requireData(await client.put(`/work/mobile/photos/${photo.photoId}`, form));
}

/**
 * Upload every photograph whose DATA the server has acknowledged.
 *
 * ⚠ **A PHOTO WHOSE DATA ITEM IS STILL QUEUED IS NOT SENT YET** — its link
 * does not exist until the data page is saved (the PO's order: *"link … along
 * with data record and pass it to async job"*), so its upload would be a 404.
 * ⚠ **A FAILED UPLOAD KEEPS THE BYTES.** A hash mismatch (409) is a damaged
 * transfer: the same bytes go again next time. Nothing is dropped until the
 * server says it has them.
 */
export async function uploadPendingPhotos(client: ApiClient = api): Promise<number> {
  const queued = new Set((await queuedItems()).map((i) => i.key));
  let sent = 0;
  for (const photo of await pendingPhotos()) {
    if (queued.has(`photo-${photo.photoId}`)) continue;
    try {
      await uploadPhoto(photo, client);
      await dropPhoto(photo.photoId);
      sent += 1;
    } catch {
      // Kept for the next pass — see the docstring.
    }
  }
  return sent;
}

/** One entry of `GET /work/mobile/changes`. */
export type MobileChange =
  | { change: "upsert"; order_id: string; at: string; job: MobileJobCard }
  | { change: "removed"; order_id: string; at: string };

/**
 * `GET /work/mobile/changes?cursor=` — everything that changed for THIS
 * technician since the cursor, page by page; refresh the bundle of each job
 * given or changed, and forget each job taken away.
 *
 * ⚠ **THE CURSOR IS PER TECHNICIAN** (TECHNICIAN SYNC DESIGN (3)): keyed by the
 * signed-in user, so on a shared tablet Chen's first sync starts from nothing
 * and never inherits where Patel's feed had got to.
 */
export async function syncChanges(client: ApiClient = api): Promise<{ upserts: number; removed: number }> {
  const user = currentUser();
  if (!user) return { upserts: 0, removed: 0 };
  let cursor = await feedCursor(user);
  let upserts = 0;
  let removed = 0;
  for (;;) {
    const page = requireData(
      await client.get<{ changes: MobileChange[]; next_cursor: string | null; has_more: boolean }>(
        "/work/mobile/changes",
        { query: { cursor: cursor ?? undefined, page_size: 50 } },
      ),
    );
    for (const change of page.changes) {
      if (change.change === "removed") {
        await dropJob(change.order_id);
        removed += 1;
      } else {
        try {
          await syncJob(change.order_id, client);
          upserts += 1;
        } catch {
          // One bundle that would not come must not cost the others.
        }
      }
    }
    cursor = page.next_cursor;
    await setFeedCursor(user, cursor);
    if (!page.has_more || page.changes.length === 0) break;
  }
  return { upserts, removed };
}

/**
 * Send everything waiting, one job at a time, and stamp the marker.
 *
 * ⚠ **ONE REQUEST PER JOB, NOT ONE FOR THE DAY** (`07-endpoints.md` #90 is
 * addressed at a job). Three jobs closed offline are three batches, so a job
 * whose close is refused does not hold up the other two — and the response the
 * technician sees is per job, which is how the day is actually thought about.
 *
 * ⚠ **THE MARKER IS STAMPED ONLY IF SOMETHING ACTUALLY REACHED THE SERVER.**
 * `syncToday` states the same rule above and for the same reason: *synced 17:40*
 * has to be true.
 */
export async function syncEverythingQueued(
  client: ApiClient = api,
): Promise<SyncBatchResult[]> {
  const all = await queuedItems();
  const orders = [...new Set(all.map((i) => i.orderId))];
  const results: SyncBatchResult[] = [];
  for (const orderId of orders) {
    try {
      const result = await syncJobQueue(orderId, client);
      if (result !== null) results.push(result);
    } catch {
      // ⚠ ONE JOB'S FAILURE NEVER HOLDS UP ANOTHER'S. Its items stay queued.
    }
  }
  // Then the BYTES, to the links the pages above just created (CR-168 §F).
  const photos = await uploadPendingPhotos(client);
  if (results.length > 0 || photos > 0) await markSynced();
  return results;
}

let flushing: Promise<SyncBatchResult[]> | null = null;

/**
 * Send the outbox now — data pages first, then photographs. One flush at a
 * time: a second call while one runs waits for it rather than sending the
 * same items twice (the server would answer *duplicate*, but a phone on a
 * metered connection should not pay for it).
 */
export function flushOutbox(client: ApiClient = api): Promise<SyncBatchResult[]> {
  if (flushing) return flushing;
  flushing = syncEverythingQueued(client).finally(() => {
    flushing = null;
  });
  return flushing;
}
