/**
 * The bell at the right of the frame's header on FF-10, FF-11, FF-13 and
 * FF-63 — opens Alerts (FF-42). The boards draw a red count on it; the count
 * of unread alerts is the Alerts wave's (FF-42) and is not on the handset
 * yet, so the bell carries no number rather than a guessed one.
 */
import { useNavigation } from '@react-navigation/native';
import { useTranslation } from 'react-i18next';

import { Glyph, IconButton } from '../../components';
import { openScreen } from './go';

export function HeaderBell() {
  const { t } = useTranslation();
  const navigation = useNavigation();
  return (
    <IconButton label={t('field.nav.item.alerts')} onPress={() => openScreen(navigation, 'FF-42')} testID="door-FF-42">
      <Glyph name="bell" />
    </IconButton>
  );
}
