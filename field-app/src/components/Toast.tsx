/**
 * Toast — brief feedback after a COMMITTED action. A port of the web kit's
 * `Toast.tsx` (BR-SHL-021 / BR-SHL-022): the same names (`createToastQueue`,
 * `ToastProvider`, `useToast`, `useToastIfMounted`, `ToastSurface`,
 * `TOAST_DISMISS_MS`), the same laws, a native surface.
 *
 *   - every toast dismisses itself after ~2.5s, nothing to tap (BR-SHL-021);
 *   - one at a time, later ones queue FIFO, none lost, each gets its full
 *     time (BR-SHL-022);
 *   - text only, never an action, never focus-stealing; announced through a
 *     polite live region;
 *   - a toast is feedback, never a record — and a failure never fires one,
 *     it renders a state (the web's US-SHL-012 TC-4).
 *
 * The queue is the web's, line for line in behaviour: plain state and a
 * timer, no React, so its laws are testable without rendering.
 */
import { createContext, useContext, useRef, useSyncExternalStore } from 'react';
import type { ReactNode } from 'react';
import { Text, View } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';

export const TOAST_DISMISS_MS = 2500;

export interface ToastQueue {
  fire: (message: string) => void;
  dismissCurrent: () => void;
  getCurrent: () => string | null;
  getPending: () => readonly string[];
  subscribe: (listener: () => void) => () => void;
}

export function createToastQueue(): ToastQueue {
  let current: string | null = null;
  const pending: string[] = [];
  let timer: ReturnType<typeof setTimeout> | undefined;
  const listeners = new Set<() => void>();

  function notify(): void {
    for (const listener of listeners) listener();
  }

  function show(message: string): void {
    current = message;
    timer = setTimeout(dismissCurrent, TOAST_DISMISS_MS);
    notify();
  }

  function dismissCurrent(): void {
    clearTimeout(timer);
    current = null;
    const next = pending.shift();
    if (next === undefined) {
      notify();
    } else {
      show(next);
    }
  }

  function fire(message: string): void {
    if (current === null) {
      show(message);
    } else {
      pending.push(message);
    }
  }

  return {
    fire,
    dismissCurrent,
    getCurrent: () => current,
    getPending: () => [...pending],
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}

/** The surface: a persistent polite live region at the bottom of the screen,
 *  never a touch target. */
export function ToastSurface(props: { message: string | null }) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <View
      pointerEvents="none"
      accessibilityLiveRegion="polite"
      testID="toast-region"
      style={{
        position: 'absolute',
        left: theme.space[3],
        right: theme.space[3],
        bottom: theme.space[8] + theme.touch.primary,
        alignItems: 'center',
      }}
    >
      {props.message !== null ? (
        <View
          accessible
          accessibilityRole="alert"
          accessibilityLabel={props.message}
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: theme.space[2],
            backgroundColor: c.toastFill,
            borderRadius: theme.radius.md,
            paddingHorizontal: theme.space[5],
            paddingVertical: theme.space[3],
          }}
        >
          <View
            accessible={false}
            style={{ width: theme.space[2], height: theme.space[2], backgroundColor: c.brand }}
          />
          <Text style={[textStyle(theme, 'body', 'semibold'), { color: c.toastText }]}>
            {props.message}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

const ToastContext = createContext<ToastQueue | null>(null);

/** Mounted ONCE, above the navigator, so a toast survives the navigation that
 *  usually follows a commit. `queue` lets a test drive one it also inspects. */
export function ToastProvider(props: { children: ReactNode; queue?: ToastQueue }) {
  const own = useRef<ToastQueue | null>(null);
  if (own.current === null) own.current = createToastQueue();
  const queue = props.queue ?? own.current;
  const current = useSyncExternalStore(queue.subscribe, queue.getCurrent, queue.getCurrent);
  return (
    <ToastContext.Provider value={queue}>
      <View style={{ flex: 1 }}>
        {props.children}
        <ToastSurface message={current} />
      </View>
    </ToastContext.Provider>
  );
}

export function useToast(): (message: string) => void {
  const queue = useContext(ToastContext);
  if (queue === null) throw new Error('useToast must be used inside <ToastProvider>');
  return queue.fire;
}

/** For a shared component that may be mounted without a provider: fires
 *  nothing then, never throws (the web's `useToastIfMounted`). */
export function useToastIfMounted(): (message: string) => void {
  const queue = useContext(ToastContext);
  return queue === null ? () => undefined : queue.fire;
}
