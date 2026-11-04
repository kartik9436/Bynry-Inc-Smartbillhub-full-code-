/**
 * FF-12 Claim — *Take this job?* (T-16; US-FLD-023). Built from
 * `wireframes/phone/FF-12-claim.png` and `tablet/FF-12-T-claim.png`.
 *
 * The board draws it as a sheet over Nearby; here it is the pushed screen the
 * route table makes it (AD-13: pushed screens and native back, not stacked
 * overlays), with the sheet's content in the sheet's order: the job card
 * (*UNASSIGNED · P3*, the address, the number and type, then Distance ·
 * Estimated · Due), what claiming does to the day (*Your day grows by 12
 * minutes. 6h 20m becomes 6h 32m.*), what it does for everyone else
 * (*Dispatch is told. No one else can take it.*), and *Cancel · Claim*.
 *
 * The day's length is the technician's OWN open jobs today, counted from the
 * handset (`db/queries/day.dayCounts`), plus this job's estimate. With no
 * store, or no estimate, that sentence is left out rather than guessed.
 *
 * The claim itself is the server's (N15, online only; `nearbyApi.ts`). Taken
 * a moment ago → *Taken by R. Patel* in place of the button. Whether a claim
 * outside the technician's skills is refused is `CLAIM_SKILL_QUESTION` — the
 * handset shows whatever the server answers and never filters by skill.
 */
import { useNavigation, useRoute } from '@react-navigation/native';
import { useLayoutEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, EmptyState, ListRow, Notice, Page, StatusChip } from '../../components';
import { dayBounds, dayCounts } from '../../db/queries/day';
import { useTheme } from '../../theme';
import { duration, estimate, miles, shortDate } from './format';
import { useFieldData, useScoped } from './fieldData';
import { openScreen } from './go';
import { priorityTone } from './jobStatus';
import { type NearbyJob, NearbyGapError } from './nearbyApi';
import { ScreenBoundary } from './ScreenBoundary';

type Outcome = null | { kind: 'taken'; by: string | null } | { kind: 'gap' } | { kind: 'failed' };

function ClaimBody() {
  const theme = useTheme();
  const { t, i18n } = useTranslation();
  const navigation = useNavigation();
  const route = useRoute();
  const job = (route.params as { job?: NearbyJob } | undefined)?.job ?? null;
  const { nearby, now } = useFieldData();
  const s = useScoped();
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<Outcome>(job?.takenBy ? { kind: 'taken', by: job.takenBy } : null);

  useLayoutEffect(() => {
    navigation.setOptions({ title: t('field.claim.title') });
  }, [navigation, t]);

  if (!job) {
    return (
      <Page testID="screen-FF-12">
        <EmptyState
          title={t('field.claim.noJob')}
          helper={t('field.claim.noJobHelp')}
          ctaLabel={t('field.today.nearby')}
          onCta={() => openScreen(navigation, 'FF-11')}
        />
      </Page>
    );
  }

  const planned = s ? dayCounts(s, { ...dayBounds(now(), 0), today: true }).plannedMinutes : null;
  const grows = job.estMinutes;
  const due = shortDate(job.dueAt, i18n.language);
  const numberLine = [job.number, job.type].filter(Boolean).join(' · ');

  const claim = async () => {
    setBusy(true);
    try {
      const answer = await nearby.claim(job.id);
      if (answer.ok) {
        openScreen(navigation, 'FF-10');
        return;
      }
      setOutcome({ kind: 'taken', by: answer.takenBy });
    } catch (err) {
      setOutcome(err instanceof NearbyGapError ? { kind: 'gap' } : { kind: 'failed' });
    } finally {
      setBusy(false);
    }
  };

  const taken = outcome?.kind === 'taken';

  return (
    <Page
      testID="screen-FF-12"
      footer={
        <>
          <Button grow onPress={() => navigation.goBack()} testID="door-FF-11">
            {t('field.common.cancel')}
          </Button>
          {taken ? null : (
            <Button variant="primary" grow busy={busy} onPress={() => void claim()} testID="claim-confirm">
              {t('field.nearby.claim')}
            </Button>
          )}
        </>
      }
    >
      <AppText variant="title">{t('field.claim.title')}</AppText>
      <Card>
        <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
          <StatusChip tone="neutral">{t('field.claim.unassigned')}</StatusChip>
          {job.priorityCode ? <StatusChip tone={priorityTone(job.priorityCode)}>{job.priorityCode}</StatusChip> : null}
        </View>
        <View>
          <AppText variant="section">{job.address ?? job.number ?? ''}</AppText>
          {numberLine ? (
            <AppText variant="label" tone="muted">
              {numberLine}
            </AppText>
          ) : null}
        </View>
        <View>
          {job.distanceMi != null ? (
            <ListRow divider label={t('field.claim.distance')} value={t('field.nearby.milesShort', { miles: miles(job.distanceMi) })} />
          ) : null}
          {grows != null ? <ListRow divider label={t('field.claim.estimated')} value={estimate(t, grows) ?? ''} /> : null}
          {due ? <ListRow divider label={t('field.claim.due')} value={due} /> : null}
        </View>
      </Card>
      {grows != null && planned != null ? (
        <Notice tone="info" testID="claim-day-grows">
          {t('field.claim.dayGrows', {
            minutes: grows,
            before: duration(t, planned),
            after: duration(t, planned + grows),
          })}
        </Notice>
      ) : null}
      {taken ? (
        <Notice tone="warning" testID="claim-taken">
          {outcome.by ? t('field.nearby.takenBy', { name: outcome.by }) : t('field.claim.takenSomeone')}
        </Notice>
      ) : outcome?.kind === 'gap' ? (
        <Notice tone="danger" testID="claim-gap">
          {t('field.claim.gap')}
        </Notice>
      ) : outcome?.kind === 'failed' ? (
        <Notice tone="danger" testID="claim-failed">
          {t('field.claim.failed')}
        </Notice>
      ) : (
        <AppText variant="label" tone="muted" testID="claim-consequence">
          {t('field.claim.consequence')}
        </AppText>
      )}
    </Page>
  );
}

export function ClaimScreen() {
  return (
    <ScreenBoundary screen="FF-12">
      <ClaimBody />
    </ScreenBoundary>
  );
}
