from typing import Any, List, Optional, Union
import base64
import json
import requests

from pydantic import ValidationError
import hassapi as hass

from pulse_models import HubDetails, LatestSensorData

PULSE_API_KEY_ENTITY = "input_text.pulse_api_key"
PULSE_API_BASE = "https://api.pulsegrow.com"
API_TIMEOUT = 10.0
SENSOR_UPDATE_INTERVAL = 60.0  # 1 minutes
SENSOR_DISCOVERY_INTERVAL = 3600.0  # 1 hour


class PulseSensors(hass.Hass):
    def initialize(self):
        """Initialize periodic updates and set up API session."""
        self.logger = self.get_user_log("pulse_sensors")
        self.logger.info("📝 Logging initialized for PulseSensors.")

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
        self.sensor_update_job_uuid = self.run_every(self.update_sensor_states, "now", update_interval)
        self.logger.info(
            f"⏱️ Registered sensor state update job: {self.sensor_update_job_uuid} ({update_interval} sec)"
        )
        self.sensor_discover_job_uuid = self.run_every(self.discover_hub_sensors, "now", discover_interval)
        self.logger.info(
            f"⏱️ Registered hub sensor discovery job: {self.sensor_discover_job_uuid} ({discover_interval} sec)"
        )

        # Listen for changes to update intervals (from the UI or wherever)
        self.listen_state(self.update_intervals, "input_number.sensor_update_interval")
        self.listen_state(self.update_intervals, "input_number.sensor_discovery_interval")

    def update_intervals(self, entity, attribute, old, new, **kwargs):
        """Reconfigure intervals when input_number changes."""
        new_interval = int(float(new))

        if entity == "input_number.pulse_update_interval":
            self.cancel_timer(self.sensor_update_job_uuid)
            self.sensor_update_job_uuid = self.run_every(self.update_sensor_states, "now", new_interval)
            self.logger.info(f"📝️ Updated sensor state update interval to {new_interval} sec")

        elif entity == "input_number.pulse_discover_interval":
            self.cancel_timer(self.sensor_discover_job_uuid)
            self.sensor_discover_job_uuid = self.run_every(self.discover_hub_sensors, "now", new_interval)
            self.logger.info(f"📝️ Updated hub sensor discovery interval to {new_interval} sec")

    def terminate(self):
        """Close the session when the AppDaemon context is terminated."""
        if hasattr(self, "_session"):
            self._session.close()
            self.logger.info("🛑 Closed Pulse API session.")

        self.logger.info("🛑 Pulse Sensor app terminated.")

    def make_request(
        self,
        endpoint: str,
        method: str = "GET",
        **kwargs
    ) -> Union[dict[str, Any], list[Any], None]:
        """Unified method to make an API request to the Pulse API.

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

    def get_hub_ids(self) -> List[int]:
        """Fetch all hub IDs."""
        url = "/hubs/ids"
        self.logger.info(f"📡 Fetching hub IDs at: {url}")
        return self.make_request(url)

    def get_hub_details(self, hub_id: int) -> Optional[HubDetails]:
        """Fetch and validate hub details and attached sensor devices.

        :param hub_id: The ID of the hub to fetch.
        :return: A validated HubDetails object if successful, or None if request or validation fails.
        """
        url = f"/hubs/{hub_id}"
        self.logger.info(f"📡 Fetching hub details for {hub_id} at: {url}")

        response = self.make_request(url)
        if not response:
            self.logger.warning(f"⚠️ No data received for hub {hub_id}")
            return None

        try:
            return HubDetails(**response)
        except ValidationError:
            self.logger.exception(f"❌ Validation error for hub {hub_id}")
            return None

    def get_sensor_latest_data(self, sensor_id: int) -> Optional[LatestSensorData]:
        """Fetch and validate the latest measurements for a sensor.

        :param sensor_id: The ID of the sensor to fetch.
        :return: A validated LatestSensorData object if successful, or None if request or validation fails.
        """
        url = f"/sensors/{sensor_id}/recent-data"
        self.logger.info(f"📡 Fetching latest sensor measurements for {sensor_id}: {url}")

        response = self.make_request(url)
        if not response:
            self.logger.warning(f"⚠️ No data received from sensor {sensor_id}")
            return None

        try:
            return LatestSensorData(**response)
        except ValidationError:
            self.logger.exception(f"❌ Validation error for sensor {sensor_id}")
            return None

    def discover_hub_sensors(self, **kwargs):
        """Discover all sensors and store their IDs."""
        self.logger.info("🔍 Discovering any hubs and their sensors...")
        hub_ids = self.get_hub_ids()
        if not hub_ids:
            self.logger.warning("⚠️ No hubs found, skipping sensor discovery.")
            return

        discovered_sensor_count = 0
        discovered_hubs = []

        for hub_id in hub_ids:
            hub = self.get_hub_details(hub_id)
            if hub is None:
                self.logger.warning(f"⚠️ No data found for hub {hub_id}, skipping.")
                continue

            discovered_hubs.append(hub.model_dump())
            discovered_sensor_count += len(hub.sensorDevices)

        hub_data_b64 = base64.b64encode(json.dumps(discovered_hubs).encode()).decode()
        self.set_state(
            "sensor.pulse_discovered_hubs",
            state=len(discovered_hubs),
            attributes={"b64_data": hub_data_b64}
        )
        self.set_state("sensor.pulse_discovered_sensors", state=discovered_sensor_count)
        self.logger.info(f"✅ Discovered {discovered_sensor_count} sensors across {len(discovered_hubs)} hubs.")

    def update_sensor_states(self, **kwargs):
        """Update state for all discovered sensors, creating new entities if needed."""
        discovered_hubs_state = self.get_state(
            "sensor.pulse_discovered_hubs",
            attribute="b64_data",  # type: ignore
        )

        if not discovered_hubs_state:
            self.logger.warning("⚠️ No sensors discovered yet, skipping update.")
            return

        discovered_hubs = json.loads(base64.b64decode(str(discovered_hubs_state)).decode())
        for hub in discovered_hubs:
            for device in hub["sensorDevices"]:
                sensor = self.get_sensor_latest_data(device["id"])

                if sensor is None:
                    continue

                for measurement in sensor.dataPointDto.dataPointValues:
                    param_name = measurement.ParamName.replace(" ", "_").lower()
                    sensor_type_name = sensor.sensorType.name.replace(" ", "_").lower()
                    entity_id = f"sensor.pulse_{hub['id']}_{device['id']}_{sensor_type_name}_{param_name}"

                    self.logger.info(
                        f"🔄 Updating sensor entity: {device['id']} {sensor_type_name} {param_name}")
                    self.set_state(entity_id, state=measurement.ParamValue, attributes={
                        "hub_id": hub["id"],
                        "unit_of_measurement": measurement.MeasuringUnit,
                        "parameter_name": f"{measurement.ParamName}",
                        "sensor_name": sensor.name,
                        "sensor_id": device["id"],
                        "sensor_type": sensor.sensorType,
                        "sensor_type_name": sensor.sensorType.name,
                        "measured_at": sensor.dataPointDto.createdAt.isoformat(),
                    })
