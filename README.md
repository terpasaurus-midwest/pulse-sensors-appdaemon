# Pulse Sensors AppDaemon Integration

Welcome to the **Pulse Sensors AppDaemon Integration** project! This repository provides an **AppDaemon app** for integrating **Pulse Grow cultivation sensors** with **Home Assistant**, allowing cultivators to retrieve historical environmental, substrate, and hydroponic sensor telemetry at configurable intervals.

## Overview

This integration **automatically discovers** all **Pulse Hubs and standalone Pulse devices** for a given Pulse Grow location. It dynamically retrieves available sensors and data points from each discovered device and **automatically creates Home Assistant sensor entities** for them on the fly—no manual configuration needed.

### What This Integration Does
✅ **Auto-discovers Pulse Hubs & standalone Pulse devices** using the API  
✅ **Creates Home Assistant sensor entities dynamically** for all detected sensors  
✅ **Polls historical data** at a configurable interval  
✅ **Supports a wide range of sensor types**  
✅ **Allows Home Assistant automations** to act on sensor readings  

### Currently Supported Devices & Sensors
- **Pulse Hub** & connected sensors  
- **Standalone Pulse Devices** (e.g., Pulse One, Pulse Pro) *(Planned Support)*  
- **Substrate Sensors**: **Volumetric Water Content (VWC) %, Pore Water EC, Bulk EC, Temperature**  
- **Environmental Sensors**: **Temperature, Humidity, VPD, Dew Point, CO₂, Light Intensity, etc.**  
- **Hydroponic Sensors**: **pH, Dissolved Oxygen, ORP (redox potential), EC, etc.**

All possible Pulse Hub datapoints should be supported, due to the generic way things are implemented in this app. 

⚠️ **Note**: This integration does **not** provide built-in alerting—Home Assistant has addons to handle those separately.

## Features

- **Auto-Discovery of Pulse Devices**: Automatically detects all Pulse Hubs & devices linked to your API key.
- **Auto-Discovery of Changes**: Changed Device Names? Added a new sensor? They get auto-discovered.
- **Dynamic Sensor Creation**: Automatically registers sensors in **Home Assistant**.
- **Historical Data Retrieval**: Fetches past sensor data at a UI configurable interval.
- **UI Configurable Options**: Device and sensor update intervals are configurable via the UI without code changes.
- **Support for Multiple Sensors**: Works with **Pulse Hub** devices and (soon) **Pulse Pro** and other standalone Pulse sensors.

## Prerequisites

- **[Home Assistant](https://www.home-assistant.io/getting-started/)**: I run Home Assistant OS in a standard Pi 5 container deployment.
- **[AppDaemon](https://community.home-assistant.io/t/home-assistant-community-add-on-appdaemon-4/163259)**: Installed via the AppDaemon 4 add-on.
- **[Pulse Grow API Access](https://api.pulsegrow.com/docs/index.html)**: API key required.
- **[Pulse Sensors](https://pulsegrow.com/collections/everything-hub)**: A Pulse Hub and at least 1 connected sensor.
