/**
 * The job's own papers, people and history on a tablet (T-29):
 *
 * FF-28 T *Documents* (`tablet/FF-28-T-documents.png`)
 *   LIST   — the phone's Documents, whole: the job's papers, the premise
 *            notes, the ones always on the phone, the shelf's totals. A row
 *            picks its paper here instead of opening it.
 *   DETAIL — the picked paper (the job's first until one is picked): its
 *            title, kind and size, whether it is on the tablet, and *Open
 *            it*, which opens the tablet's own copy as the phone's row does.
 *            The board draws the paper's first page beside the list; the
 *            paper opens in the tablet's own app instead (FB-031, ruling B).
 *            A greyed *Open it* says why beneath it (*No file attached.*,
 *            *Downloads at next sync*, *No number.*) — DEF-FLD-10805.
 *
 * FF-29 T *Crew* (`tablet/FF-29-T-crew.png`)
 *   LIST   — the phone's Crew, whole; a person's card picks them.
 *   DETAIL — *Who is on this job*: each person, their part and their labour,
 *            the picked one opened to Travel · Arrived · Labour, and the
 *            labour on the job under a rule. *Add a technician* is the list's
 *            own (the phone's button, still on screen beside it).
 *
 * FF-31 T *Activity* (`tablet/FF-31-T-activity.png`)
 *   LIST   — the job's DAYS: the phone screen is the timeline itself, not a
 *            list of days, so the board's list is built (`PickList`) from the
 *            same rows — each day, how many changes, first to last.
 *   DETAIL — *What happened* that day, the phone's timeline for it
 *            (`ActivityTimeline`), and *Notes* (FF-30), the phone's footer.
 *
 * Rationale paragraphs on all three boards are not on screen (B14 rule 33).
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Avatar, Button, Notice } from '../../components';
import { FactLines } from '../../components/Facts';
import * as crewOrderQ from '../../db/queries/crewTimeOrder';
import * as documentQ from '../../db/queries/document';
import * as shelfQ from '../../db/queries/documentShelf';
import * as technicianQ from '../../db/queries/technician';
import { ActivityTimeline, statusEvents } from '../../screens/onSite/ActivityScreen';
import { waveScreen } from '../../screens/onSite/common';
import { CrewScreen } from '../../screens/onSite/CrewScreen';
import { crewLines, totalLabour } from '../../screens/onSite/crew';
import { useShellStatus } from '../../navigation/ShellStatus';
import { cannotOpenNow, DocumentsScreen, megabytes, openPaper, opensOutside } from '../../screens/onSite/DocumentsScreen';
import { goTo, useNav, useParam, useWave } from '../../screens/onSite/fieldData';
import { formatClock, formatDate, formatMinutes, sameDay } from '../../screens/onSite/format';
import { employmentWord, leadOf, loadJob } from '../../screens/onSite/job';
import { useTheme } from '../../theme';
import { DetailCard, DetailNone, DetailPane } from '../DetailPane';
import { PickList } from '../Pickable';
import { useDefaultSelection, useSelectedOr } from '../selection';

// ── FF-28 Documents ───────────────────────────────────────────────────────

const Documents = waveScreen('FF-28', DocumentsScreen);

export function DocumentsList() {
  return <Documents />;
}

export function DocumentDetail() {
  const { t } = useTranslation();
  const w = useWave();
  const workOrderId = useParam('workOrderId');
  const job = w ? loadJob(w, workOrderId) : null;
  const first = w && job ? (shelfQ.forJob(w.db, { workOrderId: job.order.id, assetId: job.order.asset_id, templateId: job.order.template_id })[0] ?? null) : null;
  useDefaultSelection(first?.id ?? null);
  const id = useSelectedOr('documentId') ?? first?.id ?? null;
  const [note, setNote] = useState<string | null>(null);
  const online = useShellStatus().connection !== 'offline';
  const doc = w && id ? documentQ.get(w.db, id) : undefined;
  if (!w || !doc) return <DetailNone title={t('field.tablet.pick')} helper={t('field.tablet.pickHelp')} testID="document-detail" />;
  const size = doc.bytes > 0 ? t('field.tablet.megabytes', { mb: megabytes(doc.bytes) }) : null;
  const disabled = !doc.local_path && !opensOutside(doc);
  // DEF-FLD-10805 — a greyed button says why, in the phone row's own words.
  const why = disabled ? cannotOpenNow(doc, online) : null;
  return (
    <DetailPane
      testID="document-detail"
      acts={
        <Button
          grow
          variant="primary"
          disabled={disabled}
          onPress={() => {
            setNote(null);
            void openPaper(w, doc, { online }).then((why) => setNote(why ? t(`field.ff28.${why}`) : null));
          }}
          testID="document-open"
        >
          {t('field.tablet.openIt')}
        </Button>
      }
    >
      <DetailCard
        title={doc.title}
        line={
          opensOutside(doc)
            ? (doc.ref ?? '')
            : [doc.kind?.toUpperCase(), size, doc.local_path ? t('field.tablet.ff28.onTablet') : t('field.tablet.ff28.notOnTablet')]
                .filter(Boolean)
                .join(' · ')
        }
        testID="document-detail-card"
      />
      {note ? (
        <Notice tone="warning" testID="document-note">
          {note}
        </Notice>
      ) : why ? (
        <AppText variant="body" tone="muted" testID="document-why">
          {t(`field.ff28.${why}`)}
        </AppText>
      ) : null}
    </DetailPane>
  );
}

// ── FF-29 Crew ────────────────────────────────────────────────────────────

const Crew = waveScreen('FF-29', CrewScreen);

export function CrewList() {
  return <Crew />;
}

export function CrewDetail() {
  const { t } = useTranslation();
  const theme = useTheme();
  const w = useWave();
  const workOrderId = useParam('workOrderId');
  const job = w ? loadJob(w, workOrderId) : null;
  const lead = job ? leadOf(job) : null;
  useDefaultSelection(lead);
  const picked = useSelectedOr('personId') ?? lead;
  if (!w || !job) return <DetailNone title={t('field.site.notOnPhone.title')} helper={t('field.site.notOnPhone.helper')} testID="crew-detail" />;
  const lines = crewLines(crewOrderQ.listForOrder(w.s, job.order.id), w.clock.now()).sort((a, b) =>
    a.personId === lead ? -1 : b.personId === lead ? 1 : 0,
  );
  return (
    <DetailPane testID="crew-detail">
      <DetailCard title={t('field.tablet.ff29.title')} testID="crew-detail-card">
        {lines.map((line) => {
          const person = technicianQ.get(w.db, line.personId);
          const name = person?.name ?? t('field.ff29.someone');
          const part = line.personId === lead ? t('field.tablet.ff29.leadCloses') : [person?.role, person?.employment ? employmentWord(t, person.employment) : null].filter(Boolean).join(' · ');
          return (
            <View
              key={line.personId}
              testID={`crew-detail-${line.personId}`}
              style={{ gap: theme.space[2], paddingTop: theme.space[3], borderTopWidth: theme.borderWidth.divider, borderTopColor: theme.colors.divider }}
            >
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
                <Avatar name={name} />
                <View style={{ flex: 1 }}>
                  <AppText variant="body" weight="heavy">
                    {name}
                  </AppText>
                  <AppText variant="label" tone="muted">
                    {part}
                  </AppText>
                </View>
                <AppText variant="section">{formatMinutes(line.labourMinutes)}</AppText>
              </View>
              {line.personId === picked ? (
                <FactLines
                  recessed
                  split
                  testID="crew-detail-picked"
                  facts={[
                    { label: t('field.ff29.travel'), value: formatMinutes(line.travelMinutes) },
                    { label: t('field.ff29.arrived'), value: line.arrivedAt ? formatClock(line.arrivedAt) : '—' },
                    { label: t('field.ff29.labour'), value: formatMinutes(line.labourMinutes), tone: 'success', strong: true },
                  ]}
                />
              ) : null}
            </View>
          );
        })}
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
            {t('field.tablet.ff29.total')}
          </AppText>
          <AppText variant="title" testID="crew-detail-total">
            {formatMinutes(totalLabour(lines))}
          </AppText>
        </View>
      </DetailCard>
    </DetailPane>
  );
}

// ── FF-31 Activity ────────────────────────────────────────────────────────

/** A local day's key, `2026-10-20`. */
function dayKey(at: string): string {
  const d = new Date(at);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function useJobDays() {
  const w = useWave();
  const workOrderId = useParam('workOrderId');
  const job = w ? loadJob(w, workOrderId) : null;
  const events = w && job ? statusEvents(w, job.order.id) : [];
  const days = new Map<string, typeof events>();
  for (const e of events) {
    const k = dayKey(e.at);
    days.set(k, [...(days.get(k) ?? []), e]);
  }
  return { w, job, days };
}

export function ActivityDays() {
  const { t } = useTranslation();
  const { w, job, days } = useJobDays();
  const now = w ? w.clock.now() : new Date();
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const items = [...days.entries()].map(([k, list]) => {
    const at = list[0]!.at;
    const title = sameDay(at, now) ? t('field.tablet.today') : sameDay(at, yesterday) ? t('field.tablet.yesterday') : formatDate(at);
    const last = list[0]!.at;
    const firstAt = list[list.length - 1]!.at;
    return {
      id: k,
      title,
      value: list.length > 1 ? `${formatClock(firstAt)}–${formatClock(last)}` : formatClock(last),
      sub: t('field.tablet.events', { count: list.length }),
    };
  });
  return (
    <View style={{ flex: 1 }} testID="screen-FF-31">
      <PickList
        kicker={job?.order.number ?? t('field.screen.ff31')}
        items={items}
        empty={<AppText variant="body" tone="muted">{t('field.ff31.none')}</AppText>}
        testID="activity-days"
      />
    </View>
  );
}

export function ActivityDay() {
  const { t } = useTranslation();
  const navigation = useNav();
  const { w, job, days } = useJobDays();
  const firstDay = [...days.keys()][0] ?? null;
  const picked = useSelectedOr('day') ?? firstDay;
  const events = picked ? (days.get(picked) ?? []) : [];
  if (!w || !job) return <DetailNone title={t('field.site.notOnPhone.title')} helper={t('field.site.notOnPhone.helper')} testID="activity-detail" />;
  return (
    <DetailPane
      testID="activity-detail"
      acts={
        <Button grow onPress={() => goTo(navigation, 'FF-30', { workOrderId: job.order.id })} testID="pane-FF-30">
          {t('field.ff31.notes')}
        </Button>
      }
    >
      <DetailCard title={t('field.tablet.ff31.title')} testID="activity-detail-card">
        <ActivityTimeline events={events} now={w.clock.now()} />
      </DetailCard>
    </DetailPane>
  );
}
