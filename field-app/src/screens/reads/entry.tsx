/**
 * Taking a reading — RW-09 Read entry, RW-10 Dials, RW-11 Scan to confirm,
 * RW-13 The reading, RW-14 The camera (EP-FLD-11, EP-FLD-12). Built from
 * `wireframes/reads/RW-09, 10, 11, 13, 14*.png`; RW-09-T puts the route and
 * the meter's place beside the keypad.
 *
 * R78 (PO ruled): last month's reading AND the expected range are both on
 * screen. R80: a figure outside them is warned, never blocked — it turns amber
 * and the button becomes *Accept anyway*, which opens RW-15's second look.
 * R89: evidence costs one tap — Photo and Remark are the only two; position,
 * time and status come from what the reader already did. R96: the reader's
 * status is derived from the act (typed → Read; accepted anyway → Read with a
 * problem), and there is no status picker. R97: the reading's own prompt
 * (`photo_required`) decides when a photo is needed — no code knows which
 * meters need one.
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { StyleSheet, View } from 'react-native';

import {
  ActionBar,
  AppText,
  Button,
  Card,
  Field,
  IconButton,
  Keypad,
  Kicker,
  ListRow,
  Notice,
  ProgressBar,
  Sheet,
  StatusChip,
} from '../../components';
import { useNavigation } from '@react-navigation/native';
import { fromJson } from '../../db/json';
import * as assetQ from '../../db/queries/asset';
import * as outboxQ from '../../db/queries/outbox';
import * as walkQ from '../../db/queries/readsWalk';
import { declareRoutePhoto } from '../../sync/outbox';
import { useSideBySide } from '../../tablet/columns';
import { useTheme, withAlpha } from '../../theme';
import { saveReading } from './acts';
import { distanceText, group, metresBetween, needsWarning, used, verdict } from './figures';
import { Figure, MeterLine, RangeStrip, ReaderStatusChip, Spread, Toolbar, verdictKey } from './parts';
import { LocationAsk } from './LocationAsk';
import { latePositionOf } from './position';
import { useReadForm } from './ReadQuestions';
import { DraftPhotos, PhotoStrip, PhotoViewer, type ShownPhoto, useViewer } from './ReadingPhotos';
import { RemarkSheet } from './RemarkSheet';
import { ScreenBody, useGo, useLive, useParams, useTablet } from './ReadsScreen';
import { meterName, resolveAll, routeName, streetOf, unitLabel } from './records';
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

function clock(d: Date): string {
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function dateTime(d: Date, withSeconds = false): string {
  const day = d.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
  const sec = withSeconds ? `:${String(d.getSeconds()).padStart(2, '0')}` : '';
  return `${day} · ${clock(d)}${sec}`;
}

/** The reading being entered, re-read from the draft whenever the screen comes back. */
function useDraftValue(readId: string | null): [ReadDraft, (next: ReadDraft) => void] {
  const ctx = useReads();
  const navigation = useNavigation();
  const [draft, setLocal] = useState<ReadDraft>(() => ctx.draft(readId ?? ''));
  useEffect(() => {
    setLocal(ctx.draft(readId ?? ''));
    return navigation.addListener('focus', () => setLocal(ctx.draft(readId ?? '')));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [readId, navigation]);
  const set = (next: ReadDraft) => {
    if (readId) ctx.setDraft(readId, next);
    setLocal(next);
  };
  return [draft, set];
}

// ── RW-09 Read entry ────────────────────────────────────────────────────────

export function ReadEntry() {
  const { t } = useTranslation();
  const theme = useTheme();
  const tablet = useTablet();
  // The route column beside the keypad only where the PANE holds two columns
  // of 260 (R122) — in the tablet's T3 frame the shared route pane carries it
  // (`tablet/RouteContextPane.tsx`), so the content stays one column.
  const sideBySide = useSideBySide();
  const go = useGo();
  const params = useParams();
  const { s, services, settings, here, bump, clearDraft } = useReads();
  const { route, stop, meter: m } = useLive(() => resolveAll(s, params), [params.readId, params.stopId]);
  const [draft, setDraft] = useDraftValue(m?.id ?? null);
  const [remarkOpen, setRemarkOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const tally = useLive(() => (route ? walkQ.tally(s, route.id) : null), [route?.id]);
  const form = useReadForm(m);
  if (!m) return <NoMeter />;
  const value = draft.value;
  const v = value ? verdict(value, m.previous_value, m.expected_min, m.expected_max) : 'unknown';
  const warn = needsWarning(v);
  const photoNeeded = m.photo_required === 1 && draft.photos.length === 0;
  const photoAsked = (m.photo_required === 1 || warn) && draft.photos.length === 0;
  const fixLine = here
    ? m.stop_lat !== null && m.stop_lng !== null
      ? t('field.reads.rw09.atMeter', { acc: Math.round(here.accuracy_m), away: distanceText(metresBetween(here, { lat: m.stop_lat, lng: m.stop_lng })) })
      : t('field.reads.rw09.fix', { acc: Math.round(here.accuracy_m) })
    : t('field.reads.rw09.noFix');
  const save = async () => {
    setBusy(true);
    try {
      // MQ-033: the utility's questions, if its route has a format; else straight through.
      await form.saveWith('read', false, async (answers) => {
        await saveReading(services, m, draft, { readerStatus: 'read', readMethod: route?.read_type ?? null, form: answers });
        clearDraft(m.id);
        bump();
        go('RW-13', { readId: m.id });
      });
    } finally {
      setBusy(false);
    }
  };
  const primary = () => {
    if (warn) {
      setDraft(draft);
      go('RW-15', { readId: m.id });
    } else if (settings.confirmEach) setConfirm(true);
    else void save();
  };
  const keypad = (
    <Keypad
      value={value}
      onChange={(next) => setDraft({ ...draft, value: next })}
      clearLabel={t('field.reads.rw09.clear')}
      deleteLabel={t('field.reads.rw09.delete')}
      size={settings.keypad}
      columns={tablet ? 2 : 3}
      testID="keypad"
    />
  );
  const evidence = (
    <View style={{ flexDirection: 'row', gap: theme.touch.clear }}>
      <Button grow variant={photoAsked ? 'danger' : 'secondary'} testID="read-photo" onPress={() => go('RW-14', { readId: m.id })}>
        {draft.photos.length ? t('field.reads.photos.add') : t('field.reads.rw09.photo')}
      </Button>
      <Button grow testID="read-remark" onPress={() => setRemarkOpen(true)}>
        {draft.remark ? t('field.reads.rw09.remarkAdded') : t('field.reads.rw09.remark')}
      </Button>
    </View>
  );
  // FB-002: the photos taken for this reading, shown — a draft until it is
  // saved, so the viewer offers Retake and Remove (PO 2026-10-27).
  const strip = <DraftPhotos readId={m.id} photos={draft.photos} onChange={(photos) => setDraft({ ...draft, photos })} />;
  const figure = (
    <View style={{ gap: theme.space[2], paddingVertical: theme.space[3] }}>
      <Figure value={value} unit={m.unit} warn={warn} testID="entry-figure" />
      {value && v !== 'unknown' ? (
        <AppText
          variant="label"
          style={{ textAlign: 'center', color: warn ? theme.colors.statusInk.warning : theme.colors.textMuted }}
          testID="entry-verdict"
        >
          {t(verdictKey(v))}
        </AppText>
      ) : (
        <AppText variant="label" tone="muted" style={{ textAlign: 'center' }}>
          {t('field.reads.rw09.hint')}
        </AppText>
      )}
    </View>
  );
  const bar = (
    <ActionBar note={photoNeeded && !warn ? t('field.reads.rw09.photoFirst') : undefined}>
      <Button grow testID="door-RW-17" onPress={() => go('RW-17', { readId: m.id })}>
        {t('field.reads.rw09.cantRead')}
      </Button>
      <Button
        variant="primary"
        grow
        busy={busy}
        disabled={!value || (photoNeeded && !warn)}
        testID={warn ? 'door-RW-15' : 'door-RW-13'}
        onPress={primary}
      >
        {warn ? t('field.reads.rw09.acceptAnyway') : t('field.reads.rw09.save')}
      </Button>
    </ActionBar>
  );
  const head = (
    <>
      <Toolbar>
        <Button size="sm" testID="door-RW-10" onPress={() => go('RW-10', { readId: m.id })}>
          {t('field.reads.rw09.dials')}
        </Button>
        <IconButton label={t('field.reads.rw09.scan')} onPress={() => go('RW-11', { readId: m.id })} testID="door-RW-11">
          <AppText variant="section">⌗</AppText>
        </IconButton>
      </Toolbar>
      <MeterLine
        m={m}
        trailing={
          <Spread>
            <AppText variant="label" weight="semibold" style={{ color: here ? theme.colors.statusInk.success : theme.colors.statusInk.warning }} testID="fix-line">
              {fixLine}
            </AppText>
            <AppText variant="label" tone="muted">
              {dateTime(services.clock.now())}
            </AppText>
          </Spread>
        }
      />
      <RangeStrip m={m} />
    </>
  );
  const sheets = (
    <>
      <RemarkSheet
        visible={remarkOpen}
        initial={draft.remark}
        onClose={() => setRemarkOpen(false)}
        onSave={(text, source) => {
          setDraft({ ...draft, remark: text, remarkSource: source });
          setRemarkOpen(false);
        }}
      />
      <Sheet
        visible={confirm}
        onClose={() => setConfirm(false)}
        title={t('field.reads.rw09.confirmTitle', { value: value ? group(value) : '', unit: m.unit })}
        closeLabel={t('field.reads.common.close')}
        testID="confirm-sheet"
        footer={
          <>
            <Button grow onPress={() => setConfirm(false)} testID="confirm-no">
              {t('field.reads.rw09.confirmNo')}
            </Button>
            <Button
              variant="primary"
              grow
              testID="confirm-yes"
              onPress={() => {
                setConfirm(false);
                void save();
              }}
            >
              {t('field.reads.rw09.confirmYes')}
            </Button>
          </>
        }
      />
      {form.sheet}
    </>
  );
  if (sideBySide) {
    return (
      <View style={{ flex: 1, flexDirection: 'row', backgroundColor: theme.colors.page }}>
        <View style={{ flex: 2 }} testID="entry-context">
          <ScreenBody>
            {route ? (
              <View>
                <Kicker>{t('field.reads.rw09.route')}</Kicker>
                <AppText variant="section">{routeName(route)}</AppText>
                <AppText variant="label" tone="muted">
                  {[route.code, route.service, route.read_type].filter(Boolean).join(' · ')}
                </AppText>
              </View>
            ) : null}
            {tally ? (
              <Card title={t('field.reads.rw09.progress')}>
                <AppText variant="section">{t('field.reads.common.nOfM', { n: tally.done, m: tally.total })}</AppText>
                <ProgressBar done={tally.done} problem={tally.could_not} total={tally.total} label={t('field.reads.common.nOfM', { n: tally.done, m: tally.total })} />
              </Card>
            ) : null}
            {stop ? (
              <Card title={t('field.reads.rw09.where')}>
                <AppText variant="body" weight="heavy">
                  {streetOf(stop)}
                </AppText>
              </Card>
            ) : null}
            <Button testID="door-RW-06" onPress={() => go('RW-06', { stopId: m.stop_id })}>
              {t('field.reads.common.theStop')}
            </Button>
          </ScreenBody>
        </View>
        <View style={{ flex: 3 }}>
          <ScreenBody bar={bar}>
            {head}
            {figure}
            {evidence}
            {strip}
            {keypad}
          </ScreenBody>
        </View>
        {sheets}
      </View>
    );
  }
  return (
    <ScreenBody bar={bar}>
      {head}
      {figure}
      {keypad}
      {evidence}
      {strip}
      {sheets}
    </ScreenBody>
  );
}

// ── RW-10 Dials ─────────────────────────────────────────────────────────────

/**
 * One box per dial, left to right; a tap moves a dial on by one. The number
 * of dials is the number of digits the meter showed last month — a fact of
 * the meter, not a setting; with no previous reading the reader types instead.
 */
export function Dials() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s, services, bump, clearDraft } = useReads();
  const { route, meter: m } = useLive(() => resolveAll(s, params), [params.readId]);
  const [draft, setDraft] = useDraftValue(m?.id ?? null);
  const width = m?.previous_value ? m.previous_value.split('.')[0]?.replace('-', '').length ?? 0 : 0;
  const start = (draft.value || m?.previous_value?.split('.')[0] || '').padStart(width, '0').slice(-width);
  const [digits, setDigits] = useState<string[]>(() => start.split(''));
  const form = useReadForm(m);
  if (!m) return <NoMeter />;
  if (width === 0) {
    return (
      <ScreenBody>
        <Notice tone="info">{t('field.reads.rw10.noDials')}</Notice>
        <Button variant="primary" testID="door-RW-09" onPress={() => go('RW-09', { readId: m.id })}>
          {t('field.reads.rw10.type')}
        </Button>
      </ScreenBody>
    );
  }
  const value = String(Number.parseInt(digits.join('') || '0', 10));
  const v = verdict(value, m.previous_value, m.expected_min, m.expected_max);
  const warn = needsWarning(v);
  const usedNow = used(value, m.previous_value);
  const keep = () => setDraft({ ...draft, value });
  const saveIt = async () => {
    keep();
    if (warn || (m.photo_required === 1 && draft.photos.length === 0)) {
      go('RW-09', { readId: m.id });
      return;
    }
    await form.saveWith('read', false, async (answers) => {
      await saveReading(services, m, { ...draft, value }, { readerStatus: 'read', readMethod: route?.read_type ?? null, form: answers });
      clearDraft(m.id);
      bump();
      go('RW-06', { stopId: m.stop_id });
    });
  };
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button grow testID="door-RW-17" onPress={() => go('RW-17', { readId: m.id })}>
            {t('field.reads.rw09.cantRead')}
          </Button>
          <Button variant="primary" grow testID="door-RW-06" onPress={() => void saveIt()}>
            {t('field.reads.rw09.save')}
          </Button>
        </ActionBar>
      }
    >
      <Spread>
        <AppText variant="title">{t('field.screen.rw10')}</AppText>
        <AppText variant="label" tone="muted">
          {meterName(m)}
        </AppText>
      </Spread>
      <Notice tone="info">{t('field.reads.rw10.how')}</Notice>
      <Card>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: theme.touch.clear }} testID="dials">
          {digits.map((d, i) => (
            <Button
              key={i}
              grow
              accessibilityLabel={t('field.reads.rw10.dial', { n: i + 1, digit: d })}
              testID={`dial-${i}`}
              onPress={() => setDigits(digits.map((x, j) => (j === i ? String((Number(x) + 1) % 10) : x)))}
            >
              {d}
            </Button>
          ))}
        </View>
        <AppText variant="label" tone="muted" style={{ textAlign: 'center' }}>
          {t('field.reads.rw10.tap')}
        </AppText>
      </Card>
      <Card>
        <Kicker>{t('field.reads.rw10.thatReads')}</Kicker>
        <Figure value={value} unit={m.unit} warn={warn} testID="dials-figure" />
        {usedNow !== null ? (
          <Notice tone={warn ? 'warning' : 'success'} testID="dials-used">
            {t('field.reads.rw10.used', { used: group(usedNow), unit: m.unit, verdict: t(verdictKey(v)) })}
          </Notice>
        ) : null}
      </Card>
      <Button testID="door-RW-09" onPress={() => (keep(), go('RW-09', { readId: m.id }))}>
        {t('field.reads.rw10.type')}
      </Button>
      {form.sheet}
    </ScreenBody>
  );
}

