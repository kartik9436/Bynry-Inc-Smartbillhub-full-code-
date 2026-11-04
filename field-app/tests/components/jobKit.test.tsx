/**
 * The kit pieces the job screens added (T-18, T-19): SheetScreen, PhotoThumb,
 * DashedButton, CheckRow, ProgressBar, Initials, ToggleRow — each named,
 * each at least 48pt where it can be pressed (B14 rule 45), in every theme.
 */
import { fireEvent, screen } from '@testing-library/react-native';

import {
  CheckRow,
  DashedButton,
  Initials,
  PhotoThumb,
  ProgressBar,
  SheetScreen,
  ToggleRow,
  TopBar,
} from '../../src/components';
import { THEME_NAMES, renderIn, touchHeight } from './helpers';

describe.each(THEME_NAMES)('%s theme', (name) => {
  test('every pressable piece is named and at least 48pt', () => {
    renderIn(
      name,
      <>
        <DashedButton label="Add a step" onPress={() => undefined} />
        <CheckRow label="Gloves and eye protection on" checked={false} onPress={() => undefined} />
        <CheckRow kind="radio" label="No parts on the van" checked onPress={() => undefined} />
        <ToggleRow label="Needs a photo" detail="Proof for the office" value={false} onChange={() => undefined} />
        <SheetScreen title="Parts used" closeLabel="Close" onClose={() => undefined} />
      </>,
    );
    const controls = [
      ...screen.getAllByRole('button'),
      ...screen.getAllByRole('checkbox'),
      ...screen.getAllByRole('radio'),
      ...screen.getAllByRole('switch'),
    ];
    expect(controls).toHaveLength(5);
    for (const el of controls) {
      expect(String(el.props.accessibilityLabel ?? '').length).toBeGreaterThan(0);
      expect(touchHeight(el)).toBeGreaterThanOrEqual(48);
    }
  });
});

test('CheckRow announces checked, and a radio is a radio', () => {
  renderIn(
    'light',
    <>
      <CheckRow label="Main shut-off located and closed" checked testID="a" />
      <CheckRow kind="radio" label="Not my skills" checked={false} testID="b" />
    </>,
  );
  expect(screen.getByTestId('a')).toBeChecked();
  expect(screen.getByRole('radio')).not.toBeChecked();
});

test('ToggleRow: the whole row flips the switch', () => {
  const seen: boolean[] = [];
  renderIn('light', <ToggleRow label="Needs a photo" value={false} onChange={(v) => seen.push(v)} testID="t" />);
  fireEvent.press(screen.getByTestId('t'));
  expect(seen).toEqual([true]);
});

test('SheetScreen: the dimmed area is a named way out', () => {
  let closed = 0;
  renderIn('light', <SheetScreen title="Add a step" closeLabel="Close" onClose={() => (closed += 1)} closeTestID="scrim" />);
  fireEvent.press(screen.getByTestId('scrim'));
  expect(closed).toBe(1);
  expect(screen.getByText('Add a step')).toBeTruthy();
});

test('PhotoThumb: a file path, its name, and the stamp under a large one', () => {
  renderIn(
    'dark',
    <PhotoThumb size="large" path="file:///p/1.jpg" label="Before, 09:18" stamp={['20 Oct 2026 · 09:18', 'D. Ortiz · WO-4822']} testID="p" />,
  );
  expect(screen.getByLabelText('Before, 09:18')).toBeTruthy();
  expect(screen.getByText('20 Oct 2026 · 09:18')).toBeTruthy();
});

test('ProgressBar reads as progress with its value', () => {
  renderIn('sunlight', <ProgressBar done={3} total={8} label="Tasks" left="Travel 14m" right="45 min est." />);
  const bar = screen.getByRole('progressbar');
  expect(bar.props.accessibilityValue).toEqual({ min: 0, max: 8, now: 3 });
});

test('Initials and the TopBar test ids a door needs', () => {
  renderIn(
    'light',
    <>
      <Initials label="D. Ortiz">DO</Initials>
      <TopBar title="WO-4822" onBack={() => undefined} backLabel="Back" backTestID="door-FF-10" onMenu={() => undefined} menuLabel="Activity" menuTestID="door-FF-31" />
    </>,
  );
  expect(screen.getByLabelText('D. Ortiz')).toBeTruthy();
  expect(screen.getByTestId('door-FF-10')).toBeTruthy();
  expect(screen.getByTestId('door-FF-31')).toBeTruthy();
});
