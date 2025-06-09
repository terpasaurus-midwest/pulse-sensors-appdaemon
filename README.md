# Pulse Sensors AppDaemon Integration

Welcome to the **Pulse Sensors AppDaemon Integration** project! This repository provides an **AppDaemon app**
for integrating **Pulse Grow cultivation sensors** with **Home Assistant**, allowing cultivators to expose their
Pulse Grow sensor data in Home Assistant as sensor entities.

## Overview

This integration **automatically discovers** all **Pulse Hubs** for a given Pulse Grow location. It dynamically
retrieves available sensors and their measurements from each discovered device and **automatically creates and
updates** Home Assistant sensor entities for them on the fly—no manual configuration needed.

## Prerequisites

- **[Home Assistant](https://www.home-assistant.io/getting-started/)**: I run Home Assistant OS in a standard Pi 5 container deployment.
- **[AppDaemon](https://community.home-assistant.io/t/home-assistant-community-add-on-appdaemon-4/163259)**: Installed via the AppDaemon 4 add-on.
- **[Pulse Grow API Access](https://api.pulsegrow.com/docs/index.html)**: API key required.
- **[Pulse Sensors](https://pulsegrow.com/collections/everything-hub)**: A Pulse Hub and at least 1 connected sensor.

## What This Integration Does
- **Auto-discovers Pulse Hubs** using the API  
- **Creates & Updates** Home Assistant sensor entities **dynamically**  
- **Polls most recent data** at a configurable interval
- **Publishes MQTT discovery & states** on `pulseapp/<device_unique_id>/<param_name>` topics
- **Supports a wide range of sensor types**
- **Allows Home Assistant automations** to act on sensor readings
- **Supports recording the state updates using the Home Assistant Recorder addon

## Currently Supported Devices & Sensors
- Pulse Hub & all connected sensors  
- Standalone Pulse Devices (e.g., Pulse One, Pulse Pro) *(Planned Support)*  
- **Substrate Sensors**: Volumetric Water Content (VWC) %, Bulk Electrical Conductivity (EC), Pore Water EC, Temperature
- **Environmental Sensors**: Photosynthetic Photon Flux Density (PPFD), Luminous flux density (Lux), Temperature, Relative Humidity, VPD, Dew Point, CO2 PPM 
- **Hydroponic Sensors**: pH, EC, Dissolved Oxygen (DO), Oxidation-Reduction Potential (ORP)

All possible Pulse Hub datapoints should be supported. 

⚠️ **Note**: This integration does **not** provide built-in alerting—Home Assistant has addons to handle those separately.

## Historical Data & Analytics

The main objective of this integration is making current Pulse Hub sensor data available to your Home Assistant
setup, for allowing more complex orchestration and automation to take place in near real-time. Allowing one to take
external actions based on current sensor readings that would otherwise be siloed in the cloud.

Home Assistant (and Recorder) is ill-suited as a big-data analytics platform for loading historical data. This
integration is designed to be generic for scalability. The focus is on current data, not loading historical
time-series from Pulse Hub.

## Mock API Responses
Sample API responses are saved under `mock_responses/`. These were captured by calling the Pulse API endpoints used by
the app. The folder currently contains:

- `hubs_ids.json` – response from `GET /hubs/ids`
- `hub_${PULSE_HUB_ID}.json` – response from `GET /hubs/{hubId}` using the example hub ID
- `sensor_recent_data_${PULSE_THV_ID}.json` – response from `GET /sensors/{sensor_id}/recent-data` for the THV sensor
- `sensor_recent_data_${PULSE_VWC_ID}.json` – response from `GET /sensors/{sensor_id}/recent-data` for the VWC sensor
- `unauthorized_operation.json` - response when making an unprivileged call to an endpoint requiring authentication
