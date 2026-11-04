/**
 * What the pull brings besides the change feed (lane INTEGRATE-2, the FF-15
 * and FF-62 holds released when their server routes landed):
 *
 *   THE JOB BUNDLE — `GET work/mobile/jobs/{id}` (`mobile.bundle`). A card
 *   from the feed is not the whole job: its safety lines, tasks, materials and
 *   readings come from the bundle, fetched AT SYNC and never on a tap
 *   (BR-WRK-042). `delta.ts` marks an upserted job `needs_bundle`; this fetches
 *   each one, writes its rows in one transaction and clears the mark. The
 *   server wins on what it sends (R58); the handset's own tick (`state`) is
 *   never overwritten by an update (`woItem.upsert` leaves it).
 *
 *   THE TEMPLATE CATALOGUE — `GET work/mobile/templates` (N8), every page,
 *   into `work_order_templates`, so FF-62 can raise offline (R112).
 *
 * A reading whose prompt has no unit (a text answer) is not a `wo_reading` —
 * that table never holds a figure without its unit (hard rule 3) — and is
 * counted as skipped; no unit is ever invented.
 *
 *   THE JOB'S HELP (DEF-FLD-10581, beta MQ-011: *"Help and SOPs shows 0"*).
 *   The bundle's `help` — `mobile._help_row`'s `{id, seq, kind, label, ref,
 *   url}` — goes into `document` as the job's own rows (`owner_kind
 *   'work_order'`, `kind` document/phone/link/note, `ref` and `url` from 0002).
 *   The server wins: an entry it stops sending leaves the phone with its file.
 *   A document's BYTES come down in the same sync through the file store's
 *   `download` (BR-WRK-038: it opens offline; the link expires in four hours),
 *   inside the 200 MB document budget (`documentQ.DOCUMENT_CAP_BYTES`) — one
 *   that would go over stays listed, says it downloads at next sync, and is
 *   tried again then.
 */
import type { TenantDb } from '../db/database';
import * as customerQ from '../db/queries/customer';
import * as documentQ from '../db/queries/document';
import * as photoQ from '../db/queries/photo';
import * as workOrderQ from '../db/queries/workOrder';
import * as closedQ from '../db/queries/workOrderClosed';
import * as templatesQ from '../db/queries/workOrderTemplates';
import * as woItemQ from '../db/queries/woItem';
import * as woReadingQ from '../db/queries/woReading';
import * as settingsQ from '../db/queries/settings';
import { scoped, type ScopedRunner } from '../db/scoped';
import type { FieldApi, WireBundle, WireHelp } from './fieldApi';
import type { HelpDownloads } from './files';
import type { Clock } from './outbox';
import type { FileStore } from './photos';
import { CANT_READ_KEY } from './routes';
import { failureOf, TransportError, type SyncFailure } from './transport';

export interface BundleSummary {
  fetched: number;
  failed: number;
  /** Readings with no unit: not stored as figures (hard rule 3). */
  readingsSkipped: number;
  /** Help documents whose bytes came down this sync. */
  documentsDownloaded?: number;
  /** Why the last job that failed did (DEF-FLD-10608: FF-08 says it in words). */
  lastFailure?: SyncFailure;
}

/** A file store that may also fetch help documents (`files.ts`). */
export type BundleFiles = Pick<FileStore, 'delete'> & Partial<HelpDownloads>;

/**
 * One bundle onto the handset, in one transaction. Returns the readings
 * skipped for want of a unit. `orphans` collects the phone's copies of help
 * documents the bundle no longer names, for the caller to delete from disk.
 */
