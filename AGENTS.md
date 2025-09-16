# Agent instructions for pulse-sensors-appdaemon

This file contains instructions for machine (AI) agents, to quickly understand this project and the environment
in which the agent is currently being prompted. It is not intended for human readers, and they will be unable to
make full use of these instructions. A human reader should reference the `README.md` file for more information.

## Project Overview

This is a Python project that implements an AppDaemon agent. AppDaemon is a loosely coupled, multi-threaded,
sandboxed python execution environment for writing automation apps for home automation projects, and any environment
that requires a robust event driven architecture. AppDaemon uses a plugin-based architecture, with plugins for Home
Assistant and an MQTT event broker. This project implements all of these plugins, through the `PulseApp` class.

This project uses the `PulseApp` class to implement the AppDaemon agent. This agent is responsible for discovering
connected, proprietary, agricultural telemetry devices, produced by vendor Pulse Labs, Inc., via a RESTful API they
provide to their customers. It uses this data to generate device discovery payloads, which are dictionary objects that
describe an device, its attributes, and its provided sensors. Those payloads are then published to the MQTT broker,
typically Mosquitto provided as a Home Assistant addon. This causes Home Assistant to register the devices and sensor entities
within its device registry.

To regularly perform its tasks, the agent creates two scheduled AppDaemon jobs, currently:
- `self.hub_device_discovery`: discovers devices and publishes device discovery payloads to the MQTT broker
- `self.hub_sensor_updates`: gets and publishes the latest sensor data for each device to the MQTT broker

## Project Structure

```
├── AGENTS.md
├── assets
│   ├── device_info_vwc.png
│   ├── device_list.png
│   └── ha_dashboard.png
├── LICENSE
├── mock_responses
│   ├── hub_591.json
│   ├── hubs_ids.json
│   ├── sensor_recent_data_2575.json
│   ├── sensor_recent_data_380.json
│   └── unauthorized_operation.json
├── NOTICE
├── poetry.lock
├── pulseapp
│   ├── app.py
│   ├── app.yaml
│   ├── __init__.py
│   └── models.py
├── pyproject.toml
└── README.md
```

The `pulseapp` directory at the project root contains the Python package for the AppDaemon agent. It contains:
- `app.py`: implements the agent's logic
- `models.py`: pydantic models for the Pulse API responses
- `app.yaml`: configuration file for the AppDaemon agent

The project dependencies and virtual environment are managed using Poetry. The dependencies are listed in `pyproject.toml`
in the project root. The `poetry.lock` file contains the exact, resolved versions of the dependencies. The `mock_responses`
directory contains sample responses from the Pulse API as JSON files.

## Environment variables
The container exposes a few variables that allow you to make authenticated API calls as the repository owner to the Pulse API:

- `PULSE_API_BASE` - base URL for the Pulse API
- `PULSE_API_KEY` - API key header value
- `PULSE_HUB_ID` - example hub id
- `PULSE_VWC_ID` - example volumetric water content sensor id
- `PULSE_THV_ID` - example temperature/humidity/VPD sensor id

An agent can use them with tools such as `curl`. This is an example request:

```bash
curl --request GET "$PULSE_API_BASE/hubs/$PULSE_HUB_ID" --header "x-api-key: $PULSE_API_KEY"
```

## Tests
Before committing any change, run `py_compile` on the app's Python files.

```bash
poetry run python -m py_compile pulseapp/*.py
```

The repository currently does not provide unit tests; successful compilation is considered sufficient.

## Style
Use Python 3.11 features and keep the code readable. Try to follow PEP8 and established best practices.
Use `poetry ruff check` as your linter and `poetry ruff format` as your formatter. They are configured in
`pyproject.toml`. This tool has been preinstalled in your current operating environment.

The linting tool `basedpyright` is also used to check the code for type errors and similar issues. It is
not installed in your operating environment. You can just focus on using `ruff` instead.

## API Response Examples
The `mock_responses` directory contains JSON files which show the Pulse APi response for a recent data API call
to a THV and VWC sensor, as well as a request to get all data for a hub. There is also an example showing an
unauthorized error, like one would see if the API is invalid.

You can refer to these example responses, whenever you need to validate what the API response would look like.
Also, recall that you have network access to the Pulse API with a key to authenticate your calls.
