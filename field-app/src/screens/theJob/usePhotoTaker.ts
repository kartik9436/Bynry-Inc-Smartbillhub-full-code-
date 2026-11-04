/**
 * Take one photograph for the open job: camera → shrink into the band → hash
 * (`camera.ts`), stamped with who, when, where and which order (R94). Says in
 * words when the camera cannot be opened rather than failing silently — today
 * that is every time, because no camera package is installed.
 */
import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { CameraUnavailableError, type ReadyPhoto, takeReadyPhoto } from './camera';
import type { JobPortValue } from './JobPort';
import { stampForCapture } from './photoStamp';

export function usePhotoTaker(port: JobPortValue | null, orderNumber: string) {
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const take = useCallback(async (): Promise<ReadyPhoto | null> => {
    if (!port) return null;
    setError(null);
    setBusy(true);
    try {
      const stamp = stampForCapture(
        t,
        port.clock.now(),
        port.location(),
        port.displayName,
        orderNumber,
        port.tenantName,
      );
      return await takeReadyPhoto(port.camera, port.shrink, stamp);
    } catch (err) {
      setError(err instanceof CameraUnavailableError ? t('field.job.camera.unavailable') : t('field.job.camera.failed'));
      return null;
    } finally {
      setBusy(false);
    }
  }, [port, orderNumber, t]);
  return { take, error, busy };
}
