import { screen } from '@testing-library/react-native';
import { Text } from 'react-native';

import { Card, ListRow, Notice, StatusChip, StatusPill } from '../../src/components';
import { THEME_NAMES, renderIn, styleOf, themeOf, touchHeight } from './helpers';

describe('Card', () => {
  test('a plain card: white on the page, its title a header, padded 16', () => {
    const t = themeOf('light');
    renderIn(
      'light',
      <Card title="Asset" testID="c" trailing={<Text>History</Text>}>
        <Text>W-4471</Text>
      </Card>,
    );
    const card = styleOf(screen.getByTestId('c'));
    expect(card.backgroundColor).toBe(t.colors.card);
    expect(card.borderColor).toBe(t.colors.border);
    expect(screen.getByRole('header', { name: 'Asset' })).toBeTruthy();
    expect(screen.getByText('History')).toBeTruthy();
  });

  test.each(THEME_NAMES)('a toned card takes the tone border and tinted title strip (%s)', (name) => {
    const t = themeOf(name);
    renderIn(
      name,
      <Card title="Not on your van" tone="danger" testID="c">
        <Text>Water meter 5/8"</Text>
      </Card>,
    );
    expect(styleOf(screen.getByTestId('c')).borderColor).toBe(t.colors.status.danger.rule);
    expect(styleOf(screen.getByRole('header', { name: 'Not on your van' })).color).toBe(
      t.colors.status.danger.fg,
    );
  });

  test('sunlight cards draw 3px lines', () => {
    renderIn('sunlight', <Card testID="c" />);
    expect(styleOf(screen.getByTestId('c')).borderWidth).toBe(3);
  });
});

describe('ListRow', () => {
  test('a row that opens something is a 48pt button with a chevron', () => {
    const onPress = jest.fn();
    renderIn('light', <ListRow label="Readings" value="1 flagged" onPress={onPress} />);
    const row = screen.getByRole('button', { name: 'Readings, 1 flagged' });
    expect(touchHeight(row)).toBeGreaterThanOrEqual(48);
    expect(screen.getByTestId('glyph-forward', { includeHiddenElements: true })).toBeTruthy();
  });

  test('a fact row is text, not a button, and has no chevron', () => {
    renderIn('light', <ListRow label="Labour" value="1h 12m" detail="2 people" />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByLabelText('Labour, 2 people, 1h 12m')).toBeTruthy();
    expect(screen.queryByTestId('glyph-forward', { includeHiddenElements: true })).toBeNull();
  });

  test('divider draws a rule above', () => {
    const t = themeOf('light');
    renderIn('light', <ListRow label="Meter" value="W-4471" divider testID="r" />);
    const s = styleOf(screen.getByTestId('r'));
    expect(s.borderTopWidth).toBe(t.borderWidth.divider);
    expect(s.borderTopColor).toBe(t.colors.divider);
  });
});

describe('StatusChip', () => {
  test.each(THEME_NAMES)('each tone draws its pair (%s)', (name) => {
    const t = themeOf(name);
    for (const tone of ['success', 'warning', 'danger', 'info', 'neutral'] as const) {
      const { unmount } = renderIn(name, <StatusChip tone={tone}>{`chip ${tone}`}</StatusChip>);
      const chip = screen.getByLabelText(`chip ${tone}`);
      expect(styleOf(chip).backgroundColor).toBe(t.colors.status[tone].bg);
      expect(styleOf(screen.getByText(`chip ${tone}`)).color).toBe(t.colors.status[tone].fg);
      unmount();
    }
  });

  test('StatusPill is the same component (the web kit name)', () => {
    expect(StatusPill).toBe(StatusChip);
  });
});

describe('Notice', () => {
  test('danger is an alert; info is not', () => {
    renderIn(
      'light',
      <>
        <Notice tone="danger" testID="d">
          1 required photo missing
        </Notice>
        <Notice tone="info" testID="i">
          Marked as added in the field.
        </Notice>
      </>,
    );
    expect(screen.getByTestId('d').props.accessibilityRole).toBe('alert');
    expect(screen.getByTestId('i').props.accessibilityRole).toBeUndefined();
  });

  test('a 3px left rule in the tone colour', () => {
    const t = themeOf('light');
    renderIn('light', <Notice tone="warning" testID="w">Tasks stay locked.</Notice>);
    const s = styleOf(screen.getByTestId('w'));
    expect(s.borderLeftWidth).toBe(3);
    expect(s.borderLeftColor).toBe(t.colors.status.warning.rule);
    expect(s.backgroundColor).toBe(t.colors.status.warning.bg);
  });
});
