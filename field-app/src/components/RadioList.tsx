/**
 * RadioList — one choice from a short list, each option a full-width card
 * with a circle on its left. ONE component for two waves (B14 rule 43; merged
 * in the integration lane):
 *   - closing: FF-34 OUTCOME (Passed · Partly done · Failed · Waiting on
 *     someone), FF-36 WHY, FF-33's refusal reason;
 *   - reads: RW-17 *Why not?* (the utility's own list, read from data and
 *     never counted in code, R82), RW-18, RW-21 *What did you find?*.
 *
 * The chosen option takes the selected fill, a heavier border and a filled,
 * ticked circle; `tone="danger"` draws it in the danger tone (RW-21's
 * *Leak*). Each option is a `radio` at least 56pt tall (the touch standard's
 * primary; B14 rule 45) and the group is a `radiogroup` with a name, so a
 * screen reader hears "Outcome, Partly done, selected".
 *
 * The two waves spelled the choice differently, so both spellings are taken:
 * `value`/`onChange` (closing) or `selected`/`onSelect` (reads).
 */
import { Pressable, View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';
import { PRESSED_OPACITY } from './Button';

export interface RadioOption {
  id: string;
  label: string;
}

interface Common {
  /** The group's accessible name ("Outcome"). */
  label: string;
  options: readonly RadioOption[];
  /** `danger` draws the chosen row in the danger tone (RW-21's *Leak*). */
  tone?: 'default' | 'danger';
  testID?: string;
}

export type RadioListProps = Common &
  (
    | { value: string | null; onChange: (id: string) => void; selected?: undefined; onSelect?: undefined }
    | { selected: string | null; onSelect: (id: string) => void; value?: undefined; onChange?: undefined }
  );

export function RadioList(props: RadioListProps) {
  const theme = useTheme();
  const c = theme.colors;
  const tone = props.tone ?? 'default';
  const chosen = props.onSelect ? props.selected : props.value;
  const choose = (id: string) => (props.onSelect ? props.onSelect(id) : props.onChange(id));
  const mark = tone === 'danger' ? c.statusInk.danger : c.text;
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={props.label} testID={props.testID} style={{ gap: theme.space[2] }}>
      {props.options.map((o) => {
        const on = o.id === chosen;
        return (
          <Pressable
            key={o.id}
            accessibilityRole="radio"
            accessibilityLabel={o.label}
            accessibilityState={{ checked: on, selected: on }}
            onPress={() => choose(o.id)}
            testID={props.testID ? `${props.testID}-${o.id}` : undefined}
            style={({ pressed }) => ({
              minHeight: theme.touch.primary,
              flexDirection: 'row',
              alignItems: 'center',
              gap: theme.space[3],
              paddingHorizontal: theme.space[4],
              borderRadius: theme.radius.md,
              borderWidth: on ? theme.borderWidth.emphasis : theme.borderWidth.control,
              borderColor: on ? mark : c.controlBorder,
              backgroundColor: on ? (tone === 'danger' ? c.status.danger.bg : c.surface) : c.card,
              opacity: pressed ? PRESSED_OPACITY : 1,
            })}
          >
            <View
              accessible={false}
              style={{
                width: theme.space[6],
                height: theme.space[6],
                borderRadius: theme.space[3],
                borderWidth: theme.borderWidth.emphasis,
                borderColor: on ? mark : c.controlBorder,
                backgroundColor: on ? mark : c.card,
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {on ? (
                <AppText variant="micro" weight="heavy" style={{ color: c.card }} accessibilityRole="none">
                  ✓
                </AppText>
              ) : null}
            </View>
            <AppText variant="body" weight={on ? 'heavy' : 'regular'} accessibilityRole="none" style={on && tone === 'danger' ? { color: mark } : undefined}>
              {o.label}
            </AppText>
          </Pressable>
        );
      })}
    </View>
  );
}
