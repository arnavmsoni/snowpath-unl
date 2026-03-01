import requests
from datetime import datetime, timezone

def fetch_hourly_weather(lat: float, lon: float):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&hourly=temperature_2m,precipitation,snowfall,wind_speed_10m"
        "&forecast_days=2&timezone=UTC"
    )
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

def get_current_hour_bucket(weather_json):
    times = weather_json["hourly"]["time"]
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%dT%H:00")
    idx = times.index(now_str) if now_str in times else 0
    return {
        "time": times[idx],
        "temperature_2m": weather_json["hourly"]["temperature_2m"][idx],
        "precipitation": weather_json["hourly"]["precipitation"][idx],
        "snowfall": weather_json["hourly"]["snowfall"][idx],
        "wind_speed_10m": weather_json["hourly"]["wind_speed_10m"][idx],
    }

def compute_winter_penalty(hour):
    """
    Multiplier for outdoor walking "cost".
    More snow / near-freezing precip / wind => higher penalty.
    """
    temp = hour["temperature_2m"]
    precip = hour["precipitation"]
    snowfall = hour["snowfall"]
    wind = hour["wind_speed_10m"]

    penalty = 1.0

    # snow
    penalty += min(2.0, snowfall * 0.6)

    # precip around freezing => ice
    if precip > 0.2 and (-2.0 <= temp <= 2.0):
        penalty += 2.0

    # wind => exposure/drift
    penalty += min(1.5, wind / 20.0)

    return float(penalty)