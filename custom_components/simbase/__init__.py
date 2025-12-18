import logging
import aiohttp
import async_timeout
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.components import webhook
from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN, BASE_URL, CONF_API_KEY, 
    CONF_USAGE_INTERVAL, CONF_BALANCE_INTERVAL,
    DEFAULT_USAGE_INTERVAL, DEFAULT_BALANCE_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch"]

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Simbase component (legacy/yaml support)."""
    # This must return True for the integration to load correctly
    return True
    
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Simbase from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    session = async_get_clientsession(hass)
    client = SimbaseClient(session, api_key)
    webhook_id = f"simbase_{entry.entry_id}"

    # 1. Coordinator for SIMs (Frequent updates: Status, Usage, SMS)
    usage_interval = entry.options.get(CONF_USAGE_INTERVAL, DEFAULT_USAGE_INTERVAL)
    sim_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="simbase_sims",
        update_method=client.get_all_sims,
        update_interval=timedelta(seconds=usage_interval),
    )

    webhook.async_register(
        hass,
        DOMAIN,
        "Simbase SMS Webhook",
        webhook_id,
        handle_webhook
    )
    _LOGGER.info("Simbase Webhook registered: /api/webhook/%s", webhook_id)

    # 2. Coordinator for Account Balance (Infrequent updates)
    balance_interval = entry.options.get(CONF_BALANCE_INTERVAL, DEFAULT_BALANCE_INTERVAL)
    balance_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="simbase_balance",
        update_method=client.get_account_balance,
        update_interval=timedelta(seconds=balance_interval),
    )

    # Initial fetch
    await sim_coordinator.async_config_entry_first_refresh()
    await balance_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "sim_coordinator": sim_coordinator,
        "balance_coordinator": balance_coordinator,
        "client": client,
    }

    async def handle_send_sms(call):
        device_id = call.data.get("target_sim")
        if not device_ids:
            _LOGGER.error("No SIM device selected")
            return

        dev_reg = dr.async_get(hass)
        device_entry = dev_reg.async_get(device_id)
        
        if not device_entry:
            _LOGGER.error("Device %s not found in registry", device_id)
            return

        iccid = None
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                iccid = identifier[1]
                break
        
        if not iccid or iccid == "simbase_account":
            _LOGGER.error("Selected device is not a valid SIM card")
            return
        
        message = str(call.data.get("message"))        
        
        try:
            await client.send_sms(iccid, message)
            _LOGGER.info(f"SMS sent successfully to {iccid}")
        except Exception as err:
            error_msg = str(err)
            persistent_notification.async_create(
                hass,
                title="Simbase SMS Error",
                message=f"Failed to send SMS to {iccid}: {error_msg}",
                notification_id="simbase_sms_error"
            )
    hass.services.async_register(DOMAIN, "send_sms", handle_send_sms)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook from Simbase."""
    try:
        data = await request.json()
    except Exception:
        _LOGGER.error("Invalid JSON received on Simbase webhook")
        return None

    # Simbase format: {"event": "sms", "iccid": "...", "message": "...", ...}
    if data.get("event") == "sms":
        iccid = data.get("iccid")
        message = data.get("message")
        
        _LOGGER.info("SMS Received for %s: %s", iccid, message)

        # 1. Fire a Home Assistant Event (Great for Automations!)
        hass.bus.async_fire("simbase_sms_received", {
            "iccid": iccid,
            "message": message,
            "device_name": data.get("deviceName")
        })

        # 2. (Optional) Update the "Last SMS" sensor immediately
        # We find the coordinator and push the data into it
        for entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id].get("sim_coordinator")
            if coordinator and iccid in coordinator.data:
                coordinator.data[iccid]["last_sms_text"] = message
                coordinator.async_update_listeners()
                break

    # Simbase expects a 200 OK response
    from aiohttp import web
    return web.Response(status=200)

class SimbaseClient:
    def __init__(self, session, api_key):
        self.session = session
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def get_all_sims(self):
        # TODO: pagination
        url = f"{BASE_URL}/simcards"
        async with async_timeout.timeout(10):
            resp = await self.session.get(url, headers=self.headers)
            resp.raise_for_status()
            data = await resp.json()

            # Return a dict keyed by ICCID for easy lookup
            return {sim["iccid"]: sim for sim in data.get("simcards", [])}

    async def get_account_balance(self):
        url = f"{BASE_URL}/account/balance"
        async with async_timeout.timeout(10):
            resp = await self.session.get(url, headers=self.headers)
            resp.raise_for_status()
            return await resp.json()

    async def set_sim_state(self, iccid, state):
        url = f"{BASE_URL}/simcards/{iccid}/state"
        payload = {"state": state}
        async with async_timeout.timeout(10):
            resp = await self.session.patch(url, headers=self.headers, json=payload)
            resp.raise_for_status()

    async def set_imei_lock(self, iccid, state):
        url = f"{BASE_URL}/simcards/{iccid}"
        payload = {"imei_lock": state}
        async with async_timeout.timeout(10):
            resp = await self.session.patch(url, headers=self.headers, json=payload)
            resp.raise_for_status()

    async def send_sms(self, iccid, message):
        url = f"{BASE_URL}/simcards/{iccid}/sms"
        payload = {"message": message}
        
        async with async_timeout.timeout(10):
            resp = await self.session.post(url, headers=self.headers, json=payload)
            
            if resp.status == 202:
                return True # Success
            elif resp.status == 400:
                raise Exception("Validation Error: Check message length/format.")
            elif resp.status == 402:
                raise Exception("Insufficient Balance: Please top up your account.")
            elif resp.status == 404:
                raise Exception("SIM Not Found: The ICCID is invalid.")
            else:
                resp.raise_for_status()

    async def get_last_sms(self, iccid):
        """Fetch the most recent incoming SMS."""
        url = f"{BASE_URL}/simcards/{iccid}/sms"
        async with async_timeout.timeout(10):
            resp = await self.session.get(url, headers=self.headers)
            data = await resp.json()
            # Filter for incoming ('in') messages and return the first one
            messages = [m for m in data.get("messages", []) if m.get("direction") == "in"]
            return messages[0].get("message") if messages else "No messages"