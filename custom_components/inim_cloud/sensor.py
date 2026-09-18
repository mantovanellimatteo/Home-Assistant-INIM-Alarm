"""Sensor platform for Inim Cloud event tracking and system diagnostics."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential
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
    """Set up Inim sensor entities."""
    coordinator: InimDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    if coordinator.data:
        for device_id in coordinator.data:
            entities.append(InimLastEventSensor(coordinator, device_id))
            entities.append(InimVoltageSensor(coordinator, device_id))

    async_add_entities(entities)


class InimLastEventSensor(CoordinatorEntity[InimDataUpdateCoordinator], SensorEntity):
    """Sensor displaying the most recent event or notification received from the panel."""

    _attr_has_entity_name = True
    _attr_name = "Ultimo Evento"
    _attr_icon = "mdi:bell-ring-outline"

    def __init__(
        self,
        coordinator: InimDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"inim_last_event_{device_id}"

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
    def native_value(self) -> str:
        """Return the description of the last event."""
        last_evt = self._device.get("last_event")
        if last_evt and isinstance(last_evt, dict):
            return str(last_evt.get("info", "Evento sconosciuto"))
        return "Nessun evento registrato"

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return detailed metadata about the last event."""
        last_evt = self._device.get("last_event")
        if last_evt and isinstance(last_evt, dict):
            return {
                "category": last_evt.get("category"),
                "event_type": last_evt.get("type"),
                "is_restore": last_evt.get("is_restore"),
                "event_id": last_evt.get("event_id"),
                "timestamp": last_evt.get("timestamp"),
                "raw_data": last_evt.get("raw_data"),
            }
        return {}


class InimVoltageSensor(CoordinatorEntity[InimDataUpdateCoordinator], SensorEntity):
    """Sensor monitoring the main power supply and backup battery voltage."""

    _attr_has_entity_name = True
    _attr_name = "Tensione Alimentazione"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(
        self,
        coordinator: InimDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"inim_voltage_{device_id}"

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
    def native_value(self) -> Optional[float]:
        """Return the voltage measurement rounded to 2 decimal places."""
        v = self._device.get("voltage")
        if v is not None:
            try:
                return round(float(v), 2)
            except (ValueError, TypeError):
                return None
        return None
