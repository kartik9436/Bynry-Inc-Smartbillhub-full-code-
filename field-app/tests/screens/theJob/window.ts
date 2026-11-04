/**
 * The window size a test runs at. React Native's `useWindowDimensions` is a
 * lazy getter on the package index, which `jest.spyOn` cannot replace, so each
 * screen test file mocks the hook's own module to read this:
 *
 *   jest.mock('react-native/Libraries/Utilities/useWindowDimensions', () => ({
 *     __esModule: true, default: () => require('./window').currentWindow(),
 *   }));
 *
 * The boards' sizes: a 390 × 844 phone, a 1024 × 768 tablet. Jest's default
 * window (750 × 1334) is neither, and reads as a tablet.
 */
let tablet = false;

export function setTablet(value: boolean): void {
  tablet = value;
}

export function currentWindow() {
  return tablet ? { width: 1024, height: 768, scale: 1, fontScale: 1 } : { width: 390, height: 844, scale: 1, fontScale: 1 };
}
