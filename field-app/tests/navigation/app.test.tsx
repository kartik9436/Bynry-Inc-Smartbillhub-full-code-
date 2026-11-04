/**
 * `App.tsx` boots its services and mounts the providers and the navigation:
 * on a fresh handset nobody is signed in, so it lands on the splash (FF-01).
 */
import 'react-native-gesture-handler/jestSetup';

import { render, screen } from '@testing-library/react-native';

import App, { PRODUCT_NAME } from '../../src/App';
import { MemorySecretStore } from '../../src/security/secretStore';
import { FakeAuthApi, MemoryOutbox } from '../session/fakes';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));
// Without native metrics the real provider renders nothing until the first
// layout, which never comes in a test.
jest.mock('react-native-safe-area-context', () => require('react-native-safe-area-context/jest/mock').default);

test('shows the product name while booting, then the splash of the signed-out gate', async () => {
  const overrides = { secrets: new MemorySecretStore(), api: new FakeAuthApi(), outbox: new MemoryOutbox() };
  render(<App overrides={overrides} />);
  expect(screen.getByText(PRODUCT_NAME)).toBeTruthy();
  expect(await screen.findByTestId('screen-FF-01')).toBeTruthy();
  expect(screen.queryByTestId('app-boot-failed')).toBeNull();
});
