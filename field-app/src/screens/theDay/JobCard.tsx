/**
 * One job on FF-10 Today: the state strip with its priority, the customer,
 * the address, *WO-4822 · Meter exchange*, *08:00–12:00 · 12 min away*, and
 * the actions *Start · Navigate · ⋮*.
 *
 * WHAT IS DRAWN AND NOT BUILT, and why (reported, not hidden):
 *  - **Hold.** No field act sets a job on hold: the outbox has no `hold` kind
 *    and the server has no route for it (`sync/outbox.ts` JOB_SYNC_KINDS and
 *    UNROUTED_KINDS). A Hold button would be a live control with nothing
 *    behind it (CLAUDE.md law 2's mirror), so it is not drawn until that act
 *    exists.
 *  - **"Missing: 5/8" water meter".** Comparing a job's materials with the van
 *    needs the van's stock on the handset, which no table holds yet.
 *  - **Minutes away** need a position and a route time; with a position the
 *    card shows the straight-line distance in miles, and nothing without one.
 *
 * The body opens the job (FF-15); *Navigate* hands the street address to the
 * phone's maps app (Security §5). The first button is the job's NEXT ACT
 * (DEF-FLD-10607; PO 2026-10-26, *"A Resume — start"*; `theJob/nextPart.ts`
 * `cardAct`, the same rule as FF-15's *Continue*): *Start* opens the safety
 * checks (FF-16) on a job nothing has been captured on; *Resume* opens the
 * next unfinished part of a started one; *Finish* opens Debrief (FF-32) once
 * every part is done; a closed job has no button.
 *
 * TAKING THE JOB (DEF-FLD-10579, PO 2026-10-24): *Start* also ACCEPTS a job not
 * yet accepted (the screen passes it through `useAcceptance`). Until then a
 * ✕ *Decline* sits beside Start — in the slot the board draws *Hold* in, which
 * is not built (above). A declined job stays listed, marked *Declined*, with
 * neither: the server refuses an accept after a decline, and the dispatcher
 * moves it. Once started, *Hand back* on FF-15 is the way out.
 */
import { useTranslation } from 'react-i18next';
import { Pressable, Text, View } from 'react-native';

import { AppText, Button, Glyph, IconButton, StatusChip } from '../../components';
import { textStyle } from '../../components/AppText';
import type { DayJob } from '../../db/queries/day';
import type { CardAct } from '../theJob/nextPart';
import type { Acceptance } from './acceptance';
import { useTheme } from '../../theme';
import { priorityTone, statusLook } from './jobStatus';
import { windowText } from './format';

export interface JobCardProps {
  job: DayJob;
  /** "0.2 mi" when the handset knows where it is; null otherwise. */
  distance: string | null;
  onOpen: () => void;
  /** The first button: *Start*, *Resume* or *Finish*, or none on a closed job. */
  onStart: () => void;
  /** Which of the three the first button is (`cardAct`). Absent: *Start*. */
  act?: CardAct['act'];
  onNavigate: (() => void) | null;
  onMore: () => void;
  /** Picked in the tablet's list beside its detail (FF-10 T draws it with a heavy rule). */
  selected?: boolean;
  /** Taken, declined, or neither yet (DEF-FLD-10579). Absent: neither, and no Decline. */
  acceptance?: Acceptance;
  /** ✕ *Decline*, offered only while the job is neither taken nor declined. */
  onDecline?: () => void;
}

const ACT_WORD = { start: 'field.today.start', resume: 'field.today.resume', finish: 'field.today.finish' } as const;

export function JobCard({ job, distance, onOpen, onStart, act = 'start', onNavigate, onMore, selected = false, acceptance, onDecline }: JobCardProps) {
  const theme = useTheme();
  const { t } = useTranslation();
  const c = theme.colors;
  const look = statusLook(job.dispatchState);
  const pair = c.status[look.tone];
  const prio = job.priorityCode ? c.status[priorityTone(job.priorityCode)] : null;
  const stateWord = look.labelKey ? t(look.labelKey) : '';
  const numberLine = [job.number, job.type].filter(Boolean).join(' · ');
  const whenLine = [windowText(job.windowStart, job.windowEnd), distance].filter(Boolean).join(' · ');
  const name = job.customerName ?? job.addressLine ?? job.number ?? '';

  return (
    <View
      testID={`job-${job.id}`}
      style={{
        backgroundColor: c.card,
        borderColor: selected ? c.text : c.border,
        borderWidth: selected ? theme.borderWidth.emphasis : theme.borderWidth.card,
        borderRadius: theme.radius.lg,
        overflow: 'hidden',
      }}
    >
      <View
        testID={`job-${job.id}-state`}
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          backgroundColor: pair.bg,
          paddingHorizontal: theme.space[4],
          paddingVertical: theme.space[2],
        }}
      >
        <Text
          style={[
            textStyle(theme, 'micro', 'heavy'),
            { color: pair.fg, flexGrow: 1, textTransform: 'uppercase', letterSpacing: theme.tracking.kicker * theme.type.micro },
          ]}
        >
          {stateWord}
        </Text>
        {job.priorityCode ? (
          <Text style={[textStyle(theme, 'micro', 'heavy'), { color: theme.name === 'sunlight' ? pair.fg : prio?.fg }]}>
            {job.priorityCode}
          </Text>
        ) : null}
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={[stateWord, job.priorityCode, name, job.addressLine, numberLine, whenLine].filter(Boolean).join(', ')}
        accessibilityHint={t('field.today.openJobHint')}
        accessibilityState={{ selected }}
        onPress={onOpen}
        testID={`job-${job.id}-open`}
        style={{ paddingHorizontal: theme.space[4], paddingTop: theme.space[3], minHeight: theme.touch.control }}
      >
        <AppText variant="section">{name}</AppText>
        {job.customerName && job.addressLine ? <AppText variant="body">{job.addressLine}</AppText> : null}
        {numberLine ? (
          <AppText variant="label" tone="muted">
            {numberLine}
          </AppText>
        ) : null}
        {whenLine ? (
          <AppText variant="label" tone="muted">
            {whenLine}
          </AppText>
        ) : null}
      </Pressable>
      <View style={{ flexDirection: 'row', gap: theme.touch.clear, padding: theme.space[4] }}>
        {acceptance === 'declined' ? (
          <View style={{ flexGrow: 1, justifyContent: 'center' }} testID={`job-${job.id}-declined`}>
            <StatusChip tone="warning">{t('field.accept.declined')}</StatusChip>
          </View>
        ) : act === 'none' ? null : (
          <Button variant="primary" size="sm" grow onPress={onStart} testID={`job-${job.id}-${act}`}>
            {t(ACT_WORD[act])}
          </Button>
        )}
        {acceptance === 'pending' && onDecline ? (
          <Button
            size="sm"
            icon={<Glyph name="close" />}
            onPress={onDecline}
            accessibilityLabel={t('field.accept.declineA11y', { job: job.number ?? name })}
            testID={`job-${job.id}-decline`}
          >
            {t('field.accept.decline')}
          </Button>
        ) : null}
        {onNavigate ? (
          <Button size="sm" grow onPress={onNavigate} testID={`job-${job.id}-navigate`}>
            {t('field.today.navigate')}
          </Button>
        ) : null}
        <IconButton label={t('field.today.more')} outlined onPress={onMore} testID={`job-${job.id}-more`}>
          <Glyph name="menu" />
        </IconButton>
      </View>
    </View>
  );
}
