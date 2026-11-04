/**
 * The six kit components the reads wave added — ProgressBar, Stat/StatRow,
 * ActionBar, Keypad, RadioList, ToggleRow — in all three themes: each draws,
 * each control has a role and a name and is at least the touch standard, and
 * each does the one thing it is for.
 */
import { fireEvent, screen } from '@testing-library/react-native';
import { useState } from 'react';
import { Text } from 'react-native';

import { ActionBar, Button, Keypad, keyHeight, ProgressBar, RadioList, Stat, StatRow, ToggleRow } from '../../src/components';
import { renderIn, styleOf, themeOf, THEME_NAMES, touchHeight } from './helpers';

function KeypadHost({ size }: { size?: 'normal' | 'large' | 'largest' }) {
  const [v, setV] = useState('');
  return (
    <>
      <Keypad value={v} onChange={setV} clearLabel="Clear" deleteLabel="Delete" size={size} testID="pad" maxDigits={6} />
      <Text testID="value">{v}</Text>
    </>
  );
}

describe.each(THEME_NAMES)('%s', (name) => {
  const theme = themeOf(name);

  test('Keypad edits a figure: digits, delete, clear, a ceiling on length; every key ≥ the most-tapped size', () => {
    renderIn(name, <KeypadHost size="normal" />);
    for (const k of ['5', '2', '4', '1', '0']) fireEvent.press(screen.getByTestId(`pad-${k}`));
    expect(screen.getByTestId('value')).toHaveTextContent('52410');
    fireEvent.press(screen.getByLabelText('Delete'));
    expect(screen.getByTestId('value')).toHaveTextContent('5241');
    for (const k of ['1', '1', '1']) fireEvent.press(screen.getByTestId(`pad-${k}`));
    expect(screen.getByTestId('value')).toHaveTextContent('524111'); // six digits, no more
    fireEvent.press(screen.getByLabelText('Clear'));
    expect(screen.getByTestId('value')).toHaveTextContent('');
    const keys = screen.getAllByRole('button');
    expect(keys).toHaveLength(12);
    for (const k of keys) {
      expect(k.props.accessibilityLabel).toBeTruthy();
      expect(touchHeight(k)).toBeGreaterThanOrEqual(theme.touch.mostTapped);
    }
  });

  test('Keypad sizes for gloves grow, never shrink below the standard', () => {
    expect(keyHeight('normal', theme.touch, theme.space)).toBe(theme.touch.mostTapped);
    expect(keyHeight('large', theme.touch, theme.space)).toBeGreaterThan(theme.touch.mostTapped);
    expect(keyHeight('largest', theme.touch, theme.space)).toBeGreaterThan(keyHeight('large', theme.touch, theme.space));
  });

  test('RadioList: one checked at a time, each row a named radio ≥ 48', () => {
    function Host() {
      const [sel, setSel] = useState<string | null>(null);
      return <RadioList label="Why not?" options={[{ id: 'dog', label: 'Dog' }, { id: 'locked', label: 'Locked' }]} selected={sel} onSelect={setSel} testID="r" />;
    }
    renderIn(name, <Host />);
    fireEvent.press(screen.getByTestId('r-locked'));
    expect(screen.getByTestId('r-locked').props.accessibilityState).toMatchObject({ checked: true });
    expect(screen.getByTestId('r-dog').props.accessibilityState).toMatchObject({ checked: false });
    for (const r of screen.getAllByRole('radio')) expect(touchHeight(r)).toBeGreaterThanOrEqual(theme.touch.control);
    expect(screen.getByLabelText('Why not?')).toBeTruthy();
  });

  test('ToggleRow: the whole row is the switch, ≥ 48', () => {
    function Host() {
      const [on, setOn] = useState(false);
      return <ToggleRow label="Confirm each number" detail="Slower, and catches a slip" value={on} onChange={setOn} testID="t" />;
    }
    renderIn(name, <Host />);
    const row = screen.getByRole('switch');
    expect(row.props.accessibilityState).toMatchObject({ checked: false });
    fireEvent.press(row);
    expect(screen.getByRole('switch').props.accessibilityState).toMatchObject({ checked: true });
    expect(touchHeight(row)).toBeGreaterThanOrEqual(theme.touch.control);
  });

  test('ProgressBar reads aloud its figures; Stat names its value and caption; ActionBar holds acts', () => {
    renderIn(
      name,
      <>
        <ProgressBar done={136} problem={7} total={151} label="136 of 151 done" testID="bar" />
        <StatRow>
          <Stat value="129" caption="read" tone="success" testID="stat" />
        </StatRow>
        <ActionBar note="Opens at 100%">
          <Button grow>Start the walk</Button>
        </ActionBar>
      </>,
    );
    const bar = screen.getByTestId('bar');
    expect(bar.props.accessibilityRole).toBe('progressbar');
    expect(bar.props.accessibilityValue).toEqual({ min: 0, max: 151, now: 136 });
    expect(screen.getByLabelText('129 read')).toBeTruthy();
    expect(screen.getByText('Opens at 100%')).toBeTruthy();
    expect(styleOf(screen.getByText('129')).color).toBe(theme.colors.statusInk.success); // ink on the card (DEF-FLD-10360)
  });
});
