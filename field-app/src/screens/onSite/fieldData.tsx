/**
 * What a built screen needs from the app around it: the tenant's database,
 * whose rows these are, a clock, an id source, and the handset ports
 * (money, camera, microphone, position, documents, scanner, signature pad).
 *
 * ⚠ **NOTHING ABOVE THE NAVIGATOR PROVIDES THIS YET.** `App.tsx` mounts the
 * session and the language but opens no database and mounts no
 * `ThemeProvider`, and no other screen has been built that needs either. The
 * on-site, closing and raise screens therefore read through
 * `FieldDataProvider`, and the app root has to mount it (with a
 * `ThemeProvider`) for them to show anything but their "nothing here" state.
 * Reported to the coordinator; the tests mount both, under the real
 * navigator.
 *
 * Which job a screen is about travels as a ROUTE PARAM (`workOrderId`), and
 * `goTo` is the door that carries it: the door table (`navigation/doors.ts`)
 * names screens, not jobs, so a screen that opens another for the same job
 * passes the job along rather than the next screen guessing. A screen READS
 * it through `useJobId()`, which falls back to the job the job screens have
 * open (DEF-FLD-10578).
 */
import { CommonActions, type NavigationProp, type ParamListBase, useNavigation, useRoute } from '@react-navigation/native';
import { createContext, type ReactNode, useContext, useMemo } from 'react';

import type { TenantDb } from '../../db/database';
import { scoped, type ScopedRunner } from '../../db/scoped';
import { routeTo } from '../../navigation/routing';
import type { ScreenId } from '../../navigation/screens';
import type { KeyValueStore } from '../../security/prefs';
import { useOptionalSession } from '../../session/SessionProvider';
import type { WireAssetHit } from '../../sync/fieldApi';
import type { Captor, CaptureDeps } from '../../sync/outbox';
import type { SignaturePort } from '../closing/signature';
import type { ScannerPort } from '../raise/scanner';
import { useJobPort } from '../theJob/JobPort';
import type { MoneyPort } from './money';
import type { DevicePorts } from './ports';

/** FF-36: the reopen is the server's act, online (`field_reopen`, N21). */
export interface ReopenPort {
  /** `reason` in the board's words (`REOPEN_REASONS`); `key` minted on the handset — a replay changes nothing. */
  reopen(workOrderId: string, reason: string, key: string): Promise<void>;
}

/** FF-41's server half: every meter of the utility, when there is a signal (N9). */
export interface AssetFinder {
  search(q: string, page: number): Promise<{ hits: WireAssetHit[]; count: number; hasMore: boolean }>;
}

export interface FieldData {
  db: TenantDb;
  /** Whose rows, when no session says so (previews, tests without a sign-in). */
  technicianId: string;
  newId(): string;
  clock: { now(): Date };
  money: MoneyPort;
  device: DevicePorts;
  scanner: ScannerPort;
  signature: SignaturePort;
  /** The handset's encrypted preferences — where a close's typed debrief is kept (`closing/draft.ts`). */
  prefs?: KeyValueStore;
  /** FF-36's door; absent with no server (previews, tests that do not reopen). */
  reopen?: ReopenPort;
  /** FF-41's server search; absent with no server — the screen then searches the phone only. */
  assets?: AssetFinder;
  /** FB-028 (PO 2026-10-31, W2 = B) — send the outbox NOW: the same run every
   *  other *Send now* starts. Absent with no server (previews, tests). */
  sendNow?: () => Promise<void>;
  /** FB-028 — whether the handset last knew a signal. Absent = unknown. */
  online?: () => boolean;
}

const FieldDataContext = createContext<FieldData | null>(null);

export function FieldDataProvider(props: { value: FieldData; children: ReactNode }) {
  return <FieldDataContext.Provider value={props.value}>{props.children}</FieldDataContext.Provider>;
}

export interface Wave extends FieldData {
  /** Every technician-table read goes through this (R133). */
  s: ScopedRunner;
  /** The signed-in technician — the owner of every capture. */
  me: string;
  /** Their display name from the signed-in profile, for *Captured by …* when
   *  the roster has no row for them (DEF-FLD-10628). Never an id. */
  meName?: string;
  captor: Captor;
  deps: CaptureDeps;
}

/** The data a screen reads, or null when the app has not provided it. */
export function useWave(): Wave | null {
  const data = useContext(FieldDataContext);
  const session = useOptionalSession();
  const me = session?.snapshot.active?.technicianId ?? data?.technicianId ?? '';
  const meName = session?.snapshot.active?.displayName ?? '';
  return useMemo(() => {
    if (!data || !me) return null;
    return {
      ...data,
      me,
      meName,
      s: scoped(data.db, me),
      // The capture credential IS the signed-in technician's (Security §3).
      captor: { technicianId: me, capturedBy: me },
      deps: { newId: data.newId, clock: data.clock },
    };
  }, [data, me, meName]);
}

/** A route parameter as a string, or null. */
export function useParam(name: string): string | null {
  const route = useRoute();
  const params = (route.params ?? {}) as Record<string, unknown>;
  const v = params[name];
  return typeof v === 'string' && v !== '' ? v : null;
}

/**
 * WHICH JOB this screen is about — the one lookup every on-site and closing
 * screen uses: the route's `workOrderId` (or `jobId`, the name FF-10 and FF-14
 * pass) first, else the job the job screens have open (`JobPort.openJobId`).
 * Null only when there is truly no job by either route, which is the one case
 * a screen says "Not on this phone".
 *
 * DEF-FLD-10578 (MQ-023): these screens read ONLY the route param while the
 * job screens keep the open job in the port and their doors carried none, so
 * Debrief, Signature, Close, Activity, Notes, Help and SOPs and Money to check
 * all said "Not on this phone" from inside a job, and no job could be closed.
 * `session/FieldRuntime.tsx` mounts `JobPortProvider` above
 * `FieldDataProvider`, so the port is reachable here in the real app.
 */
export function useJobId(): string | null {
  const workOrderId = useParam('workOrderId');
  const jobId = useParam('jobId');
  const port = useJobPort();
  return workOrderId ?? jobId ?? port?.openJobId ?? null;
}

/** All route params, for a screen that hands them on. */
export function useParams(): Record<string, unknown> {
  const route = useRoute();
  return (route.params ?? {}) as Record<string, unknown>;
}

export type Nav = NavigationProp<ParamListBase>;

/** Open a screen by its id, carrying params to it (the job, a template…). */
export function goTo(navigation: Nav, id: ScreenId, params?: Record<string, unknown>): void {
  const target = routeTo(id);
  if (!params) {
    navigation.dispatch(CommonActions.navigate(target.name, target.params));
    return;
  }
  // routeTo nests { screen, params } down to the leaf; put the params there.
  const nest = (node: Record<string, unknown> | undefined): Record<string, unknown> => {
    if (!node) return params;
    const inner = node.params as Record<string, unknown> | undefined;
    return { ...node, params: inner && 'screen' in inner ? nest(inner) : { ...(inner ?? {}), ...params } };
  };
  if (!target.params) {
    navigation.dispatch(CommonActions.navigate(target.name, params));
    return;
  }
  navigation.dispatch(CommonActions.navigate(target.name, nest(target.params as Record<string, unknown>)));
}

export function useNav(): Nav {
  return useNavigation<Nav>();
}
