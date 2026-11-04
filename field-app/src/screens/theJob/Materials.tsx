/**
 * FF-23 Materials — what the template expects, what was used, and what was
 * added in the field (requirement 16, requirement 28; US-FLD-016, US-FLD-028).
 *
 *  - A planned part shows used of planned; one the van cannot cover (when the
 *    server sent the van count) is drawn in the danger card *Not on your van*.
 *  - A part not on the template is added with a REASON and shows as a
 *    variance (R7) — *"1 extra, 1 short"* counts both.
 *  - Quantities are tapped, never typed (R38): a stepper. Changes are
 *    captured once, on *Done* — one `material` item per part that moved, not
 *    one per tap.
 *  - A unit price is read and shown up to 4 places (R20) and never computed
 *    with (R16: the field app reads money and never writes it). The currency
 *    is not on the handset, so no symbol is drawn rather than one guessed.
 *
 * ⚠ *Ask the depot* is drawn and has no server door (no depot request exists
 * on the Work server or in the unrouted kinds); it is shown UNAVAILABLE with
 * its reason, and reported, rather than pretending to send.
 *
 * Built from `phone/FF-23-materials.png`. Doors: back and *Done* → FF-15, the
 * scan button → FF-38, *Van* → FF-49.
 */
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import {
  AppText,
  Button,
  Card,
  DashedButton,
  Field,
  FieldGroup,
  Glyph,
  IconButton,
  Kicker,
  Notice,
  Sheet,
  Stepper,
} from '../../components';
import { useTheme } from '../../theme';
import { addMaterial, setMaterialUsed } from './actions';
import { hhmm } from './format';
import { JobScreen, useDoor } from './JobScreen';
import type { MaterialView } from './jobModel';
import { useOpenJob } from './useJob';

/** A unit price as the server sent it, cut to at most 4 places (R20) — on the string, never a float. */
export function unitPrice(decimal: string): string {
  const [int, frac = ''] = decimal.split('.');
  return frac ? `${int}.${frac.slice(0, 4)}` : (int ?? '');
}

