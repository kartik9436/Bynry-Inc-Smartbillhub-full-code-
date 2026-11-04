/**
 * FF-15 Job — the whole template on one screen (R5, US-FLD-026): safety,
 * tasks, materials, checklist, readings, papers, help — EACH WITH A COUNT AND
 * A STATE, counted from this order's own rows (R112: the order holds its own
 * copy of the template). Nothing is a bare link: every section row says how
 * far along it is before it is opened.
 *
 * Built from `wireframes/phone/FF-15-job.png` and `tablet/FF-15-T-job.png`
 * (B14 rule 42); sizes from the tokens (rules 44, 45). The board's figures
 * (WO-4822, 3 of 8, 2h 24m) are test data (rule 37).
 *
 * Doors, as the board links them (`navigation/doors.ts` FF-15): back → FF-10,
 * the sync pill → FF-50, the menu → FF-31, Customer → FF-25, the asset →
 * FF-39, the sections → FF-16 / 17 / 23 / 19 / 20 / 60 / 61 / 28, crew →
 * FF-29, notes → FF-30, activity → FF-31, *Hand back* → FF-58, and *Continue*
 * to the next unfinished part — Safety (R3), Tasks, Materials, Readings, then
 * *Finish — debrief* FF-32 (`nextPart.ts`, DEF-FLD-10586).
 *
 * TAKING THE JOB (DEF-FLD-10579, PO 2026-10-24): until the job is accepted
 * the footer's left action is ✕ *Decline* (the shared `DeclineSheet`), and
 * *Continue* — starting it — accepts it first. Once accepted, *Hand back* is
 * back in that place and is the only way out. A declined job offers neither
 * act: the dispatcher moves it.
 *
 * *Money to check* opens FF-61 and shows no figure: a balance is read online
 * and never kept on the handset (R16; Mobile data §2 — no balance column).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Linking, View } from 'react-native';

import { AppText, Button, Card, Glyph, Initials, Kicker, ListRow, Notice, StatusChip, type StatusTone } from '../../components';
import { useShellStatus } from '../../navigation/ShellStatus';
import { useSideBySide } from '../../tablet/columns';
import { useTheme } from '../../theme';
import { DeclineSheet } from '../theDay/DeclineSheet';
import { DispatchStateChip } from '../theDay/DispatchStateChip';
import { useAcceptance } from '../theDay/useAcceptance';
import { groupDigits, hhmm, initials, shortDuration } from './format';
import { JobScreen, useDoor } from './JobScreen';
import { jobPoint, pointUrl } from './jobPoint';
import { nextPart, nextPartLabel } from './nextPart';
import { TaskList } from './TaskList';
import { TimeCard } from './TimeCard';
import { useOpenJob } from './useJob';
import { fieldRaiseOf, showsOf } from '../../db/queries/workOrder';

/** A section's state, from its count: none → not started → in progress → done. */
export function sectionState(done: number, total: number): { tone: StatusTone; key: string } | null {
  if (total === 0) return null;
  if (done >= total) return { tone: 'success', key: 'field.ff15.state.done' };
  if (done === 0) return { tone: 'neutral', key: 'field.ff15.state.notStarted' };
  return { tone: 'warning', key: 'field.ff15.state.inProgress' };
}

