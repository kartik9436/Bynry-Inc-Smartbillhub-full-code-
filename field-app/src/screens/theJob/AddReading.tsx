/**
 * FF-59 Add a reading — a reading the template did not ask for (requirement
 * 72, US-FLD-072): the mirror of adding a step or a part. A reason is REQUIRED
 * (R7; TC-2: *Add it* stays unavailable without one) and it is saved as a
 * variance. A first reading on a new meter has no expected range, so it is
 * never flagged (TC-1).
 *
 *  - Which meter: only meters AT THIS PREMISES are offered (TC-3), or scanned
 *    (→ FF-38).
 *  - The unit is CHOSEN, never assumed from the service (R12, TC-4) — no chip
 *    starts selected. The three are requirement 9's: kWh, gallons, CCF.
 *
 * ⚠ `wo_reading` has no `added_in_field` / `reason` columns (US-FLD-072 §5
 * names them); the variance and its reason travel in the `reading` item's
 * payload, and the row is written so FF-20 shows it.
 *
 * Built from `phone/FF-59-add-a-reading.png`. Doors: back, *Cancel* and *Add
 * it* → FF-20; the scan button → FF-38.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { Button, Card, ChoiceChips, Field, Glyph, IconButton, Notice } from '../../components';
import * as jobQ from '../../db/queries/jobScreens';
import { useTheme } from '../../theme';
import { addReading } from './actions';
import { JobScreen, useDoor } from './JobScreen';
import { parseTyped } from './readingCheck';
import { useOpenJob } from './useJob';

/** Requirement 9: *"explicit units (kWh, gallons, CCF)"*. */
export const READING_UNITS = ['gal', 'CCF', 'kWh'] as const;

export const ADD_READING_REASONS = ['notListed', 'secondRegister', 'officeAsked', 'templateWrong'] as const;
type AddReason = (typeof ADD_READING_REASONS)[number];

const REASON_KEY: Record<AddReason, string> = {
  notListed: 'field.ff59.reason.notListed',
  secondRegister: 'field.ff59.reason.secondRegister',
  officeAsked: 'field.ff59.reason.officeAsked',
  templateWrong: 'field.ff59.reason.templateWrong',
};

export function AddReading() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-59');
  const { port, view } = useOpenJob();
  const [assetId, setAssetId] = useState<string | null>(null);
  const [reason, setReason] = useState<AddReason | null>(null);
  const [text, setText] = useState('');
  const [unit, setUnit] = useState<string | null>(null);
  const premiseId = view?.order.premise_id ?? null;
  const meters = port && premiseId ? jobQ.assetsAtPremise(port.db, premiseId) : [];
  const value = parseTyped(text);
  const meter = meters.find((m) => m.id === assetId) ?? null;
  const ready = port !== null && view !== null && meter !== null && reason !== null && value !== null && unit !== null;

  const save = () => {
    if (!ready || !port || !view || !meter || !reason || !value || !unit) return;
    const position = Math.max(0, ...view.readings.items.map((r) => r.row.position)) + 1;
    addReading(port, view.order.id, {
      assetId: meter.id,
      assetLabel: meter.serial ?? meter.id,
      reason,
      value,
      unit,
      position,
      prompt: [meter.serial ?? meter.badge ?? meter.id, t(REASON_KEY[reason])].join(' · '),
    });
    port.changed();
    go('FF-20');
  };

  return (
    <JobScreen
      id="FF-59"
      title={t('field.screen.ff59')}
      back={{ to: 'FF-20', label: t('field.ff59.backToReadings') }}
      footer={
        <>
          <Button grow onPress={() => go('FF-20')} testID="add-reading-cancel">
            {t('field.job.cancel')}
          </Button>
          <Button grow variant="primary" disabled={!ready} onPress={save} testID="add-reading-save">
            {t('field.ff59.add')}
          </Button>
        </>
      }
    >
      {view === null ? <Notice tone="info">{t('field.job.noJob')}</Notice> : null}
      <Card
        title={t('field.ff59.whichMeter')}
        trailing={
          <IconButton outlined label={t('field.job.scan')} onPress={() => go('FF-38')} testID="door-FF-38">
            <Glyph name="scan" />
          </IconButton>
        }
      >
        {meters.length > 0 ? (
          <ChoiceChips
            label={t('field.ff59.whichMeter')}
            active={assetId}
            onSelect={setAssetId}
            segments={meters.map((m) => ({ id: m.id, label: [m.serial ?? m.badge ?? m.id, m.size].filter(Boolean).join(' · ') }))}
            testID="add-reading-meter"
          />
        ) : (
          <Notice tone="info">{t('field.ff59.noMeters')}</Notice>
        )}
      </Card>
      <Card title={t('field.ff59.why')}>
        <ChoiceChips
          label={t('field.ff59.why')}
          active={reason}
          onSelect={(id) => setReason(id as AddReason)}
          segments={ADD_READING_REASONS.map((id) => ({ id, label: t(REASON_KEY[id]) }))}
          testID="add-reading-reason"
        />
      </Card>
      <Card title={t('field.ff59.reading')}>
        <Field
          label={t('field.ff59.reading')}
          value={text}
          onChangeText={setText}
          keyboardType="decimal-pad"
          unit={unit ?? undefined}
          testID="add-reading-value"
        />
        <ChoiceChips
          label={t('field.ff59.unit')}
          fill
          active={unit}
          onSelect={setUnit}
          segments={READING_UNITS.map((u) => ({ id: u, label: u }))}
          testID="add-reading-unit"
        />
      </Card>
      <View style={{ gap: theme.space[2] }}>
        <Notice tone="warning">{t('field.ff59.noHistory')}</Notice>
        <Notice tone="info">{t('field.ff59.variance')}</Notice>
      </View>
    </JobScreen>
  );
}
