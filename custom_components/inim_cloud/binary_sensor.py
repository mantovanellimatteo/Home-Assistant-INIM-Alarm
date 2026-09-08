"""Binary sensor platform for Inim Cloud zones and system diagnostics."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import InimDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Inim binary sensors for zones and faults."""
    coordinator: InimDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    if coordinator.data:
        for device_id, dev in coordinator.data.items():
            # Add central trouble / problem binary sensor
            entities.append(InimCentralProblemSensor(coordinator, device_id))

            # Add zone sensors if zones are returned by the cloud
            zones = dev.get("zones", {})
            for zone_id in zones:
                entities.append(InimZoneBinarySensor(coordinator, device_id, zone_id))

    async_add_entities(entities)


class InimCentralProblemSensor(CoordinatorEntity[InimDataUpdateCoordinator], BinarySensorEntity):
    """Reports overall trouble/fault status on the Inim central."""

    _attr_has_entity_name = True
    _attr_name = "Problema Centrale"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        coordinator: InimDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"inim_fault_sensor_{device_id}"

    @property
    def _device(self) -> Dict[str, Any]:
        return self.coordinator.data.get(self.device_id, {})

    @property
    def device_info(self) -> Dict[str, Any]:
        dev = self._device
        return {
            "identifiers": {(DOMAIN, str(self.device_id))},
            "name": dev.get("name", f"Inim Alarm {self.device_id}"),
            "manufacturer": "Inim Electronics",
            "model": dev.get("model", "Inim SmartLiving / Prime"),
            "sw_version": dev.get("firmware"),
        }

    @property
    def is_on(self) -> bool:
        """Return True if the central has active faults."""
        return self._device.get("faults", 0) > 0

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        return {
            "fault_count": self._device.get("faults", 0),
            "voltage": self._device.get("voltage"),
        }


class InimZoneBinarySensor(CoordinatorEntity[InimDataUpdateCoordinator], BinarySensorEntity):
    """Representation of an individual Inim alarm zone/sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: InimDataUpdateCoordinator,
        device_id: int,
        zone_id: int,
    ) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self.zone_id = zone_id
        self._attr_unique_id = f"inim_zone_{device_id}_{zone_id}"

    @property
    def _zone(self) -> Dict[str, Any]:
        dev = self.coordinator.data.get(self.device_id, {})
        return dev.get("zones", {}).get(self.zone_id, {})

    @property
    def device_info(self) -> Dict[str, Any]:
        dev = self.coordinator.data.get(self.device_id, {})
        return {
            "identifiers": {(DOMAIN, str(self.device_id))},
            "name": dev.get("name", f"Inim Alarm {self.device_id}"),
            "manufacturer": "Inim Electronics",
            "model": dev.get("model", "Inim SmartLiving / Prime"),
            "sw_version": dev.get("firmware"),
        }

    @property
    def name(self) -> Optional[str]:
        """Return zone label."""
        return self._zone.get("name", f"Zona {self.zone_id}")

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Infer device class from zone name."""
        name = self.name.lower() if self.name else ""
        if any(w in name for w in ["porta", "portoncino", "ingresso", "portone"]):
            return BinarySensorDeviceClass.DOOR
        if any(w in name for w in ["finestra", "velux", "balcone"]):
            return BinarySensorDeviceClass.WINDOW
        if any(w in name for w in ["pir", "radar", "movimento", "volumetrico"]):
            return BinarySensorDeviceClass.MOTION
        if any(w in name for w in ["fumo", "antincendio"]):
            return BinarySensorDeviceClass.SMOKE
        return BinarySensorDeviceClass.OPENING

    @property
    def is_on(self) -> bool:
        """Return True if zone is open or in alarm."""
        zone = self._zone
        return bool(zone.get("open") or zone.get("alarm"))

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        zone = self._zone
        return {
            "zone_id": self.zone_id,
            "alarm": zone.get("alarm", False),
            "open": zone.get("open", False),
            "tamper": zone.get("tamper", False),
            "fault": zone.get("fault", False),
        }
