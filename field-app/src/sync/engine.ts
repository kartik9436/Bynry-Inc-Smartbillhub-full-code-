/**
 * One sync at a time, in the right order.
 *
 *  - Data before photographs (R51): the photo phase starts after the data
 *    phase, and a photo is eligible only once its declaration is acknowledged.
 *  - A pull never runs while a push is mid-batch (R59) — so a stale mirror
 *    cannot overwrite a record the server has just accepted. This engine is
 *    stricter than "per order": push and pull never overlap at all.
 *  - At most two data batches and one photograph in flight (Mobile data §12).
 *  - THREE DOWNLOADS, REPORTED SEPARATELY (DEF-FLD-10608): the change feed
 *    (`pullError`/`failures.pull` — the job LIST), the per-job bundles
 *    (`bundles` with its per-job `failed` count, `bundlesError` when the step
 *    itself stopped) and the template catalogue (`templatesError`). Until
 *    2026-10-26 all three were folded into the one `pullError`, so FF-08 could
 *    not tell a lost job list from one job's missing details and failed the
 *    whole day for either. `pullError` now means the FEED and nothing else.
 *  - `onlyDetails` re-runs the bundles (and, `withTemplates`, a failed catalogue) alone — FF-08's
 *    Retry when the list arrived and some details did not.
 *  - A RUN HAS A TIME LIMIT (`runLimitMs`, DEF-FLD-10624 F): a call joins the
 *    busy run, so a run that never settles would hold every later *Sync now*
 *    forever. When the limit passes, the run is let go (`busy` released) and
 *    the caller gets a `StepTimeLimitError`; the next call starts afresh.
 *  - The purge is NOT here. It runs on app start, never on a timer, so it can
 *    never run mid-upload (R63) — `db/purge.ts`.
 */
import type { TenantDb } from '../db/database';
import { pullChanges, type PullSummary } from './delta';
import { downloadTemplates, fetchBundles, type BundleSummary } from './extras';
import { asFieldApi } from './fieldApi';
import { sendPending, type CaptureTokens, type Clock, type SendSummary } from './outbox';
import { emptyTally } from './receipts';
import { uploadPhotos, type FileStore, type NetworkKind, type PhotoSummary } from './photos';
import { within } from './runLimits';
import { failureOf, TransportError, type SyncFailure, type Transport } from './transport';

export interface EngineDeps {
  db: TenantDb;
  transport: Transport;
  files: FileStore;
  tokens: CaptureTokens;
  clock: Clock;
  random?: () => number;
  /** The whole run's limit (`runLimits.ts`); none when not given. */
  runLimitMs?: number;
}

export interface SyncResult {
  data: SendSummary;
  photos: PhotoSummary | null;
  pull: PullSummary | null;
  /** The CHANGE FEED's failure only (the job list) — never the bundles or the catalogue. */
  pullError: string | null;
  /** The jobs' bundles fetched after the pull (`extras.ts`); null when not run. Per-job failures are `bundles.failed`. */
  bundles?: BundleSummary | null;
  /** The bundle step stopped as a whole (sign-in expired, build refused). */
  bundlesError?: string | null;
  /** Templates in the catalogue download; null when not run. */
  templates?: number | null;
  templatesError?: string | null;
  /** Each step's failure as data (kind, status), for a screen to say in words. */
  failures?: { pull: SyncFailure | null; bundles: SyncFailure | null; templates: SyncFailure | null };
  /** The run stopped because the sign-in expired / the server refused this build. */
  stoppedForAuth?: boolean;
  stoppedForUpdate?: boolean;
}

export interface SyncOptions {
  technicianId: string | null;
  network: NetworkKind;
  allowMobileData?: boolean;
  /** Push only — set while the server refuses this build, so nothing is downloaded. */
  skipPull?: boolean;
  /** Only the bundles still missing: no push, no photographs, no feed. */
  onlyDetails?: boolean;
  /** With `onlyDetails`: the catalogue too (it failed last time). */
  withTemplates?: boolean;
}

/** A details-only run sends nothing. */
const nothingSent = (): SendSummary => ({ ...emptyTally(), batches: 0, stoppedForAuth: false, stoppedForUpdate: false, skippedNoToken: 0, skippedNoTokenBy: {}, waitingForCaptor: 0 });

