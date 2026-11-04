/**
 * At the address — RW-06 The stop, RW-07 Getting in, RW-08 Find a meter,
 * RW-12 Master and subs (EP-FLD-11). Built from `wireframes/reads/RW-06,
 * 07, 08, 12*.png`.
 *
 * R74: the stop is the address and holds EVERY meter at it — master and subs
 * included. R79 (PO ruled, an overruled recommendation): the customer's name
 * is shown at the stop beside the unit label and the account number.
 * RW-12's *Still to find* is the master's figure less its subs', in the
 * meter's own unit — computed only when every figure carries the SAME unit
 * (hard rule 3: never assume, never convert); the office checks the balance.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ActionBar, AppText, Button, Card, Field, IconButton, Kicker, ListRow, Notice, StatusChip } from '../../components';
import * as assetQ from '../../db/queries/asset';
import * as walkQ from '../../db/queries/readsWalk';
import { useDefaultSelection, usePick } from '../../tablet/selection';
import { useTheme } from '../../theme';
import { add, group, subtract } from './figures';
import { Figure, PressCard, ReaderStatusChip, Spread } from './parts';
import { ScreenBody, useGo, useLive, useParams } from './ReadsScreen';
import { meterName, resolveAll, streetOf, unitLabel } from './records';
import { useReads } from './services';

function NoStop() {
  const { t } = useTranslation();
  const go = useGo();
  return (
    <ScreenBody>
      <Notice tone="info">{t('field.reads.common.noStop')}</Notice>
      <Button testID="door-RW-05" onPress={() => go('RW-05')}>
        {t('field.reads.common.theWalk')}
      </Button>
    </ScreenBody>
  );
}

// ── RW-06 The stop ──────────────────────────────────────────────────────────

export function TheStop() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s, settings } = useReads();
  const { stop } = useLive(() => resolveAll(s, params), [params.stopId, params.readId, params.routeId]);
  const meters = useLive(() => (stop ? walkQ.metersAtStop(s, stop.id) : []), [stop?.id]);
  // RW-06 T: beside the meter, a meter's card picks it (the first unread
  // until one is) and the picked one is ruled heavy.
  const pick = usePick();
  useDefaultSelection((meters.find((m) => m.state === 'unread') ?? meters[0])?.id ?? null);
  if (!stop) return <NoStop />;
  const masters = new Set(meters.filter((m) => m.parent_asset_id).map((m) => m.parent_asset_id));
  const top = meters.filter((m) => !m.parent_asset_id);
  const firstUnread = meters.find((m) => m.state === 'unread') ?? null;
  const done = meters.filter((m) => m.state !== 'unread').length;
  // R83/RW-29: with *Scan before reading* on, a meter is confirmed by its badge first.
  const open = (m: walkQ.MeterRead) => go(settings.scanFirst ? 'RW-11' : 'RW-09', { readId: m.id });
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button grow disabled={!firstUnread} testID="door-RW-17" onPress={() => firstUnread && go('RW-17', { readId: firstUnread.id })}>
            {t('field.reads.rw06.cantRead')}
          </Button>
          <Button variant="primary" grow disabled={!firstUnread} testID="door-RW-09" onPress={() => firstUnread && open(firstUnread)}>
            {t('field.reads.rw06.start')}
          </Button>
        </ActionBar>
      }
    >
      <Spread>
        <AppText variant="title" testID="stop-address">
          {streetOf(stop)}
        </AppText>
        <AppText variant="label" weight="heavy" testID="stop-count">
          {t('field.reads.common.nOfM', { n: done, m: meters.length })}
        </AppText>
      </Spread>
      {stop.hazard ? (
        <Notice tone="danger" testID="stop-hazard">
          {stop.hazard}
        </Notice>
      ) : null}
      <Card>
        <ListRow label={t('field.reads.rw06.access')} onPress={() => go('RW-07', { stopId: stop.id })} testID="door-RW-07" />
      </Card>
      <Kicker>{t('field.reads.rw06.metersHere', { n: meters.length })}</Kicker>
      {top.map((m) => {
        const isMaster = masters.has(m.asset_id);
        const subs = meters.filter((x) => x.parent_asset_id === m.asset_id);
        const unit = unitLabel(m);
        return (
          <PressCard
            key={m.id}
            label={[unit, m.customer_name, m.account_number, meterName(m)].filter(Boolean).join(', ')}
            emphasis={(pick.active ? pick.isPicked(m.id) : m.id === firstUnread?.id) ? 'strong' : isMaster ? 'info' : 'none'}
            onPress={pick.active ? () => pick.pick(m.id) : undefined}
            testID={`meter-${m.id}`}
          >
            {isMaster ? <Kicker tone="brand">{t('field.reads.rw06.masterAndSubs', { n: subs.length })}</Kicker> : null}
            {unit ? <Kicker>{unit}</Kicker> : null}
            <AppText variant="section" testID={`customer-${m.id}`}>
              {m.customer_name ?? t('field.reads.common.noCustomer')}
            </AppText>
            {m.account_number ? (
              <AppText variant="label" tone="muted" testID={`account-${m.id}`}>
                {m.account_number}
              </AppText>
            ) : null}
            <View style={{ borderTopColor: theme.colors.divider, borderTopWidth: theme.borderWidth.divider, paddingTop: theme.space[2] }}>
              <Spread>
                <AppText variant="label" tone="muted">
                  {isMaster
                    ? t('field.reads.rw06.readings', { meter: meterName(m), n: subs.length + 1 })
                    : m.badge
                      ? t('field.reads.common.meterBadge', { meter: meterName(m), badge: m.badge })
                      : meterName(m)}
                </AppText>
                {isMaster ? (
                  <Button size="sm" testID="door-RW-12" onPress={() => go('RW-12', { readId: m.id })}>
                    {t('field.reads.rw06.readAll')}
                  </Button>
                ) : m.state === 'unread' ? (
                  <Button size="sm" testID={`read-${m.id}`} onPress={() => open(m)}>
                    {t('field.reads.rw06.read')}
                  </Button>
                ) : (
                  <ReaderStatusChip status={m.reader_status} />
                )}
              </Spread>
            </View>
          </PressCard>
        );
      })}
      <Button testID="door-RW-19" onPress={() => go('RW-19', { stopId: stop.id })}>
        {t('field.reads.rw06.notListed')}
      </Button>
    </ScreenBody>
  );
}

// ── RW-07 Getting in ────────────────────────────────────────────────────────

/**
 * What the property says about getting to its meters. Held on the PREMISES
 * (one record for jobs and reads alike), so it is read here and never typed
 * into a second place. ⚠ *Add a note for next time* is not built: no server
 * door takes a premises note from the handset yet — reported, not faked.
 */
