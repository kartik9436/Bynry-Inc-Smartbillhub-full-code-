// ── SMARTBillHub SPA server ──────────────────────────────────────────────────
//
// WHY THIS FILE EXISTS, AND WHY IT IS NOT nginx.
//
// The SPA and the API are separate containers, but the application is built
// SAME-ORIGIN: src/api/client.ts calls `/api/{tenant}/…` against an empty base
// URL, and the identity session cookie is host-scoped and httpOnly. Split those
// across two origins and both break at once — the fetches become cross-origin
// and the cookie stops riding. Something must therefore put the SPA and the API
// on one origin.
//
// There is NO load balancer and NO nginx in this deployment (PO, 2026-08-10:
// "No I'm not using any ALB as of now"; "no nginx no dns things — I will manage
// that from outside"). So this server IS the join: it serves the built bundle
// and passes `/api/*` through to the API container. That pass-through is the
// PRIMARY routing mechanism, not a local-dev convenience — the whole product is
// reached through this container's single published port. `API_PROXY_TARGET`
// changes WHERE the API is; it is not a feature switch, and setting it empty
// leaves the product with no API at all (the /api routes then answer 404 — see
// below for why that is the only safe answer).
//
// Node builtins only: no express, no http-proxy, no node_modules in the runtime
// image. The whole runtime layer is `dist/` plus this file.
//
// FOUR BEHAVIOURS THAT ARE LOAD-BEARING, not stylistic:
//
//  1. Unknown paths fall back to index.html — `/brazosbend/settings/company` is
//     a client route, not a file. Without the fallback every deep link and every
//     refresh 404s.
//  2. `/api/*` NEVER falls back to index.html. The API's 404 is the answer to
//     "does this tenant exist / is it mine" — core.tenancy.require_tenant raises
//     404 for an unknown tenant AND for a foreign one, byte-identically, so the
//     two are indistinguishable (HR-1). Answering 200 + index.html instead would
//     turn a tenant-isolation answer into "sure, here's the app".
//  3. Status, headers and body pass through verbatim: the upstream's 404 stays
//     404, its 202 stays 202, its `Set-Cookie` is returned untouched, and the
//     client's `Cookie` reaches it unmodified. Bodies are STREAMED, never
//     buffered — `GET /api/exports/{id}/file` is a CSV download.
//  4. The path is never rewritten. The segment after `/api/` IS the tenant
//     (BR-TEN-003); dropping or rewriting it would re-point the request at
//     another tenant's data.
//
// The one header this proxy does modify is `X-Forwarded-For`, which it appends
// its own peer to — that is what makes the backend's TRUSTED_PROXY_COUNT=1 tell
// the truth about who is calling (see 06-backend/.env.example).
//
// FIVE, SINCE CR-069 WAVE M (2026-09-06): THE CONTENT-SECURITY-POLICY.
//
// ⚠ **THIS DEPLOYMENT HAD NONE AT ALL UNTIL THAT DATE** — `US-INT-042` §1's
// own sentence — while the assets map fetched hundreds of third-party tiles
// per pan. A browser applies a policy to the DOCUMENT it arrived with and to
// everything that document fetches; a header on an XHR response governs
// nothing. **This server is the only thing in the deployment that serves
// `index.html`, so it is the only place the enforcing header can be set.**
//
// The policy is GENERATED, never typed: the API builds it from the manifests'
// registered BROWSER operations and the tenant's own connections
// (`apps/integrations/page_policy.py`), so a host is permitted because a
// utility connected it. This file asks for it — `GET /api/{tenant}/
// integrations/page-policy`, which is `AllowAny` for the reason that module's
// docstring gives — and caches it briefly per tenant.
//
// ⚠ **IT FAILS CLOSED.** Any answer but a 200, any parse problem, any tenant
// it cannot resolve: `BASE_POLICY` below, which permits `'self'` and nothing
// third-party. The permissive answer has to be earned.
//
// TLS, redirects and HSTS are deliberately absent: the edge is managed outside
// the box (PO ruling above).
//
// Tested by server.test.mjs (`npm run test:server`) — the 404-not-rewritten and
// cookie-passthrough cases especially, because a mistake in either breaks a
// security property silently instead of visibly.