function Count({ done, total, testID }: { done: number; total: number; testID: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const state = sectionState(done, total);
  return (
    <View style={{ alignItems: 'flex-end', gap: theme.space[1] }} testID={testID}>
      <AppText variant="body" weight="heavy">
        {t('field.job.nOfM', { done, total })}
      </AppText>
      {state ? <StatusChip tone={state.tone}>{t(state.key)}</StatusChip> : null}
    </View>
  );
}

/** One section of the template: its name, its count and its state — read aloud as well as drawn. */
function SectionRow(props: {
  name: string;
  label: string;
  detail?: string;
  done: number;
  total: number;
  divider?: boolean;
  onPress: () => void;
  testID: string;
}) {
  const { t } = useTranslation();
  const state = sectionState(props.done, props.total);
  const hint = [t('field.job.nOfM', { done: props.done, total: props.total }), state ? t(state.key) : null]
    .filter(Boolean)
    .join(', ');
  return (
    <ListRow
      divider={props.divider}
      label={props.label}
      detail={props.detail}
      value={<Count done={props.done} total={props.total} testID={`count-${props.name}`} />}
      accessibilityHint={hint}
      onPress={props.onPress}
      testID={props.testID}
    />
  );
}

/**
 * The job itself — everything FF-15 shows above its footer. On the phone it is
 * the whole screen's body; on a tablet it is the job pane beside the steps
 * (FF-15 T, `tablet/layouts/JobLayout.tsx`).
 */
export function JobDetails() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-15');
  const { port, view } = useOpenJob();
  const units = { h: t('field.job.unit.h'), m: t('field.job.unit.m') };

  const order = view?.order ?? null;
  const tasksTotal = view?.tasks.total ?? 0;
  // FB-023 F6 — the job's copy of its template's *What the technician sees on
  // the job* ticks (DEF-FLD-10791). The address and *Navigate* stay whatever
  // the ticks say: the technician still has to get there (decision log FB-023).
  const shows = showsOf(order);
  // FB-028 W3 = C (PO 2026-10-31) — *"Assign it to Dana, but her phone warns
  // before she starts"*: the template's skill she does not hold, by name.
  const skillMissing = fieldRaiseOf(order).skillMissing;

  const premise = view?.premise ?? null;
  const addressLines = premise
    ? [premise.address_line, [premise.locality, [premise.region, premise.postal_code].filter(Boolean).join(' ')].filter(Boolean).join(', ')].filter(
        (l): l is string => Boolean(l),
      )
    : [];
  // DEF-FLD-10582: the job's own point (a unit's, else its building's) —
  // enabled whenever one exists, opening the phone's maps app at it.
  const point = jobPoint(view?.order?.extra, premise);
  const navigate = () => {
    if (!point) return;
    void Linking.openURL(pointUrl(point, premise?.address_line ?? null));
  };

  const asset = view?.asset ?? null;
  const assetLine = asset ? [asset.serial ?? asset.badge ?? asset.id, asset.model, asset.size].filter(Boolean).join(' · ') : t('field.ff15.noAsset');
  const lastReading = view?.readings.items.find((r) => r.row.previous_value !== null)?.row ?? null;
  const assetDetail = asset
    ? [
        asset.badge ? t('field.ff15.badge', { badge: asset.badge }) : null,
        view && view.subMeters > 0 ? t('field.ff15.subMeters', { count: view.subMeters }) : null,
        lastReading ? t('field.ff15.last', { value: groupDigits(lastReading.previous_value), unit: lastReading.unit }) : null,
      ]
        .filter(Boolean)
        .join(' · ')
    : undefined;

  const v = view;
  const tasksDetail = v && v.tasks.needPhoto > 0 ? t('field.ff15.needPhoto', { count: v.tasks.needPhoto }) : undefined;
  const materialsDetail = v && v.materials.notOnVan > 0 ? t('field.ff15.notOnVan', { count: v.materials.notOnVan }) : undefined;
  const readingsDetail = v
    ? [
        v.readings.needPhoto > 0 ? t('field.ff15.needPhoto', { count: v.readings.needPhoto }) : null,
        v.readings.flagged > 0 ? t('field.ff15.flagged', { count: v.readings.flagged }) : null,
      ]
        .filter(Boolean)
        .join(' · ') || undefined
    : undefined;
  const added = v ? v.tasks.items.filter((x) => x.row.added_in_field).length + v.materials.added.length : 0;

  return (
    <>
      {order ? (
        <View style={{ gap: theme.space[2] }}>
          {order.type ? <Kicker tone="brand">{order.type}</Kicker> : null}
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: theme.space[2] }}>
            <DispatchStateChip state={order.dispatch_state} testID="job-state" />
            {order.priority_code ? <StatusChip tone="neutral">{order.priority_code}</StatusChip> : null}
            {shows.appointment && order.window_start ? (
              <AppText variant="label" tone="muted">
                {`${hhmm(order.window_start)}–${hhmm(order.window_end)}`}
              </AppText>
            ) : null}
          </View>
        </View>
      ) : (
        <Notice tone="info" testID="job-none">
          {t('field.job.noJob')}
        </Notice>
      )}

      {skillMissing ? (
        <Notice tone="warning" testID="job-skill-missing">
          {t('field.ff15.skillMissing', { skill: skillMissing })}
        </Notice>
      ) : null}

      {v ? <TimeCard port={port} view={v} /> : null}

      <Card testID="job-customer">
        {shows.accountSummary ? (
          <AppText variant="section" testID="job-customer-name">
            {v?.customer?.name ?? t('field.ff15.noCustomer')}
          </AppText>
        ) : null}
        {addressLines.map((line) => (
          <AppText key={line} variant="body">
            {line}
          </AppText>
        ))}
        {shows.accountSummary && v?.customer?.account_number ? (
          <AppText variant="label" tone="muted" testID="job-customer-account">
            {t('field.ff25.account', { account: v.customer.account_number })}
          </AppText>
        ) : null}
        <View style={{ flexDirection: 'row', gap: theme.touch.clear }}>
          <Button grow size="sm" onPress={navigate} disabled={!point} testID="job-navigate">
            {t('field.ff15.navigate')}
          </Button>
          <Button grow size="sm" onPress={() => go('FF-25')} testID="door-FF-25">
            {t('field.ff15.customer')}
          </Button>
        </View>
      </Card>

      {shows.assetCard ? (
        <Card title={t('field.ff15.asset')} testID="job-asset">
          <ListRow label={assetLine} detail={assetDetail} onPress={() => go('FF-39')} testID="door-FF-39" />
        </Card>
      ) : null}

      <Card
        title={t('field.ff15.needs')}
        trailing={
          order?.template_version ? (
            <AppText variant="label" tone="muted">
              {t('field.ff15.template', { version: order.template_version })}
            </AppText>
          ) : undefined
        }
        testID="job-sections"
      >
        <SectionRow name="safety" label={t('field.ff15.safety')} done={v?.safety.done ?? 0} total={v?.safety.total ?? 0} onPress={() => go('FF-16')} testID="door-FF-16" />
        <SectionRow divider name="tasks" label={t('field.ff15.tasks')} detail={tasksDetail} done={v?.tasks.done ?? 0} total={tasksTotal} onPress={() => go('FF-17')} testID="door-FF-17" />
        <SectionRow divider name="materials" label={t('field.ff15.materials')} detail={materialsDetail} done={v?.materials.satisfied ?? 0} total={v?.materials.planned.length ?? 0} onPress={() => go('FF-23')} testID="door-FF-23" />
        <SectionRow divider name="checklist" label={t('field.ff15.checklist')} done={v?.checklist.answered ?? 0} total={v?.checklist.total ?? 0} onPress={() => go('FF-19')} testID="door-FF-19" />
        <SectionRow divider name="readings" label={t('field.ff15.readings')} detail={readingsDetail} done={v?.readings.taken ?? 0} total={v?.readings.total ?? 0} onPress={() => go('FF-20')} testID="door-FF-20" />
        <ListRow divider label={t('field.ff15.papers')} value={String(v?.papers.length ?? 0)} onPress={() => go('FF-60')} testID="door-FF-60" />
        <ListRow divider label={t('field.ff15.money')} onPress={() => go('FF-61')} testID="door-FF-61" />
        <ListRow divider label={t('field.ff15.help')} value={String(v?.help ?? 0)} onPress={() => go('FF-28')} testID="door-FF-28" />
        {added > 0 ? (
          <Notice tone="info" testID="job-variance">
            {t('field.ff15.variance', { count: added })}
          </Notice>
        ) : null}
      </Card>

      <Card title={t('field.ff15.crew')}>
        <ListRow
          label={t('field.ff15.technicians', { count: v?.crew.people.length ?? 0 })}
          leading={
            <View style={{ flexDirection: 'row', gap: theme.space[1] }}>
              {(v?.crew.people ?? []).slice(0, 3).map((p) => (
                <Initials key={p}>{initials(p === port?.captor().technicianId ? port.displayName : p)}</Initials>
              ))}
            </View>
          }
          value={shortDuration(v?.crew.minutes ?? 0, units)}
          onPress={() => go('FF-29')}
          testID="door-FF-29"
        />
      </Card>

      <Card>
        <ListRow label={t('field.ff15.notes')} value={String(v?.remarks ?? 0)} onPress={() => go('FF-30')} testID="door-FF-30" />
        <ListRow divider label={t('field.ff15.activity')} value={t('field.ff15.events', { count: v?.events ?? 0 })} onPress={() => go('FF-31')} testID="job-activity" />
      </Card>
    </>
  );
}

