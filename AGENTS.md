# AGENTS instructions for pulse-sensors-appdaemon

This file contains instructions for machine (AI) agents, to quickly understand this project and the environment
in which the agent is currently being prompted. It is not intended for human readers, and they will be unable to
make use of these instructions.

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
python -m py_compile pulseapp.py models.py
```

The repository currently does not provide unit tests; successful compilation is considered sufficient.

## Style
Use Python 3.11 features and keep the code readable. Try to follow PEP8 and established best practices.
Use `poetry ruff check` as your linter and `poetry ruff format` as your formatter. They are configured in
`pyproject.toml`. This tool has been preinstalled in your current operating environment.

The linting tool `basedpyright` is also used to check the code for type errors and similar issues.

## API Response Examples
The `mock_responses` directory contains JSON files which show the Pulse APi response for a recent data API call
to a THV and VWC sensor, as well as a request to get all data for a hub. There is also an example showing an
unauthorized error, like one would see if the API is invalid.

You can refer to these example responses, whenever you need to validate what the API response would look like.
Also, recall that you have network access to the Pulse API with a key to authenticate your calls.
