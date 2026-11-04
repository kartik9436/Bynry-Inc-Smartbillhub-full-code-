/**
 * DEF-FLD-10630 (FB-002) and DEF-FLD-10631 (FB-003) — a reading's photos,
 * under the real navigation and the real store.
 *
 * FB-002 (reader Sam Curran, W-5005, RT-001): RW-14 showed a dark panel with
 * the stamp's text and no camera; the photo was then shown nowhere, and the
 * photo button on RW-09 became a count that opened the camera again.
 * FB-003: the saved reading said "0 photos". Reproduced 2026-10-27: a photo
 * saved WITH the reading counted; a photo added on RW-13 AFTER saving did not,
 * because the count joined a photo to its reading by the reading's capture key
 * and a later photo is its own act with its own key.
 *
 * PO 2026-10-27 ("go with recommendation"): before saving, Retake and Remove
 * freely; after saving, view and Add photo only.
 */
import 'react-native-gesture-handler/jestSetup';

import { act, fireEvent, screen, within } from '@testing-library/react-native';
import { Image } from 'react-native';

import * as walkQ from '../../../src/db/queries/readsWalk';
import { scoped } from '../../../src/db/scoped';
import { RAY } from './fixture';
import { FakeCamera, mountReads } from './harness';

jest.mock('react-native-reanimated', () => require('react-native-reanimated/mock'));

type Page = ReturnType<typeof within>;

async function press(page: Page, id: string) {
  await act(async () => {
    fireEvent.press(page.getByTestId(id));
  });
}

const top = async (id: string) => within((await screen.findAllByTestId(`screen-${id}`)).at(-1)!);

function type(page: Page, digits: string) {
  for (const d of digits) fireEvent.press(page.getByTestId(`keypad-${d}`));
}

const uriOf = (page: Page, id: string) => (within(page.getByTestId(id)).UNSAFE_getByType(Image).props as { source: { uri: string } }).source.uri;

/** RW-09 → RW-14 → Take the photo → back on RW-09. */
async function takeFromEntry(page: Page): Promise<Page> {
  await press(page, 'read-photo');
  await press(await top('RW-14'), 'door-RW-13');
  return top('RW-09');
}

describe('FB-002 — RW-14 shows the camera', () => {
  test('the panel is the live camera view, with the stamp laid over it as a preview', async () => {
    const app = await mountReads();
    const page = within((await app.open('RW-14', { readId: 'r0471' }))!);
    const panel = within(page.getByTestId('camera-view'));
    expect(panel.getByTestId('fake-camera-live')).toBeTruthy();
    expect(panel.getByTestId('stamp')).toHaveTextContent(/R\. Delacroix · MTR-0471 · WLK-07/);
    app.unmount();
  });

  test('with no camera the live view is not drawn and the notice stands', async () => {
    const app = await mountReads({ camera: new FakeCamera(false) });
    const page = within((await app.open('RW-14', { readId: 'r0471' }))!);
    expect(page.queryByTestId('fake-camera-live')).toBeNull();
    expect(page.getByText('No camera on this phone.')).toBeTruthy();
    app.unmount();
  });
});

describe('FB-002 — before saving, the photos are shown and can be retaken or removed', () => {
  test('a taken photo shows as a thumbnail on RW-09; the button then adds another', async () => {
    const app = await mountReads();
    let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    expect(page.queryByTestId('reading-photo-0')).toBeNull();
    page = await takeFromEntry(page);
    expect(uriOf(page, 'reading-photo-0')).toBe('file:///photos/p1.jpg');
    expect(page.getByTestId('read-photo')).toHaveTextContent('Add photo');
    await press(page, 'reading-photo-0');
    const viewer = within(page.getByTestId('photo-viewer-panel'));
    expect(uriOf(viewer, 'photo-viewer-image')).toBe('file:///photos/p1.jpg');
    expect(viewer.getByTestId('photo-retake')).toBeTruthy();
    expect(viewer.getByTestId('photo-remove')).toBeTruthy();
    app.unmount();
  });

  test('Remove takes the photo off the reading and deletes its file', async () => {
    const camera = new FakeCamera();
    const app = await mountReads({ camera });
    let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    page = await takeFromEntry(page);
    await press(page, 'reading-photo-0');
    await press(within(page.getByTestId('photo-viewer-panel')), 'photo-remove');
    page = await top('RW-09');
    expect(page.queryByTestId('reading-photo-0')).toBeNull();
    expect(page.getByTestId('read-photo')).toHaveTextContent(/^Photo$/);
    expect(camera.discarded).toEqual(['file:///photos/p1.jpg']);
    // Saved now, the reading carries no photo.
    type(page, '52410');
    await press(page, 'door-RW-13');
    expect(walkQ.readingPhotos(scoped(app.db, RAY), 'r0471')).toHaveLength(0);
    app.unmount();
  });

  test('Retake opens the camera and the new photo takes the old one\'s place', async () => {
    const camera = new FakeCamera();
    const app = await mountReads({ camera });
    let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    page = await takeFromEntry(page);
    page = await takeFromEntry(page);
    await press(page, 'reading-photo-0');
    await press(within(page.getByTestId('photo-viewer-panel')), 'photo-retake');
    expect(app.current()).toBe('RW-14');
    await press(await top('RW-14'), 'door-RW-13');
    page = await top('RW-09');
    expect(uriOf(page, 'reading-photo-0')).toBe('file:///photos/p3.jpg');
    expect(uriOf(page, 'reading-photo-1')).toBe('file:///photos/p2.jpg');
    expect(page.queryByTestId('reading-photo-2')).toBeNull();
    expect(camera.discarded).toEqual(['file:///photos/p1.jpg']);
    app.unmount();
  });
});