export function JobOverview() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-15');
  const status = useShellStatus();
  const sideBySide = useSideBySide();
  const { port, view } = useOpenJob();
  const acceptance = useAcceptance();
  const [declining, setDeclining] = useState(false);

  const syncPill = (
    <Button size="sm" onPress={() => go('FF-50')} testID="door-FF-50" accessibilityLabel={t('field.ff15.syncA11y')}>
      {status.syncPending == null ? t('field.ff15.syncUnknown') : t('field.ff15.toSend', { count: status.syncPending })}
    </Button>
  );

  const order = view?.order ?? null;
  const next = nextPart(view);
  const v = view;
  const job = <JobDetails />;
  const taken = order ? acceptance.of(order.id) : 'accepted';

  return (
    <JobScreen
      id="FF-15"
      title={order?.number ?? t('field.screen.ff15')}
      back={{ to: 'FF-10', label: t('field.ff15.backToToday') }}
      trailing={syncPill}
      menu={{ to: 'FF-31', label: t('field.ff15.menuA11y') }}
      footer={
        <>
          {taken === 'accepted' || !acceptance.available ? (
            <Button onPress={() => go('FF-58')} testID="door-FF-58">
              {t('field.ff15.handBack')}
            </Button>
          ) : taken === 'pending' ? (
            <Button icon={<Glyph name="close" />} onPress={() => setDeclining(true)} testID="job-decline">
              {t('field.accept.decline')}
            </Button>
          ) : null}
          <Button
            grow
            variant="primary"
            disabled={next.to === null || (taken === 'declined' && acceptance.available)}
            onPress={() => {
              if (!next.to) return;
              if (order) acceptance.start(order.id);
              go(next.to);
            }}
            testID="job-continue"
          >
            {nextPartLabel(next, t)}
          </Button>
        </>
      }
    >
      {sideBySide && v ? (
        <View style={{ flexDirection: 'row', gap: theme.space[4] }}>
          <View style={{ flexGrow: 1, flexBasis: 0, gap: theme.space[3] }}>{job}</View>
          <View style={{ flexGrow: 1, flexBasis: 0, gap: theme.space[3] }} testID="job-tasks-pane">
            <AppText variant="title">{t('field.screen.ff17')}</AppText>
            <TaskList port={port} view={v} />
          </View>
        </View>
      ) : (
        job
      )}
      <DeclineSheet
        job={declining && order ? { id: order.id, number: order.number } : null}
        onClose={() => setDeclining(false)}
        onDecline={(id, answer) => acceptance.decline(id, answer)}
      />
    </JobScreen>
  );
}
