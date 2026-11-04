// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-040 (the shell: installable, offline-first) TC-1/TC-4 ·
//           US-WRK-041 (the offline marker) TC-3/TC-4 · US-WRK-042 (nothing on
//           the screen was fetched — it was carried) TC-1/TC-2/TC-4
// Rules:    BR-WRK-036 (the marker is always visible, with the time the phone
//           last reached the server) · BR-WRK-042 (the bundle is fetched at
//           sync, never on tap) · BR-WRK-045 (the phone is a web app —
//           installable, offline-first)
// Tests:    src/features/work/mobile/offlineStore.test.ts
// ───────────────────────────────────────────────────────

/**
 * The phone's own store — IndexedDB, and the reason it is not `localStorage`.
 *
 * A day's bundles carry seven tasks, three readings, three parts, a help pack
 * and an SOP each. `localStorage` is synchronous (it blocks the main thread on
 * every read, on a phone, in a meter pit), string-only (so a PDF becomes
 * base64 and grows by a third), and capped around 5 MB per origin. IndexedDB
 * is asynchronous, stores `Blob`s as bytes, and is the only store a service
 * worker can also reach — which matters because the SOP has to open when the
 * page was loaded from cache.
 *
 * ⚠ **THE MARKER IS COMPUTED HERE AND CANNOT BE COMPUTED ON THE SERVER.**
 * `BR-WRK-036` asks for *◍ offline · synced 08:12* — the time the PHONE last
 * reached the server. Ask the server and the only answer it can give is *now*,
 * which is precisely the lie the rule exists to prevent: a marker that always
 * reads *just synced* because the thing rendering it is the thing being asked.
 * `US-WRK-041` TC-4 is the case that proves it — a phone that has NEVER synced
 * must read *never synced*, and no server response can say that.
 *
 * ⚠ **EVERY READ AND WRITE IS WRAPPED.** A phone in private browsing, with site
 * data blocked, or out of quota throws on `indexedDB.open` itself. A field app
 * that white-screens because storage was unavailable is worse than one that
 * works online only, so every path here degrades to *no store* and the marker
 * tells the truth about it.
 */

const DB_NAME = "sbh-work-mobile";
// ⚠ **BUMPED TO 2 BY CR-070 WAVE L, AND THE UPGRADE MUST BE ADDITIVE.** A
// technician's phone is upgraded by opening the app — often standing in a meter
// pit with a day's captured work in `queue` and no signal to re-send it. So
// `onupgradeneeded` only ever CREATES missing stores; it never deletes or
// rebuilds one, and a version bump that dropped a store would throw away the
// exact work this store exists to protect.
//
// ⚠ **3 SINCE CR-168-BRC10 §F (lane FIELD-2)** — one more store, `photos`, the
// bytes of a photograph waiting for its link. Additive, as above.
const DB_VERSION = 3;

/** The day's job cards, keyed by the technician's day. */
const STORE_DAY = "day";
/** One job bundle per order id — everything `Work-011` draws. */
const STORE_JOBS = "jobs";
/** Help documents as bytes. The pre-signed link dies in four hours; these do not. */
const STORE_FILES = "files";
/** One row: when the phone last reached the server. */
const STORE_META = "meta";

/**
 * ⚠ **THE QUEUE — CR-070 wave L, `US-WRK-044`, `BR-WRK-042`.** One record per
 * captured act, keyed by the idempotency key the handset minted AT CAPTURE.
 *
 * **The key is minted here and not on the server, and it has to be**: the
 * server has no way to tell a retry of this morning's safety tick from a
 * genuinely new one on the same row. It is what makes *everything lands once*
 * and *nothing is lost* the same promise instead of opposite ones.
 */
const STORE_QUEUE = "queue";

/**
 * ⚠ **CR-168-BRC10 §F — THE PHOTOGRAPHS' BYTES, APART FROM THE DATA.** The PO:
 * *"link you ahve to create along with data record and pass it to async job"*.
 * The DATA (a `photo` item: its id, its hash, its task or reading) travels in
 * the queue with everything else and the server answers its link; the BYTES
 * wait here and are uploaded to that link in the background. A photo leaves
 * this store only when the server has its bytes (`BR-WRK-062`).
 */
const STORE_PHOTOS = "photos";

