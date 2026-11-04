/**
 * FF-06 *Locked out?* — three ways back in, none of them typed (R38: the
 * board has NO input box): *Text me a code* to the technician's phone, *Call
 * the office*, or *Ask the office to reset* (they text a new one).
 *
 * ⚠ THE SERVER HAS NONE OF THIS YET. The web resets a password by email
 * link; there is no route that texts a code, none that tells the office a
 * technician is locked out, and no route that answers, before sign-in, the
 * technician's masked number (*(512) 555-••42*) or the office's number
 * (*(512) 555-0100*). So the shipped port refuses with `ResetGapError`
 * naming each one, and FF-06 shows that plainly — *Call the office* stays
 * possible whenever the office number is known, because a phone call needs
 * no server.
 */

export type ResetWay = 'text' | 'call' | 'ask';

export interface ResetContacts {
  /** The technician's own number, masked by the SERVER (never unmasked on the handset). */
  maskedPhone: string | null;
  /** The office's number, to ring. */
  officePhone: string | null;
}

export interface PasswordResetPort {
  contacts(input: { tenant: string; login: string }): Promise<ResetContacts>;
  textCode(input: { tenant: string; login: string }): Promise<void>;
  askOffice(input: { tenant: string; login: string }): Promise<void>;
}

export const RESET_GAPS = {
  'reset-contacts': {
    endpoint: 'GET /api/{tenant}/auth/reset/contacts?login=',
    need: 'Before sign-in: the technician\'s phone number masked by the server, and the office number to ring.',
  },
  'reset-text-code': {
    endpoint: 'POST /api/{tenant}/auth/reset/text-code',
    need: 'Text a one-time code to the technician\'s phone on file.',
  },
  'reset-ask-office': {
    endpoint: 'POST /api/{tenant}/auth/reset/ask-office',
    need: 'Tell the office a technician is locked out, so they reset it and text a new one.',
  },
} as const;

export type ResetGapId = keyof typeof RESET_GAPS;

export class ResetGapError extends Error {
  readonly gap: ResetGapId;

  constructor(gap: ResetGapId) {
    super(`server gap ${gap}: ${RESET_GAPS[gap].endpoint} — ${RESET_GAPS[gap].need}`);
    this.name = 'ResetGapError';
    this.gap = gap;
  }
}

export const resetNotWired: PasswordResetPort = {
  contacts: () => Promise.reject(new ResetGapError('reset-contacts')),
  textCode: () => Promise.reject(new ResetGapError('reset-text-code')),
  askOffice: () => Promise.reject(new ResetGapError('reset-ask-office')),
};
