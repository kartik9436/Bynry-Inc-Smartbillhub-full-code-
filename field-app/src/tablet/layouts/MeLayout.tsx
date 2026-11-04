/**
 * The technician's own boards on a tablet (T-29). Each keeps the phone screen
 * as its list — its own bar, its own acts — and draws the board's detail
 * beside it from the same services (`screens/me/services.tsx`), so the two
 * can never say different things:
 *
 * FF-44 T *Profile* — the phone's Profile; beside it the person: name, part,
 *   the details the server door gives (utility, employment, mobile,
 *   certifications current) and *Change availability* (FF-45). The board's
 *   crew, depot, van and per-certification expiry lines are not on the
 *   handset or the door (`ME-profile`), and *Change photo* has nothing to
 *   take one with — reported with FF-44 itself; left out, never guessed.
 * FF-45 T *Availability* — the phone's three choices; beside them the state
 *   now: since when, what dispatch sees, jobs left today, when the shift ends.
 * FF-46 T *Shifts* — the phone's week; a day picks it; beside it the day's
 *   window, name and note, and *Ask for time off* (the phone's request).
 * FF-47 T *Timesheet* — the week's DAYS (*This week · Last week*): the phone
 *   screen is a list of clocks, not of days, so the board's list is built
 *   (`PickList`) from the same clocks. Beside it the picked day's clocks —
 *   each still opens its correction (R9) — the day's total, *Admin time*
 *   (FF-48) and *Submit the day*, the phone's footer.
 * FF-48 T *Admin* — the phone's tasks; a task picks it instead of starting;
 *   beside it today's and this week's time on it and *Start* (or *Stop* while
 *   it runs) — the phone row's own act.
 * FF-49 T *Van* — the phone's stock; a part picks it; beside it the part,
 *   how many are on the van, how many today's jobs need, its unit price as
 *   sent (up to four places, CLAUDE.md rule 2), and *Ask the depot* while it
 *   is short — the phone's act.
 *
 * The boards' rationale paragraphs are not on screen (B14 rule 33).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Avatar, Button, ChoiceChips, Dot, Notice } from '../../components';
import { type Fact } from '../../components/Facts';
import { AdminTasksScreen } from '../../screens/me/AdminTasksScreen';
import { AVAILABILITY_TONE, useAvailability } from '../../screens/me/availability';
import { AvailabilityScreen } from '../../screens/me/AvailabilityScreen';
import { formatClock, formatDuration } from '../../screens/me/format';
import { useActiveTechnician, useCaptor, useHandsetPrefs, usePortRead } from '../../screens/me/hooks';
import { useDoor } from '../../screens/me/MeScreen';
import { ProfileScreen } from '../../screens/me/ProfileScreen';
import { ADMIN_TASKS, type AdminTask, type TimeEntry, useMeServices } from '../../screens/me/services';
import { DAY_KEYS, ShiftsScreen } from '../../screens/me/ShiftsScreen';
import { ADMIN_TASK_KEY, Correction, EntryRow, minutesOf, totals } from '../../screens/me/TimesheetScreen';
import { unitPriceText, VanScreen } from '../../screens/me/VanScreen';
import { useTheme } from '../../theme';
import { DetailCard, DetailNone, DetailPane } from '../DetailPane';
import { PickList } from '../Pickable';
import { useDefaultSelection, usePick, useSelectedOr } from '../selection';
import { employmentWord } from '../../screens/onSite/job';

const STATE_KEY = {
  available: 'field.availability.available',
  onBreak: 'field.availability.onBreak',
  offDuty: 'field.availability.offDuty',
  unavailable: 'field.availability.unavailable',
} as const;

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

/** "Tue 20 Oct" — the day's short name and date, in the shift screen's words. */
function dayName(t: (k: string) => string, d: Date): string {
  return `${t(DAY_KEYS[d.getDay()] ?? DAY_KEYS[0])} ${d.getDate()}`;
}

// ── FF-44 Profile ─────────────────────────────────────────────────────────

export function ProfileList() {
  return <ProfileScreen />;
}

