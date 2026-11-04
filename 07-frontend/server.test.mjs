// ── Tests for server.mjs — the /api pass-through, not the pretty parts ───────
//
// Run: npm run test:server   (node's built-in runner; no dependencies)
//
// These do not live in src/ and are not vitest tests on purpose: server.mjs is
// container plumbing, not application code, and it is exercised by SPAWNING the
// real entrypoint rather than by importing pieces of it — the thing shipped is
// the thing tested.
//
// What is asserted, and why each one matters more than it looks:
//   · a client route falls back to index.html            (deep links / refresh)
//   · an /api 404 stays a 404 with the API's own body    (⚠ that 404 IS the
//     tenant-isolation answer — an unknown tenant and a foreign tenant are
//     deliberately indistinguishable; serving index.html instead would answer
//     "yes, here is the app" to both)
//   · Cookie reaches the API and Set-Cookie comes back untouched  (⚠ the
//     session cookie is the sole carrier of tenant scope on this one origin)
//   · the path, method, query and body are relayed verbatim, and the tenant
//     segment survives                                   (BR-TEN-003)
//   · a 202 stays a 202                                  (BE-07 job contract)
//   · X-Forwarded-For gains our peer                     (TRUSTED_PROXY_COUNT=1)
//   · with API_PROXY_TARGET empty, /api/* answers 404 and NEVER index.html

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdtemp, writeFile, mkdir, readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { after, before, describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const SERVER = fileURLToPath(new URL("./server.mjs", import.meta.url));
const INDEX_MARKER = "<!doctype html><title>SPA INDEX</title>";

let dist;
let upstream;
let upstreamPort;
let lastRequest = null;
let upstreamHandler = null;

/** Ephemeral port, released just before the real listener claims it. */
async function freePort() {
  const probe = createServer();
  await new Promise((r) => probe.listen(0, "127.0.0.1", r));
  const { port } = probe.address();
  await new Promise((r) => probe.close(r));
  return port;
}

/** Spawn server.mjs and wait until it answers. Returns { port, stop() }. */
async function startSpa(env) {
  const port = await freePort();
  const child = spawn(process.execPath, [SERVER], {
    env: { ...process.env, PORT: String(port), STATIC_DIR: dist, ...env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  child.stderr.on("data", (b) => process.stderr.write(`[spa] ${b}`));
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      await fetch(`http://127.0.0.1:${port}/`);
      return { port, stop: () => child.kill("SIGKILL") };
    } catch {
      await new Promise((r) => setTimeout(r, 50));
    }
  }
  child.kill("SIGKILL");
  throw new Error("spa server did not start");
}

before(async () => {
  dist = await mkdtemp(join(tmpdir(), "sbh-dist-"));
  await writeFile(join(dist, "index.html"), INDEX_MARKER);
  await mkdir(join(dist, "assets"));
  await writeFile(join(dist, "assets", "app-abc123.js"), "export const x = 1;\n");

  upstream = createServer((req, res) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      lastRequest = {
        method: req.method,
        url: req.url,
        headers: req.headers,
        body: Buffer.concat(chunks).toString(),
      };
      if (upstreamHandler) return upstreamHandler(req, res);
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ ok: true }));
    });
  });
  await new Promise((r) => upstream.listen(0, "127.0.0.1", r));
  upstreamPort = upstream.address().port;
});

after(() => upstream?.close());

describe("SPA fallback", () => {
  let spa;
  before(async () => {
    spa = await startSpa({ API_PROXY_TARGET: `http://127.0.0.1:${upstreamPort}` });
  });
  after(() => spa.stop());

  it("serves index.html for a client route that is not a file", async () => {
    const res = await fetch(`http://127.0.0.1:${spa.port}/brazosbend/settings/company`);
    assert.equal(res.status, 200);
    assert.match(res.headers.get("content-type"), /text\/html/);
    assert.equal(await res.text(), INDEX_MARKER);
  });

  it("serves a real asset with an immutable cache header", async () => {
    const res = await fetch(`http://127.0.0.1:${spa.port}/assets/app-abc123.js`);
    assert.equal(res.status, 200);
    assert.match(res.headers.get("content-type"), /javascript/);
    assert.equal(res.headers.get("cache-control"), "public, max-age=31536000, immutable");
  });

  it("does not let a traversal escape the bundle directory", async () => {
    const res = await fetch(`http://127.0.0.1:${spa.port}/../../etc/passwd`);
    assert.equal(res.status, 200); // normalised back inside, then SPA fallback
    assert.equal(await res.text(), INDEX_MARKER);
  });
});

