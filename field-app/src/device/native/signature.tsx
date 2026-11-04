/**
 * THE REAL SIGNING PAD behind `SignaturePort` (`../signature.ts`) —
 * `react-native-signature-canvas` drawing in a `react-native-webview`
 * (DEF-FLD-10627; PO 2026-10-27, *"start ... the signature fix"*: install the
 * drawing pad now).
 *
 * `Pad` is the surface the customer signs on; `exportImage()` asks the pad for
 * its ink, writes it as a PNG file in the app's cache and answers it as a
 * `TakenPhoto` — path, sha256 and size — so the outbox carries the mark EXACTLY
 * as it carries any photograph: declared with the data, the bytes uploaded
 * later on signal (BR-WRK-062). Nothing here sends anything.
 *
 * The paper is always white and the ink always black, whatever the theme: the
 * PNG is what the office sees on the order, and a light mark on a dark page
 * reads as nothing once it leaves the phone.
 *
 * ⚠ ONE PAD AT A TIME. FF-33 draws one pad; the port remembers the mounted one
 * so `exportImage()` can read it. A second mounted pad would take over the
 * reference, which no screen does.
 */
import * as Crypto from 'expo-crypto';
import * as FileSystem from 'expo-file-system';
import { useEffect, useRef } from 'react';
import { View } from 'react-native';
import SignatureView, { type SignatureViewRef } from 'react-native-signature-canvas';

import { color } from '../../tokens';
import type { TakenPhoto } from '../ports';
import type { SignaturePadProps, SignaturePort } from '../signature';
import { base64Bytes } from './camera';

/** How long `exportImage()` waits for the pad's answer before calling it empty. */
export const EXPORT_WAIT_MS = 5000;

/** The pad's own buttons are hidden: FF-33 draws *Clear* and *Accept* itself. */
const WEB_STYLE = `.m-signature-pad { box-shadow: none; border: none; margin: 0; }
.m-signature-pad--body { border: none; }
.m-signature-pad--footer { display: none; margin: 0; }
body, html { height: 100%; margin: 0; background: ${color.white}; }`;

function hex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, '0')).join('');
}

/** `data:image/png;base64,…` → the PNG on disk, hashed. Null for no ink. */
export async function writeSignature(dataUrl: string, now: () => number = Date.now): Promise<TakenPhoto | null> {
  const comma = dataUrl.indexOf(',');
  const b64 = comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
  if (!b64) return null;
  const bytes = base64Bytes(b64);
  if (bytes.length === 0) return null;
  const localPath = `${FileSystem.cacheDirectory ?? ''}signature-${now()}.png`;
  await FileSystem.writeAsStringAsync(localPath, b64, { encoding: FileSystem.EncodingType.Base64 });
  const digest = await Crypto.digest(Crypto.CryptoDigestAlgorithm.SHA256, bytes);
  return { localPath, sha256: hex(digest), bytes: bytes.length };
}

export function canvasSignature(): SignaturePort {
  let mounted: SignatureViewRef | null = null;
  let waiting: ((dataUrl: string | null) => void) | null = null;
  const answer = (dataUrl: string | null) => {
    const resolve = waiting;
    waiting = null;
    resolve?.(dataUrl);
  };

  function Pad({ onInk, clearToken, label }: SignaturePadProps) {
    const ref = useRef<SignatureViewRef>(null);
    useEffect(() => {
      mounted = ref.current;
      return () => {
        if (mounted === ref.current) mounted = null;
      };
    });
    const first = useRef(true);
    useEffect(() => {
      if (first.current) {
        first.current = false;
        return;
      }
      ref.current?.clearSignature();
      onInk(false);
      // `onInk` is the screen's setter; only a new token wipes the pad.
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [clearToken]);
    return (
      <View accessible accessibilityLabel={label} style={{ flex: 1 }} testID="signature-pad">
        <SignatureView
          ref={ref}
          onBegin={() => onInk(true)}
          onOK={(dataUrl) => answer(dataUrl)}
          onEmpty={() => answer(null)}
          imageType="image/png"
          backgroundColor={color.white}
          penColor={color.black}
          trimWhitespace
          autoClear={false}
          webStyle={WEB_STYLE}
          style={{ flex: 1 }}
        />
      </View>
    );
  }

  return {
    Pad,
    async exportImage(): Promise<TakenPhoto | null> {
      const pad = mounted;
      if (!pad) return null;
      const dataUrl = await new Promise<string | null>((resolve) => {
        answer(null);
        waiting = resolve;
        setTimeout(() => {
          if (waiting === resolve) answer(null);
        }, EXPORT_WAIT_MS);
        pad.readSignature();
      });
      return dataUrl ? writeSignature(dataUrl) : null;
    },
  };
}
