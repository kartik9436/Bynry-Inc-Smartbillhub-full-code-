/**
 * Route readings on the wire — the handset's outbox item as the server's
 * `POST work/mobile/reads/sync` reads it, and the server's answer as the
 * outbox's receipts read it (`06-backend/apps/metering/field_reads.py`,
 * `sync_reads`; integration lane, when the server door landed).
 *
 * Pure functions: everything the server needs is ON the item (`screens/reads/
 * acts.ts` carries the meter's number and the premises), so sending asks the
 * store nothing.
 *
 *   handset                         server
 *   kind 'route_read'           →   kind 'reading'
 *   kind 'photo' (a declaration)→   kind 'photo' {photo_id, sha256} (DEF-FLD-10357),
 *                                   + reading_key when it was added after the
 *                                   reading was saved (FB-019, DEF-FLD-10637)
 *   kind 'field_asset'          →   kind 'add_meter'
 *   kind 'route_finding'        →   kind 'finding' (BR-WRK-067: Work keeps it;
 *                                   a rule for its kind raises the job at once)
 *   kind 'route_position'       →   kind 'position' {for_key, for_kind,
 *                                   position {lat, lng, accuracy_m, fix_at}}
 *                                   (FB-003, PO 2026-10-27: a fix that arrived
 *                                   within 5 minutes AFTER a reading or route
 *                                   photo was saved without one — its own fact,
 *                                   never written into the reading)
 *   a photo's location          →   its declaration's `position`, with fix_at
 *                                   (FB-003: the shutter's own position)
 *   capture_token               →   capture_token — the CAPTOR (DEF-FLD-10358)
 *   payload.photo_ids           →   photos
 *   payload.meter_no            →   meter_no (the download's key)
 *   payload.premises_id         →   premises_id
 *   payload.no_read_reason      →   cant_read_reason (R82)
 *   payload.warned_accepted     →   accepted_anyway (R80)
 *   location + payload.fix_quality → position {lat, lng, accuracy_m, fix_quality}
 *   captured_at                 →   captured_at (the device clock, R92)
 *   payload.read_format_version_id → read_format_version_id (MQ-033)
 *   payload.answers             →   answers [{question_key, value | photo_id}]
 *                                   (MQ-033, `CR-192-BRC10`: the utility's own
 *                                   questions, inside the reading's own item;
 *                                   a photo answer names a photo in `photos`)
 *
 * The server answers every item with `{key, result, outcome, …}`; a result of
 * accepted, duplicate or held_for_review is a RECEIPT (the reading is kept —
 * held is the office's to look at, never dropped, BR-WRK-063), refused is a
 * refusal the technician sees on FF-50, and an item with no answer stays
 * unsent and is tried again (`receipts.ts`).
 */
import type { BatchAnswer, ItemAnswer, ItemResult, WireItem } from './transport';

const RESULTS: readonly ItemResult[] = ['accepted', 'duplicate', 'refused', 'held_for_review'];

/** The server caps one request at 50 items (`field_reads.MAX_ITEMS`). */
export const ROUTE_READS_MAX_ITEMS = 50;

/** The capture's position, as the reads door's `position` reads it. */
function positionOf(item: WireItem): Record<string, unknown> | null {
  if (!item.location) return null;
  const p = item.payload;
  return {
    lat: item.location.lat,
    lng: item.location.lng,
    accuracy_m: item.location.accuracy_m,
    ...(typeof p.fix_quality === 'string' ? { fix_quality: p.fix_quality } : {}),
  };
}

/**
 * RW-20's meter the system does not know (handset kind `field_asset`) as the
 * reads door's `add_meter` (`field_reads._judge_add_meter`): a PENDING
 * proposal at the premises the reader stands at (R85, R86), with the
 * photographs' ids — the door refuses one with none.
 */
function addMeterFromWire(item: WireItem, routeId: string): Record<string, unknown> {
  const p = item.payload;
  const meter: Record<string, unknown> = {};
  const put = (from: string, to: string) => {
    const v = p[from];
    if (v !== undefined && v !== null && v !== '') meter[to] = v;
  };
  put('service', 'service');
  put('size', 'size_class');
  put('badge', 'badge');
  put('serial', 'serial_no');
  const out: Record<string, unknown> = {
    key: item.key,
    kind: 'add_meter',
    route_id: routeId,
    captured_at: item.captured_at,
    meter,
  };
  if (typeof p.premise_id === 'string' && p.premise_id) out.premises_id = p.premise_id;
  if (Array.isArray(p.photo_ids)) out.photos = p.photo_ids;
  const position = positionOf(item);
  if (position) out.position = position;
  return out;
}