import { createReadStream } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer, request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const PORT = Number(process.env.PORT || 8080);
const HOST = process.env.HOST || "0.0.0.0";
const API_PROXY_TARGET = (process.env.API_PROXY_TARGET ?? "http://backend:8000").trim();
const DIST = resolve(
  process.env.STATIC_DIR || join(fileURLToPath(new URL(".", import.meta.url)), "dist"),
);

const CONTENT_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".map": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".avif": "image/avif",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".txt": "text/plain; charset=utf-8",
  ".webmanifest": "application/manifest+json",
};

// Hop-by-hop headers belong to one connection and must not be relayed onto the
// next one (RFC 9110 §7.6.1). Node sets its own on each hop.
const HOP_BY_HOP = ["connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailer", "transfer-encoding", "upgrade"];

const isApiPath = (pathname) => pathname === "/api" || pathname.startsWith("/api/");

// ── CR-069 wave M · the generated Content-Security-Policy ───────────────────

// The closed answer. ⚠ KEPT IN STEP WITH `page_policy.BASE_DIRECTIVES` BY
// `server.test.mjs`, which asserts the two strings are identical — two copies
// of one policy is exactly the drift hard-won law 5 is about, and this one is
// unavoidable because a Node process cannot import a Python module.
const BASE_POLICY = [
  "default-src 'self'",
  "script-src 'self'",
  // `DEF-INT-4261` — this product's OWN webfont. `tokens.css` imports Archivo
  // from Google Fonts; without these two hosts every screen renders in the
  // fallback system font, silently.
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "img-src 'self' data: blob:",
  "font-src 'self' data: https://fonts.gstatic.com",
  // CR-169-BRC10 (PO 2026-10-04, answer 2: PostHog US cloud) — the ingest host
  // and the host that serves each project's remote config. posthog-js and its
  // recorder are BUNDLED, so script-src stays self and no PostHog script host
  // appears anywhere. A build with no key sends nothing to either.
  "connect-src 'self' https://us.i.posthog.com https://us-assets.i.posthog.com",
  // ⚠ NO DOUBLE QUOTES IN THIS BLOCK'S COMMENTS — `server.test.mjs` parses the
  // array by pulling every quoted string out of it, so a quoted phrase here
  // becomes a directive and the byte-identical check fails on prose.
  //
  // `DEF-INT-4410` — THIS PRODUCT'S OWN DOCUMENTS. Both were `'none'` from the
  // day this policy landed, and both screens that show a customer their bill
  // are SAME-ORIGIN embeds: `BillDetailPage.tsx` frames
  // `/api/{tenant}/…/document.pdf` (a frame, so the browser's own PDF viewer
  // carries print and save — `BR-BIL-036`'s floor) and the portal's
  // `DocumentPreview` shows the kept file in an `<object>` (the only one of the
  // three with a child fallback). A browser refuses both, and what the Product
  // Owner saw was an empty grey box saying the content is blocked — us blocking
  // us.
  //
  // `'self'` and not `*`: nothing off this origin may be framed or embedded.
  // (`frame-ancestors` below moved to `'self'` in the same fix and for the same
  // reason — it is the OTHER half, and it still refuses every other site.)
  "frame-src 'self'",
  "object-src 'self'",
  "base-uri 'none'",
  "form-action 'self'",
  // `DEF-INT-4410`, THE OTHER HALF — and this one is what the Product Owner
  // actually saw. `frame-src` above governs what THIS page may frame;
  // `frame-ancestors` travels on the FRAMED resource and says who may frame
  // IT, and `page_policy`'s middleware puts this same policy on every API
  // response — the bill PDF included. So `'none'` there refused our own page,
  // same origin and all: Chromium answers `net::ERR_BLOCKED_BY_RESPONSE` and
  // draws the interstitial saying the content is blocked. Fixing `frame-src`
  // alone changed nothing; both had to move, and only a browser could show
  // that.
  //
  // `'self'` and not `*`: the SPA and the API are ONE ORIGIN by construction
  // (this file is the join), so `'self'` permits exactly this product to embed
  // exactly its own documents and refuses every other site, which is the whole
  // of the clickjacking protection `'none'` was there for.
  "frame-ancestors 'self'",
].join("; ");

