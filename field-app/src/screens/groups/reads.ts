/**
 * Screens built by the "reads" wave — the meter-reading route mode, RW-01 to
 * RW-29 (EP-FLD-10 … EP-FLD-14). Each wave owns its own file so waves never
 * edit the same lines. The screens are in `../reads/`, one file per stretch of
 * the flow; `readsScreen` gives each its telemetry boundary and its address.
 */
import { type ComponentType } from 'react';

import { type ScreenId } from '../../navigation/screens';
import { listBesideDetail, withTabletLayout } from '../../tablet/layoutSlot';
import {
  FindList,
  FoundMeter,
  MasterBalance,
  MasterList,
  MineList,
  MineTotals,
  ReadingDetail,
  ReadingList,
  StillList,
  StillStop,
  StopList,
  StopMeter,
  WalkList,
  WalkStop,
} from '../../tablet/layouts/ReadsLayout';
import { RouteDetail, RoutesList } from '../../tablet/layouts/RoutesLayout';
import { CantRead, DifferentMeter, HighOrLow, SecondLook } from '../reads/check';
import { Dials, ReadEntry, ScanToConfirm, TheCamera, TheReading } from '../reads/entry';
import { MyReads, ReadingSettings } from '../reads/mine';
import { AddMeter, NotOnRoute, RaiseIt } from '../reads/offList';
import { Photos, StillToDo, WhereYouAre } from '../reads/progress';
import { readsScreen } from '../reads/ReadsScreen';
import { Download, MyRoutes, RouteMap, RouteSummary, TheWalk } from '../reads/route';
import { FindMeter, GettingIn, MasterAndSubs, TheStop } from '../reads/stop';
import { Sending, TurnedIn, TurnItIn } from '../reads/turnIn';

const BODIES: Partial<Record<ScreenId, ComponentType>> = {
  'RW-01': MyRoutes,
  'RW-02': RouteSummary,
  'RW-03': Download,
  'RW-04': RouteMap,
  'RW-05': TheWalk,
  'RW-06': TheStop,
  'RW-07': GettingIn,
  'RW-08': FindMeter,
  'RW-09': ReadEntry,
  'RW-10': Dials,
  'RW-11': ScanToConfirm,
  'RW-12': MasterAndSubs,
  'RW-13': TheReading,
  'RW-14': TheCamera,
  'RW-15': HighOrLow,
  'RW-16': SecondLook,
  'RW-17': CantRead,
  'RW-18': DifferentMeter,
  'RW-19': NotOnRoute,
  'RW-20': AddMeter,
  'RW-21': RaiseIt,
  'RW-22': WhereYouAre,
  'RW-23': StillToDo,
  'RW-24': Photos,
  'RW-25': TurnItIn,
  'RW-26': Sending,
  'RW-27': TurnedIn,
  'RW-28': MyReads,
  'RW-29': ReadingSettings,
};

const built: Partial<Record<ScreenId, ComponentType>> = Object.fromEntries(
  (Object.entries(BODIES) as Array<[ScreenId, ComponentType]>).map(([id, body]) => [id, readsScreen(id, body)]),
);

/** T-29: RW-01 T *My routes beside the route* — the list beside RW-02 on a tablet. */
export const SCREENS: Partial<Record<ScreenId, ComponentType>> = {
  ...built,
  'RW-01': withTabletLayout(built['RW-01'] as ComponentType, { frame: 'T2', list: RoutesList, detail: RouteDetail }),
  // T-29: the reading boards whose detail is drawn as part of the same screen.
  'RW-05': listBesideDetail(built['RW-05'] as ComponentType, WalkList, WalkStop),
  'RW-06': listBesideDetail(built['RW-06'] as ComponentType, StopList, StopMeter),
  'RW-08': listBesideDetail(built['RW-08'] as ComponentType, FindList, FoundMeter),
  'RW-12': listBesideDetail(built['RW-12'] as ComponentType, MasterList, MasterBalance),
  'RW-23': listBesideDetail(built['RW-23'] as ComponentType, StillList, StillStop),
  'RW-28': listBesideDetail(built['RW-28'] as ComponentType, MineList, MineTotals),
  'RW-29': listBesideDetail(built['RW-29'] as ComponentType, ReadingList, ReadingDetail),
};
