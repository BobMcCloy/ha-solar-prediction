"""DataUpdateCoordinator for the Solar Prediction integration."""
import logging
from datetime import timedelta
from typing import Any

from aiohttp.client_exceptions import ClientError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.helpers import event
from homeassistant.helpers.storage import Store

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
FALLBACK_SCAN_INTERVAL = timedelta(hours=1, minutes=5)
CACHE_VERSION = 1


class SolarPredictionDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API with dynamic scheduling and caching."""

    def __init__(self, hass: HomeAssistant, access_token: str, project: str, config_entry_id: str):
        """Initialize."""
        self.access_token = access_token
        self.project = project
        self._store = Store(hass, CACHE_VERSION, f"solar_prediction_{config_entry_id}")
        self.last_api_error: str | None = None
        
        super().__init__(
            hass, 
            _LOGGER, 
            name=DOMAIN, 
            update_interval=FALLBACK_SCAN_INTERVAL
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API."""
        api_url = "https://solarprognose.de/web/solarprediction/api/v1"
        
        # Hier sind die wichtigen Parameter fest integriert (MOSMIX Algorithmus)
        params = {
            "access-token": self.access_token,
            "project": self.project,
            "type": "hourly",
            "algorithm": "mosmix"
        }
        
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(api_url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                
                # Prüfen auf Solarprognose interne Fehlermeldungen in der JSON Antwort
                if data.get("status") != 0:
                    error_msg = data.get("message", "Unknown API error")
                    self.last_api_error = error_msg
                    _LOGGER.error("Solarprognose API Error for project %s: %s", self.project, error_msg)
                    return await self._load_from_cache_on_error(error_msg)

                self.last_api_error = None
                # Speichere die erfolgreichen Daten im Cache
                await self._store.async_save({"data": data})
                return data

        except ClientError as err:
            self.last_api_error = str(err)
            _LOGGER.error("Network error communicating with API for project %s: %s", self.project, err)
            return await self._load_from_cache_on_error(str(err))
        except Exception as err:
            self.last_api_error = str(err)
            _LOGGER.exception("Unexpected error for project %s: %s", self.project, err)
            return await self._load_from_cache_on_error(str(err))

    async def _load_from_cache_on_error(self, error_msg: str) -> dict[str, Any]:
        """Load data from cache if API request fails."""
        cached_file_content = await self._store.async_load()
        if cached_file_content and "data" in cached_file_content:
            _LOGGER.info("Using cached data for project %s due to API error.", self.project)
            return cached_file_content["data"]
        
        raise UpdateFailed(f"API Error: {error_msg} and no cached data available.")

    def _schedule_refresh(self) -> None:
        """Schedule the next refresh based on the API's preferred next request time."""
        if self.last_api_error:
            _LOGGER.warning(
                "API error detected for project %s. Falling back to the default refresh interval of %s.",
                self.project,
                self.update_interval
            )
            super()._schedule_refresh()
            return

        if self.last_update_success and self.data:
            try:
                # API Limitierung lesen und nächsten Call entsprechend verzögern
                next_request_epoch = self.data["preferredNextApiRequestAt"]["epochTimeUtc"]
                now_epoch = int(dt_util.utcnow().timestamp())
                # +5 Sekunden Puffer hinzufügen
                delay_seconds = max(0, next_request_epoch - now_epoch) + 5
                
                _LOGGER.debug(
                    "Scheduling next API refresh for project %s in %s seconds as suggested by API",
                    self.project,
                    delay_seconds
                )
                
                if self._unsub_refresh:
                    self._unsub_refresh()
                    self._unsub_refresh = None
                    
                self._unsub_refresh = event.async_call_later(
                    self.hass, delay_seconds, self._handle_refresh_interval
                )
                return
            except (KeyError, TypeError) as e:
                _LOGGER.warning(
                    "Could not determine next refresh time for project %s, falling back to default. Error: %s", 
                    self.project, e
                )
        
        super()._schedule_refresh()
