/**
 * `CaptureTokens` for the sync engine (`sync/outbox.ts`): each technician's
 * OWN capture credential, from the keystore through the session — so an item
 * travels under the person who captured it, whoever is signed in when it is
 * sent (Security §3, BR-WRK-059/060). The outbox never stores a credential.
 *
 * A technician with no credential on this handset, or one whose credential
 * has run out, has no token: their items WAIT (`sendPending` skips them and
 * counts it), never travel as someone else. A sign-in renews it.
 */
import type { CaptureTokens } from '../sync/outbox';
import type { Clock } from './clock';
import { isCaptureValid, type CaptureCredential } from './credentials';

export interface CredentialSource {
  captureCredentialOf(technicianId: string): CaptureCredential | null;
}

export function captureTokensOf(source: CredentialSource, clock: Clock): CaptureTokens {
  return {
    tokenFor(technicianId: string): string | null {
      const cred = source.captureCredentialOf(technicianId);
      return cred && isCaptureValid(cred, clock.now()) ? cred.serverToken : null;
    },
  };
}
