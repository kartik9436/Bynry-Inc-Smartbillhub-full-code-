/**
 * *Correct their time* (FF-29) and *Correct the time* (FF-32): one sheet with
 * travel and labour as steppers — a technician taps, never types (R38) — in
 * five-minute steps. Saving captures the correction (`crewActions.correctTime`);
 * the capture stamps who corrected it and when (R9, R10).
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Sheet } from '../../components/Sheet';
import { Stepper } from '../../components/Stepper';
import { useTheme } from '../../theme';
import { formatMinutes } from './format';

export const CORRECTION_STEP_MINUTES = 5;

export function CorrectTimeSheet(props: {
  visible: boolean;
  name: string;
  travel: number;
  labour: number;
  onCancel: () => void;
  onSave: (minutes: { travel: number; labour: number }) => void;
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [travel, setTravel] = useState(props.travel);
  const [labour, setLabour] = useState(props.labour);
  useEffect(() => {
    setTravel(props.travel);
    setLabour(props.labour);
  }, [props.travel, props.labour, props.visible]);

  return (
    <Sheet
      visible={props.visible}
      onClose={props.onCancel}
      closeLabel={t('field.site.cancel')}
      title={t('field.correct.title', { name: props.name })}
      testID="correct-sheet"
      footer={
        <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
          <Button grow onPress={props.onCancel}>
            {t('field.site.cancel')}
          </Button>
          <Button grow variant="primary" onPress={() => props.onSave({ travel, labour })} testID="correct-save">
            {t('field.correct.save')}
          </Button>
        </View>
      }
    >
      <View style={{ gap: theme.space[4] }}>
        <View style={{ gap: theme.space[2] }}>
          <AppText variant="body" weight="semibold">
            {t('field.correct.travel', { time: formatMinutes(travel) })}
          </AppText>
          <Stepper
            value={travel}
            onChange={setTravel}
            min={0}
            step={CORRECTION_STEP_MINUTES}
            label={t('field.correct.travelLabel')}
            decreaseLabel={t('field.correct.less')}
            increaseLabel={t('field.correct.more')}
            testID="correct-travel"
          />
        </View>
        <View style={{ gap: theme.space[2] }}>
          <AppText variant="body" weight="semibold">
            {t('field.correct.labour', { time: formatMinutes(labour) })}
          </AppText>
          <Stepper
            value={labour}
            onChange={setLabour}
            min={0}
            step={CORRECTION_STEP_MINUTES}
            label={t('field.correct.labourLabel')}
            decreaseLabel={t('field.correct.less')}
            increaseLabel={t('field.correct.more')}
            testID="correct-labour"
          />
        </View>
      </View>
    </Sheet>
  );
}
