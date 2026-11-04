/**
 * What the menu holds (AD-12; FF-09 on the phone, FF-09 T on the tablet).
 *
 * PHONE — the drawer board's own links, in its order: Work (Today ·
 * Completed · Map · Assets · Alerts), Reads (My routes · Find a meter · My
 * reads), Me (Profile · Admin · Shifts · Timesheet · Van · Sync), then
 * *Switch technician* and *Sign out* at the foot beside the version. Home is
 * not in it: Home is the first bottom tab (AD-22).
 *
 * TABLET — the sidebar board draws Home at the top of Work and Settings at
 * the end of Me, and it is cut off below Sync, so it does not show My reads,
 * Admin, Switch technician or Sign out. The same board says in words *"Everything
 * the phone hides behind a menu button is one tap away"*, so the sidebar is
 * the phone's menu PLUS Home and Settings — our reading of the board's own
 * sentence, recorded rather than asked. A shared van tablet with no way to
 * switch technician or sign out would break requirement 3.
 */
import { type ScreenId } from './screens';

export interface MenuItem {
  id: ScreenId;
  labelKey: string;
}

export interface MenuGroup {
  labelKey: string;
  items: MenuItem[];
}

const WORK: MenuItem[] = [
  { id: 'FF-10', labelKey: 'field.nav.item.today' },
  { id: 'FF-35', labelKey: 'field.nav.item.completed' },
  { id: 'FF-13', labelKey: 'field.nav.item.map' },
  // Assets is FF-41 Asset search, the page the board titles *Assets* under
  // the menu icon — never FF-39, one meter, which needs one (DEF-FLD-10604).
  { id: 'FF-41', labelKey: 'field.nav.item.assets' },
  { id: 'FF-42', labelKey: 'field.nav.item.alerts' },
];

const READS: MenuItem[] = [
  { id: 'RW-01', labelKey: 'field.nav.item.myRoutes' },
  { id: 'RW-08', labelKey: 'field.nav.item.findMeter' },
  { id: 'RW-28', labelKey: 'field.nav.item.myReads' },
];

const ME: MenuItem[] = [
  { id: 'FF-44', labelKey: 'field.nav.item.profile' },
  { id: 'FF-48', labelKey: 'field.nav.item.admin' },
  { id: 'FF-46', labelKey: 'field.nav.item.shifts' },
  { id: 'FF-47', labelKey: 'field.nav.item.timesheet' },
  { id: 'FF-49', labelKey: 'field.nav.item.van' },
  { id: 'FF-50', labelKey: 'field.nav.item.sync' },
];

/** The foot of the menu, beside the version. */
export const MENU_FOOT: MenuItem[] = [
  { id: 'SWITCH', labelKey: 'field.nav.switchTechnician' },
  { id: 'FF-53', labelKey: 'field.nav.signOut' },
];

export const PHONE_MENU: MenuGroup[] = [
  { labelKey: 'field.nav.group.work', items: WORK },
  { labelKey: 'field.nav.group.reads', items: READS },
  { labelKey: 'field.nav.group.me', items: ME },
];

export const TABLET_MENU: MenuGroup[] = [
  { labelKey: 'field.nav.group.work', items: [{ id: 'FF-63', labelKey: 'field.nav.item.home' }, ...WORK] },
  { labelKey: 'field.nav.group.reads', items: READS },
  { labelKey: 'field.nav.group.me', items: [...ME, { id: 'FF-51', labelKey: 'field.nav.item.settings' }] },
];

export function menuFor(tablet: boolean): MenuGroup[] {
  return tablet ? TABLET_MENU : PHONE_MENU;
}

/** Every screen the menu opens, foot included. */
export function menuTargets(tablet: boolean): ScreenId[] {
  return [...menuFor(tablet).flatMap((g) => g.items.map((i) => i.id)), ...MENU_FOOT.map((i) => i.id)];
}
