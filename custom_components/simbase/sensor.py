from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfInformation, CURRENCY_EURO
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    sim_coordinator = data["sim_coordinator"]
    balance_coordinator = data["balance_coordinator"]

    entities = []
    entities.append(SimbaseBalanceSensor(balance_coordinator, entry))

    # 2. Create a sensor for EACH SIM found
    for iccid in sim_coordinator.data:
        entities.append(SimbaseDataUsageSensor(sim_coordinator, iccid))
        entities.append(SimbaseCostSensor(sim_coordinator, balance_coordinator, iccid))
        entities.append(SimbaseLastSmsSensor(sim_coordinator, iccid))

    async_add_entities(entities)


class SimbaseBalanceSensor(CoordinatorEntity, SensorEntity):
    """Representation of the Account Balance."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_name = "Simbase Account Balance"
    _attr_unique_id = "simbase_account_balance"

    @property
    def native_value(self):
        """Return the balance value as a float."""
        return float(self.coordinator.data.get("balance", 0.0))

    @property
    def native_unit_of_measurement(self):
        """Dynamically return the currency from the API (GBP, EUR, etc.)."""
        return self.coordinator.data.get("currency")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "simbase_account")},
            "name": "Simbase Account",
            "manufacturer": "Simbase",
            "model": "Account",
        }

class SimbaseDataUsageSensor(CoordinatorEntity, SensorEntity):
    """Representation of a SIM's Data Usage."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.KILOBYTES
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:sim"

    def __init__(self, coordinator, iccid):
        super().__init__(coordinator)
        self._iccid = iccid
        self._attr_unique_id = f"{iccid}_data_usage"
        self._attr_name = f"{coordinator.data[iccid].get('name', iccid)} Data Usage"

    @property
    def native_value(self):
        sim_data = self.coordinator.data.get(self._iccid)
        if sim_data and "current_month_usage" in sim_data:
            usage_bytes = float(sim_data["current_month_usage"].get("data", 0.0))
            return float(usage_bytes / 1024 ) 
        return 0.0

    @property
    def device_info(self):
        """Link this entity to a specific SIM device."""
        sim_data = self.coordinator.data.get(self._iccid)
        return {
            "identifiers": {(DOMAIN, self._iccid)},
            "name": sim_data.get("name", self._iccid),
            "manufacturer": "Simbase",
            "model": "SIM Card",
            "hw_version": self._iccid,
            "via_device": (DOMAIN, "simbase_account"),
        }

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        sim_data = self.coordinator.data.get(self._iccid)
        if sim_data:
            return {
                "iccid": self._iccid,
                "msisdn": sim_data.get("msisdn"),
                "imsi": sim_data.get("imsi"),
            }
        return {}

class SimbaseCostSensor(CoordinatorEntity, SensorEntity):
    """Representation of a SIM's monthly cost."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator, balance_coordinator, iccid):
        super().__init__(coordinator)
        self._iccid = iccid
        self._balance_coordinator = balance_coordinator
        self._attr_unique_id = f"{iccid}_monthly_cost"
        self._attr_name = f"{coordinator.data[iccid].get('name', iccid)} Monthly Cost"

    @property
    def native_unit_of_measurement(self):
        """Pull currency from the account balance data."""
        return self._balance_coordinator.data.get("currency", "EUR")
    @property
    def native_value(self):
        sim_data = self.coordinator.data.get(self._iccid)
        if sim_data and "current_month_costs" in sim_data:
            return float(sim_data["current_month_costs"].get("total", 0.0))
        return 0.0

    @property
    def extra_state_attributes(self):
        """Return the cost breakdown as attributes."""
        sim_data = self.coordinator.data.get(self._iccid)
        if sim_data and "current_month_costs" in sim_data:
            costs = sim_data["current_month_costs"]
            return {
                "data_cost": costs.get("data"),
                "sms_cost": costs.get("sms"),
                "line_rental": costs.get("line_rental"),
                "other_costs": costs.get("other"),
                "last_synced": sim_data.get("last_update")
            }
        return {}

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._iccid)}}

class SimbaseLastSmsSensor(CoordinatorEntity, SensorEntity):
    """Sensor for the text of the last received SMS."""
    
    _attr_icon = "mdi:email-alert"
    
    def __init__(self, coordinator, iccid):
        super().__init__(coordinator)
        self._iccid = iccid
        self._attr_unique_id = f"{iccid}_last_sms"
        self._attr_name = f"{coordinator.data[iccid].get('name', iccid)} Last SMS"

    @property
    def native_value(self):
        # We'll need to update the coordinator to include this string
        return self.coordinator.data[self._iccid].get("last_sms_text", "None")

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._iccid)}}

