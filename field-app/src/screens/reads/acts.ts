/**
 * The acts a reader takes, each captured ONCE through the outbox so the act,
 * its photographs and its idempotency key land together (Mobile data §1) —
 * and each write to the reading row inside the same transaction.
 *
 * A reading is a RECORD (R88): value and unit, the reader's status, position
 * with accuracy and the distance to the meter's recorded place (R90), the
 * device clock (R92 — the server adds its own on arrival), who read it, how
 * the meter was identified, and whatever the reader chose to add. Position is
 * taken at save and never typed; no fix is stored as no fix and the reading is
 * still kept (R91). FB-003 (PO 2026-10-27): the save waits up to 10 s for a
 * first fix, and a fix within 5 minutes after a save without one is sent as
 * its own fact (`position.ts`); a photograph keeps its shutter's position.
 *
 * Route readings go on the `route` channel and the sync engine sends them to
 * `POST work/mobile/reads/sync` (`sync/routeReads.ts` maps the wire). Raises
 * and field-added meters go on the `unrouted` channel, which has no server
 * door yet, and wait. Nothing is dropped and nothing is guessed.
 */
import { fromJson } from '../../db/json';
import * as assetQ from '../../db/queries/asset';
import * as routeQ from '../../db/queries/route';
import * as routeReadQ from '../../db/queries/routeRead';
import * as walkQ from '../../db/queries/readsWalk';
import { scoped } from '../../db/scoped';
import { capture, type PhotoCapture } from '../../sync/outbox';
import { registerOfReadId } from '../../sync/routes';
import { fixQuality, metresBetween } from './figures';
import { fixForSave } from './position';
import type { Fix } from './ports';
import { type Answers, answerShots, type ReadQuestion, toWire, type WireAnswer } from './readFormat';
import type { ReadDraft, ReadsServices } from './services';

function captor(sv: ReadsServices) {
  return { technicianId: sv.technicianId, capturedBy: sv.capturedBy };
}

/** The meter's number as the server knows it: the download's `meter_no`, else the serial. */
export function meterNo(m: walkQ.MeterRead): string | null {
  const extra = fromJson<Record<string, unknown>>(m.asset_extra);
  return typeof extra?.meter_no === 'string' ? extra.meter_no : m.serial;
}

/** The register this reading is for: a downloaded reading's id names it (`sync/routes.ts`). */
function registerOf(m: walkQ.MeterRead): string | null {
  return registerOfReadId(m.id, m.route_id);
}

function deps(sv: ReadsServices) {
  return { newId: () => sv.newId(), clock: sv.clock };
}

function photosFor(shots: ReadDraft['photos'], target: PhotoCapture['target']): PhotoCapture[] {
  return shots.map((p) => ({ ...p, target }));
}

export interface SaveReading {
  readerStatus: 'read' | 'could_not_read' | 'read_with_problem';
  /** R80: the reader saw the warning and kept the figure. */
  warnedAccepted?: boolean;
  noReadReason?: string | null;
  readMethod: string | null;
  /** MQ-033: the utility's questions this reading showed, and the answers.
   *  Absent on a route with no format — the item is exactly as before. */
  form?: { versionId: string; visible: readonly ReadQuestion[]; answers: Answers };
}

/** Save the figure (or the reason) on one meter. Returns the capture key. */
export async function saveReading(sv: ReadsServices, m: walkQ.MeterRead, draft: ReadDraft, act: SaveReading): Promise<string> {
  // FB-003 (PO 2026-10-27): the watch's fresh fix, else up to 10 s for one,
  // else none — never longer. A reading saved without one may still get a
  // LATE position, as its own fact (`position.ts`).
  const fix: Fix | null = await fixForSave(sv.location, () => sv.clock.now().getTime());
  const recorded = m.stop_lat !== null && m.stop_lng !== null ? { lat: m.stop_lat, lng: m.stop_lng } : null;
  const metres = fix && recorded ? Math.round(metresBetween(fix, recorded)) : null;
  const quality = fixQuality(fix ? fix.accuracy_m : null);
  const value = act.readerStatus === 'could_not_read' ? null : draft.value;
  const now = sv.clock.now().toISOString();
  // MQ-033: a photo answer is a photograph of THIS reading, declared like the
  // others; its answer names the id minted for it (after the draft's own).
  const form = act.form ?? null;
  const shots = form ? answerShots(form.visible, form.answers) : [];
  let wireAnswers: WireAnswer[] | null = null;
  const done = capture(
    sv.db,
    captor(sv),
    {
      kind: 'route_read',
      routeId: m.route_id,
      payload: {},
      payloadFor: (photoIds) => {
        if (form) {
          const idOf = new Map(shots.map((s, i) => [s.key, photoIds[draft.photos.length + i] ?? null]));
          wireAnswers = toWire(form.visible, form.answers, (key) => idOf.get(key) ?? null);
        }
        return {
          route_read_id: m.id,
          asset_id: m.asset_id,
          // What the server identifies the meter and the place by (`POST
          // work/mobile/reads/sync`): the meter's number as the route download
          // served it, and the premises. Carried on the item so the wire needs
          // nothing the store would have to be asked for at send time.
          meter_no: meterNo(m),
          premises_id: m.premise_id,
          register: registerOf(m),
          account_id: m.account_id,
          value,
          unit: m.unit,
          reader_status: act.readerStatus,
          no_read_reason: act.noReadReason ?? null,
          warned_accepted: act.warnedAccepted ?? false,
          // RW-16: the first try travels whole beside the second (nothing overwritten).
          first_try: draft.firstTry,
          remark: draft.remark,
          remark_source: draft.remarkSource,
          identified_by: draft.identifiedBy,
          off_route: m.off_route === 1,
          read_method: act.readMethod,
          fix_quality: quality,
          metres_from_record: metres,
          ...(form ? { read_format_version_id: form.versionId, answers: wireAnswers } : {}),
        };
      },
      location: fix,
      photos: photosFor([...draft.photos, ...shots.map((x) => x.shot)], { route_read_id: m.id }),
      apply: (s, key) => {
        routeReadQ.recordCapture(s, m.id, {
          captureKey: key,
          value,
          unit: m.unit,
          readerStatus: act.readerStatus,
          noReadReason: act.noReadReason ?? null,
          warnedAccepted: act.warnedAccepted ?? false,
          location: fix ? { lat: fix.lat, lng: fix.lng, accuracy_m: fix.accuracy_m } : null,
          fixQuality: quality,
          metresFromRecord: metres,
          capturedAt: now,
          capturedBy: sv.capturedBy,
          identifiedBy: draft.identifiedBy,
          offRoute: m.off_route === 1,
          readMethod: act.readMethod ?? '',
          remark: draft.remark,
          remarkSource: draft.remarkSource,
          readFormatVersionId: form?.versionId ?? null,
          answers: wireAnswers,
        });
        walkQ.markInProgress(s, m.route_id, now);
      },
    },
    deps(sv),
  );
  return done.key;
}

