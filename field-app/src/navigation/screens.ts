/**
 * Every screen of the field app, by the design's own id (T-13).
 *
 * FF-01…FF-63 are the technician's screens and RW-01…RW-29 the meter
 * reader's (AD-20: reading is a mode of the same app, numbered RW- because
 * MR- is already the Meter Reads blueprint's). Ids and names are the design's
 * — `04-docs/05-modules/18-field-app/wireframes/README.md` — and every one is
 * a route from day one, so a screen built later lands at an address that
 * already has doors pointing at it.
 *
 * `tree` says which frame a screen lives in:
 *  - `gate`   — before anybody is signed in. A centred column, no sidebar, no
 *               tabs (the tablet boards draw FF-01…FF-08 that way).
 *  - `root`   — signed in, outside the frame: FF-07 Permissions and FF-08
 *               First sync are centred full screens on the tablet too, and
 *               FF-53 Sign out and `SWITCH` are sheets over the screen.
 *  - `drawer` — FF-09 IS the menu: the slide-over drawer on a phone, the
 *               permanent 220px sidebar on a tablet. Opening it is opening the
 *               drawer, not pushing a screen.
 *  - `tab`    — the three bottom tabs, Home · Jobs · Reads (AD-22, FF-63).
 *  - `frame`  — everything else, pushed onto the stack inside the frame
 *               (AD-13: pushed screens and native back, not stacked overlays).
 *
 * `SWITCH` is the *Switch technician* sheet. The design draws it
 * (`phone/Switch.png`) without an FF- id; it is a route because the drawer and
 * FF-53 open it.
 */
export type ScreenTree = 'gate' | 'root' | 'drawer' | 'tab' | 'frame';

const G = 'gate';
const R = 'root';
const T = 'tab';
const F = 'frame';

const TABLE = [
  ['FF-01', G], ['FF-02', G], ['FF-03', G], ['FF-04', G], ['FF-05', G], ['FF-06', G],
  ['FF-07', R], ['FF-08', R], ['FF-09', 'drawer'], ['FF-10', T],
  ['FF-11', F], ['FF-12', F], ['FF-13', F], ['FF-14', F], ['FF-15', F], ['FF-16', F],
  ['FF-17', F], ['FF-18', F], ['FF-19', F], ['FF-20', F], ['FF-21', F], ['FF-22', F],
  ['FF-23', F], ['FF-24', F], ['FF-25', F], ['FF-26', F], ['FF-27', F], ['FF-28', F],
  ['FF-29', F], ['FF-30', F], ['FF-31', F], ['FF-32', F], ['FF-33', F], ['FF-34', F],
  ['FF-35', F], ['FF-36', F], ['FF-37', F], ['FF-38', F], ['FF-39', F], ['FF-40', F],
  ['FF-41', F], ['FF-42', F], ['FF-43', F], ['FF-44', F], ['FF-45', F], ['FF-46', F],
  ['FF-47', F], ['FF-48', F], ['FF-49', F], ['FF-50', F], ['FF-51', F], ['FF-52', F],
  ['FF-53', R], ['FF-54', F], ['FF-55', F], ['FF-56', G], ['FF-57', G], ['FF-58', F],
  ['FF-59', F], ['FF-60', F], ['FF-61', F], ['FF-62', F], ['FF-63', T],
  ['RW-01', T], ['RW-02', F], ['RW-03', F], ['RW-04', F], ['RW-05', F], ['RW-06', F],
  ['RW-07', F], ['RW-08', F], ['RW-09', F], ['RW-10', F], ['RW-11', F], ['RW-12', F],
  ['RW-13', F], ['RW-14', F], ['RW-15', F], ['RW-16', F], ['RW-17', F], ['RW-18', F],
  ['RW-19', F], ['RW-20', F], ['RW-21', F], ['RW-22', F], ['RW-23', F], ['RW-24', F],
  ['RW-25', F], ['RW-26', F], ['RW-27', F], ['RW-28', F], ['RW-29', F],
  ['SWITCH', R],
] as const;

export type ScreenId = (typeof TABLE)[number][0];

export interface ScreenDef {
  id: ScreenId;
  /** `field.screen.ff10` for FF-10 — the screen's title in the catalogues. */
  titleKey: string;
  tree: ScreenTree;
}

export function titleKeyOf(id: string): string {
  return `field.screen.${id.toLowerCase().replace('-', '')}`;
}

export const SCREENS: readonly ScreenDef[] = TABLE.map(([id, tree]) => ({ id, titleKey: titleKeyOf(id), tree }));

export const SCREEN_IDS: readonly ScreenId[] = SCREENS.map((s) => s.id);

const BY_ID = new Map<string, ScreenDef>(SCREENS.map((s) => [s.id, s]));

export function screenDef(id: ScreenId): ScreenDef {
  return BY_ID.get(id) as ScreenDef;
}

export function isScreenId(id: string): id is ScreenId {
  return BY_ID.has(id);
}

export function screensIn(tree: ScreenTree): ScreenId[] {
  return SCREENS.filter((s) => s.tree === tree).map((s) => s.id);
}

/**
 * Does a door from inside a job carry the job to this screen? Every screen
 * PUSHED inside the frame does (`tree === 'frame'`: Debrief, Signature,
 * Close, Activity, Notes, Help and SOPs, Money to check, Crew, Customer, the
 * asset, Scan…); the tabs (Home FF-63, Today FF-10, Reads RW-01), the menu
 * (FF-09), the gate and the root sheets never do. Derived from the table
 * above, never listed by hand (DEF-FLD-10578: the job screens' doors carried
 * no job, so every on-site and closing screen opened "Not on this phone").
 */
export function carriesJob(id: ScreenId): boolean {
  return screenDef(id).tree === 'frame';
}

/** The three bottom tabs, in the order FF-63 draws them: Home · Jobs · Reads. */
export const TAB_SCREENS: ReadonlyArray<{ id: ScreenId; labelKey: string }> = [
  { id: 'FF-63', labelKey: 'field.nav.tab.home' },
  { id: 'FF-10', labelKey: 'field.nav.tab.jobs' },
  { id: 'RW-01', labelKey: 'field.nav.tab.reads' },
];

/**
 * The one screen nothing opens, named rather than assumed (R99: *"An entry
 * point with nothing above it (a splash) is the only legitimate orphan"*).
 */
export const ENTRY_SCREEN: ScreenId = 'FF-01';

/** The menu (FF-09) is the drawer itself. */
export const MENU_SCREEN: ScreenId = 'FF-09';
