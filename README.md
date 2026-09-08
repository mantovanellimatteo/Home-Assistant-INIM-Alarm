# Inim Cloud per Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Security: AES-Fernet](https://img.shields.io/badge/Security-AES--Fernet%20Encrypted-green.svg)](#sicurezza-e-privacy)
[![Protocol: WSS Push](https://img.shields.io/badge/Protocol-TLS%20%2F%20WSS%20Realtime-blue.svg)](#comunicazioni-cifrate)

Integrazione universale e sicura per centrali di allarme **Inim Electronics** (SmartLiving, Prime, Sol, ecc.) con **Home Assistant**.

Questo repository include:
1. **Integrazione Nativa Home Assistant (`custom_components/inim_cloud`) [CONSIGLIATA]**:
   * Dialoga **direttamente con Inim Cloud** eliminando intermediari come broker MQTT o demoni esterni.
   * **100% Universale:** importa dinamicamente qualsiasi centrale, scenario e sensore di zona del tuo account.
   * **Cifratura delle credenziali a riposo:** password cifrata con AES-Fernet e legata all'identificativo crittografico univoco della tua istanza Home Assistant.
   * **Eventi Real-Time via WebSocket (WSS):** aggiornamenti istantanei push non appena si attiva un allarme o cambia scenario.
   * **Options Flow da UI:** mappatura scenari personalizzabile con menu a tendina direttamente dall'interfaccia grafica.
   * **Entità Allarme Nativa (`alarm_control_panel`):** tastierino a schermo nativo in Lovelace, supporto codici PIN e integrazione con Apple HomeKit, Google Home e Alexa.
   * **Selettore Scenari Illimitato (`select`):** per attivare direttamente qualsiasi scenario presente sulla centrale.
   * **Sensori di Zona Fisici (`binary_sensor`):** porte, finestre e sensori di movimento PIR visibili come entità native.
2. **Bridge Standalone MQTT (`inim_mqtt_bridge.py`)**:
   * La soluzione standalone precedente in Python/MQTT, conservata per retrocompatibilità.

---

## Sicurezza e Privacy

L'integrazione è stata progettata con un focus primario sulla protezione dei dati:

* **Cifratura in Transito Rigorosa (TLS/HTTPS & WSS):**
  Tutte le comunicazioni avvengono tramite canali TLS con verifica rigorosa della catena dei certificati X.509 della CA. Nessun certificato autofirmato o bypass `CERT_NONE`.
* **Cifratura a Riposo delle Credenziali (AES-Fernet):**
  La password non viene mai salvata in chiaro nei file di configurazione (`core.config_entries`). Viene cifrata localmente con una chiave crittografica derivata dall'UUID univoco dell'istanza Home Assistant (`hass.data['core.uuid']`). Anche in caso di esportazione di backup non protetti, le credenziali rimangono indecifrabili.
* **Token di Sessione Temporaneo:**
  La password decifrata viene utilizzata in memoria volatile solo per il login iniziale (`RegisterClient`). Tutte le successive interrogazioni usano esclusivamente il token temporaneo di sessione.
* **Sanitizzazione Automatica dei Log:**
  Password, PIN e token vengono automaticamente oscurati (`***REDACTED***`) per prevenire fughe di dati anche se il livello di log viene impostato a `DEBUG`.

---

## Installazione Integrazione Nativa

### Metodo 1: Tramite HACS (Consigliato per utenti terzi)
1. Apri **HACS** in Home Assistant.
2. Clicca sui tre puntini in alto a destra e seleziona **Repository personalizzati**.
3. Incolla l'URL del repository: `https://github.com/mantovanellimatteo/inimclient`.
4. Come categoria seleziona **Integrazione**.
5. Clicca su **Scarica** e riavvia Home Assistant.

### Metodo 2: Installazione Manuale
1. Copia la cartella `custom_components/inim_cloud/` nella cartella `custom_components/` della tua installazione di Home Assistant (es. `/config/custom_components/inim_cloud/`).
2. Riavvia Home Assistant.

---

## Configurazione

1. In Home Assistant, vai su **Impostazioni → Dispositivi e Servizi → Aggiungi Integrazione**.
2. Cerca **Inim Cloud** e selezionalo.
3. Inserisci il tuo **Username / Email** e la **Password** del tuo account Inim Cloud.
4. Clicca su **Invia**: Home Assistant convaliderà le credenziali, importerà automaticamente le centrali, gli scenari e i sensori di zona.

### Personalizzare la Mappatura degli Scenari (Options Flow)
Ogni centrale può avere nomi e scenari diversi. Per associare i tuoi scenari agli stati standard del pannello allarme di Home Assistant:
1. Vai su **Impostazioni → Dispositivi e Servizi → Inim Cloud**.
2. Clicca sul pulsante **Configura**.
3. Seleziona dai menu a tendina quale scenario associare a:
   * **Disarmato** (es. *SPENTO*)
   * **Armato Fuori Casa / Totale** (es. *ON TOTALE*)
   * **Armato In Casa / Parziale** (es. *NO CAMERE* o *NO BAGNO*)
   * **Armato Notte**
   * **Armato Vacanza**
4. Salva: le modifiche saranno attive immediatamente senza necessità di riavvio.

---

## Entità Esposte

| Piattaforma | Descrizione |
| :--- | :--- |
| `alarm_control_panel` | Pannello principale allarme con stati (*Disarmato*, *Armato Totale*, *Armato Casa*) e tastierino numerico. |
| `select` | Menu a tendina contenente **tutti** gli scenari della centrale per attivarne uno al volo. |
| `binary_sensor` (Guasto) | Sensore diagnostico per rilevare allarmi, manomissioni o guasti generali della centrale. |
| `binary_sensor` (Zone) | Sensori per le singole zone fisiche (porte, finestre, sensori PIR volumetrici rilevati dalla centrale). |

---

## Autori e Licenza
Sviluppato da [Matteo Mantovanelli](https://github.com/mantovanellimatteo). Rilasciato sotto licenza MIT.
