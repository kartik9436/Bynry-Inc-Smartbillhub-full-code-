/**
 * Field — label → input → help, in that order (B14 rule 39, PO 2026-09-11:
 * *"It starts with the field name. then the input field, and then it should
 * show the helper text below that input field."*), with the ratified anatomy:
 * label → input 5 · input → help 6 · field → field 20. FF-18 (Add a step)
 * draws exactly this: "What did you do?" → the box → "The office reads this".
 *
 * `FieldGroup` spaces adjacent fields by the 20; a screen never adds a margin
 * between two fields itself.
 *
 * `tone` colours the input's border for a reading's verdict on FF-20 (amber
 * outside the expected range, green inside) — WARNED, never blocked (R11/R80),
 * so it changes a colour and never disables anything.
 *
 * R38 (*"A technician taps, never types"*) is the screen's decision, not this
 * component's: prefer `ChoiceChips` or `Stepper` wherever the boards do.
 */
import { Children, Fragment } from 'react';
import type { ReactNode } from 'react';
import { TextInput, View } from 'react-native';
import type { KeyboardTypeOptions } from 'react-native';

import { useTheme } from '../theme';
import { AppText, textStyle } from './AppText';

export type FieldTone = 'default' | 'success' | 'warning' | 'danger';

export interface FieldProps {
  label: string;
  value: string;
  onChangeText?: (text: string) => void;
  /** One line under the input. */
  help?: string;
  /** Shown in place of the help, in the danger ink. */
  error?: string;
  /** A unit written after the input ("gal"). Consumption always carries one
   *  (CLAUDE.md hard rule 3). */
  unit?: string;
  multiline?: boolean;
  placeholder?: string;
  keyboardType?: KeyboardTypeOptions;
  editable?: boolean;
  /** The keyboard's done key (FF-20 commits a reading on it). */
  onSubmitEditing?: () => void;
  tone?: FieldTone;
  /** A password: hidden as it is typed, never auto-corrected or capitalised. */
  secure?: boolean;
  /** The same as `secure` (FF-05, FF-57, the lock cover spell it this way). */
  secureTextEntry?: boolean;
  autoCapitalize?: 'none' | 'sentences' | 'words' | 'characters';
  autoCorrect?: boolean;
  /** The platform's autofill hint ("username", "password", "newPassword", "emailAddress"). */
  textContentType?: 'username' | 'password' | 'newPassword' | 'emailAddress' | 'oneTimeCode';
  maxLength?: number;
  testID?: string;
}

export function Field(props: FieldProps) {
  const theme = useTheme();
  const c = theme.colors;
  const tone = props.error ? 'danger' : (props.tone ?? 'default');
  const borderColour = tone === 'default' ? c.controlBorder : c.status[tone].rule;
  const borderWidth = tone === 'default' ? theme.borderWidth.control : theme.borderWidth.emphasis;
  const under = props.error ?? props.help;
  const secure = props.secure ?? props.secureTextEntry;
  return (
    <View testID={props.testID}>
      <AppText variant="label" weight="semibold" style={{ marginBottom: theme.field.labelToInput }}>
        {props.label}
      </AppText>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
        <TextInput
          accessibilityLabel={props.label}
          accessibilityHint={props.help}
          accessibilityState={{ disabled: props.editable === false }}
          value={props.value}
          onChangeText={props.onChangeText}
          multiline={props.multiline}
          placeholder={props.placeholder}
          placeholderTextColor={c.textMuted}
          keyboardType={props.keyboardType}
          editable={props.editable}
          onSubmitEditing={props.onSubmitEditing}
          returnKeyType={props.onSubmitEditing ? 'done' : undefined}
          secureTextEntry={secure}
          autoCorrect={props.autoCorrect ?? (secure ? false : undefined)}
          autoCapitalize={props.autoCapitalize ?? (secure ? 'none' : undefined)}
          textContentType={props.textContentType}
          maxLength={props.maxLength}
          testID={props.testID ? `${props.testID}-input` : undefined}
          style={[
            textStyle(theme, 'body'),
            {
              flexGrow: 1,
              flexShrink: 1,
              minHeight: props.multiline ? theme.touch.control * 2 : theme.touch.control,
              paddingHorizontal: theme.space[4],
              paddingVertical: theme.space[2],
              borderWidth,
              borderColor: borderColour,
              borderRadius: theme.radius.md,
              backgroundColor: props.editable === false ? c.surface : c.card,
              textAlignVertical: props.multiline ? 'top' : 'center',
            },
          ]}
        />
        {props.unit ? (
          <AppText variant="body" tone="muted" weight="semibold">
            {props.unit}
          </AppText>
        ) : null}
      </View>
      {under ? (
        <AppText
          variant="label"
          tone={props.error ? 'danger' : 'muted'}
          accessibilityLiveRegion={props.error ? 'polite' : undefined}
          style={{ marginTop: theme.field.inputToHelp }}
        >
          {under}
        </AppText>
      ) : null}
    </View>
  );
}

/** Adjacent fields, 20 apart (field → field). */
export function FieldGroup(props: { children: ReactNode }) {
  const theme = useTheme();
  const items = Children.toArray(props.children);
  return (
    <View>
      {items.map((child, i) => (
        <Fragment key={i}>
          {i > 0 ? <View style={{ height: theme.field.fieldToField }} /> : null}
          {child}
        </Fragment>
      ))}
    </View>
  );
}
