/**
 * The handset the on-site, closing and raise screens are tested on: a real
 * tenant store (better-sqlite3, every query the SQL it is), seeded with the
 * boards' own test data (B14 rule 37: figures on a board are illustrations —
 * used here as test data, never as facts the code builds to), mounted under
 * the REAL navigator inside the real session, language, theme and
 * `FieldDataProvider` — never a bare component (hard-won law 2's fixture
 * lesson: a routed screen is mounted under its real route).
 *
 * Times are LOCAL (no `Z`): the screens show the handset's own clock.
 */
import 'react-native-gesture-handler/jestSetup';

import { CommonActions, createNavigationContainerRef, NavigationContainer, type ParamListBase } from '@react-navigation/native';
import { act, render, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';

import type { TenantDb } from '../../../src/db/database';
import * as activityQ from '../../../src/db/queries/activity';
import * as assetQ from '../../../src/db/queries/asset';
import * as crewTimeQ from '../../../src/db/queries/crewTime';
import * as customerQ from '../../../src/db/queries/customer';
import * as documentQ from '../../../src/db/queries/document';
import * as outboxQ from '../../../src/db/queries/outbox';
import * as premiseQ from '../../../src/db/queries/premise';
import * as searchQ from '../../../src/db/queries/searchIndex';
import * as technicianQ from '../../../src/db/queries/technician';
import * as templatesQ from '../../../src/db/queries/workOrderTemplates';
import * as woItemQ from '../../../src/db/queries/woItem';
import * as woReadingQ from '../../../src/db/queries/woReading';
import * as workOrderQ from '../../../src/db/queries/workOrder';
import { scoped } from '../../../src/db/scoped';
import { applyChangesPage } from '../../../src/sync/delta';
import { createFieldI18n } from '../../../src/i18n/i18n';
import { I18nProvider } from '../../../src/i18n/I18nProvider';
import { AppNavigator } from '../../../src/navigation/AppNavigator';
import { routeTo } from '../../../src/navigation/routing';
import type { ScreenId } from '../../../src/navigation/screens';
import { UNKNOWN_STATUS, ShellStatusProvider } from '../../../src/navigation/ShellStatus';
import { unwiredSignature, type SignaturePort } from '../../../src/screens/closing/signature';
import { type FieldData, FieldDataProvider } from '../../../src/screens/onSite/fieldData';
import serverTemplate from '../../sync/support/serverTemplate.json';
import { FakeMoneyPort, type MoneyPort } from '../../../src/screens/onSite/money';
import { type DevicePorts, fakeDevicePorts } from '../../../src/screens/onSite/ports';
import { type ScannerPort, unwiredScanner } from '../../../src/screens/raise/scanner';
import { SessionProvider } from '../../../src/session/SessionProvider';
import { ThemeProvider, type ThemeName } from '../../../src/theme';
import { FakeClock, idSource, openStore } from '../../db/support/fixtures';
import { makeHandset, PEOPLE, signIn } from '../../session/fakes';

/** 10:00 on 20 October 2026 on the handset's own clock. */
export const NOW = new Date(2026, 9, 20, 10, 0, 0);
export const local = (d: number, h: number, m = 0) => new Date(2026, 9, d, h, m, 0).toISOString();

export const DANA = PEOPLE['d.ortiz']!.technicianId;
export const MARCO = PEOPLE['m.chen']!.technicianId;
export const PATEL = PEOPLE['r.patel']!.technicianId;

function upsertOrder(
  db: TenantDb,
  tech: string,
  o: {
    id: string;
    number: string;
    type: string;
    premiseId: string;
    customerId: string;
    accountId: string;
    assetId: string | null;
    windowStart?: string | null;
    windowEnd?: string | null;
    dueAt?: string | null;
    dispatchState?: string | null;
    priorityCode?: string | null;
    accessNotes?: string | null;
    templateId?: string | null;
    extra?: Record<string, unknown> | null;
  },
): void {
  const s = scoped(db, tech);
  workOrderQ.upsertFromServer(
    s,
    {
      id: o.id,
      number: o.number,
      type: o.type,
      state: 'in_progress',
      dispatchState: o.dispatchState ?? null,
      priorityCode: o.priorityCode ?? null,
      priorityRank: null,
      premiseId: o.premiseId,
      windowStart: o.windowStart ?? null,
      windowEnd: o.windowEnd ?? null,
      dueAt: o.dueAt ?? null,
      estMinutes: null,
      accessNotes: o.accessNotes ?? null,
      hazards: null,
      gateCode: null,
      extra: o.extra ?? null,
      serverUpdatedAt: null,
    },
    local(20, 7),
  );
  // The job card's links the mirror keeps beside the card (test data only).
  s.run(
    `UPDATE work_order SET customer_id = :c, account_id = :a, asset_id = :asset, template_id = :tpl
      WHERE technician_id = :technician_id AND id = :id`,
    { id: o.id, c: o.customerId, a: o.accountId, asset: o.assetId, tpl: o.templateId ?? null },
  );
}

/** The boards' world, as one technician's handset holds it. */
export function seed(db: TenantDb, tech: string = DANA): void {
  const now = local(20, 7);
  technicianQ.upsert(db, { id: DANA, name: 'D. Ortiz', role: 'Water II' }, now);
  technicianQ.upsert(db, { id: MARCO, name: 'M. Chen', role: 'Water I' }, now);
  technicianQ.upsert(db, { id: PATEL, name: 'R. Patel', role: 'Meter tech' }, now);
  // FB-023 F3 (DEF-FLD-10789): employment is NOT seeded by hand — it arrives
  // the way it does on a real phone, on the change feed's `technician` block
  // (`apps/work/mobile.changes`), applied by the real `applyChangesPage`.
  for (const [who, employment] of [[DANA, 'employee'], [MARCO, 'employee'], [PATEL, 'contractor']] as const) {
    applyChangesPage(db, who, { changes: [], count: 0, next_cursor: null, has_more: false, technician: { employment } }, new Date(now));
  }

  premiseQ.upsert(db, { id: 'p-1400', addressLine: '1400 Elm Street · Unit A', locality: 'Austin', region: 'TX', postalCode: '78704', lat: 30.2651, lng: -97.7494 }, now);
  premiseQ.upsert(db, { id: 'p-22', addressLine: '22 Cedar Court', locality: 'Austin', region: 'TX', postalCode: '78704' }, now);
  premiseQ.upsert(db, { id: 'p-95', addressLine: '95 Cedar Court', locality: 'Austin', region: 'TX', postalCode: '78704' }, now);

  customerQ.upsert(db, { id: 'c-sarah', name: 'Sarah Miller', accountNumber: 'A-10432', phone: '5125550100' }, now);
  customerQ.upsert(db, { id: 'c-aaron', name: 'Aaron Bruner', accountNumber: 'A-10588' }, now);
  customerQ.upsert(db, { id: 'c-priya', name: 'Priya Raghunathan', accountNumber: 'ACC-10377' }, now);

  assetQ.upsert(
    db,
    {
      id: 'a-4471',
      serial: 'W-4471',
      badge: '88-2041',
      deviceId: 'E1P-77412',
      model: 'Neptune T-10',
      size: '5/8"',
      service: 'Water',
      premiseId: 'p-1400',
      extra: { installed_at: '2019-03-14', location_note: 'Pit at the front kerb' },
      history: [
        { date: '2025-09-21', work: 'Leak investigation', outcome: 'passed', problem: 'High usage reported', done: 'Leak found on customer side', who: 'M. Chen', minutes: 52 },
        { date: '2026-06-12', work: 'Routine read', outcome: 'passed', problem: 'None reported', done: 'Read taken', who: 'R. Patel', minutes: 18, reading: { value: '48180', unit: 'gal' } },
        { date: '2026-02-03', work: 'Seal check', outcome: 'partially_done', problem: 'Security seal broken', done: 'Re-sealed · tamper logged', parts: '1 · wire seal', who: 'D. Ortiz', minutes: 34 },
      ],
    },
    now,
  );
  assetQ.upsert(db, { id: 'a-4471a', serial: 'W-4471-A', parentAssetId: 'a-4471', premiseId: 'p-1400', service: 'Water', history: [{ date: '2026-06-12', work: 'Routine read', reading: { value: '12210', unit: 'gal' } }] }, now);
  assetQ.upsert(db, { id: 'a-4471b', serial: 'W-4471-B', parentAssetId: 'a-4471', premiseId: 'p-1400', service: 'Water', history: [{ date: '2026-06-12', work: 'Routine read', reading: { value: '9044', unit: 'gal' } }] }, now);
  assetQ.upsert(db, { id: 'a-6120', serial: 'W-6120', badge: '88-6120', model: 'Neptune T-10', size: '5/8"', service: 'Water', premiseId: 'p-22' }, now);

  upsertOrder(db, tech, {
    id: 'wo-4822', number: 'WO-4822', type: 'Meter exchange', premiseId: 'p-1400', customerId: 'c-sarah', accountId: 'acc-10432',
    assetId: 'a-4471', windowStart: local(20, 8), windowEnd: local(20, 12), accessNotes: 'Dog in the yard. Pit lid is heavy.', templateId: 'tpl-exchange',
    // Worked since 08:46, so taken (DEF-FLD-10579): FF-15 offers Hand back, not Decline.
    extra: { technician_acceptance: { state: 'accepted', at: local(20, 8), reason: null } },
  });
  upsertOrder(db, tech, {
    id: 'wo-4824', number: 'WO-4824', type: 'Disconnect — non-payment', premiseId: 'p-22', customerId: 'c-aaron', accountId: 'acc-10588',
    assetId: 'a-6120', dispatchState: 'scheduled', priorityCode: 'P1',
  });
  upsertOrder(db, tech, {
    id: 'wo-4826', number: 'WO-4826', type: 'Restoration', premiseId: 'p-22', customerId: 'c-aaron', accountId: 'acc-10588',
    assetId: 'a-6120', dueAt: local(20, 13, 12),
  });
  upsertOrder(db, tech, {
    id: 'wo-4830', number: 'WO-4830', type: 'Reconnect', premiseId: 'p-95', customerId: 'c-priya', accountId: 'acc-10377', assetId: null,
  });

  const s = scoped(db, tech);
  const task = (id: string, wo: string, position: number, label: string, extra: Partial<woItemQ.WoItemInput> = {}) =>
    woItemQ.upsert(s, { id, workOrderId: wo, kind: 'task', position, label, ...extra }, now);
  task('t-24-1', 'wo-4824', 1, 'Photograph the meter', { state: 'done' });
  task('t-24-2', 'wo-4824', 2, 'Record the closing read', { state: 'done' });
  task('t-24-3', 'wo-4824', 3, 'Close the valve', { detail: { money_fresh_minutes: 5 } });
  task('t-26-1', 'wo-4826', 1, 'Open the kerb stop');
  task('t-26-2', 'wo-4826', 2, 'Check for flow and leaks');
  task('t-26-3', 'wo-4826', 3, 'Record the opening read', { photoRequired: true, photoMinCount: 1 });
  task('t-22-1', 'wo-4822', 1, 'Photograph the old meter', { photoRequired: true, photoMinCount: 1 });
  woItemQ.upsert(s, { id: 'm-22-1', workOrderId: 'wo-4822', kind: 'material', position: 1, label: 'Water meter 5/8"', detail: { used: 1 } }, now);
  woItemQ.upsert(s, { id: 'm-22-2', workOrderId: 'wo-4822', kind: 'material', position: 2, label: 'Wire seal', detail: { used: 1 } }, now);
  woReadingQ.upsert(s, { id: 'r-22-1', workOrderId: 'wo-4822', position: 1, prompt: 'Old meter final', unit: 'gal' }, now);

  documentQ.upsert(db, { id: 'd-sop', ownerKind: 'work_order', ownerId: 'wo-4822', title: 'Water shut-off SOP', kind: 'pdf', source: 'server', localPath: '/docs/sop.pdf', bytes: 2 * 1024 * 1024 }, now);
  documentQ.upsert(db, { id: 'd-guide', ownerKind: 'asset', ownerId: 'a-4471', title: 'Neptune T-10 install guide', kind: 'pdf', source: 'server', localPath: '/docs/t10.pdf', bytes: 20 * 1024 * 1024 }, now);
  documentQ.upsert(db, { id: 'd-confined', ownerKind: 'tenant', ownerId: null, title: 'Confined space procedure', kind: 'pdf', source: 'server', localPath: null }, now);
  documentQ.upsert(db, { id: 'd-traffic', ownerKind: 'tenant', ownerId: null, title: 'Traffic control setup', kind: 'pdf', source: 'server', localPath: '/docs/traffic.pdf', bytes: 1024 }, now);

  // The service as the server sends it — `{id, code, name}`, never plain text
  // (DEF-FLD-10613: every template test seeded 'Water' and none met the object).
  templatesQ.upsert(db, { id: 'tpl-leak', name: 'Leak investigation', version: '3', service: serverTemplate.service, stepCount: 4, safetyCount: 3, readingCount: 1, body: { steps: ['a', 'b', 'c', 'd'] } }, now);
  templatesQ.upsert(db, { id: 'tpl-exchange', name: 'Meter replacement', version: '7', service: serverTemplate.service, stepCount: 8, safetyCount: 4, readingCount: 2 }, now);
  templatesQ.upsert(db, { id: 'tpl-seal', name: 'Broken seal', version: '2', service: serverTemplate.service, stepCount: 3, safetyCount: 2 }, now);
  templatesQ.upsert(db, { id: 'tpl-draft', name: 'Draft thing', version: '1', published: false }, now);
  templatesQ.markUsed(db, 'tpl-leak', local(18, 9));
  templatesQ.markUsed(db, 'tpl-exchange', local(10, 9));

  // WO-4822's crew: D. Ortiz leads, M. Chen came with her (FF-29's board).
  crewTimeQ.insert(s, { id: 'ct-1', workOrderId: 'wo-4822', personId: DANA, kind: 'travel', startedAt: local(20, 8), endedAt: local(20, 8, 14) });
  crewTimeQ.insert(s, { id: 'ct-2', workOrderId: 'wo-4822', personId: DANA, kind: 'labour', startedAt: local(20, 8, 46), endedAt: local(20, 9, 58) });
  crewTimeQ.insert(s, { id: 'ct-3', workOrderId: 'wo-4822', personId: MARCO, kind: 'labour', startedAt: local(20, 8, 46), endedAt: local(20, 9, 58) });

  // WO-4822's story (FF-31) and notes (FF-30).
  const ev = (id: string, status: string, at: string, author: string, text: string | null = null) =>
    activityQ.insert(s, { id, workOrderId: 'wo-4822', kind: 'status', status, text, author, at });
  ev('e-1', 'raised', local(17, 14, 22), 'J. Okafor');
  ev('e-2', 'pushed', local(20, 7, 12), 'D. Ortiz');
  ev('e-3', 'accepted', local(20, 7, 48), 'D. Ortiz');
  ev('e-4', 'arrived', local(20, 8, 14), 'D. Ortiz', '30.2651, -97.7494 · ±4m');
  ev('e-5', 'work_started', local(20, 8, 46), 'D. Ortiz');
  ev('e-6', 'crew_joined', local(20, 8, 47), 'D. Ortiz', 'M. Chen');
  activityQ.insert(s, { id: 'n-1', workOrderId: 'wo-4822', kind: 'remark', status: 'dispatch', text: 'Customer works from home. Ring the side door.', author: 'J. Okafor', at: local(20, 7, 12) });
  activityQ.insert(s, { id: 'n-2', workOrderId: 'wo-4822', kind: 'remark', status: 'on_site', text: 'Pit lid seized.', author: 'D. Ortiz', at: local(20, 8, 52) });

  for (const id of ['a-4471', 'a-4471a', 'a-4471b', 'a-6120']) {
    const a = assetQ.get(db, id)!;
    searchQ.put(s, 'asset', id, { serial: a.serial, badge: a.badge, address: '1400 Elm Street' });
  }
}

export interface Wave {
  db: TenantDb;
  clock: FakeClock;
  money: FakeMoneyPort;
  device: ReturnType<typeof fakeDevicePorts>;
  data: FieldData;
}

export function makeWave(over: { tech?: string; money?: MoneyPort; device?: DevicePorts; scanner?: ScannerPort; signature?: SignaturePort } = {}): Wave {
  const clock = new FakeClock(NOW.getTime());
  const db = openStore('silver-creek', undefined, clock);
  seed(db, over.tech ?? DANA);
  const money = new FakeMoneyPort();
  const device = fakeDevicePorts({
    photos: [{ localPath: '/photos/1.jpg', sha256: 'aa', bytes: 1000 }],
    words: ['no leaks.'],
    location: { lat: 30.2612, lng: -97.7431, accuracy_m: 4, fix_at: local(20, 10) },
  });
  const data: FieldData = {
    db,
    technicianId: over.tech ?? DANA,
    newId: idSource('k'),
    clock,
    money: over.money ?? money,
    device: over.device ?? device,
    scanner: over.scanner ?? unwiredScanner,
    signature: over.signature ?? unwiredSignature,
  };
  return { db, clock, money, device, data };
}

/** Mount the whole app, signed in, and open one screen with its params. */
export async function openScreen(
  wave: Wave,
  id: ScreenId,
  params?: Record<string, unknown>,
  opts: { login?: string; theme?: ThemeName; connection?: 'online' | 'offline' | 'unknown' } = {},
) {
  const h = makeHandset();
  await signIn(h.session, opts.login ?? 'd.ortiz');
  const fieldI18n = createFieldI18n({ language: 'en' });
  const ref = createNavigationContainerRef<ParamListBase>();
  const ui: ReactElement = (
    <ThemeProvider initialMode={opts.theme ?? 'light'}>
      <FieldDataProvider value={wave.data}>
        <I18nProvider fieldI18n={fieldI18n} prefs={h.prefs}>
          <SessionProvider manager={h.session}>
            <ShellStatusProvider value={{ ...UNKNOWN_STATUS, connection: opts.connection ?? UNKNOWN_STATUS.connection }}>
              <NavigationContainer ref={ref}>
                <AppNavigator tablet={false} />
              </NavigationContainer>
            </ShellStatusProvider>
          </SessionProvider>
        </I18nProvider>
      </FieldDataProvider>
    </ThemeProvider>
  );
  const utils = render(ui);
  await screen.findByTestId('screen-FF-63');
  const target = routeTo(id);
  const leaf = { ...(target.params as { params: Record<string, unknown> }).params, params };
  await act(async () => {
    ref.dispatch(CommonActions.navigate(target.name, { ...(target.params as object), params: leaf }));
  });
  return { ...utils, ref, onTop: () => screen.getAllByTestId(`screen-${id}`).at(-1)! };
}

/** Where the app is now: the focused route and its params. */
export function current(ref: { getCurrentRoute(): { name: string; params?: object } | undefined }) {
  const r = ref.getCurrentRoute();
  return { name: r?.name, params: (r?.params ?? {}) as Record<string, unknown> };
}

/** What a technician has captured, oldest first, payloads parsed. */
export function captured(db: TenantDb, tech: string = DANA) {
  return outboxQ
    .listMine(scoped(db, tech), { limit: 500 })
    .reverse()
    .map((r) => ({ ...r, body: JSON.parse(r.payload) as Record<string, unknown> }));
}

/** The wave a screen gets from `useWave`, for calling an act directly. */
export function waveOf(w: Wave, tech: string = DANA) {
  return {
    ...w.data,
    me: tech,
    s: scoped(w.db, tech),
    captor: { technicianId: tech, capturedBy: tech },
    deps: { newId: w.data.newId, clock: w.data.clock },
  };
}
