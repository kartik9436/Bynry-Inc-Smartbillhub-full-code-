/**
 * FF-24 Parts used — the parts this STEP used, recorded against it
 * (requirement 16, US-FLD-016 TC-1: meter MTR-W58 ×1 and a wire seal ×1 on
 * step 4 → *"Van drops to 0 of this meter"*). A sheet over the step, built as
 * a route (`SheetScreen`).
 *
 * Counts are tapped (R38). The van line is shown only where the server sent a
 * van count — van stock is not kept on the handset — and it is a fact, never
 * a block: a part not on the van can still be recorded as used.
 *
 * Built from `phone/FF-24-parts-used.png`. Doors: the scan button and *Add
 * another part* → FF-38 (scan the part), *Done* → FF-17.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText, Button, Card, Glyph, IconButton, Notice, SheetScreen, Stepper } from '../../components';
import { useTheme } from '../../theme';
import { setMaterialUsed } from './actions';
import { JobScreen, useDoor } from './JobScreen';
import { useOpenJob } from './useJob';

export function PartsUsed() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-24');
  const { port, view } = useOpenJob();
  const [counts, setCounts] = useState<Record<string, number>>({});
  const step = view && view.tasks.currentIndex >= 0 ? view.tasks.items[view.tasks.currentIndex] : null;
  const parts = view?.materials.items ?? [];

  const done = () => {
    if (port && view) {
      for (const m of parts) {
        const next = counts[m.row.id];
        if (next !== undefined && next !== m.used) {
          setMaterialUsed(port, view.order.id, { id: m.row.id, detail: m.detail, state: m.row.state }, next, step?.row.id ?? null);
        }
      }
      port.changed();
    }
    go('FF-17');
  };

  const emptied = parts.filter((m) => {
    const van = m.detail.van;
    const n = counts[m.row.id] ?? m.used;
    return van != null && n > m.used && van - (n - m.used) <= 0;
  });

  return (
    <JobScreen id="FF-24" title={t('field.screen.ff24')} bare>
      <SheetScreen
        title={t('field.ff24.title')}
        closeLabel={t('field.job.close')}
        onClose={() => go('FF-17')}
        closeTestID="sheet-close"
        trailing={
          <IconButton outlined label={t('field.job.scan')} onPress={() => go('FF-38')} testID="door-FF-38">
            <Glyph name="scan" />
          </IconButton>
        }
        context={
          step && view ? (
            <View>
              <AppText variant="section">{step.row.label}</AppText>
              <AppText variant="label" tone="muted">
                {t('field.ff24.stepOf', { step: view.tasks.currentIndex + 1, total: view.tasks.total, order: view.order.number ?? '' })}
              </AppText>
            </View>
          ) : null
        }
        footer={
          <View style={{ flexGrow: 1, gap: theme.touch.clear }}>
            <Button onPress={() => go('FF-38')} testID="parts-add-another">
              {t('field.ff24.another')}
            </Button>
            <Button variant="primary" onPress={done} testID="door-FF-17">
              {t('field.job.done')}
            </Button>
          </View>
        }
      >
        {view === null ? <Notice tone="info">{t('field.job.noJob')}</Notice> : null}
        {parts.map((m) => (
          <Card key={m.row.id} testID={`part-${m.row.id}`}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
              <View style={{ flexGrow: 1, flexShrink: 1 }}>
                <AppText variant="body" weight="heavy">
                  {m.row.label}
                </AppText>
                <AppText variant="label" tone="muted">
                  {[m.detail.code, m.detail.serial ? t('field.ff24.serial', { serial: m.detail.serial }) : null, m.detail.van != null ? t('field.ff23.onVan', { count: m.detail.van }) : null]
                    .filter(Boolean)
                    .join(' · ')}
                </AppText>
              </View>
              <Stepper
                value={counts[m.row.id] ?? m.used}
                onChange={(n) => setCounts((c) => ({ ...c, [m.row.id]: n }))}
                label={m.row.label}
                decreaseLabel={t('field.job.fewer', { item: m.row.label })}
                increaseLabel={t('field.job.more', { item: m.row.label })}
                testID={`part-${m.row.id}-qty`}
              />
            </View>
          </Card>
        ))}
        {emptied.map((m) => (
          <Notice key={m.row.id} tone="warning" testID={`part-${m.row.id}-van`}>
            {t('field.ff24.vanDrops', { item: m.row.label })}
          </Notice>
        ))}
      </SheetScreen>
    </JobScreen>
  );
}
