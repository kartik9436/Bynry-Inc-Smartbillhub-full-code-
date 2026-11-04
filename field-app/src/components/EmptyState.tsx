/**
 * EmptyState — the whole list region when there is nothing in it. The web
 * kit's equivalent is `EmptyList` (StateFrame.tsx) and this keeps its props:
 * `title`, `helper`, and an OPTIONAL `ctaLabel` + `onCta`.
 *
 * The web learned two things the hard way and both are kept:
 *   - no `ctaLabel` draws NO button (DEF-MET-4764: a required callback once
 *     produced a live button that did nothing);
 *   - a CTA the user cannot act on is drawn DISABLED WITH ITS REASON VISIBLE
 *     (`ctaReason`), never as a tooltip — a phone has no hover at all
 *     (DEF-SHL-4043).
 */
import { View } from 'react-native';

import { useTheme } from '../theme';
import { AppText } from './AppText';
import { Button } from './Button';

export interface EmptyStateProps {
  title: string;
  helper: string;
  ctaLabel?: string;
  onCta?: () => void;
  /** When set, the CTA is disabled and this sentence is shown under it. */
  ctaReason?: string | null;
  testID?: string;
}

export function EmptyState(props: EmptyStateProps) {
  const theme = useTheme();
  const blocked = props.ctaReason != null && props.ctaReason !== '';
  return (
    <View
      testID={props.testID}
      style={{
        alignItems: 'center',
        justifyContent: 'center',
        paddingHorizontal: theme.space[6],
        paddingVertical: theme.space[8],
        gap: theme.space[3],
      }}
    >
      <AppText variant="section" style={{ textAlign: 'center' }}>
        {props.title}
      </AppText>
      <AppText variant="body" tone="muted" style={{ textAlign: 'center' }}>
        {props.helper}
      </AppText>
      {props.ctaLabel ? (
        <View style={{ alignSelf: 'stretch', marginTop: theme.space[3], gap: theme.space[2] }}>
          <Button variant="primary" onPress={props.onCta} disabled={blocked}>
            {props.ctaLabel}
          </Button>
          {blocked ? (
            <AppText variant="label" tone="muted" style={{ textAlign: 'center' }}>
              {props.ctaReason ?? ''}
            </AppText>
          ) : null}
        </View>
      ) : null}
    </View>
  );
}
