/**
 * FF-51 Settings (T-25, T-58; US-FLD-033, -035, -036, -047; image
 * `phone/FF-51-settings.png`, and the board below the image's cut:
 * Nearby work · Reading · Notifications · Sync and data · Permissions ·
 * About · Sign out).
 *
 *  - Language — every one of the eleven, each named in itself, switched at
 *    run time with no restart (TC-1; `i18n/I18nProvider`).
 *  - Date and time — the date format, the clock, the units.
 *  - Screen — Automatic · Light · Dark · Sunlight, switched at once (TC-2,
 *    requirement 35); *Bigger text* (the type ramp one step up); keep the
 *    screen awake on a job; and the two theme previews (FF-54, FF-55).
 *  - Nearby work — 1 · 2 · 5 · 10 miles, default 2 (R34; FF-11 reads it).
 *  - Reading (RW-29) · Notifications (FF-52) · Sync and data (opens FF-50)
 *    and *Photos on wi-fi only*, default OFF (PO 2026-10-28, FB-015 — it
 *    replaced R54's *Photos on mobile data*, which is SUPERSEDED) ·
 *    Permissions (FF-07).
 *  - About — the version from package.json (R40, T-58), the utility, and the
 *    diagnostics line (R72, `telemetry/settingsLine.ts`). ⚠ It carried a
 *    *"Beta build — certificate check off"* line (DEF-FLD-10617, 2026-10-26)
 *    until 2026-10-28, when pinning was made dormant in every build and the
 *    line was removed (`CR-195-BRC10`, PO *"start A1"*): nothing about
 *    certificate pinning is shown to a user.
 *  - Sign out (FF-53).
 *
 * Every choice is a tap (R38). Every choice is kept in the handset's
 * preferences (`prefs.ts`) and survives a restart (US-FLD-033 §5).
 *
 * Each card is its own component (B14 rule 43): the tablet board (FF-51 T)
 * lists the sections and shows one beside the list.
 */
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Card, ChoiceChips, ListRow, ToggleRow } from '../../components';
import { useLanguage } from '../../i18n/I18nProvider';
import { isLanguageCode } from '../../i18n/languages';
import { versionLabel } from '../../release/build';
import { diagnosticsLine } from '../../telemetry/settingsLine';
import { useBiggerText, useTheme, useThemeMode } from '../../theme';
import type { ThemeMode } from '../../theme';
import { formatClock, formatDate } from './format';
import { useActiveTechnician, useHandsetPrefs } from './hooks';
import { MeScreen, useDoor } from './MeScreen';
import { CLOCKS, DATE_FORMATS, NEARBY_RADII, PREF, UNITS, writeFlag, writePref } from './prefs';
import { useMeServices } from './services';

export const THEME_KEY: Record<ThemeMode, string> = {
  automatic: 'field.ff51.theme.automatic',
  light: 'field.ff51.theme.light',
  dark: 'field.ff51.theme.dark',
  sunlight: 'field.ff51.theme.sunlight',
};

const UNIT_KEY = { miles: 'field.ff51.units.miles', kilometres: 'field.ff51.units.kilometres' } as const;

const DIAGNOSTICS_KEY = {
  'settings.diagnostics.on': 'field.settings.diagnostics.on',
  'settings.diagnostics.off': 'field.settings.diagnostics.off',
} as const;

/** A preference write that the screen re-reads at once. */
function usePrefWriter() {
  const services = useMeServices();
  const [prefs, reread] = useHandsetPrefs();
  const store = services.prefs;
  return {
    prefs,
    store,
    set(key: string, value: string) {
      writePref(store, key, value);
      reread();
    },
    flag(key: string, on: boolean) {
      writeFlag(store, key, on);
      reread();
    },
  };
}

export function LanguageSection() {
  const { t } = useTranslation();
  const { language, setLanguage, languages } = useLanguage();
  return (
    <Card title={t('field.ff51.language')}>
      <ChoiceChips
        label={t('field.ff51.language')}
        segments={languages.map((l) => ({ id: l.code, label: l.name }))}
        active={language}
        onSelect={(code) => {
          if (isLanguageCode(code)) void setLanguage(code);
        }}
        testID="ff51-language"
      />
    </Card>
  );
}

export function DateTimeSection() {
  const { t } = useTranslation();
  const services = useMeServices();
  const w = usePrefWriter();
  const sample = services.now();
  return (
    <Card title={t('field.ff51.dateAndTime')}>
      <AppText variant="body">{t('field.ff51.date')}</AppText>
      <ChoiceChips
        label={t('field.ff51.date')}
        segments={DATE_FORMATS.map((f) => ({ id: f, label: formatDate(sample, f) }))}
        active={w.prefs.dateFormat}
        onSelect={(id) => w.set(PREF.DATE_FORMAT, id)}
        testID="ff51-date"
      />
      <AppText variant="body">{t('field.ff51.clock')}</AppText>
      <ChoiceChips
        label={t('field.ff51.clock')}
        fill
        segments={CLOCKS.map((c) => ({ id: c, label: formatClock(sample.toISOString(), c) }))}
        active={w.prefs.clock}
        onSelect={(id) => w.set(PREF.CLOCK, id)}
        testID="ff51-clock"
      />
      <AppText variant="body">{t('field.ff51.units')}</AppText>
      <ChoiceChips
        label={t('field.ff51.units')}
        fill
        segments={UNITS.map((u) => ({ id: u, label: t(UNIT_KEY[u]) }))}
        active={w.prefs.units}
        onSelect={(id) => w.set(PREF.UNITS, id)}
        testID="ff51-units"
      />
    </Card>
  );
}

