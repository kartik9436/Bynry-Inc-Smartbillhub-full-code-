import { fireEvent, screen } from '@testing-library/react-native';
import { useState } from 'react';
import { Text } from 'react-native';

import { ChoiceChips, Stepper, TopBar } from '../../src/components';
import { renderIn, styleOf, themeOf, touchHeight } from './helpers';

describe('TopBar', () => {
  test('a 56pt bar: back button named, the title a 22pt header, trailing content', () => {
    const onBack = jest.fn();
    renderIn(
      'light',
      <TopBar title="WO-4822" onBack={onBack} backLabel="Back to today" trailing={<Text>12 to send</Text>} testID="bar" />,
    );
    expect(touchHeight(screen.getByTestId('bar'))).toBe(56);
    const title = screen.getByRole('header', { name: 'WO-4822' });
    expect(styleOf(title).fontSize).toBe(22);
    fireEvent.press(screen.getByRole('button', { name: 'Back to today' }));
    expect(onBack).toHaveBeenCalled();
    expect(screen.getByText('12 to send')).toBeTruthy();
  });

  test('sunlight title is one size up', () => {
    renderIn('sunlight', <TopBar title="WO-4822" />);
    expect(styleOf(screen.getByRole('header', { name: 'WO-4822' })).fontSize).toBe(25);
  });

  test('a back button with no name is refused', () => {
    jest.spyOn(console, 'error').mockImplementation(() => undefined);
    expect(() => renderIn('light', <TopBar title="x" onBack={() => undefined} />)).toThrow(/backLabel/);
    (console.error as jest.Mock).mockRestore();
  });
});

describe('ChoiceChips', () => {
  const segments = [
    { id: '5', label: '5 min' },
    { id: '15', label: '15 min' },
    { id: '30', label: '30 min', disabled: true },
  ];

  test('a radio group of radios, the active one checked and filled', () => {
    const t = themeOf('light');
    renderIn('light', <ChoiceChips label="How long?" segments={segments} active="15" />);
    // The group itself is not an accessibility element (that would swallow its
    // radios on iOS), so it is found by its label and its role checked.
    expect(screen.getByLabelText('How long?').props.accessibilityRole).toBe('radiogroup');
    const on = screen.getByRole('radio', { name: '15 min' });
    const off = screen.getByRole('radio', { name: '5 min' });
    expect(on.props.accessibilityState).toMatchObject({ checked: true });
    expect(off.props.accessibilityState).toMatchObject({ checked: false });
    expect(styleOf(on).backgroundColor).toBe(t.colors.selectedFill);
    for (const r of [on, off]) expect(touchHeight(r)).toBeGreaterThanOrEqual(48);
  });

  test('selecting reports the id; a disabled chip does not', () => {
    const onSelect = jest.fn();
    renderIn('light', <ChoiceChips label="How long?" segments={segments} active="15" onSelect={onSelect} />);
    fireEvent.press(screen.getByRole('radio', { name: '5 min' }));
    expect(onSelect).toHaveBeenCalledWith('5');
    fireEvent.press(screen.getByRole('radio', { name: '30 min' }));
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  test('size default is the 56pt choice (FF-51 Screen)', () => {
    renderIn('light', <ChoiceChips label="Screen" segments={segments} active="5" size="default" />);
    expect(touchHeight(screen.getByRole('radio', { name: '5 min' }))).toBe(56);
  });
});

describe('Stepper', () => {
  function Harness(props: { start: number; max?: number }) {
    const [n, setN] = useState(props.start);
    return (
      <Stepper
        value={n}
        onChange={setN}
        max={props.max}
        label="Meter coupling kit"
        decreaseLabel="Fewer"
        increaseLabel="More"
        testID="st"
      />
    );
  }

  test('− and + are 56pt named buttons and change the count', () => {
    renderIn('light', <Harness start={1} />);
    const more = screen.getByRole('button', { name: 'More' });
    const fewer = screen.getByRole('button', { name: 'Fewer' });
    expect(styleOf(more).width).toBe(56);
    expect(styleOf(more).height).toBe(56);
    fireEvent.press(more);
    expect(screen.getByTestId('st-value').props.children).toBe('2');
    fireEvent.press(fewer);
    fireEvent.press(fewer);
    expect(screen.getByTestId('st-value').props.children).toBe('0');
  });

  test('the bounds disable the button that would cross them', () => {
    renderIn('light', <Harness start={0} max={1} />);
    expect(screen.getByRole('button', { name: 'Fewer' }).props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(screen.getByRole('button', { name: 'More' }));
    expect(screen.getByRole('button', { name: 'More' }).props.accessibilityState).toMatchObject({ disabled: true });
  });

  test('to a screen reader the figure is one adjustable control', () => {
    renderIn('light', <Harness start={3} />);
    const adj = screen.getByRole('adjustable', { name: 'Meter coupling kit' });
    expect(adj.props.accessibilityValue).toMatchObject({ now: 3, min: 0 });
    fireEvent(adj, 'accessibilityAction', { nativeEvent: { actionName: 'increment' } });
    expect(screen.getByTestId('st-value').props.children).toBe('4');
  });
});