export function ProfileDetail() {
  const { t } = useTranslation();
  const services = useMeServices();
  const door = useDoor('FF-44');
  const tech = useActiveTechnician();
  const [facts] = usePortRead(
    () => (tech ? services.profile.facts(tech.technicianId) : Promise.resolve(null)),
    [services, tech?.technicianId],
  );
  if (!tech) return <DetailNone title={t('field.me.notHereYet')} helper={t('field.tablet.pickHelp')} testID="profile-detail" />;
  const fromServer = facts.state === 'ready' ? facts.value : null;
  const who = services.data.who(tech.technicianId);
  const role = fromServer?.role ?? who?.role ?? null;
  const employment = fromServer?.employment ?? who?.employment ?? null;
  const lines: Fact[] = [];
  if (fromServer?.utility) lines.push({ label: t('field.ff44.utility'), value: fromServer.utility });
  if (employment) lines.push({ label: t('field.ff44.employment'), value: employmentWord(t, employment) });
  if (fromServer?.mobile) lines.push({ label: t('field.ff44.mobile'), value: fromServer.mobile });
  if (fromServer?.certificationsCurrent != null) {
    lines.push({ label: t('field.ff44.certifications'), value: t('field.ff44.certificationsCurrent', { count: fromServer.certificationsCurrent }) });
  }
  return (
    <DetailPane
      testID="profile-detail"
      acts={
        <Button grow onPress={() => door('FF-45')} testID="pane-FF-45">
          {t('field.tablet.ff44.changeAvailability')}
        </Button>
      }
    >
      <DetailCard title={tech.name} line={role} trailing={<Avatar name={tech.name} size="large" />} facts={lines} testID="profile-detail-card" />
    </DetailPane>
  );
}

// ── FF-45 Availability ────────────────────────────────────────────────────

export function AvailabilityList() {
  return <AvailabilityScreen />;
}

export function AvailabilityDetail() {
  const { t } = useTranslation();
  const services = useMeServices();
  const tech = useActiveTechnician();
  const [prefs] = useHandsetPrefs();
  const [state] = useAvailability(tech?.technicianId ?? null);
  const [week] = usePortRead(
    () => (tech ? services.shifts.week(tech.technicianId, services.now()) : Promise.resolve(null)),
    [services, tech?.technicianId],
  );
  const today = tech ? services.data.today(tech.technicianId, services.now()) : null;
  const label = state.value ? t(STATE_KEY[state.value]) : t('field.availability.unknown');
  const since = state.value && state.since ? formatClock(state.since, prefs.clock) : null;
  const shiftEnd = week.state === 'ready' && week.value?.current ? formatClock(week.value.current.end, prefs.clock) : null;
  const facts: Fact[] = [{ label: t('field.tablet.ff45.dispatchSees'), value: since ? t('field.tablet.ff45.since', { state: label, time: since }) : label }];
  if (today) facts.push({ label: t('field.tablet.ff45.jobsLeft'), value: String(today.left) });
  if (shiftEnd) facts.push({ label: t('field.tablet.ff45.shiftEnds'), value: shiftEnd });
  return (
    <DetailPane testID="availability-detail">
      <DetailCard
        title={label}
        line={since ? t('field.tablet.ff45.sinceTime', { time: since }) : null}
        trailing={state.value ? <Dot tone={AVAILABILITY_TONE[state.value]} /> : undefined}
        facts={facts}
        testID="availability-detail-card"
      />
    </DetailPane>
  );
}

// ── FF-46 Shifts ──────────────────────────────────────────────────────────

export function ShiftsList() {
  return <ShiftsScreen />;
}

