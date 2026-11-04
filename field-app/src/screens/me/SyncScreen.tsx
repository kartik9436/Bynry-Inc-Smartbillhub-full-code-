/**
 * FF-50 Sync (T-25; US-FLD-004, -041, -042, -046, -048; image
 * `phone/FF-50-sync.png`).
 *
 * The outbox, in the technician's words:
 *  - how many items are waiting (R32, R65: a NUMBER of items, never bytes)
 *    and whether the phone is connected;
 *  - what is on this phone (jobs with their bundle, of all open jobs);
 *  - what is waiting to send — completed work, and photographs on their own
 *    line with how many are up and how much is left (TC-4, R65);
 *  - anything the server REFUSED, with the server's own reason, kept here
 *    until the technician acts on it (R48: never retried silently), one row
 *    per job and reason with the act that reason allows (DEF-FLD-10612);
 *  - whose work it is when more than one technician has used the handset,
 *    each under their own name (E2E-21).
 *
 * Nothing on this screen deletes anything (R60, R64): there is no discard,
 * no clear, no "remove from queue". *Download everything* opens FF-08; *Sync
 * now* asks the engine to run (T-10 — not mounted in the app yet, so it says
 * it did not run).
 *
 * WHY NOTHING WENT (DEF-FLD-10624, A): one short fact under the count — from
 * the run just pressed, else from the waiting items' own saved failure — so
 * *"16 waiting"* never sits there unexplained. *Sync now* is a MANUAL run:
 * it clears this technician's backoff before sending (C).
 *
 * FB-004 (DEF-FLD-10629): a technician whose CAPTURE credential is gone
 * sees *Sign in again to send.*, how many wait, and the button (G); another
 * captor's work reads *Waiting for {name} to sign in.*; *Sync now* shows
 * *Sending…* and then *Sent N.* or the reason (H); a photograph whose act
 * has not gone yet waits for it, never *uploading* (I); a reader sees their
 * routes on the phone (J).
 *
 * Each card is its own component (B14 rule 43) because the tablet board
 * (FF-50 T) shows them one at a time beside the list of directions.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, ListRow, Meter, Notice, StatusChip } from '../../components';
import { useShellStatus } from '../../navigation/ShellStatus';
import { useOptionalSession } from '../../session/SessionProvider';
import type { UnsentSummary } from '../../session/sessionManager';
import { clockOffsetMs, clockWarning, subscribeClockOffset } from '../../sync/deviceClock';
import type { OutboxKind } from '../../sync/outbox';
import { REASON_KEY, type SyncReason } from '../../sync/syncReason';
import { useTheme } from '../../theme';
import { formatClock, formatMegabytes } from './format';
import { useActiveTechnician, useHandsetPrefs } from './hooks';
import { MeScreen, useDoor } from './MeScreen';
import { groupRefusals, type RefusalAction, type RefusalGroup } from './refusalGroups';
import { useMeServices, type RefusedItem, type StuckItem } from './services';

/**
 * A word for every kind the outbox can hold. Typed over `OutboxKind`, so a new
 * kind without a word fails `tsc`, and `kindWords.test.ts` walks
 * `CAPTURABLE_KINDS` against it. DEF-FLD-10603 found `raise` shown as the bare
 * word; DEF-FLD-10623 found `job_accept`, and nine more with no word at all.
 */
export const KIND_KEY: Record<OutboxKind, string> = {
  safety_tick: 'field.ff50.kind.safety_tick',
  task_tick: 'field.ff50.kind.task_tick',
  reading: 'field.ff50.kind.reading',
  material: 'field.ff50.kind.material',
  attachment: 'field.ff50.kind.attachment',
  signature: 'field.ff50.kind.signature',
  close: 'field.ff50.kind.close',
  photo: 'field.ff50.kind.photo',
  route_read: 'field.ff50.kind.route_read',
  route_finding: 'field.ff50.kind.route_finding',
  field_asset: 'field.ff50.kind.field_asset',
  route_position: 'field.ff50.kind.route_position',
  raise: 'field.ff50.kind.raise',
  crew_time: 'field.ff50.kind.crew_time',
  hand_back: 'field.ff50.kind.hand_back',
  job_accept: 'field.ff50.kind.job_accept',
  job_decline: 'field.ff50.kind.job_decline',
  shift_end: 'field.ff50.kind.shift_end',
  timesheet_submit: 'field.ff50.kind.timesheet_submit',
  availability: 'field.ff50.kind.availability',
  remark: 'field.ff50.kind.remark',
  document: 'field.ff50.kind.document',
};

