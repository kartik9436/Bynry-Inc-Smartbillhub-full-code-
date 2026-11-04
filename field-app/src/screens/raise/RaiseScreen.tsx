/**
 * FF-37 Raise — a new order from the field, filled in from where the
 * technician is (US-FLD-011, US-FLD-076; R21, R23, R24, R112).
 *
 *   TEMPLATE — the work. *Change →* opens FF-62. The order takes its OWN
 *     COPY of the template and stamps the version (R112): editing the
 *     template to v4 later changes nothing already raised (TC-3).
 *   *Number arrives when this sends* — never a number the server might not
 *     honour (R24). The technician quotes the address and the time.
 *   CARRIED FROM — the order it was raised from: customer, premise (the
 *     address lives there and nowhere else, hard rule 8), account, meter, and
 *     the technician's position now (requirement 11, `BR-MET-1202`).
 *   WHERE — raised with NO job (Home, Scan, an asset), the place it stands on,
 *     picked by address, account or meter (`RaiseWhere.tsx`). Send waits for
 *     it: the server refuses an order that stands on nothing (`BR-WRK-006`).
 *     The drawing shows only the carried case (DEF-FLD-10603, MQ-036).
 *   HOW URGENT — Normal · Same day · Emergency, the urgencies the story names
 *     (US-FLD-011 §4). The server stores the urgency AS SAID for the office
 *     (`apps/work/field_raise.py`: which priority *Same day* means is unruled).
 *   NOTE — typed or dictated (R38).
 *
 * Send captures ONE outbox item of kind `raise`, which goes through its own
 * door, `POST work/mobile/orders` (`sync/doors.ts`, N16; `raise_from_field`,
 * on the branch since 22df9f422). ⚠ THIS DOCSTRING SAID THAT KIND HAD NO
 * SERVER DOOR UNTIL DEF-FLD-10603 — hard-won law 1.
 *
 * ⚠ **FB-028 (PO 2026-10-31) — THE RAISE IS THE TECHNICIAN'S JOB, AND IT IS
 * SENT AT ONCE.** This read *"A raised reconnect lands pending the office's
 * approval, never auto-scheduled (R23)"* and *"AFTER SEND it goes back … the
 * number shows on Sync once the office has it"*. R23 is superseded: the
 * server assigns the order to whoever raised it, every template. W2 = B:
 * *"the job appears only once the server has it, so with no signal she
 * waits"* — so no provisional job is made here. With a signal Send starts
 * the outbox run at once (`FieldData.sendNow`); with none the item waits in
 * the outbox as before. Either way the screen stays and says so, with
 * *Send now* and *Open job* — the latter live once the server's answer has
 * brought the job onto Today, numbered. The carried job's unit travels with
 * the raise (`unit_id`).
 *
 * ⚠ The board's WHAT IS NEEDED chips (Reconnect · Leak · Damaged meter ·
 * Broken seal · Hazard) are a business list the server does not send; the
 * template already names the work (R112), so they are not built (reported).
 */
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceChips } from '../../components/ChoiceChips';
import { Field } from '../../components/Field';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { ScreenFrame } from '../../components/ScreenFrame';
import { useToastIfMounted } from '../../components/Toast';
import { fromJson } from '../../db/json';
import type { PlaceAnchors } from '../../db/queries/placeSearch';
import * as searchQ from '../../db/queries/templateSearch';
import * as templatesQ from '../../db/queries/workOrderTemplates';
import type { TemplateRow } from '../../db/queries/workOrderTemplates';
import type { CaptureLocation } from '../../sync/outbox';
import { capture } from '../../sync/outbox';
import { useTheme } from '../../theme';
import type { WaveScreenProps } from '../onSite/common';
import { goTo, useNav, useParam, useParams, type Wave } from '../onSite/fieldData';
import { addressLines } from '../onSite/format';
import * as outboxQ from '../../db/queries/outbox';
import { fieldRaiseOf } from '../../db/queries/workOrder';
import { type JobView, loadJob } from '../onSite/job';
import { countsLine } from './PickTemplateScreen';
import { raiseCarry, returnTarget, whereOf, whereParams } from './raiseRoute';
import { PositionLine, RaiseWhere } from './RaiseWhere';

