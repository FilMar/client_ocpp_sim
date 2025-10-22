import asyncio
import collections
import logging
from datetime import datetime, timezone

import websockets
from ocpp.v201 import ChargePoint as ocpp_ChargePoint
from ocpp.v201 import call
from ocpp.v201.enums import (
    BootReasonEnumType,
    ConnectorStatusEnumType,
    ReadingContextEnumType,
    TransactionEventEnumType,
    TriggerReasonEnumType,
)

from .handlers import CoreHandlers
from .repl.cmd import REPL
from .senders import ChargePointSenderMixin
from .state import load_state


class ChargePoint(ocpp_ChargePoint, CoreHandlers, ChargePointSenderMixin):
    def __init__(self, cp_id, connection, vendor, model, firmware_version=None, connectors=2):
        super().__init__(cp_id, connection)
        self.vendor = vendor
        self.model = model
        self.firmware_version = firmware_version
        self.history = collections.deque(maxlen=50)

        saved_state = load_state()
        if saved_state:
            raw_evses = saved_state.get("evses", {})
            self.evses = {int(k): v for k, v in raw_evses.items()}
            for evse in self.evses.values():
                if "status" in evse:
                    evse["status"] = ConnectorStatusEnumType(evse["status"])
                elif "connectors" in evse:
                    # Migration from old connector-based structure
                    first_connector = list(evse["connectors"].values())[0]
                    evse["status"] = ConnectorStatusEnumType(first_connector["status"])
                    del evse["connectors"]

            # Load transactions and clean up invalid ones
            raw_transactions = saved_state.get("transactions", {})
            self.transactions = {}
            for tx_key, tx_data in raw_transactions.items():
                evse_id = tx_data.get("evse_id")
                # Skip transactions on available EVSEs (inconsistent state)
                if evse_id and evse_id in self.evses:
                    if self.evses[evse_id]["status"] == ConnectorStatusEnumType.available:
                        logging.warning(f"Skipping transaction {tx_data.get('transaction_id')} on available EVSE {evse_id}")
                        continue
                self.transactions[tx_key] = tx_data
        else:
            self.evses = {
                i: {"status": ConnectorStatusEnumType.available}
                for i in range(1, connectors + 1)
            }
            self.transactions = {}
        
        raw_profiles = saved_state.get("charging_profiles", {}) if saved_state else {}
        self.charging_profiles = {int(k): v for k, v in raw_profiles.items()} if raw_profiles else {}

    def get_power_limit(self, evse_id):
        # Simplified: assumes one profile per EVSE and a simple schedule.
        if evse_id in self.charging_profiles:
            profile = self.charging_profiles[evse_id]
            schedule = profile.get("charging_schedule", {})

            if not schedule:
                return 9999  # No schedule defined

            charging_rate_unit = schedule.get("charging_rate_unit", "").lower()
            charging_schedule_period = schedule.get("charging_schedule_period", [])

            if not charging_schedule_period:
                return 9999  # No periods defined

            # Use the first period (simplified - should check timestamps in real implementation)
            limit = charging_schedule_period[0].get("limit", 9999)

            if charging_rate_unit == "w":  # Power in Watts
                return limit
            elif charging_rate_unit == "a":  # Current in Amps, convert to Watts (assuming 230V monophase)
                return limit * 230

        return 9999  # Default high limit if no profile

    async def meter_values_sender(self, tx_key):
        """Periodically sends MeterValues for a transaction."""
        try:
            # Salva il transaction_id originale per verificare che la transazione non sia cambiata
            if tx_key not in self.transactions:
                return
            original_tx_id = self.transactions[tx_key]["transaction_id"]

            while True:
                await asyncio.sleep(10)

                # Verifica che la transazione esista ancora e sia la stessa
                if tx_key not in self.transactions:
                    logging.info(f"Transaction for EVSE {tx_key} no longer exists, stopping meter values")
                    break

                transaction = self.transactions[tx_key]

                # Verifica che sia ancora la stessa transazione (non sostituita)
                if transaction["transaction_id"] != original_tx_id:
                    logging.info(f"Transaction for EVSE {tx_key} has changed, stopping meter values for old transaction")
                    break

                # Verifica che il task sia ancora quello registrato
                if transaction.get("meter_task") != asyncio.current_task():
                    logging.info(f"Meter task for EVSE {tx_key} has been replaced, stopping old task")
                    break

                power_limit = self.get_power_limit(transaction["evse_id"])
                # Simulate energy added in 10 seconds (Wh)
                energy_added = (power_limit * 10) / 3600
                transaction["energy"] += energy_added
                transaction["seq_no"] += 1

                meter_value = [
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "sampledValue": [
                            {
                                "value": transaction["energy"],
                                "context": ReadingContextEnumType.sample_periodic,
                                "measurand": "Energy.Active.Import.Register",
                                "unitOfMeasure": {"unit": "Wh"},
                            }
                        ],
                    }
                ]
                # Send MeterValues message
                await self.send_meter_values(
                    evse_id=transaction["evse_id"],
                    meter_value=meter_value,
                )

                # Send TransactionEvent with meter values
                response = await self.send_transaction_event(
                    event_type=TransactionEventEnumType.updated,
                    transaction_id=transaction["transaction_id"],
                    trigger_reason=TriggerReasonEnumType.meter_value_periodic,
                    seq_no=transaction["seq_no"],
                    evse_id=transaction["evse_id"],
                    connector_id=1,
                    meter_value=meter_value,
                )

                # If server rejected the transaction, stop sending updates
                if response is None:
                    logging.warning(f"Server rejected transaction {transaction['transaction_id']}, stopping meter values sender")
                    # Clean up the transaction
                    if tx_key in self.transactions:
                        del self.transactions[tx_key]
                    # Save state
                    from .state import save_state
                    save_state(self)
                    break
        except asyncio.CancelledError:
            logging.info(f"Meter values sender for EVSE {tx_key} was cancelled")
            raise

    async def resume_transactions(self):
        """
        Informs the CSMS about ongoing transactions after restart.
        According to OCPP 2.0.1, we should send TransactionEvent (updated)
        for all active transactions after BootNotification.
        """
        transactions_to_remove = []

        for tx_key, tx_data in self.transactions.items():
            transaction_id = tx_data.get("transaction_id")
            evse_id = tx_data.get("evse_id")

            # Remove transaction if EVSE is available (no vehicle connected)
            if evse_id and evse_id in self.evses:
                if self.evses[evse_id]["status"] == ConnectorStatusEnumType.available:
                    logging.warning(f"Removing transaction {transaction_id} - EVSE {evse_id} is available (no vehicle)")
                    transactions_to_remove.append(tx_key)
                    continue

            # Skip invalid transactions
            if not transaction_id or not evse_id:
                logging.warning(f"Invalid transaction data for key {tx_key}, skipping")
                transactions_to_remove.append(tx_key)
                continue

            # Handle pending_remote_start transactions - invalidate them
            if tx_data.get("pending_remote_start"):
                logging.info(f"Invalidating pending remote start transaction {transaction_id} after restart")
                transactions_to_remove.append(tx_key)
                continue

            # For active transactions, send TransactionEvent updated
            tx_data["seq_no"] += 1

            # Build meter values with current energy
            meter_value = [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "sampledValue": [
                        {
                            "value": tx_data.get("energy", 0),
                            "context": ReadingContextEnumType.sample_periodic,
                            "measurand": "Energy.Active.Import.Register",
                            "unitOfMeasure": {"unit": "Wh"},
                        }
                    ],
                }
            ]

            logging.info(f"Resuming transaction {transaction_id} on EVSE {evse_id}")
            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] Resuming transaction {transaction_id} after restart"
            )

            # Send TransactionEvent with trigger ChargingStateChanged
            response = await self.send_transaction_event(
                event_type=TransactionEventEnumType.updated,
                transaction_id=transaction_id,
                trigger_reason=TriggerReasonEnumType.charging_state_changed,
                seq_no=tx_data["seq_no"],
                evse_id=evse_id,
                connector_id=1,
                meter_value=meter_value,
            )

            # If server rejected the transaction, mark it for removal
            if response is None:
                logging.warning(f"Server rejected resumed transaction {transaction_id}, removing it")
                transactions_to_remove.append(tx_key)
                continue

        # Remove invalid/pending transactions
        for tx_key in transactions_to_remove:
            del self.transactions[tx_key]

        # Save state after cleanup
        if transactions_to_remove:
            from .state import save_state
            save_state(self)

    async def resume_ongoing_tasks(self):
        """Resumes background tasks after loading the state."""
        for tx_key, tx_data in self.transactions.items():
            if tx_data.get("is_charging"):
                logging.info(f"Resuming charging for transaction {tx_data['transaction_id']}")
                task = asyncio.create_task(self.meter_values_sender(tx_key))
                self.transactions[tx_key]["meter_task"] = task

    async def send_boot_notification(self):
        request = call.BootNotification(
            charging_station={
                "model": self.model,
                "vendor_name": self.vendor,
                "serial_number": f"afef3d68-{self.id}",
                "firmware_version": self.firmware_version,
            },
            reason=BootReasonEnumType.power_up,
        )
        self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] >> BootNotification")
        response = await self.call(request)
        if response.status == "Accepted":
            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] << BootNotification Confirmed"
            )
            asyncio.create_task(self.send_heartbeat(response.interval))

            # Send StatusNotification for all EVSEs after successful BootNotification
            for evse_id, evse_data in self.evses.items():
                await self.send_status_notification(evse_id, evse_data["status"])

            # Resume transactions: inform CSMS about ongoing transactions
            await self.resume_transactions()

    async def send_heartbeat(self, interval):
        while True:
            await self.call(call.Heartbeat())
            self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] >> Heartbeat")
            await asyncio.sleep(interval)


async def start_client(ws_url, cp_id, vendor, model, firmware, connectors):
    uri = f"{ws_url}/{cp_id}"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(
            uri, subprotocols=["ocpp2.0.1"], ping_interval=None
        ) as ws:
            charge_point = ChargePoint(
                cp_id=cp_id,
                connection=ws,
                vendor=vendor,
                model=model,
                firmware_version=firmware,
                connectors=connectors,
            )

            await charge_point.resume_ongoing_tasks()

            ocpp_task = asyncio.create_task(charge_point.start())
            asyncio.create_task(charge_point.send_boot_notification())
            print("Starting REPL...")
            repl = REPL(charge_point)
            await repl.run()

            ocpp_task.cancel()
    except Exception as e:
        print(f"An error occurred: {e}")
