/**
 * CheckRow — one component, two shapes, because two waves each drew a "row
 * with a mark in front of the words" and the kit holds ONE (B14 rule 43; merged
 * in the integration lane). The props decide the shape: pass `checked` and it
 * is a row the technician TAPS; pass `state` and it is a line that REPORTS.
 *
 * A — the tap row (`checked`, optional `kind`, `onPress`, `disabled`): a whole
 * card that is one tick or one choice: FF-16's four safety rows (a CHECKBOX —
 * each is its own fact) and FF-58's reasons (a RADIO — one of six). R38: a
 * technician taps, never types — the row is the target, not a small box inside
 * it, and it is at least 56pt tall (the boards' 58, built to the touch
 * standard's primary). A ticked safety row stays ticked: ticking is an act
 * captured to the outbox, so the screen passes `disabled` once it is done.
 *
 * B — the progress line (`state`, `stateLabel`, optional `value`): one line of
 * a list of things being done: a mark, the words, and how far along it is on
 * the right. FF-08 draws it five times (*Jobs and checklists · 8 of 11*) and
 * FF-57 three times (*At least ten characters* ticked).
 *
 *   done     — a tick in the success ink
 *   active   — the under-way mark in the warning ink, value in the same
 *   waiting  — a hollow ring, muted
 *   refused  — a cross in the danger ink (a check that failed)
 *
 * The state is in the accessible name as a word as well as a colour (WCAG
 * 1.4.1): "Jobs and checklists, under way, 8 of 11".
 */
import { Pressable, Text, View } from 'react-native';

import { useTheme } from '../theme';
import { textStyle } from './AppText';
import { PRESSED_OPACITY } from './Button';
import { Glyph } from './Glyph';
import type { GlyphName } from './Glyph';

export type CheckState = 'done' | 'active' | 'waiting' | 'refused';

/** Shape A — a row the technician taps. */
export interface CheckRowTapProps {
  label: string;
  checked: boolean;
  onPress?: () => void;
  kind?: 'checkbox' | 'radio';
  disabled?: boolean;
  testID?: string;
  state?: undefined;
}

/** Shape B — a line that reports how far something has got. */
export interface CheckRowProgressProps {
  state: CheckState;
  label: string;
  value?: string;
  /** The state as a word, pre-translated ("done", "under way"…). */
  stateLabel: string;
  testID?: string;
  checked?: undefined;
}

export type CheckRowProps = CheckRowTapProps | CheckRowProgressProps;

const MARK: Record<CheckState, GlyphName> = {
  done: 'check',
  active: 'pending',
  waiting: 'waiting',
  refused: 'close',
};

export function CheckRow(props: CheckRowProps) {
  if (props.state !== undefined) return <ProgressLine {...props} />;
  return <TapRow {...props} />;
}

function TapRow({ label, checked, onPress, kind = 'checkbox', disabled = false, testID }: CheckRowTapProps) {
  const theme = useTheme();
  const c = theme.colors;
  const mark = theme.touch.control / 2 + theme.space[1];
  const selectedBorder = kind === 'radio' && checked;
  return (
    <Pressable
      accessibilityRole={kind}
      accessibilityLabel={label}
      accessibilityState={{ checked, disabled }}
      disabled={disabled}
      onPress={onPress}
      testID={testID}
      style={({ pressed }) => ({
        minHeight: theme.touch.primary,
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[3],
        paddingHorizontal: theme.space[4],
        backgroundColor: c.card,
        borderWidth: selectedBorder ? theme.borderWidth.emphasis : theme.borderWidth.card,
        borderColor: selectedBorder ? c.text : c.border,
        opacity: pressed ? PRESSED_OPACITY : 1,
      })}
    >
      <View
        accessible={false}
        style={{
          width: mark,
          height: mark,
          alignItems: 'center',
          justifyContent: 'center',
          borderWidth: checked ? 0 : theme.borderWidth.emphasis,
          borderColor: c.controlBorder,
          backgroundColor: checked ? (kind === 'radio' ? c.text : c.status.success.rule) : c.card,
        }}
      >
        {checked ? <Glyph name="check" colour={c.card} /> : null}
      </View>
      <Text style={[textStyle(theme, 'body', 'semibold'), { flexShrink: 1 }]}>{label}</Text>
    </Pressable>
  );
}

function ProgressLine({ state, label, value, stateLabel, testID }: CheckRowProgressProps) {
  const theme = useTheme();
  const c = theme.colors;
  const sun = theme.name === 'sunlight';
  const ink =
    state === 'done'
      ? c.statusInk.success
      : state === 'active'
        ? c.statusInk.warning
        : state === 'refused'
          ? c.statusInk.danger
          : c.textMuted;
  const markInk = sun ? c.text : ink;
  return (
    <View
      accessible
      accessibilityRole="text"
      accessibilityLabel={[label, stateLabel, value].filter(Boolean).join(', ')}
      testID={testID}
      style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3], minHeight: theme.touch.control / 2 + theme.space[3] }}
    >
      <Glyph name={MARK[state]} colour={markInk} size={theme.type.section} />
      <Text style={[textStyle(theme, 'body', 'regular', state === 'waiting' ? 'muted' : 'default'), { flexGrow: 1, flexShrink: 1 }]}>
        {label}
      </Text>
      {value ? (
        <Text style={[textStyle(theme, 'label', state === 'active' ? 'heavy' : 'regular', 'muted'), state === 'active' ? { color: markInk } : null]}>
          {value}
        </Text>
      ) : null}
    </View>
  );
}
