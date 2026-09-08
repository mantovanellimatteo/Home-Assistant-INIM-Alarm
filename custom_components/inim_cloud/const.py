"""Constants for the Inim Cloud integration."""
from homeassistant.const import Platform

DOMAIN = "inim_cloud"

# Inim Cloud Endpoints
API_BASE_URL = "https://api.inimcloud.com"
WSS_BASE_URL = "wss://ws.inimcloud.com/events"

# Platforms supported
PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
]

# Configuration keys
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_NAME = "client_name"

# Options Flow - Scenario mappings for Alarm Control Panel
CONF_SCENARIO_DISARM = "scenario_disarm"
CONF_SCENARIO_AWAY = "scenario_away"
CONF_SCENARIO_HOME = "scenario_home"
CONF_SCENARIO_NIGHT = "scenario_night"
CONF_SCENARIO_VACATION = "scenario_vacation"

# Inim API default metadata
DEFAULT_CLIENT_PLATFORM = "Inim Home"
DEFAULT_CLIENT_VERSION = "2.4.5"
DEFAULT_CLIENT_INFO = "Inim Home"
DEFAULT_CLIENT_APP = "Inim Home"

# Polling interval (fallback if websocket disconnects)
DEFAULT_SCAN_INTERVAL = 300
