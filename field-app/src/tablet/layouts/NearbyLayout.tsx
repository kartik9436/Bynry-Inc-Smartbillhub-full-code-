/**
 * FF-11 T *Nearby* and FF-12 T *Claim* (T-29; images `tablet/FF-11-T-nearby.png`,
 * `tablet/FF-12-T-claim.png`) — both draw the phone's Nearby list on the left.
 *
 *   FF-11 LIST   — the phone's Nearby, whole (radius, the cards, *Claim*). A
 *                  card's body picks its job; the first is picked as drawn.
 *   FF-11 DETAIL — the picked job: its address, number and type, then Due ·
 *                  Estimated · Priority · Distance, and *On the map* · *Claim
 *                  it* (FF-12 with the job, as the card's own *Claim* does).
 *   FF-12 LIST   — the same Nearby list; a card's *Claim* picks rather than
 *                  pushing (`SelectOnOpen`), so the list stays beside it.
 *   FF-12 DETAIL — the phone's FF-12 itself, handed the picked job as its
 *                  `job` param (`SelectedParam` carries the record: the job is
 *                  the server's and cannot be re-read on the handset by id).
 *
 * Not on screen, by rule 33: FF-11 T's paragraph on why Nearby never reorders
 * the day, and FF-12 T's on contractors claiming (rationale). FF-11 T's
 * *Service* and *Meters* lines are facts the server's nearby answer does not
 * carry (`nearbyApi.ts` `NearbyJob`); they are left out rather than guessed.
 */
import { type NavigationProp, type ParamListBase, useNavigation } from '@react-navigation/native';
import { useTranslation } from 'react-i18next';

import { Button, StatusChip } from '../../components';
import { type Fact } from '../../components/Facts';
import { ClaimScreen } from '../../screens/theDay/ClaimScreen';
import { estimate, miles, shortDate } from '../../screens/theDay/format';
import { openScreen } from '../../screens/theDay/go';
import { priorityTone } from '../../screens/theDay/jobStatus';
import { type NearbyJob } from '../../screens/theDay/nearbyApi';
import { NearbyScreen } from '../../screens/theDay/NearbyScreen';
import { DetailCard, DetailNone, DetailPane } from '../DetailPane';
import { SelectedParam, SelectOnOpen, usePick } from '../selection';

export function NearbyList() {
  return <NearbyScreen />;
}

export function NearbyDetail() {
  const { t, i18n } = useTranslation();
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  const pick = usePick();
  const job = (pick.payload as NearbyJob | undefined) ?? null;
  if (!job) return <DetailNone title={t('field.tablet.pick')} helper={t('field.tablet.pickHelp')} testID="nearby-detail" />;
  const due = shortDate(job.dueAt, i18n.language);
  const facts: Fact[] = [];
  if (due) facts.push({ label: t('field.claim.due'), value: due });
  const est = estimate(t, job.estMinutes);
  if (est) facts.push({ label: t('field.claim.estimated'), value: est });
  if (job.distanceMi != null) facts.push({ label: t('field.claim.distance'), value: t('field.nearby.milesShort', { miles: miles(job.distanceMi) }) });
  if (job.takenBy) facts.push({ label: t('field.tablet.nearby.taken'), value: job.takenBy });
  return (
    <DetailPane
      testID="nearby-detail"
      acts={
        <>
          <Button grow onPress={() => openScreen(navigation, 'FF-13')} testID="pane-FF-13">
            {t('field.tablet.onTheMap')}
          </Button>
          {job.takenBy ? null : (
            <Button grow variant="primary" onPress={() => openScreen(navigation, 'FF-12', { job })} testID="pane-FF-12">
              {t('field.tablet.nearby.claimIt')}
            </Button>
          )}
        </>
      }
    >
      <DetailCard
        title={job.address ?? job.number ?? ''}
        line={[job.number, job.type].filter(Boolean).join(' · ')}
        trailing={job.priorityCode ? <StatusChip tone={priorityTone(job.priorityCode)}>{job.priorityCode}</StatusChip> : undefined}
        facts={facts}
        testID="nearby-detail-card"
      />
    </DetailPane>
  );
}

export function ClaimList() {
  return (
    <SelectOnOpen opens="FF-12" param="job">
      <NearbyScreen />
    </SelectOnOpen>
  );
}

export function ClaimDetail() {
  return (
    <SelectedParam param="job">
      <ClaimScreen />
    </SelectedParam>
  );
}
