# A4 — Roles & Permissions Matrix

> Part A (extraction). Source: SMARTBillHub prototype `../../05-prototype/UtilityBilling.html`. Role × screen × action; approvals; cross-tenant flags.
> Cardinal rule: anything not determinable from the UI is `UNKNOWN — <question>`, never invented.


Roles implied: **Platform Admin** (SMARTBillHub staff), **Owner** (utility, from self-signup), **Admin**, **Billing Clerk / Staff**, **Finance (read-mostly)**, **End Customer (portal)**.

| Area / Action | Platform Admin | Owner | Admin | Staff/Clerk | Finance | Customer |
|---|---|---|---|---|---|---|
| Tenant settings / lookup tables | R (support) | CRUD | CRUD | R | R | — |
| User management | — | CRUD | CRUD | — | — | — |
| Plans & Rates | — | CRUD | CRUD | R | R | — |
| Premises / Units / Meters | — | CRUD | CRUD | CRUD | R | — |
| Accounts (create/move) | — | CRUD | CRUD | CRUD | R | R (own) |
| Reads (upload/edit) | — | CRUD | CRUD | CRUD | R | — |
| Run billing | — | CRUD | CRUD | CRUD | R | — |
| Payments record | — | CRUD | CRUD | CRUD | CRU | pay own |
| **Adjustment approval** | — | ✔ | ✔ | request only | ✔ | — |
| **Invoice void/reverse** | — | ✔ | ✔ | UNKNOWN | ✔ | — |
| **Change tariff/rate** | — | ✔ | ✔ | — | — | — |
| Write-off | — | ✔ (approval) | ✔ | request | ✔ | — |
| Finance / reconcile / export | — | CRUD | CRUD | R | CRUD | — |
| Reports | — | CRUD | CRUD | R/run | R/run | own bills |
| **Cross-tenant data** | R (support only) | — | — | — | — | — |

Explicit answers:
- **Approve/reverse invoice:** Owner, Admin, Finance. (Adjust modal shows "Requires supervisor approval".) Clerk reversal `UNKNOWN`.
- **Change tariff:** Owner, Admin only.
- **See other tenants' data:** none except Platform Admin in a support capacity — `UNKNOWN whether even that is in scope`. Flag: no UI exposes cross-tenant data — good.
- **Self-serve signup role:** the signup Owner account = **Owner** role.
`UNKNOWN — the exact role list and granular permissions are not defined by a Settings→Users screen in full fidelity. Confirm role names and the full CRUD matrix.`

---


## Addendum — Predefined roles (confirmed 2026-08-07, settles O-5)
Roles are **predefined, not tenant-editable**; new roles are created by the platform provider (backend). Three tenant roles:
- **System Admin** — full access to all modules + settings + user management + approvals.
- **Billing Clerk** — full on Premises/Accounts/Reads/Billing/Payments; view on Plans&Rates; requests adjustments/write-offs (no approve); runs reports; no settings/users.
- **Executive** — view across operational modules; full on Finance + Reports; approves adjustments/write-offs; views settings.

Read-only permission matrix (as shown in Settings → Users & roles):
| Permission | System Admin | Billing Clerk | Executive |
|---|---|---|---|
| Settings & lookup tables | Full | — ⁽¹⁾ | View |
| User management | Full | — | — |
| Plans & Rates | Full | View | View |
| Premises / Accounts | Full | Full | View |
| Reads & Billing runs | Full | Full | View |
| Payments (record) | Full | Full | View |
| Adjustment / write-off approval | Approve | Request | Approve |
| Finance / reconcile / export | Full | — | Full |
| Reports | Full | Run | Full |


## Addendum — Self-service account (2026-08-07)
Every authenticated user (any role) can manage **their own** profile, password, and 2FA via the user menu, and sign out. This is distinct from **user management** (Settings → Users & roles), which is System Admin only.

## Addendum — ⁽¹⁾ A Billing Clerk READS New Connection's size and equipment lists (PO ruling 2026-10-02)
**AMENDED 2026-10-02, FOR ONE READ AND NOTHING ELSE.** PO, verbatim: *"5. Should a billing clerk see the size lists New Connection needs? A · Let the billing clerk read the size and equipment lists (read only)."* (decision log 2026-10-02, top row; `DEF-CUS-9048`, found by the portal 21-walk: a clerk's New Connection step 3 offered no device, no size and no work template, because all three lists answered 403).

| Permission | System Admin | Billing Clerk | Executive |
|---|---|---|---|
| Settings & lookup tables — **only** `asset_types`, `service_size_classes` and the work templates list | Full | **View (read only)** | View |

- **Read only.** No write on any list moves: adding, editing or retiring an entry, and creating or publishing a work template, stay System Admin's.
- **Those three lists only.** The clerk's cell on *Settings & lookup tables* stays **—** for every other list and every Settings tab (US-TEN-009 TC-5 stands).
- **Where it is enforced:** `06-backend/core/permissions.py` — `NewConnectionLookupRead` (`GET /lookups/asset_types`, `GET /lookups/service_size_classes`) and `WorkTemplateListRead` (`GET /work/templates`); restated for the role table as `apps/identity/models.py` `A4_CLERK_READ_GRANTS`, held equal by `tests/test_def_cus_9048_clerk_reads_new_connect_lists.py`. The nine-row grid above (`A4_MATRIX`, BR-IDN-014) is unchanged.
