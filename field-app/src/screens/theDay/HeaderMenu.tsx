/**
 * The menu button at the left of the header, for the two PUSHED screens the
 * boards draw as top-level pages with the menu rather than a back arrow:
 * FF-11 Nearby (Today's other half) and FF-13 Map (a menu entry of its own).
 * It opens the drawer (FF-09); on a tablet the sidebar is already open and
 * the frame shows no button. The system back gesture still goes back.
 */
import { DrawerActions, useNavigation } from '@react-navigation/native';
import { useTranslation } from 'react-i18next';

import { Glyph, IconButton } from '../../components';

export function HeaderMenu() {
  const { t } = useTranslation();
  const navigation = useNavigation();
  return (
    <IconButton label={t('field.nav.menu')} onPress={() => navigation.dispatch(DrawerActions.openDrawer())} testID="door-FF-09">
      <Glyph name="drawer" />
    </IconButton>
  );
}
