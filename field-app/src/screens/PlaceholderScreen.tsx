/**
 * The stand-in every FF- and RW- route mounts until its real screen is built
 * from its drawing (T-15 onwards). It says which screen it is, and it renders
 * the screen's DOORS — the links the design draws on it (`navigation/doors.ts`)
 * — as working buttons, so the app can be walked end to end today and the
 * doors test can press them.
 *
 * A screen built later replaces this at the same route name and keeps the
 * same doors; `tests/navigation/doors.test.ts` is what says so.
 *
 * Two kinds of door are an ACT, not a link, and are drawn as such: from the
 * signed-out screens into the app (*after sign in*) and from the app back to
 * them (*signs you out*). Pushing across that line would put a signed-out
 * person in the app, or a signed-in one at the gate.
 */
import { useNavigation } from '@react-navigation/native';
import { useTranslation } from 'react-i18next';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { textStyle } from '../components/AppText';
import { DOORS } from '../navigation/doors';
import { doorAction, doorKind } from '../navigation/routing';
import { type ScreenId, screenDef } from '../navigation/screens';
import { useTheme } from '../theme';

export function PlaceholderScreen({ id }: { id: ScreenId }) {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const theme = useTheme();
  const c = theme.colors;

  return (
    <ScrollView
      keyboardShouldPersistTaps="handled"
      style={{ flex: 1, backgroundColor: c.page }}
      contentContainerStyle={{ padding: theme.space[4], gap: theme.space[2] }}
      testID={`screen-${id}`}
    >
      <Text style={textStyle(theme, 'micro', 'heavy', 'brand')}>{id}</Text>
      <Text style={textStyle(theme, 'title', 'heavy')}>{t(screenDef(id).titleKey)}</Text>
      <Text style={textStyle(theme, 'body', 'regular', 'muted')}>{t('field.placeholder.notBuilt')}</Text>
      <Text style={[textStyle(theme, 'micro', 'heavy', 'muted'), { paddingTop: theme.space[4] }]}>
        {t('field.placeholder.doors').toUpperCase()}
      </Text>
      <View style={{ gap: theme.space[2] }}>
        {DOORS[id].map((to) => {
          const kind = doorKind(id, to);
          const action = doorAction(id, to);
          const act = kind === 'signs-in' ? t('field.door.signsIn') : kind === 'signs-out' ? t('field.door.signsOut') : null;
          return (
            <Pressable
              key={to}
              accessibilityRole="button"
              accessibilityState={{ disabled: action == null }}
              disabled={action == null}
              onPress={() => {
                if (action) navigation.dispatch(action);
              }}
              style={{
                minHeight: theme.touch.control,
                justifyContent: 'center',
                paddingHorizontal: theme.space[4],
                borderRadius: theme.radius.md,
                borderWidth: theme.borderWidth.control,
                borderColor: c.border,
                backgroundColor: action == null ? c.page : c.card,
              }}
              testID={`door-${to}`}
            >
              <Text style={textStyle(theme, 'body')}>
                {to} · {t(screenDef(to).titleKey)}
                {act ? ` — ${act}` : ''}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </ScrollView>
  );
}
