/**
 * One of FF-63's two tiles: *Jobs* and *Reads*. A titled card with *Open →*,
 * three figures, a rule, and what comes NEXT (a kicker, a bold line, a muted
 * line). The Jobs tile is drawn with the heavier border — it is the one the
 * day starts from.
 *
 * R120: what is LEFT and what is NEXT, never how fast anybody is going — the
 * tile takes counts and an address and has nowhere to put a rate.
 */
import type { ReactNode } from 'react';
import { View } from 'react-native';

import { AppText, Button, Figure, Glyph, Kicker } from '../../components';
import type { FigureProps, GlyphName } from '../../components';
import { useTheme } from '../../theme';

export interface HomeTileProps {
  title: string;
  glyph: GlyphName;
  openLabel: string;
  onOpen: () => void;
  openTestID: string;
  figures: ReadonlyArray<Pick<FigureProps, 'value' | 'label' | 'tone' | 'testID'>>;
  nextKicker: string;
  nextLine: string | null;
  nextDetail: string | null;
  /** Shown in place of the next line when there is nothing next. */
  nothingNext: string;
  emphasis?: boolean;
  children?: ReactNode;
  testID?: string;
}

export function HomeTile(props: HomeTileProps) {
  const theme = useTheme();
  const c = theme.colors;
  return (
    <View
      testID={props.testID}
      style={{
        backgroundColor: c.card,
        borderColor: props.emphasis ? c.text : c.border,
        borderWidth: props.emphasis ? theme.borderWidth.emphasis : theme.borderWidth.card,
        borderRadius: theme.radius.lg,
        padding: theme.space[4],
        gap: theme.space[3],
      }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
        <Glyph name={props.glyph} colour={c.brand} />
        <AppText variant="section" style={{ flexGrow: 1 }}>
          {props.title}
        </AppText>
        <Button size="sm" onPress={props.onOpen} testID={props.openTestID} accessibilityLabel={`${props.openLabel} ${props.title}`}>
          {props.openLabel}
        </Button>
      </View>
      <View style={{ flexDirection: 'row', gap: theme.space[6] }}>
        {props.figures.map((f) => (
          <Figure key={f.label} value={f.value} label={f.label} tone={f.tone} testID={f.testID} />
        ))}
      </View>
      <View style={{ borderTopWidth: theme.borderWidth.divider, borderTopColor: c.divider, paddingTop: theme.space[3] }}>
        <Kicker>{props.nextKicker}</Kicker>
        {props.nextLine ? (
          <>
            <AppText variant="body" weight="heavy">
              {props.nextLine}
            </AppText>
            {props.nextDetail ? (
              <AppText variant="label" tone="muted">
                {props.nextDetail}
              </AppText>
            ) : null}
          </>
        ) : (
          <AppText variant="body" tone="muted">
            {props.nothingNext}
          </AppText>
        )}
      </View>
      {props.children}
    </View>
  );
}