/** How many raised orders *Raised* shows before *Show more* (NFR-3: no cap, paged). */
export const RAISED_PAGE = 20;

/** What every part of FF-50 reads: the outbox's counts, the refusals, whose work it is, and the two acts. */
export function useSyncState() {
  const { t } = useTranslation();
  const services = useMeServices();
  const tech = useActiveTechnician();
  const session = useOptionalSession();
  const status = useShellStatus();
  const [prefs] = useHandsetPrefs();
  const [version, setVersion] = useState(0);
  const [notice, setNotice] = useState<string | null>(null);
  /** The pressed run's reason; undefined — not pressed on this visit. */
  const [ran, setRan] = useState<{ reason: SyncReason | null; sent: number } | undefined>(undefined);
  const [running, setRunning] = useState(false);
  const [owners, setOwners] = useState<UnsentSummary | null>(null);
  // FB-014: the phone's clock against the server's, from the last answer.
  const [clockOffset, setClockOffset] = useState<number | null>(clockOffsetMs());
  useEffect(() => subscribeClockOffset(setClockOffset), []);
  const clock = clockWarning(clockOffset);

  const counts = tech ? services.data.syncCounts(tech.technicianId) : null;
  const refused = tech ? services.data.refused(tech.technicianId) : null;
  // FB-022: pending items the server has failed five times — still retried, now shown.
  const stuck = tech && services.data.needsAttention ? services.data.needsAttention(tech.technicianId) : null;

  useEffect(() => {
    let live = true;
    session?.manager.unsentSummary().then(
      (s) => live && setOwners(s),
      // The outbox port refuses rather than answering zero (session/services.ts):
      // "not known" is shown as nothing, never as "all sent".
      () => live && setOwners(null),
    );
    return () => {
      live = false;
    };
  }, [session, version]);

  async function syncNow() {
    setNotice(null);
    setRunning(true);
    try {
      const outcome = await services.sync.syncNow({ manual: true });
      setRan({ reason: outcome ? outcome.reason : null, sent: outcome ? outcome.sent : 0 });
      setVersion((v) => v + 1);
    } catch {
      setNotice(t('field.ff50.didNotRun'));
    } finally {
      setRunning(false);
    }
  }

  // The pressed run's reason first; else, while anything waits, the items' own.
  const reason: SyncReason | null =
    ran?.reason ?? (counts && counts.itemsWaiting > 0 ? (counts.waitingReason ?? null) : null);

  function resend(id: string): boolean {
    if (tech && services.data.resend(tech.technicianId, id)) {
      setVersion((v) => v + 1);
      return true;
    }
    return false;
  }

  /** *Send again* / *Sign in again* on a group: every item of it goes again, same keys. How many went. */
  function resendAll(ids: readonly string[]): number {
    if (!tech) return 0;
    const n = ids.filter((id) => services.data.resend(tech.technicianId, id)).length;
    if (n > 0) setVersion((v) => v + 1);
    return n;
  }

  /** *Send again* on a stuck item (FB-022): its wait is cleared, then a manual run sends it. */
  async function sendStuckNow(id: string): Promise<void> {
    if (!tech || !services.data.retryNow) return;
    services.data.retryNow(tech.technicianId, id);
    setVersion((v) => v + 1);
    await syncNow();
  }

  // G: the signed-in technician's capture credential is gone — their work cannot travel.
  const mineBlocked = !!counts && counts.itemsWaiting > 0 && !!session?.snapshot.captureNeedsPassword;
  /** Another captor on this handset whose work waits for their sign-in. */
  const waitsForSignIn = (technicianId: string) => !!session && !session.manager.captureValid(technicianId);
  /** H: what the pressed run sent, when it had nothing else to say. */
  const sent = ran && !reason && ran.sent > 0 ? ran.sent : null;

  return { tech, status, prefs, counts, refused, stuck, sendStuckNow, owners, notice, reason, sent, running, mineBlocked, waitsForSignIn, syncNow, resend, resendAll, clock, connected: status.connection === 'online' };
}

