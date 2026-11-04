/**
 * Off the list — RW-19 Not on the route, RW-20 Add a meter, RW-21 Raise it
 * (EP-FLD-13). Built from `wireframes/reads/RW-19…21*.png`.
 *
 * R84: a meter the system knows that is not on the route is read anyway and
 * marked off-route; the office decides where it belongs. R85: a meter the
 * system does not know is added PENDING with a required photo and bills only
 * once the office accepts it. R86: its address is the premises the reader is
 * standing at — confirmable, never typed. RW-21: what the reader found goes to
 * the office with the place filled in for them and a required photograph.
 *
 * ⚠ THE LISTS ON THESE SCREENS ARE THE UTILITY'S, AND NONE IS ON THE HANDSET
 * YET: services and sizes (RW-20: *"the utility's own list, however long it
 * is"*), findings and urgency (RW-21). Each is read from `settings` where the
 * route download will put it; until then the screen says the list is missing
 * rather than offering one written in code (R82's reasoning).
 *
 * ⚠ AN OFF-ROUTE READING NEEDS ITS UNIT (hard rule 3), and the handset's asset
 * row has no unit column. It is read from the asset's downloaded `extra.unit`;
 * with no unit known, *Read it anyway* is unavailable and says why.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ActionBar, AppText, Button, Card, ChoiceChips, Field, ListRow, Notice, RadioList, StatusChip } from '../../components';
import { fromJson } from '../../db/json';
import * as assetQ from '../../db/queries/asset';
import * as outboxQ from '../../db/queries/outbox';
import * as templateSearchQ from '../../db/queries/templateSearch';
import * as premiseQ from '../../db/queries/premise';
import * as settingsQ from '../../db/queries/settings';
import * as walkQ from '../../db/queries/readsWalk';
import { useTheme } from '../../theme';
import { addMeter, raiseIt, readOffRoute } from './acts';
import { PhotoAsk } from './parts';
import { RemarkSheet } from './RemarkSheet';
import { ScreenBody, useGo, useLive, useParams } from './ReadsScreen';
import { asList, LIST_KEYS, meterName, resolveAll, streetOf, unitLabel } from './records';
import { type FindingsPort, type ReadDraft, useReads } from './services';
import type { WireFinding, WireFindingOptions } from '../../sync/fieldApi';

function assetUnit(a: assetQ.AssetRow): string | null {
  const extra = fromJson<Record<string, unknown>>(a.extra) ?? {};
  return typeof extra.unit === 'string' && extra.unit ? extra.unit : null;
}

/** Take a photograph straight into a screen's own list (RW-20, RW-21). */
function useShots(stamp: () => string[]) {
  const { services } = useReads();
  const [shots, setShots] = useState<ReadDraft['photos']>([]);
  const [failed, setFailed] = useState(false);
  const shoot = async () => {
    try {
      const shot = await services.camera.take(stamp());
      setShots((xs) => [...xs, shot]);
    } catch {
      setFailed(true);
    }
  };
  return { shots, shoot, failed: failed || !services.camera.available, available: services.camera.available };
}

// ── RW-19 Not on the route ──────────────────────────────────────────────────