export function GettingIn() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const { s } = useReads();
  const { stop } = useLive(() => resolveAll(s, params), [params.stopId, params.readId]);
  if (!stop) return <NoStop />;
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button variant="primary" grow testID="door-RW-06" onPress={() => go('RW-06', { stopId: stop.id })}>
            {t('field.reads.rw07.back')}
          </Button>
        </ActionBar>
      }
    >
      <AppText variant="title">{streetOf(stop)}</AppText>
      {stop.hazard ? (
        <Card tone="danger" title={t('field.reads.rw07.hazard')}>
          <AppText variant="body" testID="getting-in-hazard">
            {stop.hazard}
          </AppText>
        </Card>
      ) : null}
      <Card title={t('field.reads.rw07.access')}>
        <AppText variant="body" testID="getting-in-notes">
          {stop.access_notes ?? t('field.reads.rw07.noNotes')}
        </AppText>
      </Card>
    </ScreenBody>
  );
}

// ── RW-08 Find a meter ──────────────────────────────────────────────────────

export function FindMeter() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const { s, services } = useReads();
  const [text, setText] = useState('');
  const [scanFailed, setScanFailed] = useState(false);
  const hits = useLive(() => (text.trim().length >= 2 ? walkQ.findOnPhone(s, text, 50) : []), [text]);
  const scan = async () => {
    try {
      const code = await services.scanner.scan();
      if (!code) return;
      const found = assetQ.matchScannedCode(services.db, code);
      const mine = found ? walkQ.anyMeterForAsset(s, found.asset.id) : undefined;
      if (mine) go('RW-09', { readId: mine.id });
      else go('RW-19', { code });
    } catch {
      setScanFailed(true);
    }
  };
  return (
    <ScreenBody>
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: theme.touch.clear }}>
        <View style={{ flex: 1 }}>
          <Field
            label={t('field.reads.rw08.search')}
            value={text}
            onChangeText={setText}
            help={t('field.reads.rw08.help')}
            testID="find-input"
          />
        </View>
        <IconButton outlined label={t('field.reads.rw08.scan')} onPress={() => void scan()} disabled={!services.scanner.available} testID="door-RW-19">
          <AppText variant="section">⌗</AppText>
        </IconButton>
      </View>
      {!services.scanner.available || scanFailed ? <Notice tone="info">{t('field.reads.common.noScanner')}</Notice> : null}
      {text.trim().length >= 2 ? <Kicker>{t('field.reads.rw08.onPhone', { n: hits.length })}</Kicker> : null}
      {hits.map((m, i) => (
        <PressCard
          key={m.id}
          label={meterName(m)}
          onPress={() => go('RW-09', { readId: m.id })}
          testID={i === 0 ? 'door-RW-09' : `hit-${m.id}`}
        >
          <Spread>
            <View style={{ flexShrink: 1 }}>
              <AppText variant="body" weight="heavy">
                {m.badge ? t('field.reads.common.meterBadge', { meter: meterName(m), badge: m.badge }) : meterName(m)}
              </AppText>
              <AppText variant="label" tone="muted">
                {[m.address_line, unitLabel(m), m.customer_name].filter(Boolean).join(' · ')}
              </AppText>
            </View>
            {m.no_read_reason ? <StatusChip tone="warning">{m.no_read_reason}</StatusChip> : <ReaderStatusChip status={m.reader_status} />}
          </Spread>
        </PressCard>
      ))}
      <Notice tone="warning">{t('field.reads.rw08.phoneOnly')}</Notice>
      <Button testID="door-RW-01" onPress={() => go('RW-01')}>
        {t('field.reads.common.myRoutes')}
      </Button>
    </ScreenBody>
  );
}

