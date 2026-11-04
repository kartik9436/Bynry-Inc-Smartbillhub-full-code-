/**
 * DEF-FLD-10589 (MQ-031): when the phone's font scale changes, every label's
 * line height moves by `measureKey`, so Fabric's text-measure cache misses and
 * the label is measured again at the new size (`src/theme/measureKey.ts`).
 * At the scale the app started at, nothing moves at all.
 *
 * WHAT WOULD MAKE THIS PASS WRONGLY: a label that does not take its style from
 * `textStyle`. Every on-screen label does today except the photo stamp, which
 * is drawn off screen into an image (`device/native/DeviceHost.tsx`).
 */
import { act, render, screen } from '@testing-library/react-native';
import { Dimensions, StyleSheet } from 'react-native';

import { AppText } from '../../src/components/AppText';
import { ThemeProvider } from '../../src/theme';
import { measureKey, resetMeasureKeyForTests } from '../../src/theme/measureKey';

function setFontScale(fontScale: number) {
  const window = Dimensions.get('window');
  const screenDims = Dimensions.get('screen');
  act(() => {
    Dimensions.set({ window: { ...window, fontScale }, screen: { ...screenDims, fontScale } });
  });
}

const lineHeight = () => StyleSheet.flatten(screen.getByTestId('label').props.style).lineHeight as number;

describe('measureKey', () => {
  beforeEach(() => resetMeasureKeyForTests());

  test('0 at the launch scale; distinct, small and stable at every other Android step', () => {
    expect(measureKey(1)).toBe(0);
    const steps = [0.85, 1, 1.15, 1.3, 1.5, 1.8, 2];
    const keys = steps.map(measureKey);
    expect(new Set(keys).size).toBe(steps.length);
    for (let i = 1; i < keys.length; i++) expect(Math.abs(keys[i]! - keys[i - 1]!)).toBeGreaterThanOrEqual(0.005);
    for (const k of keys) expect(Math.abs(k)).toBeLessThanOrEqual(0.25);
    expect(measureKey(1)).toBe(0);
    expect(measureKey(2)).toBe(keys[6]);
  });
});

describe('a font-size change re-measures every label (DEF-FLD-10589)', () => {
  beforeEach(() => resetMeasureKeyForTests());
  afterEach(() => setFontScale(2));

  test("the label's line height follows the phone's font scale, and returns when it does", () => {
    setFontScale(1);
    render(
      <ThemeProvider initialMode="light">
        <AppText testID="label">Unlock</AppText>
      </ThemeProvider>,
    );
    const atLaunch = lineHeight();
    expect(Number.isInteger(atLaunch)).toBe(true);

    setFontScale(2);
    expect(lineHeight()).not.toBe(atLaunch);
    expect(lineHeight()).toBeCloseTo(atLaunch + measureKey(2), 6);

    setFontScale(1);
    expect(lineHeight()).toBe(atLaunch);
  });
});
