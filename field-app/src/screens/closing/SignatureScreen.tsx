/**
 * FF-33 Signature — the customer signs with a printed name, or the refusal
 * is recorded with its reason and a photograph of the door hanger
 * (US-FLD-014; requirement 14; R30, BR-WRK-046).
 *
 *   SIGNED — printed name + the image, stamped *Captured by D. Ortiz · 20 Oct
 *     09:58*. No name, no signature (TC-4); no ink, no signature.
 *   REFUSED — a reason and the door-hanger photo; no photo, no refusal
 *     (TC-3). Never both (the server's CHECK says so too).
 *
 * Either is captured as ONE outbox item of kind `signature` with its image
 * declared beside it (R123), then FF-34 opens with the draft.
 *
 * ⚠ THE PHOTO IS NAMED BY THE PHONE'S OWN PHOTO ID, WITH ITS HASH
 *   (DEF-WRK-10625). The signature item carries `door_hanger_photo_id` (a
 *   refusal) or `image_photo_id` (the signed mark) and the matching
 *   `*_sha256`; the declaration follows as its own `photo` item and the bytes
 *   upload later on signal. The server makes the link from the signature item
 *   itself when it arrives first, so the order of the two never matters. Until
 *   2026-10-27 the item named no photograph at all, and the server refused
 *   every refusal: *"A refusal needs a door-hanger photo."*
 * ⚠ The pad is `SignaturePort` — the shipped app wires a real one
 *   (`device/native/signature.tsx`, DEF-FLD-10627).
 * ⚠ The refusal reasons are the three the story names (US-FLD-014 §4); the
 *   server sends no reason list for a signature refusal (reported). The
 *   reason travels as words, the way `decline_reason` stores it.
 * ⚠ "Captured by" is the technician's NAME, never an id (B14 rule 31,
 *   DEF-FLD-10628); with no name known it reads the time alone.
 */
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button } from '../../components/Button';
import { Card } from '../../components/Card';
import { ChoiceChips } from '../../components/ChoiceChips';
import { Field } from '../../components/Field';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { RadioList } from '../../components/RadioList';
import { ScreenFrame } from '../../components/ScreenFrame';
import { capture } from '../../sync/outbox';
import { useTheme } from '../../theme';
import { NotOnPhone, type WaveScreenProps } from '../onSite/common';
import { goTo, useNav, useParam, type Wave } from '../onSite/fieldData';
import { formatStamp } from '../onSite/format';
import { loadJob, myName } from '../onSite/job';
import type { TakenPhoto } from '../onSite/ports';
import { asParams, useCloseDraft } from './draft';

export const REFUSAL_REASONS = ['nobodyHome', 'declined', 'couldNotSign'] as const;

export function captureSigned(w: Wave, workOrderId: string, name: string, image: TakenPhoto): string {
  if (!name.trim()) throw new Error('a signature needs a printed name (R30)');
  return capture(
    w.db,
    w.captor,
    {
      kind: 'signature',
      workOrderId,
      payload: {},
      payloadFor: ([photoId]) => ({
        refused: false,
        printed_name: name.trim(),
        signed_at: w.clock.now().toISOString(),
        image_photo_id: photoId,
        image_sha256: image.sha256,
      }),
      photos: [{ ...image, target: {} }],
    },
    w.deps,
  ).key;
}

export function captureRefusal(w: Wave, workOrderId: string, reason: string, hanger: TakenPhoto): string {
  if (!reason.trim()) throw new Error('a refusal needs its reason (R30)');
  return capture(
    w.db,
    w.captor,
    {
      kind: 'signature',
      workOrderId,
      payload: {},
      payloadFor: ([photoId]) => ({
        refused: true,
        decline_reason: reason,
        signed_at: w.clock.now().toISOString(),
        door_hanger_photo_id: photoId,
        door_hanger_sha256: hanger.sha256,
      }),
      photos: [{ ...hanger, target: {} }],
    },
    w.deps,
  ).key;
}

