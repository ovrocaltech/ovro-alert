# ovro-alert
Code and services for sending, receiving, and using astronomical alerts at OVRO. Operations instructions are documented in the [wiki](https://github.com/ovrocaltech/ovro-alert/wiki).

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

As a low-frequency all-sky monitor, OVRO-LWA is well positioned to respond to fast, dispersed transients. We need a way to poll the relay server and send commands for new OVRO-LWA observations. Two kinds of observation must be supported:
- Trigger voltage buffer dump in response to LIGO NS merger events
- Point a power beam at an FRB detected by CHIME or DSA-110

The OVRO-LWA observing client is in this repo.

### CHIME

CHIME/FRB has the highest low-resolution FRB discovery rate. It is a good source of events for OVRO-LWA follow up. We need a way to receive CHIME/FRB events to:
- Identify and send slack notification for CHIME/FRB repeaters
- Identify joint CHIME/DSA events
- Repoint DSA-110 (human in the loop)
- Automatically point beam at OVRO-LWA

The VOEvent receiver uses `twistd` to run the `comet` broker.

### LIGO

LIGO detects NS mergers and provides rough localizations to guide OVRO-LWA search for prompt counterparts. We need a way to receive LIGO events to:
- Notify on slack
- Automatically trigger voltage buffer dump at OVRO-LWA

The LIGO receiver uses `pygcn` to parse the event stream.

### DSA-110

DSA-110 discovers FRBs and provides rapid triggers to Swift/BAT and (optionally) repointing for XRT. Alerts received by GUANO. First implementation done for [realfast](https://github.com/realfastvla/realfast/blob/main/realfast/util.py#L98) and now working at DSA-110

### GCN

Swift, Fermi, and other all-sky, high-energy transient search systems distribute alerts publicly with low latency. Short GRBs are caused by binary NS mergers, which may be detectable as prompt fast radio emission. 
We receive events and filter for short GRBs to:
- Notify on slack
- Automatically trigger beamforming at OVRO-LWA

The GCN receiver uses `pygcn` to parse the event stream.

### Flarescope

We need a way to start a beamformed observation at OVRO-LWA in coincidence with Flarescope:
- Create SDF for a given (RA, Dec, start time, duration). Optionally set name or integration time.
- Ensure beams are calibrated
- Run SDF
