"""DataUpdateCoordinator for Inim Cloud integration."""
import asyncio
from datetime import timedelta
import json
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

    def _format_inim_event(
        self,
        dev_id: Optional[int],
        data_block: Dict[str, Any],
        event_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Format and enrich an incoming Inim Cloud event into a human-readable payload."""
        dev_info = (self.data.get(dev_id, {}) if (self.data and dev_id in self.data) else {})
        raw_name = dev_info.get("name", "")
        model_str = dev_info.get("model", "")

        # Format friendly device name if raw_name looks like firmware/serial (starts with digit)
        if raw_name and not raw_name[0].isdigit():
            dev_name = raw_name
        elif model_str:
            dev_name = f"Inim {model_str}"
        elif dev_id is not None:
            dev_name = f"Inim Centrale {dev_id}"
        else:
            dev_name = "Centrale Inim"

        category = str(data_block.get("Category", "")).upper()
        event_type = str(data_block.get("Type", event_data.get("Type", "")))
        is_restore = bool(data_block.get("IsRestore", False))
        raw_data = str(data_block.get("Data", "")).strip()
        info = data_block.get("Info")
        event_id = data_block.get("DeviceEvent_Id")

        areas = dev_info.get("areas", {})
        category_name = category.title() or "Evento"
        description = ""
        event_class = "generic"

        if category in ("ARM_AREA", "ARM_AREA_STAY") or category.startswith("ARM"):
            is_stay = "STAY" in category or "PARZIALE" in category
            area_name = None
            try:
                data_val = int(raw_data)
                if 170 <= data_val <= 199:
                    area_idx = (data_val - 175) if (data_val >= 175 and is_stay) else (data_val - 170)
                    if area_idx in areas:
                        area_name = areas[area_idx].get("name")
                    else:
                        area_name = f"Area {area_idx + 1}"
                elif data_val in areas:
                    area_name = areas[data_val].get("name")
            except (ValueError, TypeError):
                pass

            if not area_name:
                area_name = f"Area {raw_data}" if raw_data and raw_data != "0" else "Centrale"

            if is_restore:
                category_name = "Disinserimento" if not is_stay else "Disinserimento Parziale"
                description = f"Disinserimento {area_name}" if not is_stay else f"Disinserimento Parziale {area_name}"
            else:
                category_name = "Inserimento Totale" if not is_stay else "Inserimento Parziale"
                description = f"Inserimento Totale {area_name}" if not is_stay else f"Inserimento Parziale {area_name}"
            event_class = "area"

        elif category == "CHANGE" and raw_data.startswith("{"):
            try:
                parsed = json.loads(raw_data)
            except Exception:
                parsed = {}

            if isinstance(parsed, dict):
                area_list = parsed.get("AreaList")
                zone_list = parsed.get("ZoneList")
                if area_list and isinstance(area_list, list):
                    alarm_areas = [str(a.get("Name") or f"Area {a.get('AreaId')}") for a in area_list if a.get("Alarm")]
                    tamper_areas = [str(a.get("Name") or f"Area {a.get('AreaId')}") for a in area_list if a.get("Tamper")]
                    if alarm_areas:
                        category_name = "Allarme"
                        description = "ALLARME IN CORSO: " + ", ".join(alarm_areas)
                        event_class = "alarm"
                    elif tamper_areas:
                        category_name = "Manomissione"
                        description = "MANOMISSIONE: " + ", ".join(tamper_areas)
                        event_class = "tamper"
                    else:
                        armed_states = [a.get("Armed") for a in area_list]
                        if all(st in (0, 4) for st in armed_states):
                            category_name = "Disinserimento"
                            description = "Centrale Disinserita (Tutte le aree a riposo)"
                            event_class = "status_change"
                        elif all(st == 1 for st in armed_states):
                            category_name = "Inserimento Totale"
                            description = "Centrale Inserita (Totale)"
                            event_class = "status_change"
                        else:
                            armed_names = [str(a.get("Name") or f"Area {a.get('AreaId')}") for a in area_list if a.get("Armed") in (1, 2, 3)]
                            if armed_names:
                                category_name = "Inserimento Parziale"
                                description = "Centrale Inserita Parziale (" + ", ".join(armed_names) + ")"
                                event_class = "status_change"
                            else:
                                category_name = "Stato Impianto"
                                description = "Aggiornamento stato aree"
                                event_class = "status_change"

                elif zone_list and isinstance(zone_list, list):
                    alarm_zones = [str(z.get("Name") or f"Zona {z.get('ZoneId')}") for z in zone_list if z.get("AlarmMemory")]
                    tamper_zones = [str(z.get("Name") or f"Zona {z.get('ZoneId')}") for z in zone_list if z.get("TamperMemory")]
                    open_zones = [str(z.get("Name") or f"Zona {z.get('ZoneId')}") for z in zone_list if z.get("Status") == 2]
                    closed_zones = [str(z.get("Name") or f"Zona {z.get('ZoneId')}") for z in zone_list if z.get("Status") == 1]
                    if alarm_zones:
                        category_name = "Memoria Allarme"
                        description = "Memoria Allarme su: " + ", ".join(alarm_zones)
                        event_class = "alarm"
                    elif tamper_zones:
                        category_name = "Manomissione"
                        description = "Manomissione rilevata: " + ", ".join(tamper_zones)
                        event_class = "tamper"
                    elif open_zones:
                        category_name = "Zona Aperta"
                        description = "Zona Aperta: " + ", ".join(open_zones)
                        event_class = "zone"
                    elif closed_zones:
                        category_name = "Zona Chiusa"
                        description = "Zona Chiusa: " + ", ".join(closed_zones)
                        event_class = "zone"
                    else:
                        category_name = "Stato Zone"
                        description = "Aggiornamento stato zone"
                        event_class = "zone"

        elif category == "PIN":
            category_name = "Tastiera"
            description = "Codice PIN inserito su tastiera"
            event_class = "keypad"

        elif "ALARM" in category:
            category_name = "Allarme"
            description = f"ALLARME: {info or raw_data or 'Intrusione'}"
            event_class = "alarm"

        elif "TAMPER" in category:
            category_name = "Manomissione"
            description = f"Manomissione: {info or raw_data or 'Sabotaggio'}"
            event_class = "tamper"

        elif "FAULT" in category or "TROUBLE" in category:
            category_name = "Guasto"
            description = (
                f"Guasto: {info or raw_data or 'Anomalia'}"
                if not is_restore
                else f"Ripristino Guasto: {info or raw_data or 'Anomalia'}"
            )
            event_class = "trouble"

        elif "MAINS" in category or "POWER" in category:
            category_name = "Alimentazione"
            description = "Ripristino Rete 220V" if is_restore else "Assenza Rete 220V"
            event_class = "trouble"

        elif "BATTERY" in category:
            category_name = "Batteria"
            description = "Ripristino Batteria" if is_restore else "Batteria Bassa / Scarica"
            event_class = "trouble"

        else:
            if info and not str(info).isdigit():
                description = str(info)
            elif raw_data and not raw_data.isdigit() and not raw_data.startswith("{"):
                description = raw_data
            else:
                description = f"{category_name} ({event_type})"
            event_class = "generic"

        return {
            "device_id": dev_id,
            "device_name": dev_name,
            "info": description,
            "description": description,
            "category": category_name,
            "raw_category": category,
            "type": str(event_type),
            "event_class": event_class,
            "is_restore": is_restore,
            "event_id": event_id,
            "raw_data": raw_data,
            "timestamp": dt_util.now().isoformat(),
        }

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

                    event_payload = self._format_inim_event(dev_id, data_block, event_data)

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
