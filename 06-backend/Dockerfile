# ── SMARTBillHub API image (the ONLY backend image; Dockerfile.dev is deleted) ──
#
# Two stages. `build` owns a compiler and a package index; `runtime` owns neither.
# Everything that survives into the shipped layer is copied explicitly:
#   /opt/venv   the dependency set, resolved from pyproject.toml (one source of truth)
#   /app        the source tree, minus everything .dockerignore drops
# No apt build chain, no pip cache, no wheels, no tests in the runtime image.
#
# The app's DEPENDENCIES are installed; the app itself is deliberately not.
# `pip install .` would work now (pyproject.toml gained a package-discovery
# table — until today setuptools called the flat layout ambiguous and refused,
# which is why the old dev image carried `|| pip install <the same pins again>`,
# a second dependency list free to drift from the first). It is still the wrong
# thing to do here: it would put a SECOND copy of apps/ config/ core/ in
# site-packages, shadowed by /app on sys.path and silently stale after every
# edit. Installing only the pins keeps one copy of the source, at /app, which is
# all Django ever needed — gunicorn runs with WORKDIR=/app.
#
# Build context: 06-backend/ (see the root docker-compose.yml).

# ── stage 1: build ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

# Present only in this stage. psycopg[binary] ships manylinux wheels so nothing
# should need compiling today; a transitive dependency that publishes an sdist
# tomorrow must fail in the build stage, not at `docker run`.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /src
COPY pyproject.toml ./

# One source of truth for the pins: [project].dependencies, read with the stdlib
# TOML parser. Change pyproject.toml and the image changes with it — there is no
# second list to keep in step. (The project itself is deliberately NOT installed;
# see the header.)
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
 && cat requirements.txt \
 && pip install --no-cache-dir -r requirements.txt

# ── stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# ── Tagged customer PDFs (DEF-BIL-10546, PO/QA ruling 2026-10-23, Group H) ───
# WeasyPrint (pinned in pyproject.toml) writes every customer PDF — bill, final
# bill, statement, agreement — as PDF/UA-1 from the document's HTML. It needs
# Pango (layout), HarfBuzz (shaping) and HarfBuzz-Subset (font subsetting:
# without it WeasyPrint falls back to fontTools, which is slower and which
# `core/tagged_pdf.py` has to keep away from the clock), plus fontconfig.
# These are SYSTEM libraries, so a host gets them only when this image is
# rebuilt — editing pyproject.toml or pulling new code does nothing to a running
# container (hard-won law 4). See `09-infra/05-tagged-customer-pdfs.md`.
#
# The FONT is not installed here on purpose: Liberation Sans ships inside the
# source tree, at `core/fonts/liberation/` with its SIL OFL 1.1 licence
# (`OFL.txt`), and `COPY . .` below carries it. The renderer names those files
# directly, so no system font can be substituted for it.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
      fontconfig libfontconfig1 \
 && rm -rf /var/lib/apt/lists/* \
 && test -s /usr/lib/$(uname -m)-linux-gnu/libharfbuzz-subset.so.0

# Non-root, with a fixed uid/gid so any file the container writes has a stable owner.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY --chown=app:app . .

# Fail the BUILD, not the first bill run, if the tagged-PDF stack is incomplete:
# render one tiny page through the product's own renderer, which refuses a file
# with no structure tree, no /Lang, no title or no embedded Liberation Sans.
RUN cd /app && python -c "from core import tagged_pdf; tagged_pdf.render('<!doctype html><html lang=\"en\"><head><title>build check</title></head><body><h1>ok</h1></body></html>')"

# No /app/var/artifacts any more (2026-10-02, `DEF-MET-4954`): export files go
# to S3, and a job builds its file in its own folder under /tmp, removed when
# the job ends. Nothing in this image writes under /app at run time.
# gunicorn 26 opens a control server backed by a file in its working directory.
# Without this the first live deploy logged, on every boot:
#   [ERROR] Control server error: [Errno 13] Permission denied: '/app/.gunicorn'
# The workers boot and serve regardless — but an ERROR line on every start is a
# false alarm that costs someone an investigation, and the container runs as
# uid 10001 which cannot create it in a root-owned /app.
RUN mkdir -p /app/.gunicorn && chown -R app:app /app/.gunicorn

USER app

# Documentation only — the root compose file publishes NO backend port. The API
# is reached through the frontend container's /api pass-through, which is what
# makes the SPA and the API same-origin with nothing in front of them.
EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
