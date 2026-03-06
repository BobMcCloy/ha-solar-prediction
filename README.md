# Home Assistant Integration: Solar Prediction

[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/integration)

This is a custom integration for Home Assistant to retrieve solar forecast data from the [solarprognose.de](https://solarprognose.de) service and provide it as sensors.

Read this document in other languages: [Deutsch](README.de.md)

## Prerequisites

* A running Home Assistant instance.
* A user account at [solarprognose.de](https://solarprognose.de) to obtain a personal **Access Token**.

## Installation

The easiest way to install this integration is through the [Home Assistant Community Store (HACS)](https://hacs.xyz/).

1.  **(Coming Soon) Via the HACS Default Repository:**
    * Navigate to HACS > Integrations and search for "Solar Prediction".
    * Click "Install".

2.  **Manual Installation via a Custom Repository:**
    * Navigate to HACS > Integrations.
    * Click the three-dots menu in the top right and select "Custom repositories".
    * Add the URL to this repository: `https://github.com/code-chicken/ha-solar-prediction`
    * Select the category "Integration".
    * Click "Add".
    * The integration will now appear in the search, and you can install it like any other.

## Configuration

After installing via HACS, you need to configure the integration in Home Assistant.

1.  Navigate to **Settings > Devices & Services**.
2.  Click the **+ Add Integration** button in the bottom right.
3.  Search for **"Solar Prediction"** and select it.
4.  In the configuration dialog, enter your **Access Token** and your **Project** (e.g., your email address).

## Created Entities

The integration creates one device with the following sensors:

* **Today Total**: The total predicted solar energy for the current day in kWh.
* **Tomorrow Total**: The total predicted solar energy for the next day in kWh.
* **API Status**: Shows the connection status to the `solarprognose.de` API ("OK" or an error message).

The "Today Total" sensor also contains the detailed hourly forecast in its attributes, which can be used for visualizations.

## Example Lovelace Card

Here is an example using the [ApexCharts-Card](https://github.com/RomRider/apexcharts-card) to display the hourly forecast curve and the daily total value:

```yaml
type: vertical-stack
cards:
  - type: entity
    entity: sensor.solar_prediction_today
    name: Solar Prediction Today (Total)
  - type: custom:apexcharts-card
    graph_span: 24h
    span:
      start: day
    series:
      - entity: sensor.solar_prediction_today
        name: Power Forecast
        unit: kW
        type: area
        curve: smooth
        stroke_width: 2
        data_generator: |
          const forecast = entity.attributes.hourly_forecast;
          if (!forecast) return [];
          return Object.entries(forecast).map(([timestamp, values]) => {
            return [new Date(parseInt(timestamp) * 1000), values.power_kw];
          });
    yaxis:
      - min: 0
        decimals: 2
```
*Note: You may need to replace `sensor.solar_prediction_today` with the correct entity ID of your sensor.*

## Contributions

Issues and feature requests are welcome! Please open an [issue in this GitHub repository](https://github.com/code-chicken/ha-solar-prediction/issues).

## License

This project is licensed under the MIT License.
