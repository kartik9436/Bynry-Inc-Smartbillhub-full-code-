/** Screens built by the "raise" wave. Each wave owns its own file so waves never edit the same lines. */
import { type ComponentType } from 'react';

import { type ScreenId } from '../../navigation/screens';
import { listBesideDetail, withTabletLayout } from '../../tablet/layoutSlot';
import { AssetDetail, AssetsList } from '../../tablet/layouts/AssetsLayout';
import { HistoryList, SearchDetail, SearchList, TemplateDetail, TemplatesList, VisitDetail } from '../../tablet/layouts/RaiseLayout';
import { waveScreen } from '../onSite/common';
import { AssetHistoryScreen } from '../raise/AssetHistoryScreen';
import { AssetScreen } from '../raise/AssetScreen';
import { AssetSearchScreen } from '../raise/AssetSearchScreen';
import { PickTemplateScreen } from '../raise/PickTemplateScreen';
import { RaiseScreen } from '../raise/RaiseScreen';
import { ScanScreen } from '../raise/ScanScreen';

export const SCREENS: Partial<Record<ScreenId, ComponentType>> = {
  'FF-37': waveScreen('FF-37', RaiseScreen),
  'FF-38': waveScreen('FF-38', ScanScreen),
  // T-28: FF-39 T *Asset beside its history* — the search beside the meter.
  'FF-39': withTabletLayout(waveScreen('FF-39', AssetScreen), { frame: 'T2', list: AssetsList, detail: AssetDetail }),
  // T-29: the boards whose detail is drawn as part of the same screen.
  'FF-40': listBesideDetail(waveScreen('FF-40', AssetHistoryScreen), HistoryList, VisitDetail),
  'FF-41': listBesideDetail(waveScreen('FF-41', AssetSearchScreen), SearchList, SearchDetail),
  'FF-62': listBesideDetail(waveScreen('FF-62', PickTemplateScreen), TemplatesList, TemplateDetail),
};