type SyncState = ReturnType<typeof useSyncState>;

/** How many items are waiting, whether the phone is connected, when it last reached the server. */
export function SyncStatusCard({ sync }: { sync: SyncState }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { counts, status, prefs } = sync;
  return (
    <Card testID="ff50-status">
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
        <View style={{ flexGrow: 1, flexShrink: 1 }}>
          <AppText variant="title" testID="ff50-waiting">
            {counts ? t('field.ff50.waiting', { count: counts.itemsWaiting }) : t('field.status.sync.unknown')}
          </AppText>
        </View>
        <StatusChip tone={sync.connected ? 'success' : 'neutral'} testID="ff50-connection">
          {t(
            status.connection === 'online'
              ? 'field.status.connection.online'
              : status.connection === 'offline'
                ? 'field.status.connection.offline'
                : 'field.status.connection.unknown',
          )}
        </StatusChip>
      </View>
      {counts?.lastReachedAt ? (
        <AppText variant="label" tone="muted" testID="ff50-last-reached">
          {t('field.ff50.lastReached', { time: formatClock(counts.lastReachedAt, prefs.clock) })}
        </AppText>
      ) : null}
      {sync.running ? (
        <AppText variant="body" testID="ff50-sending">
          {t('field.ff50.sending')}
        </AppText>
      ) : sync.reason && !(sync.mineBlocked && (sync.reason === 'signIn' || sync.reason === 'signInToSend')) ? (
        <AppText variant="body" testID="ff50-reason">
          {t(REASON_KEY[sync.reason])}
        </AppText>
      ) : sync.sent !== null ? (
        <AppText variant="body" testID="ff50-sent">
          {t('field.ff50.sent', { count: sync.sent })}
        </AppText>
      ) : null}
      {sync.clock ? (
        // FB-014 (PO 2026-10-28): said past 5 minutes; the work still goes.
        <AppText variant="body" tone="danger" testID="ff50-clock">
          {t(sync.clock.direction === 'fast' ? 'field.ff50.clockFast' : 'field.ff50.clockSlow', { minutes: sync.clock.minutes })}
        </AppText>
      ) : null}
    </Card>
  );
}

/** G: the signed-in technician's work cannot travel until they sign in again — said, counted, and the way in. */
export function SignInToSendCard({ sync }: { sync: SyncState }) {
  const { t } = useTranslation();
  const door = useDoor('FF-50');
  if (!sync.mineBlocked || !sync.counts) return null;
  return (
    <Card tone="danger" testID="ff50-sign-in-to-send">
      <AppText variant="body" weight="heavy">
        {t('field.ff50.reason.signInToSend')}
      </AppText>
      <AppText variant="body" testID="ff50-sign-in-to-send-count">
        {t('field.ff50.itemsWaitForYou', { count: sync.counts.itemsWaiting })}
      </AppText>
      <Button size="sm" onPress={() => door('FF-53')} testID="ff50-sign-in-to-send-button">
        {t('field.ff50.signInAgain')}
      </Button>
    </Card>
  );
}

