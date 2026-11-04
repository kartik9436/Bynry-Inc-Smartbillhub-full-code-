/**
 * A job's dispatch state as a chip — the word and tone from THE ONE LIST
 * (`jobStatus.ts`, MQ-009). The job page (FF-15, and the tablet job pane), the
 * stop (FF-14), the tablet day list and the disconnect board (FF-27) all use
 * this, so none of them can print a raw server code (DEF-FLD-10610: FF-15
 * printed `SCHEDULED` untranslated, in the green tone). A state that is not one
 * of the seven renders nothing.
 */
import { useTranslation } from 'react-i18next';

import { StatusChip } from '../../components/StatusChip';
import { statusLook } from './jobStatus';

export function DispatchStateChip({ state, testID }: { state: string | null | undefined; testID?: string }) {
  const { t } = useTranslation();
  const look = statusLook(state);
  if (!look.labelKey) return null;
  return (
    <StatusChip tone={look.tone} testID={testID}>
      {t(look.labelKey)}
    </StatusChip>
  );
}
