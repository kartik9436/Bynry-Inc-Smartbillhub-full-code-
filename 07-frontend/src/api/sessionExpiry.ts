// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-SHL-6378 (2026-09-23) — an expired session showed the ROLE
//           denial ("You don't have access to this.") on every screen.
// Rules:    BR-SHL-009 (no tenant data readable once the session is gone) ·
//           BR-IDN-026 (a session ends after 12 hours, or when revoked)
// Consumers: api/client.ts (every request, including imperative ones such as
//           a wizard's autosave) · api/queryClient.ts (every query and
//           mutation) · components/SessionExpired.tsx (the one listener)
// ───────────────────────────────────────────────────────
// THE ONE CHANNEL A 401 TRAVELS ON.
//
// The server says two different things and the product used to hear one:
//   · 401 `AUTH-001` — there is no live session. Nothing on any screen can
//     work until the person signs in again. (`core/errors.py`)
//   · 403 `AUTH-002` — the session is fine and THIS ROLE may not do this.
// A 403 belongs to the screen that asked, which knows the role and the module
// and says so (A18 §6). A 401 belongs to NO screen: it is true of every screen
// at once, so it is answered once, by the shell, and never by a page.
//
// ⚠ THIS FILE IMPORTS NOTHING. The client announces from inside `request()`
// and the listener lives in a component, so a channel that imported either
// would be an import cycle; it is a list of callbacks and nothing else.
//
// ⚠ WITH NO LISTENER, AN ANNOUNCEMENT IS A NO-OP — AND THAT IS THE DESIGN.
// Only the staff shell listens. The sign-in page answers a wrong password with
// a 401 too (`identity/services.py` — BR-IDN-002's one generic failure), the
// forced password change sits outside the shell, and the customer portal and
// the technician's phone are separate application roots with their own
// signed-out states. None of them mounts the shell, so none of them can be
// told their session expired by a request of their own.

type Listener = () => void;

const listeners = new Set<Listener>();

/** Subscribe; returns the unsubscribe. The staff shell is the one caller. */
export function onSessionExpired(listener: Listener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/**
 * Say the session has ended. Called for EVERY 401, by two layers that may both
 * see the same one — so a listener must be idempotent, and the shell's is.
 */
export function announceSessionExpired(): void {
  for (const listener of [...listeners]) {
    listener();
  }
}

/** The status the server answers a missing, expired or revoked session with. */
export const SESSION_EXPIRED_STATUS = 401;

// ── Lifecycle ─────────────────────────────────────────────
// packet: DEF-SHL-6378 (maintenance — PO report, production v2.344.0)
// generated: 2026-09-23 by lane SESSION-EXPIRY
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────
