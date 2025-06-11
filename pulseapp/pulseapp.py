from typing import Any
import json

import requests
import textwrap

from pydantic import ValidationError
from appdaemon import adbase as ad
from appdaemon import AppDaemon, ADAPI
from appdaemon.models.config.app import AppConfig

from .models import HubDetails, LatestSensorData, DeviceClass

__version__ = "1.0.1"

PULSE_API_KEY_ENTITY = "input_text.pulse_api_key"
PULSE_API_BASE = "https://api.pulsegrow.com"
API_TIMEOUT = 10.0
SENSOR_UPDATE_INTERVAL = 60.0  # 1 minute
SENSOR_DISCOVERY_INTERVAL = 3600.0  # 1 hour

# This is added to device discovery messages so, Home
# Assistant logs have context about the source of MQTT messages.
MQTT_ORIGIN = {
    "name": "Pulse Sensors AppDaemon",
    "sw_version": str(__version__),
    "support_url": "https://github.com/terpasaurus-midwest/pulse-sensors-appdaemon",
}


class PulseApp(ad.ADBase):
    def __init__(self, ad: "AppDaemon", config_model: "AppConfig"):
        self._adapi: ADAPI | None
        self._hass: ADAPI | None
        self._queue: ADAPI | None
        self._session: requests.Session | None = None
        self.state_update_job: str | None = None
        self.discovery_job: str | None = None
        super().__init__(ad, config_model)

    def _ensure_plugins_loaded(self):
        required_plugins = [
            ("HASS", self._hass),
            ("MQTT", self._queue),
        ]
        for name, plugin in required_plugins:
            if plugin is None:
                raise RuntimeError(f"❌ Required AppDaemon plugin missing: {name}")

    def _init_required_apis(self):
        self._adapi = self.get_ad_api()
        self._hass = self.get_plugin_api("HASS")
        self._queue = self.get_plugin_api("MQTT")
        self._ensure_plugins_loaded()
        self._init_pulse_api()

    def _init_pulse_api(self):
        api_key = self._hass.get_state(PULSE_API_KEY_ENTITY)
        if not api_key:
            self.logger.error(f"🛑 Pulse API key not found at {PULSE_API_KEY_ENTITY}")
            raise RuntimeError(f"Pulse API key not found at: {PULSE_API_KEY_ENTITY}")
        self._session = requests.Session()
        self._session.headers["x-api-key"] = str(api_key)
        self.logger.info("🔗 Created persistent Pulse API session.")

    def _get_update_intervals(self):
        state_update_interval = int(
            float(
                str(self._hass.get_state("input_number.sensor_update_interval"))
                or SENSOR_UPDATE_INTERVAL
            )
        )
        discovery_interval = int(
            float(
                str(self._hass.get_state("input_number.sensor_discovery_interval"))
                or SENSOR_DISCOVERY_INTERVAL
            )
        )
        return state_update_interval, discovery_interval

    def _register_scheduled_ad_jobs(self):
        state_update_interval, discovery_interval = self._get_update_intervals()
        self.state_update_job = self._adapi.run_every(
            self.update_sensor_states,
            "now",
            state_update_interval,
        )
        self.logger.info(
            f"⏱️ Registered sensor state update job: "
            + f"{self.state_update_job} ({state_update_interval} sec)"
        )

        self.discovery_job = self._adapi.run_every(
            self.discover_hub_sensors,
            "now",
            discovery_interval,
        )
        self.logger.info(
            f"⏱️ Registered hub sensor discovery job: "
            + f"{self.discovery_job} ({discovery_interval} sec)"
        )

    def _register_update_interval_listeners(self):
        _ = self._adapi.listen_state(
            self.update_intervals, "input_number.sensor_update_interval"
        )
        _ = self._adapi.listen_state(
            self.update_intervals, "input_number.sensor_discovery_interval"
        )

    def initialize(self):
        """Initialize API sessions and register scheduled jobs and listeners.

        An initial discovery job will be launched 10 seconds after initialization.
        """
        self._init_required_apis()
        self._register_scheduled_ad_jobs()
        self._register_update_interval_listeners()
        _ = self._adapi.run_in(self.discover_hub_sensors, 10)

    def terminate(self):
        """Close the session when the AppDaemon context is terminated."""
        if hasattr(self, "_session"):
            self._session.close()
            self.logger.info("🛑 Closed Pulse API session.")

        self.logger.info("🛑 Pulse Sensor app terminated.")

    def update_intervals(
        self, entity: str, attribute: str, old: Any, new: Any, **kwargs: Any
    ) -> None:
        """Reconfigure intervals when input_number changes."""
        new_interval = int(float(new))

        if entity == "input_number.sensor_update_interval":
            if self.state_update_job:
                _ = self._adapi.cancel_timer(self.state_update_job)
            self.state_update_job = self._adapi.run_every(
                self.update_sensor_states,
                "now",
                new_interval,
            )
            self.logger.info(
                f"📝️ Updated sensor state update interval to {new_interval} sec"
            )

        elif entity == "input_number.sensor_discovery_interval":
            if self.discovery_job:
                _ = self._adapi.cancel_timer(self.discovery_job)
            self.discovery_job = self._adapi.run_every(
                self.discover_hub_sensors,
                "now",
                new_interval,
            )
            self.logger.info(
                f"📝️ Updated hub sensor discovery interval to {new_interval} sec"
            )

    def _make_pulse_api_request(
        self, endpoint: str, method: str = "GET", **kwargs: Any
    ) -> dict[str, Any] | list[Any] | None:
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

    def get_hub_ids(self) -> list[int] | None:
        """Fetch all hub IDs."""
        self.logger.info(f"📡 Fetching hub IDs")
        hub_ids = self._make_pulse_api_request("/hubs/ids")
        if not hub_ids or not isinstance(hub_ids, list):
            self.logger.warning("❌ No hubs returned by the Pulse API")
            return []
        return hub_ids

    def get_hub_details(self, hub_id: int) -> HubDetails | None:
        """Fetch and validate hub details and attached sensor devices."""
        url = f"/hubs/{hub_id}"
        self.logger.info(f"📡 Fetching hub details for {hub_id} at: {url}")

        response = self._make_pulse_api_request(url)
        if not response:
            self.logger.warning(f"⚠️ No data received for hub {hub_id}")
            return None

        try:
            return HubDetails(**response)  # pyright: ignore [reportCallIssue]
        except ValidationError:
            self.logger.exception(f"❌ Validation error for hub {hub_id}")
            return None

    def get_sensor_latest_data(self, sensor_id: int) -> LatestSensorData | None:
        """Fetch and validate the latest measurements for a sensor.

        :param sensor_id: The ID of the sensor to fetch.
        :return: A validated LatestSensorData object if successful, or None if request or validation fails.
        """
        url = f"/sensors/{sensor_id}/recent-data"
        self.logger.info(
            f"📡 Fetching latest sensor measurements for {sensor_id}: {url}"
        )

        response = self._make_pulse_api_request(url)
        if not response:
            self.logger.warning(f"⚠️ No data received from sensor {sensor_id}")
            return None

        try:
            return LatestSensorData(**response)  # pyright: ignore [reportCallIssue]
        except ValidationError:
            self.logger.exception(f"❌ Validation error for sensor {sensor_id}")
            return None

    def discover_hub_sensors(self, **kwargs: Any):  # pyright: ignore [reportUnusedParameter]
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

        _ = self._hass.set_state(
            "sensor.pulseapp_discovered_hubs",
            state=len(discovered_hubs),
            attributes={"hubs": discovered_hubs},
        )
        _ = self._hass.set_state(
            "sensor.pulseapp_discovered_sensors", state=discovered_sensor_count
        )
        self.logger.info(
            f"✅ Discovered {discovered_sensor_count} sensors across {len(discovered_hubs)} hubs."
        )

    def update_sensor_states(self, **kwargs: Any):  # pyright: ignore [reportUnusedParameter]
        """Publish the latest data points for each connected hub and sensor device."""
        discovered_hubs = self._hass.get_state(
            "sensor.pulseapp_discovered_hubs",
            attribute="hubs",
        )

        if not discovered_hubs or isinstance(discovered_hubs, dict):
            self.logger.warning("⚠️ No sensors discovered yet, skipping update.")
            return

        for hub in discovered_hubs:
            self._publish_hub_state(hub)

            for device in hub["sensorDevices"]:
                device_data = self.get_sensor_latest_data(device["id"])
                if device_data is None:
                    continue
                self._publish_device_state(device["id"], device_data)

    def _publish_hub_state(self, hub: dict[str, Any]) -> None:
        """Publish the hub state and update all attached devices."""
        hub_unique_id = f"pulseapp_hub_{hub['id']}"
        self._queue.mqtt_publish(  # pyright: ignore [reportAttributeAccessIssue]
            topic=f"pulseapp/{hub_unique_id}/state",
            payload="ON",
            retain=True,
        )

    def _publish_device_state(
        self, device_id: int, device_data: LatestSensorData
    ) -> None:
        """Publish the latest sensor measurements for a device."""
        sensor_data_payload = self._generate_sensor_payload(device_data)
        device_type = str(device_data.sensorType.name).replace(" ", "_").lower()
        device_unique_id = f"pulseapp_{device_type}_{device_id}"
        state_topic = f"pulseapp/{device_unique_id}/state"

        self.logger.info(f"🔄 Publishing state update to topic: {state_topic}")
        self._queue.mqtt_publish(  # pyright: ignore [reportAttributeAccessIssue]
            topic=state_topic,
            payload=json.dumps(sensor_data_payload),
            retain=True,
        )

    @staticmethod
    def _generate_sensor_payload(device_data: LatestSensorData) -> dict[str, Any]:
        """Return the measurements for a sensor as a state payload."""
        payload: dict[str, Any] = {}
        for measurement in device_data.dataPointDto.dataPointValues:
            param_name = measurement.ParamName.replace(" ", "_").lower()
            payload[param_name] = measurement.ParamValue
        return payload

    @staticmethod
    def _process_device_components(
        device_unique_id: str, device_data: LatestSensorData
    ) -> dict[str, dict[str, Any]]:
        """Generate discovery components for a device."""
        components: dict[str, dict[str, Any]] = {}
        for measurement in device_data.dataPointDto.dataPointValues:
            param_name = measurement.ParamName.replace(" ", "_").lower()
            comp_unique_id = f"{device_unique_id}_{param_name}"
            device_class_enum = DeviceClass.from_param_name(measurement.ParamName)
            components[comp_unique_id] = {
                "platform": "sensor",
                "name": f"{measurement.ParamName}",
                "unique_id": comp_unique_id,
                "object_id": comp_unique_id,
                "unit_of_measurement": measurement.MeasuringUnit,
                "device_class": device_class_enum.value if device_class_enum else None,
                "state_topic": f"pulseapp/{device_unique_id}/state",
                "value_template": f"{{{{ value_json.{param_name} }}}}",
            }
        return components

    def _process_and_publish_devices(self, hub_unique_id: str, hub: HubDetails) -> int:
        """Process all devices attached to a hub."""
        if hub.sensorDevices:
            self.logger.info(
                f"🔍 Discovery: processing {len(hub.sensorDevices)} connected devices on {hub.id}..."
            )
        else:
            self.logger.info(
                f"🔍 Discovery: no devices found connected to this hub: {hub.id} "
            )

        discovered_sensor_count = 0
        for device in hub.sensorDevices:
            device_data = self.get_sensor_latest_data(device.id)
            if device_data is None:
                self.logger.warning(
                    f"🔍 Discovery: no data received for device {device.id}, skipping."
                )
                continue

            device_type = device_data.sensorType.name.lower()
            device_unique_id = f"pulseapp_{device_type}_{device.id}"
            device_config_topic = f"homeassistant/device/{device_unique_id}/config"
            self.logger.info(
                f"🔍 Discovery: found device {device_unique_id}, processing its components"
            )

            components = self._process_device_components(device_unique_id, device_data)
            discovered_sensor_count = len(components)

            device_payload = {
                "origin": MQTT_ORIGIN,
                "device": {
                    "identifiers": device_unique_id,
                    "name": f"{device_data.name}",
                    "manufacturer": "Pulse Labs, Inc.",
                    "model": f"Pulse {device_data.sensorType.name} Sensor",
                    "model_id": device_data.sensorType.name,
                    "via_device": hub_unique_id,
                },
                "components": components,
            }

            self.logger.info(
                f"🔍 Discovery: publishing discovery message for {device_unique_id}: {device_config_topic}"
            )
            self._queue.mqtt_publish(  # pyright: ignore [reportAttributeAccessIssue]
                topic=device_config_topic,
                payload=json.dumps(device_payload),
                retain=True,
            )

        return discovered_sensor_count

    def _process_and_publish_hubs(
        self, hub_ids: list[int]
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
                "origin": MQTT_ORIGIN,
                "device": {
                    "identifiers": hub_unique_id,
                    "name": hub.name,
                    "manufacturer": "Pulse Labs, Inc.",
                    "model": "Pulse Hub",
                    "model_id": "Hub",
                    "connections": [["mac", hub_mac_address]],
                },
                "components": {
                    f"{hub_unique_id}_void": {
                        "platform": "binary_sensor",
                        "name": f"{hub.name} {hub.id}",
                        "unique_id": hub_unique_id,
                        "state_topic": f"pulseapp/{hub_unique_id}/state",
                    }
                },
            }
            hub_config_topic = f"homeassistant/device/{hub_unique_id}/config"

            self.logger.info(
                f"🔍 Discovery: Publishing discovery message for hub {hub_id}: {hub_config_topic}"
            )
            self._queue.mqtt_publish(  # pyright: ignore [reportAttributeAccessIssue]
                topic=hub_config_topic,
                payload=json.dumps(hub_payload),
                retain=True,
            )

            discovered_sensor_count += self._process_and_publish_devices(
                hub_unique_id, hub
            )
            discovered_hubs.append(hub.model_dump())

        return discovered_sensor_count, discovered_hubs
