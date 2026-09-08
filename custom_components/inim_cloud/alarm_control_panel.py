"""Support for Inim Cloud Alarm Control Panels."""
import logging
from typing import Any, Dict, Optional

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_SCENARIO_AWAY,
    CONF_SCENARIO_DISARM,
    CONF_SCENARIO_HOME,
    CONF_SCENARIO_NIGHT,
    CONF_SCENARIO_VACATION,
    DOMAIN,
)
from .coordinator import InimDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Inim alarm control panel entities."""
    coordinator: InimDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    if coordinator.data:
        for device_id in coordinator.data:
            entities.append(InimAlarmControlPanel(coordinator, entry, device_id))

    async_add_entities(entities)


class InimAlarmControlPanel(CoordinatorEntity[InimDataUpdateCoordinator], AlarmControlPanelEntity):
    """Representation of an Inim Cloud alarm system."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: InimDataUpdateCoordinator,
        entry: ConfigEntry,
        device_id: int,
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self.device_id = device_id
        self._attr_unique_id = f"inim_alarm_panel_{device_id}"

    @property
    def _device(self) -> Dict[str, Any]:
        """Return the device data dictionary from coordinator."""
        if self.coordinator.data and self.device_id in self.coordinator.data:
            return self.coordinator.data[self.device_id]
        return {}

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device information for Home Assistant device registry."""
        dev = self._device
        return {
            "identifiers": {(DOMAIN, str(self.device_id))},
            "name": dev.get("name", f"Inim Alarm {self.device_id}"),
            "manufacturer": "Inim Electronics",
            "model": dev.get("model", "Inim SmartLiving / Prime"),
            "sw_version": dev.get("firmware"),
        }

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        """Return the list of supported alarm features based on mapped scenarios."""
        options = self.entry.options
        features = AlarmControlPanelEntityFeature(0)

        if options.get(CONF_SCENARIO_AWAY, -1) != -1:
            features |= AlarmControlPanelEntityFeature.ARM_AWAY
        if options.get(CONF_SCENARIO_HOME, -1) != -1:
            features |= AlarmControlPanelEntityFeature.ARM_HOME
        if options.get(CONF_SCENARIO_NIGHT, -1) != -1:
            features |= AlarmControlPanelEntityFeature.ARM_NIGHT
        if options.get(CONF_SCENARIO_VACATION, -1) != -1:
            features |= AlarmControlPanelEntityFeature.ARM_VACATION

        # If no custom options are configured yet, enable default features
        if features == AlarmControlPanelEntityFeature(0):
            features = (
                AlarmControlPanelEntityFeature.ARM_AWAY
                | AlarmControlPanelEntityFeature.ARM_HOME
            )

        return features

    @property
    def alarm_state(self) -> Optional[AlarmControlPanelState]:
        """Return the current alarm state."""
        dev = self._device
        active_sc = dev.get("active_scenario")
        options = self.entry.options

        # Check explicit option mappings
        if active_sc is not None:
            if active_sc == options.get(CONF_SCENARIO_DISARM):
                return AlarmControlPanelState.DISARMED
            if active_sc == options.get(CONF_SCENARIO_AWAY):
                return AlarmControlPanelState.ARMED_AWAY
            if active_sc == options.get(CONF_SCENARIO_HOME):
                return AlarmControlPanelState.ARMED_HOME
            if active_sc == options.get(CONF_SCENARIO_NIGHT):
                return AlarmControlPanelState.ARMED_NIGHT
            if active_sc == options.get(CONF_SCENARIO_VACATION):
                return AlarmControlPanelState.ARMED_VACATION

            # Fallback heuristic if not yet configured via Options Flow
            sc_info = dev.get("scenarios", {}).get(active_sc, {})
            sc_name = sc_info.get("name", "").lower()
            if any(w in sc_name for w in ["spento", "disarm", "off"]):
                return AlarmControlPanelState.DISARMED
            if any(w in sc_name for w in ["totale", "away"]):
                return AlarmControlPanelState.ARMED_AWAY
            if any(w in sc_name for w in ["home", "notte", "camere", "parziale"]):
                return AlarmControlPanelState.ARMED_HOME

            return AlarmControlPanelState.ARMED_CUSTOM_BYPASS

        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return device state attributes."""
        dev = self._device
        active_sc = dev.get("active_scenario")
        sc_info = dev.get("scenarios", {}).get(active_sc, {})
        return {
            "active_scenario_id": active_sc,
            "active_scenario_name": sc_info.get("name", dev.get("active_scenarios_str", "Unknown")),
            "voltage": dev.get("voltage"),
            "faults": dev.get("faults", 0),
            "serial_number": dev.get("serial_number"),
        }

    async def _async_set_scenario(self, scenario_id: int) -> None:
        """Helper to send scenario activation and refresh state."""
        _LOGGER.info("Activating scenario %s on device %s", scenario_id, self.device_id)
        success = await self.coordinator.client.async_activate_scenario(
            self.device_id, scenario_id
        )
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to activate scenario %s", scenario_id)

    async def async_alarm_disarm(self, code: Optional[str] = None) -> None:
        """Send disarm command."""
        sc_id = self.entry.options.get(CONF_SCENARIO_DISARM)
        if sc_id is not None and sc_id != -1:
            await self._async_set_scenario(sc_id)
        else:
            # Fallback heuristic
            dev = self._device
            for s_id, s_data in dev.get("scenarios", {}).items():
                if any(w in s_data.get("name", "").lower() for w in ["spento", "disarm", "off"]):
                    await self._async_set_scenario(s_id)
                    return
            _LOGGER.warning("No disarm scenario mapped in Options Flow.")

    async def async_alarm_arm_away(self, code: Optional[str] = None) -> None:
        """Send arm away command."""
        sc_id = self.entry.options.get(CONF_SCENARIO_AWAY)
        if sc_id is not None and sc_id != -1:
            await self._async_set_scenario(sc_id)
        else:
            dev = self._device
            for s_id, s_data in dev.get("scenarios", {}).items():
                if any(w in s_data.get("name", "").lower() for w in ["totale", "away"]):
                    await self._async_set_scenario(s_id)
                    return
            _LOGGER.warning("No arm away scenario mapped in Options Flow.")

    async def async_alarm_arm_home(self, code: Optional[str] = None) -> None:
        """Send arm home command."""
        sc_id = self.entry.options.get(CONF_SCENARIO_HOME)
        if sc_id is not None and sc_id != -1:
            await self._async_set_scenario(sc_id)
        else:
            dev = self._device
            for s_id, s_data in dev.get("scenarios", {}).items():
                if any(w in s_data.get("name", "").lower() for w in ["home", "notte", "camere"]):
                    await self._async_set_scenario(s_id)
                    return
            _LOGGER.warning("No arm home scenario mapped in Options Flow.")

    async def async_alarm_arm_night(self, code: Optional[str] = None) -> None:
        """Send arm night command."""
        sc_id = self.entry.options.get(CONF_SCENARIO_NIGHT)
        if sc_id is not None and sc_id != -1:
            await self._async_set_scenario(sc_id)

    async def async_alarm_arm_vacation(self, code: Optional[str] = None) -> None:
        """Send arm vacation command."""
        sc_id = self.entry.options.get(CONF_SCENARIO_VACATION)
        if sc_id is not None and sc_id != -1:
            await self._async_set_scenario(sc_id)
