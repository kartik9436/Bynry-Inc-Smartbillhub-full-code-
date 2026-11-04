/**
 * FF-45 Availability (T-24; US-FLD-006; image `phone/FF-45-availability.png`).
 *
 * Three choices, each with the line that says what it means for the
 * technician — *New jobs can be assigned* · *Emergencies still reach you*
 * (TC-2) · *Shift ends. Unsent work still sends.* (TC-3) — and, when photos
 * are still going up, how many. *Done* returns to the profile.
 *
 * The choice is kept on the handset at once and the chip that is always on
 * screen follows it (`availability.tsx`). Telling dispatch is captured
 * through the outbox with the tap's time (FB-033, `availabilityPort.ts`) and
 * goes when there is signal, like every other act — so the screen says
 * nothing about it (B14 rule 33). Off duty holds back nothing unsent (TC-5):
 * the tap adds its own item and touches no other.
 */
import { useTranslation } from 'react-i18next';
import { Pressable, View } from 'react-native';

import { AppText, Button, Dot, Glyph, Notice } from '../../components';
import { useTheme } from '../../theme';
import { AVAILABILITIES, AVAILABILITY_TONE, type Choosable, useAvailability } from './availability';
import { useActiveTechnician, useCaptor } from './hooks';
import { MeSheetScreen, useDoor } from './MeScreen';
import { useMeServices } from './services';

const LABEL = {
  available: 'field.availability.available',
  onBreak: 'field.availability.onBreak',
  offDuty: 'field.availability.offDuty',
} as const;

const MEANS = {
  available: 'field.ff45.means.available',
  onBreak: 'field.ff45.means.onBreak',
  offDuty: 'field.ff45.means.offDuty',
} as const;

function Choice(props: { value: Choosable; selected: boolean; onPress: () => void }) {
  const { t } = useTranslation();
  const theme = useTheme();
  const c = theme.colors;
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityLabel={`${t(LABEL[props.value])}, ${t(MEANS[props.value])}`}
      accessibilityState={{ checked: props.selected }}
      onPress={props.onPress}
      testID={`ff45-${props.value}`}
      style={{
        minHeight: theme.touch.primary,
        flexDirection: 'row',
        alignItems: 'center',
        gap: theme.space[3],
        paddingHorizontal: theme.space[4],
        paddingVertical: theme.space[3],
        borderWidth: props.selected ? theme.borderWidth.emphasis : theme.borderWidth.control,
        borderColor: props.selected ? c.text : c.controlBorder,
        borderRadius: theme.radius.md,
        backgroundColor: props.selected ? c.surface : c.card,
      }}
    >
      <Dot tone={AVAILABILITY_TONE[props.value]} />
      <View style={{ flexGrow: 1, flexShrink: 1 }}>
        <AppText variant="section" weight={props.selected ? 'heavy' : 'regular'}>
          {t(LABEL[props.value])}
        </AppText>
        <AppText variant="label" tone="muted">
          {t(MEANS[props.value])}
        </AppText>
      </View>
      {props.selected ? <Glyph name="check" /> : null}
    </Pressable>
  );
}

export function AvailabilityScreen() {
  const { t } = useTranslation();
  const theme = useTheme();
  const services = useMeServices();
  const door = useDoor('FF-45');
  const tech = useActiveTechnician();
  const captor = useCaptor();
  const [state, setLocal] = useAvailability(tech?.technicianId ?? null);
  const counts = tech ? services.data.syncCounts(tech.technicianId) : null;

  async function choose(value: Choosable) {
    if (!tech) return;
    setLocal(value);
    // The choice is the handset's at once; the office hears it when it sends.
    try {
      await services.availability.send(captor(), value, services.now());
    } catch {
      // Not sent (no store, or no capture credential): the chip still holds it.
    }
  }

  return (
    <MeSheetScreen
      id="FF-45"
      title={t('field.screen.ff45')}
      footer={
        <Button variant="primary" onPress={() => door('FF-44')} testID="door-FF-44">
          {t('field.ff45.done')}
        </Button>
      }
    >
      <View accessibilityRole="radiogroup" accessibilityLabel={t('field.screen.ff45')} style={{ gap: theme.touch.clear }}>
        {AVAILABILITIES.map((v) => (
          <Choice key={v} value={v} selected={state.value === v} onPress={() => choose(v)} />
        ))}
      </View>
      {counts && counts.photosWaiting > 0 ? (
        <Notice tone="warning" testID="ff45-photos">
          {t('field.ff45.photosUploading', { count: counts.photosWaiting })}
        </Notice>
      ) : null}
    </MeSheetScreen>
  );
}
