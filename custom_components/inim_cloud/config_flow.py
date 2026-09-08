"""Config flow and Options flow for Inim Cloud integration."""
import socket
from typing import Any, Dict, Optional
import uuid

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_NAME,
    CONF_SCENARIO_AWAY,
    CONF_SCENARIO_DISARM,
    CONF_SCENARIO_HOME,
    CONF_SCENARIO_NIGHT,
    CONF_SCENARIO_VACATION,
    DOMAIN,
)
from .inim_api import InimApiClient, InimAuthError, InimConnectionError
from .security import encrypt_credential


class InimConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Inim Cloud."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            # Unique ID based on lowercase username
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            # Generate unique client ID and obtain hostname
            client_id = f"ha-{uuid.uuid4().hex[:12]}"
            client_name = socket.gethostname() or "HomeAssistant"

            session = async_get_clientsession(self.hass)
            api_client = InimApiClient(
                session=session,
                username=username,
                password=password,
                client_id=client_id,
                client_name=client_name,
            )

            try:
                # Test authentication and device retrieval
                await api_client.async_login()
                await api_client.async_get_devices()

                # Encrypt password at rest using instance-bound Fernet key
                encrypted_password = encrypt_credential(self.hass, password)

                return self.async_create_entry(
                    title=f"Inim Cloud ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: encrypted_password,
                        CONF_CLIENT_ID: client_id,
                        CONF_CLIENT_NAME: client_name,
                    },
                )
            except InimAuthError:
                errors["base"] = "invalid_auth"
            except InimConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return options flow handler to map scenarios."""
        return InimOptionsFlowHandler()


class InimOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow to configure scenario mappings."""

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the scenario mapping options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Retrieve scenarios dynamically from coordinator data
        coordinator = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        scenarios_options: Dict[int, str] = {-1: "None / Disabilitato"}

        if coordinator and coordinator.data:
            # Aggregate scenarios from available devices
            for dev in coordinator.data.values():
                for sc_id, sc in dev.get("scenarios", {}).items():
                    scenarios_options[sc_id] = f"{sc['name']} (ID: {sc_id})"

        options = self.config_entry.options
        current_disarm = options.get(CONF_SCENARIO_DISARM, -1)
        current_away = options.get(CONF_SCENARIO_AWAY, -1)
        current_home = options.get(CONF_SCENARIO_HOME, -1)
        current_night = options.get(CONF_SCENARIO_NIGHT, -1)
        current_vacation = options.get(CONF_SCENARIO_VACATION, -1)

        # If options not set yet, attempt auto-detection from scenario names
        if current_disarm == -1 or current_away == -1:
            for sc_id, label in scenarios_options.items():
                if sc_id == -1:
                    continue
                lower_label = label.lower()
                if current_disarm == -1 and any(w in lower_label for w in ["spento", "disarm", "off"]):
                    current_disarm = sc_id
                elif current_away == -1 and any(w in lower_label for w in ["totale", "away", "on totale"]):
                    current_away = sc_id
                elif current_home == -1 and any(w in lower_label for w in ["notte", "home", "camere", "parziale"]):
                    current_home = sc_id

        schema = vol.Schema(
            {
                vol.Optional(CONF_SCENARIO_DISARM, default=current_disarm): vol.In(scenarios_options),
                vol.Optional(CONF_SCENARIO_AWAY, default=current_away): vol.In(scenarios_options),
                vol.Optional(CONF_SCENARIO_HOME, default=current_home): vol.In(scenarios_options),
                vol.Optional(CONF_SCENARIO_NIGHT, default=current_night): vol.In(scenarios_options),
                vol.Optional(CONF_SCENARIO_VACATION, default=current_vacation): vol.In(scenarios_options),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