export function applyBundle(db: TenantDb, technicianId: string, b: WireBundle, now: Date, orphans: string[] = []): number {
  const s = scoped(db, technicianId);
  const at = now.toISOString();
  let skipped = 0;
  db.transaction(() => {
    for (const row of b.safety ?? []) {
      woItemQ.upsert(
        s,
        {
          id: row.id,
          workOrderId: b.order_id,
          kind: 'safety',
          position: row.seq,
          label: row.text,
          mustDo: row.is_mandatory ?? true,
          state: row.ticked_at ? 'ticked' : null,
        },
        at,
      );
    }
    for (const row of b.tasks ?? []) {
      const minutes = (row as { est_minutes?: unknown }).est_minutes;
      // The template's instruction, verbatim; a blank one stores nothing (DEF-FLD-10587).
      const instruction = typeof row.instruction === 'string' && row.instruction.trim() ? row.instruction : undefined;
      // FB-013 (DEF-FLD-10642) — the step's payment check, kept where FF-27
      // reads it (`freshnessOf`). Dropped here until 2026-10-28, so a money
      // step never warned or stopped on a real phone.
      const fresh = typeof row.money_fresh_minutes === 'number' && row.money_fresh_minutes >= 1 ? row.money_fresh_minutes : undefined;
      const charge = typeof row.money_charge_code === 'string' && row.money_charge_code.trim() ? row.money_charge_code : undefined;
      woItemQ.upsert(
        s,
        {
          id: row.id,
          workOrderId: b.order_id,
          kind: 'task',
          position: row.seq,
          label: row.title,
          mustDo: row.is_mandatory ?? false,
          photoRequired: row.photo_required ?? false,
          photoMinCount: row.photo_required ? 1 : 0,
          state: row.ticked_at ? 'done' : null,
          detail: {
            ...(typeof minutes === 'number' ? { minutes } : {}),
            ...(instruction ? { instruction } : {}),
            ...(fresh ? { money_fresh_minutes: fresh } : {}),
            ...(fresh && charge ? { money_charge_code: charge } : {}),
          },
        },
        at,
      );
    }
    (b.materials ?? []).forEach((row, i) => {
      const planned = row.planned_qty != null ? Number(row.planned_qty) : NaN;
      woItemQ.upsert(
        s,
        {
          id: row.id,
          workOrderId: b.order_id,
          kind: 'material',
          position: i + 1,
          label: row.part_name ?? row.part_no ?? '',
          addedInField: row.unplanned ?? false,
          detail: { code: row.part_no ?? undefined, ...(Number.isFinite(planned) ? { planned } : {}) },
        },
        at,
      );
    });
    for (const row of b.readings ?? []) {
      // DEF-FLD-10585: a TEXT reading (a serial, a seal number) has no unit and is kept.
      const text = row.kind === 'text';
      if (!text && (!row.unit_of_measure || !row.unit_of_measure.trim())) {
        skipped += 1;
        continue;
      }
      woReadingQ.upsert(
        s,
        {
          id: row.id,
          workOrderId: b.order_id,
          position: row.seq,
          prompt: row.prompt,
          unit: row.unit_of_measure ?? '',
          minValue: row.min_value,
          maxValue: row.max_value,
          photoRequired: row.photo_required ?? false,
          kind: text ? 'text' : 'number',
        },
        at,
      );
    }
    applyRecord(s, b, at);
    applyCustomer(db, s, b, at);
    // FB-023 — the job's account, and its copy of the template's "what the
    // technician sees" ticks (F6, F4). Only when the bundle SAYS: an older
    // server sends neither key and the phone keeps what it had.
    if ('account_id' in b) workOrderQ.setAccount(s, b.order_id, b.account_id ?? null);
    if ('details' in b) workOrderQ.setDetails(s, b.order_id, (b.details ?? null) as Record<string, unknown> | null);
    // DEF-MET-10609 — the ONE can't-read list, kept where RW-17 reads it
    // (`CANT_READ_KEY`), so a job's *Unable to read* offers the route
    // reading's reasons. Only when the bundle SAYS what its list is: an older
    // server sends none and the phone keeps what it had.
    if (Array.isArray(b.cant_read_reasons)) {
      settingsQ.set(
        db,
        CANT_READ_KEY,
        b.cant_read_reasons.map((r) => ({ code: r.code, label: r.name })),
        at,
      );
    }
    // The help travels with the job (BR-WRK-038). Only when the bundle SAYS
    // what its help is: a bundle with no `help` key leaves the phone's alone.
    if (Array.isArray(b.help)) {
      for (const row of b.help) {
        const stale = documentQ.upsertHelp(
          db,
          { id: row.id, workOrderId: b.order_id, kind: row.kind, label: row.label, ref: row.ref ?? null, url: helpFetchAddress(row) },
          at,
        );
        if (stale) orphans.push(stale);
      }
      orphans.push(...documentQ.removeHelpNotIn(db, b.order_id, b.help.map((r) => r.id)));
    }
    workOrderQ.markBundled(
      s,
      b.order_id,
      {
        id: b.template_id ?? null,
        version: b.template_version != null ? String(b.template_version) : null,
      },
      // `mobile.bundle` answers where the job stands (DEF-FLD-10579).
      b.technician_acceptance,
    );
  });
  return skipped;
}

