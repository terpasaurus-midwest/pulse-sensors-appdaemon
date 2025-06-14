from __future__ import annotations
from datetime import datetime
from enum import IntEnum, Enum
from typing_extensions import override

from pydantic import BaseModel, Field


class DeviceType(IntEnum):
    """Pulse device types as defined in the Pulse API spec."""

    PULSE_ONE = 0  # Original Pulse One device
    PULSE_PRO = 1  # Pulse Pro device
    HUB = 2  # Pulse Hub device
    SENSOR = 3  # Standalone sensor (e.g., VWC, pH, EC, etc.)
    CONTROL = 4  # Some control device (unclear what this is)
    PULSE_ZERO = 5  # Possibly an older or experimental device?
    UNKNOWN = -1  # Fallback for unknown device types

    @override
    @classmethod
    def _missing_(cls, value: object):
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
    EC1 = 4  # Electrical Conductivity Sensor
    VWC12 = 5  # TEROS12 Retrofit Kit - Soil Moisture Sensor
    PAR1 = 8  # PAR (Light) Sensor
    VWC2 = 9  # Terralink (Pulse-vendored) - Soil Moisture Sensor
    ORP1 = 10  # ORP (Redox Potential) Sensor
    THC1 = 11  # CO₂, Temperature, Humidity, Lux Sensor (CO2-1)
    TDO1 = 12  # Dissolved Oxygen (DO) Sensor
    VWC3 = 13  # Possibly Terralink (Growlink-vendored/retrofit) - Soil Moisture Sensor
    UNKNOWN = -1  # Default fallback for unknown values

    @override
    @classmethod
    def _missing_(cls, value: object):
        """Handles unknown values by returning the UNKNOWN enum member."""
        return cls.UNKNOWN


class SensorReadingType(IntEnum):
    """Sensor reading types as defined in the Pulse API spec."""

    # Acclima (VWC1)
    VWC1_RH = 0
    VWC1_TEMPERATURE = 1
    VWC1_CONDUCTIVITY = 2
    VWC1_CONDUCTIVITY_PWE = 3

    # Growlink Terralink (VWC2)
    VWC2_RH = 4
    VWC2_TEMPERATURE = 5
    VWC2_CONDUCTIVITY = 6
    VWC2_CONDUCTIVITY_PWE = 7

    # TEROS 12 (VWC12)
    VWC12_RH = 8
    VWC12_TEMPERATURE = 9
    VWC12_CONDUCTIVITY = 10
    VWC12_CONDUCTIVITY_PWE = 11

    # General Readings
    PH = 12
    WATER_TEMPERATURE = 13
    VPD = 14
    DEW_POINT = 15
    AIR_TEMPERATURE = 16
    ORP = 17
    CO2 = 18
    DLI = 19
    PPFD = 20
    EC = 21
    THC1_LIGHT = 22  # Light Intensity Reading from THC1
    RH = 23
    ORIGINAL_DEVICES_LIGHT = 24  # Light Reading from Pulse Pro? Not sure.
    DO = 25  # Dissolved Oxygen (DO) Reading

    UNKNOWN = -1

    @override
    @classmethod
    def _missing_(cls, value: object):
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
    resolvedAt: datetime | None
    resolved: bool
    thresholdId: int
    thresholdType: ThresholdType | None
    deviceId: int
    deviceName: str
    lowOrHigh: bool
    lowThresholdValue: float
    highThresholdValue: float
    triggeringValue: str
    sensorThresholdType: SensorThresholdType | None
    hubThresholdType: HubThresholdType | None


class DataPointDto(BaseModel):
    dataPointValues: list[DataPointValue]
    triggeredThresholds: list[TriggeredThreshold] = Field(default_factory=list)
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
    lowThresholdValue: float | None
    highThresholdValue: float | None
    delay: str  # example: "00:03:00"
    day: str | None


class SensorDevice(BaseModel):
    hubId: int
    parSensorSubtype: str | None
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
    hubThresholds: list[HubThreshold]
    hidden: bool
    macAddress: str
    growId: int
    sensorDevices: list[SensorDevice]


class DeviceClass(Enum):
    """Enum to map Home Assistant device classes to sensor parameters.

    Sensor measurement parameter names from the Pulse API like "Water Content"
    are mapped to compatible Home Assistant device classes like "moisture",
    by using this enum's ``from_param_name`` method.
    """

    HUMIDITY = "humidity"
    TEMPERATURE = "temperature"
    MOISTURE = "moisture"
    PRESSURE = "pressure"

    @classmethod
    def from_param_name(cls, param_name: str) -> DeviceClass | None:
        mapping = {
            "Humidity": cls.HUMIDITY,
            "Temperature": cls.TEMPERATURE,
            "Water Content": cls.MOISTURE,
            "VPD": cls.PRESSURE,
        }
        return mapping.get(param_name)