export function NotOnRoute() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s, services, bump } = useReads();
  const { route, stop } = useLive(() => resolveAll(s, params), [params.stopId, params.routeId]);
  const [code, setCode] = useState<string | null>(params.code ?? null);
  const [typed, setTyped] = useState('');
  const [scanFailed, setScanFailed] = useState(false);
  const found = useLive(() => (code ? assetQ.matchScannedCode(services.db, code) : null), [code]);
  const where = useLive(() => (found?.asset.premise_id ? premiseQ.get(services.db, found.asset.premise_id) ?? null : null), [found?.asset.id]);
  const mine = useLive(() => (found ? walkQ.anyMeterForAsset(s, found.asset.id) ?? null : null), [found?.asset.id]);
  const scan = async () => {
    try {
      const got = await services.scanner.scan();
      if (got) setCode(got);
    } catch {
      setScanFailed(true);
    }
  };
  const unit = found ? assetUnit(found.asset) : null;
  const readAnyway = () => {
    if (!found || !route || !stop) return;
    if (mine) {
      go('RW-09', { readId: mine.id });
      return;
    }
    if (!unit) return;
    const id = readOffRoute(services, { routeId: route.id, stopId: stop.id, asset: found.asset, unit });
    bump();
    go('RW-09', { readId: id });
  };
  return (
    <ScreenBody>
      <View
        testID="viewfinder"
        style={{ minHeight: theme.touch.primary * 2, backgroundColor: theme.colors.toastFill, alignItems: 'center', justifyContent: 'center', padding: theme.space[3] }}
      >
        <AppText variant="body" style={{ color: theme.colors.toastText }}>
          {services.scanner.available ? t('field.reads.rw11.point') : t('field.reads.common.noScanner')}
        </AppText>
      </View>
      {services.scanner.available ? (
        <Button testID="scan-again" onPress={() => void scan()}>
          {t('field.reads.rw11.scanAgain')}
        </Button>
      ) : null}
      {scanFailed ? <Notice tone="warning">{t('field.reads.common.noScanner')}</Notice> : null}
      {!code ? (
        <>
          <Field label={t('field.reads.rw11.badgeOrSerial')} value={typed} onChangeText={setTyped} testID="typed-code" />
          <Button disabled={!typed.trim()} testID="typed-code-ok" onPress={() => setCode(typed.trim())}>
            {t('field.reads.rw11.check')}
          </Button>
        </>
      ) : null}
      {code && found ? (
        <>
          <Notice tone="success" testID="known">
            {t('field.reads.rw19.known', { code })}
          </Notice>
          <Card testID="known-card">
            <AppText variant="section">{found.asset.serial ?? found.asset.badge ?? code}</AppText>
            <ListRow label={t('field.reads.rw19.badge')} value={found.asset.badge ?? '—'} />
            <ListRow divider label={t('field.reads.rw19.service')} value={found.asset.service ?? '—'} />
            <ListRow divider label={t('field.reads.rw19.where')} value={where?.address_line ?? '—'} />
            <ListRow divider label={t('field.reads.rw19.route')} value={mine ? (mine.route_id === route?.id ? route.code ?? '' : mine.route_id) : t('field.reads.common.none')} />
          </Card>
          <Button variant="primary" disabled={!mine && (!unit || !stop)} testID="door-RW-09" onPress={readAnyway}>
            {t('field.reads.rw19.readAnyway')}
          </Button>
          <AppText variant="label" tone="muted" style={{ textAlign: 'center' }}>
            {!mine && !unit ? t('field.reads.rw19.noUnit') : t('field.reads.rw19.offRoute')}
          </AppText>
        </>
      ) : null}
      {code && !found ? (
        <Notice tone="danger" testID="unknown">
          {t('field.reads.rw19.unknown', { code })}
        </Notice>
      ) : null}
      <Button testID="door-RW-20" onPress={() => go('RW-20', { code: code ?? undefined, stopId: stop?.id })}>
        {t('field.reads.rw19.add')}
      </Button>
      <Button testID="door-RW-06" onPress={() => go('RW-06', stop ? { stopId: stop.id } : undefined)}>
        {t('field.reads.common.theStop')}
      </Button>
    </ScreenBody>
  );
}

// ── RW-20 Add a meter ───────────────────────────────────────────────────────

