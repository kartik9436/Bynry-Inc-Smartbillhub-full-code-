// ── Trace ──────────────────────────────────────────────
// Change:   CR-168-BRC10 §F — lane FIELD-2: the field app on the technician API.
// Rules:    BR-WRK-059 · 060 · 061 · 062 · 063 · 042
// ───────────────────────────────────────────────────────
//
// The store is an IN-MEMORY stand-in with the real module's semantics (jsdom has
// no IndexedDB); the API client is a fake that answers like the server. What is
// proved is this lane's own logic: what an item carries, who it belongs to, and
// that it leaves the phone only on ITS acknowledgement.
import { beforeEach, describe, expect, it, vi } from "vitest";

type Item = { key: string; orderId: string; kind: string; seq: number; capturedAt: string; payload: Record<string, unknown>; captureToken?: string | null; owner?: string | null; location?: unknown };
type Photo = { photoId: string; orderId: string; sha256: string; blob: Blob; taskId?: string | null };

const store = {
  queue: new Map<string, Item>(),
  photos: new Map<string, Photo>(),
  tokens: new Map<string, string>(),
  declared: new Map<string, Record<string, string>>(),
  user: null as string | null,
  synced: 0,
};

vi.mock("./offlineStore", () => ({
  enqueue: vi.fn(async (item: Item) => void store.queue.set(item.key, item)),
  queuedItems: vi.fn(async (orderId?: string) =>
    [...store.queue.values()]
      .filter((i) => orderId === undefined || i.orderId === orderId)
      .sort((a, b) => a.seq - b.seq),
  ),
  acknowledge: vi.fn(async (keys: string[]) => keys.forEach((k) => store.queue.delete(k))),
  nextSeq: vi.fn(async (orderId: string) => [...store.queue.values()].filter((i) => i.orderId === orderId).length + 1),
  captureToken: vi.fn(async () => (store.user ? store.tokens.get(store.user) ?? null : null)),
  currentUser: vi.fn(() => store.user),
  putPhoto: vi.fn(async (p: Photo) => void store.photos.set(p.photoId, p)),
  pendingPhotos: vi.fn(async () => [...store.photos.values()]),
  dropPhoto: vi.fn(async (id: string) => void store.photos.delete(id)),
  declarePhoto: vi.fn(async (orderId: string, rowId: string, photoId: string) =>
    void store.declared.set(orderId, { ...(store.declared.get(orderId) ?? {}), [rowId]: photoId }),
  ),
  photoItemKey: (id: string) => `photo-${id}`,
  markSynced: vi.fn(async () => void (store.synced += 1)),
  feedCursor: vi.fn(async () => null),
  setFeedCursor: vi.fn(async () => undefined),
  dropJob: vi.fn(async () => undefined),
  readDay: vi.fn(async () => null),
  writeDay: vi.fn(async () => undefined),
  readJob: vi.fn(async () => null),
  writeJob: vi.fn(async () => undefined),
  readFix: vi.fn(async () => ({ lat: 29.5601, lng: -95.8072, accuracy_m: 8, fix_at: "2026-10-04T15:00:00.000Z" })),
  writeFix: vi.fn(async () => undefined),
}));

vi.mock("./compressPhoto", () => ({
  compressPhoto: vi.fn(async (file: Blob) => file),
  PhotoTooLarge: class extends Error {},
}));

const posts: { path: string; body: { items: Record<string, unknown>[] } }[] = [];
const puts: string[] = [];
let ackOnly: ((key: string) => boolean) | null = null;
let failPhotoUpload = false;

vi.mock("@/api/client", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/api/client")>();
  const fake = {
    get: vi.fn(),
    post: vi.fn(async (path: string, body: { items: Record<string, unknown>[] }) => {
      posts.push({ path, body });
      const acked = body.items.map((i) => String(i.key)).filter((k) => (ackOnly ? ackOnly(k) : true));
      return {
        status: 200,
        data: {
          work_order_id: "o1",
          accepted: acked.length,
          duplicate: 0,
          refused: body.items.length - acked.length,
          acknowledged: acked,
          items: body.items.map((i) => ({
            key: i.key,
            kind: i.kind,
            seq: i.seq,
            result: acked.includes(String(i.key)) ? "accepted" : "refused",
            detail: i.kind === "photo" ? { upload_url: `/api/x/work/mobile/photos/${(i.payload as { photo_id: string }).photo_id}`, state: "pending" } : null,
          })),
          synced_at: "",
        },
      };
    }),
    put: vi.fn(async (path: string) => {
      puts.push(path);
      if (failPhotoUpload) throw new Error("409 work.photo.hash_mismatch");
      return { status: 200, data: { state: "landed", attachment_id: "a1", duplicate: false } };
    }),
    del: vi.fn(),
    patch: vi.fn(),
  };
  return { ...real, api: fake };
});

import { capture, capturePhoto, sha256Hex } from "./capture";
import { flushOutbox, SYNC_PAGE, wireItem } from "./mobileEndpoints";

function online(on: boolean) {
  Object.defineProperty(navigator, "onLine", { configurable: true, get: () => on });
}