// ── RW-11 Scan to confirm ───────────────────────────────────────────────────

/**
 * The badge decides the meter (R83: serial, then badge, then device ID).
 * A match reads the meter as identified by scan; anything else goes to RW-18,
 * which refuses to let a wrong badge be guessed.
 */
export function ScanToConfirm() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s, services } = useReads();
  const { meter: m } = useLive(() => resolveAll(s, params), [params.readId]);
  const [draft, setDraft] = useDraftValue(m?.id ?? null);
  const [code, setCode] = useState<string | null>(null);
  const [how, setHow] = useState<'scan' | 'typed'>('scan');
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState('');
  const [failed, setFailed] = useState(false);
  const scan = async () => {
    try {
      const got = await services.scanner.scan();
      if (got) {
        setCode(got);
        setHow('scan');
      }
    } catch {
      setFailed(true);
    }
  };
  useEffect(() => {
    if (services.scanner.available) void scan();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (!m) return <NoMeter />;
  const found = code ? assetQ.matchScannedCode(services.db, code) : null;
  const matches = found?.asset.id === m.asset_id;
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button grow testID="scan-type" onPress={() => setTyping(true)}>
            {t('field.reads.rw11.typeIt')}
          </Button>
          <Button
            variant="primary"
            grow
            disabled={!matches}
            testID="door-RW-09"
            onPress={() => {
              setDraft({ ...draft, identifiedBy: how });
              go('RW-09', { readId: m.id });
            }}
          >
            {t('field.reads.rw11.readThis')}
          </Button>
        </ActionBar>
      }
    >
      <View
        testID="viewfinder"
        style={{ minHeight: theme.touch.primary * 4, backgroundColor: theme.colors.toastFill, alignItems: 'center', justifyContent: 'center', padding: theme.space[4] }}
      >
        <AppText variant="body" style={{ color: theme.colors.toastText, textAlign: 'center' }}>
          {services.scanner.available ? t('field.reads.rw11.point') : t('field.reads.common.noScanner')}
        </AppText>
      </View>
      {services.scanner.available ? (
        <Button testID="scan-again" onPress={() => void scan()}>
          {t('field.reads.rw11.scanAgain')}
        </Button>
      ) : null}
      {failed ? <Notice tone="warning">{t('field.reads.common.noScanner')}</Notice> : null}
      {code && matches ? (
        <Notice tone="success" testID="scan-match">
          {t('field.reads.rw11.matches', { code, who: [unitLabel(m), m.customer_name].filter(Boolean).join(', ') })}
        </Notice>
      ) : null}
      {code && !matches ? (
        <Notice tone="danger" testID="scan-mismatch">
          {t('field.reads.rw11.noMatch', { code })}
        </Notice>
      ) : null}
      <Button variant={code && !matches ? 'danger' : 'secondary'} testID="door-RW-18" onPress={() => go('RW-18', { readId: m.id, code: code ?? undefined })}>
        {t('field.reads.rw11.notRight')}
      </Button>
      <Sheet
        visible={typing}
        onClose={() => setTyping(false)}
        title={t('field.reads.rw11.typeIt')}
        closeLabel={t('field.reads.common.close')}
        footer={
          <Button
            variant="primary"
            grow
            testID="typed-code-ok"
            onPress={() => {
              setCode(typed.trim() || null);
              setHow('typed');
              setTyping(false);
            }}
          >
            {t('field.reads.rw11.check')}
          </Button>
        }
      >
        <Field label={t('field.reads.rw11.badgeOrSerial')} value={typed} onChangeText={setTyped} testID="typed-code" />
      </Sheet>
    </ScreenBody>
  );
}

