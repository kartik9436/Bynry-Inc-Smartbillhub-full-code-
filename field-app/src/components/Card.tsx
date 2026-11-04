/**
 * Card — every grouped block on the boards: a white card on the page, an
 * optional uppercase title and something on the right of it (FF-15 TIME /
 * ASSET / CREW, FF-25 SERVICE, FF-34 DEBRIEF). The web kit's `Panel` is its
 * equivalent and lends the `title` / `trailing` / `tone` props.
 *
 * A toned card is the boards' alert card: the title sits in a tinted strip and
 * the border takes the tone (FF-27 "BALANCE IS 3 DAYS OLD" in amber, FF-23
 * "NOT ON YOUR VAN" in red, "NOT ON THE TEMPLATE" in blue).
 */
import type { ReactNode } from 'react';
import { View } from 'react-native';
import type { StyleProp, ViewStyle } from 'react-native';

import { useTheme } from '../theme';
import { Kicker, textStyle } from './AppText';
import { Text } from 'react-native';

export type CardTone = 'plain' | 'info' | 'warning' | 'danger';

export interface CardProps {
  title?: string;
  trailing?: ReactNode;
  tone?: CardTone;
  children?: ReactNode;
  testID?: string;
  style?: StyleProp<ViewStyle>;
}

export function Card({ title, trailing, tone = 'plain', children, testID, style }: CardProps) {
  const theme = useTheme();
  const c = theme.colors;
  const toned = tone !== 'plain';
  const pair = toned ? c.status[tone] : null;
  return (
    <View
      testID={testID}
      style={[
        {
          backgroundColor: c.card,
          borderColor: pair ? pair.rule : c.border,
          borderWidth: pair ? theme.borderWidth.emphasis : theme.borderWidth.card,
          borderRadius: theme.radius.lg,
          overflow: 'hidden',
        },
        style,
      ]}
    >
      {title && pair ? (
        <View
          style={{
            backgroundColor: pair.bg,
            paddingHorizontal: theme.space[4],
            paddingVertical: theme.space[3],
            flexDirection: 'row',
            alignItems: 'center',
            gap: theme.space[2],
          }}
        >
          <Text
            accessibilityRole="header"
            style={[
              textStyle(theme, 'micro', 'heavy'),
              {
                color: pair.fg,
                flexGrow: 1,
                textTransform: 'uppercase',
                letterSpacing: theme.tracking.kicker * theme.type.micro,
              },
            ]}
          >
            {title}
          </Text>
          {trailing}
        </View>
      ) : null}
      <View style={{ padding: theme.space[4], gap: theme.space[3] }}>
        {title && !pair ? (
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
            <View style={{ flexGrow: 1 }}>
              <Kicker>{title}</Kicker>
            </View>
            {trailing}
          </View>
        ) : null}
        {children}
      </View>
    </View>
  );
}
