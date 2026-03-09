"""Config flow for the Solar Prediction integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import DOMAIN, CONF_PROJECT

_LOGGER = logging.getLogger(__name__)

# 1. Eingabemaske für Home Assistant
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): str,
        vol.Required(CONF_PROJECT): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Prüft, ob der Token und die ID bei Solarprognose.de gültig sind."""
    api_url = "https://solarprognose.de/web/solarprediction/api/v1"
    
    # Wir nutzen direkt die korrekten Parameter für den Test
    params = {
        "access-token": data[CONF_ACCESS_TOKEN],
        "project": data[CONF_PROJECT],
        "type": "hourly",
        "algorithm": "mosmix"
    }

    session = async_get_clientsession(hass)
    try:
        async with session.get(api_url, params=params) as response:
            response.raise_for_status()
            result = await response.json()
            
            # Die API wirft 'status': 0 wenn es keinen Fehler gab
            if result.get("status") != 0:
                _LOGGER.error("API Error während Setup: %s", result.get("message"))
                raise CannotConnect
            
            # Erfolgreich! Wir geben den Namen für die Integration zurück
            return {"title": f"Solarprognose ({data[CONF_PROJECT]})"}
            
    except Exception as e:
        _LOGGER.error("Netzwerkfehler beim Setup: %s", e)
        raise CannotConnect


class SolarPredictionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Prediction."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        if user_input is not None:
            # WICHTIG: Setzt die Projekt-ID als Unique ID. 
            # Dadurch erlaubt Home Assistant mehrere Instanzen der Integration!
            await self.async_set_unique_id(user_input[CONF_PROJECT])
            self._abort_if_unique_id_configured()

            try:
                # Zugangsdaten testen
                info = await validate_input(self.hass, user_input)
                
                # Wenn alles klappt, Eintrag speichern
                return self.async_create_entry(title=info["title"], data=user_input)
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unerwarteter Fehler im Config Flow")
                errors["base"] = "unknown"

        # Formular anzeigen (entweder initial oder mit Fehlermeldung)
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
