"""Sensor platform for Solar Prediction."""

from __future__ import annotations
import logging
from datetime import timedelta
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

    # Wir definieren hier die zentralen Sensoren (jetzt 7 Stück)
    sensors_to_add: list[SensorEntity] = [
        SolarPredictionDailyTotalSensor(coordinator, "today"),
        SolarPredictionDailyTotalSensor(coordinator, "tomorrow"),
        SolarPredictionDailyTotalSensor(coordinator, "day_after_tomorrow"),
        SolarPredictionRemainingTodaySensor(coordinator),
        SolarPredictionCurrentHourSensor(coordinator),
        SolarPredictionNextHourSensor(coordinator),
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
        self._attr_translation_key = f"{day}_total"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
            "manufacturer": "solarprognose.de",
            "model": "Cloud API",
        }

    @property
    def native_value(self) -> float | None:
        """Calculate the total kWh for the specific day cleanly."""
        forecast_data = self.coordinator.data.get("data") if self.coordinator.data else None
        if not forecast_data:
            return None

        today = dt_util.now().date()
        if self._day == "today":
            target_date = today
        elif self._day == "tomorrow":
            target_date = today + timedelta(days=1)
        elif self._day == "day_after_tomorrow":
            target_date = today + timedelta(days=2)
        else:
            target_date = today
        
        sorted_ts = sorted(forecast_data.keys(), key=int)
        daily_total = 0.0
        
        for i, ts_str in enumerate(sorted_ts):
            ts_int = int(ts_str)
            dt = dt_util.as_local(dt_util.utc_from_timestamp(ts_int))
            
            # Wir berechnen die Differenz für jeden Datenpunkt exakt
            if dt.date() == target_date:
                curr_vals = forecast_data[ts_str]
                # Index 2 ist der kumulative Wert der coordinator.py
                curr_cum = float(curr_vals[2] if len(curr_vals) > 2 else curr_vals[1])
                
                prev_cum = 0.0
                if i > 0:
                    prev_vals = forecast_data[sorted_ts[i-1]]
                    prev_cum = float(prev_vals[2] if len(prev_vals) > 2 else prev_vals[1])
                
                # Stundenwert ist die Differenz zwischen dem aktuellen und vorherigen Zählerstand
                hourly_energy = max(0.0, curr_cum - prev_cum)
                daily_total += hourly_energy
        
        return round(daily_total, 3)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return hourly forecast as a list of objects for easy charting."""
        forecast_data = self.coordinator.data.get("data") if self.coordinator.data else None
        if not forecast_data:
            return None

        today = dt_util.now().date()
        if self._day == "today":
            target_date = today
        elif self._day == "tomorrow":
            target_date = today + timedelta(days=1)
        elif self._day == "day_after_tomorrow":
            target_date = today + timedelta(days=2)
        else:
            target_date = today
        
        chart_data = []
        sorted_ts = sorted(forecast_data.keys(), key=int)
        
        for i, ts_str in enumerate(sorted_ts):
            ts_int = int(ts_str)
            dt = dt_util.as_local(dt_util.utc_from_timestamp(ts_int))
            
            if dt.date() == target_date:
                curr_vals = forecast_data[ts_str]
                curr_power = float(curr_vals[1])
                curr_cum = float(curr_vals[2] if len(curr_vals) > 2 else curr_vals[1])
                
                prev_cum = 0.0
                if i > 0:
                    prev_vals = forecast_data[sorted_ts[i-1]]
                    prev_cum = float(prev_vals[2] if len(prev_vals) > 2 else prev_vals[1])
                
                hourly_energy = max(0.0, curr_cum - prev_cum)
                
                chart_data.append({
                    "datetime": dt.isoformat(),
                    "power_kw": round(curr_power, 3),
                    "energy_kwh": round(hourly_energy, 3)
                })

        return {"forecast": chart_data}


class SolarPredictionRemainingTodaySensor(
    CoordinatorEntity[SolarPredictionDataUpdateCoordinator], SensorEntity
):
    """Sensor for the remaining expected energy for today."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:solar-power-variant"
    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarPredictionDataUpdateCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project}_today_remaining"
        self._attr_translation_key = "today_remaining"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
            "manufacturer": "solarprognose.de",
            "model": "Cloud API",
        }

    @property
    def native_value(self) -> float | None:
        """Calculate the remaining kWh for today (from current hour onwards)."""
        forecast_data = self.coordinator.data.get("data") if self.coordinator.data else None
        if not forecast_data:
            return None

        now = dt_util.now()
        target_date = now.date()
        
        sorted_ts = sorted(forecast_data.keys(), key=int)
        remaining_total = 0.0
        
        for i, ts_str in enumerate(sorted_ts):
            ts_int = int(ts_str)
            dt = dt_util.as_local(dt_util.utc_from_timestamp(ts_int))
            
            # Wir berechnen die Energie nur für den heutigen Tag
            if dt.date() == target_date:
                curr_vals = forecast_data[ts_str]
                curr_cum = float(curr_vals[2] if len(curr_vals) > 2 else curr_vals[1])
                
                prev_cum = 0.0
                if i > 0:
                    prev_vals = forecast_data[sorted_ts[i-1]]
                    prev_cum = float(prev_vals[2] if len(prev_vals) > 2 else prev_vals[1])
                
                hourly_energy = max(0.0, curr_cum - prev_cum)
                
                # Wir addieren nur, wenn die Stunde in der Zukunft liegt oder es die aktuelle Stunde ist
                if dt.hour >= now.hour:
                    remaining_total += hourly_energy
        
        return round(remaining_total, 3)


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
        self._attr_translation_key = "current_hour"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
            "manufacturer": "solarprognose.de",
            "model": "Cloud API",
        }

    @property
    def native_value(self) -> float | None:
        """Get the predicted power value for the current hour."""
        forecast_data = self.coordinator.data.get("data") if self.coordinator.data else None
        if not forecast_data:
            return None

        now = dt_util.now()
        for ts_str, values in forecast_data.items():
            dt = dt_util.as_local(dt_util.utc_from_timestamp(int(ts_str)))
            if dt.date() == now.date() and dt.hour == now.hour:
                return round(float(values[1]), 3)
        
        return 0.0


class SolarPredictionNextHourSensor(
    CoordinatorEntity[SolarPredictionDataUpdateCoordinator], SensorEntity
):
    """Sensor for the predicted solar power in the next hour."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_icon = "mdi:sun-clock-outline"
    _attr_has_entity_name = True

    def __init__(self, coordinator: SolarPredictionDataUpdateCoordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.project}_next_hour"
        self._attr_translation_key = "next_hour"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.project)},
            "name": f"Solar Prediction ({coordinator.project})",
            "manufacturer": "solarprognose.de",
            "model": "Cloud API",
        }

    @property
    def native_value(self) -> float | None:
        """Get the predicted power value for the next hour."""
        forecast_data = self.coordinator.data.get("data") if self.coordinator.data else None
        if not forecast_data:
            return None

        # Wir nehmen die aktuelle Zeit plus 1 Stunde
        next_hour_dt = dt_util.now() + timedelta(hours=1)
        for ts_str, values in forecast_data.items():
            dt = dt_util.as_local(dt_util.utc_from_timestamp(int(ts_str)))
            if dt.date() == next_hour_dt.date() and dt.hour == next_hour_dt.hour:
                return round(float(values[1]), 3)
        
        return 0.0