const META_LAST_SYNC = "lastSyncAt";
/** Whose login is in front of the phone now (`BR-WRK-059`). */
const META_ACTIVE_USER = "activeUser";

/**
 * One act, waiting to be sent.
 *
 * ⚠ **`capturedAt` IS THE MOMENT THE TECHNICIAN DID THE THING, NOT THE MOMENT
 * IT IS SENT, AND CONFLATING THEM WOULD BE A LIE ON A BILLING PATH.** A close
 * captured at 16:07 that reaches the server at 17:40 dates its meter read to
 * 16:07 — `BR-WRK-003` and `BR-TEN-043`. The server reads this field and
 * refuses a time in the future; it does not invent one.
 */
export type QueuedItem = {
  /** Minted at capture, on this handset. The server's idempotency key. */
  readonly key: string;
  readonly orderId: string;
  readonly kind:
    | "safety_tick"
    | "task_tick"
    | "reading"
    | "material"
    | "attachment"
    | "photo"
    | "signature"
    | "close";
  /** The phone's own position in this job's queue — recorded, never trusted. */
  readonly seq: number;
  readonly capturedAt: string;
  readonly payload: Record<string, unknown>;
  /**
   * ⚠ **CR-168-BRC10 §F — WHO CAPTURED IT, STAMPED AT CAPTURE AND NEVER AT
   * SEND** (`BR-WRK-059`/`060`). The signed token the server issued to the
   * technician signed in when this was done. A shared tablet sends it under
   * whoever is signed in later, and the server writes it as THIS technician.
   * Absent only when the phone has never reached the server since sign-in.
   */
  readonly captureToken?: string | null;
  /** The captor's user id — so the next login never sees this item's job. */
  readonly owner?: string | null;
  /** The best fix in hand at capture (`BR-WRK-061`), or none. */
  readonly location?: LocationFix | null;
};

/** `BR-WRK-061`'s four fields, exactly as the wire carries them. */
export type LocationFix = {
  lat: number;
  lng: number;
  accuracy_m: number;
  fix_at: string;
};

/** One photograph's bytes, waiting for (or uploading to) its link. */
export type PendingPhoto = {
  /** The phone's own uuid — the link's name on the server. */
  readonly photoId: string;
  readonly orderId: string;
  readonly owner: string | null;
  /** Hex sha256 of `blob`, declared in the data page; the server checks it. */
  readonly sha256: string;
  readonly blob: Blob;
  /** The task or reading it was taken for, or neither (a job photograph). */
  readonly taskId?: string | null;
  readonly readingId?: string | null;
  readonly takenAt: string;
};

export type SyncMarker = {
  /** True when the browser reports no connection. */
  offline: boolean;
  /** ISO timestamp of the last successful sync, or null when there has been none. */
  lastSyncAt: string | null;
  /**
   * ⚠ **JOBS WITH A QUEUED CLOSE, NOT ITEMS** (`US-WRK-044` TC-7). The marker
   * reads *3 jobs to send*, and a technician who ticked four safety rows on a
   * job they have not finished is not waiting to send anything — they are
   * mid-job. Counting items would read *17 to send* over one unfinished job.
   */
  jobsToSend: number;
  /**
   * EVERY captured item not yet ACKNOWLEDGED by the server (TECHNICIAN SYNC
   * DESIGN (6), PO 2026-10-04: *"we cant drop data record"*) — *N waiting to
   * send*. An item leaves the device only on its acknowledgement.
   */
  itemsWaiting?: number;
};

let dbPromise: Promise<IDBDatabase | null> | null = null;

function open(): Promise<IDBDatabase | null> {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve) => {
    try {
      if (typeof indexedDB === "undefined") {
        resolve(null);
        return;
      }
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        for (const name of [STORE_DAY, STORE_JOBS, STORE_FILES, STORE_META, STORE_QUEUE, STORE_PHOTOS]) {
          if (!db.objectStoreNames.contains(name)) db.createObjectStore(name);
        }
      };
      request.onsuccess = () => resolve(request.result);
      // Not a throw: a phone with site data blocked gets `null` and the app
      // runs online-only with an honest marker.
      request.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
  return dbPromise;
}

async function put(store: string, key: string, value: unknown): Promise<void> {
  const db = await open();
  if (!db) return;
  await new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(store, "readwrite");
      tx.objectStore(store).put(value, key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
      tx.onabort = () => resolve();
    } catch {
      resolve();
    }
  });
}