describe('FB-002 — the other screens that hold an unsaved reading\'s photos show them too', () => {
  test('RW-17 Can\'t read shows the photo and Remove takes it off', async () => {
    const camera = new FakeCamera();
    const app = await mountReads({ camera });
    let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    page = await takeFromEntry(page);
    await press(page, 'door-RW-17');
    let cant = await top('RW-17');
    expect(uriOf(cant, 'reading-photo-0')).toBe('file:///photos/p1.jpg');
    await press(cant, 'reading-photo-0');
    await press(within(cant.getByTestId('photo-viewer-panel')), 'photo-remove');
    cant = await top('RW-17');
    expect(cant.queryByTestId('reading-photo-0')).toBeNull();
    expect(camera.discarded).toEqual(['file:///photos/p1.jpg']);
    app.unmount();
  });
});

describe('FB-002 / FB-003 — after saving, the photos are evidence: view and add only', () => {
  test('a reading saved with 1 photo and given 1 more reads 2 photos, and neither can be removed', async () => {
    const app = await mountReads();
    let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    page = await takeFromEntry(page);
    type(page, '52410');
    await press(page, 'door-RW-13');
    let kept = await top('RW-13');
    expect(kept.getByTestId('kept-photos')).toHaveTextContent(/1 photo/);
    expect(uriOf(kept, 'reading-photo-0')).toBe('file:///photos/p1.jpg');
    // The count opens the photos, never the camera.
    await press(kept, 'kept-photos');
    expect(app.current()).toBe('RW-13');
    let viewer = within(kept.getByTestId('photo-viewer-panel'));
    expect(uriOf(viewer, 'photo-viewer-image')).toBe('file:///photos/p1.jpg');
    expect(viewer.queryByTestId('photo-retake')).toBeNull();
    expect(viewer.queryByTestId('photo-remove')).toBeNull();
    await press(viewer, 'photo-viewer-close');
    // Add photo: the camera, then back to the reading, which now counts two.
    expect(kept.getByTestId('door-RW-14')).toHaveTextContent('Add photo');
    await press(kept, 'door-RW-14');
    await press(await top('RW-14'), 'door-RW-13');
    kept = await top('RW-13');
    expect(kept.getByTestId('kept-photos')).toHaveTextContent(/2 photos/);
    expect(uriOf(kept, 'reading-photo-1')).toBe('file:///photos/p2.jpg');
    await press(kept, 'reading-photo-1');
    viewer = within(kept.getByTestId('photo-viewer-panel'));
    expect(uriOf(viewer, 'photo-viewer-image')).toBe('file:///photos/p2.jpg');
    expect(viewer.queryByTestId('photo-remove')).toBeNull();
    app.unmount();
  });

  test('a reading changed and saved again keeps the photos it already had', async () => {
    const app = await mountReads();
    let page = within((await app.open('RW-09', { readId: 'r0471' }))!);
    page = await takeFromEntry(page);
    type(page, '52410');
    await press(page, 'door-RW-13');
    await press(await top('RW-13'), 'door-RW-09');
    page = await top('RW-09');
    type(page, '52411');
    await press(page, 'door-RW-13');
    const kept = await top('RW-13');
    expect(kept.getByTestId('kept-photos')).toHaveTextContent(/1 photo/);
    app.unmount();
  });
});
