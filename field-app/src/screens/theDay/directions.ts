/**
 * The deep link to Google Maps or Apple Maps (FF-14 *Google Maps · Apple
 * Maps*, FF-10 *Navigate*).
 *
 * ⚠ IT CARRIES THE STREET ADDRESS AND NOTHING ELSE (Security §5): no
 * customer name, no work-order number, no account, no note. Another
 * company's app receives it, and the address is already what a driver would
 * type. The premises' coordinates are not sent either — the address is what
 * the technician can read and check before they drive.
 */
export type MapsApp = 'google' | 'apple';

export function directionsUrl(app: MapsApp, address: string): string {
  const q = encodeURIComponent(address);
  return app === 'google'
    ? `https://www.google.com/maps/dir/?api=1&destination=${q}`
    : `https://maps.apple.com/?daddr=${q}`;
}
