/**
 * The field app's door to the shared token module. Everything here IS
 * `shared/tokens.ts` — the one source both apps import (Stack page: "One
 * tokens module, two renderers"). Nothing is redefined on this side; a theme
 * (`src/theme/`) chooses from these values and a component reads the theme.
 */
export {
  color,
  space,
  radius,
  nativeRadius,
  font,
  type,
  lineHeight,
  letterSpacing,
  touch,
  field,
  tokens,
  WEB_CSS_MIRROR,
  WEB_TAILWIND_MIRROR,
} from '../../../shared/tokens';
export type { Tokens } from '../../../shared/tokens';
