# ovro-alert
Code and services for sending, receiving, and using astronomical alerts at OVRO.

Alert scenarios:
- CHIME/FRB to DSA-110 -- Identify co-detections of non-repeating FRBs and alert to new repeating FRBs from CHIME
- CHIME/FRB to OVRO-LWA -- Search for ultra-wide band emission from repeating FRBs from CHIME
- DSA-110 to Swift/GUANO -- Search for prompt high-energy counterparts or afterglows from FRBs
- DSA-110 to OVRO-LWA -- Search for ultra-wide band emission from non-repeating FRBs
- LIGO to OVRO-LWA -- Search for prompt radio counterparts to neutron star mergers
- CHIMERA to OVRO-LWA -- Dynamic co-observing to search for stellar flares
- Optical transients to SPRITE?
- GREX to OVRO-LWA?

## Requirements
- astropy
- fastapi
- pydantic
- uvicorn


## Command relay

We need a way for OVRO to pull commands in from external server. `relay_api.py` is a REST API that allows a `get` and `set` method for the paths `/dsa` and `/lwa`. Services on the DSA-110 and OVRO-LWA private networks can poll the API for alerts.

The API can be run with:
`uvicorn relay_api:app --reload --host <ip> --port 8001`

Service is available at <ip>:8001. Docs at `/docs`.

## OVRO-LWA

We need a way to poll the relay server and send commands for new OVRO-LWA observations. Two kinds of observation must be supported:
- Trigger voltage buffer dump
- Point a power beam at a target

An OVRO client example module is at `lwa_alert.py`.

## DSA-110

We need a way to poll the relay server with info about CHIME/FRB events to:
- Identify and send slack notification for CHIME/FRB repeaters
- Identify joint CHIME/DSA events

We need a way to send DSA-110 discovery alerts to Swift/GUANO. Example implementation exists for [realfast](https://github.com/realfastvla/realfast/blob/main/realfast/util.py#L98).

We need a way to send DSA-110 discovery alerts to OVRO-LWA. This could be done via `relay_api.py`.
