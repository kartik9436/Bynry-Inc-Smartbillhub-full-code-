/**
 * FF-18 Add a step — work the template did not plan. R7 (PO ruled): *"A field
 * addition is never silent. An added step or material carries a reason and
 * shows as a variance against the template."* So *Add step* stays
 * unavailable until BOTH what was done and why are written (US-FLD-028 TC-3),
 * and the saved step is marked added in the field, with who and when, on
 * FF-17 and in FF-15's count (TC-4 of US-FLD-026).
 *
 * *How long?* is three taps, not a typed number (R38); the three presets are
 * this screen's, drawn on the board. *Needs a photo* makes the step demand a
 * photograph like a template step (US-FLD-028 TC-4).
 *
 * A sheet over the step (`phone/FF-18-add-step.png`), built as a route of its
 * own (`SheetScreen`). Doors: *Cancel* and *Add step* both return to FF-17.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { AppText, Button, ChoiceChips, Field, FieldGroup, Notice, SheetScreen, ToggleRow } from '../../components';
import { addStep } from './actions';
import { JobScreen, useDoor } from './JobScreen';
import { useOpenJob } from './useJob';

/** The board's three durations, in minutes. A preset of this screen, not a rule. */
export const STEP_MINUTES = [5, 15, 30] as const;

export function AddStep() {
  const { t } = useTranslation();
  const go = useDoor('FF-18');
  const { port, view } = useOpenJob();
  const [label, setLabel] = useState('');
  const [reason, setReason] = useState('');
  const [minutes, setMinutes] = useState<number>(STEP_MINUTES[1]);
  const [photo, setPhoto] = useState(false);
  const ready = port !== null && view !== null && label.trim() !== '' && reason.trim() !== '';
  const current = view?.tasks.items[view.tasks.currentIndex] ?? null;

  const save = () => {
    if (!ready || !port || !view) return;
    const position = Math.max(0, ...view.tasks.items.map((x) => x.row.position)) + 1;
    addStep(port, view.order.id, { label, reason, minutes, photoRequired: photo, position });
    port.changed();
    go('FF-17');
  };

  return (
    <JobScreen id="FF-18" title={t('field.screen.ff18')} bare>
      <SheetScreen
        title={t('field.ff18.title')}
        closeLabel={t('field.job.close')}
        onClose={() => go('FF-17')}
        closeTestID="sheet-close"
        context={
          current ? (
            <AppText variant="section">{`${view ? view.tasks.currentIndex + 1 : ''} · ${current.row.label}`}</AppText>
          ) : null
        }
        footer={
          <>
            <Button grow onPress={() => go('FF-17')} testID="door-FF-17">
              {t('field.job.cancel')}
            </Button>
            <Button grow variant="primary" disabled={!ready} onPress={save} testID="add-step-save">
              {t('field.ff18.add')}
            </Button>
          </>
        }
      >
        <Notice tone="info">{t('field.ff18.marked')}</Notice>
        <FieldGroup>
          <Field label={t('field.ff18.what')} value={label} onChangeText={setLabel} testID="add-step-what" />
          <Field
            label={t('field.ff18.why')}
            value={reason}
            onChangeText={setReason}
            multiline
            help={t('field.ff18.officeReads')}
            testID="add-step-why"
          />
        </FieldGroup>
        <AppText variant="label" weight="semibold">
          {t('field.ff18.howLong')}
        </AppText>
        <ChoiceChips
          label={t('field.ff18.howLong')}
          fill
          active={String(minutes)}
          onSelect={(id) => setMinutes(Number(id))}
          segments={STEP_MINUTES.map((m) => ({ id: String(m), label: t('field.job.minutes', { count: m }) }))}
          testID="add-step-minutes"
        />
        <ToggleRow
          label={t('field.ff18.needsPhoto')}
          detail={t('field.ff18.proof')}
          value={photo}
          onChange={setPhoto}
          testID="add-step-photo"
        />
      </SheetScreen>
    </JobScreen>
  );
}
