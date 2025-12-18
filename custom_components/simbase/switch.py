from typing import Any
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    sim_coordinator = data["sim_coordinator"]
    client = data["client"]

    entities = []
    for iccid in sim_coordinator.data:
        entities.append(SimbaseStatusSwitch(sim_coordinator, client, iccid))
        entities.append(SimbaseIMEILockSwitch(sim_coordinator, client, iccid))

    async_add_entities(entities)

class SimbaseStatusSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable a SIM."""

    def __init__(self, coordinator, client, iccid):
        super().__init__(coordinator)
        self._client = client
        self._iccid = iccid
        self._attr_unique_id = f"{iccid}_status"
        self._attr_name = f"{coordinator.data[iccid].get('name', iccid)} Status"

    @property
    def is_on(self):
        """Return true if SIM is enabled."""
        sim_data = self.coordinator.data.get(self._iccid)
        return sim_data.get("state") == "enabled"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the SIM."""
        await self._client.set_sim_state(self._iccid, "enabled")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the SIM."""
        await self._client.set_sim_state(self._iccid, "disabled")
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._iccid)},
        }

class SimbaseIMEILockSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to enable/disable the Anti-theft IMEI lock."""

    def __init__(self, coordinator, client, iccid):
        super().__init__(coordinator)
        self._client = client
        self._iccid = iccid
        self._attr_unique_id = f"{iccid}_imei_lock"
        self._attr_name = f"{coordinator.data[iccid].get('name', iccid)} IMEI Lock"

    @property
    def is_on(self):
        """Return true if IMEI lock is enabled."""
        sim_data = self.coordinator.data.get(self._iccid)
        return sim_data.get("imei_lock") == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable IMEI lock"""
        await self._client.set_imei_lock(self._iccid, "on")
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the IMEI lock"""
        await self._client.set_imei_lock(self._iccid, "off")
        await self.coordinator.async_request_refresh()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._iccid)},
        }