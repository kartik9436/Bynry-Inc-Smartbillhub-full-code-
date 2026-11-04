# Module — identity

Staff authentication, 3 predefined roles (System Admin / Billing Clerk / Executive), 2FA, memberships.

**Owns (B2):** users, roles, permissions, role_permissions, tenant_memberships, sso_links
**Screens:** S3 Sign-in · S48 User menu · S8 Settings→Users & roles
**Boundary rule (B1):** no other module writes this module's tables; cross-module reads via service functions only.
