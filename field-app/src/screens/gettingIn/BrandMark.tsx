/**
 * The product mark — the white tile with the brand drop on the splash
 * (FF-01) and the small brand tile at the top of sign-in (FF-05). A drawing,
 * not a control: hidden from the screen reader, because the product name is
 * always written beside it.
 *
 * Interim, as the kit's `Glyph` says: the drop is a text mark until an icon
 * set is installed.
 */
import { View } from 'react-native';

import { Glyph } from '../../components';
import { useTheme } from '../../theme';

export function BrandMark(props: { size: 'sm' | 'lg'; inverse?: boolean }) {
  const theme = useTheme();
  const c = theme.colors;
  const side = props.size === 'lg' ? theme.touch.primary * 2 : theme.touch.primary;
  return (
    <View
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      style={{
        width: side,
        height: side,
        borderRadius: theme.radius.lg,
        backgroundColor: props.inverse ? c.card : c.brandFill,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Glyph name="mark" colour={props.inverse ? c.brand : c.card} size={props.size === 'lg' ? theme.type.title * 2 : theme.type.title} />
    </View>
  );
}
