/**
 * FB-003 — location is asked for where it is used: the route (RW-02, RW-05)
 * and the camera (RW-14). PO ruling 2026-10-27, verbatim: *"if user has
 * location permission not enabled asked the user to give permission"*.
 *
 * Mounting it asks ONCE for that opening (`LocationPort.ensureOn`):
 *   * not allowed yet → Android's own *Allow location?* prompt;
 *   * the phone's Location switched off → Android's own *Turn on location?*;
 *   * refused with *Don't ask again* → Android shows nothing more, so this
 *     draws one line, *"Location is off for this app."*, with *Open settings*
 *     — the only control left, because Android allows no other path.
 * Anything else draws nothing: there is no position button (*"no need of new
 * button"*). Coming back from the settings page asks again, so the line goes
 * the moment it is switched on.
 */
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Notice } from '../../components';
import type { LocationAccess } from './ports';
import { useReads } from './services';

export function LocationAsk() {
  const { t } = useTranslation();
  const { services, refreshHere } = useReads();
  const location = services.location;
  const [access, setAccess] = useState<LocationAccess | null>(null);
  const ask = useCallback(async () => {
    if (!location.ensureOn) return;
    const answer = await location.ensureOn().catch((): LocationAccess => 'unknown');
    setAccess(answer);
    if (answer === 'on') await refreshHere().catch(() => undefined);
  }, [location, refreshHere]);
  useEffect(() => {
    void ask();
    // Once per opening of the screen that mounts it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  if (access !== 'blocked') return null;
  return (
    <Notice
      tone="warning"
      testID="location-off"
      action={
        location.openSettings ? (
          <Button
            testID="location-open-settings"
            onPress={() =>
              void location.openSettings!()
                .then(ask)
                .catch(() => undefined)
            }
          >
            {t('field.reads.location.openSettings')}
          </Button>
        ) : undefined
      }
    >
      {t('field.reads.location.off')}
    </Notice>
  );
}
