import math
from datetime import date as date_type
from urllib.parse import urlencode
from personal_assistant.http_client import ServiceError


class WeatherTool:
    def __init__(self, client, timezone, timeout):
        self.client = client
        self.timezone = timezone
        self.timeout = timeout

    def __call__(self) -> dict:
        fields = {
            "high_c": "temperature_2m_max",
            "low_c": "temperature_2m_min",
            "precipitation_mm": "precipitation_sum",
            "peak_hourly_rain_or_snow_probability_pct": "precipitation_probability_max",
            "wmo_weather_code": "weather_code",
        }
        params = urlencode({
            "latitude": 45.31,
            "longitude": -75.90,
            "timezone": self.timezone,
            "forecast_days": 1,
            "daily": ",".join(fields.values()),
        })
        data = self.client.request("https://api.open-meteo.com/v1/forecast?" + params,
                                   timeout=self.timeout)
        try:
            daily = data["daily"]
            date = daily["time"][0]
            date_type.fromisoformat(date)
            result = {"location": "Kanata, Ottawa", "date": date}
            for output, source in fields.items():
                value = daily[source][0]
                if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
                    raise ValueError
                result[output] = value
            return result
        except (KeyError, IndexError, TypeError, ValueError):
            raise ServiceError("invalid_weather_response") from None
