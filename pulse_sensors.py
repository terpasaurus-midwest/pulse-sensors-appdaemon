from datetime import datetime, timedelta, timezone
from enum import IntEnum
import json
import requests

import hassapi as hass

PULSE_API_KEY_ENTITY = "input_text.pulse_api_key"
LAST_TIMESTAMP_ENTITY = "input_text.pulse_last_update"
PULSE_API_BASE = "https://api.pulsegrow.com"
API_TIMEOUT = 20
SENSOR_UPDATE_INTERVAL = 600.0  # 10 minutes
SENSOR_DISCOVERY_INTERVAL = 43200.0  # 12 hours


class DeviceType(IntEnum):
    """Pulse device types as defined in the Pulse API spec."""
    PULSE_ONE = 0  # Original Pulse One device
    PULSE_PRO = 1  # Pulse Pro device
    HUB = 2  # Pulse Hub device
    SENSOR = 3  # Standalone sensor (e.g., VWC, pH, EC, etc.)
    CONTROL = 4  # Some control device (unclear what this is)
    PULSE_ZERO = 5  # Possibly an older or experimental device?
    UNKNOWN = -1  # Fallback for unknown device types

    @classmethod
    def _missing_(cls, value):
        """Handles unknown values by returning the UNKNOWN enum member."""
        return cls.UNKNOWN


class SensorType(IntEnum):
    """Sensor types as defined in the Pulse API spec.

    Some of these are guesses based on the device type. Specifically,
    the multiple VWC sensors. I only have the Acclima, so I can't verify
    the types for the Growlink from Pulse, the Growlink from Terralink
    using a retrofit kit, and the TEROS 12.

    There are also two different PAR sensors offered for the Pulse Hub,
    but only one PAR sensor type. I will try to get a comprehensive
    list from Pulse Grow. If you have a different PAR or VWC sensor,
    please create an issue or PR on the GitHub repo, and I'll try to
    support it.
    """
    HUB = 0  # Hub device
    VWC1 = 1  # Acclima TDR 310W - Soil Moisture Sensor
    THV1 = 2  # Temperature, Humidity, VPD Sensor
    PH10 = 3  # pH Sensor
    EC1 = 4   # Electrical Conductivity Sensor
    VWC12 = 5  # TEROS12 Retrofit Kit - Soil Moisture Sensor
    PAR1 = 8  # PAR (Light) Sensor
    VWC2 = 9  # Terralink (Pulse-vendored) - Soil Moisture Sensor
    ORP1 = 10  # ORP (Redox Potential) Sensor
    THC1 = 11  # CO₂, Temperature, Humidity, Lux Sensor (CO2-1)
    TDO1 = 12  # Dissolved Oxygen (DO) Sensor
    VWC3 = 13  # Possibly Terralink (Growlink-vendored/retrofit) - Soil Moisture Sensor
    UNKNOWN = -1  # Default fallback for unknown values

    @classmethod
    def _missing_(cls, value):
        """Handles unknown values by returning the UNKNOWN enum member."""
        return cls.UNKNOWN


