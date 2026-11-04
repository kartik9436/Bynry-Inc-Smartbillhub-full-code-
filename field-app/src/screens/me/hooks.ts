/**
 * Small hooks the "me" screens share: who is signed in, a port read that
 * may answer later (or never), and the technician's handset preferences.
 */
import { NavigationContext } from '@react-navigation/native';
import { useCallback, useContext, useEffect, useState } from 'react';

import { useOptionalSession } from '../../session/SessionProvider';
import type { Captor } from './services';
import { readPrefs, subscribePrefs, type HandsetPrefs } from './prefs';
import { useMeServices } from './services';

export interface ActiveTechnician {
  technicianId: string;
  name: string;
  tenant: string;
}

export function useActiveTechnician(): ActiveTechnician | null {
  const session = useOptionalSession();
  const a = session?.snapshot.active;
  return a ? { technicianId: a.technicianId, name: a.displayName, tenant: a.tenant } : null;
}

/**
 * Who an act is captured as: the technician who owns it, and `captured_by`
 * from the CAPTURE CREDENTIAL — never the session's name (Security §3). A
 * credential that has run out throws, and the screen says a password is
 * needed rather than capturing under nobody.
 */
export function useCaptor(): () => Captor {
  const session = useOptionalSession();
  return useCallback(() => {
    const active = session?.snapshot.active;
    if (!session || !active) throw new Error('nobody is signed in');
    const stamp = session.manager.stampCapture();
    return { technicianId: active.technicianId, capturedBy: stamp.captured_by };
  }, [session]);
}

export type Loaded<T> = { state: 'loading' } | { state: 'ready'; value: T } | { state: 'failed' };

/** A port read: loading, then its answer (which may be `null`, "not known"). */
export function usePortRead<T>(read: () => Promise<T>, deps: readonly unknown[]): [Loaded<T>, () => void] {
  const [loaded, setLoaded] = useState<Loaded<T>>({ state: 'loading' });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    read().then(
      (value) => live && setLoaded({ state: 'ready', value }),
      () => live && setLoaded({ state: 'failed' }),
    );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return [loaded, () => setTick((n) => n + 1)];
}

/**
 * The handset preferences, re-read whenever ANY screen writes one and whenever
 * this screen comes back into focus. It read once at mount until FB-015
 * (DEF-FLD-10640): Sync went on saying *Photos wait for wi-fi.* after the
 * switch had changed on Settings.
 */
export function useHandsetPrefs(): [HandsetPrefs, () => void] {
  const { prefs } = useMeServices();
  const [value, setValue] = useState(() => readPrefs(prefs));
  const reread = useCallback(() => setValue(readPrefs(prefs)), [prefs]);
  // Outside a navigator (a tablet pane, a test) there is no focus to follow.
  const navigation = useContext(NavigationContext);
  useEffect(() => subscribePrefs(prefs, reread), [prefs, reread]);
  useEffect(() => (navigation ? navigation.addListener('focus', reread) : undefined), [navigation, reread]);
  return [value, reread];
}