export function AddMeter() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const { s, services, bump } = useReads();
  const { route, stop } = useLive(() => resolveAll(s, params), [params.stopId, params.routeId]);
  const services_ = useLive(() => asList(settingsQ.get(services.db, LIST_KEYS.services)), []);
  const sizes = useLive(() => asList(settingsQ.get(services.db, LIST_KEYS.sizes)), []);
  const [badge, setBadge] = useState(params.code ?? '');
  const [serial, setSerial] = useState('');
  const [service, setService] = useState<string | null>(null);
  const [size, setSize] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const photos = useShots(() => [services.clock.now().toISOString(), services.readerName, badge, route?.code ?? '']);
  const ready = !!stop && !!route && !!service && !!size && photos.shots.length > 0 && (!!badge.trim() || !!serial.trim());
  const send = async () => {
    if (!ready || !stop || !route || !service || !size) return;
    setBusy(true);
    try {
      await addMeter(services, {
        routeId: route.id,
        premiseId: stop.premise_id,
        badge: badge.trim() || null,
        serial: serial.trim() || null,
        service,
        size,
        photos: photos.shots,
      });
      bump();
      go('RW-06', { stopId: stop.id });
    } finally {
      setBusy(false);
    }
  };
  return (
    <ScreenBody
      bar={
        <ActionBar note={t('field.reads.rw20.billsOnce')}>
          <Button variant="primary" grow busy={busy} disabled={!ready} testID="door-RW-06" onPress={() => void send()}>
            {t('field.reads.rw20.send')}
          </Button>
        </ActionBar>
      }
    >
      <Notice tone="danger">{params.code ? t('field.reads.rw20.notInSystem', { code: params.code }) : t('field.reads.rw20.newMeter')}</Notice>
      <Card>
        <Field label={t('field.reads.rw20.badge')} value={badge} onChangeText={setBadge} help={params.code ? t('field.reads.rw20.fromBarcode') : undefined} testID="add-badge" />
        {params.code ? <StatusChip tone="success">{t('field.reads.rw20.scanned')}</StatusChip> : null}
      </Card>
      <Card>
        <Field label={t('field.reads.rw20.serial')} value={serial} onChangeText={setSerial} placeholder={t('field.reads.rw20.typeOrScan')} testID="add-serial" />
      </Card>
      <Card title={t('field.reads.rw20.service')}>
        {services_ && services_.length ? (
          <ChoiceChips label={t('field.reads.rw20.service')} segments={services_.map((x) => ({ id: x.code, label: x.label }))} active={service} onSelect={setService} testID="add-service" />
        ) : (
          <Notice tone="warning">{t('field.reads.rw20.noList')}</Notice>
        )}
      </Card>
      <Card title={t('field.reads.rw20.size')}>
        {sizes && sizes.length ? (
          <ChoiceChips label={t('field.reads.rw20.size')} segments={sizes.map((x) => ({ id: x.code, label: x.label }))} active={size} onSelect={setSize} testID="add-size" />
        ) : (
          <Notice tone="warning">{t('field.reads.rw20.noList')}</Notice>
        )}
      </Card>
      <Card title={t('field.reads.rw20.where')}>
        <AppText variant="body" weight="semibold" testID="add-where">
          {stop ? streetOf(stop) : t('field.reads.common.none')}
        </AppText>
      </Card>
      <PhotoAsk
        label={photos.shots.length ? t('field.reads.rw09.photos', { n: photos.shots.length }) : t('field.reads.rw20.photo')}
        required
        taken={photos.shots.length}
        disabled={!photos.available}
        onPress={() => void photos.shoot()}
        testID="add-photo"
      />
      {photos.failed ? <Notice tone="warning">{t('field.reads.rw14.noCamera')}</Notice> : null}
      <Button testID="door-RW-19" onPress={() => go('RW-19', stop ? { stopId: stop.id } : undefined)}>
        {t('field.reads.common.back')}
      </Button>
    </ScreenBody>
  );
}

// ── RW-21 Raise it ──────────────────────────────────────────────────────────

