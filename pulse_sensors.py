from datetime import datetime
from enum import IntEnum
from typing import Any, List, Optional, Union
import base64
import json
import requests

from pydantic import BaseModel, Field, ValidationError
import hassapi as hass

PULSE_API_KEY_ENTITY = "input_text.pulse_api_key"
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
    VWC1_CONDUCTIVITY = 2  # VWC1 - Bulk EC Reading
    VWC1_CONDUCTIVITY_PWE = 3  # VWC1 - Pore Water EC Reading

    # Growlink Terralink (VWC2)
    VWC2_RH = 4  # VWC2 - Relative Humidity Reading
    VWC2_TEMPERATURE = 5  # VWC2 - Temperature Reading
    VWC2_CONDUCTIVITY = 6  # VWC2 - Bulk EC Reading
    VWC2_CONDUCTIVITY_PWE = 7  # VWC2 - Pore Water EC Reading

    # TEROS 12 (VWC12)
    VWC12_RH = 8  # VWC12 - Relative Humidity Reading
    VWC12_TEMPERATURE = 9  # VWC12 - Temperature Reading
    VWC12_CONDUCTIVITY = 10  # VWC12 - Bulk EC Reading
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


class ThresholdType(IntEnum):
    LIGHT = 1
    TEMPERATURE = 2
    HUMIDITY = 3
    POWER = 4
    CONNECTIVITY = 5
    BATTERY_V = 6
    CO2 = 7
    VOC = 8
    VPD = 11
    DEW_POINT = 12


class SensorThresholdType(IntEnum):
    VWC1 = 1
    TEMPERATURE = 2
    HUMIDITY = 3
    VPD = 4
    DEW_POINT = 5
    PH = 6
    EC1_EC = 7
    EC1_TEMP = 8
    VWC1_PWEC = 9
    VWC12_VWC = 10
    VWC12_PWEC = 11
    PAR1_PPFD = 12
    SUBSTRATE_TEMP = 13
    SUBSTRATE_BULK_EC = 14
    PH1_TEMP = 15
    PAR1_DLI = 16
    VWC2_VWC = 17
    VWC2_PWEC = 18
    ORP1_ORP = 19
    THC1_CO2 = 20
    THC1_RH = 21
    THC1_TEMP = 22
    THC1_DEW_POINT = 23
    THC1_VPD = 24
    TDO1_TEMP = 25
    TDO1_DO = 26
    THC1_LIGHT = 27


class HubThresholdType(IntEnum):
    POWER = 1
    CONNECTIVITY = 2


class DataPointValue(BaseModel):
    MeasuringUnit: str
    ParamName: str
    ParamValue: float


class TriggeredThreshold(BaseModel):
    id: int
    createdAt: datetime
    resolvedAt: Optional[datetime]
    resolved: bool
    thresholdId: int
    thresholdType: Optional[ThresholdType]
    deviceId: int
    deviceName: str
    lowOrHigh: bool
    lowThresholdValue: float
    highThresholdValue: float
    triggeringValue: str
    sensorThresholdType: Optional[SensorThresholdType]
    hubThresholdType: Optional[HubThresholdType]


class DataPointDto(BaseModel):
    dataPointValues: List[DataPointValue]
    triggeredThresholds: List[TriggeredThreshold] = Field(default_factory=list)
    sensorId: int
    createdAt: datetime


class LatestSensorData(BaseModel):
    sensorType: SensorType
    deviceType: int
    name: str
    dataPointDto: DataPointDto


class HubThreshold(BaseModel):
    hubId: int
    thresholdType: HubThresholdType
    id: int
    notificationActive: bool
    lowThresholdValue: Optional[float]
    highThresholdValue: Optional[float]
    delay: str  # example: "00:03:00"
    day: Optional[str]  # sometimes null


class SensorDevice(BaseModel):
    hubId: int
    parSensorSubtype: Optional[str]
    deviceType: int
    sensorType: int
    id: int
    displayOrder: int
    name: str
    growId: int
    hidden: bool


class HubDetails(BaseModel):
    id: int
    name: str
    hubThresholds: List[HubThreshold]
    hidden: bool
    macAddress: str
    growId: int
    sensorDevices: List[SensorDevice]


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

    def make_request(self, endpoint: str, method: str = "GET", **kwargs) -> Union[dict[str, Any], list[Any], None]:
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