export function ShiftDayDetail() {
  const { t } = useTranslation();
  const services = useMeServices();
  const tech = useActiveTechnician();
  const [prefs] = useHandsetPrefs();
  const [notice, setNotice] = useState<string | null>(null);
  const [loaded] = usePortRead(
    () => (tech ? services.shifts.week(tech.technicianId, services.now()) : Promise.resolve(null)),
    [services, tech?.technicianId],
  );
  const week = loaded.state === 'ready' ? loaded.value : null;
  const todayKey = services.now().toISOString().slice(0, 10);
  const fallback = week ? (week.days.find((d) => d.date.slice(0, 10) === todayKey) ?? week.days[0] ?? null) : null;
  useDefaultSelection(fallback?.date ?? null);
  const picked = useSelectedOr('day');
  const day = week?.days.find((d) => d.date === picked) ?? fallback;
  const ask = (
    <Button
      grow
      onPress={async () => {
        if (!tech) return;
        setNotice(null);
        try {
          await services.shifts.requestTimeOff(tech.technicianId);
        } catch {
          setNotice(t('field.me.notSent'));
        }
      }}
      testID="shift-detail-time-off"
    >
      {t('field.tablet.ff46.askTimeOff')}
    </Button>
  );
  if (!day) {
    return (
      <DetailPane testID="shift-detail" acts={ask}>
        <DetailCard title={t('field.me.notHereYet')} line={t('field.ff46.emptyHelper')} />
        {notice ? <Notice tone="warning">{notice}</Notice> : null}
      </DetailPane>
    );
  }
  const d = new Date(day.date);
  const facts: Fact[] = [];
  if (day.kind === 'shift' && day.start && day.end) {
    facts.push({ label: t('field.tablet.ff46.shift'), value: `${formatClock(day.start, prefs.clock)} – ${formatClock(day.end, prefs.clock)}` });
  }
  if (day.kind === 'timeOff') facts.push({ label: t('field.tablet.ff46.shift'), value: t('field.ff46.timeOff') });
  if (day.name) facts.push({ label: t('field.tablet.ff46.name'), value: day.name });
  if (day.note) facts.push({ label: t('field.tablet.ff46.note'), value: day.note });
  return (
    <DetailPane testID="shift-detail" acts={ask}>
      <DetailCard title={dayName(t, d)} facts={facts} testID="shift-detail-card" />
      {notice ? (
        <Notice tone="warning" testID="shift-detail-notice">
          {notice}
        </Notice>
      ) : null}
    </DetailPane>
  );
}

// ── FF-47 Timesheet ───────────────────────────────────────────────────────

type Week = 'this' | 'last';

/** Monday 00:00 of the week `now` is in, `back` weeks ago. */
function weekStart(now: Date, back: number): Date {
  const d = startOfDay(now);
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7) - 7 * back);
  return d;
}

function dayKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/**
 * The clocks from `from` for `days` days, by local day. Null when the clocks
 * are not on the handset (`N17`). Read on every render — one indexed query —
 * so a correction beside the list shows in both panes at once.
 */
function useClocksByDay(from: Date, days: number): Map<string, TimeEntry[]> | null {
  const services = useMeServices();
  const tech = useActiveTechnician();
  if (!tech) return null;
  const to = new Date(from);
  to.setDate(to.getDate() + days);
  const entries = services.data.timesheet(tech.technicianId, from, to);
  if (!entries) return null;
  const byDay = new Map<string, TimeEntry[]>();
  for (const e of entries) {
    const k = dayKey(new Date(e.startedAt));
    byDay.set(k, [...(byDay.get(k) ?? []), e]);
  }
  return byDay;
}

/** `2026-10-20` → that local midnight. */
function dayOf(key: string): Date {
  const [y, m, d] = key.split('-').map(Number);
  return new Date(y ?? 1970, (m ?? 1) - 1, d ?? 1);
}

export function TimesheetDays() {
  const { t } = useTranslation();
  const services = useMeServices();
  const [week, setWeek] = useState<Week>('this');
  const now = services.now();
  const from = weekStart(now, week === 'this' ? 0 : 1);
  // A correction beside the list re-picks its day, which renders the pair again.
  const days = useClocksByDay(from, 7);
  const items = [...(days?.entries() ?? [])]
    .sort(([a], [b]) => b.localeCompare(a))
    .map(([k, list]) => {
      const jobs = new Set(list.filter((e) => e.workOrderId).map((e) => e.workOrderId)).size;
      return {
        id: k,
        title: dayName(t, dayOf(k)),
        value: formatDuration(totals(list, now).all),
        sub: t('field.tablet.ff47.jobs', { count: jobs }),
      };
    });
  const to = new Date(from);
  to.setDate(to.getDate() + 6);
  return (
    <View style={{ flex: 1 }} testID="screen-FF-47">
      <PickList
        header={
          <ChoiceChips
            label={t('field.ff47.range')}
            segments={[
              { id: 'this', label: t('field.tablet.ff47.thisWeek') },
              { id: 'last', label: t('field.tablet.ff47.lastWeek') },
            ]}
            active={week}
            onSelect={(id) => setWeek(id === 'last' ? 'last' : 'this')}
            testID="ff47-week"
          />
        }
        kicker={`${dayName(t, from)} – ${dayName(t, to)}`}
        items={items}
        empty={<AppText variant="body" tone="muted">{days ? t('field.ff47.none') : t('field.me.notHereYet')}</AppText>}
        testID="timesheet-days"
      />
    </View>
  );
}