/** The jobs on the phone, and the completed work waiting to send — or that the counts are not here. */
export function WaitingCards({ sync, photos = true }: { sync: SyncState; photos?: boolean }) {
  const { t } = useTranslation();
  const { counts } = sync;
  if (!counts) {
    return (
      <Notice tone="info" testID="ff50-not-wired">
        {t('field.me.notHereYet')}
      </Notice>
    );
  }
  return (
    <>
      <Card title={t('field.ff50.onThisPhone')}>
        <ListRow label={t('field.ff50.jobs')} value={t('field.ff50.of', { n: counts.jobsReady, total: counts.jobsTotal })} testID="ff50-jobs" />
        {counts.routesTotal ? (
          <ListRow
            divider
            label={t('field.ff50.routes')}
            value={t('field.ff50.routesValue', { count: counts.routesTotal, meters: counts.routeMeters ?? 0 })}
            testID="ff50-routes"
          />
        ) : null}
      </Card>
      <Card title={t('field.ff50.waitingToSend')}>
        <ListRow
          label={t('field.ff50.completedWork')}
          value={counts.itemsWaiting === 0 ? t('field.ff50.allSent') : t('field.ff50.itemsWaiting', { count: counts.itemsWaiting })}
          testID="ff50-completed"
        />
        {photos ? <PhotoLines sync={sync} divider /> : null}
      </Card>
    </>
  );
}