export function RaiseIt() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const { s, services, here, bump } = useReads();
  const { route, meter: m } = useLive(() => resolveAll(s, params), [params.readId, params.stopId]);
  const findings = useLive(() => asList(settingsQ.get(services.db, LIST_KEYS.raiseFindings)), []);
  const urgency = useLive(() => asList(settingsQ.get(services.db, LIST_KEYS.raiseUrgency)), []);
  useFindingLists(services.findings, findings === null, (opts) => {
    // BR-WRK-067: the server owns the list a rule matches on. Kept on the
    // phone so RW-21 works without signal next time; words come from the
    // catalogue by code (`field.reads.finding.*`).
    const at = services.clock.now().toISOString();
    settingsQ.set(services.db, LIST_KEYS.raiseFindings, opts.kinds.map((k) => ({ code: k.code, label: k.code })), at);
    settingsQ.set(services.db, LIST_KEYS.raiseUrgency, opts.urgencies.map((u) => ({ code: u.code, label: u.code })), at);
    bump();
  });
  const [finding, setFinding] = useState<string | null>(null);
  const [urgent, setUrgent] = useState<string | null>(null);
  const [remark, setRemark] = useState<{ text: string | null; source: 'voice' | 'typed' | null }>({ text: null, source: null });
  const [remarkOpen, setRemarkOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const photos = useShots(() => [services.clock.now().toISOString(), services.readerName, m ? meterName(m) : '', route?.code ?? '']);
  if (!m) {
    return (
      <ScreenBody>
        <Notice tone="info">{t('field.reads.common.noMeter')}</Notice>
        <Button testID="door-RW-06" onPress={() => go('RW-06')}>
          {t('field.reads.common.theStop')}
        </Button>
      </ScreenBody>
    );
  }
  const ready = !!finding && photos.shots.length > 0 && (!urgency || urgency.length === 0 || !!urgent);
  const filled = [
    m.address_line,
    unitLabel(m),
    m.account_number,
    meterName(m),
    here ? `${here.lat.toFixed(4)}, ${here.lng.toFixed(4)}` : null,
  ]
    .filter(Boolean)
    .join(' · ');
  const send = async () => {
    if (!finding) return;
    setBusy(true);
    try {
      await raiseIt(services, m, { finding, urgency: urgent, remark: remark.text, remarkSource: remark.source, photos: photos.shots });
      bump();
      go('RW-06', { stopId: m.stop_id });
    } finally {
      setBusy(false);
    }
  };
  return (
    <ScreenBody
      bar={
        <ActionBar note={t('field.reads.rw21.carryOn')}>
          <Button variant="primary" grow busy={busy} disabled={!ready} testID="door-RW-06" onPress={() => void send()}>
            {t('field.reads.rw21.send')}
          </Button>
        </ActionBar>
      }
    >
      {findings && findings.length ? (
        <RadioList
          label={t('field.reads.rw21.found')}
          tone="danger"
          options={findings.map((f) => ({ id: f.code, label: t(`field.reads.finding.kind.${f.code}`, { defaultValue: f.label }) }))}
          selected={finding}
          onSelect={setFinding}
          testID="findings"
        />
      ) : (
        <Notice tone="warning" testID="no-findings">
          {t('field.reads.rw21.noList')}
        </Notice>
      )}
      <Notice tone="success" testID="filled-in">
        {t('field.reads.rw21.filled', { what: filled })}
      </Notice>
      <FindingsHere readId={m.id} />
      <PhotoAsk
        label={photos.shots.length ? t('field.reads.rw09.photos', { n: photos.shots.length }) : t('field.reads.rw21.photo')}
        required
        taken={photos.shots.length}
        disabled={!photos.available}
        onPress={() => void photos.shoot()}
        testID="raise-photo"
      />
      {photos.failed ? <Notice tone="warning">{t('field.reads.rw14.noCamera')}</Notice> : null}
      <Button testID="raise-remark" onPress={() => setRemarkOpen(true)}>
        {remark.text ? t('field.reads.rw09.remarkAdded') : t('field.reads.rw21.say')}
      </Button>
      {urgency && urgency.length ? (
        <Card title={t('field.reads.rw21.urgent')}>
          <ChoiceChips label={t('field.reads.rw21.urgent')} fill segments={urgency.map((u) => ({ id: u.code, label: t(`field.reads.finding.urgency.${u.code}`, { defaultValue: u.label }) }))} active={urgent} onSelect={setUrgent} testID="urgency" />
        </Card>
      ) : null}
      <RemarkSheet
        visible={remarkOpen}
        initial={remark.text}
        onClose={() => setRemarkOpen(false)}
        onSave={(text, source) => {
          setRemark({ text, source });
          setRemarkOpen(false);
        }}
      />
    </ScreenBody>
  );
}

// ── RW-21 · the findings already raised here (BR-WRK-067) ───────────────────

/** RW-21's lists from the server, once, when the phone holds none. */
function useFindingLists(port: FindingsPort | undefined, missing: boolean, keep: (o: WireFindingOptions) => void) {
  useEffect(() => {
    if (!port || !missing) return;
    let live = true;
    port
      .options()
      .then((o) => {
        if (live) keep(o);
      })
      .catch(() => undefined); // no signal: the screen says the list is missing
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, missing]);
}

function findingOf(row: outboxQ.OutboxRow): WireFinding | null {
  const answer = fromJson<{ finding?: WireFinding }>(row.answer);
  return answer?.finding ?? null;
}