/**
 * FB-030 (PO 2026-10-31) — a CLOSED job's record, for a job refilled onto a
 * new phone or closed elsewhere: the captured reading values, the debrief and
 * the signer, and the photographs as rows with no file (loaded on tap, never
 * stored). Everything only where the handset holds nothing — its own close
 * and its own captures win. An open job's bundle (`record: null`) writes none.
 */
function applyRecord(s: ScopedRunner, b: WireBundle, at: string): void {
  const r = b.record;
  if (!r) return;
  for (const row of b.readings ?? []) {
    if (row.value == null && !row.value_text && !row.unable_to_read) continue;
    woReadingQ.fillValueIfEmpty(s, row.id, {
      value: row.kind === 'text' ? null : (row.value ?? null),
      valueText: row.kind === 'text' ? (row.value_text ?? null) : null,
      unableToRead: row.unable_to_read === true,
      capturedAt: row.captured_at ?? null,
    });
  }
  const sig = r.signature;
  closedQ.setRecordIfAbsent(s, b.order_id, {
    problem: r.problem ?? '',
    done: r.done ?? '',
    signer: !sig
      ? null
      : sig.kind === 'refused'
        ? { kind: 'refused', reason: sig.reason ?? '', at: sig.at ?? null }
        : { kind: 'signed', name: sig.name ?? '', at: sig.at ?? null },
  });
  if (r.completed_at) closedQ.fillCloseFromServer(s, b.order_id, r.completed_at, r.outcome ?? null);
  for (const p of r.photos ?? []) {
    photoQ.insertRemote(s, { id: p.photo_id, workOrderId: b.order_id, capturedAt: p.taken_at ?? null, at });
  }
}

/** The bundle's `customer` (`mobile._customer_contact`): who to ring, read live. */
interface WireCustomer {
  name?: string | null;
  phone?: string | null;
  account_no?: string | null;
  customer_no?: string | null;
}

/**
 * DEF-FLD-10582 — the bundle's customer into the customer store, and the job
 * pointed at it, so FF-15 and FF-25 are not *No customer*. Keyed by account
 * number the way the route sync keys one (`acct:<no>`, `routes.ts`), so the
 * same household is one row however it arrived. Server wins: a bundle with no
 * customer clears the job's.
 */
function applyCustomer(db: TenantDb, s: ScopedRunner, b: WireBundle, at: string): void {
  const c = (b as { customer?: WireCustomer | null }).customer ?? null;
  if (!c) {
    workOrderQ.setCustomer(s, b.order_id, null);
    return;
  }
  const id = c.account_no ? `acct:${c.account_no}` : `wo:${b.order_id}`;
  const prev = customerQ.get(db, id);
  customerQ.upsert(
    db,
    {
      id,
      name: c.name ?? null,
      accountNumber: c.account_no ?? null,
      phone: c.phone ?? null,
      email: prev?.email ?? null,
      extra: c.customer_no ? { customer_no: c.customer_no } : null,
    },
    at,
  );
  workOrderQ.setCustomer(s, b.order_id, id);
}

