import { act, fireEvent, render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';

import {
  Button,
  EmptyState,
  Sheet,
  TOAST_DISMISS_MS,
  ToastProvider,
  createToastQueue,
  useToast,
  useToastIfMounted,
} from '../../src/components';
import { ThemeProvider } from '../../src/theme';
import { renderIn, styleOf, themeOf } from './helpers';

describe('Sheet', () => {
  test('shows its title and content, and closes from the dimmed page', () => {
    const onClose = jest.fn();
    renderIn(
      'light',
      <Sheet visible title="Add a step" closeLabel="Close" onClose={onClose} testID="s"
        footer={<Button>Cancel</Button>}>
        <Text>What did you do?</Text>
      </Sheet>,
    );
    expect(screen.getByRole('header', { name: 'Add a step' })).toBeTruthy();
    expect(screen.getByText('What did you do?')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();
    // The dimmed page is hidden from VoiceOver by the modal panel, on purpose,
    // so it is found by id; it is still a named button for touch and Android.
    const scrim = screen.getByTestId('s-scrim', { includeHiddenElements: true });
    expect(scrim.props.accessibilityRole).toBe('button');
    expect(scrim.props.accessibilityLabel).toBe('Close');
    expect(styleOf(scrim).backgroundColor).toBe(themeOf('light').colors.scrim);
    fireEvent.press(scrim);
    expect(onClose).toHaveBeenCalledTimes(1);
    // The VoiceOver escape gesture closes it too.
    fireEvent(screen.getByTestId('s-panel'), 'accessibilityEscape');
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  test('renders nothing when not visible', () => {
    renderIn(
      'light',
      <Sheet visible={false} title="Add a step" closeLabel="Close" onClose={() => undefined}>
        <Text>inside</Text>
      </Sheet>,
    );
    expect(screen.queryByText('inside')).toBeNull();
  });
});

describe('EmptyState', () => {
  test('no ctaLabel draws no button at all', () => {
    renderIn('light', <EmptyState title="No jobs today" helper="Pull to refresh." />);
    expect(screen.getByRole('header', { name: 'No jobs today' })).toBeTruthy();
    expect(screen.queryByRole('button')).toBeNull();
  });

  test('a live CTA presses', () => {
    const onCta = jest.fn();
    renderIn('light', <EmptyState title="No routes" helper="Download today’s." ctaLabel="Download" onCta={onCta} />);
    fireEvent.press(screen.getByRole('button', { name: 'Download' }));
    expect(onCta).toHaveBeenCalled();
  });

  test('a blocked CTA is disabled and its reason is on screen, not in a tooltip', () => {
    const onCta = jest.fn();
    renderIn(
      'light',
      <EmptyState title="No routes" helper="h" ctaLabel="Download" onCta={onCta} ctaReason="Needs a signal" />,
    );
    const btn = screen.getByRole('button', { name: 'Download' });
    expect(btn.props.accessibilityState).toMatchObject({ disabled: true });
    fireEvent.press(btn);
    expect(onCta).not.toHaveBeenCalled();
    expect(screen.getByText('Needs a signal')).toBeTruthy();
  });
});

describe('Toast', () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  test('the queue: one at a time, FIFO, each its full time, none lost', () => {
    const q = createToastQueue();
    q.fire('Reading saved');
    q.fire('Photo saved');
    expect(q.getCurrent()).toBe('Reading saved');
    expect(q.getPending()).toEqual(['Photo saved']);
    jest.advanceTimersByTime(TOAST_DISMISS_MS);
    expect(q.getCurrent()).toBe('Photo saved');
    jest.advanceTimersByTime(TOAST_DISMISS_MS - 1);
    expect(q.getCurrent()).toBe('Photo saved');
    jest.advanceTimersByTime(1);
    expect(q.getCurrent()).toBeNull();
  });

  function Fire() {
    const toast = useToast();
    return <Button onPress={() => toast('Step added')}>Go</Button>;
  }

  test('useToast shows the message in a polite live region, then it goes', () => {
    render(
      <ThemeProvider initialMode="light">
        <ToastProvider>
          <Fire />
        </ToastProvider>
      </ThemeProvider>,
    );
    expect(screen.getByTestId('toast-region').props.accessibilityLiveRegion).toBe('polite');
    fireEvent.press(screen.getByRole('button', { name: 'Go' }));
    expect(screen.getByText('Step added')).toBeTruthy();
    act(() => {
      jest.advanceTimersByTime(TOAST_DISMISS_MS);
    });
    expect(screen.queryByText('Step added')).toBeNull();
  });

  test('useToast outside a provider throws; useToastIfMounted does nothing', () => {
    jest.spyOn(console, 'error').mockImplementation(() => undefined);
    expect(() => renderIn('light', <Fire />)).toThrow('useToast must be used inside <ToastProvider>');
    (console.error as jest.Mock).mockRestore();
    function Quiet() {
      const t = useToastIfMounted();
      t('nothing');
      return <Text>ok</Text>;
    }
    renderIn('light', <Quiet />);
    expect(screen.getByText('ok')).toBeTruthy();
  });
});
