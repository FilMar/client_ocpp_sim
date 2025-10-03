"""Handlers for REPL commands."""
import asyncio
import uuid

from ocpp.v201.enums import (
    ConnectorStatusEnumType,
    TransactionEventEnumType,
    TriggerReasonEnumType,
)

from src.state import save_state


async def status(charge_point, *args):
    """Display status of EVSEs."""
    print("--- EVSE Status ---")
    for evse_id, evse_data in charge_point.evses.items():
        tx_info = ""
        if evse_id in charge_point.transactions:
            tx = charge_point.transactions[evse_id]
            state = "Charging" if tx.get("is_charging") or "meter_task" in tx else "Occupied"
            tx_info = f" (State: {state}, TxId: {tx['transaction_id']})"
        print(f"EVSE {evse_id}: {evse_data['status'].value}{tx_info}")
    print("-------------------")


async def logs(charge_point, *args):
    """Display event history."""
    filter_term = args[0] if args else None
    print("--- Event History ---")
    for event in charge_point.history:
        if not filter_term or filter_term.lower() in event.lower():
            print(event)
    print("---------------------")


async def connect(charge_point, evse_id_str):
    """Simulate connecting a vehicle to an EVSE."""
    evse_id = int(evse_id_str)
    charge_point.evses[evse_id]["status"] = ConnectorStatusEnumType.occupied
    await charge_point.send_status_notification(evse_id, ConnectorStatusEnumType.occupied)
    tx_id = str(uuid.uuid4())
    
    try:
        response = await charge_point.send_transaction_event(
            TransactionEventEnumType.started, tx_id, TriggerReasonEnumType.cable_plugged_in, 0, evse_id=evse_id, connector_id=1
        )
        # Solo se il TransactionEvent viene accettato, salviamo la transazione localmente
        charge_point.transactions[evse_id] = {
            "transaction_id": tx_id, "seq_no": 0, "energy": 0, "evse_id": evse_id
        }
        print(f"EVSE {evse_id} Occupied, transaction {tx_id} started.")
        save_state(charge_point)
    except Exception as e:
        print(f"Error starting transaction: {e}")
        # Ripristina lo stato dell'EVSE se la transazione fallisce
        charge_point.evses[evse_id]["status"] = ConnectorStatusEnumType.available
        await charge_point.send_status_notification(evse_id, ConnectorStatusEnumType.available)


async def authorize(charge_point, id_token):
    """Authorize a transaction."""
    await charge_point.send_authorize(id_token)
    print(f"Sent Authorize request for id_token: {id_token}")


async def event(charge_point, event_type, *description_parts):
    """Send a custom NotifyEvent message."""
    if not description_parts:
        print("Usage: event <event_type> <description>")
        return
    description = " ".join(description_parts)
    await charge_point.send_notify_event(event_type, description)
    print(f"Sent NotifyEvent (Type: {event_type}, Description: '{description}')")


async def charge(charge_point, evse_id_str):
    """Start charging."""
    evse_id = int(evse_id_str)
    if evse_id in charge_point.transactions and "meter_task" not in charge_point.transactions[evse_id]:
        tx = charge_point.transactions[evse_id]
        tx["seq_no"] += 1
        await charge_point.send_transaction_event(
            TransactionEventEnumType.updated, tx["transaction_id"], TriggerReasonEnumType.charging_state_changed, tx["seq_no"], evse_id=evse_id, connector_id=1
        )
        task = asyncio.create_task(charge_point.meter_values_sender(evse_id))
        tx["meter_task"] = task
        print(f"Charging started for transaction {tx['transaction_id']}.")
        save_state(charge_point)
    else:
        print("Error: No active transaction or already charging.")


async def stop_charge(charge_point, evse_id_str):
    """Stop charging."""
    evse_id = int(evse_id_str)
    if evse_id in charge_point.transactions and "meter_task" in charge_point.transactions[evse_id]:
        tx = charge_point.transactions[evse_id]
        tx["meter_task"].cancel()
        del tx["meter_task"]
        tx["seq_no"] += 1
        await charge_point.send_transaction_event(
            TransactionEventEnumType.updated, tx["transaction_id"], TriggerReasonEnumType.stop_authorized, tx["seq_no"], evse_id=evse_id, connector_id=1
        )
        print(f"Charging stopped for transaction {tx['transaction_id']}.")
        save_state(charge_point)
    else:
        print("Error: Not charging.")


async def disconnect(charge_point, evse_id_str):
    """Disconnect a vehicle."""
    evse_id = int(evse_id_str)
    tx = charge_point.transactions.pop(evse_id, None)
    if tx:
        if "meter_task" in tx:
            tx["meter_task"].cancel()
        tx["seq_no"] += 1
        await charge_point.send_transaction_event(
            TransactionEventEnumType.ended, tx["transaction_id"], TriggerReasonEnumType.ev_departed, tx["seq_no"], evse_id=evse_id, connector_id=1
        )
        print(f"Transaction {tx['transaction_id']} ended.")
    charge_point.evses[evse_id]["status"] = ConnectorStatusEnumType.available
    await charge_point.send_status_notification(evse_id, ConnectorStatusEnumType.available)
    print(f"EVSE {evse_id} is now Available.")
    save_state(charge_point)


async def quit(charge_point, *args):
    """Exit the application."""
    print("Exiting...")
    save_state(charge_point)
    # This will cause the REPL loop to exit
    raise EOFError
