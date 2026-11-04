/** Screens built by the "theDay" wave. Each wave owns its own file so waves never edit the same lines.
 *  T-16 The day (FF-10 Today, FF-11 Nearby, FF-12 Claim, FF-63 Home) and T-17 Getting there (FF-13 Map, FF-14 Stop). */
import { type ComponentType, createElement } from 'react';

import { type ScreenId } from '../../navigation/screens';
import { listBesideDetail, withTabletLayout } from '../../tablet/layoutSlot';
import { ClaimDetail, ClaimList, NearbyDetail, NearbyList } from '../../tablet/layouts/NearbyLayout';
import { StopsList, StopsMap } from '../../tablet/layouts/MapLayout';
import { TodayDetail, TodayList } from '../../tablet/layouts/TodayLayout';
import { ClaimScreen } from '../theDay/ClaimScreen';
import { HomeScreen } from '../theDay/HomeScreen';
import { MapScreen } from '../theDay/MapScreen';
import { NearbyScreen } from '../theDay/NearbyScreen';
import { StopScreen } from '../theDay/StopScreen';
import { TodayScreen } from '../theDay/TodayScreen';

/** T-28: on a tablet, FF-10 *Today beside the job* and FF-13 *Stops beside the map*. */
// Fresh components, so marking them never marks the phone screens themselves
// (the list pane mounts `TodayScreen` too).
function TodayPhone() {
  return createElement(TodayScreen);
}
function MapPhone() {
  return createElement(MapScreen);
}

export const SCREENS: Partial<Record<ScreenId, ComponentType>> = {
  'FF-10': withTabletLayout(TodayPhone, { frame: 'T2', list: TodayList, detail: TodayDetail }),
  'FF-11': listBesideDetail(NearbyScreen, NearbyList, NearbyDetail),
  'FF-12': listBesideDetail(ClaimScreen, ClaimList, ClaimDetail),
  'FF-13': withTabletLayout(MapPhone, { frame: 'T2', list: StopsList, detail: StopsMap }),
  'FF-14': StopScreen,
  'FF-63': HomeScreen,
};
