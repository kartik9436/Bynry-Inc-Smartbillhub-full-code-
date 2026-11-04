/**
 * The session, in React: one `SessionManager` for the app, its snapshot as
 * context, and the two things that lock it — five minutes with no touch, and
 * five minutes away from the app (Security tab §3 as amended 2026-10-26,
 * MQ-019: it read *"the app going to the background"* until then, and locked
 * the instant Android reported its own permission dialog as backgrounding —
 * DEF-FLD-10614). Leaving records the time; returning to `active` decides.
 *
 * A touch anywhere counts as activity: the provider's root view claims no
 * touch, it only watches them start (`onTouchStart` bubbles without taking the
 * gesture away from whatever was pressed).
 */
import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { AppState, type AppStateStatus, View } from 'react-native';

import { type SessionManager, type SessionSnapshot } from './sessionManager';

/** How often the idle clock is checked. A lock lands within this of the five minutes. */
export const IDLE_CHECK_MS = 15 * 1000;

interface SessionContextValue {
  manager: SessionManager;
  snapshot: SessionSnapshot;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ manager, children }: { manager: SessionManager; children: ReactNode }) {
  const [snapshot, setSnapshot] = useState<SessionSnapshot>(() => manager.snapshot());

  useEffect(() => manager.subscribe(setSnapshot), [manager]);

  useEffect(() => {
    const timer = setInterval(() => manager.tick(), IDLE_CHECK_MS);
    return () => clearInterval(timer);
  }, [manager]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state: AppStateStatus) => {
      if (state === 'background' || state === 'inactive') manager.onBackground();
      else if (state === 'active') manager.onForeground();
    });
    return () => sub.remove();
  }, [manager]);

  const value = useMemo(() => ({ manager, snapshot }), [manager, snapshot]);

  return (
    <SessionContext.Provider value={value}>
      <View style={{ flex: 1 }} onTouchStart={() => manager.touch()} testID="session-activity-root">
        {children}
      </View>
    </SessionContext.Provider>
  );
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession outside SessionProvider');
  return ctx;
}

/** The same, for a component that may render before the provider exists (previews). */
export function useOptionalSession(): SessionContextValue | null {
  return useContext(SessionContext);
}
