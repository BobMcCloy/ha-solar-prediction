"""Sensor platform for Solar Prediction."""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import SolarPredictionDataUpdateCoordinator
from . import SolarPredictionConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolarPredictionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data

    # Wir definieren hier die festen Sensoren
    sensors_to_add: list[SensorEntity] = [
        SolarPredictionDailyTotalSensor(coordinator, "today"),
        SolarPredictionDailyTotalSensor(coordinator, "tomorrow"),
        SolarPredictionCurrentHourSensor(coordinator),
        SolarPredictionStatusSensor(coordinator),
    ]

    async_add_entities(sensors_to_add)


class SolarPredictionStatusSensor(
    CoordinatorEntity[SolarPredictionDataUpdateCoordinator], SensorEntity
):
    """Represents a sensor for the API status."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarPredictionDataUpdateCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project}_status"
        self._attr_translation_key = "api_status"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
            "manufacturer": "solarprognose.de",
            "model": "Cloud API",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> str:
        if self.coordinator.last_api_error:
            return self.coordinator.last_api_error[:255]
        return "OK"

    @property
    def icon(self) -> str:
        return "mdi:cloud-alert" if self.coordinator.last_api_error else "mdi:cloud-check"


class SolarPredictionDailyTotalSensor(
    CoordinatorEntity[SolarPredictionDataUpdateCoordinator], SensorEntity
):
    """Sensor for total daily solar prediction (Today/Tomorrow)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:solar-power"
    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarPredictionDataUpdateCoordinator, day: str):
        super().__init__(coordinator)
        self._day = day
        self._attr_unique_id = f"{coordinator.project}_{day}_total"
        self._attr_name = f"Solar Forecast {day.capitalize()}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
        }

    @property
    def native_value(self) -> float | None:
        """Calculate the total kWh for the specific day."""
        forecast_data = self.coordinator.data.get("data") if self.coordinator.data else None
        if not forecast_data:
            return None

        today = dt_util.now().date()
        target_date = today if self._day == "today" else today + timedelta(days=1)
        
        day_values = []
        for ts_str, values in forecast_data.items():
            dt = dt_util.as_local(dt_util.utc_from_timestamp(int(ts_str)))
            if dt.date() == target_date:
                # Solarprognose API: [timestamp, power_kw, cumulative_kwh]
                val = values[2] if len(values) > 2 else values[1]
                day_values.append(float(val))
        
        return round(max(day_values), 3) if day_values else 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return hourly forecast as a list for easy charting."""
        forecast_data = self.coordinator.data.get("data") if self.coordinator.data else None
        if not forecast_data:
            return None

        today = dt_util.now().date()
        target_date = today if self._day == "today" else today + timedelta(days=1)
        
        chart_data = []
        # Sort timestamps to calculate deltas correctly
        sorted_ts = sorted(forecast_data.keys(), key=int)
        
        for i, ts_str in enumerate(sorted_ts):
            ts_int = int(ts_str)
            dt = dt_util.as_local(dt_util.utc_from_timestamp(ts_int))
            
            if dt.date() == target_date:
                current_vals = forecast_data[ts_str]
                curr_cum = float(current_vals[2] if len(current_vals) > 2 else current_vals[1])
                
                # Calculate hourly delta
                prev_cum = 0.0
                if i > 0:
                    prev_vals = forecast_data[sorted_ts[i-1]]
                    prev_cum = float(prev_vals[2] if len(prev_vals) > 2 else prev_vals[1])
                    # Reset if it's the first hour of a new day or cumulative drops
                    if dt.hour == 0 or curr_cum < prev_cum:
                        prev_cum = 0.0
                
                chart_data.append({
                    "datetime": dt.isoformat(),
                    "hour": dt.hour,
                    "power_kw": round(float(current_vals[1]), 3),
                    "energy_kwh": round(curr_cum - prev_cum, 3)
                })

        return {"forecast": chart_data}


class SolarPredictionCurrentHourSensor(
    CoordinatorEntity[SolarPredictionDataUpdateCoordinator], SensorEntity
):
    """Sensor for the predicted solar power in the current hour."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_icon = "mdi:sun-clock"
    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarPredictionDataUpdateCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project}_current_hour"
        self._attr_name = "Solar Forecast Current Hour"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
        }

    @property
    def native_value(self) -> float | None:
        """Get the power value for the current hour."""
        forecast_data = self.coordinator.data.get("data") if self.coordinator.data else None
        if not forecast_data:
            return None

        now = dt_util.now()
        # Find the entry that matches the current hour
        for ts_str, values in forecast_data.items():
            dt = dt_util.as_local(dt_util.utc_from_timestamp(int(ts_str)))
            if dt.date() == now.date() and dt.hour == now.hour:
                return round(float(values[1]), 3)
        
        return 0.0
