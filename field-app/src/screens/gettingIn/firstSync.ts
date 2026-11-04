/**
 * FF-08 *Loading your day* — the first sync after signing in, as a port.
 *
 * The board draws five parts, each with its own progress: *Your shift and
 * route · Safety documents · Jobs and checklists · Asset history · Customer
 * details*, one combined percentage, and *Open my day* waiting for 100%
 * (US-FLD-002 TC-1).
 *
 * ⚠ ONLY ONE OF THE FIVE HAS A FEED TODAY. The sync engine pulls the job
 * change feed (`sync/delta.ts`, `GET work/mobile/changes`); the shift and
 * route, documents, asset history and customer details have no change feed
 * on the server (decision log 2026-10-21, *"non-job change feeds"* not
 * built). A part with no feed is reported `unavailable`, and the percentage
 * is taken over the parts that CAN load — otherwise the bar could never
 * reach 100% and *Open my day* would be a dead button. Both facts are on
 * screen: the unavailable parts say so on their own row.
 *
 * ⚠ JOBS FAILS ONLY WHEN THE JOB LIST FAILS (DEF-FLD-10608, decision log
 * 2026-10-26 FA-10). The row follows the engine's three steps separately:
 *   - the change feed (the LIST) failed → *Did not load*, with the reason in
 *     words, and Retry runs the whole sync again;
 *   - the list arrived → the row is DONE and counts the jobs whose details
 *     arrived of the jobs listed (*10 of 11*). A job whose details did not
 *     arrive is a WARNING, not a block: the part has SETTLED, so it counts
 *     whole in the percentage and the day can reach 100% and open. The
 *     shortfall is said beside it (the count, the reason, *Some jobs are not
 *     on the phone.* by Skip) and Retry fetches the missing details alone;
 *   - the template catalogue failing changes nothing on this screen — it is
 *     for raising new work, not for the day's jobs, and the next sync tries it
 *     again (Retry includes it when it failed).
 * *Open my day* stays a button at 100% — the PO declined an automatic jump.
 *
 * With no loader wired at all (the app root has not passed one), FF-08 says
 * the day cannot load yet and offers *Skip* — never a fake bar.
 */

export const FIRST_SYNC_PARTS = ['shift', 'documents', 'jobs', 'assets', 'customers'] as const;
export type FirstSyncPartId = (typeof FIRST_SYNC_PARTS)[number];

/** Why a part did not (wholly) load, said in words on FF-08. */
/**
 * `certificate` — the phone refused the server's certificate; `outdated` — the
 * server has no such door (an HTML 404). Each says its own words, never *No
 * signal* (`DEF-FLD-10617`, decision log 2026-10-26).
 */
export type FirstSyncReason = 'noSignal' | 'signedOut' | 'server' | 'update' | 'certificate' | 'outdated';

export interface FirstSyncPart {
  id: FirstSyncPartId;
  state: 'waiting' | 'loading' | 'done' | 'failed' | 'unavailable';
  /** Loaded so far, and of how many when the server said (*8 of 11*). */
  done: number;
  total: number | null;
  /** Why it failed — or, on a `done` part with `done < total`, why some did not arrive. */
  reason?: FirstSyncReason | null;
}

export interface FirstSyncProgress {
  parts: FirstSyncPart[];
}

export interface FirstSyncPort {
  /** Starts (or joins) the first sync; reports as it goes; resolves when every loadable part settled. */
  run(onProgress: (p: FirstSyncProgress) => void): Promise<FirstSyncProgress>;
  /** Re-runs only what failed last time (the list → the whole sync; details → the missing details). */
  retry?(onProgress: (p: FirstSyncProgress) => void): Promise<FirstSyncProgress>;
}

/** The combined percentage over the parts that can load (0–100, whole numbers). */
export function percentOf(p: FirstSyncProgress): number {
  const loadable = p.parts.filter((x) => x.state !== 'unavailable');
  if (loadable.length === 0) return 0;
  let sum = 0;
  for (const part of loadable) {
    if (part.state === 'done') sum += 1;
    else if (part.total && part.total > 0) sum += Math.min(part.done / part.total, 1);
  }
  return Math.floor((sum / loadable.length) * 100);
}

export function isComplete(p: FirstSyncProgress): boolean {
  const loadable = p.parts.filter((x) => x.state !== 'unavailable');
  return loadable.length > 0 && loadable.every((x) => x.state === 'done');
}

/** The jobs still to come, for *3 of 11 jobs still to come*. Null when the total is not known or the part has settled. */
export function jobsToCome(p: FirstSyncProgress): { left: number; total: number } | null {
  const jobs = p.parts.find((x) => x.id === 'jobs');
  if (!jobs || jobs.total == null || (jobs.state !== 'loading' && jobs.state !== 'waiting')) return null;
  return { left: Math.max(jobs.total - jobs.done, 0), total: jobs.total };
}

/** A part that failed, or settled short (*10 of 11*): what Retry is for. */
export function hasShortfall(p: FirstSyncProgress): boolean {
  return p.parts.some((x) => x.state === 'failed' || (x.state === 'done' && x.total != null && x.done < x.total));
}

