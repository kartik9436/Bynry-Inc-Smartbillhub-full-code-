## Story ID(s)
<!-- REQUIRED, first line: US-XXX-### (feeds the traceability matrix code-refs column). "N/A — <reason>" for non-story changes. -->

## What & why
<!-- One paragraph. Link the story ID (US-XXX-###) and screen IDs (S#). -->

## Spec references
- Stories / rules: <!-- US-..., BR-... -->
- Screens: <!-- S# from 04-docs/01-spec/01-screen-inventory.md -->

## Money & isolation checklist
- [ ] No tenant table touched without RLS context (`app.tenant_id`)
- [ ] No float/cents money — `NUMERIC(18,6)` + currency end to end
- [ ] No UPDATE/DELETE on issued financial rows — corrections are new rows
- [ ] Money actions write `audit_log`
- [ ] No changes to human-only files (or a human owner has reviewed them)
- [ ] `depends_on` stories + journey files (J#) read before coding
- [ ] Golden tests pass (or xfail with A17/B4 reference)
- [ ] Tenant-isolation suite passes

## Tests
<!-- What was added/updated; how verified. -->
