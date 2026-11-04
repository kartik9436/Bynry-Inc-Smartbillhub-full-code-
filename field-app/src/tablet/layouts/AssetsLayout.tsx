/**
 * FF-39 T *Asset beside its history* (T-28; image `tablet/FF-39-T-asset.png`).
 *
 *   LIST   — *Assets*: the phone's asset search (FF-41) — the box, the scan
 *            button, the hits on this phone and the line saying only today's
 *            assets are here (R42). A hit, which opens FF-39 on a phone, picks
 *            it here (`SelectOnOpen`), so the search and its hits stay put.
 *   DETAIL — the picked meter under its own bar (*W-4471* and its state): the
 *            phone's FF-39 itself, handed the pick as its `assetId`
 *            (`SelectedParam`), so it reads the store exactly as it does when
 *            Scan or Search opens it. Nothing picked → the meter the screen
 *            was opened with (Scan, the job), as on the phone.
 */
import { useTranslation } from 'react-i18next';

import { StatusChip } from '../../components';
import { waveScreen } from '../../screens/onSite/common';
import { useParam, useWave } from '../../screens/onSite/fieldData';
import { AssetScreen, assetFor } from '../../screens/raise/AssetScreen';
import { AssetSearchScreen } from '../../screens/raise/AssetSearchScreen';
import { SelectedParam, SelectOnOpen, useSelectedOr } from '../selection';
import { HeadedPane } from './parts';

const Search = waveScreen('FF-41', AssetSearchScreen);
const Asset = waveScreen('FF-39', AssetScreen);

export function AssetsList() {
  const { t } = useTranslation();
  return (
    <HeadedPane title={t('field.nav.item.assets')} testID="assets-list-pane">
      <SelectOnOpen opens="FF-39" param="assetId">
        <Search />
      </SelectOnOpen>
    </HeadedPane>
  );
}

function useAssetTitle() {
  const { t } = useTranslation();
  const w = useWave();
  const workOrderId = useParam('workOrderId');
  const assetId = useSelectedOr('assetId');
  const asset = w ? assetFor(w, assetId, workOrderId) : null;
  return { title: asset?.serial ?? asset?.badge ?? t('field.screen.ff39'), active: asset ? asset.status === 'active' : null };
}

export function AssetDetail() {
  const { t } = useTranslation();
  const { title, active } = useAssetTitle();
  return (
    <SelectedParam param="assetId">
      <HeadedPane
        title={title}
        trailing={
          active === null ? undefined : (
            <StatusChip tone={active ? 'success' : 'warning'}>{active ? t('field.ff39.installed') : t('field.site.asset.pending')}</StatusChip>
          )
        }
        testID="asset-detail-pane"
      >
        <Asset />
      </HeadedPane>
    </SelectedParam>
  );
}
