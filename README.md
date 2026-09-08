# Inim Cloud Alarm for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/badge/release-v0.1.0-blue.svg)](https://github.com/mantovanellimatteo/Home-Assistant-INIM-Alarm/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security: AES-Fernet](https://img.shields.io/badge/Security-AES--Fernet%20Encrypted-green.svg)](#security--privacy)
[![Protocol: WSS Push](https://img.shields.io/badge/Protocol-TLS%20%2F%20WSS%20Realtime-blue.svg)](#real-time-push-architecture)

A native, secure, and universal Home Assistant integration for **Inim Electronics** alarm systems (SmartLiving, Prime, Sol, etc.) communicating directly with **Inim Cloud**.

Eliminates the need for MQTT brokers, legacy bridges, or external daemons.

<p align="center">
  <img src="images/screenshot.png" alt="Inim Cloud Device in Home Assistant" width="800">
</p>

---

## Key Features

* **Direct Cloud Connection:** Communicates natively with Inim Cloud over HTTPS and Secure WebSockets (WSS).
* **Real-Time Push Events:** Instant status updates (alarm triggers, scenario changes) through a persistent WebSocket stream.
* **Instance-Bound Credential Encryption:** Passwords are never stored in plaintext. They are encrypted at rest using AES-Fernet with keys tied to your specific Home Assistant instance UUID.
* **100% Dynamic Topology:** No hardcoded scenario IDs or panel identifiers. Automatically detects and imports all panels, scenarios, and physical zones linked to your account.
* **Native Alarm Control Panel:** Provides a standard `alarm_control_panel` entity compatible with Lovelace alarm cards, PIN verification, Apple HomeKit, Google Home, and Amazon Alexa.
* **Direct Scenario Selector:** A `select` dropdown exposing all panel scenarios for one-click activation.
* **Zone & Diagnostic Sensors:** Automatically exposes physical zones (doors, windows, PIR motion sensors) and panel trouble/fault status as `binary_sensor` entities.
* **Interactive Options Flow:** Customize scenario mappings (`disarmed`, `armed_away`, `armed_home`, `armed_night`, `armed_vacation`) directly from the Home Assistant UI without restarting.
* **Multilingual:** Full support for both English and Italian.

---

## Security & Privacy

This integration was designed from the ground up with a strict security-first architecture:

1. **Encrypted in Transit (TLS 1.2 / 1.3):**
   * All REST endpoints (`https://api.inimcloud.com`) and WebSocket streams (`wss://ws.inimcloud.com`) enforce TLS encryption with strict X.509 CA certificate chain validation. No insecure certificate bypasses (`CERT_NONE`) are permitted.
2. **Encrypted at Rest (AES-Fernet):**
   * Passwords stored in Home Assistant storage (`.storage/core.config_entries`) are encrypted using a Fernet key derived from your unique Home Assistant instance ID (`hass.data['core.uuid']`). Even if a configuration backup is leaked or extracted, stored credentials remain unreadable.
3. **Least Privilege Session Tokens:**
   * Passwords are only decrypted in volatile memory during the initial handshake (`RegisterClient`). All subsequent API queries, scenario activations, and WebSocket streams use short-lived session tokens.
4. **Log Sanitization:**
   * An integrated redaction filter automatically masks passwords, session tokens, PINs, and authentication headers (`***REDACTED***`) across all log messages, even when `DEBUG` logging is enabled.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Home Assistant Core                  │
│                                                         │
│  ┌─────────────────────────┐   ┌─────────────────────┐  │
│  │   alarm_control_panel   │   │    select entity    │  │
│  │   (Native Lovelace /    │   │  (All panel native  │  │
│  │    HomeKit / Alexa)     │   │      scenarios)     │  │
│  └────────────┬────────────┘   └──────────┬──────────┘  │
│               │                           │             │
│               ▼                           ▼             │
│         ┌───────────────────────────────────────┐       │
│         │       InimDataUpdateCoordinator       │       │
│         │    (State Cache & Push Distributor)   │       │
│         └───────────────────┬───────────────────┘       │
│                             │                           │
│                             ▼                           │
│         ┌───────────────────────────────────────┐       │
│         │             InimApiClient             │       │
│         │      (AES Decryption & HTTP/WSS)      │       │
│         └───────────────┬───────▲───────────────┘       │
└─────────────────────────┼───────┼───────────────────────┘
          HTTPS REST (TLS)│       │Persistent WSS (TLS Push)
          ActivateScenario│       │Real-time events
          GetDevices      │       │State sync
                          ▼       │
        ┌───────────────────────────────────────────┐
        │                 Inim Cloud                │
        │   api.inimcloud.com / ws.inimcloud.com    │
        └─────────────────────┬─────────────────────┘
                              │
                              ▼
        ┌───────────────────────────────────────────┐
        │         Physical Inim Alarm Panel         │
        │     (SmartLiving / Prime / Sol LAN)       │
        └───────────────────────────────────────────┘
```

---

## Installation

### Method 1: Via HACS (Recommended)

1. Ensure [HACS (Home Assistant Community Store)](https://hacs.xyz/) is installed.
2. In Home Assistant, open **HACS** > **Integrations**.
3. Click the three dots (top right) and select **Custom repositories**.
4. Enter the repository URL:
   ```
   https://github.com/mantovanellimatteo/Home-Assistant-INIM-Alarm
   ```
5. Select **Integration** as the Category and click **Add**.
6. Find **Inim Cloud Alarm** in HACS, click **Download**, and restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release `.zip` from the [Releases](https://github.com/mantovanellimatteo/Home-Assistant-INIM-Alarm/releases) page.
2. Extract and copy the `custom_components/inim_cloud` directory to your Home Assistant configuration directory:
   ```
   <config_dir>/custom_components/inim_cloud/
   ```
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **+ Add Integration** in the bottom right corner.
3. Search for **Inim Cloud** and select it.
4. Enter your Inim Cloud **Email / Username** and **Password**.
5. Click **Submit**. The integration will validate credentials with Inim Cloud, encrypt the password at rest, and discover all devices.

### Customizing Scenario Mappings (Options Flow)

Because every installation has different scenario names and configurations, you can easily map your panel's scenarios to standard Home Assistant alarm states:

1. Go to **Settings** > **Devices & Services** > **Inim Cloud**.
2. Click **Configure**.
3. Use the dropdown menus to select which scenario activates for each mode:
   * **Disarmed** (e.g. *SPENTO* / *Disarm*)
   * **Armed Away** (e.g. *ON TOTALE* / *Away*)
   * **Armed Home** (e.g. *NO CAMERE* / *Stay*)
   * **Armed Night** (e.g. *NOTTE* / *Night*)
   * **Armed Vacation** (e.g. *VACANZA*)
4. Click **Submit**. Changes apply immediately without requiring a restart.

---

## Entities Provided

| Platform | Entity Name | Description |
| :--- | :--- | :--- |
| `alarm_control_panel` | `alarm_control_panel.inim_alarm_<id>` | Full alarm control with Arm Away, Arm Home, Arm Night, and Disarm controls. |
| `select` | `select.inim_alarm_<id>_scenario` | Dropdown selector displaying and activating any panel scenario directly. |
| `binary_sensor` | `binary_sensor.inim_fault_sensor_<id>` | Diagnostic sensor reporting trouble, tamper, or fault states on the panel. |
| `binary_sensor` | `binary_sensor.inim_zone_<id>_<zone_id>` | Individual physical zone sensors (Door, Window, Motion) with open/alarm states. |

---

## Debugging & Logs

To enable verbose debug logging for this integration, add the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.inim_cloud: debug
```

> **Note:** Sensitive data such as passwords, tokens, and PINs are automatically redacted from logs.

---

## Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [Issues page](https://github.com/mantovanellimatteo/Home-Assistant-INIM-Alarm/issues).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
