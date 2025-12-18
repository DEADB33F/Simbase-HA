import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN, CONF_API_KEY, CONF_USAGE_INTERVAL, CONF_BALANCE_INTERVAL, DEFAULT_USAGE_INTERVAL, DEFAULT_BALANCE_INTERVAL

class SimbaseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title="Simbase Account", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_API_KEY): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SimbaseOptionsFlowHandler()

class SimbaseOptionsFlowHandler(config_entries.OptionsFlow):

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_USAGE_INTERVAL, 
                    default=self.config_entry.options.get(CONF_USAGE_INTERVAL, DEFAULT_USAGE_INTERVAL)
                ): int,
                vol.Optional(
                    CONF_BALANCE_INTERVAL, 
                    default=self.config_entry.options.get(CONF_BALANCE_INTERVAL, DEFAULT_BALANCE_INTERVAL)
                ): int,
            })
        )
