/**
 * FF-01 Splash (T-15; US-FLD-032 TC-1). Built from `wireframes/phone/
 * FF-01-splash.png` and `tablet/FF-01-T-splash.png`: the brand colour edge to
 * edge, the white mark, *SMART360 Next* over *Field*, and at the foot a
 * spinner, the utility's name and the version (R40: *"The app version is on
 * screen, so a defect report can name a build"*).
 *
 * It moves on by itself after `SPLASH_MS`: to the intro (FF-02) on a handset
 * nobody has signed in on, straight to sign-in (FF-05) on one somebody has —
 * the three intro screens are for a first morning, not every morning (our
 * judgment; the boards show the order, not the repeat). It REPLACES itself,
 * so back from the intro never lands on a splash. Only while it is the
 * screen on show: a timer firing after the technician has moved on does
 * nothing.
 *
 * The board's *2.587.0 · build 412* is the product version and the store
 * build number of the RUNNING BINARY (T-58, `release/build.ts`); where the
 * binary carries none (Expo Go, a test) the version is shown alone.
 */
import { StackActions, useIsFocused, useNavigation } from '@react-navigation/native';
import { useEffect, useLayoutEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';

import { textStyle } from '../../components/AppText';
import { versionLabel } from '../../release/build';
import { useOptionalSession } from '../../session/SessionProvider';
import { useTheme } from '../../theme';
import { ScreenBoundary } from '../theDay/ScreenBoundary';
import { BrandMark } from './BrandMark';
import { useGettingIn } from './gettingInServices';

/** How long the splash stays when nothing is in the way. */
export const SPLASH_MS = 1200;

/** The product's name — a brand, not translated (`App.tsx` PRODUCT_NAME). */
const PRODUCT = { first: 'SMART360', second: 'Next' };

function SplashBody() {
  const theme = useTheme();
  const c = theme.colors;
  const { t } = useTranslation();
  const navigation = useNavigation();
  const focused = useIsFocused();
  const focusedRef = useRef(focused);
  focusedRef.current = focused;
  const session = useOptionalSession();
  const { utilityName } = useGettingIn();
  const seenBefore = (session?.snapshot.known.length ?? 0) > 0;
  const next = seenBefore ? 'FF-05' : 'FF-02';

  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (focusedRef.current) navigation.dispatch(StackActions.replace(next));
    }, SPLASH_MS);
    return () => clearTimeout(timer);
  }, [navigation, next]);

  // Ink on the brand fill: the card colour, which is white in light and the
  // dark card in dark — both pass on their theme's brand fill (R100: in light
  // the fill is the 5%-darker #e12e13, because white on #ec3013 is 4.20:1).
  const ink = c.card;
  // *Next* is drawn in the page's dark ink; in sunlight the brand IS black,
  // so it takes the card's white instead of vanishing.
  const second = theme.name === 'sunlight' ? c.card : theme.name === 'dark' ? c.page : c.text;
  // DEF-FLD-10362: the screen names itself. The product name is the HEADING
  // and comes first to a screen reader; the whole screen is still one tap to
  // go on — a full-screen *Continue* button drawn over it — rather than the
  // button swallowing the heading (a reader landed on *Continue* with no
  // screen name).
  const go = () => navigation.dispatch(StackActions.replace(next));
  return (
    <View testID="screen-FF-01" style={{ flex: 1, backgroundColor: c.brandFill, padding: theme.space[6] }}>
      <View pointerEvents="none" style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: theme.space[3] }}>
        <BrandMark size="lg" inverse />
        <Text
          accessibilityRole="header"
          style={[textStyle(theme, 'title', 'heavy'), { color: ink, fontSize: theme.type.title * 1.5, lineHeight: Math.round(theme.type.title * 1.5 * theme.lineHeight.heading) }]}
        >
          {PRODUCT.first}
          <Text style={{ color: second }}> {PRODUCT.second}</Text>
        </Text>
        <Text style={[textStyle(theme, 'section', 'semibold'), { color: ink }]}>{t('field.splash.field')}</Text>
      </View>
      <View pointerEvents="none" style={{ alignItems: 'center', gap: theme.space[3] }}>
        <ActivityIndicator color={ink} accessibilityLabel={t('field.common.loading')} />
        {utilityName ? <Text style={[textStyle(theme, 'body', 'semibold'), { color: ink }]}>{utilityName}</Text> : null}
        <Text style={[textStyle(theme, 'label'), { color: ink }]} testID="splash-version">
          {versionLabel(t)}
        </Text>
      </View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('field.splash.continue')}
        onPress={go}
        testID={`door-${next}`}
        style={{ position: 'absolute', top: 0, right: 0, bottom: 0, left: 0 }}
      />
    </View>
  );
}

export function SplashScreen() {
  return (
    <ScreenBoundary screen="FF-01">
      <SplashBody />
    </ScreenBoundary>
  );
}
