/**
 * FF-38 Scan — point at the meter's code; the app says whether it is this
 * job's meter and opens it (US-FLD-010, US-FLD-038, US-FLD-084; R43, R83).
 *
 *   The camera stays open (continuous mode): each code that comes into view
 *   replaces the last result, no relaunch.
 *   Two modes, as drawn: Barcode (Code 128, Code 39, ITF, UPC-A, EAN-13) and
 *   QR (QR, Data Matrix). The torch is one tap (TC-3).
 *   A code is matched serial, then badge, then device ID — one order,
 *   everywhere (`asset.matchScannedCode`), so the same sticker always finds
 *   the same meter. Scanning changes nothing (TC-3 of US-FLD-010): it reads.
 *   *Enter manually* is the damaged-label path and the whole path when the
 *   handset cannot scan.
 *   NOT ON THE PHONE (FB-009, DEF-FLD-10634; MQ-046): the phone holds only
 *   today's job meters and the assigned routes' meters, so a code it does not
 *   know is asked of the server — the same search FF-41 asks (`w.assets`,
 *   `GET work/mobile/assets/search`, N9) — and a hit whose serial or asset
 *   number IS the code is the meter, kept on the phone and opened exactly as
 *   FF-41 opens one (`serverAsset.ts`). Only an exact hit: the server also
 *   matches prefixes and addresses, and a scan is one meter. No signal: *"Not
 *   on this phone."* with FF-41's own *"A signal searches the whole
 *   utility."* Until then this screen said *"No meter with this code"* for a
 *   meter the utility has (reader Sam Curran, `AR-TEST-SN1`, 2026-10-26).
 *
 * ⚠ No scanner package is installed: the camera is `ScannerPort`
 * (`scanner.ts`; reported).
 */
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { View } from 'react-native';

import { AppText } from '../../components/AppText';
import { Button, IconButton } from '../../components/Button';
import { ChoiceChips } from '../../components/ChoiceChips';
import { Field } from '../../components/Field';
import { Mark } from '../../components/Mark';
import { Notice } from '../../components/Notice';
import { Sheet } from '../../components/Sheet';
import * as assetQ from '../../db/queries/asset';
import * as workOrderQ from '../../db/queries/workOrder';
import type { WireAssetHit } from '../../sync/fieldApi';
import { useTheme } from '../../theme';
import type { WaveScreenProps } from '../onSite/common';
import { goTo, useNav, useParam } from '../onSite/fieldData';
import { FORMATS_BY_MODE, type ScanMode } from './scanner';
import { exactServerMatch, isNoSignal, keepServerAsset } from './serverAsset';

/** `hit` is a meter only the server held; it is kept on the phone when opened. */
type Result =
  | { kind: 'match' | 'other'; code: string; assetId: string; hit?: WireAssetHit }
  | { kind: 'none' | 'asking' | 'offline' | 'failed'; code: string };

