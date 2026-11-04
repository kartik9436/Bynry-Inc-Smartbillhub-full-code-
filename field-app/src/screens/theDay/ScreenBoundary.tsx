/**
 * Every screen of the two waves gettingIn and theDay is wrapped in the
 * telemetry error boundary (T-74), so a render crash is written to the crash
 * file through the scrubber — component names only, never customer text —
 * and the technician sees a plain sentence instead of a white page.
 *
 * The crash capture comes from `FieldData.crashes`. ⚠ The app root does not
 * build telemetry yet (`telemetry/index.ts` lists that hand-off), so until it
 * does the default capture only logs to the developer console: nothing is
 * kept on the handset. Reported, not hidden.
 */
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { EmptyState } from '../../components';
import { TelemetryErrorBoundary } from '../../telemetry/TelemetryErrorBoundary';
import type { CrashCapture } from '../../telemetry/crashReporter';
import type { RawCrash } from '../../telemetry/types';
import { useFieldData } from './fieldData';

export const consoleOnlyCapture: CrashCapture = {
  record: (raw: RawCrash) => {
    // eslint-disable-next-line no-console
    console.error(`[${raw.screen ?? 'screen'}] render crash`, raw.error);
  },
  breadcrumb: () => undefined,
} as unknown as CrashCapture;

export function ScreenBoundary(props: { screen: string; children: ReactNode }) {
  const { t } = useTranslation();
  const { crashes } = useFieldData();
  return (
    <TelemetryErrorBoundary
      capture={crashes ?? consoleOnlyCapture}
      screen={props.screen}
      fallback={<EmptyState title={t('field.common.crashTitle')} helper={t('field.common.crashHelp')} testID={`crashed-${props.screen}`} />}
    >
      {props.children}
    </TelemetryErrorBoundary>
  );
}
