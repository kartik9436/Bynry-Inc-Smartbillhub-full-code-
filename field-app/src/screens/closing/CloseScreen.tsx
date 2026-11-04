/**
 * FF-34 Close — the outcome, what the debrief says, the signature, and the
 * close itself (US-FLD-014; R4, R8, R110, R17, R111).
 *
 *   FOUR OUTCOMES (R4): Passed · Partly done · Failed · Waiting on someone,
 *     sent as the server's own tokens (`apps/metering/connections.py`
 *     WORK_ORDER_OUTCOMES: passed · partially_done · failed ·
 *     waiting_on_someone_else).
 *   A FIFTH, NOT DONE — PAYMENT RECEIVED (FB-013, PO ruling (b) 2026-10-28):
 *     offered ONLY when FF-27 stopped the step on a fresh cleared balance and
 *     handed over what it saw (`paymentReceived`); chosen already, with the
 *     remark *Customer has paid. Not disconnected.* written and editable, the
 *     photo optional. The snapshot travels as `field_data.money_seen` — the
 *     server refuses the paid close without it — and the remark as `reason`.
 *   A REQUIRED PHOTO MISSING stops the close and says how many (the board's
 *     red line and greyed button). Short of a task's COUNT is warned, never
 *     blocked (R110).
 *   THE LEAD CLOSES (R8): anyone else sees why the button is greyed.
 *   WHAT EARLIER SCREENS KNEW rides on the close for the office: FF-27's
 *     balance read more than five minutes before (`money_unverified`, E2E-12
 *     — *"the office sees the word unverified"*) and FF-61's unpaid fee
 *     (`reconnect_fee_outstanding`, US-FLD-075 TC-2). Read only (R16): these
 *     are the figures the technician SAW, never a money write.
 *
 *   ARRIVED AND FINISHED (DEF-WRK-4127, PO 2026-10-05 *"allow technicain to
 *     fill in time"*; DEF-FLD-10626, PO 2026-10-27): both shown, pre-filled,
 *     moved with − / + in five-minute steps (R38: taps, never types), and
 *     ALWAYS both sent — the server refuses half a pair (*"Enter both
 *     times."*), which is what every close did when Arrived was never tapped.
 *     Arrived defaults to the crew arrival, else the first labour start, else
 *     the FIRST WORK SAVED ON THE JOB (`firstWorkAt`), else five minutes
 *     before Finished (our judgment: a close with no work saved at all still
 *     sends a pair the technician can see and move). Finished defaults to
 *     now. Arrived stays a minute before Finished and Finished never passes
 *     now, so the pair is always one the server accepts.
 *
 * The close is one outbox item of kind `close`, and on the handset the order
 * is marked closed with its outcome and the act is stamped on the activity
 * (R10), all in one transaction. The board's link then opens FF-15.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Pressable, View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { Field } from '../../components/Field';
import { ListRow } from '../../components/ListRow';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { RadioList } from '../../components/RadioList';
import { GroupLabel, ScreenFrame } from '../../components/ScreenFrame';
import { Stepper } from '../../components/Stepper';
import * as activityQ from '../../db/queries/activity';
import * as crewOrderQ from '../../db/queries/crewTimeOrder';
import * as jobTimesQ from '../../db/queries/jobTimes';
import * as evidenceQ from '../../db/queries/woItemEvidence';
import * as woItemQ from '../../db/queries/woItem';
import * as woReadingQ from '../../db/queries/woReading';
import * as closedQ from '../../db/queries/workOrderClosed';
import { capture } from '../../sync/outbox';
import { useTheme } from '../../theme';
import { NotOnPhone, type WaveScreenProps } from '../onSite/common';
import { crewLines } from '../onSite/crew';
import { goTo, useNav, type Wave } from '../onSite/fieldData';
import { formatClock, formatMinutes } from '../onSite/format';
import { leadOf, loadJob, myName } from '../onSite/job';
import { REQUIRED_PHOTO_BLOCKS_CLOSE } from '../theJob/jobModel';
import { asParams, clearDraft, type CloseDraft, useCloseDraft } from './draft';

/** R4, in the server's tokens. */
export const OUTCOMES = [
  { id: 'passed', key: 'field.site.outcome.passed' },
  { id: 'partially_done', key: 'field.site.outcome.partially_done' },
  { id: 'failed', key: 'field.site.outcome.failed' },
  { id: 'waiting_on_someone_else', key: 'field.site.outcome.waiting_on_someone_else' },
  // FB-013 (PO ruling (b) 2026-10-28) — offered ONLY when FF-27 stopped the
  // step on a FRESH cleared balance (the draft carries `paymentReceived`).
  { id: 'not_done_payment_received', key: 'field.site.outcome.not_done_payment_received' },
] as const;
export type Outcome = (typeof OUTCOMES)[number]['id'];