/** The first reason on the board, for the reason line. */
export function reasonOf(p: FirstSyncProgress): FirstSyncReason | null {
  for (const x of p.parts) if (x.reason && hasShortfall({ parts: [x] })) return x.reason;
  return null;
}

/** A sync step's failure in the engine's words (`SyncFailure`), as FF-08 says it. */
export function reasonFor(f: { kind: string; status?: number } | null | undefined): FirstSyncReason | null {
  if (!f) return null;
  if (f.kind === 'auth') return 'signedOut';
  if (f.kind === 'app_too_old') return 'update';
  if (f.kind === 'certificate') return 'certificate';
  if (f.kind === 'endpoint_missing') return 'outdated';
  // A timeout or a dropped connection has no status; a 5xx does.
  if (f.kind === 'network' && f.status === undefined) return 'noSignal';
  return 'server';
}

/** The part of the engine's `SyncResult` this port reads (structural, so a test can hand one in). */
export interface FirstSyncResult {
  pull: { upserts: number } | null;
  pullError: string | null;
  failures?: {
    pull: { kind: string; status?: number } | null;
    bundles?: { kind: string; status?: number } | null;
    templates?: { kind: string; status?: number } | null;
  };
  bundles?: { fetched: number; failed: number; lastFailure?: { kind: string; status?: number } } | null;
  bundlesError?: string | null;
  templatesError?: string | null;
  stoppedForAuth?: boolean;
  stoppedForUpdate?: boolean;
}

/** `all` = the whole sync; `details` = the missing bundles (and the catalogue when `templates`). */
export type FirstSyncRun = (what: 'all' | 'details', opts?: { templates: boolean }) => Promise<FirstSyncResult>;

/**
 * A `FirstSyncPort` over the sync engine, for the app root to pass once it
 * builds one: `engineFirstSync((what) => engine.sync({ technicianId, network,
 * onlyDetails: what === 'details' }))`. The jobs part follows the engine's
 * three steps separately (header); the four parts with no feed are
 * `unavailable`.
 */
export function engineFirstSync(runSync: FirstSyncRun): FirstSyncPort {
  const base = (jobs: FirstSyncPart): FirstSyncProgress => ({
    parts: FIRST_SYNC_PARTS.map((id) => (id === 'jobs' ? jobs : { id, state: 'unavailable', done: 0, total: null })),
  });
  /** What the last run left: the jobs listed, and whether the list or the catalogue failed. */
  let last: { jobs: FirstSyncPart; templatesFailed: boolean } | null = null;

  const failed = (reason: FirstSyncReason | null): FirstSyncPart => ({ id: 'jobs', state: 'failed', done: 0, total: null, reason });

  /**
   * The jobs row from a result. On a details-only retry `listed` is the list
   * from the run before and `before` the jobs still missing then.
   */
  const jobsFrom = (r: FirstSyncResult, listed: number | null, before?: number): FirstSyncPart => {
    const total = listed ?? r.pull?.upserts ?? null;
    if (total === null || (listed === null && (!r.pull || r.pullError))) {
      const why = reasonFor(r.failures?.pull) ?? (r.stoppedForUpdate ? 'update' : r.stoppedForAuth || !r.pull ? 'signedOut' : 'server');
      return failed(why);
    }
    const b = r.bundles;
    // No bundle door on this transport: the list is the whole of what loads.
    // A step that stopped half way (signed out) counts what it DID fetch.
    const missing = b ? (r.bundlesError ? Math.max((before ?? total) - b.fetched, 0) : Math.min(b.failed, total)) : 0;
    const reason = missing > 0 ? reasonFor(r.failures?.bundles ?? b?.lastFailure) ?? 'server' : null;
    return { id: 'jobs', state: 'done', done: total - missing, total, reason };
  };

  const settle = async (onProgress: (p: FirstSyncProgress) => void, go: () => Promise<FirstSyncPart>) => {
    let jobs: FirstSyncPart;
    try {
      jobs = await go();
    } catch {
      // Not from the wire (the engine rethrows those): say the server's.
      jobs = failed('server');
    }
    const out = base(jobs);
    onProgress(out);
    return out;
  };

  const run = async (onProgress: (p: FirstSyncProgress) => void): Promise<FirstSyncProgress> => {
    onProgress(base({ id: 'jobs', state: 'loading', done: 0, total: null }));
    return settle(onProgress, async () => {
      const r = await runSync('all');
      const jobs = jobsFrom(r, null);
      last = { jobs, templatesFailed: !!r.templatesError };
      return jobs;
    });
  };

  return {
    run,
    async retry(onProgress) {
      const prev = last;
      // The list failed (or nothing ran yet): the whole sync again.
      if (!prev || prev.jobs.state !== 'done' || prev.jobs.total == null) return run(onProgress);
      const total = prev.jobs.total;
      const before = total - prev.jobs.done;
      onProgress(base({ ...prev.jobs, state: 'loading', reason: null }));
      return settle(onProgress, async () => {
        const r = await runSync('details', { templates: prev.templatesFailed });
        const jobs = jobsFrom(r, total, before);
        last = { jobs, templatesFailed: prev.templatesFailed && !!r.templatesError };
        return jobs;
      });
    },
  };
}
