/**
 * The REAL dictation behind `DictationDevice` (`../ports.ts`):
 * `expo-speech-recognition` (2.1.x, the line built for Expo SDK 53), ON THE
 * DEVICE ONLY.
 *
 * ⚠ **ON-DEVICE, OR NOT AT ALL.** A technician's note can carry a customer's
 * name, an address, what was said at the door. Server recognition would send
 * that audio to Apple or Google, which no ruling allows. So the port is
 * `available` only where the platform recognises speech on the handset
 * (`supportsOnDeviceRecognition`), and every request sets
 * `requiresOnDeviceRecognition`. Where the handset cannot, the port refuses
 * exactly as the unwired one did and the screens offer typing (R95).
 *
 * One utterance per call (R38: dictation beside every note): the words heard,
 * or null for silence.
 */
import { ExpoSpeechRecognitionModule } from 'expo-speech-recognition';

import { withSystemInteraction } from '../../session/systemInteraction';
import { type DictationDevice, PortUnavailableError, UNWIRED_DICTATION } from '../ports';

function onDevice(): boolean {
  try {
    return ExpoSpeechRecognitionModule.isRecognitionAvailable() && ExpoSpeechRecognitionModule.supportsOnDeviceRecognition();
  } catch {
    return false;
  }
}

export function expoDictation(): DictationDevice {
  if (!onDevice()) return UNWIRED_DICTATION;
  return {
    available: true,
    async listen(language: string): Promise<string | null> {
      // The microphone question is the app's own pop-up; never "leaving" (MQ-019).
      const permission = await withSystemInteraction(() => ExpoSpeechRecognitionModule.requestPermissionsAsync());
      if (!permission.granted) throw new PortUnavailableError('dictation (microphone not allowed)');
      return new Promise<string | null>((resolve, reject) => {
        let heard: string | null = null;
        const subs: Array<{ remove(): void }> = [];
        const finish = (fn: () => void) => {
          for (const s of subs.splice(0)) s.remove();
          fn();
        };
        subs.push(
          ExpoSpeechRecognitionModule.addListener('result', (e) => {
            const words = e.results[0]?.transcript?.trim();
            if (e.isFinal && words) heard = words;
          }),
          ExpoSpeechRecognitionModule.addListener('error', (e) => {
            // Silence is not a failure: nothing was said.
            if (e.error === 'no-speech' || e.error === 'aborted') finish(() => resolve(null));
            else finish(() => reject(new PortUnavailableError(`dictation (${e.error})`)));
          }),
          ExpoSpeechRecognitionModule.addListener('end', () => finish(() => resolve(heard))),
        );
        try {
          ExpoSpeechRecognitionModule.start({
            lang: language,
            interimResults: false,
            continuous: false,
            requiresOnDeviceRecognition: true,
            addsPunctuation: true,
          });
        } catch (err) {
          finish(() => reject(err));
        }
      });
    },
  };
}
