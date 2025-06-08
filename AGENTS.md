# AGENTS instructions for pulse-sensors-appdaemon

This repository contains an AppDaemon app that integrates the Pulse Grow API with Home Assistant via MQTT.

## Environment variables
The container exposes a few variables that allow you to make authenticated API calls as the repository owner:

- `PULSE_API_BASE` - base URL for the Pulse API
- `PULSE_API_KEY` - API key header value
- `PULSE_HUB_ID` - example hub id
- `PULSE_VWC_ID` - example volumetric water content sensor id
- `PULSE_THV_ID` - example temperature/humidity/VPD sensor id

Use them with tools such as `curl`:

```bash
curl --request GET "$PULSE_API_BASE/hubs/$PULSE_HUB_ID" --header "x-api-key: $PULSE_API_KEY"
```

## Tests
Before committing any change, run:

```bash
python -m py_compile pulse_sensors.py pulse_models.py
```

The repository currently does not provide unit tests; successful compilation is considered sufficient.

## Style
Use Python 3.11 features and keep the code readable. No additional style requirements have been defined.