describe("/api pass-through", () => {
  let spa;
  before(async () => {
    spa = await startSpa({ API_PROXY_TARGET: `http://127.0.0.1:${upstreamPort}` });
  });
  after(() => {
    spa.stop();
    upstreamHandler = null;
  });

  it("keeps an API 404 a 404 and never substitutes index.html", async () => {
    // The API's 404 for an unknown OR foreign tenant is a security answer.
    upstreamHandler = (_req, res) => {
      res.writeHead(404, { "content-type": "application/json" });
      res.end(JSON.stringify({ code: "NOT_FOUND", trace_id: "t-1" }));
    };
    const res = await fetch(`http://127.0.0.1:${spa.port}/api/nosuchtenant/settings/company`);
    assert.equal(res.status, 404);
    const body = await res.text();
    assert.equal(body, JSON.stringify({ code: "NOT_FOUND", trace_id: "t-1" }));
    assert.doesNotMatch(body, /SPA INDEX/);
  });

  it("relays Cookie to the API and returns Set-Cookie untouched", async () => {
    const setCookie = "sbh_session=abc123; Path=/; HttpOnly; SameSite=Lax";
    upstreamHandler = (_req, res) => {
      res.writeHead(200, { "set-cookie": setCookie, "content-type": "application/json" });
      res.end("{}");
    };
    const res = await fetch(`http://127.0.0.1:${spa.port}/api/brazosbend/me`, {
      headers: { cookie: "sbh_session=abc123" },
    });
    assert.equal(res.status, 200);
    assert.equal(lastRequest.headers.cookie, "sbh_session=abc123");
    assert.equal(res.headers.getSetCookie()[0], setCookie);
  });

  it("relays method, path, query and body verbatim — tenant segment intact", async () => {
    upstreamHandler = null;
    const res = await fetch(`http://127.0.0.1:${spa.port}/api/brazosbend/exports?scope=all`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ kind: "units" }),
    });
    assert.equal(res.status, 200);
    assert.equal(lastRequest.method, "POST");
    assert.equal(lastRequest.url, "/api/brazosbend/exports?scope=all");
    assert.equal(lastRequest.body, JSON.stringify({ kind: "units" }));
  });

  it("passes a 202 through as a 202", async () => {
    upstreamHandler = (_req, res) => {
      res.writeHead(202, { "content-type": "application/json" });
      res.end(JSON.stringify({ job_id: "j-1" }));
    };
    const res = await fetch(`http://127.0.0.1:${spa.port}/api/brazosbend/exports`, { method: "POST" });
    assert.equal(res.status, 202);
  });

  it("appends its own peer to X-Forwarded-For", async () => {
    upstreamHandler = null;
    await fetch(`http://127.0.0.1:${spa.port}/api/brazosbend/me`, {
      headers: { "x-forwarded-for": "203.0.113.9" },
    });
    // Rightmost entry is what the proxy saw; TRUSTED_PROXY_COUNT=1 reads exactly
    // that one and ignores everything a client prepended.
    const chain = lastRequest.headers["x-forwarded-for"].split(",").map((s) => s.trim());
    assert.equal(chain[0], "203.0.113.9");
    assert.match(chain.at(-1), /127\.0\.0\.1|::1|::ffff:127\.0\.0\.1/);
  });
});

describe("with no API configured (API_PROXY_TARGET empty)", () => {
  let spa;
  before(async () => {
    spa = await startSpa({ API_PROXY_TARGET: "" });
  });
  after(() => spa.stop());

  it("answers /api/* with 404, never index.html", async () => {
    const res = await fetch(`http://127.0.0.1:${spa.port}/api/brazosbend/settings/company`);
    assert.equal(res.status, 404);
    const body = await res.text();
    assert.doesNotMatch(body, /SPA INDEX/);
  });

  it("still serves the SPA for client routes", async () => {
    const res = await fetch(`http://127.0.0.1:${spa.port}/brazosbend/dashboard`);
    assert.equal(res.status, 200);
    assert.equal(await res.text(), INDEX_MARKER);
  });
});

