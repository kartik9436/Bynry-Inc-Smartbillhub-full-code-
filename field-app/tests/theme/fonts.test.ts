/**
 * Archivo is loaded in exactly the three weights the web loads, under the
 * family names every component's `fontFamily` reads.
 *
 * `useFonts` is mocked: the test is about WHICH files are registered under
 * WHICH names, not about expo-font's loader.
 */
const mockUseFonts = jest.fn((_map: Record<string, unknown>) => [true, null]);
jest.mock('@expo-google-fonts/archivo/useFonts', () => ({
  useFonts: (map: Record<string, unknown>) => mockUseFonts(map),
}));

import { ARCHIVO } from '../../src/theme';
import { ARCHIVO_SOURCES, useArchivoFonts } from '../../src/theme/fonts';

test('three weights, registered under the theme family names', () => {
  expect(Object.keys(ARCHIVO_SOURCES).sort()).toEqual(
    ['Archivo_400Regular', 'Archivo_600SemiBold', 'Archivo_800ExtraBold'].sort(),
  );
  expect(Object.values(ARCHIVO).sort()).toEqual(Object.keys(ARCHIVO_SOURCES).sort());
  for (const source of Object.values(ARCHIVO_SOURCES)) {
    expect(source).toBeDefined();
  }
});

test('useArchivoFonts hands every source to useFonts', () => {
  expect(useArchivoFonts()).toEqual([true, null]);
  expect(mockUseFonts).toHaveBeenCalledWith(ARCHIVO_SOURCES);
});