/** FB-013 — the paid outcome's token (`apps/work/connection_models.py`). */
export const PAID_OUTCOME: Outcome = 'not_done_payment_received';

/** The outcomes this close may offer: the paid one only with a paid snapshot. */
export function offeredOutcomes(draft: CloseDraft) {
  return OUTCOMES.filter((o) => o.id !== PAID_OUTCOME || draft.paymentReceived !== undefined);
}

/** The times move in steps of this many minutes. */
export const TIME_STEP_MINUTES = 5;
const MINUTE_MS = 60 * 1000;
const toMinute = (at: string | Date) => Math.floor(new Date(at).getTime() / MINUTE_MS);
const fromMinute = (m: number) => new Date(m * MINUTE_MS).toISOString();

/** What a close says about when the technician was on site — both, always. */
export interface CloseTimes {
  arrivedAt: string;
  finishedAt: string;
}

/**
 * FF-34's pre-filled pair (DEF-FLD-10626): Arrived from the crew arrival, else
 * the first labour start, else the first work saved on the job, else five
 * minutes before Finished; Finished is now. Whole minutes, Arrived strictly
 * before Finished.
 */
export function defaultCloseTimes(w: Wave, workOrderId: string): CloseTimes {
  const now = w.clock.now();
  const mine = crewLines(crewOrderQ.listForOrder(w.s, workOrderId), now).find((l) => l.personId === w.me);
  const finished = toMinute(now);
  const seen = mine?.arrivedAt ?? mine?.labourFrom ?? jobTimesQ.firstWorkAt(w.s, workOrderId);
  const arrived = seen ? Math.min(toMinute(seen), finished - 1) : finished - TIME_STEP_MINUTES;
  return { arrivedAt: fromMinute(arrived), finishedAt: fromMinute(finished) };
}

export function closeJob(
  w: Wave,
  draft: CloseDraft,
  outcome: Outcome,
  times: CloseTimes,
  photosMissing = 0,
  remark?: string,
): string {
  const at = w.clock.now().toISOString();
  const author = myName(w);
  const fieldData: Record<string, unknown> = {};
  if (outcome === PAID_OUTCOME && draft.paymentReceived) {
    // FB-013 — what the phone SAW (the server refuses the paid close without
    // it) and the technician's remark, which the office reads as the reason.
    fieldData.money_seen = draft.paymentReceived;
    if (remark && remark.trim()) fieldData.reason = remark.trim();
  }
  if (draft.debrief?.problem) fieldData.problem_found = draft.debrief.problem;
  if (draft.debrief?.done) fieldData.what_i_did = draft.debrief.done;
  if (draft.moneyUnverified) fieldData.money_unverified = draft.moneyUnverified;
  if (draft.feeOutstanding) fieldData.reconnect_fee_outstanding = draft.feeOutstanding;
  // PO 2026-10-21: a required photo missing warns and never blocks — the gap
  // travels with the close so the office sees it.
  // FB-013: on a paid close the photo is optional, so no gap is reported.
  if (photosMissing > 0 && outcome !== PAID_OUTCOME) fieldData.required_photos_missing = photosMissing;
  return capture(
    w.db,
    w.captor,
    {
      kind: 'close',
      workOrderId: draft.workOrderId,
      payload: { outcome, arrived_at: times.arrivedAt, finished_at: times.finishedAt, field_data: fieldData },
      apply: (s, key) => {
        // FB-030 — the handset KEEPS what the close said (the debrief and who
        // signed, and when) for the record FF-35 opens; it used to discard it.
        const sig = draft.signature;
        closedQ.recordClose(s, draft.workOrderId, outcome, at, {
          problem: draft.debrief?.problem ?? '',
          done: draft.debrief?.done ?? '',
          signer: !sig
            ? null
            : sig.kind === 'signed'
              ? { kind: 'signed', name: sig.name, at: sig.at ?? null }
              : { kind: 'refused', reason: sig.reason, at: sig.at ?? null },
        });
        if (draft.moneyUnverified) {
          activityQ.insert(s, {
            id: w.newId(),
            workOrderId: draft.workOrderId,
            kind: 'status',
            status: 'proceeded_unverified',
            author,
            at,
            outboxId: key,
          });
        }
        activityQ.insert(s, {
          id: w.newId(),
          workOrderId: draft.workOrderId,
          kind: 'status',
          status: 'closed',
          text: outcome,
          author,
          at,
          outboxId: key,
        });
      },
    },
    w.deps,
  ).key;
}

