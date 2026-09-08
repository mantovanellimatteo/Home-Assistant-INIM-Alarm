"""Button platform for direct one-click Inim scenario activation."""
import logging
from typing import Any, Dict

from homeassistant.components.button import ButtonEntity
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
    """Set up Inim scenario button entities."""
    coordinator: InimDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    if coordinator.data:
        for device_id, dev in coordinator.data.items():
            scenarios = dev.get("scenarios", {})
            for sc_id, sc in scenarios.items():
                entities.append(
                    InimScenarioButton(coordinator, device_id, sc_id, sc["name"])
                )

    async_add_entities(entities)


class InimScenarioButton(CoordinatorEntity[InimDataUpdateCoordinator], ButtonEntity):
    """Button entity to activate a specific Inim scenario directly."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: InimDataUpdateCoordinator,
        device_id: int,
        scenario_id: int,
        scenario_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.device_id = device_id
        self.scenario_id = scenario_id
        self._attr_name = scenario_name
        self._attr_unique_id = f"inim_scenario_btn_{device_id}_{scenario_id}"

        # Assign intuitive icons based on scenario name
        lower_name = scenario_name.lower()
        if any(w in lower_name for w in ["spento", "disarm", "off"]):
            self._attr_icon = "mdi:shield-off"
        elif any(w in lower_name for w in ["totale", "away"]):
            self._attr_icon = "mdi:shield-lock"
        elif any(w in lower_name for w in ["home", "notte", "camere", "parziale"]):
            self._attr_icon = "mdi:shield-home"
        else:
            self._attr_icon = "mdi:shield-check"

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

    async def async_press(self) -> None:
        """Handle the button press to activate this specific scenario."""
        _LOGGER.info(
            "Button pressed: activating scenario %s (ID: %s) on device %s",
            self._attr_name,
            self.scenario_id,
            self.device_id,
        )
        success = await self.coordinator.client.async_activate_scenario(
            self.device_id, self.scenario_id
        )
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to activate scenario %s", self._attr_name)
