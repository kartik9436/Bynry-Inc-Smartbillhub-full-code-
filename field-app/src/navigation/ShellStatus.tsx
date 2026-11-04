/**
 * Always on screen (AD-12): the sync NUMBER with its connection icon, and the
 * availability chip.
 *
 * R32: *"The sync indicator is a number, not a word — how far the phone and
 * the server are in step, in both directions. The icon carries the
 * connection; the number carries the sync."* R103: *"Sync is one tap from the
 * day"* — so the number opens FF-50 Sync, and the chip opens FF-45
 * Availability.
 *
 * The figures come from `ShellStatusContext`, which the sync engine (T-10)
 * and the availability screen (T-24) will feed. Until they do, the strip shows
 * that it does not know — never a made-up zero, because "0" reads as "all
 * sent" and would be a lie on a handset holding a day of work.
 */
import { CommonActions, type NavigationProp, type ParamListBase, useNavigation } from '@react-navigation/native';
import { createContext, type ReactNode, useContext } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, Text, View } from 'react-native';

import { textStyle } from '../components/AppText';
import { useTheme } from '../theme';
import { routeTo } from './routing';

export type Connection = 'online' | 'offline' | 'unknown';
/** `unavailable` is the OFFICE's word, read back from the server (FB-033) —
 *  the technician cannot choose it (`AVAILABILITIES` holds the three they can). */
export type Availability = 'available' | 'onBreak' | 'offDuty' | 'unavailable';

export interface ShellStatusValue {
  /** Items not yet in step with the server, both directions; `null` = not known yet. */
  syncPending: number | null;
  connection: Connection;
  availability: Availability | null;
}

export const UNKNOWN_STATUS: ShellStatusValue = { syncPending: null, connection: 'unknown', availability: null };

const ShellStatusContext = createContext<ShellStatusValue>(UNKNOWN_STATUS);

export function ShellStatusProvider({ value, children }: { value: ShellStatusValue; children: ReactNode }) {
  return <ShellStatusContext.Provider value={value}>{children}</ShellStatusContext.Provider>;
}

export function useShellStatus(): ShellStatusValue {
  return useContext(ShellStatusContext);
}

function go(navigation: NavigationProp<ParamListBase>, id: 'FF-50' | 'FF-45'): void {
  const target = routeTo(id);
  navigation.dispatch(CommonActions.navigate(target.name, target.params));
}

export function ShellStatus() {
  const { t } = useTranslation();
  const theme = useTheme();
  const c = theme.colors;
  const chip = {
    minHeight: theme.touch.control,
    minWidth: theme.touch.control,
    paddingHorizontal: theme.space[3],
    flexDirection: 'row' as const,
    alignItems: 'center' as const,
    gap: theme.space[2],
    borderRadius: theme.touch.control / 2,
    borderWidth: theme.borderWidth.control,
    borderColor: c.controlBorder,
    backgroundColor: c.card,
  };
  const navigation = useNavigation<NavigationProp<ParamListBase>>();
  const status = useShellStatus();

  const connectionLabel = t(`field.status.connection.${status.connection}`);
  const syncLabel =
    status.syncPending == null ? t('field.status.sync.unknown') : t('field.status.sync.a11y', { count: status.syncPending });
  const availabilityLabel = t(status.availability ? `field.availability.${status.availability}` : 'field.availability.unknown');

  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'flex-end',
        gap: theme.space[2],
        paddingHorizontal: theme.space[4],
        paddingVertical: theme.space[1],
        backgroundColor: c.card,
        borderBottomWidth: theme.borderWidth.divider,
        borderBottomColor: c.border,
      }}
      testID="shell-status"
    >
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${connectionLabel}. ${syncLabel}`}
        onPress={() => go(navigation, 'FF-50')}
        style={chip}
        testID="shell-status-sync"
      >
        <View
          style={{
            width: theme.space[2],
            height: theme.space[2],
            borderRadius: theme.space[1],
            backgroundColor: status.connection === 'online' ? c.status.success.rule : c.status.neutral.rule,
          }}
          testID={`shell-status-connection-${status.connection}`}
        />
        <Text style={[textStyle(theme, 'body', 'heavy'), { fontVariant: ['tabular-nums'] }]}>
          {status.syncPending == null ? '–' : String(status.syncPending)}
        </Text>
      </Pressable>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={availabilityLabel}
        onPress={() => go(navigation, 'FF-45')}
        style={[
          chip,
          status.availability === 'available'
            ? { backgroundColor: c.status.success.bg, borderColor: c.status.success.rule }
            : null,
        ]}
        testID="shell-status-availability"
      >
        <Text style={textStyle(theme, 'label', 'semibold')}>{availabilityLabel}</Text>
      </Pressable>
    </View>
  );
}