/**
 * A route photograph's DECLARATION (DEF-FLD-10357) as the reads door's `photo`
 * item: its id and the sha256 of the bytes that will follow. The door makes
 * the link and answers `upload_url` (`metering/field_read_photos.py`); the
 * bytes go there, not to the job door. Until this, the declaration went as a
 * `reading` — one bogus held reading per photograph in the office's queue.
 */
function photoFromWire(item: WireItem, routeId: string): Record<string, unknown> {
  const p = item.payload;
  const out: Record<string, unknown> = { key: item.key, kind: 'photo', route_id: routeId, captured_at: item.captured_at, photo_id: p.photo_id, sha256: p.sha256 };
  // FB-019 (DEF-FLD-10637): a photo added after the reading was saved names
  // that reading by the key the door holds it under — its capture key, which
  // is `field_reads.key`. The handset's own `route_read_id` is a local id the
  // server has never seen, so it does not travel.
  if (typeof p.reading_key === 'string' && p.reading_key) out.reading_key = p.reading_key;
  // FB-003: the shutter's position, with the time of its fix.
  const position = fixOf(item);
  if (position) out.position = position;
  return out;
}

/** The item's position WITH the time of its fix — a photograph's, or a late one. */
function fixOf(item: WireItem): Record<string, unknown> | null {
  if (!item.location) return null;
  const { lat, lng, accuracy_m, fix_at } = item.location;
  return { lat, lng, accuracy_m, fix_at };
}

/**
 * FB-003 (PO 2026-10-27): a position that arrived within 5 minutes after a
 * reading or a route photograph was saved without one, as the reads door's
 * `position` item — a separate, time-stamped fact naming the capture key it
 * belongs to (`field_reads._judge_position`).
 */
function positionFromWire(item: WireItem, routeId: string): Record<string, unknown> {
  const p = item.payload;
  const out: Record<string, unknown> = {
    key: item.key,
    kind: 'position',
    route_id: routeId,
    captured_at: item.captured_at,
    for_key: p.for_key,
    for_kind: p.for_kind,
  };
  if (typeof p.photo_id === 'string') out.photo_id = p.photo_id;
  const position = fixOf(item);
  if (position) out.position = position;
  return out;
}

/**
 * RW-21's finding, or RW-18's mismatch (handset kind `route_finding`), as the
 * reads door's `finding` (`field_reads._claim_finding`, BR-WRK-067). RW-18
 * names no kind of its own — what it reports IS a meter that is not the one on
 * the list, so it travels as `meter_mismatch` with its answer. The stop and the
 * meter go as the download named them; the door refuses a finding with
 * neither, back to the reader.
 */
function findingFromWire(item: WireItem, routeId: string): Record<string, unknown> {
  const p = item.payload;
  const mismatch = typeof p.mismatch === 'string' && p.mismatch ? p.mismatch : null;
  const out: Record<string, unknown> = {
    key: item.key,
    kind: 'finding',
    route_id: routeId,
    captured_at: item.captured_at,
    finding: mismatch ? 'meter_mismatch' : p.finding,
  };
  const copy = (from: string, to: string = from) => {
    const v = p[from];
    if (v !== undefined && v !== null && v !== '') out[to] = v;
  };
  copy('urgency');
  copy('remark');
  copy('remark_source');
  copy('premise_id', 'premises_id');
  copy('premises_id');
  copy('asset_id');
  if (mismatch && out.asset_id === undefined) copy('listed_asset_id', 'asset_id');
  copy('meter_no');
  copy('mismatch');
  copy('scanned_code');
  if (Array.isArray(p.photo_ids) && p.photo_ids.length) out.photos = p.photo_ids;
  const position = positionOf(item);
  if (position) out.position = position;
  return out;
}

