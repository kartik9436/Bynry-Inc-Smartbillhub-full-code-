from .base import *  # noqa

DEBUG = True
ALLOWED_HOSTS = ["*"]

# App-layer field encryption (BR-CUS-092 / OQ-016). A DEVELOPMENT key, committed
# on purpose: a developer and a CI box need one, and a per-machine secret is a
# secret typed wrong. `insecure-` is a reserved prefix — core/crypto.py refuses
# such a key unless the settings module explicitly allows it, and base.py leaves
# FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS False. So this key CANNOT reach a real
# deployment: getting it requires typing `DJANGO_SETTINGS_MODULE=config.settings
# .local`, which already means DEBUG=True and ALLOWED_HOSTS=["*"].
# ⚠ IT PROTECTS NOTHING. Anything encrypted under it is readable by anyone with
# this repo. That is the point of naming it `insecure-dev`.
FIELD_ENCRYPTION_KEYS = "insecure-dev:REglBOqa8pf2qDnwnG7zH9Yajye7-QKSQ6mSaeZqqMM"  # noqa: F405
FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS = True

# CR-049 — the document store. A developer has no bucket, so documents go to a
# directory under 06-backend/var/. ⚠ THIS IS NOT A STORE: local disk can make
# no immutable-retention promise, and NFR-35 requires seven years. It CANNOT
# reach a real deployment — getting here requires typing
# DJANGO_SETTINGS_MODULE=config.settings.local, which already means DEBUG=True
# and ALLOWED_HOSTS=["*"], and base.py leaves the allow-flag False.
DOCUMENT_STORAGE_BACKEND = "filesystem"
DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True
DOCUMENT_STORAGE_DIR = str(BASE_DIR / "var" / "documents")  # noqa: F405

# DEF-2717 — a developer's local PostgreSQL role is very often a SUPERUSER, and
# that is legitimate: creating databases, loading extensions and dropping test
# schemas all want it. A superuser BYPASSES row-level security entirely, so
# core/rls_guard.py would otherwise refuse to start here (base.py leaves
# RLS_ALLOW_BYPASSING_ROLE False so every settings module fails closed).
#
# ⚠ IT PROVES NOTHING WHILE IT IS TRUE. Tenant isolation on this machine is
# whatever the app layer happens to do; the DATABASE is not enforcing it, and an
# RLS assertion made on this connection is VACUOUS. That is why the G5 isolation
# suite runs its RLS half under the dedicated `sbh_rls_probe` role instead
# (NOLOGIN NOSUPERUSER NOBYPASSRLS — tests/isolation_helpers.py) and why every
# benchmark must print the role's rolsuper/rolbypassrls beside its figures.
#
# It CANNOT reach a real deployment: getting here requires typing
# DJANGO_SETTINGS_MODULE=config.settings.local, which already means DEBUG=True
# and ALLOWED_HOSTS=["*"]. The guard still prints one loud line per boot.
RLS_ALLOW_BYPASSING_ROLE = True

# CR-144-BRC07 (X3) — `Secure` on the sign-in cookies is OFF here and nowhere
# else. base.py defaults it True (hard-won law 3, the unsafe option is the one
# you type); a developer on `http://localhost` would otherwise sign in
# successfully and be anonymous on the very next request, because the browser
# accepts a `Secure` cookie over HTTPS only and silently declines to send it
# back over plain HTTP. There is no error anywhere in that sequence, which is
# what makes it worth a paragraph.
#
# ⚠ It CANNOT reach a real deployment: getting here requires typing
# DJANGO_SETTINGS_MODULE=config.settings.local, which already means DEBUG=True
# and ALLOWED_HOSTS=["*"]. A local run under PRODUCTION settings (`make up`)
# sets SBH_AUTH_COOKIE_SECURE=false in its own .env instead.
AUTH_COOKIE_SECURE = False

# The SPA's dev server. Exactly the origins Vite serves from — never `*`, which
# a credentialed request cannot use in any case (see base.py).
CORS_ALLOWED_ORIGINS = env.list(  # noqa: F405
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)
ORIGIN_GUARD_ALLOWED_ORIGINS = CORS_ALLOWED_ORIGINS

# The SPA's dev server is where a local portal address points (DEF-CWP-9717).
PUBLIC_APP_ORIGIN = env("PUBLIC_APP_ORIGIN", default="http://localhost:5173")  # noqa: F405
