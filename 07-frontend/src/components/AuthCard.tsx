// ── Trace ──────────────────────────────────────────────
// Change:   CR-170-BRC10 (forgot password, PO 2026-10-05)
// Rules:    BR-IDN-022 · BR-IDN-023 · B14 rule 43 (a piece of UI is built as a
//           COMPONENT) · rule 21 (Tailwind utilities, no stylesheet class) ·
//           rule 44 (our UI standard decides how it is built)
// ───────────────────────────────────────────────────────
/**
 * THE SIGNED-OUT CARD — the full-viewport centred stage and the 420px,
 * accent-topped card that sign-in, the forced password change and the
 * forgot-password page all stand on.
 *
 * Until `CR-170-BRC10` the stage and the card were written out by hand in
 * `SignInPage` and again, *"value for value"*, in `ChangePasswordPage`. The
 * forgot-password page was ruled to sit on THE SAME card, and a third copy is
 * exactly what rule 43 forbids — so the two copies became this one component,
 * and every screen a signed-out person crosses in one click shares it.
 *
 * `page` is the `data-page` machine handle each screen already carried
 * (`tenantPath.test.tsx` and the walks read it); it is passed through, never
 * invented here.
 */
import type { ReactNode } from "react";

import { Kicker } from "@/components/TextBits";

export interface AuthCardProps {
  /** The `data-page` handle of the screen standing on this card. */
  page: string;
  /** The small line above the heading. Omitted → no kicker at all. */
  kicker?: ReactNode;
  /** The heading, rendered as the card's `h2`. */
  title: ReactNode;
  /** The one sentence under the heading. Omitted → no paragraph at all. */
  lede?: ReactNode;
  children?: ReactNode;
}

export function AuthCard({ page, kicker, title, lede, children }: AuthCardProps) {
  return (
    <div
      className="flex min-h-screen items-center justify-center bg-surface px-6 py-8"
      data-page={page}
    >
      <div className="w-full max-w-[420px] border-t-4 border-t-accent bg-bg p-8 shadow-md">
        {kicker !== undefined && <Kicker>{kicker}</Kicker>}
        {/* text-h4 on a real heading: size 20px plus the heading family /
            weight / leading / tracking tokens global.css gives every h2. */}
        <h2 className="my-2 text-h4">{title}</h2>
        {lede !== undefined && (
          <p className="m-0 mb-4 text-md text-[color-mix(in_srgb,var(--color-text)_65%,transparent)]">
            {lede}
          </p>
        )}
        {children}
      </div>
    </div>
  );
}
