/**
 * The kit piece the tablet layouts added (T-28): NumberDisc, FF-13 T's
 * numbered stop — its number in the status pair of its state, in every theme,
 * and hidden from a screen reader because the row beside it says it in words.
 */
import { screen } from '@testing-library/react-native';

import { NumberDisc } from '../../src/components';
import { THEME_NAMES, renderIn, styleOf, themeOf } from './helpers';

describe.each(THEME_NAMES)('%s theme', (name) => {
  test.each(['success', 'info', 'neutral'] as const)('NumberDisc in the %s pair', (tone) => {
    renderIn(name, <NumberDisc n={2} tone={tone} testID="disc" />);
    const disc = screen.getByTestId('disc', { includeHiddenElements: true });
    const pair = themeOf(name).colors.status[tone];
    expect(styleOf(disc)).toMatchObject({ backgroundColor: pair.bg, borderColor: pair.rule });
    expect(disc.props.accessible).toBe(false);
    expect(disc.props.importantForAccessibility).toBe('no-hide-descendants');
    const text = screen.getByText('2', { includeHiddenElements: true });
    expect(styleOf(text).color).toBe(pair.fg);
  });
});
