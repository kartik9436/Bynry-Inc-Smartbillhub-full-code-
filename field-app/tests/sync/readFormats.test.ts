/**
 * MQ-033 (`CR-192-BRC10` task 12) — a utility's read format on the phone:
 * downloaded with the route and kept by VERSION id (offline), carried on the
 * reading's own item exactly as the server's sync door reads it, and its
 * receipt kept beside the reading. A route with no format is the route it
 * always was.
 *
 * Built from `support/serverReadFormat.json`, the server's own shape —
 * `06-backend/tests/test_mq033_phone_shape.py` fails when it drifts, and sends
 * `reading_item` through the real door (DEF-FLD-10582's lesson).
 */
import * as readFormatQ from '../../src/db/queries/readFormat';
import * as routeQ from '../../src/db/queries/route';
import { scoped } from '../../src/db/scoped';
import { batchAnswerFromReads, routeItemFromWire } from '../../src/sync/routeReads';
import { downloadRoutes, type RouteStopsPage, type RoutesApi, type ServedReadFormatVersion, type ServedRouteFormat } from '../../src/sync/routes';
import type { WireItem } from '../../src/sync/transport';
import { openStore } from '../db/support/fixtures';
import server from './support/serverReadFormat.json';

const VERSION = server.version as unknown as ServedReadFormatVersion;
const NOW = () => new Date('2026-10-20T07:00:00Z');

const meter = {
  asset_id: 'a-1',
  meter_no: 'MTR-0471',
  serial_no: null,
  parent_meter_no: null,
  service: 'electric',
  size_class: null,
  read_method: null,
  location_note: null,
  unit_label: null,
  account_no: null,
  customer_name: null,
  registers: [{ register: 'total', unit: 'kWh', previous: null, expected: null }],
};

function api(opts: { formats: ServedRouteFormat[]; versions?: unknown[]; fetchVersion?: (id: string) => Promise<ServedReadFormatVersion> }): RoutesApi & { fetched: string[] } {
  const card = { id: 'route-1', code: 'WLK-07', services: ['electric'], read_formats: opts.formats };
  const fetched: string[] = [];
  return {
    fetched,
    myRoutes: async () => ({ results: [card], next_page: null }),
    routePage: async () =>
      ({
        route: card,
        read_format_versions: opts.versions ?? [],
        stops: [{ premises_id: 'p-1', premise_no: null, position: 1, walk_order: 1, address: null, point: null, meters: [meter] }],
        next_page: null,
      }) as unknown as RouteStopsPage,
    turnIn: async () => ({}),
    cantReadReasons: async () => ({ results: [] }),
    ...(opts.fetchVersion
      ? {
          readFormatVersion: async (id: string) => {
            fetched.push(id);
            return opts.fetchVersion!(id);
          },
        }
      : {}),
  };
}

describe('download', () => {
  test('the route keeps its resolved format per service, and the version with its questions is kept by id', async () => {
    const db = openStore('brazos');
    await downloadRoutes(db, 'tech-ray', api({ formats: [server.route_format as ServedRouteFormat], versions: [server.version] }), NOW);
    const s = scoped(db, 'tech-ray');
    expect(readFormatQ.routeFormats(s, 'route-1')).toEqual([{ service: 'electric', source: 'cycle', version_id: VERSION.id }]);
    const kept = readFormatQ.getVersion(db, VERSION.id)!;
    expect(kept.read_format_id).toBe(VERSION.read_format_id);
    expect(kept.questions.map((q) => [q.key, q.data_type, q.asked_when])).toEqual(VERSION.questions.map((q) => [q.key, q.data_type, q.asked_when]));
    // The utility's own words, kept verbatim.
    expect(kept.questions[0]).toMatchObject({ label: 'Seal intact?', help_text: 'Look at the wire seal on the ring.' });
    expect(kept.questions[1]!.show_if).toEqual({ question_key: 'seal_intact', answer: false });
  });

  test('a version the page names but did not carry is fetched from its own door, once', async () => {
    const db = openStore('brazos');
    const a = api({ formats: [server.route_format as ServedRouteFormat], versions: [], fetchVersion: async () => VERSION });
    await downloadRoutes(db, 'tech-ray', a, NOW);
    expect(a.fetched).toEqual([VERSION.id]);
    expect(readFormatQ.getVersion(db, VERSION.id)?.questions).toHaveLength(6);
    // Cached by id: a second download asks for nothing.
    await downloadRoutes(db, 'tech-ray', a, NOW);
    expect(a.fetched).toEqual([VERSION.id]);
  });

  test('a route the server stops listing (DEF-FLD-10592) leaves with its format; the shared version stays cached', async () => {
    const db = openStore('brazos');
    await downloadRoutes(db, 'tech-ray', api({ formats: [server.route_format as ServedRouteFormat], versions: [server.version] }), NOW);
    const none: RoutesApi = { ...api({ formats: [] }), myRoutes: async () => ({ results: [], next_page: null }) };
    const summary = await downloadRoutes(db, 'tech-ray', none, NOW);
    expect(summary.removed).toBe(1);
    const s = scoped(db, 'tech-ray');
    expect(routeQ.listMine(s)).toHaveLength(0);
    expect(readFormatQ.routeFormats(s, 'route-1')).toEqual([]);
    expect(readFormatQ.hasVersion(db, VERSION.id)).toBe(true);
  });

  test('a route with no format downloads exactly as before: no format, no version', async () => {
    const db = openStore('brazos');
    await downloadRoutes(db, 'tech-ray', api({ formats: [{ service: 'electric', source: null, read_format: null }] }), NOW);
    const s = scoped(db, 'tech-ray');
    expect(readFormatQ.routeFormats(s, 'route-1')).toEqual([]);
    expect(routeQ.listMine(s)).toHaveLength(1);
  });
});

describe('on the wire', () => {
  const sent: WireItem = {
    key: 'k-000001',
    kind: 'route_read',
    seq: 1,
    captured_at: '2026-10-20T10:42:18.000Z',
    payload: {
      route_read_id: 'r-1',
      meter_no: 'MTR-0471',
      premises_id: server.reading_item.premises_id,
      register: null,
      value: '48400',
      unit: 'kWh',
      reader_status: 'read',
      no_read_reason: null,
      warned_accepted: false,
      identified_by: 'listed',
      remark: null,
      remark_source: null,
      read_format_version_id: VERSION.id,
      answers: server.reading_item.answers,
      photo_ids: server.reading_item.photos,
    },

  };

  test('the reading item carries its version and answers exactly as the sync door reads them', () => {
    expect(routeItemFromWire(sent, server.reading_item.route_id)).toEqual(server.reading_item);
  });

  test('a reading with no format carries neither key', () => {
    const plain = { ...sent, payload: { ...sent.payload, read_format_version_id: null, answers: null } };
    const out = routeItemFromWire(plain, 'route-1');
    expect(out).not.toHaveProperty('read_format_version_id');
    expect(out).not.toHaveProperty('answers');
  });

  test('the receipt keeps the answers block, so the reading can say the office will look', () => {
    const answer = batchAnswerFromReads([sent], {
      items: [{ key: 'k-000001', result: 'accepted', outcome: 'posted', answers: { ...server.receipt_answers, needs_review: true, issues: [{ question_key: 'gate_code', issue: 'required_missing' }] } } as never],
    });
    expect(answer.items[0]!.detail).toMatchObject({ answers: { needs_review: true, issues: [{ question_key: 'gate_code', issue: 'required_missing' }] } });
  });
});
