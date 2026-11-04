/**
 * FF-54 Dark theme and FF-55 Sunlight theme (T-26; US-FLD-001, -035; images
 * `phone/FF-54-dark-theme.png`, `phone/FF-55-sunlight-theme.png`).
 *
 * US-FLD-035 TC-2: *"FF-54 dark and FF-55 sunlight — the same screen, nothing
 * re-laid out — only the tokens change."* So both are ONE component, the job
 * card the two boards draw, mounted under a ThemeProvider pinned to each
 * theme. Nothing here branches on the theme: the proof is that the same tree
 * reads differently only through `useTheme()`.
 *
 * ⚠ WHAT THE BOARDS DRAW, AND WHY IT IS A STAND-IN. The brief says "the same
 * Today screen"; the two images draw the JOB screen (FF-15, WO-4822), and the
 * doors swept from them are the job's (FF-15, FF-25, FF-20, FF-17, FF-21,
 * FF-34) — the images win (B14 rule 42). FF-15 belongs to another wave and is
 * not on this branch, and mounting its component here would carry ITS doors
 * rather than these boards', so this is the job card built from the kit with
 * the boards' own doors, over the technician's first open job from the
 * handset. When there is none it says so; it never draws the board's
 * WO-4822, which is an illustration (B14 rule 37).
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, EmptyState, Kicker, ListRow, StatusChip } from '../../components';
import type { ScreenId } from '../../navigation/screens';
import { ThemeProvider, useTheme, type ThemeName } from '../../theme';
import { formatClock } from './format';
import { useActiveTechnician, useHandsetPrefs } from './hooks';
import { MeScreen, useDoor } from './MeScreen';
import { useMeServices } from './services';

function JobProof({ id }: { id: ScreenId }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const door = useDoor(id);
  const tech = useActiveTechnician();
  const [prefs] = useHandsetPrefs();
  const job = tech ? services.data.firstOpenJob(tech.technicianId, services.now()) : null;
  const window =
    job?.windowStart && job.windowEnd
      ? `${formatClock(job.windowStart, prefs.clock)}–${formatClock(job.windowEnd, prefs.clock)}`
      : null;

  return (
    <MeScreen
      id={id}
      title={job?.number ?? t(id === 'FF-54' ? 'field.screen.ff54' : 'field.screen.ff55')}
      leading={{ back: 'FF-15' }}
      footer={
        <Button grow variant="primary" onPress={() => door('FF-34')} testID="door-FF-34">
          {t('field.ff54.closeJob')}
        </Button>
      }
    >
      {job ? (
        <View style={{ gap: theme.space[2] }} testID={`${id}-job`}>
          {job.type ? <Kicker tone="brand">{job.type}</Kicker> : null}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
            {job.priority ? <StatusChip tone="neutral">{job.priority}</StatusChip> : null}
            {window ? (
              <AppText variant="label" tone="muted">
                {window}
              </AppText>
            ) : null}
          </View>
        </View>
      ) : (
        <EmptyState title={t('field.ff54.noJob')} helper={t('field.ff54.noJobHelper')} testID={`${id}-no-job`} />
      )}
      <Card>
        {job?.address ? <AppText variant="section">{job.address}</AppText> : null}
        {job?.locality ? <AppText variant="body">{job.locality}</AppText> : null}
        <Button onPress={() => door('FF-25')} testID="door-FF-25">
          {t('field.ff54.customer')}
        </Button>
      </Card>
      <Card title={t('field.ff54.work')}>
        <ListRow label={t('field.ff54.steps')} onPress={() => door('FF-17')} testID="door-FF-17" />
        <ListRow divider label={t('field.ff54.readings')} onPress={() => door('FF-20')} testID="door-FF-20" />
        <ListRow divider label={t('field.ff54.photos')} onPress={() => door('FF-21')} testID="door-FF-21" />
      </Card>
    </MeScreen>
  );
}

function pinned(name: ThemeName, id: ScreenId) {
  function ThemeProof() {
    return (
      <ThemeProvider initialMode={name}>
        <JobProof id={id} />
      </ThemeProvider>
    );
  }
  ThemeProof.displayName = `ThemeProof(${name})`;
  return ThemeProof;
}

export const DarkThemeScreen = pinned('dark', 'FF-54');
export const SunlightThemeScreen = pinned('sunlight', 'FF-55');
export { JobProof };