/**
 * Every open job still waiting for its bundle. A job the server no longer
 * gives this technician answers 404 and keeps its mark — the feed's removal
 * takes it off the phone. A refused build or an expired sign-in stops here.
 */
export async function fetchBundles(
  db: TenantDb,
  api: FieldApi,
  technicianId: string,
  opts: { clock: Clock; files?: BundleFiles; summary?: BundleSummary },
): Promise<BundleSummary> {
  const s = scoped(db, technicianId);
  // The caller may hold the tally, so a sign-in that expires half way still
  // leaves it the count of jobs that DID arrive (DEF-FLD-10608).
  const summary: BundleSummary = opts.summary ?? { fetched: 0, failed: 0, readingsSkipped: 0, documentsDownloaded: 0 };
  const tried = new Set<string>();
  const orphans: string[] = [];
  let noSignal = false;
  for (;;) {
    const page = noSignal ? [] : workOrderQ.needingBundle(s, 50 + tried.size).filter((r) => !tried.has(r.id));
    if (page.length === 0) {
      if (opts.files) {
        for (const path of orphans) await opts.files.delete(path);
        // No signal: the documents would only wait out their own time limits.
        if (!noSignal) summary.documentsDownloaded = await downloadHelpDocuments(db, opts.files, { ...opts, api, technicianId });
      }
      return summary;
    }
    for (const { id } of page) {
      tried.add(id);
      try {
        const bundle = await api.jobBundle(id);
        summary.readingsSkipped += applyBundle(db, technicianId, { ...bundle, order_id: bundle.order_id ?? id }, opts.clock.now(), orphans);
        summary.fetched += 1;
      } catch (err) {
        if (err instanceof TransportError && (err.kind === 'auth' || err.kind === 'app_too_old')) throw err;
        summary.failed += 1;
        summary.lastFailure = failureOf(err);
        // No answer at all (no signal, or the time limit): every job still to
        // try would wait 30 s for the same silence (DEF-FLD-10608). Each is
        // counted as not arrived and keeps its mark for the next sync.
        if (err instanceof TransportError && err.kind === 'network' && err.status === undefined) {
          const rest = workOrderQ.needingBundle(s, 100_000).filter((r) => !tried.has(r.id)).length;
          summary.failed += rest;
          noSignal = true;
          break;
        }
      }
    }
  }
}

/**
 * FB-031 (DEF-FLD-10805) — what the phone keeps in `document.url` for a help
 * row: where its bytes come from, or null when there is nothing to fetch.
 *
 *   `has_file: false`  → null: the server holds no file (*No file attached.*).
 *   `content_path`     → our own route, fetched with the credential; it never
 *                        expires. The file's name rides as the fragment
 *                        (`…/content#sop.pdf`) so the copy on the phone keeps
 *                        its extension and the phone's own app knows its type.
 *   otherwise          → the storage link (an older server), as before.
 */
export function helpFetchAddress(row: WireHelp): string | null {
  if (row.kind === 'document' && row.has_file === false) return null;
  if (row.kind === 'document' && row.content_path) {
    return row.file_name ? `${row.content_path}#${encodeURIComponent(row.file_name)}` : row.content_path;
  }
  return row.url ?? null;
}

/** Our own API path (FB-031) rather than a storage host's address. */
export function isOwnPath(url: string): boolean {
  return !/^[a-z][a-z0-9+.-]*:/i.test(url);
}

/** A storage link is good for four hours (`document_store.download_url`). */
export const HELP_LINK_LIFE_MS = 4 * 60 * 60 * 1000;

