/**
 * @jest-environment node
 *
 * The one free-text box (Mobile data §3): FTS5 over number, customer name,
 * address, serial and badge — and scoped, so Marco never finds Dana's customers.
 */
import * as searchQ from '../../src/db/queries/searchIndex';
import { scoped } from '../../src/db/scoped';
import { openStore } from './support/fixtures';

describe('search_index', () => {
  const db = openStore();
  const dana = scoped(db, 'dana');
  const marco = scoped(db, 'marco');

  beforeAll(() => {
    searchQ.put(dana, 'work_order', 'wo-1', { number: 'WO-4822', customerName: 'Rivera', address: '221 Oak Ave' });
    searchQ.put(dana, 'asset', 'a-1', { serial: 'A-1234', badge: 'B77881', address: '221 Oak Ave' });
    searchQ.put(marco, 'work_order', 'wo-9', { number: 'WO-5000', customerName: 'Okafor', address: '9 Elm St' });
  });
  afterAll(() => db.close());

  test('finds by prefix across the indexed columns', () => {
    expect(searchQ.search(dana, 'oak', { limit: 10 }).map((h) => h.entity_id).sort()).toEqual(['a-1', 'wo-1']);
    expect(searchQ.search(dana, 'rive', { limit: 10 }).map((h) => h.entity_id)).toEqual(['wo-1']);
    expect(searchQ.search(dana, 'B7788', { limit: 10 }).map((h) => h.entity_id)).toEqual(['a-1']);
  });

  test('every word must match', () => {
    expect(searchQ.search(dana, 'oak rivera', { limit: 10 }).map((h) => h.entity_id)).toEqual(['wo-1']);
  });

  test('punctuation in a serial or a number is text, not query syntax', () => {
    expect(searchQ.search(dana, 'A-1234', { limit: 10 }).map((h) => h.entity_id)).toEqual(['a-1']);
    expect(searchQ.search(dana, 'WO-4822', { limit: 10 }).map((h) => h.entity_id)).toEqual(['wo-1']);
    expect(() => searchQ.search(dana, '"unbalanced (', { limit: 10 })).not.toThrow();
  });

  test("never surfaces another technician's customers", () => {
    expect(searchQ.search(marco, 'oak', { limit: 10 })).toEqual([]);
    expect(searchQ.search(dana, 'okafor', { limit: 10 })).toEqual([]);
    expect(searchQ.search(marco, 'okafor', { limit: 10 }).map((h) => h.entity_id)).toEqual(['wo-9']);
  });

  test('is paged, and an empty box finds nothing rather than everything', () => {
    expect(searchQ.search(dana, 'oak', { limit: 1 })).toHaveLength(1);
    expect(searchQ.search(dana, 'oak', { limit: 1, offset: 1 })).toHaveLength(1);
    expect(searchQ.search(dana, '   ', { limit: 10 })).toEqual([]);
  });

  test('replacing an entry replaces it, removing removes it', () => {
    searchQ.put(dana, 'work_order', 'wo-1', { number: 'WO-4822', customerName: 'Nakamura', address: '221 Oak Ave' });
    expect(searchQ.search(dana, 'rivera', { limit: 10 })).toEqual([]);
    searchQ.remove(dana, 'work_order', 'wo-1');
    expect(searchQ.search(dana, 'nakamura', { limit: 10 })).toEqual([]);
  });
});
