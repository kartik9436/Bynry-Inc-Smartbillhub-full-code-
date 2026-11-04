/**
 * A fake of `POST /api/<tenant>/work/mobile/reads/sync` — the ROUTE door
 * (`06-backend/apps/metering/field_reads.py sync_reads`) — served as `fetch`,
 * so the handset's REAL `HttpTransport.sendRouteReads` and the REAL mapping
 * both ways (`sync/routeReads.ts`) are what is under test, not a stand-in.
 *
 * Faithful to the server in the ways the arithmetic depends on:
 *   - more than `MAX_ITEMS` (50) in one request is refused WHOLE, 400, before
 *     anything is stored;
 *   - ONE TRANSACTION PER REQUEST (`with transaction.atomic()` around the
 *     whole batch): a request either commits all of its items or none;
 *   - one row per `(tenant, key)` — a key seen before is answered `duplicate`
 *     and stores nothing (the unique constraint);
 *   - BR-WRK-063: an item the pipeline cannot post is STORED and answered
 *     `held_for_review`, never dropped — here, any `kind` but `reading`, or a
 *     `reader_status` outside the server's three (`HELD_UNKNOWN_KIND`,
 *     `HELD_READER_STATUS`);
 *   - `refused` only for an item with no key.
 * And the connection can be killed two ways, because a dropped connection on
 * an atomic door means one of exactly two things to the handset:
 *   - `before`: the request never reached the server — nothing committed;
 *   - `after`:  the server committed the whole batch and the ANSWER was lost.
 */
export const MAX_ITEMS = 50;
const READER_STATUSES = new Set(['read', 'could_not_read', 'read_with_problem']);

export interface StoredRead {
  key: string;
  kind: string;
  route_id: unknown;
  meter_no: unknown;
  premises_id: unknown;
  reader_status: unknown;
  value: unknown;
  unit: unknown;
  cant_read_reason: unknown;
  accepted_anyway: boolean;
  outcome: 'posted' | 'held';
  held_reason: string | null;
  bearer: string;
}

export class FakeReadsDoor {
  /** The server's `field_reads` table, by key. */
  readonly rows = new Map<string, StoredRead>();
  readonly requests: Array<{ size: number; outcome: 'answered' | 'killed-before' | 'killed-after' | 'refused-whole' }> = [];
  duplicatesAnswered = 0;
  /** Request numbers (1-based) to kill, and how. */
  killPlan = new Map<number, 'before' | 'after'>();

  readonly fetch = async (url: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const href = String(url);
    if (!href.endsWith('/work/mobile/reads/sync') || init?.method !== 'POST') {
      return json(404, { message_key: 'not_found' });
    }
    const bearer = String((init.headers as Record<string, string>)?.Authorization ?? '');
    const body = JSON.parse(String(init.body)) as { items?: Array<Record<string, unknown>> };
    const items = body.items ?? [];
    const n = this.requests.length + 1;
    const kill = this.killPlan.get(n);
    if (kill === 'before') {
      this.requests.push({ size: items.length, outcome: 'killed-before' });
      throw new TypeError('Network request failed');
    }
    if (items.length === 0 || items.length > MAX_ITEMS) {
      this.requests.push({ size: items.length, outcome: 'refused-whole' });
      return json(400, { message_key: items.length ? 'work.sync.too_many_items' : 'work.sync.no_items' });
    }
    // ONE transaction: build the batch's rows, then commit them together.
    const staged = new Map<string, StoredRead>();
    const receipts = items.map((raw, i) => {
      const key = typeof raw.key === 'string' ? raw.key : '';
      if (!key) return { position: i + 1, result: 'refused', reason: 'key_missing' };
      if (this.rows.has(key) || staged.has(key)) {
        this.duplicatesAnswered += 1;
        return { key, position: i + 1, result: 'duplicate' };
      }
      const kind = String(raw.kind ?? '');
      const held =
        kind !== 'reading' ? 'unknown_kind' : !READER_STATUSES.has(String(raw.reader_status)) ? 'reader_status_unknown' : null;
      staged.set(key, {
        key,
        kind,
        route_id: raw.route_id,
        meter_no: raw.meter_no,
        premises_id: raw.premises_id,
        reader_status: raw.reader_status,
        value: raw.value ?? null,
        unit: raw.unit ?? null,
        cant_read_reason: raw.cant_read_reason ?? null,
        accepted_anyway: raw.accepted_anyway === true,
        outcome: held ? 'held' : 'posted',
        held_reason: held,
        bearer,
      });
      return held
        ? { key, position: i + 1, result: 'held_for_review', outcome: 'held', reason: held }
        : { key, position: i + 1, result: 'accepted', outcome: 'posted' };
    });
    for (const [k, v] of staged) this.rows.set(k, v); // COMMIT
    if (kill === 'after') {
      this.requests.push({ size: items.length, outcome: 'killed-after' });
      throw new TypeError('Network request failed'); // committed; the answer never arrives
    }
    this.requests.push({ size: items.length, outcome: 'answered' });
    const count = (r: string) => receipts.filter((x) => x.result === r).length;
    return json(200, {
      received: items.length,
      accepted: count('accepted'),
      duplicate: count('duplicate'),
      held_for_review: count('held_for_review'),
      refused: count('refused'),
      server_time: '2026-10-21T17:00:00Z',
      items: receipts,
    });
  };
}

function json(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}
