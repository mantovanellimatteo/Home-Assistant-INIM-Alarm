# Inim Client (Inim to MQTT Hub)

`inimclient` è un servizio demone scritto in Go che funge da bridge tra i server di **Inim Cloud** e un broker **MQTT** locale (ad esempio, Mosquitto gestito come add-on all'interno di Home Assistant). 
Questo bridge consente di integrare la centrale di allarme Inim in Home Assistant, permettendo di leggerne gli stati e di attivare gli scenari definiti.

---

## Struttura del Progetto

Il progetto si compone di:
1. **`inimclient`**: Il binario Go (compilato staticamente per architetture ELF 64-bit Linux).
2. **`config.yaml`**: Il file di configurazione con i parametri MQTT e le credenziali cifrate per Inim Cloud.
3. **`encrypt.py`**: Script di utilità in Python per cifrare le nuove credenziali Inim da inserire nel file di configurazione.
4. **`inimclient.service`**: File di configurazione per il demone systemd (con politiche di hardening e sicurezza).
5. **Regola logrotate**: Configurazione per la rotazione e compressione automatica dei log di runtime.

---

## Configurazione (`config.yaml`)

Il file di configurazione deve essere posizionato nella cartella `/srv/inim-hub/config.yaml`.
Ecco un esempio di configurazione tipo:

```yaml
mqtt:
  host: "127.0.0.1" # IP del broker MQTT
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

### Gestione Credenziali (Cifratura AES-256-CBC)
Le credenziali (`username` e `password`) per connettersi ad Inim Cloud devono essere cifrate utilizzando l'algoritmo AES-256-CBC con la chiave fissa integrata all'interno del client.

Per cifrare una stringa (es. quando cambi la tua password di Inim), usa lo script Python `encrypt.py` incluso in questo repository:

```bash
python3 encrypt.py "mia_nuova_password"
```

Lo script restituirà la stringa cifrata in Base64 da copiare e incollare all'interno del file `config.yaml`.

---

## Installazione sulla VM

### 1. File di Servizio Systemd
Crea il file `/etc/systemd/system/inimclient.service` con la seguente configurazione di sicurezza ed isolamento:

```ini
[Unit]
Description=Inim hub to mqtt
After=network.target

[Service]
Type=simple
User=administrator
ExecStart=/srv/inim-hub/inimclient
WorkingDirectory=/srv/inim-hub/
Restart=on-failure
RestartSec=300

# Security Hardening (Isolamento)
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
NoNewPrivileges=yes
ReadWritePaths=/srv/inim-hub

[Install]
WantedBy=multi-user.target
```

Ricarica il demone per applicare la nuova configurazione:
```bash
sudo systemctl daemon-reload
```

### 2. Permessi di Sicurezza
Per garantire la sicurezza delle credenziali, assegna la proprietà dei file all'utente che esegue il servizio (es. `administrator`) e imposta permessi restrittivi:

```bash
# Assegna la proprietà della cartella e del config
sudo chown -R administrator:administrator /srv/inim-hub
# Rendi config.yaml leggibile solo dall'utente proprietario
sudo chmod 600 /srv/inim-hub/config.yaml
# Consenti la scrittura della cartella log
sudo chmod -R 700 /srv/inim-hub/log
```

### 3. Rotazione dei Log (`logrotate`)
Per evitare che il file `/srv/inim-hub/log/log.log` riempia lo spazio sul disco della VM, configura logrotate creando il file `/etc/logrotate.d/inimclient`:

```logrotate
/srv/inim-hub/log/log.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

---

## Comandi di Gestione Servizio

* **Avviare il servizio:**
  ```bash
  sudo systemctl start inimclient.service
  ```
* **Fermare il servizio:**
  ```bash
  sudo systemctl stop inimclient.service
  ```
* **Riavviare il servizio:**
  ```bash
  sudo systemctl restart inimclient.service
  ```
* **Verificare lo stato del servizio:**
  ```bash
  systemctl status inimclient.service
  ```
* **Vedere i log in tempo reale (systemd):**
  ```bash
  journalctl -u inimclient.service -f
  ```
* **Vedere i log di runtime di inimclient:**
  ```bash
  tail -f /srv/inim-hub/log/log.log
  ```

---

## Integrazione con Home Assistant (MQTT)

La centrale pubblica e riceve comandi tramite MQTT.

### Esempio di Armamento / Disarmamento (Scenari)
Per attivare uno scenario specifico (ad esempio lo Scenario `0`), invia un comando sul topic MQTT:
* **Topic:** `homeassistant/binary_sensor/inim_scenario_0/command`

Puoi configurare Script e Automazioni all'interno di Home Assistant:

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
