/**
 * The six kit components the screen waves gettingIn and theDay added —
 * Page, SegmentTabs, IconCircle, Figure, CheckRow, SyncStrip — and the
 * Field and Glyph additions, in every theme.
 */
import { fireEvent, screen } from '@testing-library/react-native';
import { Text } from 'react-native';

import { CheckRow, Field, Figure, Glyph, IconCircle, Page, SegmentTabs, SyncStrip } from '../../src/components';
import { ThemeProvider } from '../../src/theme';
import { THEME_NAMES, renderIn, styleOf, themeOf, touchHeight } from './helpers';

describe.each(THEME_NAMES)('%s theme', (name) => {
  test('SegmentTabs: each is a named tab, at least 48pt, the chosen one marked selected', () => {
    const onSelect = jest.fn();
    renderIn(
      name,
      <SegmentTabs
        label="Whose work"
        tabs={[
          { id: 'mine', label: 'Mine' },
          { id: 'nearby', label: 'Nearby' },
        ]}
        active="mine"
        onSelect={onSelect}
        testID="t"
      />,
    );
    const tabs = screen.getAllByRole('tab');
    expect(tabs).toHaveLength(2);
    for (const tab of tabs) expect(touchHeight(tab)).toBeGreaterThanOrEqual(48);
    expect(screen.getByRole('tab', { name: 'Mine' })).toHaveProp('accessibilityState', { selected: true });
    fireEvent.press(screen.getByTestId('t-nearby'));
    expect(onSelect).toHaveBeenCalledWith('nearby');
  });

  test('SyncStrip: the words open Sync; Send now only when there is something behind it', () => {
    const onOpen = jest.fn();
    const onSend = jest.fn();
    const view = renderIn(
      name,
      <SyncStrip title="12 waiting to send" detail="8 photos" onOpen={onOpen} sendLabel="Send now" onSend={onSend} testID="s" />,
    );
    fireEvent.press(screen.getByTestId('s-open'));
    fireEvent.press(screen.getByTestId('s-send'));
    expect([onOpen.mock.calls.length, onSend.mock.calls.length]).toEqual([1, 1]);
    expect(screen.getByTestId('s-open').props.accessibilityLabel).toBe('12 waiting to send. 8 photos');
    expect(touchHeight(screen.getByTestId('s-open'))).toBeGreaterThanOrEqual(48);
    view.rerender(
      <ThemeProvider initialMode={name}>
        <SyncStrip title="12 waiting to send" onOpen={onOpen} sendLabel="Send now" testID="s" />
      </ThemeProvider>,
    );
    expect(screen.queryByTestId('s-send')).toBeNull();
  });

  test('Figure: one line to a screen reader; a status tone colours the number only', () => {
    renderIn(name, <Figure value="3" label="done" tone="success" testID="f" />);
    expect(screen.getByTestId('f').props.accessibilityLabel).toBe('3 done');
    const number = screen.getByText('3');
    const theme = themeOf(name);
    expect(styleOf(number).color).toBe(name === 'sunlight' ? theme.colors.text : theme.colors.status.success.fg);
    expect(styleOf(screen.getByText('done')).color).toBe(theme.colors.textMuted);
  });

  test('CheckRow: the state is a word as well as a colour (WCAG 1.4.1)', () => {
    renderIn(name, <CheckRow state="active" label="Jobs and checklists" value="8 of 11" stateLabel="Loading" testID="c" />);
    expect(screen.getByTestId('c').props.accessibilityLabel).toBe('Jobs and checklists, Loading, 8 of 11');
  });

  test('IconCircle is decoration: hidden from a screen reader', () => {
    renderIn(name, <IconCircle glyph="sync" tone="info" size="lg" testID="i" />);
    // Hidden from assistive technology, so RNTL only finds it when asked to look at hidden elements.
    expect(screen.queryByTestId('i')).toBeNull();
    const disc = screen.getByTestId('i', { includeHiddenElements: true });
    expect(disc.props.accessible).toBe(false);
    expect(Number(styleOf(disc).width)).toBe(themeOf(name).touch.primary * 4);
  });

  test('Page: the body, and a footer under a rule', () => {
    renderIn(
      name,
      <Page testID="p" footer={<Text>Continue</Text>}>
        <Text>Body</Text>
      </Page>,
    );
    expect(screen.getByText('Body')).toBeTruthy();
    expect(screen.getByText('Continue')).toBeTruthy();
    expect(styleOf(screen.getByTestId('p')).backgroundColor).toBe(themeOf(name).colors.page);
  });
});

test('Field: a password is hidden, and the input carries its own testID', () => {
  renderIn('light', <Field label="Password" value="secret" secureTextEntry testID="pw" />);
  expect(screen.getByTestId('pw-input')).toHaveProp('secureTextEntry', true);
});

test('Glyph: the added names render, at a size the caller asks', () => {
  renderIn('light', <Glyph name="bell" size={30} />);
  expect(screen.getByTestId('glyph-bell', { includeHiddenElements: true })).toBeTruthy();
  expect(screen.UNSAFE_getByProps({ name: 'notifications-outline' }).props.size).toBe(30);
});
