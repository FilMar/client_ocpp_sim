# Funzionalità del Simulatore Client OCPP

Questo documento descrive le funzionalità attuali e pianificate per il simulatore di client OCPP 2.0.1.

## Funzionalità Attuali

- **REPL Interattivo**: Il simulatore offre una shell interattiva per controllare il ciclo di vita di una transazione, inviare eventi e ispezionare lo stato.
- **Gestione Stati e Persistenza**: Simulazione dello stato dei connettori e delle transazioni, con salvataggio e caricamento automatico da file (`charge_point_state.json`).
- **Invio e Ricezione Messaggi Core**: Implementazione della maggior parte dei messaggi OCPP 2.0.1 per la gestione di transazioni, configurazione e aggiornamenti.
- **Simulazione Multi-EVSE**: Il client è strutturato per simulare una colonnina con più EVSE e connettori.

## Funzionalità Pianificate

-   **Implementazione di Base (Core)**:
    -   [x] **Interfaccia a Riga di Comando (CLI)**.
    -   [x] **Connessione e Comunicazione OCPP**.
    -   [x] **Flusso di Avvio e Heartbeat**.
    -   [x] **Gestione Handler di Base**.
    -   [ ] Gestire la riconnessione automatica in caso di perdita di connessione.

-   **Controllo Interattivo (REPL)**:
    -   [x] Creare una shell interattiva per inviare comandi manuali (es. `connect`, `authorize`).
    -   [x] Implementare i metodi per inviare i messaggi OCPP dalla colonnina al server.

-   **Gestione degli Stati e Persistenza**:
    -   [x] Implementare una macchina a stati per i connettori (es. `Available`, `Preparing`, `Charging`, `Finished`).
    -   [x] Utilizzare un file JSON (`charge_point_state.json`) per caricare la configurazione iniziale e persistere l'ultimo stato noto della colonnina.

-   **Sicurezza della Connessione**:
    -   [ ] Implementare il supporto per connessioni sicure tramite WebSocket su TLS (`wss://`).
    -   [ ] (Opzionale) Aggiungere il supporto per TLS reciproco (mTLS) con certificati client.

-   **Gestione Multi-Connettore**:
    -   [x] Simulare una colonnina con più punti di ricarica (EVSEs) e connettori.
    -   [x] Gestire lo stato indipendente per ciascun connettore.

-   **Simulazione di Errori**:
    -   [ ] Aggiungere la capacità di simulare guasti (es. `GroundFault`, `OverCurrentFail`) tramite `StatusNotification`.

-   **Scenari Automatizzati**:
    -   [ ] Eseguire sequenze di azioni predefinite da un file di scenario (es. YAML o JSON).

---

## Requisiti Messaggi OCPP (Come da richiesta)

Questa sezione traccia l'implementazione dei messaggi specifici richiesti.

### Messaggi Inviati dal CSMS (Handler implementati)

-   [x] `SetVariables`
-   [x] `GetVariables`
-   [x] `Reset`
-   [x] `RequestStartTransaction`
-   [x] `RequestStopTransaction`
-   [x] `UnlockConnector`
-   [x] `SetChargingProfile`
-   [x] `GetChargingProfiles`
-   [x] `ClearChargingProfile`
-   [x] `UpdateFirmware`
-   [x] `GetLog`
-   [x] `DataTransfer`

### Messaggi Inviati dalla Colonnina (Implementati tramite REPL o automaticamente)

-   [x] `BootNotification` (all'avvio)
-   [x] `Heartbeat` (periodico)
-   [x] `StatusNotification`
-   [x] `Authorize`
-   [x] `TransactionEvent`
-   [x] `NotifyEvent`
-   [x] `MeterValues`
-   [x] `FirmwareStatusNotification` (in risposta a `UpdateFirmware`)
-   [x] `LogStatusNotification` (in risposta a `GetLog`)
-   [ ] `DataTransfer`