// ── RW-13 The reading ───────────────────────────────────────────────────────

/**
 * The record, as it was kept: the figure and its unit, the reader's status,
 * what was caught automatically, what the reader added, and the office's
 * verdict as a separate thing that has not happened yet (R96).
 */
export function TheReading() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s, services } = useReads();
  const { meter: m } = useLive(() => resolveAll(s, params), [params.readId]);
  // FB-003: every photo of THIS reading — saved with it, added after, or kept
  // from before it was changed — by the reading each photo names (0006).
  const shots = useLive(() => (m ? walkQ.readingPhotoCount(s, m.id) : 0), [m?.id, m?.capture_key]);
  const kept = useLive(() => (m ? walkQ.readingPhotos(s, m.id) : []), [m?.id, m?.capture_key]);
  const viewer = useViewer();
  // FB-003: saved without a position, the first fix within 5 minutes is its
  // own fact — shown as *added at*, never as if it were there at save.
  const late = useLive(() => (m && m.lat === null ? latePositionOf(s, m.capture_key) : null), [m?.capture_key, m?.lat]);
  // MQ-033: the server keeps every answer and flags what it doubts — never
  // refuses (BR-MET-1216). Said here as the receipt's own fact; it blocks nothing.
  const answersFlagged = useLive(() => {
    const row = m?.capture_key ? outboxQ.getMine(s, m.capture_key) : undefined;
    return fromJson<{ answers?: { needs_review?: unknown } }>(row?.answer)?.answers?.needs_review === true;
  }, [m?.capture_key, m?.state]);
  if (!m) return <NoMeter />;
  const keptShown: ShownPhoto[] = kept.map((p) => ({
    key: p.id,
    path: p.file_deleted ? null : p.local_path,
    caption: clock(new Date(p.captured_at)),
  }));
  const usedNow = m.value ? used(m.value, m.previous_value) : null;
  const next = walkQ.nextUnreadAtStop(s, m.stop_id, m.id);
  const position =
    m.lat !== null && m.lng !== null
      ? t('field.reads.rw13.position', {
          lat: m.lat.toFixed(6),
          lng: m.lng.toFixed(6),
          acc: Math.round(m.accuracy_m ?? 0),
          away: m.metres_from_record !== null ? t('field.reads.rw13.fromRecord', { m: m.metres_from_record }) : '',
        })
      : late
        ? t('field.reads.rw13.positionAdded', { time: clock(new Date(late.fix_at)), acc: Math.round(late.accuracy_m) })
        : t('field.reads.rw13.noPosition');
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button grow testID="door-RW-09" onPress={() => go('RW-09', { readId: m.id })}>
            {t('field.reads.rw13.change')}
          </Button>
          <Button
            variant="primary"
            grow
            testID="door-RW-06"
            onPress={() => (next ? go('RW-09', { readId: next.id }) : go('RW-06', { stopId: m.stop_id }))}
          >
            {t('field.reads.rw13.next')}
          </Button>
        </ActionBar>
      }
    >
      <Card>
        <Spread>
          {m.value !== null ? (
            <Figure value={m.value} unit={m.unit} testID="kept-figure" />
          ) : (
            <AppText variant="section">{m.no_read_reason ?? t('field.reads.status.couldNot')}</AppText>
          )}
          <ReaderStatusChip status={m.reader_status} />
        </Spread>
        {usedNow !== null ? (
          <AppText variant="label" tone="muted" testID="kept-used">
            {t('field.reads.rw13.used', { used: group(usedNow), unit: m.unit })}
          </AppText>
        ) : null}
      </Card>
      <Kicker>{t('field.reads.rw13.caught')}</Kicker>
      <Card>
        <ListRow label={position} testID="kept-position" />
        <ListRow divider label={m.captured_at ? dateTime(new Date(m.captured_at), true) : ''} testID="kept-time" />
      </Card>
      {m.lat === null && late === null ? <Notice tone="warning">{t('field.reads.rw13.noFixWarn')}</Notice> : null}
      <Kicker>{t('field.reads.rw13.added', { name: services.readerName })}</Kicker>
      <Card>
        {/* Saved: the photos are evidence — view and add, never retake or remove (PO 2026-10-27). */}
        <ListRow
          label={t('field.reads.photos.count', { count: shots })}
          detail={t('field.reads.rw13.cameraOnly')}
          onPress={shots > 0 ? () => viewer.open(0) : undefined}
          testID="kept-photos"
        />
        <PhotoStrip photos={keptShown} onOpen={viewer.open} />
        <Button testID="door-RW-14" onPress={() => go('RW-14', { readId: m.id })}>
          {t('field.reads.photos.add')}
        </Button>
      </Card>
      <PhotoViewer photos={keptShown} index={viewer.index} onClose={viewer.close} />
      {m.remark ? (
        <Card title={t('field.reads.rw13.remark')}>
          <AppText variant="body" testID="kept-remark">
            {`“${m.remark}”`}
          </AppText>
          <AppText variant="label" tone="muted">
            {m.remark_source === 'voice' ? t('field.reads.rw13.spoken') : t('field.reads.rw13.typed')}
          </AppText>
        </Card>
      ) : null}
      <Kicker>{t('field.reads.rw13.office')}</Kicker>
      <Card>
        <Spread>
          <StatusChip tone="neutral">{t('field.reads.rw13.notYet')}</StatusChip>
          <AppText variant="body" style={{ flexShrink: 1 }}>
            {t('field.reads.rw13.checked')}
          </AppText>
        </Spread>
      </Card>
      <Notice tone="info" testID="kept-state">
        {m.state === 'pending' || m.state === 'sending' ? t('field.reads.rw13.held') : t(`field.reads.send.${m.state}`)}
      </Notice>
      {answersFlagged ? (
        <Notice tone="warning" testID="kept-answers-flagged">
          {t('field.reads.rw13.answersChecked')}
        </Notice>
      ) : null}
    </ScreenBody>
  );
}

