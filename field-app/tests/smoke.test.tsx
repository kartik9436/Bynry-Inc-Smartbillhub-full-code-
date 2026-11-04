import { render, screen } from '@testing-library/react-native';
import App from '../src/App';

test('the app mounts', () => {
  render(<App />);
  expect(screen.getByText('SMART360 Next Field')).toBeTruthy();
});
