/**
 * The navigation tree (T-13; AD-12, AD-13, AD-22; FF-09, FF-09 T, FF-63).
 *
 *   signed out → Root stack of the gate screens (FF-01…FF-06, FF-56, FF-57)
 *   signed in  → Root stack
 *                 ├─ Frame — the drawer: slide-over on a phone, the permanent
 *                 │   220px sidebar on a tablet (chosen by width, `layout.ts`)
 *                 │   └─ Shell — the native stack every screen is PUSHED onto
 *                 │        ├─ Tabs — Home · Jobs · Reads (phone only; on a
 *                 │        │         tablet the sidebar carries all three)
 *                 │        └─ every other FF- / RW- screen
 *                 ├─ FF-07 Permissions, FF-08 First sync — full screen, no frame
 *                 └─ FF-53 Sign out, SWITCH — sheets over the screen
 *
 * The sync number and the availability chip sit above the Shell on every
 * framed screen (AD-12, *"Always on screen"*) — on a phone. On a tablet the
 * permanent sidebar carries both (T-28), so the strip is not drawn there.
 *
 * A LOCKED session keeps the tree mounted and covers it, so unlocking returns
 * the technician to exactly where they were rather than to Home. The cover
 * carries its own unlock form (`screens/gettingIn/LockCover.tsx`).
 *
 * AFTER A SIGN-IN FROM THE GATE the signed-in tree opens on FF-07
 * Permissions, which leads to FF-08 First sync and from there to the day —
 * the design's own doors FF-05 → FF-07 → FF-08 → FF-10. A session that was
 * already open when the app started (restored, so it comes back LOCKED) and
 * a technician switching on an open session both keep the frame: only a
 * sign-in this navigator SAW happen goes through the two. (Before T-15 every
 * sign-in landed on Home.)
 *
 * Every colour, size and face here comes from the theme (`useTheme()`), the
 * same token set the kit reads — `shellStyle.ts`, the stand-in the frame was
 * first built with, is gone.
 */
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createDrawerNavigator } from '@react-navigation/drawer';
import { DrawerActions, type ParamListBase, useNavigation } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, useWindowDimensions, View } from 'react-native';

import { Glyph } from '../components/Glyph';
import { ToastProvider } from '../components/Toast';
import { LockCover } from '../screens/gettingIn/LockCover';
import { useOptionalSession } from '../session/SessionProvider';
// T-27: every screen is mounted inside its tablet frame (a no-op on a phone).
import { FormFactorProvider } from '../tablet/FormFactor';
import { FRAMED_SCREENS } from '../tablet/framedScreens';
import { type Theme, useTheme } from '../theme';
import { isTabletSize, SIDEBAR_WIDTH } from './layout';
import { MenuContent } from './MenuContent';
import { FRAME, SHELL, TABS } from './routing';
import { type ScreenId, screenDef, screensIn, TAB_SCREENS } from './screens';
import { ShellStatus } from './ShellStatus';

const RootStack = createNativeStackNavigator<ParamListBase>();
const ShellStack = createNativeStackNavigator<ParamListBase>();
const Drawer = createDrawerNavigator<ParamListBase>();
const Tab = createBottomTabNavigator<ParamListBase>();

/** The frame's header, in the theme: the card colour, the 22pt title in Archivo heavy (B14 rule 45). */
export function headerOptions(theme: Theme) {
  return {
    headerStyle: { backgroundColor: theme.colors.card },
    headerTintColor: theme.colors.text,
    headerTitleStyle: { fontFamily: theme.fonts.heavy, fontSize: theme.type.title, color: theme.colors.text },
    headerShadowVisible: true,
    contentStyle: { backgroundColor: theme.colors.page },
  } as const;
}

function MenuButton() {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNavigation();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={t('field.nav.menu')}
      onPress={() => navigation.dispatch(DrawerActions.openDrawer())}
      style={{ width: theme.touch.control, height: theme.touch.control, alignItems: 'center', justifyContent: 'center' }}
      testID="open-menu"
    >
      <Glyph name="drawer" />
    </Pressable>
  );
}