// ── RW-14 The camera ────────────────────────────────────────────────────────

/**
 * The camera and nothing else — the port has no gallery (R93). The stamp is
 * handed to the camera to burn into the pixels (R94): date and time, position
 * with accuracy, reader, meter, route.
 *
 * FB-002 (DEF-FLD-10630): the panel IS the camera — the port's live view, with
 * the stamp laid over it as a preview — and *Take the photo* shoots from that
 * view. It used to be a dark panel holding only the stamp's words, with the
 * real camera opening full screen on top after the shutter was pressed. With
 * `photo` in the address (Retake, before the reading is saved) the new photo
 * takes that one's place and the old file is deleted (PO 2026-10-27).
 */
export function TheCamera() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useGo();
  const params = useParams();
  const { s, services, here, bump } = useReads();
  const { route, meter: m } = useLive(() => resolveAll(s, params), [params.readId]);
  const [draft, setDraft] = useDraftValue(m?.id ?? null);
  const [failed, setFailed] = useState(false);
  if (!m) return <NoMeter />;
  // Retake (PO 2026-10-27): the new photo takes the place of the one named.
  const retake = params.photo !== undefined && draft.photos[Number(params.photo)] ? Number(params.photo) : null;
  const Live = services.camera.available ? services.camera.Preview : undefined;
  const now = services.clock.now();
  const stamp = [
    dateTime(now, true),
    here ? `${here.lat.toFixed(6)}, ${here.lng.toFixed(6)} · ±${Math.round(here.accuracy_m)} m` : t('field.reads.rw13.noPosition'),
    [services.readerName, meterName(m), route?.code ?? ''].filter(Boolean).join(' · '),
  ];
  const shoot = async () => {
    // FB-003 (PO 2026-10-27, *"when user takes the photo record the lat,long
    // positions"*): the position at the shutter, with its own fix time, is
    // the photograph's — on its record as in its burned-in stamp.
    const atShutter = here;
    try {
      const shot = { ...(await services.camera.take(stamp)), location: atShutter };
      if (m.state === 'unread') {
        if (retake !== null) {
          const old = draft.photos[retake];
          setDraft({ ...draft, photos: draft.photos.map((p, i) => (i === retake ? shot : p)) });
          if (old) void services.camera.discard?.(old.localPath);
        } else {
          setDraft({ ...draft, photos: [...draft.photos, shot] });
        }
        go('RW-09', { readId: m.id });
      } else {
        // The reading is already kept: the photograph is declared against the
        // same reading (R123) — ONE item naming the reading's key — and the
        // reading is not touched (FB-019, DEF-FLD-10637: it used to queue an
        // empty `photo` act beside the declaration, refused as damaged).
        if (!m.capture_key) throw new Error('a saved reading has its capture key');
        declareRoutePhoto(
          services.db,
          { technicianId: services.technicianId, capturedBy: services.capturedBy },
          { routeId: m.route_id, routeReadId: m.id, readingKey: m.capture_key, photo: shot },
          { newId: () => services.newId(), clock: services.clock },
        );
        bump();
        go('RW-13', { readId: m.id });
      }
    } catch {
      setFailed(true);
    }
  };
  return (
    <ScreenBody
      bar={
        <ActionBar>
          <Button grow testID="door-RW-09" onPress={() => go(m.state === 'unread' ? 'RW-09' : 'RW-13', { readId: m.id })}>
            {t('field.reads.common.back')}
          </Button>
          <Button variant="primary" grow disabled={!services.camera.available} testID="door-RW-13" onPress={() => void shoot()}>
            {t('field.reads.rw14.take')}
          </Button>
        </ActionBar>
      }
    >
      {/* FB-003: opening the camera asks for location where it is not on yet. */}
      <LocationAsk />
      {/* FB-002: the LIVE camera, with the stamp laid over it as a preview of
          what is burned into the pixels on the shutter (R94). */}
      <View
        testID="camera-view"
        style={{ width: '100%', aspectRatio: 3 / 4, minHeight: theme.touch.primary * 6, backgroundColor: theme.colors.toastFill, overflow: 'hidden' }}
      >
        {Live ? (
          <View style={StyleSheet.absoluteFill}>
            <Live />
          </View>
        ) : null}
        <View style={{ flex: 1, justifyContent: 'space-between', padding: theme.space[3] }}>
          <StatusChip tone="neutral">{t('field.reads.rw14.cameraOnly')}</StatusChip>
          <View style={{ gap: theme.space[1], padding: theme.space[2], backgroundColor: withAlpha(theme.colors.toastFill, 0.55) }} testID="stamp">
            {stamp.map((line) => (
              <AppText key={line} variant="label" weight="semibold" style={{ color: theme.colors.toastText }}>
                {line}
              </AppText>
            ))}
          </View>
        </View>
      </View>
      <Notice tone="info">{t('field.reads.rw14.burned')}</Notice>
      {!services.camera.available || failed ? <Notice tone="warning">{t('field.reads.rw14.noCamera')}</Notice> : null}
    </ScreenBody>
  );
}