export function ScanScreen({ w }: WaveScreenProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const navigation = useNav();
  const workOrderId = useParam('workOrderId');
  const [mode, setMode] = useState<ScanMode>('barcode');
  const [torch, setTorch] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState('');

  const order = workOrderId ? workOrderQ.getMine(w.s, workOrderId) : undefined;
  const jobAsset = order?.asset_id ? assetQ.get(w.db, order.asset_id) : undefined;

  // Each code supersedes the last: an answer for an older code is dropped.
  const asked = useRef(0);
  const finder = w.assets ?? null;

  const matched = (code: string, assetId: string, hit?: WireAssetHit): Result => ({
    kind: !jobAsset || assetId === jobAsset.id ? 'match' : 'other',
    code,
    assetId,
    ...(hit ? { hit } : {}),
  });

  const resolve = (raw: string) => {
    const code = raw.trim();
    const n = ++asked.current;
    const found = assetQ.matchScannedCode(w.db, code);
    if (found) return setResult(matched(code, found.asset.id));
    if (!finder) return setResult({ kind: 'none', code });
    setResult({ kind: 'asking', code });
    finder.search(code, 1).then(
      (r) => {
        if (n !== asked.current) return;
        const hit = exactServerMatch(r.hits, code);
        setResult(hit ? matched(code, hit.id, hit) : { kind: 'none', code });
      },
      (err: unknown) => {
        if (n !== asked.current) return;
        setResult({ kind: isNoSignal(err) ? 'offline' : 'failed', code });
      },
    );
  };

  useEffect(() => {
    if (!w.scanner.available) return undefined;
    return w.scanner.start(FORMATS_BY_MODE[mode], (c) => resolve(c.value));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [w, mode, jobAsset?.id]);

  const Preview = w.scanner.Preview;
  const ink = theme.colors.toastText;

  return (
    <View style={{ flex: 1, backgroundColor: theme.colors.toastFill }}>
      <View style={{ flexDirection: 'row', justifyContent: 'flex-end', padding: theme.space[2] }}>
        <IconButton
          label={torch ? t('field.ff38.torchOff') : t('field.ff38.torchOn')}
          disabled={!w.scanner.available}
          onPress={() => {
            w.scanner.setTorch(!torch);
            setTorch(!torch);
          }}
          testID="torch"
        >
          <Mark name="torch" colour={ink} />
        </IconButton>
      </View>
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', gap: theme.space[3], padding: theme.space[4] }}>
        {Preview ? <Preview /> : null}
        <AppText variant="section" style={{ color: ink, textAlign: 'center' }}>
          {w.scanner.available ? t('field.ff38.point') : t('field.ff38.cannotScan')}
        </AppText>
        {w.scanner.available ? (
          <ChoiceChips
            label={t('field.ff38.mode')}
            segments={[
              { id: 'barcode', label: t('field.ff38.barcode') },
              { id: 'qr', label: t('field.ff38.qr') },
            ]}
            active={mode}
            onSelect={(id) => setMode(id === 'qr' ? 'qr' : 'barcode')}
            testID="scan-mode"
          />
        ) : null}
      </View>

      <View style={{ backgroundColor: theme.colors.card, padding: theme.space[4], gap: theme.space[3] }} testID="scan-result">
        {result?.kind === 'match' ? (
          <Notice tone="success" icon={<Mark name="check" colour={theme.colors.status.success.fg} />} testID="scan-match">
            {jobAsset ? t('field.ff38.matches') : t('field.ff38.found')}
          </Notice>
        ) : null}
        {result?.kind === 'other' ? (
          <Notice tone="warning" testID="scan-other">
            {t('field.ff38.notThisJob')}
          </Notice>
        ) : null}
        {result?.kind === 'asking' ? (
          <Notice tone="info" testID="scan-asking">
            {t('field.ff38.asking')}
          </Notice>
        ) : null}
        {result?.kind === 'offline' ? (
          <Notice tone="info" icon={<Mark name="info" colour={theme.colors.status.info.fg} />} testID="scan-offline">
            {`${t('field.ff38.notOnPhone')} ${t('field.ff41.signal')}`}
          </Notice>
        ) : null}
        {result?.kind === 'failed' ? (
          <Notice tone="danger" testID="scan-failed">
            {t('field.ff38.searchFailed')}
          </Notice>
        ) : null}
        {result?.kind === 'none' ? (
          <Notice tone="danger" testID="scan-none">
            {t('field.ff38.noMeter')}
          </Notice>
        ) : null}
        {result ? (
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: theme.space[3] }}>
            <View>
              <AppText variant="label" tone="muted">
                {t('field.ff38.scanned')}
              </AppText>
              <AppText variant="section" testID="scanned-code">
                {result.code}
              </AppText>
            </View>
            {jobAsset ? (
              <View style={{ alignItems: 'flex-end' }}>
                <AppText variant="label" tone="muted">
                  {t('field.ff38.onJob')}
                </AppText>
                <AppText variant="section">{jobAsset.serial ?? '—'}</AppText>
              </View>
            ) : null}
          </View>
        ) : null}
        <View style={{ flexDirection: 'row', gap: theme.space[2] }}>
          {result && (result.kind === 'match' || result.kind === 'other') ? (
            <Button
              variant="primary"
              grow
              onPress={() => {
                if (result.hit) keepServerAsset(w, result.hit);
                goTo(navigation, 'FF-39', { assetId: result.assetId, ...(workOrderId ? { workOrderId } : {}) });
              }}
              testID="open-asset"
            >
              {t('field.ff38.openAsset')}
            </Button>
          ) : null}
          <Button grow onPress={() => setTyping(true)} testID="enter-manually">
            {t('field.ff38.enterManually')}
          </Button>
        </View>
      </View>

      <Sheet
        visible={typing}
        onClose={() => setTyping(false)}
        closeLabel={t('field.site.cancel')}
        title={t('field.ff38.enterManually')}
        testID="manual-sheet"
        footer={
          <Button
            variant="primary"
            disabled={typed.trim() === ''}
            onPress={() => {
              resolve(typed);
              setTyping(false);
            }}
            testID="manual-find"
          >
            {t('field.ff38.find')}
          </Button>
        }
      >
        <Field label={t('field.ff38.code')} value={typed} onChangeText={setTyped} help={t('field.ff38.codeHelp')} testID="manual-code" />
      </Sheet>
    </View>
  );
}
