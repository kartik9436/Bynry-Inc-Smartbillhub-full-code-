/**
 * DEF-FLD-10604 (beta MQ-046): Menu → *Assets* opened FF-39 — ONE asset, which
 * needs a meter to show — and read *"Not on this phone — Open it from a job."*
 *
 * Every menu check passed over it, because each asked whether an entry opens
 * A screen (`doors.test`: the target is registered; `navigator.test`: pressing
 * a row lands somewhere) and FF-39 is a real screen. None asked whether it
 * opens the screen the DRAWING makes that row. So this table is read off the
 * boards (B14 rule 42: the image is the specification), one row per menu
 * entry, naming the board each one is: the page whose title is the row's word
 * and which carries the menu icon. *Assets* is `phone/FF-41-asset-search.png`
 * (titled *Assets*, menu icon, scan icon, *"Only today's assets are here."*),
 * never `phone/FF-39-asset.png` (a meter's serial under a back arrow).
 *
 * Proved red (law 7) on the code as it stood: *Assets → FF-41* failed with
 * `FF-39`, and pressing the drawer's *Assets* landed on `FF-39`.
 */
import 'react-native-gesture-handler/jestSetup';

import { fireEvent, screen, within } from '@testing-library/react-native';
import { existsSync } from 'fs';
import { join } from 'path';

import { MENU_FOOT, PHONE_MENU, TABLET_MENU } from '../../src/navigation/drawerEntries';
import { mountApp } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

const BOARDS = join(__dirname, '../../../04-docs/05-modules/18-field-app/wireframes');

/** Each menu row → the screen its board is, and the board that shows it. */
const DRAWN: Record<string, { id: string; board: string }> = {
  'field.nav.item.home': { id: 'FF-63', board: 'phone/FF-63-home.png' },
  'field.nav.item.today': { id: 'FF-10', board: 'phone/FF-10-today.png' },
  'field.nav.item.completed': { id: 'FF-35', board: 'phone/FF-35-completed.png' },
  'field.nav.item.map': { id: 'FF-13', board: 'phone/FF-13-map.png' },
  'field.nav.item.assets': { id: 'FF-41', board: 'phone/FF-41-asset-search.png' },
  'field.nav.item.alerts': { id: 'FF-42', board: 'phone/FF-42-alerts.png' },
  'field.nav.item.myRoutes': { id: 'RW-01', board: 'reads/RW-01-my-routes.png' },
  'field.nav.item.findMeter': { id: 'RW-08', board: 'reads/RW-08-find-a-meter.png' },
  'field.nav.item.myReads': { id: 'RW-28', board: 'reads/RW-28-my-reads.png' },
  'field.nav.item.profile': { id: 'FF-44', board: 'phone/FF-44-profile.png' },
  'field.nav.item.admin': { id: 'FF-48', board: 'phone/FF-48-admin-tasks.png' },
  'field.nav.item.shifts': { id: 'FF-46', board: 'phone/FF-46-shifts.png' },
  'field.nav.item.timesheet': { id: 'FF-47', board: 'phone/FF-47-timesheet.png' },
  'field.nav.item.van': { id: 'FF-49', board: 'phone/FF-49-van.png' },
  'field.nav.item.sync': { id: 'FF-50', board: 'phone/FF-50-sync.png' },
  'field.nav.item.settings': { id: 'FF-51', board: 'phone/FF-51-settings.png' },
  'field.nav.switchTechnician': { id: 'SWITCH', board: 'phone/Switch.png' },
  'field.nav.signOut': { id: 'FF-53', board: 'phone/FF-53-sign-out.png' },
};

const ROWS = [
  ...PHONE_MENU.flatMap((g) => g.items).map((i) => ['phone', i.labelKey, i.id] as const),
  ...TABLET_MENU.flatMap((g) => g.items).map((i) => ['tablet', i.labelKey, i.id] as const),
  ...MENU_FOOT.map((i) => ['foot', i.labelKey, i.id] as const),
];

describe('each menu entry opens its DRAWN screen', () => {
  test.each(ROWS)('%s: %s → its board', (_form, labelKey, id) => {
    const drawn = DRAWN[labelKey];
    expect(drawn).toBeDefined();
    expect(existsSync(join(BOARDS, drawn!.board))).toBe(true);
    expect(`${labelKey} → ${id}`).toBe(`${labelKey} → ${drawn!.id}`);
  });

  test('phone: pressing Assets in the drawer lands on FF-41 Asset search', async () => {
    const app = await mountApp();
    await screen.findByTestId('screen-FF-63');
    fireEvent.press(within(screen.getByTestId('menu-drawer')).getByText('Assets'));
    expect(app.ref.getCurrentRoute()?.name).toBe('FF-41');
  });
});
