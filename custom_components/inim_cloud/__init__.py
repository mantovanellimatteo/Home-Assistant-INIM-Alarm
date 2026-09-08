"""Initialization of Inim Cloud integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_CLIENT_ID, CONF_CLIENT_NAME, DOMAIN, PLATFORMS
from .coordinator import InimDataUpdateCoordinator
from .inim_api import InimApiClient
from .security import decrypt_credential

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Inim Cloud from a config entry."""
    username = entry.data[CONF_USERNAME]
    encrypted_password = entry.data[CONF_PASSWORD]
    client_id = entry.data[CONF_CLIENT_ID]
    client_name = entry.data.get(CONF_CLIENT_NAME, "HomeAssistant")

    # Decrypt credential in volatile memory
    password = decrypt_credential(hass, encrypted_password)

    session = async_get_clientsession(hass)
    api_client = InimApiClient(
        session=session,
        username=username,
        password=password,
        client_id=client_id,
        client_name=client_name,
    )

    coordinator = InimDataUpdateCoordinator(hass, api_client, entry.entry_id)

    # Perform initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Start persistent WebSocket for real-time push events
    await coordinator.async_start_websocket()

    # Forward entry setups to alarm_control_panel, select, binary_sensor
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for options flow changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Inim Cloud config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
        if coordinator:
            await coordinator.async_shutdown()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
