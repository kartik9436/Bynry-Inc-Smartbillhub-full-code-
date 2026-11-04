# ── SMARTBillHub SPA image (the ONLY frontend image; Dockerfile.dev is deleted) ──
#
# Two stages. `build` owns node_modules, TypeScript and Vite; `runtime` owns a
# directory of static files and one script. Nothing from the build survives
# except `dist/`:
#   /app/dist       the bundle (`tsc --noEmit && vite build`)
#   /app/server.mjs the static server + /api pass-through (node builtins only —
#                   there is no node_modules in the runtime image at all)
#
# server.mjs is what makes the SPA and the API one origin. There is no ALB and
# no nginx here; read the header of that file before changing anything about
# `/api` handling — the behaviour is load-bearing, not decorative.
#
# The bundle is environment-independent: Vite inlines only `VITE_*` variables
# and src/vite-env.d.ts declares none ("THERE ARE NONE RIGHT NOW"). One image is
# therefore valid in every environment — no build args, nothing to inject, and a
# build cannot be "wrong for this environment".
#
# Build context: 07-frontend/ (see the root docker-compose.yml).

# ── stage 1: build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS build

ENV npm_config_update_notifier=false \
    npm_config_fund=false

WORKDIR /app

# Dependency layer first: it re-resolves only when the lockfile moves.
COPY package.json package-lock.json ./

# ⚠ **DEF-2382 — `npm ci` PULLS ~1,100 TARBALLS AND ONE RESET KILLS THE IMAGE.**
# Reported from a real `docker compose build` on 2026-09-02:
#
#     npm error code ECONNRESET
#     npm error network aborted
#
# after 25 seconds and seven deprecation warnings — i.e. most of the way
# through a successful install. Nothing was wrong with the lockfile or the
# code; a single connection dropped and the whole layer failed.
#
# It bites hardest exactly when a release is being cut, because this layer is
# cached until the LOCKFILE MOVES, and a lockfile moves on every version bump —
# so the one build that has to re-download everything is the one a person is
# waiting on.
#
# npm's own retry policy is the fix and it is off by default in effect: three
# retries with a 10-second ceiling gives up long before a flaky link recovers.
# These four settings are npm's documented knobs, not a workaround:
#   fetch-retries        5   — five attempts per request, not three
#   fetch-retry-mintimeout / maxtimeout — back off 20s → 2m instead of 10ms → 10s
#   fetch-timeout        10m — a slow tarball is not a dead one
# A genuinely unreachable registry still fails the build, and should.
ENV npm_config_fetch_retries=5 \
    npm_config_fetch_retry_mintimeout=20000 \
    npm_config_fetch_retry_maxtimeout=120000 \
    npm_config_fetch_timeout=600000

RUN npm ci

COPY . .

# ── the heap ceiling, and it is NOT the machine's RAM ────────────────────────
# `npm run build` = tsc --noEmit && vite build. The typecheck is part of the
# build on purpose: a type error must fail the image, not ship in it.
#
# ⚠ **THIS LAYER DIED WITH `JavaScript heap out of memory` ON A 4 GB HOST
# (2026-09-23, reported by the PO), AND RAISING THE HOST'S RAM WOULD NOT HAVE
# FIXED IT.** The trace capped at **1917.7 / 1953.6 MB** — that is Node 20's
# OWN default old-space limit on this box, not the 4 GB available. Node never
# asked for the rest, so the build failed with roughly half the machine idle.
# Exit code 134 is SIGABRT, which is V8 giving up, not the kernel OOM killer;
# a kernel kill would have been 137 and is what raising RAM alone addresses.
#
# **WHAT IT IS ACTUALLY HOLDING:** 651,644 lines of TypeScript across 1,302
# files, and `src/api/endpoints.ts` alone is **20,266 lines** — one file `tsc`
# must hold whole. 3072 MB leaves ~1 GB for the OS, Docker and the backend
# image building beside it, which is tight but measured rather than guessed.
#
# ⚠ **IF THIS FAILS AGAIN, THE LIMIT IS THE NEXT THING TO RAISE, NOT THE FIRST
# THING TO BLAME — AND THE DURABLE FIX IS THE TRANSLATION CATALOGUES, NOT
# `endpoints.ts`. THIS COMMENT SAID `endpoints.ts` UNTIL IT WAS MEASURED.**
#
# **MEASURED 2026-09-23** on this repo's own TypeScript, each probe a project
# containing nothing but the imports named, `--extendedDiagnostics`:
#
#   | what is type-inferred          | types built | memory  |
#   |--------------------------------|-------------|---------|
#   | all eleven locale JSON files   |     293,897 |  403 MB |
#   | one locale JSON file           |      29,602 |   89 MB |
#   | none (declared, not inferred)  |          92 |   55 MB |
#
# `resolveJsonModule` is on and `src/i18n/index.ts` STATICALLY IMPORTS ALL
# ELEVEN, so `tsc` builds a literal type for **211,794 translation keys** —
# **403 MB, about a fifth of the ceiling this layer died at**, before a single
# line of application code is checked. Typing ONE catalogue and declaring the
# rest as that shape recovers **314 MB** and is a few lines in one file.
#
# ⚠ **AND IT IS NOT A BUILD WORKAROUND — IT IS WORK THIS REPO ALREADY OWES.**
# `src/i18n/index.ts` says so itself: `BR-SHL-040` requires the catalogues to
# load LAZILY, one locale at a time, *"they are static imports below, so every
# user still downloads all eleven"*, and **824,000 of 1,546,871 bundle bytes
# were translation JSON**. Over half the shipped application is text every
# customer downloads to read one language of. The build fix and that fix are
# the same job.
#
# `endpoints.ts` is the SECOND candidate, not the first, and splitting it would
# not help this layer much anyway: `tsc` builds one program over all files, so
# 622 types cost the same in one file or eleven. Its real costs are merge
# contention — six commits in one day, one of them titled *"restore the sibling
# work my own push subtracted"* — and that `13-component-registry.md` marks it
# **generated** (*"Generated from the audited A11/OpenAPI schema — no
# hand-written fetch"*) while no generator exists in the repo.
ENV NODE_OPTIONS=--max-old-space-size=3072
#
# ⚠ **`DEF-DEP-10115` (2026-10-13): KILLED WITH EXIT 137 ON THE PO's HOST — THE
# KERNEL, NOT V8 — IN `build:types`.** The typecheck had grown to **2.88 GB**,
# at its own 3 GB ceiling, so the host ran out before Node did. Two changes,
# measured with `--extendedDiagnostics`:
#   * `build:types` checks `tsconfig.build.json` — what the image SHIPS, test
#     files are not roots — and `npm run typecheck` still checks all of `src`;
#   * `src/i18n/index.ts` loads the catalogues through an eager glob, so `tsc`
#     no longer builds a literal type for every translation key.
#   **2.88 GB → 1.51 GB** for the typecheck (1.85 GB resident). The bundle step
#   (`vite build`) is now the larger half, **~2.45 GB resident** including
#   esbuild, and it fails below ~1.5 GB of heap — so this layer needs about
#   **2.5 GB free**. Building the backend image at the same moment roughly
#   doubles the demand; build the two one at a time on a small host.

