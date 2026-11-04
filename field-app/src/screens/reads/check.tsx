/**
 * When a reading needs a second thought — RW-15 High or low, RW-16 Second
 * look, RW-17 Can't read, RW-18 Different meter (EP-FLD-12, EP-FLD-13).
 * Built from `wireframes/reads/RW-15…18*.png`.
 *
 * R80: warned, never blocked — RW-15 offers a re-read FIRST and accepting
 * second, and accepting keeps the figure flagged for the office (*Read with a
 * problem*, R96). R81: below last month is its own warning, not "low".
 * RW-16 keeps BOTH entries — the first try travels whole beside the second,
 * nothing is overwritten. R82: the reasons a meter cannot be read are the
 * utility's own list, read from data and never written in code. R83/RW-18: a
 * badge that is not the one on the list is never guessed — the plate photo
 * is required and the reader says what is true.
 *
 * ⚠ RW-15 draws *Usual month 7,800 gal* — a typical month's use. No column on
 * the handset carries it (the route download has last month's reading and an
 * expected range only), so it is left out rather than computed from a guess;
 * reported as a download gap.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { ActionBar, AppText, Button, Card, Keypad, Kicker, ListRow, Notice, RadioList, StatusChip } from '../../components';
import * as assetQ from '../../db/queries/asset';
import * as premiseQ from '../../db/queries/premise';
import * as walkQ from '../../db/queries/readsWalk';
import { capture } from '../../sync/outbox';
import { useTheme } from '../../theme';
import { saveReading } from './acts';
import { group, needsWarning, used, verdict } from './figures';
import { Figure, MeterLine, PhotoAsk, Spread, verdictKey } from './parts';
import { ScreenBody, useGo, useLive, useParams } from './ReadsScreen';
import { useReadForm } from './ReadQuestions';
import { DraftPhotos } from './ReadingPhotos';
import { CantReadReasonPicker, cantReadReasons } from './CantReadReasonPicker';
import { meterName, resolveAll } from './records';
import { type ReadDraft, useReads } from './services';

function NoMeter() {
  const { t } = useTranslation();
  const go = useGo();
  return (
    <ScreenBody>
      <Notice tone="info">{t('field.reads.common.noMeter')}</Notice>
      <Button testID="door-RW-06" onPress={() => go('RW-06')}>
        {t('field.reads.common.theStop')}
      </Button>
    </ScreenBody>
  );
}

function hhmm(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

// ── RW-15 High or low ───────────────────────────────────────────────────────

export function HighOrLow() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const ctx = useReads();
  const { s, services, bump } = ctx;
  const { route, meter: m } = useLive(() => resolveAll(s, params), [params.readId]);
  const [busy, setBusy] = useState(false);
  const [, redraw] = useState(0);
  const form = useReadForm(m);
  if (!m) return <NoMeter />;
  const draft = ctx.draft(m.id);
  const value = draft.value;
  if (!value) {
    return (
      <ScreenBody>
        <Notice tone="info">{t('field.reads.rw15.nothingTyped')}</Notice>
        <Button variant="primary" testID="door-RW-09" onPress={() => go('RW-09', { readId: m.id })}>
          {t('field.reads.rw15.typeIt')}
        </Button>
      </ScreenBody>
    );
  }
  const v = verdict(value, m.previous_value, m.expected_min, m.expected_max);
  const usedNow = used(value, m.previous_value);
  const photoNeeded = m.photo_required === 1 && draft.photos.length === 0;
  const accept = async () => {
    setBusy(true);
    try {
      // MQ-033: accepting a warned figure is what makes it *out of range*.
      await form.saveWith(needsWarning(v) ? 'read_with_problem' : 'read', needsWarning(v), async (answers) => {
        await saveReading(services, m, draft, {
          readerStatus: needsWarning(v) ? 'read_with_problem' : 'read',
          warnedAccepted: needsWarning(v),
          readMethod: route?.read_type ?? null,
          form: answers,
        });
        ctx.clearDraft(m.id);
        bump();
        go('RW-06', { stopId: m.stop_id });
      });
    } finally {
      setBusy(false);
    }
  };
  return (
    <ScreenBody
      bar={
        <ActionBar note={photoNeeded ? t('field.reads.rw09.photoFirst') : t('field.reads.rw15.flagged')}>
          <Button variant="danger" grow busy={busy} disabled={photoNeeded} testID="door-RW-06" onPress={() => void accept()}>
            {t('field.reads.rw15.accept', { value: group(value) })}
          </Button>
        </ActionBar>
      }
    >
      <Card tone="warning" title={t(verdictKey(v))} testID="warning-card">
        <ListRow label={t('field.reads.rw15.youTyped')} value={`${group(value)} ${m.unit}`} testID="you-typed" />
        <ListRow
          divider
          label={t('field.reads.common.expected')}
          value={m.expected_min && m.expected_max ? `${group(m.expected_min)}–${group(m.expected_max)}` : t('field.reads.common.none')}
        />
        <ListRow divider label={t('field.reads.common.lastMonth')} value={m.previous_value ? group(m.previous_value) : t('field.reads.common.none')} />
        {usedNow !== null ? (
          <ListRow
            divider
            label={t('field.reads.rw15.wouldBe')}
            value={<AppText variant="section" style={{ color: theme.colors.statusInk.warning }} testID="would-be">{`${group(usedNow)} ${m.unit}`}</AppText>}
          />
        ) : null}
      </Card>
      <Card title={t('field.reads.rw15.often')}>
        <AppText variant="body">{t('field.reads.rw15.causes')}</AppText>
      </Card>
      <Button
        variant="primary"
        testID="door-RW-16"
        onPress={() => {
          const next: ReadDraft = { ...draft, firstTry: { value, at: services.clock.now().toISOString() }, value: '' };
          ctx.setDraft(m.id, next);
          go('RW-16', { readId: m.id });
        }}
      >
        {t('field.reads.rw15.again')}
      </Button>
      <PhotoAsk
        label={t('field.reads.rw15.photograph')}
        required={m.photo_required === 1}
        taken={draft.photos.length}
        onPress={() => go('RW-14', { readId: m.id })}
        testID="rw15-photo"
      />
      <DraftPhotos
        readId={m.id}
        photos={draft.photos}
        onChange={(photos) => {
          ctx.setDraft(m.id, { ...draft, photos });
          redraw((n) => n + 1);
        }}
      />
      {form.sheet}
    </ScreenBody>
  );
}

// ── RW-16 Second look ───────────────────────────────────────────────────────

export function SecondLook() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const ctx = useReads();
  const { s, services, bump, settings } = ctx;
  const { route, meter: m } = useLive(() => resolveAll(s, params), [params.readId]);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const form = useReadForm(m);
  if (!m) return <NoMeter />;
  const draft = ctx.draft(m.id);
  const first = draft.firstTry;
  const v = value ? verdict(value, m.previous_value, m.expected_min, m.expected_max) : 'unknown';
  const warn = needsWarning(v);
  const usedNow = value ? used(value, m.previous_value) : null;
  const photoNeeded = m.photo_required === 1 && draft.photos.length === 0;
  const save = async () => {
    setBusy(true);
    try {
      await form.saveWith(warn ? 'read_with_problem' : 'read', warn, async (answers) => {
        await saveReading(services, m, { ...draft, value }, {
          readerStatus: warn ? 'read_with_problem' : 'read',
          warnedAccepted: warn,
          readMethod: route?.read_type ?? null,
          form: answers,
        });
        ctx.clearDraft(m.id);
        bump();
        go('RW-13', { readId: m.id });
      });
    } finally {
      setBusy(false);
    }
  };
  return (
    <ScreenBody
      bar={
        <ActionBar note={photoNeeded ? t('field.reads.rw09.photoFirst') : undefined}>
          <Button variant="primary" grow busy={busy} disabled={!value || photoNeeded} testID="door-RW-13" onPress={() => void save()}>
            {value ? t('field.reads.rw16.save', { value: group(value) }) : t('field.reads.rw16.typeSecond')}
          </Button>
        </ActionBar>
      }
    >
      {first ? (
        <View style={{ backgroundColor: theme.colors.surface, padding: theme.space[3], gap: theme.space[1] }} testID="first-try">
          <Spread>
            <View>
              <Kicker>{t('field.reads.rw16.firstTry', { time: hhmm(first.at) })}</Kicker>
              <AppText variant="section" style={{ color: theme.colors.statusInk.warning }}>
                {group(first.value)}
              </AppText>
            </View>
            <StatusChip tone="warning">{t('field.reads.rw16.kept')}</StatusChip>
          </Spread>
          <AppText variant="label" tone="muted">
            {t('field.reads.rw16.bothGo')}
          </AppText>
        </View>
      ) : null}
      <Kicker>{t('field.reads.rw16.secondTry')}</Kicker>
      <Figure value={value} unit={m.unit} warn={warn} testID="second-figure" />
      {value && usedNow !== null ? (
        <Notice tone={warn ? 'warning' : 'success'} testID="second-verdict">
          {t('field.reads.rw10.used', { used: group(usedNow), unit: m.unit, verdict: t(verdictKey(v)) })}
        </Notice>
      ) : null}
      <Keypad
        value={value}
        onChange={setValue}
        clearLabel={t('field.reads.rw09.clear')}
        deleteLabel={t('field.reads.rw09.delete')}
        size={settings.keypad}
        testID="keypad2"
      />
      <Button testID="rw16-photo" onPress={() => go('RW-14', { readId: m.id })}>
        {draft.photos.length ? t('field.reads.rw09.photos', { n: draft.photos.length }) : t('field.reads.rw15.photograph')}
      </Button>
      {form.sheet}
    </ScreenBody>
  );
}

// ── RW-17 Can't read ────────────────────────────────────────────────────────

export function CantRead() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const ctx = useReads();
  const { s, services, bump } = ctx;
  const { route, meter: m } = useLive(() => resolveAll(s, params), [params.readId, params.stopId]);
  const reasons = useLive(() => cantReadReasons(services.db), []);
  const [picked, setPicked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [, redraw] = useState(0);
  const form = useReadForm(m);
  if (!m) return <NoMeter />;
  const draft = ctx.draft(m.id);
  const record = async () => {
    if (!picked) return;
    setBusy(true);
    try {
      await form.saveWith('could_not_read', false, async (answers) => {
        await saveReading(services, m, draft, { readerStatus: 'could_not_read', noReadReason: picked, readMethod: route?.read_type ?? null, form: answers });
        ctx.clearDraft(m.id);
        bump();
        go('RW-06', { stopId: m.stop_id });
      });
    } finally {
      setBusy(false);
    }
  };
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button variant="primary" grow busy={busy} disabled={!picked} testID="door-RW-06" onPress={() => void record()}>
            {t('field.reads.rw17.record')}
          </Button>
        </ActionBar>
      }
    >
      <MeterLine m={m} />
      {/* DEF-MET-10609 — the ONE picker, shared with FF-20's *Unable to read*. */}
      <CantReadReasonPicker reasons={reasons} selected={picked} onSelect={setPicked} />
      <PhotoAsk
        label={draft.photos.length ? t('field.reads.rw09.photos', { n: draft.photos.length }) : t('field.reads.rw17.photo')}
        required={false}
        taken={draft.photos.length}
        onPress={() => go('RW-14', { readId: m.id })}
        testID="rw17-photo"
      />
      <DraftPhotos
        readId={m.id}
        photos={draft.photos}
        onChange={(photos) => {
          ctx.setDraft(m.id, { ...draft, photos });
          redraw((n) => n + 1);
        }}
      />
      <Button variant="danger" testID="door-RW-21" onPress={() => go('RW-21', { readId: m.id })}>
        {t('field.reads.rw17.raise')}
      </Button>
      <Button testID="door-RW-09" onPress={() => go('RW-09', { readId: m.id })}>
        {t('field.reads.rw17.backToRead')}
      </Button>
      {form.sheet}
    </ScreenBody>
  );
}