export function TimesheetDay() {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const door = useDoor('FF-47');
  const tech = useActiveTechnician();
  const captor = useCaptor();
  const [prefs] = useHandsetPrefs();
  const pick = usePick();
  const [, setVersion] = useState(0);
  const [editing, setEditing] = useState<TimeEntry | null>(null);
  const [notice, setNotice] = useState<{ tone: 'warning' | 'info'; text: string } | null>(null);
  const now = services.now();
  const key = useSelectedOr('day') ?? dayKey(now);
  const days = useClocksByDay(dayOf(key), 1);
  const entries = days?.get(key) ?? [];
  // CR-193-BRC10 — a submitted day is read-only on the handset (the office corrects it).
  const submitted = tech ? services.timesheet.submitted?.(tech.technicianId, dayOf(key)) === true : false;

  async function submit() {
    if (!tech) return;
    setNotice(null);
    try {
      await services.timesheet.submitDay(captor(), dayOf(key));
      setVersion((v) => v + 1);
      setNotice({ tone: 'info', text: t(services.timesheet.submitted ? 'field.ff47.queued' : 'field.ff47.submitted') });
    } catch {
      setNotice({ tone: 'warning', text: t('field.me.notSent') });
    }
  }

  function save(start: string, end: string | null) {
    if (!editing) return;
    try {
      services.data.correct(captor(), editing.id, start, end, services.now());
      setEditing(null);
      setVersion((v) => v + 1);
      // Re-pick the day so the list beside it re-reads its total.
      if (pick.active) pick.pick(key);
    } catch {
      setEditing(null);
      setNotice({ tone: 'warning', text: t('field.me.notSaved') });
    }
  }

  const acts = (
    <>
      <Button grow onPress={() => door('FF-48')} testID="pane-FF-48">
        {t('field.tablet.ff47.adminTime')}
      </Button>
      <Button grow variant="primary" disabled={submitted || entries.length === 0} onPress={submit} testID="timesheet-detail-submit">
        {t(submitted ? 'field.ff47.submittedLabel' : 'field.ff47.submit')}
      </Button>
    </>
  );
  return (
    <DetailPane testID="timesheet-detail" acts={acts}>
      {notice ? <Notice tone={notice.tone}>{notice.text}</Notice> : null}
      {entries.length === 0 ? (
        <DetailCard title={days ? t('field.ff47.none') : t('field.me.notHereYet')} line={t('field.ff47.emptyHelper')} />
      ) : (
        <DetailCard title={dayName(t, dayOf(key))} testID="timesheet-detail-card">
          <View style={{ gap: theme.space[2] }}>
            {entries.map((e) => (
              <EntryRow key={e.id} entry={e} now={now} clock={prefs.clock} onPress={() => (submitted ? undefined : setEditing(e))} />
            ))}
          </View>
          <View
            style={{
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              paddingTop: theme.space[3],
              borderTopWidth: theme.borderWidth.emphasis,
              borderTopColor: theme.colors.border,
            }}
          >
            <AppText variant="body" weight="heavy">
              {t('field.tablet.ff47.theDay')}
            </AppText>
            <AppText variant="title" testID="timesheet-detail-total">
              {formatDuration(totals(entries, now).all)}
            </AppText>
          </View>
        </DetailCard>
      )}
      <Correction entry={editing} clock={prefs.clock} onClose={() => setEditing(null)} onSave={save} />
    </DetailPane>
  );
}

// ── FF-48 Admin ───────────────────────────────────────────────────────────

export function AdminList() {
  return <AdminTasksScreen />;
}

