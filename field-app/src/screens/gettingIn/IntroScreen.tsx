/**
 * FF-02 · FF-03 · FF-04 — the three intro screens (T-15; US-FLD-032 TC-1).
 * Built from `wireframes/phone/FF-02-intro-1.png`, `FF-03-intro-2.png`,
 * `FF-04-intro-3.png` and their tablet boards: *Skip* top right, the
 * illustration disc (calendar on green, a hand on amber, sync on blue), the
 * heading, two short sentences, the three dots, and *Next* — *Sign in* on the
 * last.
 *
 * ⚠ THE WORDS ARE SHORTER THAN THE BOARDS' (B14 rule 33, which our standard
 * applies to every screen — rule 44): a heading is at most three words and a
 * sentence at most six. The boards' *"Your whole day, on the phone"* becomes
 * *Your whole day*; each paragraph becomes two short sentences that keep its
 * facts. The design's figures and layout are unchanged.
 */
import { useNavigation } from '@react-navigation/native';
import { useLayoutEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, Text, View } from 'react-native';

import { AppText, Button, IconCircle } from '../../components';
import type { GlyphName } from '../../components';
import { textStyle } from '../../components/AppText';
import type { ScreenId } from '../../navigation/screens';
import { useTheme } from '../../theme';
import type { StatusTone } from '../../theme';
import { openScreen } from '../theDay/go';
import { ScreenBoundary } from '../theDay/ScreenBoundary';

interface IntroPage {
  id: ScreenId;
  index: number;
  glyph: GlyphName;
  tone: StatusTone;
  next: ScreenId;
  titleKey: string;
  bodyKey: string;
  nextKey: string;
}

export const INTRO_PAGES: readonly IntroPage[] = [
  { id: 'FF-02', index: 0, glyph: 'calendar', tone: 'success', next: 'FF-03', titleKey: 'field.intro.one.title', bodyKey: 'field.intro.one.body', nextKey: 'field.intro.next' },
  { id: 'FF-03', index: 1, glyph: 'hand', tone: 'warning', next: 'FF-04', titleKey: 'field.intro.two.title', bodyKey: 'field.intro.two.body', nextKey: 'field.intro.next' },
  { id: 'FF-04', index: 2, glyph: 'sync', tone: 'info', next: 'FF-05', titleKey: 'field.intro.three.title', bodyKey: 'field.intro.three.body', nextKey: 'field.intro.signIn' },
];

function Dots({ index, total }: { index: number; total: number }) {
  const theme = useTheme();
  const { t } = useTranslation();
  return (
    <View
      accessible
      accessibilityRole="text"
      accessibilityLabel={t('field.intro.position', { n: index + 1, total })}
      style={{ flexDirection: 'row', justifyContent: 'center', gap: theme.space[2] }}
    >
      {Array.from({ length: total }, (_, i) => (
        <View
          key={i}
          style={{
            width: i === index ? theme.space[6] : theme.space[2],
            height: theme.space[2],
            borderRadius: theme.space[1],
            backgroundColor: i === index ? theme.colors.brand : theme.colors.border,
          }}
        />
      ))}
    </View>
  );
}

function IntroBody({ page }: { page: IntroPage }) {
  const theme = useTheme();
  const { t } = useTranslation();
  const navigation = useNavigation();
  const last = page.next === 'FF-05';

  useLayoutEffect(() => {
    navigation.setOptions({ headerShown: false });
  }, [navigation]);

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.card, padding: theme.space[6] }} testID={`screen-${page.id}`}>
      <View style={{ alignItems: 'flex-end', minHeight: theme.touch.control }}>
        {last ? null : (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t('field.intro.skip')}
            onPress={() => openScreen(navigation, 'FF-05')}
            testID="door-FF-05"
            style={{ minHeight: theme.touch.control, minWidth: theme.touch.control, alignItems: 'center', justifyContent: 'center' }}
          >
            <Text style={textStyle(theme, 'body', 'semibold', 'muted')}>{t('field.intro.skip')}</Text>
          </Pressable>
        )}
      </View>
      <View style={{ flex: 1, justifyContent: 'center' }}>
        <IconCircle glyph={page.glyph} tone={page.tone} size="lg" />
      </View>
      <View style={{ gap: theme.space[3], paddingBottom: theme.space[6] }}>
        <AppText variant="title">{t(page.titleKey)}</AppText>
        <AppText variant="body" tone="muted">
          {t(page.bodyKey)}
        </AppText>
      </View>
      <View style={{ gap: theme.space[6] }}>
        <Dots index={page.index} total={INTRO_PAGES.length} />
        <Button variant="primary" onPress={() => openScreen(navigation, page.next)} testID={`door-${page.next}`}>
          {t(page.nextKey)}
        </Button>
      </View>
    </View>
  );
}

function make(page: IntroPage) {
  function Intro() {
    return (
      <ScreenBoundary screen={page.id}>
        <IntroBody page={page} />
      </ScreenBoundary>
    );
  }
  Intro.displayName = `Intro(${page.id})`;
  return Intro;
}

export const IntroOneScreen = make(INTRO_PAGES[0] as IntroPage);
export const IntroTwoScreen = make(INTRO_PAGES[1] as IntroPage);
export const IntroThreeScreen = make(INTRO_PAGES[2] as IntroPage);
