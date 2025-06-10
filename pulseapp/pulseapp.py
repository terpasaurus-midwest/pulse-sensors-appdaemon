from typing import Any, List, Optional, Union
import json
import requests
import textwrap

from pydantic import ValidationError
from appdaemon import adbase as ad
from appdaemon import AppDaemon, ADAPI
from appdaemon.models.config.app import AppConfig
from appdaemon.plugins.hass.hassapi import Hass
from appdaemon.plugins.mqtt.mqttapi import Mqtt

from models import HubDetails, LatestSensorData, DeviceClass

__version__ = "0.1.0"

PULSE_API_KEY_ENTITY = "input_text.pulse_api_key"
PULSE_API_BASE = "https://api.pulsegrow.com"
API_TIMEOUT = 10.0
SENSOR_UPDATE_INTERVAL = 60.0  # 1 minute
SENSOR_DISCOVERY_INTERVAL = 3600.0  # 1 hour

# This is added to device discovery messages so, Home
# Assistant logs have context about the source of MQTT messages.
MQTT_ORIGIN = {
    "name": "Pulse Sensors AppDaemon",
    "sw": str(__version__),
    "url": "https://github.com/terpasaurus-midwest/pulse-sensors-appdaemon",
}


class PulseApp(ad.ADBase):
    def __init__(self, ad: "AppDaemon", config_model: "AppConfig"):
        # Placeholders for the API plugins we need.
        self._adapi: ADAPI | None = None
        self._hass: Hass | None = None
        self._queue: Mqtt | None = None
        self._session: requests.Session | None = None

        # Placeholders for scheduled job handles set up during ``initialize``.
        self.sensor_update_job_uuid: str | None = None
        self.sensor_discover_job_uuid: str | None = None
        super().__init__(ad, config_model)

    def initialize(self):
        """Initialize periodic updates and set up API session."""
        # Load all the plugins we need.
        self._adapi: ADAPI = self.get_ad_api()
        self._hass: Hass = self.get_plugin_api("HASS")
        self._queue: Mqtt = self.get_plugin_api("MQTT")

        if not self._hass or not self._queue:
            raise RuntimeError("❌ Required plugin(s) missing: HASS or MQTT")

        # Set up a persistent requests Session, authenticated.
        # No API key has to be a hard failure, we can do nothing without one.
        api_key = self._hass.get_state(PULSE_API_KEY_ENTITY)
        if not api_key:
            self.logger.error(f"🛑 Pulse API key not found at {PULSE_API_KEY_ENTITY}")
            raise RuntimeError(f"Pulse API key not found at: {PULSE_API_KEY_ENTITY}")
        self._session = requests.Session()
        self._session.headers.update({"x-api-key": api_key})
        self.logger.info("🔗 Created persistent Pulse API session.")

        # If the user specified custom update intervals, use them
        # otherwise fallback to our defaults
        update_interval = int(
            float(
                self._hass.get_state("input_number.sensor_update_interval")
                or SENSOR_UPDATE_INTERVAL
            )
        )
        discover_interval = int(
            float(
                self._hass.get_state("input_number.sensor_discovery_interval")
                or SENSOR_DISCOVERY_INTERVAL
            )
        )

        # Register scheduled jobs with the AD API helper.
        self.sensor_update_job_uuid = self._adapi.run_every(
            self.update_sensor_states,
            "now",
            update_interval,
        )
        self.logger.info(
            f"⏱️ Registered sensor state update job: {self.sensor_update_job_uuid} ({update_interval} sec)"
        )
        self.sensor_discover_job_uuid = self._adapi.run_every(
            self.discover_hub_sensors,
            "now",
            discover_interval,
        )
        self.logger.info(
            f"⏱️ Registered hub sensor discovery job: {self.sensor_discover_job_uuid} ({discover_interval} sec)"
        )

        # Listen for changes to update intervals (from the UI or wherever)
        self._hass.listen_state(
            self.update_intervals, "input_number.sensor_update_interval"
        )
        self._hass.listen_state(
            self.update_intervals, "input_number.sensor_discovery_interval"
        )

        # Kick off discovery shortly after we start, so the user doesn't wait an hour
        self._adapi.run_in(self.discover_hub_sensors, 10)

    def update_intervals(self, entity, attribute, old, new, **kwargs):
        """Reconfigure intervals when input_number changes."""
        new_interval = int(float(new))

        # Only cancel if we had a scheduled job handle
        if entity == "input_number.sensor_update_interval":
            if self.sensor_update_job_uuid:
                self._adapi.cancel_timer(self.sensor_update_job_uuid)
            self.sensor_update_job_uuid = self._adapi.run_every(
                self.update_sensor_states,
                "now",
                new_interval,
            )
            self.logger.info(
                f"📝️ Updated sensor state update interval to {new_interval} sec"
            )

        elif entity == "input_number.sensor_discovery_interval":
            if self.sensor_discover_job_uuid:
                self._adapi.cancel_timer(self.sensor_discover_job_uuid)
            self.sensor_discover_job_uuid = self._adapi.run_every(
                self.discover_hub_sensors,
                "now",
                new_interval,
            )
            self.logger.info(
                f"📝️ Updated hub sensor discovery interval to {new_interval} sec"
            )

    def terminate(self):
        """Close the session when the AppDaemon context is terminated."""
        if hasattr(self, "_session"):
            self._session.close()
            self.logger.info("🛑 Closed Pulse API session.")

        self.logger.info("🛑 Pulse Sensor app terminated.")

    def make_request(
        self, endpoint: str, method: str = "GET", **kwargs
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
        self.logger.info(
            f"📡 Fetching latest sensor measurements for {sensor_id}: {url}"
        )

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

        self.logger.info(
            f"🔍 Discovery: Found {len(hub_ids)} hub devices, getting details..."
        )

        discovered_sensor_count, discovered_hubs = self._process_and_publish_hubs(
            hub_ids
        )

        self._hass.set_state(
            "sensor.pulseapp_discovered_hubs",
            state=len(discovered_hubs),
            attributes={"hubs": discovered_hubs},
        )
        self._hass.set_state(
            "sensor.pulseapp_discovered_sensors", state=discovered_sensor_count
        )
        self.logger.info(
            f"✅ Discovered {discovered_sensor_count} sensors across {len(discovered_hubs)} hubs."
        )

    def update_sensor_states(self, **kwargs):
        """Publish the latest data points for each connected hub and sensor device."""
        discovered_hubs: dict[dict, Any] = self._hass.get_state(
            "sensor.pulseapp_discovered_hubs",
            attribute="hubs",
        )

        if not discovered_hubs:
            self.logger.warning("⚠️ No sensors discovered yet, skipping update.")
            return

        for hub in discovered_hubs:
            # Ensure this hub's fake binary sensor component is marked as ``ON``
            self._publish_hub_state(hub)

            # Get and publish the latest readings for each connected sensor device
            for device in hub["sensorDevices"]:
                device_data = self.get_sensor_latest_data(device["id"])
                if device_data is None:
                    continue

                self._publish_device_state(device["id"], device_data)

    def _publish_hub_state(self, hub: dict[str, Any]) -> None:
        """Publish the hub state and update all attached devices."""
        hub_unique_id = f"pulseapp_hub_{hub['id']}"
        self._queue.mqtt_publish(
            topic=f"pulseapp/{hub_unique_id}/state",
            payload="ON",
            retain=True,
        )

    def _publish_device_state(
        self, device_id: int, device_data: LatestSensorData
    ) -> None:
        """Publish the latest sensor measurements for a device."""
        sensor_data_payload = self._process_device_sensor_data(device_data)
        device_type = device_data.sensorType.name.replace(" ", "_").lower()
        device_unique_id = f"pulseapp_{device_type}_{device_id}"
        state_topic = f"pulseapp/{device_unique_id}/state"

        self.logger.info(f"🔄 Publishing state update to topic: {state_topic}")
        self._queue.mqtt_publish(
            topic=state_topic,
            payload=json.dumps(sensor_data_payload),
            retain=True,
        )

    def _process_device_sensor_data(
        self, device_data: LatestSensorData
    ) -> dict[str, Any]:
        """Return the measurements for a sensor as a state payload."""
        payload: dict[str, Any] = {}
        for measurement in device_data.dataPointDto.dataPointValues:
            param_name = measurement.ParamName.replace(" ", "_").lower()
            payload[param_name] = measurement.ParamValue
        return payload

    def _process_device_components(
        self, device_unique_id: str, latest: LatestSensorData
    ) -> tuple[dict[str, dict[str, Any]], int]:
        """Generate discovery components for a device."""
        components: dict[str, dict[str, Any]] = {}
        count = 0
        for measurement in latest.dataPointDto.dataPointValues:
            param_name = measurement.ParamName.replace(" ", "_").lower()
            comp_unique_id = f"{device_unique_id}_{param_name}"
            device_class_enum = DeviceClass.from_param_name(measurement.ParamName)
            components[comp_unique_id] = {
                "p": "sensor",
                "name": f"{measurement.ParamName}",
                "unique_id": comp_unique_id,
                "object_id": comp_unique_id,
                "unit_of_measurement": measurement.MeasuringUnit,
                "device_class": device_class_enum.value if device_class_enum else None,
                "stat_t": f"pulseapp/{device_unique_id}/state",
                "value_template": f"{{{{ value_json.{param_name} }}}}",
            }
            count += 1
        return components, count

    def _process_and_publish_devices(self, hub_unique_id: str, hub: HubDetails) -> int:
        """Process all devices attached to a hub."""
        discovered_sensor_count = 0
        if hub.sensorDevices:
            self.logger.info(
                f"🔍 Discovery: processing {len(hub.sensorDevices)} connected devices on {hub.id}..."
            )
        else:
            self.logger.info(
                f"🔍 Discovery: no devices found connected to this hub: {hub.id} "
            )

        for device in hub.sensorDevices:
            latest = self.get_sensor_latest_data(device.id)
            if latest is None:
                self.logger.warning(
                    f"🔍 Discovery: no data received for device {device.id}, skipping."
                )
                continue

            sensor_type_name = latest.sensorType.name.lower()
            device_unique_id = f"pulseapp_{sensor_type_name}_{device.id}"
            device_config_topic = f"homeassistant/device/{device_unique_id}/config"
            self.logger.info(
                f"🔍 Discovery: found device {device_unique_id}, processing its components"
            )

            components, count = self._process_device_components(
                device_unique_id, latest
            )
            discovered_sensor_count += count

            device_payload = {
                "o": MQTT_ORIGIN,
                "dev": {
                    "ids": device_unique_id,
                    "name": f"{latest.name}",
                    "mf": "Pulse Labs, Inc.",
                    "mdl": f"Pulse {latest.sensorType.name} Sensor",
                    "mdl_id": latest.sensorType.name,
                    "via_device": hub_unique_id,
                },
                "cmps": components,
            }

            self.logger.info(
                f"🔍 Discovery: publishing discovery message for {device_unique_id}: {device_config_topic}"
            )
            self._queue.mqtt_publish(
                topic=device_config_topic,
                payload=json.dumps(device_payload),
                retain=True,
            )

        return discovered_sensor_count

    def _process_and_publish_hubs(
        self, hub_ids: List[int]
    ) -> tuple[int, list[dict[str, Any]]]:
        """Process hubs, publish discovery, and return totals."""
        discovered_sensor_count = 0
        discovered_hubs: list[dict[str, Any]] = []
        for hub_id in hub_ids:
            hub = self.get_hub_details(hub_id)
            if hub is None:
                self.logger.warning(f"⚠️ No data found for hub {hub_id}, skipping.")
                continue

            self.logger.info(
                f"🔍 Discovery: Data found for hub {hub_id}, generating MQTT payload..."
            )

            hub_mac_address = ":".join(textwrap.wrap(hub.macAddress, 2))
            hub_unique_id = f"pulseapp_hub_{hub.id}"
            hub_payload = {
                "o": MQTT_ORIGIN,
                "dev": {
                    "ids": hub_unique_id,
                    "name": hub.name,
                    "mf": "Pulse Labs, Inc.",
                    "mdl": "Pulse Hub",
                    "mdl_id": "HUB",
                    "cns": [["mac", hub_mac_address]],
                },
                "cmps": {
                    f"{hub_unique_id}_void": {
                        "p": "binary_sensor",
                        "name": f"{hub.name} {hub.id}",
                        "unique_id": hub_unique_id,
                        "stat_t": f"pulseapp/{hub_unique_id}/state",
                    }
                },
            }
            hub_config_topic = f"homeassistant/device/{hub_unique_id}/config"

            self.logger.info(
                f"🔍 Discovery: Publishing discovery message for hub {hub_id}: {hub_config_topic}"
            )
            self._queue.mqtt_publish(
                topic=hub_config_topic,
                payload=json.dumps(hub_payload),
                retain=True,
            )

            discovered_sensor_count += self._process_and_publish_devices(
                hub_unique_id, hub
            )
            discovered_hubs.append(hub.model_dump())

        return discovered_sensor_count, discovered_hubs