// ── RW-18 Different meter ───────────────────────────────────────────────────

type Truth = 'swapped' | 'wrong_address' | 'cannot_tell';

/**
 * The listed meter and the scanned one, side by side, and the reader says
 * which is true. Nothing is read against the wrong record: *swapped* reads the
 * scanned meter where it is (on this route if it is on it, otherwise as an
 * off-route reading through RW-19); *wrong address* goes to the scanned
 * meter's own stop; *cannot tell* sends the plates to the office. Every
 * choice sends the office the mismatch with the plate photograph, which is
 * required (US-FLD-061 TC-3).
 */
export function DifferentMeter() {
  const { t } = useTranslation();
  const go = useGo();
  const params = useParams();
  const { s, services, bump } = useReads();
  const { meter: m } = useLive(() => resolveAll(s, params), [params.readId]);
  const scanned = useLive(() => (params.code ? assetQ.matchScannedCode(services.db, params.code)?.asset ?? null : null), [params.code]);
  const scannedHere = useLive(() => (scanned ? walkQ.anyMeterForAsset(s, scanned.id) ?? null : null), [scanned?.id]);
  const recordedAt = useLive(() => (scanned?.premise_id ? premiseQ.get(services.db, scanned.premise_id) ?? null : null), [scanned?.premise_id]);
  const [truth, setTruth] = useState<Truth | null>(null);
  const [plate, setPlate] = useState<ReadDraft['photos']>([]);
  const [failed, setFailed] = useState(false);
  if (!m) return <NoMeter />;
  const shoot = async () => {
    try {
      const shot = await services.camera.take([services.clock.now().toISOString(), services.readerName, meterName(m)]);
      setPlate([...plate, shot]);
    } catch {
      setFailed(true);
    }
  };
  const send = () => {
    if (!truth) return;
    capture(
      services.db,
      { technicianId: services.technicianId, capturedBy: services.capturedBy },
      {
        kind: 'route_finding',
        routeId: m.route_id,
        payload: {
          mismatch: truth,
          listed_asset_id: m.asset_id,
          // BR-WRK-067: the stop it was found at, so the office sees where.
          premise_id: m.premise_id,
          scanned_code: params.code ?? null,
          scanned_asset_id: scanned?.id ?? null,
          route_read_id: m.id,
        },
        photos: plate.map((p) => ({ ...p, target: { route_read_id: m.id } })),
      },
      { newId: () => services.newId(), clock: services.clock },
    );
    bump();
    if (truth === 'swapped') {
      if (scannedHere) go('RW-09', { readId: scannedHere.id });
      else go('RW-19', { code: params.code, stopId: m.stop_id });
    } else if (truth === 'wrong_address' && scannedHere) go('RW-06', { stopId: scannedHere.stop_id });
    else go('RW-06', { stopId: m.stop_id });
  };
  const truths: Array<{ id: Truth; label: string }> = [
    { id: 'swapped', label: t('field.reads.rw18.swapped') },
    { id: 'wrong_address', label: t('field.reads.rw18.wrongAddress') },
    { id: 'cannot_tell', label: t('field.reads.rw18.cannotTell') },
  ];
  return (
    <ScreenBody
      bar={
        <ActionBar note={plate.length === 0 ? t('field.reads.rw18.plateFirst') : undefined}>
          <Button variant="primary" grow disabled={!truth || plate.length === 0} testID="door-RW-09" onPress={send}>
            {truth === 'swapped' && scanned
              ? t('field.reads.rw18.readScanned', { meter: scanned.serial ?? scanned.badge ?? '' })
              : t('field.reads.rw18.send')}
          </Button>
        </ActionBar>
      }
    >
      <Notice tone="danger">{t('field.reads.rw18.notOnList')}</Notice>
      <Card title={t('field.reads.rw18.listSays')}>
        <AppText variant="section">{meterName(m)}</AppText>
        <AppText variant="label" tone="muted">
          {[m.badge && t('field.reads.rw18.badge', { badge: m.badge }), m.size].filter(Boolean).join(' · ')}
        </AppText>
      </Card>
      <Card title={t('field.reads.rw18.youScanned')} testID="scanned-card">
        <AppText variant="section">{scanned ? scanned.serial ?? scanned.badge ?? '' : params.code ?? '—'}</AppText>
        {scanned ? (
          <AppText variant="label" tone="muted">
            {[scanned.badge && t('field.reads.rw18.badge', { badge: scanned.badge }), scanned.size].filter(Boolean).join(' · ')}
          </AppText>
        ) : (
          <AppText variant="label" tone="muted">
            {t('field.reads.rw18.unknown')}
          </AppText>
        )}
        {recordedAt?.address_line ? <Notice tone="warning">{t('field.reads.rw18.recordedAt', { address: recordedAt.address_line })}</Notice> : null}
      </Card>
      <RadioList label={t('field.reads.rw18.whatIsTrue')} options={truths} selected={truth} onSelect={(id) => setTruth(id as Truth)} testID="truth" />
      <PhotoAsk
        label={plate.length ? t('field.reads.rw09.photos', { n: plate.length }) : t('field.reads.rw18.plate')}
        required
        taken={plate.length}
        disabled={!services.camera.available}
        onPress={() => void shoot()}
        testID="plate-photo"
      />
      {!services.camera.available || failed ? <Notice tone="warning">{t('field.reads.rw14.noCamera')}</Notice> : null}
      <Button testID="door-RW-11" onPress={() => go('RW-11', { readId: m.id })}>
        {t('field.reads.rw18.scanAgain')}
      </Button>
    </ScreenBody>
  );
}
