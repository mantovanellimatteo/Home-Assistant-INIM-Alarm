# Inim Client (Inim to MQTT Hub)

Questo repository contiene due implementazioni per interfacciare la tua centrale di allarme **Inim** (tramite Inim Cloud) a un broker **MQTT** locale (es. Mosquitto integrato in Home Assistant):

1. **Versione Python (`inim_mqtt_bridge.py`) [CONSIGLIATA]**: 
   * Scritta da zero in Python.
   * Totalmente open-source, leggera e facilmente personalizzabile/debuggabile.
   * Gestisce in modo nativo il protocollo WebSocket con keep-alive automatico, garantendo **stabilità assoluta senza crash**.
2. **Versione Go (`inimclient`)**: 
   * Il binario pre-compilato originale.
   * Presenta un bug noto del compilatore Go durante la gestione dei tentativi di riconnessione WebSocket che lo porta a crashare ogni 60 secondi in caso di disconnessione (generando elevato traffico di riavvii e potenziale ban dell'account).

---

## Struttura del Progetto

* **`inim_mqtt_bridge.py`**: Il codice sorgente del bridge Python.
* **`inimclient`**: Il binario compilato Go originale (backup).
* **`encrypt.py`**: Script di utilità in Python per cifrare le nuove credenziali Inim da inserire nel file di configurazione `config.yaml`.
* **`config.yaml`**: Struttura dei parametri MQTT e credenziali Inim Cloud.

---

## Configurazione (`config.yaml`)

Il file di configurazione deve essere posizionato in `/srv/inim-hub/config.yaml`:

```yaml
mqtt:
  host: "192.168.1.250" # IP del broker MQTT
  port: 1883
  user: "mqttuser"
  password: "mqttpassword"

inim:
  username: "<encrypted_username_base64>"
  password: "<encrypted_password_base64>"
  client-id: "home-9BF57085-7E85-FB85-C06C-B5C8CFD93C85"
  scenarios:
    - 0
    - 2
    - 4

log:
  level: "INFO" # INFO per uso normale, DEBUG in fase di risoluzione problemi
```

### Cifratura delle Credenziali
Le credenziali Inim devono essere cifrate in AES-256-CBC tramite lo script `encrypt.py`:
```bash
python3 encrypt.py "mia_password"
```
Copia il valore Base64 restituito all'interno della sezione `username` e `password` in `config.yaml`.

---

## Installazione della Versione Python

### 1. Prerequisiti sulla VM Debian/Ubuntu
Installa le dipendenze Python necessarie tramite il gestore di pacchetti del sistema:
```bash
sudo apt-get update
sudo apt-get install -y python3-websockets python3-yaml python3-paho-mqtt
```

### 2. Copia i file nella cartella `/srv/inim-hub/`
Assicurati che i file siano posizionati in `/srv/inim-hub/`:
* `/srv/inim-hub/inim_mqtt_bridge.py`
* `/srv/inim-hub/config.yaml`

Imposta i permessi corretti per proteggere le credenziali:
```bash
sudo chown -R administrator:administrator /srv/inim-hub
sudo chmod 600 /srv/inim-hub/config.yaml
sudo chmod 700 /srv/inim-hub/inim_mqtt_bridge.py
```

### 3. File di Servizio Systemd (`inim-python.service`)
Crea il file `/etc/systemd/system/inim-python.service`:

```ini
[Unit]
Description=Inim hub to mqtt (Python Version)
After=network.target

[Service]
Type=simple
User=administrator
ExecStart=/usr/bin/python3 /srv/inim-hub/inim_mqtt_bridge.py
WorkingDirectory=/srv/inim-hub/
Restart=on-failure
RestartSec=60

# Security Hardening (Isolamento)
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
NoNewPrivileges=yes
ReadWritePaths=/srv/inim-hub

[Install]
WantedBy=multi-user.target
```

Attiva ed avvia il servizio:
```bash
sudo systemctl daemon-reload
sudo systemctl enable inim-python.service
sudo systemctl start inim-python.service
```

---

## Comandi utili di manutenzione

* **Verificare lo stato del servizio:**
  ```bash
  systemctl status inim-python.service
  ```
* **Controllare i log di sistema:**
  ```bash
  journalctl -u inim-python.service -f
  ```
* **Visualizzare il file di log del bridge:**
  ```bash
  tail -f /srv/inim-hub/log/python_bridge.log
  ```

---

## Integrazione con Home Assistant

La versione Python è perfettamente retrocompatibile con la precedente versione Go. Mantiene lo stesso schema dei topic MQTT ed espone i sensori e i comandi di armamento in modo trasparente.

**Esempio di Script (`scripts.yaml`):**
```yaml
allarme_inim_on:
  alias: "Attiva Allarme (Scenario 0)"
  sequence:
    - action: mqtt.publish
      data:
        topic: "homeassistant/binary_sensor/inim_scenario_0/command"
        payload: "ON"
```
