import asyncio
from datetime import datetime, timezone

from ocpp.routing import on
from ocpp.v201 import call_result
from ocpp.v201.enums import (
    Action,
    ChargingProfileStatusEnumType,
    ClearChargingProfileStatusEnumType,
    DataTransferStatusEnumType,
    FirmwareStatusEnumType,
    GenericStatusEnumType,
    GetChargingProfileStatusEnumType,
    GetVariableStatusEnumType,
    LogStatusEnumType,
    RequestStartStopStatusEnumType,
    ResetStatusEnumType,
    SetVariableStatusEnumType,
    TriggerMessageStatusEnumType,
    UnlockStatusEnumType,
    UpdateFirmwareStatusEnumType,
    UploadLogStatusEnumType,
)


class CoreHandlers:
    @on(Action.reset)
    async def on_reset(self, **kwargs):
        self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] << Reset")
        return call_result.Reset(status=ResetStatusEnumType.accepted)

    @on(Action.request_start_transaction)
    async def on_request_start_transaction(self, remote_start_id: int, id_token: dict, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << RequestStartTransaction"
        )
        return call_result.RequestStartTransaction(
            status=RequestStartStopStatusEnumType.accepted
        )

    @on(Action.request_stop_transaction)
    async def on_request_stop_transaction(self, transaction_id: str, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << RequestStopTransaction"
        )
        return call_result.RequestStopTransaction(
            status=RequestStartStopStatusEnumType.accepted
        )

    @on(Action.change_availability)
    async def on_change_availability(self, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << ChangeAvailability"
        )
        return call_result.ChangeAvailability(status=GenericStatusEnumType.accepted)

    @on(Action.unlock_connector)
    async def on_unlock_connector(self, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << UnlockConnector"
        )
        return call_result.UnlockConnector(status=UnlockStatusEnumType.unlocked)

    @on(Action.set_variables)
    async def on_set_variables(self, set_variable_data: list, **kwargs):
        self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] << SetVariables")
        response_payload = []
        for item in set_variable_data:
            response_payload.append(
                {
                    "attribute_status": SetVariableStatusEnumType.accepted,
                    "component": item["component"],
                    "variable": item["variable"],
                }
            )
        return call_result.SetVariables(set_variable_result=response_payload)

    @on(Action.trigger_message)
    async def on_trigger_message(self, **kwargs):
        self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] << TriggerMessage")
        return call_result.TriggerMessage(status=TriggerMessageStatusEnumType.accepted)

    @on(Action.get_variables)
    async def on_get_variables(self, get_variable_data: list, **kwargs):
        self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] << GetVariables")
        response_payload = []
        for item in get_variable_data:
            response_payload.append(
                {
                    "attribute_status": GetVariableStatusEnumType.unknown_component,
                    "component": item["component"],
                    "variable": item["variable"],
                }
            )
        return call_result.GetVariables(get_variable_result=response_payload)

    @on(Action.set_charging_profile)
    async def on_set_charging_profile(self, evse_id: int, charging_profile: dict, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << SetChargingProfile"
        )
        return call_result.SetChargingProfile(
            status=ChargingProfileStatusEnumType.accepted
        )

    @on(Action.get_charging_profiles)
    async def on_get_charging_profiles(self, request_id: int, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << GetChargingProfiles"
        )
        return call_result.GetChargingProfiles(
            status=GetChargingProfileStatusEnumType.no_profiles
        )

    @on(Action.clear_charging_profile)
    async def on_clear_charging_profile(self, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << ClearChargingProfile"
        )
        return call_result.ClearChargingProfile(
            status=ClearChargingProfileStatusEnumType.accepted
        )

    async def _firmware_update_process(self, request_id: int):
        await asyncio.sleep(2) # Simula il tempo per iniziare il download
        await self.send_firmware_status_notification(FirmwareStatusEnumType.downloading, request_id)
        await asyncio.sleep(10) # Simula il tempo di download
        await self.send_firmware_status_notification(FirmwareStatusEnumType.downloaded, request_id)
        await asyncio.sleep(2)
        await self.send_firmware_status_notification(FirmwareStatusEnumType.installing, request_id)
        await asyncio.sleep(10) # Simula il tempo di installazione
        await self.send_firmware_status_notification(FirmwareStatusEnumType.installed, request_id)

    @on(Action.update_firmware)
    async def on_update_firmware(self, request_id: int, **kwargs):
        self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] << UpdateFirmware")
        asyncio.create_task(self._firmware_update_process(request_id))
        return call_result.UpdateFirmware(status=UpdateFirmwareStatusEnumType.accepted)

    async def _log_upload_process(self, request_id: int):
        await asyncio.sleep(1) # Simula il tempo per iniziare l'upload
        await self.send_log_status_notification(UploadLogStatusEnumType.uploading, request_id)
        await asyncio.sleep(5)  # Simula il tempo di upload
        await self.send_log_status_notification(UploadLogStatusEnumType.uploaded, request_id)

    @on(Action.get_log)
    async def on_get_log(self, log_type: str, request_id: int, **kwargs):
        self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] << GetLog")
        asyncio.create_task(self._log_upload_process(request_id))
        return call_result.GetLog(status=LogStatusEnumType.accepted)

    @on(Action.data_transfer)
    async def on_data_transfer(self, vendor_id: str, **kwargs):
        self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] << DataTransfer")
        return call_result.DataTransfer(status=DataTransferStatusEnumType.accepted)