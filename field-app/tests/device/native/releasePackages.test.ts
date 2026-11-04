/**
 * The release packages (expo-constants, expo-updates, expo-dev-client) load
 * under Jest without a native module, so the release lane's `src/release/`
 * can read the build number in tests.
 */
import Constants from 'expo-constants';
import * as Updates from 'expo-updates';

test('expo-constants and expo-updates load in Jest', () => {
  expect(Constants).toBeDefined();
  expect(typeof Constants.expoConfig === 'object' || Constants.expoConfig === null).toBe(true);
  expect(Updates).toBeDefined();
});

test('expo-dev-client resolves (it is a native launcher; nothing in src imports it)', () => {
  expect(() => require.resolve('expo-dev-client')).not.toThrow();
});