# ⚠ **ONE `RUN npm run build`, AND THE TWO HALVES ARE NAMED SCRIPTS INSIDE IT.**
# An earlier version of this file split them into `RUN npx tsc --noEmit` and
# `RUN npx vite build`, for a good reason — chained with `&&`, a failure says
# only *"npm run build did not complete"* and a reader cannot tell whether the
# typecheck or the bundler ran out of room, which is the question that decides
# what to fix. **`G54` caught that within hours and it was right to** (`DEF-GOV-6252`):
# it parses this stage for `RUN npm run <script>` and then RUNS it, so a
# Dockerfile that builds some other way leaves the gate unable to prove the
# image builds at all. Its own message says *"if the image stopped building
# through an npm script, teach this gate the new shape; do not delete the gate"*
# — and teaching it a second shape to keep a diagnostic is the worse trade when
# `package.json` gives the same diagnostic for free.
#
# So `build` is now `npm run build:types && npm run build:bundle`. The gate finds
# its line, the failing half still NAMES ITSELF in the output, and a developer
# can run either half alone. Nothing was given up.
# ⚠ **`build:compose`, NOT `build` — `DEF-DEP-7460`.** `vite build` with no
# `--mode` resolves as mode **production**, so the plain `build` script asks for
# a PRODUCTION bundle: one carrying a deployed API origin. `CR-144-BRC07`'s guard
# then refuses it, correctly — `.dockerignore` excludes `.env.*`, so no API host
# can reach this build context, and a production bundle with a relative base URL
# is the exact failure that guard exists to stop.
#
# This image is NOT a deployed bundle. It is served by `server.mjs`, which
# PROXIES `/api` through to the API container, so the bundle it wants is
# SAME-ORIGIN — an empty base URL, which is what any mode outside
# `DEPLOYED_MODES` resolves to by construction. `compose` is that mode — named for the only thing that builds it, and NOT `local`, which vite reserves because of the `.env.local` postfix (it refuses the mode name outright).
#
# ⚠ **DO NOT "FIX" THIS BY RELAXING THE GUARD OR BY UN-IGNORING `.env.*`.**
# Relaxing it lets a real bundle ship pointing at its own static host, which is
# every screen failing at once with nothing red in CI. Un-ignoring `.env.*`
# would put `.env` — which holds real secrets — into an image layer.
RUN npm run build

# ── stage 2: runtime ─────────────────────────────────────────────────────────
FROM node:20-alpine AS runtime

ENV NODE_ENV=production

WORKDIR /app

COPY --from=build /app/dist ./dist
COPY server.mjs ./

# `node` (uid 1000) ships with the base image. Nothing here is written at
# runtime, so the whole tree can stay read-only to the process that serves it.
USER node

EXPOSE 8080

# Serves ./dist and passes /api/* to API_PROXY_TARGET (default
# http://backend:8000). PORT and API_PROXY_TARGET are the only knobs — see
# 07-frontend/.env.example.
CMD ["node", "server.mjs"]