const POLICY_TTL_MS = 60_000;
const policyCache = new Map(); // tenant -> { policy, at }

/** The tenant slug a SPA path names, or null. `/brazosbend/premises` -> `brazosbend`. */
function tenantOf(pathname) {
  const first = pathname.split("/").filter(Boolean)[0];
  return first && /^[-a-zA-Z0-9_]+$/.test(first) ? first : null;
}

/** Ask the API for this tenant's generated policy. Never throws. */
function fetchPolicy(tenant, cookie) {
  return new Promise((resolve) => {
    if (!API_PROXY_TARGET) return resolve(BASE_POLICY);
    let target;
    try {
      target = new URL(API_PROXY_TARGET);
    } catch {
      return resolve(BASE_POLICY);
    }
    const secure = target.protocol === "https:";
    const send = secure ? httpsRequest : httpRequest;
    const req = send(
      {
        protocol: target.protocol,
        hostname: target.hostname,
        port: target.port || (secure ? 443 : 80),
        method: "GET",
        path: `/api/${encodeURIComponent(tenant)}/integrations/page-policy`,
        headers: cookie ? { cookie } : {},
        timeout: 2000,
      },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => {
          if (res.statusCode !== 200) return resolve(BASE_POLICY);
          try {
            const parsed = JSON.parse(body);
            resolve(typeof parsed.policy === "string" && parsed.policy ? parsed.policy : BASE_POLICY);
          } catch {
            resolve(BASE_POLICY);
          }
        });
      },
    );
    req.on("error", () => resolve(BASE_POLICY));
    req.on("timeout", () => {
      req.destroy();
      resolve(BASE_POLICY);
    });
    req.end();
  });
}

/** The policy for a document request. Cached per tenant for POLICY_TTL_MS. */
export async function policyForRequest(pathname, cookie) {
  const tenant = tenantOf(pathname);
  if (!tenant) return BASE_POLICY;
  const cached = policyCache.get(tenant);
  if (cached && Date.now() - cached.at < POLICY_TTL_MS) return cached.policy;
  const policy = await fetchPolicy(tenant, cookie);
  policyCache.set(tenant, { policy, at: Date.now() });
  return policy;
}

export { BASE_POLICY };

const stripHopByHop = (headers) => {
  const out = { ...headers };
  for (const name of HOP_BY_HOP) delete out[name];
  return out;
};

/** Pass /api/* through to the API container, changing as little as possible. */
function proxyToApi(req, res) {
  const target = new URL(API_PROXY_TARGET);
  const secure = target.protocol === "https:";
  const headers = stripHopByHop(req.headers);
  // Host is forwarded UNCHANGED: same-origin means the API sees the name the
  // browser used, which is what DJANGO_ALLOWED_HOSTS validates against.
  // X-Forwarded-For gains the address we saw, appended — the backend reads the
  // chain right-to-left with TRUSTED_PROXY_COUNT hops of trust.
  headers["x-forwarded-for"] = [req.headers["x-forwarded-for"], req.socket.remoteAddress]
    .filter(Boolean)
    .join(", ");

  const send = secure ? httpsRequest : httpRequest;
  const upstream = send(
    {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port || (secure ? 443 : 80),
      method: req.method,
      path: req.url, // verbatim: path + query, tenant segment and all
      headers,
    },
    (upstreamRes) => {
      // Status verbatim; headers verbatim minus hop-by-hop. `set-cookie` arrives
      // as an array and writeHead preserves it, so the session cookie the
      // identity module set is returned exactly as it was written.
      res.writeHead(upstreamRes.statusCode, stripHopByHop(upstreamRes.headers));
      upstreamRes.pipe(res); // streamed, not buffered
    },
  );

  upstream.on("error", (err) => {
    if (!res.headersSent) {
      res.writeHead(502, { "content-type": "application/json; charset=utf-8" });
    }
    res.end(JSON.stringify({ detail: `API unreachable at ${API_PROXY_TARGET}: ${err.code || err.message}` }));
  });

  req.pipe(upstream); // request body streamed too
  req.on("aborted", () => upstream.destroy());
}

