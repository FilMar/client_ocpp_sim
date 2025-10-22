import asyncio
from datetime import datetime, timezone

from ocpp.routing import on
from ocpp.v201 import call_result
from ocpp.v201.enums import (
    Action,
    ChargingProfileStatusEnumType,
    ClearChargingProfileStatusEnumType,
    ConnectorStatusEnumType,
    DataTransferStatusEnumType,
    FirmwareStatusEnumType,
    GenericStatusEnumType,
    GetChargingProfileStatusEnumType,
    GetVariableStatusEnumType,
    LogStatusEnumType,
    RequestStartStopStatusEnumType,
    ResetStatusEnumType,
    SetVariableStatusEnumType,
    TransactionEventEnumType,
    TriggerMessageStatusEnumType,
    TriggerReasonEnumType,
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
    async def on_request_start_transaction(self, remote_start_id: int, id_token: dict, evse_id=None, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << RequestStartTransaction (EVSE {evse_id})"
        )

        # Se non è specificato un evse_id, usa il primo disponibile
        if evse_id is None:
            for eid in self.evses.keys():
                if eid not in self.transactions:
                    evse_id = eid
                    break

        if evse_id is None:
            # Nessun EVSE disponibile
            return call_result.RequestStartTransaction(
                status=RequestStartStopStatusEnumType.rejected
            )

        # Avvia la transazione in background
        asyncio.create_task(self._handle_remote_start_transaction(evse_id, remote_start_id, id_token))

        return call_result.RequestStartTransaction(
            status=RequestStartStopStatusEnumType.accepted
        )
    
    async def _handle_remote_start_transaction(self, evse_id, remote_start_id, id_token):
        """Gestisce la creazione della transazione per RequestStartTransaction."""
        import uuid

        # Se c'è già una transazione su questo EVSE
        if evse_id in self.transactions:
            tx = self.transactions[evse_id]

            # Se sta già caricando, ignora
            if "meter_task" in tx:
                self.history.append(
                    f"[{datetime.now(timezone.utc).isoformat()}] Remote start ignored: EVSE {evse_id} is already charging"
                )
                return

            # Se è una transazione normale (già connessa ma non in carica), avvia la ricarica
            if not tx.get("pending_remote_start"):
                tx["seq_no"] += 1

                # Invia TransactionEvent updated con trigger RemoteStart
                response = await self.send_transaction_event(
                    event_type=TransactionEventEnumType.updated,
                    transaction_id=tx["transaction_id"],
                    trigger_reason=TriggerReasonEnumType.remote_start,
                    seq_no=tx["seq_no"],
                    evse_id=evse_id,
                    connector_id=1
                )

                # If server rejected, stop here
                if response is None:
                    self.history.append(
                        f"[{datetime.now(timezone.utc).isoformat()}] Remote start rejected by server for EVSE {evse_id}"
                    )
                    return

                # Cambia lo stato a unavailable durante la ricarica
                self.evses[evse_id]["status"] = ConnectorStatusEnumType.unavailable
                await self.send_status_notification(evse_id, ConnectorStatusEnumType.unavailable)

                # Avvia il meter values sender
                task = asyncio.create_task(self.meter_values_sender(evse_id))
                tx["meter_task"] = task
                tx["remote_start_id"] = remote_start_id

                self.history.append(
                    f"[{datetime.now(timezone.utc).isoformat()}] Remote start: charging started on already connected EVSE {evse_id}"
                )

                # Salva lo stato
                from .state import save_state
                save_state(self)
                return
            else:
                # È già un remote start pending, ignora
                self.history.append(
                    f"[{datetime.now(timezone.utc).isoformat()}] Remote start ignored: EVSE {evse_id} already has a pending remote start"
                )
                return

        # Nessuna transazione esistente: crea una nuova transazione con stato pending_remote_start
        tx_id = str(uuid.uuid4())

        # Invia TransactionEvent started con trigger RemoteStart
        response = await self.send_transaction_event(
            event_type=TransactionEventEnumType.started,
            transaction_id=tx_id,
            trigger_reason=TriggerReasonEnumType.remote_start,
            seq_no=0,
            evse_id=evse_id,
            connector_id=1
        )

        if response is not None:
            # Salva la transazione con flag che indica che è in attesa del plug-in
            self.transactions[evse_id] = {
                "transaction_id": tx_id,
                "seq_no": 0,
                "energy": 0,
                "evse_id": evse_id,
                "pending_remote_start": True,
                "remote_start_id": remote_start_id,
                "id_token": id_token
            }

            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] Remote start transaction {tx_id} created for EVSE {evse_id}, waiting for plug-in"
            )

            # Salva lo stato
            from .state import save_state
            save_state(self)

    @on(Action.request_stop_transaction)
    async def on_request_stop_transaction(self, transaction_id: str, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << RequestStopTransaction (TxId: {transaction_id})"
        )
        
        # Trova la transazione corrispondente
        evse_id = None
        for eid, tx in self.transactions.items():
            if tx["transaction_id"] == transaction_id:
                evse_id = eid
                break
        
        if evse_id is None:
            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] RequestStopTransaction rejected: transaction {transaction_id} not found"
            )
            return call_result.RequestStopTransaction(
                status=RequestStartStopStatusEnumType.rejected
            )
        
        tx = self.transactions[evse_id]
        
        # Verifica se sta caricando
        if "meter_task" not in tx:
            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] RequestStopTransaction: transaction {transaction_id} is not charging"
            )
            return call_result.RequestStopTransaction(
                status=RequestStartStopStatusEnumType.accepted
            )
        
        # Ferma la ricarica in background
        asyncio.create_task(self._handle_remote_stop_transaction(evse_id, transaction_id))
        
        return call_result.RequestStopTransaction(
            status=RequestStartStopStatusEnumType.accepted
        )
    
    async def _handle_remote_stop_transaction(self, evse_id, transaction_id):
        """Gestisce lo stop della ricarica per RequestStopTransaction."""
        tx = self.transactions[evse_id]
        
        # Cancella il meter task
        if "meter_task" in tx:
            tx["meter_task"].cancel()
            try:
                await tx["meter_task"]
            except asyncio.CancelledError:
                pass
            del tx["meter_task"]
        
        # Invia TransactionEvent updated con trigger remote_stop
        tx["seq_no"] += 1
        await self.send_transaction_event(
            event_type=TransactionEventEnumType.updated,
            transaction_id=transaction_id,
            trigger_reason=TriggerReasonEnumType.remote_stop,
            seq_no=tx["seq_no"],
            evse_id=evse_id,
            connector_id=1
        )
        
        # Cambia lo stato a occupied (cavo ancora connesso ma non in carica)
        self.evses[evse_id]["status"] = ConnectorStatusEnumType.occupied
        await self.send_status_notification(evse_id, ConnectorStatusEnumType.occupied)
        
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] Remote stop: charging stopped for transaction {transaction_id} on EVSE {evse_id}"
        )
        
        # Salva lo stato
        from .state import save_state
        save_state(self)

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
        profile_id = charging_profile.get("id", "unknown")
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << SetChargingProfile (EVSE: {evse_id}, Profile ID: {profile_id})"
        )

        # Basic validation
        if not charging_profile:
            return call_result.SetChargingProfile(
                status=ChargingProfileStatusEnumType.rejected
            )

        # Validate required fields
        if "id" not in charging_profile:
            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] SetChargingProfile rejected: missing 'id'"
            )
            return call_result.SetChargingProfile(
                status=ChargingProfileStatusEnumType.rejected
            )

        if "charging_schedule" not in charging_profile:
            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] SetChargingProfile rejected: missing 'charging_schedule'"
            )
            return call_result.SetChargingProfile(
                status=ChargingProfileStatusEnumType.rejected
            )

        schedule = charging_profile["charging_schedule"]
        if "charging_rate_unit" not in schedule or "charging_schedule_period" not in schedule:
            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] SetChargingProfile rejected: invalid charging_schedule"
            )
            return call_result.SetChargingProfile(
                status=ChargingProfileStatusEnumType.rejected
            )

        # Check if EVSE exists
        if evse_id not in self.evses:
            self.history.append(
                f"[{datetime.now(timezone.utc).isoformat()}] SetChargingProfile rejected: EVSE {evse_id} not found"
            )
            return call_result.SetChargingProfile(
                status=ChargingProfileStatusEnumType.rejected
            )

        # Save the profile
        self.charging_profiles[evse_id] = charging_profile
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] Charging profile {profile_id} set for EVSE {evse_id}"
        )

        # Save state
        from .state import save_state
        save_state(self)

        return call_result.SetChargingProfile(
            status=ChargingProfileStatusEnumType.accepted
        )

    @on(Action.get_charging_profiles)
    async def on_get_charging_profiles(
        self,
        request_id: int,
        evse_id: int = None,
        charging_profile: dict = None,
        **kwargs
    ):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << GetChargingProfiles (EVSE: {evse_id})"
        )

        # Filter profiles based on request criteria
        if not self.charging_profiles:
            return call_result.GetChargingProfiles(
                status=GetChargingProfileStatusEnumType.no_profiles
            )

        # If evse_id is specified, check if we have a profile for it
        if evse_id is not None:
            if evse_id not in self.charging_profiles:
                return call_result.GetChargingProfiles(
                    status=GetChargingProfileStatusEnumType.no_profiles
                )

            # TODO: In a complete implementation, we should send ReportChargingProfiles
            # with the actual profile data. For now, we just confirm we have it.
            return call_result.GetChargingProfiles(
                status=GetChargingProfileStatusEnumType.accepted
            )

        # If no evse_id specified, return accepted if we have any profiles
        return call_result.GetChargingProfiles(
            status=GetChargingProfileStatusEnumType.accepted
        )

    @on(Action.clear_charging_profile)
    async def on_clear_charging_profile(self, charging_profile_id: int = None, **kwargs):
        self.history.append(
            f"[{datetime.now(timezone.utc).isoformat()}] << ClearChargingProfile"
        )

        if charging_profile_id is None:
            self.charging_profiles.clear()
            return call_result.ClearChargingProfile(
                status=ClearChargingProfileStatusEnumType.accepted
            )

        for evse_id, profile in self.charging_profiles.items():
            if profile.get("id") == charging_profile_id:
                del self.charging_profiles[evse_id]
                return call_result.ClearChargingProfile(
                    status=ClearChargingProfileStatusEnumType.accepted
                )

        return call_result.ClearChargingProfile(
            status=ClearChargingProfileStatusEnumType.unknown
        )

    async def _firmware_update_process(self, request_id: int):
        await asyncio.sleep(2) # Simulate time to start download
        await self.send_firmware_status_notification(FirmwareStatusEnumType.downloading, request_id)
        await asyncio.sleep(10) # Simulate download time
        await self.send_firmware_status_notification(FirmwareStatusEnumType.downloaded, request_id)
        await asyncio.sleep(2)
        await self.send_firmware_status_notification(FirmwareStatusEnumType.installing, request_id)
        await asyncio.sleep(10) # Simulate installation time
        await self.send_firmware_status_notification(FirmwareStatusEnumType.installed, request_id)

    @on(Action.update_firmware)
    async def on_update_firmware(self, request_id: int, **kwargs):
        self.history.append(f"[{datetime.now(timezone.utc).isoformat()}] << UpdateFirmware")
        asyncio.create_task(self._firmware_update_process(request_id))
        return call_result.UpdateFirmware(status=UpdateFirmwareStatusEnumType.accepted)

    async def _log_upload_process(self, request_id: int):
        await asyncio.sleep(1) # Simulate time to start upload
        await self.send_log_status_notification(UploadLogStatusEnumType.uploading, request_id)
        await asyncio.sleep(5)  # Simulate upload time
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