// ── RW-12 Master and subs ───────────────────────────────────────────────────

/** RW-12's *So far*: the master less its read subs, only when every figure carries the master's unit. */
export function masterBalance(master: walkQ.MeterRead, subs: readonly walkQ.MeterRead[]) {
  const readSubs = subs.filter((m) => m.value !== null);
  const sameUnit = [master, ...subs].every((m) => m.unit === master.unit);
  const balance =
    master.value !== null && sameUnit && readSubs.length > 0
      ? { subs: add(readSubs.map((m) => m.value as string)), left: subtract(master.value, add(readSubs.map((m) => m.value as string))) }
      : null;
  return { readSubs, sameUnit, balance };
}

/** The *So far* card — the phone's under the subs, the tablet's beside them (RW-12 T). */
export function BalanceCard({ master, subs }: { master: walkQ.MeterRead; subs: readonly walkQ.MeterRead[] }) {
  const { t } = useTranslation();
  const { readSubs, sameUnit, balance } = masterBalance(master, subs);
  return (
    <>
      {balance ? (
        <Card title={t('field.reads.rw12.soFar')} testID="balance">
          <ListRow label={t('field.reads.rw12.master')} value={`${group(master.value as string)} ${master.unit}`} />
          <ListRow divider label={t('field.reads.rw12.subsTotal', { n: readSubs.length })} value={`${group(balance.subs)} ${master.unit}`} />
          <ListRow divider label={t('field.reads.rw12.stillToFind')} value={`${group(balance.left)} ${master.unit}`} testID="still-to-find" />
        </Card>
      ) : null}
      {!sameUnit ? <Notice tone="warning">{t('field.reads.rw12.mixedUnits')}</Notice> : null}
    </>
  );
}

export function MasterAndSubs() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const { s } = useReads();
  const master = useLive(() => resolveAll(s, params).meter, [params.readId, params.stopId]);
  const subs = useLive(() => (master ? walkQ.subsOf(s, master.route_id, master.asset_id) : []), [master?.id]);
  const pick = usePick();
  if (!master) return <NoStop />;
  const all = [master, ...subs];
  const next = all.find((m) => m.state === 'unread') ?? null;
  const done = all.filter((m) => m.state !== 'unread').length;
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button grow disabled={!next} testID="door-RW-17" onPress={() => next && go('RW-17', { readId: next.id })}>
            {t('field.reads.rw06.cantRead')}
          </Button>
          <Button variant="primary" grow disabled={!next} testID="door-RW-09" onPress={() => next && go('RW-09', { readId: next.id })}>
            {next ? t('field.reads.rw12.readNext', { name: unitLabel(next) ?? meterName(next) }) : t('field.reads.rw12.allRead')}
          </Button>
        </ActionBar>
      }
    >
      <Spread>
        <AppText variant="title">{t('field.screen.rw12')}</AppText>
        <AppText variant="label" weight="heavy">
          {t('field.reads.common.nOfM', { n: done, m: all.length })}
        </AppText>
      </Spread>
      <Card tone="info" title={t('field.reads.rw12.master')}>
        <Spread>
          <View style={{ flexShrink: 1 }}>
            <AppText variant="body" weight="heavy">
              {master.customer_name ?? t('field.reads.common.noCustomer')}
            </AppText>
            <AppText variant="label" tone="muted">
              {[meterName(master), master.account_number].filter(Boolean).join(' · ')}
            </AppText>
          </View>
          {master.value !== null ? (
            <Figure value={master.value} unit={master.unit} testID="master-figure" />
          ) : (
            <Button size="sm" testID={`read-${master.id}`} onPress={() => go('RW-09', { readId: master.id })}>
              {t('field.reads.rw06.read')}
            </Button>
          )}
        </Spread>
      </Card>
      <Kicker>{t('field.reads.rw12.subMeters', { n: subs.length })}</Kicker>
      <Card>
        {subs.map((m, i) => (
          <ListRow
            key={m.id}
            divider={i > 0}
            label={unitLabel(m) ?? meterName(m)}
            detail={meterName(m)}
            value={m.value !== null ? group(m.value) : m.reader_status === 'could_not_read' ? t('field.reads.status.couldNot') : t('field.reads.rw06.read')}
            onPress={m.state === 'unread' ? () => go('RW-09', { readId: m.id }) : undefined}
            testID={`sub-${m.id}`}
          />
        ))}
      </Card>
      {/* RW-12 T draws the balance beside the subs instead (the layout's detail). */}
      {pick.active ? null : <BalanceCard master={master} subs={subs} />}
    </ScreenBody>
  );
}
