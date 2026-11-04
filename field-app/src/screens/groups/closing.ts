/** Screens built by the "closing" wave. Each wave owns its own file so waves never edit the same lines. */
import { type ComponentType } from 'react';

import { type ScreenId } from '../../navigation/screens';
import { withTabletLayout } from '../../tablet/layoutSlot';
import { CompletedDetail, CompletedList } from '../../tablet/layouts/CompletedLayout';
import { CloseScreen } from '../closing/CloseScreen';
import { CompletedScreen } from '../closing/CompletedScreen';
import { DebriefScreen } from '../closing/DebriefScreen';
import { ReopenScreen } from '../closing/ReopenScreen';
import { SignatureScreen } from '../closing/SignatureScreen';
import { waveScreen } from '../onSite/common';

export const SCREENS: Partial<Record<ScreenId, ComponentType>> = {
  'FF-32': waveScreen('FF-32', DebriefScreen),
  'FF-33': waveScreen('FF-33', SignatureScreen),
  'FF-34': waveScreen('FF-34', CloseScreen),
  // T-28: FF-35 T *Completed work beside its record*.
  'FF-35': withTabletLayout(waveScreen('FF-35', CompletedScreen), { frame: 'T2', list: CompletedList, detail: CompletedDetail }),
  'FF-36': waveScreen('FF-36', ReopenScreen),
};