/** Resolve a URL path to a file inside DIST, or null if it escapes DIST. */
function resolveStatic(pathname) {
  let decoded;
  try {
    decoded = decodeURIComponent(pathname);
  } catch {
    return null; // malformed percent-encoding
  }
  if (decoded.includes("\0")) return null;
  const candidate = resolve(DIST, "." + normalize(decoded.startsWith("/") ? decoded : "/" + decoded));
  return candidate === DIST || candidate.startsWith(DIST + sep) ? candidate : null;
}

function sendFile(req, res, filePath, size, extra = {}) {
  const type = CONTENT_TYPES[extname(filePath).toLowerCase()] || "application/octet-stream";
  res.writeHead(200, { "content-type": type, "content-length": size, ...extra });
  if (req.method === "HEAD") return res.end();
  createReadStream(filePath).pipe(res);
}

async function serveStatic(req, res, pathname) {
  if (req.method !== "GET" && req.method !== "HEAD") {
    res.writeHead(405, { allow: "GET, HEAD", "content-type": "text/plain; charset=utf-8" });
    return res.end("method not allowed\n");
  }

  const filePath = resolveStatic(pathname);
  if (filePath) {
    const info = await stat(filePath).catch(() => null);
    if (info?.isFile()) {
      // Vite emits content-hashed names under /assets/, so those are immutable
      // forever. Everything else — index.html above all — must revalidate, or a
      // deploy leaves browsers on the previous bundle.
      const cache = pathname.startsWith("/assets/")
        ? "public, max-age=31536000, immutable"
        : "no-cache";
      return sendFile(req, res, filePath, info.size, { "cache-control": cache });
    }
  }

  // Unknown path. `/api/*` must NOT become the app — see note 2 in the header.
  // Reaching here for an /api path means API_PROXY_TARGET is empty, i.e. there
  // is no API configured; 404 is the honest answer and the safe one.
  if (isApiPath(pathname)) {
    res.writeHead(404, { "content-type": "application/json; charset=utf-8" });
    return res.end(JSON.stringify({ detail: "no API is configured on this origin (API_PROXY_TARGET is empty)" }));
  }

  const index = join(DIST, "index.html");
  const info = await stat(index).catch(() => null);
  if (!info?.isFile()) {
    res.writeHead(500, { "content-type": "text/plain; charset=utf-8" });
    return res.end(`no index.html in ${DIST} — was the bundle built?\n`);
  }
  // CR-069 wave M — the enforcing header, on the DOCUMENT. Generated per
  // tenant from the registered browser operations; BASE_POLICY on any doubt.
  const policy = await policyForRequest(pathname, req.headers.cookie);
  return sendFile(req, res, index, info.size, {
    "cache-control": "no-cache",
    "content-security-policy": policy,
  });
}

export const app = createServer((req, res) => {
  const pathname = (req.url || "/").split("?")[0];
  if (isApiPath(pathname) && API_PROXY_TARGET) return proxyToApi(req, res);
  serveStatic(req, res, pathname).catch((err) => {
    if (!res.headersSent) res.writeHead(500, { "content-type": "text/plain; charset=utf-8" });
    res.end(`internal error: ${err.message}\n`);
  });
});

// Started unless imported by a test.
if (!process.env.SPA_SERVER_NO_LISTEN) {
  app.listen(PORT, HOST, () => {
    console.log(`spa: serving ${DIST} on http://${HOST}:${PORT}`);
    console.log(
      API_PROXY_TARGET
        ? `spa: /api/* → ${API_PROXY_TARGET} (same-origin pass-through)`
        : "spa: API_PROXY_TARGET is empty — /api/* answers 404, the app has no API",
    );
  });
  for (const signal of ["SIGTERM", "SIGINT"]) {
    process.on(signal, () => app.close(() => process.exit(0)));
  }
}
