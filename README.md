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

![diagram of connections](drawio/diagram.png)

## Requirements
- astropy
- fastapi
- pydantic
- uvicorn
- twisted
- voevent-parse
- slack_sdk
- astropy

## Assumptions and Rules

- Server hosts processes for relay plus one per alert receiver (e.g., LIGO) -- currently this is on "major"
- Responsive clients poll a path on the relay (e.g., /lwa for messages of interest to OVRO-LWA)
-- Alternatively, clients poll path for the sender (e.g., /chime for messages from CHIME/FRB)
- Either response to a command must be faster than update frequency or we need multiple relay fields (e.g., "lwa-ligo" and "lwa-flarescope").
- Telescope trigger code should be aware of telescope state (e.g., don't reconfigure lwa x-engine if already configured)
- Relay can also just hold info for insight to direct-sent triggers (e.g., DSA-110 to Swift)

## Protocol
  
| path | command | args |
| ---  | ------- | ---- |
| /lwa | trigger | (metadata) |
| /lwa | powerbeam | RA, Dec, start time, duration, beamnum |
| /dsa | CHIME FRB | RA, Dec, DM, TOA |

An alternative would be to structure as events from a sender:

| path | type | args |
| ---  | ------- | ---- |
| /ligo | test/event | TOA, FAR, BNS |
| /chime | test/event | TOA, DM, RA, Dec |
| /dsa  | test/event | TOA, DM, RA, Dec |
| /flarescope | test/observation | start, duration, RA, Dec |

Current implementation is structured as commands to a receiver.

## Command relay

We need a way for OVRO to pull commands in from external server. `relay_api.py` is a REST API that allows a `get` and `set` method for the paths `/dsa` and `/lwa`. Services on the DSA-110 and OVRO-LWA private networks can poll the API for alerts.

The API can be run with:
`uvicorn relay_api:app --reload --host <ip> --port 8001`

Service is available at <ip>:8001. Docs at `/docs`.

Outside of relay:
- CHIME/FRB alerts received and sent to slack directly.
- DSA-110 alerts sent to Swift/GUANO directly. See code at [dsa110-event](https://github.com/dsa110/dsa110-event/blob/main/event/cli.py#L145).

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