/** `help/<id>.pdf` — the entry's id, and the extension its file's name (the fragment) or its link's path carries, if any. */
export function helpFileName(id: string, url: string): string {
  const fragment = url.includes('#') ? decodeURIComponent(url.slice(url.indexOf('#') + 1)) : '';
  const path = url.split(/[?#]/)[0] ?? '';
  const extOf = (name: string) => /\.([A-Za-z0-9]{1,8})$/.exec(name.slice(name.lastIndexOf('/') + 1))?.[1];
  const ext = extOf(fragment) ?? extOf(path);
  return `${id.replace(/[^A-Za-z0-9._-]/g, '_')}${ext ? `.${ext.toLowerCase()}` : ''}`;
}

/**
 * Every help document still waiting for its bytes, each fetched into the
 * phone's own store. Within the 200 MB budget: nothing is fetched once the
 * cached documents reach it, and a file that lands over it is deleted again
 * and waits (it is listed, and says so). A failure never stops the sync.
 *
 * FB-031 (DEF-FLD-10805): our own route is fetched with the credential
 * (`api.fileRequest`). A storage link more than four hours old is not tried,
 * and a download refused 401/403/404 is not retried as it stands: either way
 * the job is marked to fetch its BUNDLE again (`needs_bundle`), which carries
 * a fresh address, and the file lands at the next sync. Until 2026-10-31 a
 * failure was swallowed here and only the change feed reset the mark, so an
 * expired link stayed *Downloads at next sync* for ever.
 */
export async function downloadHelpDocuments(
  db: TenantDb,
  files: BundleFiles,
  opts: { clock: Clock; capBytes?: number; api?: Pick<FieldApi, 'fileRequest'>; technicianId?: string },
): Promise<number> {
  if (typeof files.download !== 'function') return 0;
  const cap = opts.capBytes ?? documentQ.DOCUMENT_CAP_BYTES;
  const now = opts.clock.now().getTime();
  const refetch = (orderId: string | null) => {
    if (orderId && opts.technicianId) workOrderQ.markNeedsBundle(scoped(db, opts.technicianId), orderId);
  };
  let n = 0;
  for (const d of documentQ.helpAwaitingDownload(db, 200)) {
    if (!d.url) continue;
    if (documentQ.cachedBytes(db) >= cap) break;
    let landed: { path: string; bytes: number };
    try {
      if (isOwnPath(d.url)) {
        const request = opts.api?.fileRequest?.(d.url.split('#')[0]!);
        if (!request) continue;
        landed = await files.download(request.url, helpFileName(d.id, d.url), request.headers);
      } else {
        if (now - Date.parse(d.updated_at) > HELP_LINK_LIFE_MS) {
          refetch(d.owner_id);
          continue;
        }
        landed = await files.download(d.url, helpFileName(d.id, d.url));
      }
    } catch (err) {
      const status = err instanceof TransportError ? err.status : undefined;
      if (status === 401 || status === 403 || status === 404) refetch(d.owner_id);
      continue;
    }
    if (documentQ.cachedBytes(db) + landed.bytes > cap) {
      await files.delete(landed.path);
      continue;
    }
    documentQ.markDownloaded(db, d.id, landed.path, landed.bytes, opts.clock.now().toISOString());
    n += 1;
  }
  return n;
}

/** The whole published catalogue, every page (NFR-3), into the handset's table. */
export async function downloadTemplates(db: TenantDb, api: FieldApi, opts: { clock: Clock }): Promise<number> {
  let n = 0;
  for (let page = 1; ; page += 1) {
    const answer = await api.templates(page);
    const at = opts.clock.now().toISOString();
    db.transaction(() => {
      for (const t of answer.results) {
        templatesQ.upsert(
          db,
          {
            id: t.id,
            name: t.name,
            version: String(t.version),
            // An object on the wire; a NAME in the table (DEF-FLD-10613).
            service: templatesQ.nameOf(t.service),
            published: true,
            stepCount: t.steps ?? 0,
            safetyCount: t.safety_checks ?? 0,
            readingCount: t.readings ?? 0,
            body: templatesQ.bodyOf(db, t.id),
          },
          at,
        );
      }
    });
    n += answer.results.length;
    if (answer.next === null || answer.next === undefined || answer.results.length === 0) return n;
  }
}
