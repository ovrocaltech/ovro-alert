# ovro-alert
Code and services for sending, receiving, and using astronomical alerts at OVRO.

Alert scenarios:
- CHIME/FRB to DSA-110 -- Identify co-detections of non-repeating FRBs and alert to new repeating FRBs from CHIME
- CHIME/FRB to OVRO-LWA -- Search for ultra-wide band emission from repeating FRBs from CHIME
- DSA-110 to Swift/GUANO -- Search for prompt high-energy counterparts or afterglows from FRBs
- DSA-110 to OVRO-LWA -- Search for ultra-wide band emission from non-repeating FRBs
- LIGO to OVRO-LWA -- Search for prompt radio counterparts to neutron star mergers
- Flarescope and OVRO-LWA co-observing -- Automatic OVRO-LWA observing to search for stellar flares
- Optical transients to SPRITE?
- GREX to OVRO-LWA?

## Requirements
- astropy
- fastapi
- pydantic
- uvicorn
- twisted
- voevent-parse
- slack_sdk
- astropy

## Command relay

We need a way for OVRO to pull commands in from external server. `relay_api.py` is a REST API that allows a `get` and `set` method for the paths `/dsa` and `/lwa`. Services on the DSA-110 and OVRO-LWA private networks can poll the API for alerts.

The API can be run with:
`uvicorn relay_api:app --reload --host <ip> --port 8001`

Service is available at <ip>:8001. Docs at `/docs`.

## CHIME-ALERTS

We need a way to receive CHIME/FRB events to:
- Identify and send slack notification for CHIME/FRB repeaters
- Identify joint CHIME/DSA events
- Repoint DSA-110 (human in the loop)
- Automatically point beam at OVRO-LWA

The VOEvent receiver uses `twistd` to run the `comet` broker, like this:
`twistd -n comet -v --remote=chimefrb.physics.mcgill.ca --print-event --save-event --local-ivo=ivo://caltech/comet_broker`

## LIGO-ALERTS

We need a way to receive LIGO events to:
- Notify on slack
- Automatically trigger voltage buffer dump at OVRO-LWA

## Flarescope-ALERTS

We need a way to start a beamformed observation at OVRO-LWA in coincidence with Flarescope:
- Create SDF for a given (RA, Dec, start time, duration). Optionally set name or integration time.
- Ensure beams are calibrated
- Run SDF

## OVRO-LWA

We need a way to poll the relay server and send commands for new OVRO-LWA observations. Two kinds of observation must be supported:
- Trigger voltage buffer dump
- Point a power beam at a target

An OVRO client example module is at `lwa_alert.py`.

## DSA-110

We need a way to send DSA-110 discovery alerts to Swift/GUANO. Example implementation exists for [realfast](https://github.com/realfastvla/realfast/blob/main/realfast/util.py#L98).

We need a way to send DSA-110 discovery alerts to OVRO-LWA. This could be done via `relay_api.py`.


## Assumptions and Rules
- major hosts processes for relay plus one per telescope
- Multiple telescope trigger processes may watch the same relay field (e.g., for different responses by OVRO-LWA)
- Either response to a command must be faster than update frequency or we need multiple relay fields (e.g., "lwa-ligo" and "lwa-flarescope").
- Telescope trigger code should be aware of telescope state (e.g., don't reconfigure lwa x-engine if already configured)

## Protocol
  
| path | command | args |
| ---  | ------- | ---- |
| /lwa | trigger | (metadata) |
| /lwa | powerbeam | RA, Dec, start time, duration, beamnum |
| /dsa | slew? | elevation |
| /sprite? | slew? | RA, Dec |

Outside of relay:
- CHIME/FRB alerts received and sent to slack directly.
- DSA-110 alerts sent to Swift/GUANO directly.