class SensorReadingType(IntEnum):
    """Sensor reading types as defined in the Pulse API spec."""
    # Acclima (VWC1)
    VWC1_RH = 0  # VWC1 - Relative Humidity Reading
    VWC1_TEMPERATURE = 1  # VWC1 - Temperature Reading
    VWC1_CONDUCTIVITY = 2  # VWC1 - Conductivity Reading
    VWC1_CONDUCTIVITY_PWE = 3  # VWC1 - Pore Water EC Reading

    # Growlink Terralink (VWC2)
    VWC2_RH = 4  # VWC2 - Relative Humidity Reading
    VWC2_TEMPERATURE = 5  # VWC2 - Temperature Reading
    VWC2_CONDUCTIVITY = 6  # VWC2 - Conductivity Reading
    VWC2_CONDUCTIVITY_PWE = 7  # VWC2 - Pore Water EC Reading

    # TEROS 12 (VWC12)
    VWC12_RH = 8  # VWC12 - Relative Humidity Reading
    VWC12_TEMPERATURE = 9  # VWC12 - Temperature Reading
    VWC12_CONDUCTIVITY = 10  # VWC12 - Conductivity Reading
    VWC12_CONDUCTIVITY_PWE = 11  # VWC12 - Pore Water EC Reading

    # General Readings
    PH = 12  # pH Reading
    WATER_TEMPERATURE = 13  # Water Temperature Reading
    VPD = 14  # Vapor Pressure Deficit Reading
    DEW_POINT = 15  # Dew Point Reading
    AIR_TEMPERATURE = 16  # Air Temperature Reading
    ORP = 17  # Oxidation-Reduction Potential (ORP) Reading
    CO2 = 18  # Carbon Dioxide (CO₂) Reading
    DLI = 19  # Daily Light Integral (DLI) Reading
    PPFD = 20  # Photosynthetic Photon Flux Density (PPFD) Reading
    EC = 21  # Electrical Conductivity (EC) Reading
    THC1_LIGHT = 22  # Light Intensity Reading from THC1
    RH = 23  # Relative Humidity Reading
    ORIGINAL_DEVICES_LIGHT = 24  # Light Reading from Original Devices
    DO = 25  # Dissolved Oxygen (DO) Reading

    UNKNOWN = -1  # Default fallback for unknown values

    @classmethod
    def _missing_(cls, value):
        """Handles unknown values by returning the UNKNOWN enum member."""
        return cls.UNKNOWN


