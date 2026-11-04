/**
 * The six-character code box on FF-56 (*K 7 M 2 • •*): one wide box, the
 * characters spread out in the heading face, a dot for each one still to
 * come. Under it the kit's `Field` anatomy (label → box → help) is kept, so
 * it reads like every other field (B14 rule 39).
 *
 * The code is read off an email or a phone call, so it is upper-cased as it
 * is typed and spaces or dashes are dropped (`security/activation.ts`
 * `normaliseActivationCode`). It is the one thing on these screens that must
 * be typed — R38's taps cannot carry a secret the office made.
 */
import { TextInput, View } from 'react-native';

import { AppText } from '../../components';
import { textStyle } from '../../components/AppText';
import { ACTIVATION_CODE_LENGTH, normaliseActivationCode } from '../../security/activation';
import { useTheme } from '../../theme';

export function CodeField(props: { label: string; value: string; onChange: (code: string) => void; error?: string | null; testID?: string }) {
  const theme = useTheme();
  const c = theme.colors;
  const code = normaliseActivationCode(props.value).slice(0, ACTIVATION_CODE_LENGTH);
  const shown = (code + '•'.repeat(ACTIVATION_CODE_LENGTH - code.length)).split('').join(' ');
  return (
    <View testID={props.testID}>
      <AppText variant="micro" weight="heavy" tone="muted" style={{ marginBottom: theme.field.labelToInput, textTransform: 'uppercase' }}>
        {props.label}
      </AppText>
      <View
        style={{
          minHeight: theme.touch.primary,
          justifyContent: 'center',
          borderWidth: theme.borderWidth.emphasis,
          borderColor: props.error ? c.status.danger.rule : c.text,
          borderRadius: theme.radius.md,
          backgroundColor: c.card,
        }}
      >
        <AppText
          variant="title"
          accessible={false}
          importantForAccessibility="no"
          style={{ textAlign: 'center', letterSpacing: theme.space[1] }}
        >
          {shown}
        </AppText>
        <TextInput
          accessibilityLabel={props.label}
          accessibilityHint={props.error ?? undefined}
          value={code}
          onChangeText={(text) => props.onChange(normaliseActivationCode(text).slice(0, ACTIVATION_CODE_LENGTH))}
          autoCapitalize="characters"
          autoCorrect={false}
          textContentType="oneTimeCode"
          maxLength={ACTIVATION_CODE_LENGTH + 2}
          caretHidden
          testID={props.testID ? `${props.testID}-input` : undefined}
          style={[
            textStyle(theme, 'title'),
            { position: 'absolute', top: 0, bottom: 0, left: 0, right: 0, opacity: 0 },
          ]}
        />
      </View>
      {props.error ? (
        <AppText variant="label" tone="danger" accessibilityLiveRegion="polite" style={{ marginTop: theme.field.inputToHelp }}>
          {props.error}
        </AppText>
      ) : null}
    </View>
  );
}
