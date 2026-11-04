# platform-shell — Field Map

One row per field. Origin: user-input | system-derived | reference-data | integration | computed-display. Rows cite A2 § or "prototype-extracted"; underivable = GAP (mint an OQ).

| Field | Screen | Spec source | DB target (B2) | Type/unit | Origin | Validation | Status |
|---|---|---|---|---|---|---|---|
| Sidebar collapsed state | shell chrome | 04-docs/README §Interactions | `user_preferences.value` key `shell.sidebar_collapsed` | boolean (jsonb) | user-input | true/false | PROPOSED-SCHEMA (US-SHL-001/013) |
| Visible-column set + order (per screen) | all list screens | B9 IS-5 | `user_preferences.value` key `table.‹screen›.columns` | jsonb array of column keys | user-input | subset of screen's available columns; identity column mandatory | PROPOSED-SCHEMA (US-SHL-007/013) |
| `user_preferences.tenant_id` | — | module ownership (01-overview.md); absent from B2 | `user_preferences.tenant_id` | uuid | system-derived | FK tenants.id; RLS FORCE | PROPOSED-SCHEMA (US-SHL-013) |
| `user_preferences.user_id` | — | absent from B2 | `user_preferences.user_id` | uuid | system-derived | FK users.id (⚠ cross-module → identity, B2 §2 review) | PROPOSED-SCHEMA (US-SHL-013) |
| `user_preferences.key` | — | absent from B2 | `user_preferences.key` | text | system-derived | dotted namespace ≤128 chars; UNIQUE (tenant_id, user_id, key) | PROPOSED-SCHEMA (US-SHL-013) |
| `user_preferences.value` | — | absent from B2 | `user_preferences.value` | jsonb | user-input | ≤32 KB; UI preferences only, never business data | PROPOSED-SCHEMA (US-SHL-013) |
| Global search query `q` | shell chrome (topbar) | 04-docs/README §Global Layout | none (transient request param) | text | user-input | min 2 chars, debounced 300 ms (IS-3) | ok (US-SHL-003) |
| Global search result rows | shell chrome (popover) | README §Global Layout + B2 identifiers | read-only: `accounts.account_no`, `contacts.full_name`, `premises.name/address_line`, `units.label`, `invoices.invoice_no`, `payments.confirmation` | text / money display 2 dp | computed-display | tenant-scoped reads only; `GET /search` is a PROPOSED A11 addition | ok (US-SHL-003) |
| Breadcrumb segments / tab title | shell chrome | README §Global Layout | none (route-derived; leaf reads record display id) | text | computed-display | leaf never a raw UUID | ok (US-SHL-002) |
| Notifications bell items (event type, subject, read state, timestamp) + unread count | shell chrome (topbar) | BR-SHL-007 CONFIRMED (PO R1 example 3) — tenant-scoped bell, unread 9+ badge, newest-first popover | staff-notification store lands with the notifications pack (W6) | — | — | — | GAP → OQ-019 (US-SHL-004) |
