# OCPP 2.0.1 Client Simulator

This project is a simple command-line **OCPP 2.0.1** client simulator, written in Python. It is designed to simulate the basic behavior of a Charge Point to test connection and communication with a Central System Management System (CSMS).

## Key Features

-   **OCPP 2.0.1 Compliant**: Uses the `ocpp2.0.1` subprotocol over WebSockets.
-   **CLI Interface**: Based on `click` for a simple and intuitive user experience.
-   **Boot Flow**: Executes the `BootNotification` sequence upon connection to register the Charge Point.
-   **Automatic Heartbeat**: Keeps the connection alive by sending periodic `Heartbeat` messages at the interval specified by the CSMS.
-   **Basic Handlers**: Implements minimal responses for server-initiated commands like `Reset`, `RemoteStartTransaction`, and `RemoteStopTransaction`.
-   **Asynchronous**: Built on `asyncio` and `websockets` for efficient communication handling.

## Prerequisites

-   Python 3.13 or higher
-   `uv` (or `pip`) for dependency management

## Installation

1.  **Clone the repository (if you haven't already):**
    ```bash
    git clone <YOUR_REPOSITORY_URL>
    cd ocpp_manager/client_sim
    ```

2.  **Create a virtual environment and install the dependencies:**
    ```bash
    # Create the virtual environment
    uv venv

    # Activate the virtual environment
    source .venv/bin/activate

    # Install the dependencies
    uv pip install -e .
    ```

## Usage

The simulator is run via the `client-sim` command.

**Syntax:**
```bash
client-sim run <WS_URL> [OPTIONS]
```

**Arguments:**

-   `WS_URL`: The WebSocket URL of your CSMS (e.g., `ws://localhost:9000`).

**Main Options:**

-   `--cp-id TEXT`: The Charge Point identifier (default: `CP001`).
-   `--vendor TEXT`: The manufacturer's name (default: `AcmeCorp`).
-   `--model TEXT`: The station model (default: `ModelX`).
-   `--firmware TEXT`: The firmware version (optional).
-   `--log-level [DEBUG|INFO|WARNING|ERROR]`: Sets the logging level (default: `INFO`).
-   `-h, --help`: Shows the help message.

**Example:**

To connect a Charge Point with the ID `CP_TEST_01` to a local server:
```bash
client-sim run ws://localhost:9000 --cp-id CP_TEST_01 --vendor "My Test Inc."
```

Once connected, the client will send a `BootNotification`, start sending `Heartbeats`, and listen for commands from the server. To stop the client, press `Ctrl+C`.

## Roadmap

This project is in its early stages. Future developments include:

-   [ ] **Code Refactoring**: Split the logic into dedicated files (`client.py`, `handlers.py`, `config.py`).
-   [ ] **State Management**: Implement a state machine for connectors (e.g., `Available`, `Preparing`, `Charging`, `Finished`).
-   [ ] **Full Charging Flows**: Add support for `Authorize`, `TransactionEvent`, `StatusNotification`, etc.
-   [ ] **TLS/mTLS Support**: Implement secure connections using `wss://`.
-   [ ] **Add Tests**: Write unit tests with `pytest` to ensure reliability.
