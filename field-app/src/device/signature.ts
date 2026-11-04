/**
 * THE signing pad port (moved here from `screens/closing/signature.ts` in the
 * integration lane; that file re-exports it).
 *
 * Capturing a customer's signature (FF-33; R30, BR-WRK-046).
 *
 * FF-33 draws the pad through `SignaturePort`: `Pad` is the surface the
 * customer signs on and `exportImage()` turns the ink into an image file the
 * outbox can carry. The shipped app wires the real one
 * (`native/signature.tsx`, react-native-signature-canvas — DEF-FLD-10627, PO
 * 2026-10-27). `unwiredSignature` has no pad and is what tests and previews
 * get by default — FF-33 then still offers the RECORDED REFUSAL, which needs
 * only a reason and a camera photo — and a test's own fake pad lets it sign.
 */
import type { ComponentType } from 'react';

import type { TakenPhoto } from './ports';

export interface SignaturePadProps {
  /** Called whenever the pad goes from empty to inked or back. */
  onInk: (hasInk: boolean) => void;
  /** Bumped by the screen's *Clear*: the pad wipes itself when it changes. */
  clearToken: number;
  /** Accessible name of the pad ("Sign below"). */
  label: string;
}

export interface SignaturePort {
  readonly Pad: ComponentType<SignaturePadProps> | null;
  /** The ink as an image file on disk; null when the pad is empty. */
  exportImage(): Promise<TakenPhoto | null>;
}

export const unwiredSignature: SignaturePort = {
  Pad: null,
  exportImage: () => Promise.resolve(null),
};
