/**
 * What the job screens need from the app, in one place: the tenant's store,
 * whose work it is, who is capturing, a clock, an id source, the camera and
 * the file picker — and WHICH job is open.
 *
 * ⚠ **NOTHING IN THE APP PROVIDES THIS YET.** The shell (`App.tsx`) opens no
 * tenant store today, so until the coordinator mounts `<JobPortProvider>` with
 * the store opened at sign-in, every job screen renders its frame, its doors
 * and an honest *"No job open"* — never invented figures. Tests mount it with a
 * better-sqlite3 store.
 *
 * WHO: `technicianId` owns the rows (R132); `capturedBy` comes from the
 * CAPTURE CREDENTIAL (Security §3 — never read from the session), which is why
 * the provider is handed a function rather than reading the session itself.
 *
 * WHICH JOB: a door names a SCREEN, not a job (`navigation/doors.ts`), so the
 * open job lives here. FF-15 sets it from its route param `workOrderId`; every
 * screen under it (FF-16…FF-24, FF-58…FF-60) reads it. `openJob()` is how a
 * screen elsewhere (FF-10 Today, FF-14 Stop) opens one.
 */
import { CommonActions, type NavigationProp, type ParamListBase } from '@react-navigation/native';
import { createContext, type ReactNode, useContext, useMemo, useState } from 'react';

import type { TenantDb } from '../../db/database';
import type { CaptureLocation, Captor, Clock } from '../../sync/outbox';
import type { CrashCapture } from '../../telemetry/crashReporter';
import { FRAME, SHELL } from '../../navigation/routing';
import {
  type CameraPort,
  type FilePickerPort,
  type ImageShrinkPort,
  UNAVAILABLE_CAMERA,
  UNAVAILABLE_FILE_PICKER,
  UNAVAILABLE_SHRINK,
} from './camera';

export interface JobServices {
  db: TenantDb;
  /** Who is capturing, from the capture credential (Security §3). */
  captor(): Captor;
  /** The technician's own display name, for "Added in the field · D. Ortiz". */
  displayName: string;
  clock: Clock;
  newId(): string;
  camera?: CameraPort;
  shrink?: ImageShrinkPort;
  files?: FilePickerPort;
  /** The last position fix, or null — a poor or absent fix warns and accepts (R91). */
  location?: () => CaptureLocation | null;
  /** The utility's name, for the photo stamp. */
  tenantName?: string;
  crashes?: CrashCapture;
}

export interface JobPortValue extends Required<Omit<JobServices, 'location' | 'tenantName' | 'crashes'>> {
  location: () => CaptureLocation | null;
  tenantName: string;
  crashes: CrashCapture | null;
  openJobId: string | null;
  setOpenJobId(id: string | null): void;
  /** Bumped after every capture so the screens re-read the store. */
  version: number;
  changed(): void;
}

const JobPortContext = createContext<JobPortValue | null>(null);

export function JobPortProvider(props: { services: JobServices; initialJobId?: string | null; children: ReactNode }) {
  const [openJobId, setOpenJobId] = useState<string | null>(props.initialJobId ?? null);
  const [version, setVersion] = useState(0);
  const s = props.services;
  const value = useMemo<JobPortValue>(
    () => ({
      db: s.db,
      captor: s.captor,
      displayName: s.displayName,
      clock: s.clock,
      newId: s.newId,
      camera: s.camera ?? UNAVAILABLE_CAMERA,
      shrink: s.shrink ?? UNAVAILABLE_SHRINK,
      files: s.files ?? UNAVAILABLE_FILE_PICKER,
      location: s.location ?? (() => null),
      tenantName: s.tenantName ?? '',
      crashes: s.crashes ?? null,
      openJobId,
      setOpenJobId,
      version,
      changed: () => setVersion((v) => v + 1),
    }),
    [s, openJobId, version],
  );
  return <JobPortContext.Provider value={value}>{props.children}</JobPortContext.Provider>;
}

/** The job services, or null when the app has not opened a store (see the header). */
export function useJobPort(): JobPortValue | null {
  return useContext(JobPortContext);
}

/** Open a job from anywhere: FF-15 with the order's id. */
export function openJob(navigation: NavigationProp<ParamListBase>, workOrderId: string): void {
  navigation.dispatch(
    CommonActions.navigate(FRAME, { screen: SHELL, params: { screen: 'FF-15', params: { workOrderId } } }),
  );
}
