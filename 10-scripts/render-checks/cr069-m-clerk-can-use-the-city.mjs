// ── Trace ──────────────────────────────────────────────
// Story:    US-INT-042 (EP-INT-12) — CR-069 wave M
// Defects:  DEF-INT-4267 (this check's subject) · DEF-SHL-4272 (why it is not
//           a browser walk)
// Rules:    BR-MET-035 — a Billing Clerk may create a premises
// ───────────────────────────────────────────────────────
/**
 * `DEF-INT-4267`, proved through the RUNNING SERVER as the Billing Clerk.
 *
 *     DATABASE_URL=… python manage.py seed_demo
 *     DATABASE_URL=… python manage.py seed_gis_city --tenant brazosbend
 *     DATABASE_URL=… ALLOWED_HOSTS='*' python manage.py runserver 127.0.0.1:8099
 *     node 10-scripts/render-checks/cr069-m-clerk-can-use-the-city.mjs
 *
 * ⚠ **WHY THIS EXISTS AT ALL.** The City address search and the Create beside
 * it were gated to `{system_admin, executive}` — a Billing Clerk was refused
 * `403 AUTH-002` on the SEARCH, the panel read that as *this tenant has no
 * City* and removed itself, and the feature did not exist for her, silently.
 * Every backend case in the wave drove the services directly or through an
 * admin fixture, and every walkthrough in this repo signs in as an
 * administrator, so nothing could see it. **The only check that can is one
 * that is somebody else.**
 *
 * ⚠ **AND IT IS HTTP RATHER THAN A BROWSER WALK, WHICH IS NOT A SHORTCUT —
 * `DEF-SHL-4272`.** A Billing Clerk cannot reach ANY screen in this product
 * today: the shell boots by reading `GET /settings/company` and
 * `GET /settings/regional`, both `SettingsReadAnyWriteSystemAdmin`, so she
 * signs in, lands on `/dashboard`, and every page renders *"We couldn't load
 * your regional settings."* with a Retry that cannot succeed. That is older
 * than this wave (2026-08-21) and is filed separately. When it is fixed, this
 * check should become a browser walk — and the walk will then be the first in
 * the repo that is not an administrator.
 *
 * ⚠ **THE SEEDED CLERK IS `invited` AND HAS NO PASSWORD**, which is right for
 * a sample tenant and useless here. Activate her in the throwaway clone first:
 * set `password_hash = make_password(...)`, `must_change_password = False`, and
 * the membership to ACTIVE. Never in a database anyone else is using.
 */
const BASE = process.env.BASE ?? "http://127.0.0.1:8099";
const TENANT = process.env.TENANT ?? "brazosbend";

async function main() {
  const signin = await fetch(`${BASE}/api/${TENANT}/auth/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: "sam.reyes@sample.test", password: "S3cure!passw0rd" }),
  });
  const cookie = (signin.headers.getSetCookie?.() ?? []).map((c) => c.split(";")[0]).join("; ");
  const me = await (await fetch(`${BASE}/api/${TENANT}/me`, { headers: { cookie } })).json();
  console.log(`signed in as ${me.email ?? me.data?.email} · role ${me.role ?? me.data?.role}`);

  const search = await fetch(
    `${BASE}/api/${TENANT}/integrations/gis_city/address-search?q=1408+Pec`,
    { headers: { cookie } },
  );
  const found = await search.json();
  console.log(`GET address-search → ${search.status}  candidates: ${found.candidates?.length}`);

  const before = await (
    await fetch(`${BASE}/api/${TENANT}/premises?per=1`, { headers: { cookie } })
  ).json();
  const owners = await (
    await fetch(`${BASE}/api/${TENANT}/premises-owners?active=true&per=1`, { headers: { cookie } })
  ).json();
  const owner = owners.results?.[0]?.id ?? owners.data?.results?.[0]?.id ?? null;

  const create = await fetch(`${BASE}/api/${TENANT}/integrations/gis_city/premises`, {
    method: "POST",
    headers: { "content-type": "application/json", cookie },
    body: JSON.stringify({
      parcel: found.candidates?.[0]?.parcel,
      session: found.session,
      premises: {
        address_line: found.candidates?.[0]?.address_line,
        premises_type: "single_family",
        owner_id: owner,
      },
    }),
  });
  const made = await create.json();
  console.log(
    `POST premises   → ${create.status}  parcel ${made.external_ref ?? "-"}  unchecked ${made.gis_unchecked}`,
  );
  const after = await (
    await fetch(`${BASE}/api/${TENANT}/premises?per=1`, { headers: { cookie } })
  ).json();
  console.log(`premises count  ${before.count} → ${after.count}`);
  if (create.status !== 201 || search.status !== 200) {
    console.log("FAIL — the clerk is still refused");
    process.exit(1);
  }
  console.log("the Billing Clerk can search the City and create from a candidate.");
}

await main();