export function Materials() {
  const { t } = useTranslation();
  const theme = useTheme();
  const go = useDoor('FF-23');
  const { port, view } = useOpenJob();
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [qty, setQty] = useState(1);
  const [reason, setReason] = useState('');

  const used = (m: MaterialView) => counts[m.row.id] ?? m.used;
  const planned = view?.materials.planned ?? [];
  const added = view?.materials.added ?? [];
  const extra = added.length;
  const short = useMemo(() => planned.filter((m) => (counts[m.row.id] ?? m.used) < m.planned).length, [planned, counts]);

  const done = () => {
    if (port && view) {
      for (const m of view.materials.items) {
        const next = counts[m.row.id];
        if (next !== undefined && next !== m.used) {
          setMaterialUsed(port, view.order.id, { id: m.row.id, detail: m.detail, state: m.row.state }, next, null);
        }
      }
      port.changed();
    }
    setCounts({});
    go('FF-15');
  };

  const saveAdded = () => {
    if (!port || !view || !name.trim() || !reason.trim()) return;
    const position = Math.max(0, ...view.materials.items.map((m) => m.row.position)) + 1;
    addMaterial(port, view.order.id, { label: name, code, qty, reason, position });
    port.changed();
    setAdding(false);
    setName('');
    setCode('');
    setQty(1);
    setReason('');
  };

  const stepper = (m: MaterialView) => (
    <Stepper
      value={used(m)}
      onChange={(n) => setCounts((c) => ({ ...c, [m.row.id]: n }))}
      label={m.row.label}
      decreaseLabel={t('field.job.fewer', { item: m.row.label })}
      increaseLabel={t('field.job.more', { item: m.row.label })}
      testID={`material-${m.row.id}-qty`}
    />
  );

  return (
    <JobScreen
      id="FF-23"
      title={t('field.screen.ff23')}
      back={{ to: 'FF-15', label: t('field.job.backToJob') }}
      trailing={
        <IconButton label={t('field.job.scan')} onPress={() => go('FF-38')} testID="door-FF-38">
          <Glyph name="scan" />
        </IconButton>
      }
      footer={
        <Button grow variant="primary" onPress={done} testID="materials-done">
          {t('field.job.done')}
        </Button>
      }
    >
      {view === null ? <Notice tone="info">{t('field.job.noJob')}</Notice> : null}
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[2] }}>
        <View style={{ flexGrow: 1 }}>
          <Kicker>{t('field.ff23.expects')}</Kicker>
        </View>
        <Button size="sm" onPress={() => go('FF-49')} testID="door-FF-49">
          {t('field.ff23.van')}
        </Button>
      </View>
      {planned.map((m) => {
        const line = [m.detail.code, t('field.ff23.planned', { count: m.planned }), m.detail.van != null ? t('field.ff23.onVan', { count: m.detail.van }) : null]
          .filter(Boolean)
          .join(' · ');
        return (
          <Card
            key={m.row.id}
            tone={m.shortOnVan ? 'danger' : 'plain'}
            title={m.shortOnVan ? t('field.ff23.notOnVan') : undefined}
            testID={`material-${m.row.id}`}
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
              <View style={{ flexGrow: 1, flexShrink: 1 }}>
                <AppText variant="body" weight="heavy">
                  {m.row.label}
                </AppText>
                <AppText variant="label" tone="muted">
                  {line}
                </AppText>
              </View>
              {stepper(m)}
            </View>
            {m.shortOnVan ? (
              <View style={{ gap: theme.space[1] }}>
                <Button size="sm" variant="danger" disabled testID={`material-${m.row.id}-depot`}>
                  {t('field.ff23.askDepot')}
                </Button>
                <AppText variant="label" tone="muted">
                  {t('field.ff23.depotNotYet')}
                </AppText>
              </View>
            ) : null}
          </Card>
        );
      })}
      {added.length > 0 ? <Kicker>{t('field.ff23.addedInField')}</Kicker> : null}
      {added.map((m) => (
        <Card key={m.row.id} tone="info" title={t('field.ff23.notOnTemplate')} testID={`material-${m.row.id}`}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: theme.space[3] }}>
            <View style={{ flexGrow: 1, flexShrink: 1 }}>
              <AppText variant="body" weight="heavy">
                {m.row.label}
              </AppText>
              <AppText variant="label" tone="muted">
                {[m.detail.code, m.detail.unit_cost ? t('field.ff23.each', { price: unitPrice(m.detail.unit_cost) }) : null]
                  .filter(Boolean)
                  .join(' · ')}
              </AppText>
            </View>
            {stepper(m)}
          </View>
          {m.row.reason ? (
            <View style={{ backgroundColor: theme.colors.surface, padding: theme.space[3] }}>
              <AppText variant="label" tone="muted">
                {t('field.ff23.reason')}
              </AppText>
              <AppText variant="body">{m.row.reason}</AppText>
            </View>
          ) : null}
          <AppText variant="label" tone="muted">
            {`${m.detail.added_by ?? ''} · ${hhmm(m.detail.added_at)}`}
          </AppText>
        </Card>
      ))}
      <DashedButton icon={<Glyph name="more" />} label={t('field.ff23.addMaterial')} onPress={() => setAdding(true)} disabled={!port || !view} testID="materials-add" />
      {extra > 0 || short > 0 ? (
        <Notice tone="warning" icon={<Glyph name="warning" />} testID="materials-variance">
          {t('field.ff23.variance', { extra, short })}
        </Notice>
      ) : null}
      <Sheet
        visible={adding}
        onClose={() => setAdding(false)}
        title={t('field.ff23.addMaterial')}
        closeLabel={t('field.job.close')}
        testID="add-material-sheet"
        footer={
          <>
            <Button grow onPress={() => setAdding(false)}>
              {t('field.job.cancel')}
            </Button>
            <Button grow variant="primary" disabled={!name.trim() || !reason.trim()} onPress={saveAdded} testID="add-material-save">
              {t('field.ff23.add')}
            </Button>
          </>
        }
      >
        <View style={{ gap: theme.space[4] }}>
          <Notice tone="info">{t('field.ff18.marked')}</Notice>
          <FieldGroup>
            <Field label={t('field.ff23.part')} value={name} onChangeText={setName} testID="add-material-name" />
            <Field label={t('field.ff23.code')} value={code} onChangeText={setCode} testID="add-material-code" />
            <Field label={t('field.ff18.why')} value={reason} onChangeText={setReason} multiline help={t('field.ff18.officeReads')} testID="add-material-why" />
          </FieldGroup>
          <Stepper
            value={qty}
            onChange={setQty}
            min={1}
            label={t('field.ff23.quantity')}
            decreaseLabel={t('field.job.fewer', { item: name || t('field.ff23.part') })}
            increaseLabel={t('field.job.more', { item: name || t('field.ff23.part') })}
            testID="add-material-qty"
          />
        </View>
      </Sheet>
    </JobScreen>
  );
}
