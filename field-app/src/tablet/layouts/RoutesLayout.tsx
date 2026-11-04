/**
 * RW-01 T *My routes beside the route* (T-29; image
 * `tablet/RW-01-T-my-routes.png`) — a T2 board whose detail IS a screen the
 * phone already has (RW-02 Route summary), so it is filled the mechanical
 * way: the phone's My routes as the list, a card's door to RW-02 becoming the
 * pick (`SelectOnOpen`), and RW-02 itself beside it, handed the pick as its
 * `routeId` (`SelectedParam`). Nothing picked → RW-02 resolves the reader's
 * first route, the one the list rules heavy, as the board draws it.
 */
import { readsScreen } from '../../screens/reads/ReadsScreen';
import { MyRoutes, RouteSummary } from '../../screens/reads/route';
import { SelectedParam, SelectOnOpen } from '../selection';

const Routes = readsScreen('RW-01', MyRoutes);
const Summary = readsScreen('RW-02', RouteSummary);

export function RoutesList() {
  return (
    <SelectOnOpen opens="RW-02" param="routeId">
      <Routes />
    </SelectOnOpen>
  );
}

export function RouteDetail() {
  return (
    <SelectedParam param="routeId">
      <Summary />
    </SelectedParam>
  );
}
