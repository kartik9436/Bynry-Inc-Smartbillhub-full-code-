/**
 * The doors: for every screen, the screens it opens.
 *
 * R98: *"A screen is not finished until something opens it, and the thing that
 * opens it goes to the right address."* R99: *"Sweep the doors, do not reason
 * about them."* So this table is not reasoned — it was SWEPT from the design:
 * every `<a href>` on every phone and reads board of the design canvas
 * (version of 2026-10-21), mapped board → screen id, 92 boards. The placeholder
 * screens render exactly these as buttons, and `tests/navigation/doors.test.ts`
 * reads this table, the drawer and the tabs to prove every screen has a way in
 * and can be reached from the splash.
 *
 * ⚠ **THE LINKS ALONE LEFT SIX SCREENS UNREACHABLE, AND THE IMAGES CLOSE
 * THEM.** The sweep found three closed loops — FF-11 ⇄ FF-12, RW-15 ⇄ RW-16,
 * and FF-51 ⇄ RW-29 (taking FF-52, FF-54 and FF-55 with it) — each pair
 * pointing only at each other. Every screen had an inbound link, so a count of
 * inbound links passed; only a walk from the splash fails. The drawings (B14
 * rule 42: the image is the specification) show the missing doors, and they
 * are added below under `FROM_THE_IMAGES` with what each one is, so the next
 * reader can check them against the picture rather than trust them:
 *   - FF-44 Profile draws *Shifts and time off*, *Timesheet* and *Settings* rows;
 *     the board links only the first.
 *   - FF-11 Nearby draws the *Mine · Nearby* switch under Today's title; FF-10's
 *     own board does not draw it (reported as a design gap).
 *   - FF-10 T Today (the tablet board) draws *Open the stop*, FF-14; the phone
 *     board reaches the stop only from the map, and the phone build puts the
 *     same door under the card's ⋮ (added in the integration lane).
 *   - RW-15 opens from RW-09 when the figure is out of range — the design's
 *     note: *"Go under 48,210 or over 56,000 and the figure turns amber, the
 *     button becomes Accept anyway"*. It is a state of the read, not a link.
 *   - FF-15 Job's *Continue* opens Debrief, FF-32, once safety, tasks,
 *     materials and readings are all done. The board draws only the mid-job
 *     state; the PO approved the door on beta report MQ-024 (DEF-FLD-10586).
 *
 * `SWITCH` is the *Switch technician* sheet (`phone/Switch.png`).
 *
 * ⚠ **A BACK ARROW'S ROW HERE IS ITS FALLBACK, NOT WHERE IT GOES
 * (DEF-FLD-10607; PO 2026-10-26, *"A for back button"*).** The sweep records
 * each board's back arrow as a link (FF-16 → FF-15, FF-27 → FF-10…), and the
 * screens once followed it as a fixed door — Today → Start → Safety → back
 * opened the job instead of Today. Every arrow now goes back through history
 * and follows its row here only when there is none (a notification or a cold
 * link), carrying the job (`navigation/back.tsx`). The rows stay: they are
 * still the drawn way out of a screen opened cold, and the reachability walk
 * below still needs them.
 *
 * ⚠ **ONE SWEPT LINK WAS CORRECTED BY THE IMAGES: FF-09's *Assets* IS FF-41,
 * NOT FF-39 (DEF-FLD-10604, beta MQ-046).** The sweep mapped the menu board's
 * *Assets* link to FF-39, one asset, which needs a meter and so opened on
 * *"Not on this phone"*. The drawing settles it: `phone/FF-41-asset-search.png`
 * is the page titled *Assets* under the menu icon, with the scan icon and
 * *"Only today's assets are here."*; `phone/FF-39-asset.png` is a meter's
 * serial under a back arrow, reached from a search hit, a scan or a job.
 * FF-41 → FF-39 → FF-40 is the way to one meter and its history.
 */
import { type ScreenId } from './screens';

