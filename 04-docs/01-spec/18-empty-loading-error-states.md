# A18 — Empty / Loading / Error State Patterns

> Six SHARED patterns (not per-screen). Every list, detail, wizard, and import in the app composes from these. Added 2026-08-07 (the prototype shipped happy-path only). Built from Modernist tokens + components.

## 1. Empty list (nothing created yet)
Centered block inside the content area: a muted 1-line title, a 1-line helper, and the primary create action.
- Title (h4): e.g. "No accounts yet." · Helper (13px muted): "Create your first account to start billing." · Button: `.btn-primary` "+ New account".
- Never show an empty table header with zero rows — replace the whole table with this block.

## 2. Zero results after a filter/search
Keep the toolbar/filters visible; replace only the rows region.
- 13px muted: "No results for `‹query››." + a `.btn-ghost` "Clear filters". Do not offer "create" here (the data may exist, just filtered out).

## 3. Loading skeleton
Show the real layout with shimmer placeholders — never a spinner alone for content areas.
- Tables: 6–10 skeleton rows of grey bars (`--color-neutral-200` blocks, varying widths). KPI strip: grey blocks at KPI size. Cards/detail: title bar + 3 line bars.
- Buttons that trigger work show inline state: `.btn-primary` disabled + "Working…" (used by billing run, import, reconcile).

## 4. Failed import / sync (with retry)
A `.card` with `border-top-color: var(--color-danger-500)` and a `.pill.past` "Failed".
- Line 1 (bold): what failed — "Bank statement import failed." Line 2 (muted): plain-language reason — "We couldn't read row 42 (missing amount)."
- Actions: `.btn-primary` "Retry", `.btn-secondary` "Download error report", `.btn-ghost` "Cancel". Mirrors the existing Payments "Failed · Retry" pattern.
- Partial success shows counts: "84 imported · 6 need review · 2 failed" with a link to the failing rows.

## 5. Form validation error
Inline, per-field; never a single top alert alone.
- Offending `.input` gets `border-color: var(--color-danger-500)`; a 12px `--color-danger-700` message sits directly under the field ("Amount must be greater than 0.").
- Submit button stays enabled but re-validates on click and scrolls to the first error. A summary line above the form actions when >3 errors: "Fix 4 fields to continue."

## 6. Permission denied
For a role without access (see A4), the nav item is hidden where possible; if reached directly, show a centered block.
- Title: "You don't have access to this." · Helper: "Billing Clerks can't open Finance. Ask a System Admin if you need it." · `.btn-secondary` "Back to Dashboard". No data is rendered behind it.

## Tokens used
success/warning/danger (A12), `--color-neutral-200/700`, `.card`, `.pill`, `.btn-*`, `.input`. No new components required.