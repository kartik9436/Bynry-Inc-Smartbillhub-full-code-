/**
 * Every text/background pair in every theme measures at least 4.5:1 (WCAG AA
 * body text), computed — not eyeballed. Mark colours (the brand on a page or
 * a card) are held to 3:1, the bar field-app rule R100 names for them.
 *
 * The pairs are the ones the kit actually draws: a component never puts a
 * theme colour on a background that is not listed here.
 */
import { contrastRatio, THEMES } from '../../src/theme';
import type { Theme, StatusTone } from '../../src/theme';

const TONES: StatusTone[] = ['success', 'warning', 'danger', 'info', 'neutral'];

function textPairs(t: Theme): Array<[string, string, string]> {
  const c = t.colors;
  const pairs: Array<[string, string, string]> = [
    ['text on page', c.text, c.page],
    ['text on card', c.text, c.card],
    ['text on surface', c.text, c.surface],
    ['muted on page', c.textMuted, c.page],
    ['muted on card', c.textMuted, c.card],
    ['muted on surface', c.textMuted, c.surface],
    ['primary button text', c.actionText, c.actionFill],
    ['danger tier on card', c.dangerAction, c.card],
    ['danger tier on page', c.dangerAction, c.page],
    ['disabled text', c.disabledText, c.disabledFill],
    ['selected chip text', c.selectedText, c.selectedFill],
    ['toast text', c.toastText, c.toastFill],
  ];
  for (const tone of TONES) {
    pairs.push([`${tone} chip`, c.status[tone].fg, c.status[tone].bg]);
    // DEF-FLD-10360: a tone drawn as ink on the card or page (a tick, "0 left").
    pairs.push([`${tone} ink on card`, c.statusInk[tone], c.card]);
    pairs.push([`${tone} ink on page`, c.statusInk[tone], c.page]);
  }
  return pairs;
}

const cases = Object.values(THEMES).flatMap((t) =>
  textPairs(t).map(([label, fg, bg]) => [t.name, label, fg, bg] as const),
);

describe('contrast — every text pair ≥ 4.5:1', () => {
  test.each(cases)('%s · %s (%s on %s)', (_theme, _label, fg, bg) => {
    expect(contrastRatio(fg, bg)).toBeGreaterThanOrEqual(4.5);
  });

  test('the count of pairs checked is printed and is what we expect', () => {
    console.log(`contrast: ${cases.length} text pairs across ${Object.keys(THEMES).length} themes`);
    expect(cases.length).toBe(3 * (12 + 3 * TONES.length));
  });
});

describe('contrast — marks ≥ 3:1', () => {
  test.each(Object.values(THEMES).map((t) => [t.name, t] as const))('%s brand', (_n, t) => {
    expect(contrastRatio(t.colors.brand, t.colors.page)).toBeGreaterThanOrEqual(3);
    expect(contrastRatio(t.colors.brand, t.colors.card)).toBeGreaterThanOrEqual(3);
  });
});

describe('the design\'s own figures', () => {
  test('white on the brand orange is 4.20:1 and fails; on the button fill 4.56:1 and passes', () => {
    expect(contrastRatio('#ffffff', '#ec3013')).toBeCloseTo(4.2, 1);
    expect(contrastRatio('#ffffff', '#e12e13')).toBeCloseTo(4.56, 1);
  });
});
