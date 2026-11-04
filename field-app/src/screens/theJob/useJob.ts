/**
 * Which job is open, and what it holds — re-read whenever a capture lands
 * (`port.version`) or the screen comes back into focus, so a tick on FF-16
 * shows on FF-15 the moment the technician returns.
 */
import { useIsFocused, useRoute } from '@react-navigation/native';
import { useEffect, useMemo } from 'react';

import { type JobPortValue, useJobPort } from './JobPort';
import { type JobView, loadJob } from './jobModel';

export interface OpenJob {
  port: JobPortValue | null;
  workOrderId: string | null;
  view: JobView | null;
}

/** The job named by the route (`workOrderId`, or `jobId` — the name FF-10 and
 *  FF-14 pass; both are the work order's id), else the one already open.
 *  DEF-FLD-10353: reading only `workOrderId` opened "No job open" from Today. */
export function useOpenJob(): OpenJob {
  const port = useJobPort();
  const route = useRoute();
  const focused = useIsFocused();
  const params = route.params as { workOrderId?: string; jobId?: string } | undefined;
  const fromRoute = params?.workOrderId ?? params?.jobId ?? null;
  const workOrderId = fromRoute ?? port?.openJobId ?? null;
  const setOpen = port?.setOpenJobId;
  useEffect(() => {
    if (fromRoute && setOpen) setOpen(fromRoute);
  }, [fromRoute, setOpen]);
  const version = port?.version ?? 0;
  const view = useMemo(
    () => (port && workOrderId ? loadJob(port, workOrderId) : null),
    // `version` and `focused` are the re-read triggers, not inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [port, workOrderId, version, focused],
  );
  return { port, workOrderId, view };
}