export function SignatureScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const draft = useCloseDraft(w);
  const job = loadJob(w, draft?.workOrderId ?? null);
  const [tab, setTab] = useState<'signed' | 'refused'>(useParam('tab') === 'refused' ? 'refused' : 'signed');
  const [name, setName] = useState(job?.customer?.name ?? '');
  const [ink, setInk] = useState(false);
  const [clearToken, setClearToken] = useState(0);
  const [reason, setReason] = useState<string | null>(null);
  const [hanger, setHanger] = useState<TakenPhoto | null>(null);
  const [note, setNote] = useState<string | null>(null);
  if (!job || !draft) return <NotOnPhone />;

  const Pad = w.signature.Pad;
  const who = myName(w);
  const stamp = who
    ? t('field.ff33.capturedBy', { name: who, stamp: formatStamp(w.clock.now()) })
    : t('field.ff33.capturedAt', { stamp: formatStamp(w.clock.now()) });

  const acceptSignature = async () => {
    const image = await w.signature.exportImage();
    if (!image) {
      setNote(t('field.ff33.noInk'));
      return;
    }
    captureSigned(w, job.order.id, name, image);
    goTo(navigation, 'FF-34', asParams({ ...draft, signature: { kind: 'signed', name: name.trim(), at: w.clock.now().toISOString() } }));
  };

  const recordRefusal = () => {
    if (!reason || !hanger) return;
    const words = t(`field.ff33.reason.${reason}`);
    captureRefusal(w, job.order.id, words, hanger);
    goTo(navigation, 'FF-34', asParams({ ...draft, signature: { kind: 'refused', reason: words, at: w.clock.now().toISOString() } }));
  };

  const snapHanger = () =>
    w.device.camera.take().then(
      (p) => p && setHanger(p),
      () => setNote(t('field.site.note.noCamera')),
    );

  return (
    <ScreenFrame
      header={
        <ChoiceChips
          fill
          label={t('field.ff33.how')}
          segments={[
            { id: 'signed', label: t('field.ff33.signed') },
            { id: 'refused', label: t('field.ff33.refused') },
          ]}
          active={tab}
          onSelect={(id) => setTab(id === 'refused' ? 'refused' : 'signed')}
          testID="sig-tab"
        />
      }
      footer={
        tab === 'signed' ? (
          <Button variant="primary" grow disabled={!name.trim() || !ink || !Pad} onPress={() => void acceptSignature()} testID="accept-signature">
            {t('field.ff33.accept')}
          </Button>
        ) : (
          <Button variant="primary" grow disabled={!reason || !hanger} onPress={recordRefusal} testID="record-refusal">
            {t('field.ff33.recordRefusal')}
          </Button>
        )
      }
    >
      {note ? <Notice tone="warning">{note}</Notice> : null}
      {tab === 'signed' ? (
        <>
          <Card>
            <Field label={t('field.ff33.printedName')} value={name} onChangeText={setName} testID="printed-name" />
          </Card>
          <Card title={t('field.ff33.signBelow')} testID="pad-card">
            {Pad ? (
              <View
                style={{
                  minHeight: theme.touch.primary * 3,
                  borderWidth: theme.borderWidth.control,
                  borderStyle: 'dashed',
                  borderColor: theme.colors.controlBorder,
                  backgroundColor: theme.colors.surface,
                }}
              >
                <Pad onInk={setInk} clearToken={clearToken} label={t('field.ff33.signBelow')} />
              </View>
            ) : (
              <Notice tone="warning" testID="no-pad">
                {t('field.ff33.noPad')}
              </Notice>
            )}
            <Button
              size="sm"
              disabled={!Pad}
              onPress={() => {
                setClearToken((n) => n + 1);
                setInk(false);
              }}
              testID="clear-pad"
            >
              {t('field.ff33.clear')}
            </Button>
          </Card>
        </>
      ) : (
        <>
          <Card title={t('field.ff33.why')}>
            <RadioList
              label={t('field.ff33.why')}
              options={REFUSAL_REASONS.map((id) => ({ id, label: t(`field.ff33.reason.${id}`) }))}
              value={reason}
              onChange={setReason}
              testID="refusal-reason"
            />
          </Card>
          <Card title={t('field.ff33.doorHanger')}>
            {hanger ? (
              <AppText variant="body" testID="hanger-taken">
                {t('field.ff33.hangerTaken')}
              </AppText>
            ) : null}
            <Button size="sm" onPress={() => void snapHanger()} icon={<Mark name="camera" />} testID="hanger-photo">
              {hanger ? t('field.ff33.retake') : t('field.ff33.photograph')}
            </Button>
          </Card>
        </>
      )}
      <AppText variant="label" tone="muted" testID="captured-by">
        {stamp}
      </AppText>
    </ScreenFrame>
  );
}
