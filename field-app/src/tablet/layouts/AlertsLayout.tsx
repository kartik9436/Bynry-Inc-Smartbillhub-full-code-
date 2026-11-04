/**
 * FF-42 T *Alerts beside the one you opened* (T-28; image
 * `tablet/FF-42-T-alerts.png`).
 *
 *   LIST   — the phone's Alerts, whole, under its own bar (*Alerts* ·
 *            *Mark read*): the open emergency first and in red, then the
 *            rest newest first (R28, R29).
 *   DETAIL — the emergency, in the danger ink, with the clock to dispatch
 *            being told and *Acknowledge* · *Call dispatch* (R28, R107): the
 *            phone's FF-43 itself.
 *
 * The emergency card, which opens FF-43 on a phone, keeps the list on screen
 * here (`SelectOnOpen`, the door itself being the pick). ⚠ The other alert
 * kinds have no detail screen of their own on any board — the tablet draws
 * only the emergency opened — so they are read in the list and open nothing.
 */
import { AlertsScreen } from '../../screens/me/AlertsScreen';
import { EmergencyScreen } from '../../screens/me/EmergencyScreen';
import { SelectOnOpen } from '../selection';

export function AlertsList() {
  return (
    <SelectOnOpen opens="FF-43">
      <AlertsScreen />
    </SelectOnOpen>
  );
}

export function AlertDetail() {
  return <EmergencyScreen />;
}
