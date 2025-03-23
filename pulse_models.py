from datetime import datetime
from enum import IntEnum
from typing import Optional, List

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