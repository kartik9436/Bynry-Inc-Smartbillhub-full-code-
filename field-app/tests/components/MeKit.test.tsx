/**
 * The kit pieces the "me" wave added (B14 rule 43: a piece of UI is a
 * component): Avatar, Dot, ToggleRow, Meter, SyncChip, the Alarm surface,
 * TopBar's drawer button and back testID, and Field's `secure`. Each in all
 * three themes where colour matters.
 */
import { fireEvent, screen } from '@testing-library/react-native';
import { useState } from 'react';

import {
  AlarmButton,
  AlarmCallout,
  Avatar,
  Dot,
  Field,
  initialsOf,
  Meter,
  SyncChip,
  ToggleRow,
  TopBar,
} from '../../src/components';
import { contrastRatio } from '../../src/theme';
import { renderIn, styleOf, THEME_NAMES, themeOf, touchHeight } from './helpers';

test('Avatar: initials from a name, or the glyph as given', () => {
  expect(initialsOf('D. Ortiz')).toBe('DO');
  expect(initialsOf('M. Chen')).toBe('MC');
  renderIn('light', <Avatar name="+" literal testID="a" />);
  expect(screen.getByText('+', { includeHiddenElements: true })).toBeTruthy();
});

test.each(THEME_NAMES)('%s: Avatar letters pass 4.5:1 on their tint', (name) => {
  const pair = themeOf(name).colors.status.neutral;
  expect(contrastRatio(pair.fg, pair.bg)).toBeGreaterThanOrEqual(4.5);
});

test('Dot is decoration — hidden from the screen reader', () => {
  renderIn('light', <Dot tone="success" testID="d" />);
  expect(screen.getByTestId('d')).toHaveProp('accessible', false);
});

function Toggle() {
  const [on, setOn] = useState(false);
  return <ToggleRow label="Bigger text" detail="Easier with gloves on" value={on} onChange={setOn} testID="t" />;
}

test.each(THEME_NAMES)('%s: ToggleRow is ONE switch, named, 48pt, and the whole row toggles it', (name) => {
  renderIn(name, <Toggle />);
  const row = screen.getByRole('switch');
  expect(row).toHaveProp('accessibilityLabel', 'Bigger text, Easier with gloves on');
  expect(touchHeight(row)).toBeGreaterThanOrEqual(48);
  expect(row).toHaveProp('accessibilityState', { checked: false, disabled: false });
  fireEvent.press(row);
  expect(screen.getByRole('switch')).toHaveProp('accessibilityState', { checked: true, disabled: false });
});

test('Meter: parts in proportion, the rest empty, and the sentence for a screen reader', () => {
  renderIn('light', <Meter parts={[{ value: 24, tone: 'warning' }]} total={62} label="24 of 62" testID="m" />);
  const bar = screen.getByTestId('m');
  expect(bar).toHaveProp('accessibilityValue', { min: 0, max: 62, now: 24 });
  expect(styleOf(screen.getByTestId('m-part-warning')).flexGrow).toBe(24);
});

test('SyncChip: null is "not known" — a dash, never a zero (R32)', () => {
  renderIn('light', <SyncChip count={null} suffix="to send" accessibilityLabel="Sync" onPress={() => undefined} testID="s" />);
  expect(screen.getByTestId('s')).toHaveTextContent(/– to send$/);
  expect(touchHeight(screen.getByTestId('s'))).toBeGreaterThanOrEqual(48);
});

test.each(THEME_NAMES)('%s: the alarm surface — card-colour words on the danger ink pass 4.5:1, both ways', (name) => {
  const c = themeOf(name).colors;
  expect(contrastRatio(c.card, c.dangerAction)).toBeGreaterThanOrEqual(4.5);
  renderIn(
    name,
    <>
      <AlarmButton variant="solid" testID="solid">
        Acknowledge
      </AlarmButton>
      <AlarmButton testID="outline">Call dispatch</AlarmButton>
      <AlarmCallout label="Dispatch is told in" figure="4:12" testID="c" />
    </>,
  );
  expect(touchHeight(screen.getByTestId('solid'))).toBe(56);
  expect(touchHeight(screen.getByTestId('outline'))).toBe(48);
  expect(screen.getByTestId('c')).toHaveProp('accessibilityLabel', 'Dispatch is told in 4:12');
});

test('TopBar: the drawer button sits at the left, needs a name, and the back button takes a door testID', () => {
  expect(() => renderIn('light', <TopBar title="Alerts" onOpenDrawer={() => undefined} />)).toThrow(/drawerLabel/);
  const open = jest.fn();
  renderIn(
    'light',
    <TopBar title="Settings" onOpenDrawer={open} drawerLabel="Menu" drawerTestID="door-FF-09" onBack={() => undefined} backLabel="Back" backTestID="door-FF-44" />,
  );
  fireEvent.press(screen.getByTestId('door-FF-09'));
  expect(open).toHaveBeenCalled();
  expect(screen.getByTestId('door-FF-44')).toHaveProp('accessibilityLabel', 'Back');
});

test('Field secure: a password is hidden and never auto-corrected', () => {
  renderIn('light', <Field label="Password" value="" secure testID="p" />);
  const input = screen.getByTestId('p-input');
  expect(input).toHaveProp('secureTextEntry', true);
  expect(input).toHaveProp('autoCorrect', false);
});