/** RW-21: something found at a meter, sent to the office (R85's sibling — the office accepts it). */
export async function raiseIt(
  sv: ReadsServices,
  m: walkQ.MeterRead,
  input: { finding: string; urgency: string | null; remark: string | null; remarkSource: 'voice' | 'typed' | null; photos: ReadDraft['photos'] },
): Promise<string> {
  const fix = await sv.location.current();
  return capture(
    sv.db,
    captor(sv),
    {
      kind: 'route_finding',
      routeId: m.route_id,
      payload: {
        finding: input.finding,
        urgency: input.urgency,
        remark: input.remark,
        remark_source: input.remarkSource,
        premise_id: m.premise_id,
        asset_id: m.asset_id,
        account_id: m.account_id,
        route_read_id: m.id,
      },
      location: fix,
      photos: photosFor(input.photos, { route_read_id: m.id }),
    },
    deps(sv),
  ).key;
}

/**
 * RW-20: a meter the system does not know, added in the field. It is
 * `pending` until the office accepts it and bills only then (R85); its address
 * is the premises the reader is standing at, never typed (R86).
 */
export async function addMeter(
  sv: ReadsServices,
  input: { routeId: string; premiseId: string; badge: string | null; serial: string | null; service: string; size: string; photos: ReadDraft['photos'] },
): Promise<string> {
  const fix = await sv.location.current();
  const assetId = sv.newId();
  const now = sv.clock.now().toISOString();
  return capture(
    sv.db,
    captor(sv),
    {
      kind: 'field_asset',
      routeId: input.routeId,
      payload: {
        asset_id: assetId,
        badge: input.badge,
        serial: input.serial,
        service: input.service,
        size: input.size,
        premise_id: input.premiseId,
      },
      location: fix,
      photos: photosFor(input.photos, {}),
      apply: (_s, key) => {
        assetQ.upsert(
          sv.db,
          {
            id: assetId,
            badge: input.badge,
            serial: input.serial,
            service: input.service,
            size: input.size,
            premiseId: input.premiseId,
            status: 'pending',
            outboxId: key,
          },
          now,
        );
      },
    },
    deps(sv),
  ).key;
}

/**
 * RW-25: the route is handed in. ⚠ No server door takes a turn-in yet; the
 * route is marked on the handset and its readings go on waiting for the
 * route-reads endpoint. Turning in never deletes anything (R60).
 */
export function turnIn(sv: ReadsServices, routeId: string): void {
  const at = sv.clock.now().toISOString();
  sv.db.transaction(() => routeQ.markTurnedIn(scopedOf(sv), routeId, at));
}

function scopedOf(sv: ReadsServices) {
  return scoped(sv.db, sv.technicianId);
}

/** RW-19: put a known meter that is not on this route onto the reader's list, off-route (R84). */
export function readOffRoute(sv: ReadsServices, input: { routeId: string; stopId: string; asset: assetQ.AssetRow; unit: string }): string {
  const id = sv.newId();
  walkQ.insertOffRoute(
    scopedOf(sv),
    { id, routeId: input.routeId, stopId: input.stopId, assetId: input.asset.id, accountId: null, previousValue: null, unit: input.unit },
    sv.clock.now().toISOString(),
  );
  return id;
}
