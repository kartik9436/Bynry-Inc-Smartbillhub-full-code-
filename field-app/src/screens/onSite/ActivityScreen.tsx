/**
 * FF-31 Activity — every status change on the job, newest first, each
 * stamped with who and when (US-FLD-030; R10). Append only: this screen
 * reads, it never edits a row.
 *
 * A row's title is its STATUS in the catalogue's words (`field.ff31.status.*`,
 * one per status the app knows: raised, pushed, accepted, departed, arrived,
 * safety passed, work started, joined, step done, closed); a status the app
 * does not know shows the server's own text rather than nothing. Never an id
 * (R35). The newest row is drawn hollow — it is where the job is now.
 *
 * *Notes* opens FF-30 (the board's link).
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { ScreenFrame } from '../../components/ScreenFrame';
import * as activityQ from '../../db/queries/activity';
import { type ActivityRow } from '../../db/queries/activity';
import type { StatusTone } from '../../theme';
import { useTheme } from '../../theme';
import { NotOnPhone, useHeader, type WaveScreenProps } from './common';
import { goTo, useNav, useJobId, type Wave } from './fieldData';
import { formatClock, formatStamp, sameDay } from './format';
import { loadJob } from './job';

/** The statuses the app has words for. */
export const KNOWN_STATUSES = [
  'raised',
  'pushed',
  'accepted',
  'departed',
  'arrived',
  'safety_passed',
  'work_started',
  'crew_joined',
  'step_done',
  'closed',
  'proceeded_unverified',
] as const;

const TONES: Partial<Record<string, StatusTone>> = {
  safety_passed: 'success',
  work_started: 'success',
  closed: 'success',
  crew_joined: 'info',
  proceeded_unverified: 'warning',
};

/**
 * The timeline itself, newest first — the phone's whole screen, and on a
 * tablet one day of it beside the list of days (FF-31 T *What happened*).
 */
export function ActivityTimeline(props: { events: readonly ActivityRow[]; now: Date }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const { events, now } = props;
  const titleOf = (status: string | null, text: string | null) => {
    if (status && (KNOWN_STATUSES as readonly string[]).includes(status)) {
      return t(`field.ff31.status.${status}`, { name: text ?? '' });
    }
    return text ?? status ?? '';
  };
  return (
    <>
      {events.map((e, i) => {
        const tone = TONES[e.status ?? ''] ?? 'neutral';
        const ink = theme.colors.statusInk[tone];
        const known = e.status !== null && (KNOWN_STATUSES as readonly string[]).includes(e.status);
        const when = sameDay(e.at, now) ? formatClock(e.at) : formatStamp(e.at);
        const detail =
          e.status === 'closed' && e.text
            ? t(`field.site.outcome.${e.text}`)
            : known && e.status !== 'crew_joined'
              ? e.text
              : null;
        const sub = [when, e.author, detail].filter(Boolean).join(' · ');
        return (
          <View
            key={e.id}
            accessible
            accessibilityLabel={`${titleOf(e.status, e.text)}, ${sub}`}
            testID={`event-${i}`}
            style={{ flexDirection: 'row', gap: theme.space[3] }}
          >
            <View style={{ alignItems: 'center', width: theme.space[5] }}>
              <View
                style={{
                  width: theme.space[4],
                  height: theme.space[4],
                  borderRadius: theme.radius.sm,
                  borderWidth: theme.borderWidth.emphasis,
                  borderColor: i === 0 ? theme.colors.statusInk.success : ink,
                  backgroundColor: i === 0 ? theme.colors.card : ink,
                }}
              />
              {i < events.length - 1 ? (
                <View style={{ flex: 1, width: theme.borderWidth.emphasis, backgroundColor: theme.colors.divider }} />
              ) : null}
            </View>
            <View style={{ flex: 1, paddingBottom: theme.space[3] }}>
              <AppText variant="body" weight="heavy">
                {titleOf(e.status, e.text)}
              </AppText>
              <AppText variant="label" tone="muted">
                {sub}
              </AppText>
            </View>
          </View>
        );
      })}
    </>
  );
}

/** Every status change on the order, newest first. */
export function statusEvents(w: Wave, workOrderId: string): ActivityRow[] {
  return activityQ
    .listForOrder(w.s, workOrderId)
    .filter((a) => a.kind === 'status')
    .reverse();
}

export function ActivityScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const navigation = useNav();
  const job = loadJob(w, useJobId());
  useHeader({ chip: job?.order.number ?? null });
  if (!job) return <NotOnPhone />;

  const now = w.clock.now();
  const events = statusEvents(w, job.order.id);

  return (
    <ScreenFrame
      footer={
        <Button grow onPress={() => goTo(navigation, 'FF-30', { workOrderId: job.order.id })} testID="door-FF-30">
          {t('field.ff31.notes')}
        </Button>
      }
    >
      <ActivityTimeline events={events} now={now} />
      {events.length === 0 ? (
        <AppText variant="body" tone="muted">
          {t('field.ff31.none')}
        </AppText>
      ) : null}
    </ScreenFrame>
  );
}