export function CloseScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const draft = useCloseDraft(w);
  const [picked, setOutcome] = useState<Outcome | null>(null);
  // FB-013 — a stopped step arrives with the paid outcome chosen and its
  // remark written; both stay editable.
  const outcome = picked ?? (draft?.paymentReceived ? PAID_OUTCOME : null);
  const [remark, setRemark] = useState<string | null>(null);
  const job = loadJob(w, draft?.workOrderId ?? null);
  // The pre-filled pair until the technician moves one (Finished then stops following the clock).
  const [edited, setTimes] = useState<CloseTimes | null>(null);
  const times = edited ?? (job ? defaultCloseTimes(w, job.order.id) : null);
  if (!job || !draft || !times) return <NotOnPhone />;

  const workOrderId = job.order.id;
  const needs = evidenceQ.photoNeeds(w.s, workOrderId);
  const missing = needs.filter((n) => n.photos === 0).length;
  const short = needs.filter((n) => n.photos > 0 && n.photos < n.photo_min_count).length;
  const isLead = leadOf(job) === w.me;
  const mine = crewLines(crewOrderQ.listForOrder(w.s, workOrderId), w.clock.now()).find((l) => l.personId === w.me);
  const parts = woItemQ.listForOrder(w.s, workOrderId, 'material');
  const readings = woReadingQ.listForOrder(w.s, workOrderId);
  const flagged = readings.filter((r) => r.flagged === 1).length;
  const paid = outcome === PAID_OUTCOME;
  const remarkText = remark ?? t('field.ff34.paidRemark');
  const canClose = outcome !== null && isLead && (paid || !REQUIRED_PHOTO_BLOCKS_CLOSE || missing === 0);

  return (
    <ScreenFrame
      footer={
        <Button
          variant="primary"
          grow
          disabled={!canClose}
          onPress={() => {
            if (!outcome) return;
            closeJob(w, draft, outcome, times, missing, paid ? remarkText : undefined);
            // Captured: the typed draft has done its job.
            clearDraft(w.prefs, w.me, workOrderId);
            goTo(navigation, 'FF-15', { workOrderId });
          }}
          testID="close-job"
        >
          {t('field.ff34.closeJob')}
        </Button>
      }
    >
      {missing > 0 && !paid ? (
        <Notice
          tone={REQUIRED_PHOTO_BLOCKS_CLOSE ? 'danger' : 'warning'}
          icon={<Mark name="alert" colour={theme.colors.status[REQUIRED_PHOTO_BLOCKS_CLOSE ? 'danger' : 'warning'].fg} />}
          testID="photo-missing"
        >
          {t('field.ff34.photoMissing', { count: missing })}
        </Notice>
      ) : null}
      {short > 0 ? (
        <Notice tone="warning" testID="photo-short">
          {t('field.ff34.photoShort', { count: short })}
        </Notice>
      ) : null}
      {!isLead ? (
        <Notice tone="info" testID="lead-closes">
          {t('field.ff29.leadCloses')}
        </Notice>
      ) : null}

      <GroupLabel>{t('field.ff34.outcome')}</GroupLabel>
      <RadioList
        label={t('field.ff34.outcome')}
        options={offeredOutcomes(draft).map((o) => ({ id: o.id, label: t(o.key) }))}
        value={outcome}
        onChange={(id) => setOutcome(id as Outcome)}
        testID="outcome"
      />
      {paid ? (
        <Field label={t('field.ff34.remark')} value={remarkText} onChangeText={setRemark} multiline testID="remark" />
      ) : null}

      <Card title={t('field.ff34.times')} testID="times-card">
        {(
          [
            ['arrived', times.arrivedAt, toMinute(times.arrivedAt) - 24 * 60, toMinute(times.finishedAt) - 1],
            ['finished', times.finishedAt, toMinute(times.arrivedAt) + 1, toMinute(w.clock.now())],
          ] as const
        ).map(([which, at, min, max]) => (
          <View
            key={which}
            style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: theme.space[3] }}
          >
            <AppText variant="body">{t(`field.ff34.${which}`)}</AppText>
            <Stepper
              label={t(`field.ff34.${which}`)}
              decreaseLabel={t('field.ff34.earlier')}
              increaseLabel={t('field.ff34.later')}
              value={toMinute(at)}
              min={min}
              max={max}
              step={TIME_STEP_MINUTES}
              format={(m) => formatClock(fromMinute(m))}
              onChange={(m) =>
                setTimes(which === 'arrived' ? { ...times, arrivedAt: fromMinute(m) } : { ...times, finishedAt: fromMinute(m) })
              }
              testID={which}
            />
          </View>
        ))}
      </Card>

      <Card title={t('field.ff34.debrief')} testID="debrief-card">
        <ListRow label={t('field.ff29.labour')} value={formatMinutes(mine?.labourMinutes ?? 0)} />
        <ListRow
          divider
          label={t('field.ff34.parts')}
          value={parts.length > 0 ? [String(parts.length), parts[0]?.label].filter(Boolean).join(' · ') : '0'}
        />
        <ListRow
          divider
          label={t('field.ff34.readings')}
          value={
            <AppText variant="body" weight="heavy" style={flagged > 0 ? { color: theme.colors.statusInk.warning } : undefined} testID="readings-value">
              {flagged > 0 ? t('field.ff34.readingsFlagged', { count: readings.length, flagged }) : String(readings.length)}
            </AppText>
          }
        />
      </Card>

      <Card title={t('field.ff34.signature')} testID="signature-card">
        {draft.signature ? (
          <ListRow
            label={draft.signature.kind === 'signed' ? t('field.ff34.signedBy', { name: draft.signature.name }) : t('field.ff34.refusedWhy', { reason: draft.signature.reason })}
            leading={<Mark name="check" colour={theme.colors.statusInk.success} />}
            testID="signature-done"
          />
        ) : (
          <>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t('field.ff34.askToSign')}
              onPress={() => goTo(navigation, 'FF-33', asParams(draft))}
              testID="door-FF-33"
              style={{
                minHeight: theme.touch.primary * 2,
                alignItems: 'center',
                justifyContent: 'center',
                borderWidth: theme.borderWidth.control,
                borderStyle: 'dashed',
                borderColor: theme.colors.controlBorder,
                backgroundColor: theme.colors.surface,
              }}
            >
              <AppText variant="body" tone="muted">
                {t('field.ff34.askToSign')}
              </AppText>
            </Pressable>
            <Button size="sm" onPress={() => goTo(navigation, 'FF-33', { ...asParams(draft), tab: 'refused' })} testID="record-refused">
              {t('field.ff34.refused')}
            </Button>
          </>
        )}
      </Card>
    </ScreenFrame>
  );
}
