# Inim Cloud Alarm for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/badge/release-v0.1.1-blue.svg)](https://github.com/mantovanellimatteo/Home-Assistant-INIM-Alarm/releases)
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
* **Dedicated Scenario Buttons:** Individual button entities for each native panel scenario to easily trigger them in dashboards or automations.
* **Comprehensive Diagnostic Sensors:** Exposes live power supply voltage (`sensor.inim_voltage_<id>`) and real-time event status (`sensor.inim_last_event_<id>`).
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
│  ┌────────────┴────────────┐   ┌──────────┴──────────┐  │
│  │     button entities     │   │    sensor entities  │  │
│  │   (One-click scenarios) │   │ (Last Event/Voltage)│  │
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
| `button` | `button.<scenario_name>` | Dedicated one-click button for each native scenario (e.g. *ON TOTALE*, *SPENTO*). |
| `select` | `select.inim_alarm_<id>_scenario` | Dropdown selector displaying and activating any panel scenario directly. |
| `sensor` | `sensor.inim_last_event_<id>` | Real-time last event description, category, and metadata from Inim Cloud. |
| `sensor` | `sensor.inim_voltage_<id>` | Power supply and backup battery voltage in Volts (e.g. *13.80 V*). |
| `binary_sensor` | `binary_sensor.inim_fault_sensor_<id>` | Diagnostic sensor reporting trouble, tamper, or fault states on the panel. |
| `binary_sensor` | `binary_sensor.inim_zone_<id>_<zone_id>` | Individual physical zone sensors (Door, Window, Motion) with open/alarm states. |

---

## Detailed Explanation of Sensor Entities

### 1. Last Event Sensor (`sensor.inim_last_event_<device_id>`)
This sensor acts as a live bulletin for everything happening on your physical alarm panel. Whenever the panel registers an action (such as arming from a keypad, a sensor triggering an alarm, a power restoral, or a tamper alert), Inim Cloud pushes the event over WebSocket and updates this entity instantly.

* **State:** Human-readable description of the last event (e.g. `"Disinserimento da Tastiera - Area Ingresso"`, `"Allarme Intrusione - Ingresso"`, `"Centrale: Ripristino Rete 220V"`).
* **Attributes:**
  * `category`: Broad classification (e.g. `Arming`, `Alarm`, `Trouble`, `System`).
  * `event_type`: Specific type identifier (e.g. `Disarm`, `Away`, `ZoneAlarm`, `MainsLoss`).
  * `is_restore`: Boolean indicating if the event is a restoration (`true`) or an active trigger (`false`).
  * `event_id`: Unique identifier assigned by Inim Cloud.
  * `timestamp`: Precise ISO 8601 timestamp of when the event occurred.
  * `raw_data`: Raw payload string received from the panel.

**Lovelace Card Example:**
```yaml
type: entities
title: "Centrale Inim - Stato & Eventi"
entities:
  - entity: sensor.inim_last_event_12345
    name: "Ultimo Evento"
  - type: attribute
    entity: sensor.inim_last_event_12345
    attribute: timestamp
    name: "Orario Evento"
  - type: attribute
    entity: sensor.inim_last_event_12345
    attribute: category
    name: "Categoria"
```

### 2. Voltage Sensor (`sensor.inim_voltage_<device_id>`)
* **State:** Main power supply and backup battery voltage in Volts (e.g. `13.80`).
* **Unit of Measurement:** `V`
* **Device Class:** `voltage`
* **State Class:** `measurement`
* **Use Case:** Monitor the health of the backup battery and receive alerts if a prolonged power outage drops the voltage below the safe operating threshold (e.g. `< 12.0 V`).

---

## Comprehensive Automation Guide

Home Assistant allows you to automate your Inim alarm either using the graphical user interface (UI) or directly in YAML.

### Method 1: Activating Scenarios via UI or Buttons (Recommended)
Each scenario has its own dedicated **Button** entity:
* In UI automations, select **Action** > **Perform Action** > `button.press` > choose the button entity corresponding to your scenario (e.g. `button.on_totale`).