function TabsNavigator({ tablet }: { tablet: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const head = headerOptions(theme);
  return (
    <Tab.Navigator
      screenOptions={{
        headerLeft: tablet ? undefined : () => <MenuButton />,
        headerStyle: head.headerStyle,
        headerTintColor: head.headerTintColor,
        headerTitleStyle: head.headerTitleStyle,
        sceneStyle: { backgroundColor: theme.colors.page },
        tabBarActiveTintColor: theme.colors.brand,
        tabBarInactiveTintColor: theme.colors.text,
        tabBarLabelStyle: { fontSize: theme.type.label, fontFamily: theme.fonts.semibold },
        tabBarStyle: tablet
          ? { display: 'none' }
          : { minHeight: theme.touch.primary, backgroundColor: theme.colors.card, borderTopColor: theme.colors.border },
        tabBarIcon: () => null,
      }}
    >
      {TAB_SCREENS.map((tab) => (
        <Tab.Screen
          key={tab.id}
          name={tab.id}
          component={FRAMED_SCREENS[tab.id]}
          options={{ title: t(screenDef(tab.id).titleKey), tabBarLabel: t(tab.labelKey), tabBarButtonTestID: `tab-${tab.id}` }}
        />
      ))}
    </Tab.Navigator>
  );
}

function ShellNavigator({ tablet }: { tablet: boolean }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.page }}>
      {/* T-28: on a tablet the sidebar carries both figures (the availability
          chip under the name, the sync number on *Sync*), and the boards draw
          no strip above the panes — each pane has its own header. */}
      {tablet ? null : <ShellStatus />}
      <ShellStack.Navigator screenOptions={headerOptions(theme)}>
        <ShellStack.Screen name={TABS} options={{ headerShown: false }}>
          {() => <TabsNavigator tablet={tablet} />}
        </ShellStack.Screen>
        {screensIn('frame').map((id) => (
          <ShellStack.Screen
            key={id}
            name={id}
            component={FRAMED_SCREENS[id]}
            options={{ title: t(screenDef(id).titleKey) }}
          />
        ))}
      </ShellStack.Navigator>
    </View>
  );
}

function FrameNavigator({ tablet }: { tablet: boolean }) {
  return (
    <Drawer.Navigator
      drawerContent={(props) => <MenuContent {...props} tablet={tablet} />}
      screenOptions={{
        headerShown: false,
        drawerType: tablet ? 'permanent' : 'front',
        drawerStyle: tablet ? { width: SIDEBAR_WIDTH } : undefined,
        swipeEnabled: !tablet,
      }}
    >
      <Drawer.Screen name={SHELL}>{() => <ShellNavigator tablet={tablet} />}</Drawer.Screen>
    </Drawer.Navigator>
  );
}

function SignedInNavigator({ tablet, initialRoute }: { tablet: boolean; initialRoute: string }) {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <RootStack.Navigator initialRouteName={initialRoute} screenOptions={{ ...headerOptions(theme), headerShown: false }}>
      <RootStack.Screen name={FRAME}>{() => <FrameNavigator tablet={tablet} />}</RootStack.Screen>
      {screensIn('root').map((id) => (
        <RootStack.Screen
          key={id}
          name={id}
          component={FRAMED_SCREENS[id]}
          options={{
            title: t(screenDef(id).titleKey),
            presentation: id === 'FF-53' || id === 'SWITCH' ? 'modal' : 'card',
            headerShown: true,
          }}
        />
      ))}
    </RootStack.Navigator>
  );
}

function GateNavigator() {
  const { t } = useTranslation();
  const theme = useTheme();
  return (
    <RootStack.Navigator initialRouteName="FF-01" screenOptions={headerOptions(theme)}>
      {screensIn('gate').map((id) => (
        <RootStack.Screen
          key={id}
          name={id}
          component={FRAMED_SCREENS[id]}
          options={{ title: t(screenDef(id).titleKey), headerShown: id !== 'FF-01' }}
        />
      ))}
    </RootStack.Navigator>
  );
}

/** The first screen after a sign-in this navigator watched happen (the header above). */
export const AFTER_SIGN_IN: ScreenId = 'FF-07';

export interface AppNavigatorProps {
  /** Override the session (tests, previews). Defaults to the session context. */
  signedIn?: boolean;
  locked?: boolean;
  /** Override the width test (tests, previews). */
  tablet?: boolean;
}

export function AppNavigator(props: AppNavigatorProps) {
  const session = useOptionalSession();
  const { width, height } = useWindowDimensions();
  const phase = session?.snapshot.phase ?? 'signedOut';
  const signedIn = props.signedIn ?? phase !== 'signedOut';
  const locked = props.locked ?? phase === 'locked';
  const tablet = props.tablet ?? isTabletSize(width, height);
  // Remembers that the gate was on screen in this run, so the signed-in tree
  // that replaces it opens on FF-07 rather than the frame.
  const sawGate = useRef(false);
  if (!signedIn) sawGate.current = true;

  if (!signedIn) {
    return (
      <FormFactorProvider tablet={tablet}>
        <GateNavigator />
      </FormFactorProvider>
    );
  }
  return (
    <FormFactorProvider tablet={tablet}>
      {/* One toast surface above every signed-in screen, so feedback after a
          committed act survives the navigation that follows it — FF-37's
          *Sent* is shown on the screen Send returns to (DEF-FLD-10603). */}
      <ToastProvider>
        <View style={{ flex: 1 }}>
          <SignedInNavigator tablet={tablet} initialRoute={sawGate.current ? AFTER_SIGN_IN : FRAME} />
          {locked ? <LockCover /> : null}
        </View>
      </ToastProvider>
    </FormFactorProvider>
  );
}
