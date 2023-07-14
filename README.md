# ovro-alert
Code and services for sending, receiving, and using astronomical alerts at OVRO.

![diagram of connections](drawio/diagram.drawio.png)

## Requirements
- astropy
- fastapi
- pydantic
- uvicorn
- twisted
- voevent-parse
- slack_sdk
- astropy
- pygcn

## Design and Assumptions

- A central server hosts relay plus one process per alert receiver (e.g., LIGO) -- currently this is on "major"
- Clients at observing resource poll the relay (e.g., OVRO-LWA polls /ligo to see LIGO alerts)
- Observing resource will respond with awareness of telescope state (e.g., OVRO-LWA triggers voltage recording after LIGO event)
- We assume that response is faster than update rate to avoid losing events
- Relay can also just hold info for analysis (e.g., comparing DSA/CHIME FRBs to list of repeaters)

## Protocol

Design centered on sender (alert source).

| path | type | args |
| ---  | ------- | ---- |
| /ligo | test/observation | GraceID, nsamp |
| /chime | test/observation | event_no, dm, position |
| /dsa  | test/observation | trigname, dm, position |
| /gcn  | test/observation | duration, position |

## Command relay

We need a way for OVRO to pull commands in from external server. `relay_api.py` is a REST API that allows a `get` and `set` method for the paths `/dsa` and `/lwa`. Services on the DSA-110 and OVRO-LWA private networks can poll the API for alerts.

The API can be run with:
`uvicorn relay_api:app --reload --host <ip> --port 8001`

Service is available at <ip>:8001. Docs at `/docs`.

Outside of relay:
- CHIME/FRB alerts received and sent to slack directly.
- DSA-110 alerts sent to Swift/GUANO directly. See code at [dsa110-event](https://github.com/dsa110/dsa110-event/blob/main/event/cli.py#L145).

## Applications

Alert scenarios:
- CHIME/FRB to DSA-110 -- Identify co-detections of non-repeating FRBs and alert to new repeating FRBs from CHIME
- CHIME/FRB to OVRO-LWA -- Search for ultra-wide band emission from repeating FRBs from CHIME
- LIGO to OVRO-LWA -- Search for prompt radio counterparts to neutron star mergers
- GCN (Fermi, Swift) to OVRO-LWA -- Search for prompt radio counterparts to short GRBs
- DSA-110 to Swift/GUANO -- Search for prompt high-energy counterparts or afterglows from FRBs (managed by dsa110-event)
- DSA-110 to OVRO-LWA -- Search for ultra-wide band emission from non-repeating FRBs
- Flarescope and OVRO-LWA co-observing -- Automatic OVRO-LWA observing to search for stellar flares
- Optical transients to SPRITE?
- GREX to OVRO-LWA?

### OVRO-LWA

As an low-freq all-sky monitor, OVRO-LWA is well positioned to respond to fast, dispersed transients. We need a way to poll the relay server and send commands for new OVRO-LWA observations. Two kinds of observation must be supported:
- Trigger voltage buffer dump in response to LIGO NS merger events
- Point a power beam at an FRB detected by CHIME or DSA-110

An OVRO client example module is at `lwa_alert_client.py`.

### CHIME

CHIME/FRB has the highest low-resolution FRB discovery rate. It is a good source of events for OVRO-LWA follow up. We need a way to receive CHIME/FRB events to:
- Identify and send slack notification for CHIME/FRB repeaters
- Identify joint CHIME/DSA events
- Repoint DSA-110 (human in the loop)
- Automatically point beam at OVRO-LWA

The VOEvent receiver uses `twistd` to run the `comet` broker, like this:
`twistd -n comet -v --subscribe chimefrb.physics.mcgill.ca --save-event --local-ivo ivo://caltech/comet_broker`

### LIGO

LIGO detects NS mergers and provides rough localizations to guide OVRO-LWA search for prompt counterparts. We need a way to receive LIGO events to:
- Notify on slack
- Automatically trigger voltage buffer dump at OVRO-LWA

### GCN

Swift, Fermi, and other all-sky, high-energy transient search systems distribute alerts publicly with low latency. Short GRBs are caused by binary NS mergers, which may be detectable as prompt fast radio emission. We need a way to receive events and filter for short GRBs to:
- Notify on slack
- Automatically trigger beamforming at OVRO-LWA

### Flarescope

We need a way to start a beamformed observation at OVRO-LWA in coincidence with Flarescope:
- Create SDF for a given (RA, Dec, start time, duration). Optionally set name or integration time.
- Ensure beams are calibrated
- Run SDF

### DSA-110

We need a way to send DSA-110 discovery alerts to Swift/GUANO. Example implementation exists for [realfast](https://github.com/realfastvla/realfast/blob/main/realfast/util.py#L98).

We need a way to send DSA-110 discovery alerts to OVRO-LWA. This could be done via `relay_api.py`.
