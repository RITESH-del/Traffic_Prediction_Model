
import requests
import pandas as pd
from pathlib import Path

OUTPUT_DIR = Path("data/raw/weather")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

URL = "https://archive-api.open-meteo.com/v1/archive"

HOURLY_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "rain",
    "snowfall",
    "weather_code",
    "visibility",
    "wind_speed_10m",
    "cloud_cover",
    "surface_pressure",
]


def fetch_weather(
    name,
    latitude,
    longitude,
    start_date,
    end_date,
    timezone,
):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": HOURLY_VARIABLES,
        "timezone": timezone,
    }

    response = requests.get(URL, params=params, timeout=120)
    response.raise_for_status()

    payload = response.json()
    weather = pd.DataFrame(payload["hourly"])
    weather = weather.rename(columns={"time": "timestamp"})

    weather["timestamp"] = pd.to_datetime(weather["timestamp"])
    weather = weather.sort_values("timestamp")

    weather["is_fog"] = weather["weather_code"].isin(
        [45, 48]
    ).astype("int8")

    weather["is_rain"] = weather["weather_code"].isin(
        [51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82]
    ).astype("int8")

    weather["is_snow"] = weather["weather_code"].isin(
        [71, 73, 75, 77, 85, 86]
    ).astype("int8")

    weather["is_thunderstorm"] = weather["weather_code"].isin(
        [95, 96, 99]
    ).astype("int8")

    output_path = OUTPUT_DIR / f"{name}_hourly.csv"
    weather.to_csv(output_path, index=False)

    print(f"{name}: saved {len(weather)} hourly records to {output_path}")
    print(weather.head())

    return weather


if __name__ == "__main__":
    # Example dates only. Replace with the actual dates
    # covered by your traffic datasets.

    metr_la_weather = fetch_weather(
        name="metr_la",
        latitude=34.14,
        longitude=-118.36,
        start_date="2012-03-01",
        end_date="2012-06-30",
        timezone="America/Los_Angeles",
    )

    pems_bay_weather = fetch_weather(
        name="pems_bay",
        latitude=37.34,
        longitude=-121.90,
        start_date="2017-01-01",
        end_date="2017-05-31",
        timezone="America/Los_Angeles",
    )
