"""DataUpdateCoordinator for Inim Cloud integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, EVENT_INIM_CLOUD
from .inim_api import InimApiClient, InimApiError

_LOGGER = logging.getLogger(__name__)


class InimDataUpdateCoordinator(DataUpdateCoordinator[Dict[int, Dict[str, Any]]]):
    """Coordinator to manage fetching data from Inim Cloud and listening to real-time events."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: InimApiClient,
        entry_id: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.entry_id = entry_id
        self._is_running = True
        self._ws_task: Optional[asyncio.Task] = None
        self.last_events: Dict[int, Dict[str, Any]] = {}

    async def _async_update_data(self) -> Dict[int, Dict[str, Any]]:
        """Fetch all devices, scenarios, and zone states from Inim Cloud."""
        try:
            raw_response = await self.client.async_get_devices()
            devices_data = raw_response.get("Data", {})

            parsed_devices: Dict[int, Dict[str, Any]] = {}

            for dev_key, dev_info in devices_data.items():
                if not dev_key.isdigit():
                    continue

                dev_id = int(dev_key)
                # Map scenarios
                scenarios = {}
                for sc in dev_info.get("Scenarios", []):
                    sc_id = sc.get("ScenarioId")
                    if sc_id is not None:
                        scenarios[sc_id] = {
                            "id": sc_id,
                            "name": sc.get("Name", f"Scenario {sc_id}"),
                            "area_mask": sc.get("AreaMask"),
                            "area_set": sc.get("AreaSet"),
                        }

                # Map zones (if available in payload)
                zones = {}
                for z in dev_info.get("Zones", []):
                    z_id = z.get("ZoneId") or z.get("Id")
                    if z_id is not None:
                        zones[z_id] = {
                            "id": z_id,
                            "name": z.get("Name", f"Zone {z_id}"),
                            "alarm": bool(z.get("Alarm", 0)),
                            "open": bool(z.get("Open", 0)),
                            "tamper": bool(z.get("Tamper", 0)),
                            "fault": bool(z.get("Fault", 0)),
                            "type": z.get("Type"),
                        }

                # Map areas
                areas = {}
                for a in dev_info.get("Areas", []):
                    a_id = a.get("AreaId") or a.get("Id")
                    if a_id is not None:
                        areas[a_id] = {
                            "id": a_id,
                            "name": a.get("Name", f"Area {a_id}"),
                            "status": a.get("Status"),
                        }

                parsed_devices[dev_id] = {
                    "id": dev_id,
                    "name": dev_info.get("Name", f"Inim Central {dev_id}"),
                    "serial_number": dev_info.get("SerialNumber", str(dev_id)),
                    "model": f"{dev_info.get('ModelFamily', '')} {dev_info.get('ModelNumber', '')}".strip() or "Inim Alarm",
                    "firmware": f"{dev_info.get('FirmwareVersionMajor', '')}.{dev_info.get('FirmwareVersionMinor', '')}".strip("."),
                    "active_scenario": dev_info.get("ActiveScenario"),
                    "active_scenarios_str": dev_info.get("ActiveScenarios", ""),
                    "voltage": dev_info.get("Voltage"),
                    "faults": dev_info.get("Faults", 0),
                    "network_status": dev_info.get("NetworkStatus"),
                    "scenarios": scenarios,
                    "zones": zones,
                    "areas": areas,
                    "last_event": self.last_events.get(dev_id),
                }

            return parsed_devices

        except InimApiError as err:
            raise UpdateFailed(f"Error communicating with Inim Cloud: {err}") from err

    async def async_start_websocket(self) -> None:
        """Start the background WebSocket push listener."""
        if self._ws_task and not self._ws_task.done():
            return

        self._is_running = True

        async def _on_event(event_data: Dict[str, Any]) -> None:
            """Handle an incoming real-time push event."""
            _LOGGER.debug("Handling real-time push event: %s", event_data)

            if isinstance(event_data, dict):
                data_block = event_data.get("Data")
                if isinstance(data_block, dict):
                    dev_id = (
                        data_block.get("Device_Id")
                        or data_block.get("DeviceId")
                        or (next(iter(self.data.keys())) if self.data else None)
                    )

                    dev_name = (
                        self.data.get(dev_id, {}).get("name", f"Inim Central {dev_id}")
                        if (self.data and dev_id in self.data)
                        else f"Inim Central {dev_id}"
                    )

                    info = (
                        data_block.get("Info")
                        or data_block.get("Data")
                        or event_data.get("Type", "Evento Centrale")
                    )
                    category = data_block.get("Category", "System")
                    event_type = data_block.get("Type", event_data.get("Type", ""))
                    is_restore = bool(data_block.get("IsRestore", False))
                    event_id = data_block.get("DeviceEvent_Id")

                    event_payload = {
                        "device_id": dev_id,
                        "device_name": dev_name,
                        "info": str(info),
                        "category": str(category),
                        "type": str(event_type),
                        "is_restore": is_restore,
                        "event_id": event_id,
                        "raw_data": str(data_block.get("Data", "")),
                        "timestamp": dt_util.now().isoformat(),
                    }

                    if dev_id is not None:
                        self.last_events[dev_id] = event_payload

                    # Fire native Home Assistant event on the event bus
                    self.hass.bus.async_fire(EVENT_INIM_CLOUD, event_payload)
                    _LOGGER.info("Fired %s: %s", EVENT_INIM_CLOUD, event_payload)

            # Re-fetch data to synchronize full state reliably
            await self.async_request_refresh()

        self._ws_task = asyncio.create_task(
            self.client.async_listen_events(_on_event, lambda: self._is_running)
        )

    async def async_shutdown(self) -> None:
        """Gracefully stop coordinator and WebSocket listener."""
        self._is_running = False
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
            self._ws_task = None
