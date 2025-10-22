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
    async def send_status_notification(self, evse_id: int, status: ConnectorStatusEnumType):
        request = call.StatusNotification(
            timestamp=datetime.now(timezone.utc).isoformat(),
            connector_status=status,
            evse_id=evse_id,
            connector_id=1,
        )
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> StatusNotification (EvseId: {evse_id}, ConnectorId: 1, Status: {status})"
        )
        await self.call(request)

    async def send_authorize(self, id_token: str):
        request = call.Authorize(
            id_token={"id_token": id_token, "type": "ISO14443"})
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()
                }] >> Authorize (IdToken: {id_token})"
        )
        response = await self.call(request)
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << Authorize Response ({
                response.id_token_info['status']})"
        )

    async def send_transaction_event(self, event_type: TransactionEventEnumType, transaction_id: str, trigger_reason: TriggerReasonEnumType, seq_no: int, evse_id: int = 1, connector_id: int = 1, meter_value: list = None):
        evse = {"id": evse_id, "connectorId": connector_id}

        request = call.TransactionEvent(
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            trigger_reason=trigger_reason,
            seq_no=seq_no,
            transaction_info={"transaction_id": transaction_id},
            evse=evse,
            meter_value=meter_value,
        )
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> TransactionEvent (Type: {
                event_type}, TxId: {transaction_id})"
        )

        try:
            response = await self.call(request)
            return response
        except Exception as e:
            # Server rejected the transaction (CallError or other exception)
            import logging
            logging.warning(f"TransactionEvent rejected by server: {e}")
            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] << TransactionEvent REJECTED: {e}"
            )
            return None

    async def send_firmware_status_notification(self, status: FirmwareStatusEnumType, request_id: int):
        request = call.FirmwareStatusNotification(
            status=status, request_id=request_id)
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat(
            )}] >> FirmwareStatusNotification (Status: {status})"
        )
        await self.call(request)

    async def send_log_status_notification(self, status: LogStatusEnumType, request_id: int):
        request = call.LogStatusNotification(
            status=status, request_id=request_id)
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()
                }] >> LogStatusNotification (Status: {status})"
        )
        await self.call(request)

    async def send_meter_values(self, evse_id: int, meter_value: list):
        request = call.MeterValues(
            evse_id=evse_id,
            meter_value=meter_value,
        )
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> MeterValues (EvseId: {evse_id})"
        )
        response = await self.call(request)
        return response

    async def send_notify_event(self, event_type: str, description: str):
        request = call.NotifyEvent(
            generated_at=datetime.now(timezone.utc).isoformat(),
            seq_no=0,  # In a real implementation, this should be managed
            event_data=[
                {
                    "eventId": 0,  # In a real implementation, this should be managed
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
            f"[{datetime.now(timezone.utc).isoformat()
                }] >> NotifyEvent (Type: {event_type})"
        )
        await self.call(request)

    async def send_report_charging_profiles(self, request_id: int, evse_id: int, charging_profile: dict, source: str = "CSO"):
        request = call.ReportChargingProfiles(
            request_id=request_id,
            charging_limit_source=source,
            evse_id=evse_id,
            charging_profile=[charging_profile],
        )
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] >> ReportChargingProfiles (RequestId: {request_id}, EvseId: {evse_id}, ProfileId: {charging_profile.get('id', 'unknown')})"
        )
        await self.call(request)
