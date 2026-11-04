/**
 * Blocks that repeat across the reading screens and nowhere else (B14 rule
 * 43: a piece of UI is a component). The general ones live in the kit
 * (`src/components`); these know what a meter, a stop and a figure are.
 * Like the kit, they name no colour and no pixel — the theme does.
 */
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, View } from 'react-native';

import { AppText, Kicker, StatusChip } from '../../components';
import { DISABLED_OPACITY, PRESSED_OPACITY } from '../../components/Button';
import type { StatusTone } from '../../theme';
import { useTheme } from '../../theme';
import type * as walkQ from '../../db/queries/readsWalk';
import { group, type RangeVerdict } from './figures';
import { meterName, unitLabel } from './records';

/** A pressable card — a route on RW-01, a stop on RW-05, a meter on RW-06. */
export function PressCard(props: {
  children: ReactNode;
  onPress?: () => void;
  label: string;
  /** `strong` draws the next one (RW-05's nearest, RW-06's first unread). */
  emphasis?: 'strong' | 'warning' | 'info' | 'none';
  testID?: string;
}) {
  const theme = useTheme();
  const c = theme.colors;
  const border =
    props.emphasis === 'strong'
      ? c.text
      : props.emphasis === 'warning'
        ? c.status.warning.rule
        : props.emphasis === 'info'
          ? c.status.info.rule
          : c.border;
  const width = props.emphasis && props.emphasis !== 'none' ? theme.borderWidth.emphasis : theme.borderWidth.card;
  const style = {
    minHeight: theme.touch.control,
    backgroundColor: c.card,
    borderColor: border,
    borderWidth: width,
    borderRadius: theme.radius.lg,
    padding: theme.space[4],
    gap: theme.space[2],
  };
  if (!props.onPress) {
    return (
      <View style={style} testID={props.testID} accessibilityLabel={props.label}>
        {props.children}
      </View>
    );
  }
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={props.label}
      onPress={props.onPress}
      testID={props.testID}
      style={({ pressed }) => [style, { opacity: pressed ? PRESSED_OPACITY : 1 }]}
    >
      {props.children}
    </Pressable>
  );
}

/** Two things on one line, the second pushed right. */
export function Spread(props: { children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: theme.space[3] }}>
      {props.children}
    </View>
  );
}

/** A row of controls under the top bar (RW-05's map, RW-09's Dials and scan). */
export function Toolbar(props: { children: ReactNode }) {
  const theme = useTheme();
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: theme.touch.clear }}>
      {props.children}
    </View>
  );
}

/**
 * Who and what a reading is about — the customer's name, the unit label and
 * the account number beside the meter (R79, PO ruled: never removed).
 */
export function MeterLine({ m, trailing }: { m: walkQ.MeterRead; trailing?: ReactNode }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const unit = unitLabel(m);
  const who = [unit, m.customer_name].filter(Boolean).join(' · ');
  return (
    <View
      testID="meter-line"
      style={{
        backgroundColor: theme.colors.card,
        borderColor: theme.colors.border,
        borderWidth: theme.borderWidth.card,
        padding: theme.space[3],
        gap: theme.space[1],
      }}
    >
      <Spread>
        <AppText variant="body" weight="heavy">
          {who || t('field.reads.common.noCustomer')}
        </AppText>
        <AppText variant="label" tone="muted">
          {m.account_number ?? ''}
        </AppText>
      </Spread>
      <Spread>
        <AppText variant="label" tone="muted">
          {m.badge ? t('field.reads.common.meterBadge', { meter: meterName(m), badge: m.badge }) : meterName(m)}
        </AppText>
        <AppText variant="label" tone="muted">
          {m.address_line ?? ''}
        </AppText>
      </Spread>
      {trailing}
    </View>
  );
}