export const URGENCIES = ['normal', 'same_day', 'emergency'] as const;
export type Urgency = (typeof URGENCIES)[number];

export function raiseOrder(
  w: Wave,
  input: {
    template: TemplateRow;
    from: JobView | null;
    /** The place picked on *Where* when there is no job (DEF-FLD-10603). */
    place?: PlaceAnchors | null;
    urgency: Urgency;
    note: string;
    location: CaptureLocation | null;
  },
): string {
  const { template, from } = input;
  const place = from ? null : (input.place ?? null);
  const at = w.clock.now().toISOString();
  return capture(
    w.db,
    w.captor,
    {
      kind: 'raise',
      payload: {
        template_id: template.id,
        template_version: template.version,
        // R112: the order's own copy, so a later edit changes nothing raised.
        template: fromJson(template.body),
        carried_from: from?.order.id ?? null,
        premise_id: from?.order.premise_id ?? place?.premiseId ?? null,
        account_id: from?.order.account_id ?? place?.accountId ?? null,
        customer_id: from?.order.customer_id ?? null,
        asset_id: from?.order.asset_id ?? place?.assetId ?? null,
        // FB-028 — the unit the carried job stands on (the server also copies it).
        unit_id: from ? fieldRaiseOf(from.order).unitId : null,
        urgency: input.urgency,
        note: input.note || null,
        raised_at: at,
      },
      location: input.location,
      apply: () => templatesQ.markUsed(w.db, template.id, at),
    },
    w.deps,
  ).key;
}

