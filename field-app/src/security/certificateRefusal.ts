/**
 * WAS THIS FAILED CONNECTION A REFUSED CERTIFICATE? (`DEF-FLD-10617`;
 * decision log 2026-10-26.)
 *
 * On 2.603.0 the phone refused the server's certificate and the screen said
 * *"No signal"* while the tester was online. A refused certificate and a
 * dropped connection reach JavaScript looking much alike — React Native's
 * `fetch` often rejects both with a bare `TypeError: Network request failed`
 * — so this file decides by two signals:
 *
 *  1. **The error names it** — an SSL / TLS / certificate / pinning / trust
 *     anchor message (OkHttp's `SSLPeerUnverifiedException: Certificate
 *     pinning failure!`, iOS's *"An SSL error has occurred"*), or the pinning
 *     library's own error type.
 *  2. **The pinning library said so moments before** — `react-native-ssl-
 *     public-key-pinning` reports every pin mismatch to a listener
 *     (`pinning.ts` subscribes it to `noteCertificateRefusal`). A bare network
 *     failure within `RECENT_MS` of such a report is the same refusal.
 *
 * Anything else is a real no-connection and keeps saying *No signal*.
 */

/** How long a reported pin mismatch explains a bare network failure. */
export const RECENT_MS = 15_000;

const CERTIFICATE_WORDS = /\b(ssl|tls|certificate|certification path|pinning|pin verification|trust ?anchor|handshake|x509|untrusted)\b|SSL[A-Za-z]*Exception|NSURLErrorServerCertificate|-120[0-9]\b/i;

let lastRefusalAt: number | null = null;

/** The pinning library reported a mismatch (its error listener). */
export function noteCertificateRefusal(now: number = Date.now()): void {
  lastRefusalAt = now;
}

/** Tests: forget any reported mismatch. */
export function resetCertificateRefusals(): void {
  lastRefusalAt = null;
}

function textOf(err: unknown): string {
  if (!err || typeof err !== 'object') return typeof err === 'string' ? err : '';
  const e = err as { name?: unknown; message?: unknown; code?: unknown; cause?: unknown };
  const parts = [e.name, e.message, e.code].filter((x): x is string => typeof x === 'string');
  // One hop into a wrapped cause is enough for our own wrappers.
  if (e.cause && typeof e.cause === 'object') {
    const c = e.cause as { name?: unknown; message?: unknown };
    for (const x of [c.name, c.message]) if (typeof x === 'string') parts.push(x);
  }
  return parts.join(' ');
}

/** True when `err` (a fetch rejection) is the server's certificate being refused. */
export function isCertificateRefusal(err: unknown, now: number = Date.now()): boolean {
  const text = textOf(err);
  if (/SslPinning/i.test(text) || CERTIFICATE_WORDS.test(text)) return true;
  return lastRefusalAt !== null && now - lastRefusalAt >= 0 && now - lastRefusalAt <= RECENT_MS;
}
