/**
 * FF-35 T *Completed work beside its record* (T-28; image
 * `tablet/FF-35-T-completed.png`).
 *
 *   LIST   — the phone's Completed, whole (*Today · This week · Earlier*, the
 *            toned cards, *Show more*), under its own *Completed* bar. A card
 *            picks its job here; its own *Raise follow-on* and *Reopen* still
 *            work.
 *   DETAIL — the picked job's record (the newest closed one until a card is
 *            picked, as the board draws it), with *Reopen* · *Raise a
 *            follow-on* under the same rules as the card (R21, R22: reopen
 *            greyed once the office accepted the close).
 *
 * FB-030 (PO 2026-10-31): the record is ONE component, `CompletedRecord`
 * (B14 rule 43), the same one a phone pushes when its card is tapped. This
 * file dropped the debrief and the signature until then (*"the handset does
 * not keep it on the order"* — it does now, `workOrderClosed.recordClose`),
 * and drew labour and travel minutes, which history no longer shows (no speed
 * figures, coordinator judgment (5)).
 */
import { type NavigationProp, type ParamListBase, useNavigation } from '@react-navigation/native';
import { useTranslation } from 'react-i18next';

import { Button, StatusChip } from '../../components';
import { fromJson } from '../../db/json';
import * as closedQ from '../../db/queries/workOrderClosed';
import { CompletedRecord, useRecordView } from '../../screens/closing/CompletedRecord';
import { CompletedScreen, sinceFor } from '../../screens/closing/CompletedScreen';
import { OUTCOME_TONE } from '../../screens/closing/outcomeTone';
import { waveScreen } from '../../screens/onSite/common';
import { goTo, useWave } from '../../screens/onSite/fieldData';
import { acceptedAt } from '../../screens/onSite/job';
import { useDefaultSelection, useSelectedOr } from '../selection';
import { HeadedPane, PaneScreen } from './parts';

const Completed = waveScreen('FF-35', CompletedScreen);

export function CompletedList() {
  const { t } = useTranslation();
  return (
    <HeadedPane title={t('field.screen.ff35')} testID="completed-list-pane">
      <Completed />
    </HeadedPane>
  );
}

export function CompletedDetail() {
  const { t } = useTranslation();
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  const w = useWave();
  const newest = w ? (closedQ.listClosedSince(w.s, { since: sinceFor('earlier', w.clock.now()), limit: 1 })[0]?.id ?? null) : null;
  useDefaultSelection(newest);
  const id = useSelectedOr('workOrderId') ?? newest;
  const view = useRecordView(id);
  if (!view) {
    return (
      <PaneScreen title={t('field.screen.ff35')} testID="completed-detail">
        <CompletedRecord workOrderId={null} testID="completed-detail-record" />
      </PaneScreen>
    );
  }
  const order = view.order;
  const accepted = acceptedAt({ extra: fromJson<Record<string, unknown>>(order.extra) ?? {} });
  const outcome = order.outcome ? t(`field.site.outcome.${order.outcome}`) : null;

  return (
    <PaneScreen
      title={order.number ?? order.id}
      trailing={outcome ? <StatusChip tone={OUTCOME_TONE[order.outcome ?? ''] ?? 'neutral'}>{outcome}</StatusChip> : undefined}
      testID="completed-detail"
      footer={
        <>
          <Button disabled={accepted !== null} onPress={() => goTo(navigation, 'FF-36', { workOrderId: order.id })} testID="completed-detail-reopen">
            {t('field.ff35.reopen')}
          </Button>
          <Button grow variant="primary" onPress={() => goTo(navigation, 'FF-37', { carriedFrom: order.id })} testID="completed-detail-raise">
            {t('field.ff35.raiseFollowOn')}
          </Button>
        </>
      }
    >
      <CompletedRecord workOrderId={order.id} head={false} testID="completed-detail-record" />
    </PaneScreen>
  );
}