/**
 * What was raised at this meter, and what became of it: waiting to send, the
 * job a rule made (*WO-4870 created*), or — where no rule took it — *Create
 * work order*, from the published templates on this phone (FF-62's catalogue)
 * and a priority. Online only; the server converts a finding once.
 */
export function FindingsHere({ readId }: { readId: string }) {
  const { t } = useTranslation();
  const { s, services, bump } = useReads();
  const rows = useLive(() => outboxQ.findingsAtMine(s, readId), [readId]);
  const [creating, setCreating] = useState<string | null>(null);
  if (rows.length === 0) return null;
  return (
    <Card title={t('field.reads.rw21.here')} testID="findings-here">
      {rows.map((row, i) => {
        const payload = fromJson<Record<string, unknown>>(row.payload) ?? {};
        const code = typeof payload.mismatch === 'string' ? 'meter_mismatch' : String(payload.finding ?? '');
        const finding = findingOf(row);
        const order = finding?.work_order?.order_no ?? null;
        const open = finding?.status === 'open';
        return (
          <View key={row.id}>
            <ListRow
              divider={i > 0}
              label={t(`field.reads.finding.kind.${code}`, { defaultValue: code })}
              value={
                order ? (
                  <StatusChip tone="success" testID={`finding-order-${row.id}`}>
                    {t('field.reads.rw21.order', { order })}
                  </StatusChip>
                ) : open ? (
                  <StatusChip tone="warning">{t('field.reads.rw21.open')}</StatusChip>
                ) : (
                  <StatusChip tone="neutral">{t('field.reads.rw21.waiting')}</StatusChip>
                )
              }
              testID={`finding-${row.id}`}
            />
            {open && creating !== row.id ? (
              <Button testID={`finding-create-${row.id}`} disabled={!services.findings} onPress={() => setCreating(row.id)}>
                {t('field.reads.rw21.create')}
              </Button>
            ) : null}
            {open && creating === row.id && services.findings ? (
              <CreateFromFinding
                port={services.findings}
                findingKey={row.id}
                onDone={(answer) => {
                  outboxQ.setFindingAnswerMine(s, row.id, answer);
                  setCreating(null);
                  bump();
                }}
              />
            ) : null}
          </View>
        );
      })}
    </Card>
  );
}

const TEMPLATE_ROWS = 50;

/** *Create work order*: which work (a published template), how urgent (a
 *  priority, or the template's own), then the server raises it once. */
function CreateFromFinding(props: { port: FindingsPort; findingKey: string; onDone: (answer: WireFinding) => void }) {
  const { t } = useTranslation();
  const { services } = useReads();
  const templates = useLive(() => templateSearchQ.searchPublished(services.db, '', { limit: TEMPLATE_ROWS }), []);
  const [priorities, setPriorities] = useState<WireFindingOptions['priorities']>([]);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [priorityId, setPriorityId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    props.port
      .options()
      .then((o) => {
        if (live) setPriorities(o.priorities);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [props.port]);
  const create = async () => {
    if (!templateId) return;
    setBusy(true);
    setFailed(false);
    try {
      const answer = await props.port.createWorkOrder(
        props.findingKey,
        priorityId ? { template_id: templateId, priority_id: priorityId } : { template_id: templateId },
      );
      props.onDone(answer);
    } catch {
      setFailed(true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <View testID="finding-create-form">
      {templates.length ? (
        <RadioList
          label={t('field.reads.rw21.whatWork')}
          options={templates.map((tpl) => ({ id: tpl.id, label: tpl.name }))}
          selected={templateId}
          onSelect={setTemplateId}
          testID="finding-templates"
        />
      ) : (
        <Notice tone="warning" testID="finding-no-templates">
          {t('field.reads.rw21.noTemplates')}
        </Notice>
      )}
      {priorities.length ? (
        <ChoiceChips
          label={t('field.reads.rw21.priority')}
          segments={priorities.map((p) => ({ id: p.id, label: p.name }))}
          active={priorityId}
          onSelect={setPriorityId}
          testID="finding-priority"
        />
      ) : null}
      {failed ? <Notice tone="warning">{t('field.reads.rw21.notCreated')}</Notice> : null}
      <Button variant="primary" busy={busy} disabled={!templateId} testID="finding-create-send" onPress={() => void create()}>
        {t('field.reads.rw21.create')}
      </Button>
    </View>
  );
}
