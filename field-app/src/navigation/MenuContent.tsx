/**
 * FF-09, the menu — the phone's slide-over drawer and the tablet's permanent
 * 220px sidebar are this one component (FF-09 T: *"What it replaces: FF-09,
 * the phone's slide-over menu"*). Brought to the boards in T-15
 * (`wireframes/phone/FF-09-menu.png`, `tablet/FF-09-T-the-sidebar.png`).
 *
 * Top: the initials disc, who is signed in, and the availability chip
 * (*Available*, which opens FF-45). Then the groups WORK · READS · ME, each a
 * brand-coloured kicker over rows with an icon and, where the handset can
 * count it, a figure on the right (*Today 11*, *My routes 15 left*). The
 * screen you are on is marked with the brand rule down its left edge and a
 * tinted row (FF-09 T: *"the screen you are on is marked"*). Foot: VERSION
 * and the version, always visible (R40), and on the phone *Switch
 * technician* and *Sign out* side by side.
 *
 * THE FIGURES ARE COUNTED, never stored, and only where the handset holds the
 * rows: Today (open jobs today) and My routes (meters left) from the day's
 * store when one is open (`FieldData`). *Completed 4* and the red *Alerts 2*
 * are the Completed and Alerts waves' counts and are not drawn until those
 * exist — a missing count is no count, never a zero.
 *
 * The board's sub-line under the name (*Water II · Silver Creek*) is the
 * technician's grade and utility, which the session does not carry; it is
 * left out rather than made up.
 */
import { type DrawerContentComponentProps } from '@react-navigation/drawer';
import { CommonActions, DrawerActions } from '@react-navigation/native';
import { useTranslation } from 'react-i18next';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { PRODUCT_VERSION, versionLabel } from '../release/build';
import { Button } from '../components/Button';
import { Glyph, type GlyphName } from '../components/Glyph';
import { textStyle } from '../components/AppText';
import { dayBounds, dayCounts, readCounts } from '../db/queries/day';
import { useFieldData, useScoped } from '../screens/theDay/fieldData';
import { useOptionalSession } from '../session/SessionProvider';
import { useTheme } from '../theme';
import { MENU_FOOT, type MenuItem, menuFor } from './drawerEntries';
import { routeTo, focusedLeaf } from './routing';
import { type ScreenId } from './screens';
import { useShellStatus } from './ShellStatus';

/** The product version (T-58). The build number is added on screen by `versionLabel`. */
export const APP_VERSION: string = PRODUCT_VERSION;

/** The icon each row carries on the boards. */
const ICON: Partial<Record<ScreenId, GlyphName>> = {
  'FF-63': 'mark',
  'FF-10': 'calendar',
  'FF-35': 'check',
  'FF-13': 'pin',
  'FF-41': 'message',
  'FF-42': 'bell',
  'RW-01': 'pin',
  'RW-08': 'scan',
  'RW-28': 'pending',
  'FF-44': 'person',
  'FF-48': 'message',
  'FF-46': 'pending',
  'FF-47': 'pending',
  'FF-49': 'navigate',
  'FF-50': 'sync',
  'FF-51': 'menu',
};

