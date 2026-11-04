/**
 * A tap made WHILE THE KEYBOARD IS UP, as React Native delivers it
 * (DEF-FLD-10611, MQ-021).
 *
 * `fireEvent.press` calls `onPress` directly, so a test that types into a
 * field and then presses Save never meets the one thing the technician met:
 * with the keyboard open, a `ScrollView` whose `keyboardShouldPersistTaps` is
 * unset (React Native's default, `'never'`) CAPTURES the touch, closes the
 * keyboard, and the button underneath never hears it. Save had to be pressed
 * twice, and every test pressed it once and passed.
 *
 * This models React Native's own rule (`ScrollView`'s
 * `_handleStartShouldSetResponderCapture`): the capture phase runs from the
 * root down, so ANY scrolling ancestor of the pressed element that does not
 * persist taps takes the touch first. `'handled'` or `'always'` lets it
 * through. The jest mock of `ScrollView` renders a host `RCTScrollView` with
 * every prop spread onto it, so the prop is readable from the tree.
 *
 * Returns what happened, so a test can say which; never presses when the
 * real device would not have.
 */
import { fireEvent } from '@testing-library/react-native';
type ReactTestInstance = Parameters<typeof fireEvent.press>[0];

const PERSISTS = new Set(['handled', 'always']);

export function tapWithKeyboardUp(element: ReactTestInstance): 'pressed' | 'swallowed' {
  for (let node = element.parent; node; node = node.parent) {
    if (node.type === 'RCTScrollView' && !PERSISTS.has(node.props.keyboardShouldPersistTaps as string)) return 'swallowed';
  }
  fireEvent.press(element);
  return 'pressed';
}
