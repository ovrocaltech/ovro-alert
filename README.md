# ovro-alert
Code and services for sending, receiving, and using astronomical alerts


## Command relay

We need a way for OVRO to pull commands in from external server. `relay_api.py` is a REST API that allows a `get` and `set` method for the paths `/dsa` and `/lwa`. The API can be run with:
`uvicorn relay_api:app --reload`

Service is available at 127.0.0.1:8000. Docs at `/docs`.

## OVRO-LWA

Receiving LIGO alerts to trigger OVRO-LWA voltage buffer...

Receiving DSA-110 alerts to start beamforming observation of FRB...

## DSA-110

Receiving CHIME/FRB alerts to identify repeating FRBs...

Sending DSA-110 alerts to Swift/GUANO...

Sending DSA-110 alerts to OVRO-LWA...