/** Swept from the boards' links. */
const FROM_THE_LINKS: Record<ScreenId, readonly ScreenId[]> = {
  'FF-01': ['FF-02'],
  'FF-02': ['FF-05', 'FF-03'],
  'FF-03': ['FF-05', 'FF-04'],
  'FF-04': ['FF-05'],
  'FF-05': ['FF-07', 'FF-06', 'FF-56'],
  'FF-06': ['FF-05'],
  'FF-07': ['FF-08'],
  'FF-08': ['FF-10'],
  'FF-09': ['FF-10', 'FF-35', 'FF-13', 'FF-41', 'FF-42', 'RW-01', 'RW-08', 'RW-28', 'FF-44', 'FF-48', 'FF-46', 'FF-47', 'FF-49', 'FF-50', 'SWITCH', 'FF-53'],
  'FF-10': ['FF-09', 'FF-42', 'FF-50', 'FF-15', 'FF-16', 'FF-63', 'RW-01'],
  'FF-11': ['FF-09', 'FF-50', 'FF-10', 'FF-12', 'FF-42'],
  'FF-12': ['FF-11', 'FF-10'],
  'FF-13': ['FF-09', 'FF-14', 'FF-10', 'FF-42'],
  'FF-14': ['FF-15'],
  'FF-15': ['FF-10', 'FF-50', 'FF-31', 'FF-25', 'FF-39', 'FF-16', 'FF-17', 'FF-23', 'FF-19', 'FF-20', 'FF-60', 'FF-61', 'FF-28', 'FF-29', 'FF-30', 'FF-58'],
  'FF-16': ['FF-15', 'FF-17'],
  'FF-17': ['FF-15', 'FF-18', 'FF-23', 'FF-20'],
  'FF-18': ['FF-17'],
  'FF-19': ['FF-17'],
  'FF-20': ['FF-15', 'FF-59', 'FF-21', 'FF-32'],
  'FF-21': ['FF-15', 'FF-34', 'FF-22'],
  'FF-22': ['FF-21'],
  'FF-23': ['FF-15', 'FF-38', 'FF-49'],
  'FF-24': ['FF-38', 'FF-17'],
  'FF-25': ['FF-15', 'FF-26', 'FF-27'],
  'FF-26': ['FF-15', 'FF-17'],
  'FF-27': ['FF-10', 'FF-34', 'FF-58'],
  'FF-28': ['FF-15'],
  'FF-29': ['FF-15'],
  'FF-30': ['FF-15'],
  'FF-31': ['FF-15', 'FF-30'],
  'FF-32': ['FF-17', 'FF-24', 'FF-33'],
  'FF-33': ['FF-34'],
  'FF-34': ['FF-15'],
  'FF-35': ['FF-09', 'FF-37', 'FF-36'],
  'FF-36': ['FF-35', 'FF-15'],
  'FF-37': ['FF-35', 'FF-62'],
  'FF-38': ['FF-15', 'FF-39'],
  'FF-39': ['FF-15', 'FF-41', 'FF-38', 'FF-40'],
  'FF-40': ['FF-39'],
  'FF-41': ['FF-09', 'FF-38', 'FF-39'],
  'FF-42': ['FF-09', 'FF-43', 'FF-10'],
  'FF-43': ['FF-42'],
  'FF-44': ['FF-09', 'FF-45', 'FF-46', 'FF-50'],
  'FF-45': ['FF-44'],
  'FF-46': ['FF-44'],
  'FF-47': ['FF-44'],
  'FF-48': ['FF-09', 'FF-47'],
  'FF-49': ['FF-09', 'FF-38'],
  'FF-50': ['FF-10', 'FF-08'],
  'FF-51': ['FF-44', 'FF-54', 'FF-55', 'RW-29', 'FF-52', 'FF-50', 'FF-07', 'FF-53'],
  'FF-52': ['FF-51'],
  'FF-53': ['SWITCH', 'FF-05', 'FF-09'],
  'FF-54': ['FF-15', 'FF-25', 'FF-20', 'FF-17', 'FF-21', 'FF-34'],
  'FF-55': ['FF-15', 'FF-25', 'FF-17', 'FF-20', 'FF-21', 'FF-34'],
  'FF-56': ['FF-05', 'FF-57'],
  'FF-57': ['FF-56', 'FF-07'],
  'FF-58': ['FF-15', 'FF-10'],
  'FF-59': ['FF-20', 'FF-38'],
  'FF-60': ['FF-15'],
  'FF-61': ['FF-15', 'FF-34'],
  'FF-62': ['FF-15', 'FF-37'],
  'FF-63': ['FF-09', 'FF-42', 'FF-50', 'FF-10', 'RW-01', 'FF-38', 'FF-37', 'FF-47'],
  'RW-01': ['FF-09', 'RW-08', 'RW-26', 'RW-02', 'RW-27', 'RW-03', 'FF-63', 'FF-10'],
  'RW-02': ['RW-01', 'RW-04', 'RW-03'],
  'RW-03': ['RW-05'],
  'RW-04': ['RW-05', 'RW-06'],
  'RW-05': ['RW-02', 'RW-04', 'RW-22', 'RW-06', 'RW-19'],
  'RW-06': ['RW-05', 'RW-07', 'RW-09', 'RW-12', 'RW-19', 'RW-17'],
  'RW-07': ['RW-06'],
  'RW-08': ['RW-01', 'RW-19', 'RW-09'],
  'RW-09': ['RW-06', 'RW-10', 'RW-11', 'RW-17', 'RW-13'],
  'RW-10': ['RW-09', 'RW-17', 'RW-06'],
  'RW-11': ['RW-09', 'RW-18'],
  'RW-12': ['RW-06', 'RW-09', 'RW-17'],
  'RW-13': ['RW-09', 'RW-14', 'RW-06'],
  'RW-14': ['RW-09', 'RW-13'],
  'RW-15': ['RW-09', 'RW-16', 'RW-06'],
  'RW-16': ['RW-15', 'RW-13'],
  'RW-17': ['RW-09', 'RW-21', 'RW-06'],
  'RW-18': ['RW-11', 'RW-09'],
  'RW-19': ['RW-06', 'RW-09', 'RW-20'],
  'RW-20': ['RW-19', 'RW-06'],
  'RW-21': ['RW-06'],
  'RW-22': ['RW-05', 'RW-23', 'RW-24', 'RW-25'],
  'RW-23': ['RW-22', 'RW-06', 'RW-04'],
  'RW-24': ['RW-22'],
  'RW-25': ['RW-22', 'RW-23', 'RW-26'],
  'RW-26': ['RW-27'],
  'RW-27': ['RW-01', 'RW-06'],
  'RW-28': ['FF-09', 'RW-27'],
  'RW-29': ['FF-51'],
  // The Switch technician sheet: Cancel goes back; Hand over signs the next
  // technician in, which is the gate's sign-in, not a link.
  SWITCH: [],
};

