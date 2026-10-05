# Dashboard UX specification

## Information architecture

Primary views: Overview, Live Map, Scenario Lab, Events, Devices, Alerts, Infrastructure, Experiments, and Session. A persistent header shows mode, connection, active run, build version, and—only in AWS mode—session expiry.

## Scenario Lab

Controls select a catalog scenario, device count, seed, and supported degradation parameters. Start is disabled while a run is starting/running. The UI renders server-returned run and stage records. Gate cards show observed/required values and `passed`, `failed`, `pending`, or `unavailable`. Reset is explicit and separate from session teardown.

## State rules

- Initial loading uses stable skeleton regions, not layout-shifting cards.
- Empty state explains what creates data.
- Disconnection freezes the last snapshot with its timestamp and retry state.
- Errors contain a safe message, correlation/run ID when available, and recovery action.
- No card invents a zero when data is unavailable.

## Visual/accessibility baseline

Use a restrained academic operations palette, system typography, 8px spacing rhythm, clear table density, and status icon + text. All actions are keyboard reachable, focus is visible, map data has a textual equivalent, dialogs restore focus, motion respects reduced-motion preferences, and common widths from 1280×720 to 1920×1080 avoid horizontal page overflow.