class PulseSensors(hass.Hass):
    def initialize(self):
        """Initialize periodic updates and set up API session."""
        self.logger = self.get_user_log("pulse_sensors")
        self.logger.info("📜 Logging initialized for PulseSensors.")

        self.api_key = self.get_state(PULSE_API_KEY_ENTITY)
        if not self.api_key:
            self.logger.error("🛑 Pulse API key not found!")
            return

        self._session = requests.Session()
        self._session.headers.update({"x-api-key": self.api_key})
        self.logger.info("🔗 Created persistent Pulse API session.")

        # Read update intervals from Home Assistant inputs
        update_interval = int(float(
            self.get_state("input_number.sensor_update_interval")
            or SENSOR_UPDATE_INTERVAL
        ))
        discover_interval = int(float(
            self.get_state("input_number.sensor_discovery_interval")
            or SENSOR_DISCOVERY_INTERVAL
        ))

        # Register scheduled jobs
        self.sensor_update_job_uuid = self.run_every(self.update_sensors, "now", update_interval)
        self.logger.info(f"⏱️ Registered sensor update job: {self.sensor_update_job_uuid} ({update_interval} sec)")
        self.sensor_discover_job_uuid = self.run_every(self.discover_sensors, "now", discover_interval)
        self.logger.info(
            f"⏱️ Registered sensor discovery job: {self.sensor_discover_job_uuid} ({discover_interval} sec)"
        )

        # Listen for changes to update intervals (from the UI or wherever)
        self.listen_state(self.update_intervals, "input_number.sensor_update_interval")
        self.listen_state(self.update_intervals, "input_number.sensor_discovery_interval")

    def update_intervals(self, entity, attribute, old, new, **kwargs):
        """Reconfigure intervals when input_number changes."""
        new_interval = int(float(new))

        if entity == "input_number.pulse_update_interval":
            self.cancel_timer(self.sensor_update_job_uuid)
            self.sensor_update_job_uuid = self.run_every(self.update_sensors, "now", new_interval)
            self.logger.info(f"⏱️ Updated sensor update interval to {new_interval} sec")

        elif entity == "input_number.pulse_discover_interval":
            self.cancel_timer(self.sensor_discover_job_uuid)
            self.sensor_discover_job_uuid = self.run_every(self.discover_sensors, "now", new_interval)
            self.logger.info(f"⏱️ Updated sensor discovery interval to {new_interval} sec")

    def terminate(self):
        """Close the session when the AppDaemon context is terminated."""
        if hasattr(self, "_session"):
            self._session.close()
            self.logger.info("🛑 Closed Pulse API session.")

        self.logger.info("🛑 Pulse Sensor app terminated.")

    def make_request(self, endpoint, method="GET", **kwargs):
        """
        Unified method to make an API request to the Pulse API.

        This is mostly just exposing request.Session().request() for convenience.

        :param endpoint: API endpoint (appended to PULSE_API_BASE).
        :param method: HTTP method (default: "GET").
        :param kwargs: Additional request parameters (json, params, etc.).
                       Supports 'ignore_errors=True' to suppress error logs.
        :return: JSON response (dict) or None if an error occurs (or {} if 'ignore_errors' is set).
        """
        url = f"{PULSE_API_BASE}{endpoint}"
        ignore_errors = kwargs.pop("ignore_errors", False)

        try:
            response = self._session.request(method, url, timeout=API_TIMEOUT, **kwargs)
            return response.json()
        except Exception:
            self.logger.exception(f"❌ Request error for {method} {url}")
            if ignore_errors:
                return {}
            raise

    def get_hub_ids(self):
        """Fetch all hub IDs."""
        url = "/hubs/ids"
        self.logger.info(f"📡 Fetching hub IDs at: {url}")
        return self.make_request(url)

    def get_hub_details(self, hub_id):
        """Fetch hub details and sensors for a given hub.

        Returns:
        {
            "id": hub_id,
            "name": "Hub Name",
            "sensorDevices": [{sensor_1_data}, {sensor_2_data}, ... ]
        }
        """
        url = f"/hubs/{hub_id}"
        self.logger.info(f"📡 Fetching hub details for {hub_id} at: {url}")
        return self.make_request(url)

    def get_sensor_data(self, sensor_id, last_update):
        """Fetch latest sensor data since last recorded timestamp."""
        start_time = last_update.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"/sensors/{sensor_id}/data-range?start={start_time}"
        self.logger.info(f"📡 Fetching sensor data from {start_time} to now: {url}")
        return self.make_request(url)

    def discover_sensors(self, **kwargs):
        """Discover all sensors and store their IDs."""
        self.logger.info("🔍 Discovering hubs and sensors...")
        hub_ids = self.get_hub_ids()
        if not hub_ids:
            self.logger.warning("⚠️ No hubs found, skipping sensor discovery.")
            return

        discovered_sensors = {}
        discovered_hubs = {}

        for hub_id in hub_ids:
            hub_data = self.get_hub_details(hub_id)
            if not hub_data:
                self.logger.warning(f"⚠️ No data found for hub {hub_id}, skipping.")
                continue

            hub_name = hub_data.get("name", f"Hub {hub_id}")
            discovered_hubs[hub_id] = hub_name

            for sensor in hub_data.get("sensorDevices", []):
                sensor_id = sensor["id"]
                sensor_name = sensor["name"]
                discovered_sensors[sensor_id] = {
                    "name": sensor_name,
                    "hub_id": hub_id,
                    "hub_name": hub_name,
                    "sensor_type": sensor.get("sensorType"),
                    "par_sensor_subtype": sensor.get("parSensorSubtype"),
                    "device_type": sensor.get("deviceType"),
                    "display_order": sensor.get("displayOrder"),
                    "grow_id": sensor.get("growId"),
                    "hidden": sensor.get("hidden", False),
                }

        self.set_state("sensor.pulse_discovered_hubs", state=json.dumps(discovered_hubs))
        self.set_state("sensor.pulse_discovered_sensors", state=json.dumps(discovered_sensors))
        self.logger.info(f"✅ Discovered {len(discovered_sensors)} sensors across {len(discovered_hubs)} hubs.")

    def update_sensors(self, **kwargs):
        """Fetch latest sensor data since the last recorded timestamp."""
        self.logger.info("🔄 Updating sensor data...")

        # Get last update timestamp
        last_update_str = self.get_state(LAST_TIMESTAMP_ENTITY)
        if last_update_str and last_update_str != "unknown":
            last_update = datetime.strptime(last_update_str, "%Y-%m-%dT%H:%M:%SZ")
        else:
            # get data from the last hour by default
            last_update = datetime.now(timezone.utc) - timedelta(hours=1)

        self.logger.info(f"📅 Last update was determined to be: {last_update.isoformat()}")

        sensor_data = self.get_state("sensor.pulse_discovered_sensors")
        if not sensor_data:
            self.logger.warning("⚠️ No sensors discovered yet, skipping update.")
            return

        discovered_sensors = json.loads(sensor_data)
        new_timestamp = last_update

        for sensor_id, sensor_info in discovered_sensors.items():
            sensor_name = sensor_info["name"]
            response = self.get_sensor_data(sensor_id, last_update)

            if not response:
                self.logger.warning(f"⚠️ No data received for sensor {sensor_id}: {response}")
                continue

            required_keys = {"dataPointValues", "dataPointValuesCreatedAt"}
            if not isinstance(response, dict) or not required_keys.issubset(response):
                self.logger.warning(
                    f"⚠️ Data received wasn't structured as expected for '{sensor_id}-{sensor_name}': {response}"
                )
                continue

            timestamps = response["dataPointValuesCreatedAt"]
            if not timestamps:
                self.logger.warning(f"⚠️ No timestamps available for sensor {sensor_id}. Skipping.")
                continue

            # Each sensor provides datapoints for various parameters, like temperature,
            # humidity, dew point, etc. Each dictionary in this list has keys describing
            # the parameter being measured: "MeasuringUnit", "ParamName", "ParamValues".
            # All of these are string values.
            for metadata in response["dataPointValues"]:
                param_name = metadata["ParamName"]
                measuring_unit = metadata["MeasuringUnit"]

                # This is absolutely absurd, but the Pulse APIs data model here is at fault.
                # The individual datapoint values, which map to each timestamp in
                # data["dataPointValuesCreatedAt"], are encoded as a comma-separated string here.
                # Like: "66.6, 66.7, 66.6, 70, 68.2".

                # Split the string on comma, into a list. Then coerce each string value into a float.
                try:
                    datapoint_values = list(map(float, metadata["ParamValues"].split(", ")))
                except ValueError:
                    self.logger.warning(
                        f"⚠️ Failed to parse values for {sensor_id}-{sensor_name}: {metadata['ParamValues']}")
                    continue

                # We should have an equal number of datapoints to map to our timestamps, or something is wrong
                if len(datapoint_values) != len(timestamps):
                    self.logger.warning(
                        f"⚠️ Mismatch in lengths for {sensor_id}-{sensor_name} "
                        f"({len(datapoint_values)} values, {len(timestamps)} timestamps). Skipping."
                    )
                    continue

                # Map each timestamp to its corresponding sensor value
                for i, timestamp in enumerate(timestamps):
                    entry_time = datetime.strptime(
                        timestamp, "%Y-%m-%dT%H:%M:%S"
                    ).replace(tzinfo=timezone.utc)

                    if entry_time > new_timestamp:
                        new_timestamp = entry_time

                    # Normalize param names, they can look like e.g. "Dew Point"
                    # This would make them "dew_point"
                    sensor_key = param_name.lower().replace(" ", "_")
                    sensor_value = datapoint_values[i]

                    # Construct state key dynamically
                    state_key = f"sensor.pulse_{sensor_id}_{sensor_key}"

                    # Use the provided measuring unit instead of a hardcoded map
                    unit = measuring_unit if measuring_unit else "N/A"

                    # Set state in Home Assistant
                    self.set_state(
                        state_key,
                        state=sensor_value,
                        attributes={
                            "unit_of_measurement": unit,
                            "friendly_name": f"{param_name} - {sensor_name}"
                        },
                    )

        if new_timestamp > last_update:
            self.set_state(LAST_TIMESTAMP_ENTITY, state=new_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"))
            self.logger.info(f"🏁 Updated last timestamp to: {new_timestamp.isoformat()}")
