"""State management for the charge point."""
import copy
import json
import logging
import os

from ocpp.v201.enums import ConnectorStatusEnumType

STATE_FILE = "charge_point_state.json"


def save_state(charge_point):
    """Saves the state of the charge point to a JSON file."""
    evses_to_save = copy.deepcopy(charge_point.evses)
    for evse in evses_to_save.values():
        for conn in evse["connectors"].values():
            conn["status"] = conn["status"].value

    transactions_to_save = {}
    for tx_key, tx_data in charge_point.transactions.items():
        serializable_tx = tx_data.copy()
        is_charging = "meter_task" in serializable_tx
        if is_charging:
            del serializable_tx["meter_task"]
        serializable_tx["is_charging"] = is_charging
        transactions_to_save[tx_key] = serializable_tx

    state = {
        "evses": evses_to_save,
        "transactions": transactions_to_save,
    }

    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)
    logging.info(f"State saved to {STATE_FILE}")


def load_state():
    """Loads the charge point state from a JSON file, if it exists."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                logging.info(f"Loading state from {STATE_FILE}")
                return json.load(f)
        except json.JSONDecodeError:
            logging.error(f"Error reading {STATE_FILE}. Starting with a fresh state.")
            return None
    return None