export function AdminTaskDetail() {
  const { t } = useTranslation();
  const services = useMeServices();
  const tech = useActiveTechnician();
  const captor = useCaptor();
  const [, setVersion] = useState(0);
  const [problem, setProblem] = useState(false);
  useDefaultSelection(ADMIN_TASKS[0]);
  const task = (useSelectedOr('task') ?? ADMIN_TASKS[0]) as AdminTask;
  const now = services.now();
  const from = startOfDay(now);
  const to = new Date(from);
  to.setDate(to.getDate() + 1);
  const weekFrom = weekStart(now, 0);
  const mine = (list: TimeEntry[] | null) => (list ?? []).filter((e) => e.kind === 'admin' && e.adminTask === task);
  const today = tech ? services.data.timesheet(tech.technicianId, from, to) : null;
  const week = tech ? services.data.timesheet(tech.technicianId, weekFrom, to) : null;
  const running = tech ? services.data.runningClock(tech.technicianId) : null;
  const runningThis = running?.kind === 'admin' && running.adminTask === task;
  const sum = (list: TimeEntry[]) => list.reduce((n, e) => n + minutesOf(e, now), 0);
  const facts: Fact[] =
    today && week
      ? [
          { label: t('field.tablet.ff48.today'), value: formatDuration(sum(mine(today))) },
          { label: t('field.tablet.ff48.thisWeek'), value: formatDuration(sum(mine(week))) },
        ]
      : [];

  function act(fn: () => void) {
    setProblem(false);
    try {
      fn();
      setVersion((v) => v + 1);
    } catch {
      setProblem(true);
    }
  }

  return (
    <DetailPane
      testID="admin-detail"
      acts={
        runningThis ? (
          <Button grow onPress={() => act(() => services.data.stopClock(captor(), services.now()))} testID="admin-detail-stop">
            {t('field.ff48.stop')}
          </Button>
        ) : (
          <Button
            grow
            variant="primary"
            disabled={!services.data.wired || !tech}
            onPress={() => act(() => services.data.startAdmin(captor(), task, services.now()))}
            testID="admin-detail-start"
          >
            {t('field.tablet.ff48.start', { task: t(ADMIN_TASK_KEY[task]) })}
          </Button>
        )
      }
    >
      <DetailCard
        title={t(ADMIN_TASK_KEY[task])}
        line={runningThis && running ? t('field.ff47.since', { time: formatClock(running.startedAt, 'h24') }) : null}
        facts={facts}
        testID="admin-detail-card"
      />
      {problem ? <Notice tone="warning">{t('field.me.notSaved')}</Notice> : null}
    </DetailPane>
  );
}

// ── FF-49 Van ─────────────────────────────────────────────────────────────

export function VanList() {
  return <VanScreen />;
}

export function VanItemDetail() {
  const { t } = useTranslation();
  const services = useMeServices();
  const tech = useActiveTechnician();
  const [notice, setNotice] = useState<string | null>(null);
  const [loaded] = usePortRead(
    () => (tech ? services.van.stock(tech.technicianId) : Promise.resolve(null)),
    [services, tech?.technicianId],
  );
  const stock = loaded.state === 'ready' ? loaded.value : null;
  const isShort = (i: { neededToday: number | null; onHand: number }) => i.neededToday != null && i.neededToday > i.onHand;
  const ordered = stock ? [...stock.items.filter(isShort), ...stock.items.filter((i) => !isShort(i))] : [];
  useDefaultSelection(ordered[0]?.sku ?? null);
  const sku = useSelectedOr('sku') ?? ordered[0]?.sku ?? null;
  const item = ordered.find((i) => i.sku === sku) ?? null;
  if (!item) return <DetailNone title={t('field.me.notHereYet')} helper={t('field.ff49.emptyHelper')} testID="van-detail" />;
  const short = isShort(item);
  const facts: Fact[] = [
    { label: t('field.tablet.ff49.part'), value: item.sku },
    { label: t('field.tablet.ff49.onVan'), value: String(item.onHand) },
  ];
  if (item.neededToday != null) facts.push({ label: t('field.ff49.neededToday'), value: String(item.neededToday) });
  if (item.unitPrice) facts.push({ label: t('field.tablet.ff49.each'), value: unitPriceText(item.unitPrice.amount, item.unitPrice.currency) });
  return (
    <DetailPane
      testID="van-detail"
      acts={
        short ? (
          <Button
            grow
            variant="danger"
            onPress={async () => {
              if (!tech) return;
              setNotice(null);
              try {
                await services.van.askDepot(tech.technicianId, item.sku);
                setNotice(t('field.ff49.asked'));
              } catch {
                setNotice(t('field.me.notSent'));
              }
            }}
            testID="van-detail-ask"
          >
            {t('field.ff49.askDepot')}
          </Button>
        ) : undefined
      }
    >
      <DetailCard title={item.name} line={stock?.van ?? null} facts={facts} tone={short ? 'danger' : 'plain'} testID="van-detail-card">
        {short ? (
          <Notice tone="warning" testID="van-detail-short">
            {t('field.tablet.short', { count: (item.neededToday ?? 0) - item.onHand })}
          </Notice>
        ) : null}
      </DetailCard>
      {notice ? (
        <Notice tone="info" testID="van-detail-notice">
          {notice}
        </Notice>
      ) : null}
    </DetailPane>
  );
}
