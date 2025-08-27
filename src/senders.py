from datetime import datetime, timezone

from ocpp.v201 import call
from ocpp.v201.enums import (
    ConnectorStatusEnumType,
    EventNotificationEnumType,
    FirmwareStatusEnumType,
    LogStatusEnumType,
    ReadingContextEnumType,
    TransactionEventEnumType,
    TriggerReasonEnumType,
)


class ChargePointSenderMixin:
    async def send_status_notification(self, evse_id: int, connector_id: int, status: ConnectorStatusEnumType):
        request = call.StatusNotification(
            timestamp=datetime.now(timezone.utc).isoformat(),
            connector_status=status,
            evse_id=evse_id,
            connector_id=connector_id,
        )
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> StatusNotification (EvseId: {evse_id}, ConnectorId: {connector_id}, Status: {status})"
        )
        await self.call(request)

    async def send_authorize(self, id_token: str):
        request = call.Authorize(id_token={"id_token": id_token, "type": "ISO14443"})
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> Authorize (IdToken: {id_token})"
        )
        response = await self.call(request)
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << Authorize Response ({response.id_token_info['status']})"
        )

    async def send_transaction_event(self, event_type: TransactionEventEnumType, transaction_id: str, trigger_reason: TriggerReasonEnumType, seq_no: int, meter_value: list = None):
        request = call.TransactionEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            trigger_reason=trigger_reason,
            seq_no=seq_no,
            transaction_info={"transaction_id": transaction_id},
            meter_value=meter_value,
        )
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> TransactionEvent (Type: {event_type}, TxId: {transaction_id})"
        )
        await self.call(request)

    async def send_meter_values(self, evse_id: int, meter_value: list):
        request = call.MeterValues(
            evse_id=evse_id,
            meter_value=meter_value,
        )
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> MeterValues"
        )
        await self.call(request)

    async def send_firmware_status_notification(self, status: FirmwareStatusEnumType, request_id: int):
        request = call.FirmwareStatusNotification(status=status, request_id=request_id)
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> FirmwareStatusNotification (Status: {status})"
        )
        await self.call(request)

    async def send_log_status_notification(self, status: LogStatusEnumType, request_id: int):
        request = call.LogStatusNotification(status=status, request_id=request_id)
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> LogStatusNotification (Status: {status})"
        )
        await self.call(request)

    async def send_notify_event(self, event_type: str, description: str):
        request = call.NotifyEvent(
            generated_at=datetime.now(timezone.utc).isoformat(),
            seq_no=0,  # In una implementazione reale, questo andrebbe gestito
            event_data=[
                {
                    "eventId": 0,  # In una implementazione reale, questo andrebbe gestito
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "trigger": "Delta",
                    "actualValue": description,
                    "eventNotificationType": EventNotificationEnumType.custom_monitor,
                    "component": {"name": "CustomEvent"},
                    "variable": {"name": event_type},
                }
            ],
        )
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> NotifyEvent (Type: {event_type})"
        )
        await self.call(request)