/** RW-09's strip: last month's reading and the expected range, both (R78). */
export function RangeStrip({ m }: { m: walkQ.MeterRead }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const range =
    m.expected_min && m.expected_max
      ? `${group(m.expected_min)}–${group(m.expected_max)}`
      : t('field.reads.common.none');
  return (
    <View
      testID="range-strip"
      style={{ flexDirection: 'row', backgroundColor: theme.colors.surface, padding: theme.space[3], gap: theme.space[6] }}
    >
      <View>
        <Kicker>{t('field.reads.common.lastMonth')}</Kicker>
        <AppText variant="section" weight="heavy" testID="previous-value">
          {m.previous_value ? group(m.previous_value) : t('field.reads.common.none')}
        </AppText>
      </View>
      <View>
        <Kicker>{t('field.reads.common.expected')}</Kicker>
        <AppText variant="section" weight="heavy" testID="expected-range">
          {range}
        </AppText>
      </View>
    </View>
  );
}

/** A figure and its unit, the unit always beside it (hard rule 3). Amber when warned. */
export function Figure({ value, unit, warn, testID }: { value: string; unit: string; warn?: boolean; testID?: string }) {
  const theme = useTheme();
  const colour = warn ? theme.colors.statusInk.warning : theme.colors.text;
  return (
    <View
      style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'center', gap: theme.space[2] }}
      accessible
      accessibilityRole="text"
      accessibilityLabel={`${value || '—'} ${unit}`}
      testID={testID}
    >
      <AppText variant="title" weight="heavy" style={{ color: colour }} testID={testID ? `${testID}-value` : undefined}>
        {value ? group(value) : '—'}
      </AppText>
      <AppText variant="body" tone="muted" weight="semibold">
        {unit}
      </AppText>
    </View>
  );
}

/** The reader's status, in the reader's words (R96 — never the office's verdict). */
export function ReaderStatusChip({ status }: { status: walkQ.MeterRead['reader_status'] }) {
  const { t } = useTranslation();
  if (!status) return <StatusChip tone="neutral">{t('field.reads.status.toDo')}</StatusChip>;
  const tone: StatusTone = status === 'read' ? 'success' : 'warning';
  const key =
    status === 'read'
      ? 'field.reads.status.read'
      : status === 'could_not_read'
        ? 'field.reads.status.couldNot'
        : 'field.reads.status.withProblem';
  return (
    <StatusChip tone={tone} testID="reader-status">
      {t(key)}
    </StatusChip>
  );
}

/** What the handset says about a figure before it is kept (R80, R81). */
export function verdictKey(v: RangeVerdict): string {
  if (v === 'high') return 'field.reads.verdict.high';
  if (v === 'low') return 'field.reads.verdict.low';
  if (v === 'below_previous') return 'field.reads.verdict.belowPrevious';
  if (v === 'inside') return 'field.reads.verdict.inside';
  return 'field.reads.verdict.unknown';
}

/** A big bordered box with a camera in it — *Photograph the plate — required*. */
export function PhotoAsk(props: { label: string; required: boolean; taken: number; onPress: () => void; disabled?: boolean; testID?: string }) {
  const theme = useTheme();
  const c = theme.colors;
  const tone = props.required && props.taken === 0 ? c.dangerAction : c.controlBorder;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={props.label}
      accessibilityState={{ disabled: props.disabled === true }}
      disabled={props.disabled}
      onPress={props.onPress}
      testID={props.testID}
      style={({ pressed }) => ({
        minHeight: theme.touch.primary,
        alignItems: 'center',
        justifyContent: 'center',
        borderWidth: theme.borderWidth.emphasis,
        borderStyle: props.required ? 'solid' : 'dashed',
        borderColor: tone,
        borderRadius: theme.radius.md,
        backgroundColor: c.card,
        padding: theme.space[3],
        opacity: props.disabled ? DISABLED_OPACITY : pressed ? PRESSED_OPACITY : 1,
      })}
    >
      <AppText variant="body" weight="semibold" style={{ color: props.required && props.taken === 0 ? c.dangerAction : c.text }}>
        {props.label}
      </AppText>
    </Pressable>
  );
}
