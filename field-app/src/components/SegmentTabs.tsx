/**
 * SegmentTabs — the underlined switch across the top of a list: FF-10's
 * *Today · Tue · Wed · Later · All* and FF-11's *Mine · Nearby* (and the
 * tablet's FF-10 T). Each is a tab, at least 48pt tall, the chosen one
 * underlined in the brand mark and set heavy. Unlike `ChoiceChips` (a choice
 * in a form), this changes WHICH LIST is showing, so its role is `tab`.
 *
 * ⚠ `scrollable` (FB-029, DEF-FLD-10804): five tabs share 390pt at 78pt each,
 * and a long word in some of the eleven languages, or the tablet's narrower
 * list pane, does not fit that. B14 rule 45 fixes the type size, so the row
 * SCROLLS sideways instead of shrinking or wrapping the words: each tab is as
 * wide as its word plus padding (never under 48pt), one line, and the tabs
 * still stretch to fill the row when they all fit.
 */
import { Pressable, ScrollView, Text, View } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';

export interface SegmentTab {
  id: string;
  label: string;
  /** A testID for this one tab (a door test presses it). */
  testID?: string;
}

export interface SegmentTabsProps {
  tabs: readonly SegmentTab[];
  active: string;
  onSelect: (id: string) => void;
  /** The group's accessible name ("Which day"). */
  label: string;
  /** Scroll sideways when the words do not fit, never shrink them (see the header). */
  scrollable?: boolean;
  testID?: string;
}

export function SegmentTabs(props: SegmentTabsProps) {
  const theme = useTheme();
  const c = theme.colors;
  const scrollable = props.scrollable === true;
  const tabs = props.tabs.map((tab) => {
    const selected = tab.id === props.active;
    return (
      <Pressable
        key={tab.id}
        accessibilityRole="tab"
        accessibilityLabel={tab.label}
        accessibilityState={{ selected }}
        onPress={() => props.onSelect(tab.id)}
        testID={tab.testID ?? (props.testID ? `${props.testID}-${tab.id}` : undefined)}
        style={{
          flexGrow: 1,
          flexBasis: scrollable ? 'auto' : 0,
          minWidth: theme.touch.control,
          minHeight: theme.touch.control,
          paddingHorizontal: scrollable ? theme.space[3] : 0,
          alignItems: 'center',
          justifyContent: 'center',
          borderBottomWidth: theme.borderWidth.rule,
          borderBottomColor: selected ? c.brand : 'transparent',
        }}
      >
        <Text
          numberOfLines={scrollable ? 1 : undefined}
          style={textStyle(theme, 'body', selected ? 'heavy' : 'regular', selected ? 'default' : 'muted')}
        >
          {tab.label}
        </Text>
      </Pressable>
    );
  });
  const bar = {
    backgroundColor: c.card,
    borderBottomWidth: theme.borderWidth.divider,
    borderBottomColor: c.border,
  } as const;
  if (scrollable) {
    return (
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        // Today's search box can hold the keyboard open; a tab still switches on the first tap (DEF-FLD-10611).
        keyboardShouldPersistTaps="handled"
        accessibilityRole="tablist"
        accessibilityLabel={props.label}
        testID={props.testID}
        style={[bar, { flexGrow: 0 }]}
        contentContainerStyle={{ flexGrow: 1, flexDirection: 'row' }}
      >
        {tabs}
      </ScrollView>
    );
  }
  return (
    <View accessibilityRole="tablist" accessibilityLabel={props.label} testID={props.testID} style={[bar, { flexDirection: 'row' }]}>
      {tabs}
    </View>
  );
}
