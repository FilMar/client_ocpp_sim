# OCPP Client Simulator Features

This document describes the current and planned features for the OCPP 2.0.1 client simulator.

## Current Features

- **Interactive REPL**: The simulator offers an interactive shell to control the lifecycle of a transaction, send events, and inspect the state.
- **State Management and Persistence**: Simulates the state of connectors and transactions, with automatic saving and loading from a file (`charge_point_state.json`).
- **Core Message Sending and Receiving**: Implements most of the OCPP 2.0.1 messages for managing transactions, configuration, and updates.
- **Multi-EVSE Simulation**: The client is structured to simulate a charging station with multiple EVSEs and connectors.

## Planned Features

-   **Core Implementation**:
    -   [x] **Command-Line Interface (CLI)**.
    -   [x] **OCPP Connection and Communication**.
    -   [x] **Boot Flow and Heartbeat**.
    -   [x] **Basic Handler Management**.
    -   [ ] Handle automatic reconnection in case of connection loss.

-   **Interactive Control (REPL)**:
    -   [x] Create an interactive shell to send manual commands (e.g., `connect`, `authorize`).
    -   [x] Implement methods to send OCPP messages from the charging station to the server.

-   **State Management and Persistence**:
    -   [x] Implement a state machine for connectors (e.g., `Available`, `Preparing`, `Charging`, `Finished`).
    -   [x] Use a JSON file (`charge_point_state.json`) to load the initial configuration and persist the last known state of the charging station.

-   **Connection Security**:
    -   [ ] Implement support for secure connections via WebSocket over TLS (`wss://`).
    -   [ ] (Optional) Add support for mutual TLS (mTLS) with client certificates.

-   **Multi-Connector Management**:
    -   [x] Simulate a charging station with multiple charging points (EVSEs) and connectors.
    -   [x] Manage independent state for each connector.

-   **Error Simulation**:
    -   [ ] Add the ability to simulate faults (e.g., `GroundFault`, `OverCurrentFail`) via `StatusNotification`.

-   **Automated Scenarios**:
    -   [ ] Execute predefined action sequences from a scenario file (e.g., YAML or JSON).

---

## OCPP Message Requirements (As requested)

This section tracks the implementation of the specific required messages.

### Messages Sent by CSMS (Handlers implemented)

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

### Messages Sent by the Charging Station (Implemented via REPL or automatically)

-   [x] `BootNotification` (on startup)
-   [x] `Heartbeat` (periodic)
-   [x] `StatusNotification`
-   [x] `Authorize`
-   [x] `TransactionEvent`
-   [x] `NotifyEvent`
-   [x] `MeterValues`
-   [x] `FirmwareStatusNotification` (in response to `UpdateFirmware`)
-   [x] `LogStatusNotification` (in response to `GetLog`)
-   [ ] `DataTransfer`
