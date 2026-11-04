// ── Trace ──────────────────────────────────────────────
// Rules:    BR-SHL-033 (a long list is a searchable type-ahead) · B14 rule 8
//           (five or more options are searchable) · B14 rule 43 (one list,
//           imported — never re-typed on a second screen)
// Moved:    2026-09-23 from `features/tenancy/SignupWizard.tsx`, which
//           re-exports it, so sign-up, the service-request billing address and
//           the kit's `UsAddressFields` read ONE list (`DEF-CUS-6408`).
// ───────────────────────────────────────────────────────
//
// A1 dropdown coverage: 50 states + DC + PR, as a searchable type-ahead
// (BR-SHL-033). Values are the 2-letter codes `us_state_code()` accepts
// (06-backend/apps/tenancy/selectors.py US_STATES, the authority).
//
// ⚠ **THE LABELS ARE PROPER NOUNS AND ARE NOT TRANSLATED.** A state is called
// `Texas` on an envelope in every language this product speaks; the CODE is what
// is stored.
export const US_STATE_ROWS: readonly (readonly [string, string])[] = [
  ["AL", "Alabama"],
  ["AK", "Alaska"],
  ["AZ", "Arizona"],
  ["AR", "Arkansas"],
  ["CA", "California"],
  ["CO", "Colorado"],
  ["CT", "Connecticut"],
  ["DE", "Delaware"],
  ["DC", "District of Columbia"],
  ["FL", "Florida"],
  ["GA", "Georgia"],
  ["HI", "Hawaii"],
  ["ID", "Idaho"],
  ["IL", "Illinois"],
  ["IN", "Indiana"],
  ["IA", "Iowa"],
  ["KS", "Kansas"],
  ["KY", "Kentucky"],
  ["LA", "Louisiana"],
  ["ME", "Maine"],
  ["MD", "Maryland"],
  ["MA", "Massachusetts"],
  ["MI", "Michigan"],
  ["MN", "Minnesota"],
  ["MS", "Mississippi"],
  ["MO", "Missouri"],
  ["MT", "Montana"],
  ["NE", "Nebraska"],
  ["NV", "Nevada"],
  ["NH", "New Hampshire"],
  ["NJ", "New Jersey"],
  ["NM", "New Mexico"],
  ["NY", "New York"],
  ["NC", "North Carolina"],
  ["ND", "North Dakota"],
  ["OH", "Ohio"],
  ["OK", "Oklahoma"],
  ["OR", "Oregon"],
  ["PA", "Pennsylvania"],
  ["PR", "Puerto Rico"],
  ["RI", "Rhode Island"],
  ["SC", "South Carolina"],
  ["SD", "South Dakota"],
  ["TN", "Tennessee"],
  ["TX", "Texas"],
  ["UT", "Utah"],
  ["VT", "Vermont"],
  ["VA", "Virginia"],
  ["WA", "Washington"],
  ["WV", "West Virginia"],
  ["WI", "Wisconsin"],
  ["WY", "Wyoming"],
];

export const US_STATE_OPTIONS = US_STATE_ROWS.map(([value, label]) => ({ value, label }));