export class SyncEngine {
  private busy: Promise<SyncResult> | null = null;

  constructor(private readonly deps: EngineDeps) {}

  get running(): boolean {
    return this.busy !== null;
  }

  /**
   * Push the outbox, then the photographs, then pull for whoever is signed in
   * (`technicianId` null = signed in as nobody: push only, E2E-21). A second
   * call while one is running joins it rather than starting a parallel one.
   */
  sync(opts: SyncOptions): Promise<SyncResult> {
    if (this.busy) return this.busy;
    const run = this.run(opts);
    const limited = this.deps.runLimitMs ? within(run, this.deps.runLimitMs, 'sync run') : run;
    this.busy = limited.finally(() => {
      this.busy = null;
    });
    return this.busy;
  }

  private async run(opts: SyncOptions): Promise<SyncResult> {
    const { db, transport, files, tokens, clock, random } = this.deps;
    if (opts.onlyDetails) return this.details(opts, { data: nothingSent(), photos: null, pull: null, pullError: null }, !!opts.withTemplates);
    // Every item, own-door ones included, travels under its CAPTOR's token
    // (lane S-GAPS): who is signed in no longer decides what is sent.
    const data = await sendPending(db, transport, { clock, tokens, random });
    // A refused build (`app_too_old`, DEF-FLD-10355) stops the run where it
    // is: what was not sent stays queued and sends after the update.
    const photos = data.stoppedForAuth || data.stoppedForUpdate
      ? null
      : await uploadPhotos(db, transport, files, {
          clock,
          network: opts.network,
          allowMobileData: opts.allowMobileData,
          random,
        });
    let pull: PullSummary | null = null;
    let pullFailure: SyncFailure | null = null;
    if (opts.technicianId && !data.stoppedForAuth && !data.stoppedForUpdate && !photos?.stoppedForUpdate && !opts.skipPull) {
      try {
        pull = await pullChanges(db, transport, opts.technicianId, { clock });
      } catch (err) {
        // A failed pull leaves the cursor where the last good page put it;
        // the next sync resumes from there. Captured work is unaffected.
        if (!(err instanceof TransportError)) throw err;
        pullFailure = failureOf(err);
      }
    }
    const base: SyncResult = {
      data,
      photos,
      pull,
      pullError: pullFailure?.message ?? null,
      failures: { pull: pullFailure, bundles: null, templates: null },
      stoppedForAuth: !!data.stoppedForAuth || pullFailure?.kind === 'auth',
      stoppedForUpdate: !!data.stoppedForUpdate || !!photos?.stoppedForUpdate || pullFailure?.kind === 'app_too_old',
    };
    return pull ? this.details(opts, base, true) : base;
  }

  /**
   * The bundles and the catalogue, after the feed (BR-WRK-042: at sync, never
   * on a tap) — only where the transport has those doors. Each its own step:
   * a failed bundle never marks the feed failed, and a failed catalogue never
   * marks the bundles failed (DEF-FLD-10608).
   */
  private async details(opts: SyncOptions, base: SyncResult, withTemplates: boolean): Promise<SyncResult> {
    const { db, transport, files, clock } = this.deps;
    const api = asFieldApi(transport);
    const out: SyncResult = { ...base, failures: base.failures ?? { pull: null, bundles: null, templates: null } };
    if (!api || !opts.technicianId) return out;
    const tally: BundleSummary = { fetched: 0, failed: 0, readingsSkipped: 0, documentsDownloaded: 0 };
    try {
      out.bundles = await fetchBundles(db, api, opts.technicianId, { clock, files, summary: tally });
    } catch (err) {
      if (!(err instanceof TransportError)) throw err;
      out.bundles = tally;
      out.bundlesError = err.message;
      out.failures!.bundles = failureOf(err);
      if (err.kind === 'auth') out.stoppedForAuth = true;
      if (err.kind === 'app_too_old') out.stoppedForUpdate = true;
      // Signed out or refused: the catalogue would be refused the same way.
      return out;
    }
    if (!withTemplates) return out;
    try {
      out.templates = await downloadTemplates(db, api, { clock });
    } catch (err) {
      if (!(err instanceof TransportError)) throw err;
      out.templatesError = err.message;
      out.failures!.templates = failureOf(err);
    }
    return out;
  }
}
