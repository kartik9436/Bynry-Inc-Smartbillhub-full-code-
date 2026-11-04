import { fireEvent, screen } from '@testing-library/react-native';
import { Text } from 'react-native';

import { Button, IconButton } from '../../src/components';
import { THEME_NAMES, renderIn, styleOf, themeOf, touchHeight } from './helpers';

describe('Button', () => {
  test('is a button, named by its words, and presses', () => {
    const onPress = jest.fn();
    renderIn('light', <Button onPress={onPress}>Navigate</Button>);
    const btn = screen.getByRole('button', { name: 'Navigate' });
    fireEvent.press(btn);
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  test('two sizes: default 56, sm 48 (B14 rule 45)', () => {
    renderIn(
      'light',
      <>
        <Button size="default">Big</Button>
        <Button size="sm">Small</Button>
      </>,
    );
    expect(touchHeight(screen.getByRole('button', { name: 'Big' }))).toBe(56);
    expect(touchHeight(screen.getByRole('button', { name: 'Small' }))).toBe(48);
  });

  test.each(THEME_NAMES)('three tiers draw from the %s theme', (name) => {
    const t = themeOf(name);
    renderIn(
      name,
      <>
        <Button variant="primary">P</Button>
        <Button variant="secondary">S</Button>
        <Button variant="danger">D</Button>
      </>,
    );
    const p = styleOf(screen.getByRole('button', { name: 'P' }));
    const s = styleOf(screen.getByRole('button', { name: 'S' }));
    const d = styleOf(screen.getByRole('button', { name: 'D' }));
    expect(p.backgroundColor).toBe(t.colors.actionFill);
    expect(s.backgroundColor).toBe(t.colors.card);
    expect(s.borderColor).toBe(t.colors.controlBorder);
    expect(d.borderColor).toBe(t.colors.dangerAction);
    expect(d.borderWidth).toBe(t.borderWidth.emphasis);
  });

  test('the light primary fill is #e12e13 (R100)', () => {
    renderIn('light', <Button variant="primary">Continue</Button>);
    expect(styleOf(screen.getByRole('button', { name: 'Continue' })).backgroundColor).toBe('#e12e13');
  });

  test('disabled: announced, not pressable, still labelled, disabled colours', () => {
    const onPress = jest.fn();
    renderIn(
      'light',
      <Button variant="primary" disabled onPress={onPress}>
        Tasks locked
      </Button>,
    );
    const btn = screen.getByRole('button', { name: 'Tasks locked' });
    expect(btn.props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(btn);
    expect(onPress).not.toHaveBeenCalled();
    expect(styleOf(btn).backgroundColor).toBe(themeOf('light').colors.disabledFill);
  });

  test('busy is announced and blocks a second press', () => {
    const onPress = jest.fn();
    renderIn('light', <Button busy onPress={onPress}>Send</Button>);
    const btn = screen.getByRole('button', { name: 'Send' });
    expect(btn.props.accessibilityState).toMatchObject({ busy: true, disabled: true });
    fireEvent.press(btn);
    expect(onPress).not.toHaveBeenCalled();
  });

  test('an explicit accessibilityLabel wins over the words', () => {
    renderIn('light', <Button accessibilityLabel="Close the job">Close job</Button>);
    expect(screen.getByRole('button', { name: 'Close the job' })).toBeTruthy();
  });
});

describe('IconButton', () => {
  test('48 square, a button, named by its label', () => {
    const onPress = jest.fn();
    renderIn(
      'light',
      <IconButton label="Scan a part" onPress={onPress}>
        <Text>[]</Text>
      </IconButton>,
    );
    const btn = screen.getByRole('button', { name: 'Scan a part' });
    const s = styleOf(btn);
    expect(s.width).toBe(48);
    expect(s.height).toBe(48);
    fireEvent.press(btn);
    expect(onPress).toHaveBeenCalled();
  });

  test('disabled is announced and does not press', () => {
    const onPress = jest.fn();
    renderIn(
      'dark',
      <IconButton label="Refresh" onPress={onPress} disabled>
        <Text>r</Text>
      </IconButton>,
    );
    const btn = screen.getByRole('button', { name: 'Refresh' });
    expect(btn.props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(btn);
    expect(onPress).not.toHaveBeenCalled();
  });
});
