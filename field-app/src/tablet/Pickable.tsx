/**
 * The list half of a T-29 board, in two components (B14 rule 43):
 *
 *   `Pickable` — wraps one row of a PHONE list screen. Beside its detail
 *     (a split T2 frame) the row becomes a button that picks it, ruled heavy
 *     while it is the one on show (FF-10 T, FF-35 T); anywhere else it is the
 *     phone's row, untouched — or, given `onPhone`, the phone's own press.
 *   `PickList` — the drawn list itself, for a board whose phone screen is
 *     not a list of the things its detail shows (FF-31 T draws the job's DAYS
 *     beside the timeline, FF-51 T the settings' SECTIONS beside one of them):
 *     a kicker and its line, then one card per item — its name, the figure on
 *     the right, the line under it — the first picked until one is pressed.
 *
 * Every colour, size and border is the theme's; nothing here is a literal.
 */
import { type ReactNode } from 'react';
import { Pressable, ScrollView, View } from 'react-native';

import { AppText, Kicker } from '../components';
import { useTheme } from '../theme';
import { useDefaultSelection, usePick } from './selection';

export function Pickable(props: {
  id: string;
  /** What a screen reader says for the row. */
  label: string;
  children: ReactNode;
  /** The phone's own press, kept where the row has one. */
  onPhone?: () => void;
  /** The record the detail reads, where it is not on the handset to re-read by id (FF-11's unassigned job). */
  payload?: unknown;
  /** The row rules itself heavy (its card already has a border to thicken): draw no border here. */
  bare?: boolean;
  testID?: string;
}) {
  const theme = useTheme();
  const pick = usePick();
  if (!pick.active) {
    if (!props.onPhone) return <>{props.children}</>;
    return (
      <Pressable accessibilityRole="button" accessibilityLabel={props.label} onPress={props.onPhone} testID={props.testID}>
        {props.children}
      </Pressable>
    );
  }
  const picked = pick.isPicked(props.id);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={props.label}
      accessibilityState={{ selected: picked }}
      onPress={() => pick.pick(props.id, props.payload)}
      testID={props.testID}
      style={
        picked && !props.bare
          ? { borderColor: theme.colors.text, borderWidth: theme.borderWidth.emphasis, borderRadius: theme.radius.lg, minHeight: theme.touch.control }
          : { minHeight: theme.touch.control }
      }
    >
      {props.children}
    </Pressable>
  );
}

export interface PickItem {
  id: string;
  title: string;
  /** The figure on the right (*1h 12m*, *On*, *62*). */
  value?: string | null;
  /** The line under the name. */
  sub?: string | null;
}

export function PickList(props: {
  kicker: string;
  line?: string | null;
  items: readonly PickItem[];
  /** What shows when there is nothing to pick. */
  empty?: ReactNode;
  /** Above the kicker (a search box, a period switch). */
  header?: ReactNode;
  testID?: string;
}) {
  const theme = useTheme();
  const pick = usePick();
  useDefaultSelection(props.items[0]?.id ?? null);
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID={props.testID}>
      <ScrollView keyboardShouldPersistTaps="handled" style={{ flex: 1 }} contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }}>
        {props.header}
        <View>
          <Kicker>{props.kicker}</Kicker>
          {props.line ? (
            <AppText variant="label" tone="muted">
              {props.line}
            </AppText>
          ) : null}
        </View>
        {props.items.length === 0 ? props.empty : null}
        {props.items.map((item) => {
          const picked = pick.isPicked(item.id);
          return (
            <Pressable
              key={item.id}
              accessibilityRole="button"
              accessibilityLabel={[item.title, item.value, item.sub].filter(Boolean).join(', ')}
              accessibilityState={{ selected: picked }}
              onPress={() => pick.pick(item.id)}
              testID={`pick-${item.id}`}
              style={{
                minHeight: theme.touch.control,
                backgroundColor: theme.colors.card,
                borderColor: picked ? theme.colors.text : theme.colors.border,
                borderWidth: picked ? theme.borderWidth.emphasis : theme.borderWidth.card,
                borderRadius: theme.radius.lg,
                padding: theme.space[4],
                gap: theme.space[1],
              }}
            >
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', gap: theme.space[3] }}>
                <AppText variant="body" weight="heavy" style={{ flexShrink: 1 }}>
                  {item.title}
                </AppText>
                {item.value ? (
                  <AppText variant="label" tone="muted">
                    {item.value}
                  </AppText>
                ) : null}
              </View>
              {item.sub ? (
                <AppText variant="label" tone="muted">
                  {item.sub}
                </AppText>
              ) : null}
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}