export function RaiseScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const params = useParams();
  const toast = useToastIfMounted();
  const templateId = useParam('templateId');
  const carriedFrom = useParam('carriedFrom');
  const [urgency, setUrgency] = useState<Urgency>('normal');
  const [note, setNote] = useState('');
  const [warn, setWarn] = useState<string | null>(null);
  const [location, setLocation] = useState<CaptureLocation | null>(null);
  // FB-028 — the raise just captured (its outbox key), and a re-read tick.
  const [raisedKey, setRaisedKey] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [, setTick] = useState(0);

  useEffect(() => {
    let live = true;
    w.device.location.current().then(
      (fix) => live && setLocation(fix),
      () => undefined,
    );
    return () => {
      live = false;
    };
  }, [w]);

  const template = templateId ? (searchQ.getPublished(w.db, templateId) ?? null) : null;
  const from = loadJob(w, carriedFrom);
  const carry = raiseCarry(params);
  const where = addressLines(from?.premise);
  // No job to carry from: the place picked on *Where* (DEF-FLD-10603).
  const place = from ? null : whereOf(params);
  const back = returnTarget(params);
  const ready = !!template && (!!from || !!place);

  const send = async () => {
    if (!w.sendNow) return;
    setSending(true);
    try {
      await w.sendNow();
    } catch {
      // No signal: the item waits in the outbox; the card says so.
    } finally {
      setSending(false);
      setTick((n) => n + 1);
    }
  };
  // What the server answered for this raise, once it has (W2 = B).
  const row = raisedKey ? outboxQ.getMine(w.s, raisedKey) : undefined;
  let answer: { order_id?: string; order_no?: string | null } | null = null;
  try {
    answer = row?.answer ? (JSON.parse(row.answer) as { order_id?: string; order_no?: string | null }) : null;
  } catch {
    answer = null;
  }
  const arrived = answer?.order_id ? loadJob(w, answer.order_id) : null;

  const dictate = () =>
    w.device.dictation.listen().then(
      (heard) => heard && setNote((now) => (now ? `${now} ${heard}` : heard)),
      () => setWarn(t('field.site.note.noDictation')),
    );

  return (
    <ScreenFrame
      footer={
        <>
          <Button grow onPress={() => goTo(navigation, back)} testID={`door-${back}`}>
            {raisedKey ? t('field.ff37.done') : t('field.site.cancel')}
          </Button>
          <Button
            grow
            variant="primary"
            onPress={() => {
              if (!template || !ready || raisedKey) return;
              const key = raiseOrder(w, { template, from, place, urgency, note: note.trim(), location });
              setRaisedKey(key);
              // W2 = B — with a signal it goes now; without, it waits its turn.
              const online = w.online ? w.online() : true;
              toast(online && w.sendNow ? t('field.ff37.sent') : t('field.ff37.queued'));
              if (online) void send();
            }}
            disabled={!ready || raisedKey !== null}
            testID="send-raise"
          >
            {t('field.ff37.send')}
          </Button>
        </>
      }
    >
      {template ? (
        <Card title={t('field.ff37.template')} testID="template-card" style={{ borderColor: theme.colors.text, borderWidth: theme.borderWidth.emphasis }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: theme.space[2] }}>
            <AppText variant="section" testID="template-name">
              {template.name}
            </AppText>
            <AppText variant="label" tone="muted">
              {t('field.tpl.version', { version: template.version })}
            </AppText>
          </View>
          <AppText variant="label" tone="muted" testID="template-counts">
            {countsLine(t, { ...template, service: null })}
          </AppText>
          <ListRow divider label={t('field.ff37.isTheWork')} value={t('field.ff37.change')} onPress={() => goTo(navigation, 'FF-62', carry)} testID="door-FF-62" />
        </Card>
      ) : (
        <Card title={t('field.ff37.template')} tone="warning" testID="template-card">
          <Button variant="primary" onPress={() => goTo(navigation, 'FF-62', carry)} testID="door-FF-62">
            {t('field.ff37.pick')}
          </Button>
        </Card>
      )}

      {raisedKey ? (
        <Card title={t('field.ff37.raised')} testID="raise-confirmation">
          <AppText variant="body" testID="raise-state">
            {arrived
              ? t('field.ff37.onToday', { number: arrived.order.number ?? answer?.order_no ?? '' })
              : answer?.order_id
                ? t('field.ff37.sentWaiting', { number: answer.order_no ?? '' })
                : sending
                  ? t('field.ff37.sending')
                  : t('field.ff37.waitingSignal')}
          </AppText>
          <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
            {!answer?.order_id ? (
              <Button grow busy={sending} disabled={!w.sendNow} onPress={() => void send()} testID="raise-send-now">
                {t('field.ff37.sendNow')}
              </Button>
            ) : null}
            <Button
              grow
              variant="primary"
              disabled={!arrived}
              onPress={() => arrived && goTo(navigation, 'FF-15', { workOrderId: arrived.order.id })}
              testID="raise-open-job"
            >
              {t('field.ff37.openJob')}
            </Button>
          </View>
        </Card>
      ) : (
        <Notice tone="info" icon={<Mark name="refresh" colour={theme.colors.status.info.fg} />} testID="no-number">
          {t('field.ff37.numberLater')}
        </Notice>
      )}

      {from ? (
        <Card title={t('field.ff37.carriedFrom', { number: from.order.number ?? '' })} testID="carried-card">
          <AppText variant="section">{from.customer?.name ?? ''}</AppText>
          <View>
            <AppText variant="body">{where.line1}</AppText>
            <AppText variant="body">{where.line2}</AppText>
          </View>
          <AppText variant="label" tone="muted">
            {[from.customer?.account_number, from.asset?.serial].filter(Boolean).join(' · ')}
          </AppText>
          <PositionLine location={location} />
        </Card>
      ) : (
        <RaiseWhere w={w} place={place} location={location} onPick={(picked) => navigation.setParams(whereParams(picked) as never)} />
      )}

      <Card title={t('field.ff37.urgent')}>
        <ChoiceChips
          fill
          label={t('field.ff37.urgent')}
          segments={URGENCIES.map((u) => ({ id: u, label: t(`field.ff37.urgency.${u}`) }))}
          active={urgency}
          onSelect={(id) => setUrgency(id as Urgency)}
          testID="urgency"
        />
      </Card>

      <Card title={t('field.ff37.note')}>
        <Field label={t('field.ff37.note')} value={note} onChangeText={setNote} multiline testID="raise-note" />
        <Button size="sm" onPress={() => void dictate()} icon={<Mark name="mic" />} testID="dictate">
          {t('field.site.note.dictate')}
        </Button>
        {warn ? <Notice tone="warning">{warn}</Notice> : null}
      </Card>
    </ScreenFrame>
  );
}