/** Photographs on their own line: how many are going up, how many are up, how much is left (TC-4, R65). */
export function PhotoLines({ sync, divider }: { sync: SyncState; divider?: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { counts, prefs } = sync;
  if (!counts) return null;
  // I (DEF-FLD-10629): a photograph whose act has not gone has nowhere to go
  // yet — it waits for its reading or its job, and is not counted as uploading.
  const awaitingRoute = counts.photosAwaitingRoute ?? 0;
  const awaitingJob = counts.photosAwaitingJob ?? 0;
  const able = Math.max(0, counts.photosWaiting - awaitingRoute - awaitingJob);
  const total = Math.max(0, counts.photosTotal - awaitingRoute - awaitingJob);
  const waitingWord = awaitingRoute > 0 ? t('field.ff50.photosWaitReadings') : t('field.ff50.photosWaitWork');
  return (
    <>
      <ListRow
        divider={divider}
        label={t('field.ff50.photos')}
        value={
          counts.photosWaiting === 0
            ? t('field.ff50.allSent')
            : able > 0
              ? t('field.ff50.photosUploading', { count: able })
              : waitingWord
        }
        testID="ff50-photos"
      />
      {able > 0 && awaitingRoute + awaitingJob > 0 ? (
        <AppText variant="label" tone="muted" testID="ff50-photos-waiting">
          {waitingWord}
        </AppText>
      ) : null}
      {total > 0 ? (
        <View style={{ gap: theme.space[2] }}>
          <Meter
            parts={[{ value: counts.photosUploaded, tone: 'warning' }]}
            total={total}
            label={t('field.ff50.photoProgress', {
              n: counts.photosUploaded,
              total,
              left: formatMegabytes(counts.photoBytesLeft),
            })}
            testID="ff50-photo-meter"
          />
          <AppText variant="label" tone="muted" testID="ff50-photo-progress">
            {t('field.ff50.photoProgress', {
              n: counts.photosUploaded,
              total,
              left: formatMegabytes(counts.photoBytesLeft),
            })}
          </AppText>
          {/* PO 2026-10-28 (FB-015): said ONLY when *Photos on wi-fi only* is on. */}
          {prefs.photosWifiOnly ? (
            <AppText variant="label" tone="muted">
              {t('field.ff50.photosWaitWifi')}
            </AppText>
          ) : null}
        </View>
      ) : null}
    </>
  );
}

/**
 * What the server refused, until the technician acts (R48) — one row per job
 * and reason, with the act that reason allows (DEF-FLD-10612, `refusalGroups.ts`):
 * none when the job has gone from them, *Sign in again*, *Send again*, or
 * *Fix and send again* per item. A group of one shows the item itself.
 */
export function RefusedCard({ sync, onResent }: { sync: SyncState; onResent?: () => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { refused } = sync;
  if (!refused || refused.length === 0) return null;
  const groups = groupRefusals(refused);
  // A job's refused accept is the cause of its row, not an item (DEF-FLD-10623):
  // a row counts its work, or one when the accept is all that has come back.
  const count = groups.reduce((n, g) => n + (g.work.length || 1), 0);
  return (
    <Card tone="danger" title={t('field.ff50.needsYou', { count })} testID="ff50-refused">
      {groups.map((g, i) => (
        <View
          key={g.id}
          style={{
            gap: theme.space[2],
            paddingTop: i > 0 ? theme.space[3] : 0,
            borderTopWidth: i > 0 ? theme.borderWidth.divider : 0,
            borderTopColor: theme.colors.divider,
          }}
        >
          {g.items.length === 1 && !g.cause ? (
            <RefusedItemRow sync={sync} item={g.items[0]!} onResent={onResent} />
          ) : (
            <RefusedGroupRow sync={sync} group={g} onResent={onResent} />
          )}
        </View>
      ))}
    </Card>
  );
}

/**
 * FB-022 (DEF-FLD-10794) — *Needs attention*: work the server has failed five
 * times and that is STILL being retried in the background (`backoff.ts`).
 * Each says what it is, why, how often it failed, and the server's short
 * reference to quote; *Send again* sends it now. Nothing here discards.
 */
export function AttentionCard({ sync }: { sync: SyncState }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { stuck } = sync;
  if (!stuck || stuck.length === 0) return null;
  return (
    <Card tone="warning" title={t('field.ff50.attention')} testID="ff50-attention">
      {stuck.map((item: StuckItem, i) => (
        <View
          key={item.id}
          testID={`ff50-attention-${item.id}`}
          style={{
            gap: theme.space[2],
            paddingTop: i > 0 ? theme.space[3] : 0,
            borderTopWidth: i > 0 ? theme.borderWidth.divider : 0,
            borderTopColor: theme.colors.divider,
          }}
        >
          <AppText variant="body" weight="heavy">
            {[kindLabel(t, item.kind), item.workOrderNumber].filter(Boolean).join(' · ')}
          </AppText>
          {item.reason ? (
            <AppText variant="body" testID={`ff50-attention-reason-${item.id}`}>
              {t(REASON_KEY[item.reason])}
            </AppText>
          ) : null}
          <AppText variant="label" tone="muted">
            {t('field.ff50.attentionFailed', { count: item.failures })}
          </AppText>
          {item.reference ? (
            <AppText variant="label" testID={`ff50-attention-ref-${item.id}`} selectable>
              {t('field.ff50.reference', { ref: item.reference })}
            </AppText>
          ) : null}
          <Button size="sm" busy={sync.running} onPress={() => void sync.sendStuckNow(item.id)} testID={`ff50-attention-send-${item.id}`}>
            {t('field.ff50.sendAgainAll')}
          </Button>
        </View>
      ))}
    </Card>
  );
}

function useReasonText() {
  const { t, i18n } = useTranslation();
  return (r: { reasonKey?: string | null; reason: string }) =>
    r.reasonKey && i18n.exists(r.reasonKey) ? t(r.reasonKey) : r.reason || t('field.ff50.noReason');
}

function kindLabel(t: (k: string) => string, kind: string): string {
  const key = (KIND_KEY as Record<string, string | undefined>)[kind];
  return key ? t(key) : kind;
}

/** One refused item: what it is, why, and — when the reason allows — its act. */
function RefusedItemRow({ sync, item, onResent }: { sync: SyncState; item: RefusedItem; onResent?: () => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const reasonText = useReasonText();
  return (
    <View testID={`ff50-refused-${item.id}`} style={{ gap: theme.space[2] }}>
      <AppText variant="body" weight="heavy">
        {[kindLabel(t, item.kind), item.workOrderNumber].filter(Boolean).join(' · ')}
      </AppText>
      <AppText variant="body" testID={`ff50-reason-${item.id}`}>
        {reasonText(item)}
      </AppText>
      {item.keptForOffice === true ? (
        <AppText variant="body" testID={`ff50-office-${item.id}`}>
          {t('field.ff50.keptForOffice')}
        </AppText>
      ) : null}
      <RefusalAct sync={sync} action={item.action ?? 'fix'} ids={[item.id]} testID={item.id} onResent={onResent} />
    </View>
  );
}

/** *WO-0028 · 13 items · This job was reassigned.*, its act, and the items behind it. */
function RefusedGroupRow({ sync, group, onResent }: { sync: SyncState; group: RefusalGroup<RefusedItem>; onResent?: () => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const reasonText = useReasonText();
  const [open, setOpen] = useState(false);
  // The refused accept is the cause, never counted (DEF-FLD-10623): the row
  // counts its work — one item by its word, none when only the accept is back.
  const { work } = group;
  const what = work.length > 1 ? t('field.ff50.groupItems', { count: work.length }) : work.length === 1 && group.cause ? kindLabel(t, work[0]!.kind) : null;
  const line = [group.workOrderNumber, what, reasonText(group)].filter(Boolean).join(' · ');
  return (
    <View testID={`ff50-group-${group.id}`} style={{ gap: theme.space[2] }}>
      <AppText variant="body" weight="heavy" testID={`ff50-group-line-${group.id}`}>
        {line}
      </AppText>
      {group.keptForOffice ? (
        <AppText variant="body" testID={`ff50-office-${group.id}`}>
          {t('field.ff50.keptForOffice')}
        </AppText>
      ) : null}
      {group.action !== 'fix' ? (
        <RefusalAct sync={sync} action={group.action} ids={group.items.map((r) => r.id)} testID={group.id} onResent={onResent} />
      ) : null}
      {work.length > 1 ? (
        <Button size="sm" onPress={() => setOpen((o) => !o)} testID={`ff50-group-toggle-${group.id}`}>
          {open ? t('field.ff50.hideItems') : t('field.ff50.showItems')}
        </Button>
      ) : null}
      {open
        ? work.map((r) => (
            <View key={r.id} testID={`ff50-refused-${r.id}`} style={{ gap: theme.space[2] }}>
              <AppText variant="body">{kindLabel(t, r.kind)}</AppText>
              {group.action === 'fix' ? (
                <RefusalAct sync={sync} action="fix" ids={[r.id]} testID={r.id} onResent={onResent} />
              ) : null}
            </View>
          ))
        : null}
    </View>
  );
}

/** The one act a reason allows: none, *Sign in again*, *Send again* (all of them), or *Fix and send again*. */
function RefusalAct(props: { sync: SyncState; action: RefusalAction; ids: string[]; testID: string; onResent?: () => void }) {
  const { t } = useTranslation();
  const door = useDoor('FF-50');
  const { sync, action, ids, testID, onResent } = props;
  if (action === 'none') return null;
  if (action === 'signIn') {
    return (
      <Button
        size="sm"
        onPress={() => {
          // Queued again now, so they go under the fresh credential once signed in.
          sync.resendAll(ids);
          door('FF-53');
        }}
        testID={`ff50-sign-in-${testID}`}
      >
        {t('field.ff50.signInAgain')}
      </Button>
    );
  }
  if (action === 'sendAgain') {
    return (
      <Button
        size="sm"
        onPress={() => {
          if (sync.resendAll(ids) > 0) onResent?.();
        }}
        testID={`ff50-send-again-${testID}`}
      >
        {t('field.ff50.sendAgainAll')}
      </Button>
    );
  }
  return (
    <Button
      size="sm"
      onPress={() => {
        if (sync.resend(ids[0]!)) onResent?.();
      }}
      testID={`ff50-resend-${testID}`}
    >
      {t('field.ff50.sendAgain')}
    </Button>
  );
}

/**
 * The orders this technician raised in the field: waiting to send, refused,
 * or — once the office has it — *WO-4870 raised*, the number the server
 * allocated (R24: never a number the phone made up). DEF-FLD-10603: the
 * number came back on the raise's answer and was shown nowhere, so a
 * technician who raised from Home could not quote it.
 */
export function RaisedCard({ sync }: { sync: SyncState }) {
  const { t } = useTranslation();
  const services = useMeServices();
  const [pages, setPages] = useState(1);
  const tech = sync.tech;
  const rows = tech && services.data.raised ? services.data.raised(tech.technicianId, RAISED_PAGE * pages + 1) : null;
  if (!rows || rows.length === 0) return null;
  const shown = rows.slice(0, RAISED_PAGE * pages);
  return (
    <Card title={t('field.ff50.raised')} testID="ff50-raised">
      {shown.map((r, i) => (
        <ListRow
          key={r.id}
          divider={i > 0}
          label={r.templateName ?? t('field.ff50.kind.raise')}
          detail={formatClock(r.capturedAt, sync.prefs.clock)}
          value={
            r.orderNo ? (
              <StatusChip tone="success" testID={`ff50-raised-order-${r.id}`}>
                {t('field.ff50.raisedAs', { order: r.orderNo })}
              </StatusChip>
            ) : r.refused ? (
              <StatusChip tone="danger">{t('field.ff50.raisedRefused')}</StatusChip>
            ) : (
              <StatusChip tone="neutral">{r.sent ? t('field.ff50.raisedSent') : t('field.ff50.raisedWaiting')}</StatusChip>
            )
          }
          testID={`ff50-raised-${r.id}`}
        />
      ))}
      {rows.length > shown.length ? (
        <Button size="sm" onPress={() => setPages((n) => n + 1)} testID="ff50-raised-more">
          {t('field.site.showMore')}
        </Button>
      ) : null}
    </Card>
  );
}

/** Whose work is waiting, when more than one technician has used the handset (E2E-21). */
export function OwnersCard({ sync }: { sync: SyncState }) {
  const { t } = useTranslation();
  const { owners, tech } = sync;
  const others = owners?.others ?? [];
  if (!owners || others.length === 0) return null;
  return (
    <Card title={t('field.ff50.capturedBy')} testID="ff50-owners">
      <ListRow label={tech?.name ?? ''} value={t('field.ff50.ownerLine', { items: owners.mine.items, photos: owners.mine.photos })} />
      {others.map((o) => (
        <ListRow
          key={o.technicianId}
          divider
          label={o.displayName || t('field.ff50.someoneElse')}
          value={t('field.ff50.ownerLine', { items: o.items, photos: o.photos })}
          detail={sync.waitsForSignIn(o.technicianId) ? t('field.ff50.waitingForName', { name: o.displayName || t('field.ff50.someoneElse') }) : undefined}
          testID={`ff50-owner-${o.technicianId}`}
        />
      ))}
    </Card>
  );
}

export function SyncScreen() {
  const { t } = useTranslation();
  const door = useDoor('FF-50');
  const sync = useSyncState();

  return (
    <MeScreen
      id="FF-50"
      title={t('field.screen.ff50')}
      leading={{ back: 'FF-10' }}
      footer={
        <Button grow variant="primary" busy={sync.running} onPress={sync.syncNow} testID="ff50-sync-now">
          {sync.running ? t('field.ff50.sending') : t('field.ff50.syncNow')}
        </Button>
      }
    >
      <Button variant="primary" onPress={() => door('FF-08')} testID="door-FF-08">
        {t('field.ff50.downloadEverything')}
      </Button>
      {sync.notice ? <Notice tone="warning">{sync.notice}</Notice> : null}
      <SyncStatusCard sync={sync} />
      <SignInToSendCard sync={sync} />
      <WaitingCards sync={sync} />
      <RefusedCard sync={sync} />
      <AttentionCard sync={sync} />
      <RaisedCard sync={sync} />
      <OwnersCard sync={sync} />
    </MeScreen>
  );
}
