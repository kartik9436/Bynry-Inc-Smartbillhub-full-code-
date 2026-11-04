/**
 * Archivo, bundled into the app (OQ-272 (a), ratified by the PO 2026-10-20:
 * *"our style's font"*; AD-10). React Native ships the font file in the
 * bundle, so these three imports ARE the decision — the same three weights
 * the web loads (`Archivo:wght@400;600;800`). Importing per weight keeps the
 * other fifteen files out of the bundle.
 *
 * `useArchivoFonts()` registers them under the family names in `ARCHIVO`
 * (themes.ts), which is what every component's `fontFamily` reads.
 */
import { useFonts } from '@expo-google-fonts/archivo/useFonts';
import { Archivo_400Regular } from '@expo-google-fonts/archivo/400Regular';
import { Archivo_600SemiBold } from '@expo-google-fonts/archivo/600SemiBold';
import { Archivo_800ExtraBold } from '@expo-google-fonts/archivo/800ExtraBold';

import { ARCHIVO } from './themes';

export const ARCHIVO_SOURCES = {
  [ARCHIVO.regular]: Archivo_400Regular,
  [ARCHIVO.semibold]: Archivo_600SemiBold,
  [ARCHIVO.heavy]: Archivo_800ExtraBold,
};

/** `[loaded, error]` — render a splash until `loaded`. A font that fails to
 *  load is reported, never fatal: the system font draws the same words. */
export function useArchivoFonts(): [boolean, Error | null] {
  return useFonts(ARCHIVO_SOURCES);
}
