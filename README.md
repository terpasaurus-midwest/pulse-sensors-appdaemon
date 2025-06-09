# Pulse Sensors AppDaemon Integration

This AppDaemon app integrates Pulse Labs sensor data into Home Assistant via MQTT. It uses the Pulse Grow API to discover your hubs and their connected devices, then publishes MQTT discovery and state messages so Home Assistant can treat them as native devices.

## What It Does

- Discovers all Pulse Hubs and connected sensors using Pulse Labs’ REST API.
- Publishes MQTT discovery messages so hubs and sensors show up in Home Assistant's device registry.
- Updates sensor readings every minute by default, pushing live telemetry to Home Assistant via MQTT.
- Sensors work seamlessly with Home Assistant features like generic thermostats, hygrostats, and automation helpers.
- Makes Pulse data accessible to any MQTT-capable client—not just Home Assistant.

## Why This Helps

Pulse Labs doesn’t support MQTT or Home Assistant natively, which limits local automation. This app bridges that
gap—once installed, you can:

- View Pulse sensor data in Home Assistant dashboards, configurable like native devices.
- Use grow tent temp/humidity sensors to control HVAC via HA automations.
- Feed substrate EC and VWC into irrigation scheduling logic.
- Log all readings in HA Recorder or external tools.
- Pipe real-time data to any local MQTT consumer (other apps, dashboards, logging).

## Screenshots

With this integration, sensors like Pulse's VWC show up in Home Assistant under their respective hubs, with all
connected measurement values (e.g., VWC, Bulk EC, Pore Water EC, Temp) exposed as individual entities. From there, 
they behave like any other MQTT-native sensor in HA.

![Example Device Info Screenshot](/assets/device_info_vwc.png)  
*Example of a registered Acclima TDR-310W device showing its data in Home Assistant.*

![Example Device List Screenshot](/assets/device_list.png)  
*The device list showing THV, VWC, and Hub devices.*

## How It Works

This app uses two scheduled jobs:

### Sensor Discovery (`discover_hub_sensors`)

- Runs hourly (or on a custom interval).
- Calls the Pulse API to list hubs and attached devices.
- Builds MQTT discovery payloads using the device registry format.
- Publishes one config topic per hub and sensor device to the `homeassistant` discovery prefix like:
  `homeassistant/device/pulseapp_vwc1_1234/config`

### Sensor State Updates (`update_sensor_states`)

- Runs every minute (or on a custom interval).
- Queries the latest data from each sensor.
- Publishes readings to state topics like:
  `pulseapp/pulseapp_vwc1_1234/pore_water_ec`

## Requirements

- Home Assistant with:
  - [MQTT integration](https://www.home-assistant.io/integrations/mqtt/) enabled
  - [AppDaemon](https://appdaemon.readthedocs.io/) installed
- Pulse Grow API key saved to an `input_text.pulse_api_key` entity
- At least one Pulse Hub with attached sensors
- MQTT broker (typically Mosquitto) connected to both Home Assistant and AppDaemon

## Configuration

You configure update/discovery intervals using two `input_number` entities:

- `input_number.sensor_update_interval` (default: 60s)
- `input_number.sensor_discovery_interval` (default: 3600s)

These values can be adjusted live in the UI, and the app will reconfigure itself automatically.

As mentioned earlier, you need an `input_text.pulse_api_key` entity with your Pulse API key saved.

## Known Limitations

- Only a single Pulse Grow location is supported for now.
  - If you have a Professional subscription to Pulse and want to support multiple grows, contact me.
- No historical data import—this is a live sync integration, not an analytics backend.
- No alerting—it’s expected that Home Assistant’s automations or notification integrations handle that.

## Disclaimer

This project and I are **not affiliated with, endorsed by, or in any way officially connected to Pulse Labs, Inc.** All
product names, logos, and brands are the property of their respective owners.