async function get<T>(store: string, key: string): Promise<T | null> {
  const db = await open();
  if (!db) return null;
  return new Promise<T | null>((resolve) => {
    try {
      const request = db.transaction(store, "readonly").objectStore(store).get(key);
      request.onsuccess = () => resolve((request.result as T) ?? null);
      request.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

// ── WHOSE PHONE IT IS RIGHT NOW (CR-168-BRC10 §F, `BR-WRK-059`/`060`) ──────
//
// ⚠ **THE DAY AND THE BUNDLES ARE KEPT PER LOGIN.** One tablet, several
// technicians in turn: M. Chen signing in after R. Patel must see none of
// Patel's jobs — not from the server (the server scopes every route) and not
// from THIS store either, which is the half only the phone can get wrong. So
// every day and bundle key carries the signed-in user, and a sign-out forgets
// who is signed in without deleting a byte: Patel's unsent work is still in
// the queue, still his, and goes on uploading under his capture token.

let activeUser: string | null = null;

/** The user whose day and jobs this phone is showing, or `null`. */
export function currentUser(): string | null {
  return activeUser;
}

/** Called once the session is known (sign-in, or the app opening online). */
export async function setActiveUser(userId: string | null, captureToken?: string | null): Promise<void> {
  activeUser = userId;
  await put(STORE_META, META_ACTIVE_USER, userId);
  if (userId && captureToken) await put(STORE_META, `captureToken:${userId}`, captureToken);
  notify();
}

/** At app start with no signal: the last login this phone saw. */
export async function restoreActiveUser(): Promise<string | null> {
  if (activeUser === null) activeUser = await get<string>(STORE_META, META_ACTIVE_USER);
  return activeUser;
}

/** Sign-out: forget WHO, keep everything they captured (`BR-WRK-060`). */
export async function forgetActiveUser(): Promise<void> {
  activeUser = null;
  await put(STORE_META, META_ACTIVE_USER, null);
  notify();
}

/** The signed-in technician's capture token, stamped on every new item. */
export async function captureToken(userId: string | null = activeUser): Promise<string | null> {
  return userId ? get<string>(STORE_META, `captureToken:${userId}`) : null;
}

function mine(key: string): string {
  return `${activeUser ?? "-"}|${key}`;
}

/** The day's cards, as they were at the last sync. */
export async function readDay(key: string): Promise<unknown | null> {
  return get(STORE_DAY, mine(key));
}

export async function writeDay(key: string, day: unknown): Promise<void> {
  await put(STORE_DAY, mine(key), day);
}

/**
 * One job's bundle.
 *
 * ⚠ **THIS IS WHAT MAKES `US-WRK-042` TC-1 POSSIBLE** — *"zero network requests
 * during the tap"*. The bundle was written at sync; opening a job READS and
 * never fetches. A screen that falls back to the network on a miss would pass
 * every test with a signal and fail the only case that matters.
 */
export async function readJob(orderId: string): Promise<unknown | null> {
  return get(STORE_JOBS, mine(orderId));
}

export async function writeJob(orderId: string, bundle: unknown): Promise<void> {
  await put(STORE_JOBS, mine(orderId), bundle);
  notify();
}

/** A job the change feed says was taken away from this technician. */
export async function dropJob(orderId: string): Promise<void> {
  await drop(STORE_JOBS, mine(orderId));
  notify();
}

/** A help document's bytes, fetched at sync from its pre-signed link. */
export async function readFile(ref: string): Promise<Blob | null> {
  return get<Blob>(STORE_FILES, ref);
}

export async function writeFile(ref: string, bytes: Blob): Promise<void> {
  await put(STORE_FILES, ref, bytes);
}

/**
 * Stamp a successful sync. Called ONLY after a response actually arrived —
 * `BR-WRK-036`'s whole value is that the time is true.
 */
export async function markSynced(at: Date = new Date()): Promise<void> {
  await put(STORE_META, META_LAST_SYNC, at.toISOString());
  notify();
}

/**
 * The marker `Work-010` renders — *◍ offline · synced 08:12* or
 * *◍ offline · never synced*.
 *
 * ⚠ **`null` MEANS NEVER, AND THE SCREEN MUST NOT RENDER A TIME FOR IT**
 * (`US-WRK-041` TC-4). The tempting default — "no stored value, so use now" —
 * produces a phone that has never reached the server claiming it synced this
 * minute, which is the one thing this marker exists to make impossible.
 */
export async function syncMarker(): Promise<SyncMarker> {
  const lastSyncAt = await get<string>(STORE_META, META_LAST_SYNC);
  const waiting = await queuedItems();
  // ⚠ **THE DEVICE'S COUNT, NOT THE LOGIN'S** (CR-168-BRC10 §F, FIELD-2).
  // *"The phone always shows N waiting to send"* — the outbox belongs to the
  // TABLET, and Patel's three unsent items are still waiting while Chen is
  // signed in. A number names no job, no customer and no technician, so Chen
  // seeing *3 waiting to send* shows him nothing of Patel's; hiding it would
  // make the one gap the design exists to keep visible silent.
  //
  // A photograph counts once: as its DATA while that is queued, then as its
  // BYTES until they have been uploaded to the link.
  const queuedKeys = new Set(waiting.map((i) => i.key));
  const bytesOnly = (await pendingPhotos()).filter((p) => !queuedKeys.has(photoItemKey(p.photoId)));
  return {
    offline: typeof navigator !== "undefined" && navigator.onLine === false,
    lastSyncAt: lastSyncAt ?? null,
    jobsToSend: new Set(waiting.filter((i) => i.kind === "close").map((i) => i.orderId)).size,
    itemsWaiting: waiting.length + bytesOnly.length,
  };
}

// ── CHANGE NOTICES — so the marker re-reads itself when the outbox moves ──
const listeners = new Set<() => void>();

/** Subscribe to "something in the store changed"; returns the unsubscribe. */
export function onStoreChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify(): void {
  for (const listener of listeners) {
    try {
      listener();
    } catch {
      // A screen that has gone away is not the store's problem.
    }
  }
}

// ══════════════════════════════════════════════════════════════════════════
// CR-070 wave L — the queue: what has been done and not yet sent
// ══════════════════════════════════════════════════════════════════════════

async function all<T>(store: string): Promise<T[]> {
  const db = await open();
  if (!db) return [];
  return new Promise<T[]>((resolve) => {
    try {
      const request = db.transaction(store, "readonly").objectStore(store).getAll();
      request.onsuccess = () => resolve((request.result as T[]) ?? []);
      request.onerror = () => resolve([]);
    } catch {
      resolve([]);
    }
  });
}

async function drop(store: string, key: string): Promise<void> {
  const db = await open();
  if (!db) return;
  await new Promise<void>((resolve) => {
    try {
      const tx = db.transaction(store, "readwrite");
      tx.objectStore(store).delete(key);
      tx.oncomplete = () => resolve();
      tx.onerror = () => resolve();
      tx.onabort = () => resolve();
    } catch {
      resolve();
    }
  });
}

/**
 * Add one captured act to the queue.
 *
 * ⚠ **IDEMPOTENT ON THE KEY, AND THAT IS `US-WRK-045` TC-5 ON THE PHONE.**
 * Tapping *Close job* twice queues ONE item, because the second `put` writes to
 * the same key. Without it a double tap on a laggy screen becomes two closes,
 * and only the server's receipts table would catch it — after a round trip the
 * technician does not have.
 */
export async function enqueue(item: QueuedItem): Promise<void> {
  await put(STORE_QUEUE, item.key, item);
  notify();
}

/** Everything waiting, in CAPTURE order — the order the server applies. */
export async function queuedItems(orderId?: string): Promise<QueuedItem[]> {
  const rows = await all<QueuedItem>(STORE_QUEUE);
  const mine = orderId === undefined ? rows : rows.filter((r) => r.orderId === orderId);
  // ⚠ **SORTED BY `seq` AND THEN BY `capturedAt`, AND NEVER BY KIND.** The
  // server refuses a close that arrives before the safety row it is gated on
  // (`BR-WRK-037`) — deliberately, so a tampered client cannot be repaired by
  // helpfulness — so the phone's job is to preserve the order things happened
  // in, not to arrange them into an order the server will like.
  return mine.sort((a, b) => a.seq - b.seq || a.capturedAt.localeCompare(b.capturedAt));
}

/** The jobs with a queued CLOSE — what the marker counts. */
export async function jobsWaitingToSend(): Promise<string[]> {
  const rows = await queuedItems();
  return [...new Set(rows.filter((r) => r.kind === "close").map((r) => r.orderId))];
}

/**
 * Forget the items the server has acknowledged.
 *
 * ⚠ **ACCEPTED *AND* DUPLICATE ARE BOTH ACKNOWLEDGEMENTS, AND ONLY REFUSED IS
 * NOT** (`US-WRK-044` TC-4/TC-10). *Duplicate* means the server already has it
 * — keeping it would re-send it forever. *Refused* means it did not happen, so
 * it stays queued for the technician to fix and re-send. Dropping the whole
 * queue on a response would silently discard the refusals, which is the one
 * case a technician has to see.
 */
export async function acknowledge(keys: readonly string[]): Promise<void> {
  for (const key of keys) await drop(STORE_QUEUE, key);
  notify();
}

// ══════════════════════════════════════════════════════════════════════════
// CR-168-BRC10 §F — photographs' bytes, the job's best fix, the feed cursor
// ══════════════════════════════════════════════════════════════════════════

/** The queue key of a photograph's DATA item — one spelling, here. */
export function photoItemKey(photoId: string): string {
  return `photo-${photoId}`;
}

export async function putPhoto(photo: PendingPhoto): Promise<void> {
  await put(STORE_PHOTOS, photo.photoId, photo);
  notify();
}

/** Every photograph whose bytes the server does not have yet. */
export async function pendingPhotos(): Promise<PendingPhoto[]> {
  return all<PendingPhoto>(STORE_PHOTOS);
}

/** The server has these bytes (or already had them): let them go. */
export async function dropPhoto(photoId: string): Promise<void> {
  await drop(STORE_PHOTOS, photoId);
  notify();
}

/**
 * A photograph taken on this phone for a task or reading of this job, by
 * row id — so *Photo taken* stays true between the capture and the server's
 * bundle catching up (the link is pending there, never missing).
 */
export async function declaredPhotos(orderId: string): Promise<Record<string, string>> {
  return (await get<Record<string, string>>(STORE_META, mine(`declared:${orderId}`))) ?? {};
}

export async function declarePhoto(orderId: string, rowId: string, photoId: string): Promise<void> {
  const current = await declaredPhotos(orderId);
  await put(STORE_META, mine(`declared:${orderId}`), { ...current, [rowId]: photoId });
}

export async function readFix(orderId: string): Promise<LocationFix | null> {
  return get<LocationFix>(STORE_META, `fix:${orderId}`);
}

export async function writeFix(orderId: string, fix: LocationFix): Promise<void> {
  await put(STORE_META, `fix:${orderId}`, fix);
}

/**
 * `DEF-WRK-4127` — when THIS technician first opened this job on this phone,
 * by the phone's own clock. It is what the close pre-fills as *Arrived* (PO
 * 2026-10-05: *"allow technicain to fill in time"*); the technician corrects
 * it there. Written once — reopening the job does not move it — and kept per
 * login, like every other key a shared tablet holds.
 */
export async function markOnSite(orderId: string, at: Date = new Date()): Promise<void> {
  if ((await onSiteSince(orderId)) !== null) return;
  await put(STORE_META, mine(`onSite:${orderId}`), at.toISOString());
}

export async function onSiteSince(orderId: string): Promise<string | null> {
  return get<string>(STORE_META, mine(`onSite:${orderId}`));
}

/** The change feed's cursor — PER TECHNICIAN, so a shared tablet never mixes logins. */
export async function feedCursor(userId: string): Promise<string | null> {
  return get<string>(STORE_META, `feedCursor:${userId}`);
}

export async function setFeedCursor(userId: string, cursor: string | null): Promise<void> {
  await put(STORE_META, `feedCursor:${userId}`, cursor);
}

/** The next `seq` for a job — one past the highest already queued for it. */
export async function nextSeq(orderId: string): Promise<number> {
  const rows = await queuedItems(orderId);
  return rows.reduce((max, r) => Math.max(max, r.seq), 0) + 1;
}

/** Test seam: forget the open handle so a fresh fake IndexedDB can be used. */
export function resetForTests(): void {
  dbPromise = null;
  activeUser = null;
  listeners.clear();
}
