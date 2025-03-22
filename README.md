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

I have a separate big data analytics pipeline project more suited for this purpose, using serverless
infrastructure. Once that is ready, I will share that Terraform or CloudFormation template here. It uses the scheduled
exports functionality in the Pulse App, to automate loading scheduled CSV exports into object storage (S3), and exposing
the data to AWS Glue and Amazon Athena. It can then be queried or transformed and loaded to any other tooling, where
you can perform regression analytics/forecasting, etc.