/** Who captured it travels with it (DEF-FLD-10358, `BR-WRK-059`): the server records the CAPTOR, not the courier. */
function withCaptor(item: WireItem, out: Record<string, unknown>): Record<string, unknown> {
  if (item.capture_token) out.capture_token = item.capture_token;
  return out;
}

export function routeItemFromWire(item: WireItem, routeId: string): Record<string, unknown> {
  if (item.kind === 'field_asset') return withCaptor(item, addMeterFromWire(item, routeId));
  if (item.kind === 'photo') return withCaptor(item, photoFromWire(item, routeId));
  if (item.kind === 'route_finding') return withCaptor(item, findingFromWire(item, routeId));
  if (item.kind === 'route_position') return withCaptor(item, positionFromWire(item, routeId));
  const p = item.payload;
  const out: Record<string, unknown> = {
    key: item.key,
    kind: 'reading',
    route_id: routeId,
    captured_at: item.captured_at,
    reader_status: p.reader_status,
    identified_by: p.identified_by,
  };
  const copy = (from: string, to: string = from) => {
    const v = p[from];
    if (v !== undefined && v !== null && v !== '') out[to] = v;
  };
  copy('meter_no');
  copy('premises_id');
  copy('register');
  copy('value');
  copy('unit');
  copy('no_read_reason', 'cant_read_reason');
  copy('remark');
  copy('remark_source');
  copy('read_method');
  if (p.warned_accepted === true) out.accepted_anyway = true;
  if (Array.isArray(p.photo_ids) && p.photo_ids.length) out.photos = p.photo_ids;
  // MQ-033: a reading on a route with no format carries neither key.
  copy('read_format_version_id');
  if (typeof out.read_format_version_id === 'string' && Array.isArray(p.answers)) out.answers = p.answers;
  const position = positionOf(item);
  if (position) out.position = position;
  return withCaptor(item, out);
}

interface ServerReceipt {
  key?: unknown;
  result?: unknown;
  outcome?: unknown;
  reason?: unknown;
  message_key?: unknown;
  detail?: unknown;
  meter_read_id?: unknown;
  engine?: unknown;
  /** A photo declaration's link (DEF-FLD-10357); a duplicate carries it on `first`. */
  upload_url?: unknown;
  photo_id?: unknown;
  first?: { upload_url?: unknown; photo_id?: unknown } | null;
  /** A finding's own state (BR-WRK-067): open, or the job a rule made. */
  finding?: unknown;
  /** MQ-033 — `{version_id, stored, needs_review, issues, work}`: stored and flagged, never refused. */
  answers?: unknown;
}

export interface ServerReadsAnswer {
  received?: number;
  accepted?: number;
  duplicate?: number;
  held_for_review?: number;
  refused?: number;
  server_time?: string;
  items?: ServerReceipt[];
}

/** The server's answer as the outbox's receipt reads it. An unknown result is no answer. */
export function batchAnswerFromReads(sent: readonly WireItem[], answer: ServerReadsAnswer): BatchAnswer {
  const byKey = new Map(sent.map((i) => [i.key, i]));
  const items: ItemAnswer[] = [];
  const acknowledged: string[] = [];
  for (const r of answer.items ?? []) {
    const key = typeof r.key === 'string' ? r.key : null;
    const result = RESULTS.find((x) => x === r.result) ?? null;
    const mine = key ? byKey.get(key) : undefined;
    if (!key || !result || !mine) continue;
    const detail: Record<string, unknown> = {};
    for (const f of ['outcome', 'reason', 'message_key', 'detail', 'meter_read_id', 'engine', 'upload_url', 'photo_id', 'finding', 'answers'] as const) {
      if (r[f] !== undefined && r[f] !== null) detail[f] = r[f];
    }
    if (detail.upload_url === undefined && r.first && typeof r.first.upload_url === 'string') detail.upload_url = r.first.upload_url;
    items.push({ key, kind: mine.kind, seq: mine.seq, result, ack: result !== 'refused', detail: Object.keys(detail).length ? detail : null });
    if (result !== 'refused') acknowledged.push(key);
  }
  const count = (x: ItemResult) => items.filter((i) => i.result === x).length;
  return {
    accepted: count('accepted'),
    duplicate: count('duplicate'),
    refused: count('refused'),
    held_for_review: count('held_for_review'),
    acknowledged,
    items,
    synced_at: answer.server_time,
  };
}