// ── CR-069 wave M · the base Content-Security-Policy is written TWICE ────────
//
// ⚠ **THIS TEST IS THE GUARANTEE A COMMENT CLAIMED BEFORE IT EXISTED.**
// `server.mjs` sets the enforcing header on the DOCUMENT, and
// `06-backend/apps/integrations/page_policy.py` generates the same policy for
// the API — a Node process cannot import a Python module, so the base
// directives are declared in both files. The comment beside the copy in
// `server.mjs` said this test kept them in step, and the test did not exist:
// hard-won law 1, written by the lane that had just quoted law 1. It mattered
// within the hour — `DEF-INT-4261` (the policy blocked this product's own
// webfont) had to be fixed in both, and a fix in one is silently half a fix.
//
// It parses the PYTHON, deliberately, rather than trusting a duplicated
// literal here: a third copy would be the same drift one file further along.
describe("the base page-security policy, in both of its two homes", () => {
  const POLICY_PY = fileURLToPath(
    new URL("../06-backend/apps/integrations/page_policy.py", import.meta.url),
  );

  // ⚠ NEITHER COPY IS IMPORTED. Importing `server.mjs` starts a listener
  // unless `SPA_SERVER_NO_LISTEN` is set, and that variable then leaks into
  // every server this file SPAWNS — the first draft did exactly that and ten
  // of the thirteen tests were CANCELLED while these three passed and the run
  // printed `fail 0`. Both are read as source, which is also the honest shape:
  // the question is whether two DECLARATIONS agree.
  async function policyFromServerMjs() {
    const source = await readFile(SERVER, "utf8");
    const block = source.match(/const BASE_POLICY = \[([\s\S]*?)\]\.join\("; "\);/);
    assert.ok(block, "BASE_POLICY not found in server.mjs");
    return [...block[1].matchAll(/"([^"]+)"/g)].map(([, one]) => one).join("; ");
  }

  it("server.mjs's BASE_POLICY is byte-identical to page_policy.BASE_DIRECTIVES", async () => {
    const python = await readFile(POLICY_PY, "utf8");
    const block = python.match(
      /BASE_DIRECTIVES:[^=]*=\s*\(([\s\S]*?)\n\)/,
    );
    assert.ok(block, "BASE_DIRECTIVES not found in page_policy.py");

    const fromPython = [...block[1].matchAll(/\(\s*"([a-z-]+)"\s*,\s*\(([^)]*)\)/g)].map(
      ([, directive, sources]) => {
        const values = [...sources.matchAll(/"([^"]+)"/g)].map(([, one]) => one);
        return `${directive} ${values.join(" ")}`;
      },
    );
    assert.ok(fromPython.length > 5, "parsed too few directives — the shape moved");

    assert.equal(
      await policyFromServerMjs(),
      fromPython.join("; "),
      "server.mjs and page_policy.py disagree about the base policy — fix BOTH",
    );
  });

  it("the base policy permits this product's own webfont (DEF-INT-4261)", async () => {
    const policy = await policyFromServerMjs();
    assert.match(policy, /style-src[^;]*https:\/\/fonts\.googleapis\.com/);
    assert.match(policy, /font-src[^;]*https:\/\/fonts\.gstatic\.com/);
  });

  it("permits nothing by wildcard", async () => {
    assert.doesNotMatch(await policyFromServerMjs(), /\*/);
  });

  // ⚠ `DEF-INT-4410` — THE PRODUCT'S OWN DOCUMENTS, AND WHY THIS IS AN
  // ASSERTION AND NOT A COMMENT. `frame-src 'none'` and `object-src 'none'`
  // shipped with the policy on 2026-09-06 and blanked BOTH screens that show a
  // person a bill: the staff Document tab frames
  // `/api/{tenant}/…/document.pdf`, the portal's `DocumentPreview` embeds the
  // kept file in an `<object>`, and both are same-origin. Every check in this
  // file passed over it — the two copies agreed, the webfont was permitted and
  // there was no wildcard — because none of them asks whether the policy
  // permits the thing the product actually does.
  //
  // So this test names the two screens. A lane tightening either directive back
  // to `'none'` fails here and reads WHY, instead of shipping two grey boxes.
  it("permits this product's own same-origin documents (DEF-INT-4410)", async () => {
    const policy = await policyFromServerMjs();
    // The staff bill's Document tab — an <iframe> at /api/{tenant}/…/document.pdf
    assert.match(policy, /(?:^|; )frame-src [^;]*'self'/);
    // The portal's DocumentPreview — an <object> at the same kind of address
    assert.match(policy, /(?:^|; )object-src [^;]*'self'/);
    // …and neither may be 'none', which reads as NO FRAMES AT ALL whatever
    // else is beside it.
    assert.doesNotMatch(policy, /(?:^|; )frame-src [^;]*'none'/);
    assert.doesNotMatch(policy, /(?:^|; )object-src [^;]*'none'/);

    // ⚠ THE HALF THAT ACTUALLY BLANKED THE SCREENS. `frame-src` governs what
    // this page may frame; `frame-ancestors` rides on the FRAMED resource —
    // and the API puts this same policy on the PDF — so 'none' there refused
    // our own same-origin page with net::ERR_BLOCKED_BY_RESPONSE. Moving
    // frame-src alone changed nothing in a browser, which is why this
    // assertion is here beside it rather than trusted to a comment.
    assert.match(policy, /(?:^|; )frame-ancestors 'self'/);
  });
});