function initials(name: string): string {
  return name
    .split(/[\s.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

/** The figures the handset can count for the menu, or none. */
function useMenuCounts(): Partial<Record<ScreenId, string>> {
  const { t } = useTranslation();
  const { now } = useFieldData();
  const s = useScoped();
  const status = useShellStatus();
  // FF-09 T draws *Sync 12*: on a tablet this row is where the sync number
  // lives, the status strip not being drawn there (T-28). Unknown → no figure.
  const sync: Partial<Record<ScreenId, string>> = status.syncPending == null ? {} : { 'FF-50': String(status.syncPending) };
  if (!s) return sync;
  const jobs = dayCounts(s, { ...dayBounds(now(), 0), today: true });
  const reads = readCounts(s);
  return {
    ...sync,
    'FF-10': String(jobs.left),
    'RW-01': t('field.menu.left', { count: reads.left }),
  };
}

export function MenuContent({ navigation, state, tablet }: DrawerContentComponentProps & { tablet: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const c = theme.colors;
  const session = useOptionalSession();
  const status = useShellStatus();
  const counts = useMenuCounts();
  const current = focusedLeaf(state);
  const name = session?.snapshot.active?.displayName ?? '';
  const available = status.availability === 'available';

  function open(id: ScreenId): void {
    const target = routeTo(id);
    navigation.dispatch(CommonActions.navigate(target.name, target.params));
    // FF-53 Sign out is a sheet OVER the menu: its *Stay signed in* is the
    // board's door back to FF-09, so the menu stays open beneath it and
    // dismissing the sheet lands on the menu (tests/screens/me/doors.test).
    if (!tablet && id !== 'FF-53') navigation.dispatch(DrawerActions.closeDrawer());
  }

  function row(item: MenuItem) {
    const active = current === item.id;
    const icon = ICON[item.id];
    const count = counts[item.id];
    return (
      <Pressable
        key={item.id}
        accessibilityRole="button"
        accessibilityLabel={[t(item.labelKey), count].filter(Boolean).join(', ')}
        accessibilityState={{ selected: active }}
        onPress={() => open(item.id)}
        testID={`menu-${item.id}`}
        style={{
          minHeight: theme.touch.control,
          flexDirection: 'row',
          alignItems: 'center',
          gap: theme.space[3],
          paddingHorizontal: theme.space[4],
          borderLeftWidth: theme.space[1],
          borderLeftColor: active ? c.brand : 'transparent',
          backgroundColor: active ? c.surface : 'transparent',
        }}
      >
        {icon ? <Glyph name={icon} colour={c.text} size={theme.type.section} /> : null}
        <Text style={[textStyle(theme, 'body', active ? 'heavy' : 'regular'), { flexGrow: 1 }]}>{t(item.labelKey)}</Text>
        {count ? (
          <Text style={textStyle(theme, 'label', 'regular', 'muted')} testID={`menu-${item.id}-count`}>
            {count}
          </Text>
        ) : null}
      </Pressable>
    );
  }

  return (
    <View style={{ flex: 1, backgroundColor: c.card }} testID={tablet ? 'menu-sidebar' : 'menu-drawer'}>
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: theme.space[3],
          padding: theme.space[4],
          backgroundColor: c.surface,
          borderBottomWidth: theme.borderWidth.divider,
          borderBottomColor: c.border,
        }}
      >
        <View
          accessible={false}
          style={{
            width: theme.touch.control,
            height: theme.touch.control,
            borderRadius: theme.touch.control / 2,
            backgroundColor: c.border,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Text style={textStyle(theme, 'body', 'heavy')}>{initials(name)}</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={textStyle(theme, 'section', 'heavy')} numberOfLines={1}>
            {name}
          </Text>
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t(status.availability ? `field.availability.${status.availability}` : 'field.availability.unknown')}
          onPress={() => open('FF-45')}
          testID="menu-availability"
          style={{
            minHeight: theme.touch.control,
            paddingHorizontal: theme.space[3],
            flexDirection: 'row',
            alignItems: 'center',
            gap: theme.space[2],
            borderRadius: theme.radius.md,
            borderWidth: theme.borderWidth.control,
            borderColor: available ? c.status.success.rule : c.controlBorder,
            backgroundColor: available ? c.status.success.bg : c.card,
          }}
        >
          <Text style={textStyle(theme, 'label', 'semibold')}>
            {t(status.availability ? `field.availability.${status.availability}` : 'field.availability.unknown')}
          </Text>
        </Pressable>
      </View>
      <ScrollView keyboardShouldPersistTaps="handled" style={{ flex: 1 }}>
        {menuFor(tablet).map((group) => (
          <View
            key={group.labelKey}
            style={{ paddingTop: theme.space[4], paddingBottom: theme.space[2], borderBottomWidth: theme.borderWidth.divider, borderBottomColor: c.border }}
          >
            <Text
              accessibilityRole="header"
              style={[
                textStyle(theme, 'micro', 'heavy', 'brand'),
                {
                  paddingHorizontal: theme.space[4],
                  paddingBottom: theme.space[2],
                  textTransform: 'uppercase',
                  letterSpacing: theme.tracking.kicker * theme.type.micro,
                },
              ]}
            >
              {t(group.labelKey)}
            </Text>
            {group.items.map(row)}
          </View>
        ))}
      </ScrollView>
      <View style={{ borderTopWidth: theme.borderWidth.divider, borderTopColor: c.border, padding: theme.space[4], gap: theme.space[3] }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
          <Text
            style={[
              textStyle(theme, 'micro', 'heavy', 'muted'),
              { textTransform: 'uppercase', letterSpacing: theme.tracking.kicker * theme.type.micro },
            ]}
          >
            {t('field.nav.version')}
          </Text>
          <Text style={textStyle(theme, 'label', 'semibold')} testID="menu-version">
            {versionLabel(t)}
          </Text>
        </View>
        <View style={{ flexDirection: 'row', gap: theme.touch.clear }}>
          {MENU_FOOT.map((item) => (
            <Button
              key={item.id}
              size="sm"
              grow={item.id === 'SWITCH'}
              onPress={() => open(item.id)}
              testID={`menu-${item.id}`}
              accessibilityLabel={t(item.labelKey)}
            >
              {t(item.labelKey)}
            </Button>
          ))}
        </View>
      </View>
    </View>
  );
}