/** Doors the drawings show and the boards do not link — see the header. */
export const FROM_THE_IMAGES: ReadonlyArray<{ from: ScreenId; to: ScreenId; what: string }> = [
  { from: 'FF-44', to: 'FF-47', what: 'FF-44 Profile draws a Timesheet row' },
  { from: 'FF-44', to: 'FF-51', what: 'FF-44 Profile draws a Settings row' },
  { from: 'FF-10', to: 'FF-11', what: 'FF-11 draws the Mine · Nearby switch on Today' },
  { from: 'RW-09', to: 'RW-15', what: 'an out-of-range figure on RW-09 opens RW-15' },
  { from: 'FF-10', to: 'FF-14', what: 'FF-10 T Today draws Open the stop (tablet/FF-10-T-today.png); the phone has it under ⋮' },
  { from: 'FF-15', to: 'FF-32', what: 'FF-15 Continue reads Finish — debrief once every part is done (PO, MQ-024; DEF-FLD-10586)' },
  { from: 'FF-50', to: 'FF-53', what: 'FF-50 Sign in again on work refused for its capture credential (PO, MQ-027; DEF-FLD-10612)' },
];

function merged(): Record<ScreenId, readonly ScreenId[]> {
  const out = {} as Record<ScreenId, ScreenId[]>;
  for (const [from, tos] of Object.entries(FROM_THE_LINKS) as Array<[ScreenId, readonly ScreenId[]]>) {
    out[from] = [...tos];
  }
  for (const { from, to } of FROM_THE_IMAGES) {
    if (!out[from].includes(to)) out[from].push(to);
  }
  return out;
}

export const DOORS: Readonly<Record<ScreenId, readonly ScreenId[]>> = merged();

/**
 * Doors that cross between "nobody signed in" and "signed in". A placeholder
 * cannot push across that line — signing in or out is what moves you — so
 * they render as a stated act rather than a link.
 */
export type DoorKind = 'link' | 'signs-in' | 'signs-out' | 'opens-menu';
