/**
 * The kit pieces the on-site, closing and raise screens added (B14 rule 43:
 * a block drawn on more than one board is a component): RadioList,
 * SearchField, FactGrid / FactLines, DotLine, Mark, ScreenFrame / GroupLabel.
 * Each renders in every theme, names itself to a screen reader, and keeps
 * its controls at 48pt or more.
 */
import { fireEvent, screen } from '@testing-library/react-native';
import { Text } from 'react-native';

import { DotLine } from '../../src/components/DotLine';
import { FactGrid, FactLines } from '../../src/components/Facts';
import { Mark } from '../../src/components/Mark';
import { RadioList } from '../../src/components/RadioList';
import { GroupLabel, ScreenFrame } from '../../src/components/ScreenFrame';
import { SearchField } from '../../src/components/SearchField';
import { THEME_NAMES, renderIn, styleOf, themeOf, touchHeight } from './helpers';

describe.each(THEME_NAMES)('%s theme', (name) => {
  test('RadioList: a named group of radios, one checked, each at least 48pt', () => {
    const picked: string[] = [];
    renderIn(
      name,
      <RadioList
        label="Outcome"
        options={[
          { id: 'passed', label: 'Passed' },
          { id: 'failed', label: 'Failed' },
        ]}
        value="failed"
        onChange={(id) => picked.push(id)}
        testID="o"
      />,
    );
    expect(screen.getByTestId('o')).toHaveProp('accessibilityRole', 'radiogroup');
    expect(screen.getByTestId('o')).toHaveProp('accessibilityLabel', 'Outcome');
    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(2);
    for (const r of radios) expect(touchHeight(r)).toBeGreaterThanOrEqual(48);
    expect(screen.getByTestId('o-failed')).toHaveProp('accessibilityState', { checked: true, selected: true });
    expect(screen.getByTestId('o-passed')).toHaveProp('accessibilityState', { checked: false, selected: false });
    fireEvent.press(screen.getByTestId('o-passed'));
    expect(picked).toEqual(['passed']);
  });

  test('SearchField: a search input named by its label, 48pt, with its help line', () => {
    const typed: string[] = [];
    renderIn(name, <SearchField label="Search assets" value="" onChangeText={(v) => typed.push(v)} help="Serial or badge" />);
    const input = screen.getByLabelText('Search assets');
    expect(input).toHaveProp('accessibilityRole', 'search');
    expect(touchHeight(input)).toBeGreaterThanOrEqual(48);
    expect(screen.getByText('Serial or badge')).toBeTruthy();
    fireEvent.changeText(input, 'W-447');
    expect(typed).toEqual(['W-447']);
  });

  test('FactGrid and FactLines: each pair is one element a screen reader reads together', () => {
    renderIn(
      name,
      <>
        <FactGrid facts={[{ label: 'Serial', value: 'W-4471' }]} />
        <FactLines split facts={[{ label: 'Labour', value: '1h 12m', tone: 'success', strong: true, testID: 'lab' }]} />
      </>,
    );
    expect(screen.getByLabelText('Serial, W-4471')).toBeTruthy();
    expect(screen.getByTestId('lab')).toHaveProp('accessibilityLabel', 'Labour, 1h 12m');
    expect(styleOf(screen.getByText('1h 12m')).color).toBe(themeOf(name).colors.statusInk.success); // ink on the card (DEF-FLD-10360)
  });

  test('DotLine and Mark: the words carry the meaning; the mark is hidden', () => {
    renderIn(
      name,
      <>
        <DotLine tone="warning" mark="clock" testID="d">
          Waiting for the office
        </DotLine>
        <Mark name="check" />
      </>,
    );
    expect(screen.getByTestId('d')).toHaveProp('accessibilityLabel', 'Waiting for the office');
    expect(styleOf(screen.getByText('Waiting for the office')).color).toBe(themeOf(name).colors.statusInk.warning); // ink on the card (DEF-FLD-10360)
    expect(screen.getByTestId('mark-check', { includeHiddenElements: true })).toHaveProp('accessible', false);
  });

  test('ScreenFrame: the page, a fixed header, the scroll and the pinned action bar', () => {
    renderIn(
      name,
      <ScreenFrame testID="f" header={<Text>head</Text>} footer={<Text>foot</Text>}>
        <GroupLabel>For this job</GroupLabel>
      </ScreenFrame>,
    );
    expect(styleOf(screen.getByTestId('f')).backgroundColor).toBe(themeOf(name).colors.page);
    expect(screen.getByText('head')).toBeTruthy();
    expect(screen.getByText('foot')).toBeTruthy();
    expect(screen.getByRole('header')).toHaveTextContent('For this job');
  });
});
