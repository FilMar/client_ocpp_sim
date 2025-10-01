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
                evse["connectors"] = {
                    int(k): v for k, v in evse["connectors"].items()
                }
                for conn in evse["connectors"].values():
                    conn["status"] = ConnectorStatusEnumType(conn["status"])
            self.transactions = saved_state.get("transactions", {})
        else:
            self.evses = {
                1: {
                    "connectors": {
                        i: {"status": ConnectorStatusEnumType.available}
                        for i in range(1, connectors + 1)
                    }
                },
            }
            self.transactions = {}

    async def meter_values_sender(self, tx_key):
        """Periodically sends MeterValues for a transaction."""
        transaction = self.transactions[tx_key]

        while True:
            await asyncio.sleep(10)
            transaction["energy"] += 100
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
            await self.send_transaction_event(
                event_type=TransactionEventEnumType.updated,
                transaction_id=transaction["transaction_id"],
                trigger_reason=TriggerReasonEnumType.meter_value_periodic,
                seq_no=transaction["seq_no"],
                evse_id=transaction["evse_id"],
                connector_id=transaction["connector_id"],
                meter_value=meter_value,
            )

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
            
            # Send StatusNotification for all connectors after successful BootNotification
            for evse_id, evse_data in self.evses.items():
                for connector_id, connector_data in evse_data["connectors"].items():
                    await self.send_status_notification(connector_id, connector_data["status"])

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
