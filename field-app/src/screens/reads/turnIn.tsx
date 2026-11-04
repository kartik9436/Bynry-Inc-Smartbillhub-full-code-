/**
 * Handing the route in — RW-25 Turn it in, RW-26 Sending, RW-27 Turned in
 * (EP-FLD-14). Built from `wireframes/reads/RW-25…27*.png`.
 *
 * RW-25 with meters unread: the PRIMARY act sends the reader back to them and
 * turning in anyway is second, in the danger tier (US-FLD-040 TC-2). RW-27's
 * receipt names what did NOT land as plainly as what did — never read, and
 * every refusal with the server's own reason and whose it is to sort out.
 *
 * ⚠ The server has no route-reads door yet (metering lane building it), so
 * on this build RW-26 shows the readings WAITING on the phone rather than a
 * send that is not happening, and RW-27 says *on this phone* until the office
 * has answered for every reading. Turning in is recorded on the handset; no
 * server door takes a turn-in yet either. Nothing is dropped (R60).
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ActionBar, AppText, Button, Card, Kicker, ListRow, Notice, ProgressBar, StatusChip } from '../../components';
import { fromJson } from '../../db/json';
import { RETENTION } from '../../db/purge';
import * as walkQ from '../../db/queries/readsWalk';
import { useTheme } from '../../theme';
import { turnIn } from './acts';
import { Spread } from './parts';
import { RouteReadings } from './readingRecord';
import { ScreenBody, useGo, useLive, useParams } from './ReadsScreen';
import { resolveRoute, routeName } from './records';
import { useReads } from './services';

function NoRoute() {
  const { t } = useTranslation();
  const go = useGo();
  return (
    <ScreenBody>
      <Notice tone="info">{t('field.reads.common.noRoute')}</Notice>
      <Button testID="door-RW-01" onPress={() => go('RW-01')}>
        {t('field.reads.common.myRoutes')}
      </Button>
    </ScreenBody>
  );
}

function Tick({ done, label, testID }: { done: boolean; label: string; testID?: string }) {
  return <ListRow label={label} leading={<AppText variant="section">{done ? '✓' : '○'}</AppText>} testID={testID} />;
}

// ── RW-25 Turn it in ────────────────────────────────────────────────────────

export function TurnItIn() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const { s, services, bump } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  const tally = useLive(() => (r ? walkQ.tally(s, r.id) : null), [r?.id]);
  const shots = useLive(() => (r ? walkQ.photoCounts(s, r.id) : null), [r?.id]);
  const left = useLive(() => (r ? walkQ.stopCount(s, r.id, 'not_read') : 0), [r?.id]);
  if (!r || !tally || !shots) return <NoRoute />;
  const hand = () => {
    turnIn(services, r.id);
    services.turnInRoute?.(r.id);
    void services.sendNow().catch(() => undefined);
    bump();
    go('RW-26', { routeId: r.id });
  };
  return (
    <ScreenBody
      bar={
        <ActionBar stacked>
          {tally.unread > 0 ? (
            <>
              <Button variant="primary" testID="go-read" onPress={() => go('RW-23', { routeId: r.id, tab: 'not_read' })}>
                {t('field.reads.rw25.goRead', { n: tally.unread })}
              </Button>
              <Button variant="danger" testID="door-RW-26" onPress={hand}>
                {t('field.reads.rw25.turnInPart', { done: tally.done, total: tally.total })}
              </Button>
            </>
          ) : (
            <Button variant="primary" testID="door-RW-26" onPress={hand}>
              {t('field.reads.rw25.turnIn')}
            </Button>
          )}
        </ActionBar>
      }
    >
      <Card>
        <Tick done label={t('field.reads.rw25.taken', { n: tally.read })} testID="tick-read" />
        <Tick done label={t('field.reads.rw25.reasons', { n: tally.could_not })} testID="tick-reasons" />
        <Tick done label={t('field.reads.rw25.flagged', { n: tally.flagged })} testID="tick-flagged" />
        <Tick done label={t('field.reads.rw25.photos', { n: shots.total })} testID="tick-photos" />
        <Tick done label={t('field.reads.rw25.raised', { n: tally.raised })} testID="tick-raised" />
      </Card>
      {tally.unread > 0 ? (
        <Card tone="warning" title={t('field.reads.rw25.notRead', { n: tally.unread })} testID="unread-card">
          <AppText variant="body">{t('field.reads.rw25.atStops', { n: left })}</AppText>
          <Button testID="door-RW-23" onPress={() => go('RW-23', { routeId: r.id, tab: 'not_read' })}>
            {t('field.reads.rw25.seeThem')}
          </Button>
        </Card>
      ) : null}
      <Card>
        <AppText variant="body">{t('field.reads.rw25.cycle')}</AppText>
      </Card>
    </ScreenBody>
  );
}

// ── RW-26 Sending ───────────────────────────────────────────────────────────

export function Sending() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const { s, services, bump } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  const tally = useLive(() => (r ? walkQ.tally(s, r.id) : null), [r?.id]);
  const shots = useLive(() => (r ? walkQ.photoCounts(s, r.id) : null), [r?.id]);
  const [tried, setTried] = useState(false);
  useEffect(() => {
    services
      .sendNow()
      .catch(() => undefined)
      .finally(() => {
        setTried(true);
        bump();
      });
  }, [services, bump]);
  if (!r || !tally || !shots) return <NoRoute />;
  const answered = tally.accepted + tally.duplicate + tally.held + tally.refused;
  const waiting = tally.pending + tally.sending;
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button variant="primary" grow testID="door-RW-27" onPress={() => go('RW-27', { routeId: r.id })}>
            {t('field.reads.rw26.leave')}
          </Button>
        </ActionBar>
      }
    >
      <Card title={t('field.reads.rw26.readings')}>
        <AppText variant="title" testID="sent-of">
          {t('field.reads.rw26.sentOf', { sent: answered, total: answered + waiting })}
        </AppText>
        <ProgressBar tone="strong" done={answered} total={answered + waiting} label={t('field.reads.rw26.sentOf', { sent: answered, total: answered + waiting })} />
      </Card>
      <Card>
        <ListRow label={t('field.reads.rw26.taken', { n: tally.accepted + tally.held })} testID="row-taken" />
        <ListRow divider label={t('field.reads.rw26.twice', { n: tally.duplicate })} testID="row-twice" />
        <ListRow
          divider
          label={t('field.reads.rw26.refused', { n: tally.refused })}
          onPress={tally.refused ? () => go('RW-27', { routeId: r.id }) : undefined}
          testID="row-refused"
        />
        <ListRow divider label={t('field.reads.rw26.waiting', { n: waiting })} testID="row-waiting" />
      </Card>
      <Card title={t('field.reads.rw26.photos')}>
        <AppText variant="section">{t('field.reads.rw26.uploaded', { sent: shots.sent, total: shots.total })}</AppText>
        <ProgressBar done={shots.sent} total={shots.total} label={t('field.reads.rw26.uploaded', { sent: shots.sent, total: shots.total })} />
        <AppText variant="label" tone="muted">
          {t('field.reads.rw26.safe')}
        </AppText>
      </Card>
      {tried && waiting > 0 ? <Notice tone="warning" testID="still-waiting">{t('field.reads.rw26.notYet')}</Notice> : null}
      <Notice tone="info">{t('field.reads.rw26.close')}</Notice>
    </ScreenBody>
  );
}

// ── RW-27 Turned in ─────────────────────────────────────────────────────────

function refusalText(raw: string | null): string | null {
  const r = fromJson<Record<string, unknown>>(raw);
  if (!r) return null;
  for (const k of ['message', 'reason', 'detail']) if (typeof r[k] === 'string') return r[k] as string;
  return null;
}

export function TurnedIn() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s } = useReads();
  const r = useLive(() => resolveRoute(s, params), [params.routeId]);
  const tally = useLive(() => (r ? walkQ.tally(s, r.id) : null), [r?.id]);
  const refused = useLive(() => (r ? walkQ.refusals(s, r.id) : []), [r?.id]);
  const left = useLive(() => (r ? walkQ.stopCount(s, r.id, 'not_read') : 0), [r?.id]);
  if (!r || !tally) return <NoRoute />;
  const waiting = tally.pending + tally.sending;
  const officeHasIt = waiting === 0 && tally.done > 0;
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button variant="primary" grow testID="door-RW-01" onPress={() => go('RW-01')}>
            {t('field.reads.common.myRoutes')}
          </Button>
        </ActionBar>
      }
    >
      <AppText variant="title">{routeName(r)}</AppText>
      <Card tone={officeHasIt ? 'plain' : 'info'} testID={officeHasIt ? 'office-has-it' : 'on-this-phone'}>
        <AppText variant="section" style={{ textAlign: 'center' }}>
          {officeHasIt ? t('field.reads.rw27.officeHasIt') : t('field.reads.rw27.onPhone', { n: waiting })}
        </AppText>
        {r.turned_in_at ? (
          <AppText variant="label" tone="muted" style={{ textAlign: 'center' }}>
            {new Date(r.turned_in_at).toLocaleString()}
          </AppText>
        ) : null}
      </Card>
      <Kicker>{t('field.reads.rw27.landed')}</Kicker>
      <Card>
        <ListRow label={t('field.reads.rw27.readings')} value={String(tally.accepted + tally.duplicate + tally.held)} testID="landed-readings" />
        <ListRow divider label={t('field.reads.rw27.withReason')} value={String(tally.could_not)} testID="landed-reason" />
        <ListRow divider label={t('field.reads.rw27.flagged')} value={String(tally.held)} testID="landed-flagged" />
      </Card>
      <Kicker>{t('field.reads.rw27.didNot')}</Kicker>
      {tally.unread > 0 ? (
        <Card tone="warning" testID="never-read">
          <Spread>
            <AppText variant="body" weight="heavy">
              {t('field.reads.rw27.neverRead', { n: tally.unread })}
            </AppText>
            <AppText variant="body" weight="heavy" style={{ color: theme.colors.statusInk.warning }}>
              {String(tally.unread)}
            </AppText>
          </Spread>
          <AppText variant="label" tone="muted">
            {t('field.reads.rw27.atStops', { n: left })}
          </AppText>
        </Card>
      ) : null}
      {waiting > 0 ? (
        <Card tone="info" testID="still-waiting">
          <AppText variant="body" weight="heavy">
            {t('field.reads.rw27.waiting', { n: waiting })}
          </AppText>
        </Card>
      ) : null}
      {refused.map((x) => (
        <Card key={x.read_id} tone="danger" testID={`refused-${x.read_id}`}>
          <Spread>
            <AppText variant="body" weight="heavy">
              {t('field.reads.rw27.refused')}
            </AppText>
            <StatusChip tone="danger">{t('field.reads.rw27.yours')}</StatusChip>
          </Spread>
          <AppText variant="body">{[x.serial, refusalText(x.refusal)].filter(Boolean).join(' — ')}</AppText>
          <View>
            <Button variant="danger" testID="door-RW-06" onPress={() => go('RW-06', { readId: x.read_id })}>
              {t('field.reads.rw27.sortOut')}
            </Button>
          </View>
        </Card>
      ))}
      {tally.unread === 0 && refused.length === 0 && waiting === 0 ? <Notice tone="success">{t('field.reads.rw27.nothingMissing')}</Notice> : null}
      {/* FB-030 — every reading taken on the route, each opening its record (RW-28's drill). */}
      <RouteReadings routeId={r.id} />
      <Notice tone="info">{t('field.reads.rw27.kept', { days: RETENTION.closedDays })}</Notice>
    </ScreenBody>
  );
}