beforeEach(() => {
  store.queue.clear();
  store.photos.clear();
  store.declared.clear();
  store.tokens.clear();
  store.user = null;
  store.synced = 0;
  posts.length = 0;
  puts.length = 0;
  ackOnly = null;
  failPhotoUpload = false;
  online(true);
});

describe("BR-WRK-059/060 — an item is its captor's, whoever is signed in when it is sent", () => {
  it("Patel's offline close carries HIS token and fix; sent while Chen is signed in, it still does", async () => {
    store.tokens.set("patel", "TOKEN-PATEL");
    store.tokens.set("chen", "TOKEN-CHEN");
    store.user = "patel";
    online(false);
    const { item, sent } = await capture({ orderId: "o1", kind: "close", key: "close-o1", payload: { outcome: "passed" } });
    expect(sent).toBeNull(); // offline: nothing attempted
    expect(item.captureToken).toBe("TOKEN-PATEL");
    expect(item.owner).toBe("patel");
    expect(item.location).toEqual({ lat: 29.5601, lng: -95.8072, accuracy_m: 8, fix_at: "2026-10-04T15:00:00.000Z" });

    // Patel signs out, Chen signs in, the signal comes back.
    store.user = "chen";
    online(true);
    await flushOutbox();
    expect(posts).toHaveLength(1);
    const wire = posts[0].body.items[0];
    expect(wire.capture_token).toBe("TOKEN-PATEL");
    expect(wire.location).toMatchObject({ accuracy_m: 8 });
    expect(store.queue.size).toBe(0);
  });
});

describe("BR-WRK-063 — an item leaves the phone only on ITS acknowledgement", () => {
  it("of two items, the one the server did not acknowledge stays", async () => {
    store.user = "patel";
    online(false);
    await capture({ orderId: "o1", kind: "safety_tick", key: "safety_tick-s1", payload: { safety_id: "s1" } });
    await capture({ orderId: "o1", kind: "task_tick", key: "task_tick-t1", payload: { task_id: "t1" } });
    online(true);
    ackOnly = (key) => key === "safety_tick-s1";
    await flushOutbox();
    expect([...store.queue.keys()]).toEqual(["task_tick-t1"]);
  });

  it("pages of at most 200 — 450 items are three requests, in capture order", async () => {
    store.user = "patel";
    online(false);
    for (let n = 0; n < 450; n += 1) {
      await capture({ orderId: "o1", kind: "reading", key: `r-${String(n).padStart(3, "0")}`, payload: { reading_id: "x", value: String(n), unit: "kWh" } });
    }
    online(true);
    await flushOutbox();
    expect(SYNC_PAGE).toBe(200);
    expect(posts.map((p) => p.body.items.length)).toEqual([200, 200, 50]);
    expect(posts[0].body.items[0].key).toBe("r-000");
    expect(store.queue.size).toBe(0);
  });
});

describe("BR-WRK-062 — the photo's link is made with its record; the bytes follow", () => {
  it("offline: the DATA is queued with its hash and task, the bytes kept; online: page first, then the upload", async () => {
    store.user = "patel";
    online(false);
    const blob = new Blob([new Uint8Array([1, 2, 3, 4])], { type: "image/jpeg" });
    const { photoId } = await capturePhoto({ orderId: "o1", file: blob, taskId: "t1" });
    const item = store.queue.get(`photo-${photoId}`)!;
    expect(item.kind).toBe("photo");
    expect(item.payload).toEqual({ photo_id: photoId, sha256: await sha256Hex(blob), task_id: "t1" });
    expect(store.photos.has(photoId)).toBe(true);
    expect(store.declared.get("o1")).toEqual({ t1: photoId });
    expect(puts).toEqual([]);

    online(true);
    await flushOutbox();
    expect(posts).toHaveLength(1);
    expect(puts).toEqual([`/work/mobile/photos/${photoId}`]);
    expect(store.photos.has(photoId)).toBe(false);
  });

  it("a failed upload keeps the bytes for the next pass — never dropped", async () => {
    store.user = "patel";
    const blob = new Blob([new Uint8Array([9, 9])], { type: "image/jpeg" });
    online(false);
    const { photoId } = await capturePhoto({ orderId: "o1", file: blob });
    online(true);
    failPhotoUpload = true;
    await flushOutbox();
    expect(store.photos.has(photoId)).toBe(true);
    failPhotoUpload = false;
    await flushOutbox();
    expect(store.photos.has(photoId)).toBe(false);
  });

  it("the sha256 is the hex digest of the bytes", async () => {
    const digest = await sha256Hex(new Blob([new TextEncoder().encode("abc")]));
    expect(digest).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });
});

describe("wireItem — what the technician API reads", () => {
  it("omits a token and a location the item never had", () => {
    expect(wireItem({ key: "k", orderId: "o", kind: "close", seq: 1, capturedAt: "t", payload: {} })).toEqual({
      key: "k",
      kind: "close",
      seq: 1,
      captured_at: "t",
      payload: {},
    });
  });
});
