/**
 * The detail half of a T-29 board (B14 rule 43). Every one of the 25 boards
 * draws the same shape beside its list: a card headed by the picked thing's
 * name, the line under it, its facts label-beside-value — and under the card
 * the board's acts, side by side, the primary one last (FF-11 T *On the map ·
 * Claim it*, RW-06 T *Can't read here · Read Unit A*).
 *
 *   `DetailPane` — the scrolling pane, its children, and the acts row.
 *   `DetailCard` — the card: title, line, facts, and anything else it holds.
 *
 * ⚠ The boards also draw a tinted paragraph under the card saying WHY the
 * screen works the way it does. That is rationale, and B14 rule 33 puts it at
 * zero words on screen; it lives in each layout's docstring instead.
 */
import { type ReactNode } from 'react';
import { ScrollView, View } from 'react-native';

import { AppText, Card, EmptyState } from '../components';
import { type CardTone } from '../components/Card';
import { type Fact, FactLines } from '../components/Facts';
import { useTheme } from '../theme';

export function DetailPane(props: { children?: ReactNode; acts?: ReactNode; testID?: string }) {
  const theme = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }} testID={props.testID}>
      <ScrollView keyboardShouldPersistTaps="handled" style={{ flex: 1 }} contentContainerStyle={{ padding: theme.space[4], gap: theme.space[3] }}>
        {props.children}
        {props.acts ? <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: theme.space[3] }}>{props.acts}</View> : null}
      </ScrollView>
    </View>
  );
}

export function DetailCard(props: {
  title: string;
  line?: string | null;
  facts?: readonly Fact[];
  tone?: CardTone;
  trailing?: ReactNode;
  children?: ReactNode;
  testID?: string;
}) {
  const theme = useTheme();
  return (
    <Card tone={props.tone} testID={props.testID}>
      <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: theme.space[3] }}>
        <View style={{ flex: 1 }}>
          <AppText variant="title" accessibilityRole="header">
            {props.title}
          </AppText>
          {props.line ? (
            <AppText variant="label" tone="muted">
              {props.line}
            </AppText>
          ) : null}
        </View>
        {props.trailing}
      </View>
      {props.facts && props.facts.length > 0 ? <FactLines facts={props.facts} /> : null}
      {props.children}
    </Card>
  );
}

/** Nothing picked, or nothing to pick: the pane says so rather than standing empty. */
export function DetailNone(props: { title: string; helper: string; testID?: string }) {
  return (
    <DetailPane testID={props.testID}>
      <EmptyState title={props.title} helper={props.helper} />
    </DetailPane>
  );
}
