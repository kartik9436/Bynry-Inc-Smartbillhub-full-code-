/**
 * One sweep over every interactive thing the kit draws, in every theme:
 * each button and radio has a name and is at least 48pt tall (B14 rule 45,
 * R39 — *"Nothing smaller ships"*). The sweep COUNTS what it checked, and the
 * count is asserted, so a component that stops rendering its control cannot
 * pass by having nothing to check.
 */
import { screen } from '@testing-library/react-native';
import { Text } from 'react-native';
import type { ReactTestInstance } from './helpers';

import {
  Button,
  ChoiceChips,
  EmptyState,
  IconButton,
  ListRow,
  Stepper,
  TopBar,
} from '../../src/components';
import { THEME_NAMES, renderIn, touchHeight } from './helpers';

function Everything() {
  return (
    <>
      <TopBar title="WO-4822" onBack={() => undefined} backLabel="Back" onMenu={() => undefined} menuLabel="More options" />
      <Button variant="primary">Continue</Button>
      <Button variant="secondary" size="sm">Pause</Button>
      <Button variant="danger" disabled>Disconnect anyway</Button>
      <IconButton label="Scan" onPress={() => undefined}>
        <Text>[]</Text>
      </IconButton>
      <ListRow label="Readings" onPress={() => undefined} />
      <ChoiceChips label="How long?" segments={[{ id: 'a', label: '5 min' }, { id: 'b', label: '15 min' }]} active="a" />
      <Stepper value={1} onChange={() => undefined} label="Kit" decreaseLabel="Fewer" increaseLabel="More" />
      <EmptyState title="Nothing" helper="h" ctaLabel="Download" onCta={() => undefined} />
    </>
  );
}

describe.each(THEME_NAMES)('%s theme', (name) => {
  test('every button and radio is named and at least 48pt', () => {
    renderIn(name, <Everything />);
    const controls: ReactTestInstance[] = [
      ...screen.getAllByRole('button'),
      ...screen.getAllByRole('radio'),
    ];
    // 2 top bar + 3 buttons + 1 icon + 1 row + 2 steps + 1 CTA = 10, + 2 radios.
    expect(controls.length).toBe(12);
    for (const el of controls) {
      expect(String(el.props.accessibilityLabel ?? '').length).toBeGreaterThan(0);
      expect(touchHeight(el)).toBeGreaterThanOrEqual(48);
    }
  });
});
