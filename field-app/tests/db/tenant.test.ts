/**
 * @jest-environment node
 *
 * T-50's handset half — tenant isolation. The tenant is the database FILE
 * (R131), so the proof is: two tenants' files never see each other's rows, and
 * a file stamped for one tenant refuses to open as another.
 */
import { openTenantDb, tenantFileName, TenantMismatchError } from '../../src/db/database';
import type { DriverFactory } from '../../src/db/driver';
import * as premiseQ from '../../src/db/queries/premise';
import * as workOrderQ from '../../src/db/queries/workOrder';
import { scoped } from '../../src/db/scoped';
import { memoryFactory, nodeDriver } from './support/nodeDriver';

const NOW = () => '2026-10-21T08:00:00.000Z';

describe('one file per tenant', () => {
  test('a contractor working for two utilities gets two files, and neither sees the other', () => {
    const factory = memoryFactory();
    const north = openTenantDb(factory, 'north', { now: NOW });
    const south = openTenantDb(factory, 'south', { now: NOW });
    expect([...factory.files.keys()].sort()).toEqual(['field-north.sqlite', 'field-south.sqlite']);

    premiseQ.upsert(north, { id: 'p-1', addressLine: '221 Oak Ave' }, NOW());
    workOrderQ.upsertFromServer(
      scoped(north, 'dana'),
      {
        id: 'wo-1', number: 'WO-4822', type: null, state: null, dispatchState: null, priorityCode: null,
        priorityRank: null, premiseId: 'p-1', windowStart: null, windowEnd: null, dueAt: null, estMinutes: null,
        accessNotes: null, hazards: null, gateCode: null, extra: null, serverUpdatedAt: null,
      },
      NOW(),
    );

    expect(premiseQ.get(north, 'p-1')?.address_line).toBe('221 Oak Ave');
    expect(premiseQ.get(south, 'p-1')).toBeUndefined();
    expect(workOrderQ.getMine(scoped(south, 'dana'), 'wo-1')).toBeUndefined();
    expect(workOrderQ.getMine(scoped(north, 'dana'), 'wo-1')?.number).toBe('WO-4822');
  });

  test('a file stamped for one tenant refuses to open as another', () => {
    // A renamed or copied file: both names reach the SAME bytes.
    const shared = nodeDriver();
    const factory: DriverFactory = () => ({ ...shared, close: () => undefined });
    openTenantDb(factory, 'north', { now: NOW });
    expect(() => openTenantDb(factory, 'south', { now: NOW })).toThrow(TenantMismatchError);
    expect(() => openTenantDb(factory, 'north', { now: NOW })).not.toThrow();
  });

  test('a tenant name that is not a plain slug never becomes a path', () => {
    for (const bad of ['', '../north', 'north/../../x', 'a b', 'north.sqlite']) {
      expect(() => tenantFileName(bad)).toThrow();
    }
    expect(tenantFileName('North-Water_2')).toBe('field-north-water_2.sqlite');
  });
});
