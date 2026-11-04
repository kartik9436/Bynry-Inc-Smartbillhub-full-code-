/**
 * DEF-FLD-10589 (MQ-031): after the phone's font size changes, every label
 * must be MEASURED AGAIN at the new size — otherwise it is drawn at the new
 * size inside a box measured at the old one, which is the *"label sits
 * top-left of its button"* the beta saw after 2.0 → 1.0.
 *
 * WHY A RE-RENDER IS NOT ENOUGH, AND WHY A ROOT `key` WOULD NOT FIX IT.
 * On Android, Fabric caches text measurements in C++ (`TextLayoutManager`'s
 * `textMeasureCache_`, React Native 0.79), keyed on the string, its layout
 * attributes (font family, size, weight, letter spacing, LINE HEIGHT, …) and
 * the layout constraints. The system font scale is NOT in that key: Android
 * applies it later, in Java, when it turns `sp` into pixels — so the
 * `fontSizeMultiplier` in the key stays 1 at every scale. The cache lives as
 * long as the React instance and survives an activity restart. So:
 *   - a re-render with the same props commits nothing, and nothing re-measures;
 *   - remounting the tree (a `key` on the app root derived from `fontScale`)
 *     builds new nodes with the SAME key, gets the OLD size back from the
 *     cache, and also throws away every screen's state — the open job, a
 *     reading half typed.
 *
 * WHAT THIS DOES: it puts the font scale INTO the key, through the one
 * attribute every label in the app already sets from the type ramp — its
 * line height (`textStyle`, `components/AppText.tsx`). `measureKey(fontScale)`
 * is added to it: **exactly 0 at the scale the app started at**, so nothing
 * moves on a phone whose text size never changes, and a distinct tiny value
 * at any other scale (0.002 sp per hundredth of scale: at most ~0.2 sp,
 * under a pixel). Different value → cache miss → measured at today's size.
 * Because the value is a function of the scale alone, every cache entry made
 * under a value was measured at that scale, so going back to an earlier
 * scale may reuse its entries and is still right.
 *
 * The scale comes from `useWindowDimensions().fontScale` (`ThemeProvider`),
 * which `MainActivity.onConfigurationChanged` now updates the moment the
 * setting changes (`plugins/withFontScaleConfigChanges.js`). Font scaling is
 * never capped: no `maxFontSizeMultiplier` anywhere, 200% included.
 *
 * Known edge, not closed here: text measured between the setting changing
 * and JavaScript hearing of it (one frame or so) is cached under the old
 * value at the new size.
 */

let launchScale: number | undefined;

/** Line-height nudge for this font scale: 0 at the launch scale, distinct at any other. */
export function measureKey(fontScale: number): number {
  if (!(fontScale > 0)) return 0;
  if (launchScale === undefined) launchScale = fontScale;
  return Math.round((fontScale - launchScale) * 100) / 500;
}

/** Tests only: forget the launch scale. */
export function resetMeasureKeyForTests(): void {
  launchScale = undefined;
}
