"""Support for selecting any Inim Cloud scenario directly."""
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.select import SelectEntity
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
    """Set up Inim scenario select entities."""
    coordinator: InimDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    if coordinator.data:
        for device_id in coordinator.data:
            entities.append(InimScenarioSelect(coordinator, device_id))

    async_add_entities(entities)


class InimScenarioSelect(CoordinatorEntity[InimDataUpdateCoordinator], SelectEntity):
    """Dropdown entity exposing all native scenarios defined in the Inim central."""

    _attr_has_entity_name = True
    _attr_name = "Scenario"
    _attr_icon = "mdi:shield-sync"

    def __init__(
        self,
        coordinator: InimDataUpdateCoordinator,
        device_id: int,
    ) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self._attr_unique_id = f"inim_scenario_select_{device_id}"

    @property
    def _device(self) -> Dict[str, Any]:
        """Return the device data dictionary from coordinator."""
        if self.coordinator.data and self.device_id in self.coordinator.data:
            return self.coordinator.data[self.device_id]
        return {}

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device registry info."""
        dev = self._device
        return {
            "identifiers": {(DOMAIN, str(self.device_id))},
            "name": dev.get("name", f"Inim Alarm {self.device_id}"),
            "manufacturer": "Inim Electronics",
            "model": dev.get("model", "Inim SmartLiving / Prime"),
            "sw_version": dev.get("firmware"),
        }

    @property
    def options(self) -> List[str]:
        """Return list of all available scenario names."""
        scenarios = self._device.get("scenarios", {})
        return [sc["name"] for sc in scenarios.values()]

    @property
    def current_option(self) -> Optional[str]:
        """Return currently active scenario name."""
        dev = self._device
        active_sc = dev.get("active_scenario")
        if active_sc is not None:
            sc_info = dev.get("scenarios", {}).get(active_sc)
            if sc_info:
                return sc_info.get("name")
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the active scenario."""
        scenarios = self._device.get("scenarios", {})
        target_id = None
        for sc_id, sc in scenarios.items():
            if sc.get("name") == option:
                target_id = sc_id
                break

        if target_id is not None:
            _LOGGER.info("Selecting scenario %s (ID: %s) on device %s", option, target_id, self.device_id)
            success = await self.coordinator.client.async_activate_scenario(
                self.device_id, target_id
            )
            if success:
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error("Failed to set scenario %s", option)
        else:
            _LOGGER.warning("Selected scenario option '%s' not found in available scenarios", option)