export function ScreenSection() {
  const { t } = useTranslation();
  const door = useDoor('FF-51');
  const { mode, setMode } = useThemeMode();
  const { biggerText, setBiggerText } = useBiggerText();
  const w = usePrefWriter();
  return (
    <Card title={t('field.ff51.screen')}>
      <ChoiceChips
        label={t('field.ff51.screen')}
        size="default"
        segments={(['automatic', 'light', 'dark', 'sunlight'] as const).map((m) => ({ id: m, label: t(THEME_KEY[m]) }))}
        active={mode}
        onSelect={(id) => setMode(id as ThemeMode)}
        testID="ff51-theme"
      />
      <ToggleRow
        divider
        label={t('field.ff51.biggerText')}
        detail={t('field.ff51.biggerTextDetail')}
        value={biggerText}
        onChange={setBiggerText}
        testID="ff51-bigger-text"
      />
      <ToggleRow divider label={t('field.ff51.keepAwake')} value={w.prefs.keepAwake} onChange={(on) => w.flag(PREF.KEEP_AWAKE, on)} testID="ff51-keep-awake" />
      <ListRow divider label={t('field.ff51.previewDark')} onPress={() => door('FF-54')} testID="door-FF-54" />
      <ListRow divider label={t('field.ff51.previewSunlight')} onPress={() => door('FF-55')} testID="door-FF-55" />
    </Card>
  );
}

export function NearbySection() {
  const { t } = useTranslation();
  const w = usePrefWriter();
  return (
    <Card title={t('field.ff51.nearby')}>
      <ChoiceChips
        label={t('field.ff51.nearby')}
        fill
        segments={NEARBY_RADII.map((r) => ({ id: r, label: t('field.ff51.miles', { count: Number(r) }) }))}
        active={w.prefs.nearbyRadius}
        onSelect={(id) => w.set(PREF.NEARBY_RADIUS, id)}
        testID="ff51-nearby"
      />
    </Card>
  );
}

/** *Photos on wi-fi only* — default off: photos go on mobile data too (PO 2026-10-28, FB-015). */
export function PhotosWifiOnlyRow(props: { divider?: boolean }) {
  const { t } = useTranslation();
  const w = usePrefWriter();
  return (
    <ToggleRow
      divider={props.divider}
      label={t('field.ff51.photosWifiOnly')}
      value={w.prefs.photosWifiOnly}
      onChange={(on) => w.flag(PREF.PHOTOS_WIFI_ONLY, on)}
      testID="ff51-photos-wifi-only"
    />
  );
}

export function LinksSection() {
  const { t } = useTranslation();
  const door = useDoor('FF-51');
  return (
    <Card>
      <ListRow label={t('field.ff51.reading')} onPress={() => door('RW-29')} testID="door-RW-29" />
      <ListRow divider label={t('field.ff51.notifications')} onPress={() => door('FF-52')} testID="door-FF-52" />
      <ListRow divider label={t('field.ff51.syncAndData')} onPress={() => door('FF-50')} testID="door-FF-50" />
      <PhotosWifiOnlyRow divider />
      <ListRow divider label={t('field.ff51.permissions')} onPress={() => door('FF-07')} testID="door-FF-07" />
    </Card>
  );
}

export function AboutSection() {
  const { t } = useTranslation();
  const theme = useTheme();
  const tech = useActiveTechnician();
  const diagnostics = diagnosticsLine(true);
  return (
    <Card title={t('field.ff51.about')} testID="ff51-about">
      <ListRow label={t('field.nav.version')} value={versionLabel(t)} testID="ff51-version" />
      {tech ? <ListRow divider label={t('field.ff51.utility')} value={tech.tenant} /> : null}
      <View style={{ paddingTop: theme.space[2] }}>
        <AppText variant="label" tone="muted" testID="ff51-diagnostics">
          {t(DIAGNOSTICS_KEY[diagnostics.key])}
        </AppText>
      </View>
    </Card>
  );
}

export function SignOutSection() {
  const { t } = useTranslation();
  const door = useDoor('FF-51');
  return (
    <Card>
      <ListRow label={t('field.nav.signOut')} onPress={() => door('FF-53')} testID="door-FF-53" />
    </Card>
  );
}

export function SettingsScreen() {
  const { t } = useTranslation();
  return (
    <MeScreen id="FF-51" title={t('field.screen.ff51')} leading={{ back: 'FF-44' }}>
      <LanguageSection />
      <DateTimeSection />
      <ScreenSection />
      <NearbySection />
      <LinksSection />
      <AboutSection />
      <SignOutSection />
    </MeScreen>
  );
}