```yaml
alias: "Inim - Arm Away automatically when leaving home"
trigger:
  - trigger: state
    entity_id: zone.home
    to: "0"
action:
  - action: button.press
    target:
      entity_id: button.on_totale
```

---

### Method 2: Real-Time Event Bus Notifications (`inim_cloud_event`)

Whenever the panel emits an event, the integration fires an **`inim_cloud_event`** directly on the Home Assistant Event Bus with the following payload structure:

```yaml
event_type: inim_cloud_event
data:
  device_id: 12345
  device_name: "Inim SmartLiving"
  info: "Disinserimento da Tastiera - Area 1"
  category: "Arming"
  type: "Disarm"
  is_restore: false
  event_id: 987654
  timestamp: "2026-09-18T20:25:00+02:00"
```

#### Safe Notification Template (Handles Manual Test Execution)
> [!TIP]
> In Home Assistant, clicking **"Run Actions" / "Esegui"** manually in the UI executes only the actions block without triggering the event, which leaves the `trigger` variable undefined (`UndefinedError: 'trigger' is undefined`). 
> Using the safe template below ensures that manual tests work smoothly while real events display all live event details:

```yaml
alias: "Inim: Real-Time Push Notification"
description: "Send push notification for any alarm panel event"
trigger:
  - trigger: event
    event_type: inim_cloud_event
condition: []
action:
  - action: notify.notify
    data:
      title: >-
        {% if trigger is defined and trigger.event is defined %}
          {{ trigger.event.data.device_name }} ({{ trigger.event.data.category }})
        {% else %}
          Inim Cloud (Manual Test)
        {% endif %}
      message: >-
        {% if trigger is defined and trigger.event is defined %}
          {{ trigger.event.data.info }}
        {% else %}
          Manual test execution from Home Assistant UI.
        {% endif %}
```

#### Critical Alarm Notification (Bypasses Silent Mode)
Receive a high-priority alert on your mobile device if a burglar alarm or fire event occurs:

```yaml
alias: "Inim: Critical Intrusion Alarm Alert"
trigger:
  - trigger: event
    event_type: inim_cloud_event
condition:
  - condition: template
    value_template: >-
      {{ trigger.event.data.category == 'Alarm' and not trigger.event.data.is_restore }}
action:
  - action: notify.notify
    data:
      title: "🚨 INTRUSION ALARM DETECTED!"
      message: "{{ trigger.event.data.info }}"
      data:
        push:
          sound:
            name: "critical_alarm.caf"
            critical: 1
            volume: 1.0
```

#### Arming / Disarming Announcement via Smart Speakers
Announce who armed or disarmed the alarm over media players:

```yaml
alias: "Inim: Voice Announcement on State Change"
trigger:
  - trigger: event
    event_type: inim_cloud_event
condition:
  - condition: template
    value_template: "{{ trigger.event.data.category in ['Arming', 'Disarm'] }}"
action:
  - action: tts.speak
    target:
      entity_id: tts.google_it_it
    data:
      media_player_entity_id: media_player.living_room_speaker
      message: "Attenzione: {{ trigger.event.data.info }}"
```

#### Low Voltage / Battery Warning Alert
```yaml
alias: "Inim: Low Battery Voltage Warning"
trigger:
  - trigger: numeric_state
    entity_id: sensor.inim_voltage_12345
    below: 12.2
    for:
      minutes: 5
action:
  - action: notify.notify
    data:
      title: "⚠️ Inim Battery Warning"
      message: "Backup battery voltage is low ({{ states('sensor.inim_voltage_12345') }} V)!"
```

---

### How to Test Events in Home Assistant

To test and verify that your event-based automations work without having to trigger a physical alarm:

1. Open Home Assistant and navigate to **Developer Tools** > **Events** tab.
2. In the **Fire Event** section:
   * **Event type:** `inim_cloud_event`
   * **Event data (YAML):**
     ```yaml
     device_name: "Inim SmartLiving"
     category: "Alarm"
     type: "Intrusion"
     info: "Allarme Intrusione - Finestra Salotto"
     is_restore: false
     ```
3. Click **Fire Event**.
4. Your automation will trigger immediately and send the notification with the simulated parameters.

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
