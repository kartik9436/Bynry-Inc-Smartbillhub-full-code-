/**
 * Which tablet frame every screen sits in (T-27, T-29) — taken row by row from
 * `04-docs/05-modules/18-field-app/08-screen-layouts.md` §2.3, whose frame
 * column was read from each board and checked by eye on a sample. That file
 * says it: *"A row whose frame looks wrong against its image: the image wins,
 * fix the row"* — and the same goes for this table.
 *
 * Counts, from the same file's §1 table: T1 11 · T2 31 · T3 34 · T4 16 = 92
 * boards. `tests/tablet/frameMap.test.ts` holds those four numbers, so a row
 * moved here without moving the document goes red.
 *
 * Two ids have no tablet board of their own:
 *  - FF-09 is the menu, which on a tablet IS the sidebar. The document files
 *    its board under T4 (the board shows the sidebar beside one explanatory
 *    pane); it is never mounted as a screen, so its frame is never drawn.
 *  - SWITCH (*Switch technician*) is drawn only for the phone, as a sheet. Its
 *    twin FF-53 Sign out is a T1 centred column on the tablet, so SWITCH
 *    follows it. ⚠ OUR JUDGMENT — reported, no board exists to check it.
 */
import { type ScreenId } from '../navigation/screens';
import { type FrameId } from './geometry';

const T1: FrameId = 'T1';
const T2: FrameId = 'T2';
const T3: FrameId = 'T3';
const T4: FrameId = 'T4';

export const FRAME_OF: Readonly<Record<ScreenId, FrameId>> = {
  'FF-01': T1, 'FF-02': T1, 'FF-03': T1, 'FF-04': T1, 'FF-05': T1, 'FF-06': T1, 'FF-07': T1, 'FF-08': T1,
  'FF-09': T4,
  'FF-10': T2, 'FF-11': T2, 'FF-12': T2, 'FF-13': T2,
  'FF-14': T3, 'FF-15': T3, 'FF-16': T3, 'FF-17': T3, 'FF-18': T3, 'FF-19': T3,
  'FF-20': T4, 'FF-21': T4,
  'FF-22': T3, 'FF-23': T3, 'FF-24': T3, 'FF-25': T3, 'FF-26': T3, 'FF-27': T3,
  'FF-28': T2, 'FF-29': T2,
  'FF-30': T3,
  'FF-31': T2,
  'FF-32': T3, 'FF-33': T3, 'FF-34': T3,
  'FF-35': T2,
  'FF-36': T3, 'FF-37': T3,
  'FF-38': T4,
  'FF-39': T2, 'FF-40': T2, 'FF-41': T2, 'FF-42': T2, 'FF-43': T2, 'FF-44': T2, 'FF-45': T2, 'FF-46': T2,
  'FF-47': T2, 'FF-48': T2, 'FF-49': T2, 'FF-50': T2, 'FF-51': T2, 'FF-52': T2,
  'FF-53': T1,
  'FF-54': T4, 'FF-55': T4,
  'FF-56': T1, 'FF-57': T1,
  'FF-58': T3, 'FF-59': T3, 'FF-60': T3, 'FF-61': T3,
  'FF-62': T2,
  'FF-63': T4,
  'RW-01': T2,
  'RW-02': T4, 'RW-03': T4, 'RW-04': T4,
  'RW-05': T2, 'RW-06': T2,
  'RW-07': T4,
  'RW-08': T2,
  'RW-09': T3, 'RW-10': T3,
  'RW-11': T4,
  'RW-12': T2,
  'RW-13': T3,
  'RW-14': T4,
  'RW-15': T3, 'RW-16': T3, 'RW-17': T3, 'RW-18': T3, 'RW-19': T3, 'RW-20': T3, 'RW-21': T3, 'RW-22': T3,
  'RW-23': T2,
  'RW-24': T4,
  'RW-25': T3,
  'RW-26': T4, 'RW-27': T4,
  'RW-28': T2, 'RW-29': T2,
  SWITCH: T1,
};

/**
 * Whose context a T3 pane carries. The job boards draw the work order — where,
 * customer, clocks, *The whole job* (FF-22 T, FF-25 T, FF-33 T, FF-37 T); the
 * reading boards draw the route — progress, where, *The walk* (RW-09 T). One
 * pane per family, built once and shared by every T3 screen in it (T-29).
 */
export type ContextFamily = 'job' | 'route';

export function contextFamilyOf(id: ScreenId): ContextFamily {
  return id.startsWith('RW-') ? 'route' : 'job';
}

/**
 * The eight screens that genuinely change shape at width (T-28: *"Today, Job,
 * Map, Assets, Alerts, Readings, Photos, Completed. These are drawn"*). Each
 * has a `tabletLayout` slot (`layoutSlot.ts`) its wave fills. T-29 then
 * gave the other 25 two-pane (T2) boards theirs (`listBesideDetail`, the
 * layouts in `layouts/NearbyLayout`, `OnSiteLayout`, `RaiseLayout`,
 * `MeLayout`, `SettingsLayout`, `ReadsLayout`), so every T2 board shows its
 * list beside its detail; `tests/tablet/screensInFrame.test.tsx` names any
 * that loses its slot. T1, T3 and T4 screens without a layout sit in their
 * frame as their phone screen.
 *
 * Which board each name is: Today FF-10 T (*Today beside the job*), Job FF-15
 * T (*The job with its tasks beside it*), Map FF-13 T (*Stops beside the
 * map*), Assets FF-39 T (*Asset beside its history*), Alerts FF-42 T (*Alerts
 * beside the one you opened*), Readings FF-20 T (*Readings in two columns*),
 * Photos FF-21 T (*The photo gallery, grouped by what it proves*), Completed
 * FF-35 T (*Completed work beside its record*) — each the board whose caption
 * says what width adds.
 */
export const SHAPE_CHANGING: readonly ScreenId[] = [
  'FF-10',
  'FF-15',
  'FF-13',
  'FF-39',
  'FF-42',
  'FF-20',
  'FF-21',
  'FF-35',
];
